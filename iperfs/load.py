#!/usr/bin/python3
import subprocess
import tempfile
import argparse
import os
import signal
import sys

def main():
    num_flows = int(args.flow)
    time = int(args.time)
    app = args.app
    cca = "bbr"

    global experiment

    if args.vxlan:
        experiment = f"rx-e-f{num_flows}-t{time}-{cca}-{app}-0"
    elif args.native:
        experiment = f"rx-n-f{num_flows}-t{time}-{cca}-{app}-0"
    else:
        experiment = f"rx-h-f{num_flows}-t{time}-{cca}-{app}-0"

    if args.app == "neper":
        neper_processes = start_neper_servers(num_flows)

    (util_p, util_f) = start_cpu_utilization()
    interrupt_f = start_interrupt_count()

    print("Press \'Enter\' to end the recording.")
    line = sys.stdin.readline()

    if not os.path.exists("../data"):
        os.mkdir("../data")
    os.chdir("../data")
    
    while os.path.exists(experiment):
        (remained, last) = experiment.rsplit("-", 1)
        trial = int(last) + 1
        experiment = f"{remained}-{trial}"

    os.mkdir(experiment)
    os.chdir(experiment)

    end_cpu_utilization(util_p, util_f)
    post_process_interrupt_count(interrupt_f)

    if args.app == "neper":
        end_neper_servers(neper_processes)

def start_neper_servers(num_flows):
    neper_processes = []
    for i in range(0, num_flows):
        port = 5300 + i
<<<<<<< Updated upstream
        cpu = 16 + i
        neper_args = ["numactl", -"C", str(cpu), "./tcp_rr", "--nolog", "-P", str(port), "-l", args.time]
=======
        neper_args = ["./tcp_rr", "--nolog", "-P", str(port), "-l", args.time]
>>>>>>> Stashed changes
        f = tempfile.TemporaryFile()
        p = subprocess.Popen(neper_args, stdout=f)
        neper_processes.append(p)

    return neper_processes

def end_neper_servers(neper_processes):
    for process in neper_processes:
        os.kill(process.pid, signal.SIGTERM)

def start_cpu_utilization():
    f = tempfile.NamedTemporaryFile()
    p = subprocess.Popen(["./cpuload.sh"], stdout=f)

    return (p, f)

def end_cpu_utilization(p, f):
    p.kill()
    with open(f'cpu.{experiment}.out', 'w') as cpu_output:
        subprocess.run(["../../iperfs/cpu.py", f.name], stdout=cpu_output)

    if not args.silent:
        subprocess.run(["../../iperfs/cpu.py", "-c", f.name])
    
def start_interrupt_count():
    f = tempfile.NamedTemporaryFile()
    subprocess.run(["cat", "/proc/interrupts"], stdout=f)

    return f

def post_process_interrupt_count(old_f):
    new_f = tempfile.NamedTemporaryFile()
    subprocess.run(["cat", "/proc/interrupts"], stdout=new_f)

    with open(f'int.{experiment}.out', 'w') as interrupt_output:
        subprocess.run(["../../iperfs/interrupts.py", old_f.name, new_f.name], stdout=interrupt_output)

    if not args.silent:
        subprocess.run(["../../iperfs/interrupts.py", old_f.name, new_f.name])

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--flow', '-f', default=6)
    parser.add_argument('--time', '-t', default=60)
    parser.add_argument('--app', '-a', default='iperf')
    parser.add_argument('--silent', '-s', action='store_true')
    parser.add_argument('--vxlan', '-v', action='store_true')
    parser.add_argument('--native', '-n', action='store_true')

    global args
    args = parser.parse_args()
    main()