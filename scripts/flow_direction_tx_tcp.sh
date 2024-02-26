#!/bin/bash

ethtool -U ens801f0 flow-type tcp4 src-ip 192.168.2.103 dst-ip 192.168.2.102 dst-port 42000 action 2
ethtool -U ens801f0 flow-type tcp4 src-ip 192.168.2.103 dst-ip 192.168.2.102 dst-port 42001 action 3
ethtool -U ens801f0 flow-type tcp4 src-ip 192.168.2.103 dst-ip 192.168.2.102 dst-port 42002 action 4
ethtool -U ens801f0 flow-type tcp4 src-ip 192.168.2.103 dst-ip 192.168.2.102 dst-port 42003 action 5
ethtool -U ens801f0 flow-type tcp4 src-ip 192.168.2.103 dst-ip 192.168.2.102 dst-port 42004 action 6
ethtool -U ens801f0 flow-type tcp4 src-ip 192.168.2.103 dst-ip 192.168.2.102 dst-port 42005 action 7
ethtool -U ens801f0 flow-type tcp4 src-ip 192.168.2.103 dst-ip 192.168.2.102 dst-port 42006 action 8
ethtool -U ens801f0 flow-type tcp4 src-ip 192.168.2.103 dst-ip 192.168.2.102 dst-port 42007 action 9

ethtool -U ens801f0 flow-type tcp4 src-ip 192.168.2.103 dst-ip 192.168.2.102 dst-port 43000 action 2
ethtool -U ens801f0 flow-type tcp4 src-ip 192.168.2.103 dst-ip 192.168.2.102 dst-port 43001 action 3
ethtool -U ens801f0 flow-type tcp4 src-ip 192.168.2.103 dst-ip 192.168.2.102 dst-port 43002 action 4
ethtool -U ens801f0 flow-type tcp4 src-ip 192.168.2.103 dst-ip 192.168.2.102 dst-port 43003 action 5
ethtool -U ens801f0 flow-type tcp4 src-ip 192.168.2.103 dst-ip 192.168.2.102 dst-port 43004 action 6
ethtool -U ens801f0 flow-type tcp4 src-ip 192.168.2.103 dst-ip 192.168.2.102 dst-port 43005 action 7
ethtool -U ens801f0 flow-type tcp4 src-ip 192.168.2.103 dst-ip 192.168.2.102 dst-port 43006 action 8
ethtool -U ens801f0 flow-type tcp4 src-ip 192.168.2.103 dst-ip 192.168.2.102 dst-port 43007 action 9