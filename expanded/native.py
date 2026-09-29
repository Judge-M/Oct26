"""Load the reviewed native reconstruction without rewriting historic facts."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / 'assets/native-windows-v1'


def records(root=ROOT):
    root = Path(root)
    manifest = json.loads((root / 'manifest.json').read_text(encoding='utf-8'))
    expected = {'windows-process', 'windows-task', 'memory-processes', 'windows-connections'}
    if set(manifest['files']) != {f'prepared/{name}.json' for name in expected}:
        raise ValueError('Incomplete native evidence record inventory')
    result = {}
    for name in expected:
        data = (root / f'prepared/{name}.json').read_bytes()
        if hashlib.sha256(data).hexdigest() != manifest['files'][f'prepared/{name}.json']:
            raise ValueError('Native record checksum mismatch: ' + name)
        result[name] = json.loads(data)
    return result


def question_overrides():
    native = records()
    process, task = native['windows-process'], native['windows-task']
    memory, connection = native['memory-processes'], native['windows-connections']
    process_time, task_time = process['utc'][11:19], task['utc'][11:19]
    return {
        13: ('Inspect acquired process-log records', 'prepared/windows-process.json', [
            ('Which process ID belongs to the acquired viewer?', str(process['pid'])),
            ('What is its parent executable?', 'browser.exe'),
            ('Which scenario workstation is this lab reconstruction mapped to?', process['scenario_host']),
            ('What actual acquisition UTC time is recorded for process creation?', process_time)], [
            f"Native Security record {process['record_id']} records viewer PID {process['pid']}.",
            'The native process event names browser.exe as the parent training surrogate.',
            'The acquisition manifest maps this isolated lab reconstruction to WS-17; the original computer name is preserved.',
            f'The reconstructed process was created at {process_time} UTC on {process["utc"][:10]}; no historic clock correction applies.']),
        14: ('Inspect acquired task-log records', 'prepared/windows-task.json', [
            ('What task name was registered?', task['task']),
            ('What executable does the task target?', 'brief-viewer.exe'),
            ('What actual acquisition UTC time is recorded for registration?', task_time),
            ('Should the historical 120-second offset be applied to this native acquisition?', 'no')], [
            f"Native Security record {task['record_id']} records the BriefSync task.",
            'The captured task XML targets the harmless brief-viewer.exe training surrogate.',
            f'The reconstructed task was registered at {task_time} UTC on {task["utc"][:10]}.',
            'Acquisition timestamps describe the lab capture and must not be rewritten as historical incident timestamps.']),
        15: ('Inspect the prepared memory process tree', 'prepared/memory-processes.json', [
            ('What viewer PID is present in the prepared capture?', str(memory['pid'])),
            ('What parent PID is recorded?', str(memory['ppid'])),
            ('What executable belongs to the parent?', memory['parent']),
            ('What path is supplied to the viewer as its cache argument?', 'C:/Temp/move-cache.txt')], [
            f"Volatility recovered viewer PID {memory['pid']} at kernel virtual offset {memory['memory_offset']}.",
            f"The recovered viewer process records parent PID {memory['ppid']}.",
            'The recovered parent process name is browser.exe; it is a training surrogate.',
            'The memory-derived command line contains cache argument C:/Temp/move-cache.txt.']),
        16: ('Correlate the acquired connection snapshot', 'prepared/windows-connections.json', [
            ('Which PID owns the recorded training connection?', str(connection['pid'])),
            ('What remote address is recorded?', connection['remote']),
            ('What remote port is recorded?', str(connection['port'])),
            ('Does this connection record prove a human read a payload?', 'no')], [
            f"The guest's native connection snapshot records PID {connection['pid']}.",
            '198.51.100.77 was a guest-local loopback address in this reconstruction; no Internet traffic occurred.',
            'The native snapshot records TCP remote port 443.',
            'This is a live acquisition sidecar, not a validated memory connection finding or evidence of human reading.']),
    }
