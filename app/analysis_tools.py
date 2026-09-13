"""Bounded, read-only viewers for released synthetic exercise artifacts."""
import csv
import hashlib
import io
import json
import socket
import sqlite3
import struct
from contextlib import closing
from datetime import datetime, timezone

LIMIT = 1000

def artifact(root, name):
    if not isinstance(name, str) or not name or '\\' in name or ':' in name or any(p in ('', '.', '..') for p in name.split('/')):
        raise ValueError('Choose a released evidence file')
    path = root / name
    if any(p.is_symlink() for p in [path, *path.parents]) or not path.resolve().is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError('Evidence is not released or available')
    if name.startswith(('handouts/', 'common/')) or path.name in ('command.md', 'SHA256SUMS.json'):
        raise ValueError('Choose an evidence artifact')
    if path.stat().st_size > 5_000_000:
        raise ValueError('Viewer limit is 5 MB; download the original')
    return path

def packets(data):
    if len(data)<24 or data[:4]!=b'\xd4\xc3\xb2\xa1' or struct.unpack_from('<I',data,20)[0]!=1:
        raise ValueError('Viewer supports little-endian Ethernet PCAP')
    rows=[]; offset=24
    while offset<len(data) and len(rows)<=LIMIT:
        sec,usec,size,original=struct.unpack_from('<IIII',data,offset);offset+=16
        packet=data[offset:offset+size];offset+=size
        if len(packet)!=size: raise ValueError('Truncated capture')
        row={'packet':len(rows)+1,'utc':datetime.fromtimestamp(sec+usec/1e6,timezone.utc).isoformat(),'bytes':original,'protocol':'Ethernet','source':'','destination':'','payload':''}
        if len(packet)>=34 and packet[12:14]==b'\x08\x00':
            ihl=(packet[14]&15)*4
            row.update(source=socket.inet_ntoa(packet[26:30]),destination=socket.inet_ntoa(packet[30:34]),protocol='IPv4')
            if packet[23]==17 and len(packet)>=14+ihl+8:
                a,b=struct.unpack_from('!HH',packet,14+ihl)
                row.update(protocol='UDP',source=row['source']+':'+str(a),destination=row['destination']+':'+str(b),payload=packet[14+ihl+8:].decode('utf-8',errors='replace'))
        rows.append(row)
    return rows

def query_database(path, query):
    with closing(sqlite3.connect(path.resolve().as_uri()+'?mode=ro&immutable=1',uri=True)) as con:
        con.enable_load_extension(False)
        con.setlimit(sqlite3.SQLITE_LIMIT_LENGTH,100_000)
        con.setlimit(sqlite3.SQLITE_LIMIT_SQL_LENGTH,8000)
        con.setlimit(sqlite3.SQLITE_LIMIT_COLUMN,100)
        con.execute('PRAGMA query_only=ON')
        schema=[dict(name=n,sql=s) for n,s in con.execute("SELECT name,sql FROM sqlite_master WHERE type='table'")]
        allowed={sqlite3.SQLITE_SELECT,sqlite3.SQLITE_READ,sqlite3.SQLITE_FUNCTION,sqlite3.SQLITE_RECURSIVE}
        def authorize(action,a,b,c,d):
            return sqlite3.SQLITE_OK if action in allowed and not (action==sqlite3.SQLITE_FUNCTION and str(b).lower() in ('load_extension','writefile','readfile')) else sqlite3.SQLITE_DENY
        con.set_authorizer(authorize)
        steps=0
        def budget():
            nonlocal steps
            steps+=1
            return steps>1000
        con.set_progress_handler(budget,1000)
        if not query: return [],[],schema
        if not isinstance(query,str) or len(query)>8000: raise ValueError('Query limit is 8000 characters')
        cursor=con.execute(query)
        columns=[d[0] for d in cursor.description or []]
        rows=[dict(zip(columns,[v.hex() if isinstance(v,bytes) else v for v in row])) for row in cursor.fetchmany(LIMIT+1)]
        return columns,rows,schema

def inspect(root, payload):
    name=payload.get('file');path=artifact(root,name);data=path.read_bytes()
    result={'file':name,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'rows':[],'columns':[]}
    suffix=path.suffix.lower()
    if suffix=='.sqlite':
        result['columns'],rows,result['schema']=query_database(path,payload.get('query',''))
    elif suffix=='.csv':
        reader=csv.DictReader(io.StringIO(data.decode('utf-8-sig')))
        rows=[]
        for row in reader:
            rows.append(row)
            if len(rows)>LIMIT:break
    elif suffix in ('.jsonl','.json'):
        value=[json.loads(line) for line in data.decode().splitlines() if line.strip()] if suffix=='.jsonl' else json.loads(data)
        rows=value if isinstance(value,list) else [value]
        rows=[r if isinstance(r,dict) else {'value':r} for r in rows]
    elif suffix=='.pcap':
        rows=packets(data)
        result['notice']='Reconstructed sensor capture, not original attack traffic. Packet viewer supports Ethernet / IPv4 / UDP.'
    else:
        result['text']=data.decode('utf-8',errors='replace');rows=[]
    result['truncated']=len(rows)>LIMIT;result['rows']=rows[:LIMIT]
    if not result['columns']:result['columns']=list(dict.fromkeys(k for r in result['rows'] for k in r))
    return result
