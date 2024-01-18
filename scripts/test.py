#!/usr/bin/python3
import numpy as np
import re
import subprocess
import tempfile
import argparse
import os
import signal

experiment = 't123'
num = 123

subprocess.run(["echo", "test"], stdout=subprocess.DEVNULL)
subprocess.run(["echo", "test"])


print('{0:>{1}} : {2:>}'.format(experiment, len(experiment) + 3, num))