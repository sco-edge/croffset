#!/bin/bash

ethtool -U ens801f0 flow-type udp4 src-ip 192.168.2.102 dst-ip 192.168.2.103 dst-port 8472 action 2

