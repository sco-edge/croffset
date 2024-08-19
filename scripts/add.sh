#!/bin/bash

value=$(tc qdisc show dev ens801f0 | awk '/root/ {print $3}' | awk -F: '{print $1}')
for i in $(seq 1 64); do
	tc qdisc add dev ens801f0 parent $value:$(printf "%x" $i) handle $(($i + 100)): netem loss 1%
done
