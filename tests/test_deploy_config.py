"""A03: deployment profile schema and validator."""
import json
import unittest
from copy import deepcopy
from pathlib import Path

from ridge.deploy.config import (ProfileError, desired_inventory, fingerprint,
                                 neutral_roster, resolve_inventory, validate)

ROOT = Path(__file__).resolve().parents[1]
TWO = json.loads((ROOT / 'deployment/profiles/example-two-team.json').read_text(encoding='utf-8'))
TEN = json.loads((ROOT / 'deployment/profiles/example-ten-team-aws.json').read_text(encoding='utf-8'))


def production(profile):
    profile = deepcopy(profile)
    profile['profile_kind'] = 'production'
    for index, desktop in enumerate(profile['desktops']):
        desktop['address'] = '10.26.10.%d' % (11 + index)
    profile['addresses']['central_bind_ip'] = '10.26.10.10'
    for key in ('iris_public_url', 'ctfd_public_url', 'guacamole_public_url'):
        profile['addresses'][key] = 'https://' + key.split('_')[0] + '.silent-ridge.local'
    return profile


class DeployProfileTests(unittest.TestCase):
    def test_example_profiles_validate_without_fixed_ids(self):
        two = validate(TWO)
        ten = validate(TEN)
        self.assertEqual(len(two['roster']['teams']), 2)
        self.assertEqual(len(ten['roster']['teams']), 10)
        for team in ten['roster']['teams']:
            self.assertNotIn('iris', team)
            self.assertNotIn('ctfd', team)

    def test_neutral_roster_and_accounts_generated(self):
        teams = neutral_roster(3)
        self.assertEqual([team['name'] for team in teams], ['team-01', 'team-02', 'team-03'])
        self.assertEqual(teams[0]['accounts'], ['team-01-p01', 'team-01-p02', 'team-01-p03'])
        self.assertEqual(validate(TWO)['roster']['teams'][0]['accounts'], teams[0]['accounts'])

    def test_production_profile_accepts_routable_addresses(self):
        self.assertEqual(validate(production(TWO))['profile_kind'], 'production')

    def test_duplicate_team_names_rejected(self):
        profile = deepcopy(TWO)
        profile['roster'] = {'teams': [
            {'name': 'team-01', 'members': 3, 'desktop': 'desktop-01'},
            {'name': 'team-01', 'members': 3, 'desktop': 'desktop-02'}]}
        with self.assertRaises(ProfileError) as caught:
            validate(profile)
        self.assertEqual(caught.exception.field, 'roster.teams[1].name')

    def test_duplicate_desktop_names_rejected(self):
        profile = deepcopy(TWO)
        profile['desktops'][1]['name'] = 'desktop-01'
        with self.assertRaises(ProfileError) as caught:
            validate(profile)
        self.assertEqual(caught.exception.field, 'desktops[1].name')

    def test_unmapped_desktop_rejected(self):
        profile = deepcopy(TWO)
        profile['roster'] = {'teams': [{'name': 'team-01', 'members': 3, 'desktop': 'desktop-99'}]}
        with self.assertRaises(ProfileError) as caught:
            validate(profile)
        self.assertEqual(caught.exception.field, 'roster.teams[0].desktop')

    def test_documentation_only_addresses_rejected_in_production(self):
        profile = production(TWO)
        profile['addresses']['central_bind_ip'] = '192.0.2.10'
        with self.assertRaises(ProfileError) as caught:
            validate(profile)
        self.assertEqual(caught.exception.field, 'addresses.central_bind_ip')
        urls = production(TWO)
        urls['addresses']['iris_public_url'] = 'https://iris.example.invalid'
        with self.assertRaises(ProfileError) as caught:
            validate(urls)
        self.assertEqual(caught.exception.field, 'addresses.iris_public_url')

    def test_missing_required_field_names_the_field(self):
        for field in ('retention', 'capacity', 'addresses', 'secret_refs', 'spending'):
            profile = deepcopy(TWO)
            del profile[field]
            with self.assertRaises(ProfileError) as caught:
                validate(profile)
            self.assertEqual(caught.exception.field, field)

    def test_invalid_dates_rejected(self):
        profile = deepcopy(TWO)
        profile['event']['incident_date'] = '2026-13-40'
        with self.assertRaises(ProfileError) as caught:
            validate(profile)
        self.assertEqual(caught.exception.field, 'event.incident_date')
        profile = deepcopy(TWO)
        profile['event']['event_start'] = '2026-10-26T09:00:00'
        with self.assertRaises(ProfileError) as caught:
            validate(profile)
        self.assertEqual(caught.exception.field, 'event.event_start')
        profile = deepcopy(TWO)
        profile['event']['event_start'] = '2026-01-01T00:00:00Z'
        with self.assertRaises(ProfileError) as caught:
            validate(profile)
        self.assertEqual(caught.exception.field, 'event.event_start')

    def test_incompatible_schema_version_rejected(self):
        profile = deepcopy(TWO)
        profile['schema_version'] = 2
        with self.assertRaises(ProfileError) as caught:
            validate(profile)
        self.assertEqual(caught.exception.field, 'schema_version')

    def test_embedded_secret_values_rejected(self):
        profile = deepcopy(TWO)
        profile['secret_refs']['iris_bridge'] = 'hunter2'
        with self.assertRaises(ProfileError) as caught:
            validate(profile)
        self.assertEqual(caught.exception.field, 'secret_refs.iris_bridge')
        profile = deepcopy(TWO)
        profile['event']['password'] = 'hunter2'
        with self.assertRaises(ProfileError) as caught:
            validate(profile)
        self.assertEqual(caught.exception.field, 'event.password')

    def test_fixed_application_ids_rejected(self):
        profile = deepcopy(TWO)
        profile['roster'] = {'teams': [{'name': 'team-01', 'members': 3,
                                        'desktop': 'desktop-01', 'iris_id': 101}]}
        with self.assertRaises(ProfileError) as caught:
            validate(profile)
        self.assertEqual(caught.exception.field, 'roster.teams[0].iris_id')

    def test_insufficient_host_capacity_rejected(self):
        profile = deepcopy(TEN)
        profile['capacity']['host']['memory_mib'] = 1024
        with self.assertRaises(ProfileError) as caught:
            validate(profile)
        self.assertEqual(caught.exception.field, 'capacity.host.memory_mib')

    def test_desired_and_resolved_inventory(self):
        desired = desired_inventory(TWO)
        self.assertNotIn('resolved', desired['teams'][0])
        self.assertEqual(desired['teams'][0]['name'], 'team-01')
        with self.assertRaises(ProfileError) as caught:
            resolve_inventory(TWO, {'teams': {}, 'desktops': {}})
        self.assertEqual(caught.exception.field, 'resolved.teams.team-01')
        resolved = {
            'teams': {'team-01': {'iris_id': '101', 'ctfd_id': 1},
                      'team-02': {'iris_id': '102', 'ctfd_id': 2}},
            'desktops': {'desktop-01': {'provider_id': 'vm-1'},
                         'desktop-02': {'provider_id': 'vm-2'}},
        }
        inventory = resolve_inventory(TWO, resolved)
        self.assertEqual(inventory['teams'][0]['resolved'], {'iris_id': '101', 'ctfd_id': 1})
        self.assertEqual(inventory['desktops'][1]['resolved']['provider_id'], 'vm-2')

    def test_fingerprint_is_stable_and_content_sensitive(self):
        self.assertEqual(fingerprint(TWO), fingerprint(deepcopy(TWO)))
        changed = deepcopy(TWO)
        changed['event']['duration_minutes'] = 300
        self.assertNotEqual(fingerprint(TWO), fingerprint(changed))


if __name__ == '__main__':
    unittest.main()
