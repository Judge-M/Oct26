"""Deterministic tests for the IRIS bootstrap planner (B01).

These run without IRIS or SQLAlchemy. The ORM adapter in
integrations/iris_bootstrap.py requires live IRIS 2.4.20 (BLOCKED here).
"""
import importlib.util
import sys
import types
import unittest
from pathlib import Path

from ridge.iris_bootstrap import (
    BootstrapError, BootstrapSpec, IdentitySpec, bootstrap, post_finding, post_task, preflight,
    resolve_statuses,
)

try:
    import click  # noqa: F401
except ModuleNotFoundError:
    click = types.ModuleType('click')
    click.ClickException = type('ClickException', (RuntimeError,), {})
    sys.modules['click'] = click

ADAPTER_PATH = Path(__file__).resolve().parents[1] / 'integrations/iris_bootstrap.py'
adapter_spec = importlib.util.spec_from_file_location('iris_registration_adapter', ADAPTER_PATH)
iris_adapter = importlib.util.module_from_spec(adapter_spec)
adapter_spec.loader.exec_module(iris_adapter)


class FakeAdmin:
    def __init__(self):
        self.version = 'iris-2.4.20'
        self.statuses = [{'id': 11, 'name': 'Open'}, {'id': 22, 'name': 'Closed'}]
        self.cases = {}
        self.users = {}
        self.access = {}
        self.tasks = {}
        self.findings = {}
        self.created = {'case': 0, 'user': 0}
        self._next = 100

    def schema_version(self):
        return self.version

    def ensure_receipt_table(self):
        self.receipt_table = True

    def list_task_statuses(self):
        return list(self.statuses)

    def find_case(self, name):
        if name in self.cases:
            return {'id': self.cases[name], 'name': name}
        return None

    def create_case(self, name, description):
        self.created['case'] += 1
        self._next += 1
        self.cases[name] = self._next
        return {'id': self._next, 'name': name}

    def find_user(self, login):
        if login in self.users:
            return {'id': self.users[login]['id'], 'user': login}
        return None

    def create_user(self, login, name, password):
        self.created['user'] += 1
        self._next += 1
        self.users[login] = {'id': self._next, 'user': login, 'name': name,
                             'password': password, 'active': True}
        return {'id': self._next, 'user': login}

    def user_password_valid(self, user_id, password):
        return any(row['id'] == user_id and row['password'] == password
                   for row in self.users.values())

    def set_user_password(self, user_id, password):
        for row in self.users.values():
            if row['id'] == user_id:
                row['password'] = password
                return
        raise ValueError('User does not exist')

    def set_case_access(self, user_id, case_id, level):
        self.access[(user_id, case_id)] = level

    def case_access(self, user_id, case_id):
        return self.access.get((user_id, case_id))

    def user_active(self, user_id):
        return any(u['id'] == user_id and u['active'] for u in self.users.values())

    def create_task(self, case_id, ticket, title, open_status_id, service_user_id):
        self.tasks[ticket] = len(self.tasks) + 1
        return self.tasks[ticket]

    def create_finding(self, case_id, iris_id, service_user_id, finding):
        self.findings[iris_id] = finding
        return len(self.findings)


def spec():
    return BootstrapSpec(
        case_name='Silent Ridge Oct26', case_description='Fictional exercise',
        service_login='svc-ridge', service_name='Silent Ridge Service', service_password='s' * 40,
        open_status='Open', closed_status='Closed',
        identities=(IdentitySpec('team-01', 'iris-team-01', 'Team 01', 'p' * 40),
                    IdentitySpec('team-02', 'iris-team-02', 'Team 02', 'q' * 40)))


class BootstrapTests(unittest.TestCase):
    def test_dynamic_registration_updates_stale_iris_password(self):
        admin = FakeAdmin()
        user = admin.create_user('iris-returning', 'Returning Team', 'stale-password')

        reconciled = iris_adapter._find_or_create_user_for_registration(
            admin, 'iris-returning', 'Returning Team', 'new-generated-password')

        self.assertEqual(reconciled['id'], user['id'])
        self.assertTrue(admin.user_password_valid(user['id'], 'new-generated-password'))

    def test_dynamic_registration_fails_closed_without_leaking_password(self):
        admin = FakeAdmin()
        admin.create_user('iris-returning', 'Returning Team', 'stale-password')
        admin.set_user_password = lambda _user_id, _password: None
        with self.assertRaisesRegex(iris_adapter.click.ClickException,
                                    'IRIS participant credential verification failed') as caught:
            iris_adapter._find_or_create_user_for_registration(
                admin, 'iris-returning', 'Returning Team', 'private-generated-password')
        self.assertNotIn('private-generated-password', str(caught.exception))

    def test_bootstrap_is_idempotent_and_returns_inventory(self):
        admin = FakeAdmin()
        first = bootstrap(admin, spec())
        second = bootstrap(admin, spec())
        self.assertEqual(first, second)
        self.assertEqual(admin.created, {'case': 1, 'user': 3})
        self.assertEqual(len(admin.cases), 1)
        self.assertEqual(len(admin.users), 3)
        self.assertEqual(first['statuses'], {'open': 11, 'closed': 22})
        self.assertEqual(first['identities']['team-01']['login'], 'iris-team-01')
        self.assertTrue(admin.receipt_table)

    def test_existing_password_is_never_rotated(self):
        admin = FakeAdmin()
        bootstrap(admin, spec())
        before = admin.users['iris-team-01']['password']
        changed = BootstrapSpec(**{**spec().__dict__,
                                   'identities': (IdentitySpec('team-01', 'iris-team-01', 'Team 01', 'z' * 40),)})
        bootstrap(admin, changed)
        self.assertEqual(admin.users['iris-team-01']['password'], before)

    def test_team_access_is_read_only_and_preflight_ready(self):
        admin = FakeAdmin()
        inventory = bootstrap(admin, spec())
        ready = preflight(admin, spec(), inventory)
        self.assertTrue(ready['ready'])
        self.assertEqual(admin.access[(inventory['identities']['team-01']['id'], inventory['case']['id'])], 'read_only')
        admin.access[(inventory['identities']['team-02']['id'], inventory['case']['id'])] = 'manage'
        with self.assertRaisesRegex(BootstrapError, 'read-only'):
            preflight(admin, spec(), inventory)

    def test_status_resolution_requires_exact_live_names(self):
        admin = FakeAdmin()
        with self.assertRaisesRegex(BootstrapError, 'open_status'):
            resolve_statuses(admin.statuses, BootstrapSpec(**{**spec().__dict__, 'open_status': 'Active'}))
        ambiguous = [{'id': 1, 'name': 'Open'}, {'id': 2, 'name': 'open'}]
        with self.assertRaisesRegex(BootstrapError, 'exactly one'):
            resolve_statuses(ambiguous, BootstrapSpec(**{**spec().__dict__, 'closed_status': 'open'}))
        same = [{'id': 5, 'name': 'Open'}]
        with self.assertRaisesRegex(BootstrapError, 'distinct'):
            resolve_statuses(same, BootstrapSpec(**{**spec().__dict__, 'closed_status': 'Open'}))

    def test_schema_mismatch_fails_before_writing(self):
        admin = FakeAdmin()
        admin.version = 'iris-2.5.0'
        with self.assertRaisesRegex(BootstrapError, 'schema'):
            bootstrap(admin, spec())
        self.assertEqual(admin.created, {'case': 0, 'user': 0})

    def test_missing_fields_and_empty_roster_rejected(self):
        admin = FakeAdmin()
        with self.assertRaisesRegex(BootstrapError, 'case_name'):
            bootstrap(admin, BootstrapSpec(**{**spec().__dict__, 'case_name': ''}))
        with self.assertRaisesRegex(BootstrapError, 'At least one identity'):
            bootstrap(admin, BootstrapSpec(**{**spec().__dict__, 'identities': ()}))
        with self.assertRaisesRegex(BootstrapError, 'Duplicate team'):
            bootstrap(admin, BootstrapSpec(**{**spec().__dict__,
                                              'identities': (IdentitySpec('t', 'a', 'A', 'x' * 40),
                                                             IdentitySpec('t', 'b', 'B', 'y' * 40))}))

    def test_task_and_finding_posted_through_adapter_contract(self):
        admin = FakeAdmin()
        inventory = bootstrap(admin, spec())
        iris_id = post_task(admin, spec(), inventory, 'T01', 'Trace document traffic')
        post_finding(admin, spec(), inventory, iris_id,
                     {'text': 'WS-17 is the workstation.', 'evidence': ['network/sensor.pcap'], 'limitation': 'replay'})
        self.assertEqual(admin.tasks['T01'], iris_id)
        self.assertIn(iris_id, admin.findings)
        with self.assertRaisesRegex(BootstrapError, 'Finding requires'):
            post_finding(admin, spec(), inventory, iris_id, {'text': 'x', 'evidence': []})


if __name__ == '__main__':
    unittest.main()
