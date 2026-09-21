import contextlib
import io
import json
from pathlib import Path
import re
import subprocess
import threading
import time

import snappi

SOURCE = str(Path(__file__).resolve().parents[2] / 'tests' / 'clab-device-endpoint.py')
API = 'https://clab-ixia-c-one-dut-test-ixia-c:8443'
NAMES = ['Device1_to_Device2', 'Device2_to_Device1']
CEOS = 'clab-ixia-c-one-dut-test-ceos'
HZ = 100


def command(args):
    return subprocess.check_output(args, text=True).strip()


def ceos_cli(text):
    return command(['docker', 'exec', CEOS, 'Cli', '-c', text])


def discards():
    output = ceos_cli('show interfaces counters discards')
    rows = {}
    for line in output.splitlines():
        m = re.match(r'^(Et[12])\s+(\d+)\s+\d+', line)
        if m:
            rows[m.group(1)] = int(m.group(2))
    if set(rows) != {'Et1', 'Et2'}:
        raise RuntimeError('Cannot parse discards: ' + output)
    return rows


def etba_cpu_time():
    processes = command(['docker', 'exec', CEOS, 'ps', '-eo', 'pid=,comm='])
    pids = [line.split()[0] for line in processes.splitlines() if line.split()[-1] == 'Etba']
    if len(pids) != 1:
        raise RuntimeError('Expected exactly one Etba process; found ' + str(pids))
    stat = command(['docker', 'exec', CEOS, 'cat', f'/proc/{pids[0]}/stat'])
    fields = stat.rsplit(')', 1)[1].split()
    return (int(fields[11]) + int(fields[12])) / HZ


def check_links():
    output = ceos_cli('show ip interface brief')
    for port in ('Ethernet1', 'Ethernet2'):
        line = next((line for line in output.splitlines() if line.startswith(port + ' ')), '')
        if not re.search(r'\bup\s+up\b', line):
            raise RuntimeError(port + ' not up/up: ' + line)


def metrics():
    api = snappi.api(location=API, verify=False)
    req = api.metrics_request()
    req.flow.flow_names = NAMES
    rows = {m.name: m for m in api.get_metrics(req).flow_metrics}
    if set(rows) != set(NAMES):
        raise RuntimeError('Unexpected metrics: ' + str(list(rows)))
    return {name: {'tx': int(rows[name].frames_tx), 'rx': int(rows[name].frames_rx), 'state': rows[name].transmit} for name in NAMES}


def cleanup():
    api = snappi.api(location=API, verify=False)
    state = api.control_state()
    state.traffic.flow_transmit.state = state.traffic.flow_transmit.STOP
    state.traffic.flow_transmit.flow_names = NAMES
    api.set_control_state(state)
    state = api.control_state()
    state.protocol.all.state = state.protocol.all.STOP
    api.set_control_state(state)


sample = {}
sample_thread = None


def sample_start():
    global sample, sample_thread
    sample = {}
    def worker():
        try:
            time.sleep(3)
            first = etba_cpu_time()
            first_wall = time.monotonic()
            time.sleep(2)
            second = etba_cpu_time()
            second_wall = time.monotonic()
            sample['etba_pct_one_core'] = 100 * (second - first) / (second_wall - first_wall)
            stats = command(['docker', 'stats', '--no-stream', '--format', '{{.CPUPerc}}', CEOS])
            sample['container_cpu_pct'] = stats
        except Exception as e:
            sample['error'] = str(e)
    sample_thread = threading.Thread(target=worker, daemon=True)
    sample_thread.start()


source = open(SOURCE, encoding='utf-8').read()
for pct in (0.1, 0.2, 0.5):
    check_links()
    before_drop = discards()
    before_cpu = etba_cpu_time()
    modified = source.replace('flow1.rate.percentage = 10', f'flow1.rate.percentage = {pct}').replace('flow2.rate.percentage = 10', f'flow2.rate.percentage = {pct}')
    if modified.count(f'rate.percentage = {pct}') != 2:
        raise RuntimeError('Rate substitution failed')
    modified = modified.replace('print("Traffic Started")', 'print("Traffic Started"); sample_start()')
    namespace = {'__name__': f'rate_{pct}', 'sample_start': sample_start}
    exec(compile(modified, SOURCE, 'exec'), namespace)
    print(f'START rate={pct} discards={before_drop} etba_seconds={before_cpu}', flush=True)
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            namespace['test_device_endpoint_minimum']()
        sample_thread.join(timeout=5)
        time.sleep(1)
        after_drop = discards()
        after_cpu = etba_cpu_time()
        flows = metrics()
        check_links()
        if any(row['state'] != 'stopped' or row['tx'] == 0 for row in flows.values()):
            raise RuntimeError('Unexpected flow state/count: ' + json.dumps(flows))
        print(json.dumps({'rate': pct, 'before_discards': before_drop, 'after_discards': after_drop, 'delta_discards': {port: after_drop[port] - before_drop[port] for port in before_drop}, 'before_etba_seconds': before_cpu, 'after_etba_seconds': after_cpu, 'delta_etba_seconds': after_cpu - before_cpu, 'during_sample': sample, 'flows': flows}), flush=True)
    except Exception:
        try:
            cleanup()
        finally:
            raise
