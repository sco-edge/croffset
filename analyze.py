#!/usr/bin/python3
from scripts import croffset
from scripts import plot
import argparse
import os
import json

class Config:
    app = None
    cca = None
    loss_detection = None
    host = None
    container = None

    saddr = None
    daddr = None
    first_sport = None
    first_dport = None

    def __init__(self, app, cca, loss_detection, host, container):
        self.app = app
        self.cca = cca
        self.loss_detection = loss_detection
        self.host = host
        self.container = container

        self.saddr = "192.168.2.102"
        self.daddr = "192.168.2.103"
        self.first_sport= 45000
        self.first_dport = 5300 if self.app == "neper" else 5200

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
            available_apps = ["iperf", "neper"]
            app = summary["app"]
            if app not in available_apps:
                print(f"{app} is not an available app. Available: {', '.join(available_apps)}")
                return None

            available_ccas = ["bbr", "cubic"]
            cca = summary["cca"]
            if cca not in available_ccas:
                print(f"{cca} is not an available cca. Available: {', '.join(available_ccas)}")
                return None

            available_loss_detection = ["rack-tlp", "rack-er", "rack-none", "reno-tlp", "reno-er", "reno-none"]
            loss_detection = summary["loss_detection"]
            if loss_detection not in available_loss_detection:
                print(f"{loss_detection} is not an available loss detection. Available: {', '.join(available_loss_detection)}")
                return None
        else:
            print("Wrong summary.")
            return None

    return Config(app, cca, loss_detection, host_index, container_index)

def analyze_traces(num_flows, is_container):
    flows = []
    protocol = "UDP" if is_container else "TCP"

    for i in range(0, num_flows):
        flow_id = f"c{i}" if is_container else f"h{i}"
        flow = croffset.Flow(protocol, configs.saddr, configs.first_sport + i,
                              configs.daddr, configs.first_dport + i, configs.app)

        if not flow.parse_xdp_trace(f"xdp.{args.experiment}.out"):
            print(f"parse_xdp_trace() at {flow_id} failed.")
            exit(-1)

        if not flow.parse_rack_trace(f"rack.{args.experiment}.out"):
            print(f"parse_rack_trace() at {flow_id} failed.")
            exit(-1)

        if not flow.parse_fq_trace(f"fq.{args.experiment}.out"):
            print(f"parse_fq_trace() at {flow_id} failed.")
            exit(-1)

        if not flow.parse_sock_trace(f"sock.{args.experiment}.out"):
            print(f"parse_sock_trace() at {flow_id} failed.")
            exit(-1)

        if not flow.construct_rtts(f"rtt.{flow_id}.{args.experiment}.out"):
            print(f"construct_rtts() at {flow_id} failed.")
            exit(-1)

        (sr_count, comp_count, altcomp_count) = flow.analyze_spurious_retrans(f"sr.{flow_id}.{args.experiment}.out", False)

        # Writing to the summary.json
        summary_json = f"summary.{args.experiment}.json"
        with open(summary_json, 'r') as file:
            data = json.load(file)

        if not data.get(flow_id):
            print(f"Writing to summary.json failed at {flow_id}.")
            continue

        (trtt, brtt, offset, offset_send, offset_recv, fq) = flow.statistics()
        data[flow_id]["trtt_mean"] = trtt[0]
        data[flow_id]["trtt_std"] = trtt[1]
        data[flow_id]["brtt_mean"] = brtt[0]
        data[flow_id]["brtt_std"] = brtt[1]
        data[flow_id]["offset_mean"] = offset[0]
        data[flow_id]["offset_std"] = offset[1]
        data[flow_id]["offset_send_mean"] = offset_send[0]
        data[flow_id]["offset_send_std"] = offset_send[1]
        data[flow_id]["offset_recv_mean"] = offset_recv[0]
        data[flow_id]["offset_recv_std"] = offset_recv[1]
        data[flow_id]["fq_mean"] = fq[0]
        data[flow_id]["fq_std"] = fq[1]

        data[flow_id]["sr_count"] = sr_count
        data[flow_id]["comp_count"] = comp_count
        data[flow_id]["altcomp_count"] = altcomp_count

        with open(summary_json, 'w') as file:
            json.dump(data, file, indent=4)

        flows.append(flow)
    
    return flows

def analyze_sock_trace_only(num_flows, is_container):
    flows = []
    protocol = "UDP" if is_container else "TCP"

    for i in range(0, num_flows):
        flow_id = f"c{i}" if is_container else f"h{i}"
        flow = croffset.Flow(protocol, configs.saddr, configs.first_sport + i,
                              configs.daddr, configs.first_dport + i, configs.app)

        if not flow.parse_sock_trace(f"sock.{args.experiment}.out"):
            print(f"parse_sock_trace() at {flow_id} failed.")
            exit(-1)

        (sr_count, comp_count, altcomp_count) = flow.analyze_spurious_retrans(f"sr.{flow_id}.{args.experiment}.out", True)

        # Writing to the summary.json
        summary_json = f"summary.{args.experiment}.json"
        with open(summary_json, 'r') as file:
            data = json.load(file)

        if not data.get(flow_id):
            print(f"Writing to summary.json failed at {flow_id}.")
            continue

        data[flow_id]["sr_count"] = sr_count
        data[flow_id]["comp_count"] = comp_count
        data[flow_id]["altcomp_count"] = altcomp_count

        with open(summary_json, 'w') as file:
            json.dump(data, file, indent=4)

        flows.append(flow)
    
    return flows

def parse_rtts(num_flows, is_container):
    flows = []
    protocol = "UDP" if is_container else "TCP"

    for i in range(0, num_flows):
        flow_id = f"c{i}" if is_container else f"h{i}"
        flow = croffset.Flow(protocol, configs.saddr, configs.first_sport + i,
                              configs.daddr, configs.first_dport + i, configs.app)

        if not flow.parse_rtt_trace(f"rtt.{flow_id}.{args.experiment}.out"):
            print(f"parse_xdp_trace() at {flow_id} failed.")
            return None

    return flows

def plot_traces(flows, is_container):
    for i, flow in enumerate(flows):
        flow_id = f"c{i}" if is_container else f"h{i}"
        plot.plot_rtts(flow, f"rtt_{flow_id}", True)
        plot.plot_offsets(flow, f"offset_{flow_id}", True)
        
if __name__ == "__main__":
    argparser = argparse.ArgumentParser()
    argparser.add_argument('experiment')
    argparser.add_argument('--cca', default="bbr")
    argparser.add_argument('--plot', '-p', action="store_true")
    argparser.add_argument('--sock-only', action="store_true")
    argparser.add_argument('--path', default="output")
    argparser.add_argument('--reuse-rtt', action="store_true")
    argparser.add_argument('--post-analysis', action="store_true")

    global args
    args = argparser.parse_args()

    global swd
    os.chdir(os.path.join(os.getcwd(), args.path, args.experiment))

    configs = identify_configs(args.experiment)
    if configs == None:
        print("Failed to parse config.")
        exit(-1)

    if args.sock_only:
        hflows = analyze_sock_trace_only(configs.host, False)
        cflows = analyze_sock_trace_only(configs.container, True)
        exit()

    # Main logic
    if args.reuse_rtt:
        hflows = parse_rtts(configs.host, False)
        cflows = parse_rtts(configs.container, True)
    else:
        hflows = analyze_traces(configs.host, False)
        cflows = analyze_traces(configs.container, True)

    # Plotting
    if args.plot == True:
        plot_traces(hflows, False)
        plot_traces(cflows, True)