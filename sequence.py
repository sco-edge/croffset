#!/usr/bin/python3
import argparse
import os
import numpy as np

class QueueingInfo:
    skb = None
    edt = None
    ts = None
    cpu = None
    is_dequeue = None
    is_ooo = False

    def __init__(self, skb, edt, ts, cpu, is_dequeue):
        self.skb = skb
        self.edt = edt
        self.ts = ts
        self.cpu = cpu
        self.is_dequeue = is_dequeue

    def mark_ooo(self):
        self.is_ooo = True

class QueueLog:
    queue = {}

    def length(self):
        return len(self.queue)
    
    def enqueue(self, item):
        self.queue[item.edt] = item
    
    def dequeue(self, item):
        if not item.is_ooo:
            self.queue.pop(item.edt)
            return -1
        
        if item.edt == min(self.queue, key=lambda x: self.queue[x].edt):
            self.queue.pop(item.edt)
            return 0
        else:
            urgent_items = list(filter(lambda x: self.queue[x].edt <= item.ts and self.queue[x].edt < item.edt, self.queue))
            self.queue.pop(item.edt)
            return len(urgent_items)
        
def ooo_queuing(experiment):
    enqueued_per_flow = {}
    qi_per_flow = {}
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
            if not sk in enqueued_per_flow:
                enqueued_per_flow[sk] = {}

            if method == "fq_enqueue()":
                if sk in enqueued_per_flow:
                    enqueued = enqueued_per_flow[sk]
                    enqueued[edt] = (skb, ts, cpu)

            if method == "fq_dequeue()":
                if sk in enqueued_per_flow:
                    enqueued = enqueued_per_flow[sk]
                    if edt in enqueued:
                        (skb, enqueue, enqueue_cpu) = enqueued[edt]
                        enqueue_qi = QueueingInfo(skb, edt, enqueue, enqueue_cpu, False)
                        dequeue_qi = QueueingInfo(skb, edt, ts, cpu, True)

                        if sk in qi_per_flow:
                            qi_per_flow[sk].append(enqueue_qi)
                            qi_per_flow[sk].append(dequeue_qi)
                        else:
                            qi_per_flow[sk] = [enqueue_qi, dequeue_qi]
                    # else:
                    #     print("Not enqueued but dequeued:", l)

    for sk in qi_per_flow:
        if len(qi_per_flow[sk]) < 1000:
            continue
        qi_per_flow[sk] = sorted(qi_per_flow[sk], key=lambda x: x.ts)
        ooo = 0
        looo = 0

        last_dequeue = None
        for qi in qi_per_flow[sk]:
            if not qi.is_dequeue:
                continue

            if last_dequeue == None:
                last_dequeue = qi
                continue

            if last_dequeue.edt > qi.edt:
                last_dequeue.mark_ooo()

            last_dequeue = qi

        ql = QueueLog()
        for qi in qi_per_flow[sk]:
            if not qi.is_dequeue:
                ql.enqueue(qi)
                # print(f"E {qi.ts} {qi.skb} {qi.edt} {qi.cpu} {ql.length()}")
            else:
                res = ql.dequeue(qi)
                if res >= 0:
                    ooo += 1
                    if res == 0:
                        looo += 1
                        print(f"D {qi.ts} {qi.skb} {qi.edt} {qi.cpu} {ql.length()} R{res}")
                # else:
                #     print(f"D {qi.ts} {qi.skb} {qi.edt} {qi.cpu} {ql.length()}")

        print(f"{sk} Len: {len(qi_per_flow[sk])} Legal-OOO: {looo} Illegal-OOO: {ooo - looo}")

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
                        print(last_dequeue_edt_per_flow[sk][0], last_dequeue_edt_per_flow[sk][1], l, end="")
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

def check_lateness(experiment):
    enqueue_count = 0
    dequeue_count = 0
    enqueue_lateness = []
    dequeue_lateness = []
    with open(f"fq.{experiment}.out", "r") as file:    
        lines = file.readlines()
        for l in lines:
            tokens = l.split()
            if len(tokens) < 6:
                continue
            
            ts = int(tokens[0])
            method = tokens[1]
            if method == "__ip_queue_xmit()":
                continue
            
            sk = tokens[2]
            skb = tokens[3]
            cpu = tokens[4]
            edt = int(tokens[5])

            if method == "fq_enqueue()":
                enqueue_count += 1
            elif method == "fq_dequeue()":
                dequeue_count += 1

            if ts > edt:
                if abs(ts - edt) > 100000:
                    continue
                # print(f"{method}: {edt - ts}")
                if method == "fq_enqueue()":
                    enqueue_lateness.append(edt - ts)
                elif method == "fq_dequeue()":
                    dequeue_lateness.append(edt - ts)

    print(f"enqueue: {enqueue_count} lateness: {len(enqueue_lateness)} {len(enqueue_lateness) / enqueue_count * 100 :.2f} {np.mean(enqueue_lateness):.0f}")
    print(f"dequeue: {dequeue_count} lateness: {len(dequeue_lateness)} {len(dequeue_lateness) / dequeue_count * 100 :.2f} {np.mean(dequeue_lateness):.0f}")

def check_lateness_track(experiment):
    enqueue_count = 0
    enqueue_lateness = []
    with open(f"track.{experiment}.out", "r") as file:    
        lines = file.readlines()
        for l in lines:
            tokens = l.split()
            if len(tokens) < 6:
                continue
            
            ts = int(tokens[0])
            cpu = int(tokens[1])
            method = tokens[2]

            if not method == "fq_enqueue()":
                continue
            
            enqueue_count += 1
            sk = tokens[3]
            skb = tokens[4]
            cpu = tokens[5]
            edt = int(tokens[6])

            if ts > edt:
                if abs(ts - edt) > 100000:
                    continue
                enqueue_lateness.append(edt - ts)
                print(l)

    print(f"enqueue: {enqueue_count} lateness: {len(enqueue_lateness)} {len(enqueue_lateness) / enqueue_count * 100 :.2f} {np.mean(enqueue_lateness):.0f}")


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
    # ooo_queuing(args.experiment)
    
    # dequeue_ordering(args.experiment)

    # analyze_per_cpu(args.experiment)

    # check_ih_queuing(args.experiment)

    check_lateness_track(args.experiment)
