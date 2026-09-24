"""N4 lifecycle tests: repeated up, kill/resume at each phase, missing-resource
re-probes, truthful pause status and start gating. Everything runs against a
scripted fake runner and a temporary runtime; no Docker is touched.
"""
import contextlib
import io
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ridge.deploy import local as deploy_local
from ridge.deploy.local import LifecycleError, LocalStack
from ridge.deploy.journal import Journal


class FakeHost(deploy_local.HostOps):
    """Deterministic host ops: fixed secrets, canned HTTP, tiny ticket set."""

    def __init__(self, runtime):
        self.runtime = Path(runtime)
        self.logins = {}
        self.preflight_calls = 0

    def randhex(self, count=24):
        return 'x' * (count * 2)

    def http_json(self, method, url, headers=None, body=None, timeout=10):
        if self.logins.get('fail'):
            return 503, {}
        return 200, {}

    def wazuh_request(self, method, url, ca_file, credential, body=None, timeout=15, headers=None):
        if url.endswith('/_count'):
            count_file = self.runtime / 'fake-index-count'
            count = int(count_file.read_text()) if count_file.is_file() else 0
            return 200, {'count': count}
        return 200, {}

    def author_tickets(self, config):
        return [{'id': 'T01', 'title': 't', 'subject': 's', 'requires': [],
                 'release_files': [],
                 'questions': [{'id': 'T01-Q1', 'prompt': 'p', 'answer': 'a',
                                'evidence': '/evidence/network/sensor.pcap',
                                'finding': {'evidence': 'e', 'limitation': 'l'}}]}]

    def preflight(self, state, config, env):
        self.preflight_calls += 1
        return {'ready': True, 'teams': len(config['teams']), 'tickets': 1}

    def index_telemetry(self, records, indexer_url, index_name, credential_file, ca_file):
        records = list(records)
        self.indexed = records
        (self.runtime / 'fake-index-count').write_text(str(len(records)))


class FakeRunner:
    """Replays Docker responses from runtime state; records every argv."""

    SERVICES = {
        'central': ['iris', 'iris-worker', 'iris-db', 'ctfd', 'ctfd-db', 'ctfd-cache', 'rabbitmq'],
        'wazuh': ['wazuh-indexer', 'wazuh-manager', 'wazuh-dashboard'],
        'guacamole': ['guacd', 'database', 'guacamole'],
        'desktops': ['desktop-team01', 'desktop-team02'],
        'integration': ['integration'],
    }
    ONE_SHOT = {'central': ['iris-db-init']}

    def __init__(self, runtime, receipts):
        self.runtime = Path(runtime)
        self.receipts = Path(receipts)
        self.calls = []
        self.healthy = True
        self.connections = 0
        self.up_projects = set()

    def run_stdin(self, argv, text, check=True):
        self.calls.append(list(argv))
        if 'psql' in argv:
            self.connections = 2
        return ''

    def run(self, argv, check=True):
        argv = [str(a) for a in argv]
        self.calls.append(argv)
        joined = ' '.join(argv)
        if argv[:2] == ['docker', 'ps']:
            return '\n'.join(getattr(self, 'ps_names', []))
        if argv[:2] == ['docker', 'image']:
            image = argv[-1]
            component = image.split(':')[0].replace('silent-ridge-', '')
            receipt = json.loads((self.receipts / (component + '.json')).read_text())
            return receipt['image_id']
        if argv[:2] == ['docker', 'compose']:
            return self._compose(argv, joined, check)
        if argv[:2] == ['docker', 'inspect']:
            return '/fake-container\n'
        if argv[:2] == ['docker', 'volume']:
            return ''
        if argv[:2] == ['docker', 'cp']:
            if argv[2].split(':')[0] in ('iris', 'ctfd', 'fake-container'):  # container -> host
                Path(argv[3]).parent.mkdir(parents=True, exist_ok=True)
                if '/tmp/silent-ridge-inventory' in argv[2]:
                    inventory = {'inventory': {'case': {'id': 2, 'name': 'case'},
                                               'service_user': {'id': 2, 'login': 'svc'},
                                               'statuses': {'open': 1, 'closed': 4},
                                               'identities': {'team-01': {'id': 3, 'login': 't1'},
                                                              'team-02': {'id': 4, 'login': 't2'}},
                                               'teams': {'team-01': {'id': 1, 'name': 'team-01'},
                                                         'team-02': {'id': 2, 'name': 'team-02'}}},
                                 'preflight': {'ready': True}}
                    Path(argv[3]).write_text(json.dumps(inventory), encoding='utf-8')
                else:  # native database dump
                    Path(argv[3]).write_bytes(b'fake-native-dump')
            return ''
        if argv[:2] == ['docker', 'run'] and 'indexer_job' in joined:
            mount = next((a for a in argv if a.endswith(':/backup')), None)
            if 'dump' in argv and mount:
                backup_dir = Path(mount.rsplit(':/', 1)[0])
                backup_dir.mkdir(parents=True, exist_ok=True)
                (backup_dir / 'index.ndjson').write_text(
                    json.dumps({'_id': 'a', '_source': {'data': {'session': 'S-41'}}}) + '\n'
                    + json.dumps({'_id': 'b', '_source': {'data': {'host': 'WS-31'}}}) + '\n')
                return json.dumps({'ok': True, 'documents': 2})
            if 'probe' in argv:
                return json.dumps({'status': 200, 'count': 2})
            if 'load' in argv:
                return json.dumps({'ok': True, 'loaded': 2})
            return json.dumps({'ok': True, 'indexed': 2})
        if argv[:2] == ['docker', 'run'] and 'tarfile' in joined:
            mount = next((a for a in argv if ':/backup' in a), None)
            if mount:
                host_dir = Path(mount.rsplit(':/', 1)[0])
                host_dir.mkdir(parents=True, exist_ok=True)
                target = next(a for a in argv if a.startswith('/backup/'))
                name = target.split('/backup/')[1]
                import tarfile, io
                with tarfile.open(host_dir / name, 'w:gz') as tar:
                    info = tarfile.TarInfo('marker.txt')
                    data = b'volume-content'
                    info.size = len(data)
                    tar.addfile(info, io.BytesIO(data))
            return ''
        if argv[:2] == ['docker', 'run'] and 'initdb.sh' in joined:
            return 'CREATE TABLE guacamole_connection ();'
        if argv[0] == 'bash':
            certs = Path(argv[-1])
            certs.mkdir(parents=True, exist_ok=True)
            (certs / 'root-ca.pem').write_text('ca')
            return ''
        return ''

    def _compose(self, argv, joined, check):
        kind = next((name for name in self.SERVICES if 'compose.%s.yaml' % name in joined), '')
        if 'ps' in argv:
            if '-q' in argv:
                return 'fakeid\n' if self.healthy and kind in self.up_projects else ''
            if not self.healthy or kind not in self.up_projects:
                return ''
            rows = [json.dumps({'Service': s, 'State': 'running', 'Health': 'healthy',
                                'ExitCode': 0}) for s in self.SERVICES[kind]]
            rows += [json.dumps({'Service': s, 'State': 'exited', 'Health': '', 'ExitCode': 0})
                     for s in self.ONE_SHOT.get(kind, [])]
            return '\n'.join(rows)
        if argv[-1] == 'up' or 'up' in argv:
            self.up_projects.add(kind)
            return ''
        if 'stop' in argv:
            self.up_projects.discard(kind)
            return ''
        if 'psql' in argv:
            return str(self.connections) + '\n'
        if 'ls /evidence' in joined:
            return '/evidence/network/sensor.pcap\n/evidence/wazuh/telemetry.jsonl'
        if 'flask' in argv:
            return json.dumps({'ready': True})
        if 'preflight' in argv:
            return json.dumps({'ready': True, 'teams': 2, 'tickets': 3})
        return ''


def make_runtime(root):
    root = Path(root)
    assets = root / 'assets'
    (assets / 'evidence-public' / 'wazuh').mkdir(parents=True)
    (assets / 'evidence-public' / 'wazuh' / 'telemetry.jsonl').write_text(
        json.dumps({'data': {'session': 'S-41'}}) + '\n' + json.dumps({'data': {'host': 'WS-31'}}) + '\n')
    (assets / 'release-vault').mkdir()
    (assets / 'case-template').mkdir()
    (assets / 'case-template' / 'WS17.aut').write_text('case')
    (assets / 'originals').mkdir()
    (assets / 'wazuh-config' / 'wazuh_indexer').mkdir(parents=True)
    (assets / 'wazuh-config' / 'wazuh_indexer' / 'wazuh.indexer.yml').write_text('y')
    (assets / 'wazuh-config' / 'wazuh_indexer' / 'internal_users.yml').write_text('y')
    (assets / 'wazuh-config' / 'wazuh_cluster').mkdir()
    (assets / 'wazuh-config' / 'wazuh_cluster' / 'wazuh_manager.conf').write_text('y')
    runtime = root / 'runtime'
    runtime.mkdir()
    (runtime / 'local.json').write_text(json.dumps({
        'assets': {'evidence_public': str(assets / 'evidence-public'),
                   'release_vault': str(assets / 'release-vault'),
                   'case_template': str(assets / 'case-template'),
                   'originals': str(assets / 'originals'),
                   'wazuh_config': str(assets / 'wazuh-config')},
        'ports': {'iris': 8081, 'ctfd': 8083, 'guac': 8082, 'wazuh_indexer': 9200}}))
    receipts = root / 'receipts'
    receipts.mkdir()
    source = 'a' * 64
    for component in ('iris', 'ctfd', 'integration', 'desktop'):
        (receipts / (component + '.json')).write_text(json.dumps({
            'component': component, 'image': 'silent-ridge-%s:dev' % component,
            'image_id': 'sha256:' + component * 4, 'source': source}))
    return runtime, receipts, source


def make_profile():
    return {
        'schema_version': 1, 'profile_kind': 'example', 'profile_id': 'n4-test',
        'provider': 'local',
        'event': {'id': 'silent-ridge-test', 'release_id': 'rel-1',
                  'incident_date': '2026-10-15', 'event_start': '2026-10-26T09:00:00-04:00',
                  'duration_minutes': 300, 'timezone': 'America/New_York'},
        'desktops': [{'name': 'desktop-01', 'address': '172.18.0.11'},
                     {'name': 'desktop-02', 'address': '172.18.0.12'}],
        'roster': {'team_count': 2},
        'capacity': {'host': {'vcpus': 16, 'memory_mib': 32768, 'disk_gib': 512},
                     'central': {'vcpus': 4, 'memory_mib': 8192, 'disk_gib': 200},
                     'desktop': {'vcpus': 4, 'memory_mib': 8192, 'disk_gib': 40}},
        'addresses': {'central_bind_ip': '172.18.0.10',
                      'iris_public_url': 'http://127.0.0.1:8081',
                      'ctfd_public_url': 'http://127.0.0.1:8083',
                      'guacamole_public_url': 'http://127.0.0.1:8082'},
        'secret_refs': {'bridge': 'file:secrets/bridge'},
        'retention': {'backup_days': 30, 'export_days': 30},
        'spending': {'ttl_hours': 72},
    }


class FakeCipher:
    """Stand-in for the openssl cipher: copies bytes; never used to claim security."""
    key_env = 'RIDGE_BACKUP_KEY'

    def encrypt(self, source, destination):
        destination.write_bytes(Path(source).read_bytes())

    def decrypt(self, source, destination):
        Path(destination).write_bytes(Path(source).read_bytes())


def fake_export_job(destination):
    destination.mkdir(parents=True, exist_ok=False)
    for name in ('iris.json', 'ctfd.json', 'integration.json'):
        (destination / name).write_text(json.dumps({'watermark': name}), encoding='utf-8')


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.runtime, self.receipts, self.source = make_runtime(self.tmp.name)
        self.runner = FakeRunner(self.runtime, self.receipts)
        self.host = FakeHost(self.runtime)
        self.stack = LocalStack(make_profile(), self.runtime, self.runner,
                                host=self.host, receipts=self.receipts)
        self.stack.cipher = FakeCipher()
        self.stack.export_job = fake_export_job

    def tearDown(self):
        self.tmp.cleanup()

    def test_fresh_up_reaches_provisioned_paused(self):
        result = self.stack.up(self.source)
        self.assertEqual(result['state'], 'PROVISIONED_PAUSED')
        self.assertEqual(set(result['stages']), set(LocalStack.STAGES))
        journal = Journal.open(self.runtime / 'deploy-journal.sqlite')
        self.assertTrue(all(s['state'] == 'verified' for s in journal.steps()))
        # State initialized paused and provisioned.
        con = sqlite3.connect(self.stack.state_path)
        self.assertEqual(con.execute('SELECT mode FROM run').fetchone()[0], 'paused')
        self.assertEqual(con.execute('SELECT provisioned FROM control').fetchone()[0], 1)
        con.close()

    def test_repeated_up_preserves_state_and_skips_creation(self):
        self.stack.up(self.source)
        self.runner.calls.clear()
        creates_before = sum(1 for c in self.runner.calls if 'up' in c)
        result = self.stack.up(self.source)
        self.assertEqual(result['state'], 'PROVISIONED_PAUSED')
        # Second run: no compose up, no secret regeneration, no state re-init.
        self.assertFalse(any('up' in c and 'compose' in c for c in self.runner.calls),
                         'verified stages must probe only')
        mtime = (self.runtime / 'secrets' / 'ridge-iris-bridge').stat().st_mtime_ns
        self.stack.up(self.source)
        self.assertEqual(mtime, (self.runtime / 'secrets' / 'ridge-iris-bridge').stat().st_mtime_ns)

    def test_kill_after_each_stage_resumes(self):
        for killed in LocalStack.STAGES:
            with tempfile.TemporaryDirectory() as other:
                runtime, receipts, source = make_runtime(other)
                runner = FakeRunner(runtime, receipts)
                stack = LocalStack(make_profile(), runtime, runner,
                                   host=FakeHost(runtime), receipts=receipts)
                original = stack._stage_ops

                def sabotaged(stage, original=original, killed=killed):
                    apply, probe = original(stage)
                    if stage == killed and apply is not None:
                        def boom():
                            raise LifecycleError('simulated kill during ' + stage)
                        return boom, probe
                    if stage == killed and apply is None:
                        return None, lambda: (_ for _ in ()).throw(
                            LifecycleError('simulated kill during ' + stage))
                    return apply, probe
                stack._stage_ops = sabotaged
                with self.assertRaises(LifecycleError):
                    stack.up(source)
                journal = Journal.open(runtime / 'deploy-journal.sqlite')
                step = journal.step(killed)
                self.assertEqual(step['state'], 'failed')
                # Resume with a healthy stack: completes without recreating earlier stages.
                stack2 = LocalStack(make_profile(), runtime, runner,
                                    host=FakeHost(runtime), receipts=receipts)
                result = stack2.up(source)
                self.assertEqual(result['state'], 'PROVISIONED_PAUSED')

    def test_verified_stage_resource_missing_is_actionable_error(self):
        self.stack.up(self.source)
        self.runner.healthy = False  # containers vanish after verification
        with self.assertRaises(LifecycleError) as ctx:
            self.stack.up(self.source)
        self.assertIn('no longer verifies', str(ctx.exception))
        self.assertIn('never', str(ctx.exception) + 'reset')  # states the no-reset contract

    def test_missing_secret_mid_runtime_is_actionable(self):
        self.stack.up(self.source)
        (self.runtime / 'secrets' / 'wazuh_writer').unlink()
        with self.assertRaises(LifecycleError) as ctx:
            self.stack.up(self.source)
        message = str(ctx.exception)
        self.assertTrue('missing secret' in message or 'incomplete secrets' in message)
        self.assertFalse((self.runtime / 'secrets' / 'wazuh_writer').is_file(),
                         'a partial secrets dir must never trigger regeneration')

    def test_start_refused_before_readiness(self):
        with self.assertRaises(LifecycleError) as ctx:
            self.stack.start(self.source)
        self.assertIn('up', str(ctx.exception))

    def test_start_then_pause_truthful(self):
        self.stack.up(self.source)
        result = self.stack.start(self.source)
        self.assertEqual(result['mode'], 'running')
        preflight_calls = [c for c in self.runner.calls
                           if 'preflight' in c and 'ridge.cli' in c]
        self.assertGreaterEqual(len(preflight_calls), 1)
        paused = self.stack.pause()
        self.assertEqual(paused['previous'], 'running')
        self.assertEqual(paused['mode'], 'paused')
        con = sqlite3.connect(self.stack.state_path)
        self.assertEqual(con.execute('SELECT mode FROM run').fetchone()[0], 'paused')
        con.close()

    def test_status_reports_probe_failures_truthfully(self):
        document = self.stack.status()
        self.assertFalse(document['event_ready'])
        self.assertIsNone(document['journal'])
        self.assertFalse(document['live']['INFRASTRUCTURE_READY']['ok'])
        self.stack.up(self.source)
        document = self.stack.status()
        self.assertTrue(document['event_ready'], json.dumps(document['live'], indent=2))
        self.runner.healthy = False
        document = self.stack.status()
        self.assertFalse(document['event_ready'])
        self.assertIn('error', document['live']['INFRASTRUCTURE_READY'])

    def test_down_stops_projects_and_marks_journal(self):
        self.stack.up(self.source)
        result = self.stack.down()
        self.assertEqual(result['state'], 'STOPPED')
        self.assertEqual(len(result['projects']), 5)

    def test_up_after_intentional_down_resumes(self):
        self.stack.up(self.source)
        self.stack.down()
        # Probes now fail (containers stopped), but STOPPED is intentional:
        # up re-applies and re-verifies instead of refusing.
        result = self.stack.up(self.source)
        self.assertEqual(result['state'], 'PROVISIONED_PAUSED')
        journal = Journal.open(self.runtime / 'deploy-journal.sqlite')
        self.assertTrue(all(s['state'] == 'verified' for s in journal.steps()))

    def test_backup_requires_paused_and_produces_manifest(self):
        self.stack.up(self.source)
        # Outbox still holds undelivered initial deliveries: backup must refuse.
        with self.assertRaises(LifecycleError) as ctx:
            self.stack.backup()
        self.assertIn('drained', str(ctx.exception))
        # Drain the outbox (worker delivery in production), then backup succeeds.
        con = sqlite3.connect(self.stack.state_path)
        con.execute('UPDATE outbox SET done=1')
        con.commit()
        con.close()
        result = self.stack.backup()
        target = Path(result['recovery_set'])
        self.assertTrue((target / 'RECOVERY-COMPLETE.json').is_file())
        manifest = json.loads((target / 'SHA256SUMS.json').read_text())
        for component in ('state/state.sqlite', 'deploy-journal.sqlite', 'db/iris-db.dump',
                          'db/ctfd-db.sql', 'db/guacamole-db.dump', 'wazuh/index.ndjson',
                          'secrets.tar.gz.enc', 'manifest.json'):
            self.assertIn(component, manifest)
        self.assertIn('volumes/silent-ridge-test-desktops_team01-cases.tar.gz', manifest)

    def test_restore_and_switch_refuse_safely_without_destination(self):
        self.stack.up(self.source)
        with self.assertRaises(LifecycleError) as ctx:
            self.stack.restore()
        self.assertIn('clean destination runtime', str(ctx.exception))
        with self.assertRaises(LifecycleError) as ctx:
            self.stack.switch()
        self.assertIn('E04', str(ctx.exception))

    def _drain_outbox(self):
        con = sqlite3.connect(self.stack.state_path)
        con.execute('UPDATE outbox SET done=1')
        con.commit()
        con.close()

    def _audit_tick(self):
        """Simulate event progress after a backup: one more audit row."""
        con = sqlite3.connect(self.stack.state_path)
        con.execute("INSERT INTO audit(timestamp, actor, action, detail) "
                    "VALUES ('2026-09-24T00:00:00Z', 'test', 'progress', '{}')")
        con.commit()
        con.close()

    def test_down_volumes_without_backup_stops_nothing(self):
        self.stack.up(self.source)
        with self.assertRaises(LifecycleError) as ctx:
            self.stack.down(volumes=True)
        self.assertIn('backup first', str(ctx.exception))
        # The refusal happens before any stop: all projects still up, journal not STOPPED.
        self.assertEqual(len(self.runner.up_projects), 5)
        journal = Journal.open(self.runtime / 'deploy-journal.sqlite')
        self.assertNotEqual(journal.state, 'STOPPED')

    def test_down_volumes_refuses_stale_backup(self):
        self.stack.up(self.source)
        self._drain_outbox()
        self.stack.backup()
        self._audit_tick()  # event progressed after the newest verified set
        with self.assertRaises(LifecycleError) as ctx:
            self.stack.down(volumes=True)
        self.assertIn('progressed', str(ctx.exception))
        self.assertEqual(len(self.runner.up_projects), 5)
        journal = Journal.open(self.runtime / 'deploy-journal.sqlite')
        self.assertNotEqual(journal.state, 'STOPPED')

    def test_down_volumes_accepts_current_backup(self):
        self.stack.up(self.source)
        self._drain_outbox()
        self.stack.backup()
        result = self.stack.down(volumes=True)
        self.assertEqual(result['state'], 'STOPPED')
        self.assertIn('silent-ridge-test-iris-db', result['volumes_removed'])
        journal = Journal.open(self.runtime / 'deploy-journal.sqlite')
        self.assertEqual(journal.state, 'STOPPED')

    def test_down_volumes_after_fence_uses_pre_fence_backup(self):
        self.stack.up(self.source)
        self._drain_outbox()
        self.stack.backup()
        info = self.stack.fence()  # appends control-plane audit rows only
        self.assertTrue(info['fenced'])
        # backup() refuses fenced sites, so the pre-fence set must satisfy the wipe.
        result = self.stack.down(volumes=True)
        self.assertEqual(result['state'], 'STOPPED')
        self.assertTrue(result['volumes_removed'])


class FenceDispatchTests(unittest.TestCase):
    """Regression: the fence action was accepted by the argument parser but omitted
    from the lifecycle dispatch, silently falling through to image verification."""

    def test_fence_reaches_lifecycle_dispatch(self):
        from ridge.deploy import __main__ as deploy_main
        argv = sys.argv
        stderr = io.StringIO()
        sys.argv = ['ridge.deploy', 'fence']
        try:
            with contextlib.redirect_stderr(stderr):
                with self.assertRaises(SystemExit):
                    deploy_main.main()
        finally:
            sys.argv = argv
        # Lifecycle path demands --profile; the old fallthrough demanded a build.
        self.assertIn('--profile is required for fence', stderr.getvalue())


if __name__ == '__main__':
    unittest.main()
