#!/usr/bin/python3
import subprocess
import tempfile
import os
import matplotlib.pyplot as pp
import numpy as np
import signal
import sys
import time
import re
import argparse

def main():
    num_flows = int(args.flow)
    time = int(args.time)
    app = args.app
    interface = "ens801f0"
    cca = "bbr"

    global experiment
    global iwd
    iwd = os.getcwd()

    initialize_nic()

    if args.vxlan:
        experiment = f"rx-e-f{num_flows}-t{time}-{cca}-{app}-0"
    elif args.native:
        experiment = f"rx-n-f{num_flows}-t{time}-{cca}-{app}-0"
    else:
        experiment = f"rx-h-f{num_flows}-t{time}-{cca}-{app}-0"

    if not os.path.exists(os.path.join(iwd, '..', 'data')):
        os.mkdir(os.path.join(iwd, '..', 'data'))
    os.chdir(os.path.join(iwd, '..', 'data'))

    while os.path.exists(os.path.join(iwd, '..', 'data', experiment)):
        (remained, last) = experiment.rsplit("-", 1)
        trial = int(last) + 1
        experiment = f"{remained}-{trial}"

    os.mkdir(os.path.join(iwd, '..', 'data', experiment))
    os.chdir(os.path.join(iwd, '..', 'data', experiment))

    if args.app == "neper":
        neper_processes = start_neper_servers(num_flows)

    (util_p, util_f) = start_cpu_utilization()
    interrupt_f = start_interrupt_count()
    (epping_p, epping_f) = start_epping(interface)

    (bpftrace_p, bpftrace_f) = start_bpftrace()

    print("Press \'Enter\' to end the recording.")
    _ = sys.stdin.readline()

    end_cpu_utilization(util_p, util_f)
    post_process_interrupt_count(interrupt_f)
    epping_map, port_map = end_client_epping(epping_p, epping_f, num_flows)
    bpftrace_map = end_bpftrace(bpftrace_p, bpftrace_f, num_flows, port_map)

    if epping_map == None or bpftrace_map == None:
        print(f'{experiment} failed.')
        return

    peak = 0
    reduced_time = 60_000_000_000
    for i in range(0, num_flows):
        print(f'{i} nic_rtt: {np.average(epping_map[i][1])} ({np.std(epping_map[i][1])})')
        print(f'{i} tcp_rtt: {np.average(bpftrace_map[i][1])} ({np.std(bpftrace_map[i][1])})')

        peak_per_flow = max(np.max(bpftrace_map[i][1]), np.max(epping_map[i][1]))
        if peak_per_flow >= peak:
            peak = peak_per_flow

        max_time_per_flow = min(np.max(bpftrace_map[i][0]), np.max(epping_map[i][0]))
        if max_time_per_flow <= reduced_time:
            reduced_time = max_time_per_flow

    plot_client_graphs(epping_map, bpftrace_map, peak, reduced_time)

    if args.app == "neper":
        end_neper_servers(neper_processes)

def initialize_nic():
    print("Initialize ice driver.", end=" ", flush=True)
    subprocess.run(["rmmod", "ice"])
    time.sleep(1)
    subprocess.run(["modprobe", "ice"])
    time.sleep(1)
    subprocess.run([os.path.join(iwd, 'flow_direction_rx_tcp.sh')], stdout=subprocess.DEVNULL)
    subprocess.run([os.path.join(iwd, 'smp_affinity.sh')], stdout=subprocess.DEVNULL)
    print("Done.")
    
def start_neper_servers(num_flows):
    neper_processes = []
    for i in range(0, num_flows):
        port = 5300 + i
        cpu = 16 + i
        neper_args = ["numactl", "-C", str(cpu), os.path.join(iwd, 'tcp_rr'), "--nolog", "-P", str(port), "-l", args.time]
        f = tempfile.TemporaryFile()
        p = subprocess.Popen(neper_args, stdout=f)
        neper_processes.append(p)

    return neper_processes

def end_neper_servers(neper_processes):
    for process in neper_processes:
        os.kill(process.pid, signal.SIGTERM)

def start_epping(interface):
    with open(f'raw.epping.{experiment}.out', 'w') as f:
        if args.vxlan:
            p = subprocess.Popen(["./pping", "-i", interface, "-x", "native", "-V"], stdout=f, cwd=os.path.join(iwd, '..'))
        else:
            p = subprocess.Popen(["./pping", "-i", interface, "-x", "native"], stdout=f, cwd=os.path.join(iwd, '..'))

    time.sleep(2)
    return (p, f)

def end_client_epping(epping_p, epping_f, num_flows):
    epping_p.kill()

    epping_map = {}

    if args.app == "iperf":
        dports = [5200, 5201, 5202, 5203, 5204, 5205, 5206, 5207]
    elif args.app == "neper":
        dports = [5300, 5301, 5302, 5303, 5304, 5305, 5306, 5307]
    port_map = {}

    with open(epping_f.name, 'r') as epping_f:
        for i in range(0, num_flows):
            epping_f.seek(0)
            if args.vxlan:
                print(f"{i}: UDP 192.168.2.102:*+192.168.2.103:{str(dports[i])}")
                target = "192.168.2.103" + ":" + str(dports[i])
                expr = re.compile(r"^(\d{2}:\d{2}:\d{2}\.\d{9})\s(.+?)\sms\s(.+?)\sms\s" + r"UDP\s192.168.2.102:(.*)\+" + re.escape(target) + r"$")
                (samples, port) = parse(epping_f, expr)
            # elif args.native:
            #     print(f"{i}: TCP {str(flow.daddr)}:{str(flow.dport)}+{str(flow.saddr)}:{str(flow.sport)}")
            #     target = str(flow.daddr) + ":" + str(flow.dport) + "+" + str(flow.saddr) + ":" + str(flow.sport)
            #     expr = re.compile(r"^(\d{2}:\d{2}:\d{2}\.\d{9})\s(.+?)\sms\s(.+?)\sms\s" + r"TCP\s" + re.escape(target) + r"$")
            #     samples = parse(epping_f, expr)
            else:
                print(f"{i}: TCP 192.168.2.102:*+192.168.2.103:{str(dports[i])}")
                target = "192.168.2.103" + ":" + str(dports[i])
                expr = re.compile(r"^(\d{2}:\d{2}:\d{2}\.\d{9})\s(.+?)\sms\s(.+?)\sms\s" + r"TCP\s192.168.2.102:(.*)\+" + re.escape(target) + r"$")
                (samples, port) = parse(epping_f, expr)

            if len(samples) == 0:
                print("There is no epping samples.")
                return None

            x = list(zip(*samples))[0]
            y = list(zip(*samples))[1]

            epping_map[i] = (x, y)
            port_map[i] = (port, dports[i])

            with open(f'epping.{i}.{experiment}.out', 'w') as epping_output_per_flow:
                for j, _ in enumerate(epping_map[i][0]):
                    epping_output_per_flow.write(f'{epping_map[i][0][j].astype(int)},{epping_map[i][1][j]}\n')

    return epping_map, port_map

def start_bpftrace():
    with open(f'raw.bpftrace.{experiment}.out', 'w') as f:
        p = subprocess.Popen(["./bbr.bt"], stdout=f, cwd=os.path.join(iwd, '..'))

    return (p, f)

def end_bpftrace(bpftrace_p, bpftrace_f, num_flows, port_map):
    bpftrace_p.kill()
    bpftrace_map = {}
    initial_timestamp_ns = 0

    with open(bpftrace_f.name, 'r') as bpftrace_f:
        for i in range(num_flows):
            bpftrace_f.seek(0)
            with open(f'bpftrace.{i}.{experiment}.out', 'w') as bpftrace_output_per_flow:
                for line in bpftrace_f.readlines():
                    data = line.rstrip().split(',')
                    if len(data) != 6:
                        bpftrace_output_per_flow.write(line)
                        continue

                    port = int(data[5])
                    if port == port_map[i][1]:                    
                        if initial_timestamp_ns == 0:
                            initial_timestamp_ns = int(data[1])
                            elapsed = 0
                        else:
                            elapsed = int(data[1]) - initial_timestamp_ns
                        delivered = int(data[2])
                        rtt_us = int(data[3])
                        ebw = (delivered * 1500 * 8) / rtt_us

                        if not i in bpftrace_map:
                            bpftrace_map[i] = ([], [], [], [])
                        
                        (x, y, z, w) = bpftrace_map[i]
                        x.append(elapsed)
                        y.append(rtt_us)
                        z.append(delivered)
                        w.append(ebw) # Mbps

                        output = ','.join(data) + ',' + str(ebw) + '\n'
                        bpftrace_output_per_flow.write(output)

            if not bpftrace_map.get(i):
                print("There is no bpftrace result.")
                return None

    return bpftrace_map
    
def start_cpu_utilization():
    f = tempfile.NamedTemporaryFile()
    p = subprocess.Popen([os.path.join(iwd, 'cpuload.sh')], stdout=f)

    return (p, f)

def end_cpu_utilization(p, f):
    p.kill()
    with open(f'cpu.{experiment}.out', 'w') as cpu_output:
        subprocess.run([os.path.join(iwd, 'cpu.py'), f.name], stdout=cpu_output)

    if not args.silent:
        subprocess.run([os.path.join(iwd, 'cpu.py'), "-c", f.name])
    
def start_interrupt_count():
    f = tempfile.NamedTemporaryFile()
    subprocess.run(["cat", "/proc/interrupts"], stdout=f)

    return f

def post_process_interrupt_count(old_f):
    new_f = tempfile.NamedTemporaryFile()
    subprocess.run(["cat", "/proc/interrupts"], stdout=new_f)

    with open(f'int.{experiment}.out', 'w') as interrupt_output:
        subprocess.run([os.path.join(iwd, 'interrupts.py'), old_f.name, new_f.name], stdout=interrupt_output)

    if not args.silent:
        subprocess.run([os.path.join(iwd, 'interrupts.py'), old_f.name, new_f.name])

def plot_client_graphs(epping_map, bpftrace_map, peak, max_time):
    minlen = min(len(epping_map), len(bpftrace_map))

    for i in range(0, minlen):
        figure = pp.figure(figsize=(10, 6))
        xrange = np.array([0, max_time])
        yrange = np.array([0, peak])
        pp.xlim(xrange)
        pp.ylim(yrange)
        pp.xticks(np.linspace(*xrange, 7))
        pp.yticks(np.linspace(*yrange, 11))

        (bx, by, bz, bw) = bpftrace_map[i]
        pp.plot(bx, by, linewidth=0.1)

        (ex, ey) = epping_map[i]
        pp.plot(ex, ey, linewidth=0.5)
        
        name = f'{i}.{experiment}'
        output = f"rtt.{name}.png"
        pp.savefig(output, dpi=300, bbox_inches='tight', pad_inches=0.05)

        # Distributions
        emin, emax = filter_range(ey, 0.001)
        bmin, bmax = filter_range(by, 0.001)
        dist_min = min(emin, bmin)
        dist_max = max(emax, bmax)
        # dist_max = max(max(by), max(ey))
        # dist_min = min(min(by), min(ey))
        bins = np.linspace(dist_min, dist_max, int(dist_max - dist_min) + 1)
        figure = pp.figure(figsize=(10, 6))
        pp.hist(by, bins, alpha=0.5, label='bpftrace', density=True)
        pp.hist(ey, bins, alpha=0.5, label='epping', density=True)
            
        output = f"dist.{i}.{experiment}.png"
        pp.savefig(output, dpi=300, bbox_inches='tight', pad_inches=0.05)

        # Estimated bandwidth
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
        output = f"ewb.{name}.png"
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

    port = None
    for l in lines:
        match = expr.search(l)
        if match == None:
            continue

        if port == None:
            port = int(match.group(4))
        else:
            if port != int(match.group(4)):
                print(f"Inconsistent ports during parse(). previous: {port}, current: {match.group(4)}")
        
        timestamp_ns = str_to_ns(match.group(1))

        if initial_timestamp_ns == 0:
            initial_timestamp_ns = timestamp_ns
            
        rtt_us = float(match.group(2)) * 1000
        samples.append((int(timestamp_ns - initial_timestamp_ns), rtt_us))

    return (np.array(samples), port)

def filter_range(data, ratio):
    dist_max = max(data)
    dist_min = min(data)
    bins = np.linspace(dist_min, dist_max, int(dist_max - dist_min) + 1)

    densities, bins = np.histogram(data, bins, density=True)
    for d in densities:
        if d < ratio:
            dist_min += 1
        else:
            break

    for d in reversed(densities):
        if d < ratio:
            dist_max -= 1
        else:
            break

    return dist_min, dist_max

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--flow', '-f', default=6)
    parser.add_argument('--time', '-t', default=60)
    parser.add_argument('--app', '-a', default='iperf')
    parser.add_argument('--silent', '-s', action='store_true')
    parser.add_argument('--vxlan', '-v', action='store_true')
    parser.add_argument('--native', '-n', action='store_true')

    global args
    args = parser.parse_args()

    if args.app != "iperf" and args.app != "neper":
        print("Wrong app name.")
        exit()

    main()
    