#!/usr/bin/python3
import subprocess
import tempfile
import argparse
import os
import sys

def main():
    num_flows = int(args.flow)
    time = int(args.time)
    cca = "bbr"

    global experiment

    if args.vxlan:
        experiment = f"rx-e-f{num_flows}-t{time}-{cca}-0"
    else:
        experiment = f"rx-h-f{num_flows}-t{time}-{cca}-0"

    (util_p, util_f) = start_cpu_utilization()
    interrupt_f = start_interrupt_count()

    print("Press \'e\' to end the recording.")
    while True:
        line = sys.stdin.readline().strip()
        if line == "e":
            break

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
    parser.add_argument('--silent', '-s', action='store_true')
    parser.add_argument('--vxlan', '-v', action='store_true')

    global args
    args = parser.parse_args()
    main()