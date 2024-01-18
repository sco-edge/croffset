FROM alpine

RUN apk add --no-cache git
RUN apk add --no-cache linux-headers
RUN apk add --no-cache libc-dev
RUN apk add --no-cache gcc
RUN apk add --no-cache make

RUN git clone https://github.com/google/neper.git
WORKDIR neper

RUN make

ENTRYPOINT ["./tcp_rr"]
