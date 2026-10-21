"""Multi-host desktop placement stays opt-in and host configuration stays private."""
import json
import tempfile
import unittest
from pathlib import Path

from ridge.deploy.journal import Journal
from ridge.deploy.local import LifecycleError, LocalStack
from tests.test_deploy_lifecycle import FakeHost, FakeRunner, make_profile, make_runtime


class MultiHostDesktopTests(unittest.TestCase):
    def setUp(self):
        scratch = Path(__file__).resolve().parents[1] / 'work' / 'test-multi-host'
        scratch.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=scratch)
        self.runtime, self.receipts, _ = make_runtime(self.tmp.name)
        self.profile = make_profile()
        self.profile['desktops'][1].update({
            'worker': 'worker-02',
            'address': '192.168.1.3',
            'vnc_port': 5902,
        })
        self.profile['capacity']['workers'] = {
            'worker-02': {'vcpus': 20, 'memory_mib': 65536, 'disk_gib': 475}}
        local_path = self.runtime / 'local.json'
        local = json.loads(local_path.read_text(encoding='utf-8'))
        local['desktop_workers'] = {
            'worker-02': {
                'docker_context': 'ridge-worker-02',
                'vnc_password_dir': 'C:/SilentRidge/runtime/secrets/vnc',
                'assets': {
                    'case_template': 'C:/SilentRidge/Oct26/evidence/prepared-case',
                    'evidence_public': 'C:/SilentRidge/Oct26/evidence/public',
                    'originals': 'C:/SilentRidge/Oct26/evidence/originals',
                },
            },
        }
        local_path.write_text(json.dumps(local), encoding='utf-8')
        self.runner = FakeRunner(self.runtime, self.receipts)
        self.stack = LocalStack(self.profile, self.runtime, self.runner,
                                host=FakeHost(self.runtime), receipts=self.receipts)

    def tearDown(self):
        self.tmp.cleanup()

    def _configure_relay(self):
        local_path = self.runtime / 'local.json'
        local = json.loads(local_path.read_text(encoding='utf-8'))
        local['desktop_workers']['worker-02']['guacamole_relay'] = {
            'address': 'host.docker.internal',
            'listen_address': '0.0.0.0',
            'source_cidr': '192.168.48.0/20',
            'ports': {'desktop-02': 15902},
        }
        local_path.write_text(json.dumps(local), encoding='utf-8')
        self.stack = LocalStack(self.profile, self.runtime, self.runner,
                                host=FakeHost(self.runtime), receipts=self.receipts)

    def test_missing_worker_runtime_configuration_fails_closed(self):
        local_path = self.runtime / 'local.json'
        local = json.loads(local_path.read_text(encoding='utf-8'))
        del local['desktop_workers']
        local_path.write_text(json.dumps(local), encoding='utf-8')
        with self.assertRaisesRegex(LifecycleError, 'missing configuration for worker-02'):
            LocalStack(self.profile, self.runtime, self.runner,
                       host=FakeHost(self.runtime), receipts=self.receipts)

    def test_worker_env_and_vnc_publish_override_are_private_runtime_files(self):
        self.stack._ensure_secrets()
        self.stack._render_env()
        env = (self.runtime / 'env' / 'desktops-worker-02.env').read_text(encoding='utf-8')
        self.assertIn('RIDGE_CASE_DIR=C:/SilentRidge/Oct26/evidence/prepared-case', env)
        self.assertIn('RIDGE_VNC_PASSWORD_DIR=C:/SilentRidge/runtime/secrets/vnc', env)
        override = (self.runtime / 'desktops-worker-02.override.yaml').read_text(
            encoding='utf-8')
        self.assertIn('desktop-team02:', override)
        self.assertIn('"192.168.1.3:5902:5901"', override)
        self.assertNotIn('desktop-team01:', override)

    def test_services_are_started_on_their_assigned_docker_context(self):
        self.stack._start_desktop_services(['desktop-team01', 'desktop-team02'])
        local = [call for call in self.runner.calls
                 if call[:2] == ['docker', 'compose'] and 'desktop-team01' in call]
        remote = [call for call in self.runner.calls
                  if call[:3] == ['docker', '--context', 'ridge-worker-02']
                  and 'desktop-team02' in call]
        self.assertEqual(len(local), 1)
        self.assertEqual(len(remote), 1)
        self.assertNotIn('desktop-team02', local[0])
        self.assertNotIn('desktop-team01', remote[0])

    def test_worker_vnc_secret_is_streamed_on_stdin_not_argv(self):
        self.stack._ensure_secrets()
        self.stack._stage_worker_vnc_secrets()
        calls = [call for call in self.runner.calls
                 if call[:3] == ['docker', '--context', 'ridge-worker-02']
                 and any('cat > /vnc/team02' in arg for arg in call)]
        self.assertEqual(len(calls), 1)
        secret = (self.stack.secrets_dir / 'vnc' / 'team02').read_text(
            encoding='utf-8')
        self.assertNotIn(secret, calls[0])

    def test_guacamole_uses_remote_lan_endpoint(self):
        remote = self.stack._guacamole_desktop(self.stack.profile['desktops'][1])
        self.assertNotIn('container', remote)
        self.assertEqual(remote['address'], '192.168.1.3')
        self.assertEqual(remote['port'], 5902)

    def test_guacamole_uses_configured_host_relay(self):
        self._configure_relay()
        remote = self.stack._guacamole_desktop(self.stack.profile['desktops'][1])
        self.assertEqual(remote['address'], 'host.docker.internal')
        self.assertEqual(remote['port'], 15902)

    def test_relay_requires_an_exact_port_map_for_worker_desktops(self):
        local_path = self.runtime / 'local.json'
        local = json.loads(local_path.read_text(encoding='utf-8'))
        local['desktop_workers']['worker-02']['guacamole_relay'] = {
            'address': 'host.docker.internal',
            'source_cidr': '192.168.48.0/20',
            'ports': {'wrong-desktop': 15902},
        }
        local_path.write_text(json.dumps(local), encoding='utf-8')
        with self.assertRaisesRegex(LifecycleError, 'must map every desktop assigned'):
            LocalStack(self.profile, self.runtime, self.runner,
                       host=FakeHost(self.runtime), receipts=self.receipts)

    def test_relay_firewall_is_scoped_and_portproxy_targets_worker(self):
        self._configure_relay()
        self.stack._apply_guacamole_relays()
        joined = [' '.join(call) for call in self.runner.calls]
        firewall = [call for call in joined if 'New-NetFirewallRule' in call]
        proxy = [call for call in joined if 'portproxy add v4tov4' in call]
        self.assertEqual(len(firewall), 1)
        self.assertIn("-RemoteAddress '192.168.48.0/20'", firewall[0])
        self.assertIn('-Profile Private', firewall[0])
        self.assertEqual(len(proxy), 1)
        self.assertIn('listenaddress=0.0.0.0 listenport=15902', proxy[0])
        self.assertIn('connectaddress=192.168.1.3 connectport=5902', proxy[0])

    def test_stopped_runtime_reconciles_endpoint_without_rotating_credentials(self):
        self.stack._ensure_secrets()
        self.stack._render_specs()
        credentials_path = self.runtime / 'specs' / 'guac-credentials.json'
        credentials = credentials_path.read_bytes()
        self._configure_relay()
        self.stack._render_specs()
        config = json.loads((self.runtime / 'specs' / 'guac-config.json').read_text())
        remote = next(row for row in config['desktops'] if row['id'] == 'desktop-02')
        self.assertEqual(remote['address'], 'host.docker.internal')
        self.assertEqual(remote['port'], 15902)
        self.assertEqual(credentials_path.read_bytes(), credentials)

    def test_relay_cleanup_removes_only_exact_event_resources(self):
        self._configure_relay()
        self.stack._remove_guacamole_relays()
        joined = [' '.join(call) for call in self.runner.calls]
        proxy = [call for call in joined if 'portproxy delete v4tov4' in call]
        firewall = [call for call in joined if 'Remove-NetFirewallRule' in call]
        self.assertEqual(proxy, [
            'netsh interface portproxy delete v4tov4 '
            'listenaddress=0.0.0.0 listenport=15902'])
        self.assertEqual(len(firewall), 1)
        self.assertIn('Silent-Ridge-Guac-Relay-silent-ridge-test-worker-02-15902',
                      firewall[0])

    def test_volume_wipe_is_refused_before_any_worker_is_stopped(self):
        Journal.create(self.runtime / 'deploy-journal.sqlite', self.profile,
                       self.profile['event']['release_id'], 'test-release-fingerprint')
        before = list(self.runner.calls)
        with self.assertRaisesRegex(LifecycleError, 'down --volumes refused'):
            self.stack.down(volumes=True)
        self.assertEqual(self.runner.calls, before)


if __name__ == '__main__':
    unittest.main()
