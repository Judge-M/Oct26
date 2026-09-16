"""H01a - reconstruct neutral native records from published inputs.

Reads a materialized ``originals/windows`` tree (see ``expanded.materialize_native``)
or the published sidecars, and writes a new versioned record directory. Viewer and
parent PIDs come from acquisition provenance, never from literals; every timestamp is
copied verbatim from the source record. Raw/source hashes are verified before any
record is published.
"""
import argparse
import json
import os
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

from ridge.artifacts import safe, sha256
from buildpipe import BuildEnvironmentError

EVENT_NS = {'e': 'http://schemas.microsoft.com/win/2004/08/events/event'}
TASK_NS = {'t': 'http://schemas.microsoft.com/windows/2004/02/mit/task'}
PROCESS_EVENT = 4688
TASK_EVENT = 4698
DEFAULT_VERSION = 'native-windows-v2'


def _read_json(path, encoding='utf-8-sig'):
    try:
        return json.loads(Path(path).read_text(encoding=encoding))
    except (OSError, ValueError) as error:
        raise ValueError('Unreadable JSON input: ' + str(path)) from error


def load_provenance(source):
    provenance = _read_json(Path(source) / 'native-provenance.json')
    for field in ('viewer_pid', 'parent_pid'):
        if not isinstance(provenance.get(field), int):
            raise ValueError('Provenance must record integer ' + field)
    return provenance


def _fields(xml):
    return {node.attrib['Name']: node.text for node in xml.findall('e:EventData/e:Data', EVENT_NS)}


def _sidecar(source, name):
    path = Path(source) / name
    if not path.is_file():
        return []
    rows = _read_json(path)
    if not isinstance(rows, list):
        raise ValueError('EVTX sidecar must be a list: ' + name)
    return rows


def _time_created(xml):
    node = xml.find('e:System/e:TimeCreated', EVENT_NS)
    if node is None or not node.attrib.get('SystemTime'):
        raise ValueError('Event record has no creation time')
    return node.attrib['SystemTime']


def select_process_event(rows, event_id, viewer_pid, field='NewProcessId', radix=16):
    for row in rows:
        if row.get('Id') != event_id or not row.get('Xml'):
            continue
        try:
            xml = ET.fromstring(row['Xml'])
        except ET.ParseError as error:
            raise ValueError('Malformed event XML') from error
        fields = _fields(xml)
        try:
            observed = int(fields[field], radix)
        except (KeyError, TypeError, ValueError):
            continue
        if observed == viewer_pid:
            return row, xml, fields
    raise ValueError(f'No event {event_id} references process {viewer_pid}')


def _find_by_pid(rows, pid):
    for row in rows:
        if int(row.get('PID', -1)) == pid:
            return row
    raise ValueError('Process record missing for PID ' + str(pid))


def _record_processes(source, provenance, security_rows):
    viewer_pid = provenance['viewer_pid']
    parent_pid = provenance['parent_pid']
    row, xml, fields = select_process_event(security_rows, PROCESS_EVENT, viewer_pid)
    if int(fields.get('ProcessId', '0x0'), 16) != parent_pid:
        raise ValueError('Acquisition event parent PID differs from provenance')
    return dict(event_id=PROCESS_EVENT, record_id=row.get('RecordId'), fields=fields,
                utc=_time_created(xml), capture_host=xml.find('e:System/e:Computer', EVENT_NS).text,
                original_path='/originals/windows/Security.evtx',
                original_sha256=sha256(Path(source) / 'Security.evtx'),
                parser='Get-WinEvent PowerShell; source XML preserved',
                command='Get-WinEvent -Path Security.evtx | ForEach-Object { $_.ToXml() }',
                pid=viewer_pid, ppid=parent_pid, process=fields.get('NewProcessName'),
                parent=fields.get('ParentProcessName'))


def _record_task(source, provenance, security_rows):
    viewer_pid = provenance['viewer_pid']
    parent_pid = provenance['parent_pid']
    row, xml, fields = select_process_event(security_rows, TASK_EVENT, viewer_pid,
                                            field='ClientProcessId', radix=10)
    if int(fields.get('ParentProcessId', '0')) != parent_pid:
        raise ValueError('Task event parent PID differs from provenance')
    task_xml = ET.fromstring(fields['TaskContent'])
    executable = task_xml.find('t:Actions/t:Exec/t:Command', TASK_NS)
    if executable is None or not executable.text:
        raise ValueError('Task event has no executable command')
    return dict(event_id=TASK_EVENT, record_id=row.get('RecordId'), fields=fields,
                utc=_time_created(xml), capture_host=xml.find('e:System/e:Computer', EVENT_NS).text,
                original_path='/originals/windows/Security.evtx',
                original_sha256=sha256(Path(source) / 'Security.evtx'),
                parser='Get-WinEvent PowerShell; source XML preserved',
                command='Get-WinEvent -Path Security.evtx | ForEach-Object { $_.ToXml() }',
                task=fields.get('TaskName', '').lstrip('\\'), pid=viewer_pid,
                executable=executable.text)


def _record_memory(source, provenance, common):
    viewer_pid = provenance['viewer_pid']
    parent_pid = provenance['parent_pid']
    pslist = _read_json(Path(source) / 'analysis/memory-pslist.json')
    cmdlines = _read_json(Path(source) / 'analysis/memory-cmdline.json')
    viewer = _find_by_pid(pslist, viewer_pid)
    parent = _find_by_pid(pslist, int(viewer.get('PPID', parent_pid)))
    command = _find_by_pid(cmdlines, viewer_pid)
    memory_hash = _read_json(Path(source) / 'memory-sha256.json')['Hash'].lower()
    return dict(common, pid=viewer['PID'], ppid=parent['PID'],
                process_kernel_name=viewer['ImageFileName'], parent=parent['ImageFileName'],
                command_line=command['Args'], utc=viewer['CreateTime'],
                memory_offset=hex(viewer['Offset(V)']), address_space='kernel virtual',
                original_path='/originals/windows/WS17.raw', original_sha256=memory_hash,
                parser='Volatility 3 2.28.0',
                commands=['vol -c memory-layer.json -r json windows.pslist',
                          f'vol -c memory-layer.json -r json windows.cmdline --pid {viewer_pid} {parent_pid}'],
                process_record=viewer, parent_record=parent)


def _record_connections(source, provenance, common, port):
    viewer_pid = provenance['viewer_pid']
    rows = _read_json(Path(source) / 'observed-connections.json')
    owned = [row for row in rows if int(row.get('OwningProcess', -1)) == viewer_pid]
    if port is not None:
        owned = [row for row in owned if int(row.get('RemotePort', -1)) == port]
    if len(owned) != 1:
        raise ValueError('Expected exactly one connection owned by the acquired process')
    connection = owned[0]
    return dict(common, pid=viewer_pid, remote=connection['RemoteAddress'],
                port=connection['RemotePort'], state='ESTABLISHED', record=connection,
                original_path='/originals/windows/observed-connections.json',
                original_sha256=sha256(Path(source) / 'observed-connections.json'),
                parser='Windows Get-NetTCPConnection, captured immediately before acquisition',
                command=f'Get-NetTCPConnection -OwningProcess {viewer_pid} | ConvertTo-Json',
                limitation='Live guest snapshot, not a memory-derived connection finding.',
                topology='Guest loopback only; external networking was disabled')


def _verify_source_hashes(source, expected):
    for name, digest in (expected or {}).items():
        path = safe(source, name)
        if not path.is_file() or sha256(path) != digest:
            raise ValueError('Source hash mismatch: ' + name)


def _verify_raw(source):
    raw = Path(source) / 'WS17.raw'
    memory = Path(source) / 'memory-sha256.json'
    if not raw.is_file() or not memory.is_file():
        return
    expected = _read_json(memory).get('Hash', '').lower()
    if expected and sha256(raw) != expected:
        raise ValueError('Acquired memory image differs from recorded hash')


def build(source, destination, version=DEFAULT_VERSION, source_hashes=None, connection_port=443):
    source, destination = Path(source), Path(destination)
    if destination.exists():
        raise ValueError('Choose a new record directory; existing records are never overwritten')
    provenance = load_provenance(source)
    _verify_source_hashes(source, source_hashes)
    _verify_raw(source)
    security = _sidecar(source, 'Security.evtx.records.json')
    if not security:
        raise ValueError('Security.evtx.records.json is required; export it with '
                         'python -m buildpipe native --export-evtx Security.evtx')
    common = dict(provenance='Native artifacts acquired from an isolated training reconstruction; not original incident acquisition',
                  scenario_host=provenance.get('scenario_host'),
                  clock_semantics='Actual acquisition UTC; do not apply the historical device offset')
    records = {
        'windows-process.json': _record_processes(source, provenance, security),
        'windows-task.json': _record_task(source, provenance, security),
        'memory-processes.json': _record_memory(source, provenance, common),
        'windows-connections.json': _record_connections(source, provenance, common, connection_port),
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix='.native-records-', dir=destination.parent))
    try:
        prepared = temporary / 'prepared'
        prepared.mkdir()
        for name, record in records.items():
            (prepared / name).write_text(json.dumps(record, indent=2, sort_keys=True) + '\n', encoding='utf-8')
        manifest = dict(schema=1, version=version, viewer_pid=provenance['viewer_pid'],
                        parent_pid=provenance['parent_pid'], source_sha256=dict(source_hashes or {}),
                        files={f'prepared/{name}': sha256(prepared / name) for name in records},
                        event_ready=False)
        (temporary / 'manifest.json').write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n', encoding='utf-8')
        os.replace(temporary, destination)
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return manifest


def evtx_export_command(evtx, destination):
    script = ("$ErrorActionPreference='Stop'; "
              "Get-WinEvent -Path " + _quote(evtx) + " | ForEach-Object { "
              "[pscustomobject]@{Id=$_.Id;RecordId=$_.RecordId;Xml=$_.ToXml()} } | "
              "ConvertTo-Json -Depth 6 | Set-Content -LiteralPath " + _quote(destination) + " -Encoding UTF8")
    return ['powershell', '-NoProfile', '-NonInteractive', '-Command', script]


def _quote(value):
    return "'" + str(value).replace("'", "''") + "'"


def export_evtx(evtx, destination):
    if os.name != 'nt':
        raise BuildEnvironmentError('Get-WinEvent export requires a Windows host')
    destination = Path(destination)
    if destination.exists():
        raise ValueError('Choose a new sidecar destination; existing files are never overwritten')
    destination.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(evtx_export_command(evtx, destination), check=True)
    if not destination.is_file():
        raise ValueError('EVTX export did not produce a sidecar')
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--destination', required=True, type=Path)
    parser.add_argument('--version', default=DEFAULT_VERSION)
    parser.add_argument('--export-evtx', type=Path, metavar='EVTX',
                        help='Export a Windows event log sidecar instead of building records')
    args = parser.parse_args()
    if args.export_evtx:
        print(export_evtx(args.export_evtx, args.destination))
    else:
        print(json.dumps(build(args.source, args.destination, args.version), indent=2))


if __name__ == '__main__':
    main()
