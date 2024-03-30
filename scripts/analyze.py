#!/usr/bin/python3
import croffset
import plot
import argparse

saddr = "192.168.2.102"
first_sport = 42000
daddr = "192.168.2.103"
first_dport = 5200

def offsets(flow):
    return

if __name__ == "__main__":
    argparser = argparse.ArgumentParser()
    argparser.add_argument('--host', '-f', default=1)
    argparser.add_argument('--container', '-c', default=1)
    argparser.add_argument('--cca', '-a', default="bbr")
    argparser.add_argument('--plot', '-p', action='store_true')

    global args
    args = argparser.parse_args()

    if args.cca != "bbr" and args.cca != "cubic":
        print(f"There is no such an algorithm \"{args.cca}\"")
        exit()

    test = []
    # plot.plot_offsets(test, "plot_test_offset.png")
    # exit()

    # Host flows
    hflows = []
    for i in range(0, args.host):
        hflow = croffset.Flow("TCP", saddr, first_sport + i, daddr, first_dport + i, "iperf")
        hflows.append(hflow)

    brtt_file = "../data/tx-h-f1-t30-bbr-iperf-1/raw.epping.tx-h-f1-t30-bbr-iperf-1.out"
    for hflow in hflows:
        hflow.parse_brtt_trace(brtt_file)

    trtt_file = "../data/tx-h-f1-t30-bbr-iperf-1/raw.bpftrace.tx-h-f1-t30-bbr-iperf-1.out"
    for hflow in hflows:
        if args.cca == "bbr":
            hflow.parse_trtt_trace_bbr(trtt_file)
        elif args.cca == "cubic":
            hflow.parse_trtt_trace_cubic(trtt_file)
        hflow.generate_offsets()
        # for o in hflow.offsets:
        #     print(o)
    
    # Container flows
    cflows = []
    for i in range(0, args.container):
        cflow = croffset.Flow("UDP", saddr, first_sport + i, daddr, first_dport + i, "iperf")
        cflows.append(cflow)
    
    brtt_file = "../data/tx-e-f1-t30-bbr-iperf-2/raw.epping.tx-e-f1-t30-bbr-iperf-2.out"
    for cflow in cflows:
        cflow.parse_brtt_trace(brtt_file)

    trtt_file = "../data/tx-e-f1-t30-bbr-iperf-2/raw.bpftrace.tx-e-f1-t30-bbr-iperf-2.out"
    for cflow in cflows:
        if args.cca == "bbr":
            cflow.parse_trtt_trace_bbr(trtt_file)
        elif args.cca == "cubic":
            cflow.parse_trtt_trace_cubic(trtt_file)
        cflow.generate_offsets()
        # for o in cflow.offsets:
        #     print(o)

    # Plot
    if args.plot == True:
        for hflow in hflows:
            plot.plot_rtts(hflow, "plot_rtts_hflow.png")
            plot.plot_offsets(hflow, "plot_offsets_hflow.png")
        for cflow in cflows:
            plot.plot_rtts(cflow, "plot_rtts_cflow.png")
            plot.plot_offsets(cflow, "plot_offsets_cflow.png")