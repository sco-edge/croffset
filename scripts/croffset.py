#!/usr/bin/python3
import copy
import re
import numpy as np

mss = 1398

class RoundTripTimestamps:
    # All timestamps are stored in ns unit regularized at init_ts
    tcp_send = None
    tcp_recv = None
    tc_egress = None
    xdp_ingress = None
    fq_enqueue = None
    fq_dequeue = None

    # All RTTs are stored in us unit
    top_rtt = None
    bottom_rtt = None
    offset_send = None
    offset_recv = None
    offset = None
    tc_fq = None
    fq = None    

    def __init__(self, init_ts, tcp_send, tcp_recv, tc_egress, xdp_ingress, fq_enqueue, fq_dequeue):
        self.tcp_send = tcp_send - init_ts
        self.tcp_recv = tcp_recv - init_ts
        self.tc_egress = tc_egress - init_ts
        self.xdp_ingress = xdp_ingress - init_ts
        self.fq_enqueue = fq_enqueue - init_ts
        self.fq_dequeue = fq_dequeue - init_ts

        self.top_rtt = (tcp_recv - tcp_send) / 1000
        self.bottom_rtt = (xdp_ingress - fq_dequeue) / 1000
        self.offset_send = (fq_dequeue - tcp_send) / 1000
        self.offset_recv = (tcp_recv - xdp_ingress) / 1000
        self.offset = (self.offset_send + self.offset_recv)
        self.tc_fq = (fq_enqueue - tc_egress) / 1000
        self.fq = (fq_dequeue - fq_enqueue) / 1000

        # Offsets exceeding 10 ms mean something wrong
        # probably due to the last truncated timestamps
        if abs(self.offset_send) > 10_000 or abs(self.offset_recv) > 10_000:
            raise ValueError("Some timestamps might be wrong")

class MeasuredRTT:
    ts = None
    sent_ts = None
    acked_ts = None
    rtt = None

    def __init__(self, ts, sent_ts, acked_ts):
        self.ts = ts
        self.sent_ts = sent_ts
        self.acked_ts = acked_ts
        self.rtt = (acked_ts - sent_ts) / 1000

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
    ts = None # To distinguish the same skbs
    skb = None
    gso_segs = None
    lost_bytes = None
    rack_rtt_us = None
    reo_wnd = None
    waiting = None
    seg_left = None
    seg_right = None

    def __init__(self, ts, skb, gso_segs, lost_bytes, rack_rtt_us, reo_wnd, waiting):
        self.ts = ts
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
    marked_brtts = None
    marked_trtts = None
    synced_offsets = None
    brtts = None     # Bottom RTTs measured at XDP-TC
    trtts = None     # Top RTTs measured at TCP
    rrtts = None     # RTTs measured at RACK
    offsets = None   # RTT offsets (trtt - brtt)
    offsets2 = None  # RTT offsets (rrtt - brtt)
    offsets3 = None  # RTT offsets (rrtt - trtt)
    losses = None    # Packet loss events
    delivered = None # Delivered events
    retrans = None   # Retransmission events
    sretrans = None  # Spurious retransmission events
    dsacks = None    # DSACK events
    astat = None     # Application Statistics
    sk = None        # sk address
    queuing = None   # Sending

    def __init__(self, transport, saddr, sport, daddr, dport, app):
        self.transport = transport
        self.saddr = saddr
        self.sport = sport
        self.daddr = daddr
        self.dport = dport

        self.marked_brtts = {}
        self.marked_trtts = {}
        self.synced_offsets = []

        self.queuing = {}

        if app == "iperf":
            self.astat = IperfStat
        elif app == "neper":
            self.astat = NeperStat
        else:
            print(f"flow init error: {app}")
    
    def parse_brtt_trace(self, file):
        brtt_points = []
        expr = re.compile(r"^(\d+?) (.+?) ms (.+?) ms " +
                        f"{self.transport} {self.daddr}:{self.dport}\+{self.saddr}:{self.sport} (.+?) (.+?) (.+?)$")
        with open(file, 'r') as lines:
            lines.seek(0)
            for l in lines:
                match = expr.search(l)
                if match == None:
                    continue
                
                ts = int(match.group(1))
                brtt_us = float(match.group(2)) * 1000
                mark = padded_hex(int(match.group(4), 16), 8)
                start_ts = int(match.group(5))
                end_ts = int(match.group(6))
                measured_rtt = MeasuredRTT(ts, start_ts, end_ts)
                self.marked_brtts[mark] = measured_rtt
                brtt_points.append((ts, brtt_us))

        if len(brtt_points) == 0:
            print("parse_brtt_trace() parsing failed.")
            return 0
        
        self.brtts = np.array(brtt_points)
        return len(self.brtts)

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
        return len(self.trtts)
    
    # Temporary
    def parse_trtt_trace_cubic(self, file):
        self.init_ts = int(np.min(self.brtts[:, 0]))

        # Regularize to init_ts
        self.brtts = np.array([(i[0] - self.init_ts, i[1]) for i in self.brtts])
        return self.init_ts

    def parse_rrtt_trace(self, file):
        rrtt_points = []

        with open(file, 'r') as lines:
            lines.seek(0)
            for l in lines:
                tokens = l.rstrip().split()
                if len(tokens) < 2:
                    continue

                # Top RTT events
                if tokens[1] == "tcp_rack_advance()":
                    self.parse_tcp_rack_advance(tokens, rrtt_points)
                    continue

        if len(rrtt_points) == 0:
            print("parse_rrtt_trace() parsing failed.")
            return 0
        
        self.rrtts = np.array(rrtt_points)

        # Regularize to init_ts
        self.rrtts = np.array([(i[0] - self.init_ts, i[1], i[2]) for i in self.rrtts])
        return len(self.rrtts)

    def parse_marked_trtt_trace(self, file):
        rrtt_points = []

        with open(file, 'r') as lines:
            lines.seek(0)
            current_mark = None
            for l in lines:
                tokens = l.rstrip().split()
                if len(tokens) < 2:
                    continue

                if tokens[1] == "tcp_ack()":
                    current_mark = padded_hex(int(tokens[3], 16), 8)
                    # print("current_mark:", current_mark)

                # Top RTT events
                if tokens[1] == "tcp_rack_advance()":
                    self.parse_tcp_rack_advance(tokens, rrtt_points, current_mark)
                    continue

        if len(rrtt_points) == 0:
            print("parse_rrtt_trace() parsing failed.")
            return 0
        
        self.rrtts = np.array(rrtt_points)

        # Regularize to init_ts
        self.rrtts = np.array([(i[0] - self.init_ts, i[1], i[2]) for i in self.rrtts])
        return len(self.rrtts)

    def parse_sock_trace(self, file):
        loss_points = []
        retrans_points = []
        sr_points = []
        dsack_points = []
        delivered_points = []

        reo_wnd_used = False
        is_valid = False

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
                    self.parse_tcp_retransmit_skb(tokens, retrans_points, is_valid)
                    continue

                # DSACK and spurious retransmission events
                if tokens[1] == "tcp_check_dsack()":
                    self.parse_tcp_check_dsack(tokens, sr_points, dsack_points)
                    continue

                # Delivered events:
                if tokens[1] == "tcp_rate_skb_delivered()":
                    self.parse_tcp_rate_skb_delivered(tokens, delivered_points)
                    continue

        self.losses = np.array([(i[0] - self.init_ts, i[1]) for i in loss_points])
        self.retrans = np.array([(i[0] - self.init_ts, i[1]) for i in retrans_points])
        self.delivered = np.array([(i[0] - self.init_ts, i[1]) for i in delivered_points])
        self.sretrans = np.array([(i[0] - self.init_ts, i[1]) for i in sr_points])
        self.dsacks = np.array([(i[0] - self.init_ts, i[1]) for i in dsack_points])

    def parse_fq_delay_trace(self, file):
        queued_packets = {}
        with open(file, 'r') as lines:
            lines.seek(0)
            for l in lines:
                tokens = l.rstrip().split()

                if len(tokens) < 2:
                    continue

                # FQ enqueue events
                if tokens[1] == "fq_enqueue()":
                    sk = padded_hex(int(tokens[2], 16), 16)
                    if sk != self.sk:
                        continue

                    ts = int(tokens[0])
                    skb = padded_hex(int(tokens[3], 16), 16)
                    skb_mstamp_ns = int(tokens[4])
                    queued_packets[skb] = (ts, skb_mstamp_ns)
                    continue

                # FQ dequeue events
                if tokens[1] == "fq_dequeue()":
                    sk = padded_hex(int(tokens[2], 16), 16)
                    if sk != self.sk:
                        continue

                    ts = int(tokens[0])
                    skb = padded_hex(int(tokens[3], 16), 16)
                    skb_mstamp_ns = int(tokens[4])

                    if skb in queued_packets:
                        (enqueue_ts, enqueue_skb_mstamp_us) = queued_packets.pop(skb)
                        
                        # div_u64() in the kernel seems to truncate the decimal point
                        skb_mstamp_us = int(skb_mstamp_ns / 1_000)

                        # skb_mstamp_us works as an identifier for sk_buff
                        if skb_mstamp_us in self.queuing:
                            existing_value = self.queuing.pop(skb_mstamp_us)
                            if isinstance(existing_value, list):
                                existing_value.append((enqueue_ts, ts))
                                self.queuing[skb_mstamp_us] = existing_value
                            else:
                                self.queuing[skb_mstamp_us] = list((existing_value, (enqueue_ts, ts)))
                        else:
                            self.queuing[skb_mstamp_us] = (enqueue_ts, ts)
                    continue

    def generate_synced_offsets(self, output):
        with open(output, 'w') as file:
            for mark in self.marked_brtts:
                if mark not in self.marked_trtts:
                    continue

                trtts_at_current_mark = self.marked_trtts.get(mark)
                for trtt_rack in trtts_at_current_mark:
                    ts = trtt_rack.ts
                    sent_ts_us = int(trtt_rack.sent_ts / 1000)

                    # To address bpf_get_prandom_u32() conflicts
                    # If the difference between brtt and trtt timestamps >= 1 ms
                    if abs(ts - self.marked_brtts[mark].ts) >= 10_000_000:
                        continue

                    if not int(sent_ts_us) in self.queuing:
                        continue

                    if isinstance(self.queuing[sent_ts_us], list):
                        (fq_enqueue, fq_dequeue) = self.queuing[sent_ts_us].pop(0)
                        if len(self.queuing[sent_ts_us]) == 0:
                            self.queuing.pop(sent_ts_us)
                    else:
                        (fq_enqueue, fq_dequeue) = self.queuing.pop(sent_ts_us)
                    try:
                        t = RoundTripTimestamps(self.init_ts, trtt_rack.sent_ts, trtt_rack.acked_ts, \
                            self.marked_brtts[mark].sent_ts, self.marked_brtts[mark].acked_ts, \
                            fq_enqueue, fq_dequeue)
                        self.synced_offsets.append(t)
                        line = f"{t.tcp_recv + self.init_ts:>15.0f} {t.tcp_recv:>11.0f} {mark}   " + \
                               f"{t.tcp_send:>11.0f} {t.fq_dequeue:>11.0f} {t.offset_send:>8.3f}   " + \
                               f"{t.xdp_ingress:>11.0f} {t.tcp_recv:>11.0f} {t.offset_recv:>8.3f}   " + \
                               f"{t.offset:>8.3f} {t.tc_fq:>8.3f} {t.fq:>8.3f}"
                        file.write(line + '\n')
                    except ValueError:
                        pass
                    
                    # offset = trtt_rack.rtt - self.marked_brtts[mark].rtt
                    # send_offset = self.marked_brtts[mark].sent - trtt_rack.sent
                    # recv_offset = trtt_rack.acked - self.marked_brtts[mark].acked

                    # # Some data is truncated at end
                    # if abs(send_offset) > 1000 or abs(recv_offset) > 1000:
                    #     continue

                    # self.synced_offsets.append((ts - self.init_ts, offset, send_offset, recv_offset))
                
        self.synced_offsets = np.array(self.synced_offsets)
        print(f"tot offset avg: {np.mean([t.offset for t in self.synced_offsets]):.3f} std: {np.std([t.offset for t in self.synced_offsets]):.3f}")
        print(f"snd offset avg: {np.mean([t.offset_send for t in self.synced_offsets]):.3f} std: {np.std([t.offset_send for t in self.synced_offsets]):.3f}")
        print(f"rcv offset avg: {np.mean([t.offset_recv for t in self.synced_offsets]):.3f} std: {np.std([t.offset_recv for t in self.synced_offsets]):.3f}")
        print(f"tcfq delay avg: {np.mean([t.tc_fq for t in self.synced_offsets]):.3f} std: {np.std([t.tc_fq for t in self.synced_offsets]):.3f}")
        print(f"fq queuing avg: {np.mean([t.fq for t in self.synced_offsets]):.3f} std: {np.std([t.fq for t in self.synced_offsets]):.3f}")

        # print(f"tot offset avg: {np.mean(self.synced_offsets[:, 1]):.3f} std: {np.std(self.synced_offsets[:, 1]):.3f}")
        # print(f"snd offset avg: {np.mean(self.synced_offsets[:, 2]):.3f} std: {np.std(self.synced_offsets[:, 2]):.3f}")
        # print(f"rcv offset avg: {np.mean(self.synced_offsets[:, 3]):.3f} std: {np.std(self.synced_offsets[:, 3]):.3f}")

    def generate_offsets(self):
        offset_points = []
        current = 0
        for (trtt_ts, trtt_us) in self.trtts:
            if trtt_ts < self.brtts[current][0]:
                # print(trtt_ts, "Case 2", None)
                # offset_points.append((trtt_ts, None))
                continue

            while True:
                if current + 1 >= len(self.brtts):
                    break
                if trtt_ts >= self.brtts[current][0] and \
                    trtt_ts < self.brtts[current + 1][0]:
                    break
                current += 1

            # If brtt reaches the last element
            if current + 1 >= len(self.brtts):
                # print(trtt_ts, "Case 1", None)
                # offset_points.append((trtt_ts, None))

                # if trtt_ts >= self.brtts[current][0]:
                #     print(trtt_ts, "Case 0", trtt_us, self.brtts[current][1], trtt_us - self.brtts[current][1])
                #     offset_points.append((trtt_ts, trtt_us - self.brtts[current][1]))
                # else:
                #     print(trtt_ts, "Case 1", None)
                #     offset_points.append((trtt_ts, None))
                continue
            else:
                # print(trtt_ts, "Case 3", trtt_us, self.brtts[current][1], trtt_us - self.brtts[current][1])
                
                # ** CAUTION **
                # This commented code tries to sample only the diffs between trtt and brtt timestamp are bounded
                # But it does not work.
                #
                # if trtt_ts - self.brtts[current][0] < 20000:
                #     print(f"{trtt_ts} {self.brtts[current][0]} {trtt_ts - self.brtts[current][0]}",
                #           f"{trtt_us} {self.brtts[current][1]} {trtt_us - self.brtts[current][1]}")
                #     offset_points.append((trtt_ts, trtt_us - self.brtts[current][1]))

                offset_points.append((trtt_ts, trtt_us - self.brtts[current][1]))

        self.offsets = np.array(offset_points)

    def generate_offsets2(self):
        offset_points = []
        current = 0
        for (rrtt_ts, rrtt_us, rrtt_min) in self.rrtts:
            if rrtt_ts < self.brtts[current][0]:
                continue

            while True:
                if current + 1 >= len(self.brtts):
                    break
                if rrtt_ts >= self.brtts[current][0] and \
                    rrtt_ts < self.brtts[current + 1][0]:
                    break
                current += 1

            # If brtt reaches the last element
            if current + 1 >= len(self.brtts):
                continue
            else:
                offset_points.append((rrtt_ts, rrtt_us - self.brtts[current][1]))

        self.offsets2 = np.array(offset_points)

    def generate_offsets3(self):
        offset_points = []
        current = 0
        for (rrtt_ts, rrtt_us, rrtt_min) in self.rrtts:
            if rrtt_ts < self.trtts[current][0]:
                continue

            while True:
                if current + 1 >= len(self.trtts):
                    break
                if rrtt_ts >= self.trtts[current][0] and \
                    rrtt_ts < self.trtts[current + 1][0]:
                    break
                current += 1

            # If brtt reaches the last element
            if current + 1 >= len(self.trtts):
                continue
            else:
                offset_points.append((rrtt_ts, rrtt_us - self.trtts[current][1]))

        self.offsets3 = np.array(offset_points)

    def parse_bbr_update_model(self, tokens, trtt_points):
        sport = int(tokens[6])
        if self.sport != sport:
            return None

        sk = tokens[2]
        if self.sk == None:
            self.sk = sk

        ts = int(tokens[0])
        delivered = float(tokens[3])
        trtt_us = float(tokens[4])
        if tokens[5] == 1:
            app_limited = True
        else:
            app_limited = False
        
        trtt_points.append((ts, trtt_us))
        return
    
    def parse_tcp_rack_advance(self, tokens, rrtt_points, current_mark):
        sport = int(tokens[2])
        if self.sport != sport:
            return None

        ts = int(tokens[0])
        rtt_us = int(tokens[5])
        tcp_min_rtt_us = int(tokens[6])
        rack_mstamp_ns = int(tokens[7]) * 1000
        xmit_time_ns = int(tokens[8]) * 1000
        tcp_mstamp_ns = int(tokens[9]) * 1000

        if rtt_us < tcp_min_rtt_us:
            return None
        # if rtt_us < tcp_min_rtt_us * 3:
        #     print(f"{ts} tcp_rack_advance() {sport} {rtt_us} {tcp_min_rtt_us}")
        
        measured_rtt = MeasuredRTT(ts, xmit_time_ns, tcp_mstamp_ns)

        # Mark-based TRTT
        if current_mark in self.marked_trtts:
            trtts_at_current_mark = self.marked_trtts[current_mark]
            trtts_at_current_mark.append(measured_rtt)
        else:
            trtts_at_current_mark = [measured_rtt]
            self.marked_trtts[current_mark] = trtts_at_current_mark

        rrtt_points.append((ts, rtt_us, tcp_min_rtt_us))
        return

    def parse_loss_event(self, tokens, loss_points, reo_wnd_used):
        ts = int(tokens[0])
        
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
            
            loss_points.append((ts,
                LossEvent((ts - self.init_ts), skb, gso_segs, lost_bytes, rack_rtt_us, reo_wnd_used, waiting)))
            # print(f"Loss. {ts} {skb} {rack_rtt_us + reo_wnd_used} {waiting} {gso_segs}, {lost_bytes}")
            return reo_wnd_used

    def parse_tcp_retransmit_skb(self, tokens, retrans_points, is_valid):
        ts = int(tokens[0])
        if tokens[1] == "tcp_retransmit_skb()":
            sk = tokens[2]
            if self.sk != sk:
                is_valid = False
                return
            
            skb = tokens[3]
            left = padded_hex(int(tokens[4], 16), 8)
            right = padded_hex(int(tokens[5], 16), 8)
            segavail = int(tokens[7])
            segs = int(tokens[8])
            
            retrans_points.append((ts,
                RetransmissionEvent(skb, left, right, segavail, segs)))
            is_valid = True
            return
        
        # Retransmission failed.
        # Valid flag prevents the cancellation from wrong skbs's failure event
        # If the just previous retransmission event is wrong, it is not valid.
        if tokens[1] == "__tcp_retransmit_skb()" and is_valid:
            if len(retrans_points) > 0:
                retrans_points.pop()
            return            

    def parse_tcp_check_dsack(self, tokens, sr_points, dsack_points):
        ts = int(tokens[0])

        # Last DSACK event is spurious retransmission.
        if tokens[2] == "returns" and tokens[3] == "true":
            if len(dsack_points) == 0:
                return
            (_, last_dsack) = dsack_points.pop()
            # print(f"SP true. {last_dsack}")
            sr_points.append((ts, last_dsack))
            return
        
        sk = tokens[2]
        if self.sk == None:
            self.sk = sk

        if self.sk != sk:
            return
        
        # DSACK event follows network byte order
        left = switch_endian(tokens[3])
        right = switch_endian(tokens[4])
        dsack_points.append((ts, Segment(left, right)))
        # print(f"Current SP. {dsack_points[-1]}")
        return

    def parse_tcp_rate_skb_delivered(self, tokens, delivered_points):
        ts = int(tokens[0])

        sk = tokens[2]
        if self.sk != sk:
            return

        skb = padded_hex(int(tokens[3], 16), 16)
        left = padded_hex(int(tokens[4], 16), 8)
        right = padded_hex(int(tokens[5], 16), 8)
        delivered_points.append((ts, Segment(left, right)))
        return        

    def analyze_spurious_retrans(self):
        # skb is not an unique identifier.
        loss_map = {}
        partial_segments = []

        for (loss_ts, loss) in self.losses:
            # print(f"Loss. {loss_ts + self.init_ts:<14} {loss_ts / 1_000_000_000:<11}",
            #       f"{loss.skb} {loss.gso_segs} {loss.lost_bytes} {loss.rack_rtt_us}",
            #       f"{loss.reo_wnd} {loss.waiting} {loss}")
            if loss_map.get(loss.skb) == None:
                loss_map[loss.skb] = [loss]
            else:
                loss_map[loss.skb].append(loss)
        # for (retrans_ts, retrans) in self.retrans:
        #     print(f"Retx. {retrans_ts + self.init_ts:<14} {retrans_ts / 1_000_000_000:<11}",
        #           f"{retrans.skb} {retrans.segment.left} {retrans.segment.right}",
        #           f"{retrans.segment.bytelen} {retrans.segment.seglen} {retrans.segsent}")
        # print("")
        # for key in loss_map.keys():
        #     losses = " ".join(str(loss.ts) for loss in loss_map[key])
        #     print(key, losses)
        # print("")        

        # Map retransmissions to loss events
        for (r_ts, retrans) in self.retrans:
            # print(f"Retx. {r_ts + self.init_ts:<14} {r_ts / 1_000_000_000:<11}",
            #       f"{retrans.skb} {retrans.segment.left} {retrans.segment.right}",
            #       f"{retrans.segment.bytelen} {retrans.segment.seglen} {retrans.segsent}", end=" ", flush=True)
            candidate_losses = loss_map.get(retrans.skb)
            if candidate_losses != None and len(candidate_losses) != 0:
                earlier_losses = [candidate for candidate in candidate_losses if candidate.ts <= r_ts]
                
                if len(earlier_losses) != 0:
                    loss = min(earlier_losses, key=lambda x: x.ts)
                    if retrans.segsent == loss.gso_segs:
                        loss.seg_left = retrans.segment.left
                        loss.seg_right = retrans.segment.right
                        retrans.loss_event = loss
                        # print(f"Full Matched. {retrans.loss_event.skb} {loss}", flush=True)
                        candidate_losses.remove(loss)
                        continue
                    else:
                        new_left = padded_hex((int(retrans.segment.left, 16) + retrans.segsent * mss), 8)
                        new_segment = Segment(new_left, retrans.segment.right)
                        partial_segments.append((new_segment, loss, loss.gso_segs - retrans.segsent))
                        retrans.loss_event = loss
                        loss.seg_left = retrans.segment.left
                        loss.seg_right = new_segment.right
                        # print(f"Head Matched. {retrans.loss_event.skb}", flush=True)
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
                        # print(f"Tail Matched. {retrans.loss_event.skb}", flush=True)
                        candidate_losses = loss_map.get(new_loss.skb)
                        candidate_losses.remove(new_loss)
                        partial_segments.remove((partial_segment, new_loss, segremained))
                        break
                    else:
                        new_left = padded_hex((int(retrans.segment.left, 16) + retrans.segsent * mss), 8)
                        new_segment = Segment(new_left, retrans.segment.right)
                        partial_segments.append((new_segment, new_loss, segremained - retrans.segsent))
                        retrans.loss_event = new_loss
                        new_loss.seg_right = new_segment.right
                        # print(f"Cont Matched. {retrans.loss_event.skb} remained={segremained - retrans.segsent}", flush=True)
                        segremained = 0
                        break

        # for (loss_ts, loss) in self.losses:
        #     print(f"Loss. {loss_ts + self.init_ts:<14} {loss_ts / 1_000_000_000:<11}",
        #           f"{loss.skb} {loss.gso_segs} {loss.lost_bytes} {loss.rack_rtt_us}",
        #           f"{loss.reo_wnd} {loss.waiting} {loss.seg_left} {loss.seg_right} {loss}")

        post_sr = {}
        for (sr_ts, segment) in self.sretrans:
            (found_loss_ts, found_loss) = (None, None)
            for (loss_ts, loss) in self.losses:
                # If these values are None, the segments are once marked lost
                # but acked before they are actually retransmitted (mainly due
                # to the retransmissions are deferred)
                if loss.seg_left == None or loss.seg_right == None:
                    continue

                if loss.seg_left <= segment.left and loss.seg_right >= segment.right:
                    found_loss = loss
                    found_loss_ts = loss_ts
                    break
            sr_bytes = int(segment.right, 16) - int(segment.left, 16)
            if found_loss != None:
                # print(f"Srtx. {sr_ts + self.init_ts:<14} {sr_ts / 1_000_000_000:<11}",
                #       f"{segment.left} {segment.right} {sr_bytes:>5} {int(sr_bytes / mss):>2}",
                #       f"{found_loss.skb} {found_loss.rack_rtt_us} {found_loss.reo_wnd}",
                #       f"{found_loss.waiting} {int((sr_ts - found_loss_ts) / 1_000)}")
                
                if found_loss.seg_left != None and found_loss.seg_right != None:
                    for (delivered_ts, delivered) in self.delivered:
                        if delivered.seglen == 0:
                            continue
                        intersection = intersection_segs(delivered.left, delivered.right, segment.left, segment.right)
                        if intersection is None:
                            continue
                        if not (intersection[0], intersection[1]) in post_sr:
                            post_sr[(intersection[0], intersection[1])] = (delivered_ts, found_loss)
            # else:
            #     print(f"Srtx. {sr_ts + self.init_ts:<14} {sr_ts / 1_000_000_000:<11}",
            #           f"{segment.left} {segment.right} {sr_bytes:>5} {int(sr_bytes / mss):>2}")

        # print("")
        # for (delivered_ts, delivered) in self.delivered:
        #     print(f"Dlvd. {delivered_ts + self.init_ts:<14} {delivered_ts / 1_000_000_000:<11}",
        #           f"{delivered.left} {delivered.right}",
        #           f"{delivered.bytelen} {delivered.seglen}")
        
        if len(post_sr) > 0:
            print("            Loss_TS  L rack reo    w      diff      late     B_TS       off      soff      roff     A_TS       off      soff      roff")
        for key in post_sr.keys():
            segment = Segment(key[0], key[1])
            (delivered_ts, found_loss) = post_sr[key]
            diff = (delivered_ts - found_loss.ts) / 1000
            lateness = found_loss.waiting + diff - (found_loss.rack_rtt_us + found_loss.reo_wnd)
            (offset_before, offset_after) = self.relevant_offsets(found_loss.ts)
            diff_offset = offset_before.offset - offset_after.offset
            diff_send_offset = offset_before.offset_send - offset_after.offset_send
            diff_recv_offset = offset_before.offset_recv - offset_after.offset_recv
            
            print(f"SR: {found_loss.ts + self.init_ts:.0f}",
                  f"{segment.seglen:2} {found_loss.rack_rtt_us:4} {found_loss.reo_wnd:3} {found_loss.waiting:4} {diff:9.3f} {lateness:9.3f}",
                  f"{abs(found_loss.ts - offset_before.tcp_recv) / 1_000 :8.3f} {offset_before.offset:9.3f} {offset_before.offset_send:9.3f} {offset_before.offset_recv:9.3f}",
                  f"{abs(offset_after.tcp_recv - found_loss.ts) / 1_000 :8.3f} {offset_after.offset:9.3f} {offset_after.offset_send:9.3f} {offset_after.offset_recv:9.3f}",
                  f"{diff_offset:9.3f} {diff_send_offset:9.3f} {diff_recv_offset:9.3f}")
            
            # lateness = found_loss.rack_rtt_us + found_loss.reo_wnd - found_loss.waiting - diff / 1_000
            # (ts, offset) = self.relevant_offset(found_loss.ts)
            # print(f"SR: {self.sk} {segment.seglen}",
            #         f"{lateness:.3} {found_loss.ts} {offset:.3}")
            
    def relevant_offsets(self, ts):
        befores = [t for t in self.synced_offsets if t.tcp_recv <= ts]
        
        if len(self.synced_offsets) >= len(befores) + 1:
            next = self.synced_offsets[len(befores)]
            return (max(befores, key=lambda x: x.tcp_recv), next)
        else:
            return (max(befores, key=lambda x: x.tcp_recv), max(befores, key=lambda x: x.tcp_recv))

    def retrans_segments(self):
        num_segs = 0
        for retrans_ts, retrans in self.retrans:
            num_segs += retrans.segsent

        return num_segs

def intersection_segs(left1, right1, left2, right2):
    left_max = max(int(left1, 16), int(left2, 16))
    right_min = min(int(right1, 16), int(right2, 16))

    if left_max >= right_min:
        return None
    else:
        return padded_hex(left_max, 8), padded_hex(right_min, 8)

def switch_endian(hex_string):
    while len(hex_string) < 10:
        hex_string = "0x0" + hex_string[2:]
    switched_hex_string = ''.join(reversed([hex_string[i:i+2] for i in range(2, len(hex_string), 2)]))
    return "0x" + switched_hex_string

def padded_hex(num, slen):
    hex_string = hex(num)
    while len(hex_string) < slen + 2:
        hex_string = "0x0" + hex_string[2:]
    return hex_string
