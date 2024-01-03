import matplotlib.pyplot as plot
import numpy as np
import re
import os

experiment = 'bbr-1M'
os.chdir(f'../data/{experiment}')
for num in range (0, 1):
    name = f'{num}.{experiment}'
    print(name, end=' ')
    with open(f'f{name}.csv') as file:
        data_rtt = []
        data_ebw = []
        data_delivered = []
        initial_time = 0
        first_port = 0
        for l in file.readlines():
            parsed = l.split(',')

            elapsed = int(parsed[1])
            delivered = int(parsed[2])
            rtt = int(parsed[3])
            port = int(parsed[5])

            if first_port == 0:
                first_port = port
                print(first_port)
            elif first_port != port:
                print("A different port is detected.")
                exit(1)
                
            if initial_time == 0:
                initial_time = elapsed
                data_rtt.append([0, rtt / 1000])
                data_delivered.append([0, delivered * 1500 * 8])
                data_ebw.append([0, (delivered * 1500 * 8) / rtt])
            else:
                data_rtt.append([elapsed - initial_time, rtt / 1000])
                data_delivered.append([elapsed - initial_time, delivered * 1500 * 8])
                data_ebw.append([elapsed - initial_time, (delivered * 1500 * 8) / rtt])
        
        x = list(zip(*data_rtt))[0]
        y = list(zip(*data_rtt))[1]
        print(f"  rtt: {np.average(y):.3f} ({np.std(y):.3f}) [{np.min(y):.3f}, {np.max(y):.3f}]")

        figure = plot.figure(figsize=(10, 6))
        xrange = np.array([0, 60000000])
        yrange = np.array([0, 2.5])
        plot.xlim(xrange)
        plot.ylim(yrange)
        plot.xticks(np.linspace(*xrange, 7))
        plot.yticks(np.linspace(*yrange, 11))

        plot.plot(x, y, linewidth=0.1)
        plot.savefig(f'out.rtt.{name}.png', dpi=300, bbox_inches='tight', pad_inches=0.05)
        # plot.savefig(f'out.rtt.{name}.eps', format='eps', bbox_inches='tight', pad_inches=0.05)

        x = list(zip(*data_delivered))[0]
        y = list(zip(*data_delivered))[1]
        print(f"  del: {np.average(y):.0f} ({np.std(y):.0f}) [{np.min(y):.0f}, {np.max(y):.0f}]")

        figure = plot.figure(figsize=(10, 6))   
        xrange = np.array([0, 60000000])
        yrange = np.array([0, 15000000])
        plot.xlim(xrange)
        plot.ylim(yrange)
        plot.xticks(np.linspace(*xrange, 7))
        plot.yticks(np.linspace(*yrange, 11))

        plot.plot(x, y, linewidth=0.5)
        plot.savefig(f'out.del.{name}.png', dpi=300, bbox_inches='tight', pad_inches=0.05)

        x = list(zip(*data_ebw))[0]
        y = list(zip(*data_ebw))[1]
        print(f"  ebw: {np.average(y):.0f} ({np.std(y):.0f}) [{np.min(y):.0f}, {np.max(y):.0f}]")

        figure = plot.figure(figsize=(10, 6))
        xrange = np.array([0, 60000000])
        yrange = np.array([0, 35000])
        plot.xlim(xrange)
        plot.ylim(yrange)
        plot.xticks(np.linspace(*xrange, 7))
        plot.yticks(np.linspace(*yrange, 11))

        plot.plot(x, y, linewidth=0.5)
        plot.savefig(f'out.ebw.{name}.png', dpi=300, bbox_inches='tight', pad_inches=0.05)