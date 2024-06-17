#/bin/bash

for ((i=0; i<20; i++)); do
    ./analyze.py --sock-only --path ../dataset/noin-cubic-20240419-c1 run-$i
    # ./analyze.py --path ../dataset/bbr-c1/ run-$i
done
