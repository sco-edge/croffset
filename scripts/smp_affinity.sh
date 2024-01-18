#!/bin/bash

# num=32
# for ((i=0; i < $num; i++))
# do
#     name=$((200+i))
#     echo 00000000,ffc00000 > /proc/irq/$name/smp_affinity
#     echo /sys/class/net/ens801f0/queues/tx-$i/xps_cpus
# done

echo 00000000,00400000 > /proc/irq/200/smp_affinity
echo 00000000,00800000 > /proc/irq/201/smp_affinity
echo 00000000,01000000 > /proc/irq/202/smp_affinity
echo 00000000,02000000 > /proc/irq/203/smp_affinity
echo 00000000,04000000 > /proc/irq/204/smp_affinity
echo 00000000,08000000 > /proc/irq/205/smp_affinity
echo 00000000,10000000 > /proc/irq/206/smp_affinity
echo 00000000,20000000 > /proc/irq/207/smp_affinity
echo 00000000,40000000 > /proc/irq/208/smp_affinity
echo 00000000,80000000 > /proc/irq/209/smp_affinity
echo 00010000,00000000 > /proc/irq/210/smp_affinity
echo 00020000,00000000 > /proc/irq/211/smp_affinity
echo 00040000,00000000 > /proc/irq/212/smp_affinity
echo 00080000,00000000 > /proc/irq/213/smp_affinity
echo 00100000,00000000 > /proc/irq/214/smp_affinity
echo 00200000,00000000 > /proc/irq/215/smp_affinity
echo 00400000,00000000 > /proc/irq/216/smp_affinity
echo 00800000,00000000 > /proc/irq/217/smp_affinity
echo 01000000,00000000 > /proc/irq/218/smp_affinity
echo 02000000,00000000 > /proc/irq/219/smp_affinity
echo 04000000,00000000 > /proc/irq/220/smp_affinity
echo 08000000,00000000 > /proc/irq/221/smp_affinity
echo 10000000,00000000 > /proc/irq/222/smp_affinity
echo 20000000,00000000 > /proc/irq/223/smp_affinity
echo 40000000,00000000 > /proc/irq/224/smp_affinity
echo 80000000,00000000 > /proc/irq/225/smp_affinity
echo 00000000,00400000 > /proc/irq/226/smp_affinity
echo 00000000,00800000 > /proc/irq/227/smp_affinity
echo 00000000,01000000 > /proc/irq/228/smp_affinity
echo 00000000,02000000 > /proc/irq/229/smp_affinity
echo 00000000,04000000 > /proc/irq/230/smp_affinity
echo 00000000,08000000 > /proc/irq/231/smp_affinity

echo 00000000,00400000 > /sys/class/net/ens801f0/queues/tx-0/xps_cpus
echo 00000000,00800000 > /sys/class/net/ens801f0/queues/tx-0/xps_cpus
echo 00000000,01000000 > /sys/class/net/ens801f0/queues/tx-0/xps_cpus
echo 00000000,02000000 > /sys/class/net/ens801f0/queues/tx-0/xps_cpus
echo 00000000,04000000 > /sys/class/net/ens801f0/queues/tx-0/xps_cpus
echo 00000000,08000000 > /sys/class/net/ens801f0/queues/tx-0/xps_cpus
echo 00000000,10000000 > /sys/class/net/ens801f0/queues/tx-0/xps_cpus
echo 00000000,20000000 > /sys/class/net/ens801f0/queues/tx-0/xps_cpus
echo 00000000,40000000 > /sys/class/net/ens801f0/queues/tx-0/xps_cpus
echo 00000000,80000000 > /sys/class/net/ens801f0/queues/tx-0/xps_cpus
echo 00010000,00000000 > /sys/class/net/ens801f0/queues/tx-0/xps_cpus
echo 00020000,00000000 > /sys/class/net/ens801f0/queues/tx-0/xps_cpus
echo 00040000,00000000 > /sys/class/net/ens801f0/queues/tx-0/xps_cpus
echo 00080000,00000000 > /sys/class/net/ens801f0/queues/tx-0/xps_cpus
echo 00100000,00000000 > /sys/class/net/ens801f0/queues/tx-0/xps_cpus
echo 00200000,00000000 > /sys/class/net/ens801f0/queues/tx-0/xps_cpus
echo 00400000,00000000 > /sys/class/net/ens801f0/queues/tx-0/xps_cpus
echo 00800000,00000000 > /sys/class/net/ens801f0/queues/tx-0/xps_cpus
echo 01000000,00000000 > /sys/class/net/ens801f0/queues/tx-0/xps_cpus
echo 02000000,00000000 > /sys/class/net/ens801f0/queues/tx-0/xps_cpus
echo 04000000,00000000 > /sys/class/net/ens801f0/queues/tx-0/xps_cpus
echo 08000000,00000000 > /sys/class/net/ens801f0/queues/tx-0/xps_cpus
echo 10000000,00000000 > /sys/class/net/ens801f0/queues/tx-0/xps_cpus
echo 20000000,00000000 > /sys/class/net/ens801f0/queues/tx-0/xps_cpus
echo 40000000,00000000 > /sys/class/net/ens801f0/queues/tx-0/xps_cpus
echo 80000000,00000000 > /sys/class/net/ens801f0/queues/tx-0/xps_cpus
echo 00000000,00400000 > /sys/class/net/ens801f0/queues/tx-0/xps_cpus
echo 00000000,00800000 > /sys/class/net/ens801f0/queues/tx-0/xps_cpus
echo 00000000,01000000 > /sys/class/net/ens801f0/queues/tx-0/xps_cpus
echo 00000000,02000000 > /sys/class/net/ens801f0/queues/tx-0/xps_cpus
echo 00000000,04000000 > /sys/class/net/ens801f0/queues/tx-0/xps_cpus
echo 00000000,08000000 > /sys/class/net/ens801f0/queues/tx-0/xps_cpus