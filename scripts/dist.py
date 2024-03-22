#!/usr/bin/python3

import os
import re
import matplotlib.pyplot as pp
import numpy as np
import argparse

def main():
    expr = re.compile(r"^(?:tx|rx)-(.)-f(\d+)-t(\d+)-(.*?)-(\d+)$")
    matched = expr.search(args.target)
    if matched == None:
        print("Wrong format.")
        exit(-1)

    os.chdir("../data")
    if not os.path.exists(args.target):
        print("There is no such target.")
        exit(-1)
    os.chdir(args.target)

    num_flows = int(matched[2])
    for i in range(0, num_flows):
        plot_dists(args.target, i)

def plot_dists(target, flow_index):
    bound = int(args.bound)
    bpf_data = []
    epping_data = []

    bpf_outliers = []
    epping_outliers = []

    max_rtt = 0
    min_rtt = float("inf")
    with open(f"bpftrace.{flow_index}.{target}.out") as f:
        lines = f.readlines()
        for l in lines:
            data = l.split(",")
            if len(data) < 6:
                continue
            if int(data[3]) >= bound:
                bpf_outliers.append(int(data[3]))
                continue

            if int(data[3]) >= max_rtt:
                max_rtt = int(data[3])
            if int(data[3]) <= min_rtt:
                min_rtt = int(data[3])
            bpf_data.append(int(data[3]))

    with open(f"epping.{flow_index}.{target}.out") as f:
        lines = f.readlines()
        for l in lines:
            data = l.split(",")
            if float(data[1].rstrip()) >= bound:
                epping_outliers.append(float(data[1].rstrip()))
                continue

            if int(float(data[1].rstrip())) >= max_rtt:
                max_rtt = int(float(data[1].rstrip()))
            if int(float(data[1].rstrip())) <= min_rtt:
                min_rtt = int(float(data[1].rstrip()))
            epping_data.append(int(float(data[1].rstrip())))


    print(f'{flow_index} epp: {np.average(epping_data):5.1f} ({np.std(epping_data):4.2f}), bpf: {np.average(bpf_data):5.1f} ({np.std(bpf_data):4.2f})')
    print(f'{flow_index} # bpf_outliers: {len(bpf_outliers)} {bpf_outliers}')
    print(f'{flow_index} # epp_outliers: {len(epping_outliers)} {epping_outliers}')

    if args.figure_bound:
        max_rtt = int(args.figure_bound)
    bins = np.linspace(min_rtt, max_rtt, max_rtt - min_rtt + 1)

    figure = pp.figure(figsize=(10, 6))
    pp.hist(bpf_data, bins, alpha=0.5, label='bpftrace', density=True)
    pp.hist(epping_data, bins, alpha=0.5, label='epping', density=True)
        
    output = f"dist2.{flow_index}.{target}.png"
    pp.savefig(output, dpi=300, bbox_inches='tight', pad_inches=0.05)

    figure = pp.figure(figsize=(10, 6))
    pp.hist(bpf_data, bins, alpha=0.5, label='bpftrace', histtype='step', cumulative=True, density=True)
    pp.hist(epping_data, bins, alpha=0.5, label='epping', histtype='step', cumulative=True, density=True)
    pp.xlim(0, max_rtt)
    pp.ylim(0, 1.0)
        
    output = f"dist3.{flow_index}.{target}.png"
    pp.savefig(output, dpi=300, bbox_inches='tight', pad_inches=0.05)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("target")
    parser.add_argument("--bound", "-b", default=100)
    parser.add_argument("--figure-bound", "-f", default=100)

    global args
    args = parser.parse_args()
    main()