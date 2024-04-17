#!/usr/bin/python3
import os
import json
import re
import numpy as np

expr = re.compile(r"^h(\d+?)-c(\d+?)$")

class Run:
    filename = None
    extype = None
    num_flows = None
    throughput = None
    mean_throughput = None
    retrans = None
    spurious_retrans = None

    def __init__(self, filename, extype, throughput, mean_throughput, retrans, spurious_retrans):
        self.filename = filename
        self.extype = extype
        self.throughput = throughput
        self.mean_throughput = mean_throughput
        self.retrans = retrans
        self.spurious_retrans = spurious_retrans

        match = expr.search(extype)
        self.num_flows = int(match.group(1)) + int(match.group(2))

    def print_stat(self):
        print(f"{self.filename} {self.extype}, {self.throughput:.2f} {self.mean_throughput:.2f} {self.retrans} {self.spurious_retrans}")

def parse_run(path, experiment):
    if not os.path.isdir(os.path.join(path, experiment)):
        print(f"Parsing {experiment} failed: no dir.")
        return None
    
    summary_json = f"summary.{experiment}.json"
    if not os.path.exists(os.path.join(path, experiment, summary_json)):
        print(f"Parsing {experiment} failed: no summary.")
        return None
    
    with open(os.path.join(path, experiment, summary_json), 'r') as file:
        summary = json.load(file)

        hflows = []
        hflow_index = 0
        while (f"h{hflow_index}" in summary):
            flow = summary.get(f"h{hflow_index}")
            throughput = flow.get("throughput")
            retrans = flow.get("retransmissions")
            spurious_retrans = flow.get("sr_count")
            hflows.append((throughput, retrans, spurious_retrans))
            hflow_index += 1
        
        cflows = []
        cflow_index = 0
        while (f"c{cflow_index}" in summary):
            flow = summary.get(f"c{cflow_index}")
            throughput = flow.get("throughput")
            retrans = flow.get("retransmissions")
            spurious_retrans = flow.get("sr_count")
            cflows.append((throughput, retrans, spurious_retrans))
            cflow_index += 1
        
        extype = f"h{len(hflows)}-c{len(cflows)}"
        if len(hflows) != 0 and len(cflows) != 0:
            print(f"Parsing {experiment} failed: {extype}.")
            return None
        
        throughput = np.sum([item[0] for item in hflows + cflows])
        mean_throughput = np.mean([item[0] for item in hflows + cflows])
        retrans = np.sum([item[1] for item in hflows + cflows])
        spurious_retrans = np.sum([item[2] for item in hflows + cflows])

        return Run(os.path.join(path, experiment), extype, throughput, mean_throughput, retrans, spurious_retrans)