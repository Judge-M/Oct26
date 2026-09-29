"""Assemble a complete offline bundle only from a validated versioned store.

Run on the Linux preparation host with all exact images already loaded. Source
matching executes only a Python hashing probe in a networkless read-only container.
"""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import zipfile
from pathlib import Path
from ridge.artifacts import safe,sha256,verify

REPO=Path(__file__).resolve().parents[1]
LAYOUTS={
    'integration':[('ridge','/opt/silent-ridge/ridge'),
                   ('bounded_http.py','/opt/silent-ridge/bounded_http.py')],
    'iris':[('ridge','/iriswebapp/ridge'),
            ('integrations/iris_silent_ridge.py','/iriswebapp/iris_silent_ridge.py'),
            ('integrations/iris_bootstrap.py','/iriswebapp/iris_bootstrap.py')],
    'ctfd':[('ridge','/opt/CTFd/ridge'),
            ('integrations/ctfd_silent_ridge','/opt/CTFd/CTFd/plugins/ctfd_silent_ridge')],
    'desktop':[('deployment/expanded/desktop/seed-case.py','/opt/silent-ridge/seed-case.py'),
               ('deployment/expanded/desktop/helpers','/opt/silent-ridge/helpers'),
               ('deployment/expanded/desktop/configure-desktop.sh','/opt/silent-ridge/configure-desktop.sh'),
               ('deployment/expanded/desktop/entrypoint.sh','/usr/local/bin/silent-ridge-entrypoint')]}
REQUIRED_IMAGES=set(LAYOUTS)|{'iris_db','rabbitmq','ctfd_db','ctfd_cache','wazuh_manager',
    'wazuh_indexer','wazuh_dashboard','guacamole','guacd','guacamole_db'}
PROBE_PYTHON={'desktop':'python3'}
LFS_POINTER = re.compile(rb'\Aversion https://git-lfs.github.com/spec/v1\r?\n'
                         rb'oid sha256:([0-9a-f]{64})\r?\nsize ([0-9]+)\r?\n?\Z')


def command(*args):
    return subprocess.check_output(args,cwd=REPO,text=True).strip()


def split_file(path, max_bytes):
    """Split ``path`` into ``<name>.part-NNN`` pieces of at most ``max_bytes``.

    Returns the ordered part paths and removes the original. The naming
    contract matches ``ridge.offline_install.image_parts`` exactly, so an
    installer reassembles precisely what was split here.
    """
    if max_bytes <= 0:
        raise ValueError('max_bytes must be positive')
    path = Path(path)
    if path.stat().st_size <= max_bytes:
        return [path]
    parts = []
    index = 0
    with path.open('rb') as source:
        while True:
            index += 1
            piece = source.read(max_bytes)
            if not piece:
                break
            part = path.with_name('%s.part-%03d' % (path.name, index))
            part.write_bytes(piece)
            parts.append(part)
    path.unlink()
    return parts


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
                              '--entrypoint',PROBE_PYTHON.get(kind,'python'),image,
                              '-c',script,json.dumps(paths)))
    if actual!=expected:raise ValueError('Source/image mismatch: '+kind)
    return expected


def save_refs(manifest, inspect=None):
    """Tags to pass to ``docker image save`` — never bare image IDs.

    Saving by ID produces an archive with no RepoTags; ``docker load`` then
    restores untagged <none> images and every compose file (pull_policy:
    never) fails on a cold host. Tags come from the manifest's image_tags
    (assembly time), falling back to the daemon's RepoTags for older
    manifests. Each tag must resolve to the manifest's image ID."""
    inspect = inspect or (lambda ref: subprocess.check_output(
        ['docker', 'image', 'inspect', '--format', '{{.Id}}', ref], text=True).strip())
    refs = []
    tags = manifest.get('image_tags') or {}
    for kind, image in sorted(manifest['images'].items()):
        tag = tags.get(kind)
        if tag is None:
            raise ValueError('manifest has no image_tags.%s; re-assemble the store with a '
                             'current scripts/assemble_offline_store.py so the bundle keeps '
                             'image tags' % kind)
        actual = inspect(tag)
        if actual != image:
            raise ValueError('tag %s resolves to %s, expected %s' % (tag, actual, image))
        refs.append(tag)
    return refs


def materialize_lfs_source(source_archive, root=REPO, exclude_prefixes=()):
    """Replace archived Git LFS pointers with their verified working-tree bytes.

    ``git archive`` exports pointer blobs even when LFS is checked out. The
    installed source must contain the actual files, and a missing or wrong LFS
    object must fail packaging before the Docker image archive is saved.
    """
    source_archive, root = Path(source_archive), Path(root)
    replacement = source_archive.with_name(source_archive.name + '.materializing')
    replaced = []
    try:
        with zipfile.ZipFile(source_archive) as original, zipfile.ZipFile(
                replacement, 'w', allowZip64=True) as output:
            for entry in original.infolist():
                if any(entry.filename.startswith(prefix) for prefix in exclude_prefixes):
                    continue
                source = None
                if not entry.is_dir() and entry.file_size <= 1024:
                    with original.open(entry) as stream:
                        pointer = LFS_POINTER.fullmatch(stream.read())
                    if pointer:
                        source = safe(root, entry.filename)
                        expected_size = int(pointer.group(2))
                        if (not source.is_file() or source.stat().st_size != expected_size
                                or sha256(source) != pointer.group(1).decode()):
                            raise ValueError('Materialize and verify Git LFS content before '
                                             'packaging: ' + entry.filename)
                        replaced.append(entry.filename)
                if entry.is_dir():
                    output.writestr(entry, b'')
                    continue
                with (source.open('rb') if source else original.open(entry)) as data, \
                        output.open(entry, 'w', force_zip64=True) as target:
                    shutil.copyfileobj(data, target, length=1024 * 1024)
        replacement.replace(source_archive)
    finally:
        replacement.unlink(missing_ok=True)
    return replaced


def pack(store,manifest,destination,allow_incomplete=False,max_part_bytes=None):
    store=Path(store);destination=Path(destination)
    if destination.exists():raise ValueError('Use a new bundle destination')
    if command('git','status','--porcelain'):
        raise ValueError('Commit source changes and remove untracked release inputs before packaging')
    if manifest['source_commit']!=command('git','rev-parse','HEAD'):
        raise ValueError('Manifest is for a different source commit')
    if allow_incomplete and manifest.get('compatibility_verified'):
        raise ValueError('--allow-incomplete is only for uncertified drill bundles')
    if not allow_incomplete and not manifest.get('compatibility_verified'):
        raise ValueError('Uncertified manifest; pass --allow-incomplete to build a drill bundle')
    verify(store,manifest,complete=not allow_incomplete,require_containers=False)
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
    # The parked VM is released separately when requested by the assembler;
    # its six Git LFS parts are never useful as source-tree pointer stubs.
    materialize_lfs_source(destination/'source.zip',
                           exclude_prefixes=('assets/vm-desktop/',))
    for artifact in manifest['artifacts']:
        if artifact['kind']=='containers':continue  # Re-save the exact checked identities.
        source=safe(store,artifact['path']);target=safe(destination,artifact['path'])
        if target.exists():raise ValueError('Artifact collides with bundle metadata')
        target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
    subprocess.run(['docker','image','save','--output',str(destination/'validated-images.tar'),
                    *save_refs(manifest)],check=True)
    from ridge.deploy.__main__ import fingerprint
    manifest=dict(manifest,
                  source_fingerprint=fingerprint(),
                  artifacts=[a for a in manifest['artifacts'] if a['kind']!='containers'])
    if allow_incomplete:
        manifest['certification']='drill-uncertified'
    image_archive=destination/'validated-images.tar'
    saved=[image_archive]
    if max_part_bytes:
        saved=split_file(image_archive,max_part_bytes)
    for archive_path in saved:
        manifest['artifacts'].append(dict(path=archive_path.name,kind='containers',version=manifest['source_commit'],
            release=manifest['release'],bytes=archive_path.stat().st_size,sha256=sha256(archive_path)))
    verify(destination,manifest,complete=not allow_incomplete)
    (destination/'release-manifest.json').write_text(json.dumps(manifest,indent=2))
    (destination/'source-image-checks.json').write_text(json.dumps(sources,indent=2))
    checks={p.relative_to(destination).as_posix():sha256(p) for p in destination.rglob('*') if p.is_file()}
    (destination/'SHA256SUMS.json').write_text(json.dumps(checks,indent=2))
    return destination


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('store',type=Path);p.add_argument('manifest',type=Path);p.add_argument('destination',type=Path)
    p.add_argument('--allow-incomplete',action='store_true',
                   help='build an uncertified drill bundle (manifest must have compatibility_verified false)')
    p.add_argument('--max-part-bytes',type=int,default=None,
                   help='split validated-images.tar into bounded .part-NNN pieces')
    a=p.parse_args();print(pack(a.store,json.loads(a.manifest.read_text(encoding='utf-8')),a.destination,
                                allow_incomplete=a.allow_incomplete,max_part_bytes=a.max_part_bytes))
