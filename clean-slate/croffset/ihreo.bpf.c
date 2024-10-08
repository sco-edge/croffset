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

static __always_inline __u16
csum_fold_helper(__u64 csum)
{
    int i;
#pragma unroll
    for (i = 0; i < 4; i++)
    {
        if (csum >> 16)
            csum = (csum & 0xffff) + (csum >> 16);
    }
    return ~csum;
}

static __always_inline __u16
iph_csum(struct iphdr *iph)
{
    iph->check = 0;
    unsigned long long csum = bpf_csum_diff(0, 0, (unsigned int *)iph, sizeof(struct iphdr), 0);
    return csum_fold_helper(csum);
}

static __always_inline __u16
tcph_csum(void *pseudo_tcph, struct tcphdr *tcph, unsigned int len)
{
    // tcph->check = 0;
    unsigned long long csum = bpf_csum_diff(0, 0, (unsigned int *)pseudo_tcph, len - 2, 0);
    return csum_fold_helper(csum);
}

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
	if (proto != bpf_htons(0x0800))
		return fid;

	/* Step 2: Parse the IPv4 header */
	struct iphdr *iph = pctx.pos;
	int hdrsize;

	if ((void *)(iph + 1) > pctx.data_end)
		return fid;

	hdrsize = iph->ihl * 4;

	/* Variable-length IPv4 header, need to use byte-based arithmetic */
	if (pctx.pos + hdrsize > pctx.data_end)
		return fid;

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

		if (udp_hdr->dest != bpf_htons(8472))
			return fid;

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
		if ((void *)(vxlan_hdr + 1) > pctx.data_end)
			return fid;

		pctx.pos = vxlan_hdr + 1;
		
		/* Step 3-UDP-3: Parse the inner IPv4 header */
		struct iphdr *ip_hdr = pctx.pos;
		int hdrsize;

		if ((void *)(ip_hdr + 1) > pctx.data_end)
			return fid;

		hdrsize = ip_hdr->ihl * 4;

		/* Variable-length IPv4 header, need to use byte-based arithmetic */
		if (pctx.pos + hdrsize > pctx.data_end)
			return fid;

		pctx.pos += hdrsize;
		if (ip_hdr->protocol != IPPROTO_TCP)
			return fid;
		
		/* Step 3-UDP-4: Parse the inner TCP header */
		struct tcphdr *tcp_hdr = pctx.pos;

		if ((void *)(tcp_hdr + 1) > pctx.data_end)
			return fid;
		
		int len = tcp_hdr->doff * 4;
		if ((void *)tcp_hdr + len > pctx.data_end)
			return fid;

		pctx.pos = tcp_hdr + 1;
		
		fid.saddr = bpf_ntohl(ip_hdr->daddr);
		fid.sport = bpf_ntohs(tcp_hdr->dest);
		fid.daddr = bpf_ntohl(ip_hdr->saddr);
		fid.dport = bpf_ntohs(tcp_hdr->source);
		fid.valid = 2;
		// bpf_printk("Parsed 0x%llx:%u-0x%llx:%u %llx",
		// 	fid.daddr, fid.dport, fid.saddr, fid.sport, pctx.pos);
		return fid;
	}
	
	return fid;
}

int parse_flow_id_mark_to(struct xdp_md *ctx)
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
		return 0;

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
	if (proto != bpf_htons(0x0800))
		return 0;

	/* Step 2: Parse the IPv4 header */
	struct iphdr *iph = pctx.pos;
	int hdrsize;

	if ((void *)(iph + 1) > pctx.data_end)
		return 0;

	hdrsize = iph->ihl * 4;

	/* Variable-length IPv4 header, need to use byte-based arithmetic */
	if (pctx.pos + hdrsize > pctx.data_end)
		return 0;

	pctx.pos += hdrsize;
	proto = iph->protocol;

	/* Step 3: Parse the TCP or UDP (VXLAN) headers */
	/* Step 3-TCP: Parse the TCP header */
	if (proto == IPPROTO_TCP) {
		struct tcphdr *hdr = pctx.pos;
		
		if ((void *)(hdr + 1) > pctx.data_end)
			return 0;
		
		int len = hdr->doff * 4;
		if ((void *)hdr + len > pctx.data_end)
			return 0;

		pctx.pos = hdr + 1;
		
		/* Since XDP program works on ACK, fid which is used as a key should be reversed */
		fid.saddr = bpf_ntohl(iph->daddr);
		fid.sport = bpf_ntohs(hdr->dest);
		fid.daddr = bpf_ntohl(iph->saddr);
		fid.dport = bpf_ntohs(hdr->source);
		fid.valid = 1;
		// bpf_printk("TCP 0x%llx:%u-0x%llx:%u",
		// 			fid.daddr, fid.dport, fid.saddr, fid.sport);
		return 0;
	}
	/* Step 3-UDP: Parse UDP (VXLAN) */
	else if (proto == IPPROTO_UDP) {
		/* Step 3-UDP-1: Parse the UDP header */
		struct udphdr *udp_hdr = pctx.pos;
		
		if ((void *)(udp_hdr + 1) > pctx.data_end)
			return 0;
		
		pctx.pos = udp_hdr + 1;

		if (udp_hdr->dest != bpf_htons(8472) && udp_hdr->dest != bpf_htons(6081))
			return 0;

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
		if ((void *)(vxlan_hdr + 1) > pctx.data_end)
			return 0;

		pctx.pos = vxlan_hdr + 1;
		
		/* Step 3-UDP-3: Parse the inner IPv4 header */
		struct iphdr *ip_hdr = pctx.pos;
		int hdrsize;

		if ((void *)(ip_hdr + 1) > pctx.data_end)
			return 0;

		hdrsize = ip_hdr->ihl * 4;

		/* Variable-length IPv4 header, need to use byte-based arithmetic */
		if (pctx.pos + hdrsize > pctx.data_end)
			return 0;

		pctx.pos += hdrsize;
		if (ip_hdr->protocol != IPPROTO_TCP)
			return 0;
		
		/* Step 3-UDP-4: Parse the inner TCP header */
		struct tcphdr *tcp_hdr = pctx.pos;

		if ((void *)(tcp_hdr + 1) > pctx.data_end)
			return 0;
		
		int len = tcp_hdr->doff * 4;
		if ((void *)tcp_hdr + len > pctx.data_end)
			return 0;

		pctx.pos = tcp_hdr + 1;
		
		fid.saddr = bpf_ntohl(ip_hdr->daddr);
		fid.sport = bpf_ntohs(tcp_hdr->dest);
		fid.daddr = bpf_ntohl(ip_hdr->saddr);
		fid.dport = bpf_ntohs(tcp_hdr->source);
		fid.valid = 2;
		// bpf_printk("Parsed 0x%llx:%u-0x%llx:%u %llx",
		// 	fid.daddr, fid.dport, fid.saddr, fid.sport, pctx.pos);
		
		void *data = (void *)(unsigned long)ctx->data;
		void *data_end = (void *)(unsigned long)ctx->data_end;

		u32 *bytes = (u32 *)(tcp_hdr + 1);
		if ((void *)(bytes + 3) > data_end)
			return 0;
			
		if (bytes[0] == 0x0a080101) {
			unsigned int len = data_end - data;
			if (len != 116) {
				return 0;
			}
			if ((void *)ip_hdr + len - 64 > data_end)
				return 0;

			struct offset_info *oinfo = bpf_map_lookup_elem(&offset_state, &fid);
			if (oinfo) {
				bytes[0] = 0x0afd0101; // #define TCPOPT_IHREO	253
				/* It means to use adaptive cvalue */
				if (cvalue == -1) {
					if (oinfo->cvalue >= 200000) {
						bytes[1] = 0xc8000000; // 0xc8 = 200
					} else {
						// bpf_printk("Marked 0x%llx:%u-0x%llx:%u %u",
						// 			fid.daddr, fid.dport, fid.saddr, fid.sport, oinfo->cvalue / 1000);
						bytes[1] = ((u32)(oinfo->cvalue / 1000) << 24);
					}
				}
				/* Fix it to the constant otherwise. Zero means no compensation */
				else {
					bytes[1] = ((u32)cvalue << 24);
				}
				u16 newcsum = tcph_csum((void *)ip_hdr + 8, tcp_hdr, len - 72);
				tcp_hdr->check = newcsum;
			}
		}
	}
	return 0;
}

SEC("kretprobe/fq_dequeue")
int BPF_KRETPROBE(kretprobe_fq_dequeue, struct sk_buff *ret)
{
	struct offset_info *oinfo;
	struct offset_info ninfo = { 0 };

	u32 daddr;
	u32 saddr;
	u16 dport;
	u16 sport;

	struct sock *sk = BPF_CORE_READ(ret, sk);
	u64 skb_mstamp_ns = BPF_CORE_READ(ret, skb_mstamp_ns);

	u64 now_ns = bpf_ktime_get_ns();
	daddr = bpf_ntohl(BPF_CORE_READ(ret, sk, __sk_common.skc_daddr));
	saddr = bpf_ntohl(BPF_CORE_READ(ret, sk, __sk_common.skc_rcv_saddr));
	dport = bpf_ntohs(BPF_CORE_READ(ret, sk, __sk_common.skc_dport));
	sport = BPF_CORE_READ(ret, sk, __sk_common.skc_num); // Only sport loaded as little-endian

	if (sk == 0) {
		const u8 *p;
		u8 byte[88];

		bpf_core_read(&p, sizeof(p), &ret->data);
		// bpf_probe_read_kernel_str(byte, sizeof(byte), p+10);
		bpf_probe_read_kernel(byte, sizeof(byte), p+36);

		if (byte[0] == 0x21 && byte[1] == 0x18) {
			// u16 data = (byte[0] << 8) + byte[1];
			saddr = (byte[40] << 24) + (byte[41] << 16) + (byte[42] << 8) + byte[43];
			daddr = (byte[44] << 24) + (byte[45] << 16) + (byte[46] << 8) + byte[47];
			sport = (byte[48] << 8) + byte[49];
			dport = (byte[50] << 8) + byte[51];
		} else {
			return 0;
		}
		// bpf_printk("Egress 0x%llx:%u-0x%llx:%u %llu", daddr, dport, saddr, sport, skb_mstamp_ns);
		// 	bpf_printk("Data1: %llx %llx %llx %llx %llx %llx %llx %llx",
		// 			byte[0], byte[1], byte[2], byte[3],
		// 			byte[4], byte[5], byte[6], byte[7]);
		// 	bpf_printk("Data2: %llx %llx %llx %llx %llx %llx %llx %llx",
		// 			byte[40], byte[41], byte[42], byte[43],
		// 			byte[44], byte[45], byte[46], byte[47]);
		// 	bpf_printk("Data3: %llx %llx %llx %llx %llx %llx %llx %llx",
		// 			byte[48], byte[49], byte[50], byte[51],
		// 			byte[52], byte[53], byte[54], byte[55]);
		// }
		// bpf_printk("Data2: %llx %llx %llx %llx %llx %llx %llx %llx",
		// 			byte[8], byte[9], byte[10], byte[11],
		// 			byte[12], byte[13], byte[14], byte[15]);
		// bpf_printk("Data3: %llx %llx %llx %llx %llx %llx %llx %llx",
		// 			byte[16], byte[17], byte[18], byte[19],
		// 			byte[20], byte[21], byte[22], byte[23]);
		// bpf_printk("Data4: %llx %llx %llx %llx %llx %llx %llx %llx",
		// 			byte[24], byte[25], byte[26], byte[27],
		// 			byte[28], byte[29], byte[30], byte[31]);
		// u8 byte[160];
		// int err = bpf_core_read(&byte, 160, &ret->data);
		// if (err) {
		// 	return 0;
		// }
		// int i = 3;
		// bpf_printk("Data1: %llx %llx %llx %llx %llx %llx %llx %llx",
		// 			byte[i*40+0], byte[i*40+1], byte[i*40+2], byte[i*40+3],
		// 			byte[i*40+4], byte[i*40+5], byte[i*40+6], byte[i*40+7]);
		// bpf_printk("Data2: %llx %llx %llx %llx %llx %llx %llx %llx",
		// 			byte[i*40+8], byte[i*40+9], byte[i*40+10], byte[i*40+11],
		// 			byte[i*40+12], byte[i*40+13], byte[i*40+14], byte[i*40+15]);
		// bpf_printk("Data3: %llx %llx %llx %llx %llx %llx %llx %llx",
		// 			byte[i*40+16], byte[i*40+17], byte[i*40+18], byte[i*40+19],
		// 			byte[i*40+20], byte[i*40+21], byte[i*40+22], byte[i*40+23]);
		// bpf_printk("Data4: %llx %llx %llx %llx %llx %llx %llx %llx",
		// 			byte[i*40+24], byte[i*40+25], byte[i*40+26], byte[i*40+27],
		// 			byte[i*40+28], byte[i*40+29], byte[i*40+30], byte[i*40+31]);
		// bpf_printk("Data5: %llx %llx %llx %llx %llx %llx %llx %llx",
		// 			byte[i*40+32], byte[i*40+33], byte[i*40+34], byte[i*40+35],
		// 			byte[i*40+36], byte[i*40+37], byte[i*40+38], byte[i*40+39]);


		// u8 byte;
		// int err = bpf_core_read(&byte, 2, &ret->data);
		// if (err) {
		// 	bpf_printk("Error");
		// 	return 0;
		// }
		// bpf_printk("Data: %llx", byte);
		// return 0;
	}
	
	/* If skb_mstamp_ns is invalid, immediate return */
	if (skb_mstamp_ns == 0) {
		return 0;
	}

	/* We only deal with VXLAN-encapsulated segments whose valid field is 2 */
	struct flow_id fid = { .daddr = daddr, .saddr = saddr, .dport = dport, .sport = sport, .valid = 2};
	oinfo = bpf_map_lookup_elem(&offset_state, &fid);

	/* Initial packet for a given flow */
	if (!oinfo) {
		ninfo.last_dequeued = now_ns;
		ninfo.last_edt = skb_mstamp_ns;
		ninfo.ooo_dequeued = 0;
		ninfo.ooo_edt = 0;
		ninfo.cvalue = 0;

		// bpf_printk("N 0x%llx:%u-0x%llx:%u now=%llu, edt=%llu offset=%llu",
		// 			daddr, dport, saddr, sport,
		// 			ninfo.last_dequeued, ninfo.last_edt, ninfo.last_dequeued - ninfo.last_edt);
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
		// bpf_printk(". 0x%llx:%u-0x%llx:%u ledt=%llu, nedt=%llu loffset=%lld, noffset=%lld, cvalue=%d",
		// 		   daddr, dport, saddr, sport,
		// 		   oinfo->last_edt, skb_mstamp_ns,
		// 		   oinfo->ooo_dequeued - oinfo->ooo_edt, // loffset
		// 		   now_ns - skb_mstamp_ns, // noffset
		// 		   oinfo->cvalue);

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

// SEC("xdp")
// int xdp_marker(struct xdp_md *ctx)
// {
// 	struct meta_info *meta;
// 	void *data;
//     void *data_end;
// 	int ret = bpf_xdp_adjust_meta(ctx, -(int)sizeof(*meta));
// 	if (ret < 0)
// 		return XDP_ABORTED;

// 	data = (void *)(unsigned long)ctx->data;
// 	data_end = (void *)(unsigned long)ctx->data_end;
// 	meta = (void *)(unsigned long)ctx->data_meta;
// 	if ((void *)(meta + 1) > data)
// 		return XDP_ABORTED;
		
//     // Parse Ethernet header
//     struct ethhdr *eth = data;

// 	struct flow_id fid = parse_flow_id(ctx);
// 	if (fid.valid != 2) {
// 		return XDP_PASS;
// 	}

//     // Cast to IP header
//     struct iphdr *ip = (struct iphdr *)(eth + 1);

//     // Calculate IP header length
//     int ip_hdr_len = ip->ihl * 4;
//     if (ip_hdr_len < sizeof(struct iphdr)) {
//         return XDP_PASS;
//     }

//     // Ensure IP header is within packet bounds
//     if ((void *)ip + ip_hdr_len > data_end) {
//         return XDP_PASS;
//     }

// 	// Parse UDP header
//     struct udphdr *udp = (struct udphdr *)((unsigned char *)ip + ip_hdr_len);

//     // Ensure UDP header is within packet bounds
//     if ((void *)(udp + 1) > data_end) {
//         return XDP_PASS;
//     }

//     // Define the number of bytes you want to capture from the TCP header
// 	if (udp->dest != bpf_htons(8472)) {
// 		return XDP_PASS;
// 	}

// 	struct vxlanhdr {
// 	__be32	r1;
// 	__be32	r2;
// 	__be32	r3;
// 	__be32	r4;
// 	__be32	r5;
// 	__be16	r6;
// 	} __attribute__((packed));

// 	struct vxlanhdr *vxlan_hdr = (struct vxlanhdr *)(udp + 1);
// 	if ((void *)(vxlan_hdr + 1) > data_end)
// 		return XDP_PASS;
	
// 	/* Step 3-UDP-3: Parse the inner IPv4 header */
// 	struct iphdr *ip_hdr = (struct iphdr *)(vxlan_hdr + 1);
// 	int hdrsize;

// 	if ((void *)(ip_hdr + 1) > data_end)
// 		return XDP_PASS;

// 	hdrsize = ip_hdr->ihl * 4;

// 	/* Variable-length IPv4 header, need to use byte-based arithmetic */
// 	if ((void *)ip_hdr + hdrsize > data_end)
// 		return XDP_PASS;

// 	if (ip_hdr->protocol != IPPROTO_TCP)
// 		return XDP_PASS;
	
// 	/* Step 3-UDP-4: Parse the inner TCP header */
// 	struct tcphdr *tcp_hdr = (struct tcphdr *)((unsigned char *)ip_hdr + hdrsize);

// 	if ((void *)(tcp_hdr + 1) > data_end)
// 		return XDP_PASS;
	
// 	int len = tcp_hdr->doff * 4;
// 	if ((void *)tcp_hdr + len > data_end)
// 		return XDP_PASS;

// 	u16 *bytes = (u16 *)(tcp_hdr + 1);
// 	if ((void *)(bytes + 6) > data_end)
// 		return XDP_PASS;

// 	if (bytes[0] == 0x0101 && bytes[1] == 0x0a08) {
// 		bytes[1] = 0x0afd; // #define TCPOPT_IHREO	253
// 		bytes[2] = 0x0000;
// 		bytes[3] = 0x1234;
		
// 		unsigned int len = data_end - data;
// 		if (len != 116) {
// 			return XDP_PASS;
// 		}
// 		if ((void *)ip_hdr + len - 64 > data_end)
// 			return XDP_PASS;

// 		u16 newcsum = tcph_csum((void *)ip_hdr + 8, tcp_hdr, len - 72);
// 		bpf_printk("%lx %lx", tcp_hdr->check, newcsum);
// 		tcp_hdr->check = newcsum;
// 	}
	
// 	return XDP_PASS;
// }

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

	int res = parse_flow_id_mark_to(ctx);
    return XDP_PASS;
}


// SEC("xdp")
// int xdp_marker(struct xdp_md *ctx)
// {
// 	struct meta_info *meta;
// 	void *data;
// 	int ret = bpf_xdp_adjust_meta(ctx, -(int)sizeof(*meta));
// 	if (ret < 0)
// 		return XDP_ABORTED;

// 	data = (void *)(unsigned long)ctx->data;
// 	meta = (void *)(unsigned long)ctx->data_meta;
// 	if ((void *)(meta + 1) > data)
// 		return XDP_ABORTED;

// 	struct flow_id fid = parse_flow_id(ctx);
// 	if (fid.valid == 2) {
// 		struct offset_info *oinfo = bpf_map_lookup_elem(&offset_state, &fid);
// 		if (oinfo) {
// 			/* It means to use adaptive cvalue */
// 			if (cvalue == -1) {
// 				if (oinfo->cvalue >= 200000) {
// 					meta->mark = 200;
// 				} else {
// 					meta->mark = oinfo->cvalue / 1000;
// 				}
// 				// bpf_printk("XDP: 0x%llx:%u-0x%llx:%u %d",
// 				// 	fid.daddr, fid.dport, fid.saddr, fid.sport, oinfo->cvalue
// 			}
// 			/* Fix it to the constant otherwise. Zero means no compensation */
// 			else {
// 				// bpf_printk("CDP: 0x%llx:%u-0x%llx:%u %d", fid.daddr, fid.dport, fid.saddr, fid.sport, oinfo->cvalue);
// 				meta->mark = cvalue;
// 			}
// 		} else {
// 			// bpf_printk("NDP: 0x%llx:%u-0x%llx:%u %d", fid.daddr, fid.dport, fid.saddr, fid.sport);
// 		}
// 	} else {
// 		// bpf_printk("VDP: 0x%llx:%u-0x%llx:%u %d", fid.daddr, fid.dport, fid.saddr, fid.sport);
// 	}
//     return XDP_PASS;
// }

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
		// bpf_printk("no mark");
		return 0; /* #define TC_ACT_OK 0 */
	}

	/* Hint: See func tc_cls_act_is_valid_access() for BPF_WRITE access */
	skb->mark = meta->mark; /* Transfer XDP-mark to SKB-mark */
	// bpf_printk("skb->mark: %d", skb->mark);

	return 0;
}

char __license[] SEC("license") = "GPL";