#!/bin/bash

for i in $(seq 1 64); do
	tc qdisc del dev ens801f0 parent :$(printf "%x" $i) handle $(($i + 100)): netem
done
