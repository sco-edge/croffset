FROM ubuntu:22.04

RUN apt-get update -y && apt-get install -y numactl iperf3

ENTRYPOINT ["iperf3"]