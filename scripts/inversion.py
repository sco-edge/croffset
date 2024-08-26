#!/usr/bin/python3
import sys
import re

old = []
new = []
expr = re.compile(r".*ice-ens801f0-TxRx-(\d+)$")

# 125264906394744 fq_dequeue() 0xff2086272e754ec0 0xff2085f85ed994e8 53 125264906381982   64424 65588

with open(sys.argv[1]) as file:
    inversion_xmit = 0
    inversion_dequeue = 0
    inversion_dequeue_est = 0
    einversion_dequeue = 0
    einversion_dequeue_est = 0
    last_xmit = {}
    last_dequeue = {}
    lines = file.readlines()
    for line in lines:
        tokens = line.split()
        if len(tokens) < 3:
            continue

        if tokens[2] == "__ip_queue_xmit()":
            sk = tokens[3]
            ts = tokens[6]
            cpu = tokens[1]
            
            if not sk in last_xmit:
                last_xmit[sk] = (ts, cpu)
            else:
                if last_xmit[sk][0] > ts:
                    inversion_xmit += 1
                    # print(last_xmit[sk][1], line, end="")
                    continue
                last_xmit[sk] = (ts, cpu)
            continue

        if tokens[1] == "fq_dequeue()":
            dts = int(tokens[0])
            sk = tokens[2]
            tts = int(tokens[5])            
            cpu = tokens[4]
            skblen = tokens[6]

            if not sk in last_dequeue:
                last_dequeue[sk] = (dts, tts, cpu)
            else:
                if last_dequeue[sk][1] > tts:
                    if dts - last_dequeue[sk][0] > 0:
                        einversion_dequeue += 1
                        einversion_dequeue_est += int((int(skblen) - 116) / 1398)
                    inversion_dequeue += 1
                    inversion_dequeue_est += int((int(skblen) - 116) / 1398)
                    if len(sys.argv) == 2:
                        print(f"G{int((int(skblen) - 116) / 1398)}D{dts - last_dequeue[sk][0]}", line, end="")
                    else:
                        print(f"G{int((int(skblen) - 116) / 1398)}D{dts - last_dequeue[sk][0]}", end=" ")
                    continue
                last_dequeue[sk] = (dts, tts, cpu)
            continue

    # print(einversion_dequeue, einversion_dequeue_est, inversion_dequeue, inversion_dequeue_est, end="")
