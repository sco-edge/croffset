#!/usr/bin/python3
import croffset
import plot
import argparse
import os
import json

saddr = "192.168.2.102"
first_sport = 42000
daddr = "192.168.2.103"
first_dport_iperf = 5200
first_dport_neper = 5300

class Config:
    app = None
    cca = None
    loss_detection = None
    host = None
    container = None

    def __init__(self, app, cca, loss_detection, host, container):
        self.app = app
        self.cca = cca
        self.loss_detection = loss_detection
        self.host = host
        self.container = container

def identify_configs(experiment):
    with open(f"summary.{experiment}.json", 'r') as file:
        summary = json.load(file)
        host_index = 0
        while (f"h{host_index}" in summary):
            host_index += 1
        
        container_index = 0
        while (f"c{container_index}" in summary):
            container_index += 1

        if "app" in summary and "cca" in summary and "loss_detection" in summary:
            app = summary["app"]
            cca = summary["cca"]
            loss_detection = summary["loss_detection"]
        else:
            return None

    return Config(app, cca, loss_detection, host_index, container_index)

if __name__ == "__main__":
    argparser = argparse.ArgumentParser()
    argparser.add_argument('experiment')
    argparser.add_argument('--cca', default="bbr")
    argparser.add_argument('--plot', '-p', action='store_true')

    global args
    args = argparser.parse_args()

    global iwd
    iwd = os.getcwd()
    os.chdir(os.path.join(iwd, '..', 'output', args.experiment))

    if args.cca != "bbr" and args.cca != "cubic":
        print(f"There is no such an algorithm \"{args.cca}\"")
        exit()

    configs = identify_configs(args.experiment)
    if configs == None:
        print("Failed to parse config.")
        exit(-1)

    # Host flows
    hflows = []
    for i in range(0, configs.host):
        if configs.app == "neper":
            hflow = croffset.Flow("TCP", saddr, first_sport + i, daddr, first_dport_neper + i, "neper")
        else:
            hflow = croffset.Flow("TCP", saddr, first_sport + i, daddr, first_dport_iperf + i, "iperf")
        hflows.append(hflow)

    brtt_file = f"brtt.{args.experiment}.out"
    for hflow in hflows:
        if not hflow.parse_brtt_trace(brtt_file):
            exit(-1)

    trtt_file = f"trtt.{args.experiment}.out"
    rrtt_file = f"trtt_rack.{args.experiment}.out"
    for hflow in hflows:
        if configs.cca == "bbr":
            if not hflow.parse_trtt_trace_bbr(trtt_file):
                exit(-1)
        elif configs.cca == "cubic":
            if not hflow.parse_trtt_trace_cubic(trtt_file):
                exit(-1)
        # if not hflow.parse_rrtt_trace(rrtt_file):
        #     exit(-1)
        if not hflow.parse_marked_trtt_trace(rrtt_file):
            exit(-1)
        hflow.parse_fq_delay_trace(f"fq_delay.{args.experiment}.out")
        hflow.generate_synced_offsets(f"so_h{i}.{args.experiment}.out")
        # with open(f"so_h{i}.{args.experiment}.out", 'w') as file:
        #     for (ts, offset, sent_offset, acked_offset) in hflow.synced_offsets:
        #         line = f"{ts + hflow.init_ts:.0f} {ts:.0f} {offset:.3f} {sent_offset:.3f} {acked_offset:.3f}"
        #         file.write(line + '\n')
        # hflow.generate_offsets()
        # hflow.generate_offsets2()
        # hflow.generate_offsets3()
    
    sock_file = f"sock.{args.experiment}.out"
    for i, hflow in enumerate(hflows):
        hflow.parse_sock_trace(sock_file)
        print(f"h{i} retransmissions:", hflow.retrans_segments())

    # Container flows
    cflows = []
    for i in range(0, configs.container):
        if configs.app == "neper":
            cflow = croffset.Flow("UDP", saddr, first_sport + i, daddr, first_dport_neper + i, "neper")
        else:
            cflow = croffset.Flow("UDP", saddr, first_sport + i, daddr, first_dport_iperf + i, "iperf")
        cflows.append(cflow)
    
    brtt_file = f"brtt.{args.experiment}.out"
    for cflow in cflows:
        if not cflow.parse_brtt_trace(brtt_file):
            exit(-1)

    trtt_file = f"trtt.{args.experiment}.out"
    rrtt_file = f"trtt_rack.{args.experiment}.out"
    for i, cflow in enumerate(cflows):
        if configs.cca == "bbr":
            if not cflow.parse_trtt_trace_bbr(trtt_file):
                exit(-1)
        elif configs.cca == "cubic":
            if not cflow.parse_trtt_trace_cubic(trtt_file):
                exit(-1)
        # if not cflow.parse_rrtt_trace(rrtt_file):
        #     exit(-1)
        if not cflow.parse_marked_trtt_trace(rrtt_file):
            exit(-1)
        cflow.parse_fq_delay_trace(f"fq_delay.{args.experiment}.out")
        cflow.generate_synced_offsets(f"so_c{i}.{args.experiment}.out")
        # with open(f"so_c{i}.{args.experiment}.out", 'w') as file:
        #     for (ts, offset, sent_offset, acked_offset) in cflow.synced_offsets:
        #         line = f"{ts + cflow.init_ts:.0f} {ts:.0f} {offset:.3f} {sent_offset:.3f} {acked_offset:.3f}"
        #         file.write(line + '\n')

        # cflow.generate_offsets()
        # cflow.generate_offsets2()
        # cflow.generate_offsets3()

    sock_file = f"sock.{args.experiment}.out"
    for i, cflow in enumerate(cflows):
        cflow.parse_sock_trace(sock_file)
        print(f"c{i} retransmissions:", cflow.retrans_segments())

    # Analyze spurious retransmissions
    for hflow in hflows:
        hflow.analyze_spurious_retrans()
    for cflow in cflows:
        cflow.analyze_spurious_retrans()

    # Plot
    if args.plot == True:
        for i, hflow in enumerate(hflows):
            # plot.plot_rtts(hflow, f"rtts_h{i}", True)
            plot.plot_synced_offsets(hflow, f"soffsets_h{i}", True)
            plot.plot_diff_offsets(hflow, f"doffsets_h{i}", True)
            # plot.plot_offsets(hflow, f"offsets_h{i}", True)
            # plot.plot_offsets2(hflow, f"offsets2_h{i}", True)
            # plot.plot_offsets3(hflow, f"offsets3_h{i}", True)
        for i, cflow in enumerate(cflows):
            # plot.plot_rtts(cflow, f"rtts_c{i}", True)
            plot.plot_synced_offsets(cflow, f"soffsets_c{i}", True)
            plot.plot_diff_offsets(cflow, f"doffsets_c{i}", True)
            # plot.plot_offsets(cflow, f"offsets_c{i}", True)
            # plot.plot_offsets2(cflow, f"offsets2_c{i}", True)
            # plot.plot_offsets3(cflow, f"offsets3_c{i}", True)