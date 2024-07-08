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

        run = plotparse.parse_run_only_sr(path, experiment)
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
        if i == 3 or i == 5:
            continue
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

    # pp.rcParams["axes.prop_cycle"] = pp.cycler("color", pp.cm.Dark2.colors)

    # pp.set_cmap("Dark2")
    # colors = pp.cm.hot(np.linspace(0,1,10))
    # pp.gca().set_prop_cycle(cycler('color', colors))
    pp.rcParams["figure.figsize"] = (3.4, 1.16)
    pp.rcParams["font.family"] = "Inter"
    pp.rcParams["font.size"] = 6
    pp.rcParams["hatch.linewidth"] = 0.75

def plot(bbr_host, bbr_cont, cubic_host, cubic_cont, name):
    x = np.array([1, 2, 3, 4])

    ax1 = pp.subplot(121)
    pp.subplots_adjust(wspace=0.5)
    pp.grid(linewidth=1, linestyle=":")
    p1 = ax1.bar(x - 0.15, [item.retrans for item in bbr_host], 0.3, color="C0", label='Host retrans', )
    p2 = ax1.bar(x - 0.15, [item.spurious for item in bbr_host], 0.3, color="C2", label='Host spurious', hatch='/////')
    p3 = ax1.bar(x + 0.15, [item.retrans for item in bbr_cont], 0.3, color="C1", label='Container retrans')
    p6 = ax1.bar(x + 0.15, [item.spurious for item in bbr_cont], 0.3, color="C3", label='Container spurious', hatch='/////')
    
    ax1.set_xlabel('BBR flows')
    ax1.set_xticks([1, 2, 3, 4], ["1", "2", "4", "6"])
    ax1.set_ylabel('# of (spurious) retx.')
    ax1.set_yticks([0, 2500, 5000, 7500, 10000])
    ax1.set_yticklabels(["0", "2.5k", "5k", "7.5k", "10k"])
    ax1.set_ylim(0, 17500)
    
    ax2 = ax1.twinx()  # instantiate a second axes that shares the same x-axis
    p5,  = ax2.plot(x, [item.sr_ratio for item in bbr_host], color="k", linewidth=1, marker='o', markersize=3, label='BBR Host throughput')
    p6,  = ax2.plot(x, [item.sr_ratio for item in bbr_cont], color="r", linewidth=1, marker='x', markersize=5, label='BBR Container throughput')

    pp.grid(linewidth=1, linestyle=":")
    ax2.set_yticks([0, 0.15, 0.3, 0.45])
    ax2.set_yticklabels(["0%", "15%", "30%", "45%"])
    ax2.set_ylim(-0.6, 0.45)

    ax3 = pp.subplot(122)
    pp.grid(linewidth=1, linestyle=":")
    p3 = ax3.bar(x - 0.15, [item.retrans for item in cubic_host], 0.3, color="C0", label='Host retrans')
    p4 = ax3.bar(x - 0.15, [item.spurious for item in cubic_host], 0.3, color="C2", label='Host spurious', hatch='/////')
    p5 = ax3.bar(x + 0.15, [item.retrans for item in cubic_cont], 0.3, color="C1", label='Container retrans')
    p6 = ax3.bar(x + 0.15, [item.spurious for item in cubic_cont], 0.3, color="C3", label='Container spurious', hatch='/////')

    ax3.set_xlabel('CUBIC flows')
    ax3.set_xticks([1, 2, 3, 4], ["1", "2", "4", "6"])
    # ax3.set_yticks([0, 20, 40, 60, 80, 100], ["", "", "", "", "", ""])
    ax3.set_yticks([0, 2500, 5000, 7500, 10000])
    ax3.set_yticklabels(["0", "2.5k", "5k", "7.5k", "10k"])
    ax3.set_ylim(0, 17500)

    ax4 = ax3.twinx()  # instantiate a second axes that shares the same x-axis
    p5,  = ax4.plot(x, [item.sr_ratio for item in cubic_host], color="k", linewidth=1, marker='o', markersize=3, label='CUBIC Host throughput')
    p6,  = ax4.plot(x, [item.sr_ratio for item in cubic_cont], color="r", linewidth=1, marker='x', markersize=5, label='CUBIC Container throughput')

    pp.grid(linewidth=1, linestyle=":")
    ax4.set_yticks([0, 0.15, 0.3, 0.45])
    ax4.set_yticklabels(["0%", "15%", "30%", "45%"])
    ax4.set_ylim(-0.6, 0.45)

    ax4.set_ylabel('Spurious retx. / retx.')
    # ax4.set_yticks([0, 150, 300, 450, 600, 750], ["0", "150", "300", "450", "600", "750"])
    # ax4.set_yticks([0, 50, 100, 150, 200])
    # ax4.set_yticklabels(["0", "50", "100", "150", "200"])

    pp.savefig(f"{name}.png", dpi=300, bbox_inches='tight', pad_inches=0.03)
    pp.savefig(f"{name}.eps", dpi=300, bbox_inches='tight', pad_inches=0.03)
    pp.savefig(f"{name}.svg", dpi=300, bbox_inches='tight', pad_inches=0.03)

if __name__ == "__main__":
    bbr = {}
    cubic = {}

    parse_dataset(bbr, "../../dataset/noin-bbr-20240415")
    bbr.pop("h0-c1")
    bbr.pop("h0-c2")
    bbr.pop("h0-c3")
    bbr.pop("h0-c4")
    bbr.pop("h0-c5")
    bbr.pop("h0-c6")
    parse_dataset(bbr, "../../dataset-perf/bbr-20240420-c1")
    parse_dataset(bbr, "../../dataset-perf/bbr-20240420-c2")
    parse_dataset(bbr, "../../dataset-perf/bbr-20240420-c3")
    parse_dataset(bbr, "../../dataset-perf/bbr-20240420-c4")
    parse_dataset(bbr, "../../dataset-perf/bbr-20240420-c5")
    parse_dataset(bbr, "../../dataset-perf/bbr-20240420-c6")

    parse_dataset(cubic, "../../dataset/noin-cubic-20240419-h1")
    parse_dataset(cubic, "../../dataset/noin-cubic-20240419-h2")
    parse_dataset(cubic, "../../dataset/noin-cubic-20240419-h3")
    parse_dataset(cubic, "../../dataset/noin-cubic-20240419-h4")
    parse_dataset(cubic, "../../dataset/noin-cubic-20240419-h5")
    parse_dataset(cubic, "../../dataset/noin-cubic-20240419-h6")
    parse_dataset(cubic, "../../dataset-perf/cubic-20240421-c1")
    parse_dataset(cubic, "../../dataset-perf/cubic-20240421-c2")
    parse_dataset(cubic, "../../dataset-perf/cubic-20240421-c3")
    parse_dataset(cubic, "../../dataset-perf/cubic-20240421-c4")
    parse_dataset(cubic, "../../dataset-perf/cubic-20240421-c5")
    parse_dataset(cubic, "../../dataset-perf/cubic-20240421-c6")

    for key in bbr:
        print(key, len(bbr[key]))
    for key in cubic:
        print(key, len(cubic[key]))

    (bbr_host, bbr_cont) = generate_plot_data(bbr)
    (cubic_host, cubic_cont) = generate_plot_data(cubic)

    for item in cubic_cont:
        print(item.sr_ratio)

    exit()
    configure_pp()

    plot(bbr_host, bbr_cont, cubic_host, cubic_cont, "fig2-ratio")