"""Verified publication before task creation; retryable, bounded bulk indexing."""
import base64
import csv
import hashlib
import json
import os
import re
import shutil
import tempfile
from itertools import islice
from pathlib import Path
from urllib.request import Request, urlopen
from ridge.artifacts import safe, sha256
from ridge.scenario import telemetry_record


def index(records):
    credential=Path(os.environ['WAZUH_INDEX_CREDENTIAL_FILE']).read_text(encoding='utf-8').strip()
    authorization='Basic '+base64.b64encode(credential.encode()).decode()
    base=os.environ['WAZUH_INDEXER_URL'].rstrip('/')
    index_name=os.environ['WAZUH_INDEX']
    if not re.fullmatch(r'silent-ridge-[a-z0-9-]+',index_name):
        raise ValueError('Use a dedicated silent-ridge-* historical index')
    records=iter(records)
    while batch := list(islice(records,100)):
        lines=[]
        for record in batch:
            body=json.dumps(record,sort_keys=True)
            identifier=hashlib.sha256(body.encode()).hexdigest()
            lines.extend((json.dumps({'index':{'_id':identifier}}),body))
        request=Request(base+'/'+index_name+'/_bulk', ('\n'.join(lines)+'\n').encode(),
                        {'Authorization':authorization,'Content-Type':'application/x-ndjson'},method='POST')
        with urlopen(request,timeout=8) as response:
            result=json.load(response)
            if result.get('errors') is not False or len(result.get('items',[])) != len(batch):
                raise ValueError('Bulk indexing incomplete; retry stable document IDs')
            if any(item.get('index',{}).get('status') not in (200,201) for item in result['items']):
                raise ValueError('Bulk indexing failed')


def validate_release(ticket, required):
    if not re.fullmatch(r'T[0-9]{2}',ticket):
        raise ValueError('Invalid ticket release')
    if not isinstance(required,list) or len(set(required)) != len(required):
        raise ValueError('Explicit unique release files required')
    vault=Path(os.environ['RIDGE_RELEASE_VAULT'])
    manifest=json.loads(safe(vault,'manifest.json').read_text(encoding='utf-8'))
    if manifest.get('schema') != 1:
        raise ValueError('Unknown release manifest schema')
    entries=manifest['tickets'].get(ticket,{})
    if set(entries) != set(required):
        raise ValueError('Required evidence differs from release manifest: '+ticket)
    source=safe(vault,ticket)
    actual={p.relative_to(source).as_posix() for p in source.rglob('*') if p.is_file()}
    if actual != set(required):
        raise ValueError('Missing or unexpected evidence: '+ticket)
    for name,digest in entries.items():
        path=safe(source,name)
        if sha256(path) != digest:
            raise ValueError('Corrupt evidence: '+ticket+'/'+name)
    return source,entries


def publish(ticket,required):
    source,entries=validate_release(ticket,required)
    if not entries:
        return
    target=Path(os.environ['RIDGE_EVIDENCE_PUBLIC'])
    if not target.is_dir():
        raise ValueError('Published evidence directory is not mounted')
    for name,digest in entries.items():
        destination=safe(target,name)
        if destination.exists() and sha256(destination) != digest:
            raise ValueError('Conflicting released evidence')
    from ridge.storage import require_space
    require_space(target, sum(safe(source,name).stat().st_size for name in entries))
    # Use the target filesystem for atomic renames; staging names contain verified
    # evidence only, and the controller removes abandoned staging while stopped.
    with tempfile.TemporaryDirectory(prefix='.ridge-release-',dir=target) as temporary:
        staging=Path(temporary)
        records=[]
        for name,digest in entries.items():
            staged=safe(staging,name)
            staged.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(safe(source,name),staged)
            if sha256(staged) != digest:
                raise ValueError('Evidence changed during publication')
            if staged.suffix == '.csv':
                with staged.open(newline='',encoding='utf-8') as f:
                    records.extend(telemetry_record(row,name) for row in csv.DictReader(f))
        if records:
            index(records)
        for name in entries:
            destination=safe(target,name)
            destination.parent.mkdir(parents=True,exist_ok=True)
            if not destination.exists():
                safe(staging,name).replace(destination)
    # Cross-file/index atomicity is impossible here. The task is acknowledged only
    # after every component succeeds; partial crash publication safely retries.
