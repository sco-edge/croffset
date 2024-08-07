# SPDX-License-Identifier: (LGPL-2.1 OR BSD-2-Clause)
OUTPUT := $(abspath .output)
CLANG ?= clang
LLVM_STRIP ?= llvm-strip
BPFTOOL_SRC := $(abspath ./bpftool/src)
BPFTOOL_OUTPUT ?= $(abspath $(OUTPUT)/bpftool)
BPFTOOL ?= $(BPFTOOL_OUTPUT)/bootstrap/bpftool
LIBBPF_SRC := $(abspath ./libbpf/src)
LIBBPF_OBJ := $(abspath $(OUTPUT)/libbpf.a)
LIBBLAZESYM_SRC := $(abspath blazesym/target/release/libblazesym_c.a)
# LIBXDP_OBJ := $(abspath ./xdp-tools/lib/libxdp/libxdp.a)
INCLUDES := -I$(OUTPUT) -I./libbpf/include/uapi -I./xdp-tools/headers
CFLAGS := -g -O2 -Wall
BPFCFLAGS := -g -O2 -Wall
INSTALL ?= install
prefix ?= /usr/local
ARCH ?= x86
VMLINUX ?= $(ARCH)/vmlinux.h
BTFHUB_ARCHIVE ?= $(abspath btfhub-archive)
ifeq ($(ARCH),x86)
CARGO ?= $(shell which cargo)
ifeq ($(strip $(CARGO)),)
USE_BLAZESYM ?= 0
else
USE_BLAZESYM ?= 1
endif
endif

APPS = ihreo

# export variables that are used in Makefile.btfgen as well.
export OUTPUT BPFTOOL ARCH BTFHUB_ARCHIVE APPS

APP_ALIASES = $(FSDIST_ALIASES) $(FSSLOWER_ALIASES) ${SIGSNOOP_ALIAS}

COMMON_OBJ = \
	$(OUTPUT)/trace_helpers.o \
	$(OUTPUT)/syscall_helpers.o \
	$(OUTPUT)/errno_helpers.o \
	$(OUTPUT)/map_helpers.o \
	$(OUTPUT)/uprobe_helpers.o \
	$(OUTPUT)/btf_helpers.o \
	$(OUTPUT)/compat.o \
	$(if $(ENABLE_MIN_CORE_BTFS),$(OUTPUT)/min_core_btf_tar.o) \
	#

ifeq ($(USE_BLAZESYM),1)
COMMON_OBJ += \
	$(OUTPUT)/libblazesym.a \
	$(OUTPUT)/blazesym.h \
	#
endif

define allow-override
  $(if $(or $(findstring environment,$(origin $(1))),\
            $(findstring command line,$(origin $(1)))),,\
    $(eval $(1) = $(2)))
endef

$(call allow-override,CC,$(CROSS_COMPILE)cc)
$(call allow-override,LD,$(CROSS_COMPILE)ld)

.PHONY: all
all: $(APPS)

ifeq ($(V),1)
Q =
msg =
else
Q = @
msg = @printf '  %-8s %s%s\n' "$(1)" "$(notdir $(2))" "$(if $(3), $(3))";
MAKEFLAGS += --no-print-directory
endif

ifneq ($(EXTRA_CFLAGS),)
CFLAGS += $(EXTRA_CFLAGS)
endif
ifneq ($(EXTRA_LDFLAGS),)
LDFLAGS += $(EXTRA_LDFLAGS)
endif
ifeq ($(USE_BLAZESYM),1)
CFLAGS += -DUSE_BLAZESYM=1
endif

ifeq ($(USE_BLAZESYM),1)
LDFLAGS += $(OUTPUT)/libblazesym.a -lrt -lpthread -ldl
endif

.PHONY: clean
clean:
	$(call msg,CLEAN)
	$(Q)rm -rf $(OUTPUT) $(APPS) $(APP_ALIASES)

$(LIBBLAZESYM_SRC)::
	$(Q)cd blazesym/capi && cargo build --release

$(OUTPUT)/libblazesym.a: $(LIBBLAZESYM_SRC) | $(OUTPUT)
	$(call msg,LIB,$@)
	$(Q)cp $(LIBBLAZESYM_SRC) $@

$(OUTPUT)/blazesym.h: $(LIBBLAZESYM_SRC) | $(OUTPUT)
	$(call msg,INC,$@)
	$(Q)cp blazesym/capi/include/blazesym.h $@

$(OUTPUT) $(OUTPUT)/libbpf $(BPFTOOL_OUTPUT):
	$(call msg,MKDIR,$@)
	$(Q)mkdir -p $@

$(BPFTOOL): | $(BPFTOOL_OUTPUT)
	$(call msg,BPFTOOL,$@)
	$(Q)$(MAKE) ARCH= CROSS_COMPILE=  OUTPUT=$(BPFTOOL_OUTPUT)/ -C $(BPFTOOL_SRC) bootstrap

# This eBPF program runs on custom Linux kernel (based on 5.19.17)
# Copy vmlinux.h using bpftool
$(VMLINUX): $(BPFTOOL)
	$(call msg,INC,$@)
	$(Q)mkdir -p $(ARCH)
	$(Q)$(BPFTOOL) btf dump file /sys/kernel/btf/vmlinux format c > $(VMLINUX)

# $(APPS): %: $(OUTPUT)/%.o $(COMMON_OBJ) $(LIBBPF_OBJ) $(LIBXDP_OBJ) $(VMLINUX) | $(OUTPUT)
# 	$(call msg,BINARY,$@)
# 	$(Q)$(CC) $(CFLAGS) $^ $(LDFLAGS) -lelf -lz $(LIBBPF_OBJ) $(LIBXDP_OBJ) -o $@

$(APPS): %: $(OUTPUT)/%.o $(COMMON_OBJ) $(LIBBPF_OBJ) | $(OUTPUT)
	$(call msg,BINARY,$@)
	$(Q)$(CC) $(CFLAGS) $^ $(LDFLAGS) -lelf -lz -o $@

ifeq ($(USE_BLAZESYM),1)
$(patsubst %,$(OUTPUT)/%.o,$(BZ_APPS)): $(OUTPUT)/blazesym.h
endif

$(patsubst %,$(OUTPUT)/%.o,$(APPS)): %.o: %.skel.h

$(OUTPUT)/%.o: %.c $(wildcard %.h) $(LIBBPF_OBJ) | $(OUTPUT)
	$(call msg,CC,$@)
	$(Q)$(CC) $(CFLAGS) $(INCLUDES) -c $(filter %.c,$^) -o $@

$(OUTPUT)/%.skel.h: $(OUTPUT)/%.bpf.o | $(OUTPUT) $(BPFTOOL)
	$(call msg,GEN-SKEL,$@)
	$(Q)$(BPFTOOL) gen skeleton $< > $@

$(OUTPUT)/%.bpf.o: %.bpf.c $(LIBBPF_OBJ) $(wildcard %.h) $(VMLINUX) | $(OUTPUT)
	$(call msg,BPF,$@)
	$(Q)$(CLANG) $(BPFCFLAGS) -target bpf -D__TARGET_ARCH_$(ARCH)	      \
		     -I$(ARCH)/ $(INCLUDES) -c $(filter %.c,$^) -o $@ &&      \
	$(LLVM_STRIP) -g $@

btfhub-archive: force
	$(call msg,GIT,$@)
	$(Q)[ -d "$(BTFHUB_ARCHIVE)" ] || git clone -q https://github.com/aquasecurity/btfhub-archive/ $(BTFHUB_ARCHIVE)
	$(Q)cd $(BTFHUB_ARCHIVE) && git pull

ifdef ENABLE_MIN_CORE_BTFS
$(OUTPUT)/min_core_btf_tar.o: $(patsubst %,$(OUTPUT)/%.bpf.o,$(APPS)) btfhub-archive | bpftool
	$(Q)$(MAKE) -f Makefile.btfgen
endif

# Build libbpf.a
$(LIBBPF_OBJ): $(wildcard $(LIBBPF_SRC)/*.[ch]) | $(OUTPUT)/libbpf
	$(call msg,LIB,$@)
	$(Q)$(MAKE) -C $(LIBBPF_SRC) BUILD_STATIC_ONLY=1		      \
		    OBJDIR=$(dir $@)libbpf DESTDIR=$(dir $@)		      \
		    INCLUDEDIR= LIBDIR= UAPIDIR=			      \
		    install

$(LIBXDP_OBJ):
	$(call msg,LIB,$@)
	$(Q)./xdp-tools/configure $@
	$(Q)$(MAKE) -C xdp-tools BUILD_STATIC_ONLY=1 libxdp

$(SIGSNOOP_ALIAS): sigsnoop
	$(call msg,SYMLINK,$@)
	$(Q)ln -f -s $^ $@

install: $(APPS) $(APP_ALIASES)
	$(call msg, INSTALL libbpf-tools)
	$(Q)$(INSTALL) -m 0755 -d $(DESTDIR)$(prefix)/bin
	$(Q)$(INSTALL) $(APPS) $(DESTDIR)$(prefix)/bin
	$(Q)cp -a $(APP_ALIASES) $(DESTDIR)$(prefix)/bin

.PHONY: force
force:

# delete failed targets
.DELETE_ON_ERROR:
# keep intermediate (.skel.h, .bpf.o, etc) targets
.SECONDARY:
