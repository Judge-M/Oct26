"""Deterministic synthetic evidence. No live traffic, exploitation, or external data."""
import csv
import hashlib
import io
import json
import shutil
import socket
import sqlite3
import struct
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CELLS = ('network', 'endpoint', 'identity', 'server', 'hunting')


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def manifest(root):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob('*')) if p.is_file() and p.name != 'SHA256SUMS.json'}


def stamp(root):
    (root / 'SHA256SUMS.json').write_text(json.dumps(manifest(root), indent=2) + '\n')


def check(root):
    expected = json.loads((root / 'SHA256SUMS.json').read_text())
    if expected != manifest(root):
        raise ValueError(f'Integrity failure: {root}')
    return len(expected)


def generate(output, config=None):
    output = Path(output)
    if output.exists():
        raise ValueError('Generation destination must not exist; use a new directory')
    config = config or json.loads((REPO / 'config.json').read_text())
    day = datetime.strptime(config['exercise_date'], '%Y-%m-%d').replace(tzinfo=timezone.utc)
    def ts(time):
        return day.strftime('%Y-%m-%dT') + time + 'Z'
    initial = output / 'initial'
    initial.mkdir(parents=True)
    shutil.copytree(REPO / 'participants', initial / 'handouts')
    def textfile(root, name, body):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding='utf-8')
    # Fictional plan content intentionally uses abstract sectors, no actual routes or locations.
    plan = b'EXERCISE ONLY\nPatrol LANTERN movement brief v3\nSector AMBER; window 10:00-11:00Z; check-in word CEDAR.\nNo real coordinates or personnel.\n'
    plan_hash = hashlib.sha256(plan).hexdigest()
    textfile(initial, 'common/collection.md', f'''# Collection and scope
All data are synthetic. Exercise date: {config['exercise_date']}. Times marked Z are UTC.
Sources cover 08:00-09:30Z unless specified. Incoming shift starts 09:30Z.
WS-17 = 10.26.10.17, WS-22 = 10.26.10.22, DOCS-1 = 10.26.20.10,
IDP-1 = 10.26.20.20, collector = 10.26.20.30. Example external address
198.51.100.77 belongs to documentation space; never connect to it.
Accounts: m.ellis (planning clerk), r.chen (duty planner), svc-index (search indexing).
File identifiers: plan-v3, plan-v4, roster-v2. DOCS audit records bytes returned by
the application, not proof of subsequent viewing by a human. Proxy bytes are
application body bytes. Export rows are selected records, not exhaustive telemetry.
Proxy TLS inspection was enabled for WS-17 in this fictional lab; no TLS key is supplied.
Record IDs are stable within each source. Manifest hashes establish package integrity,
not real-world chain of custody. No disk image, memory image, native EVTX, or complete
TLS capture is represented by these simplified CSV/JSONL exports.
Network PCAP contains reconstructed UDP syslog sensor messages, not original attack
packets; packet timestamps are the corresponding proxy event times.
''')
    write_csv(initial / 'network/proxy.csv', [dict(id=f'N{i:03}',time=ts(f'08:{i:02}:00'),src='10.26.10.22' if i%2 else '10.26.10.17',dst='10.26.20.10',method='GET',path='/health',status=200,body_bytes=2,request=f'bg-{i}') for i in range(1,21)] + [
        dict(id='N101',time=ts('09:04:00'),src='10.26.10.17',dst='10.26.20.10',method='GET',path='/files/plan-v3',status=200,body_bytes=len(plan),request='req-71'),
        dict(id='N102',time=ts('09:06:00'),src='10.26.10.17',dst='198.51.100.77',method='POST',path='/upload',status=201,body_bytes=len(plan),request='req-72'),
        dict(id='N103',time=ts('09:07:00'),src='10.26.10.17',dst='198.51.100.77',method='GET',path='/ack',status=200,body_bytes=12,request='req-73'),
        dict(id='N104',time=ts('09:12:00'),src='10.26.10.22',dst='10.26.20.10',method='GET',path='/files/plan-v4',status=200,body_bytes=170,request='req-74')])
    write_csv(initial / 'network/dns.csv', [dict(id='D01',time=ts('09:05:45'),client='10.26.10.17',query='relay.archive.example',answer='198.51.100.77',ttl=60),dict(id='D02',time=ts('09:11:40'),client='10.26.10.22',query='docs.exercise.test',answer='10.26.20.10',ttl=300)])
    textfile(initial,'network/sensor-note.txt','PCAP is a valid Ethernet/IPv4/UDP capture reconstructed from proxy.csv as syslog. Use Wireshark udp.port == 514; compare event IDs and times. Same byte count alone does not establish file identity. DNS name reputation is not supplied.\n')
    # Standards-based PCAP with valid IPv4 checksum; UDP checksum zero is legal in IPv4.
    raw = bytearray(struct.pack('<IHHIIII',0xa1b2c3d4,2,4,0,0,65535,1))
    for row in csv.DictReader(io.StringIO((initial/'network/proxy.csv').read_text())):
        payload = ('<134>1 '+row['time']+' proxy sensor - '+row['id']+' - '+json.dumps(row,sort_keys=True)).encode()
        udp=struct.pack('!HHHH',5514,514,8+len(payload),0)+payload
        ip=struct.pack('!BBHHHBBH4s4s',69,0,20+len(udp),1,0,64,17,0,socket.inet_aton('10.26.20.30'),socket.inet_aton('10.26.20.31'))
        total=sum(struct.unpack('!10H',ip)); total=(total>>16)+(total&65535); total=(total>>16)+(total&65535)
        ip=ip[:10]+struct.pack('!H',(~total)&65535)+ip[12:]
        packet=bytes.fromhex('0200000000310200000000300800')+ip+udp
        epoch=int(datetime.fromisoformat(row['time'].replace('Z','+00:00')).timestamp())
        raw.extend(struct.pack('<IIII',epoch,0,len(packet),len(packet))+packet)
    (initial/'network/sensor.pcap').write_bytes(raw)
    endpoint=[]
    for i in range(1,16):
        endpoint.append(dict(id=f'E{i:03}',host='WS-17',device_time=ts(f'08:{i:02}:00'),event='ProcessStart',user='m.ellis',process='browser.exe',parent='explorer.exe',detail='normal document portal browsing'))
    endpoint += [
        dict(id='E101',host='WS-17',device_time=ts('09:00:00'),event='ProcessStart',user='m.ellis',process='brief-viewer.exe',parent='browser.exe',detail='Downloaded unsigned viewer; origin evidence missing'),
        dict(id='E102',host='WS-17',device_time=ts('09:01:00'),event='FileRead',user='m.ellis',process='brief-viewer.exe',parent='browser.exe',detail='Browser session store opened; token contents not logged'),
        dict(id='E103',host='WS-17',device_time=ts('09:06:00'),event='FileCreate',user='m.ellis',process='brief-viewer.exe',parent='browser.exe',detail=f'C:/Temp/move-cache.txt sha256={plan_hash}'),
        dict(id='E104',host='WS-17',device_time=ts('09:08:00'),event='NetworkConnect',user='m.ellis',process='brief-viewer.exe',parent='browser.exe',detail='198.51.100.77:443'),
        dict(id='E105',host='WS-17',device_time=ts('09:10:00'),event='TaskRegistered',user='m.ellis',process='brief-viewer.exe',parent='browser.exe',detail='BriefSync runs brief-viewer.exe at user logon')]
    write_csv(initial/'endpoint/events.csv',endpoint)
    textfile(initial,'endpoint/clock.txt',f'Collection {ts("09:30:00")}: WS-17 clock is consistently 120 seconds FAST during this window; subtract 120 seconds from device_time. Collector time is synchronized UTC. No reboot in window.\n')
    db=sqlite3.connect(initial/'endpoint/browser.sqlite')
    db.execute('CREATE TABLE downloads(id INTEGER PRIMARY KEY, start_time_utc TEXT, url TEXT, target_path TEXT)')
    db.execute('INSERT INTO downloads VALUES(1,?,?,?)',(ts('08:57:00'),'https://briefs.helpdesk.example/viewer','C:/Downloads/brief-viewer.exe'))
    db.commit(); db.close()
    textfile(initial,'endpoint/acquisition.txt','browser.sqlite is a purpose-built training SQLite database, not a native Chrome database. timestamps in its start_time_utc column are already normalized. No executable is provided. The downloaded program is represented only by telemetry.\n')
    identity=[dict(id=f'I{i:03}',time=ts(f'08:{i:02}:30'),user='r.chen',src='10.26.10.22',action='interactive_login',session=f'chen-{i}',result='success',mfa='fresh') for i in range(1,13)]
    identity += [
        dict(id='I101',time=ts('08:40:00'),user='m.ellis',src='10.26.10.17',action='interactive_login',session='S-41',result='success',mfa='fresh'),
        dict(id='I102',time=ts('09:03:00'),user='m.ellis',src='198.51.100.77',action='session_refresh',session='S-41',result='success',mfa='previous_claim'),
        dict(id='I103',time=ts('09:05:00'),user='m.ellis',src='198.51.100.77',action='password_login',session='none',result='failure',mfa='not_reached'),
        dict(id='I104',time=ts('09:20:00'),user='m.ellis',src='10.26.20.20',action='password_reset',session='none',result='success',mfa='admin_verified')]
    write_csv(initial/'identity/auth.csv',identity)
    textfile(initial,'identity/policy.txt','Synthetic IdP behavior: password reset does not invalidate already issued sessions. Explicit session revocation is separate. A refresh carrying previous_claim means no fresh MFA challenge. No approved VPN or egress proxy uses 198.51.100.77. Sessions ordinarily last 8 hours. IP alone does not identify a person.\n')
    server=[dict(id=f'S{i:03}',time=ts(f'08:{i:02}:15'),actor='svc-index',src='10.26.20.30',session='service',object='roster-v2',action='metadata',status=200,bytes=0,request=f'index-{i}') for i in range(1,15)]
    server += [
        dict(id='S101',time=ts('09:04:00'),actor='m.ellis',src='10.26.10.17',session='S-41',object='plan-v3',action='download',status=200,bytes=len(plan),request='req-71'),
        dict(id='S102',time=ts('09:04:30'),actor='m.ellis',src='198.51.100.77',session='S-41',object='roster-v2',action='download',status=403,bytes=0,request='req-75'),
        dict(id='S103',time=ts('09:12:00'),actor='r.chen',src='10.26.10.22',session='chen-12',object='plan-v4',action='download',status=200,bytes=170,request='req-74')]
    write_csv(initial/'server/access.csv',server)
    write_csv(initial/'server/catalog.csv',[
        dict(object='plan-v3',version=3,classification='EXERCISE',size=len(plan),sha256=plan_hash,description='LANTERN movement brief: sector, movement window, check-in word'),
        dict(object='plan-v4',version=4,classification='EXERCISE',size=170,sha256='not_collected',description='Revised movement brief; content pending exercise control'),
        dict(object='roster-v2',version=2,classification='EXERCISE',size=640,sha256='not_collected',description='Personnel roster; no content in initial evidence')])
    textfile(initial,'server/collection.txt','Audit retrieval complete for DOCS-1 08:00-09:30Z, except 09:14-09:18Z (collector restart). HTTP 403 with zero bytes is a denied request, not a successful disclosure. Audit completeness does not cover other servers.\n')
    hunt=[dict(id=f'H{i:03}',time=ts(f'08:{i:02}:45'),host='WS-22',user='r.chen',type='baseline',value='signed document viewer; approved') for i in range(1,16)] + [
        dict(id='H101',time=ts('08:58:00'),host='WS-17',user='m.ellis',type='unsigned_process',value='brief-viewer.exe'),
        dict(id='H102',time=ts('09:03:00'),host='IDP-1',user='m.ellis',type='session_anomaly',value='S-41 refresh from 198.51.100.77'),
        dict(id='H103',time=ts('09:06:00'),host='WS-17',user='m.ellis',type='rare_egress',value='198.51.100.77 POST /upload'),
        dict(id='H104',time=ts('09:08:00'),host='WS-17',user='m.ellis',type='scheduled_task',value='BriefSync'),
        dict(id='H105',time=ts('09:12:00'),host='WS-22',user='r.chen',type='file_access',value='plan-v4; approved planner')]
    textfile(initial,'hunting/siem.jsonl',''.join(json.dumps(row,sort_keys=True)+'\n' for row in hunt))
    write_csv(initial/'hunting/coverage.csv',[
        dict(host='WS-17',endpoint='08:00-09:30',network='08:00-09:30',note='endpoint device time +120 seconds; SIEM normalized'),
        dict(host='WS-22',endpoint='08:00-09:30',network='08:00-09:30',note='approved planner'),
        dict(host='WS-31',endpoint='offline since 08:50',network='not collected',note='no negative clearance possible'),
        dict(host='DOCS-1',endpoint='not collected',network='08:00-09:30',note='audit gap 09:14-09:18')])
    for number in (1,2,3):
        (output/f'inject-{number}').mkdir()
    one=output/'inject-1'
    textfile(one,'command.md',f'''# Inject 1 — exercise clock 10:05Z
Simulated command asks for a first exposure assessment within 10 exercise minutes.
LANTERN remains in the field. State what movement details may be exposed and what
you cannot yet establish. Do not wait for all cells to finish.
The controller provides a DLP reconstruction of the body sent in req-72. This is
not an adversary-system retrieval. Compare its hash with available file metadata.
''')
    (one/'dlp-body.txt').write_bytes(plan)
    textfile(one,'dlp-metadata.json',json.dumps(dict(time=ts('09:06:00'),request='req-72',source='fictional TLS-inspecting proxy DLP',sha256=plan_hash,bytes=len(plan)),indent=2))
    two=output/'inject-2'
    textfile(two,'command.md','''# Inject 2 — exercise clock 10:45Z
The password was reset at 09:20Z. Does that contain the incident? Give a revised
recommendation within 10 exercise minutes. A delayed IdP export has arrived.
Simulated planner confirms v4 superseded v3 at 09:10Z. The sector and window changed;
the check-in word remained CEDAR. Command has not reported whether exposure was acted on.
Distinguish stale movement details from information that remains sensitive.
''')
    write_csv(two/'late-auth.csv',[dict(id='I201',time=ts('09:26:00'),user='m.ellis',src='198.51.100.77',action='session_refresh',session='S-41',result='success',mfa='previous_claim')])
    textfile(two,'version-comparison.csv','field,v3,v4\nsector,AMBER,BLUE\nwindow,10:00-11:00Z,10:30-11:30Z\ncheck_in_word,CEDAR,CEDAR\n')
    three=output/'inject-3'
    textfile(three,'command.md','''# Inject 3 — exercise clock 11:25Z
Within 15 exercise minutes, state containment priorities and limits on any all-clear.
The hunt team receives delayed WS-31 inventory. Exercise control has not executed
any action unless your request has a written controller acknowledgment.
Prepare a handover identifying remaining collection and recovery requirements.
''')
    write_csv(three/'late-inventory.csv',[
        dict(id='H201',observed=ts('08:45:00'),host='WS-31',artifact='BriefSync',publisher='unknown',path='C:/Users/Public/brief-viewer.exe',scope='task inventory only; no process or network telemetry'),
        dict(id='H202',observed=ts('08:45:00'),host='WS-22',artifact='BriefSync',publisher='Exercise IT',path='C:/Program Files/Approved/briefsync.exe',scope='approved signed application; different path and binary')])
    for root in (initial,one,two,three):
        stamp(root)
    return output


if __name__ == '__main__':
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('output',type=Path)
    args=parser.parse_args()
    generate(args.output)
    print(f'Generated evidence at {args.output}')
