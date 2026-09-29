"""Deterministic tests for the approved narrative contract (issues 56, 58, 60, 59, 66).

The contract is the one approved source for the participant narrative shared by
CTFd, IRIS and the event-day deck. These tests are what stop the three surfaces
from drifting apart again, and what stop a content edit from quietly
pre-answering a scored question.

No CTFd, IRIS, Docker or browser is required: the contract is pure data plus the
authored ticket set.
"""
import copy
import json
import unittest
from pathlib import Path

from ridge.scenario_contract import (
    CONTRACT_ID, FIXTURE, REQUIRED_TICKET_FIELDS, ContractError, build, check_no_answers,
    check_public_terms, distinctive_answers, inventory, load, narrative_strings, parse,
    phase_of, public_terms, validate,
)

ROOT = Path(__file__).resolve().parents[1]

# Surfaces that already exist in published material. A term is only exempt from
# the answer-leak guard if it is already visible to a participant somewhere.
PARTICIPANT_SURFACES = (
    [ROOT / 'ridge/web.py', ROOT / 'expanded/guides.md', ROOT / 'participants/handover.md',
     ROOT / 'participants/cells.md', ROOT / 'participants/worksheets.md']
    + sorted((ROOT / 'docs/event-day-deck/pages').glob('*.page'))
)


def authored():
    from expanded.author import build as author
    return author()


def surfaces_text():
    return '\n'.join(path.read_text(encoding='utf-8', errors='replace')
                     for path in PARTICIPANT_SURFACES if path.is_file())


class ScenarioContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tickets = authored()
        cls.contract = build(tickets=cls.tickets)

    def test_fixture_is_versioned_and_declares_its_identity(self):
        document = load()
        self.assertEqual(document['schema'], 1)
        self.assertEqual(document['contract'], CONTRACT_ID)
        self.assertIsInstance(document['revision'], int)
        self.assertEqual(FIXTURE.name, 'scenario-narrative-v1.json')
        self.assertIn('status', document)

    def test_unknown_schema_is_rejected(self):
        for bad in (0, 2, 'v1', None):
            with self.subTest(schema=bad):
                with self.assertRaisesRegex(ContractError, 'Unknown narrative contract schema'):
                    parse(dict(self.contract, schema=bad))

    def test_unknown_contract_id_is_rejected(self):
        with self.assertRaisesRegex(ContractError, 'Unknown narrative contract id'):
            parse(dict(self.contract, contract='something-else'))

    def test_missing_fixture_is_reported_by_path(self):
        with self.assertRaisesRegex(ContractError, 'not found'):
            load(ROOT / 'assets/does-not-exist.json')

    def test_every_ticket_has_a_complete_narrative_entry(self):
        for ticket in self.tickets:
            entry = self.contract['tickets'][ticket['id']]
            for field in REQUIRED_TICKET_FIELDS:
                self.assertTrue(str(entry.get(field, '')).strip(),
                                '%s.%s is empty' % (ticket['id'], field))

    def test_narrative_entry_for_an_unknown_ticket_is_rejected(self):
        broken = copy.deepcopy(self.contract)
        broken['tickets']['T99'] = broken['tickets']['T01']
        with self.assertRaisesRegex(ContractError, 'no such ticket'):
            validate(broken, self.tickets)

    def test_a_ticket_left_without_narrative_is_rejected(self):
        broken = copy.deepcopy(self.contract)
        del broken['tickets']['T13']
        with self.assertRaisesRegex(ContractError, 'no narrative for T13'):
            validate(broken, self.tickets)

    def test_empty_required_ticket_field_is_rejected(self):
        for field in REQUIRED_TICKET_FIELDS:
            with self.subTest(field=field):
                broken = copy.deepcopy(self.contract)
                broken['tickets']['T01'][field] = '   '
                with self.assertRaisesRegex(ContractError, 'required narrative field is empty'):
                    validate(broken, self.tickets)

    def test_phases_partition_every_ticket_exactly_once(self):
        claimed = [tid for phase in self.contract['phases'] for tid in phase['tickets']]
        self.assertEqual(len(claimed), len(set(claimed)))
        self.assertEqual(set(claimed), {ticket['id'] for ticket in self.tickets})
        self.assertGreaterEqual(len(self.contract['phases']), 4,
                                'the acceptance criteria require a breadcrumb in each major phase')

    def test_phase_referencing_an_unknown_ticket_is_rejected(self):
        broken = copy.deepcopy(self.contract)
        broken['phases'][0]['tickets'].append('T99')
        with self.assertRaisesRegex(ContractError, 'unknown ticket T99'):
            validate(broken, self.tickets)

    def test_ticket_claimed_by_two_phases_is_rejected(self):
        broken = copy.deepcopy(self.contract)
        broken['phases'][1]['tickets'].append('T01')
        with self.assertRaisesRegex(ContractError, 'more than one phase'):
            validate(broken, self.tickets)

    def test_ticket_with_no_phase_is_rejected(self):
        broken = copy.deepcopy(self.contract)
        broken['phases'][0]['tickets'].remove('T01')
        with self.assertRaisesRegex(ContractError, 'tickets with no phase'):
            validate(broken, self.tickets)

    def test_exercise_narrative_is_present_for_the_whole_event(self):
        exercise = self.contract['exercise']
        for field in ('premise', 'discovery', 'stakes', 'exposure', 'escalation', 'outcome',
                      'fiction_notice', 'classification_line'):
            self.assertTrue(exercise.get(field, '').strip(), 'exercise.%s is empty' % field)
        self.assertTrue(self.contract['exercise']['adversary']['rule'].strip())
        self.assertTrue(self.contract['roles'])
        self.assertTrue(self.contract['exercise_complete']['handoff'].strip())
        self.assertTrue(self.contract['aar']['prompts'])

    def test_participant_boundaries_are_declared(self):
        boundaries = self.contract['boundaries']
        for field in ('read_only', 'no_credentials', 'no_operational_detail', 'fiction_repeat',
                      'attribution'):
            self.assertTrue(boundaries.get(field, '').strip(), 'boundaries.%s is empty' % field)
        for field in ('accepted', 'ticket_complete', 'hints'):
            self.assertTrue(self.contract[field], '%s narrative is required' % field)

    def test_narrative_never_leaks_a_scored_answer(self):
        self.assertGreaterEqual(sum(len(v) for v in distinctive_answers(self.tickets).values()),
                                50, 'the leak guard should cover the distinctive answers')
        check_no_answers(self.contract, self.tickets)

    def test_leak_guard_catches_an_answer_planted_in_the_ticket_it_scores(self):
        broken = copy.deepcopy(self.contract)
        broken['tickets']['T01']['brief'] = 'The workstation WS-17 sent the brief out.'
        with self.assertRaisesRegex(ContractError, 'contains the answer to T01-Q1'):
            check_no_answers(broken, self.tickets)

    def test_leak_guard_catches_an_answer_planted_in_a_phase(self):
        broken = copy.deepcopy(self.contract)
        broken['phases'][0]['purpose'] = 'Confirm the upload to 198.51.100.77.'
        with self.assertRaisesRegex(ContractError, 'contains the answer to'):
            check_no_answers(broken, self.tickets)

    def test_leak_guard_catches_an_answer_planted_in_the_closing_statement(self):
        broken = copy.deepcopy(self.contract)
        broken['exercise_complete']['brief'] = 'The upload used request req-72.'
        with self.assertRaisesRegex(ContractError, 'contains the answer to T01-Q3'):
            check_no_answers(broken, self.tickets)

    def test_every_exempt_term_is_already_participant_visible(self):
        check_public_terms(self.contract, [surfaces_text()])

    def test_exemption_list_cannot_be_widened_to_hide_a_new_answer(self):
        broken = copy.deepcopy(self.contract)
        broken['public_terms'] = sorted(public_terms(broken) | {'ws-17'})
        with self.assertRaisesRegex(ContractError, 'not already participant-visible'):
            check_public_terms(broken, [surfaces_text()])

    def test_inventory_is_deterministic_and_covers_three_surfaces(self):
        first = inventory(self.contract, self.tickets)
        self.assertEqual(first, inventory(build(tickets=self.tickets), self.tickets))
        self.assertEqual(first['tickets'], 20)
        self.assertEqual(first['surfaces'], ['ctfd', 'iris', 'deck'])
        self.assertEqual(first['questions_guarded'],
                         sum(len(v) for v in distinctive_answers(self.tickets).values()))

    def test_narrative_strings_cover_every_rendered_field(self):
        fields = {field for field, _ in narrative_strings(self.contract)}
        for expected in ('exercise.premise', 'roles.soc-analyst', 'phases.phase-1.purpose',
                         'tickets.T01.brief', 'hints.policy', 'accepted.lead',
                         'ticket_complete.generic', 'exercise_complete.handoff',
                         'boundaries.read_only', 'aar.intro'):
            self.assertIn(expected, fields)
        self.assertTrue(all(text.strip() for field, text in narrative_strings(self.contract)
                            if not field.startswith('phases.')))

    def test_phase_of_resolves_the_containing_phase(self):
        self.assertEqual(phase_of(self.contract, 'T01')['id'], self.contract['phases'][0]['id'])
        self.assertIsNone(phase_of(self.contract, 'T99'))

    def test_no_operational_or_real_world_instructions_in_narrative(self):
        # The contract is participant-facing prose. It must not acquire instructions.
        forbidden = ('nmap ', 'mimikatz', 'powershell -enc', 'curl http', 'sudo ', 'ssh ',
                     '40.7', 'latitude', 'longitude')
        for field, text in narrative_strings(self.contract):
            for needle in forbidden:
                self.assertNotIn(needle, text.lower(), '%s contains %r' % (field, needle))

    def test_external_documentation_address_is_never_named_in_narrative(self):
        # 198.51.100.77 is a T01/T02 answer; the map surfaces it after T01 instead.
        for field, text in narrative_strings(self.contract):
            self.assertNotIn('198.51.100.77', text, '%s names the external address' % field)

    def test_contract_does_not_name_an_adversary_group(self):
        # Issue 59 proposes a 'Wraith' framing. Canon has no such name and T20-Q4
        # scores 'no' for intent, so the contract must stay unattributed.
        for field, text in narrative_strings(self.contract):
            self.assertNotIn('wraith', text.lower(), '%s names an adversary group' % field)


if __name__ == '__main__':
    unittest.main()
