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
    saddr:str = None
    sport:int = None
    daddr:str = None
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
    saddr:str = None
    sport:int = None
    daddr:str = None
    dport:int = None
    throughput:float = None
    nic_rtt_mean:float = None
    nic_rtt_std:float = None
    tcp_rtt_mean:float = None
    tcp_rtt_std:float = None

def main():
    num_flows = int(args.flow)
    num_container_flows = int(args.container_flow)
    duration = int(args.time)
    server_addr = "192.168.2.103"
    interface = "ens801f0"
    cca = "bbr"

    global experiment

    initialize_nic()

    experiment = f"tx-c-f{num_flows}-c{num_container_flows}-t{duration}-{cca}-{args.app}-0"

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
    (interrupt_f, softirqs_f) = get_interrupt_count()
    (vxlan_epping_p, vxlan_epping_f) = start_vxlan_epping(interface)
    (host_epping_p, host_epping_f) = start_host_epping(interface)

    if not args.no_bpftrace:
        (bpftrace_p, bpftrace_f) = start_bpftrace()

    time.sleep(2)

    # Using neper
    if args.app == "neper":
        servers = get_k8s_servers('neper')
        clients = get_k8s_clients('neper')

        # print(f"Debug: {servers}, {clients}")
        if len(servers) == 0 or len(clients) == 0:
            vxlan_epping_p.kill()
            host_epping_p.kill()
            util_p.kill()
            if not args.no_bpftrace:
                bpftrace_p.kill()
            print('Check that kubeconfig is properly set.')
            exit(-1)
        (flows, container_flows) = run_combined_neper_clients(num_flows, num_container_flows, duration, server_addr, servers, clients)

    # Using iperf
    else:
        servers = get_k8s_servers('iperf')
        clients = get_k8s_clients('iperf')

        if len(servers) == 0 or len(clients) == 0:
            vxlan_epping_p.kill()
            host_epping_p.kill()
            util_p.kill()
            if not args.no_bpftrace:
                bpftrace_p.kill()
            print('Check that kubeconfig is properly set.')
            exit(-1)
        (flows, container_flows) = run_combined_iperf_clients(num_flows, num_container_flows, duration, server_addr, servers, clients)

    end_cpu_utilization(util_p, util_f)
    process_interrupt_count(interrupt_f, softirqs_f)

    if flows == None or container_flows == None:
        vxlan_epping_p.kill()
        host_epping_p.kill()
        bpftrace_p.kill()
        return

    vxlan_epping_map = end_epping(vxlan_epping_p, vxlan_epping_f, container_flows, True)
    host_epping_map = end_epping(host_epping_p, host_epping_f, flows, False)
    if not args.no_bpftrace:
        host_bpftrace_map, vxlan_bpftrace_map = end_combined_bpftrace(bpftrace_p, bpftrace_f, flows, container_flows)
    else:
        host_bpftrace_map = {}
        vxlan_bpftrace_map = {}

    if vxlan_epping_map == None or host_epping_map == None or host_bpftrace_map == None or vxlan_bpftrace_map == None:
        print(f'{experiment} failed.')
        return
    
    json_data = {}
    aggregate_throughput = 0
    throughputs = []
    peak = 0
    # reduced_time = 60_000_000_000
    reduced_time = duration * 1_000_000_000

    print(f'{experiment}')
    if args.app == "neper":
        print('{0:>{1}}  i {2:>10} {3:>8} {4:>15} {5:>15} {6:>13}'. \
              format('experiment', len(experiment), 'flow', 'tput', 'nic_rtt (us)', 'tcp_rtt (us)', 'offset'))
    else:
        print('{0:>{1}} i {2:>10} {3:>7} {4:>5} {5:>15} {6:>15} {7:>13}'. \
              format('experiment', len(experiment), 'flow', 'tput', 'rtx', 'nic_rtt (us)', 'tcp_rtt (us)', 'offset'))

    for i, flow in enumerate(flows):
        flow.nic_rtt_mean = np.average(host_epping_map[i][1])
        flow.nic_rtt_std = np.std(host_epping_map[i][1])

        if not args.no_bpftrace:
            flow.tcp_rtt_mean = np.average(host_bpftrace_map[i][1])
            flow.tcp_rtt_std = np.std(host_bpftrace_map[i][1])

            peak_per_flow = max(np.max(host_bpftrace_map[i][1]), np.max(host_epping_map[i][1]))
            if peak_per_flow >= peak:
                peak = peak_per_flow
        else:
            if args.app == 'iperf':
                flow.tcp_rtt_mean = flow.iperf_rtt_mean
                flow.tcp_rtt_std = 0
            else:
                flow.tcp_rtt_mean = flow.tcp_rtt_mean
                flow.tcp_rtt_std = flow.tcp_rtt_std

            peak_per_flow = np.max(host_epping_map[i][1])
            if peak_per_flow >= peak:
                peak = peak_per_flow

        throughputs.append(flow.throughput)
        gbps = flow.throughput
        diff = flow.tcp_rtt_mean - flow.nic_rtt_mean

        if args.app == "neper":
            print('{0} h{1:>1} {2:>10}: {3:>7.1f} {4:>6.1f} {5:>8} {6:>6.1f} {7:>8} {8:>5.1f} {9:>7}'. \
                  format(experiment, i, f'{flow.sport}-{flow.dport}', gbps, \
                         flow.nic_rtt_mean, f'({flow.nic_rtt_std:>.2f})', \
                         flow.tcp_rtt_mean, f'({flow.tcp_rtt_std:>.2f})', \
                         diff, f'{(diff/flow.nic_rtt_mean * 100):>6.2f}%'))
        else:
            print('{0} h{1:>1} {2:>10}: {3:>6.2f} {4:>5} {5:>6.1f} {6:>8} {7:>6.1f} {8:>8} {9:>5.1f} {10:>7}'. \
                  format(experiment, i, f'{flow.sport}-{flow.dport}', gbps, flow.retransmissions, \
                         flow.nic_rtt_mean, f'({flow.nic_rtt_std:>.2f})', \
                         flow.tcp_rtt_mean, f'({flow.tcp_rtt_std:>.2f})', \
                         diff, f'{(diff/flow.nic_rtt_mean * 100):>6.2f}%'))
            
        json_data[f"hflow{i}"] = vars(flow)        
        aggregate_throughput += flow.throughput

    json_data["host aggregate throughput"] = aggregate_throughput

    if args.app == "neper":
        print(f'Host Aggregate Throughput: {aggregate_throughput:.1f} qps')
    else:
        print(f'Host Aggregate Throughput: {aggregate_throughput:.1f} Gbps')

    if not args.no_plot:
        plot_graphs(host_epping_map, host_bpftrace_map, peak_per_flow, reduced_time, False)

    aggregate_throughput = 0

    for i, flow in enumerate(container_flows):
        flow.nic_rtt_mean = np.average(vxlan_epping_map[i][1])
        flow.nic_rtt_std = np.std(vxlan_epping_map[i][1])

        if not args.no_bpftrace:
            flow.tcp_rtt_mean = np.average(vxlan_bpftrace_map[i][1])
            flow.tcp_rtt_std = np.std(vxlan_bpftrace_map[i][1])

            peak_per_flow = max(np.max(vxlan_bpftrace_map[i][1]), np.max(vxlan_epping_map[i][1]))
            if peak_per_flow >= peak:
                peak = peak_per_flow
        else:
            if args.app == 'iperf':
                flow.tcp_rtt_mean = flow.iperf_rtt_mean
                flow.tcp_rtt_std = 0
            else:
                flow.tcp_rtt_mean = flow.tcp_rtt_mean
                flow.tcp_rtt_std = flow.tcp_rtt_std

            peak_per_flow = np.max(vxlan_epping_map[i][1])
            if peak_per_flow >= peak:
                peak = peak_per_flow

        throughputs.append(flow.throughput)
        gbps = flow.throughput
        diff = flow.tcp_rtt_mean - flow.nic_rtt_mean

        if args.app == "neper":
            print('{0} v{1:>1} {2:>10}: {3:>7.1f} {4:>6.1f} {5:>8} {6:>6.1f} {7:>8} {8:>5.1f} {9:>7}'. \
                  format(experiment, i, f'{flow.sport}-{flow.dport}', gbps, \
                         flow.nic_rtt_mean, f'({flow.nic_rtt_std:>.2f})', \
                         flow.tcp_rtt_mean, f'({flow.tcp_rtt_std:>.2f})', \
                         diff, f'{(diff/flow.nic_rtt_mean * 100):>6.2f}%'))
        else:
            print('{0} v{1:>1} {2:>10}: {3:>6.2f} {4:>5} {5:>6.1f} {6:>8} {7:>6.1f} {8:>8} {9:>5.1f} {10:>7}'. \
                  format(experiment, i, f'{flow.sport}-{flow.dport}', gbps, flow.retransmissions, \
                         flow.nic_rtt_mean, f'({flow.nic_rtt_std:>.2f})', \
                         flow.tcp_rtt_mean, f'({flow.tcp_rtt_std:>.2f})', \
                         diff, f'{(diff/flow.nic_rtt_mean * 100):>6.2f}%'))
            
        json_data[f"cflow{i}"] = vars(flow)        
        aggregate_throughput += flow.throughput

    json_data["vxlan aggregate throughput"] = aggregate_throughput

    if args.app == "neper":
        print(f'VXLAN Aggregate Throughput: {aggregate_throughput:.1f} qps')
    else:
        print(f'VXLAN Aggregate Throughput: {aggregate_throughput:.1f} Gbps')
    print(f'Jain\'s Fairness Index: {jain_index(throughputs):.4f}')

    with open(f'summary.c.{experiment}.json', 'w') as f:
        json.dump(json_data, f)
    
    if not args.no_plot:
        plot_graphs(vxlan_epping_map, vxlan_bpftrace_map, peak_per_flow, reduced_time, True)

def initialize_nic():
    print("Initialize ice driver.", end=" ", flush=True)
    subprocess.run(["rmmod", "ice"])
    time.sleep(0.5)
    subprocess.run(["modprobe", "ice"])
    time.sleep(0.5)
    subprocess.run(["./flow_direction_tx_tcp.sh"], stdout=subprocess.DEVNULL)
    subprocess.run(["./smp_affinity.sh"], stdout=subprocess.DEVNULL)
    print("Done.")
    
def start_cpu_utilization():
    f = tempfile.NamedTemporaryFile()
    p = subprocess.Popen(['./cpuload.sh'], stdout=f, cwd='../../scripts')

    return (p, f)

def end_cpu_utilization(p, f):
    p.kill()
    with open(f'cpu.{experiment}.out', 'w') as cpu_output:
        subprocess.run(["./cpu.py", f.name], stdout=cpu_output, cwd='../../scripts')

    if not args.silent:
        subprocess.run(["./cpu.py", "-c", f.name], cwd='../../scripts')
    
def get_interrupt_count():
    interrupts_f = tempfile.NamedTemporaryFile()
    softirqs_f = tempfile.NamedTemporaryFile()
    subprocess.run(["cat", "/proc/interrupts"], stdout=interrupts_f)
    subprocess.run(["cat", "/proc/softirqs"], stdout=softirqs_f)

    return interrupts_f, softirqs_f

def process_interrupt_count(old_interrupts_f, old_softirqs_f):
    new_interrupts_f = tempfile.NamedTemporaryFile()
    new_softirqs_f = tempfile.NamedTemporaryFile()
    subprocess.run(["cat", "/proc/interrupts"], stdout=new_interrupts_f)
    subprocess.run(["cat", "/proc/softirqs"], stdout=new_softirqs_f)

    with open(f'interrupts.{experiment}.out', 'w') as interrupts_output:
        subprocess.run(["./interrupts.py", old_interrupts_f.name, new_interrupts_f.name], stdout=interrupts_output, cwd='../../scripts')

    with open(f'softirqs.{experiment}.out', 'w') as softirqs_output:
        subprocess.run(["./softirqs.py", old_softirqs_f.name, new_softirqs_f.name], stdout=softirqs_output, cwd='../../scripts')

    if not args.silent:
        subprocess.run(["./interrupts.py", old_interrupts_f.name, new_interrupts_f.name], cwd='../../scripts')
        subprocess.run(["./softirqs.py", old_softirqs_f.name, new_softirqs_f.name], cwd='../../scripts')

def start_vxlan_epping(interface):
    # f = tempfile.NamedTemporaryFile()
    with open(f'raw.epping.v.{experiment}.out', 'w') as f:
        p = subprocess.Popen(["./pping", "-i", interface, "-x", "native", "-V"], stdout=f, cwd='../..')
        
    time.sleep(2)
    return (p, f)

def start_host_epping(interface):
    # f = tempfile.NamedTemporaryFile()
    with open(f'raw.epping.h.{experiment}.out', 'w') as f:
        p = subprocess.Popen(["./pping", "-i", interface, "-x", "native"], stdout=f, cwd='../..')

    time.sleep(2)
    return (p, f)

def end_epping(epping_p, epping_f, flows, is_vxlan):
    epping_p.kill()

    epping_map = {}

    with open(epping_f.name, 'r') as epping_f:
        for (i, flow) in enumerate(flows):
            epping_f.seek(0)
            if is_vxlan:
                print(f"{i}: UDP 192.168.2.103:{str(flow.dport)}+192.168.2.102:{str(flow.sport)}")
                target = ":" + str(flow.dport) + "+" + "192.168.2.102" + ":" + str(flow.sport)
                expr = re.compile(r"^(\d{2}:\d{2}:\d{2}\.\d{9})\s(.+?)\sms\s(.+?)\sms\s" + r"UDP\s" + "192.168.2.103" + re.escape(target) + r"$")
                samples = parse(epping_f, expr)
                # samples = parse(epping_f, "UDP", "192.168.2.103", str(flow.dport), "192.168.2.102", str(flow.sport))
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

def end_combined_bpftrace(bpftrace_p, bpftrace_f, flows, container_flows):
    bpftrace_p.kill()

    initial_timestamp_ns = 0
    host_bpftrace_map = {}
    vxlan_bpftrace_map = {}

    with open(bpftrace_f.name, 'r') as bpftrace_f:
        for i, flow in enumerate(flows):
            bpftrace_f.seek(0)
            with open(f'bpftrace.h.{i}.{experiment}.out', 'w') as bpftrace_output_per_flow:
                for line in bpftrace_f.readlines():
                    data = line.rstrip().split(',')
                    if len(data) != 6:
                        bpftrace_output_per_flow.write(line)
                        continue

                    if initial_timestamp_ns == 0:
                        initial_timestamp_ns = int(data[1])
                        elapsed = 0
                    else:
                        elapsed = int(data[1]) - initial_timestamp_ns
                    delivered = int(data[2])
                    rtt_us = int(data[3])
                    port = int(data[5])
                    ebw = (delivered * 1500 * 8) / rtt_us

                    if port == flow.sport:
                        if not i in host_bpftrace_map:
                            host_bpftrace_map[i] = ([], [], [], [])
                        
                        (x, y, z, w) = host_bpftrace_map[i]
                        x.append(elapsed)
                        y.append(rtt_us)
                        z.append(delivered)
                        w.append(ebw) # Mbps

                        output = ','.join(data) + ',' + str(ebw) + '\n'
                        bpftrace_output_per_flow.write(output)

            if not host_bpftrace_map.get(i):
                print("There is no host bpftrace result.")
                return None
            
        for i, flow in enumerate(container_flows):
            bpftrace_f.seek(0)
            with open(f'bpftrace.v.{i}.{experiment}.out', 'w') as bpftrace_output_per_flow:
                for line in bpftrace_f.readlines():
                    data = line.rstrip().split(',')
                    if len(data) != 6:
                        bpftrace_output_per_flow.write(line)
                        continue

                    if initial_timestamp_ns == 0:
                        initial_timestamp_ns = int(data[1])
                        elapsed = 0
                    else:
                        elapsed = int(data[1]) - initial_timestamp_ns
                    delivered = int(data[2])
                    rtt_us = int(data[3])
                    port = int(data[5])
                    ebw = (delivered * 1500 * 8) / rtt_us

                    if port == flow.sport:
                        if not i in vxlan_bpftrace_map:
                            vxlan_bpftrace_map[i] = ([], [], [], [])
                        
                        (x, y, z, w) = vxlan_bpftrace_map[i]
                        x.append(elapsed)
                        y.append(rtt_us)
                        z.append(delivered)
                        w.append(ebw) # Mbps

                        output = ','.join(data) + ',' + str(ebw) + '\n'
                        bpftrace_output_per_flow.write(output)

            if not vxlan_bpftrace_map.get(i):
                print("There is no vxlan bpftrace result.")
                return None


    return host_bpftrace_map, vxlan_bpftrace_map

def get_k8s_servers(target):
    first = ['kubectl', 'get', 'pods', '-owide']
    second = ['perl', '-nE', fr'say $1, " ", $7 if /^({target}-server.*?)\s+(.*?)\s+(.*?)\s+(.*?)\s+(\(.*?\))?\s+(.*?)\s+(.*?)\s+.*/']
    p1 = subprocess.Popen(first, stdout=subprocess.PIPE)
    p2 = subprocess.Popen(second, stdin=p1.stdout, stdout=subprocess.PIPE, text=True)
    p1.stdout.close()  # Allow p1 to receive a SIGPIPE if p2 exits.
    output = p2.communicate()[0]
    servers = list(map(lambda item: item.split(), output.rstrip().split('\n')))
    return servers

def get_k8s_clients(target):
    first = ['kubectl', 'get', 'pods', '-owide']
    second = ['awk', f'/{target}-client/ ' + '{print $1, $6}']
    p1 = subprocess.Popen(first, stdout=subprocess.PIPE)
    p2 = subprocess.Popen(second, stdin=p1.stdout, stdout=subprocess.PIPE, text=True)
    p1.stdout.close()  # Allow p1 to receive a SIGPIPE if p2 exits.
    output = p2.communicate()[0]
    clients = list(map(lambda item: item.split(), output.rstrip().split('\n')))

    return clients

def run_combined_neper_clients(num_flows, num_container_flows, duration, server_addr, servers, clients):
    flows = []
    container_flows = []
    processes = []

    for i in range(0, num_flows):
        port = 5300 + i
        cpu = 16 + i
        neper_args = ["numactl", "-C", str(cpu), "./tcp_rr", "--nolog", "-c", "-H", server_addr, "-P", str(port), "-l", str(duration)]
        f = tempfile.NamedTemporaryFile()
        p = subprocess.Popen(neper_args, stdout=f, stderr=subprocess.PIPE, cwd='../../scripts')  
        
        processes.append((p, f, False))
        flow = NeperFlowStat()
        flow.dport = port
        netstat = ['netstat', '-tp']
        netstat_f = tempfile.NamedTemporaryFile()
        subprocess.run(netstat, stdout=netstat_f, stderr=subprocess.DEVNULL)
        with open(netstat_f.name, 'r') as netstat_f:
            netstat_f.seek(0)
            for line in netstat_f.readlines():
                tokens = line.split()
                if not len(tokens) == 7:
                    continue

                if tokens[-1].endswith('tcp_rr') and tokens[-1].startswith(str(p.pid)) and tokens[4].endswith(str(port)):
                    # print(tokens[3].split(":")[-1])
                    flow.sport = int(tokens[3].split(":")[-1])

        flows.append(flow)

    ports = [5300, 5301, 5302, 5303, 5304, 5305, 5306, 5307]
    sports = [42000, 42001, 42002, 42003, 42004, 42005, 42006, 42007]
    cpus = [20, 21, 22, 23]

    for i in range(0, num_container_flows):
        neper_args = ["kubectl", "exec", clients[i][0], "--", "numactl", "-C", str(cpus[i]), \
                      "./tcp_rr", "--nolog", "-c", "-H", servers[i][1], "--source-port", str(sports[i]), "-P", str(ports[i]), "-l", str(duration)]
        # neper_args = ["kubectl", "exec", clients[i][0], "--", \
        #               "./tcp_rr", "--nolog", "-c", "-H", servers[i][1], "--source-port", str(sports[i]), "-P", str(ports[i]), "-l", str(duration)]
        f = tempfile.NamedTemporaryFile()
        p = subprocess.Popen(neper_args, stdout=f, stderr=subprocess.PIPE)   
        
        processes.append((p, f, True))
        flow = NeperFlowStat()
        flow.saddr = "192.168.2.102"
        flow.daddr = "192.168.2.103"

        flow.sport = sports[i]
        flow.dport = ports[i]
        container_flows.append(flow)

    print(f"Start {num_flows} neper host flows for {duration} seconds.")
    print(f"Start {num_flows} neper vxlan flows for {duration} seconds.")
    for (p, f, is_vxlan) in processes:
        _, err = p.communicate()
        if err != None and err != b'':
            print('neper error:', err.decode('utf-8'))
            return None
        
        f.seek(0)
        lines = f.readlines()
        for l in lines:
            tokens = l.decode('utf-8').split('=')
            if tokens[0] == 'port':
                if is_vxlan:
                    i, flow = find_flow(container_flows, int(tokens[1]))
                else:
                    i, flow = find_flow(flows, int(tokens[1]))
            elif tokens[0] == 'throughput':
                flow.throughput = float(tokens[1])
            elif tokens[0] == 'latency_mean':
                flow.tcp_rtt_mean = float(tokens[1]) * 1000000
            elif tokens[0] == 'latency_stddev':
                flow.tcp_rtt_std = float(tokens[1]) * 1000000
        
        f.close()

        if is_vxlan:
            print(f'v{i}: {flow.sport}, {flow.dport}, {flow.throughput:.3f}')
        else:
            print(f'h{i}: {flow.sport}, {flow.dport}, {flow.throughput:.3f}')
        # print(f'{i}: {flow.dport}, {flow.throughput:.3f}')

    return flows, container_flows

def run_combined_iperf_clients(num_flows, num_container_flows, duration, server_addr, servers, clients):
    flows = []
    container_flows = []
    processes = []

    # Host flows
    for i in range(0, num_flows):
        port = 5204 + i
        cpu = 16 + i
        iperf_args = ["iperf3", "-c", server_addr, "-p", str(port), "-t", str(duration), "-J", "-A", str(cpu)]
        # iperf_args = ["iperf3", "-c", server_addr, "-p", str(port), "-t", "20", "-J", "-A", str(cpu)]
        # f = tempfile.NamedTemporaryFile()
        f = open(f'raw.iperf.h.{i}.{experiment}.out', 'w+b')
        p = subprocess.Popen(iperf_args, stdout=f, stderr=subprocess.PIPE)
        
        processes.append((p, f, False))
        flow = FlowStat()
        flow.dport = port
        flows.append(flow)

    # Container flows
    ports = [5200, 5201, 5202, 5203, 5204, 5205, 5206, 5207]
    sports = [42000, 42001, 42002, 42003, 42004, 42005, 42006, 42007]
    cpus = [20, 21, 22, 23]

    for i in range(0, num_container_flows):
        iperf_args = ["kubectl", "exec", clients[i][0], "--", \
                      "iperf3", "-c", servers[i][1], "-p", str(ports[i]), "--cport", str(sports[i]), "-t", str(duration), "-J", "-A", str(cpus[i])]
        # f = tempfile.NamedTemporaryFile()
        f = open(f'raw.iperf.v.{i}.{experiment}.out', 'w+b')
        p = subprocess.Popen(iperf_args, stdout=f, stderr=subprocess.PIPE)
        
        processes.append((p, f, True))
        flow = FlowStat()
        flow.saddr = "192.168.2.102"
        flow.daddr = "192.168.2.103"
        
        flow.dport = ports[i]
        container_flows.append(flow)

    print(f"Start {num_flows} host flows for {duration} seconds.")
    print(f"Start {num_flows} vxlan flows for {duration} seconds.")
    for (p, f, is_vxlan) in processes:
        _, err = p.communicate()
        if err != None and err != b'':
            print('iperf3 error:', err.decode('utf-8'))
            return None
        
        f.seek(0)
        data = json.load(f)
        dport = data["start"]["connected"][0]["remote_port"]
        if is_vxlan:
            i, flow = find_flow(container_flows, dport)
        else:
            i, flow = find_flow(flows, dport)

        flow.sport = data["start"]["connected"][0]["local_port"]
        flow.throughput = data["end"]["sum_sent"]["bits_per_second"] / 1000000000
        flow.retransmissions = data["end"]["sum_sent"]["retransmits"]
        flow.iperf_rtt_mean = data["end"]["streams"][0]["sender"]["mean_rtt"]
        flow.sutilization = data["end"]["cpu_utilization_percent"]["host_total"]
        flow.dutilization = data["end"]["cpu_utilization_percent"]["remote_total"]

        f.close()

        if is_vxlan:
            print(f'v{i}: {flow.sport}, {flow.dport}, {flow.throughput:.3f}, {flow.retransmissions}, {flow.iperf_rtt_mean}')
        else:
            print(f'h{i}: {flow.sport}, {flow.dport}, {flow.throughput:.3f}, {flow.retransmissions}, {flow.iperf_rtt_mean}')

    return flows, container_flows

def plot_graphs(epping_map, bpftrace_map, peak, max_time, is_vxlan):
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
            (bx, by, bz, bw) = bpftrace_map[i]
            pp.plot(bx, by, linewidth=0.1)

        (ex, ey) = epping_map[i]
        pp.plot(ex, ey, linewidth=0.5)
        
        name = f'{i}.{experiment}'
        if is_vxlan:
            output = f"rtt.v.{name}.png"
        else:
            output = f"rtt.h.{name}.png"
        pp.savefig(output, dpi=300, bbox_inches='tight', pad_inches=0.05)

        # Distributions
        dist_max = max(max(by), max(ey))
        dist_min = min(min(by), min(ey))
        bins = np.linspace(dist_min, dist_max, int(dist_max - dist_min) + 1)
        figure = pp.figure(figsize=(10, 6))
        pp.hist(by, bins, alpha=0.5, label='bpftrace', density=True)
        pp.hist(ey, bins, alpha=0.5, label='epping', density=True)
            
        if is_vxlan:
            output = f"dist.v.{i}.{experiment}.png"
        else:
            output = f"dist.h.{i}.{experiment}.png"
        pp.savefig(output, dpi=300, bbox_inches='tight', pad_inches=0.05)

        # Estimated bandwidth
        if not args.no_bpftrace:
            (bx, by, bz, bw) = bpftrace_map[i]

            figure = pp.figure(figsize=(10, 6))
            xrange = np.array([0, max_time])
            yrange = np.array([0, max(bw)])
            pp.xlim(xrange)
            pp.ylim(yrange)
            pp.xticks(np.linspace(*xrange, 7))
            pp.yticks(np.linspace(*yrange, 11))
    
            pp.plot(bx, bw, linewidth=0.1)
            name = f'{i}.{experiment}'
            if is_vxlan:
                output = f"ewb.v.{name}.png"
            else:
                output = f"ewb.h.{name}.png"
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

    return np.array(samples)

def find_flow(flows, dport):
    for i, flow in enumerate(flows):
        if flow.dport == dport:
            return i, flow

def jain_index(data):
    squared_sum = 0
    sum = 0
    for d in data:
        sum += d
        squared_sum += d**2

    return sum**2 / (len(data) * squared_sum)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--flow', '-f', default=3)
    parser.add_argument('--container-flow', '-c', default=3)
    parser.add_argument('--time', '-t', default=60)
    parser.add_argument('--app', '-a', default='iperf')
    parser.add_argument('--silent', '-s', action='store_true')
    parser.add_argument('--no-bpftrace', action='store_true')
    parser.add_argument('--no-plot', action='store_true')

    global args
    args = parser.parse_args()

    if args.app != "iperf" and args.app != "neper":
        print("Wrong app name.")
        exit()

    main()