"""Package validated images and tracked controller sources for an offline host."""
import argparse
import hashlib
import json
import platform
import subprocess
import zipfile
from pathlib import Path

REPO=Path(__file__).resolve().parents[1]


def run(*args):
    return subprocess.check_output(args,cwd=REPO,text=True).strip()


def files(root):
    if root.is_symlink() or any(p.is_symlink() for p in root.rglob('*')):
        raise ValueError('Offline package cannot contain symlinks')
    return {p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob('*')) if p.is_file() and p != root/'SHA256SUMS.json'}


def verify(root):
    root=Path(root)
    if files(root) != json.loads((root/'SHA256SUMS.json').read_text()):
        raise ValueError('Offline package checksum mismatch')
    print('Offline package verified (compare SHA256SUMS.json itself with your trusted transfer record).')


def pack(root):
    root=Path(root).resolve()
    if root.exists(): raise ValueError('Use a new offline package directory')
    if run('git','status','--porcelain','--untracked-files=no'):
        raise ValueError('Commit tracked source/config changes before offline packaging')
    root.mkdir(parents=True)
    run('git','archive','--format=zip','--output',str(root/'source.zip'),'HEAD')
    with zipfile.ZipFile(root/'source.zip') as archive:
        for name in archive.namelist():
            if not (root/'source'/name).resolve().is_relative_to(root/'source'):
                raise ValueError('Unsafe source archive path')
        archive.extractall(root/'source')
    info={'git_commit':run('git','rev-parse','HEAD'), 'host_python':platform.python_version(),
          'engine':run('docker','version','--format','{{.Server.Version}}'),
          'compose':run('docker','compose','version','--short'),'images':{}}
    tags=[]
    for service in ('exercise','gateway'):
        container=run('docker','compose','ps','-q',service)
        if not container: raise ValueError(f'{service} must be running and validated before packaging')
        inspection=json.loads(run('docker','inspect',container))[0]
        identity=inspection['Image']
        image=json.loads(run('docker','image','inspect',identity))[0]
        tag=f'silent-ridge-offline-{service}:{identity.split(":")[1][:16]}'
        run('docker','tag',identity,tag)
        info['images'][service]={'id':identity,'tag':tag,'repo_digests':image.get('RepoDigests',[]),
                                  'os':image['Os'],'architecture':image['Architecture']}
        tags.append(tag)
    subprocess.run(['docker','image','save','--output',str(root/'images.tar'),*tags],check=True)
    (root/'image-identities.json').write_text(json.dumps(info,indent=2)+'\n')
    print(json.dumps(info,indent=2))
    override={'services':{service:{'image':record['tag'],'pull_policy':'never'} for service,record in info['images'].items()}}
    (root/'source/compose.offline.json').write_text(json.dumps(override,indent=2)+'\n')
    (root/'SHA256SUMS.json').write_text(json.dumps(files(root),indent=2)+'\n')
    verify(root)
    print('Trusted manifest SHA256:',hashlib.sha256((root/'SHA256SUMS.json').read_bytes()).hexdigest())


def load(root):
    root=Path(root).resolve(); verify(root)
    subprocess.run(['docker','image','load','--input',str(root/'images.tar')],check=True)
    info=json.loads((root/'image-identities.json').read_text())
    for record in info['images'].values():
        image=json.loads(run('docker','image','inspect',record['tag']))[0]
        if image['Id'] != record['id'] or image['Architecture'] != record['architecture'] or image['Os'] != record['os']:
            raise ValueError('Loaded image identity/platform differs')
    print('Both exact image identities restored. Initialize the packaged source with host Python; do not rebuild.')


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=('pack','verify','load'))
    parser.add_argument('directory',type=Path)
    args=parser.parse_args()
    try: globals()[args.action](args.directory)
    except (ValueError,FileNotFoundError) as error: parser.exit(1,str(error)+'\n')
