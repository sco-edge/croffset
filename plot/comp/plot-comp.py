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
            # print(run.extype, run.spurious_retrans, run.comp, run.altcomp)
        else:
            data[run.extype].append(run)
            # print(run.extype, run.spurious_retrans, run.comp, run.altcomp)

def generate_plot_data(data):
    r_points = []
    s_points = []
    c_points = []
    a_points = []

    agg_s = 0
    agg_c = 0
    agg_a = 0

    c_gains = []
    a_gains = []

    for i in range(1, 7):
        # extype = f"h{i}-c0"
        # runs = data[extype]
        # r_points.append([run.retrans for run in runs])
        # s_points.append([run.spurious_retrans for run in runs])
        # c_points.append([run.comp for run in runs])
        # a_points.append([run.altcomp for run in runs])
        
        extype = f"h0-c{i}"
        runs = data[extype]
        r_points.extend([run.retrans for run in runs])
        s_points.extend([run.spurious_retrans for run in runs])
        agg_s += np.sum([run.spurious_retrans for run in runs])
        c_points.extend([run.comp for run in runs])
        agg_c += np.sum([run.comp for run in runs])
        a_points.extend([run.altcomp for run in runs])
        agg_a += np.sum([run.altcomp for run in runs])

        c_gains.extend([run.c_gain for run in runs])
        a_gains.extend([run.a_gain for run in runs])

        mean_c_gain = np.mean([item for item in c_gains if item != -1])
        mean_c_gain_without_zeros = np.mean([item for item in c_gains if item != -1 and item != 0])

        mean_a_gain = np.mean([item for item in a_gains if item != -1])
        mean_a_gain_without_zeros = np.mean([item for item in a_gains if item != -1 and item != 0])
    print(f"{agg_s}, {agg_c}, {agg_a}, {agg_c / agg_s * 100 :>.2f}, {agg_a / agg_s * 100:>.2f}, {mean_c_gain * 100:>.2f}, {mean_a_gain * 100:>.2f}, {mean_c_gain_without_zeros * 100 :>.2f}, {mean_a_gain_without_zeros * 100:>.2f}")
    return (r_points, s_points, c_points, a_points)

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
    pp.rcParams["figure.figsize"] = (1.7, 1.16)
    pp.rcParams["font.family"] = "Inter"
    pp.rcParams["font.size"] = 6
    pp.rcParams["hatch.linewidth"] = 0.75

def ecdf(data):
    x_values = np.sort(data)
    y_values = np.arange(1, len(data) + 1) / len(data)
    return x_values, y_values

def plot(r_points, s_points, c_points, a_points, name, is_bbr):
    fig, ax1 = pp.subplots()

    (r_x, r_y) = ecdf(r_points)
    (s_x, s_y) = ecdf(s_points)
    (c_x, c_y) = ecdf(c_points)
    (a_x, a_y) = ecdf(a_points)
    div_s = int(len(s_x) / 5)
    div_c = int(len(c_x) / 5)
    print(div_c)
    # p1,  = ax1.plot(r_x, r_y, linewidth=1, marker='o', markersize=3, label='Host throughput')
    p2,  = ax1.plot(s_x, s_y, linewidth=1, label='tRACK')
    # ax1.plot([s_x[div_s], s_x[div_s * 2], s_x[div_s * 3], s_x[div_s * 4], s_x[div_s * 5], s_x[div_s * 6], s_x[div_s * 7], s_x[div_s * 8], s_x[div_s * 9]],
    #          [s_y[div_s], s_y[div_s * 2], s_y[div_s * 3], s_y[div_s * 4], s_y[div_s * 5], s_y[div_s * 6], s_y[div_s * 7], s_y[div_s * 8], s_y[div_s * 9]],
    #          marker='x', markersize=3, color='C0', linestyle='None')
    ax1.plot([s_x[div_s], s_x[div_s * 2], s_x[div_s * 3], s_x[div_s * 4]],
             [s_y[div_s], s_y[div_s * 2], s_y[div_s * 3], s_y[div_s * 4]],
             marker='x', markersize=3, color='C0', linestyle='None')
    p3,  = ax1.plot(c_x, c_y, linewidth=1, label='bRACK')
    marker_style = dict(color='C1',  marker='o',
                    markersize=3, markerfacecoloralt='tab:red')
    # ax1.plot([c_x[div_c], c_x[div_c * 2], c_x[div_c * 3], c_x[div_c * 4], c_x[div_c * 5], c_x[div_c * 6], c_x[div_c * 7], c_x[div_c * 8], c_x[div_c * 9]],
    #          [c_y[div_c], c_y[div_c * 2], c_y[div_c * 3], c_y[div_c * 4], c_y[div_c * 5], c_y[div_c * 6], c_y[div_c * 7], c_y[div_c * 8], c_y[div_c * 9]],
    #          marker='x', markersize=3, color='C1', linestyle='None')
    ax1.plot([c_x[div_c], c_x[div_c * 2], c_x[div_c * 3], c_x[div_c * 4]],
             [c_y[div_c], c_y[div_c * 2], c_y[div_c * 3], c_y[div_c * 4]],
             fillstyle='none', **marker_style,  linestyle='None')
    p4,  = ax1.plot(a_x, a_y, linewidth=1, label='bRACK-alt')

    xlabel = "# of spurious retransmissions\nof BBR flows" if is_bbr else "# of spurious retransmissions\nof CUBIC flows"
    # ax1.set_xlabel('# of spurious retransmissions')
    ax1.set_xlabel(xlabel)
    ax1.set_ylabel('eCDF')
    ax1.legend()
    ax1.set_xticks([0, 1000, 2000, 3000, 4000], ["0", "1k", "2k", "3k", "4k"])
    # ax1.set_yticks([0, 20, 40, 60, 80, 100])
    pp.ylim(0, 1)
    pp.xlim(0, 3000)
    pp.grid(linewidth=1, linestyle=":")

    # ax2 = ax1.twinx()  # instantiate a second axes that shares the same x-axis
    # p3 = ax2.bar(x - 0.15, [item.retrans for item in host], 0.3, label='Host retrans')
    # p4 = ax2.bar(x - 0.15, [item.spurious for item in host], 0.3, label='Host spurious')
    # p5 = ax2.bar(x + 0.15, [item.retrans for item in cont], 0.3, label='Container retrans')
    # p6 = ax2.bar(x + 0.15, [item.spurious for item in cont], 0.3, label='Container spurious', hatch='////')
    # p6 = ax2.bar(x + 0.15, [item.spurious for item in cont], 0.3, label='Container spurious')

    # ax2.set_ylabel('Spurious retx.')
    # ax2.set_yticks([0, 150, 300, 450, 600, 750], ["0", "150", "300", "450", "600", "750"])

    pp.savefig(f"{name}.png", dpi=300, bbox_inches='tight', pad_inches=0.03)
    pp.savefig(f"{name}.eps", dpi=300, bbox_inches='tight', pad_inches=0.03)
    pp.savefig(f"{name}.svg", dpi=300, bbox_inches='tight', pad_inches=0.03)

if __name__ == "__main__":
    bbr = {}
    cubic = {}

    parse_dataset(bbr, "../../dataset-perf/bbr-20240420-c1")
    parse_dataset(bbr, "../../dataset-perf/bbr-20240420-c2")
    parse_dataset(bbr, "../../dataset-perf/bbr-20240420-c3")
    parse_dataset(bbr, "../../dataset-perf/bbr-20240420-c4")
    parse_dataset(bbr, "../../dataset-perf/bbr-20240420-c5")
    parse_dataset(bbr, "../../dataset-perf/bbr-20240420-c6")

    parse_dataset(cubic, "../../dataset-perf/cubic-20240421-c1")
    parse_dataset(cubic, "../../dataset-perf/cubic-20240421-c2")
    parse_dataset(cubic, "../../dataset-perf/cubic-20240421-c3")
    parse_dataset(cubic, "../../dataset-perf/cubic-20240421-c4")
    parse_dataset(cubic, "../../dataset-perf/cubic-20240421-c5")
    parse_dataset(cubic, "../../dataset-perf/cubic-20240421-c6")

    for key in bbr:
        if len(bbr[key]) > 10:
            print(f"{key} has {len(bbr[key])} items")

    configure_pp()
    (r_points, s_points, c_points, a_points)= generate_plot_data(bbr)
    plot(r_points, s_points, c_points, a_points, "bbr-compensation-v3", True)
    (r_points, s_points, c_points, a_points)= generate_plot_data(cubic)
    plot(r_points, s_points, c_points, a_points, "cubic-compensation-v3", False)