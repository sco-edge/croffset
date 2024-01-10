#!/usr/bin/python3
import subprocess
import tempfile
import json
import os
import matplotlib.pyplot as pp
import numpy as np
import re
import time
import argparse

class FlowStat:
    sport:int = None
    dport:int = None
    throughput:float = None
    retransmissions:int = None
    iperf_rtt_mean:int = None
    sutilization:float = None
    dutilization:float = None
    nic_rtt_mean:float = None
    nic_rtt_std:float = None
    tcp_rtt_mean:float = None
    tcp_rtt_std:float = None

class NeperFlowStat:
    sport:int = None
    dport:int = None
    throughput:float = None
    nic_rtt_mean:float = None
    nic_rtt_std:float = None
    tcp_rtt_mean:float = None
    tcp_rtt_std:float = None

def main():
    num_flows = int(args.flow)
    time = int(args.time)
    server_addr = "192.168.2.103"
    interface = "ens801f0"
    cca = "cubic"

    global experiment

    if args.vxlan:
        experiment = f"tx-e-f{num_flows}-t{time}-{cca}-0"
    else:
        experiment = f"tx-h-f{num_flows}-t{time}-{cca}-0"

    os.chdir("..")
    if not os.path.exists("data"):
        os.mkdir("data")
    os.chdir("data")

    while os.path.exists(experiment):
        (remained, last) = experiment.rsplit("-", 1)
        trial = int(last) + 1
        experiment = f"{remained}-{trial}"

    os.mkdir(experiment)
    os.chdir(experiment)

    (util_p, util_f) = start_cpu_utilization()
    interrupt_f = get_interrupt_count()
    (epping_p, epping_f) = start_epping(interface)

    if not args.no_bpftrace:
        (bpftrace_p, bpftrace_f) = start_bpftrace()

    # Using neper
    if args.neper:
        flows = run_neper_clients(num_flows, time, server_addr)
    # Using iperf
    else:
        if args.vxlan or args.native:
            server_addrs = get_k8s_iperf_server_addrs()
            client_pods = get_k8s_iperf_client_pods()

            if len(server_addrs) == 0 or len(client_pods) == 0:
                epping_p.kill()
                util_p.kill()
                if not args.no_bpftrace:
                    bpftrace_p.kill()
                print('Check that kubeconfig is properly set.')
                exit(-1)
            flows = run_k8s_iperf_clients(num_flows, time, server_addrs, client_pods)
        else:    
            flows = run_iperf_clients(num_flows, time, server_addr)

    end_cpu_utilization(util_p, util_f)
    process_interrupt_count(interrupt_f)
    epping_map = end_epping(epping_p, epping_f, flows)
    if not args.no_bpftrace:
        bpftrace_map = end_bpftrace(bpftrace_p, bpftrace_f, flows)
    else:
        bpftrace_map = {}

    if epping_map == None or bpftrace_map == None:
        return
    
    json_data = {}
    aggregate_throughput = 0
    peak = 0
    reduced_time = 6000000000

    print(f'{experiment}')
    if args.neper:
        print('i {0:>12} {1:>12} {2:>19} {3:>19} {4:>18}'. format('flow', 'tput', 'nic_rtt', 'tcp_rtt', 'offset'))
    else:
        print('i {0:>12} {1:>10} {2:>5} {3:>19} {4:>19} {5:>18}'. format('flow', 'tput', 'rtx', 'nic_rtt', 'tcp_rtt', 'offset'))

    for i, flow in enumerate(flows):
        flow.nic_rtt_mean = np.average(epping_map[i][1])
        flow.nic_rtt_std = np.std(epping_map[i][1])

        if not args.no_bpftrace:
            flow.tcp_rtt_mean = np.average(bpftrace_map[i][1])
            flow.tcp_rtt_std = np.std(bpftrace_map[i][1])

            peak_per_flow = max(np.max(bpftrace_map[i][1]), np.max(epping_map[i][1]))
            if peak_per_flow >= peak:
                peak = peak_per_flow
            
            max_time_per_flow = min(np.max(bpftrace_map[i][0]), np.max(epping_map[i][0]))
            if max_time_per_flow <= reduced_time:
                reduced_time = max_time_per_flow
        else:
            flow.tcp_rtt_mean = flow.iperf_rtt_mean
            flow.tcp_rtt_std = 0

            peak_per_flow = np.max(epping_map[i][1])
            if peak_per_flow >= peak:
                peak = peak_per_flow
            
            max_time_per_flow = np.max(epping_map[i][0])
            if max_time_per_flow <= reduced_time:
                reduced_time = max_time_per_flow

        gbps = flow.throughput
        diff = flow.tcp_rtt_mean - flow.nic_rtt_mean
        if args.neper:
#             print(f'{i} ({flow.sport}-{flow.dport}): {gbps:>4.1f} qps, \
# {flow.nic_rtt_mean:>6.1f} us ({flow.nic_rtt_std:>6.2f}), {flow.tcp_rtt_mean:>6.1f} us ({flow.tcp_rtt_std:>6.2f}), {diff:>5.1f} us ({(diff/flow.nic_rtt_mean * 100):>5.1f}%)')
            print(f'{i} (00000-{flow.dport}): {gbps:>4.1f} qps, \
{flow.nic_rtt_mean:>6.1f} us ({flow.nic_rtt_std:>6.2f}), {flow.tcp_rtt_mean:>6.1f} us ({flow.tcp_rtt_std:>6.2f}), {diff:>5.1f} us ({(diff/flow.nic_rtt_mean * 100):>5.1f}%)')
        else:
            print(f'{i} ({flow.sport}-{flow.dport}): {gbps:>4.1f} Gbps, {flow.retransmissions:>4}, \
{flow.nic_rtt_mean:>6.1f} us ({flow.nic_rtt_std:>6.2f}), {flow.tcp_rtt_mean:>6.1f} us ({flow.tcp_rtt_std:>6.2f}), {diff:>5.1f} us ({(diff/flow.nic_rtt_mean * 100):>5.1f}%)')
        aggregate_throughput += flow.throughput
        json_data[f"flow{i}"] = vars(flow)

    print(f'Aggregate Throughput: {aggregate_throughput:.1f} Gbps')
    json_data["aggregate throughput"] = aggregate_throughput
    with open(f'summary.{experiment}.json', 'w') as f:
        json.dump(json_data, f)
    
    plot_graphs(epping_map, bpftrace_map, peak_per_flow, reduced_time)

def start_cpu_utilization():
    f = tempfile.NamedTemporaryFile()
    p = subprocess.Popen(['./cpuload.sh'], stdout=f, cwd='../../iperfs')

    return (p, f)

def end_cpu_utilization(p, f):
    p.kill()
    with open(f'cpu.{experiment}.out', 'w') as cpu_output:
        subprocess.run(["./cpu.py", f.name], stdout=cpu_output, cwd='../../iperfs')

    if not args.silent:
        subprocess.run(["./cpu.py", "-c", f.name], cwd='../../iperfs')
    
def get_interrupt_count():
    f = tempfile.NamedTemporaryFile()
    subprocess.run(["cat", "/proc/interrupts"], stdout=f)

    return f

def process_interrupt_count(old_f):
    new_f = tempfile.NamedTemporaryFile()
    subprocess.run(["cat", "/proc/interrupts"], stdout=new_f)

    with open(f'int.{experiment}.out', 'w') as interrupt_output:
        subprocess.run(["./interrupts.py", old_f.name, new_f.name], stdout=interrupt_output, cwd='../../iperfs')

    if not args.silent:
        subprocess.run(["./interrupts.py", old_f.name, new_f.name], cwd='../../iperfs')

def start_epping(interface):
    # f = tempfile.NamedTemporaryFile()
    with open(f'raw.epping.{experiment}.out', 'w') as f:
        if args.vxlan:
            p = subprocess.Popen(["./pping", "-i", interface, "-V"], stdout=f, cwd='../..')
        else:
            p = subprocess.Popen(["./pping", "-i", interface], stdout=f, cwd='../..')

    time.sleep(2)
    return (p, f)

def end_epping(epping_p, epping_f, flows):
    epping_p.kill()

    epping_map = {}

    with open(epping_f.name, 'r') as epping_f:
        for (i, flow) in enumerate(flows):
            epping_f.seek(0)
            if args.vxlan:
                print(f"{i}: UDP 192.168.2.103:{str(flow.dport)}+192.168.2.102:{str(flow.sport)}")
                target = ":" + str(flow.dport) + "+" + "192.168.2.102" + ":" + str(flow.sport)
                expr = re.compile(r"^(\d{2}:\d{2}:\d{2}\.\d{9})\s(.+?)\sms\s(.+?)\sms\s" + r"UDP\s" + "192.168.2.103" + re.escape(target) + r"$")
                samples = parse(epping_f, expr)
                # samples = parse(epping_f, "UDP", "192.168.2.103", str(flow.dport), "192.168.2.102", str(flow.sport))
            elif args.native:
                print(f"{i}: TCP *.*.*.*:{str(flow.dport)}+192.168.2.102:{str(flow.sport)}")
                target = ":" + str(flow.dport) + "+" + "192.168.2.102" + ":" + str(flow.sport)
                expr = re.compile(r"^(\d{2}:\d{2}:\d{2}\.\d{9})\s(.+?)\sms\s(.+?)\sms\s" + r"TCP\s" + ".*?" + re.escape(target) + r"$")
                samples = parse(epping_f, expr)
                # samples = parse(epping_f, "TCP", ".*?", str(flow.dport), "192.168.2.102", str(flow.sport))
            else:
                print(f"{i}: TCP 192.168.2.103:{str(flow.dport)}+192.168.2.102:{str(flow.sport)}")
                target = ":" + str(flow.dport) + "+" + "192.168.2.102" + ":" + str(flow.sport)
                expr = re.compile(r"^(\d{2}:\d{2}:\d{2}\.\d{9})\s(.+?)\sms\s(.+?)\sms\s" + r"TCP\s" + "192.168.2.103" + re.escape(target) + r"$")
                samples = parse(epping_f, expr)
                # samples = parse(epping_f, "TCP", "192.168.2.103", str(flow.dport), "192.168.2.102", str(flow.sport))

            if len(samples) == 0:
                print("There is no epping samples.")
                return None

            x = list(zip(*samples))[0]
            y = list(zip(*samples))[1]

            epping_map[i] = (x, y)

            with open(f'epping.{i}.{experiment}.out', 'w') as epping_output_per_flow:
                for j, _ in enumerate(epping_map[i][0]):
                    epping_output_per_flow.write(f'{epping_map[i][0][j].astype(int)},{epping_map[i][1][j]}\n')

    return epping_map

def start_bpftrace():
    # f = tempfile.NamedTemporaryFile()
    with open(f'raw.bpftrace.{experiment}.out', 'w') as f:
        p = subprocess.Popen(["./bbr.bt"], stdout=f, cwd='../..')

    return (p, f)

def end_bpftrace(bpftrace_p, bpftrace_f, flows):
    bpftrace_p.kill()

    initial_timestamp_ns = 0
    bpftrace_map = {}

    with open(bpftrace_f.name, 'r') as bpftrace_f:
        for i, flow in enumerate(flows):
            bpftrace_f.seek(0)
            for line in bpftrace_f.readlines():
                data = line.split(',')
                if len(data) != 6:
                    continue

                if initial_timestamp_ns == 0:
                    initial_timestamp_ns = int(data[1])
                    elapsed = 0
                else:
                    elapsed = int(data[1]) - initial_timestamp_ns
                delivered = int(data[2])
                rtt_us = int(data[3])
                port = int(data[5])

                if port == flow.sport:
                    if not i in bpftrace_map:
                        bpftrace_map[i] = ([], [], [])
                    
                    (x, y, z) = bpftrace_map[i]
                    x.append(elapsed)
                    y.append(rtt_us)
                    z.append(delivered)

            if not bpftrace_map.get(i):
                print("There is no bpftrace result.")
                return None
            
            with open(f'bpftrace.{i}.{experiment}.out', 'w') as bpftrace_output_per_flow:
                for j, _ in enumerate(bpftrace_map[i][0]):
                    bpftrace_output_per_flow.write(f'{bpftrace_map[i][0][j]},{bpftrace_map[i][1][j]},{bpftrace_map[i][2][j]}\n')

    return bpftrace_map

def get_k8s_iperf_server_addrs():
    first = ['kubectl', 'get', 'pods', '-owide']
    second = ['perl', '-nE', r'say $7 if /^(iperf-server.*?)\s+(.*?)\s+(.*?)\s+(.*?)\s+(\(.*?\))?\s+(.*?)\s+(.*?)\s+.*/']
    p1 = subprocess.Popen(first, stdout=subprocess.PIPE)
    p2 = subprocess.Popen(second, stdin=p1.stdout, stdout=subprocess.PIPE, text=True)
    p1.stdout.close()  # Allow p1 to receive a SIGPIPE if p2 exits.
    output = p2.communicate()[0]
    addresses = output.split('\n')
    return addresses[:-1]

def get_k8s_iperf_client_pods():
    first = ['kubectl', 'get', 'pods', '-owide']
    second = ['awk', '/iperf-client/ {print $1}']
    p1 = subprocess.Popen(first, stdout=subprocess.PIPE)
    p2 = subprocess.Popen(second, stdin=p1.stdout, stdout=subprocess.PIPE, text=True)
    p1.stdout.close()  # Allow p1 to receive a SIGPIPE if p2 exits.
    output = p2.communicate()[0]
    addresses = output.split('\n')
    return addresses[:-1]

def run_neper_clients(num_flows, time, server_addr):
    flows = []
    processes = []

    for i in range(0, num_flows):
        port = 5300 + i
        cpu = 16 + i
        sport = 42000 + i
        # neper_args = ["./tcp_rr", "-c", "-H", server_addr, "-P", str(port), "-l", str(time), '--source-port', str(sport), '-Q', '2000', '-R', '20000']
        neper_args = ["./tcp_rr", "-c", "-H", server_addr, "-P", str(port), "-l", str(time), '-Q', '2000', '-R', '20000']
        f = tempfile.NamedTemporaryFile()
        p = subprocess.Popen(neper_args, stdout=f, cwd='../../iperfs')
        # p = subprocess.Popen(neper_args, stdout=f)
        processes.append((p, f))
        flow = NeperFlowStat()
        flow.dport = port
        flows.append(flow)

    print(f"Start {num_flows} neper flows for {time} seconds.")
    for (p, f) in processes:
        p.wait()
        f.seek(0)
        lines = f.readlines()
        for l in lines:
            tokens = l.decode('utf-8').split('=')
            if tokens[0] == 'port':
                i, flow = find_flow(flows, int(tokens[1]))
            elif tokens[0] == 'source_port':
                flow.sport = int(tokens[1])
            elif tokens[0] == 'throughput':
                flow.throughput = float(tokens[1])
        
        f.close()

        # print(f'{i}: {flow.sport}, {flow.dport}, {flow.throughput:.3f}')
        print(f'{i}: {flow.dport}, {flow.throughput:.3f}')

    return flows

def run_iperf_clients(num_flows, time, server_addr):
    flows = []
    processes = []

    for i in range(0, num_flows):
        port = 5200 + i
        cpu = 16 + i
        iperf_args = ["iperf3", "-c", server_addr, "-p", str(port), "-t", str(time), "-J", "-A", str(cpu)]
        if not args.bitrate == "":
            iperf_args.extend(["-b", args.bitrate])
        f = tempfile.NamedTemporaryFile()
        p = subprocess.Popen(iperf_args, stdout=f)
        processes.append((p, f))
        flow = FlowStat()
        flow.dport = port
        flows.append(flow)

    print(f"Start {num_flows} flows for {time} seconds.")
    for (p, f) in processes:
        p.wait()
        f.seek(0)
        data = json.load(f)
        dport = data["start"]["connected"][0]["remote_port"]
        i, flow = find_flow(flows, dport)

        flow.sport = data["start"]["connected"][0]["local_port"]
        flow.throughput = data["end"]["sum_sent"]["bits_per_second"] / 1000000000
        flow.retransmissions = data["end"]["sum_sent"]["retransmits"]
        flow.iperf_rtt_mean = data["end"]["streams"][0]["sender"]["mean_rtt"]
        flow.sutilization = data["end"]["cpu_utilization_percent"]["host_total"]
        flow.dutilization = data["end"]["cpu_utilization_percent"]["remote_total"]

        f.close()

        print(f'{i}: {flow.sport}, {flow.dport}, {flow.throughput:.3f}, {flow.retransmissions}, {flow.iperf_rtt_mean}')

    return flows

def run_k8s_iperf_clients(num_flows, time, server_addrs, client_pods):
    flows = []
    processes = []
    ports = [5200, 5201, 5202, 5203, 5204, 5205, 5206, 5207]
    cpus = [16, 17, 18, 19, 20, 21, 22, 23]

    for i in range(0, num_flows):
        iperf_args = ["kubectl", "exec", client_pods[i], "--", "iperf3", "-c", server_addrs[i], "-p", str(ports[i]), "-t", str(time), "-J", "-A", str(cpus[i])]
        if not args.bitrate == "":
            iperf_args.extend(["-b", args.bitrate])
        f = tempfile.NamedTemporaryFile()
        p = subprocess.Popen(iperf_args, stdout=f)
        processes.append((p, f))
        flow = FlowStat()
        flow.dport = ports[i]
        flows.append(flow)

    print(f"Start {num_flows} flows for {time} seconds.")
    for (p, f) in processes:
        p.wait()
        f.seek(0)
        data = json.load(f)
        dport = data["start"]["connected"][0]["remote_port"]
        i, flow = find_flow(flows, dport)

        flow.sport = data["start"]["connected"][0]["local_port"]
        flow.throughput = data["end"]["sum_sent"]["bits_per_second"] / 1000000000
        flow.retransmissions = data["end"]["sum_sent"]["retransmits"]
        flow.iperf_rtt_mean = data["end"]["streams"][0]["sender"]["mean_rtt"]
        flow.sutilization = data["end"]["cpu_utilization_percent"]["host_total"]
        flow.dutilization = data["end"]["cpu_utilization_percent"]["remote_total"]

        f.close()

        print(f'{i}: {flow.sport}, {flow.dport}, {flow.throughput:.3f}, {flow.retransmissions}, {flow.iperf_rtt_mean}')

    return flows

def plot_graphs(epping_map, bpftrace_map, peak, max_time):
    minlen = min(len(epping_map), len(bpftrace_map))

    for i in range(0, minlen):
        figure = pp.figure(figsize=(10, 6))
        xrange = np.array([0, max_time])
        yrange = np.array([0, peak])
        pp.xlim(xrange)
        pp.ylim(yrange)
        pp.xticks(np.linspace(*xrange, 7))
        pp.yticks(np.linspace(*yrange, 11))

        if not args.no_bpftrace:
            (bx, by, bz) = bpftrace_map[i]
            pp.plot(bx, by, linewidth=0.1)

        (ex, ey) = epping_map[i]
        pp.plot(ex, ey, linewidth=0.5)
        
        name = f'{i}.{experiment}'
        output = f"rtt.{name}.png"
        pp.savefig(output, dpi=300, bbox_inches='tight', pad_inches=0.05)

        # Distributions
        bins = np.linspace(50, 500, 451)
        figure = pp.figure(figsize=(10, 6))
        pp.hist(by, bins, alpha=0.5, label='bpftrace', density=True)
        pp.hist(ey, bins, alpha=0.5, label='epping', density=True)
            
        output = f"dist.{i}.{experiment}.png"
        pp.savefig(output, dpi=300, bbox_inches='tight', pad_inches=0.05)

def str_to_ns(time_str):
    h, m, s = time_str.split(":")
    int_s, ns = s.split(".")
    ns = map(lambda t, unit: np.timedelta64(t, unit), [h,m,int_s,ns.ljust(9, '0')],['h','m','s','ns'])
    return sum(ns)

def parse(f, expr):
    samples = []
    initial_timestamp_ns = 0
    lines = f.readlines()
    for l in lines:
        match = expr.search(l)
        if match == None:
            continue
        
        timestamp_ns = str_to_ns(match.group(1))

        if initial_timestamp_ns == 0:
            initial_timestamp_ns = timestamp_ns
            
        rtt_us = float(match.group(2)) * 1000
        samples.append(((timestamp_ns - initial_timestamp_ns), rtt_us))

    # Check the reverse flow
    # Why are ports mixed?
    # f.seek(0)
    # reverse_samples = []
    # target = protocol + " " + daddr + ":" + sport + "+" + saddr + ":" + dport
    # expr = re.compile(r"^(\d{2}:\d{2}:\d{2}\.\d{9})\s(.+?)\sms\s(.+?)\sms\s" + re.escape(target) + r"$")
    # lines = f.readlines()
    # for l in lines:
    #     match = expr.search(l)
    #     if match == None:
    #         continue
        
    #     timestamp_ns = str_to_ns(match.group(1))

    #     if initial_timestamp_ns == 0:
    #         initial_timestamp_ns = timestamp_ns
            
    #     rtt_us = float(match.group(2)) * 1000
    #     reverse_samples.append(((timestamp_ns - initial_timestamp_ns), rtt_us))
    
    # print(f"len(samples): {len(samples)}, len(reverse_samples): {len(reverse_samples)}")
    # samples.extend(reverse_samples)
    return np.array(samples)

def find_flow(flows, dport):
    for i, flow in enumerate(flows):
        if flow.dport == dport:
            return (i, flow)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--flow', '-f', default=6)
    parser.add_argument('--time', '-t', default=60)
    parser.add_argument('--silent', '-s', action='store_true')
    parser.add_argument('--vxlan', '-v', action='store_true')
    parser.add_argument('--native', '-n', action='store_true')
    parser.add_argument('--bitrate', '-b', default="")
    parser.add_argument('--neper', '-N', action='store_true')
    parser.add_argument('--no-bpftrace', action='store_true')

    global args
    args = parser.parse_args()
    main()