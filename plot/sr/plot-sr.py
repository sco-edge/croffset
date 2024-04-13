#!/usr/bin/python3
import matplotlib as mpl
import matplotlib.pyplot as pp
import numpy as np

import sys, os
sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))

from lib import parse as plotparse

extype_map = plotparse.parse_dataset("../../dataset/no-instrument-bbr-20240413")

for extype in extype_map:
    print(f"{extype}: {len(extype_map[extype])}")