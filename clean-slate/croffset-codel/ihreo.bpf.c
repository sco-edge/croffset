// SPDX-License-Identifier: (LGPL-2.1 OR BSD-2-Clause)
/* Copyright (c) 2020 Facebook */
#include "vmlinux.h"
// #include <linux/bpf.h>
#include <bpf/bpf_endian.h>
#include <bpf/bpf_helpers.h>
#include <bpf/bpf_tracing.h>
#include <bpf/bpf_core_read.h>
// #include <linux/if_ether.h>
// #include <xdp/parsing_helpers.h>

#include "ihreo.h"

#ifndef VLAN_MAX_DEPTH
#define VLAN_MAX_DEPTH 4
#endif

#ifndef ETH_P_IP
#define ETH_P_IP 0x0800
#endif

#ifndef ETH_P_8021Q
#define ETH_P_8021Q	0x8100
#endif

#ifndef ETH_P_8021AD
#define ETH_P_8021AD 0x88A8
#endif

const volatile int cvalue = -1;

struct meta_info {
	__u32 mark;
} __attribute__((aligned(4)));

struct {
	__uint(type, BPF_MAP_TYPE_HASH);
	__type(key, struct flow_id);
	__type(value, struct offset_info);
	__uint(max_entries, MAP_OFFSETSTATE_SIZE);
} offset_state SEC(".maps");

static __always_inline int proto_is_vlan(__u16 h_proto)
{
	return !!(h_proto == bpf_htons(ETH_P_8021Q) ||
		  h_proto == bpf_htons(ETH_P_8021AD));
}

/*
 * This struct keeps track of the data and data_end pointers from the xdp_md or
 * __skb_buff contexts, as well as a currently parsed to position kept in pos.
 * Additionally, it also keeps the length of the entire packet, which together
 * with the other members can be used to determine ex. how much data each
 * header encloses.
 */
struct parsing_context {
	void *data;            // Start of eth hdr
	void *data_end;        // End of safe acessible area
	void *pos;             // Position to parse next
	__u32 pkt_len;         // Full packet length (headers + data)
};

static struct flow_id parse_flow_id(struct xdp_md *ctx)
{
	int proto;
	struct flow_id fid = { 0 };
	struct parsing_context pctx = {
		.data = (void *)(long)ctx->data,
		.data_end = (void *)(long)ctx->data_end,
		.pos = pctx.data,
		.pkt_len = pctx.data_end - pctx.data,
	};
	
	/* Step 1: Parse the ethernet header */
	struct ethhdr *eth = pctx.pos;
	struct vlan_hdr *vlh;
	if ((void *)(eth + 1) > pctx.data_end)
		return fid;

	pctx.pos = eth + 1;
	vlh = pctx.pos;
	proto = eth->h_proto;

	/* Use loop unrolling to avoid the verifier restriction on loops;
	 * support up to VLAN_MAX_DEPTH layers of VLAN encapsulation.
	 */
	#pragma unroll
	for (int i = 0; i < VLAN_MAX_DEPTH; i++) {
		if (!proto_is_vlan(proto))
			break;

		if ((void *)(vlh + 1) > pctx.data_end)
			break;

		proto = vlh->h_vlan_encapsulated_proto;
		vlh++;
	}

	pctx.pos = vlh;
	if (proto != bpf_htons(0x0800)) {
		bpf_printk("1");
		return fid;
	}

	/* Step 2: Parse the IPv4 header */
	struct iphdr *iph = pctx.pos;
	int hdrsize;

	if ((void *)(iph + 1) > pctx.data_end) {
		bpf_printk("2");
		return fid;
	}

	hdrsize = iph->ihl * 4;

	/* Variable-length IPv4 header, need to use byte-based arithmetic */
	if (pctx.pos + hdrsize > pctx.data_end) {
		bpf_printk("3");
		return fid;
	}

	pctx.pos += hdrsize;
	proto = iph->protocol;

	/* Step 3: Parse the TCP or UDP (VXLAN) headers */
	/* Step 3-TCP: Parse the TCP header */
	if (proto == IPPROTO_TCP) {
		struct tcphdr *hdr = pctx.pos;

		if ((void *)(hdr + 1) > pctx.data_end)
			return fid;
		
		int len = hdr->doff * 4;
		if ((void *)hdr + len > pctx.data_end)
			return fid;

		pctx.pos = hdr + 1;
		
		/* Since XDP program works on ACK, fid which is used as a key should be reversed */
		fid.saddr = bpf_ntohl(iph->daddr);
		fid.sport = bpf_ntohs(hdr->dest);
		fid.daddr = bpf_ntohl(iph->saddr);
		fid.dport = bpf_ntohs(hdr->source);
		fid.valid = 1;
		return fid;
	}
	/* Step 3-UDP: Parse UDP (VXLAN) */
	else if (proto == IPPROTO_UDP) {
		/* Step 3-UDP-1: Parse the UDP header */
		struct udphdr *udp_hdr = pctx.pos;

		if ((void *)(udp_hdr + 1) > pctx.data_end)
			return fid;
		
		pctx.pos = udp_hdr + 1;

		if (udp_hdr->dest != bpf_htons(8472)) {
			bpf_printk("4");
			return fid;
		}

		/* Step 3-UDP-2: Parse the inner VXLAN header */
		struct vxlanhdr {
		__be32	r1;
		__be32	r2;
		__be32	r3;
		__be32	r4;
		__be32	r5;
		__be16	r6;
		} __attribute__((packed));

		struct vxlanhdr *vxlan_hdr = pctx.pos;
		if ((void *)(vxlan_hdr + 1) > pctx.data_end) {
			bpf_printk("5");
			return fid;
		}

		pctx.pos = vxlan_hdr + 1;
		
		/* Step 3-UDP-3: Parse the inner IPv4 header */
		struct iphdr *ip_hdr = pctx.pos;
		int hdrsize;

		if ((void *)(ip_hdr + 1) > pctx.data_end) {
			bpf_printk("6");
			return fid;
		}

		hdrsize = ip_hdr->ihl * 4;

		/* Variable-length IPv4 header, need to use byte-based arithmetic */
		if (pctx.pos + hdrsize > pctx.data_end) {
			bpf_printk("7");
			return fid;
		}

		pctx.pos += hdrsize;
		if (ip_hdr->protocol != IPPROTO_TCP) {
			bpf_printk("8");
			return fid;
		}
		
		/* Step 3-UDP-4: Parse the inner TCP header */
		struct tcphdr *tcp_hdr = pctx.pos;

		if ((void *)(tcp_hdr + 1) > pctx.data_end) {
			bpf_printk("9");
			return fid;
		}
		
		int len = tcp_hdr->doff * 4;
		if ((void *)tcp_hdr + len > pctx.data_end) {
			bpf_printk("10");
			return fid;
		}

		pctx.pos = tcp_hdr + 1;
		
		fid.saddr = bpf_ntohl(ip_hdr->daddr);
		fid.sport = bpf_ntohs(tcp_hdr->dest);
		fid.daddr = bpf_ntohl(ip_hdr->saddr);
		fid.dport = bpf_ntohs(tcp_hdr->source);
		fid.valid = 1;
		return fid;
	}
	
	return fid;
}

SEC("kretprobe/fq_codel_dequeue")
int BPF_KRETPROBE(kretprobe_fq_codel_dequeue, struct sk_buff *ret)
{
	struct offset_info *oinfo;
	struct offset_info ninfo = { 0 };

	struct sock *sk = BPF_CORE_READ(ret, sk);
	u64 skb_mstamp_ns = BPF_CORE_READ(ret, skb_mstamp_ns);

	u64 now_ns = bpf_ktime_get_ns();
	u32 daddr = bpf_ntohl(BPF_CORE_READ(ret, sk, __sk_common.skc_daddr));
	u32 saddr = bpf_ntohl(BPF_CORE_READ(ret, sk, __sk_common.skc_rcv_saddr));
	u16 dport = bpf_ntohs(BPF_CORE_READ(ret, sk, __sk_common.skc_dport));
	u16 sport = BPF_CORE_READ(ret, sk, __sk_common.skc_num); // Only sport loaded as little-endian

	struct flow_id fid = { .daddr = daddr, .saddr = saddr, .dport = dport, .sport = sport, .valid = 0};
	
	/* If either sk or skb_mstamp_ns is invalid, immediate return */
	if ((sk == 0) || (skb_mstamp_ns == 0)) {
		bpf_printk("N 0x%llx:%u-0x%llx:%u now=%llu, edt=%llu",
			daddr, dport, saddr, sport, now_ns, skb_mstamp_ns);
		return 0;
	}

	oinfo = bpf_map_lookup_elem(&offset_state, &fid);

	/* Initial packet for a given flow */
	if (!oinfo) {
		ninfo.last_dequeued = now_ns;
		ninfo.last_edt = skb_mstamp_ns;
		ninfo.ooo_dequeued = 0;
		ninfo.ooo_edt = 0;
		ninfo.cvalue = 0;

		bpf_printk("N 0x%llx:%u-0x%llx:%u now=%llu, edt=%llu offset=%llu",
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

		bpf_printk("O 0x%llx:%u-0x%llx:%u ledt=%llu, nedt=%llu, loffset=%lld, noffset=%lld, cvalue=%d",
					daddr, dport, saddr, sport,
					oinfo->last_edt, skb_mstamp_ns,
					ninfo.ooo_dequeued - ninfo.ooo_edt, // loffset
					now_ns - skb_mstamp_ns, // noffset
					ninfo.cvalue);
		bpf_map_update_elem(&offset_state, &fid, &ninfo, BPF_EXIST);
	}
	/* The last transmission is in-order (normal case) */
	else {
		/* It generates massive logs in the tracing_pipe */
		bpf_printk(". 0x%llx:%u-0x%llx:%u ledt=%llu, nedt=%llu loffset=%lld, noffset=%lld, cvalue=%d",
				   daddr, dport, saddr, sport,
				   oinfo->last_edt, skb_mstamp_ns,
				   oinfo->ooo_dequeued - oinfo->ooo_edt, // loffset
				   now_ns - skb_mstamp_ns, // noffset
				   oinfo->cvalue);

		/* Update only last_dequeued and last_edt */
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
int xdp_marker(struct xdp_md *ctx)
{
	struct meta_info *meta;
	void *data;
	int ret = bpf_xdp_adjust_meta(ctx, -(int)sizeof(*meta));
	if (ret < 0)
		return XDP_ABORTED;

	data = (void *)(unsigned long)ctx->data;
	meta = (void *)(unsigned long)ctx->data_meta;
	if ((void *)(meta + 1) > data)
		return XDP_ABORTED;

	struct flow_id fid = parse_flow_id(ctx);
	if (fid.valid == 1) {
		struct offset_info *oinfo = bpf_map_lookup_elem(&offset_state, &fid);
		if (oinfo) {
			/* It means to use adaptive cvalue */
			if (cvalue == -1) {
				if (oinfo->cvalue >= 200000) {
					meta->mark = 200;
				} else {
					meta->mark = oinfo->cvalue / 1000;
				}
				bpf_printk("XDP: 0x%llx:%u-0x%llx:%u %d", fid.daddr, fid.dport, fid.saddr, fid.sport, oinfo->cvalue);
			}
			/* Fix it to the constant otherwise. Zero means no compensation */
			else {
				// bpf_printk("Constant XDP: 0x%llx:%u-0x%llx:%u %d", fid.daddr, fid.dport, fid.saddr, fid.sport, cvalue);
				meta->mark = cvalue;
			}
		}
	}
    return XDP_PASS;
}

SEC("tc")
int tc_marker(struct __sk_buff *skb)
{
	void *data      = (void *)(unsigned long)skb->data;
	void *data_meta = (void *)(unsigned long)skb->data_meta;
	struct meta_info *meta = data_meta;

	/* Check XDP gave us some data_meta */
	if ((void *)(meta + 1) > data) {
		skb->mark = 0;
		/* Skip "accept" if no data_meta is avail */
		return 0; /* #define TC_ACT_OK 0 */
	}

	/* Hint: See func tc_cls_act_is_valid_access() for BPF_WRITE access */
	skb->mark = meta->mark; /* Transfer XDP-mark to SKB-mark */

	return 0;
}

char __license[] SEC("license") = "GPL";