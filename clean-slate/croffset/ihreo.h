#define NS_PER_SECOND 1000000000UL
#define NS_PER_MS 1000000UL
#define MS_PER_S 1000UL
#define S_PER_DAY (24 * 3600UL)

#define MAP_OFFSETSTATE_SIZE 4096UL

struct flow_id {
    __u32 daddr;
    __u32 saddr;
    __u16 dport;
    __u16 sport;
    __u16 valid;
    __u16 preserved;
};

struct offset_info {
    __u64 last_dequeued;
    __u64 last_edt;
    __u64 ooo_dequeued;
    __u64 ooo_edt;
    __u32 cvalue;
};