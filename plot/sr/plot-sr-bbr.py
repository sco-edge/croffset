#!/usr/bin/python3
import matplotlib as mpl
import matplotlib.pyplot as pp
import numpy as np

import sys, os
sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))

from lib import parse as plotparse

class PlotInput:
    throughput = None
    retrans = None
    spurious = None
    norm_spurious = None
    sr_ratio = None

    def __init__(self, throughput, retrans, spurious, norm_spurious, sr_ratio):
        self.throughput = throughput
        self.retrans = retrans
        self.spurious = spurious
        self.norm_spurious = norm_spurious
        self.sr_ratio = sr_ratio

def parse_dataset(data, path):
    for experiment in os.listdir(path):
        if not os.path.isdir(os.path.join(path, experiment)):
            continue

        run = plotparse.parse_run(path, experiment)
        if not run:
            continue

        if not data.get(run.extype):
            data[run.extype] = [run]
        else:
            data[run.extype].append(run)

def generate_plot_data(data):
    host = []
    container = []
    for i in range(1, 7):
        extype = f"h{i}-c0"
        runs = data[extype]
        throughput = np.mean([run.throughput for run in runs])
        retrans = np.mean([run.retrans for run in runs])
        spurious = np.mean([run.spurious_retrans for run in runs])
        
        norm_srs = []
        sr_ratios = []
        for run in runs:
            if run.retrans == 0:
                sr_ratios.append(0)
            else:
                sr_ratios.append(run.spurious_retrans / run.retrans)

            norm_srs.append(run.spurious_retrans / run.mean_throughput)
        
        norm_sr = np.mean(norm_srs)
        sr_ratio = np.mean(sr_ratios)

        host.append(PlotInput(throughput, retrans, spurious, norm_sr, sr_ratio))

        extype = f"h0-c{i}"
        runs = data[extype]
        throughput = np.mean([run.throughput for run in runs])
        retrans = np.mean([run.retrans for run in runs])
        spurious = np.mean([run.spurious_retrans for run in runs])
        
        norm_srs = []
        sr_ratios = []
        for run in runs:
            if run.retrans == 0:
                sr_ratios.append(0)
            else:
                sr_ratios.append(run.spurious_retrans / run.retrans)

            norm_srs.append(run.spurious_retrans / run.mean_throughput)
        
        norm_sr = np.mean(norm_srs)
        sr_ratio = np.mean(sr_ratios)

        container.append(PlotInput(throughput, retrans, spurious, norm_sr, sr_ratio))

    return (host, container)

def configure_pp():
    # Import the font
    font_dirs = ["../../../../resources/inter"]
    font_files = mpl.font_manager.findSystemFonts(fontpaths=font_dirs)

    for font_file in font_files:
        mpl.font_manager.fontManager.addfont(font_file)

    pp.rcParams["axes.prop_cycle"] = pp.cycler("color", pp.cm.Dark2.colors)

    # pp.set_cmap("Dark2")
    # colors = pp.cm.hot(np.linspace(0,1,10))
    # pp.gca().set_prop_cycle(cycler('color', colors))
    pp.rcParams["figure.figsize"] = (3.4, 1.15)
    pp.rcParams["font.family"] = "Inter"
    pp.rcParams["font.size"] = 6

def plot(host, cont, name):
    x = np.array([1, 2, 3, 4, 5, 6])

    fig, ax1 = pp.subplots()
    p1,  = ax1.plot(x, [item.throughput for item in host], linewidth=1, marker='o', markersize=3, label='Host throughput')
    p2,  = ax1.plot(x, [item.throughput for item in cont], color='C1', linewidth=1, marker='D', markersize=3, label='Container throughput')

    ax1.set_xlabel('Number of flows')
    ax1.set_ylabel('Throughput (Gbps)')
    ax1.set_xticks([1, 2, 3, 4, 5, 6])
    ax1.set_yticks([0, 20, 40, 60, 80, 100])

    ax2 = ax1.twinx()  # instantiate a second axes that shares the same x-axis
    p3 = ax2.bar(x - 0.15, [item.retrans for item in host], 0.3, label='Host retrans')
    p4 = ax2.bar(x - 0.15, [item.spurious for item in host], 0.3, label='Host spurious')
    p5 = ax2.bar(x + 0.15, [item.retrans for item in cont], 0.3, label='Container retrans')
    p6 = ax2.bar(x + 0.15, [item.spurious for item in cont], 0.3, label='Container spurious')

    ax2.set_ylabel('Number of Spurious Retx.')
    ax2.set_yticks([0, 1000, 2000, 3000, 4000], ["0", "1k", "2k", "3k", "4k"])

    pp.savefig(f"{name}.png", dpi=300, bbox_inches='tight', pad_inches=0.03)

if __name__ == "__main__":
    rack = {}

    parse_dataset(rack, "../../dataset/noin-bbr-20240415")
    rack.pop("h0-c3")
    rack.pop("h0-c4")
    rack.pop("h0-c5")
    rack.pop("h0-c6")
    parse_dataset(rack, "../../dataset/noin-bbr-20240415-compl")
    rack.pop("h0-c4")
    rack.pop("h0-c5")
    rack.pop("h0-c6")
    parse_dataset(rack, "../../dataset/noin-bbr-20240417-c4")
    parse_dataset(rack, "../../dataset/noin-bbr-20240417-c5")
    parse_dataset(rack, "../../dataset/noin-bbr-20240417-c6")

    for key in rack:
        print(key, len(rack[key]))

    (rack_host, rack_cont) = generate_plot_data(rack)

    configure_pp()

    plot(rack_host, rack_cont, "bbr-rack")