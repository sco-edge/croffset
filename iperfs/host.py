#!/usr/bin/python3
import subprocess
import tempfile
import json
import os
import matplotlib.pyplot as plot
import numpy as np
import re
import time
import argparse

class FlowStat:
    sport:int = None
    dport:int = None
    throughput:float = None
    retransmissions:int = None
    iperf_rtt_mean_us:int = None
    sutilization:float = None
    dutilization:float = None
    iperf_rtt_mean:float = None
    rtt_mean:float = None
    rtt_std:float = None

def main():
    num_flows = int(args.flow)
    time = int(args.time)
    server_addr = "192.168.2.103"
    interface = "ens801f0"
    cca = "bbr"
    tag = ""

    if not tag:
        experiment = f"tx-h-f{num_flows}-t{time}-{cca}-0"
    else:
        experiment = f"tx-h-{tag}-f{num_flows}-t{time}-{cca}-0"

    (util_p, util_f) = start_cpu_utilization()
    interrupt_f = start_interrupt_count()
    (epping_p, epping_f) = run_epping(interface)
    flows = run_iperf_clients(num_flows, time, server_addr)

    if not os.path.exists("data"):
        os.mkdir("data")
    os.chdir("data")

    while os.path.exists(experiment):
        (remained, last) = experiment.rsplit("-", 1)
        trial = int(last) + 1
        experiment = f"{remained}-{trial}"

    os.mkdir(experiment)
    os.chdir(experiment)

    end_cpu_utilization(util_p, util_f, experiment)
    post_process_interrupt_count(interrupt_f, experiment)
    post_process_epping(epping_p, epping_f, experiment, flows)

def run_epping(interface):
    os.chdir("..")
    f = tempfile.NamedTemporaryFile()
    p = subprocess.Popen(["./pping", "-i", interface], stdout=f)

    time.sleep(2)
    return (p, f)

def start_cpu_utilization():
    f = tempfile.NamedTemporaryFile()
    p = subprocess.Popen(["./cpuload.sh"], stdout=f)

    return (p, f)

def end_cpu_utilization(p, f, experiment):
    p.kill()
    with open(f'cpu.{experiment}.out', 'w') as cpu_output:
        subprocess.run(["../../iperfs/cpu.py", f.name], stdout=cpu_output)

    if not args.silent:
        subprocess.run(["../../iperfs/cpu.py", "-c", f.name])
    
def start_interrupt_count():
    f = tempfile.NamedTemporaryFile()
    subprocess.run(["cat", "/proc/interrupts"], stdout=f)

    return f

def post_process_interrupt_count(old_f, experiment):
    new_f = tempfile.NamedTemporaryFile()
    subprocess.run(["cat", "/proc/interrupts"], stdout=new_f)

    with open(f'int.{experiment}.out', 'w') as interrupt_output:
        subprocess.run(["../../iperfs/interrupts.py", old_f.name, new_f.name], stdout=interrupt_output)

    if not args.silent:
        subprocess.run(["../../iperfs/interrupts.py", old_f.name, new_f.name])

def post_process_epping(epping_p, epping_f, experiment, flows):
    epping_p.kill()

    max_rtt = 0
    rtts = {}

    for flow in flows:
        epping_f.seek(0)
        samples = parse(epping_f, "TCP", "192.168.2.103", str(flow.dport), "192.168.2.102", str(flow.sport))

        if len(samples) == 0:
            print("There is no epping samples.")
            exit(-1)

        x = list(zip(*samples))[0]
        y = list(zip(*samples))[1]
        i, flow = find_flow(flows, flow.dport)

        flow.rtt_mean = np.average(y)
        flow.rtt_std = np.std(y)

        if np.max(y) >= max_rtt:
            max_rtt = np.max(y)

        rtts[i] = (x, y)

    for i, _ in enumerate(flows):
        (x, y) = rtts[i]

        figure = plot.figure(figsize=(10, 6))
        xrange = np.array([0, 60000000])
        yrange = np.array([0, max_rtt])
        plot.xlim(xrange)
        plot.ylim(yrange)
        plot.xticks(np.linspace(*xrange, 7))
        plot.yticks(np.linspace(*yrange, 11))

        # plot.plot(x, y, 'o-', label='No mask')
        plot.plot(x, y, linewidth=0.5)
        
        name = f'{i}.{experiment}'
        output = f"pping.{name}.png"
        plot.savefig(output, dpi=300, bbox_inches='tight', pad_inches=0.05)
    
    data = {}
    aggregate_throughput = 0
    for i, flow in enumerate(flows):
        gbps = flow.throughput
        diff = flow.iperf_rtt_mean_us - flow.rtt_mean
        print(f'{i} ({flow.sport}-{flow.dport}): {gbps:>4.1f} Gbps, {flow.retransmissions:>7}, h{flow.sutilization:>4.1f}%, r{flow.dutilization:>4.1f}% \
{flow.iperf_rtt_mean_us} us {flow.rtt_mean:.0f} us (+{diff:>3.0f} us +{(diff/flow.rtt_mean * 100):>4.1f}% std: {flow.rtt_std:>3.0f})')
        aggregate_throughput += flow.throughput
        data[f"flow{i}"] = vars(flow)

    print(f"{experiment} Aggregate Throughput: {aggregate_throughput:.1f} Gbps")
    data["aggregate throughput"] = aggregate_throughput
    with open(f'{experiment}.json', 'w') as f:
        json.dump(data, f)

def run_iperf_clients(num_flows, time, server_addr):
    flows = []
    processes = []
    for i in range(0, num_flows):
        port = 5200 + i
        cpu = 16 + i
        f = tempfile.NamedTemporaryFile()
        p = subprocess.Popen(["iperf3", "-c", server_addr, "-p", str(port), "-t", str(time), "-J", "-A", str(cpu)], stdout=f)
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
        _, flow = find_flow(flows, dport)

        flow.sport = data["start"]["connected"][0]["local_port"]
        flow.throughput = data["end"]["sum_sent"]["bits_per_second"] / 1000000000
        flow.retransmissions = data["end"]["sum_sent"]["retransmits"]
        flow.iperf_rtt_mean_us = data["end"]["streams"][0]["sender"]["mean_rtt"]
        flow.sutilization = data["end"]["cpu_utilization_percent"]["host_total"]
        flow.dutilization = data["end"]["cpu_utilization_percent"]["remote_total"]

        f.close()

    return flows

def str_to_ns(time_str):
    h, m, s = time_str.split(":")
    int_s, ns = s.split(".")
    ns = map(lambda t, unit: np.timedelta64(t, unit), [h,m,int_s,ns.ljust(9, '0')],['h','m','s','ns'])
    return sum(ns)

def parse(f, protocol, saddr, sport, daddr, dport):
    samples = []
    initial_timestamp_ns = 0
    target = protocol + " " + saddr + ":" + sport + "+" + daddr + ":" + dport
    expr = re.compile(r"^(\d{2}:\d{2}:\d{2}\.\d{9})\s(.+?)\sms\s(.+?)\sms\s" + re.escape(target) + r"$")
    lines = f.readlines()
    for l in lines:
        l = l.decode("utf-8")
        match = expr.search(l)
        if match == None:
            continue
        
        timestamp_ns = str_to_ns(match.group(1))

        if initial_timestamp_ns == 0:
            initial_timestamp_ns = timestamp_ns
            
        rtt_us = float(match.group(2)) * 1000
        samples.append(((timestamp_ns - initial_timestamp_ns) / 1000, rtt_us))

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

    global args
    args = parser.parse_args()
    main()