#!/usr/bin/python3
import re
import numpy as np

class RetransmissionEvent:
    skb = None
    left = None
    right = None
    loss_event = None

    def __init__(self, skb, left, right):
        self.skb = skb
        self.left = left
        self.right = right

class LossEvent:
    skb = None
    gso_segs = None
    lost_bytes = None
    rack_rtt_us = None
    reo_wnd = None
    waiting = None

    def __init__(self, skb, gso_segs, lost_bytes, rack_rtt_us, reo_wnd, waiting):
        self.skb = skb
        self.gso_segs = gso_segs
        self.lost_bytes = lost_bytes
        self.rack_rtt_us = rack_rtt_us
        self.reo_wnd = reo_wnd
        self.waiting = waiting

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
    losses = None    # Packet loss events
    retrans = None   # Retransmission events
    sretrans = None  # Spurious retransmission events
    dsacks = None    # DSACK events
    astat = None     # Application Statistics
    sk = None        # sk address

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
        loss_points = []
        retrans_points = []
        sr_points = []
        dsack_points = []

        reo_wnd_used = False

        with open(file, 'r') as lines:
            lines.seek(0)
            for l in lines:
                tokens = l.rstrip().split()
                if len(tokens) < 2:
                    continue

                # Top RTT events
                if tokens[1] == "bbr_update_model()":
                    self.parse_bbr_update_model(tokens, trtt_points)
                    continue

                # Packet loss events
                if tokens[1] == "tcp_rack_detect_loss()" or tokens[1] == "tcp_mark_skb_lost()":
                    reo_wnd_used = self.parse_loss_event(tokens, loss_points, reo_wnd_used)
                    continue

                # Transmission events:
                if tokens[1] == "tcp_retransmit_skb()" or tokens[1] == "__tcp_retransmit_skb()":
                    self.parse_tcp_retransmit_skb(tokens, retrans_points)
                    continue

                # DSACK and spurious retransmission events
                if tokens[1] == "tcp_check_dsack()":
                    self.parse_tcp_check_dsack(tokens, sr_points, dsack_points)
                    continue

        if len(trtt_points) == 0:
            print("parse_trtt_trace_bbr() parsing failed.")
            return
        self.trtts = np.array(trtt_points)
        self.losses = np.array(loss_points)
        self.retrans = np.array(retrans_points)
        self.sretrans = np.array(sr_points)
        self.dsacks = np.array(dsack_points)

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

    def parse_bbr_update_model(self, tokens, trtt_points):
        sport = int(tokens[6])
        if self.sport != sport:
            return None

        sk = tokens[2]
        if self.sk == None:
            self.sk = sk

        ts_ns = int(tokens[0])
        delivered = float(tokens[3])
        trtt_us = float(tokens[4])
        if tokens[5] == 1:
            app_limited = True
        else:
            app_limited = False
        
        trtt_points.append((ts_ns, trtt_us))
        return
    
    def parse_loss_event(self, tokens, loss_points, reo_wnd_used):
        ts_ns = int(tokens[0])
        
        if tokens[1] == "tcp_rack_detect_loss()" and tokens[2] == "enter":
            sk = tokens[3]
            if self.sk != sk:
                return
            
            reord_seen = int(tokens[4])
            icsk_ca_state = int(tokens[5])
            sacked_out = int(tokens[6])
            reordering = int(tokens[7])
            reo_wnd_calculated = int(tokens[8])
            eighth_srtt = int(tokens[9])

            # tcp_rack_reo_wnd() logic
            if reord_seen == 0 and (icsk_ca_state >= 3 or sacked_out >= reordering):
                return 0
            
            return min(reo_wnd_calculated, eighth_srtt)
        
        if tokens[1] == "tcp_rack_detect_loss()" and tokens[2] == "exit":
            return None
        
        if tokens[1] == "tcp_mark_skb_lost()":
            sk = tokens[2]
            if self.sk != sk:
                return None
            
            if reo_wnd_used == None:
                return None
            
            skb = tokens[3]
            sport = int(tokens[4])
            gso_segs = int(tokens[5])
            tolerance = int(tokens[6])
            waiting = int(tokens[7])
            drack_seen = tokens[8]
            lost_bytes = int(tokens[9])
            rack_rtt_us = int(tokens[10])
            eighth_srtt = int(tokens[11])
            
            loss_points.append((ts_ns,
                LossEvent(skb, gso_segs, lost_bytes, rack_rtt_us, reo_wnd_used, waiting)))
            print(f"Loss. {skb} {rack_rtt_us + reo_wnd_used} {waiting} {gso_segs}, {lost_bytes}")
            return None

    def parse_tcp_retransmit_skb(self, tokens, retrans_points):
        ts_ns = int(tokens[0])

        if tokens[1] == "tcp_retransmit_skb()":
            sk = tokens[2]
            if self.sk != sk:
                return
            
            skb = tokens[3]
            left = tokens[4]
            right = tokens[5]
            
            retrans_points.append((ts_ns,
                RetransmissionEvent(skb, left, right)))
            # print(f"Retransmit. {skb} {left} {right}")
            return
        
        # Retransmission failed.
        if tokens[1] == "__tcp_retransmit_skb()":
            retrans_points.pop()
            # print(f"Retransmit failed.")
            return            

    def parse_tcp_check_dsack(self, tokens, sr_points, dsack_points):
        ts_ns = int(tokens[0])

        # Last DSACK event is spurious retransmission.
        if tokens[2] == "returns" and tokens[3] == "true":
            if len(dsack_points) == 0:
                return
            last_dsack = dsack_points.pop()
            # print(f"SP true. {last_dsack}")
            sr_points.append((ts_ns, last_dsack[1], last_dsack[2]))
            return
        
        sk = tokens[2]
        if self.sk != sk:
            return
        
        # DSACK event follows network byte order
        left = switch_endian(tokens[3])
        right = switch_endian(tokens[4])
        dsack_points.append((ts_ns, left, right))
        # print(f"Current SP. {dsack_points[-1]}")
        return
    
    def analyze_spurious_retrans(self):
        total_sr_segs = 0
        for (sr_ts_ns, sr_left, sr_right) in self.sretrans:
            found_retrans = None
            for (r_ts_ns, retrans) in self.retrans:
                if retrans.left == sr_left:
                    found_retrans = retrans
                    break
            sr_bytes = int(sr_right, 16) - int(sr_left, 16)
            if found_retrans != None:
                print(sr_ts_ns, sr_left, sr_right, sr_bytes, int(sr_bytes / 1398), found_retrans.skb)
            else:
                print(sr_ts_ns, sr_left, sr_right, sr_bytes, int(sr_bytes / 1398))
            total_sr_segs += sr_bytes / 1398
        print(total_sr_segs)


class IperfStat:
    throughput = None
    retransmissions = None

class NeperStat:
    throughput = None

def switch_endian(hex_string):
    while len(hex_string) < 10:
        hex_string = "0x0" + hex_string[2:]
    switched_hex_string = ''.join(reversed([hex_string[i:i+2] for i in range(2, len(hex_string), 2)]))
    return '0x' + switched_hex_string