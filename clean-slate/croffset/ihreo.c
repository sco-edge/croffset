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
#include <signal.h> // For detecting Ctrl-C
#include <sys/resource.h> // For setting rlmit
#include <time.h>
#include <pthread.h>
#include <sys/signalfd.h>
#include <sys/timerfd.h>
#include <sys/epoll.h>
#include <linux/unistd.h>
#include <linux/membarrier.h>
#include <limits.h>

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

	// It seems to do not attach xdp programs
	err = ihreo_bpf__attach(skel);
	if (err) {
		fprintf(stderr, "ihreo_bpf__attach failed: %d\n", err);
		return EXIT_FAILURE;
	}

	struct bpf_link *link = bpf_program__attach_xdp(skel->progs.ihreo_xdp, ifindex);
	if (!link) {
		fprintf(stderr, "bpf_program__attach_xdp() failed\n");
		return EXIT_FAILURE;
	}

	getchar();
	ihreo_bpf__destroy(skel);
	printf("Removed\n");

	return 0;
}
