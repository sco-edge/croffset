#!/usr/bin/python3
import subprocess
import tempfile
import json
import os
import matplotlib.pyplot as plot
import numpy as np
import re
import time

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
    num_flows = 6
    time = 60
    server_addr = "192.168.2.103"
    interface = "ens801f0"
    cca = "bbr"
    tag = "1ms"

    if not tag:
        experiment = f"f{num_flows}-t{time}-{cca}-0"
    else:
        experiment = f"{tag}-f{num_flows}-t{time}-{cca}-0"

    (epping_p, epping_f) = run_epping(interface)
    # statistics = run_iperfs(num_flows, time, server_addr)
    flows = run_iperfs(num_flows, time, server_addr)
    post_process_epping(epping_p, epping_f, experiment, num_flows, flows)

def run_epping(interface):
    os.chdir("..")
    f = tempfile.NamedTemporaryFile()
    p = subprocess.Popen(["./pping", "-i", interface], stdout=f)

    time.sleep(1)
    return (p, f)

def post_process_epping(epping_p, epping_f, experiment, num_flows, flows):
    epping_p.kill()

    os.chdir("data")
    while os.path.exists(experiment):
        (remained, last) = experiment.rsplit("-", 1)
        trial = int(last) + 1
        experiment = f"{remained}-{trial}"

    os.mkdir(experiment)
    os.chdir(experiment)

    epping_f.seek(0)
    # ports = frequent_flows(epping_f, num_flows)


    # for port in ports:
    for flow in flows:
        # name = f'{num}.{experiment}'
        epping_f.seek(0)
        samples = parse(epping_f, "TCP", "192.168.2.103", str(flow.dport), "192.168.2.102", str(flow.sport))

        x = list(zip(*samples))[0]
        y = list(zip(*samples))[1]
        # print(f'{name} ({port[1]}): {np.average(y):.3f} ({np.std(y):.3f})')
        # print(port[1], port[0])
        i, flow = find_flow(flows, flow.dport)
        flow.rtt_mean = np.average(y)
        flow.rtt_std = np.std(y)
        # if flow:
        #     print(f'{num} ({port[1]}-{port[0]}): {stat[0]:.1f} Gbps, {stat[1]}, {stat[2]:.1f}% {np.average(y):.3f} ({np.std(y):.3f})')

        figure = plot.figure(figsize=(10, 6))
        xrange = np.array([0, 60000000])
        yrange = np.array([0, 6000])
        plot.xlim(xrange)
        plot.ylim(yrange)
        plot.xticks(np.linspace(*xrange, 7))
        plot.yticks(np.linspace(*yrange, 11))

        # plot.plot(x, y, 'o-', label='No mask')
        plot.plot(x, y, linewidth=0.5)
        
        name = f'{i}.{experiment}'
        output = f"pping.{name}.png"
        plot.savefig(output, dpi=300, bbox_inches='tight', pad_inches=0.05)
    
    aggregate_throughput = 0
    for i, flow in enumerate(flows):
        gbps = flow.throughput / 1000000000
        diff = flow.iperf_rtt_mean_us - flow.rtt_mean
        print(f'{i} ({flow.sport}-{flow.dport}): {gbps:>4.1f} Gbps, {flow.retransmissions:>7}, h{flow.sutilization:>4.1f}%, r{flow.dutilization:>4.1f}% \
{flow.iperf_rtt_mean_us} us {flow.rtt_mean:.0f} us (+{diff:>3.0f} us +{(diff/flow.rtt_mean * 100):>4.1f}% std: {flow.rtt_std:>3.0f})')
        aggregate_throughput += flow.throughput
    print(f"{experiment} Aggregate Throughput: {aggregate_throughput / 1000000000:.1f} Gbps")

def run_iperfs(num_flows, time, server_addr):
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
        flow.throughput = data["end"]["sum_sent"]["bits_per_second"]
        flow.retransmissions = data["end"]["sum_sent"]["retransmits"]
        flow.iperf_rtt_mean_us = data["end"]["streams"][0]["sender"]["mean_rtt"]
        flow.sutilization = data["end"]["cpu_utilization_percent"]["host_total"]
        flow.dutilization = data["end"]["cpu_utilization_percent"]["remote_total"]

        # while True:
        #     line = f.readline()
        #     if not line:
        #         break
        #     print(line.decode('utf-8'), end='')
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
    main()