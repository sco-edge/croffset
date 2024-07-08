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
        retrans = np.mean([run.retrans / 10 for run in runs])
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
    pp.rcParams["figure.figsize"] = (3.4, 1.16)
    pp.rcParams["font.family"] = "Inter"
    pp.rcParams["font.size"] = 6
    pp.rcParams["hatch.linewidth"] = 0.75

def plot(bbr_host, bbr_cont, cubic_host, cubic_cont, name):
    x = np.array([1, 2, 3, 4])

    ax1 = pp.subplot(121)
    pp.subplots_adjust(wspace=0.5)
    p1,  = ax1.plot(x, [item.throughput for item in bbr_host], linewidth=1, marker='o', markersize=3, label='BBR Host throughput')
    p2,  = ax1.plot(x, [item.throughput for item in bbr_cont], linewidth=1, marker='x', markersize=3, label='BBR Container throughput')

    pp.grid(linewidth=1, linestyle=":")
    ax1.set_xlabel('BBR flows')
    ax1.set_ylabel('Throughput (Gbps)')
    ax1.set_xticks([1, 2, 3, 4], ["1", "2", "4", "6"])
    ax1.set_yticks([0, 20, 40, 60, 80, 100])
    ax1.set_yticklabels(["0", "20", "40", "60", "80", "100"])

    ax2 = ax1.twinx()  # instantiate a second axes that shares the same x-axis
    p3 = ax2.bar(x - 0.15, [item.retrans for item in bbr_host], 0.3, label='Host retrans')
    p4 = ax2.bar(x - 0.15, [item.spurious for item in bbr_host], 0.3, label='Host spurious')
    p5 = ax2.bar(x + 0.15, [item.retrans for item in bbr_cont], 0.3, label='Container retrans')
    p6 = ax2.bar(x + 0.15, [item.spurious for item in bbr_cont], 0.3, label='Container spurious', hatch='/////')

    # ax2.set_ylabel('Spurious retx.')
    # ax2.set_yticks([0, 150, 300, 450, 600, 750], ["0", "150", "300", "450", "600", "750"])
    # ax2.set_yticks([0, 150, 300, 450, 600, 750], ["", "", "", "", "", ""])
    # ax2.set_yticks([0, 250, 500, 750, 1000], ["", "", "", "", ""])
    ax2.set_yticks([0, 250, 500, 750, 1000], ["0", "250", "500", "750", "1k"])
    ax2.set_yticklabels(["0", "250", "500", "750", "1k"])
    # box = ax1.get_position()
    # ax1.set_position([box.x0, box.y0 + box.height * 0.1,
    #                 box.width, box.height * 0.9])

    # Put a legend below current axis
    # ax1.legend([p1, p2, p3, p4, p5, p6],
    #            [p1.get_label(), p2.get_label(), p3.get_label(), p4.get_label(), p5.get_label(), p6.get_label()],
    #             loc='upper center', bbox_to_anchor=(0.5, -0.3), ncol=3)
    # ax1.legend([p1, p2, p4, p6],
    #            [p1.get_label(), p2.get_label(), p4.get_label(), p6.get_label()],
    #             loc='upper center', bbox_to_anchor=(0.5, -0.3), ncol=2)


    ax3 = pp.subplot(122)
    p1,  = ax3.plot(x, [item.throughput for item in cubic_host], linewidth=1, marker='o', markersize=3, label='CUBIC Host throughput')
    p2,  = ax3.plot(x, [item.throughput for item in cubic_cont], linewidth=1, marker='x', markersize=3, label='CUBIC Container throughput')

    pp.grid(linewidth=1, linestyle=":")
    
    ax3.set_xlabel('CUBIC flows')
    # ax3.set_ylabel('Throughput (Gbps)')
    ax3.set_xticks([1, 2, 3, 4], ["1", "2", "4", "6"])
    # ax3.set_yticks([0, 20, 40, 60, 80, 100], ["", "", "", "", "", ""])
    ax3.set_yticks([0, 20, 40, 60, 80, 100])
    ax3.set_yticklabels(["0", "20", "40", "60", "80", "100"])

    ax4 = ax3.twinx()  # instantiate a second axes that shares the same x-axis
    p3 = ax4.bar(x - 0.15, [item.retrans for item in cubic_host], 0.3, label='Host retrans')
    p4 = ax4.bar(x - 0.15, [item.spurious for item in cubic_host], 0.3, label='Host spurious')
    p5 = ax4.bar(x + 0.15, [item.retrans for item in cubic_cont], 0.3, label='Container retrans')
    p6 = ax4.bar(x + 0.15, [item.spurious for item in cubic_cont], 0.3, label='Container spurious', hatch='/////')

    ax4.set_ylabel('Spurious retx.')
    # ax4.set_yticks([0, 150, 300, 450, 600, 750], ["0", "150", "300", "450", "600", "750"])
    ax4.set_yticks([0, 50, 100, 150, 200])
    ax4.set_yticklabels(["0", "50", "100", "150", "200"])

    pp.savefig(f"{name}.png", dpi=300, bbox_inches='tight', pad_inches=0.03)
    pp.savefig(f"{name}.eps", dpi=300, bbox_inches='tight', pad_inches=0.03)

if __name__ == "__main__":
    bbr = {}
    cubic = {}

    parse_dataset(bbr, "../../dataset/noin-bbr-20240415")
    bbr.pop("h0-c3")
    bbr.pop("h0-c4")
    bbr.pop("h0-c5")
    bbr.pop("h0-c6")
    parse_dataset(bbr, "../../dataset/noin-bbr-20240415-compl")
    bbr.pop("h0-c2")
    bbr.pop("h0-c3")
    bbr.pop("h0-c4")
    bbr.pop("h0-c5")
    bbr.pop("h0-c6")
    bbr.pop("h0-c1")
    parse_dataset(bbr, "../../dataset-perf/bbr-20240420-c1")
    parse_dataset(bbr, "../../dataset-perf/bbr-20240420-c1-2")
    # parse_dataset(bbr, "../../dataset/noin-bbr-20240417-c2")
    parse_dataset(bbr, "../../dataset-perf/bbr-20240420-c2")
    # parse_dataset(bbr, "../../dataset/noin-bbr-20240418-c3")
    # parse_dataset(bbr, "../../dataset/noin-bbr-20240417-c4")
    parse_dataset(bbr, "../../dataset-perf/bbr-20240420-c4")
    # parse_dataset(bbr, "../../dataset/noin-bbr-20240417-c5")
    parse_dataset(bbr, "../../dataset/noin-bbr-20240419-c6")

    # parse_dataset(cubic, "../../dataset/noin-cubic-20240419-h1")
    parse_dataset(cubic, "../../dataset/noin-cubic-20240419-h1")
    parse_dataset(cubic, "../../dataset/noin-cubic-20240419-h2")
    # parse_dataset(cubic, "../../dataset/noin-cubic-20240419-h3")
    parse_dataset(cubic, "../../dataset/noin-cubic-20240419-h4")
    # parse_dataset(cubic, "../../dataset/noin-cubic-20240419-h5")
    parse_dataset(cubic, "../../dataset/noin-cubic-20240419-h6")
    # parse_dataset(cubic, "../../dataset/noin-cubic-20240419-c1")
    parse_dataset(cubic, "../../dataset-perf/cubic-20240421-c1")
    parse_dataset(cubic, "../../dataset/noin-cubic-20240419-c2")
    # parse_dataset(cubic, "../../dataset/noin-cubic-20240419-c3")
    parse_dataset(cubic, "../../dataset/noin-cubic-20240419-c4")
    # parse_dataset(cubic, "../../dataset/noin-cubic-20240419-c5")
    parse_dataset(cubic, "../../dataset/noin-cubic-20240419-c6")

    for key in bbr:
        print(key, len(bbr[key]))
    for key in cubic:
        print(key, len(cubic[key]))

    (bbr_host, bbr_cont) = generate_plot_data(bbr)
    (cubic_host, cubic_cont) = generate_plot_data(cubic)

    configure_pp()

    plot(bbr_host, bbr_cont, cubic_host, cubic_cont, "sr")