"""Deterministic tests for the participant narrative render context (issue 56).

The contract holds the approved prose; ``ridge.web_narrative`` turns it into the
context that ``ridge/web.py`` renders on both lanes. These tests hold three
things true at once: every section a participant reads is present, nothing
facilitator-only or scored reaches the context, and the template still
references every key the assembler emits. That last one is the likeliest
regression, because a renamed Jinja variable renders as a silently blank
paragraph rather than an exception.

No CTFd, IRIS, Docker, browser, network or clock is required.
"""
import copy
import inspect
import json
import re
import sys
import unittest
from unittest.mock import patch

from ridge.scenario_contract import ContractError, build, distinctive_answers
from ridge.web import PAGE
from ridge.web_narrative import (
    CONTEXT_KEYS, QUESTION_FIELDS, NarrativeError, check_deployment, context, matters,
    question_narrative, ticket_narrative, validate,
)

ROOT_TICKET = 'T01'


def authored():
    from expanded.author import build as author
    return author()


def questions_for(contract, ticket_id=ROOT_TICKET, solved=False):
    """Authored question bodies as the bridge hands them over, answers included."""
    ticket = next(t for t in authored() if t['id'] == ticket_id)
    bodies = [dict(question, ticket=ticket_id) for question in ticket['questions']]
    if solved:
        bodies[0] = dict(bodies[0], solved_by='team-01', answered_at='2026-10-28T09:30:00Z',
                         finding={'text': 'a finding', 'evidence': ['network/sensor.pcap'],
                                  'limitation': 'a limitation'})
    return bodies


def snapshot(rows):
    return {'mode': 'running', 'team': 'team-01', 'tickets': rows,
            'scores': [{'id': 'team-01', 'name': 'Team 01', 'points': 0}]}


def write_contract(document):
    """A temporary contract file, for proving a broken contract is refused."""
    import tempfile
    from pathlib import Path
    handle = tempfile.NamedTemporaryFile('w', suffix='.json', delete=False, encoding='utf-8')
    with handle:
        json.dump(document, handle)
    return Path(handle.name)


def template_paths():
    """Identifier paths the template actually reads, e.g. {'briefing.codename'}."""
    page = re.sub(r'<script>.*?</script>', '', PAGE, flags=re.S)
    paths = set()
    expressions = re.findall(r'{{.*?}}|{%.*?%}', page, flags=re.S)
    for expression in expressions:
        text = re.sub(r"\['([^']+)'\]", r'.\1', expression)
        paths.update(re.findall(r'[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*', text))
    return paths


def template_names():
    """Every bare name and attribute segment the template reads."""
    names = set()
    for path in template_paths():
        parts = path.split('.')
        names.add(parts[0])
        names.update(parts[1:])
    return names


def context_names(rendered, prefix=''):
    """Every key name the assembler emits, at any depth.

    Ticket ids are lookup keys, not rendered field names, so they are skipped.
    """
    names = set()
    for key, value in rendered.items():
        if re.fullmatch(r'T[0-9]{2}', key):
            continue
        names.add(key)
        if isinstance(value, dict):
            names.update(context_names(value))
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    names.update(context_names(item))
    return names


class NarrativeContextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tickets = authored()
        cls.contract = build(tickets=cls.tickets)
        cls.rows = [{'id': 'T01', 'status': 'available'}, {'id': 'T02', 'status': 'complete'}]
        cls.ctfd = context(cls.contract, snapshot(cls.rows), questions_for(cls.contract), 'ctfd')
        cls.iris = context(cls.contract, snapshot(cls.rows), None, 'iris')

    def test_assembler_produces_every_required_section(self):
        for rendered in (self.ctfd, self.iris):
            for key in CONTEXT_KEYS:
                self.assertIn(key, rendered)
            self.assertEqual(set(rendered), set(CONTEXT_KEYS))
            self.assertTrue(all(str(value).strip() for value in rendered['briefing'].values()))
            self.assertEqual([r['name'] for r in rendered['roles']],
                             [r['name'] for r in self.contract['roles']])
            self.assertEqual(len(rendered['tool_map']), len(self.contract['tool_map']))
            self.assertEqual(len(rendered['phases']), len(self.contract['phases']))
            self.assertEqual(set(rendered['boundaries']),
                             {'read_only', 'no_credentials', 'no_operational_detail',
                              'fiction_repeat', 'attribution'})

    def test_every_value_comes_from_the_contract(self):
        source = contract_text(self.contract)
        for rendered in (self.ctfd, self.iris):
            for key in ('briefing', 'roles', 'tool_map', 'phases', 'narrative_tickets',
                        'hints_policy', 'accepted', 'ticket_complete', 'exercise_complete',
                        'boundaries'):
                for token in rendered_strings(rendered[key]):
                    self.assertTrue(sourced(token, source),
                                    '%s renders text absent from the contract: %r' % (key, token))

    def test_both_lane_contexts_are_complete_and_distinct(self):
        validate(self.ctfd, self.contract['revision'])
        validate(self.iris, self.contract['revision'])
        self.assertTrue(self.ctfd['questions'])
        self.assertEqual(self.iris['questions'], [],
                         'the IRIS queue never renders question cards')
        # Both lanes still carry the event briefing and the role briefing.
        for key in ('briefing', 'roles', 'tool_map', 'phases', 'narrative_tickets',
                    'boundaries', 'hints_policy', 'accepted', 'ticket_complete',
                    'exercise_complete'):
            self.assertEqual(self.ctfd[key], self.iris[key], key)

    def test_ticket_narrative_names_its_phase_and_next_step(self):
        for ticket in self.tickets:
            entry = self.ctfd['narrative_tickets'][ticket['id']]
            authored_entry = self.contract['tickets'][ticket['id']]
            self.assertEqual(entry['headline'], authored_entry['headline'])
            self.assertEqual(entry['brief'], authored_entry['brief'])
            self.assertEqual(entry['stakes'], authored_entry['stakes'])
            self.assertEqual(entry['why_now'], authored_entry['why_now'])
            self.assertEqual(entry['next'], authored_entry['transition'])
            self.assertEqual(entry['phase_id'],
                             next(p['id'] for p in self.contract['phases']
                                  if ticket['id'] in p['tickets']))
            self.assertEqual(entry['phase_transition'],
                             next(p['transition'] for p in self.contract['phases']
                                  if ticket['id'] in p['tickets']))

    def test_a_completed_ticket_yields_the_completion_narrative(self):
        rows = [{'id': 'T01', 'status': 'complete'}]
        rendered = context(self.contract, snapshot(rows), None, 'iris')
        entry = rendered['narrative_tickets']['T01']
        self.assertTrue(entry['complete'])
        self.assertFalse(rendered['narrative_tickets']['T02']['complete'])
        self.assertEqual(rendered['ticket_complete']['generic'],
                         self.contract['ticket_complete']['generic'])
        self.assertEqual(rendered['ticket_complete']['handoff'],
                         self.contract['ticket_complete']['handoff'])

    def test_only_a_fully_closed_exercise_yields_the_ending(self):
        running = context(self.contract, snapshot([{'id': 'T01', 'status': 'complete'}]), None, 'iris')
        self.assertFalse(running['exercise_complete']['done'])
        self.assertTrue(all(not str(value).strip()
                            for key, value in running['exercise_complete'].items() if key != 'done'))
        closed = context(self.contract, snapshot([{'id': tid, 'status': 'complete'}
                                                  for tid in sorted(self.contract['tickets'])]), None, 'iris')
        self.assertTrue(closed['exercise_complete']['done'])
        for field in ('brief', 'handoff', 'residual', 'scoring_note'):
            self.assertEqual(closed['exercise_complete'][field],
                             self.contract['exercise_complete'][field])

    def test_a_solved_question_yields_the_accepted_answer_narrative(self):
        rendered = context(self.contract, snapshot([{'id': 'T01', 'status': 'active'}]),
                           questions_for(self.contract, solved=True), 'ctfd')
        card = rendered['questions'][0]
        self.assertEqual(card['accepted'], [self.contract['accepted']['lead']])
        self.assertEqual(card['solved_by'], 'team-01')
        self.assertEqual(card['finding']['text'], 'a finding')
        unsolved = context(self.contract, snapshot([{'id': 'T01', 'status': 'active'}]),
                           questions_for(self.contract), 'ctfd')['questions'][0]
        self.assertEqual(unsolved['accepted'], [])
        self.assertEqual(unsolved['finding'], {'text': '', 'evidence': [], 'limitation': ''})

    def test_hints_carry_a_lead_in_per_level(self):
        card = context(self.contract, snapshot([{'id': 'T01', 'status': 'active'}]),
                       questions_for(self.contract), 'ctfd')['questions'][0]
        self.assertEqual(len(card['hints']), len(questions_for(self.contract)[0]['hints']))
        for number, hint in enumerate(card['hints'], 1):
            self.assertEqual(hint['level'], number)
            self.assertEqual(hint['lead'], self.contract['hints']['level_%s'
                                                            % ['one', 'two', 'three'][number - 1]])

    def test_why_this_question_matters_is_derived_not_authored(self):
        card = context(self.contract, snapshot([{'id': 'T01', 'status': 'active'}]),
                       questions_for(self.contract), 'ctfd')['questions'][0]
        tool = next(entry for entry in self.contract['tool_map'] if entry['surface'] == 'Wireshark')
        self.assertEqual(card['matters'], '%s %s: %s' % (self.contract['tickets']['T01']['stakes'],
                                                         tool['lane'], tool['text']))
        self.assertEqual(card['matters'], matters(self.contract, 'T01',
                                                  questions_for(self.contract)[0]))
        # No authored question carries this field, so it cannot be a second prose source.
        self.assertNotIn('matters', questions_for(self.contract)[0])
        unmapped = dict(questions_for(self.contract)[0], tool='Unmapped surface')
        self.assertEqual(matters(self.contract, 'T01', unmapped),
                         self.contract['tickets']['T01']['stakes'])

    def test_no_contract_section_leaks_a_scored_answer(self):
        answers = distinctive_answers(self.tickets)
        self.assertGreaterEqual(sum(len(ids) for ids in answers.values()), 50)
        exempt = {term.strip().lower() for term in self.contract['public_terms']}
        blob = (contract_blob(self.ctfd) + contract_blob(self.iris)).lower()
        for answer, question_ids in answers.items():
            if answer in exempt:
                continue
            self.assertNotIn(answer, blob, 'the narrative leaks the answer to %s' % question_ids)
        full = repr(self.ctfd) + repr(self.iris)
        for field in ('answer', 'digest'):
            self.assertNotIn("'%s'" % field, full)
        for path in ('facilitator/', 'ground-truth', 'solutions.md'):
            self.assertNotIn(path, full)
        card = self.ctfd['questions'][0]
        self.assertNotIn('answer', card)
        authored_body = set(questions_for(self.contract)[0])
        self.assertEqual(set(card) & authored_body, set(QUESTION_FIELDS) | {'finding', 'hints'},
                         'the assembler must copy named fields, never the whole body')

    def test_the_only_answers_in_the_context_are_the_authored_walkthrough_hints(self):
        # expanded/author.py:157 builds the level-3 hint as a full walkthrough that
        # states the value, and the page has always shown it inside a <details>.
        # The assembler must not add to that, so every answer present in the render
        # context has to be traceable to an authored hint body.
        blob = repr(self.ctfd).lower()
        authored_hints = '\n'.join(hint.lower()
                                   for ticket in self.tickets
                                   for question in ticket['questions']
                                   for hint in question['hints'])
        found = [answer for answer in distinctive_answers(self.tickets) if answer in blob]
        self.assertTrue(found, 'the walkthrough hints are the expected known exception')
        for answer in found:
            self.assertIn(answer, authored_hints,
                          'the context states %r outside an authored walkthrough hint' % answer)

    def test_template_references_every_key_the_assembler_emits(self):
        names = template_names()
        for rendered in (self.ctfd, self.iris):
            for key in context_names(rendered):
                self.assertIn(key, names, 'the template never renders %r' % key)
        paths = template_paths()
        for path in ('briefing.codename', 'briefing.classification_line', 'briefing.fiction_notice',
                     'briefing.premise', 'briefing.discovery', 'briefing.stakes',
                     'role.name', 'role.duty', 'role.authority', 'role.not',
                     'tool.surface', 'tool.lane', 'tool.text',
                     'phase.id', 'phase.title', 'phase.timeframe', 'phase.purpose',
                     'phase.urgency', 'phase.action', 'phase.transition', 'phase.tickets',
                     'tn.phase_id', 'tn.phase_title', 'tn.phase_timeframe', 'tn.headline',
                     'tn.brief', 'tn.stakes', 'tn.why_now', 'tn.next', 'tn.phase_transition',
                     'tn.complete', 'ticket_complete.generic', 'ticket_complete.handoff',
                     'q.headline', 'q.brief', 'q.matters', 'q.next', 'q.phase_id', 'q.phase_title',
                     'q.complete', 'q.accepted', 'hint.level', 'hint.lead', 'hint.text',
                     'hints_policy', 'exercise_complete.done', 'exercise_complete.brief',
                     'exercise_complete.handoff', 'exercise_complete.residual',
                     'exercise_complete.scoring_note', 'boundaries.read_only',
                     'boundaries.no_credentials', 'boundaries.no_operational_detail',
                     'boundaries.fiction_repeat', 'boundaries.attribution'):
            self.assertIn(path, paths, 'the template no longer renders %s' % path)

    def test_lane_forms_and_disclosure_survive(self):
        self.assertIn("value=\"claim\"", PAGE)
        self.assertIn("value=\"release\"", PAGE)
        self.assertIn('name="csrf_token"', PAGE)
        self.assertIn('<details><summary>Help level {{hint.level}}', PAGE)
        self.assertIn('name="question"', PAGE)
        self.assertIn('name="answer"', PAGE)
        self.assertIn("fetch('/silent-ridge/status'", PAGE)
        self.assertNotIn('cdn', PAGE)
        self.assertNotIn('<script src=', PAGE)

    def test_unknown_lane_is_refused(self):
        with self.assertRaisesRegex(NarrativeError, 'unknown render lane'):
            context(self.contract, None, None, 'deck')

    def test_a_question_naming_no_ticket_is_refused(self):
        body = dict(questions_for(self.contract)[0])
        body['ticket'] = 'T99'
        with self.assertRaisesRegex(NarrativeError, 'names no known ticket'):
            question_narrative(self.contract, body, ticket_narrative(self.contract))

    def test_ticket_without_a_phase_is_refused(self):
        broken = copy.deepcopy(self.contract)
        broken['phases'][0]['tickets'].remove('T01')
        with self.assertRaisesRegex(NarrativeError, 'T01'):
            ticket_narrative(broken, None)


class NarrativePreflightTests(unittest.TestCase):
    def setUp(self):
        self.tickets = authored()
        self.contract = build(tickets=self.tickets)

    def test_a_clean_deployment_passes_and_names_the_contract(self):
        receipt = check_deployment()
        self.assertTrue(receipt['ready'])
        self.assertEqual(receipt['contract'], self.contract['contract'])
        self.assertEqual(receipt['tickets'], 20)
        self.assertEqual(receipt['phases'], 4)
        # The controller host holds expanded/, so the answer-leak guard really runs.
        self.assertEqual(receipt['leak_guard'], 'authored')

    def test_a_host_without_answers_reports_that_it_skipped_the_leak_guard(self):
        # The integration container ships no expanded/ on purpose, and that is the
        # host `python -m ridge.cli preflight` actually runs on.
        with patch.dict(sys.modules, {'expanded.author': None}):
            receipt = check_deployment()
        self.assertTrue(receipt['ready'])
        self.assertEqual(receipt['leak_guard'], 'fixture-only')
        self.assertEqual(receipt['tickets'], 20)
        with patch.dict(sys.modules, {'expanded.author': None}):
            broken = copy.deepcopy(self.contract)
            del broken['tickets']['T13']
            with self.assertRaisesRegex(NarrativeError, 'no narrative for T13'):
                check_deployment(write_contract(broken))

    def test_an_unsafe_contract_still_fails_without_the_render_check(self):
        broken = copy.deepcopy(self.contract)
        broken['tickets']['T01']['brief'] = 'The workstation WS-17 sent the brief out.'
        with self.assertRaisesRegex(ContractError, 'contains the answer to T01-Q1'):
            check_deployment(write_contract(broken))

    def test_preflight_proves_the_ending_and_accepted_text_before_the_run(self):
        closed = snapshot([{'id': tid, 'status': 'complete'}
                           for tid in sorted(self.contract['tickets'])])
        rendered = context(self.contract, closed, questions_for(self.contract, solved=True), 'ctfd')
        validate(rendered, self.contract['revision'])
        self.assertTrue(rendered['exercise_complete']['done'])
        self.assertEqual(rendered['questions'][0]['accepted'],
                         [self.contract['accepted']['lead']])
        broken = copy.deepcopy(self.contract)
        broken['exercise_complete']['residual'] = ''
        with self.assertRaisesRegex(NarrativeError, 'exercise completion is missing'):
            check_deployment(write_contract(broken))

    def test_a_missing_narrative_section_fails_loudly(self):
        for field in ('premise', 'discovery', 'stakes', 'fiction_notice',
                      'classification_line'):
            with self.subTest(field=field):
                broken = copy.deepcopy(self.contract)
                broken['exercise'][field] = '   '
                rendered = context(broken, None, None, 'ctfd')
                with self.assertRaisesRegex(NarrativeError,
                                            'the event briefing is missing %s' % field):
                    validate(rendered)

    def test_a_dropped_context_section_fails_loudly(self):
        rendered = context(self.contract, None, None, 'ctfd')
        for key in CONTEXT_KEYS:
            with self.subTest(key=key):
                with self.assertRaisesRegex(NarrativeError, 'render context is missing'):
                    validate({k: v for k, v in rendered.items() if k != key})

    def test_a_missing_ending_fails_loudly(self):
        broken = copy.deepcopy(self.contract)
        broken['exercise_complete']['residual'] = ''
        closed = snapshot([{'id': tid, 'status': 'complete'}
                           for tid in sorted(broken['tickets'])])
        with self.assertRaisesRegex(NarrativeError, 'exercise completion is missing'):
            validate(context(broken, closed, None, 'iris'), broken['revision'])

    def test_an_early_ending_fails_loudly(self):
        # A snapshot that is short, or still open, must never carry the ending.
        for rows in ([{'id': 'T01', 'status': 'complete'}],
                     [{'id': tid, 'status': 'complete' if tid == 'T01' else 'active'}
                      for tid in sorted(self.contract['tickets'])]):
            with self.subTest(rows=len(rows)):
                rendered = context(self.contract, snapshot(rows), None, 'ctfd')
                validate(rendered, self.contract['revision'])
                self.assertFalse(rendered['exercise_complete']['done'])
        # And a hand-built context that leaks it anyway is refused.
        rendered = context(self.contract, snapshot([{'id': 'T01', 'status': 'active'}]), None, 'ctfd')
        rendered['exercise_complete']['brief'] = 'You are done.'
        with self.assertRaisesRegex(NarrativeError, 'readable before the investigation closes'):
            validate(rendered)

    def test_a_question_without_an_explanation_fails_loudly(self):
        rendered = context(self.contract, None, questions_for(self.contract), 'ctfd')
        rendered['questions'][0]['matters'] = ''
        with self.assertRaisesRegex(NarrativeError, 'no explanation of why it matters'):
            validate(rendered)

    def test_an_absent_fixture_fails_with_the_contract_error(self):
        from ridge.scenario_contract import FIXTURE
        with self.assertRaisesRegex(ContractError, 'narrative contract not found'):
            check_deployment(FIXTURE.parents[1] / 'assets' / 'scenario-narrative-absent.json')

    def test_cli_preflight_runs_the_narrative_check(self):
        import ridge.cli
        from ridge.preflight import check as preflight_check
        self.assertIn('preflight', inspect.getsource(ridge.cli))
        self.assertEqual(preflight_check.__module__, 'ridge.preflight')
        self.assertIn('check_narrative', inspect.getsource(preflight_check))


# Everything the assembler derives from the contract, as opposed to the authored
# question body it copies verbatim. The answer-leak check looks only here.
CONTRACT_SECTIONS = ('briefing', 'roles', 'tool_map', 'phases', 'narrative_tickets',
                     'hints_policy', 'accepted', 'ticket_complete', 'exercise_complete',
                     'boundaries')
CARD_CONTRACT_FIELDS = ('headline', 'brief', 'next', 'matters', 'phase_id', 'phase_title',
                        'accepted')


def contract_blob(rendered):
    parts = [repr(rendered[key]) for key in CONTRACT_SECTIONS]
    for card in rendered['questions']:
        parts.append(repr({field: card[field] for field in CARD_CONTRACT_FIELDS}))
        parts.append(repr([hint['lead'] for hint in card['hints']]))
    return '\n'.join(parts)


def sourced(token, source):
    """True when a rendered value is the fixture's own text, verbatim or composed."""
    if token in source:
        return True
    return all(word.strip('.,;:-—') in source for word in token.split(' ') if word)


def rendered_strings(value):
    """Every participant-facing string in a rendered section, short tokens included.

    Prose is composed by joining contract strings, so a value counts as sourced
    when it appears in the fixture verbatim or as a space-joined run of strings
    that do.
    """
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, dict):
        return [token for item in value.values() for token in rendered_strings(item)]
    if isinstance(value, list):
        return [token for item in value for token in rendered_strings(item)]
    return []


def contract_text(contract):
    """The approved fixture as text, so identity values count as sourced too."""
    return json.dumps(contract, indent=1, sort_keys=True)


if __name__ == '__main__':
    unittest.main()
