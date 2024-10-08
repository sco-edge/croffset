/* SPDX-License-Identifier: GPL-2.0-or-later */
static const char *__doc__ =
	"ihreo - Compensating in-host RTT offsets for reducing spurious rtx";

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

static const char *get_libbpf_strerror(int err)
{
	static char buf[200];
	libbpf_strerror(err, buf, sizeof(buf));
	return buf;
}

static const struct option options[] = {
	{ "help",      no_argument,       NULL, 'h'},
	{ "interface", required_argument, NULL, 'i'},
	{ "constant",  required_argument, NULL, 'c'}, // Fix cvalue to a given constant (us)
	{ 0, 0, NULL, 0 }
};

static void print_usage(char *argv[])
{
	printf("\nDOCUMENTATION:\n%s\n", __doc__);
	printf("\n");
	printf(" Usage: %s (options-see-below)\n", argv[0]);
	printf(" Listing options:\n");
	for (int i = 0; options[i].name != 0; i++) {
		printf(" --%-12s", options[i].name);
		if (options[i].flag != NULL)
			printf(" flag (internal value: %d)",
			       *options[i].flag);
		else if (isalnum(options[i].val))
			printf(" short-option: -%c", options[i].val);
		printf("\n");
	}
	printf("\n");
}

static int parse_bounded_long(long long *res, const char *str, long long low,
			      long long high, const char *name)
{
	char *endptr;
	errno = 0;

	*res = strtoll(str, &endptr, 10);
	if (endptr == str || strlen(str) != endptr - str) {
		fprintf(stderr, "%s %s is not a valid integer\n", name, str);
		return -EINVAL;
	}

	if (errno == ERANGE) {
		fprintf(stderr, "%s %s overflowed\n", name, str);
		return -ERANGE;
	}

	if (*res < low || *res > high) {
		fprintf(stderr, "%s must be in range [%lld, %lld]\n", name, low,
			high);
		return -ERANGE;
	}

	return 0;
}

static int parse_arguments(int argc, char *argv[], struct ihreo_config *config)
{
	int err, opt, len;
	long long user_int;

	config->ifindex = 0;

	while ((opt = getopt_long(argc, argv, "hi:c:",
				  options, NULL)) != -1) {
		switch (opt) {
		case 'i':
			len = strlen(optarg);
			if (len >= IF_NAMESIZE) {
				fprintf(stderr, "interface name too long\n");
				return -EINVAL;
			}
			memcpy(config->ifname, optarg, len);
			config->ifname[len] = '\0';

			config->ifindex = if_nametoindex(config->ifname);
			if (config->ifindex == 0) {
				err = -errno;
				fprintf(stderr,
					"Could not get index of interface %s: %s\n",
					config->ifname,
					get_libbpf_strerror(err));
				return err;
			}
			break;
		case 'c':
			err = parse_bounded_long(&user_int, optarg, 0,
						   2000000,
						   "cvalue");
			if (err)
				return -EINVAL;

			config->cvalue = user_int;
			break;
		case 'h':
			printf("HELP:\n");
			print_usage(argv);
			exit(0);
		default:
			fprintf(stderr, "Unknown option %s\n", argv[optind]);
			return -EINVAL;
		}
	}

	if (config->ifindex == 0) {
		fprintf(stderr,
			"An interface (-i or --interface) must be provided\n");
		return -EINVAL;
	}

	return 0;
}

int main(int argc, char *argv[])
{
	int err = 0;
	char log_buf[64 * 1024];

	struct ihreo_config config = { .cvalue = -1 };

	// Detect if running as root
	if (geteuid() != 0) {
		fprintf(stderr, "This program must be run as root.\n");
		return EXIT_FAILURE;
	}

	err = parse_arguments(argc, argv, &config);
	if (err) {
		fprintf(stderr, "Failed parsing arguments:  %s\n",
			get_libbpf_strerror(err));
		print_usage(argv);
		return EXIT_FAILURE;
	}
	
	LIBBPF_OPTS(bpf_object_open_opts, opts,
		.kernel_log_buf = log_buf,
		.kernel_log_size = sizeof(log_buf),
		.kernel_log_level = 1,
	);

	struct ihreo_bpf *skel = ihreo_bpf__open_opts(&opts);
	if (!skel) {
		fprintf(stderr, "ihreo_bpf__open_opts() failed\n");
		return EXIT_FAILURE;
	}

	skel->rodata->cvalue = config.cvalue;

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
	DECLARE_LIBBPF_OPTS(bpf_tc_hook, hook, .ifindex = config.ifindex,
			.attach_point = 1 << 0); /* BPF_TC_INGRESS = 1 << 0 */
	DECLARE_LIBBPF_OPTS(bpf_tc_opts, tc_ingress_opts);

	err = bpf_tc_hook_create(&hook);
	if (err) {
		/* EEXIST happens maybe due to cilium */
		if (err == -EEXIST) {
			fprintf(stderr, "bpf_tc_hook_create() failed EEXIST\n");
		} else if (err) {
			fprintf(stderr, "bpf_tc_hook_create() failed\n");
			return EXIT_FAILURE;
		}
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
	struct bpf_link *link = bpf_program__attach_xdp(skel->progs.xdp_marker, config.ifindex);
	if (!link) {
		fprintf(stderr, "bpf_program__attach_xdp() failed\n");
		return EXIT_FAILURE;
	}

	getchar();
	ihreo_bpf__destroy(skel);
	printf("Removed\n");

	return 0;
}