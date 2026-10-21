"""Deterministic tests for the CTFd provisioning planner (B02).

These run without CTFd or SQLAlchemy. The ORM adapter in
integrations/ctfd_silent_ridge/provision.py requires live CTFd 3.7.7 (BLOCKED).
"""
import importlib.util
import sys
import types
import unittest
from dataclasses import replace
from pathlib import Path

from ridge.ctfd_provision import (
    FacilitatorSpec, ProvisionError, ProvisionSpec, TeamSpec, UserSpec, preflight, provision,
)

try:
    import click  # noqa: F401
except ModuleNotFoundError:
    click = types.ModuleType('click')
    click.ClickException = type('ClickException', (RuntimeError,), {})
    sys.modules['click'] = click

ADAPTER_PATH = Path(__file__).resolve().parents[1] / 'integrations/ctfd_silent_ridge/provision.py'
adapter_spec = importlib.util.spec_from_file_location('ctfd_registration_adapter', ADAPTER_PATH)
ctfd_adapter = importlib.util.module_from_spec(adapter_spec)
adapter_spec.loader.exec_module(ctfd_adapter)


class FakeAdmin:
    def __init__(self):
        self.config = {}
        self.teams = {}
        self.users = {}
        self.awards = 0
        self.created = {'team': 0, 'user': 0}
        self._next = 0

    def get_config(self, key, default=None):
        return self.config.get(key, default)

    def set_config(self, key, value):
        self.config[key] = value

    def find_team(self, name):
        row = self.teams.get(name)
        return None if row is None else dict(row)

    def create_team(self, name, password):
        self.created['team'] += 1
        self._next += 1
        self.teams[name] = {'id': self._next, 'name': name, 'banned': False, 'hidden': False,
                            'password': password}
        return dict(self.teams[name])

    def team_password_valid(self, team_id, password):
        return any(row['id'] == team_id and row['password'] == password
                   for row in self.teams.values())

    def set_team_password(self, team_id, password):
        for row in self.teams.values():
            if row['id'] == team_id:
                row['password'] = password
                return
        raise ValueError('Team does not exist')

    def find_user(self, name):
        row = self.users.get(name)
        return None if row is None else {'id': row['id'], 'name': row['name']}

    def create_user(self, name, email, password):
        self.created['user'] += 1
        self._next += 1
        self.users[name] = {'id': self._next, 'name': name, 'email': email,
                            'password': password, 'team_id': None}
        return {'id': self._next, 'name': name}

    def user_password_valid(self, user_id, password):
        return any(row['id'] == user_id and row['password'] == password
                   for row in self.users.values())

    def set_user_password(self, user_id, password):
        for row in self.users.values():
            if row['id'] == user_id:
                row['password'] = password
                return
        raise ValueError('User does not exist')

    def create_admin(self, name, email, password):
        row = self.create_user(name, email, password)
        self.users[name]['type'] = 'admin'
        return row

    def admin_login_valid(self, name, password):
        row = self.users.get(name)
        return bool(row and row.get('type') == 'admin' and row['team_id'] is None
                    and row['password'] == password)

    def set_user_team(self, user_id, team_id):
        for row in self.users.values():
            if row['id'] == user_id:
                row['team_id'] = team_id

    def user_team(self, user_id):
        for row in self.users.values():
            if row['id'] == user_id:
                return row['team_id']
        return None

    def count_awards(self):
        return self.awards


def spec():
    return ProvisionSpec(
        teams=(TeamSpec('team-01', 'Team 01', 't' * 40), TeamSpec('team-02', 'Team 02', 'u' * 40)),
        users=(UserSpec('team01-a', 'a@example.test', 'team-01', 'p' * 40),
               UserSpec('team01-b', 'b@example.test', 'team-01', 'q' * 40),
               UserSpec('team01-c', 'c@example.test', 'team-01', 'r' * 40),
               UserSpec('team02-a', 'd@example.test', 'team-02', 's' * 40)))


class CtfdProvisionTests(unittest.TestCase):
    def test_dynamic_registration_updates_stale_team_and_user_passwords(self):
        admin = FakeAdmin()
        team = admin.create_team('Returning Team', 'stale-team-password')
        user = admin.create_user('returning-seat', 'seat@example.test', 'stale-user-password')
        admin.set_user_team(user['id'], team['id'])

        reconciled_team = ctfd_adapter._find_or_create_team_for_registration(
            admin, 'Returning Team', 'new-team-password')
        reconciled_user = ctfd_adapter._find_or_create_user_for_registration(
            admin, {'username': 'returning-seat', 'password': 'new-user-password'},
            team['id'])

        self.assertEqual(reconciled_team['id'], team['id'])
        self.assertEqual(reconciled_user['id'], user['id'])
        self.assertTrue(admin.team_password_valid(team['id'], 'new-team-password'))
        self.assertTrue(admin.user_password_valid(user['id'], 'new-user-password'))

    def test_dynamic_registration_fails_closed_when_password_cannot_converge(self):
        admin = FakeAdmin()
        team = admin.create_team('Returning Team', 'stale-team-password')
        admin.set_team_password = lambda _team_id, _password: None
        with self.assertRaisesRegex(ctfd_adapter.click.ClickException,
                                    'CTFd team credential verification failed') as caught:
            ctfd_adapter._find_or_create_team_for_registration(
                admin, 'Returning Team', 'private-generated-password')
        self.assertNotIn('private-generated-password', str(caught.exception))

    def test_facilitator_admin_is_idempotent_and_authenticates(self):
        admin = FakeAdmin()
        desired = replace(spec(), facilitator=FacilitatorSpec(
            'ridge-facilitator', 'facilitator@example.test', 'a' * 40))
        first = provision(admin, desired)
        self.assertTrue(preflight(admin, desired, first)['ready'])
        self.assertEqual(first, provision(admin, desired))
        self.assertEqual(admin.users['ridge-facilitator']['type'], 'admin')
        self.assertIsNone(admin.users['ridge-facilitator']['team_id'])
        with self.assertRaisesRegex(ProvisionError, 'authenticating admin'):
            provision(admin, replace(desired, facilitator=FacilitatorSpec(
                'ridge-facilitator', 'facilitator@example.test', 'b' * 40)))

    def test_provision_is_idempotent_and_returns_inventory(self):
        admin = FakeAdmin()
        first = provision(admin, spec())
        second = provision(admin, spec())
        self.assertEqual(first, second)
        self.assertEqual(admin.created, {'team': 2, 'user': 4})
        self.assertEqual(admin.config['user_mode'], 'teams')
        self.assertFalse(admin.config['registration_visible'])
        self.assertEqual(admin.config['score_visibility'], 'private')
        self.assertEqual(admin.config['account_visibility'], 'private')
        self.assertEqual(len(first['teams']), 2)
        self.assertEqual(len(first['users']), 4)
        self.assertEqual(admin.users['team01-a']['team_id'], first['teams']['team-01']['id'])

    def test_existing_awards_and_passwords_are_preserved(self):
        admin = FakeAdmin()
        provision(admin, spec())
        admin.awards = 7
        before = admin.users['team01-a']['password']
        changed = replace(spec(), teams=(TeamSpec('team-01', 'Team 01', 'z' * 40),),
                          users=(UserSpec('team01-a', 'a@example.test', 'team-01', 'y' * 40),))
        provision(admin, changed)
        self.assertEqual(admin.awards, 7)
        self.assertEqual(admin.users['team01-a']['password'], before)

    def test_preflight_ready_and_detects_banned_or_reassigned(self):
        admin = FakeAdmin()
        inventory = provision(admin, spec())
        self.assertTrue(preflight(admin, spec(), inventory)['ready'])
        admin.teams['Team 02']['banned'] = True
        with self.assertRaisesRegex(ProvisionError, 'banned or hidden'):
            preflight(admin, spec(), inventory)
        admin.teams['Team 02']['banned'] = False
        admin.users['team02-a']['team_id'] = inventory['teams']['team-01']['id']
        with self.assertRaisesRegex(ProvisionError, 'membership changed'):
            preflight(admin, spec(), inventory)

    def test_duplicate_and_unmapped_roster_rejected(self):
        admin = FakeAdmin()
        with self.assertRaisesRegex(ProvisionError, 'duplicate team'):
            provision(admin, replace(spec(), teams=(TeamSpec('team-01', 'Team 01', 'x' * 40),
                                                    TeamSpec('team-01', 'Other', 'y' * 40))))
        with self.assertRaisesRegex(ProvisionError, 'duplicate user'):
            provision(admin, replace(spec(), users=(UserSpec('dup', 'a@example.test', 'team-01', 'x' * 40),
                                                    UserSpec('dup', 'b@example.test', 'team-01', 'y' * 40))))
        with self.assertRaisesRegex(ProvisionError, 'unmapped team'):
            provision(admin, replace(spec(), users=(UserSpec('solo', 'a@example.test', 'team-99', 'x' * 40),)))

    def test_user_already_in_another_team_rejected(self):
        admin = FakeAdmin()
        inventory = provision(admin, spec())
        admin.users['team01-a']['team_id'] = inventory['teams']['team-02']['id']
        with self.assertRaisesRegex(ProvisionError, 'already belongs to another team'):
            provision(admin, spec())

    def test_preflight_returns_one_shared_identity_per_team(self):
        admin = FakeAdmin()
        inventory = provision(admin, spec())
        ready = preflight(admin, spec(), inventory)
        self.assertEqual(len(ready['identities']), 2)
        self.assertEqual({row['name'] for row in ready['identities']}, {'Team 01', 'Team 02'})

    def test_preflight_rejects_hidden_scoreboard(self):
        admin = FakeAdmin()
        inventory = provision(admin, spec())
        admin.config['score_visibility'] = None
        with self.assertRaisesRegex(ProvisionError, 'score_visibility'):
            preflight(admin, spec(), inventory)


if __name__ == '__main__':
    unittest.main()
