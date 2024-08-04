// SPDX-License-Identifier: (LGPL-2.1 OR BSD-2-Clause)
/* Copyright (c) 2020 Facebook */
#include "vmlinux.h"
// #include <linux/bpf.h>
#include <bpf/bpf_helpers.h>
#include <bpf/bpf_tracing.h>
#include <bpf/bpf_core_read.h>
// #include <xdp/parsing_helpers.h>

const volatile int cvalue = -1;

SEC("kretprobe/fq_dequeue")
int BPF_KRETPROBE(kretprobe_fq_dequeue, struct sk_buff *ret)
{
	pid_t pid;
	// ktime_t tstamp = BPF_CORE_READ(ret, tstamp);
	struct sock *sk = BPF_CORE_READ(ret, sk);
	u64 skb_mstamp_ns = BPF_CORE_READ(ret, skb_mstamp_ns);
	u32 daddr = BPF_CORE_READ(ret, sk, __sk_common.skc_daddr);
	u32 saddr = BPF_CORE_READ(ret, sk, __sk_common.skc_rcv_saddr);
	u16 dport = BPF_CORE_READ(ret, sk, __sk_common.skc_dport);
	u16 sport = BPF_CORE_READ(ret, sk, __sk_common.skc_num);
	u64 now_ns = bpf_ktime_get_ns();
	pid = bpf_get_current_pid_tgid() >> 32;
	// bpf_probe_read_kernel(&data, sizeof(data), tstamp);

	u32 cpu = bpf_get_smp_processor_id();

	if (sk != 0 && skb_mstamp_ns != 0) {
		bpf_printk("fq_dequeue returns pid=%d cpu=%d sk=0x%llx skb_mstamp_ns=%llu queueing=%llu %llx:%x to %llx:%x\n", pid, cpu, sk, skb_mstamp_ns, now_ns - skb_mstamp_ns, saddr, sport, daddr, dport);
	}
	return 0;
}

SEC("xdp")
int ihreo_xdp(struct xdp_md *ctx)
{
    void *data = (void *)(long)ctx->data;
    void *data_end = (void *)(long)ctx->data_end;
    int pkt_sz = data_end - data;

    bpf_printk("size: %d cvalue is %d", pkt_sz, cvalue);
    return XDP_PASS;
}

char __license[] SEC("license") = "GPL";