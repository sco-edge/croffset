#!/bin/bash

ethtool -U ens801f0 flow-type tcp4 src-ip 192.168.2.102 dst-ip 192.168.2.103 dst-port 5200 action 2
ethtool -U ens801f0 flow-type tcp4 src-ip 192.168.2.102 dst-ip 192.168.2.103 dst-port 5201 action 3
ethtool -U ens801f0 flow-type tcp4 src-ip 192.168.2.102 dst-ip 192.168.2.103 dst-port 5202 action 4
ethtool -U ens801f0 flow-type tcp4 src-ip 192.168.2.102 dst-ip 192.168.2.103 dst-port 5203 action 5
ethtool -U ens801f0 flow-type tcp4 src-ip 192.168.2.102 dst-ip 192.168.2.103 dst-port 5204 action 6
ethtool -U ens801f0 flow-type tcp4 src-ip 192.168.2.102 dst-ip 192.168.2.103 dst-port 5205 action 7
ethtool -U ens801f0 flow-type tcp4 src-ip 192.168.2.102 dst-ip 192.168.2.103 dst-port 5206 action 8
ethtool -U ens801f0 flow-type tcp4 src-ip 192.168.2.102 dst-ip 192.168.2.103 dst-port 5207 action 9

ethtool -U ens801f0 flow-type tcp4 src-ip 192.168.2.102 dst-ip 192.168.2.103 dst-port 5300 action 2
ethtool -U ens801f0 flow-type tcp4 src-ip 192.168.2.102 dst-ip 192.168.2.103 dst-port 5301 action 3
ethtool -U ens801f0 flow-type tcp4 src-ip 192.168.2.102 dst-ip 192.168.2.103 dst-port 5302 action 4
ethtool -U ens801f0 flow-type tcp4 src-ip 192.168.2.102 dst-ip 192.168.2.103 dst-port 5303 action 5
ethtool -U ens801f0 flow-type tcp4 src-ip 192.168.2.102 dst-ip 192.168.2.103 dst-port 5304 action 6
ethtool -U ens801f0 flow-type tcp4 src-ip 192.168.2.102 dst-ip 192.168.2.103 dst-port 5305 action 7
ethtool -U ens801f0 flow-type tcp4 src-ip 192.168.2.102 dst-ip 192.168.2.103 dst-port 5306 action 8
ethtool -U ens801f0 flow-type tcp4 src-ip 192.168.2.102 dst-ip 192.168.2.103 dst-port 5307 action 9