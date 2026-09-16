import json
import sqlite3
from pathlib import Path
from xml.sax.saxutils import escape

from ridge.artifacts import sha256

EVENT_XML = ('<Event xmlns="http://schemas.microsoft.com/win/2004/08/events/event">'
             '<System><Computer>{computer}</Computer>'
             '<TimeCreated SystemTime="{time}"/></System>'
             '<EventData>{data}</EventData></Event>')


def event_xml(fields, computer='1CA9BC0F-EF75-4', time='2026-09-15T23:22:00.0000000Z'):
    data = ''.join(f'<Data Name="{key}">{escape(str(value))}</Data>' for key, value in fields.items())
    return EVENT_XML.format(computer=computer, time=time, data=data)


def native_source(root, viewer_pid=6364, parent_pid=7644):
    source = Path(root)
    source.mkdir(parents=True, exist_ok=True)
    (source / 'WS17.raw').write_bytes(b'fixture memory image')
    (source / 'Security.evtx').write_bytes(b'fixture evtx bytes')
    (source / 'memory-sha256.json').write_text(json.dumps(
        {'Algorithm': 'SHA256', 'Hash': sha256(source / 'WS17.raw')}))
    (source / 'native-provenance.json').write_text(json.dumps(dict(
        scenario_host='WS-17', capture_host='1CA9BC0F-EF75-4', viewer_pid=viewer_pid,
        parent_pid=parent_pid, capture_time_utc='2026-09-15T23:22:04Z',
        clock_semantics='Actual acquisition UTC; no historic clock shift applied')))
    task_content = ('<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">'
                    '<Actions><Exec><Command>C:\\Fixture\\brief-viewer.exe</Command></Exec></Actions></Task>')
    records = [
        {'Id': 4688, 'RecordId': 606, 'Xml': event_xml({
            'NewProcessId': hex(viewer_pid), 'ProcessId': hex(parent_pid),
            'NewProcessName': 'C:\\Fixture\\brief-viewer.exe',
            'ParentProcessName': 'C:\\Fixture\\browser.exe'})},
        {'Id': 4698, 'RecordId': 607, 'Xml': event_xml({
            'ClientProcessId': str(viewer_pid), 'ParentProcessId': str(parent_pid),
            'TaskName': '\\BriefSync', 'TaskContent': task_content})},
    ]
    (source / 'Security.evtx.records.json').write_text(json.dumps(records))
    (source / 'observed-connections.json').write_text(json.dumps([
        {'OwningProcess': viewer_pid, 'RemotePort': 443, 'RemoteAddress': '198.51.100.77',
         'LocalAddress': '198.51.100.77', 'LocalPort': 49673, 'State': 5}]))
    analysis = source / 'analysis'
    analysis.mkdir()
    (analysis / 'memory-pslist.json').write_text(json.dumps([
        {'PID': parent_pid, 'PPID': 8544, 'ImageFileName': 'browser.exe',
         'Offset(V)': 221565838229632, 'CreateTime': '2026-09-15T23:22:00+00:00'},
        {'PID': viewer_pid, 'PPID': parent_pid, 'ImageFileName': 'brief-viewer.e',
         'Offset(V)': 221565856223360, 'CreateTime': '2026-09-15T23:22:00+00:00'}]))
    (analysis / 'memory-cmdline.json').write_text(json.dumps([
        {'PID': viewer_pid, 'Args': '"C:\\Fixture\\brief-viewer.exe" --cache C:/Temp/move-cache.txt'}]))
    return source


def case_fixture(root, ingest=2):
    root = Path(root)
    case = root / 'cases' / 'WS17'
    case.mkdir(parents=True)
    (case / 'WS17.aut').write_text('case')
    connection = sqlite3.connect(case / 'autopsy.db')
    connection.executescript(
        'CREATE TABLE ingest_jobs(status_id INTEGER, start_date_time TEXT, end_date_time TEXT);'
        'CREATE TABLE tsk_files(name TEXT, size INTEGER);')
    connection.execute('INSERT INTO ingest_jobs VALUES (?,?,?)', (ingest, '2026-09-15', '2026-09-15'))
    connection.execute('INSERT INTO ingest_jobs VALUES (?,?,?)', (ingest, '2026-09-15', '2026-09-15'))
    connection.execute("INSERT INTO tsk_files VALUES ('_OVECACH.TXT', 137)")
    connection.commit()
    connection.close()
    (case / 'ModuleOutput' / 'keywordsearch').mkdir(parents=True)
    (case / 'ModuleOutput' / 'keywordsearch' / 'segments_1').write_bytes(b'index')
    evidence = root / 'evidence'
    (evidence / 'disk').mkdir(parents=True)
    (evidence / 'disk' / 'WS17-fat16.img').write_bytes(b'disk fixture')
    (evidence / 'prepared').mkdir()
    (evidence / 'prepared' / 'memory-processes.json').write_text('{}')
    return case, evidence
