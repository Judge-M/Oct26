"""Assemble a complete offline bundle only from a validated versioned store.

Run on the Linux preparation host with all exact images already loaded. Source
matching executes only a Python hashing probe in a networkless read-only container.
"""
import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from ridge.artifacts import safe,sha256,verify

REPO=Path(__file__).resolve().parents[1]
LAYOUTS={
    'integration':[('ridge','/opt/silent-ridge/ridge')],
    'iris':[('ridge','/iriswebapp/ridge'),('integrations/iris_silent_ridge.py','/iriswebapp/iris_silent_ridge.py')],
    'ctfd':[('ridge','/opt/CTFd/ridge'),('integrations/ctfd_silent_ridge','/opt/CTFd/CTFd/plugins/ctfd_silent_ridge')]}
REQUIRED_IMAGES=set(LAYOUTS)|{'iris_db','rabbitmq','ctfd_db','ctfd_cache','wazuh_manager',
    'wazuh_indexer','wazuh_dashboard','guacamole','guacd','guacamole_db'}


def command(*args):
    return subprocess.check_output(args,cwd=REPO,text=True).strip()


def image_sources(kind,image):
    expected={}
    paths=[]
    for local,remote in LAYOUTS[kind]:
        root=REPO/local;paths.append(remote)
        for path in ([root] if root.is_file() else root.rglob('*')):
            if path.is_file() and '__pycache__' not in path.parts and path.suffix!='.pyc':
                key=remote if root.is_file() else remote+'/'+path.relative_to(root).as_posix()
                expected[key]=sha256(path)
    script='''import hashlib,json,pathlib,sys
out={}
for name in json.loads(sys.argv[1]):
 r=pathlib.Path(name)
 for p in ([r] if r.is_file() else r.rglob('*')):
  if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc':
   out[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
print(json.dumps(out))
'''
    actual=json.loads(command('docker','run','--rm','--network','none','--read-only',
                              '--entrypoint','python',image,'-c',script,json.dumps(paths)))
    if actual!=expected:raise ValueError('Source/image mismatch: '+kind)
    return expected


def pack(store,manifest,destination):
    store=Path(store);destination=Path(destination)
    if destination.exists():raise ValueError('Use a new bundle destination')
    if command('git','status','--porcelain'):
        raise ValueError('Commit source changes and remove untracked release inputs before packaging')
    if manifest['source_commit']!=command('git','rev-parse','HEAD'):
        raise ValueError('Manifest is for a different source commit')
    verify(store,manifest,complete=True)
    if not REQUIRED_IMAGES<=set(manifest.get('images',{})):
        raise ValueError('Record every central application and dependency image identity')
    reserved={'source.zip','release-manifest.json','source-image-checks.json','SHA256SUMS.json','validated-images.tar'}
    if any(a['path'] in reserved for a in manifest['artifacts']):
        raise ValueError('Artifact collides with bundle metadata')
    for image in manifest['images'].values():
        if not image.startswith('sha256:'):raise ValueError('Immutable image ID required')
    sources={}
    for kind in LAYOUTS:
        image=manifest['images'][kind]
        if not image.startswith('sha256:'):raise ValueError('Immutable image ID required')
        sources[kind]=image_sources(kind,image)
    destination.mkdir(parents=True)
    command('git','archive','--format=zip','--output',str((destination/'source.zip').resolve()),'HEAD')
    for artifact in manifest['artifacts']:
        if artifact['kind']=='containers':continue  # Re-save the exact checked identities.
        source=safe(store,artifact['path']);target=safe(destination,artifact['path'])
        if target.exists():raise ValueError('Artifact collides with bundle metadata')
        target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
    subprocess.run(['docker','image','save','--output',str(destination/'validated-images.tar'),
                    *sorted(set(manifest['images'].values()))],check=True)
    manifest=dict(manifest,artifacts=[a for a in manifest['artifacts'] if a['kind']!='containers'])
    image_archive=destination/'validated-images.tar'
    manifest['artifacts'].append(dict(path='validated-images.tar',kind='containers',version=manifest['source_commit'],
        release=manifest['release'],bytes=image_archive.stat().st_size,sha256=sha256(image_archive)))
    verify(destination,manifest,complete=True)
    (destination/'release-manifest.json').write_text(json.dumps(manifest,indent=2))
    (destination/'source-image-checks.json').write_text(json.dumps(sources,indent=2))
    checks={p.relative_to(destination).as_posix():sha256(p) for p in destination.rglob('*') if p.is_file()}
    (destination/'SHA256SUMS.json').write_text(json.dumps(checks,indent=2))
    return destination


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('store',type=Path);p.add_argument('manifest',type=Path);p.add_argument('destination',type=Path)
    a=p.parse_args();print(pack(a.store,json.loads(a.manifest.read_text(encoding='utf-8')),a.destination))
