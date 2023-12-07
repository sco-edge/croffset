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
    
def parse(experiment, protocol, saddr, sport, daddr, dport):
    samples = []
    initial_timestamp_ns = 0
    target = protocol + " " + saddr + ":" + sport + "+" + daddr + ":" + dport
    expr = re.compile(r"^(\d{2}:\d{2}:\d{2}\.\d{9})\s(.+?)\sms\s(.+?)\sms\s" + re.escape(target) + r"$")
    with open(f'{experiment}.pping') as file:
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
            # dport = match.group(4)
            # print(l, rtt, min_rtt, dport)
            # print(l, rtt, min_rtt)
            samples.append(((timestamp_ns - initial_timestamp_ns) / 1000, float(rtt)))

    return np.array(samples)

experiment = 'bbr-h-fq_codel-port'
os.chdir(f'../data/{experiment}')
dst_ports = [39762, 39788, 39776, 39768, 39816, 39800]
num = 0
for dst_port in dst_ports:
    name = f'{num}.{experiment}'
    samples = parse(experiment, "TCP", "192.168.2.103", "5001", "192.168.2.102", str(dst_port))
    # for (timestamp_ns, sample) in samples:
    #     # print(timestamp_ns / np.timedelta64(1, "ms"), sample)
    #     print(timestamp_ns / np.timedelta64(1, "s"), sample)

    average = np.average(samples, axis=0)[1]
    print(f'{name} ({dst_port}): {average:.3f}')

    x = list(zip(*samples))[0]
    y = list(zip(*samples))[1]

    figure = plot.figure(figsize=(10, 6))
    xrange = np.array([0, 60000000])
    yrange = np.array([0, 2.5])
    plot.xlim(xrange)
    plot.ylim(yrange)
    plot.xticks(np.linspace(*xrange, 7))
    plot.yticks(np.linspace(*yrange, 11))

    # plot.plot(x, y, 'o-', label='No mask')
    plot.plot(x, y, linewidth=0.5)
    plot.savefig(f'out.pping.{name}.png', dpi=300, bbox_inches='tight', pad_inches=0.05)

    num += 1