"""Controller CLI; run from the repository root. Runtime paths are fixed and ignored."""
import argparse
import hashlib
import json
import os
import secrets
import shutil
import sqlite3
import sys
import tempfile
import zipfile
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generate import CELLS, REPO, check, generate

RUNTIME = REPO / 'runtime'


def init():
    if RUNTIME.exists():
        raise ValueError('Runtime already exists. Use export then reset for a new run.')
    RUNTIME.mkdir(mode=0o700)
    generate(RUNTIME/'vault')
    shutil.copytree(RUNTIME/'vault/initial',RUNTIME/'public')
    (RUNTIME/'state').mkdir()
    # UID 10001 needs write access on Linux bind mounts. Secrets remain outside state.
    if os.name != 'nt':
        (RUNTIME/'state').chmod(0o777)
    credentials={}
    issue=[]
    for cell in CELLS:
        password=secrets.token_urlsafe(18)
        salt=secrets.token_bytes(16)
        credentials[cell]={'salt':salt.hex(),'hash':hashlib.pbkdf2_hmac('sha256',password.encode(),salt,200000).hex()}
        issue.append(f'{cell}: {password}')
    (RUNTIME/'credentials.json').write_text(json.dumps(credentials,indent=2))
    (RUNTIME/'cell-logins.txt').write_text('\n'.join(issue)+'\n')
    (RUNTIME/'cell-logins.txt').chmod(0o600)
    # Container secret must be readable by the unprivileged service user.
    (RUNTIME/'credentials.json').chmod(0o644)
    (RUNTIME/'run-config.json').write_bytes((REPO/'config.json').read_bytes())
    (RUNTIME/'release-log.json').write_text('[]\n')
    print('Initialized. Controller: distribute each cell only its line from runtime/cell-logins.txt.')


def release(number):
    source=RUNTIME/f'vault/inject-{number}'
    check(source)
    destination=RUNTIME/f'public/inject-{number}'
    if destination.exists():
        print('Already released; unchanged.')
        return
    if number>1 and not (RUNTIME/f'public/inject-{number-1}').exists():
        raise ValueError('Release injects in order')
    staging=RUNTIME/f'release-staging-{number}'
    if staging.exists():
        raise ValueError('Staging exists from interrupted release; inspect before retrying')
    shutil.copytree(source,staging)
    staging.rename(destination)
    log=json.loads((RUNTIME/'release-log.json').read_text())
    log.append({'inject':number,'released_at':datetime.now(timezone.utc).isoformat()})
    (RUNTIME/'release-log.json').write_text(json.dumps(log,indent=2))
    print(f'Released inject {number}; ask cells to refresh evidence.')


def verify():
    for name in ('initial','inject-1','inject-2','inject-3'):
        check(RUNTIME/'vault'/name)
    expected=json.loads((RUNTIME/'vault/initial/SHA256SUMS.json').read_text())
    for relative,digest in expected.items():
        if hashlib.sha256((RUNTIME/'public'/relative).read_bytes()).hexdigest()!=digest:
            raise ValueError(f'Changed public artifact: {relative}')
    allowed=set(expected)|{'SHA256SUMS.json'}
    for number in (1,2,3):
        folder=RUNTIME/f'public/inject-{number}'
        if folder.exists():
            check(folder)
            allowed.update(p.relative_to(RUNTIME/'public').as_posix() for p in folder.rglob('*') if p.is_file())
    actual={p.relative_to(RUNTIME/'public').as_posix() for p in (RUNTIME/'public').rglob('*') if p.is_file()}
    if actual!=allowed or any(p.is_symlink() for p in (RUNTIME/'public').rglob('*')):
        raise ValueError('Unexpected or linked file in participant distribution')
    print(f'Integrity and distribution verified: {len(actual)} public files.')


def export():
    if not RUNTIME.exists():
        raise ValueError('No runtime')
    target=REPO/'exports'
    target.mkdir(exist_ok=True)
    path=target/('run-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.zip')
    with tempfile.TemporaryDirectory() as tmp:
        snapshot=Path(tmp)/'tickets.sqlite'
        db=RUNTIME/'state/tickets.sqlite'
        if db.exists():
            with closing(sqlite3.connect(db)) as src,closing(sqlite3.connect(snapshot)) as dst:
                src.backup(dst)
        with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:
            if snapshot.exists():
                z.write(snapshot,'tickets.sqlite')
            for name in ('run-config.json','release-log.json'):
                z.write(RUNTIME/name,name)
            for p in (RUNTIME/'public').rglob('*'):
                if p.is_file():
                    z.write(p,'public/'+p.relative_to(RUNTIME/'public').as_posix())
    print(f'Exported {path}; contains participant work; keep private. Credentials excluded.')
    return path


def reset(confirmed):
    if not confirmed:
        raise ValueError('Stop the server/Compose first, then pass --stopped to attest it is stopped')
    export()
    # Never recursively delete runtime. Archive under this repository after checking resolved paths.
    root=REPO.resolve()
    source=RUNTIME.resolve()
    if source.parent!=root or RUNTIME.is_symlink():
        raise ValueError('Unsafe runtime location')
    archive=REPO/'exports'/('runtime-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    if not archive.resolve().is_relative_to(root/'exports'):
        raise ValueError('Unsafe archive location')
    shutil.move(str(source),str(archive))
    init()
    print('New run initialized. Prior full runtime archived privately, including old credentials.')


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=('init','verify','release','export','reset'))
    parser.add_argument('number',nargs='?',type=int,choices=(1,2,3))
    parser.add_argument('--stopped',action='store_true')
    args=parser.parse_args()
    try:
        if args.action=='release':
            if args.number is None:
                parser.error('release requires 1, 2, or 3')
            release(args.number)
        elif args.action=='reset': reset(args.stopped)
        else: globals()[args.action]()
    except (ValueError,FileNotFoundError) as error:
        parser.exit(1,str(error)+'\n')
