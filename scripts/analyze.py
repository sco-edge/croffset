#!/usr/bin/python3
import croffset
import plot
import argparse

saddr = "192.168.2.102"
first_sport = 42000
daddr = "192.168.2.103"
first_dport = 5200

if __name__ == "__main__":
    argparser = argparse.ArgumentParser()
    argparser.add_argument('experiment')
    argparser.add_argument('--host', '-f', type=int, default=0)
    argparser.add_argument('--container', '-c', type=int, default=1)
    argparser.add_argument('--cca', '-a', default="bbr")
    argparser.add_argument('--plot', '-p', action='store_true')

    global args
    args = argparser.parse_args()

    if args.cca != "bbr" and args.cca != "cubic":
        print(f"There is no such an algorithm \"{args.cca}\"")
        exit()

    # Host flows
    hflows = []
    for i in range(0, args.host):
        hflow = croffset.Flow("TCP", saddr, first_sport + i, daddr, first_dport + i, "iperf")
        hflows.append(hflow)

    brtt_file = f"../output/{args.experiment}/brtt.{args.experiment}.out"
    for hflow in hflows:
        hflow.parse_brtt_trace(brtt_file)

    trtt_file = f"../output/{args.experiment}/trtt.{args.experiment}.out"
    for hflow in hflows:
        if args.cca == "bbr":
            if not hflow.parse_trtt_trace_bbr(trtt_file):
                exit(-1)
        elif args.cca == "cubic":
            if not hflow.parse_trtt_trace_cubic(trtt_file):
                exit(-1)
        hflow.generate_offsets()
    
    sock_file = f"../output/{args.experiment}/sock.{args.experiment}.out"
    for hflow in hflows:
        hflow.parse_sock_trace(sock_file)

    # Container flows
    cflows = []
    for i in range(0, args.container):
        cflow = croffset.Flow("UDP", saddr, first_sport + i, daddr, first_dport + i, "iperf")
        cflows.append(cflow)
    
    brtt_file = f"../output/{args.experiment}/brtt.{args.experiment}.out"
    for cflow in cflows:
        cflow.parse_brtt_trace(brtt_file)

    trtt_file = f"../output/{args.experiment}/trtt.{args.experiment}.out"
    for cflow in cflows:
        if args.cca == "bbr":
            if not cflow.parse_trtt_trace_bbr(trtt_file):
                exit(-1)
        elif args.cca == "cubic":
            if not cflow.parse_trtt_trace_cubic(trtt_file):
                exit(-1)
        cflow.generate_offsets()

    sock_file = f"../output/{args.experiment}/sock.{args.experiment}.out"
    for cflow in cflows:
        cflow.parse_sock_trace(sock_file)

    print("parsing done.")

    # Analyze spurious retransmissions
    for hflow in hflows:
        hflow.analyze_spurious_retrans()
    for cflow in cflows:
        cflow.analyze_spurious_retrans()

    # Plot
    if args.plot == True:
        for hflow in hflows:
            plot.plot_rtts(hflow, "plot_rtts_hflow.png", True)
            plot.plot_offsets(hflow, "plot_offsets_hflow.png")
        for cflow in cflows:
            print(len(cflow.trtts))
            plot.plot_rtts(cflow, "plot_rtts_cflow.png", True)
            plot.plot_offsets(cflow, "plot_offsets_cflow.png")