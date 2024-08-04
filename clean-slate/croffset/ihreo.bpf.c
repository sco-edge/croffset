// SPDX-License-Identifier: (LGPL-2.1 OR BSD-2-Clause)
/* Copyright (c) 2020 Facebook */
#include "vmlinux.h"
// #include <linux/bpf.h>
#include <bpf/bpf_helpers.h>
#include <bpf/bpf_tracing.h>
#include <bpf/bpf_core_read.h>
// #include <xdp/parsing_helpers.h>

#include "ihreo.h"

const volatile int cvalue = -1;

struct {
	__uint(type, BPF_MAP_TYPE_HASH);
	__type(key, struct flow_id);
	__type(value, struct offset_info);
	__uint(max_entries, MAP_OFFSETSTATE_SIZE);
} offset_state SEC(".maps");

SEC("kretprobe/fq_dequeue")
int BPF_KRETPROBE(kretprobe_fq_dequeue, struct sk_buff *ret)
{
	struct offset_info *oinfo;
	struct offset_info ninfo = { 0 };

	struct sock *sk = BPF_CORE_READ(ret, sk);
	u64 skb_mstamp_ns = BPF_CORE_READ(ret, skb_mstamp_ns);

	u64 now_ns = bpf_ktime_get_ns();
	u32 daddr = BPF_CORE_READ(ret, sk, __sk_common.skc_daddr);
	u32 saddr = BPF_CORE_READ(ret, sk, __sk_common.skc_rcv_saddr);
	u16 dport = BPF_CORE_READ(ret, sk, __sk_common.skc_dport);
	u16 sport = BPF_CORE_READ(ret, sk, __sk_common.skc_num);
	sport = sport << 8 | sport >> 8; // Only sport loaded as big-endian

	struct flow_id fid = { .daddr = daddr, .saddr = saddr, .dport = dport, .sport = sport };

	/* If either sk or skb_mstamp_ns is invalid, immediate return */
	if ((sk == 0) || (skb_mstamp_ns == 0))
		return 0;

	oinfo = bpf_map_lookup_elem(&offset_state, &fid);

	/* Initial packet for a given flow */
	if (!oinfo) {
		ninfo.last_dequeued = now_ns;
		ninfo.last_edt = skb_mstamp_ns;
		ninfo.ooo_dequeued = 0;
		ninfo.ooo_edt = 0;
		ninfo.cvalue = 0;

		bpf_printk("N 0x%llx:0x%u-0x%llx:0x%u now=%llu, edt=%llu offset=%llu",
					daddr, dport, saddr, sport,
					ninfo.last_dequeued, ninfo.last_edt, ninfo.last_dequeued - ninfo.last_edt);
		bpf_map_update_elem(&offset_state, &fid, &ninfo, BPF_NOEXIST);
	}
	/* The last transmission is OOO */
	else if (oinfo->last_edt > skb_mstamp_ns) {
		/* Update the OOO info */
		ninfo.ooo_dequeued = oinfo->last_dequeued;
		ninfo.ooo_edt = oinfo->last_edt;
		ninfo.last_dequeued = now_ns;
		ninfo.last_edt = skb_mstamp_ns;

		/* 
			* Calculate the cvalue as theta_tx(now) - theta_tx(ooo)
			* where theta_tx(i) = ts_down - ts_up
			* If the calculated value is negative, bound it to zero.
			*/
		ninfo.cvalue = 0;
		if ((now_ns - skb_mstamp_ns) > (ninfo.ooo_dequeued - ninfo.ooo_edt))
			ninfo.cvalue = (now_ns - skb_mstamp_ns) - (oinfo->ooo_dequeued - oinfo->ooo_edt);

		bpf_printk("O 0x%llx:0x%u-0x%llx:0x%u ledt=%llu, nedt=%llu, loffset=%lld, noffset=%lld, cvalue=%d",
					daddr, dport, saddr, sport,
					oinfo->last_edt, skb_mstamp_ns,
					ninfo.ooo_dequeued - ninfo.ooo_edt, // loffset
					now_ns - skb_mstamp_ns, // noffset
					ninfo.cvalue);
		bpf_map_update_elem(&offset_state, &fid, &ninfo, BPF_EXIST);
	}
	/* The last transmission is in-order (normal case) */
	else {
		/* Update only last_dequeued and last_edt */
		// bpf_printk(". 0x%llx:0x%u-0x%llx:0x%u ledt=%llu, nedt=%llu loffset=%lld, noffset=%lld, cvalue=%d",
		// 		   daddr, dport, saddr, sport,
		// 		   oinfo->last_edt, skb_mstamp_ns,
		// 		   oinfo->ooo_dequeued - oinfo->ooo_edt, // loffset
		// 		   now_ns - skb_mstamp_ns, // noffset
		// 		   oinfo->cvalue);
		ninfo.ooo_dequeued = oinfo->ooo_dequeued;
		ninfo.ooo_edt = oinfo->ooo_edt;
		ninfo.last_dequeued = now_ns;
		ninfo.last_edt = skb_mstamp_ns;
		ninfo.cvalue = oinfo->cvalue;

		bpf_map_update_elem(&offset_state, &fid, &ninfo, BPF_EXIST);
	}

	return 0;
}

SEC("xdp")
int ihreo_xdp(struct xdp_md *ctx)
{
    // void *data = (void *)(long)ctx->data;
    // void *data_end = (void *)(long)ctx->data_end;
    // int pkt_sz = data_end - data;

    // bpf_printk("size: %d cvalue is %d", pkt_sz, cvalue);
    return XDP_PASS;
}

char __license[] SEC("license") = "GPL";