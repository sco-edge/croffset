#!/usr/bin/python3
import sys
import re

old = []
new = []
expr = re.compile(r".*ice-ens801f0-TxRx-(\d+)$")

with open(sys.argv[1]) as file:
    lines = file.readlines()
    for l in lines:
        match = expr.search(l)
        if not match:
            continue
        queue = int(match.group(1))
        tokens = l.split()
        old.append([])
        for (i, token) in enumerate(tokens):
            if i == 0:
                old[queue] = []
                continue
            if i > 64:
                break
            old[queue].append(int(token))

with open(sys.argv[2]) as file:
    lines = file.readlines()
    for l in lines:
        match = expr.search(l)
        if not match:
            continue
        queue = int(match.group(1))
        tokens = l.split()
        new.append([])
        for (i, token) in enumerate(tokens):
            if i == 0:
                new[queue] = []
                continue
            if i > 64:
                break
            new[queue].append(int(token))

for i in range(0, 32):
    diffs = []
    for j in range(0, 64):
        diff = new[i][j] - old[i][j]
        if diff != 0:
            diffs.append((j, diff))
    print(f"Q{i:>2}: ", end="")
    for diff in diffs:
        print(f"C{diff[0]:>2} {diff[1]:>7}  ", end="")
    print("")