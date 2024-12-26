#!/bin/bash

n=$1

for ((i=0; i<$n; i++)); do  
    ./server-varying-scenario.py -l error -f 0 -c 4 -t15 | tee -a run-varying-comp-bbr.out
    # ./server-varying-scenario.py -l error -f 0 -c 4 --cca cubic -t15 --no-instrument | tee -a run-varying-comp-cubic.out
done

# for ((i=0; i<$n; i++)); do  
#     ./server-varying-scenario.py -l error -f 0 -c 4 --cca cubic -t15 -C0 | tee -a run-varying-default-cubic.out
# done    