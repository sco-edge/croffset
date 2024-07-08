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
    comp = None
    altcomp = None
    c_gain = None
    a_gain = None

    def __init__(self, filename, extype, throughput, mean_throughput, retrans, spurious_retrans, comp, altcomp):
        self.filename = filename
        self.extype = extype
        self.throughput = throughput
        self.mean_throughput = mean_throughput
        self.retrans = retrans
        self.spurious_retrans = spurious_retrans
        self.comp = comp
        self.altcomp = altcomp
        if spurious_retrans == 0:
            self.c_gain = -1
            self.a_gain = -1
        else:
            if comp == 0:
                self.c_gain = 0
            else:    
                self.c_gain = comp / spurious_retrans

            if altcomp == 0:
                self.a_gain = 0
            else:
                self.a_gain = altcomp / spurious_retrans

        match = expr.search(extype)
        self.num_flows = int(match.group(1)) + int(match.group(2))

    def print_stat(self):
        print(f"{self.filename} {self.extype}, {self.throughput:.2f} {self.mean_throughput:.2f} {self.retrans} {self.spurious_retrans}")

def parse_run(path, experiment):
    if not os.path.isdir(os.path.join(path, experiment)):
        print(f"Parsing {os.path.join(path, experiment)} failed: no dir.")
        return None
    
    summary_json = f"summary.{experiment}.json"
    if not os.path.exists(os.path.join(path, experiment, summary_json)):
        print(f"Parsing {os.path.join(path, experiment)} failed: no summary.")
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
            comp = flow.get("comp_count")
            comp = spurious_retrans - comp if spurious_retrans >= comp else 0
            altcomp = flow.get("altcomp_count")
            altcomp = spurious_retrans - altcomp if spurious_retrans >= altcomp else 0
            hflows.append((throughput, retrans, spurious_retrans, comp, altcomp))
            hflow_index += 1
        
        cflows = []
        cflow_index = 0
        while (f"c{cflow_index}" in summary):
            flow = summary.get(f"c{cflow_index}")
            throughput = flow.get("throughput")
            retrans = flow.get("retransmissions")
            spurious_retrans = flow.get("sr_count")
            comp = flow.get("comp_count")
            comp = spurious_retrans - comp if spurious_retrans >= comp else 0
            altcomp = flow.get("altcomp_count")
            altcomp = spurious_retrans - altcomp if spurious_retrans >= altcomp else 0
            cflows.append((throughput, retrans, spurious_retrans, comp, altcomp))
            cflow_index += 1
        
        extype = f"h{len(hflows)}-c{len(cflows)}"
        if len(hflows) != 0 and len(cflows) != 0:
            print(f"Parsing {os.path.join(path, experiment)} failed: {extype}.")
            return None        
        
        throughput = np.sum([item[0] for item in hflows + cflows])
        mean_throughput = np.mean([item[0] for item in hflows + cflows])
        retrans = np.sum([item[1] for item in hflows + cflows])
        spurious_retrans = np.sum([item[2] for item in hflows + cflows])
        comp = np.sum([item[3] for item in hflows + cflows])
        altcomp = np.sum([item[4] for item in hflows + cflows])

        return Run(os.path.join(path, experiment), extype, throughput, mean_throughput, retrans, spurious_retrans, comp, altcomp)

def parse_run_offset(path, experiment):
    if not os.path.isdir(os.path.join(path, experiment)):
        print(f"Parsing {os.path.join(path, experiment)} failed: no dir.")
        return None
    
    summary_json = f"summary.{experiment}.json"
    if not os.path.exists(os.path.join(path, experiment, summary_json)):
        print(f"Parsing {os.path.join(path, experiment)} failed: no summary.")
        return None
    
    with open(os.path.join(path, experiment, summary_json), 'r') as file:
        summary = json.load(file)
        hflows = []
        hflow_index = 0
        while (f"h{hflow_index}" in summary):
            flow = summary.get(f"h{hflow_index}")
            trtt = flow.get("trtt_mean")
            brtt = flow.get("brtt_mean")
            offset = flow.get("offset_mean")
            offset_std = flow.get("offset_std")
            offset_send = flow.get("offset_send_mean")
            offset_send_std = flow.get("offset_send_std")
            offset_recv= flow.get("offset_recv_mean")
            offset_recv_std = flow.get("offset_recv_std")
            sr = flow.get("sr_count")
            hflows.append((trtt, brtt, offset, offset_std, offset_send, offset_send_std, offset_recv, offset_recv_std, sr))
            hflow_index += 1
        
        cflows = []
        cflow_index = 0
        while (f"c{cflow_index}" in summary):
            flow = summary.get(f"c{cflow_index}")
            trtt = flow.get("trtt_mean")
            brtt = flow.get("brtt_mean")
            offset = flow.get("offset_mean")
            offset_std = flow.get("offset_std")
            offset_send = flow.get("offset_send_mean")
            offset_send_std = flow.get("offset_send_std")
            offset_recv= flow.get("offset_recv_mean")
            offset_recv_std = flow.get("offset_recv_std")
            sr = flow.get("sr_count")
            cflows.append((trtt, brtt, offset, offset_std, offset_send, offset_send_std, offset_recv, offset_recv_std, sr))
            cflow_index += 1
        
        extype = f"h{len(hflows)}-c{len(cflows)}"
        if len(hflows) != 0 and len(cflows) != 0:
            print(f"Parsing {os.path.join(path, experiment)} failed: {extype}.")
            return None

        return (extype, hflows + cflows)

def parse_run_only_sr(path, experiment):
    if not os.path.isdir(os.path.join(path, experiment)):
        print(f"Parsing {os.path.join(path, experiment)} failed: no dir.")
        return None
    
    summary_json = f"summary.{experiment}.json"
    if not os.path.exists(os.path.join(path, experiment, summary_json)):
        print(f"Parsing {os.path.join(path, experiment)} failed: no summary.")
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
            print(f"Parsing {os.path.join(path, experiment)} failed: {extype}.")
            return None        
        
        throughput = np.sum([item[0] for item in hflows + cflows])
        mean_throughput = np.mean([item[0] for item in hflows + cflows])
        retrans = np.sum([item[1] for item in hflows + cflows])
        spurious_retrans = np.sum([item[2] for item in hflows + cflows])

        return Run(os.path.join(path, experiment), extype, throughput, mean_throughput, retrans, spurious_retrans, 0, 0)