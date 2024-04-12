#!/usr/bin/python3
import matplotlib.pyplot as pp
import numpy as np

def plot_rtts(flow, output_name, plot_loss):
    rack_recv = [rtt.rack_recv - flow.init_ts for rtt in flow.rtts]
    trtts = [rtt.trtt for rtt in flow.rtts]
    brtts = [rtt.brtt for rtt in flow.rtts]

    figure = pp.figure(figsize=(10, 6))
    # yrange = np.array([-500, 1000])
    # pp.ylim(yrange)

    pp.scatter(rack_recv, trtts, s=1, label='TRTT')
    pp.scatter(rack_recv, brtts, s=1, label='BRTT')

    if plot_loss == True:
        for (ts_ns, loss) in flow.losses:
            pp.axvline(x=ts_ns - flow.init_ts, ymin=0, ymax=0.02, color='red')
        for (ts_ns, sretrans) in flow.sretrans:
            pp.axvline(x=ts_ns - flow.init_ts, ymin=0, ymax=0.01, color='blue')

    pp.legend(loc='upper right', fontsize=18)
    pp.savefig(f"{output_name}.png", dpi=300, bbox_inches='tight', pad_inches=0.05)

    figure = pp.figure(figsize=(10, 6))
    yrange = np.array([-100, 1000])
    pp.ylim(yrange)
    pp.scatter(rack_recv, trtts, s=1, label='TRTT')
    pp.axhline(y=0, color='r', linewidth=1, linestyle='-')

    if plot_loss == True:
        for (ts_ns, loss) in flow.losses:
            pp.axvline(x=ts_ns - flow.init_ts, ymin=0, ymax=0.02, color='red')
        for (ts_ns, sretrans) in flow.sretrans:
            pp.axvline(x=ts_ns - flow.init_ts, ymin=0, ymax=0.01, color='blue')

    pp.legend(loc='upper right', fontsize=18)
    pp.savefig(f"{output_name}_trtt.png", dpi=300, bbox_inches='tight', pad_inches=0.05)


    figure = pp.figure(figsize=(10, 6))
    yrange = np.array([-100, 1000])
    pp.ylim(yrange)
    pp.scatter(rack_recv, brtts, s=1, label='BRTT')
    pp.axhline(y=0, color='r', linewidth=1, linestyle='-')

    if plot_loss == True:
        for (ts_ns, loss) in flow.losses:
            pp.axvline(x=ts_ns - flow.init_ts, ymin=0, ymax=0.02, color='red')
        for (ts_ns, sretrans) in flow.sretrans:
            pp.axvline(x=ts_ns - flow.init_ts, ymin=0, ymax=0.01, color='blue')

    pp.legend(loc='upper right', fontsize=18)
    pp.savefig(f"{output_name}_brtt.png", dpi=300, bbox_inches='tight', pad_inches=0.05)
    

def plot_offsets(flow, output_name, plot_retrans):
    rack_recv = [rtt.rack_recv - flow.init_ts for rtt in flow.rtts]
    offsets = [rtt.offset for rtt in flow.rtts]
    offsets_send = [rtt.offset_send for rtt in flow.rtts]
    offsets_recv = [rtt.offset_recv for rtt in flow.rtts]

    figure = pp.figure(figsize=(10, 6))
    y_max = max(np.max(offsets), np.max(offsets_send), np.max(offsets_recv))
    y_min = min(np.min(offsets), np.min(offsets_send), np.min(offsets_recv))
    yrange = np.array([y_min, y_max])
    pp.ylim(yrange)
    pp.scatter(rack_recv, offsets, s=1, label='offset')

    if plot_retrans == True:
        for (ts_ns, loss) in flow.losses:
            pp.axvline(x=ts_ns - flow.init_ts, ymin=0, ymax=0.02, color='red')
        for (ts_ns, sretrans) in flow.sretrans:
            pp.axvline(x=ts_ns - flow.init_ts, ymin=0, ymax=0.01, color='blue')
            
    pp.axhline(y=0, color='r', linewidth=1, linestyle='-')

    pp.savefig(f"{output_name}.png", dpi=300, bbox_inches='tight', pad_inches=0.01)

    figure = pp.figure(figsize=(10, 6))
    yrange = np.array([y_min, y_max])
    pp.ylim(yrange)
    # pp.step(flow.offsets[:, 0], flow.offsets[:, 1], where='post', label='offset')
    pp.scatter(rack_recv, offsets_send, s=1, label='offset')

    if plot_retrans == True:
        for (ts_ns, loss) in flow.losses:
            pp.axvline(x=ts_ns - flow.init_ts, ymin=0, ymax=0.02, color='red')
        for (ts_ns, sretrans) in flow.sretrans:
            pp.axvline(x=ts_ns - flow.init_ts, ymin=0, ymax=0.01, color='blue')

    pp.axhline(y=0, color='r', linewidth=1, linestyle='-')

    pp.savefig(f"{output_name}_send.png", dpi=300, bbox_inches='tight', pad_inches=0.01)

    figure = pp.figure(figsize=(10, 6))
    yrange = np.array([y_min, y_max])
    pp.ylim(yrange)
    # pp.step(flow.offsets[:, 0], flow.offsets[:, 1], where='post', label='offset')
    pp.scatter(rack_recv, offsets_recv, s=1, label='offset')

    if plot_retrans == True:
        for (ts_ns, loss) in flow.losses:
            pp.axvline(x=ts_ns - flow.init_ts, ymin=0, ymax=0.02, color='red')
        for (ts_ns, sretrans) in flow.sretrans:
            pp.axvline(x=ts_ns - flow.init_ts, ymin=0, ymax=0.01, color='blue')

    pp.axhline(y=0, color='r', linewidth=1, linestyle='-')

    pp.savefig(f"{output_name}_recv.png", dpi=300, bbox_inches='tight', pad_inches=0.01)

def plot_diff_offsets(flow, output_name, plot_retrans):
    x = []
    diff_offsets = []
    diff_send_offsets = []
    diff_recv_offsets = []
    for i in range(0, len(flow.synced_offsets) - 1):
        # if flow.synced_offsets[i][1] != 0 and  flow.synced_offsets[i][2] != 0 and flow.synced_offsets[i][3] != 0:
        #     x.append(flow.synced_offsets[i][0])
        #     diff_offsets.append((flow.synced_offsets[i + 1][1] - flow.synced_offsets[i][1]) / flow.synced_offsets[i][1]) 
        #     diff_send_offsets.append((flow.synced_offsets[i + 1][2] - flow.synced_offsets[i][2]) / flow.synced_offsets[i][2])
        #     diff_recv_offsets.append((flow.synced_offsets[i + 1][3] - flow.synced_offsets[i][3]) / flow.synced_offsets[i][3])
        
        x.append(flow.synced_offsets[i].tcp_recv - flow.init_ts)
        diff_offsets.append(flow.synced_offsets[i + 1].offset - flow.synced_offsets[i].offset) 
        diff_send_offsets.append(flow.synced_offsets[i + 1].offset_send - flow.synced_offsets[i].offset_send)
        diff_recv_offsets.append(flow.synced_offsets[i + 1].offset_recv - flow.synced_offsets[i].offset_recv)

    figure = pp.figure(figsize=(10, 6))
    # yrange = np.array([-500, 1500])
    # pp.ylim(yrange)
    # pp.step(flow.offsets3[:, 0], flow.offsets3[:, 1], where='post', label='offset')
    pp.scatter(x, diff_offsets, s=1, label='offset')

    if plot_retrans == True:
        for (ts_ns , loss) in flow.losses:
            pp.axvline(x=ts_ns - flow.init_ts, ymin=0, ymax=0.02, color='red')
        for (ts_ns, sretrans) in flow.sretrans:
            pp.axvline(x=ts_ns - flow.init_ts, ymin=0, ymax=0.01, color='blue')

    pp.savefig(f"{output_name}.png", dpi=300, bbox_inches='tight', pad_inches=0.01)

    figure = pp.figure(figsize=(10, 6))
    # yrange = np.array([-500, 1500])
    # pp.ylim(yrange)
    # pp.step(flow.offsets3[:, 0], flow.offsets3[:, 1], where='post', label='offset')
    pp.scatter(x, diff_send_offsets, s=1, label='offset')

    if plot_retrans == True:
        for (ts_ns, loss) in flow.losses:
            pp.axvline(x=ts_ns - flow.init_ts, ymin=0, ymax=0.02, color='red')
        for (ts_ns, sretrans) in flow.sretrans:
            pp.axvline(x=ts_ns - flow.init_ts, ymin=0, ymax=0.01, color='blue')

    pp.savefig(f"{output_name}_send.png", dpi=300, bbox_inches='tight', pad_inches=0.01)

    figure = pp.figure(figsize=(10, 6))
    # yrange = np.array([-500, 1500])
    # pp.ylim(yrange)
    # pp.step(flow.offsets3[:, 0], flow.offsets3[:, 1], where='post', label='offset')
    pp.scatter(x, diff_recv_offsets, s=1, label='offset')

    if plot_retrans == True:
        for (ts_ns, loss) in flow.losses:
            pp.axvline(x=ts_ns - flow.init_ts, ymin=0, ymax=0.02, color='red')
        for (ts_ns, sretrans) in flow.sretrans:
            pp.axvline(x=ts_ns - flow.init_ts, ymin=0, ymax=0.01, color='blue')

    pp.savefig(f"{output_name}_recv.png", dpi=300, bbox_inches='tight', pad_inches=0.01)