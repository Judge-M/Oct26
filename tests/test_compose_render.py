"""Deterministic Compose run-scoping and audit tests (B04).

``docker compose config`` is unavailable on this Windows host (BLOCKED: no
Docker). These tests parse the Compose documents and enforce the run-scoping,
private-port, CA-trust, log-rotation and readiness invariants.
"""
import unittest
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover - CI installs PyYAML; local dev may not
    yaml = None

from ridge.compose_render import ComposeError, RunProfile, audit, names, render_env, slug

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ROOT / 'deployment/expanded'
FILES = ['compose.central.yaml', 'compose.integration.yaml', 'compose.guacamole.yaml', 'wazuh/compose.wazuh.yaml']


def profile(event='ridge-oct26'):
    return RunProfile(event=event, release='v1.0.0',
                      state_dir='/private/state', release_vault='/private/vault',
                      evidence_public='/private/evidence', ca_file='/private/certs/root-ca.pem')


@unittest.skipUnless(yaml is not None, 'PyYAML not installed')
class ComposeAuditTests(unittest.TestCase):
    def test_all_compose_files_pass_audit(self):
        for name in FILES:
            document = yaml.safe_load((COMPOSE / name).read_text(encoding='utf-8'))
            self.assertEqual(audit(document, name), [], name)

    def test_top_level_names_are_run_scoped(self):
        for name in FILES:
            document = yaml.safe_load((COMPOSE / name).read_text(encoding='utf-8'))
            self.assertTrue(str(document['name']).startswith('${RIDGE_PROJECT'), name)

    def test_integration_mounts_ca_and_trusts_it(self):
        document = yaml.safe_load((COMPOSE / 'compose.integration.yaml').read_text(encoding='utf-8'))
        service = document['services']['integration']
        mounts = ' '.join(str(v) for v in service['volumes'])
        self.assertIn('WAZUH_CA_FILE', mounts)
        self.assertIn('silent-ridge-ca.pem', service['environment']['SSL_CERT_FILE'])

    def test_database_readiness_gates_dependents(self):
        central = yaml.safe_load((COMPOSE / 'compose.central.yaml').read_text(encoding='utf-8'))
        self.assertEqual(central['services']['iris']['depends_on']['iris-db']['condition'], 'service_healthy')
        self.assertEqual(central['services']['ctfd']['depends_on']['ctfd-db']['condition'], 'service_healthy')
        self.assertIn('healthcheck', central['services']['iris-db'])
        guac = yaml.safe_load((COMPOSE / 'compose.guacamole.yaml').read_text(encoding='utf-8'))
        self.assertEqual(guac['services']['guacamole']['depends_on']['database']['condition'], 'service_healthy')

    def test_audit_flags_private_port_and_missing_logging(self):
        bad = {'name': '${RIDGE_PROJECT}-x', 'services': {
            'leaky': {'ports': ['0.0.0.0:8091:8091'], 'privileged': True}}}
        problems = audit(bad, 'bad.yaml')
        self.assertTrue(any('private port 8091' in p for p in problems))
        self.assertTrue(any('privileged' in p for p in problems))
        self.assertTrue(any('log rotation' in p for p in problems))

    def test_compose_files_contain_no_literal_secret_values(self):
        for name in FILES:
            text = (COMPOSE / name).read_text(encoding='utf-8')
            self.assertNotRegex(text, r'(?i)password\s*[:=]\s*[A-Za-z0-9+/]{20,}')
            self.assertNotRegex(text, r'(?i)secret_key\s*[:=]\s*[A-Za-z0-9+/]{20,}')


class RenderTests(unittest.TestCase):
    def test_render_env_is_run_scoped_without_secret_values(self):
        env = render_env(profile())
        self.assertEqual(env['RIDGE_PROJECT'], 'ridge-oct26')
        self.assertEqual(env['RIDGE_CENTRAL_NETWORK'], 'ridge-oct26-central')
        self.assertEqual(env['RIDGE_DESKTOP_NETWORK'], 'ridge-oct26-desktop')
        self.assertEqual(env['BIND_IP'], '127.0.0.1')
        for key, value in env.items():
            self.assertNotIn('PASSWORD', key.upper())
            self.assertNotIn('SECRET', key.upper())

    def test_two_events_get_disjoint_namespaces(self):
        first, second = names(profile('ridge-oct26')), names(profile('ridge-oct27'))
        self.assertNotEqual(first['project'], second['project'])
        self.assertFalse(set(first['volumes'].values()) & set(second['volumes'].values()))
        self.assertNotEqual(first['central_network'], second['central_network'])

    def test_slug_rejects_unsafe_names(self):
        for bad in ('', '   ', 'a' * 41, '9event'):
            with self.assertRaises(ComposeError):
                slug(bad)
        self.assertEqual(slug('  Ridge-Oct26  '), 'ridge-oct26')
        self.assertEqual(slug('Ridge Oct26!'), 'ridge-oct26')

    def test_render_rejects_public_bind_and_missing_private_paths(self):
        with self.assertRaisesRegex(ComposeError, 'bind_ip'):
            render_env(RunProfile(event='ridge-oct26', release='v1', bind_ip='0.0.0.0',
                                  state_dir='/s', release_vault='/v', evidence_public='/e', ca_file='/c'))
        with self.assertRaisesRegex(ComposeError, 'ca_file'):
            render_env(RunProfile(event='ridge-oct26', release='v1',
                                  state_dir='/s', release_vault='/v', evidence_public='/e'))


if __name__ == '__main__':
    unittest.main()
