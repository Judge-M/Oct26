"""Deterministic tests for the optional breadcrumbs (issue 59).

These breadcrumbs are a participant-facing content surface with no scoring, so the
tests are mostly guards. They prove the fixture is well formed, that it survives
reset and reseed byte for byte, that a breadcrumb belonging to a still-locked phase
is genuinely not on the evidence mount, and that nothing in it can pre-answer a
scored question, name an adversary, carry a credential or point outside the
exercise.

No CTFd, IRIS, Docker, browser or network is required: the fixture is pure data,
``expanded/prepare.py`` builds a real release into a temporary directory, and the
Wazuh indexer call made while publishing a follow-up file is patched out.
"""
import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from expanded.prepare import build as prepare
from ridge import breadcrumbs
from ridge.breadcrumbs import (
    CONTRACT_ID, FIXTURE, REQUIRED_FIELDS, BreadcrumbError, build, entries, inventory,
    load, parse, published_paths, text_of, validate, visible_to,
)
from ridge.scenario import RELEASE_FILES
from ridge.scenario_contract import build as build_contract, public_terms
from ridge.state import State

ROOT = Path(__file__).resolve().parents[1]


def authored(config=None):
    from expanded.author import build as author
    return author(config)


class BreadcrumbFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tickets = authored()
        cls.contract = build_contract(tickets=cls.tickets)
        cls.document = build(tickets=cls.tickets, contract=cls.contract)

    def test_fixture_is_versioned_and_declares_its_identity(self):
        self.assertEqual(self.document['schema'], 1)
        self.assertEqual(self.document['contract'], CONTRACT_ID)
        self.assertIsInstance(self.document['revision'], int)
        self.assertEqual(FIXTURE.name, 'breadcrumbs-v1.json')
        self.assertIn('status', self.document)

    def test_unknown_schema_is_rejected(self):
        for bad in (0, 2, 'v1', None):
            with self.subTest(schema=bad):
                with self.assertRaisesRegex(BreadcrumbError, 'Unknown breadcrumb schema'):
                    parse(dict(self.document, schema=bad))

    def test_unknown_contract_id_is_rejected(self):
        with self.assertRaisesRegex(BreadcrumbError, 'Unknown breadcrumb contract id'):
            parse(dict(self.document, contract='something-else'))

    def test_missing_fixture_is_reported_by_path(self):
        with self.assertRaisesRegex(BreadcrumbError, 'not found'):
            load(ROOT / 'assets/does-not-exist.json')

    def test_every_breadcrumb_declares_its_whole_contract(self):
        for entry in entries(self.document):
            for field in REQUIRED_FIELDS:
                self.assertIn(field, entry, '%s.%s is missing' % (entry['id'], field))
            self.assertTrue(text_of(entry).strip())
            self.assertTrue(entry['must_not_reveal'])

    def test_every_major_phase_carries_at_least_one_breadcrumb(self):
        grouped = breadcrumbs.by_phase(self.document)
        for phase in breadcrumbs.phase_ids(self.contract):
            self.assertTrue(grouped.get(phase), 'no breadcrumb in ' + phase)
        self.assertEqual(set(grouped), set(breadcrumbs.phase_ids(self.contract)))

    def test_breadcrumbs_meet_the_issue_scale_and_cross_task_floor(self):
        self.assertGreaterEqual(len(entries(self.document)), 4)
        self.assertLessEqual(len(entries(self.document)), 10)
        cross = [e for e in entries(self.document) if e['cross_task']]
        self.assertGreaterEqual(len(cross), 2, 'the issue asks for genuine cross-task pointers')

    def test_a_phase_without_a_breadcrumb_is_rejected(self):
        broken = copy.deepcopy(self.document)
        broken['breadcrumbs'] = [e for e in broken['breadcrumbs'] if e['phase'] != 'phase-3']
        with self.assertRaisesRegex(BreadcrumbError, 'phases with no breadcrumb: phase-3'):
            validate(broken, self.tickets, self.contract)

    def test_breadcrumb_in_an_unknown_phase_is_rejected(self):
        broken = copy.deepcopy(self.document)
        broken['breadcrumbs'][0]['phase'] = 'phase-9'
        with self.assertRaisesRegex(BreadcrumbError, 'not a phase in the narrative contract'):
            validate(broken, self.tickets, self.contract)

    def test_inventory_is_deterministic_and_covers_every_phase(self):
        first = inventory(self.document, self.contract)
        self.assertEqual(first, inventory(build(tickets=self.tickets), self.contract))
        self.assertEqual(first['breadcrumbs'], len(entries(self.document)))
        self.assertEqual(first['contract_phases'], 4)
        self.assertEqual(first['initial'] + first['release'], first['breadcrumbs'])
        self.assertEqual(first['bonus'], 0)

    def test_attribution_and_scoring_policies_are_declared(self):
        self.assertTrue(self.document['framing']['rule'].strip())
        self.assertTrue(self.document['framing']['rationale'].strip())
        self.assertIs(self.document['scoring']['bonus'], False)
        self.assertTrue(self.document['scoring']['rule'].strip())
        self.assertTrue(self.document['scoring']['rationale'].strip())
        for field in breadcrumbs.REQUIRED_DELIVERY_FIELDS:
            self.assertTrue(self.document['delivery'][field].strip())


class BreadcrumbPointerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tickets = authored()
        cls.contract = build_contract(tickets=cls.tickets)
        cls.document = build(tickets=cls.tickets, contract=cls.contract)

    def test_every_referenced_ticket_exists_in_the_authored_set(self):
        known = {ticket['id'] for ticket in self.tickets}
        self.assertEqual(len(known), 20)
        for entry in entries(self.document):
            self.assertIn(entry['iris_ticket'], known)
            for point in entry['points_to']:
                if point['kind'] == 'ticket':
                    self.assertIn(point['ref'], known, entry['id'])

    def test_pointer_at_an_unknown_ticket_is_rejected(self):
        broken = copy.deepcopy(self.document)
        broken['breadcrumbs'][0]['points_to'].append({'kind': 'ticket', 'ref': 'T99'})
        with self.assertRaisesRegex(BreadcrumbError, 'points at unknown ticket T99'):
            validate(broken, self.tickets, self.contract)

    def test_every_referenced_evidence_path_is_in_the_published_set(self):
        # The prepared-case manifest is the inventory of the published evidence tree.
        manifest = json.loads((ROOT / 'assets/autopsy-case-v2.json').read_text(encoding='utf-8'))
        case = {record['path'] for record in manifest['evidence_files']}
        self.assertTrue(case)
        published = published_paths()
        for entry in entries(self.document):
            for point in entry['points_to']:
                if point['kind'] != 'evidence':
                    continue
                self.assertIn(point['ref'], published, entry['id'])
                self.assertTrue(point['ref'].startswith('/') is False)
        # At least one pointer must reach the case inventory itself, not only a
        # follow-up file, so the breadcrumbs are anchored to real evidence.
        referenced = {p['ref'] for e in entries(self.document) for p in e['points_to']
                      if p['kind'] == 'evidence'}
        self.assertTrue(referenced & case)

    def test_pointer_at_evidence_that_is_not_published_is_rejected(self):
        broken = copy.deepcopy(self.document)
        broken['breadcrumbs'][0]['points_to'].append(
            {'kind': 'evidence', 'ref': 'vault/releases/T19/network/dlp-body.txt'})
        with self.assertRaisesRegex(BreadcrumbError, 'not published'):
            validate(broken, self.tickets, self.contract)

    def test_pointer_of_unknown_kind_is_rejected(self):
        broken = copy.deepcopy(self.document)
        broken['breadcrumbs'][0]['points_to'].append({'kind': 'host', 'ref': '10.26.20.10'})
        with self.assertRaisesRegex(BreadcrumbError, 'unknown pointer kind host'):
            validate(broken, self.tickets, self.contract)

    def test_a_breadcrumb_must_point_at_something(self):
        broken = copy.deepcopy(self.document)
        broken['breadcrumbs'][0]['points_to'] = []
        with self.assertRaisesRegex(BreadcrumbError, 'must point at something'):
            validate(broken, self.tickets, self.contract)

    def test_a_breadcrumb_path_cannot_leave_the_evidence_mount(self):
        for path in ('../facilitator/ground-truth.md', '/etc/passwd', 'notes/../../x.txt',
                     'facilitator/solutions.md', 'notes\\x.txt'):
            with self.subTest(path=path):
                broken = copy.deepcopy(self.document)
                broken['breadcrumbs'][0]['path'] = path
                with self.assertRaises(BreadcrumbError):
                    validate(broken, self.tickets, self.contract)

    def test_breadcrumbs_never_reference_facilitator_material(self):
        for entry in entries(self.document):
            blob = json.dumps(entry).lower()
            for needle in ('facilitator/', 'ground-truth', 'solutions.md', '/vault',
                           'inject-1', 'controller/'):
                self.assertNotIn(needle, blob, '%s references %s' % (entry['id'], needle))

    def test_breadcrumbs_are_not_required_by_any_scored_question(self):
        # A breadcrumb is optional, so no question, step, hint or selection may name
        # one. This is the machine-checkable half of the optionality claim.
        for ticket in self.tickets:
            for question in ticket['questions']:
                blob = json.dumps({k: v for k, v in question.items() if k != 'finding'}).lower()
                self.assertNotIn('notes/', blob, question['id'] + ' points at a breadcrumb')
        from ridge.question_matrix import build as matrix
        for row in matrix():
            self.assertNotIn('notes/', row['evidence_path'], row['question_id'])
            self.assertNotIn('notes/', row['selection'], row['question_id'])
        markdown = (ROOT / 'docs/acceptance/question-matrix.md').read_text(encoding='utf-8')
        self.assertNotIn('notes/', markdown)


class BreadcrumbSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tickets = authored()
        cls.contract = build_contract(tickets=cls.tickets)
        cls.document = build(tickets=cls.tickets, contract=cls.contract)

    def test_no_breadcrumb_carries_a_scored_answer(self):
        from ridge.scenario_contract import distinctive_answers
        answers = distinctive_answers(self.tickets)
        self.assertGreaterEqual(sum(len(v) for v in answers.values()), 50)
        breadcrumbs.check_no_answers(self.document, self.tickets, self.contract)

    def test_leak_guard_catches_an_answer_planted_in_a_breadcrumb(self):
        broken = copy.deepcopy(self.document)
        broken['breadcrumbs'][0]['text'] += '\nThe workstation was WS-17.\n'
        with self.assertRaisesRegex(BreadcrumbError, 'contains the answer to T01-Q1'):
            breadcrumbs.check_no_answers(broken, self.tickets, self.contract)

    def test_leak_guard_catches_a_closing_ticket_answer_planted_in_a_breadcrumb(self):
        broken = copy.deepcopy(self.document)
        broken['breadcrumbs'][-1]['text'] += '\nThe upload used req-72.\n'
        with self.assertRaisesRegex(BreadcrumbError, 'contains the answer to T01-Q3'):
            breadcrumbs.check_no_answers(broken, self.tickets, self.contract)

    def test_breadcrumbs_are_stricter_than_the_contract_on_public_terms(self):
        # The contract exempts its public_terms from the leak guard. A note somebody
        # left behind gains nothing by naming one, so none of them may appear.
        for entry in entries(self.document):
            for term in sorted(public_terms(self.contract)):
                self.assertNotIn(term, text_of(entry).lower(),
                                 '%s restates the public term %s' % (entry['id'], term))

    def test_external_documentation_address_is_never_named(self):
        breadcrumbs.check_no_documentation_address(self.document)
        broken = copy.deepcopy(self.document)
        broken['breadcrumbs'][0]['text'] += '\nSee 198.51.100.77.\n'
        with self.assertRaisesRegex(BreadcrumbError, 'names the external documentation address'):
            breadcrumbs.check_no_documentation_address(broken)

    def test_no_breadcrumb_carries_any_address_literal(self):
        breadcrumbs.check_no_addresses(self.document)
        broken = copy.deepcopy(self.document)
        broken['breadcrumbs'][0]['text'] += '\nFrom 10.26.10.17 to 10.26.20.10.\n'
        with self.assertRaisesRegex(BreadcrumbError, 'address literal'):
            breadcrumbs.check_no_addresses(broken)

    def test_no_breadcrumb_names_an_adversary(self):
        # Issue 59 asks for a fictional adversary framing. Canon has no such name and
        # T20-Q4 scores 'no' for intent, so the fixture must stay unattributed.
        for word in ('wraith', 'APT29', 'Lazarus', 'Cobalt Strike', 'mimikatz', 'meterpreter'):
            with self.subTest(word=word):
                broken = copy.deepcopy(self.document)
                broken['breadcrumbs'][0]['text'] += '\nLeft behind by the %s operator.\n' % word
                with self.assertRaisesRegex(BreadcrumbError, 'names an adversary'):
                    breadcrumbs.check_contained(broken)

    def test_ordinary_words_containing_an_adversary_token_are_not_false_positives(self):
        broken = copy.deepcopy(self.document)
        broken['breadcrumbs'][0]['text'] += '\nThe capture was adapted for the drill.\n'
        breadcrumbs.check_contained(broken)

    def test_no_breadcrumb_carries_a_credential_or_an_operational_instruction(self):
        probes = ('Run sudo cat /etc/shadow', 'nmap -sS 10.26.20.10',
                  'password=hunter2', 'api_key: abcd1234',
                  'curl http://relay.archive.example/upload', 'export TOKEN=abcd')
        for probe in probes:
            with self.subTest(probe=probe):
                broken = copy.deepcopy(self.document)
                broken['breadcrumbs'][0]['text'] += '\n' + probe + '\n'
                with self.assertRaisesRegex(BreadcrumbError, 'operational instruction|credential'):
                    breadcrumbs.check_contained(broken)

    def test_no_breadcrumb_carries_a_real_world_target(self):
        broken = copy.deepcopy(self.document)
        broken['breadcrumbs'][0]['text'] += '\nMeet at latitude 35.6 after the shift.\n'
        with self.assertRaisesRegex(BreadcrumbError, 'real-world target'):
            breadcrumbs.check_contained(broken)

    def test_a_breadcrumb_does_not_sign_itself_with_the_exercise_codename(self):
        # The notes read as traces left by someone using the access, not as exercise
        # control writing to participants.
        broken = copy.deepcopy(self.document)
        broken['breadcrumbs'][0]['text'] += '\n-- Silent Ridge exercise cell\n'
        with self.assertRaisesRegex(BreadcrumbError, 'exercise codename'):
            breadcrumbs.check_contained(broken)

    def test_contained_check_passes_on_the_committed_fixture(self):
        breadcrumbs.check_contained(self.document)


class BreadcrumbDeliveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tickets = authored()
        cls.contract = build_contract(tickets=cls.tickets)
        cls.document = build(tickets=cls.tickets, contract=cls.contract)

    def test_every_release_breadcrumb_sits_behind_a_ticket_with_prerequisites(self):
        # State.initialize enqueues every ticket with no prerequisites, and
        # transport.remote_sink publishes a ticket's release on delivery, so a
        # breadcrumb hung on a root ticket would be on the mount at run start.
        requires = {ticket['id']: list(ticket.get('requires', [])) for ticket in self.tickets}
        gated = [e for e in entries(self.document) if e['delivery'] == 'release']
        self.assertTrue(gated, 'the fixture should exercise the release path')
        for entry in gated:
            self.assertTrue(requires[entry['gate']],
                            '%s rides a root ticket and would publish at run start' % entry['id'])

    def test_release_breadcrumb_on_a_root_ticket_is_rejected(self):
        broken = copy.deepcopy(self.document)
        broken['breadcrumbs'][0]['delivery'] = 'release'
        broken['breadcrumbs'][0]['gate'] = 'T01'
        with self.assertRaisesRegex(BreadcrumbError, 'published at run start'):
            validate(broken, self.tickets, self.contract)

    def test_release_delivery_without_a_gate_is_rejected(self):
        broken = copy.deepcopy(self.document)
        broken['breadcrumbs'][0]['delivery'] = 'release'
        with self.assertRaisesRegex(BreadcrumbError, 'release delivery requires a gate ticket'):
            validate(broken, self.tickets, self.contract)

    def test_unknown_delivery_kind_is_rejected(self):
        broken = copy.deepcopy(self.document)
        broken['breadcrumbs'][0]['delivery'] = 'slideshow'
        with self.assertRaisesRegex(BreadcrumbError, 'delivery must be initial or release'):
            validate(broken, self.tickets, self.contract)

    def test_release_contract_and_fixture_must_agree(self):
        # If these drift, a breadcrumb is written into the vault under a ticket whose
        # release never names it, and validate_release fails closed on the next run.
        breadcrumbs.check_release_contract(self.document)
        broken = copy.deepcopy(self.document)
        broken['breadcrumbs'][0]['delivery'] = 'release'
        broken['breadcrumbs'][0]['gate'] = 'T07'
        with self.assertRaisesRegex(BreadcrumbError, 'does not match the declared release'):
            breadcrumbs.check_release_contract(broken)

    def test_authored_release_files_carry_the_declared_breadcrumbs(self):
        for ticket in self.tickets:
            names = set(ticket['release_files'])
            declared = {e['path'] for e in entries(self.document)
                        if e['delivery'] == 'release' and e['gate'] == ticket['id']}
            self.assertEqual(names & {n for n in names if n.startswith('notes/')}, declared,
                             'ticket %s release list drifted from the fixture' % ticket['id'])

    def test_visibility_follows_the_completed_tickets(self):
        initial = [e for e in entries(self.document) if e['delivery'] == 'initial']
        self.assertEqual(visible_to(self.document, []), initial)
        for entry in entries(self.document):
            if entry['delivery'] != 'release':
                continue
            gate = entry['gate']
            self.assertNotIn(entry, visible_to(self.document, set()))
            self.assertIn(entry, visible_to(self.document, {gate}))
            self.assertEqual(len(visible_to(self.document, {gate})), len(initial) + 1)
        every = {ticket['id'] for ticket in self.tickets}
        self.assertEqual(len(visible_to(self.document, every)), len(entries(self.document)))
        self.assertEqual(breadcrumbs.gated_behind(self.document, []),
                         [e for e in entries(self.document) if e['delivery'] == 'release'])

    def test_later_phases_are_not_visible_before_their_gate_opens(self):
        phase_of = self.contract['phases']
        phase_id = {tid: phase['id'] for phase in phase_of for tid in phase['tickets']}
        for entry in entries(self.document):
            if entry['delivery'] != 'release':
                continue
            # Everything in a phase that is still locked stays hidden.
            self.assertNotIn(entry, visible_to(self.document, set()))
            self.assertEqual(phase_id[entry['iris_ticket']], entry['phase'])


class BreadcrumbPublicationTimingTests(unittest.TestCase):
    """Anchor the gating to what the controller actually does, not to a comment.

    Every ticket with no prerequisites is enqueued for delivery at
    ``State.initialize`` and ``transport.remote_sink`` publishes a ticket's release
    on delivery. The phase-3 and phase-4 breadcrumbs depend on that being true, so
    this walks a real state through it.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.state = State(self.root / 'state.sqlite', retry_delay=0)
        self.tickets_by_id = {ticket['id']: ticket for ticket in authored()}
        self.state.initialize([dict(id='a', iris='1', ctfd=1, name='A')], authored())
        self.state.provision('operator')
        self.delivered = []
        self.remote = 0

    def tearDown(self):
        self.tmp.cleanup()

    def drain(self):
        def deliver(kind, key, payload, context):
            if kind == 'ticket':
                self.delivered.append((payload['ticket'], list(json.loads(context['release_files']))))
            self.remote += 1
            return self.remote
        for _ in range(64):
            if not self.state.sync_once(deliver):
                break
        return self.delivered

    def test_root_tickets_and_their_releases_are_delivered_at_run_start(self):
        self.drain()
        roots = {ticket['id'] for ticket in authored() if not ticket['requires']}
        self.assertEqual({ticket for ticket, _ in self.delivered}, roots)
        # The trap: because root tickets deliver at run start, a release breadcrumb
        # hung on one would be on the mount before any team had done anything. No
        # root ticket may carry a release, which is why the breadcrumbs are not.
        for ticket, names in self.delivered:
            self.assertEqual(names, [], '%s is a root ticket and published a release' % ticket)
        for ticket in RELEASE_FILES:
            self.assertIn(ticket, self.tickets_by_id)
            self.assertTrue(self.tickets_by_id[ticket]['requires'],
                            '%s has no prerequisites and would publish at run start' % ticket)

    def test_a_gated_ticket_delivers_only_once_its_prerequisites_close(self):
        self.drain()
        self.assertNotIn('T11', {ticket for ticket, _ in self.delivered})
        self.state.mode('operator', 'running')
        questions = [q for t in authored() if t['id'] == 'T10' for q in t['questions']]
        self.state.claim('a', 'T10', 0)
        for question in questions:
            self.assertTrue(self.state.answer('a', question['id'], question['answer'])['correct'])
        self.drain()
        delivered = {ticket: names for ticket, names in self.delivered}
        self.assertIn('T11', delivered)
        self.assertIn('notes/third-machine.txt', delivered['T11'])
        published = {name for _, names in self.delivered for name in names}
        self.assertNotIn('notes/timeline-order.txt', published,
                         'the phase-4 breadcrumb must stay unexposed')


class BreadcrumbFlagTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tickets = authored()
        cls.contract = build_contract(tickets=cls.tickets)
        cls.document = build(tickets=cls.tickets, contract=cls.contract)

    def test_optional_and_bonus_are_complete_and_consistent(self):
        for entry in entries(self.document):
            self.assertIsInstance(entry['optional'], bool)
            self.assertIsInstance(entry['bonus'], bool)
            self.assertTrue(entry['optional'], entry['id'] + ' may not be required')
            self.assertFalse(entry['bonus'], entry['id'] + ' may not be bonus')
            self.assertIsInstance(entry['must_not_reveal'], list)
            self.assertTrue(entry['must_not_reveal'])

    def test_bonus_scoring_is_refused(self):
        broken = copy.deepcopy(self.document)
        broken['breadcrumbs'][0]['bonus'] = True
        with self.assertRaisesRegex(BreadcrumbError, 'not reconcilable with CTFd and IRIS'):
            validate(broken, self.tickets, self.contract)

    def test_a_required_breadcrumb_is_refused(self):
        broken = copy.deepcopy(self.document)
        broken['breadcrumbs'][0]['optional'] = False
        with self.assertRaisesRegex(BreadcrumbError, 'a breadcrumb may not be required'):
            validate(broken, self.tickets, self.contract)

    def test_a_breadcrumb_must_declare_what_it_may_not_reveal(self):
        for mutation in ([], 'nothing'):
            with self.subTest(mutation=mutation):
                broken = copy.deepcopy(self.document)
                broken['breadcrumbs'][0]['must_not_reveal'] = mutation
                with self.assertRaisesRegex(BreadcrumbError, 'must_not_reveal'):
                    validate(broken, self.tickets, self.contract)

    def test_breadcrumb_ids_are_stable_and_unique(self):
        ids = [entry['id'] for entry in entries(self.document)]
        self.assertEqual(ids, sorted(ids), 'ids should read in phase order')
        self.assertEqual(len(ids), len(set(ids)))
        for name in ids:
            self.assertRegex(name, r'^BC-[0-9]{2}$')

    def test_a_duplicate_breadcrumb_id_is_rejected(self):
        broken = copy.deepcopy(self.document)
        broken['breadcrumbs'].append(copy.deepcopy(broken['breadcrumbs'][0]))
        with self.assertRaisesRegex(BreadcrumbError, 'duplicate breadcrumb id'):
            validate(broken, self.tickets, self.contract)


class BreadcrumbReleaseTests(unittest.TestCase):
    """Presence in the generated evidence tree, determinism, and real publication."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.release = prepare(self.root / 'release', {'exercise_date': '2026-10-15'})

    def tearDown(self):
        self.tmp.cleanup()

    def notes(self, base):
        return {p.relative_to(base).as_posix(): p.read_bytes()
                for p in sorted(base.rglob('notes/*')) if p.is_file()}

    def test_every_breadcrumb_is_present_in_the_generated_release(self):
        document = load()
        public = self.release / 'initial'
        vault = self.release / 'controller/releases'
        for entry in entries(document):
            base = public if entry['delivery'] == 'initial' else vault / entry['gate']
            target = base / entry['path']
            with self.subTest(breadcrumb=entry['id']):
                self.assertTrue(target.is_file(), entry['path'] + ' is not in the release')
                self.assertEqual(target.read_text(encoding='utf-8'), text_of(entry))

    def test_only_phase_one_and_two_breadcrumbs_are_on_the_mount_at_run_start(self):
        # The whole initial tree is mounted before the first ticket is claimed, so
        # anything in it is visible immediately. A phase-3 or phase-4 breadcrumb
        # there would be a locked-phase spoiler.
        document = load()
        on_mount = set(self.notes(self.release / 'initial'))
        for entry in entries(document):
            if entry['delivery'] != 'initial':
                self.assertNotIn(entry['path'], on_mount, entry['id'] + ' is exposed at run start')
        self.assertEqual(on_mount, {e['path'] for e in entries(document) if e['delivery'] == 'initial'})

    def test_release_breadcrumbs_live_in_the_vault_beside_their_follow_up_evidence(self):
        document = load()
        vault = self.release / 'controller/releases'
        for entry in entries(document):
            if entry['delivery'] != 'release':
                continue
            ticket = vault / entry['gate']
            with self.subTest(breadcrumb=entry['id']):
                self.assertTrue((ticket / entry['path']).is_file())
                self.assertIn(entry['path'], RELEASE_FILES[entry['gate']])
                self.assertFalse((self.release / 'initial' / entry['path']).exists())

    def test_release_breadcrumbs_reach_the_mount_only_when_their_gate_publishes(self):
        from ridge.evidence_release import publish
        document = load()
        gated = [e for e in entries(document) if e['delivery'] == 'release']
        environment = {'RIDGE_RELEASE_VAULT': str(self.release / 'controller/releases'),
                       'RIDGE_EVIDENCE_PUBLIC': str(self.release / 'initial'),
                       'RIDGE_MIN_FREE_BYTES': '0'}
        with patch.dict(os.environ, environment), patch('ridge.evidence_release.index'):
            for entry in gated:
                target = self.release / 'initial' / entry['path']
                self.assertFalse(target.exists(), entry['id'] + ' published before its gate')
                publish(entry['gate'], RELEASE_FILES[entry['gate']])
                self.assertTrue(target.is_file(), entry['id'] + ' was not published')
                self.assertEqual(target.read_text(encoding='utf-8'), text_of(entry))
            # Publication is idempotent: a retry after a lost response is a no-op.
            for entry in gated:
                publish(entry['gate'], RELEASE_FILES[entry['gate']])

    def test_breadcrumb_publication_fails_closed_on_a_corrupt_vault_file(self):
        from ridge.evidence_release import publish
        document = load()
        entry = next(e for e in entries(document) if e['delivery'] == 'release')
        source = self.release / 'controller/releases' / entry['gate'] / entry['path']
        original = source.read_bytes()
        source.write_bytes(b'corrupt')
        environment = {'RIDGE_RELEASE_VAULT': str(self.release / 'controller/releases'),
                       'RIDGE_EVIDENCE_PUBLIC': str(self.release / 'initial'),
                       'RIDGE_MIN_FREE_BYTES': '0'}
        with patch.dict(os.environ, environment), patch('ridge.evidence_release.index'):
            with self.assertRaisesRegex(ValueError, 'Corrupt evidence'):
                publish(entry['gate'], RELEASE_FILES[entry['gate']])
            self.assertFalse((self.release / 'initial' / entry['path']).exists())
        source.write_bytes(original)

    def test_preflight_accepts_the_release_with_breadcrumbs_attached(self):
        # The controller reconciles every ticket's release against the vault before
        # provisioning, so a breadcrumb that drifted out of the release contract
        # would stop the run rather than quietly going missing.
        from ridge.evidence_release import validate_release
        environment = {'RIDGE_RELEASE_VAULT': str(self.release / 'controller/releases'),
                       'RIDGE_EVIDENCE_PUBLIC': str(self.release / 'initial')}
        with patch.dict(os.environ, environment):
            for ticket, names in RELEASE_FILES.items():
                source, released = validate_release(ticket, names)
                self.assertEqual(set(released), set(names))
                self.assertTrue(source.is_dir())

    def test_a_rebuild_is_byte_for_byte_identical(self):
        other = prepare(self.root / 'rebuild', {'exercise_date': '2026-10-15'})
        self.assertEqual(self.notes(self.release / 'initial'), self.notes(other / 'initial'))
        for ticket in RELEASE_FILES:
            with self.subTest(ticket=ticket):
                left = self.release / 'controller/releases' / ticket
                right = other / 'controller/releases' / ticket
                self.assertEqual({p.relative_to(left).as_posix(): p.read_bytes()
                                  for p in sorted(left.rglob('*')) if p.is_file()},
                                 {p.relative_to(right).as_posix(): p.read_bytes()
                                  for p in sorted(right.rglob('*')) if p.is_file()})
        sums = json.loads((self.release / 'SHA256SUMS.json').read_text(encoding='utf-8'))
        self.assertEqual(sums, json.loads((other / 'SHA256SUMS.json').read_text(encoding='utf-8')))

    def test_breadcrumbs_survive_a_reseeded_exercise_date(self):
        reseeded = prepare(self.root / 'reseed', {'exercise_date': '2027-02-03'})
        document = load()
        for entry in entries(document):
            base = (reseeded / 'initial' if entry['delivery'] == 'initial'
                    else reseeded / 'controller/releases' / entry['gate'])
            with self.subTest(breadcrumb=entry['id']):
                self.assertEqual((base / entry['path']).read_text(encoding='utf-8'), text_of(entry))

    def test_the_release_manifest_checksums_cover_every_breadcrumb(self):
        from ridge.artifacts import sha256
        manifest = json.loads((self.release / 'controller/releases/manifest.json').read_text(encoding='utf-8'))
        for entry in entries(load()):
            if entry['delivery'] != 'release':
                continue
            digest = manifest['tickets'][entry['gate']][entry['path']]
            actual = sha256(self.release / 'controller/releases' / entry['gate'] / entry['path'])
            self.assertEqual(digest, actual, entry['id'] + ' is not covered by the release manifest')

    def test_preparation_fails_closed_on_an_unsafe_breadcrumb_fixture(self):
        broken = copy.deepcopy(load())
        broken['breadcrumbs'][-1]['text'] += '\nWhoever did this signed in as m.ellis.\n'
        with patch('ridge.breadcrumbs.load', return_value=broken):
            with self.assertRaises(BreadcrumbError):
                prepare(self.root / 'unsafe', {'exercise_date': '2026-10-15'})


if __name__ == '__main__':
    unittest.main()
