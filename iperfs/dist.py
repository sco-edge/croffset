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
    bpf_data = []
    epping_data = []
    max_rtt = 0
    min_rtt = float("inf")
    with open(f"bpftrace.{flow_index}.{target}.out") as f:
        lines = f.readlines()
        for l in lines:
            data = l.split(",")
            if int(data[1]) >= max_rtt:
                max_rtt = int(data[1])
            if int(data[1]) <= min_rtt:
                min_rtt = int(data[1])
            bpf_data.append(int(data[1]))

    with open(f"epping.{flow_index}.{target}.out") as f:
        lines = f.readlines()
        for l in lines:
            data = l.split(",")
            if int(float(data[1].rstrip())) >= max_rtt:
                max_rtt = int(float(data[1].rstrip()))
            if int(float(data[1].rstrip())) <= min_rtt:
                min_rtt = int(float(data[1].rstrip()))
            epping_data.append(int(float(data[1].rstrip())))

    print(flow_index, len(bpf_data), len(epping_data))

    bins = np.linspace(min_rtt, max_rtt, max_rtt - min_rtt + 1)

    figure = pp.figure(figsize=(10, 6))
    pp.hist(bpf_data, bins, alpha=0.5, label='bpftrace', density=True)
    pp.hist(epping_data, bins, alpha=0.5, label='epping', density=True)
        
    output = f"dist.{flow_index}.{target}.png"
    pp.savefig(output, dpi=300, bbox_inches='tight', pad_inches=0.05)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("target")

    global args
    args = parser.parse_args()
    main()