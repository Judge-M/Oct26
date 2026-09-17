"""Deterministic tests for idempotent Guacamole provisioning (C02).

No Guacamole/PostgreSQL is available (LIVE ACCEPTANCE BLOCKED). These tests
inspect the generated SQL for reconciliation and isolation properties.
"""
import importlib.util
import re
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / 'deployment/expanded/guacamole.py'
spec = importlib.util.spec_from_file_location('guac_reconcile', MODULE_PATH)
guac = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guac)


def config(shared=False):
    return dict(
        desktops=[dict(id='desk-a', address='192.0.2.11', shared=shared, max_connections=3),
                  dict(id='desk-b', address='192.0.2.12', shared=shared, max_connections=3)],
        teams=[dict(id='team-a', desktop='desk-a'), dict(id='team-b', desktop='desk-b')])


def credentials():
    return dict(
        desktops={'desk-a': {'password': 'vnc-a'}, 'desk-b': {'password': 'vnc-b'}},
        teams={'team-a': {'username': 'team-a-user', 'password': 'a-long-generated-password'},
               'team-b': {'username': 'team-b-user', 'password': 'b-long-generated-password'}})


class GuacamoleReconcileTests(unittest.TestCase):
    def test_connections_use_upsert_and_default_admin_is_disabled(self):
        sql = guac.reconcile(config(), credentials())
        self.assertIn('LOCK TABLE guacamole_connection', sql)
        self.assertIn('WHERE NOT EXISTS', sql)
        self.assertIn('ON CONFLICT (entity_id) DO NOTHING', sql)
        self.assertIn("name='guacadmin'", sql)
        self.assertIn('disabled=TRUE', sql)

    def test_each_team_only_reaches_its_own_desktop(self):
        sql = guac.reconcile(config(), credentials())
        blocks = [line for line in sql.splitlines() if 'guacamole_connection_permission' in line]
        self.assertEqual(len(blocks), 2)
        team_a = next(line for line in blocks if "'team-a-user'" in line)
        team_b = next(line for line in blocks if "'team-b-user'" in line)
        self.assertIn("connection_name='desk-a'", team_a)
        self.assertNotIn("connection_name='desk-b'", team_a)
        self.assertIn("connection_name='desk-b'", team_b)
        self.assertNotIn("connection_name='desk-a'", team_b)

    def test_repeated_reconcile_is_byte_identical(self):
        self.assertEqual(guac.reconcile(config(), credentials()), guac.reconcile(config(), credentials()))

    def test_shared_and_exclusive_connection_limits(self):
        exclusive = guac.reconcile(config(shared=False), credentials())
        self.assertIn("'vnc',1,1", exclusive)
        shared = guac.reconcile(config(shared=True), credentials())
        self.assertIn("'vnc',3,3", shared)

    def test_login_password_is_hashed_never_plaintext(self):
        sql = guac.reconcile(config(), credentials())
        self.assertNotIn('a-long-generated-password', sql)
        self.assertIn('password_hash', sql)

    def test_vnc_passwords_are_required(self):
        bad = credentials()
        bad['desktops']['desk-a']['password'] = ''
        with self.assertRaisesRegex(ValueError, 'VNC password'):
            guac.reconcile(config(), bad)

    def test_unmapped_desktop_and_weak_login_rejected(self):
        bad = config()
        bad['teams'][0]['desktop'] = 'desk-z'
        with self.assertRaisesRegex(ValueError, 'Team desktop missing'):
            guac.reconcile(bad, credentials())
        weak = credentials()
        weak['teams']['team-a']['password'] = 'short'
        with self.assertRaisesRegex(ValueError, 'strong generated passwords'):
            guac.reconcile(config(), weak)


if __name__ == '__main__':
    unittest.main()
