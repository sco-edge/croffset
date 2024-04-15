#/bin/bash

n=$1

for ((i=0; i<$n; i++)); do
    for ((j=1; j<7; j++)); do
        ./server.py -f$j -c0 -t120 --no-instrument --sock-only | tee -a run-bbr-2.out
        ./server.py -f0 -c$j -t120 --no-instrument --sock-only | tee -a run-bbr-2.out
    done
done