#!/usr/bin/python3
import re
import numpy as np

class Flow:
    saddr = None
    sport = None
    daddr = None
    dport = None
    transport = None
    init_ts = None   # Initial timestamp
    brtts = None     # Bottom RTTs measured at XDP-TC
    trtts = None     # Top RTTs measured at TCP
    offsets = None   # RTT offsets
    astat = None     # Application Statistics

    def __init__(self, transport, saddr, sport, daddr, dport, app):
        self.transport = transport
        self.saddr = saddr
        self.sport = sport
        self.daddr = daddr
        self.dport = dport

        if app == "iperf":
            self.astat = IperfStat
        elif app == "neper":
            self.astat = NeperStat
        else:
            print(f"flow init error: {app}")
    
    def parse_brtt_trace(self, file):
        brtt_points = []
        expr = re.compile(r"^(\d+?) (.+?) ms (.+?) ms " +
                        f"{self.transport} {self.daddr}:{self.dport}\+{self.saddr}:{self.sport}$")
        with open(file, 'r') as lines:
            lines.seek(0)
            for l in lines:
                match = expr.search(l)
                if match == None:
                    continue
                
                ts_ns = int(match.group(1))
                brtt_us = float(match.group(2)) * 1000
                brtt_points.append((ts_ns, brtt_us))

        self.brtts = np.array(brtt_points)

        brtt_min = np.min(self.brtts[:, 0])
        if self.init_ts == None:
            self.init_ts = brtt_min
        elif brtt_min < self.init_ts:
            self.init_ts = brtt_min

    def parse_trtt_trace_bbr(self, file):
        trtt_points = []
        with open(file, 'r') as lines:
            lines.seek(0)
            for l in lines:
                tokens = l.rstrip().split()
                if len(tokens) < 7:
                    continue

                if tokens[1] == "bbr_update_model()":
                    if self.sport != int(tokens[6]):
                        continue

                    ts_ns = int(tokens[0])
                    sk = tokens[2]
                    delivered = float(tokens[3])
                    trtt_us = float(tokens[4])
                    if tokens[5] == 1:
                        app_limited = True
                    else:
                        app_limited = False
                    trtt_points.append((ts_ns, trtt_us))
        
        self.trtts = np.array(trtt_points)

        trtt_min = np.min(self.trtts[:, 0])
        if self.init_ts == None:
            self.init_ts = trtt_min
        elif trtt_min < self.init_ts:
            self.init_ts = trtt_min

    def generate_offsets(self):
        offset_points = []
        current = 0
        for (trtt_ts_ns, trtt_us) in self.trtts:
            if trtt_ts_ns < self.brtts[current][0]:
                # print(trtt_ts_ns, "Case 2", None)
                # offset_points.append((trtt_ts_ns, None))
                continue

            while True:
                if current + 1 >= len(self.brtts):
                    break
                if trtt_ts_ns >= self.brtts[current][0] and \
                    trtt_ts_ns < self.brtts[current + 1][0]:
                    break
                current += 1

            # If brtt reaches the last element
            if current + 1 >= len(self.brtts):
                # print(trtt_ts_ns, "Case 1", None)
                # offset_points.append((trtt_ts_ns, None))

                # if trtt_ts_ns >= self.brtts[current][0]:
                #     print(trtt_ts_ns, "Case 0", trtt_us, self.brtts[current][1], trtt_us - self.brtts[current][1])
                #     offset_points.append((trtt_ts_ns, trtt_us - self.brtts[current][1]))
                # else:
                #     print(trtt_ts_ns, "Case 1", None)
                #     offset_points.append((trtt_ts_ns, None))
                continue
            else:
                # print(trtt_ts_ns, "Case 3", trtt_us, self.brtts[current][1], trtt_us - self.brtts[current][1])
                offset_points.append((trtt_ts_ns, trtt_us - self.brtts[current][1]))

        self.offsets = np.array(offset_points)

class IperfStat:
    throughput = None
    retransmissions = None

class NeperStat:
    throughput = None
