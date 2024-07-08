#!/usr/bin/python3
import matplotlib as mpl
import matplotlib.pyplot as pp
import numpy as np
import scipy.stats as stats

import sys, os
sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))

from lib import parse as plotparse

class PlotInput:
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

        (extype, offsets) = plotparse.parse_run_offset(path, experiment)
        if not offsets:
            continue

        if not data.get(extype):
            data[extype] = []
        data[extype].extend(offsets)

        # cflows.append((trtt, brtt, offset, offset_send, offset_recv, sr))


def generate_plot_data(data):
    trtt = []
    brtt = []
    offset = []
    offset_std = []
    offset_send = []
    offset_send_std = []
    offset_recv = []
    offset_recv_std = []
    sr = []

    for i in range(1, 7):
        extype = f"h0-c{i}"
        if not extype in data:
            continue
        offsets = data[extype]
        for item in offsets:
            if item[8] > 2000:
                continue
            trtt.append(item[0])
            brtt.append(item[1])
            offset.append(item[2])
            offset_std.append(item[3])
            offset_send.append(item[4])
            offset_send_std.append(item[5])
            offset_recv.append(item[6])
            offset_recv_std.append(item[7])
            sr.append(item[8])

    return (trtt, brtt, offset, offset_std, offset_send, offset_send_std, offset_recv, offset_recv_std, sr)

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

def ecdf(data):
    x_values = np.sort(data)
    y_values = np.arange(1, len(data) + 1) / len(data)
    return x_values, y_values

def sort_lists(a, b, c, d):
    sorted_indices = sorted(range(len(a)), key=lambda i: a[i])
    sorted_a = [a[i] for i in sorted_indices]
    sorted_b = [b[i] for i in sorted_indices]
    sorted_c = [c[i] for i in sorted_indices]
    sorted_d = [d[i] for i in sorted_indices]
    return sorted_a, sorted_b, sorted_c, sorted_d

def plot_single(trtt, brtt, offset, offset_std, offset_send, offset_send_std, offset_recv, offset_recv_std, sr,
         trtt2, brtt2, offset2, offset_std2, offset_send2, offset_send_std2, offset_recv2, offset_recv_std2, sr2, name):
    
    ax1 = pp.subplot(111)
    pp.subplots_adjust(wspace=0.5)

    sr_x = range(len(sr))
    (offset_y, offset_send_y, offset_recv_y, sr_y) = sort_lists(offset_std, offset_send_std, offset_recv_std, sr)

    print(np.mean(offset))
    p1 = ax1.bar(sr_x, sr_y)
    xlabel = "Flow index"
    ax1.set_xlabel(xlabel)
    ax1.set_yticks([0, 500, 1000, 1500], ["0", "500", "1k", "1.5k"])
    pp.grid(linewidth=1, linestyle=":")
    ax1.set_ylabel('# of spurious retx.')
    pp.ylim(0, 3000)

    ax2 = ax1.twinx()
    div_s = int(len(sr_x) / 15)
    p2 = ax2.plot(sr_x, offset_y, linewidth=0.5, color='r', label='Total offset')
    ax2.plot([sr_x[div_s], sr_x[div_s * 2], sr_x[div_s * 3], sr_x[div_s * 4], sr_x[div_s * 5], sr_x[div_s * 6], sr_x[div_s * 7],
              sr_x[div_s * 8], sr_x[div_s * 9], sr_x[div_s * 10], sr_x[div_s * 11], sr_x[div_s * 12], sr_x[div_s * 13], sr_x[div_s * 14], sr_x[div_s * 15]],
             [offset_y[div_s], offset_y[div_s * 2], offset_y[div_s * 3], offset_y[div_s * 4], offset_y[div_s * 5], offset_y[div_s * 6], offset_y[div_s * 7],
              offset_y[div_s * 8], offset_y[div_s * 9], offset_y[div_s * 10], offset_y[div_s * 11], offset_y[div_s * 12], offset_y[div_s * 13], offset_y[div_s * 14], offset_y[div_s * 15]],
             marker='x', markersize=3, color='r', linestyle='None')

    p3 = ax2.plot(sr_x, offset_send_y, linewidth=0.5, color='k', label='Send offset')
    p4 = ax2.plot(sr_x, offset_recv_y, linewidth=0.5, color='b', label='Receive offset')
    pp.xlim(0, 200)
    pp.ylim(-60, 60)
    ax2.set_yticks([0, 20, 40, 60])
    pp.grid(linewidth=1, linestyle=":")

    legend_elements = [mpl.lines.Line2D([0], [0], color='r', marker='x', lw=0.8, markersize=3, label='Total offset'),
                       mpl.patches.Patch(color='C0', label='Spurious retx.'),
                       mpl.lines.Line2D([0], [0], color='k', lw=0.8, label='Send offset'),
                       mpl.lines.Line2D([0], [0], color='b', lw=0.8, label='Receive offset')]
    ax2.legend(handles=legend_elements, loc=2, ncol=3, fontsize=4)

    # ax2.legend(ncol=3, fontsize=5)
    
    # ax1.legend()
    # # ax1.set_yticks([0, 20, 40, 60, 80, 100])
    # pp.ylim(0, 1)

    # ax2 = ax1.twinx()  # instantiate a second axes that shares the same x-axis
    # p3 = ax2.bar(x - 0.15, [item.retrans for item in host], 0.3, label='Host retrans')
    # p4 = ax2.bar(x - 0.15, [item.spurious for item in host], 0.3, label='Host spurious')
    # p5 = ax2.bar(x + 0.15, [item.retrans for item in cont], 0.3, label='Container retrans')
    # p6 = ax2.bar(x + 0.15, [item.spurious for item in cont], 0.3, label='Container spurious', hatch='////')
    # p6 = ax2.bar(x + 0.15, [item.spurious for item in cont], 0.3, label='Container spurious')

    # ax2.set_ylabel('Standard deviation of offsets')
    # ax2.set_yticks([0, 150, 300, 450, 600, 750], ["0", "150", "300", "450", "600", "750"])

    ax2.set_ylabel('Std. deviation of offsets')

    pp.savefig(f"{name}.png", dpi=300, bbox_inches='tight', pad_inches=0.03)
    pp.savefig(f"{name}.eps", dpi=300, bbox_inches='tight', pad_inches=0.03)
    pp.savefig(f"{name}.svg", dpi=300, bbox_inches='tight', pad_inches=0.03)

def plot(trtt, brtt, offset, offset_std, offset_send, offset_send_std, offset_recv, offset_recv_std, sr,
         trtt2, brtt2, offset2, offset_std2, offset_send2, offset_send_std2, offset_recv2, offset_recv_std2, sr2, name):
    
    ax1 = pp.subplot(131)
    pp.subplots_adjust(wspace=0.5)

    sr_x = range(len(sr))
    (offset_y, offset_send_y, offset_recv_y, sr_y) = sort_lists(offset_std, offset_send_std, offset_recv_std, sr)

    ax1.bar(sr_x, sr_y)
    xlabel = "Flow #"
    ax1.set_xlabel(xlabel)
    ax1.set_yticks([0, 500, 1000, 1500, 2000, 2500], ["0", "500", "1k", "1.5k", "2k", "2.5k"])
    pp.grid(linewidth=1, linestyle=":")
    ax1.set_ylabel('# of spurious retx.')

    ax2 = ax1.twinx() 
    ax2.plot(sr_x, offset_y, linewidth=0.3, color='r')
    ax2.plot(sr_x, offset_send_y, linewidth=0.3, color='k')
    ax2.plot(sr_x, offset_recv_y, linewidth=0.3, color='b')
    pp.ylim(-100, 100)
    # ax2.set_yticks([0, 500, 1000, 1500, 2000, 2500], ["0", "500", "1k", "1.5k", "2k", "2.5k"])
    
    # ax1.legend()
    # # ax1.set_yticks([0, 20, 40, 60, 80, 100])
    # pp.ylim(0, 1)

    # ax2 = ax1.twinx()  # instantiate a second axes that shares the same x-axis
    # p3 = ax2.bar(x - 0.15, [item.retrans for item in host], 0.3, label='Host retrans')
    # p4 = ax2.bar(x - 0.15, [item.spurious for item in host], 0.3, label='Host spurious')
    # p5 = ax2.bar(x + 0.15, [item.retrans for item in cont], 0.3, label='Container retrans')
    # p6 = ax2.bar(x + 0.15, [item.spurious for item in cont], 0.3, label='Container spurious', hatch='////')
    # p6 = ax2.bar(x + 0.15, [item.spurious for item in cont], 0.3, label='Container spurious')

    # ax2.set_ylabel('Standard deviation of offsets')
    # ax2.set_yticks([0, 150, 300, 450, 600, 750], ["0", "150", "300", "450", "600", "750"])

    ax3 = pp.subplot(132)

    sr_x = range(len(sr))
    (offset_send_y, offset_y, offset_recv_y, sr_y) = sort_lists(offset_send_std, offset_std, offset_recv_std, sr)

    ax3.bar(sr_x, sr_y)
    xlabel = "Flow #"
    ax3.set_xlabel(xlabel)
    ax3.set_yticks([0, 500, 1000, 1500, 2000, 2500], ["0", "500", "1k", "1.5k", "2k", "2.5k"])
    pp.grid(linewidth=1, linestyle=":")
    ax3.set_ylabel('# of spurious retx.')

    ax4 = ax3.twinx() 
    ax4.plot(sr_x, offset_y, linewidth=0.3, color='r')
    ax4.plot(sr_x, offset_send_y, linewidth=0.3, color='k')
    ax4.plot(sr_x, offset_recv_y, linewidth=0.3, color='b')
    pp.ylim(-100, 100)

    ax5= pp.subplot(133)

    sr_x = range(len(sr))
    (offset_recv_y, offset_y, offset_send_y, sr_y) = sort_lists(offset_recv_std, offset_std, offset_send_std, sr)

    ax5.bar(sr_x, sr_y)
    xlabel = "Flow #"
    ax5.set_xlabel(xlabel)
    ax5.set_yticks([0, 500, 1000, 1500, 2000, 2500], ["0", "500", "1k", "1.5k", "2k", "2.5k"])
    pp.grid(linewidth=1, linestyle=":")
    ax5.set_ylabel('# of spurious retx.')

    ax6 = ax5.twinx() 
    ax6.plot(sr_x, offset_y, linewidth=0.3, color='r')
    ax6.plot(sr_x, offset_send_y, linewidth=0.3, color='k')
    ax6.plot(sr_x, offset_recv_y, linewidth=0.3, color='b')
    pp.ylim(-100, 100)


    ax4.set_ylabel('Standard deviation of offsets')

    pp.savefig(f"{name}.png", dpi=300, bbox_inches='tight', pad_inches=0.03)
    # pp.savefig(f"{name}.eps", dpi=300, bbox_inches='tight', pad_inches=0.03)
    # pp.savefig(f"{name}.svg", dpi=300, bbox_inches='tight', pad_inches=0.03)

if __name__ == "__main__":
    bbr = {}
    cubic = {}

    parse_dataset(bbr, "../../dataset-perf/bbr-20240420-c1")
    # parse_dataset(bbr, "../../dataset-perf/bbr-20240420-c1-2")
    # parse_dataset(bbr, "../../dataset-perf/bbr-20240420-c1-3")
    # parse_dataset(bbr, "../../dataset-perf/bbr-20240420-c1-4")
    # parse_dataset(bbr, "../../dataset-perf/bbr-20240420-c1-5")
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

    # for key in bbr:
    #     if len(bbr[key]) >= 10:
    #         print(f"{key} has {len(bbr[key])} items")

    # for key in cubic:
    #     if len(cubic[key]) >= 10:
    #         print(f"{key} has {len(cubic[key])} items")

    configure_pp()
    (trtt, brtt, offset, offset_std, offset_send, offset_send_std, offset_recv, offset_recv_std, sr)= generate_plot_data(bbr)
    (trtt2, brtt2, offset2, offset_std2, offset_send2, offset_send_std2, offset_recv2, offset_recv_std2, sr2)= generate_plot_data(cubic)

    # plot(trtt, brtt, offset, offset_std, offset_send, offset_send_std, offset_recv, offset_recv_std, sr,
    #      trtt2, brtt2, offset2, offset_std2, offset_send2, offset_send_std2, offset_recv2, offset_recv_std2, sr2, "disc")
    
    plot_single(trtt, brtt, offset, offset_std, offset_send, offset_send_std, offset_recv, offset_recv_std, sr,
         trtt2, brtt2, offset2, offset_std2, offset_send2, offset_send_std2, offset_recv2, offset_recv_std2, sr2, "fig4-offsets")