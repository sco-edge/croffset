#!/bin/bash

ethtool -U ens801f0 flow-type udp4 src-ip 192.168.2.102 src-port 42000 dst-ip 192.168.2.103 action 2
ethtool -U ens801f0 flow-type udp4 src-ip 192.168.2.102 src-port 42001 dst-ip 192.168.2.103 action 3
ethtool -U ens801f0 flow-type udp4 src-ip 192.168.2.102 src-port 42002 dst-ip 192.168.2.103 action 4
ethtool -U ens801f0 flow-type udp4 src-ip 192.168.2.102 src-port 42003 dst-ip 192.168.2.103 action 5
ethtool -U ens801f0 flow-type udp4 src-ip 192.168.2.102 src-port 42004 dst-ip 192.168.2.103 action 6
ethtool -U ens801f0 flow-type udp4 src-ip 192.168.2.102 src-port 42005 dst-ip 192.168.2.103 action 7
ethtool -U ens801f0 flow-type udp4 src-ip 192.168.2.102 src-port 42006 dst-ip 192.168.2.103 action 8
ethtool -U ens801f0 flow-type udp4 src-ip 192.168.2.102 src-port 42007 dst-ip 192.168.2.103 action 9

