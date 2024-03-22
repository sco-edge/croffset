#!/usr/bin/python3
import sys
import json
import numpy as np

# tputs = [10.15, 13.75, 14.13, 14.13, 10.15, 8.29, 14.13, 9.42]
tputs = [28770.9, 30327.4, 30910.5, 31623.8, 22108.3, 23088.8, 23002.3, 21166.0]

squared_sum = 0
sum = 0
for tput in tputs:
    sum += tput
    squared_sum += tput**2

print(sum**2 / (len(tputs) * squared_sum))