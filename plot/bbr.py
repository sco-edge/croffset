import matplotlib.pyplot as plot
import numpy as np
import re
import os

# 06:43:26.534972038 0.401727 ms 0.027272 ms TCP 192.168.2.103:5201+192.168.2.102:46382

def str_to_ns(time_str):
    h, m, s = time_str.split(":")
    int_s, ns = s.split(".")
    ns = map(lambda t, unit: np.timedelta64(t, unit), [h,m,int_s,ns.ljust(9, '0')],['h','m','s','ns'])
    return sum(ns)
    
def parse(protocol, saddr, sport, daddr):
    samples = []
    initial_timestamp_ns = 0
    target_with_random_dport = protocol + " " + saddr + ":" + sport + "+" + daddr
    expr = re.compile(r"^(\d{2}:\d{2}:\d{2}\.\d{9})\s(.+?)\sms\s(.+?)\sms\s" + re.escape(target_with_random_dport) + r":(.+?)$")
    with open("host2.data") as file:
        lines = file.readlines()
        for l in lines:
            match = expr.search(l)
            if match == None:
                continue
            
            timestamp_ns = str_to_ns(match.group(1))

            if initial_timestamp_ns == 0:
                initial_timestamp_ns = timestamp_ns
                
            rtt = match.group(2)
            min_rtt = match.group(3)
            dport = match.group(4)
            # print(l, rtt, min_rtt, dport)
            samples.append((timestamp_ns - initial_timestamp_ns, float(rtt)))

    return np.array(samples)

name = 'bbr-n-1gbps'
os.chdir('../data')
with open(f'f.{name}.csv') as file:
    data_rtt = []
    data_ebw = []
    data_delivered = []
    initial_time = 0
    for l in file.readlines():
        parsed = l.split(',')

        elapsed = int(parsed[1])
        delivered = int(parsed[2])
        rtt = int(parsed[3])
        if initial_time == 0:
            initial_time = elapsed
            data_rtt.append([0, rtt / 1000])
            data_delivered.append([0, delivered * 1500 * 8])
            data_ebw.append([0, (delivered * 1500 * 8) / rtt])
        else:
            data_rtt.append([elapsed - initial_time, rtt / 1000])
            data_delivered.append([elapsed - initial_time, delivered * 1500 * 8])
            data_ebw.append([elapsed - initial_time, (delivered * 1500 * 8) / rtt])
    
    # for item in data:
    #     print(item[0], item[1])

    x = list(zip(*data_rtt))[0]
    y = list(zip(*data_rtt))[1]

    figure = plot.figure(figsize=(10, 6))

    print("rtt:", np.average(y), np.min(y), np.max(y))
    # plot.plot(x, y, linewidth=0.5)
    # plot.savefig(f'out.rtt.{name}.png', dpi=300, bbox_inches='tight', pad_inches=0.05)

    x = list(zip(*data_delivered))[0]
    y = list(zip(*data_delivered))[1]

    figure = plot.figure(figsize=(10, 6))

    print("del:", np.average(y), np.min(y), np.max(y))
    # plot.plot(x, y, linewidth=0.5)
    # plot.savefig(f'out.del.{name}.png', dpi=300, bbox_inches='tight', pad_inches=0.05)

    x = list(zip(*data_ebw))[0]
    y = list(zip(*data_ebw))[1]

    figure = plot.figure(figsize=(10, 6))

    print("ebw:", np.average(y), np.min(y), np.max(y))
    # plot.plot(x, y, linewidth=0.5)
    # plot.savefig(f'out.ebw.{name}.png', dpi=300, bbox_inches='tight', pad_inches=0.05)

# samples = parse("TCP", "192.168.2.103", "5201", "192.168.2.102")
# for (timestamp_ns, sample) in samples:
#     # print(timestamp_ns / np.timedelta64(1, "ms"), sample)
#     print(timestamp_ns / np.timedelta64(1, "s"), sample)

# print(np.average(samples, axis=0))

# x = list(zip(*samples))[0]
# y = list(zip(*samples))[1]

# figure = plot.figure(figsize=(10, 6))
# ax = figure.add_subplot(1, 1, 1)
# plot.plot(x, y, 'o-', label='No mask')
# plot.savefig(f'host2.png', dpi=300, bbox_inches='tight', pad_inches=0.05)