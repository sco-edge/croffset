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
        self.first_sport= 42000
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

def post_analyze_traces(num_flows, is_container):
    flows = []
    protocol = "UDP" if is_container else "TCP"

    for i in range(0, num_flows):
        flow_id = f"c{i}" if is_container else f"h{i}"
        flow = croffset.Flow(protocol, configs.saddr, configs.first_sport + i,
                              configs.daddr, configs.first_dport + i, configs.app)

        if not flow.parse_rtt_trace(f"rtt.{flow_id}.{args.experiment}.out"):
            print(f"parse_xdp_trace() at {flow_id} failed.")
            exit(-1)

    return flows

def plot_traces(flows, is_container):
    for i, flow in enumerate(flows):
        flow_id = f"c{i}" if is_container else f"h{i}"
        plot.plot_rtts(flow, f"rtt_{flow_id}", True)
        plot.plot_offsets(flow, f"offset_{flow_id}", True)

if __name__ == "__main__":
    argparser = argparse.ArgumentParser()
    argparser.add_argument('experiment')
    argparser.add_argument('--path', default="../output")
    argparser.add_argument('--plot', '-p', action='store_true')

    global args
    args = argparser.parse_args()

    global swd
    swd = os.path.join(os.getcwd(), 'scripts')
    os.chdir(os.path.join(swd, args.path, args.experiment))

    configs = identify_configs(args.experiment)
    if configs == None:
        print("Failed to parse config.")
        exit(-1)

    # Main logic
    hflows = post_analyze_traces(configs.host, False)
    cflows = post_analyze_traces(configs.container, True)

    # Plotting
    if args.plot == True:
        plot_traces(hflows, False)
        plot_traces(cflows, True)