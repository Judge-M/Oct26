import json
import os
import tempfile
import time
import unittest
from pathlib import Path

from ridge.artifacts import sha256
from ridge.retention import (abandoned_staging, accounting, cleanup, plan_cleanup,
                             require_allocation, verify_backup)


def make_backup(path, files):
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    sums = {}
    for name, data in files.items():
        target = path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        sums[name] = sha256(target)
    (path / 'SHA256SUMS.json').write_text(json.dumps(sums))
    return path


class RetentionTests(unittest.TestCase):
    def test_accounting_categorizes_and_flags_unknown(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'events/e1/vms').mkdir(parents=True)
            (root / 'events/e1/vms/disk.qcow2').write_bytes(b'x' * 10)
            (root / 'events/e1/cases').mkdir(parents=True)
            (root / 'events/e1/cases/case.tar.gz').write_bytes(b'y' * 5)
            (root / 'unknown-dir').mkdir()
            (root / 'unknown-dir/blob').write_bytes(b'z' * 3)
            result = accounting(root)
            self.assertEqual(result['vms'], 10)
            self.assertEqual(result['cases'], 5)
            self.assertEqual(result['unknown'], 3)

    def test_allocation_reserves(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with self.assertRaisesRegex(ValueError, 'nonnegative'):
                require_allocation(root, -1)
            with self.assertRaisesRegex(ValueError, 'headroom'):
                require_allocation(root, 10 ** 18, reserve_bytes=0)
            self.assertGreater(require_allocation(root, 1, reserve_bytes=0), 0)

    def test_cleanup_scoped_verified_and_safe(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / 'root'
            backup_root = Path(folder) / 'backup-root'
            event = root / 'events/e1'
            event.mkdir(parents=True)
            old = time.time() - 10 * 86400
            candidate = make_backup(event / 'backups/old', {'data.bin': b'payload'})
            make_backup(backup_root / 'old', {'data.bin': b'payload'})
            os.utime(candidate, (old, old))
            plan = plan_cleanup(root, 'e1', backup_root, retention_days=5, now=time.time())
            self.assertEqual(plan, ['old'])
            # A corrupt mirror prevents pruning.
            (backup_root / 'old' / 'data.bin').write_bytes(b'tampered')
            self.assertEqual(plan_cleanup(root, 'e1', backup_root, 5), [])
            make_backup(backup_root / 'old', {'data.bin': b'payload'})
            # An active run is never pruned.
            (event / 'active').write_text('running')
            self.assertEqual(plan_cleanup(root, 'e1', backup_root, 5), [])
            (event / 'active').unlink()
            # Apply removes only the planned event-owned backup.
            (root / 'golden').mkdir()
            (root / 'golden/keep.bin').write_bytes(b'golden')
            removed = cleanup(root, 'e1', backup_root, retention_days=5, apply=True)
            self.assertEqual(removed, ['old'])
            self.assertFalse(candidate.exists())
            self.assertTrue((root / 'golden/keep.bin').is_file())
            self.assertFalse(any(root.glob('**/unknown*')))

    def test_recent_backup_not_pruned_and_verify_requires_manifest(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / 'root'
            backup_root = Path(folder) / 'backup-root'
            event = root / 'events/e1'
            event.mkdir(parents=True)
            make_backup(event / 'backups/fresh', {'a': b'1'})
            make_backup(backup_root / 'fresh', {'a': b'1'})
            self.assertEqual(plan_cleanup(root, 'e1', backup_root, retention_days=30), [])
            with self.assertRaisesRegex(ValueError, 'verifiable manifest'):
                verify_backup(root / 'nowhere')

    def test_abandoned_staging_respects_locks(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            staging = root / 'events/e1/staging'
            (staging / 'held').mkdir(parents=True)
            (staging / 'abandoned').mkdir()
            self.assertEqual(abandoned_staging(root, 'e1', held_locks=('held',)), ['abandoned'])


if __name__ == '__main__':
    unittest.main()
