#/bin/bash

n=$1

for ((i=0; i<$n; i++)); do
    for ((j=1; j<7; j++)); do
        ./run.py -f$j -c0 -t120 --no-instrument --sock-only | tee -a run-bbr-2.out
        ./run.py -f0 -c$j -t120 --no-instrument --sock-only | tee -a run-bbr-2.out
    done
done

# ./run.py -f1 -c0 -t120 --no-instrument --loss-detection reno-er | tee -a run.out
# ./run.py -f2 -c0 -t120 --no-instrument --loss-detection reno-er | tee -a run.out
# ./run.py -f3 -c0 -t120 --no-instrument --loss-detection reno-er | tee -a run.out
# ./run.py -f4 -c0 -t120 --no-instrument --loss-detection reno-er | tee -a run.out
# ./run.py -f5 -c0 -t120 --no-instrument --loss-detection reno-er | tee -a run.out
# ./run.py -f6 -c0 -t120 --no-instrument --loss-detection reno-er | tee -a run.out

# ./run.py -f0 -c1 -t120 --no-instrument --loss-detection reno-er | tee -a run.out
# ./run.py -f0 -c2 -t120 --no-instrument --loss-detection reno-er | tee -a run.out
# ./run.py -f0 -c3 -t120 --no-instrument --loss-detection reno-er | tee -a run.out
# ./run.py -f0 -c4 -t120 --no-instrument --loss-detection reno-er | tee -a run.out
# ./run.py -f0 -c5 -t120 --no-instrument --loss-detection reno-er | tee -a run.out
# ./run.py -f0 -c6 -t120 --no-instrument --loss-detection reno-er | tee -a run.out

# ./run.py -f1 -c0 -t120 --no-instrument --cca cubic --loss-detection reno-er | tee -a run.out
# ./run.py -f2 -c0 -t120 --no-instrument --cca cubic --loss-detection reno-er | tee -a run.out
# ./run.py -f3 -c0 -t120 --no-instrument --cca cubic --loss-detection reno-er | tee -a run.out
# ./run.py -f4 -c0 -t120 --no-instrument --cca cubic --loss-detection reno-er | tee -a run.out
# ./run.py -f5 -c0 -t120 --no-instrument --cca cubic --loss-detection reno-er | tee -a run.out
# ./run.py -f6 -c0 -t120 --no-instrument --cca cubic --loss-detection reno-er | tee -a run.out

# ./run.py -f0 -c1 -t120 --no-instrument --cca cubic --loss-detection reno-er | tee -a run.out
# ./run.py -f0 -c2 -t120 --no-instrument --cca cubic --loss-detection reno-er | tee -a run.out
# ./run.py -f0 -c3 -t120 --no-instrument --cca cubic --loss-detection reno-er | tee -a run.out
# ./run.py -f0 -c4 -t120 --no-instrument --cca cubic --loss-detection reno-er | tee -a run.out
# ./run.py -f0 -c5 -t120 --no-instrument --cca cubic --loss-detection reno-er | tee -a run.out
# ./run.py -f0 -c6 -t120 --no-instrument --cca cubic --loss-detection reno-er | tee -a run.out