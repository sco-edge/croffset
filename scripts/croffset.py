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

        if self.init_ts == None:
            self.init_ts = np.min(self.brtts[:, 0])

    def parse_trtt_trace(self, file):
        trtt_points = []


class IperfStat:
    throughput = None
    retransmissions = None

class NeperStat:
    throughput = None

def parse_trtt_trace(f, flow):
    trtt_points = []
