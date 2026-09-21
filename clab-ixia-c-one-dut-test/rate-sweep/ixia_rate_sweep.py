import contextlib
import io
import json
from pathlib import Path
import re
import subprocess
import time

import snappi

SOURCE = str(Path(__file__).resolve().parents[2] / 'tests' / 'clab-device-endpoint.py')
API = 'https://clab-ixia-c-one-dut-test-ixia-c:8443'
NAMES = ['Device1_to_Device2', 'Device2_to_Device1']


def cli(command):
    return subprocess.check_output(['docker', 'exec', 'clab-ixia-c-one-dut-test-ceos', 'Cli', '-c', command], text=True)


def discards():
    output = cli('show interfaces counters discards')
    result = {}
    for line in output.splitlines():
        match = re.match(r'^(Et[12])\s+(\d+)\s+(\d+)', line)
        if match:
            result[match.group(1)] = int(match.group(2))
    if set(result) != {'Et1', 'Et2'}:
        raise RuntimeError('Cannot parse cEOS InDiscards: ' + output)
    return result


def check_links():
    output = cli('show ip interface brief')
    for port in ('Ethernet1', 'Ethernet2'):
        line = next((line for line in output.splitlines() if line.startswith(port + ' ')), '')
        if not re.search(r'\bup\s+up\b', line):
            raise RuntimeError(port + ' is not up/up: ' + line)


def metrics():
    api = snappi.api(location=API, verify=False)
    req = api.metrics_request()
    req.flow.flow_names = NAMES
    rows = {m.name: m for m in api.get_metrics(req).flow_metrics}
    if set(rows) != set(NAMES):
        raise RuntimeError('Unexpected flow metrics: ' + str(list(rows)))
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


source = open(SOURCE, encoding='utf-8').read()
for pct in (1, 2, 5, 10):
    check_links()
    before = discards()
    modified = source.replace('flow1.rate.percentage = 10', f'flow1.rate.percentage = {pct}').replace('flow2.rate.percentage = 10', f'flow2.rate.percentage = {pct}')
    if modified == source or modified.count(f'rate.percentage = {pct}') != 2:
        raise RuntimeError('Rate substitution failed')
    namespace = {'__name__': f'rate_{pct}'}
    exec(compile(modified, SOURCE, 'exec'), namespace)
    print(f'START rate={pct} before={before}', flush=True)
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            namespace['test_device_endpoint_minimum']()
        time.sleep(1)
        after = discards()
        flows = metrics()
        check_links()
        if any(item['state'] != 'stopped' or item['tx'] == 0 for item in flows.values()):
            raise RuntimeError('Unexpected flow state/count: ' + json.dumps(flows))
        print(json.dumps({'rate': pct, 'before': before, 'after': after, 'delta': {p: after[p] - before[p] for p in before}, 'flows': flows}), flush=True)
    except Exception:
        try:
            cleanup()
        finally:
            raise
