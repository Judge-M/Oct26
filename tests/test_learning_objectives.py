"""Learning objectives are generated from the tree, and every guard fires (issue 157).

``docs/learning-objectives.md`` used to be hand-written prose that had drifted
from the exercise: it told participants to use a single Wazuh view for a ticket
whose records have no time field, credited four tickets with a clock correction
the code applies to one, quoted ticket titles upstream has since changed, and
asserted NICE identifiers from a superseded framework revision.

These tests are the mechanism that stops it drifting again. The committed
document is compared with ``render()`` byte for byte, and each guard has a
negative test proving it fires: a validator with no failing test is not a
validator. Nothing here needs a service, a browser, a network or Docker.
"""
import contextlib
import copy
import io
import json
import tempfile
import unittest
from pathlib import Path

from ridge import learning_objectives
from ridge.learning_objectives import (
    DOCUMENT, FIXTURE, ObjectivesError, authored, facts, load, nice_status, render,
    report, validate, write,
)
from ridge.preflight import check_learning_objectives

ROOT = Path(__file__).resolve().parents[1]


def fixture():
    """A fresh mutable copy of the committed fixture."""
    return copy.deepcopy(load())


def flat(path):
    """One document, one line: prose assertions must not depend on where it wraps."""
    import re

    return re.sub(r'\s+', ' ', Path(path).read_text(encoding='utf-8'))


class LearningObjectiveFixtureTests(unittest.TestCase):
    def test_the_fixture_is_versioned_ascii_and_names_its_generator(self):
        raw = FIXTURE.read_bytes()
        self.assertFalse(raw.startswith(b'\xef\xbb\xbf'), 'the fixture must have no BOM')
        raw.decode('ascii')
        document = json.loads(raw.decode('utf-8'))
        self.assertEqual(document['schema'], learning_objectives.SCHEMA)
        self.assertIn('#157', document['revision'])

    def test_a_missing_or_unknown_fixture_is_refused_by_path(self):
        with self.assertRaisesRegex(ObjectivesError, 'fixture not found'):
            load(ROOT / 'assets/learning-objectives-v99.json')
        broken = fixture()
        broken['schema'] = 99
        with self.assertRaisesRegex(ObjectivesError, 'Unknown learning objectives schema'):
            learning_objectives.parse(broken)

    def test_a_fixture_without_the_required_sections_is_refused(self):
        for field in ('revision', 'title', 'framework', 'objectives', 'sections'):
            with self.subTest(field=field):
                broken = fixture()
                broken[field] = [] if field in ('objectives', 'sections') else ''
                with self.assertRaisesRegex(ObjectivesError, field):
                    learning_objectives.parse(broken)


class GeneratedDocumentTests(unittest.TestCase):
    """The committed document is the renderer's output, not prose anyone may edit."""

    def test_the_committed_document_matches_render_byte_for_byte(self):
        document = load()
        committed = DOCUMENT.read_text(encoding='utf-8')
        self.assertEqual(committed, render(document),
                         'docs/learning-objectives.md has drifted from the fixture; run '
                         'python -m ridge.learning_objectives --write')

    def test_the_committed_document_is_ascii_with_lf_endings_and_no_bom(self):
        raw = DOCUMENT.read_bytes()
        self.assertFalse(raw.startswith(b'\xef\xbb\xbf'))
        raw.decode('ascii')
        self.assertNotIn(b'\r\n', raw)

    def test_rendering_is_deterministic(self):
        document = load()
        self.assertEqual(render(document), render(document))

    def test_write_reproduces_the_committed_document_in_a_scratch_tree(self):
        document = load()
        with tempfile.TemporaryDirectory() as scratch:
            target = write(Path(scratch) / 'learning-objectives.md', document)
            self.assertEqual(target.read_text(encoding='utf-8'), DOCUMENT.read_text(encoding='utf-8'))

    def test_the_document_states_the_materials_the_audit_found_missing(self):
        text = flat(DOCUMENT)
        for required in ('IRIS', 'CTFd', 'Guacamole', '/originals', 'original_sha256',
                         'silent-ridge-timed', 'silent-ridge-timeless',
                         'case and outer whitespace are ignored',
                         'assets/t01-network-map-v1.json',
                         'check_no_answers', 'check_public_terms',
                         'narrative_consistency.py', '195', '270'):
            with self.subTest(term=required):
                self.assertIn(required, text)
        # The superseded pin and the withdrawn stability claim are named, not hidden.
        self.assertIn('SP 800-181', text)
        self.assertIn('is withdrawn', text)

    def test_the_document_refuses_to_assert_an_unverified_framework_mapping(self):
        text = DOCUMENT.read_text(encoding='utf-8')
        self.assertIn('`verified: false`', text)
        self.assertIn('unverified candidate', text)
        self.assertNotIn('Task IDs are stable across the revision.', text)


class ObjectiveCoverageTests(unittest.TestCase):
    """Every ticket is claimed, every claimed ticket exists, and nothing else is claimed."""

    def setUp(self):
        self.document = fixture()
        self.known = {ticket['id'] for ticket in authored()}

    def test_the_committed_fixture_claims_every_authored_ticket_exactly_once_or_more(self):
        receipt = report(load())
        self.assertEqual(receipt['unclaimed'], [])
        self.assertEqual(receipt['tickets'], len(self.known))
        self.assertTrue(receipt['tickets'] >= 20, 'the ticket set is derived, not assumed')

    def test_a_ticket_no_objective_claims_is_refused(self):
        """T15 was claimed by no objective in the previous revision."""
        self.document['objectives'] = [entry for entry in self.document['objectives']
                                       if 'T15' not in entry['tickets']]
        with self.assertRaisesRegex(ObjectivesError, r'objectives: no objective claims T15'):
            validate(self.document)

    def test_a_ticket_that_does_not_exist_is_refused(self):
        self.document['objectives'][0]['tickets'] = ['T99']
        with self.assertRaisesRegex(ObjectivesError, r'T99 is not an authored ticket'):
            validate(self.document)

    def test_the_ticket_set_is_derived_from_authoring_not_hardcoded(self):
        self.assertEqual(self.known, set(learning_objectives.titles()))

    def test_a_missing_objective_field_is_refused(self):
        for field in learning_objectives.REQUIRED_OBJECTIVE_FIELDS:
            with self.subTest(field=field):
                broken = fixture()
                broken['objectives'][0][field] = [] if field == 'tickets' else ''
                # An emptied ticket list is caught as an unclaimed ticket, not a
                # missing field; either way the fixture is refused.
                expected = 'no objective claims' if field == 'tickets' else field
                with self.assertRaisesRegex(ObjectivesError, expected):
                    validate(broken)

    def test_a_missing_nice_field_is_refused(self):
        for field in learning_objectives.REQUIRED_NICE_FIELDS:
            with self.subTest(field=field):
                broken = fixture()
                broken['objectives'][0]['nice'][field] = []
                with self.assertRaisesRegex(ObjectivesError, 'nice.%s' % field):
                    validate(broken)

    def test_a_duplicate_objective_id_is_refused(self):
        self.document['objectives'].append(copy.deepcopy(self.document['objectives'][0]))
        with self.assertRaisesRegex(ObjectivesError, 'is declared twice'):
            validate(self.document)

    def test_an_aar_row_naming_an_unknown_objective_is_refused(self):
        self.document['aar_map']['rows'][0]['objectives'] = ['LO42']
        with self.assertRaisesRegex(ObjectivesError, 'LO42 is not an objective'):
            validate(self.document)


class OverClaimTests(unittest.TestCase):
    """A mapping asserts that a scored question exercises the capability."""

    def test_a_mapping_for_a_capability_the_exercise_does_not_demonstrate_is_refused(self):
        for banned, statement in (
                ('duplicate', 'Create forensically sound duplicates of evidence'),
                ('notify', 'Notify designated managers of suspected incidents'),
                ('contain', 'Contain an incident')):
            with self.subTest(statement=statement):
                broken = fixture()
                roles = broken['objectives'][0]['nice']['roles']
                roles[0]['candidate_tasks'][0]['statement'] = statement
                with self.assertRaisesRegex(ObjectivesError, 'claims'):
                    validate(broken)

    def test_a_candidate_task_without_its_verified_flag_is_refused(self):
        broken = fixture()
        del broken['objectives'][0]['nice']['roles'][0]['candidate_tasks'][0]['verified']
        with self.assertRaisesRegex(ObjectivesError, 'missing verified'):
            validate(broken)


class ViewGuardTests(unittest.TestCase):
    """The defect that made T12 unanswerable cannot come back."""

    def test_the_committed_document_documents_t12_against_the_timeless_view(self):
        views = load()['views']
        self.assertEqual(views['silent-ridge-timeless']['tickets'], ['T12'])
        self.assertNotIn('T12', views['silent-ridge-timed']['tickets'])

    def test_moving_t12_into_the_timed_view_is_refused(self):
        broken = fixture()
        broken['views']['silent-ridge-timed']['tickets'].append('T12')
        broken['views']['silent-ridge-timeless']['tickets'] = []
        with self.assertRaisesRegex(ObjectivesError, r'views.silent-ridge-timeless.tickets'):
            validate(broken)

    def test_a_single_view_instruction_is_refused(self):
        """The old defect: one ``silent-ridge-*`` view with an absolute range for everything."""
        broken = fixture()
        del broken['views']['silent-ridge-timeless']
        with self.assertRaisesRegex(ObjectivesError, 'timeless view must be documented'):
            validate(broken)

    def test_a_view_name_that_is_not_provisioned_is_refused(self):
        broken = fixture()
        broken['views']['silent-ridge-replay'] = {'tickets': ['T12'], 'reason': 'merged'}
        with self.assertRaisesRegex(ObjectivesError, 'not a Wazuh saved view'):
            validate(broken)

    def test_prose_naming_an_unprovisioned_view_is_refused(self):
        broken = fixture()
        broken['views']['intro'] = ('Use the silent-ridge-historical view for every Wazuh '
                                    'ticket, with one absolute UTC range.')
        with self.assertRaisesRegex(ObjectivesError, 'not a provisioned view'):
            validate(broken)

    def test_a_ticket_in_both_views_is_refused(self):
        broken = fixture()
        broken['views']['silent-ridge-timed']['tickets'].append('T12')
        with self.assertRaisesRegex(ObjectivesError, 'both saved views'):
            validate(broken)

    def test_the_view_partition_is_derived_from_the_authored_steps(self):
        derived = learning_objectives.wazuh_views()
        self.assertEqual(derived['silent-ridge-timeless'], ['T12'])
        self.assertEqual(sorted(derived['silent-ridge-timed']),
                         ['T06', 'T07', 'T10', 'T11', 'T20'])


class ClockGuardTests(unittest.TestCase):
    """Only the ticket the code corrects may be documented as correcting anything."""

    def test_the_committed_fixture_names_one_corrected_ticket(self):
        clock = load()['clock']
        self.assertEqual(clock['applied_by'], ['T04'])
        self.assertEqual(clock['asked_about'], ['T12'])
        self.assertEqual(clock['must_not_apply'], ['T13', 'T14', 'T15', 'T16'])

    def test_the_old_four_ticket_correction_claim_is_refused(self):
        """The previous revision credited T01, T02, T03/T04 and T12 with the correction."""
        broken = fixture()
        broken['clock']['applied_by'] = ['T01', 'T02', 'T03', 'T04']
        with self.assertRaisesRegex(ObjectivesError, r'clock.applied_by: documented T01, T02, T03, T04'):
            validate(broken)

    def test_prose_attributing_the_offset_to_another_ticket_is_refused(self):
        broken = fixture()
        broken['objectives'][2]['mechanism'] = ('T03 applies the documented 120-second '
                                                'WS-17 device correction before the timeline '
                                                'is built.')
        with self.assertRaisesRegex(ObjectivesError, 'attributes the device clock correction to T03'):
            validate(broken)

    def test_a_wrong_offset_is_refused(self):
        broken = fixture()
        broken['clock']['seconds'] = 60
        with self.assertRaisesRegex(ObjectivesError, r'clock: documented a 60 s offset'):
            validate(broken)

    def test_correcting_a_native_record_is_refused(self):
        broken = fixture()
        broken['clock']['must_not_apply'] = ['T13', 'T14', 'T15']
        with self.assertRaisesRegex(ObjectivesError, r'clock.must_not_apply: documented T13, T14, T15'):
            validate(broken)

    def test_the_clock_facts_are_derived_from_the_code_not_typed(self):
        from ridge.scenario import DEVICE_OFFSETS

        derived = learning_objectives.clock_facts()
        self.assertEqual(derived['seconds'], DEVICE_OFFSETS['WS-17'])
        self.assertEqual(derived['host'], 'WS-17')

    def test_the_offset_applies_to_a_device_clock_and_to_nothing_else(self):
        """The sentence the document makes about ``ridge.scenario.timestamp``."""
        from ridge.scenario import DEVICE_OFFSETS, timestamp

        self.assertEqual(DEVICE_OFFSETS['WS-17'], 120)
        self.assertEqual(
            timestamp({'host': 'WS-17', 'device_time': '2026-10-15T09:00:00Z'}, 'endpoint.csv'),
            '2026-10-15T08:58:00Z')
        self.assertEqual(
            timestamp({'host': 'WS-17', 'time': '2026-10-15T09:00:00Z'}, 'proxy.csv'),
            '2026-10-15T09:00:00Z')

    def test_the_one_corrected_ticket_reads_the_source_that_carries_a_device_clock(self):
        ticket = learning_objectives.tickets_by_id()['T04']
        corrected = [question for question in ticket['questions']
                     if 'corrected' in question['prompt'].lower()]
        self.assertEqual(len(corrected), 1)
        self.assertEqual(corrected[0]['evidence'], '/evidence/endpoint/events.csv')


class DateGuardTests(unittest.TestCase):
    """The scenario date and the acquisition date are different days, and both are stated."""

    def test_both_dates_are_stated_and_distinct(self):
        dates = learning_objectives.acquisition_dates()
        self.assertEqual(dates['scenario_date'], '2026-10-15')
        self.assertEqual(dates['acquisition_date'], '2026-09-15')
        self.assertNotEqual(dates['scenario_date'], dates['acquisition_date'])
        self.assertEqual(load()['acquisition']['scenario_date'], dates['scenario_date'])
        self.assertEqual(load()['acquisition']['acquisition_date'], dates['acquisition_date'])

    def test_claiming_one_day_for_both_is_refused(self):
        broken = fixture()
        broken['acquisition']['acquisition_date'] = broken['acquisition']['scenario_date']
        with self.assertRaisesRegex(ObjectivesError, 'stated as the same day'):
            validate(broken)

    def test_a_wrong_scenario_date_is_refused(self):
        broken = fixture()
        broken['acquisition']['scenario_date'] = '2026-09-16'
        with self.assertRaisesRegex(ObjectivesError, 'expanded/config.json'):
            validate(broken)

    def test_a_wrong_acquisition_date_is_refused(self):
        broken = fixture()
        broken['acquisition']['acquisition_date'] = '2026-09-14'
        with self.assertRaisesRegex(ObjectivesError, 'the native manifest records'):
            validate(broken)

    def test_an_unstated_date_is_refused(self):
        broken = fixture()
        broken['acquisition']['acquisition_date'] = ''
        with self.assertRaisesRegex(ObjectivesError, 'both dates must be stated'):
            validate(broken)


class TicketTitleGuardTests(unittest.TestCase):
    """Upstream retitled T13, T14 and T16; a stale title here names the wrong ticket."""

    def test_the_committed_crosswalk_quotes_the_current_titles(self):
        current = learning_objectives.titles()
        self.assertEqual(current['T13'], 'Inspect acquired process-log records')
        self.assertEqual(current['T14'], 'Inspect acquired task-log records')
        self.assertEqual(current['T16'], 'Correlate the acquired connection snapshot')
        for row in load()['crosswalk']['rows']:
            for ticket, title in zip(row['tickets'], row['titles']):
                self.assertEqual(title, current[ticket])

    def test_a_stale_title_is_refused(self):
        broken = fixture()
        row = next(entry for entry in broken['crosswalk']['rows'] if entry['id'] == 'native')
        row['titles'][0] = 'Inspect prepared process-log records'
        with self.assertRaisesRegex(ObjectivesError, r'crosswalk\[2\].titles: T13 is'):
            validate(broken)

    def test_a_crosswalk_row_without_one_title_per_ticket_is_refused(self):
        broken = fixture()
        broken['crosswalk']['rows'][0]['titles'] = ['Trace document traffic']
        with self.assertRaisesRegex(ObjectivesError, 'one title is required per ticket'):
            validate(broken)

    def test_a_ticket_no_crosswalk_row_covers_is_refused(self):
        broken = fixture()
        broken['crosswalk']['rows'] = [row for row in broken['crosswalk']['rows']
                                       if 'T18' not in row['tickets']]
        with self.assertRaisesRegex(ObjectivesError, r'no row covers T17, T18'):
            validate(broken)


class NiceGateTests(unittest.TestCase):
    """The gate is the point: an unverifiable mapping must read as unverifiable."""

    def test_the_committed_gate_is_open_and_validate_still_passes(self):
        document = load()
        status = nice_status(document)
        self.assertFalse(status['verified'])
        self.assertIsNone(status['verified_against'])
        self.assertGreater(status['unverified_mappings'], 0)
        self.assertEqual(status['verified_mappings'], 0)
        validate(document)

    def test_strict_mode_fails_while_the_gate_is_open(self):
        with self.assertRaisesRegex(ObjectivesError, 'unverified mapping'):
            validate(fixture(), strict=True)

    def test_a_mapping_claiming_verified_without_a_dated_release_is_refused(self):
        broken = fixture()
        broken['objectives'][0]['nice']['roles'][0]['candidate_tasks'][0]['verified'] = True
        with self.assertRaisesRegex(ObjectivesError, 'not a dated release'):
            nice_status(broken)
        with self.assertRaisesRegex(ObjectivesError, 'not a dated release'):
            validate(broken)

    def test_an_undated_release_does_not_open_the_gate(self):
        broken = fixture()
        broken['framework']['verified_against'] = 'NICE Framework 4.0'
        status = nice_status(broken)
        self.assertFalse(status['verified'])
        self.assertFalse(status['release_is_dated'])
        with self.assertRaisesRegex(ObjectivesError, 'nice gate'):
            validate(broken, strict=True)

    def test_a_dated_release_with_every_mapping_verified_opens_the_gate(self):
        """The gate is a gate, not a constant: it can be opened by evidence."""
        broken = fixture()
        broken['framework']['verified_against'] = 'NICE Framework 4.0, 2024-08-01'
        for objective in broken['objectives']:
            for role in objective['nice']['roles']:
                for task in role['candidate_tasks']:
                    task['verified'] = True
        status = nice_status(broken)
        self.assertTrue(status['verified'])
        self.assertEqual(status['unverified_mappings'], 0)
        validate(broken, strict=True)

    def test_one_unverified_mapping_keeps_the_gate_closed(self):
        broken = fixture()
        broken['framework']['verified_against'] = 'NICE Framework 4.0, 2024-08-01'
        broken['objectives'][0]['nice']['roles'][0]['candidate_tasks'][0]['verified'] = True
        status = nice_status(broken)
        self.assertFalse(status['verified'])
        self.assertIn('still unverified candidates', status['reason'])

    def test_the_gate_is_surfaced_by_preflight_without_failing_it(self):
        receipt = check_learning_objectives()
        self.assertTrue(receipt['ready'])
        self.assertFalse(receipt['nice']['verified'])
        self.assertGreater(receipt['nice']['unverified_mappings'], 0)
        self.assertIn('verified_against', receipt['nice'])

    def test_preflight_reports_an_unusable_fixture_instead_of_claiming_coverage(self):
        receipt = check_learning_objectives(ROOT / 'assets/learning-objectives-v99.json')
        self.assertFalse(receipt['ready'])
        self.assertFalse(receipt['proved'])
        self.assertIn('fixture not found', receipt['reason'])


class PhasePartitionTests(unittest.TestCase):
    """Two fixtures disagree; the document must not pick a winner."""

    def test_both_partitions_are_reported_as_a_conflict(self):
        derived = learning_objectives.phase_facts()
        self.assertTrue(derived['differ'])
        self.assertEqual(len(derived['sources']), 2)
        self.assertEqual(derived['sources'][0]['sizes'], [3, 8, 5, 4])
        self.assertEqual(derived['sources'][1]['sizes'], [5, 5, 5, 5])
        self.assertGreater(derived['disagreements'], 0)

    def test_the_document_names_both_fixtures_the_readers_and_the_open_decision(self):
        text = DOCUMENT.read_text(encoding='utf-8')
        self.assertIn('assets/scenario-narrative-v1.json', text)
        self.assertIn('ridge/scenario_narrative_v1.json', text)
        self.assertIn('PR #151', text)
        self.assertIn('does not assert either partition as fact', text)

    def test_naming_only_one_phase_fixture_is_refused(self):
        broken = fixture()
        broken['phases']['sources'] = [{'fixture': 'assets/scenario-narrative-v1.json'}]
        with self.assertRaisesRegex(ObjectivesError, 'name both fixtures'):
            validate(broken)

    def test_a_phase_fixture_that_is_not_in_the_tree_is_refused(self):
        broken = fixture()
        broken['phases']['sources'][1]['fixture'] = 'assets/narrative-v9.json'
        with self.assertRaisesRegex(ObjectivesError, 'not a phase fixture in the tree'):
            validate(broken)

    def test_dropping_the_open_decision_is_refused(self):
        broken = fixture()
        broken['phases']['decision'] = ''
        with self.assertRaisesRegex(ObjectivesError, 'open decision must be named'):
            validate(broken)


class SectionAndLimitTests(unittest.TestCase):
    def test_a_required_section_cannot_be_dropped(self):
        for needed in ('objectives', 'crosswalk', 'limits', 'maintenance'):
            with self.subTest(section=needed):
                broken = fixture()
                broken['sections'] = [section for section in broken['sections']
                                      if section['id'] != needed]
                with self.assertRaisesRegex(ObjectivesError, needed):
                    validate(broken)

    def test_an_unknown_block_type_is_refused(self):
        broken = fixture()
        broken['sections'][0]['blocks'].append({'type': 'prose', 'text': 'invented'})
        with self.assertRaisesRegex(ObjectivesError, 'is not a block type'):
            validate(broken)

    def test_dropping_the_duration_figures_is_refused(self):
        """The previous revision omitted the makespan and called the target a four-hour goal."""
        broken = fixture()
        broken['workload']['notes'] = ['The activity should last about four hours.']
        broken['workload']['text'] = 'The exercise has {tickets} tickets.'
        with self.assertRaisesRegex(ObjectivesError, 'makespan and the configured target'):
            validate(broken)

    def test_an_invented_placeholder_is_refused(self):
        broken = fixture()
        broken['workload']['text'] = 'Roughly {whatever} minutes of work.'
        broken['workload']['notes'] = ['{makespan_minutes} of {target_minutes}. ' + 'x' * 80]
        with self.assertRaisesRegex(ObjectivesError, 'not derived figures'):
            validate(broken)

    def test_the_limits_still_refuse_to_claim_event_readiness(self):
        text = flat(DOCUMENT)
        self.assertIn('is not event-ready', text)
        self.assertIn('not a validated deployment', text)
        self.assertIn('forensic duplicate', text)
        self.assertIn('gated on a hash', text)


class AnswerLeakTests(unittest.TestCase):
    """The document is published, so it may not state an answer either."""

    def test_the_committed_fixture_states_no_distinctive_scored_answer(self):
        validate(load())

    def test_stating_an_answer_in_prose_is_refused(self):
        from ridge.scenario_contract import distinctive_answers

        answers = distinctive_answers(authored())
        answer = next(name for name in sorted(answers) if len(name) > 6)
        broken = fixture()
        broken['objectives'][1]['statement'] = 'The chain closes at ' + answer + '.'
        with self.assertRaisesRegex(ObjectivesError, 'states the answer to'):
            validate(broken)

    def test_a_canon_name_is_not_treated_as_a_leak(self):
        """The clock guard has to name WS-17, which is also a scored answer."""
        self.assertIn('ws-17', learning_objectives.visible_terms())


class DerivedFactsTests(unittest.TestCase):
    def test_map_counts_come_from_the_map_fixture(self):
        derived = learning_objectives.map_facts()
        self.assertEqual((derived['nodes'], derived['edges']), (19, 13))
        self.assertEqual((derived['observed'], derived['inferred']), (11, 2))
        self.assertEqual(derived['unlocks_after'], 'T01')

    def test_workload_figures_come_from_the_schedule_model(self):
        derived = learning_objectives.workload_facts()
        self.assertEqual(derived['makespan_minutes'], 195)
        self.assertEqual(derived['target_minutes'], 270)
        self.assertEqual(derived['estimated_team_minutes'], 1300)

    def test_deck_and_breadcrumb_counts_are_read_from_the_tree(self):
        derived = facts()
        self.assertEqual(derived['deck']['participant'], 22)
        self.assertEqual(derived['deck']['facilitator'], 2)
        self.assertEqual(derived['breadcrumbs']['count'], 7)
        self.assertFalse(derived['breadcrumbs']['bonus'])


class CommandLineTests(unittest.TestCase):
    def test_the_check_and_report_commands_pass(self):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            self.assertEqual(learning_objectives.main([]), 0)
            self.assertEqual(learning_objectives.main(['--report']), 0)
        self.assertIn('unverified mapping', buffer.getvalue())

    def test_strict_mode_exits_non_zero_while_the_gate_is_open(self):
        with contextlib.redirect_stderr(io.StringIO()) as errors:
            self.assertEqual(learning_objectives.main(['--strict']), 1)
        self.assertIn('nice gate', errors.getvalue())

    def test_write_reports_the_path_it_wrote(self):
        buffer = io.StringIO()
        with tempfile.TemporaryDirectory() as scratch:
            with contextlib.redirect_stdout(buffer):
                code = learning_objectives.main(['--write', '--document',
                                                 str(Path(scratch) / 'out.md')])
            self.assertEqual(code, 0)
            self.assertIn('out.md', buffer.getvalue())

    def test_a_broken_fixture_exits_non_zero_instead_of_raising(self):
        broken = ROOT / 'work' / 'learning-objectives-broken.json'
        broken.parent.mkdir(parents=True, exist_ok=True)
        document = fixture()
        document['objectives'] = [entry for entry in document['objectives']
                                  if 'T15' not in entry['tickets']]
        broken.write_text(json.dumps(document), encoding='utf-8')
        try:
            with contextlib.redirect_stderr(io.StringIO()) as errors:
                self.assertEqual(learning_objectives.main(['--path', str(broken)]), 1)
            self.assertIn('no objective claims T15', errors.getvalue())
        finally:
            broken.unlink()


if __name__ == '__main__':
    unittest.main()
