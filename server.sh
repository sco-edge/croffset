#!/bin/bash

n=$1

for ((i=0; i<$n; i++)); do
    ./server.py -l error -f0 -c1 -t60 --cca reno -C 0 | tee -a run-reno-rack.out
    # ./server.py -l error -f6 -c0 -t60 --cca reno -C 0 | tee -a run-reno-host.out
done
