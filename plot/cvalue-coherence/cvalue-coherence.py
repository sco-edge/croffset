#!/usr/bin/python3
import matplotlib as mpl
import matplotlib.pyplot as pp
import numpy as np
import scipy.stats as stats

import sys, os
# sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))

# from lib import parse as plotparse

def parse_data(experiment):
    path = os.path.join(os.getcwd(), "..", "..", "output", experiment, f"rack.{experiment}.out")
    if not os.path.exists(path):
        print(f"{path} does not exist.")
        return None
    
    data = []
    with open(path, "r") as file:
        init_ts = 0
        lines = file.readlines()
        for line in lines:
            tokens = line.split()
            if len(tokens) < 2:
                continue
            if tokens[1] != "tcp_ack()":
                continue
            
            ts = int(tokens[0])
            cvalue = int(tokens[4], 16)
            
            if init_ts == 0:
                init_ts = ts

            if cvalue < 3072 and ts - init_ts < 2_000_000_000 and ts - init_ts >= 1_000_000_000:
                data.append((ts - init_ts, cvalue))

    return data

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
    pp.rcParams["figure.figsize"] = (34, 3.32)
    pp.rcParams["font.family"] = "Inter"
    pp.rcParams["font.size"] = 6
    pp.rcParams["hatch.linewidth"] = 0.75

def plot(data, name):
    fig, ax1 = pp.subplots()
    (x, y) = zip(*data)
    # p1,  = ax1.plot(x, y, linewidth=1, marker='o', markersize=3, label='Host throughput')
    p1,  = ax1.step(x, y)

    ax1.set_xlabel('BBR flows')
    ax1.set_ylabel('Throughput (Gbps)')
    # ax1.set_xticks([1, 2, 3, 4, 5, 6])
    # ax1.set_yticks([0, 20, 40, 60, 80, 100])

    pp.savefig(f"{name}.png", dpi=300, bbox_inches='tight', pad_inches=0.03)
    # pp.savefig(f"{name}.eps", dpi=300, bbox_inches='tight', pad_inches=0.03)
    # pp.savefig(f"{name}.svg", dpi=300, bbox_inches='tight', pad_inches=0.03)

if __name__ == "__main__":

    configure_pp()
    data = parse_data(sys.argv[1])
    plot(data, "cvalues")