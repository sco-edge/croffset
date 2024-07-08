#!/usr/bin/python3
import numpy as np
import matplotlib.pyplot as pp
import matplotlib as mpl

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
    pp.rcParams["font.size"] = 8
    pp.rcParams["hatch.linewidth"] = 0.75

# import matplotlib
# gui_env = [i for i in matplotlib.rcsetup.interactive_bk]
# non_gui_backends = matplotlib.rcsetup.non_interactive_bk
# print ("Non Gui backends are:", non_gui_backends)
# print ("Gui backends I will test for", gui_env)
# for gui in gui_env:
#     print ("testing", gui)
#     try:
#         matplotlib.use(gui,warn=False, force=True)
#         from matplotlib import pyplot as plt
#         print ("    ",gui, "Is Available")
#         plt.plot([1.5,2.0,2.5])
#         fig = plt.gcf()
#         fig.suptitle(gui)
#         plt.show()
#         print ("Using ..... ",matplotlib.get_backend())
#     except:
#         print ("    ",gui, "Not found")


configure_pp()

fig, ax1 = pp.subplots()

# ax1.set_xlabel('CUBIC flows')
# ax1.set_ylabel('Throughput (Gbps)')
# ax1.set_xticks([1, 2, 3, 4, 5, 6])
# ax1.set_yticks([0, 20, 40, 60, 80, 100])

p1 = ax1.bar([1], [1], 0.4, color='C0', label='Host retx.')
p2 = ax1.bar([1], [1], 0.4, color='C2', label='Host spurious retx.', hatch='/////')
p3 = ax1.bar([1], [1], 0.4, color='C1', label='Container retx.')
p4 = ax1.bar([1], [1], 0.4, color='C3', label='Container spurious retx.', hatch='/////')

ax2 = ax1.twinx()  # instantiate a second axes that shares the same x-axis

p5,  = ax2.plot([1], [1], linewidth=1, color='k', marker='o', markersize=3, label='Host spurious retx. ratio')
p6,  = ax2.plot([1], [1], linewidth=1, color='r', marker='x', markersize=5, label='Container spurious retx. ratio')


# legend = pp.legend([p1, p2, p3, p5],
#                    [p1.get_label(), p2.get_label(), p3.get_label(), p5.get_label()], loc=3, framealpha=1, frameon=True, ncol=2)
legend = pp.legend([p1, p3, p2, p4, p5, p6],
                   [p1.get_label(), p3.get_label(), p2.get_label(), p4.get_label(), p5.get_label(), p6.get_label()], loc='upper center', bbox_to_anchor=(0.5, -0.3), ncol=3)

    # ax1.legend([p1, p2, p4, p6],
    #            [p1.get_label(), p2.get_label(), p4.get_label(), p6.get_label()],
    #             loc='upper center', bbox_to_anchor=(0.5, -0.3), ncol=2)

fig = legend.figure
fig.canvas.draw()
bbox  = legend.get_window_extent()
bbox = bbox.from_extents(*(bbox.extents + np.array([-2, -2, 2, 2])))
bbox = bbox.transformed(fig.dpi_scale_trans.inverted())
fig.savefig("fig2-legend.svg", dpi=300, bbox_inches=bbox, pad_inches=0.03)
fig.savefig("fig2-legend.eps", dpi=300, bbox_inches=bbox, pad_inches=0.03)
fig.savefig("fig2-legend.png", dpi=300, bbox_inches=bbox, pad_inches=0.03)
