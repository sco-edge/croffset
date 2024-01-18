FROM ubuntu:22.04

RUN apt-get update -y && apt-get install -y git gcc make numactl
RUN git clone https://github.com/google/neper.git
WORKDIR neper

RUN make

ENTRYPOINT ["/bin/bash"]