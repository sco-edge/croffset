#!/usr/bin/python3
import subprocess
import tempfile
import json
import os
import numpy as np
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
    rtt_mean:int = None

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
        enable_bbr = json_output.get("data").get("enable-bbr")
        if args.cca == "bbr" and enable_bbr != "true":
            logging.error(f"enable_bbr = {enable_bbr} ({args.cca} is desired)")
            ret = False
        elif args.cca != "bbr" and enable_bbr == "true":
            logging.error(f"enable_bbr = {enable_bbr} ({args.cca} is desired)")
            ret = False
        else:
            logging.info(f"enable_bbr = {enable_bbr}")
    else:
        if args.cca == "bbr":
            logging.error("json_output is wrong. no enable-bbr.")
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
        logging.error(f"{output.rstrip()} ({tcp_recovery} is desired. Do sysctl.net.ipv4.tcp_recovery={tcp_recovery})")
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
            logging.error("json_output is wrong. no allowedUnsafeSysctls.")
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
            logging.error(f"{pod}'s json_output is wrong no securityContext.")
            ret = False
            
    if ret == False:
        logging.error("Wrong configuration.")
    
    return ret

def summarize_statistics(hflows, cflows):
    json_data = {}
    throughputs = []
    retransmissions = []
    rtts = []
    
    json_data["app"] = args.app
    json_data["cca"] = args.cca
    json_data["loss_detection"] = args.loss_detection

    if len(hflows) > 0:
        for i, hflow in enumerate(hflows):
            json_data[f"h{i}"] = vars(hflow)
            throughputs.append(hflow.throughput)
            retransmissions.append(hflow.retransmissions)
            rtts.append(hflow.rtt_mean)

        print(experiment, f"h{len(hflows)}", args.cca, args.loss_detection, \
            f"{np.sum(throughputs):.3f} {np.average(throughputs):.3f} {np.std(throughputs):.3f}", \
            f"{np.average(retransmissions):.3f} {np.std(retransmissions):.3f} {np.average(rtts):.3f} {np.std(rtts):.3f}")
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
            rtts.append(cflow.rtt_mean)

        print(experiment, f"c{len(cflows)}", args.cca, args.loss_detection, \
            f"{np.sum(throughputs):.3f} {np.average(throughputs):.3f} {np.std(throughputs):.3f}", \
            f"{np.average(retransmissions):.3f} {np.std(retransmissions):.3f} {np.average(rtts):.3f} {np.std(rtts):.3f}")
        json_data["container_aggregate_throughput"] = np.sum(throughputs)
        json_data["container_throughput_average"] = np.average(throughputs)
        json_data["container_throughput_std"] = np.std(throughputs)
        json_data["container_retransmissions_average"] = np.average(retransmissions)
        json_data["container_retransmissions_std"] = np.std(retransmissions)
        json_data["container_rtt_average"] = np.average(rtts)
        json_data["container_rtt_std"] = np.std(rtts)

    with open(f'summary.{experiment}.json', 'w') as f:
        json.dump(json_data, f, indent=4)

def main():
    duration = int(args.time)
    server_addr = "192.168.2.103"
    interface = "ens801f0"

    global swd
    swd = os.path.join(os.getcwd(), 'scripts')

    global experiment
    experiment = f"run-0"

    if check_configuration() == False:
        exit()
    initialize_nic()

    if not os.path.exists(os.path.join(swd, '..', 'output')):
        os.mkdir(os.path.join(swd, '..', 'output'))
    os.chdir(os.path.join(swd, '..', 'output'))

    while os.path.exists(os.path.join(swd, '..', 'output', experiment)):
        (remained, last) = experiment.rsplit("-", 1)
        trial = int(last) + 1
        experiment = f"{remained}-{trial}"

    os.mkdir(os.path.join(swd, '..', 'output', experiment))
    os.chdir(os.path.join(swd, '..', 'output', experiment))

    if args.app == "neper":
        server_pods = get_k8s_servers('neper')
        client_pods = get_k8s_clients('neper')
    else:
        server_pods = get_k8s_servers('iperf')
        client_pods = get_k8s_clients('iperf')

    if int(args.container) > 0 and (len(server_pods[0]) == 0 or len(client_pods[0])) == 0:
        print('Check that kubeconfig is properly set.')
        exit(-1)

    if not args.no_instrument:
        (h_meas_starts, cs_meas_starts, cc_meas_starts) = start_system_measurements(int(args.container), server_pods, client_pods)
        (instrument_files, instrument_procs) = start_instruments(interface)
    
    # sock trace only for checking spurious retransmissions
    if args.no_instrument and args.sock_only:
        (instrument_files, instrument_procs) = start_sock_instrument(interface)
        
    time.sleep(4)

    if args.app == "neper":
        (hflows, cflows) = run_neper_clients(int(args.host), int(args.container),
                                             duration, server_addr, server_pods, client_pods)
    else:
        (hflows, cflows) = run_iperf_clients(int(args.host), int(args.container),
                                             duration, server_addr, server_pods, client_pods)

    if not args.no_instrument:
        end_system_measurements(h_meas_starts, cs_meas_starts, cc_meas_starts, int(args.container), server_pods, client_pods)
        end_instruments(instrument_files, instrument_procs)

    # sock trace only for checking spurious retransmissions
    if args.no_instrument and args.sock_only:
        for proc in instrument_procs:
            proc.kill()

    if len(hflows) != int(args.host) or len(cflows) != int(args.container):
        print(f'Inconsistent # flow. hflows={len(hflows)}, cflows={len(cflows)}')
        exit(-1)

    summarize_statistics(hflows, cflows)
    
def initialize_nic():
    logging.info("Initialize ice driver.")
    subprocess.run(["rmmod", "ice"])
    time.sleep(0.5)
    subprocess.run(["modprobe", "ice"])
    time.sleep(0.5)
    subprocess.Popen(["./flow_direction_tx_tcp.sh"], stdout=subprocess.DEVNULL, cwd=swd).communicate()
    subprocess.Popen(["./smp_affinity.sh"], stdout=subprocess.DEVNULL, cwd=swd).communicate()

def start_system_measurements(num_cflows, server_pods, client_pods):
    # interrupts
    interrupts_f = tempfile.NamedTemporaryFile()
    subprocess.run(["cat", "/proc/interrupts"], stdout=interrupts_f)

    # softirqs
    softirqs_f = tempfile.NamedTemporaryFile()
    subprocess.run(["cat", "/proc/softirqs"], stdout=softirqs_f)

    # netstat
    netstat_f = tempfile.NamedTemporaryFile()
    subprocess.run(["cat", "/proc/net/netstat"], stdout=netstat_f)

    h_meas_starts = (interrupts_f, softirqs_f, netstat_f)

    # containers
    cs_meas_starts = []
    cc_meas_starts = []
    for i in range(0, num_cflows):
        # server
        cs_interrupts_f = tempfile.NamedTemporaryFile()
        subprocess.run(["kubectl", "exec", server_pods[i][0], "--", \
                    "cat", "/proc/interrupts"], stdout=cs_interrupts_f)
        
        cs_softirqs_f = tempfile.NamedTemporaryFile()
        subprocess.run(["kubectl", "exec", server_pods[i][0], "--", \
                    "cat", "/proc/softirqs"], stdout=cs_softirqs_f)

        cs_netstat_f = tempfile.NamedTemporaryFile()
        subprocess.run(["kubectl", "exec", server_pods[i][0], "--", \
                    "cat", "/proc/net/netstat"], stdout=cs_netstat_f)
        
        cs_meas_starts.append((cs_interrupts_f, cs_softirqs_f, cs_netstat_f))

        # client
        cc_interrupts_f = tempfile.NamedTemporaryFile()
        subprocess.run(["kubectl", "exec", client_pods[i][0], "--", \
                    "cat", "/proc/interrupts"], stdout=cc_interrupts_f)
        
        cc_softirqs_f = tempfile.NamedTemporaryFile()
        subprocess.run(["kubectl", "exec", client_pods[i][0], "--", \
                    "cat", "/proc/softirqs"], stdout=cc_softirqs_f)
        
        cc_netstat_f = tempfile.NamedTemporaryFile()
        subprocess.run(["kubectl", "exec", client_pods[i][0], "--", \
                    "cat", "/proc/net/netstat"], stdout=cc_netstat_f)
        
        cc_meas_starts.append((cc_interrupts_f, cc_softirqs_f, cc_netstat_f))

    return (h_meas_starts, cs_meas_starts, cc_meas_starts)

def end_system_measurements(h_meas_starts, cs_meas_starts, cc_meas_starts, num_cflows, server_pods, client_pods):
    # interrupts
    end_interrupts_f = tempfile.NamedTemporaryFile()
    subprocess.run(["cat", "/proc/interrupts"], stdout=end_interrupts_f)
    with open(f'interrupts.h.{experiment}.out', 'w') as interrupts_output:
        subprocess.Popen(["./interrupts.py", h_meas_starts[0].name, end_interrupts_f.name],
                         stdout=interrupts_output, cwd=swd).communicate()

    # softirqs
    end_softirqs_f = tempfile.NamedTemporaryFile()
    subprocess.run(["cat", "/proc/softirqs"], stdout=end_softirqs_f)
    with open(f'softirqs.h.{experiment}.out', 'w') as softirqs_output:
        subprocess.Popen(["./softirqs.py", h_meas_starts[1].name, end_softirqs_f.name],
                         stdout=softirqs_output, cwd=swd).communicate()
    
    # netstat
    end_netstat_f = tempfile.NamedTemporaryFile()
    subprocess.run(["cat", "/proc/net/netstat"], stdout=end_netstat_f)
    with open(f'netstat.h.{experiment}.out', 'w') as netstat_output:
        subprocess.Popen(["./netstat.py", h_meas_starts[2].name, end_netstat_f.name],
                         stdout=netstat_output, cwd=swd).communicate()
        
    # container
    for i in range(0, num_cflows):
        # server
        end_cs_interrupts_f = tempfile.NamedTemporaryFile()
        subprocess.run(["kubectl", "exec", server_pods[i][0], "--", \
                    "cat", "/proc/interrupts"], stdout=end_cs_interrupts_f)
        with open(f'interrupts.cs{i}.{experiment}.out', 'w') as cs_interrupts_output:
            subprocess.Popen(["./interrupts.py", cs_meas_starts[i][0].name, end_cs_interrupts_f.name],
                            stdout=cs_interrupts_output, cwd=swd).communicate()
            
        end_cs_softirqs_f = tempfile.NamedTemporaryFile()
        subprocess.run(["kubectl", "exec", server_pods[i][0], "--", \
                    "cat", "/proc/softirqs"], stdout=end_cs_softirqs_f)
        with open(f'softirqs.cs{i}.{experiment}.out', 'w') as cs_softirqs_output:
            subprocess.Popen(["./softirqs.py", cs_meas_starts[i][1].name, end_cs_softirqs_f.name],
                            stdout=cs_softirqs_output, cwd=swd).communicate()
            
        end_cs_netstat_f = tempfile.NamedTemporaryFile()
        subprocess.run(["kubectl", "exec", server_pods[i][0], "--", \
                    "cat", "/proc/net/netstat"], stdout=end_cs_netstat_f)
        with open(f'netstat.cs{i}.{experiment}.out', 'w') as cs_netstat_output:
            subprocess.Popen(["./netstat.py", cs_meas_starts[i][2].name, end_cs_netstat_f.name],
                            stdout=cs_netstat_output, cwd=swd).communicate()
        
        # client
        end_cc_interrupts_f = tempfile.NamedTemporaryFile()
        subprocess.run(["kubectl", "exec", client_pods[i][0], "--", \
                    "cat", "/proc/interrupts"], stdout=end_cc_interrupts_f)
        with open(f'interrupts.cc{i}.{experiment}.out', 'w') as cc_interrupts_output:
            subprocess.Popen(["./interrupts.py", cc_meas_starts[i][0].name, end_cc_interrupts_f.name],
                            stdout=cc_interrupts_output, cwd=swd).communicate()
            
        end_cc_softirqs_f = tempfile.NamedTemporaryFile()
        subprocess.run(["kubectl", "exec", client_pods[i][0], "--", \
                    "cat", "/proc/softirqs"], stdout=end_cc_softirqs_f)
        with open(f'softirqs.cc{i}.{experiment}.out', 'w') as cc_softirqs_output:
            subprocess.Popen(["./softirqs.py", cc_meas_starts[i][1].name, end_cc_softirqs_f.name],
                            stdout=cc_softirqs_output, cwd=swd).communicate()
            
        end_cc_netstat_f = tempfile.NamedTemporaryFile()
        subprocess.run(["kubectl", "exec", client_pods[i][0], "--", \
                    "cat", "/proc/net/netstat"], stdout=end_cc_netstat_f)
        with open(f'netstat.cc{i}.{experiment}.out', 'w') as cc_netstat_output:
            subprocess.Popen(["./netstat.py", cc_meas_starts[i][2].name, end_cc_netstat_f.name],
                            stdout=cc_netstat_output, cwd=swd).communicate()

def start_instruments(interface):
    instrument_files = []
    instrument_procs =[]

    # CPU load
    cpuload_f = tempfile.NamedTemporaryFile()
    cpuload_p = subprocess.Popen(['./cpuload.sh'], stdout=cpuload_f, cwd=swd)
    instrument_files.append(cpuload_f)
    instrument_procs.append(cpuload_p)

    # xdp
    with open(f'xdp.{experiment}.out', 'w') as brtt_f:
        # if int(args.container) > 0:
        #     brtt_p = subprocess.Popen(["./xdpts", "-i", interface, "-I", "xdp", "-x", "native", "-r" "0.001", "-V"],
        #                               stdout=brtt_f, cwd=os.path.join(swd, '../xdpts'))
        # else:
        #     brtt_p = subprocess.Popen(["./xdpts", "-i", interface, "-I", "xdp", "-x", "native", "-r" "0.001"],
        #                               stdout=brtt_f, cwd=os.path.join(swd, '../xdpts'))
        if int(args.container) > 0:
            brtt_p = subprocess.Popen(["./tcxdp", "-i", interface, "-I", "xdp", "-x", "native", "-r" "0.001", "-V"],
                                      stdout=brtt_f, cwd=os.path.join(swd, '../tcxdp'))
        else:
            brtt_p = subprocess.Popen(["./tcxdp", "-i", interface, "-I", "xdp", "-x", "native", "-r" "0.001"],
                                      stdout=brtt_f, cwd=os.path.join(swd, '../tcxdp'))
    instrument_files.append(brtt_f)
    instrument_procs.append(brtt_p)

    # rack
    with open(f'rack.{experiment}.out', 'w') as trtt_rack_f:
        trtt_rack_p = subprocess.Popen(["./rack.bt"],
                                  stdout=trtt_rack_f, cwd=os.path.join(swd, '../bpftraces'))
    instrument_files.append(trtt_rack_f)
    instrument_procs.append(trtt_rack_p)

    # fq
    with open(f'fq.{experiment}.out', 'w') as fq_delay_f:
        fq_delay_p = subprocess.Popen(["./fq.bt"],
                                  stdout=fq_delay_f, cwd=os.path.join(swd, '../bpftraces'))
    instrument_files.append(fq_delay_f)
    instrument_procs.append(fq_delay_p)
    
    # sock
    with open(f'sock.{experiment}.out', 'w') as sock_f:
        sock_p = subprocess.Popen(["./sock.bt"],
                                  stdout=sock_f, cwd=os.path.join(swd, '../bpftraces'))
    instrument_files.append(sock_f)
    instrument_procs.append(sock_p)

    # write_xmit
    with open(f'write.{experiment}.out', 'w') as write_f:
        write_p = subprocess.Popen(["./write_xmit.bt"],
                                  stdout=write_f, cwd=os.path.join(swd, '../bpftraces'))
    instrument_files.append(write_f)
    instrument_procs.append(write_p)

    return (instrument_files, instrument_procs)

def start_sock_instrument(interface):
    instrument_files = []
    instrument_procs =[]

    # sock
    with open(f'sock.{experiment}.out', 'w') as sock_f:
        sock_p = subprocess.Popen(["./sock.bt"],
                                  stdout=sock_f, cwd=os.path.join(swd, '../bpftraces'))
    instrument_files.append(sock_f)
    instrument_procs.append(sock_p)

    return (instrument_files, instrument_procs)

def end_instruments(instrument_files, instruments_procs):
    for proc in instruments_procs:
        proc.kill()

    with open(f'cpu.{experiment}.out', 'w') as cpu_output:
        subprocess.Popen(["./cpu.py", instrument_files[0].name], stdout=cpu_output, cwd=swd).communicate()

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

def run_iperf_clients(num_hflows, num_cflows, duration, server_addr, server_pods, client_pods):
    hflows = []
    cflows = []
    processes = []

    # Host flows
    for i in range(0, num_hflows):
        port = 5200 + i
        cport = 45000 + i
        cpu = 16 + i
        iperf_args = ["iperf3", "-c", server_addr, "-p", str(port), "--cport", str(cport), \
                      "-t", str(duration), "-J", "-A", str(cpu)]
        f = open(f'iperf.h{i}.{experiment}.out', 'w+b')
        p = subprocess.Popen(iperf_args, stdout=f, stderr=subprocess.PIPE, cwd='../../scripts')
        
        processes.append((p, f, False))
        hflow = FlowStat()
        hflow.dport = port
        hflows.append(hflow)

    # Container flows
    for i in range(0, num_cflows):
        port = 5200 + i
        cport = 45000 + i
        cpu = 16 + i
        iperf_args = ["kubectl", "exec", client_pods[i][0], "--", \
                      "iperf3", "-c", server_pods[i][1], "-p", str(port), "--cport", str(cport), \
                      "-t", str(duration), "-J", "-A", str(cpu)]
        # iperf_args = ["kubectl", "exec", client_pods[i][0], "--", \
        #               "iperf3", "-c", server_addr, "-p", str(port), "--cport", str(cport), \
        #               "-t", str(duration), "-J", "-A", str(cpu)]
        f = open(f'iperf.c{i}.{experiment}.out', 'w+b')
        p = subprocess.Popen(iperf_args, stdout=f, stderr=subprocess.PIPE)

        processes.append((p, f, True))
        cflow = FlowStat()
        cflow.saddr = "192.168.2.102"
        cflow.daddr = "192.168.2.103"
        cflow.dport = port
        cflows.append(cflow)

    logging.info(f"Start {num_hflows} iperf host flows for {duration} seconds.")
    logging.info(f"Start {num_cflows} iperf container flows for {duration} seconds.")
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
        flow.rtt_mean = data["end"]["streams"][0]["sender"]["mean_rtt"]

        f.close()

        if is_cflow:
            logging.debug(f'c{i}: {flow.sport}, {flow.dport}, {flow.throughput:.3f}, {flow.retransmissions}, {flow.rtt_mean}')
        else:
            logging.debug(f'h{i}: {flow.sport}, {flow.dport}, {flow.throughput:.3f}, {flow.retransmissions}, {flow.rtt_mean}')

    return hflows, cflows

def run_neper_clients(num_hflows, num_cflows, duration, server_addr, server_pods, client_pods):
    hflows = []
    cflows = []
    processes = []

    # Host flows
    for i in range(0, num_hflows):
        port = 5300 + i
        cport = 45000 + i
        cpu = 16 + i
        neper_args = ["numactl", "-C", str(cpu), "./tcp_rr", "--nolog", "-c", "-H", server_addr, \
                      "-l", str(duration), "--source-port", str(cport), "-P", str(port)]
        f = open(f'neper.h{i}.{experiment}.out', 'w+b')
        p = subprocess.Popen(neper_args, stdout=f, stderr=subprocess.PIPE, cwd=swd)
        
        processes.append((p, f, False))
        hflow = FlowStat()
        hflow.dport = port
        hflow.sport = cport
        
        # Neper does not report retransmissions
        hflow.retransmissions = 0
        hflows.append(hflow)
        
    # Container flows
    for i in range(0, num_cflows):
        port = 5300 + i
        cport = 45000 + i
        cpu = 16 + i
        neper_args = ["kubectl", "exec", client_pods[i][0], "--", "numactl", "-C", str(cpu), \
                      "./tcp_rr", "--nolog", "-c", "-H", server_pods[i][1], "-l", str(duration), \
                      "--source-port", str(cport), "-P", str(port)]
        f = open(f'neper.c{i}.{experiment}.out', 'w+b')
        p = subprocess.Popen(neper_args, stdout=f, stderr=subprocess.PIPE)

        processes.append((p, f, True))
        cflow = FlowStat()
        cflow.saddr = "192.168.2.102"
        cflow.daddr = "192.168.2.103"
        cflow.dport = port
        cflow.sport = cport

        # Neper does not report retransmissions
        cflow.retransmissions = 0
        cflows.append(cflow)

    logging.info(f"Start {num_hflows} neper host flows for {duration} seconds.")
    logging.info(f"Start {num_cflows} neper container flows for {duration} seconds.")
    for (p, f, is_cflow) in processes:
        _, err = p.communicate()
        if err != None and err != b'':
            logging.error('neper error:', err.decode('utf-8'))
            return None, None
        
        f.seek(0)
        lines = f.readlines()
        for l in lines:
            tokens = l.decode('utf-8').split('=')
            if tokens[0] == 'port':
                if is_cflow:
                    i, flow = find_flow(cflows, int(tokens[1]))
                else:
                    i, flow = find_flow(hflows, int(tokens[1]))
            elif tokens[0] == 'throughput':
                flow.throughput = float(tokens[1])
            elif tokens[0] == 'latency_mean':
                flow.rtt_mean = float(tokens[1]) * 1000000

        f.close()

        if is_cflow:
            logging.debug(f'c{i}: {flow.sport}, {flow.dport}, {flow.throughput:.3f}, {flow.retransmissions}, {flow.rtt_mean}')
        else:
            logging.debug(f'h{i}: {flow.sport}, {flow.dport}, {flow.throughput:.3f}, {flow.retransmissions}, {flow.rtt_mean}')

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
    parser.add_argument('--no-instrument', action='store_true')
    parser.add_argument('--sock-only', action='store_true')

    global args
    args = parser.parse_args()

    if int(args.host) < 0 or int(args.container) < 0 or (int(args.host) == 0 and int(args.container) == 0):
        print(f"Check the number of flows")
        exit()

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