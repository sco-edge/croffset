#!/usr/bin/python3
import sys
import re

tcp_ext_old = {}
tcp_ext_new = {}
ip_ext_old = {}
ip_ext_new = {}

with open(sys.argv[1]) as file:
    lines = file.readlines()
    tcp_ext_keys = lines[0].split()
    tcp_ext_values = lines[1].split()
    ip_ext_keys = lines[2].split()
    ip_ext_values = lines[3].split()

    for i, tcp_ext_key in enumerate(tcp_ext_keys):
        if i == 0:
            continue
        tcp_ext_old[tcp_ext_key] = int(tcp_ext_values[i])

    for i, ip_ext_key in enumerate(ip_ext_keys):
        if i == 0:
            continue
        ip_ext_old[ip_ext_key] = int(ip_ext_values[i])

with open(sys.argv[2]) as file:
    lines = file.readlines()
    tcp_ext_keys = lines[0].split()
    tcp_ext_values = lines[1].split()
    ip_ext_keys = lines[2].split()
    ip_ext_values = lines[3].split()

    for i, tcp_ext_key in enumerate(tcp_ext_keys):
        if i == 0:
            continue
        tcp_ext_new[tcp_ext_key] = int(tcp_ext_values[i])

    for i, ip_ext_key in enumerate(ip_ext_keys):
        if i == 0:
            continue
        ip_ext_new[ip_ext_key] = int(ip_ext_values[i])

for k in tcp_ext_old:
    if not k in tcp_ext_new:
        continue
    if tcp_ext_new[k] - tcp_ext_old[k] != 0:
        print(k, tcp_ext_new[k] - tcp_ext_old[k])

for k in ip_ext_old:
    if not k in ip_ext_new:
        continue
    if ip_ext_new[k] - ip_ext_old[k] != 0:
        print(k, ip_ext_new[k] - ip_ext_old[k])

exit()