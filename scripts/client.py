#!/usr/bin/python3
import subprocess
import tempfile
import os
import sys
import time
import argparse
import logging

def main():
    global iwd
    iwd = os.getcwd()

    global experiment
    experiment = f"run-0"

    initialize_nic()

    if not os.path.exists(os.path.join(iwd, '..', 'output')):
        os.mkdir(os.path.join(iwd, '..', 'output'))
    os.chdir(os.path.join(iwd, '..', 'output'))

    while os.path.exists(os.path.join(iwd, '..', 'output', experiment)):
        (remained, last) = experiment.rsplit("-", 1)
        trial = int(last) + 1
        experiment = f"{remained}-{trial}"

    os.mkdir(os.path.join(iwd, '..', 'output', experiment))
    os.chdir(os.path.join(iwd, '..', 'output', experiment))

    if not args.no_instrument:
        measurement_starts = start_system_measurements()
        (instrument_files, instrument_procs) = start_instruments()
    
    time.sleep(1)

    print(f"{experiment}. Press \'Enter\' to end the recording.")
    _ = sys.stdin.readline()

    if not args.no_instrument:
        end_system_measurements(measurement_starts)
        end_instruments(instrument_files, instrument_procs)

    # sock trace only for checking spurious retransmissions
    if args.no_instrument and args.sock_only:
        for proc in instrument_procs:
            proc.kill()

def initialize_nic():
    logging.info("Initialize ice driver.")
    subprocess.run(["rmmod", "ice"])
    time.sleep(0.5)
    subprocess.run(["modprobe", "ice"])
    time.sleep(0.5)
    subprocess.Popen(["./flow_direction_rx_tcp.sh"], stdout=subprocess.DEVNULL, cwd=iwd).communicate()
    subprocess.Popen(["./smp_affinity.sh"], stdout=subprocess.DEVNULL, cwd=iwd).communicate()

def start_system_measurements():
    measurements_starts = []

    # interrupts
    interrupts_f = tempfile.NamedTemporaryFile()
    subprocess.run(["cat", "/proc/interrupts"], stdout=interrupts_f)
    measurements_starts.append(interrupts_f)

    # softirqs
    softirqs_f = tempfile.NamedTemporaryFile()
    subprocess.run(["cat", "/proc/softirqs"], stdout=softirqs_f)
    measurements_starts.append(softirqs_f)

    return measurements_starts

def end_system_measurements(measurements_starts):
    # interrupts
    end_interrupts_f = tempfile.NamedTemporaryFile()
    subprocess.run(["cat", "/proc/interrupts"], stdout=end_interrupts_f)
    with open(f'interrupts.{experiment}.out', 'w') as interrupts_output:
        subprocess.Popen(["./interrupts.py", measurements_starts[0].name, end_interrupts_f.name],
                         stdout=interrupts_output, cwd=iwd).communicate()

    # softirqs
    end_softirqs_f = tempfile.NamedTemporaryFile()
    subprocess.run(["cat", "/proc/softirqs"], stdout=end_softirqs_f)
    with open(f'softirqs.{experiment}.out', 'w') as softirqs_output:
        subprocess.Popen(["./softirqs.py", measurements_starts[1].name, end_softirqs_f.name],
                         stdout=softirqs_output, cwd=iwd).communicate()

def start_instruments():
    instrument_files = []
    instrument_procs =[]

    # CPU load
    cpuload_f = tempfile.NamedTemporaryFile()
    cpuload_p = subprocess.Popen(['./cpuload.sh'], stdout=cpuload_f, cwd=iwd)
    instrument_files.append(cpuload_f)
    instrument_procs.append(cpuload_p)

    return (instrument_files, instrument_procs)

def end_instruments(instrument_files, instruments_procs):
    for proc in instruments_procs:
        proc.kill()

    with open(f'cpu.{experiment}.out', 'w') as cpu_output:
        subprocess.Popen(["./cpu.py", instrument_files[0].name], stdout=cpu_output, cwd=iwd).communicate()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--log', '-l', default="warning")
    parser.add_argument('--no-instrument', action='store_true')

    global args
    args = parser.parse_args()

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