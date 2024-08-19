#!/usr/bin/python3
import sys
import re
import random

old = []
new = []
expr = re.compile(r".*ice-ens801f0-TxRx-(\d+)$")

# 125264906394744 fq_dequeue() 0xff2086272e754ec0 0xff2085f85ed994e8 53 125264906381982   64424 65588

# 40482385573279 tcp_mark_skb_lost() 0xff146224d8a308c0 0xff1461f57db70e00 45000 46   179 185 0 64308   169 228 40482385380477

experiment = sys.argv[1]

lost_count = 0
marked_lost = {}
with open(f"../output/{experiment}/sock.{experiment}.out", 'r') as file:
    lines = file.readlines()
    for line in lines:
        tokens = line.split()
        if len(tokens) < 3:
            continue

        if tokens[1] == "tcp_mark_skb_lost()":
            sk = tokens[2]
            ts = int(tokens[12])
            port = int(tokens[4])

            if not port == 45000:
                continue
            
            lost_count += 1
            if not sk in marked_lost:
                marked_lost[sk] = [ts]
            else:
                marked_lost[sk].append(ts)

with open(f"../output/{experiment}/fqd.{experiment}.out", 'r') as file:
    target_ts = {}
    last_dequeue = {}
    inversions = {}
    lines = file.readlines()
    for line in lines:
        tokens = line.split()
        if len(tokens) < 3:
            continue

        if tokens[1] == "fq_dequeue()":
            dts = int(tokens[0])
            sk = tokens[2]
            tts = int(tokens[5])
            cpu = tokens[4]
            skblen = tokens[6]

            if not sk in marked_lost:
                continue

            if not sk in last_dequeue:
                last_dequeue[sk] = (dts, tts, cpu)
            else:
                if last_dequeue[sk][1] > tts:
                    if not sk in inversions:
                        inversions[sk] = [(last_dequeue[sk][0], last_dequeue[sk][1], last_dequeue[sk][2], dts, tts, cpu, int((int(skblen) - 116) / 1398))]
                    else:
                        inversions[sk].append((last_dequeue[sk][0], last_dequeue[sk][1], last_dequeue[sk][2], dts, tts, cpu, int((int(skblen) - 116) / 1398)))
                    target_ts[last_dequeue[sk][1]] = -1
                    target_ts[tts] = -1

                    continue
                last_dequeue[sk] = (dts, tts, cpu)
            continue

with open(f"../output/{experiment}/fqd.{experiment}.out", 'r') as file:
    lines = file.readlines()
    for line in lines:
        tokens = line.split()
        if len(tokens) < 3:
            continue

        if tokens[1] == "fq_enqueue()":
            dts = int(tokens[0])
            sk = tokens[2]
            tts = int(tokens[5])
            cpu = tokens[4]

            if not sk in marked_lost:
                continue

            if tts in target_ts:
                target_ts[tts] = cpu
                continue

# For host flow without any marked lost
if len(marked_lost) == 0:
    with open(f"../output/{experiment}/fqd.{experiment}.out", 'r') as file:
        dequeue = {}
        lines = file.readlines()
        for line in lines:
            tokens = line.split()
            if len(tokens) < 3:
                continue

            if tokens[1] == "fq_dequeue()":
                sk = tokens[2]
                if not sk in dequeue:
                    dequeue[sk] = 0
                else:
                    dequeue[sk] += 1
    
    sk = max(dequeue, key=dequeue.get)
    marked_lost[sk] = [0]

with open(f"../output/{experiment}/fqd.{experiment}.out", 'r') as file:
    random_flag = False
    last_dequeue = {}
    normals = {}
    lines = file.readlines()
    for line in lines:
        if random_flag == False:
            if random.random() < 0.00001:
                random_flag = True
            else:
                continue

        tokens = line.split()
        if len(tokens) < 3:
            continue

        if tokens[1] == "fq_dequeue()":
            dts = int(tokens[0])
            sk = tokens[2]
            tts = int(tokens[5])
            cpu = tokens[4]
            skblen = tokens[6]

            if not sk in marked_lost:
                continue

            if not sk in last_dequeue:
                last_dequeue[sk] = (dts, tts, cpu)
            else:
                if last_dequeue[sk][1] < tts:
                    if not sk in normals:
                        normals[sk] = [last_dequeue[sk][0] - last_dequeue[sk][1] - (dts - tts)]
                    else:
                        normals[sk].append(last_dequeue[sk][0] - last_dequeue[sk][1] - (dts - tts))
                    random_flag = False
                    last_dequeue.pop(sk)
                    continue
                
                last_dequeue.pop(sk)
                random_flag = False
            continue

offsets = []
for sk in marked_lost:
    # Due to the host flows which we artificially inject sk
    if sk in inversions:
        for inv in inversions[sk]:
            send_offset_j = inv[0] - inv[1]
            send_offset_i = inv[3] - inv[4]
            
            if inv[4] in marked_lost[sk]:
                offsets.append((sk, target_ts[inv[1]], inv[2], target_ts[inv[4]], inv[5], send_offset_i - send_offset_j, send_offset_j, send_offset_i, inv[6], True, inv[1], inv[4]))
            # else:
            #     offsets.append((sk, target_ts[inv[1]], inv[2], target_ts[inv[4]], inv[5], send_offset_i - send_offset_j, send_offset_j, send_offset_i, inv[6], False))
    
    for normal in normals[sk]:
        offsets.append((0, 0, 0, 0, 0, normal, 0, 0, 0, False))

# offsets = sorted(offsets, key=lambda offsets: -offsets[5])

for offset in offsets:
    if offset[9] == True:
        # print(f"T{offset[5]} {offset[10]} {offset[11]}", end=" ")
        print(f"T{offset[5]}", end=" ")
    else:
        print(f"F{offset[5]}", end=" ")


print()
# print(lost_count, " ".join(map(str, offsets)), end="")