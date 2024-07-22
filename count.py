#!/usr/bin/python3
import subprocess
import tempfile

tcp_ext = {}
ip_ext = {}

# netstat_args = ["cat", "/proc/net/netstat"]
netstat_args = ["kubectl", "exec", "iperf-server-deployment-1-6dc5d5bb8f-z5t4k", "--", \
                "cat", "/proc/net/netstat"]
netstat_file = tempfile.NamedTemporaryFile()
subprocess.run(netstat_args, stdout=netstat_file)
with open(netstat_file.name, "r") as file:
    lines = file.readlines()
    tcp_ext_keys = lines[0].split()
    tcp_ext_values = lines[1].split()
    ip_ext_keys = lines[2].split()
    ip_ext_values = lines[3].split()

for i, tcp_ext_key in enumerate(tcp_ext_keys):
    if i == 0:
        continue
    tcp_ext[tcp_ext_key] = tcp_ext_values[i]

for i, ip_ext_key in enumerate(ip_ext_keys):
    if i == 0:
        continue
    ip_ext[ip_ext_key] = ip_ext_values[i]

for k in tcp_ext:
    print(k, tcp_ext[k])

for k in ip_ext:
    print(k, ip_ext[k])