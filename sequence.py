#!/usr/bin/python3
import argparse
import os
import numpy as np

class QueueStatus:
    last_enqueue_edt = None
    last_enqueue_cpu = None
    last_dequeue_edt = None
    last_dequeue_cpu = None
    queue = set()

    ooo_enqueue = 0
    ooo_dequeue = 0
    ooo_dequeue_legal = 0

def ooo_queuing(experiment):
    flows = {}
    with open(f"fq.{experiment}.out", "r") as file:    
        lines = file.readlines()
        for l in lines:
            tokens = l.split()
            if len(tokens) < 6:
                continue
            
            ts = int(tokens[0])
            method = tokens[1]
            sk = tokens[2]
            skb = tokens[3]
            cpu = tokens[4]
            edt = int(tokens[5])
            if not sk in flows:
                flows[sk] = QueueStatus()

            if method == "fq_enqueue()":
                if sk in flows:
                    qs = flows[sk]
                    qs.queue.add(edt)
                    # print(len(qs.queue), edt - ts, l, end="")
                    if not qs.last_enqueue_edt:
                        qs.last_enqueue_edt = edt
                        qs.last_enqueue_cpu = cpu
                        continue

                    if edt < qs.last_enqueue_edt:
                        qs.ooo_enqueue += 1
                        # print(last_dequeue_edt_per_flow[sk][0], last_dequeue_edt_per_flow[sk][1], l, end="")
                    qs.last_enqueue_edt = edt
                    qs.last_enqueue_cpu = cpu

            if method == "fq_dequeue()":
                # if edt == 574068449121493:
                #     break
                if sk in flows:
                    qs = flows[sk]
                    if edt in qs.queue:
                        qs.queue.remove(edt)
                    # print(len(qs.queue), edt - ts, l, end="")
                    if not qs.last_dequeue_edt:
                        qs.last_dequeue_edt = edt
                        qs.last_dequeue_cpu = cpu
                        continue

                    if edt < qs.last_dequeue_edt:
                        print(len(qs.queue), l)
                        for entry in qs.queue:
                            print(entry, edt - entry)
                        qs.ooo_dequeue += 1
                        if len(qs.queue) == 0:
                            qs.ooo_dequeue_legal += 1
                    qs.last_dequeue_edt = edt
                    qs.last_dequeue_cpu = cpu

    for sk in flows:
        if flows[sk].ooo_enqueue != 0 or flows[sk].ooo_dequeue != 0 or flows[sk].ooo_dequeue_legal != 0:
            print(sk, flows[sk].ooo_enqueue, flows[sk].ooo_dequeue, flows[sk].ooo_dequeue_legal)

def dequeue_ordering(experiment):
    count = 0
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

            if method == "fq_dequeue()":
                if sk in last_dequeue_edt_per_flow:
                    if edt < last_dequeue_edt_per_flow[sk][0]:
                        # print(last_dequeue_edt_per_flow[sk][0], last_dequeue_edt_per_flow[sk][1], l, end="")
                        count += 1
                last_dequeue_edt_per_flow[sk] = (edt, cpu)
    print("out-of-order dequeue:", count)

def analyze_per_cpu(experiment):
    flows = {}
    with open(f"fq.{experiment}.out", "r") as file:    
        lines = file.readlines()
        for l in lines:
            tokens = l.split()
            if len(tokens) < 6:
                continue
            
            ts = tokens[0]
            method = tokens[1]

            if method == "__ip_queue_xmit()":
                sk = tokens[2]
                skb = tokens[3]
                port = tokens[4]
                tcp_gso_segs = tokens[5]
                edt = tokens[6]
                cpu = tokens[7]
                if not sk in flows:
                    flows[sk] = {}

                flows[sk][edt] = (ts, skb, cpu)

            if method == "fq_enqueue()":
                sk = tokens[2]
                skb = tokens[3]
                cpu = tokens[4]
                edt = tokens[5]

                if sk not in flows:
                    continue

                if edt in flows[sk]:
                    if cpu != flows[sk][edt][2]:
                        print(l)
                
            # if method == "fq_dequeue()":
            #     sk = tokens[2]
            #     skb = tokens[3]
            #     cpu = tokens[4]
            #     edt = tokens[5]

            #     if sk not in flows:
            #         continue

            #     if edt in flows[sk]:
            #         if cpu != flows[sk][edt][2]:
            #             print(l)

def check_ih_queuing(experiment):
    flows = {}
    ihq_list = []
    with open(f"fq.{experiment}.out", "r") as file:    
        lines = file.readlines()
        for l in lines:
            tokens = l.split()
            if len(tokens) < 6:
                continue
            
            ts = tokens[0]
            method = tokens[1]

            if method == "__ip_queue_xmit()":
                sk = tokens[2]
                skb = tokens[3]
                port = tokens[4]
                tcp_gso_segs = tokens[5]
                edt = tokens[6]
                cpu = tokens[7]
                if not sk in flows:
                    flows[sk] = {}

                flows[sk][edt] = (ts, skb, cpu)

            if method == "fq_dequeue()":
                sk = tokens[2]
                skb = tokens[3]
                cpu = tokens[4]
                edt = tokens[5]

                if sk not in flows:
                    continue

                if edt in flows[sk]:
                    if int(edt) <= int(ts):
                        ih_queuing = int(ts) - int(edt)
                        # print(ih_queuing, l, end="")
                        ihq_list.append(ih_queuing)
    print(len(ihq_list), np.mean(ihq_list))

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
    ooo_queuing(args.experiment)
    
    # analyze_per_cpu(args.experiment)

    # check_ih_queuing(args.experiment)