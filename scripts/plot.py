#!/usr/bin/python3
import matplotlib.pyplot as pp
import numpy as np
import croffset

def plot_graphs(fbrtt, ftrtt, flows):
    for i in range(0, minlen):
        figure = pp.figure(figsize=(10, 6))
        xrange = np.array([0, max_time])
        yrange = np.array([0, peak])
        pp.xlim(xrange)
        pp.ylim(yrange)
        pp.xticks(np.linspace(*xrange, 7))
        pp.yticks(np.linspace(*yrange, 11))

        if not args.no_bpftrace:
            (bx, by, bz, bw) = bpftrace_map[i]
            pp.plot(bx, by, linewidth=0.1)

        (ex, ey) = epping_map[i]
        pp.plot(ex, ey, linewidth=0.5)
        
        name = f'{i}.{experiment}'
        output = f"rtt.{name}.png"
        pp.savefig(output, dpi=300, bbox_inches='tight', pad_inches=0.05)

        # Distributions
        dist_max = max(max(by), max(ey))
        dist_min = min(min(by), min(ey))
        bins = np.linspace(dist_min, dist_max, int(dist_max - dist_min) + 1)
        figure = pp.figure(figsize=(10, 6))
        pp.hist(by, bins, alpha=0.5, label='bpftrace', density=True)
        pp.hist(ey, bins, alpha=0.5, label='epping', density=True)
            
        output = f"dist.{i}.{experiment}.png"
        pp.savefig(output, dpi=300, bbox_inches='tight', pad_inches=0.05)

        # Estimated bandwidth
        if not args.no_bpftrace:
            (bx, by, bz, bw) = bpftrace_map[i]

            figure = pp.figure(figsize=(10, 6))
            xrange = np.array([0, max_time])
            yrange = np.array([0, max(bw)])
            pp.xlim(xrange)
            pp.ylim(yrange)
            pp.xticks(np.linspace(*xrange, 7))
            pp.yticks(np.linspace(*yrange, 11))
    
            pp.plot(bx, bw, linewidth=0.1)
            name = f'{i}.{experiment}'
            output = f"ewb.{name}.png"
            pp.savefig(output, dpi=300, bbox_inches='tight', pad_inches=0.05)

def plot_rtts(flow, output_name):
    figure = pp.figure(figsize=(10, 6))
    # brtts_x = flow.brtts[:, 0]
    # brtts_y = flow.brtts[:, 1]
    yrange = np.array([0, 500])
    pp.ylim(yrange)
    pp.plot(flow.brtts[:, 0], flow.brtts[:, 1], linewidth=0.5)
    pp.plot(flow.trtts[:, 0], flow.trtts[:, 1], linewidth=0.1)
    pp.savefig(output_name, dpi=300, bbox_inches='tight', pad_inches=0.05)

def plot_offsets(flow, output_name):
    # print(flow.offsets[:, 0])
    # print("##")
    # print(flow.offsets[:, 1])
    figure = pp.figure(figsize=(10, 6))
    yrange = np.array([-500, 1500])
    pp.ylim(yrange)
    pp.step(flow.offsets[:, 0], flow.offsets[:, 1], where='post', label='offset')
    pp.savefig(output_name, dpi=300, bbox_inches='tight', pad_inches=0.05)
