"""Fail-closed, streamed integrity checks for a provider-independent offline store.

The trusted manifest is transferred separately. Hashes detect alteration, not an
untrusted manifest author. No provider, host capacity or application compatibility
is inferred from a successful checksum verification.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath

REQUIRED={'containers','desktop','disk','memory','autopsy','dependencies','guides','evidence'}


def sha256(path):
    digest=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):
            digest.update(block)
    return digest.hexdigest()


def safe(root,name):
    relative=PurePosixPath(name)
    if not name or relative.is_absolute() or any(p in ('..','.') for p in relative.parts) or '\\' in name or ':' in name:
        raise ValueError('Unsafe artifact path')
    path=root.joinpath(*relative.parts)
    if any(p.is_symlink() for p in [path,*path.parents]) or not path.resolve().is_relative_to(root.resolve()):
        raise ValueError('Symlink or escaped artifact')
    return path


def verify(root,manifest,complete=True):
    root=Path(root).resolve()
    if manifest.get('schema')!=1 or not manifest.get('release') or not manifest.get('source_commit'):
        raise ValueError('Versioned manifest with source commit required')
    names=set();kinds=set()
    for artifact in manifest['artifacts']:
        name=artifact['path']
        if name in names:
            raise ValueError('Duplicate artifact path')
        names.add(name);kinds.add(artifact['kind'])
        path=safe(root,name)
        if not path.is_file() or path.stat().st_size!=artifact['bytes'] or sha256(path)!=artifact['sha256']:
            raise ValueError('Missing or corrupt artifact: '+name)
        if artifact.get('release')!=manifest['release'] or not artifact.get('version'):
            raise ValueError('Artifact release/version mismatch: '+name)
    if complete and (not REQUIRED<=kinds or not manifest.get('compatibility_verified')):
        raise ValueError('Incomplete offline bundle or compatibility not verified')
    return len(names)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('store',type=Path);p.add_argument('manifest',type=Path)
    p.add_argument('--allow-incomplete',action='store_true',help='Integrity inspection only; cannot certify deployment')
    a=p.parse_args();print(verify(a.store,json.loads(a.manifest.read_text(encoding='utf-8')),not a.allow_incomplete))
