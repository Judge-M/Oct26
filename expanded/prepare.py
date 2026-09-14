"""Build reproducible, explicitly synthetic evidence on a preparation host.

This produces a real FAT16 image and PCAP, plus prepared JSON fixtures. It does
NOT claim JSON fixtures are native Windows EVTX or a Windows memory acquisition.
Native logs, memory captures, and validated Autopsy cases remain release gates.
"""
import argparse
import csv
import hashlib
import importlib.util
import json
import random
import shutil
import socket
import sqlite3
import struct
import sys
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path

REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO/'scripts'))
import generate


def write(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes(data if isinstance(data,(bytes,bytearray)) else data.encode())


def read_csv(path):
    with path.open(newline='',encoding='utf-8-sig') as source:
        return list(csv.DictReader(source))


def fat16(path,files):
    """8 MiB FAT16 superfloppy. Deleted entry retains recoverable allocated bytes."""
    sectors=16384;fat_sectors=64;root_sectors=32;data_sector=1+2*fat_sectors+root_sectors
    image=bytearray(sectors*512)
    image[:3]=b'\xeb\x3c\x90';image[3:11]=b'SRIDGE  '
    struct.pack_into('<HBHBHHBHHHII',image,11,512,1,1,2,512,sectors,0xf8,fat_sectors,32,64,0,0)
    image[36]=0x80;image[38]=0x29
    struct.pack_into('<I',image,39,0x53495231)
    image[43:54]=b'SILENTRIDGE';image[54:62]=b'FAT16   ';image[510:512]=b'\x55\xaa'
    fat=bytearray(fat_sectors*512);struct.pack_into('<HH',fat,0,0xfff8,0xffff)
    cluster=2
    for i,(name,content,deleted) in enumerate(files):
        if len(name)!=11:
            raise ValueError('FAT short names must be 11 bytes')
        entry=(1+2*fat_sectors)*512+i*32
        image[entry:entry+11]=name.encode('ascii')
        if deleted:image[entry]=0xe5
        image[entry+11]=0x20
        struct.pack_into('<HHHI',image,entry+22,0x4820,((2026-1980)<<9)|(10<<5)|15,cluster,len(content))
        count=max(1,(len(content)+511)//512)
        for offset in range(count):
            current=cluster+offset
            if not deleted:struct.pack_into('<H',fat,current*2,0xffff if offset==count-1 else current+1)
            start=(data_sector+current-2)*512
            block=content[offset*512:(offset+1)*512];image[start:start+len(block)]=block
        cluster+=count
    image[512:512+len(fat)]=fat
    image[(1+fat_sectors)*512:(1+2*fat_sectors)*512]=fat
    write(path,image)


def dns_capture(path):
    raw=bytearray(struct.pack('<IHHIIII',0xa1b2c3d4,2,4,0,0,65535,1))
    for name,client,address,time in [('relay.archive.example','10.26.10.17','198.51.100.77','09:05:45'),
                                     ('docs.exercise.test','10.26.10.22','10.26.20.10','09:11:40')]:
        labels=b''.join(bytes([len(p)])+p.encode() for p in name.split('.'))+b'\0'
        question=labels+struct.pack('!HH',1,1)
        for response in (False,True):
            payload=struct.pack('!HHHHHH',110,0x8180 if response else 0x0100,1,int(response),0,0)+question
            if response:payload+=b'\xc0\x0c'+struct.pack('!HHIH',1,1,60,4)+socket.inet_aton(address)
            udp=struct.pack('!HHHH',53 if response else 54000,54000 if response else 53,8+len(payload),0)+payload
            source,dest=('10.26.20.53',client) if response else (client,'10.26.20.53')
            ip=struct.pack('!BBHHHBBH4s4s',69,0,20+len(udp),110,0,64,17,0,socket.inet_aton(source),socket.inet_aton(dest))
            total=sum(struct.unpack('!10H',ip));total=(total>>16)+(total&65535);total=(total>>16)+(total&65535)
            ip=ip[:10]+struct.pack('!H',(~total)&65535)+ip[12:]
            packet=bytes.fromhex('0200000000530200000000170800')+ip+udp
            stamp=int(datetime.fromisoformat('2026-10-15T'+time+'+00:00').timestamp())
            raw+=struct.pack('<IIII',stamp,1000 if response else 0,len(packet),len(packet))+packet
    write(path,raw)


def syslog_capture(path,rows):
    raw=bytearray(struct.pack('<IHHIIII',0xa1b2c3d4,2,4,0,0,65535,1))
    for row in rows:
        payload=('<134>1 '+row['time']+' proxy sensor - '+row['id']+' - '+json.dumps(row,sort_keys=True)).encode()
        udp=struct.pack('!HHHH',5514,514,8+len(payload),0)+payload
        ip=struct.pack('!BBHHHBBH4s4s',69,0,20+len(udp),1,0,64,17,0,socket.inet_aton('10.26.20.30'),socket.inet_aton('10.26.20.31'))
        total=sum(struct.unpack('!10H',ip));total=(total>>16)+(total&65535);total=(total>>16)+(total&65535)
        ip=ip[:10]+struct.pack('!H',(~total)&65535)+ip[12:]
        packet=bytes.fromhex('0200000000310200000000300800')+ip+udp
        epoch=int(datetime.fromisoformat(row['time'].replace('Z','+00:00')).timestamp())
        raw+=struct.pack('<IIII',epoch,0,len(packet),len(packet))+packet
    write(path,raw)


def build(output):
    output=Path(output)
    if output.exists():raise ValueError('Use a new artifact release directory')
    public=output/'initial';vault=output/'controller'
    public.mkdir(parents=True);vault.mkdir()
    with tempfile.TemporaryDirectory() as tmp:
        old=generate.generate(Path(tmp)/'baseline')
        # Preserve incident facts, not the obsolete handouts, prompts or specialist IDs.
        for folder in ('network','endpoint','identity','server','hunting'):
            shutil.copytree(old/'initial'/folder,public/folder)
        for name in ('acquisition.txt','clock.txt'):
            (public/'endpoint'/name).unlink(missing_ok=True)
        for path in public.rglob('*.csv'):
            with path.open(newline='') as f:rows=list(csv.DictReader(f))
            if rows and 'id' in rows[0]:
                for row in rows:row['id']=hashlib.sha256(json.dumps({k:v for k,v in row.items() if k!='id'},sort_keys=True).encode()).hexdigest()[:12]
                generate.write_csv(path,rows)
        write(public/'network/sensor-note.txt','Synthetic reconstruction: outer packets carry collector syslog. Use embedded fields for incident endpoints. All times are UTC.\n')
        write(public/'server/collection.txt','DOCS-1 audit: 08:00–09:30 UTC; collection unavailable 09:14–09:18 UTC. Other servers were not collected.\n')
        coverage=read_csv(public/'hunting/coverage.csv')
        for r in coverage:r['note']='WS-17 device clock +120 seconds; SIEM normalized' if r['host']=='WS-17' else 'See recorded collection intervals'
        generate.write_csv(public/'hunting/coverage.csv',coverage)
        # Follow-up evidence remains outside the initial read-only share.
        release_files={'T19':{'network/dlp-body.txt':old/'inject-1/dlp-body.txt','network/dlp-metadata.json':old/'inject-1/dlp-metadata.json'},
                       'T07':{'identity/late-auth.csv':old/'inject-2/late-auth.csv'},
                       'T09':{'server/version-comparison.csv':old/'inject-2/version-comparison.csv'},
                       'T11':{'hunting/late-inventory.csv':old/'inject-3/late-inventory.csv'}}
        for ticket,files in release_files.items():
            for name,source in files.items():write(vault/'releases'/ticket/name,source.read_bytes())
        inventory=read_csv(old/'inject-3/late-inventory.csv')
        generate.write_csv(public/'hunting/approved-inventory.csv',[r for r in inventory if r['host']=='WS-22'])
        generate.write_csv(vault/'releases/T11/hunting/late-inventory.csv',[r for r in inventory if r['host']=='WS-31'])
        comparison=vault/'releases/T09/server/version-comparison.csv'
        write(comparison,comparison.read_text()+'superseded_utc,not_applicable,09:10:00\n')
        plan=(old/'inject-1/dlp-body.txt').read_bytes()
        fat16(public/'disk/WS17-fat16.img',[
            ('README  TXT',b'Fictional prepared disk fixture. Native FAT16; no acquired Windows installation.\n',False),
            ('MOVECACHTXT',plan,True),('PLANV3  TXT',plan,False),
            ('HISTORY TXT',b'08:57:00Z https://briefs.helpdesk.example/viewer -> C:/Downloads/brief-viewer.exe\n',False)])
        rows=[{'id':1,'start_time_utc':'2026-10-15T08:57:00Z','url':'https://briefs.helpdesk.example/viewer','target_path':'C:/Downloads/brief-viewer.exe'}]
        generate.write_csv(public/'browser/downloads.csv',rows)
    dns_capture(public/'network/dns.pcap')
    syslog_capture(public/'network/sensor.pcap',read_csv(public/'network/proxy.csv'))
    hunt=[json.loads(line) for line in (public/'hunting/siem.jsonl').read_text().splitlines()]
    for row in hunt:row['id']=hashlib.sha256(json.dumps({k:v for k,v in row.items() if k!='id'},sort_keys=True).encode()).hexdigest()[:12]
    write(public/'hunting/siem.jsonl',''.join(json.dumps(r)+'\n' for r in hunt))
    fixtures={
      'windows-process':{'host':'WS-17','device_time':'2026-10-15T09:00:00Z','utc':'2026-10-15T08:58:00Z','pid':4240,'parent':'browser.exe'},
      'windows-task':{'host':'WS-17','device_time':'2026-10-15T09:10:00Z','utc':'2026-10-15T09:08:00Z','task':'BriefSync','executable':'brief-viewer.exe'},
      'memory-processes':{'pid':4240,'ppid':3100,'parent':'browser.exe','process':'brief-viewer.exe','command_line':'brief-viewer.exe --cache C:/Temp/move-cache.txt'},
      'memory-connections':{'pid':4240,'remote':'198.51.100.77','port':443,'state':'ESTABLISHED'}}
    for name,record in fixtures.items():
        write(vault/'preparation-fixtures'/f'{name}.json',json.dumps(dict(record,provenance='Synthetic preparation fixture, not native EVTX or a memory acquisition'),indent=2))
    telemetry=[dict(timestamp=r['time'],data=dict(r,source='hunting/siem.jsonl')) for r in hunt]
    for path in public.rglob('*.csv'):
        for row in read_csv(path):
            stamp=row.get('time',row.get('observed',row.get('device_time','2026-10-15T08:00:00Z')))
            if 'device_time' in row:
                stamp=(datetime.fromisoformat(stamp.replace('Z','+00:00'))-timedelta(seconds=120)).isoformat().replace('+00:00','Z')
            telemetry.append(dict(timestamp=stamp,data=dict(row,source=path.relative_to(public).as_posix(),type='coverage' if path.name=='coverage.csv' else 'historical')))
    # Interleave ordinary records in the same time window and identifier scheme.
    rng=random.Random(20261015)
    for i in range(400):
        minute=rng.randrange(90);host=rng.choice(['WS-17','WS-22','DOCS-1','IDP-1'])
        telemetry.append(dict(timestamp=f'2026-10-15T{8+minute//60:02}:{minute%60:02}:{rng.randrange(60):02}Z',
            data=dict(host=host,action=rng.choice(['health_check','document_index','service_status']),result='success',source='background-sensor',type='historical')))
    for record in telemetry:
        record['record_id']=hashlib.sha256(json.dumps(record,sort_keys=True).encode()).hexdigest()[:12]
        record['observation']='synthetic historical replay'
    telemetry.sort(key=lambda r:r['timestamp'])
    write(public/'wazuh/telemetry.jsonl',''.join(json.dumps(r,sort_keys=True)+'\n' for r in telemetry))
    write(public/'README.txt','All evidence is fictional training material. Replayed evidence is not a live observation. Original sources, hashes and preparation versions are recorded in provenance.json. Do not modify shared evidence.\n')
    write(public/'guides/getting-started.md',(REPO/'expanded/guides.md').read_bytes())
    sources={p.relative_to(output).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in output.rglob('*') if p.is_file()}
    write(output/'provenance.json',json.dumps(dict(generator='expanded/prepare.py',schema=1,sources=sources,
        status='Preparation fixtures only; Autopsy cases, native EVTX and native memory capture outstanding',
        command='python expanded/prepare.py <new-release-directory>',python=sys.version,sqlite=sqlite3.sqlite_version),indent=2))
    generate.stamp(output)
    return output


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output',type=Path);a=p.parse_args();print(build(a.output))
