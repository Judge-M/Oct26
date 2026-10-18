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

    def test_claim_complete_is_idempotent_and_marks_slots_running(self):
        store = RegistrationStore(self.path, RegistrationConfig(max_teams=1))
        created = store.register('Blue Lanterns', 'Alex Morgan')
        claimed = store.claim_pending()
        self.assertEqual(claimed['id'], created['id'])
        self.assertEqual(claimed['status'], 'provisioning')
        handout = {'desktop_urls': [
            {'slot': slot, 'url': 'https://event/guacamole/#/' + slot}
            for slot in claimed['slots']
        ]}
        store.complete(created['id'], handout)
        store.complete(created['id'], handout)
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

    def test_failed_registration_releases_its_desktops(self):
        store = RegistrationStore(self.path, RegistrationConfig(max_teams=1))
        created = store.register('Blue Lanterns', 'Alex Morgan')
        claimed = store.claim_pending()
        store.fail(claimed['id'], 'IRIS was unavailable')
        self.assertEqual(store.capacity()['available'], 1)
        again = store.register('Red Comets', 'Jamie Lee')
        self.assertEqual(again['slots'], created['slots'])

    def test_handout_has_three_distinct_tool_roles(self):
        handout = desktop_handout(['desktop-slot01', 'desktop-slot02', 'desktop-slot03'],
                                  'https://event:8082')
        self.assertEqual([row['role'] for row in handout],
                         ['forensics-a', 'forensics-b', 'analysis'])
        self.assertIn('Wireshark', handout[2]['tools'])
        self.assertTrue(all(row['url'].startswith('https://event:8082/guacamole/')
                            for row in handout))


if __name__ == '__main__':
    unittest.main()
