#/bin/bash

for ((i=2; i<242; i++)); do
    ./analyze.py --sock-only --path ../dataset/no-instrument-bbr-20240413 run-$i
done
