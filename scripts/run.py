#!/usr/bin/python3
import subprocess
import tempfile
import json
import os
import matplotlib.pyplot as pp
import numpy as np
import re
import time
import argparse
import logging

class FlowStat:
    saddr:str = None
    sport:int = None
    daddr:str = None
    dport:int = None
    throughput:float = None
    retransmissions:int = None
    iperf_rtt_mean:int = None
    sutilization:float = None
    dutilization:float = None
    nic_rtt_mean:float = None
    nic_rtt_std:float = None
    tcp_rtt_mean:float = None
    tcp_rtt_std:float = None

class NeperFlowStat:
    saddr:str = None
    sport:int = None
    daddr:str = None
    dport:int = None
    throughput:float = None
    nic_rtt_mean:float = None
    nic_rtt_std:float = None
    tcp_rtt_mean:float = None
    tcp_rtt_std:float = None

def check_configuration():
    ret = True

    # Configure congestion control algorithm (host)
    sysctl_tcp_congestion_control = ['sysctl', 'net.ipv4.tcp_congestion_control']
    p = subprocess.Popen(sysctl_tcp_congestion_control, stdout=subprocess.PIPE)
    output = p.stdout.read().decode('utf-8')
    if output.partition('=')[2].strip() != args.cca:
        logging.error(f"{output.rstrip()} ({args.cca} is desired. Do sysctl.net.ipv4.tcp_congestion_control={args.cca})")
        ret = False
    else:
        logging.info(output.rstrip())

    # Configure congestion control algorithm (container cluster)
    kubectl_check_bbr = ['kubectl', 'get', 'cm', 'cilium-config', '-n', 'kube-system', '-o', 'json']
    p = subprocess.Popen(kubectl_check_bbr, stdout=subprocess.PIPE)
    json_output = json.loads(p.stdout.read())
    if json_output.get("data") != None and json_output.get("data").get("enable-bbr") != None:
        enable_bbr = bool(json_output.get("data").get("enable-bbr"))
        if args.cca == "bbr" and enable_bbr != True:
            logging.error(f"enable_bbr = {enable_bbr} ({args.cca} is desired)")
            ret = False
        elif args.cca != "bbr" and enable_bbr == True:
            logging.error(f"enable_bbr = {enable_bbr} ({args.cca} is desired)")
            ret = False
        else:
            logging.info(f"enable_bbr = {enable_bbr}")
    else:
        if args.cca == "bbr":
            logging.error("json_output is wrong.", json_output)
            ret = False

    # Check loss detection
    if args.loss_detection.split("-")[0] == "rack":
        tcp_recovery = "1"
    else:
        tcp_recovery = "0"
    
    if args.loss_detection.split("-")[1] == "tlp":
        tcp_early_retrans = "3"
    elif args.loss_detection.split("-")[1] == "er":
        tcp_early_retrans = "2"
    else:
        tcp_early_retrans = "0"

    sysctl_tcp_recovery = ['sysctl', 'net.ipv4.tcp_recovery']
    p = subprocess.Popen(sysctl_tcp_recovery, stdout=subprocess.PIPE)
    output = p.stdout.read().decode('utf-8')
    if output.partition('=')[2].strip() != tcp_recovery:
        logging.error(f"{output.rstrip()} ({tcp_recovery} is desired. Do sysctl.net.ipv4.sysctl_tcp_recovery={tcp_recovery})")
        ret = False
    else:
        logging.info(output.rstrip())

    sysctl_tcp_early_retrans = ['sysctl', 'net.ipv4.tcp_early_retrans']
    p = subprocess.Popen(sysctl_tcp_early_retrans, stdout=subprocess.PIPE)
    output = p.stdout.read().decode('utf-8')
    if output.partition('=')[2].strip() != tcp_early_retrans:
        logging.error(f"{output.rstrip()} ({tcp_early_retrans} is desired. Do sysctl.net.ipv4.tcp_early_retrans={tcp_early_retrans})")
        ret = False
    else:
        logging.info(output.rstrip())
    
    # Get cluster nodes
    nodes = get_k8s_nodes()
    for node in nodes:
        kubectl_check_sysctl = ['kubectl', 'get', '--raw', f'/api/v1/nodes/{node}/proxy/configz']
        p = subprocess.Popen(kubectl_check_sysctl, stdout=subprocess.PIPE)
        json_output = json.loads(p.stdout.read())
        if json_output.get("kubeletconfig") != None and json_output.get("kubeletconfig").get("allowedUnsafeSysctls") != None:
            allowed_unsafe_sysctls = json_output.get("kubeletconfig").get("allowedUnsafeSysctls")
            if "net.ipv4.tcp_recovery" not in allowed_unsafe_sysctls or "net.ipv4.tcp_early_retrans" not in allowed_unsafe_sysctls:
                logging.error("allowedUnsafeSysctls is not set.")
                ret = False
        else:
            logging.error("json_output is wrong.", json_output)
            ret = False

    # Get default pods
    default_pods = get_k8s_default_pods()
    for pod in default_pods:
        kubectl_check_loss_detection = ['kubectl', 'get', 'pod', pod, '-o', 'json']
        p = subprocess.Popen(kubectl_check_loss_detection, stdout=subprocess.PIPE)
        json_output = json.loads(p.stdout.read())
        if json_output.get("spec") != None and json_output.get("spec").get("securityContext") != None:
            security_context = json_output.get("spec").get("securityContext")
            if security_context.get("sysctls") != None:
                for item in security_context.get("sysctls"):
                    if item["name"] == "net.ipv4.tcp_recovery":
                        val = item["value"]
                        if val != tcp_recovery:
                            logging.error(f"{pod}'s net.ipv4.tcp_recovery = {val} ({tcp_recovery} is desired)")
                            ret = False
                    elif item["name"] == "net.ipv4.tcp_early_retrans":
                        val = item["value"]
                        if val != tcp_early_retrans:
                            logging.error(f"{pod}'s net.ipv4.tcp_early_retrans = {val} ({tcp_early_retrans} is desired)")
                            ret = False
            else:
                if tcp_recovery != "1" or tcp_early_retrans != "3":
                    logging.error(f"{pod}'s sysctls are not set.")
                    ret = False
        else:
            logging.error(f"{pod}'s json_output is wrong.", json_output)
            ret = False
            
    if ret == False:
        logging.error("Wrong configuration.")
    
    return ret

def summarize_statistics(hflows, cflows):
    json_data = {}
    throughputs = []
    retransmissions = []
    rtts = []
    
    json_data["cca"] = args.cca
    json_data["loss_detection"] = args.loss_detection

    logging.info(f'{experiment}')
    if args.app == "neper":
        logging.info('expr i {0:>10} {1:>8} {2:>15} {3:>15} {4:>13}'. \
              format('flow', 'tput', 'nic_rtt (us)', 'tcp_rtt (us)', 'offset'))
    else:
        logging.info('expr i {0:>10} {1:>7} {2:>5} {3:>15} {4:>15} {5:>13}'. \
              format('flow', 'tput', 'rtx', 'nic_rtt (us)', 'tcp_rtt (us)', 'offset'))

    if len(hflows) > 0:
        for i, hflow in enumerate(hflows):
            json_data[f"h{i}"] = vars(hflow)
            throughputs.append(hflow.throughput)
            retransmissions.append(hflow.retransmissions)
            rtts.append(hflow.iperf_rtt_mean)

        print(experiment, f"h{len(hflows)}", args.cca, args.loss_detection, \
            f"{np.sum(throughputs):.3f}, {np.average(throughputs):.3f}, {np.std(throughputs):.3f}, " \
            f"{np.average(retransmissions):.3f}, {np.std(retransmissions):.3f}, {np.average(rtts):.3f}, {np.std(rtts):.3f}")
        json_data["host_aggregate_throughput"] = np.sum(throughputs)
        json_data["host_throughput_average"] = np.average(throughputs)
        json_data["host_throughput_std"] = np.std(throughputs)
        json_data["host_retransmissions_average"] = np.average(retransmissions)
        json_data["host_retransmissions_std"] = np.std(retransmissions)
        json_data["host_rtt_average"] = np.average(rtts)
        json_data["host_rtt_std"] = np.std(rtts)

    if len(cflows) > 0:
        for i, cflow in enumerate(cflows):
            json_data[f"c{i}"] = vars(cflow)
            throughputs.append(cflow.throughput)
            retransmissions.append(cflow.retransmissions)
            rtts.append(cflow.iperf_rtt_mean)

        print(experiment, f"c{len(cflows)}", args.cca, args.loss_detection, \
            f"{np.sum(throughputs):.3f}, {np.average(throughputs):.3f}, {np.std(throughputs):.3f}, " \
            f"{np.average(retransmissions):.3f}, {np.std(retransmissions):.3f}, {np.average(rtts):.3f}, {np.std(rtts):.3f}")
        json_data["container_aggregate_throughput"] = np.sum(throughputs)
        json_data["container_throughput_average"] = np.average(throughputs)
        json_data["container_throughput_std"] = np.std(throughputs)
        json_data["container_retransmissions_average"] = np.average(retransmissions)
        json_data["container_retransmissions_std"] = np.std(retransmissions)
        json_data["container_rtt_average"] = np.average(rtts)
        json_data["container_rtt_std"] = np.std(rtts)

    with open(f'summary.{experiment}.json', 'w') as f:
        json.dump(json_data, f)

def main():
    duration = int(args.time)
    server_addr = "192.168.2.103"
    interface = "ens801f0"

    global experiment
    experiment = f"run-0"

    if check_configuration() == False:
        exit()
    initialize_nic()

    os.chdir("..")
    if not os.path.exists("data"):
        os.mkdir("data")
    os.chdir("data")

    while os.path.exists(experiment):
        (remained, last) = experiment.rsplit("-", 1)
        trial = int(last) + 1
        experiment = f"{remained}-{trial}"

    os.mkdir(experiment)
    os.chdir(experiment)

    processes = []
    files = []
    if not args.no_trace:
        (util_p, util_f) = start_cpu_utilization()
        processes.append(util_p)
        files.append(util_f)

        (interrupt_f, softirqs_f) = get_interrupt_count()
        files.append(interrupt_f)
        files.append(softirqs_f)

        (epping_p, epping_f) = start_epping(interface)
        processes.append(epping_p)
        files.append(epping_f)
        
        (bpftrace_p, bpftrace_f) = start_bpftrace()
        processes.append(bpftrace_p)
        files.append(bpftrace_f)
        
        (socktrace_p, socktrace_f) = start_socktrace()
        processes.append(socktrace_p)
        files.append(socktrace_f)
        
    time.sleep(2)

    # Using neper
    if args.app == "neper":
        server_pods = get_k8s_servers('neper')
        client_pods = get_k8s_clients('neper')

        if len(server_pods[0]) == 0 or len(client_pods[0]) == 0:
            clear_instrumentation(processes)
            print('Check that kubeconfig is properly set.')
            exit(-1)
        hflows = run_neper_clients(int(args.host), duration, server_addr)
        cflows = run_k8s_neper_clients(int(args.container), duration, server_pods, client_pods)
    # Using iperf
    else:
        server_pods = get_k8s_servers('iperf')
        client_pods = get_k8s_clients('iperf')

        if len(server_pods) == 0 or len(client_pods) == 0:
            clear_instrumentation(processes)
            print('Check that kubeconfig is properly set.')
            exit(-1)
        # flows = run_iperf_clients(num_flows, duration, servers, clients)
        (hflows, cflows) = run_iperf_clients(int(args.host), int(args.container), duration, server_addr, server_pods, client_pods)

    if not args.no_trace:
        (processes, files) = end_cpu_utilization(processes, files, util_p, util_f)
        files = process_interrupt_count(files, interrupt_f, softirqs_f)
        clear_instrumentation(processes)

    summarize_statistics(hflows, cflows)
    
def initialize_nic():
    logging.info("Initialize ice driver.")
    subprocess.run(["rmmod", "ice"])
    time.sleep(0.5)
    subprocess.run(["modprobe", "ice"])
    time.sleep(0.5)
    subprocess.run(["./flow_direction_tx_tcp.sh"], stdout=subprocess.DEVNULL)
    subprocess.run(["./smp_affinity.sh"], stdout=subprocess.DEVNULL)
    
def start_cpu_utilization():
    f = tempfile.NamedTemporaryFile()
    p = subprocess.Popen(['./cpuload.sh'], stdout=f, cwd='../../scripts')

    return (p, f)

def end_cpu_utilization(processes, files, cpu_p, cpu_f):
    cpu_p.kill()
    
    with open(f'cpu.{experiment}.out', 'w') as cpu_output:
        subprocess.run(["./cpu.py", cpu_f.name], stdout=cpu_output, cwd='../../scripts')

    if not args.silent:
        subprocess.run(["./cpu.py", "-c", cpu_f.name], cwd='../../scripts')

    filtered_processes = [p for p in processes if p != cpu_p]
    filtered_files = [f for f in files if f != cpu_f]

    return (filtered_processes, filtered_files)
    
def get_interrupt_count():
    interrupts_f = tempfile.NamedTemporaryFile()
    softirqs_f = tempfile.NamedTemporaryFile()
    subprocess.run(["cat", "/proc/interrupts"], stdout=interrupts_f)
    subprocess.run(["cat", "/proc/softirqs"], stdout=softirqs_f)

    return interrupts_f, softirqs_f

def process_interrupt_count(files, old_interrupts_f, old_softirqs_f):
    new_interrupts_f = tempfile.NamedTemporaryFile()
    new_softirqs_f = tempfile.NamedTemporaryFile()
    subprocess.run(["cat", "/proc/interrupts"], stdout=new_interrupts_f)
    subprocess.run(["cat", "/proc/softirqs"], stdout=new_softirqs_f)

    with open(f'interrupts.{experiment}.out', 'w') as interrupts_output:
        subprocess.run(["./interrupts.py", old_interrupts_f.name, new_interrupts_f.name], stdout=interrupts_output, cwd='../../scripts')

    with open(f'softirqs.{experiment}.out', 'w') as softirqs_output:
        subprocess.run(["./softirqs.py", old_softirqs_f.name, new_softirqs_f.name], stdout=softirqs_output, cwd='../../scripts')

    if not args.silent:
        subprocess.run(["./interrupts.py", old_interrupts_f.name, new_interrupts_f.name], cwd='../../scripts')
        subprocess.run(["./softirqs.py", old_softirqs_f.name, new_softirqs_f.name], cwd='../../scripts')
    
    files = [f for f in files if f != old_interrupts_f or f != old_softirqs_f]
    
    return files

def clear_instrumentation(processes):
    for process in processes:
        process.kill()

def start_epping(interface):
    # f = tempfile.NamedTemporaryFile()
    with open(f'raw.epping.{experiment}.out', 'w') as f:
        if int(args.container) > 0:
            p = subprocess.Popen(["./pping", "-i", interface, "-I", "xdp", "-x", "native", "-r" "0.001", "-V"], stdout=f, cwd='../..')
            # p = subprocess.Popen(["./pping", "-i", interface, "-I", "xdp", "-x", "native", "-V"], stdout=f, cwd='../..')
        else:
            p = subprocess.Popen(["./pping", "-i", interface, "-I", "xdp", "-x", "native", "-r" "0.001"], stdout=f, cwd='../..')
            # p = subprocess.Popen(["./pping", "-i", interface, "-I", "xdp", "-x", "native"], stdout=f, cwd='../..')

    time.sleep(2)
    return (p, f)

def end_epping(epping_p, epping_f, flows):
    epping_p.kill()

    epping_map = {}

    with open(epping_f.name, 'r') as epping_f:
        for (i, flow) in enumerate(flows):
            epping_f.seek(0)
            if args.vxlan:
                print(f"{i}: UDP 192.168.2.103:{str(flow.dport)}+192.168.2.102:{str(flow.sport)}")
                target = ":" + str(flow.dport) + "+" + "192.168.2.102" + ":" + str(flow.sport)
                # expr = re.compile(r"^(\d{2}:\d{2}:\d{2}\.\d{9})\s(.+?)\sms\s(.+?)\sms\s" + r"UDP\s" + "192.168.2.103" + re.escape(target) + r"$")
                expr = re.compile(r"^(\d+)\s(.+?)\sms\s(.+?)\sms\s" + r"UDP\s" + "192.168.2.103" + re.escape(target) + r"$")
                samples = parse_raw(epping_f, expr)                
                # samples = parse(epping_f, expr)
                # samples = parse(epping_f, "UDP", "192.168.2.103", str(flow.dport), "192.168.2.102", str(flow.sport))
            elif args.native:
                print(f"{i}: TCP {str(flow.daddr)}:{str(flow.dport)}+{str(flow.saddr)}:{str(flow.sport)}")
                target = str(flow.daddr) + ":" + str(flow.dport) + "+" + str(flow.saddr) + ":" + str(flow.sport)
                # expr = re.compile(r"^(\d{2}:\d{2}:\d{2}\.\d{9})\s(.+?)\sms\s(.+?)\sms\s" + r"TCP\s" + re.escape(target) + r"$")
                expr = re.compile(r"^(\d+)\s(.+?)\sms\s(.+?)\sms\s" + r"TCP\s" + re.escape(target) + r"$")
                samples = parse(epping_f, expr)
                # samples = parse(epping_f, "TCP", ".*?", str(flow.dport), "192.168.2.102", str(flow.sport))
            else:
                print(f"{i}: TCP 192.168.2.103:{str(flow.dport)}+192.168.2.102:{str(flow.sport)}")
                target = ":" + str(flow.dport) + "+" + "192.168.2.102" + ":" + str(flow.sport)
                # expr = re.compile(r"^(\d{2}:\d{2}:\d{2}\.\d{9})\s(.+?)\sms\s(.+?)\sms\s" + r"TCP\s" + "192.168.2.103" + re.escape(target) + r"$")
                expr = re.compile(r"^(\d+)\s(.+?)\sms\s(.+?)\sms\s" + r"TCP\s" + "192.168.2.103" + re.escape(target) + r"$")
                samples = parse_raw(epping_f, expr)
                # samples = parse(epping_f, expr)
                # samples = parse(epping_f, "TCP", "192.168.2.103", str(flow.dport), "192.168.2.102", str(flow.sport))

            if len(samples) == 0:
                print("There is no epping samples.")
                return None

            x = list(zip(*samples))[0]
            y = list(zip(*samples))[1]

            epping_map[i] = (x, y)

            with open(f'epping.{i}.{experiment}.out', 'w') as epping_output_per_flow:
                for j, _ in enumerate(epping_map[i][0]):
                    epping_output_per_flow.write(f'{epping_map[i][0][j].astype(int)} {epping_map[i][1][j]}\n')

    return epping_map

def start_socktrace():
    with open(f'raw.sock.{experiment}.out', 'w') as f:
        p = subprocess.Popen(["./sock.bt"], stdout=f, cwd='../..')

    return (p, f)

def end_socktrace(socktrace_p, socktrace_f, flows):
    socktrace_p.kill()
    return

def start_bpftrace():
    # f = tempfile.NamedTemporaryFile()
    with open(f'raw.bpftrace.{experiment}.out', 'w') as f:
        # p = subprocess.Popen(["./trtt_cubic.bt"], stdout=f, cwd='../..')
        # p = subprocess.Popen(["./trtt_bbr.bt"], stdout=f, cwd='../..')
        p = subprocess.Popen(["./trtt_rack_bbr.bt"], stdout=f, cwd='../..')
        # p = subprocess.Popen(["./trtt_rack_cubic_proto.bt"], stdout=f, cwd='../..')
        # p = subprocess.Popen(["./skb_timeout.bt"], stdout=f, cwd='../..')

    return (p, f)

def end_bpftrace(bpftrace_p, bpftrace_f, flows):
    bpftrace_p.kill()
    bpftrace_map = {}
    loss_map = {}

    # To check tcp_mark_skb_lost() is called through tcp_ack() path
    rack_detect_loss_flag = False

    with open(bpftrace_f.name, 'r') as bpftrace_f:
        for i, flow in enumerate(flows):
            bpftrace_f.seek(0)
            with open(f'bpftrace.{i}.{experiment}.out', 'w') as bpftrace_output_per_flow:
                for line in bpftrace_f.readlines():
                    data = line.rstrip().split()
                    if len(data) < 2:
                        continue

                    if data[1] == "bbr_update_model()":
                        ts_ns = int(data[0])
                        sock = data[2]
                        delivered = int(data[3])
                        trtt_us = int(data[4])
                        app_limited = int(data[5])
                        sport = int(data[6])
                        ebw = (delivered * 1500 * 8) / trtt_us

                        if sport == flow.sport:
                            if not i in bpftrace_map:
                                bpftrace_map[i] = ([], [], [], [])
                            
                            (x, y, z, w) = bpftrace_map[i]
                            x.append(ts_ns)
                            y.append(trtt_us)
                            z.append(delivered)
                            w.append(ebw) # Mbps

                            output = ' '.join(data) + ' ' + str(ebw) + '\n'
                            bpftrace_output_per_flow.write(output)
                    elif data[1] == "tcp_rack_detect_loss()" and data[2] == "enter":
                        rack_detect_loss_flag = True
                    elif data[1] == "rack_detect_loss_flag" and rack_detect_loss_flag == True:
                        sport = int(data[4])
                        if sport == flow.sport:
                            if not i in loss_map:
                                loss_map[i] = ([], [], [], [])
                            (x, y, z, w) = loss_map[i]

                            ts_ns = int(data[0])
                            gso_segs = int(data[5])
                            reord_seen = int(data[6])
                            tolerance = int(data[7])
                            diff = int(data[8])
                            dsack_seen = int(data[9])

                            x.append(ts_ns)
                            y.append(gso_segs)
                            z.append(tolerance)
                            w.append(diff)

                    elif data[1] == "tcp_rack_detect_loss()" and data[2] == "exit":
                        rack_detect_loss_flag = False


            if not bpftrace_map.get(i):
                logging.error("There is no bpftrace result.")
                return None, None

    return (bpftrace_map, loss_map)

def get_k8s_nodes():
    first = ['kubectl', 'get', 'nodes']
    second = ['awk', '/Ready/ {print $1}']
    p1 = subprocess.Popen(first, stdout=subprocess.PIPE)
    p2 = subprocess.Popen(second, stdin=p1.stdout, stdout=subprocess.PIPE, text=True)
    p1.stdout.close()  # Allow p1 to receive a SIGPIPE if p2 exits.
    output = p2.communicate()[0]
    nodes = output.rstrip().split('\n')

    return nodes

def get_k8s_default_pods():
    first = ['kubectl', 'get', 'pods', '-n', 'default']
    second = ['awk', 'NR > 1 {print $1}']
    p1 = subprocess.Popen(first, stdout=subprocess.PIPE)
    p2 = subprocess.Popen(second, stdin=p1.stdout, stdout=subprocess.PIPE, text=True)
    p1.stdout.close()  # Allow p1 to receive a SIGPIPE if p2 exits.
    output = p2.communicate()[0]
    nodes = output.rstrip().split('\n')

    return nodes

def get_k8s_servers(target):
    first = ['kubectl', 'get', 'pods', '-owide']
    second = ['perl', '-nE', fr'say $1, " ", $7 if /^({target}-server.*?)\s+(.*?)\s+(.*?)\s+(.*?)\s+(\(.*?\))?\s+(.*?)\s+(.*?)\s+.*/']
    p1 = subprocess.Popen(first, stdout=subprocess.PIPE)
    p2 = subprocess.Popen(second, stdin=p1.stdout, stdout=subprocess.PIPE, text=True)
    p1.stdout.close()  # Allow p1 to receive a SIGPIPE if p2 exits.
    output = p2.communicate()[0]
    servers = list(map(lambda item: item.split(), output.rstrip().split('\n')))

    return servers

def get_k8s_clients(target):
    first = ['kubectl', 'get', 'pods', '-owide']
    second = ['awk', f'/{target}-client/ ' + '{print $1, $6}']
    p1 = subprocess.Popen(first, stdout=subprocess.PIPE)
    p2 = subprocess.Popen(second, stdin=p1.stdout, stdout=subprocess.PIPE, text=True)
    p1.stdout.close()  # Allow p1 to receive a SIGPIPE if p2 exits.
    output = p2.communicate()[0]
    clients = list(map(lambda item: item.split(), output.rstrip().split('\n')))

    return clients

def run_neper_clients(num_flows, num_container_flows, duration, server_addr, servers, clients):
    flows = []
    container_flows = []
    processes = []

    for i in range(0, num_flows):
        port = 5304 + i
        cport = 43004 + i
        cpu = 16 + i
        neper_args = ["numactl", "-C", str(cpu), "./tcp_rr", "--nolog", "-c", "-H", server_addr, \
                      "-l", str(duration), "--source-port", str(cport), "-P", str(port)]
        f = tempfile.NamedTemporaryFile()
        p = subprocess.Popen(neper_args, stdout=f, stderr=subprocess.PIPE, cwd='../../scripts')  
        
        processes.append((p, f, False))
        flow = NeperFlowStat()
        flow.dport = port
        netstat = ['netstat', '-tp']
        netstat_f = tempfile.NamedTemporaryFile()
        subprocess.run(netstat, stdout=netstat_f, stderr=subprocess.DEVNULL)
        with open(netstat_f.name, 'r') as netstat_f:
            netstat_f.seek(0)
            for line in netstat_f.readlines():
                tokens = line.split()
                if not len(tokens) == 7:
                    continue

                if tokens[-1].endswith('tcp_rr') and tokens[-1].startswith(str(p.pid)) and tokens[4].endswith(str(port)):
                    # print(tokens[3].split(":")[-1])
                    flow.sport = int(tokens[3].split(":")[-1])

        flows.append(flow)

    ports = [5300, 5301, 5302, 5303, 5304, 5305, 5306, 5307]
    sports = [43000, 43001, 43002, 43003, 43004, 43005, 43006, 43007]
    cpus = [20, 21, 22, 23]

    for i in range(0, num_container_flows):
        neper_args = ["kubectl", "exec", clients[i][0], "--", "numactl", "-C", str(cpus[i]), \
                      "./tcp_rr", "--nolog", "-c", "-H", servers[i][1], "-l", str(duration), \
                      "--source-port", str(sports[i]), "-P", str(ports[i])]
        # neper_args = ["kubectl", "exec", clients[i][0], "--", \
        #               "./tcp_rr", "--nolog", "-c", "-H", servers[i][1], "--source-port", str(sports[i]), "-P", str(ports[i]), "-l", str(duration)]
        f = tempfile.NamedTemporaryFile()
        p = subprocess.Popen(neper_args, stdout=f, stderr=subprocess.PIPE)   
        
        processes.append((p, f, True))
        flow = NeperFlowStat()
        flow.saddr = "192.168.2.102"
        flow.daddr = "192.168.2.103"

        flow.sport = sports[i]
        flow.dport = ports[i]
        container_flows.append(flow)

    logging.info(f"Start {num_flows} neper host flows for {duration} seconds.")
    logging.info(f"Start {num_flows} neper vxlan flows for {duration} seconds.")
    for (p, f, is_vxlan) in processes:
        _, err = p.communicate()
        if err != None and err != b'':
            logging.error('neper error:', err.decode('utf-8'))
            return None
        
        f.seek(0)
        lines = f.readlines()
        for l in lines:
            tokens = l.decode('utf-8').split('=')
            if tokens[0] == 'port':
                if is_vxlan:
                    i, flow = find_flow(container_flows, int(tokens[1]))
                else:
                    i, flow = find_flow(flows, int(tokens[1]))
            elif tokens[0] == 'throughput':
                flow.throughput = float(tokens[1])
            elif tokens[0] == 'latency_mean':
                flow.tcp_rtt_mean = float(tokens[1]) * 1000000
            elif tokens[0] == 'latency_stddev':
                flow.tcp_rtt_std = float(tokens[1]) * 1000000
        
        f.close()

        if is_vxlan:
            print(f'v{i}: {flow.sport}, {flow.dport}, {flow.throughput:.3f}')
        else:
            print(f'h{i}: {flow.sport}, {flow.dport}, {flow.throughput:.3f}')
        # print(f'{i}: {flow.dport}, {flow.throughput:.3f}')

    return flows, container_flows

def run_iperf_clients(num_hflows, num_cflows, duration, server_addr, server_pods, client_pods):
    hflows = []
    cflows = []
    processes = []

    # Host flows
    for i in range(0, num_hflows):
        port = 5200 + i
        cport = 42000 + i
        cpu = 16 + i
        iperf_args = ["iperf3", "-c", server_addr, "-p", str(port), "--cport", str(cport), \
                      "-t", str(duration), "-J", "-A", str(cpu)]
        f = open(f'iperf.h{i}.{experiment}.out', 'w+b')
        p = subprocess.Popen(iperf_args, stdout=f, stderr=subprocess.PIPE)
        
        processes.append((p, f, False))
        hflow = FlowStat()
        hflow.dport = port
        hflows.append(hflow)

    # Container flows
    for i in range(0, num_cflows):
        port = 5200 + i
        cport = 42000 + i
        cpu = 20 + i
        iperf_args = ["kubectl", "exec", client_pods[i][0], "--", \
                      "iperf3", "-c", server_pods[i][1], "-p", str(port), "--cport", str(cport), \
                      "-t", str(duration), "-J", "-A", str(cpu)]
        f = open(f'iperf.c{i}.{experiment}.out', 'w+b')
        p = subprocess.Popen(iperf_args, stdout=f, stderr=subprocess.PIPE)

        processes.append((p, f, True))
        cflow = FlowStat()
        cflow.saddr = "192.168.2.102"
        cflow.daddr = "192.168.2.103"
        cflow.dport = port
        cflows.append(cflow)

    logging.info(f"Start {num_hflows} host flows for {duration} seconds.")
    logging.info(f"Start {num_cflows} container flows for {duration} seconds.")
    for (p, f, is_cflow) in processes:
        _, err = p.communicate()
        if err != None and err != b'':
            logging.error('iperf3 error:', err.decode('utf-8'))
            return None, None
        
        f.seek(0)
        data = json.load(f)
        dport = data["start"]["connected"][0]["remote_port"]
        if is_cflow:
            i, flow = find_flow(cflows, dport)
        else:
            i, flow = find_flow(hflows, dport)

        flow.sport = data["start"]["connected"][0]["local_port"]
        flow.throughput = data["end"]["sum_sent"]["bits_per_second"] / 1000000000
        flow.retransmissions = data["end"]["sum_sent"]["retransmits"]
        flow.iperf_rtt_mean = data["end"]["streams"][0]["sender"]["mean_rtt"]
        flow.sutilization = data["end"]["cpu_utilization_percent"]["host_total"]
        flow.dutilization = data["end"]["cpu_utilization_percent"]["remote_total"]

        f.close()

        if is_cflow:
            logging.debug(f'c{i}: {flow.sport}, {flow.dport}, {flow.throughput:.3f}, {flow.retransmissions}, {flow.iperf_rtt_mean}')
        else:
            logging.debug(f'h{i}: {flow.sport}, {flow.dport}, {flow.throughput:.3f}, {flow.retransmissions}, {flow.iperf_rtt_mean}')

    return hflows, cflows

def find_flow(flows, dport):
    for i, flow in enumerate(flows):
        if flow.dport == dport:
            return (i, flow)

def jain_index(data):
    squared_sum = 0
    sum = 0
    for d in data:
        sum += d
        squared_sum += d**2

    return sum**2 / (len(data) * squared_sum)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', '-f', default=1)
    parser.add_argument('--container', '-c', default=0)
    parser.add_argument('--time', '-t', default=10)
    parser.add_argument('--app', '-a', default='iperf')
    parser.add_argument('--log', '-l', default="warning")
    parser.add_argument('--cca', default='bbr')
    parser.add_argument('--loss-detection', default='rack-tlp')
    parser.add_argument('--no-trace', action='store_true')

    global args
    args = parser.parse_args()

    available_apps = ["iperf", "neper"]
    if args.app not in available_apps:
        print(f"{args.app} is not an available app. Available: {', '.join(available_apps)}")
        exit()

    available_ccas = ["bbr", "cubic"]
    if args.cca not in available_ccas:
        print(f"{args.cca} is not an available cca. Available: {', '.join(available_ccas)}")
        exit()

    available_loss_detection = ["rack-tlp", "rack-er", "rack-none", "reno-tlp", "reno-er", "reno-none"]
    if args.loss_detection not in available_loss_detection:
        print(f"{args.loss_detection} is not an available loss detection. Available: {', '.join(available_loss_detection)}")
        exit()

    if args.log == "critical":
        logging.basicConfig(level=logging.CRITICAL)
    elif args.log == "error":
        logging.basicConfig(level=logging.ERROR)
    elif args.log == "warning":
        logging.basicConfig(level=logging.WARNING)
    elif args.log == "info":
        logging.basicConfig(level=logging.INFO)
    elif args.log == "debug":
        logging.basicConfig(level=logging.DEBUG)
    else:
        print(f"{args.log} is not an available log level. Available: critical, error, warning, info, debug")
        exit()

    main()