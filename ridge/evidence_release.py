"""Idempotent local publication and historical Wazuh indexing on ticket release."""
import base64
import csv
import hashlib
import json
import os
import re
from pathlib import Path
from urllib.request import Request, urlopen
from ridge.artifacts import safe, sha256


def index(records):
    credential=Path(os.environ['WAZUH_INDEX_CREDENTIAL_FILE']).read_text().strip()
    authorization='Basic '+base64.b64encode(credential.encode()).decode()
    base=os.environ['WAZUH_INDEXER_URL'].rstrip('/')
    index_name=os.environ['WAZUH_INDEX']
    if not re.fullmatch(r'silent-ridge-[a-z0-9-]+',index_name):
        raise ValueError('Use a dedicated silent-ridge-* historical index')
    for record in records:
        body=json.dumps(record,sort_keys=True).encode()
        identifier=hashlib.sha256(body).hexdigest()
        request=Request(base+'/'+index_name+'/_doc/'+identifier,body,
                        {'Authorization':authorization,'Content-Type':'application/json'},method='PUT')
        with urlopen(request,timeout=8) as response:
            if response.status not in (200,201):raise ValueError('Indexing failed')


def publish(ticket):
    if not re.fullmatch(r'T[0-9]{2}',ticket):raise ValueError('Invalid ticket release')
    vault=Path(os.environ['RIDGE_RELEASE_VAULT'])
    source=safe(vault,ticket)
    if not source.exists():return  # Authored tickets may use only initial evidence.
    target=Path(os.environ['RIDGE_EVIDENCE_PUBLIC'])
    records=[]
    for path in sorted(source.rglob('*')):
        if path.is_symlink():raise ValueError('Symlink in evidence release')
        if not path.is_file():continue
        name=path.relative_to(source).as_posix()
        destination=safe(target,name)
        destination.parent.mkdir(parents=True,exist_ok=True)
        if destination.exists():
            if sha256(destination)!=sha256(path):raise ValueError('Conflicting released evidence')
        else:
            temporary=destination.with_name(destination.name+'.pending')
            temporary.write_bytes(path.read_bytes());temporary.replace(destination)
        if path.suffix=='.csv':
            with path.open(newline='') as f:
                for row in csv.DictReader(f):
                    records.append(dict(timestamp=row.get('time',row.get('observed','2026-10-15T09:10:00Z')),
                        observation='synthetic historical replay',data=dict(row,source=name)))
    if records:index(records)
