#!/usr/bin/python3
import copy
import re
import numpy as np
mss = 1398

class MeasuredRTT:
    # All timestamps are stored in ns unit
    mark = None
    rack_send = None
    rack_recv = None
    xdp_ingress = None
    fq_enqueue = None
    fq_dequeue = None

    # All RTTs are stored in us unit
    trtt = None
    brtt = None
    offset_send = None
    offset_recv = None
    offset = None
    tc_fq = None
    fq = None

    def __init__(self, mark, rack_send, rack_recv, xdp_ingress, fq_enqueue, fq_dequeue):
        self.mark = mark
        self.rack_send = rack_send
        self.rack_recv = rack_recv
        self.xdp_ingress = xdp_ingress
        self.fq_enqueue = fq_enqueue
        self.fq_dequeue = fq_dequeue

        self.trtt = (rack_recv - rack_send) / 1000
        self.brtt = (xdp_ingress - fq_dequeue) / 1000
        self.offset_send = (fq_dequeue - rack_send) / 1000
        self.offset_recv = (rack_recv - xdp_ingress) / 1000
        self.offset = self.offset_send + self.offset_recv
        self.fq = (fq_dequeue - fq_enqueue) / 1000
        self.tc_fq = self.offset_send - self.fq

        # Offsets exceeding 10 ms mean something wrong
        # probably due to the last truncated timestamps
        if abs(self.offset_send) > 10_000 or abs(self.offset_recv) > 10_000:
            raise ValueError("Some timestamps might be wrong")

# class MeasuredRTT:
#     ts = None
#     sent_ts = None
#     acked_ts = None
#     rtt = None

#     def __init__(self, ts, sent_ts, acked_ts):
#         self.ts = ts
#         self.sent_ts = sent_ts
#         self.acked_ts = acked_ts
#         self.rtt = (acked_ts - sent_ts) / 1000

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
    sk = None        # sk address
    saddr = None
    sport = None
    daddr = None
    dport = None
    transport = None

    astat = None     # Application Statistics
    
    init_ts = None   # Initial timestamp
    xdps_map = None     # Raw timestamps for xdp
    racks_map = None    # Raw timestamps for rack
    fqs_map = None      # Raw timestamps for fq
    rtts = None       # Measured RTTs

    losses = None    # Packet loss events
    delivered = None # Delivered events
    retrans = None   # Retransmission events
    sretrans = None  # Spurious retransmission events
    dsacks = None    # DSACK events
    
    def __init__(self, transport, saddr, sport, daddr, dport, app):
        self.transport = transport
        self.saddr = saddr
        self.sport = sport
        self.daddr = daddr
        self.dport = dport

        self.xdps_map = {}
        self.racks_map = {}
        self.fqs_map = {}
        self.rtts = []

        if app == "iperf":
            self.astat = IperfStat
        elif app == "neper":
            self.astat = NeperStat
        else:
            print(f"flow init error: {app}")

    def parse_xdp_trace(self, file):
        expr = re.compile(r"^(\d+?) (.+?)$")
        with open(file, 'r') as lines:
            lines.seek(0)
            for l in lines:
                match = expr.search(l)
                if match == None:
                    continue
                
                ts = int(match.group(1))
                mark = padded_hex(int(match.group(2), 16), 8)

                if not mark in self.xdps_map:
                    self.xdps_map[mark] = [ts]
                else:
                    self.xdps_map[mark].append(ts)

        return len(self.xdps_map)

    def parse_rack_trace(self, file):
        marks = {}

        with open(file, 'r') as lines:
            lines.seek(0)
            for l in lines:
                tokens = l.rstrip().split()
                if len(tokens) < 2:
                    continue

                # Parse tcp_ack()
                if tokens[1] == "tcp_ack()":
                    mark = padded_hex(int(tokens[4], 16), 8)
                    port = int(tokens[5])
                    if self.sport == port and self.sk == None:
                        self.sk = tokens[2]

                    marks[port] = mark
                    
                # Parse tcp_rack_advance()
                if tokens[1] == "tcp_rack_advance()":
                    sport = int(tokens[2])
                    if self.sport != sport or not marks.get(sport):
                        continue
                    mark = marks[sport]

                    ts = int(tokens[0])
                    rtt_us = int(tokens[5])
                    tcp_min_rtt_us = int(tokens[6])
                    rack_mstamp = int(tokens[7]) * 1000
                    xmit_time = int(tokens[8]) * 1000
                    tcp_mstamp = int(tokens[9]) * 1000
                    sacked = int(tokens[10])

                    # tcp_rack_advance() logic
                    # if rtt_us < tcp_min_rtt_us and (sacked & int("0x02", 16) + int("0x80", 16) + int("0x10", 16)):
                    #     continue

                    # init_ts is initialized here
                    if not self.init_ts:
                        self.init_ts = xmit_time

                    if not mark in self.racks_map:
                        self.racks_map[mark] = [(ts, xmit_time, tcp_mstamp)]
                    else:
                        self.racks_map[mark].append((ts, xmit_time, tcp_mstamp))

        return len(self.racks_map)
    
    def parse_fq_trace(self, file):
        queued = {}
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
                    queued[skb] = (ts, skb_mstamp_ns)
                    continue

                # FQ dequeue events
                if tokens[1] == "fq_dequeue()":
                    sk = padded_hex(int(tokens[2], 16), 16)
                    if sk != self.sk:
                        continue

                    ts = int(tokens[0])
                    skb = padded_hex(int(tokens[3], 16), 16)
                    skb_mstamp_ns = int(tokens[4])

                    if skb in queued:
                        (enqueue_ts, enqueue_skb_mstamp_ns) = queued.pop(skb)
                        
                        # div_u64() in the kernel seems to truncate the decimal point
                        skb_mstamp_us = int(skb_mstamp_ns / 1_000)
  
                        # skb_mstamp_us works as an identifier for sk_buff
                        if not skb_mstamp_us in self.fqs_map:
                            self.fqs_map[skb_mstamp_us] = [(enqueue_ts, ts)]
                        else:
                            self.fqs_map[skb_mstamp_us].append((enqueue_ts, ts))
        
        return len(self.fqs_map)

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

        self.losses = np.array([(i[0], i[1]) for i in loss_points])
        self.retrans = np.array([(i[0], i[1]) for i in retrans_points])
        self.delivered = np.array([(i[0], i[1]) for i in delivered_points])
        self.sretrans = np.array([(i[0], i[1]) for i in sr_points])
        self.dsacks = np.array([(i[0], i[1]) for i in dsack_points])
    
        # sock trace may have no entries
        return True

    def construct_rtts(self, output):
        for mark in self.xdps_map:
            if mark not in self.racks_map:
                continue

            racks = self.racks_map.get(mark)
            for (rack_ts, rack_send, rack_recv) in racks:
                rack_send_us = int(rack_send / 1_000)

                xdp_ts = min((el for el in self.xdps_map[mark] if el <= rack_recv),
                                key=lambda x: rack_recv - x)

                # To address bpf_get_prandom_u32() conflicts
                # If the difference between brtt and trtt timestamps >= 1 ms
                if abs(rack_ts - xdp_ts) >= 10_000_000:
                    continue

                if not int(rack_send_us) in self.fqs_map:
                    continue

                (fq_enqueue, fq_dequeue) = min(self.fqs_map[rack_send_us], key=lambda x: x)
                try:
                    rtt = MeasuredRTT(mark, rack_send, rack_recv, xdp_ts, fq_enqueue, fq_dequeue)
                    # print(rack_send, rack_recv, xdp_ts, fq_enqueue, fq_dequeue)
                    self.rtts.append(rtt)
                except ValueError:
                    pass

        self.rtts = sorted(self.rtts, key=lambda x: x.rack_recv)
        with open(output, 'w') as rtt_file:
            for rtt in self.rtts:
                line = f"{rtt.rack_recv} {rtt.rack_recv - self.init_ts:>11.0f} {rtt.mark}   " +  \
                       f"{rtt.trtt:>8.3f} {rtt.brtt:>8.3f} {rtt.offset:>8.3f}   " + \
                       f"{rtt.rack_send:>11.0f} {rtt.fq_dequeue:>11.0f} {rtt.offset_send:>8.3f}   " + \
                       f"{rtt.xdp_ingress:>11.0f} {rtt.rack_recv:>11.0f} {rtt.offset_recv:>8.3f}   " + \
                       f"{rtt.fq:>8.3f} {rtt.tc_fq:>8.3f}\n"
                rtt_file.write(line)
        
        return True

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
                LossEvent(ts, skb, gso_segs, lost_bytes, rack_rtt_us, reo_wnd_used, waiting)))
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
            sr_points.append((ts, last_dsack))
            return
        
        sk = tokens[2]
        # if self.sk == None:
        #     self.sk = sk

        if self.sk != sk:
            return
        
        # DSACK event follows network byte order
        left = switch_endian(tokens[3])
        right = switch_endian(tokens[4])
        dsack_points.append((ts, Segment(left, right)))
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

    def analyze_spurious_retrans(self, output):
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
        
        with open(output, "w") as sr_file:
            for key in post_sr.keys():
                segment = Segment(key[0], key[1])
                (delivered_ts, found_loss) = post_sr[key]
                lateness = (delivered_ts - found_loss.ts - found_loss.reo_wnd) / 1_000
                lateness = found_loss.waiting + lateness - (found_loss.rack_rtt_us + found_loss.reo_wnd)
                (rtt_before, rtt_after) = self.relevant_rtt(found_loss.ts)
                # offset_diff = 
                # line = f"{found_loss.ts:15.0f} {segment.seglen:2} {found_loss.rack_rtt_us:4} {found_loss.reo_wnd:3} {found_loss.waiting:4} {diff:9.3f}   " + \
                #     f"{lateness:9.3f} " + \
                #     f"{rtt_before.rack_recv:15.0f} {abs(found_loss.ts - rtt_before.rack_recv) / 1_000 :8.3f} {rtt_before.offset:9.3f} {rtt_before.offset_send:9.3f} {rtt_before.offset_recv:9.3f} " + \
                #     f"{rtt_after.rack_recv:15.0f} {abs(rtt_after.rack_recv - found_loss.ts) / 1_000 :8.3f} {rtt_after.offset:9.3f} {rtt_after.offset_send:9.3f} {rtt_after.offset_recv:9.3f}\n"
                line = f"{found_loss.ts} {segment.seglen:2} {found_loss.rack_rtt_us:4} {found_loss.reo_wnd:3} {found_loss.waiting:4} " + \
                       f"{delivered_ts:15.0f}\n"
                sr_file.write(line)
            
        return True
            
    def relevant_rtt(self, ts):
        befores = [t for t in self.rtts if t.rack_recv <= ts]
        if len(self.rtts) >= len(befores) + 1:
            next = self.rtts[len(befores)]
            return (max(befores, key=lambda x: x.rack_recv), next)
        else:
            return (max(befores, key=lambda x: x.rack_recv), max(befores, key=lambda x: x.rack_recv))

    def retrans_segments(self):
        num_segs = 0
        for retrans_ts, retrans in self.retrans:
            num_segs += retrans.segsent

        return num_segs
    
    def statistics(self):
        trtt = (np.mean([rtt.trtt for rtt in self.rtts]), np.std([rtt.trtt for rtt in self.rtts]))
        brtt = (np.mean([rtt.brtt for rtt in self.rtts]), np.std([rtt.brtt for rtt in self.rtts]))
        offset = (np.mean([rtt.offset for rtt in self.rtts]), np.std([rtt.offset for rtt in self.rtts]))
        offset_send = (np.mean([rtt.offset_send for rtt in self.rtts]), np.std([rtt.offset_send for rtt in self.rtts]))
        offset_recv = (np.mean([rtt.offset_recv for rtt in self.rtts]), np.std([rtt.offset_recv for rtt in self.rtts]))
        fq = (np.mean([rtt.fq for rtt in self.rtts]), np.std([rtt.fq for rtt in self.rtts]))

        return (trtt, brtt, offset, offset_send, offset_recv, fq)

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