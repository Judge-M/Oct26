"""A04: deployment journal, event-scoped lock, provider contract and orchestration."""
import json
import sqlite3
import tempfile
import threading
import unittest
from copy import deepcopy
from pathlib import Path

from ridge.deploy import (Deployment, DeploymentError, FakeProvider,
                          FingerprintError, Journal, JournalError, LockError)

ROOT = Path(__file__).resolve().parents[1]
TWO = json.loads((ROOT / 'deployment/profiles/example-two-team.json').read_text(encoding='utf-8'))
PLAN = [
    {'name': 'INFRASTRUCTURE_READY', 'kind': 'network', 'spec': {'cidr': '10.26.10.0/24'}},
    {'name': 'APPLICATIONS_READY', 'kind': 'host', 'spec': {}},
    {'name': 'DESKTOPS_READY', 'kind': 'desktop', 'spec': {}},
]


class JournalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.path = self.root / 'deploy.journal.sqlite'

    def tearDown(self):
        self.tmp.cleanup()

    def make(self):
        return Journal.create(self.path, TWO, 'silent-ridge-expanded-1', 'release-fingerprint-1')

    def test_create_and_open_roundtrip(self):
        journal = self.make()
        self.assertEqual(journal.state, 'NEW')
        self.assertEqual(journal.meta()['event_id'], TWO['event']['id'])
        self.assertEqual([step['state'] for step in journal.steps()], ['pending'] * len(journal.steps()))
        reopened = Journal.open(self.path)
        self.assertEqual(reopened.meta()['deployment_id'], journal.meta()['deployment_id'])

    def test_create_refuses_existing_journal(self):
        self.make()
        with self.assertRaises(JournalError):
            self.make()

    def test_corrupt_and_half_written_journals_fail_closed(self):
        with self.assertRaises(JournalError):
            Journal.open(self.root / 'missing.sqlite')
        empty = self.root / 'empty.sqlite'
        empty.write_bytes(b'')
        with self.assertRaises(JournalError):
            Journal.open(empty)
        garbage = self.root / 'garbage.sqlite'
        garbage.write_bytes(b'this is not a database')
        with self.assertRaises(JournalError):
            Journal.open(garbage)
        self.make()
        con = sqlite3.connect(self.path)
        con.execute('DROP TABLE meta')
        con.commit()
        con.close()
        with self.assertRaises(JournalError):
            Journal.open(self.path)

    def test_two_concurrent_up_attempts_serialize(self):
        provider = FakeProvider(delay=0.1)
        journal = self.make()
        deployment = Deployment(journal, provider)
        results = []

        def run():
            results.append(deployment.up(PLAN, timeout=10))

        threads = [threading.Thread(target=run) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(results, ['PROVISIONED_PAUSED', 'PROVISIONED_PAUSED'])
        self.assertEqual(len(provider.inventory()), len(PLAN))
        self.assertEqual(sum(1 for call in provider.calls if call[0] == 'create'), len(PLAN))

    def test_kill_between_create_and_ack_reconciles_one_resource(self):
        provider = FakeProvider()
        provider.fail_after_create = True
        journal = self.make()
        deployment = Deployment(journal, provider)
        with self.assertRaises(Exception):
            deployment.up(PLAN)
        self.assertEqual(journal.step('INFRASTRUCTURE_READY')['state'], 'failed')
        provider.fail_after_create = False
        self.assertEqual(deployment.up(PLAN), 'PROVISIONED_PAUSED')
        creates = [call for call in provider.calls
                   if call[0] == 'create' and call[2] == 'INFRASTRUCTURE_READY']
        self.assertEqual(len(creates), 1)
        self.assertEqual(len(provider.inventory()), len(PLAN))

    def test_changed_release_or_profile_requires_migration(self):
        journal = self.make()
        self.assertEqual(journal.check_fingerprints(TWO, 'silent-ridge-expanded-1', 'release-fingerprint-1'), [])
        changed = deepcopy(TWO)
        changed['event']['duration_minutes'] = 300
        with self.assertRaises(FingerprintError):
            journal.check_fingerprints(changed, 'silent-ridge-expanded-1', 'release-fingerprint-1')
        with self.assertRaises(FingerprintError):
            journal.check_fingerprints(TWO, 'silent-ridge-expanded-2', 'release-fingerprint-2')
        self.assertIn('profile', journal.check_fingerprints(changed, 'silent-ridge-expanded-1',
                                                            'release-fingerprint-1', migrate=True))
        self.assertEqual(journal.meta()['active_site_generation'], '1')

    def test_fake_receipts_are_not_deployment_acceptance(self):
        provider = FakeProvider()
        provider.fake_receipts = True
        journal = self.make()
        deployment = Deployment(journal, provider)
        with self.assertRaises(DeploymentError):
            deployment.up(PLAN)
        self.assertEqual(journal.step('INFRASTRUCTURE_READY')['state'], 'failed')
        self.assertNotEqual(journal.state, 'PROVISIONED_PAUSED')
        self.assertTrue(all(step['state'] != 'verified' for step in journal.steps()))

    def test_stop_cleans_partial_run(self):
        provider = FakeProvider()
        journal = self.make()
        deployment = Deployment(journal, provider)
        deployment.up(PLAN)
        self.assertEqual(len(provider.inventory()), len(PLAN))
        self.assertEqual(deployment.stop(), 'STOPPED')
        self.assertEqual(provider.inventory(), [])
        self.assertEqual(journal.state, 'STOPPED')

    def test_lock_times_out_while_held_then_becomes_available(self):
        journal = self.make()
        with journal.lock('first', timeout=1):
            with self.assertRaises(LockError):
                with journal.lock('second', timeout=0.2):
                    pass
        with journal.lock('second', timeout=1):
            pass


if __name__ == '__main__':
    unittest.main()
