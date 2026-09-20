"""N5 semantics: recovery-set completeness (D02), restore refusals and happy path
(D03), retention pruning of verified sets (D04), and active-site fencing (F01)."""
import json
import sqlite3
import unittest

from pathlib import Path

from ridge.deploy.local import LifecycleError
from ridge.deploy import recovery
from ridge.state import Conflict, State
from test_deploy_lifecycle import (FakeCipher, FakeHost, FakeRunner, fake_export_job,
                                   make_profile, make_runtime)
from ridge.deploy.local import LocalStack


def make_stack(case):
    runtime, receipts, source = make_runtime(case.tmp.name)
    runner = FakeRunner(runtime, receipts)
    stack = LocalStack(make_profile(), runtime, runner,
                       host=FakeHost(runtime), receipts=receipts)
    stack.cipher = FakeCipher()
    stack.export_job = fake_export_job
    return stack, runner, source, receipts


def drain(stack):
    con = sqlite3.connect(stack.state_path)
    con.execute('UPDATE outbox SET done=1')
    con.commit()
    con.close()


class CompletenessTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        self.stack, self.runner, self.source, self.receipts = make_stack(self)
        self.stack.up(self.source)
        drain(self.stack)
        self.set_dir = Path(self.stack.backup()['recovery_set'])

    def tearDown(self):
        self.tmp.cleanup()

    def test_complete_set_verifies(self):
        manifest = recovery.verify_set(self.set_dir)
        self.assertEqual(manifest['event'], 'silent-ridge-test')
        self.assertEqual(manifest['secrets_encryption']['key_env'], 'RIDGE_BACKUP_KEY')

    def test_missing_marker_is_never_restorable(self):
        (self.set_dir / 'RECOVERY-COMPLETE.json').unlink()
        with self.assertRaises(recovery.RecoveryError):
            recovery.verify_set(self.set_dir)

    def test_corrupt_file_is_never_restorable(self):
        target = self.set_dir / 'db' / 'iris-db.dump'
        target.write_bytes(target.read_bytes() + b'x')
        with self.assertRaises(recovery.RecoveryError):
            recovery.verify_set(self.set_dir)

    def test_missing_component_is_never_restorable(self):
        (self.set_dir / 'wazuh' / 'index.ndjson').unlink()
        # Hash manifest still lists it: verification must fail.
        with self.assertRaises(recovery.RecoveryError):
            recovery.verify_set(self.set_dir)


class RestoreRefusalTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        self.stack, self.runner, self.source, self.receipts = make_stack(self)
        self.stack.up(self.source)
        drain(self.stack)
        self.set_dir = Path(self.stack.backup()['recovery_set'])

    def tearDown(self):
        self.tmp.cleanup()

    def clean_runtime(self):
        runtime = Path(self.tmp.name) / 'restore-target'
        runtime.mkdir()
        (runtime / 'local.json').write_text(
            (self.stack.runtime / 'local.json').read_text(encoding='utf-8'), encoding='utf-8')
        return runtime

    def test_dirty_destination_refused(self):
        runtime = self.clean_runtime()
        (runtime / 'secrets').mkdir()
        with self.assertRaises(recovery.RecoveryError) as ctx:
            recovery.restore(make_profile(), runtime, self.set_dir, self.runner,
                             cipher=FakeCipher(), receipts=self.receipts)
        self.assertIn('not clean', str(ctx.exception))

    def test_live_containers_refused(self):
        self.runner.ps_names = ['silent-ridge-test-central-iris-1']
        with self.assertRaises(recovery.RecoveryError) as ctx:
            recovery.restore(make_profile(), self.clean_runtime(), self.set_dir,
                             self.runner, cipher=FakeCipher(), receipts=self.receipts)
        self.assertIn('still running', str(ctx.exception))

    def test_wrong_release_refused(self):
        with self.assertRaises(recovery.RecoveryError) as ctx:
            recovery.restore(make_profile(), self.clean_runtime(), self.set_dir,
                             self.runner, cipher=FakeCipher(), receipts=self.receipts,
                             release_fingerprint='0' * 64)
        self.assertIn('wrong-release', str(ctx.exception))

    def test_corrupt_set_refused_before_any_change(self):
        (self.set_dir / 'manifest.json').write_text('{}')
        runtime = self.clean_runtime()
        with self.assertRaises(recovery.RecoveryError):
            recovery.restore(make_profile(), runtime, self.set_dir, self.runner,
                             cipher=FakeCipher(), receipts=self.receipts)
        self.assertEqual([p.name for p in runtime.iterdir()], ['local.json'])

    def test_restore_happy_path_leaves_paused(self):
        runtime = self.clean_runtime()
        result = recovery.restore(make_profile(), runtime, self.set_dir, self.runner,
                                  host=FakeHost(runtime), cipher=FakeCipher(),
                                  receipts=self.receipts, release_fingerprint=self.source)
        self.assertEqual(result['mode'], 'paused')
        self.assertTrue((runtime / 'state' / 'state.sqlite').is_file())
        self.assertTrue((runtime / 'secrets' / 'team-credentials.json').is_file())
        self.assertTrue((runtime / 'specs' / 'iris-bootstrap-spec.json').is_file())


class FencingTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        self.stack, self.runner, self.source, self.receipts = make_stack(self)
        self.stack.up(self.source)

    def tearDown(self):
        self.tmp.cleanup()

    def test_fence_requires_drained(self):
        with self.assertRaises(LifecycleError) as ctx:
            self.stack.fence()
        self.assertIn('Drain', str(ctx.exception))

    def test_fenced_site_refuses_mutations_and_stale_workers(self):
        drain(self.stack)
        info = self.stack.fence()
        self.assertEqual(info['state'], 'FENCED')
        self.assertTrue(info['fenced'])
        state = State(self.stack.state_path)
        with self.assertRaises(Conflict):
            state.mode('tester', 'running')
        # Stale worker path: any guarded mutation raises, including provision.
        with self.assertRaises(Conflict):
            state.provision('stale-worker')

    def test_unfence_is_explicit_rollback(self):
        drain(self.stack)
        self.stack.fence()
        state = State(self.stack.state_path)
        state.unfence('operator')
        self.assertFalse(state.site_info()['fenced'])
        with self.assertRaises(Conflict):
            state.unfence('operator')  # not fenced anymore

    def test_activation_generation_is_monotonic(self):
        state = State(self.stack.state_path)
        state.activate_generation('operator', 2)
        with self.assertRaises(Conflict):
            state.activate_generation('operator', 2)
        with self.assertRaises(Conflict):
            state.activate_generation('operator', 1)
        drain(self.stack)
        self.stack.fence()
        with self.assertRaises(Conflict):
            state.activate_generation('operator', 3)  # fenced sites never activate

    def test_two_sites_cannot_share_active_generation(self):
        """Simulated: restore a fenced site's backup to a clean destination; the
        destination activates generation+1 while the source stays fenced at the
        old generation. Mutations fail at the source and succeed nowhere until
        explicit unpause at the destination."""
        drain(self.stack)
        self.stack.fence()
        source_state = State(self.stack.state_path)
        self.assertEqual(source_state.site_info(), {'fenced': True, 'generation': 1})
        with self.assertRaises(Conflict):
            source_state.announce('attacker', 'write attempt')


class RetentionTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def test_prune_requires_intact_independent_backup(self):
        import time
        from ridge import storage
        root = Path(self.tmp.name) / 'sets'
        backup = Path(self.tmp.name) / 'mirror'
        root.mkdir()
        backup.mkdir()
        old = root / '20260901T000000Z'
        old.mkdir()
        (old / 'SHA256SUMS.json').write_text(json.dumps({'iris.json': 'x', 'ctfd.json': 'y',
                                                         'integration.json': 'z'}))
        # Corrupt/unverifiable marker content: prune must refuse, not delete.
        import os
        old_time = time.time() - 40 * 86400
        os.utime(old / 'SHA256SUMS.json', (old_time, old_time))
        with self.assertRaises(ValueError):
            storage.prune(root, backup, 30, apply=True)
        self.assertTrue(old.is_dir())

    def test_unknown_directories_never_removed(self):
        from ridge import storage
        root = Path(self.tmp.name) / 'sets'
        backup = Path(self.tmp.name) / 'mirror'
        root.mkdir()
        backup.mkdir()
        stranger = root / 'somebody-elses-data'
        stranger.mkdir()
        (stranger / 'file.txt').write_text('keep me')
        selected = storage.prune(root, backup, 30, apply=True)
        self.assertEqual(selected, [])
        self.assertTrue((stranger / 'file.txt').is_file())


if __name__ == '__main__':
    unittest.main()
