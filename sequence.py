#!/usr/bin/python3
import argparse
import os
import json

def analyze_sequences(experiment):
    flows = {}
    last_dequeue_edt_per_flow = {}
    with open(f"fq.{experiment}.out", "r") as file:    
        lines = file.readlines()
        for l in lines:
            tokens = l.split()
            if len(tokens) < 6:
                continue
            
            ts = tokens[0]
            method = tokens[1]
            sk = tokens[2]
            skb = tokens[3]
            cpu = tokens[4]
            edt = tokens[5]
            if not sk in flows:
                flows[sk] = {}
            
            if method == "fq_enqueue()":
                flows[sk][edt] = (ts, skb, cpu)

            if method == "fq_dequeue()":
                if edt in flows[sk]:
                    if sk in last_dequeue_edt_per_flow:
                        if edt < last_dequeue_edt_per_flow[sk][0]:
                            # print(ts, skb, cpu)
                            print(last_dequeue_edt_per_flow[sk][0], last_dequeue_edt_per_flow[sk][1], l, end="")
                    last_dequeue_edt_per_flow[sk] = (edt, cpu)

if __name__ == "__main__":
    argparser = argparse.ArgumentParser()
    argparser.add_argument('experiment')
    argparser.add_argument('--path', default="../output")

    global args
    args = argparser.parse_args()

    global swd
    swd = os.path.join(os.getcwd(), 'scripts')
    os.chdir(os.path.join(swd, args.path, args.experiment))

    # Main logic
    analyze_sequences(args.experiment)
    