"""Capacity checks and explicit pruning of verified, independently backed-up exports."""
import argparse
import json
import os
import shutil
import time
from pathlib import Path
from ridge.artifacts import safe, sha256


def require_space(path, incoming=0):
    path=Path(path).resolve()
    while not path.exists():
        path=path.parent
    reserve=int(os.environ.get('RIDGE_MIN_FREE_BYTES', 1024**3))
    if reserve < 0 or incoming < 0:
        raise ValueError('Storage thresholds must be nonnegative')
    if shutil.disk_usage(path).free < incoming+reserve:
        raise ValueError('Insufficient disk headroom; archive/prune verified old runs')


def inventory(root):
    root=Path(root)
    files=[p for p in root.rglob('*') if p.is_file() and not p.is_symlink()]
    return {'root':str(root.resolve()), 'bytes':sum(p.stat().st_size for p in files),
            'files':len(files), 'free_bytes':shutil.disk_usage(root).free}


def verified_export(folder):
    folder=Path(folder)
    manifest=json.loads(safe(folder,'SHA256SUMS.json').read_text(encoding='utf-8'))
    if set(manifest) != {'iris.json','ctfd.json','integration.json'}:
        raise ValueError('Only completed three-system exports can be pruned')
    if any(p.is_symlink() for p in folder.rglob('*')):
        raise ValueError('Linked export cannot be pruned')
    if {p.name for p in folder.iterdir()} != set(manifest)|{'SHA256SUMS.json'}:
        raise ValueError('Unexpected files in export')
    for name,digest in manifest.items():
        if sha256(safe(folder,name)) != digest:
            raise ValueError('Corrupt export')
    return manifest


def prune(root, backup, days, apply=False):
    root,backup=Path(root).resolve(),Path(backup).resolve()
    if days < 1 or root==backup or root.is_relative_to(backup) or backup.is_relative_to(root):
        raise ValueError('Separate export/backup roots and positive retention required')
    selected=[]
    for candidate in sorted(root.iterdir()):
        if candidate.is_symlink() or not candidate.is_dir():
            continue
        marker=candidate/'SHA256SUMS.json'
        if not marker.exists() or marker.stat().st_mtime >= time.time()-days*86400:
            continue
        original=verified_export(candidate)
        mirror=safe(backup,candidate.name)
        if original != verified_export(mirror):
            raise ValueError('Backup differs from export')
        selected.append(candidate.name)
        if apply:
            # No path composition crosses shells; resolve and check immediately before deletion.
            resolved=candidate.resolve()
            if resolved.parent != root or candidate.is_symlink():
                raise ValueError('Unsafe export directory')
            shutil.rmtree(resolved)
    return selected


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('root',type=Path)
    parser.add_argument('--backup',type=Path)
    parser.add_argument('--retention-days',type=int,default=30)
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    if args.apply and args.backup is None:
        parser.error('--apply requires an independently verified --backup')
    print(json.dumps(inventory(args.root),indent=2))
    if args.backup:
        print(json.dumps({'prune':prune(args.root,args.backup,args.retention_days,args.apply)}))


if __name__=='__main__':
    main()
