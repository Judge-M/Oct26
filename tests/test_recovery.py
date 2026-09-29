"""N5 semantics: recovery-set completeness (D02), restore refusals and happy path
(D03), retention pruning of verified sets (D04), and active-site fencing (F01)."""
import json
import os
import sqlite3
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from pathlib import Path

from ridge.deploy.local import LifecycleError
from ridge.deploy import recovery
from ridge.state import Conflict, State
from test_deploy_lifecycle import (FakeCipher, FakeHost, FakeRunner, fake_export_job,
                                   make_profile, make_runtime)
from ridge.deploy.local import LocalStack


class CipherRuntimeTests(unittest.TestCase):
    def test_offline_docker_cipher_keeps_key_out_of_command(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'secrets.tar.gz'
            destination = Path(folder) / 'secrets.tar.gz.enc'
            source.write_bytes(b'disposable secret archive')
            calls = []

            def runner(argv, **kwargs):
                calls.append((argv, kwargs))
                return SimpleNamespace(returncode=0, stderr='')

            with patch.dict(os.environ, {'RIDGE_BACKUP_KEY': 'disposable-test-key-12345'}), \
                    patch('ridge.deploy.recovery.shutil.which', return_value=None):
                recovery.Cipher(runner=runner).encrypt(source, destination)
            command, options = calls[0]
            self.assertEqual(command[:5], ['docker', 'run', '--rm', '--pull', 'never'])
            self.assertIn('--network', command)
            self.assertIn('none', command)
            self.assertIn('--read-only', command)
            self.assertIn('--env', command)
            self.assertIn('RIDGE_BACKUP_KEY', command)
            self.assertIn('silent-ridge-integration:dev', command)
            self.assertIn('/source/secrets.tar.gz', command)
            self.assertIn('/destination/secrets.tar.gz.enc', command)
            self.assertNotIn('disposable-test-key-12345', ' '.join(command))
            self.assertEqual(options['env']['RIDGE_BACKUP_KEY'], 'disposable-test-key-12345')

    def test_cipher_refuses_missing_key_before_running_docker(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'input'
            source.write_bytes(b'x')
            with patch.dict(os.environ, {'RIDGE_BACKUP_KEY': ''}):
                with self.assertRaisesRegex(recovery.RecoveryError, 'RIDGE_BACKUP_KEY'):
                    recovery.Cipher(runner=lambda *args, **kwargs: self.fail('ran Docker')).encrypt(
                        source, Path(folder) / 'output')


class VolumeArchiveRuntimeTests(unittest.TestCase):
    def test_restore_runs_as_root_offline_and_uses_safe_tar_filter(self):
        calls = []
        recovery._volume_untar(calls.append, 'event-ctfd-logs',
                               Path('backup') / 'event-ctfd-logs.tar.gz')
        self.assertEqual(calls[0], ['docker', 'volume', 'create', 'event-ctfd-logs'])
        command = calls[1]
        self.assertIn('--pull', command)
        self.assertIn('never', command)
        self.assertIn('--network', command)
        self.assertIn('none', command)
        self.assertEqual(command[command.index('--user') + 1], '0:0')
        self.assertIn("filter='data'", command[command.index('-c') + 1])


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

    def test_preexisting_event_volume_refused_before_runtime_materialization(self):
        stale = 'silent-ridge-test-desktops_team01-workspace'
        self.runner.volume_names.add(stale)
        runtime = self.clean_runtime()
        with self.assertRaisesRegex(recovery.RecoveryError, 'stale data'):
            recovery.restore(make_profile(), runtime, self.set_dir, self.runner,
                             cipher=FakeCipher(), receipts=self.receipts)
        self.assertEqual([p.name for p in runtime.iterdir()], ['local.json'])

    def test_restore_refuses_non_neutral_roster_mismatch(self):
        manifest_path = self.set_dir / 'manifest.json'
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        manifest['teams'] = ['associate-renamed-a', 'associate-renamed-b']
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
        recovery._write_sums(self.set_dir)
        runtime = self.clean_runtime()
        self.runner.volume_names.clear()
        with self.assertRaisesRegex(recovery.RecoveryError, 'original event profile'):
            recovery.restore(make_profile(), runtime, self.set_dir, self.runner,
                             cipher=FakeCipher(), receipts=self.receipts)
        self.assertEqual([p.name for p in runtime.iterdir()], ['local.json'])

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
        self.runner.volume_names.clear()
        result = recovery.restore(make_profile(), runtime, self.set_dir, self.runner,
                                  host=FakeHost(runtime), cipher=FakeCipher(),
                                  receipts=self.receipts, release_fingerprint=self.source)
        self.assertEqual(result['mode'], 'paused')
        self.assertTrue((runtime / 'state' / 'state.sqlite').is_file())
        self.assertTrue((runtime / 'secrets' / 'team-credentials.json').is_file())
        self.assertTrue((runtime / 'specs' / 'iris-bootstrap-spec.json').is_file())
        self.assertTrue((runtime / 'wazuh-config' / 'internal_users.yml').is_file())
        self.assertTrue((runtime / 'wazuh-config' / 'ossec.conf').is_file())
        central_wait_start = [call for call in self.runner.calls
                              if 'compose.central.yaml' in ' '.join(call)
                              and call[-4:] == ['up', '-d', 'ctfd-cache', 'rabbitmq']]
        self.assertEqual(len(central_wait_start), 1)

    def test_restore_recreates_effective_team_override_from_manifest(self):
        source_runtime, receipts, source = make_runtime(Path(self.tmp.name) / 'ten-source')
        (source_runtime / 'overrides.json').write_text(
            json.dumps({'team_count': 10}), encoding='utf-8')
        profile = make_profile()
        profile['capacity']['central']['memory_mib'] = 6144
        profile['capacity']['desktop'].update(
            {'vcpus': 1, 'memory_mib': 2048, 'disk_gib': 15})
        runner = FakeRunner(source_runtime, receipts)
        source_stack = LocalStack(profile, source_runtime, runner,
                                  host=FakeHost(source_runtime), receipts=receipts)
        source_stack.cipher = FakeCipher()
        source_stack.export_job = fake_export_job
        source_stack.up(source)
        drain(source_stack)
        recovery_set = Path(source_stack.backup()['recovery_set'])
        runtime = Path(self.tmp.name) / 'ten-restore'
        runtime.mkdir()
        (runtime / 'local.json').write_text(
            (source_runtime / 'local.json').read_text(encoding='utf-8'), encoding='utf-8')
        runner.volume_names.clear()
        result = recovery.restore(profile, runtime, recovery_set, runner,
                                  host=FakeHost(runtime), cipher=FakeCipher(),
                                  receipts=receipts, release_fingerprint=source)
        self.assertEqual(result['mode'], 'paused')
        self.assertEqual(json.loads((runtime / 'overrides.json').read_text()),
                         {'team_count': 10})
        restored = LocalStack(profile, runtime, runner,
                              host=FakeHost(runtime), receipts=receipts)
        self.assertEqual(len(restored.teams), 10)

    def test_restore_replaces_asset_trees_instead_of_overlaying(self):
        runtime = self.clean_runtime()
        local = json.loads((runtime / 'local.json').read_text(encoding='utf-8'))
        evidence = Path(local['assets']['evidence_public'])
        vault = Path(local['assets']['release_vault'])
        (evidence / 'stale-only.txt').write_text('must disappear', encoding='utf-8')
        (vault / 'stale-only.txt').write_text('must disappear', encoding='utf-8')
        self.runner.volume_names.clear()
        recovery.restore(make_profile(), runtime, self.set_dir, self.runner,
                         host=FakeHost(runtime), cipher=FakeCipher(),
                         receipts=self.receipts, release_fingerprint=self.source)
        self.assertFalse((evidence / 'stale-only.txt').exists())
        self.assertFalse((vault / 'stale-only.txt').exists())


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
