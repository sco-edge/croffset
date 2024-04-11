USER_TARGETS   := pping offset
BPF_TARGETS    := pping_kern offset.bpf

LDLIBS     += -pthread
EXTRA_DEPS += pping.h pping_debug_cleanup.h

LIB_DIR = ./lib

include $(LIB_DIR)/common.mk