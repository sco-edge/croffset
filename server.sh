#/bin/bash

n=$1

# for ((i=0; i<$n; i++)); do
#     for ((j=1; j<7; j++)); do
#         ./server.py -f$j -c0 -t120 --no-instrument --sock-only | tee -a run-bbr-2.out
#         ./server.py -f0 -c$j -t120 --no-instrument --sock-only | tee -a run-bbr-2.out
#     done
# done

# for ((i=0; i<$n; i++)); do
#     ./server.py -f0 -c6 -t30 | tee -a bbr-c6.out
# done

for ((i=0; i<$n; i++)); do
    # ./server.py -f0 -c1 -t10 --no-instrument --sock-only | tee -a noin-reno-er-bbr-20240418-c1.out
    ./server.py -f0 -c1 -t30 --no-instrument --sock-only | tee -a noin-cubic-20240419-c1.out
done
