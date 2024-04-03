#/bin/bash

# n=$1

# for((i=0; i<$n; i++))
# do
#     ./run.py -f0 -c1 --no-trace | tee run.out
#     ./run.py -f1 -c0 --no-trace | tee run.out
# done

# ./run.py -f1 -c0 -t120 --no-trace --loss-detection reno-er | tee -a run.out
# ./run.py -f2 -c0 -t120 --no-trace --loss-detection reno-er | tee -a run.out
# ./run.py -f3 -c0 -t120 --no-trace --loss-detection reno-er | tee -a run.out
# ./run.py -f4 -c0 -t120 --no-trace --loss-detection reno-er | tee -a run.out
# ./run.py -f5 -c0 -t120 --no-trace --loss-detection reno-er | tee -a run.out
# ./run.py -f6 -c0 -t120 --no-trace --loss-detection reno-er | tee -a run.out

# ./run.py -f0 -c1 -t120 --no-trace --loss-detection reno-er | tee -a run.out
# ./run.py -f0 -c2 -t120 --no-trace --loss-detection reno-er | tee -a run.out
# ./run.py -f0 -c3 -t120 --no-trace --loss-detection reno-er | tee -a run.out
# ./run.py -f0 -c4 -t120 --no-trace --loss-detection reno-er | tee -a run.out
# ./run.py -f0 -c5 -t120 --no-trace --loss-detection reno-er | tee -a run.out
# ./run.py -f0 -c6 -t120 --no-trace --loss-detection reno-er | tee -a run.out

./run.py -f1 -c0 -t120 --no-trace --cca cubic --loss-detection reno-er | tee -a run.out
./run.py -f2 -c0 -t120 --no-trace --cca cubic --loss-detection reno-er | tee -a run.out
./run.py -f3 -c0 -t120 --no-trace --cca cubic --loss-detection reno-er | tee -a run.out
./run.py -f4 -c0 -t120 --no-trace --cca cubic --loss-detection reno-er | tee -a run.out
./run.py -f5 -c0 -t120 --no-trace --cca cubic --loss-detection reno-er | tee -a run.out
./run.py -f6 -c0 -t120 --no-trace --cca cubic --loss-detection reno-er | tee -a run.out

./run.py -f0 -c1 -t120 --no-trace --cca cubic --loss-detection reno-er | tee -a run.out
./run.py -f0 -c2 -t120 --no-trace --cca cubic --loss-detection reno-er | tee -a run.out
./run.py -f0 -c3 -t120 --no-trace --cca cubic --loss-detection reno-er | tee -a run.out
./run.py -f0 -c4 -t120 --no-trace --cca cubic --loss-detection reno-er | tee -a run.out
./run.py -f0 -c5 -t120 --no-trace --cca cubic --loss-detection reno-er | tee -a run.out
./run.py -f0 -c6 -t120 --no-trace --cca cubic --loss-detection reno-er | tee -a run.out