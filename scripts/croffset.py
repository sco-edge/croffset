#!/usr/bin/python3
import copy
import re
import numpy as np

mss = 1398

class Segment:
    left = None
    right = None
    seglen = None
    bytelen = None

    def __init__(self, left, right):
        self.left = left
        self.right = right
        self.bytelen = int(right, 16) - int(left, 16)
        self.seglen = int(self.bytelen / mss)

class RetransmissionEvent:
    skb = None
    segment = None
    segavail = None
    loss_event = None
    segsent = None

    def __init__(self, skb, left, right, segavail, segs):
        self.skb = skb
        self.segment = Segment(left, right)
        self.segavail = segavail
        self.segsent = min(segs, segavail)

class LossEvent:
    ts_ns = None # To distinguish the same skbs
    skb = None
    gso_segs = None
    lost_bytes = None
    rack_rtt_us = None
    reo_wnd = None
    waiting = None
    seg_left = None
    seg_right = None

    def __init__(self, ts_ns, skb, gso_segs, lost_bytes, rack_rtt_us, reo_wnd, waiting):
        self.ts_ns = ts_ns
        self.skb = skb
        self.gso_segs = gso_segs
        self.lost_bytes = lost_bytes
        self.rack_rtt_us = rack_rtt_us
        self.reo_wnd = reo_wnd
        self.waiting = waiting

class IperfStat:
    throughput = None
    retransmissions = None

class NeperStat:
    throughput = None

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

    def parse_trtt_trace_bbr(self, file):
        trtt_points = []

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

        if len(trtt_points) == 0:
            print("parse_trtt_trace_bbr() parsing failed.")
            return 0
        
        self.trtts = np.array(trtt_points)
        self.init_ts = int(min(np.min(self.trtts[:, 0]), np.min(self.brtts[:, 0])))

        # Regularize to init_ts
        self.brtts = np.array([(i[0] - self.init_ts, i[1]) for i in self.brtts])
        self.trtts = np.array([(i[0] - self.init_ts, i[1]) for i in self.trtts])

    def parse_sock_trace(self, file):
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

                # Packet loss events
                if tokens[1] == "tcp_rack_detect_loss()" or tokens[1] == "tcp_mark_skb_lost()":
                    reo_wnd_used = self.parse_loss_event(tokens, loss_points, reo_wnd_used)
                    continue

                # Transmission events
                if tokens[1] == "tcp_retransmit_skb()" or tokens[1] == "__tcp_retransmit_skb()":
                    self.parse_tcp_retransmit_skb(tokens, retrans_points)
                    continue

                # DSACK and spurious retransmission events
                if tokens[1] == "tcp_check_dsack()":
                    self.parse_tcp_check_dsack(tokens, sr_points, dsack_points)
                    continue

        self.losses = np.array([(i[0] - self.init_ts, i[1]) for i in loss_points])
        self.retrans = np.array([(i[0] - self.init_ts, i[1]) for i in retrans_points])
        self.sretrans = np.array([(i[0] - self.init_ts, i[1]) for i in sr_points])
        self.dsacks = np.array([(i[0] - self.init_ts, i[1]) for i in dsack_points])

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
                return reo_wnd_used
            
            if reo_wnd_used == None:
                return reo_wnd_used
            
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
                LossEvent((ts_ns - self.init_ts), skb, gso_segs, lost_bytes, rack_rtt_us, reo_wnd_used, waiting)))
            # print(f"Loss. {ts_ns} {skb} {rack_rtt_us + reo_wnd_used} {waiting} {gso_segs}, {lost_bytes}")
            return reo_wnd_used

    def parse_tcp_retransmit_skb(self, tokens, retrans_points):
        ts_ns = int(tokens[0])

        if tokens[1] == "tcp_retransmit_skb()":
            sk = tokens[2]
            if self.sk != sk:
                return
            
            skb = tokens[3]
            left = padded_hex(int(tokens[4], 16))
            right = padded_hex(int(tokens[5], 16))
            segavail = int(tokens[7])
            segs = int(tokens[8])
            
            retrans_points.append((ts_ns,
                RetransmissionEvent(skb, left, right, segavail, segs)))
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
            (_, last_dsack) = dsack_points.pop()
            # print(f"SP true. {last_dsack}")
            sr_points.append((ts_ns, last_dsack))
            return
        
        sk = tokens[2]
        if self.sk != sk:
            return
        
        # DSACK event follows network byte order
        left = switch_endian(tokens[3])
        right = switch_endian(tokens[4])
        dsack_points.append((ts_ns, Segment(left, right)))
        # print(f"Current SP. {dsack_points[-1]}")
        return
    
    def analyze_spurious_retrans(self):
        # skb is not an unique identifier.
        loss_map = {}
        for (loss_ts_ns, loss) in self.losses:
            print(f"Loss. {loss_ts_ns + self.init_ts:<14} {loss_ts_ns / 1_000_000_000:<11} {loss.skb} {loss.gso_segs} {loss.lost_bytes} {loss.rack_rtt_us} {loss.reo_wnd} {loss.waiting} {loss}")
            if loss_map.get(loss.skb) == None:
                loss_map[loss.skb] = [loss]
            else:
                loss_map[loss.skb].append(loss)
        for (retrans_ts_ns, retrans) in self.retrans:
            print(f"Retx. {retrans_ts_ns + self.init_ts:<14} {retrans_ts_ns / 1_000_000_000:<11} {retrans.skb} {retrans.segment.left} {retrans.segment.right} {retrans.segment.bytelen} {retrans.segment.seglen} {retrans.segsent}")

        print("")
        for key in loss_map.keys():
            losses = " ".join(str(loss.ts_ns) for loss in loss_map[key])
            print(key, losses)
        print("")
        partial_segments = []

        # Map retransmissions to loss events
        for (r_ts_ns, retrans) in self.retrans:
            print(f"Retx. {r_ts_ns + self.init_ts:<14} {r_ts_ns / 1_000_000_000:<11} {retrans.skb} {retrans.segment.left} {retrans.segment.right}",
                  f"{retrans.segment.bytelen} {retrans.segment.seglen} {retrans.segsent}", end=" ", flush=True)
            candidate_losses = loss_map.get(retrans.skb)
            if candidate_losses != None and len(candidate_losses) != 0:
                # print([f"{candidate_loss.ts_ns / 1_000_000_000:<11}" for candidate_loss in candidate_losses])
                earlier_losses = [candidate for candidate in candidate_losses if candidate.ts_ns <= r_ts_ns]
                
                if len(earlier_losses) != 0:
                    loss = min(earlier_losses, key=lambda x: x.ts_ns)
                    if retrans.segsent == loss.gso_segs:
                        loss.seg_left = retrans.segment.left
                        loss.seg_right = retrans.segment.right
                        retrans.loss_event = loss
                        print(f"Full Matched. {retrans.loss_event.skb} {loss}", flush=True)
                        candidate_losses.remove(loss)
                        continue
                    else:
                        new_left = padded_hex(int(retrans.segment.left, 16) + retrans.segsent * mss)
                        new_segment = Segment(new_left, retrans.segment.right)
                        partial_segments.append((new_segment, loss, loss.gso_segs - retrans.segsent))
                        retrans.loss_event = loss
                        loss.seg_left = retrans.segment.left
                        loss.seg_right = new_segment.right
                        print(f"Head Matched. {retrans.loss_event.skb} remained={loss.gso_segs - retrans.segsent}, new_left={new_left}", flush=True)
                        continue
            
            for (partial_segment, new_loss, segremained) in partial_segments:
                # This partial segment is already taken
                if segremained == 0:
                    continue

                if retrans.segment.right == partial_segment.right and \
                    retrans.segment.left == partial_segment.left:
                    if retrans.segsent == segremained:
                        retrans.loss_event = new_loss
                        new_loss.seg_right = retrans.segment.right
                        print(f"Tail Matched. {retrans.loss_event.skb}", flush=True)
                        candidate_losses = loss_map.get(new_loss.skb)
                        # print(retrans.skb, [f"{candidate_loss.ts_ns / 1_000_000_000:<11}" for candidate_loss in candidate_losses])
                        # print(new_loss.ts_ns)
                        candidate_losses.remove(new_loss)
                        partial_segments.remove((partial_segment, new_loss, segremained))
                        break
                    else:
                        new_left = padded_hex(int(retrans.segment.left, 16) + retrans.segsent * mss)
                        new_segment = Segment(new_left, retrans.segment.right)
                        partial_segments.append((new_segment, new_loss, segremained - retrans.segsent))
                        retrans.loss_event = new_loss
                        new_loss.seg_right = new_segment.right
                        print(f"Cont Matched. {retrans.loss_event.skb} remained={segremained - retrans.segsent}", flush=True)
                        segremained = 0
                        break

        for (loss_ts_ns, loss) in self.losses:
            print(f"Loss. {loss_ts_ns + self.init_ts:<14} {loss_ts_ns / 1_000_000_000:<11} {loss.skb} {loss.gso_segs}",
                  f"{loss.lost_bytes} {loss.rack_rtt_us} {loss.reo_wnd} {loss.waiting}",
                  f"{loss.seg_left} {loss.seg_right} {loss}")

        for (sr_ts_ns, segment) in self.sretrans:
            (found_loss_ts_ns, found_loss) = (None, None)
            for (loss_ts_ns, loss) in self.losses:
                # If these values are None, the segments are once marked lost
                # but acked before they are actually retransmitted (mainly due
                # to the retransmissions are deferred)
                if loss.seg_left == None or loss.seg_right == None:
                    continue

                if loss.seg_left <= segment.left and loss.seg_right >= segment.right:
                    found_loss = loss
                    found_loss_ts_ns = loss_ts_ns
                    break
            sr_bytes = int(segment.right, 16) - int(segment.left, 16)
            if found_loss != None:
                print(f"Srtx. {sr_ts_ns + self.init_ts:<14} {sr_ts_ns / 1_000_000_000:<11} {segment.left} {segment.right} {sr_bytes:>5} {int(sr_bytes / mss):>2} {found_loss.skb} {found_loss.rack_rtt_us} {found_loss.reo_wnd} {found_loss.waiting} {int((sr_ts_ns - found_loss_ts_ns) / 1_000)}")
            else:
                print(f"Srtx. {sr_ts_ns + self.init_ts:<14} {sr_ts_ns / 1_000_000_000:<11} {segment.left} {segment.right} {sr_bytes:>5} {int(sr_bytes / mss):>2}")

def switch_endian(hex_string):
    while len(hex_string) < 10:
        hex_string = "0x0" + hex_string[2:]
    switched_hex_string = ''.join(reversed([hex_string[i:i+2] for i in range(2, len(hex_string), 2)]))
    return "0x" + switched_hex_string

def padded_hex(num):
    hex_string = hex(num)
    while len(hex_string) < 10:
        hex_string = "0x0" + hex_string[2:]
    return hex_string
