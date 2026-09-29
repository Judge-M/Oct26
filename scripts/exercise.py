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
from schedule import validate
import control

RUNTIME = REPO / 'runtime'


def init():
    if RUNTIME.exists():
        raise ValueError('Runtime already exists. Use export then reset for a new run.')
    config,_=validate(json.loads((REPO/'config.json').read_text()))
    RUNTIME.mkdir(mode=0o700)
    generate(RUNTIME/'vault',config)
    shutil.copytree(RUNTIME/'vault/initial',RUNTIME/'public')
    (RUNTIME/'state').mkdir()
    (RUNTIME/'control').mkdir()
    control.save(RUNTIME, [])
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
    (RUNTIME/'run-config.json').write_text(json.dumps(config,indent=2)+'\n')
    (RUNTIME/'release-log.json').write_text('[]\n')
    print('Initialized. Controller: distribute each cell only its line from runtime/cell-logins.txt.')


def release(number, operator=None):
    with control.locked(RUNTIME):
        return _release(number, operator)


def _release(number, operator):
    verify()
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
    event=control.append(RUNTIME,'release',operator,{'inject':number})
    log=json.loads((RUNTIME/'release-log.json').read_text())
    log.append({'inject':number,'released_at':event['actual_utc'],
                'event_id':event['id'],'elapsed_seconds':event['elapsed_seconds']})
    temporary=RUNTIME/'release-log.tmp'
    temporary.write_text(json.dumps(log,indent=2))
    temporary.replace(RUNTIME/'release-log.json')
    print(f'Released inject {number}; ask cells to refresh evidence.')


def verify():
    for name in ('initial','inject-1','inject-2','inject-3'):
        check(RUNTIME/'vault'/name)
    expected=json.loads((RUNTIME/'vault/initial/SHA256SUMS.json').read_text())
    if (RUNTIME/'public/SHA256SUMS.json').read_bytes() != (RUNTIME/'vault/initial/SHA256SUMS.json').read_bytes():
        raise ValueError('Initial manifest differs from canonical manifest')
    for relative,digest in expected.items():
        if hashlib.sha256((RUNTIME/'public'/relative).read_bytes()).hexdigest()!=digest:
            raise ValueError(f'Changed public artifact: {relative}')
    allowed=set(expected)|{'SHA256SUMS.json'}
    released=[]
    for number in (1,2,3):
        folder=RUNTIME/f'public/inject-{number}'
        if folder.exists():
            canonical=RUNTIME/f'vault/inject-{number}'
            originals={p.relative_to(canonical).as_posix():p.read_bytes() for p in canonical.rglob('*') if p.is_file()}
            actual_bundle={p.relative_to(folder).as_posix():p.read_bytes() for p in folder.rglob('*') if p.is_file()}
            if originals != actual_bundle:
                raise ValueError(f'Released inject {number} differs from vault')
            released.append(number)
            allowed.update(p.relative_to(RUNTIME/'public').as_posix() for p in folder.rglob('*') if p.is_file())
    actual={p.relative_to(RUNTIME/'public').as_posix() for p in (RUNTIME/'public').rglob('*') if p.is_file()}
    expected_dirs={parent.as_posix() for name in allowed for parent in Path(name).parents if parent != Path('.')}
    actual_dirs={p.relative_to(RUNTIME/'public').as_posix() for p in (RUNTIME/'public').rglob('*') if p.is_dir()}
    if actual_dirs != expected_dirs:
        raise ValueError('Unexpected or missing participant directory')
    if actual!=allowed or any(p.is_symlink() for p in (RUNTIME/'public').rglob('*')):
        raise ValueError('Unexpected or linked file in participant distribution')
    if released != list(range(1,len(released)+1)):
        raise ValueError('Released directories are not sequential')
    events=control.read(RUNTIME)
    release_events=[e for e in events if e['kind']=='release']
    logs=json.loads((RUNTIME/'release-log.json').read_text())
    canonical_log=[dict(inject=e['details']['inject'],released_at=e['actual_utc'],
                        event_id=e['id'],elapsed_seconds=e['elapsed_seconds']) for e in release_events]
    if logs != canonical_log or [e['details']['inject'] for e in release_events] != released:
        raise ValueError('Release log, controller ledger and directories disagree')
    print(f'Integrity and distribution verified: {len(actual)} public files.')


def export():
    if not RUNTIME.exists():
        raise ValueError('No runtime')
    with control.locked(RUNTIME):
        return _export()


def _export():
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
            if (RUNTIME/'control/ledger.json').exists():
                z.write(RUNTIME/'control/ledger.json','control/ledger.json')
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
    parser.add_argument('action',choices=('init','verify','release','export','reset','start','pause','resume','decision','note'))
    parser.add_argument('number',nargs='?',type=int,choices=(1,2,3))
    parser.add_argument('--stopped',action='store_true')
    parser.add_argument('--operator',help='Named controller alias, recorded with authenticated host user')
    parser.add_argument('--request',help='Legacy rehearsal ticket/comment reference, e.g. T1-C12')
    parser.add_argument('--outcome',choices=('approved','denied','pending'))
    parser.add_argument('--effective-minute',type=float)
    parser.add_argument('--text',help='Reason, tradeoff, verification or revised deadline')
    args=parser.parse_args()
    try:
        if args.action=='release':
            if args.number is None:
                parser.error('release requires 1, 2, or 3')
            release(args.number,args.operator)
        elif args.action in ('start','pause','resume','decision','note'):
            if not args.operator or not args.text:
                parser.error('Controller events require --operator and --text')
            details={'text':args.text}
            if args.action=='decision':
                if not args.request or not args.outcome:
                    parser.error('Decisions require --request and --outcome')
                duration=json.loads((RUNTIME/'run-config.json').read_text())['duration_minutes']
                if args.outcome=='approved' and args.effective_minute is None:
                    parser.error('Approved decisions require --effective-minute')
                if args.effective_minute is not None and not 0 <= args.effective_minute <= duration:
                    parser.error('Effective minute must fit the event duration')
                details.update(request=args.request,outcome=args.outcome,effective_minute=args.effective_minute)
            with control.locked(RUNTIME):
                print(json.dumps(control.append(RUNTIME,args.action,args.operator,details),indent=2))
        elif args.action=='reset': reset(args.stopped)
        else: globals()[args.action]()
    except (ValueError,FileNotFoundError) as error:
        parser.exit(1,str(error)+'\n')
