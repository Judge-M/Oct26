import importlib.util
import unittest
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ROOT / 'deployment/expanded/compose.desktops.yaml'
GUACAMOLE = ROOT / 'deployment/expanded/guacamole.py'
TEAMS = ['team%02d' % number for number in range(1, 11)]


@unittest.skipIf(yaml is None, 'PyYAML is not installed')
class ComposeDesktopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = yaml.safe_load(COMPOSE.read_text(encoding='utf-8'))
        cls.services = cls.document['services']

    def test_project_name_scopes_the_run(self):
        self.assertEqual(self.document['name'], 'silent-ridge-desktops')

    def test_ten_team_services_share_the_anchor(self):
        self.assertEqual(set(self.services), {'desktop-' + team for team in TEAMS})
        self.assertIn('x-desktop', self.document)

    def test_common_service_contract(self):
        for team in TEAMS:
            service = self.services['desktop-' + team]
            self.assertEqual(service['image'], '${RIDGE_DESKTOP_IMAGE:-silent-ridge-desktop:dev}')
            self.assertEqual(service['pull_policy'], 'never')
            self.assertEqual(service['shm_size'], '2g')
            self.assertEqual(service['restart'], 'unless-stopped')
            self.assertEqual(service['networks'], ['desktop'])
            limits = service['deploy']['resources']['limits']
            self.assertIn('RIDGE_DESKTOP_CPUS', str(limits['cpus']))
            self.assertIn('RIDGE_DESKTOP_MEMORY', str(limits['memory']))
            self.assertNotIn('ports', service)

    def test_healthcheck_probes_the_vnc_port(self):
        for team in TEAMS:
            healthcheck = self.services['desktop-' + team]['healthcheck']
            self.assertIn('5901', ' '.join(str(part) for part in healthcheck['test']))

    def test_evidence_and_originals_are_read_only(self):
        for team in TEAMS:
            volumes = self.services['desktop-' + team]['volumes']
            self.assertTrue(any(entry.startswith('${RIDGE_EVIDENCE_DIR:?') and entry.endswith(':/evidence:ro')
                                for entry in volumes), volumes)
            self.assertTrue(any(entry.startswith('${RIDGE_ORIGINALS_DIR:?') and entry.endswith(':/originals:ro')
                                for entry in volumes), volumes)

    def test_per_team_volumes_are_declared_and_unique(self):
        declared = self.document['volumes']
        for team in TEAMS:
            volumes = self.services['desktop-' + team]['volumes']
            for folder in ('Cases', 'Workspace', 'Scratch'):
                name = '%s-%s' % (team, folder.lower())
                self.assertIn('%s:/home/participant/%s' % (name, folder), volumes)
                self.assertIn(name, declared)
        self.assertEqual(len(declared), len(set(declared)))
        self.assertEqual(len(declared), 30)

    def test_vnc_password_secret_per_team(self):
        secrets = self.document['secrets']
        for team in TEAMS:
            entries = self.services['desktop-' + team]['secrets']
            self.assertEqual(entries, [{'source': 'vnc_password_' + team, 'target': 'vnc_password'}])
            self.assertTrue(secrets['vnc_password_' + team]['file'].endswith('/' + team))

    def test_external_desktop_network_matches_guacamole(self):
        network = self.document['networks']['desktop']
        self.assertTrue(network['external'])
        self.assertIn('RIDGE_DESKTOP_NETWORK', network['name'])


def _guacamole():
    spec = importlib.util.spec_from_file_location('guacamole_desktops', GUACAMOLE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class GuacamoleContainerAddressTests(unittest.TestCase):
    def test_container_address_helper(self):
        module = _guacamole()
        self.assertEqual(module.container_address('team-01'), 'desktop-team01')
        self.assertEqual(module.container_address('desktop-10'), 'desktop-team10')
        self.assertTrue(module.is_container_address('desktop-team07'))
        self.assertFalse(module.is_container_address('192.0.2.11'))
        with self.assertRaises(ValueError):
            module.container_address('desktop')

    def test_generate_accepts_a_container_service_address(self):
        module = _guacamole()
        config = dict(desktops=[dict(id='desktop-01', container=True, shared=True, max_connections=4)],
                      teams=[dict(id='team-01', desktop='desktop-01')])
        credentials = dict(desktops={'desktop-01': {'password': 'vnc-pass'}},
                           teams={'team-01': {'username': 'team-01', 'password': 'a-long-generated-password'}})
        sql = module.generate(config, credentials)
        self.assertIn("'desktop-team01'", sql)
        self.assertIn("'5901'", sql)


if __name__ == '__main__':
    unittest.main()
