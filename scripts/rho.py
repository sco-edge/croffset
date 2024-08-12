#!/usr/bin/python3
import sys
import re

old = []
new = []
expr = re.compile(r".*ice-ens801f0-TxRx-(\d+)$")

# 412767728982702 tcp_rack_detect_loss() enter 0xff23091319269a40 0 3 1658 3   12 921 1
# 412767728985384 tcp_mark_skb_lost() 0xff23091319269a40 0xff230913187cb000 45000 18   935 1025 0 25164   923 921 412767728053 412767727951111
# 412767728985806 tcp_rack_detect_loss() exit

with open(sys.argv[1]) as file:
    remained = []
    rho = {}
    lines = file.readlines()
    for line in lines:
        tokens = line.split()
        if len(tokens) < 3:
            continue

        if tokens[1] == "tcp_rack_detect_loss()" and tokens[2] == "enter":
            rho[tokens[3]] = (int(tokens[0]), int(tokens[8]) * 1000)
            continue

        if tokens[1] == "tcp_mark_skb_lost()":
            if not tokens[2] in rho or rho[tokens[2]] == None:
                continue
        
            (ts, data) = rho[tokens[2]]
            if int(tokens[0]) - ts > 5_000_000:
                rho[tokens[2]] = None
                continue
            remained.append((int(tokens[12]) * 1000 - int(tokens[13])) - data)

print(" ".join(map(str, remained)), end="")