import json
import tempfile
import unittest
from pathlib import Path

from ridge.registration import (RegistrationCapacity, RegistrationConfig,
                                RegistrationError, RegistrationStore,
                                desktop_handout)


class RegistrationStoreTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[1] / 'work' / 'test-registration'
        root.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=root)
        self.path = str(Path(self.temp.name) / 'registration.sqlite')

    def tearDown(self):
        self.temp.cleanup()

    def test_team_limit_is_positive_but_not_arbitrarily_capped_at_ten(self):
        RegistrationConfig(max_teams=11).validate()
        for bad in (0, -1, True, '11'):
            with self.subTest(max_teams=bad):
                with self.assertRaisesRegex(RegistrationError, 'positive integer'):
                    RegistrationConfig(max_teams=bad).validate()

    def test_registration_reserves_three_roles_and_retrieval_is_persistent(self):
        store = RegistrationStore(self.path, RegistrationConfig(max_teams=2))
        created = store.register('Blue Lanterns', 'Alex Morgan')
        self.assertEqual(created['status'], 'pending')
        self.assertNotIn('credentials', created)
        pending = store.get(created['access_code'])
        self.assertEqual(pending['slots'], ['desktop-slot01', 'desktop-slot02', 'desktop-slot03'])
        self.assertEqual(pending['status'], 'pending')
        private = store.get(created['access_code'], include_private=True)
        self.assertEqual(len(private['credentials']['ctfd']['members']), 5)
        self.assertEqual(store.capacity()['available'], 1)

    def test_claim_complete_requires_current_worker_lease_and_marks_slots_running(self):
        store = RegistrationStore(self.path, RegistrationConfig(max_teams=1))
        created = store.register('Blue Lanterns', 'Alex Morgan')
        claimed = store.claim_pending()
        self.assertEqual(claimed['id'], created['id'])
        self.assertEqual(claimed['status'], 'provisioning')
        handout = {'desktop_urls': [
            {'slot': slot, 'url': 'https://event/guacamole/#/' + slot}
            for slot in claimed['slots']
        ]}
        store.complete(created['id'], handout, claimed['worker_token'])
        visible = store.get(created['access_code'])
        self.assertEqual(visible['status'], 'ready')
        self.assertEqual(visible['result'], handout)
        self.assertIsNone(store.claim_pending())

    def test_capacity_and_duplicate_names_are_safe(self):
        store = RegistrationStore(self.path, RegistrationConfig(max_teams=1))
        store.register('Blue Lanterns', 'Alex Morgan')
        with self.assertRaises(RegistrationError):
            store.register('Blue Lanterns', 'Someone Else')
        with self.assertRaises(RegistrationCapacity):
            store.register('Red Comets', 'Jamie Lee')

    def test_pending_cancellation_releases_its_desktops(self):
        store = RegistrationStore(self.path, RegistrationConfig(max_teams=1))
        created = store.register('Blue Lanterns', 'Alex Morgan')
        store.cancel(created['id'], 'captain registered the wrong team')
        self.assertEqual(store.capacity()['available'], 1)
        again = store.register('Red Comets', 'Jamie Lee')
        self.assertEqual(again['slots'], created['slots'])

    def test_cancellation_refuses_provisioning_and_ready_registrations(self):
        store = RegistrationStore(self.path, RegistrationConfig(max_teams=1))
        created = store.register('Blue Lanterns', 'Alex Morgan')
        claimed = store.claim_pending()
        with self.assertRaisesRegex(RegistrationError, 'provisioning is in progress'):
            store.cancel(created['id'])
        self.assertEqual(store.capacity()['available'], 0)

        handout = {'desktop_urls': [{'slot': slot, 'url': 'https://event/' + slot}
                                    for slot in claimed['slots']]}
        store.complete(created['id'], handout, claimed['worker_token'])
        with self.assertRaisesRegex(RegistrationError, 'host-side deprovisioning'):
            store.cancel(created['id'])
        self.assertEqual(store.capacity()['available'], 0)
        with store._connect() as con:
            slots = con.execute(
                'SELECT status,registration_id FROM desktop_slots ORDER BY slot').fetchall()
        self.assertTrue(all(row['status'] == 'running' for row in slots))
        self.assertTrue(all(row['registration_id'] == created['id'] for row in slots))

    def test_requeue_never_resurrects_cancelled_registration(self):
        store = RegistrationStore(self.path, RegistrationConfig(max_teams=1))
        created = store.register('Blue Lanterns', 'Alex Morgan')
        store.cancel(created['id'])
        self.assertFalse(store.requeue(created['id'], 'late worker failure', 'stale-token'))
        self.assertEqual(store.get(created['access_code'])['status'], 'cancelled')

    def test_needs_operator_cancellation_requires_host_cleanup(self):
        store = RegistrationStore(self.path, RegistrationConfig(max_teams=1))
        created = store.register('Blue Lanterns', 'Alex Morgan')
        with store._connect() as con:
            con.execute('UPDATE registrations SET attempt_count=? WHERE id=?',
                        (store.MAX_ATTEMPTS - 1, created['id']))
        claimed = store.claim_pending()
        store.requeue(created['id'], 'partial provisioning failure',
                      claimed['worker_token'])
        self.assertEqual(store.get(created['access_code'])['status'], 'needs_operator')
        with self.assertRaisesRegex(RegistrationError, 'host-side cleanup'):
            store.cancel(created['id'])
        self.assertEqual(store.capacity()['available'], 0)

    def test_stale_worker_cannot_complete_or_requeue_a_reclaimed_lease(self):
        store = RegistrationStore(self.path, RegistrationConfig(max_teams=1))
        created = store.register('Blue Lanterns', 'Alex Morgan')
        first = store.claim_pending()
        with store._connect() as con:
            con.execute('UPDATE registrations SET lease_until=1 WHERE id=?', (created['id'],))
        second = store.claim_pending()
        self.assertNotEqual(first['worker_token'], second['worker_token'])
        with self.assertRaisesRegex(RegistrationError, 'lease is no longer active'):
            store.activate_credentials(created['id'], first['worker_token'])
        store.activate_credentials(created['id'], second['worker_token'])
        handout = {'desktop_urls': [{'slot': slot, 'url': 'https://event/' + slot}
                                    for slot in second['slots']]}
        with self.assertRaisesRegex(RegistrationError, 'lease is no longer active'):
            store.complete(created['id'], handout, first['worker_token'])
        with self.assertRaisesRegex(RegistrationError, 'lease is no longer active'):
            store.requeue(created['id'], 'stale worker failure', first['worker_token'])
        self.assertEqual(store.get(created['access_code'])['status'], 'provisioning')
        store.complete(created['id'], handout, second['worker_token'])
        self.assertEqual(store.get(created['access_code'])['status'], 'ready')

    def test_production_registration_uses_enrollment_code_as_its_only_gate(self):
        store = RegistrationStore(self.path, RegistrationConfig(max_teams=1),
                                  enrollment_code='LANTERN-42')
        with self.assertRaisesRegex(RegistrationError, 'invalid'):
            store.register('Blue Lanterns', 'Alex Morgan', enrollment_code='wrong')
        created = store.register('Blue Lanterns', 'Alex Morgan',
                                 enrollment_code='LANTERN-42')
        self.assertEqual(created['status'], 'pending')

    def test_existing_runtime_can_adopt_the_static_enrollment_code(self):
        original = RegistrationStore(self.path, RegistrationConfig(max_teams=1),
                                     enrollment_code='OLD-RANDOM-CODE')
        with original._connect() as con:
            con.execute("INSERT INTO registration_meta(key,value) VALUES ('open','0')")
        migrated = RegistrationStore(self.path, RegistrationConfig(max_teams=1),
                                     enrollment_code='SILENT-RIDGE')
        created = migrated.register('Blue Lanterns', 'Alex Morgan',
                                    enrollment_code='SILENT-RIDGE')
        self.assertEqual(created['status'], 'pending')

    def test_failed_provisioning_stops_for_operator_and_can_be_retried(self):
        store = RegistrationStore(self.path, RegistrationConfig(max_teams=1))
        created = store.register('Blue Lanterns', 'Alex Morgan')
        for attempt in range(store.MAX_ATTEMPTS):
            claimed = store.claim_pending()
            self.assertIsNotNone(claimed)
            store.requeue(created['id'], 'temporary failure %d' % attempt,
                          claimed['worker_token'])
            if attempt < store.MAX_ATTEMPTS - 1:
                with store._connect() as con:
                    con.execute('UPDATE registrations SET retry_at=0 WHERE id=?',
                                (created['id'],))
        self.assertEqual(store.get(created['access_code'])['status'], 'needs_operator')
        store.retry(created['id'])
        self.assertEqual(store.get(created['access_code'])['status'], 'pending')

    def test_rotating_retrieval_link_invalidates_old_link(self):
        store = RegistrationStore(self.path, RegistrationConfig(max_teams=1))
        created = store.register('Blue Lanterns', 'Alex Morgan')
        replacement = store.rotate_access(created['id'])
        with self.assertRaisesRegex(RegistrationError, 'not found'):
            store.get(created['access_code'])
        self.assertEqual(store.get(replacement)['id'], created['id'])

    def test_handout_has_three_distinct_tool_roles(self):
        handout = desktop_handout(['desktop-slot01', 'desktop-slot02', 'desktop-slot03'],
                                  'https://event:8082')
        self.assertEqual([row['role'] for row in handout],
                         ['forensics-a', 'forensics-b', 'analysis'])
        self.assertIn('Wireshark', handout[2]['tools'])
        self.assertIn('Wireshark', handout[0]['tools'])
        self.assertTrue(all(row['guidance'] for row in handout))
        self.assertEqual([row['connection_name'] for row in handout],
                         ['desktop-slot01', 'desktop-slot02', 'desktop-slot03'])

    def test_private_handout_includes_wazuh_route_and_credentials(self):
        source = (Path(__file__).resolve().parents[1] /
                  'integrations/ctfd_silent_ridge/__init__.py').read_text(encoding='utf-8')
        self.assertIn("os.environ['WAZUH_PUBLIC_URL']", source)
        self.assertIn('/app/data-explorer/discover#?', source)
        self.assertNotIn('columns:!(_source)', source)
        self.assertIn("2026-10-15T08:00:00.000Z", source)
        self.assertIn('credentials.wazuh.username', source)
        self.assertIn('credentials.wazuh.password', source)


if __name__ == '__main__':
    unittest.main()
