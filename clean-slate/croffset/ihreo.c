/* SPDX-License-Identifier: GPL-2.0-or-later */
// static const char *__doc__ =
// 	"ihreo-comp - Compensating in-host RTT offsets for reducing spurious rtx";

#include <bpf/bpf.h>
#include <bpf/libbpf.h>
#include <linux/if_link.h>
#include <net/if.h> // For if_nametoindex
#include <arpa/inet.h> // For inet_ntoa and ntohs

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <unistd.h>
#include <getopt.h>
#include <stdbool.h>
#include <ctype.h>
#include <sys/resource.h> // For setting rlmit
#include <time.h>
#include <pthread.h>
#include <sys/signalfd.h>
#include <sys/timerfd.h>
#include <sys/epoll.h>
#include <linux/unistd.h>
#include <linux/membarrier.h>
#include <limits.h>
#include <signal.h>

#include "ihreo.skel.h"
#include "ihreo.h" //common structs for user-space and BPF parts

int main(int argc, char *argv[])
{
	int err = 0;
	char log_buf[64 * 1024];
	LIBBPF_OPTS(bpf_object_open_opts, opts,
		.kernel_log_buf = log_buf,
		.kernel_log_size = sizeof(log_buf),
		.kernel_log_level = 1,
	);

	// Detect if running as root
	if (geteuid() != 0) {
		fprintf(stderr, "This program must be run as root.\n");
		return EXIT_FAILURE;
	}

	char* ifname = "ens801f0";
	int ifindex = if_nametoindex(ifname);

	struct ihreo_bpf *skel = ihreo_bpf__open_opts(&opts);
	if (!skel) {
		fprintf(stderr, "ihreo_bpf__open_opts() failed\n");
		return EXIT_FAILURE;
	}

	skel->rodata->cvalue = 123;

	err = ihreo_bpf__load(skel);
	// for (int i = 0; i < sizeof(log_buf); i++) {
	// 	if (log_buf[i] == 0 && log_buf[i+1] == 0) {
	// 		break;
	// 	}
	// 	printf("%c", log_buf[i]);
	// }
	if (err) {
		fprintf(stderr, "ihreo_bpf__load() failed: %d\n", err);
		return EXIT_FAILURE;
	}

	/* Attach at kretprobe/fq_dequeue */
	// It seems to do not attach xdp programs
	err = ihreo_bpf__attach(skel);
	if (err) {
		fprintf(stderr, "ihreo_bpf__attach failed: %d\n", err);
		return EXIT_FAILURE;
	}

	/* Attach at TC ingress */
	int prog_fd;
	DECLARE_LIBBPF_OPTS(bpf_tc_hook, hook, .ifindex = ifindex,
			.attach_point = 1 << 0); /* BPF_TC_INGRESS = 1 << 0 */
	DECLARE_LIBBPF_OPTS(bpf_tc_opts, tc_ingress_opts);

	err = bpf_tc_hook_create(&hook);
	if (err) {
		if (err == -EEXIST) {
			fprintf(stderr, "bpf_tc_hook_create() failed (EEXIST).\n");
		} else {
			fprintf(stderr, "bpf_tc_hook_create() failed\n");
		}
		return EXIT_FAILURE;
	}

	prog_fd = bpf_program__fd(
		bpf_object__find_program_by_name(skel->obj, "tc_marker"));
	if (prog_fd < 0) {
		fprintf(stderr, "bpf_object__find_program_by_name() failed\n");
		return EXIT_FAILURE;
	}

	tc_ingress_opts.prog_fd = prog_fd;
	tc_ingress_opts.prog_id = 0;
	err = bpf_tc_attach(&hook, &tc_ingress_opts);
	if (err) {
		fprintf(stderr, "bpf_tc_attach() failed\n");
		return EXIT_FAILURE;
	}

	/* Attach at XDP */
	struct bpf_link *link = bpf_program__attach_xdp(skel->progs.xdp_marker, ifindex);
	if (!link) {
		fprintf(stderr, "bpf_program__attach_xdp() failed\n");
		return EXIT_FAILURE;
	}

	getchar();
	ihreo_bpf__destroy(skel);
	printf("Removed\n");

	return 0;
}
