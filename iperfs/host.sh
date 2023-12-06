#!/bin/bash

num=4
tarl=192.168.2.103

port=""
for ((i=0; i < $((num-1)); i++))
do
	port=520$i
	#iperf3 -c $tarl -p $port > out_$i.data &
	iperf3 -c $tarl -p $port | perl -nE 'say "$4,$5" if /^(\[.*\])\s*(.*?)\s*sec\s*(.*?)\s*.Bytes\s*(.*?)\s*.bits\/sec\s*(.*?)\s*sender$/' &
done
iperf3 -c $tarl -p 520$((num-1)) | perl -nE 'say "$4,$5" if /^(\[.*\])\s*(.*?)\s*sec\s*(.*?)\s*.Bytes\s*(.*?)\s*.bits\/sec\s*(.*?)\s*sender$/'

# port=5201
# for ((i=0; i < $((num-1)); i++))
# do
# 	#iperf3 -c $tarl -p $port > out_$i.data &
# 	iperf3 -c $tarl -p $port | perl -nE 'say "$4,$5" if /^(\[.*\])\s*(.*?)\s*sec\s*(.*?)\s*.Bytes\s*(.*?)\s*.bits\/sec\s*(.*?)\s*sender$/' &
# done
# iperf3 -c $tarl -p $port | perl -nE 'say "$4,$5" if /^(\[.*\])\s*(.*?)\s*sec\s*(.*?)\s*.Bytes\s*(.*?)\s*.bits\/sec\s*(.*?)\s*sender$/'