"""D04 - storage accounting, allocation reserves and event-scoped retention.

Extends storage accounting beyond logical JSON exports to VM clones, cases, workspaces,
logs, indices, backups, partial downloads and release caches. Incoming allocation is
estimated before copies/imports and checked against a configurable reserve. Cleanup is a
dry run by default, scoped to event-owned directories, and removes only expired data that
is independently verified in a separate backup root. Golden artifacts, active runs and
unknown directories are never touched.
"""
import argparse
import json
import os
import shutil
import time
from pathlib import Path

from ridge.artifacts import safe, sha256

CATEGORIES = ('vms', 'cases', 'workspaces', 'logs', 'indices', 'backups',
              'downloads', 'cache', 'staging')
PROTECTED = ('golden',)
ACTIVE_MARKER = 'active'
MIN_FREE_ENV = 'RIDGE_MIN_FREE_BYTES'


def _reserve(reserve_bytes):
    value = int(os.environ.get(MIN_FREE_ENV, 1024 ** 3)) if reserve_bytes is None else reserve_bytes
    if value < 0:
        raise ValueError('Storage thresholds must be nonnegative')
    return value


def accounting(root):
    root = Path(root)
    result = {name: 0 for name in CATEGORIES}
    result['unknown'] = 0
    if not root.exists():
        return result
    for path in root.rglob('*'):
        if not path.is_file() or path.is_symlink():
            continue
        parts = path.relative_to(root).parts
        matched = next((part for part in parts if part in CATEGORIES), None)
        if matched:
            result[matched] += path.stat().st_size
        else:
            result['unknown'] += path.stat().st_size
    result['free_bytes'] = shutil.disk_usage(root).free
    return result


def require_allocation(root, incoming, reserve_bytes=None):
    root = Path(root)
    while not root.exists():
        root = root.parent
    if incoming < 0:
        raise ValueError('Incoming allocation must be nonnegative')
    reserve = _reserve(reserve_bytes)
    free = shutil.disk_usage(root).free
    if free < incoming + reserve:
        raise ValueError('Insufficient disk headroom for allocation plus reserve')
    return free


def verify_backup(backup):
    backup = Path(backup)
    if (backup / 'RESTORABLE').is_file() and (backup / 'manifest.json').is_file():
        from ridge.recovery import verify as verify_recovery
        verify_recovery(backup)
        return True
    sums = backup / 'SHA256SUMS.json'
    if sums.is_file():
        manifest = json.loads(sums.read_text(encoding='utf-8'))
        for name, digest in manifest.items():
            path = safe(backup, name)
            if not path.is_file() or sha256(path) != digest:
                raise ValueError('Backup content is corrupt: ' + name)
        return True
    raise ValueError('Backup has no verifiable manifest')


def _fingerprint(folder):
    return {path.relative_to(folder).as_posix(): sha256(path)
            for path in sorted(Path(folder).rglob('*')) if path.is_file()}


def plan_cleanup(root, event, backup_root, retention_days, now=None):
    if retention_days < 1:
        raise ValueError('Positive retention is required')
    root, backup_root = Path(root).resolve(), Path(backup_root).resolve()
    if root == backup_root or root.is_relative_to(backup_root) or backup_root.is_relative_to(root):
        raise ValueError('Separate event and backup roots are required')
    now = time.time() if now is None else now
    event_dir = root / 'events' / event
    if not event_dir.is_dir():
        raise ValueError('Unknown event directory: ' + event)
    if (event_dir / ACTIVE_MARKER).exists():
        return []
    plan = []
    backups = event_dir / 'backups'
    if not backups.is_dir():
        return plan
    for candidate in sorted(backups.iterdir()):
        if candidate.is_symlink() or not candidate.is_dir():
            continue
        if candidate.stat().st_mtime >= now - retention_days * 86400:
            continue
        mirror = backup_root / candidate.name
        try:
            verify_backup(candidate)
            verify_backup(mirror)
        except ValueError:
            continue
        if _fingerprint(candidate) != _fingerprint(mirror):
            continue
        plan.append(candidate.name)
    return plan


def cleanup(root, event, backup_root, retention_days, apply=False, now=None):
    root = Path(root).resolve()
    plan = plan_cleanup(root, event, backup_root, retention_days, now)
    if apply:
        backups = (root / 'events' / event / 'backups').resolve()
        for name in plan:
            candidate = (backups / name)
            if candidate.is_symlink() or candidate.resolve().parent != backups:
                raise ValueError('Unsafe retention target')
            shutil.rmtree(candidate)
    return plan


def abandoned_staging(root, event, held_locks=()):
    staging = Path(root) / 'events' / event / 'staging'
    if not staging.is_dir():
        return []
    return sorted(entry.name for entry in staging.iterdir()
                  if entry.is_dir() and not entry.is_symlink() and entry.name not in held_locks)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    parser.add_argument('--event')
    parser.add_argument('--backup-root', type=Path)
    parser.add_argument('--retention-days', type=int, default=30)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    print(json.dumps(accounting(args.root), indent=2))
    if args.event and args.backup_root:
        print(json.dumps({'plan': cleanup(args.root, args.event, args.backup_root,
                                          args.retention_days, args.apply)}, indent=2))


if __name__ == '__main__':
    main()
