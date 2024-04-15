#!/usr/bin/python3
import matplotlib as mpl
import matplotlib.pyplot as pp
import numpy as np

import sys, os
sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))

from lib import parse as plotparse

extype_map = plotparse.parse_dataset("../../dataset/no-instrument-bbr-20240413")

agg_throughputs = []
agg_retransmissions = []
agg_sr = []
agg_ratio = []

for i in range(1, 7):
    extype = f"h0-c{i}"
    exes = extype_map[extype]

    throughput = []
    retransmission = []
    sr = []
    cflows_per_ex = [ex[1] for ex in exes]
    for cflows in cflows_per_ex:
        throughput.append(np.sum([cflow[0] for cflow in cflows]))
        retransmission.append(np.sum([cflow[1] for cflow in cflows]))
        sr.append(np.sum([cflow[2] for cflow in cflows]))
    
    print(f"{extype}: {np.mean(throughput)}, {np.mean(retransmission)}, {np.mean(sr)}")
    agg_throughputs.append(throughput)
    agg_retransmissions.append(retransmission)
    agg_sr.append(sr)
    ratio = []
    for i, item in enumerate(retransmission):
        if retransmission[i] != 0:
            ratio.append(sr[i] / retransmission[i])
    agg_ratio.append(ratio)


for i in range(1, 7):
    extype = f"h{i}-c0"
    exes = extype_map[extype]

    throughput = []
    retransmission = []
    sr = []
    hflows_per_ex = [ex[0] for ex in exes]
    for hflows in hflows_per_ex:
        throughput.append(np.sum([hflow[0] for hflow in hflows]))
        retransmission.append(np.sum([hflow[1] for hflow in hflows]))
        sr.append(np.sum([hflow[2] for hflow in hflows]))
    
    print(f"{extype}: {np.mean(throughput)}, {np.mean(retransmission)}, {np.mean(sr)}")
    agg_throughputs.append(throughput)
    agg_retransmissions.append(retransmission)
    agg_sr.append(sr)
    ratio = []
    for i, item in enumerate(retransmission):
        if retransmission[i] != 0:
            ratio.append(sr[i] / retransmission[i])
    agg_ratio.append(ratio)

for item in agg_ratio:
    print(item)    

fig, ax = pp.subplots()
ax.boxplot(agg_ratio)
output = f"test.png"
yrange = np.array([0, 2])
pp.ylim(yrange)
pp.savefig(output, dpi=300, bbox_inches='tight', pad_inches=0.05)