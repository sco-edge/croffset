#!/bin/bash

ethtool -U ens801f0 flow-type tcp4 src-ip 192.168.2.103 dst-ip 192.168.2.102 src-port 5200 action 2
ethtool -U ens801f0 flow-type tcp4 src-ip 192.168.2.103 dst-ip 192.168.2.102 src-port 5201 action 3
ethtool -U ens801f0 flow-type tcp4 src-ip 192.168.2.103 dst-ip 192.168.2.102 src-port 5202 action 4
ethtool -U ens801f0 flow-type tcp4 src-ip 192.168.2.103 dst-ip 192.168.2.102 src-port 5203 action 5
ethtool -U ens801f0 flow-type tcp4 src-ip 192.168.2.103 dst-ip 192.168.2.102 src-port 5204 action 6
ethtool -U ens801f0 flow-type tcp4 src-ip 192.168.2.103 dst-ip 192.168.2.102 src-port 5205 action 7