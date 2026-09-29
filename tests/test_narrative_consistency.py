"""Deterministic tests for cross-surface narrative consistency (issue 60).

``ridge.narrative_consistency`` is the check that the five participant-facing
surfaces - the CTFd question page, the IRIS incident queue, the event-day deck,
the T01 network map and the evidence breadcrumbs - still tell one story. The other
four issues in this track wrote the content and the renderers; this one is what
stops the next edit from quietly reopening the gap between them.

So this file is mostly negative. A validator with no failing test is not a
validator, and each guard here is proved by building the broken case and asserting
the named failure, not merely by observing that the clean tree passes. The
positive tests exist to say what a pass is worth: the receipt has to be
deterministic, it has to name every surface it proved, and it has to say which
surfaces a host could not prove.

No CTFd, IRIS, Docker, browser, network, database or clock is required. The
fixtures, the deck sources and the generated evidence inventory are all committed.
"""
import copy
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ridge import deck_narrative, scenario_contract, web_narrative
from ridge import narrative_consistency as nc
from ridge.narrative_consistency import (
    CANON, LEAK_PATTERNS, NGRAM, SECTION_PLAN, ConsistencyError, Span, Survey,
)
from ridge.scenario import RELEASE_FILES

ROOT = Path(__file__).resolve().parents[1]

# A T09 answer. T09's evidence arrives on T09's unlock, so it is not readable from
# the tree a team can see when the map appears: the value the map's evidence rule
# is supposed to refuse. distinctive_answers lowercases, so the constant does too.
FOLLOW_UP_ANSWER = '10:30-11:30z'
FOLLOW_UP_QUESTION = 'T09-Q3'
# A T19 answer the map really does project, as a published record value.
RECORD_VALUE = '09:06:00'

# Reading every surface costs a couple of seconds and the guards all work on the
# same read, so it is built once, here, and copied rather than rebuilt per test.
_CACHE = {}


def authored():
    from expanded.author import build as author
    return author()


def shared():
    if not _CACHE:
        tickets = authored()
        contract = scenario_contract.build(tickets=tickets)
        _CACHE.update(tickets=tickets, contract=contract,
                      survey=nc.survey(contract, tickets, 'authored'))
    return _CACHE


class SurveyTests(unittest.TestCase):
    """One survey for the whole module, copied so a broken case never leaks."""

    @classmethod
    def setUpClass(cls):
        shared()

    @property
    def tickets(self):
        return _CACHE['tickets']

    @property
    def contract(self):
        return _CACHE['contract']

    @property
    def survey(self):
        return _CACHE['survey']

    def copy(self, **overrides) -> Survey:
        found = copy.copy(self.survey)
        found.spans = dict(self.survey.spans)
        found.absent = dict(self.survey.absent)
        found.contexts = dict(self.survey.contexts)
        found.expected = set(self.survey.expected)
        found.unproved = []
        for key, value in overrides.items():
            setattr(found, key, value)
        return found

    def plant(self, surface, text, file='assets/scenario-narrative-v1.json', line=1,
              kind='prose') -> Span:
        return Span(surface, file, line, text, text, kind)

    def fails(self, problems, pattern):
        """A guard returned these problems; the named one has to be among them."""
        joined = '\n'.join(problems)
        self.assertIsNotNone(re.search(pattern, joined),
                             'expected %r in:\n%s' % (pattern, joined or '(no problems)'))
        return joined

    def assertNothingWrong(self, found):
        problems = []
        for name in nc.GUARDS:
            problems += nc.run_guard(name, found)
        self.assertEqual(problems, [])

    def closed(self):
        return {'mode': 'running', 'team': 'team-01', 'pending': 0, 'elapsed_seconds': 0,
                'announcements': [],
                'tickets': [{'id': tid, 'status': 'complete'}
                            for tid in sorted(self.contract['tickets'])]}


class CleanTreeTests(SurveyTests):
    """What a pass is worth."""

    def test_the_clean_tree_passes_and_names_every_surface(self):
        result = nc.validate(found=self.copy())
        self.assertTrue(result['consistent'])
        self.assertEqual(result['contract'], scenario_contract.CONTRACT_ID)
        self.assertEqual(result['revision'], self.contract['revision'])
        for surface in ('contract', 'ctfd', 'iris', 'deck', 'map', 'breadcrumbs', 'handout',
                        'web-template'):
            self.assertIn(surface, result['surfaces'])
        self.assertEqual(result['surfaces_not_proved'], {})
        self.assertEqual(result['not_proved'], [])
    def test_the_receipt_is_deterministic(self):
        first = nc.validate(found=self.copy())
        second = nc.validate(found=nc.survey(self.contract, self.tickets, 'authored'))
        self.assertEqual(json.dumps(first, sort_keys=True), json.dumps(second, sort_keys=True))
        # No absolute path and no clock: the receipt is a function of the tree.
        again = nc.check_deployment()
        self.assertNotIn(str(ROOT), json.dumps(again))
        self.assertNotIn('generated_at', again)
        self.assertEqual(first['sha256'], again['sha256'])

    def test_the_receipt_reports_the_contract_questions_it_guards(self):
        result = nc.validate(found=self.copy())
        self.assertEqual(result['answers_guarded'],
                         sum(len(ids) for ids
                             in scenario_contract.distinctive_answers(self.tickets).values()))
        self.assertGreaterEqual(result['answers_guarded'], 50)
        self.assertEqual(result['leak_guard'], 'authored')
        self.assertEqual(result['initial_evidence_files'], 25)
        self.assertEqual(result['follow_up_evidence_files'], 8)
        self.assertEqual(result['deck_slides_regenerated'], 15)

    def test_every_section_is_carried_by_the_surface_that_owes_it(self):
        carriers = nc.validate(found=self.copy())['sections']
        for section, lane_key, wanted in SECTION_PLAN:
            if lane_key is not None:
                self.assertIn(section, carriers['ctfd'], section)
                self.assertIn(section, carriers['iris'], section)
            if wanted is not None:
                self.assertIn(section, carriers['deck'], section)
        # The deck is the projection set, so it owes the whole exercise narrative;
        # a question page owes what a participant reads mid-investigation.
        for section in ('exercise.exposure', 'exercise.escalation', 'exercise.outcome', 'aar'):
            self.assertIn(section, carriers['deck'])
            self.assertNotIn(section, carriers['ctfd'])
        self.assertIn('exercise.fiction_notice', carriers['ctfd'])
        self.assertNotIn('exercise.fiction_notice', carriers['deck'])


class CanonTests(SurveyTests):
    """The fictional entity registry is pinned to the files that declare canon."""

    def test_every_declared_entity_still_appears_where_it_is_declared(self):
        self.assertEqual(nc.check_canon(self.copy()), [])
        self.assertEqual(sum(len(entries) for entries in CANON.values()), 26)
        for category, entries in CANON.items():
            for name, sources in entries.items():
                for source in sources:
                    with self.subTest(entity=name, source=source.name):
                        self.assertIn(name, source.read_text(encoding='utf-8'))

    def test_an_entity_that_leaves_its_canon_file_fails(self):
        moved = dict(CANON['host'], **{'WS-17': (ROOT / 'README.md',)})
        with patch.dict(CANON, {'host': moved}):
            self.fails(nc.check_canon(self.copy()),
                       r'canon: host WS-17 no longer appears in README.md')

    def test_a_canon_file_that_is_absent_is_reported_not_proved(self):
        moved = dict(CANON['host'], **{'WS-31': (ROOT / 'facilitator/absent.md',)})
        found = self.copy()
        with patch.dict(CANON, {'host': moved}):
            self.assertEqual(nc.check_canon(found), [])
        self.fails(found.unproved, 'canon: host WS-31 is declared by facilitator/absent.md')

    def test_the_registry_is_pinned_to_the_files_the_issue_names(self):
        sources = {source for entries in CANON.values() for pair in entries.values()
                   for source in pair}
        self.assertIn(ROOT / 'scripts/generate.py', sources)
        self.assertIn(ROOT / 'facilitator/ground-truth.md', sources)
        glossary = (ROOT / 'scripts/generate.py').read_text(encoding='utf-8')
        # The collection handout glossary, scripts/generate.py:74-90, is where the
        # host, service, account and document names are declared to participants.
        block = glossary.split("'''# Collection and scope", 1)[1].split("'''", 1)[0]
        for name in ('WS-17', 'WS-22', 'DOCS-1', 'IDP-1', 'm.ellis', 'r.chen', 'svc-index',
                     'plan-v3', 'plan-v4', 'roster-v2'):
            with self.subTest(glossary=name):
                self.assertIn(name, block)
        # The patrol, sector and check-in word are declared by the plan content the
        # same generator writes, a few lines above the handout.
        plan = glossary.split('plan = ', 1)[1].split("\n", 1)[0]
        for name in ('LANTERN', 'AMBER', 'CEDAR'):
            with self.subTest(plan=name):
                self.assertIn(name, plan)
        ground = (ROOT / 'facilitator/ground-truth.md').read_text(encoding='utf-8')
        for name in ('WS-31', 'S-41', 'brief-viewer.exe', 'CEDAR', 'LANTERN', 'BriefSync',
                     'AMBER'):
            with self.subTest(ground_truth=name):
                self.assertIn(name, ground)


class EntityTests(SurveyTests):
    """A name a participant can read is canon, spelled the one declared way."""

    def test_every_name_in_participant_content_is_declared_canon(self):
        self.assertEqual(nc.check_entities(self.copy()), [])

    def test_an_undeclared_workstation_is_a_failure(self):
        found = self.copy(spans=dict(self.survey.spans,
                                     deck=self.survey.spans['deck'] + [self.plant(
                                         'deck', 'The claim is about WS-42 and nothing else.',
                                         'docs/event-day-deck/pages/03_stakes.page', 40)]))
        joined = self.fails(nc.check_entities(found), r"WS-42' is not a declared host")
        self.assertIn('deck: docs/event-day-deck/pages/03_stakes.page:40', joined)

    def test_a_misspelt_sector_is_a_failure(self):
        found = self.copy(spans=dict(self.survey.spans,
                                     handout=self.survey.spans['handout'] + [self.plant(
                                         'handout', 'The superseded brief named the Amber sector.',
                                         'participants/handover.md', 12)]))
        self.fails(nc.check_entities(found), 'AMBER is spelled differently here')

    def test_the_guard_only_recognises_the_shapes_the_registry_declares(self):
        # A documented limit rather than a gap in disguise: the guard sees a token
        # that reads as a name in this fiction because it matches one of
        # ENTITY_PATTERNS. That is why the registry is pinned to canon, and why
        # adding a new shape means adding a pattern and a negative test.
        for category, pattern in nc.ENTITY_PATTERNS:
            names = CANON[category]
            with self.subTest(category=category, pattern=pattern.pattern):
                self.assertTrue(any(pattern.search(name) for name in names), pattern.pattern)
        invented = Span('handout', 'participants/handover.md', 12,
                        'A wholly invented label with no shape the registry knows.',
                        'A wholly invented label with no shape the registry knows.')
        found = self.copy(spans=dict(self.survey.spans,
                                     handout=self.survey.spans['handout'] + [invented]))
        self.assertEqual(nc.check_entities(found), [])

    def test_a_misspelt_name_is_a_failure_and_not_a_variation(self):
        found = self.copy(spans=dict(self.survey.spans,
                                     handout=self.survey.spans['handout'] + [self.plant(
                                         'handout', 'The clerk signs in from ws-17 every morning.',
                                         'participants/cells.md', 14)]))
        self.fails(nc.check_entities(found), 'WS-17 is spelled differently here')

    def test_a_lower_case_patrol_name_is_a_failure(self):
        found = self.copy(spans=dict(self.survey.spans,
                                     handout=self.survey.spans['handout'] + [self.plant(
                                         'handout', 'A short note about the lantern movement.',
                                         'participants/cells.md', 14)]))
        self.fails(nc.check_entities(found), 'LANTERN is spelled differently here')

    def test_a_name_filed_under_the_wrong_category_is_a_failure(self):
        moved = dict(CANON['document'], **{'WS-17': CANON['host']['WS-17']})
        with patch.dict(CANON, {'document': moved}):
            self.fails(nc.check_entities(self.copy()),
                       "'WS-17' is declared as a document but reads as a host")

    def test_the_deck_theme_token_is_not_the_sector(self):
        # ``$amber`` is the colour on every generated slide. If the spelling test
        # cannot tell it from sector AMBER it is useless on a real surface.
        source = (nc.DECK_PAGES / '03_stakes.page').read_text(encoding='utf-8')
        self.assertIn('$amber', source)
        found = self.copy(spans=dict(
            self.survey.spans,
            deck=self.survey.spans['deck'] + [self.plant(
                'deck', 'Set the accent to $amber and the title to $ink.', 'x.page', 1)]))
        self.assertEqual(nc.check_entities(found), [])
        variants = {name: re.compile('(?<![$\\w.\\-/])%s(?![$\\w.\\-/])' % re.escape(name),
                                     re.IGNORECASE) for name in ('AMBER', 'CEDAR')}
        for name, pattern in variants.items():
            with self.subTest(theme_token=name):
                self.assertIsNone(pattern.search('$amber'), name)

    def test_the_ordinary_english_reading_of_a_name_is_not_a_variant(self):
        # "In this exercise it is documentation space" is not a misspelt Exercise IT.
        found = self.copy(spans=dict(
            self.survey.spans,
            map=self.survey.spans['map'] + [self.plant(
                'map', 'In this exercise it is documentation space and nothing answers.',
                'assets/t01-network-map-v1.json', 29)]))
        self.assertEqual(nc.check_entities(found), [])

    def test_the_entity_scan_covers_the_map_and_the_breadcrumbs_too(self):
        for surface, fixture in (('map', 'assets/t01-network-map-v1.json'),
                                 ('breadcrumbs', 'assets/breadcrumbs-v1.json'),
                                 ('handout', 'participants/cells.md'),
                                 ('web-template', 'ridge/web.py')):
            with self.subTest(surface=surface):
                found = self.copy(spans=dict(
                    self.survey.spans,
                    **{surface: self.survey.spans[surface] + [self.plant(
                        surface, 'A note left beside WS-44 with no other context.',
                        fixture, 12)]}))
                self.fails(nc.check_entities(found), r"WS-44' is not a declared host")

    def test_the_guard_fires_through_the_aggregate_entry_point(self):
        found = self.copy(spans=dict(self.survey.spans,
                                     handout=self.survey.spans['handout'] + [self.plant(
                                         'handout', 'One more host, WS-42, to rule out.',
                                         'participants/cells.md', 14)]))
        with self.assertRaisesRegex(ConsistencyError, 'WS-42'):
            nc.validate(found=found)


class SectionTests(SurveyTests):
    """Every required section exists, non-empty, on the surface that renders it."""

    def test_an_emptied_required_contract_section_fails(self):
        for field in scenario_contract.REQUIRED_EXERCISE_FIELDS:
            with self.subTest(field=field):
                broken = copy.deepcopy(self.contract)
                broken['exercise'][field] = '   '
                self.fails(nc.check_sections(self.copy(contract=broken)),
                           'exercise.%s is a required section and is empty' % field)

    def test_a_lane_that_drops_a_section_fails(self):
        broken = copy.deepcopy(self.contract)
        broken['exercise']['premise'] = '   '
        context = web_narrative.context(broken, self.closed(), None, 'ctfd')
        found = self.copy(contexts=dict(self.survey.contexts, ctfd=context))
        self.fails(nc.check_sections(found), r'ctfd: does not render exercise.premise')

    def test_a_lane_that_drops_the_ending_fails(self):
        broken = copy.deepcopy(self.contract)
        broken['exercise_complete'] = dict(broken['exercise_complete'], residual='')
        context = web_narrative.context(broken, self.closed(), None, 'iris')
        found = self.copy(contexts=dict(self.survey.contexts, iris=context))
        self.fails(nc.check_sections(found), 'iris: does not render exercise_complete')

    def test_a_lane_that_drops_a_ticket_section_fails(self):
        broken = copy.deepcopy(self.contract)
        broken['tickets']['T13'] = dict(broken['tickets']['T13'], brief='')
        context = web_narrative.context(broken, self.closed(), None, 'ctfd')
        found = self.copy(contexts=dict(self.survey.contexts, ctfd=context))
        self.fails(nc.check_sections(found), r'tickets \(T13\.brief\)')

    def test_a_lane_that_loses_a_whole_section_key_is_a_failure(self):
        context = copy.deepcopy(self.survey.contexts['ctfd'])
        del context['boundaries']
        found = self.copy(contexts=dict(self.survey.contexts, ctfd=context))
        self.fails(nc.check_sections(found), r'ctfd: does not render boundaries')

    def test_a_deck_that_stops_projecting_a_required_section_fails(self):
        class Truncated:
            """The real deck with one contract reference taken out."""

            def __init__(self, deck, dropped):
                self.root = deck.root
                self._refs = {ref for ref in deck.refs() if ref != dropped}

            def refs(self):
                return self._refs

        for dropped in ('exercise.exposure', 'aar.close', 'boundaries.attribution',
                        'phases.phase-2.action', 'roles.soc-analyst.duty'):
            with self.subTest(dropped=dropped):
                found = self.copy(deck=Truncated(self.survey.deck, dropped))
                self.fails(nc.check_sections(found), re.escape(dropped))

    def test_a_deck_that_projects_nothing_fails(self):
        class Empty:
            root = nc.DECK_DIR

            @staticmethod
            def refs():
                return set()

        found = self.copy(deck=Empty())
        joined = self.fails(nc.check_sections(found), 'never projects')
        self.assertIn('exercise.premise', joined)

    def test_a_section_with_no_carrier_on_this_host_is_reported_not_proved(self):
        # The integration container holds the contract and nothing else. The four
        # sections only the deck owes then have no carrier, and that has to be
        # reported rather than failed, or the check could never run there.
        found = self.copy()
        found.deck = None
        found.absent = dict(found.absent, deck='not shipped in this image')
        found.spans = {name: spans for name, spans in found.spans.items() if name != 'deck'}
        self.assertEqual(nc.check_sections(found), [])
        joined = '\n'.join(found.unproved)
        for section in ('exercise.exposure', 'exercise.escalation', 'exercise.outcome', 'aar'):
            with self.subTest(section=section):
                self.assertIn(section, joined)


class LineageTests(SurveyTests):
    """Every surface names the contract revision it renders."""

    def test_all_five_surfaces_declare_the_same_contract_revision(self):
        self.assertEqual(nc.check_lineage(self.copy()), [])
        lineage = nc.validate(found=self.copy())['lineage']
        self.assertEqual(sorted(lineage), ['breadcrumbs', 'ctfd', 'deck', 'iris', 'map'])
        self.assertEqual(set(lineage.values()), {self.contract['revision']})

    def test_a_fixture_written_against_an_older_revision_fails(self):
        for name in ('map', 'breadcrumbs'):
            with self.subTest(surface=name):
                self.fails(self.lineage_problems(name, {'revision': 0}),
                           'was written against narrative revision 0')

    def test_a_fixture_with_no_lineage_block_fails(self):
        for name in ('map', 'breadcrumbs'):
            with self.subTest(surface=name):
                self.fails(self.lineage_problems(name, None),
                           'declares no narrative_contract block')

    def test_a_fixture_naming_another_contract_fails(self):
        for name in ('map', 'breadcrumbs'):
            with self.subTest(surface=name):
                self.fails(self.lineage_problems(name, {'contract': 'something-else'}),
                           "names contract 'something-else'")

    def test_a_fixture_missing_from_this_host_is_reported_not_proved(self):
        for name in ('map', 'breadcrumbs'):
            with self.subTest(surface=name):
                found = self.copy()
                with patch.object(nc, 'MAP_FIXTURE' if name == 'map' else 'BREADCRUMB_FIXTURE',
                                  ROOT / 'assets/absent.json'):
                    self.assertEqual(nc.check_lineage(found), [])
                self.assertIn('%s: assets/absent.json is not on this host' % name,
                              '\n'.join(found.unproved))

    def lineage_problems(self, name, block):
        """The lineage problems for a fixture whose provenance block is replaced."""
        module = 'ridge.network_map' if name == 'map' else 'ridge.breadcrumbs'
        attribute = 'build' if name == 'map' else 'load'
        original = getattr(__import__(module, fromlist=['x']), attribute)()
        broken = copy.deepcopy(original)
        if block is None:
            broken.pop('narrative_contract', None)
        else:
            broken['narrative_contract'] = dict(original['narrative_contract'], **block)
        found = self.copy()
        with patch('%s.%s' % (module, attribute), return_value=broken):
            problems = nc.check_lineage(found)
        return problems


class ProvenanceTests(SurveyTests):
    """Exact drift: the committed and the regenerated surfaces are the same bytes."""

    def test_the_committed_deck_is_what_the_contract_generates(self):
        self.assertEqual(nc.check_provenance(self.copy()), [])
        generated = deck_narrative.generate(self.contract)
        self.assertEqual(sorted(generated), sorted(deck_narrative.GENERATED))
        for name, source in generated.items():
            directory = 'facilitator-pages' if name.startswith('f') else 'pages'
            with self.subTest(page=name):
                self.assertEqual((nc.DECK_DIR / directory / name).read_text(encoding='utf-8'),
                                 source)

    def test_a_hand_edited_contract_slide_fails(self):
        broken = dict(deck_narrative.generate(self.contract))
        broken['02_brief.page'] = broken['02_brief.page'].replace('fictional field unit',
                                                                  'fictional field unit, roughly')
        with patch.object(deck_narrative, 'generate', return_value=broken):
            self.fails(nc.check_provenance(self.copy()),
                       r'deck: docs/event-day-deck/pages/02_brief.page:1 does not match')

    def test_a_generated_slide_that_is_not_committed_fails(self):
        target = nc.DECK_PAGES / '22_close.page'
        backup = target.read_text(encoding='utf-8')
        try:
            target.unlink()
            self.fails(nc.check_provenance(self.copy()),
                       '22_close.page is generated from the contract but is not committed')
        finally:
            target.write_text(backup, encoding='utf-8', newline='\n')

    def test_a_render_context_value_that_is_not_the_contract_fails(self):
        context = copy.deepcopy(self.survey.contexts['ctfd'])
        context['briefing'] = dict(context['briefing'],
                                   premise='A fictional document service holds the briefs.')
        found = self.copy(contexts=dict(self.survey.contexts, ctfd=context))
        self.fails(nc.check_provenance(found), 'is not the contract wording')

    def test_a_composed_value_the_renderer_produces_is_accepted(self):
        # The assembler composes "stakes + tool note"; that has to keep passing, or
        # the guard is demanding the impossible from every future renderer.
        values = nc.contract_values(self.contract)
        for lane in ('ctfd', 'iris'):
            for value in nc._rendered_values(self.survey.contexts[lane]):
                with self.subTest(lane=lane, value=value[:40]):
                    self.assertTrue(nc._composed(value, values), value)

    def test_the_guard_fires_through_the_aggregate_entry_point(self):
        context = copy.deepcopy(self.survey.contexts['iris'])
        context['phases'] = [dict(context['phases'][0], purpose='A sentence of its own.')]
        found = self.copy(contexts=dict(self.survey.contexts, iris=context))
        with self.assertRaisesRegex(ConsistencyError, 'is not the contract wording'):
            nc.validate(found=found)


class RestatementTests(SurveyTests):
    """No surface may restate the contract in words of its own."""

    def test_no_surface_restates_the_contract(self):
        self.assertEqual(nc.check_restatement(self.copy()), [])

    def test_the_guard_only_sees_sections_long_enough_to_restate(self):
        long_enough = {field for field, text in scenario_contract.narrative_strings(self.contract)
                       if len(nc.words(text)) >= NGRAM}
        self.assertGreaterEqual(len(long_enough), 40)
        # A section shorter than the window cannot share the window, so the guard
        # never claims coverage it does not have.
        for field, text in scenario_contract.narrative_strings(self.contract):
            if len(nc.words(text)) < NGRAM:
                with self.subTest(field=field):
                    self.assertEqual(nc.ngrams(text), set())

    def test_a_restated_sentence_is_named_with_its_surface_file_and_line(self):
        restated = ('An access review after a routine credential change noticed that one '
                    'document had been fetched and re-used outside its normal pattern on the '
                    'same morning, while the same session was refreshed.')
        found = self.copy(spans=dict(
            self.survey.spans,
            handout=self.survey.spans['handout'] + [self.plant(
                'handout', restated, 'participants/handover.md', 6)]))
        joined = self.fails(nc.check_restatement(found), 'restates exercise.discovery')
        self.assertIn('handout: participants/handover.md:6', joined)

    def test_the_guards_own_wording_is_still_accepted(self):
        # The contract value itself, rendered on a slide, is not a restatement.
        found = self.copy(spans=dict(
            self.survey.spans,
            deck=self.survey.spans['deck'] + [self.plant('deck', self.contract['exercise']
                                                        ['discovery'], 'x.page', 1)]))
        self.assertEqual(nc.check_restatement(found), [])

    def test_a_record_value_on_the_map_is_not_prose(self):
        # The map's edge timestamps are drawn from published records, and a value
        # that happens to be a scored answer is evidence rather than a sentence.
        kinds = {span.kind for span in self.survey.spans['map']}
        self.assertEqual(kinds, {'prose', 'data'})
        for span in self.survey.spans['map']:
            if span.kind == 'data':
                with self.subTest(value=span.text):
                    self.assertNotIn(span, nc.check_restatement(self.copy()))


class ToolTests(SurveyTests):
    """Every tool the issue names is placed, and the deck names the contract's set."""

    def test_every_tool_the_issue_names_is_placed(self):
        self.assertEqual(nc.check_tools(self.copy()), [])
        coverage = nc.tool_coverage(self.copy())
        for tool in ('IRIS', 'CTFd', 'Wazuh', 'Guacamole', 'Wireshark', 'Autopsy',
                     'the prepared evidence'):
            with self.subTest(tool=tool):
                self.assertTrue(coverage[tool], tool)
                for place in coverage[tool]:
                    surface, where, line = place.rsplit(':', 2)
                    self.assertIn(surface, self.survey.spans)
                    self.assertTrue((ROOT / where).is_file(), where)
                    self.assertGreater(int(line), 0)

    def test_a_tool_nobody_explains_fails(self):
        without = {name: [span for span in spans if 'Guacamole' not in span.text]
                   for name, spans in self.survey.spans.items()}
        self.fails(nc.check_tools(self.copy(spans=without)),
                   'Guacamole is never explained in participant-facing content')

    def test_a_bare_mention_is_not_an_explanation(self):
        # A tool name on its own is navigation. The passage has to say what it is
        # for, or a participant still cannot place the tool.
        found = self.copy(spans=dict(
            self.survey.spans,
            deck=self.survey.spans['deck'] + [self.plant('deck', 'Guacamole', 'x.page', 1)]))
        self.assertIn('deck:docs/event-day-deck/pages/15_step3.page:30',
                      nc.tool_coverage(found)['Guacamole'])
        stripped = {name: [span for span in spans if 'Guacamole' not in span.text]
                    for name, spans in found.spans.items()}
        self.fails(nc.check_tools(self.copy(spans=stripped)),
                   'Guacamole is never explained')

    def test_a_contract_tool_the_deck_never_names_fails(self):
        # The deck's tool table is one element, so the whole element has to go, not
        # just the row that names the tool.
        without = {name: [span for span in spans if 'Cutter' not in span.unit]
                   for name, spans in self.survey.spans.items()}
        self.fails(nc.check_tools(self.copy(spans=without)),
                   "deck: never names 'Cutter'")

    def test_the_decks_short_name_for_a_contract_tool_is_declared_not_a_variation(self):
        # The deck's table says "File manager"; the contract says "Linux file
        # manager". That is a declared alias, and the guard has to accept it.
        self.assertEqual(nc.TOOL_ALIASES, {'File manager': 'Linux file manager'})
        text = '\n'.join(span.unit for span in self.survey.spans['deck'])
        self.assertIn('File manager', text)
        self.assertNotIn('Linux file manager', text)
        self.assertEqual(nc.check_tools(self.copy()), [])

    def test_a_tool_that_only_a_missing_surface_explained_is_not_proved_not_wrong(self):
        found = self.copy()
        found.deck = None
        found.absent = dict(found.absent, deck='not shipped in this image')
        found.spans = {name: [span for span in spans if 'Guacamole' not in span.text]
                       for name, spans in found.spans.items() if name != 'deck'}
        self.assertEqual(nc.check_tools(found), [])
        self.assertIn('Guacamole is never explained in participant-facing content',
                      '\n'.join(found.unproved))


class LeakageTests(SurveyTests):
    """No answer key, credential, facilitator path or deployment detail, anywhere."""

    def test_no_surface_carries_one(self):
        self.assertEqual(nc.check_leakage(self.copy()), [])

    def test_the_scan_covers_every_surface_the_branches_added(self):
        for surface in ('contract', 'ctfd', 'iris', 'deck', 'breadcrumbs', 'handout',
                        'web-template'):
            with self.subTest(surface=surface):
                fixture = {'breadcrumbs': 'assets/breadcrumbs-v1.json'}.get(
                    surface, 'docs/event-day-deck/pages/03_stakes.page')
                found = self.copy(spans=dict(
                    self.survey.spans,
                    **{surface: self.survey.spans[surface] + [self.plant(
                        surface, 'The answer is WS-17, taken straight from the record.',
                        fixture, 20)]}))
                self.fails(nc.check_leakage(found), 'names the answer to T01-Q1')

    def test_the_map_is_held_to_the_evidence_rule_rather_than_the_narrative_one(self):
        # WS-17 is a T01 answer, T01 reads sensor.pcap, and that file is on the mount
        # from run start. The map may therefore name the workstation, in a label or
        # in a sentence, without becoming a spoiler - the map only appears once T01
        # is closed. What it may not do is state a value whose record has not been
        # published yet, which is the other half of this class of test below.
        drawn = [span for span in self.survey.spans['map'] if 'WS-17' in span.text]
        self.assertTrue(drawn, 'the map should still name the workstation')
        self.assertEqual(nc.check_leakage(self.copy()), [])
        self.assertEqual(self.map_leak_problems(
            'The workstation that sent the brief was WS-17, and no record disputes it.'), [])

    def test_a_planted_answer_in_the_contract_is_a_failure(self):
        found = self.copy(spans=dict(
            self.survey.spans,
            contract=self.survey.spans['contract'] + [self.plant(
                'contract', 'The transfer left the estate towards 198.51.100.77 that morning.',
                'assets/scenario-narrative-v1.json', 40)]))
        self.fails(nc.check_leakage(found), 'names the answer to T01-Q4')

    def test_a_public_term_stays_exempt_because_it_is_already_visible(self):
        # LANTERN, AMBER, S-41 and WS-22 are in the fixture's public_terms, so a
        # passage naming one is not a leak. That exemption is load-bearing.
        exempt = scenario_contract.public_terms(self.contract)
        self.assertEqual(sorted(exempt), ['amber', 'lantern', 's-41', 'ws-22'])
        found = self.copy(spans=dict(
            self.survey.spans,
            handout=self.survey.spans['handout'] + [self.plant(
                'handout', 'The cache names LANTERN and sector AMBER, both already public.',
                'participants/handover.md', 22)]))
        self.assertEqual(nc.check_leakage(found), [])

    def test_a_credential_assignment_is_a_failure(self):
        found = self.copy(spans=dict(
            self.survey.spans,
            deck=self.survey.spans['deck'] + [self.plant(
                'deck', 'Sign in with password: CorrectHorseBattery on the shared desktop.',
                'docs/event-day-deck/pages/15_step3.page', 30)]))
        self.fails(nc.check_leakage(found), 'carries a credential assignment')

    def test_a_password_hash_or_private_key_is_a_failure(self):
        for text, pattern in (('The hash is $2b$10$abcdefghijklmnopqrstuv for the account.',
                               'a password hash'),
                              ('-----BEGIN OPENSSH PRIVATE KEY-----\nbm9wdQ==',
                               'a private key block')):
            with self.subTest(text=text[:32]):
                found = self.copy(spans=dict(
                    self.survey.spans,
                    handout=self.survey.spans['handout'] + [self.plant(
                        'handout', text, 'participants/cells.md', 20)]))
                self.fails(nc.check_leakage(found), re.escape(pattern))

    def test_a_facilitator_only_path_is_a_failure(self):
        for needle in ('facilitator/ground-truth.md', 'expanded/author.py', 'solutions.md',
                       'EXPECTED_QUESTIONS'):
            with self.subTest(needle=needle):
                found = self.copy(spans=dict(
                    self.survey.spans,
                    handout=self.survey.spans['handout'] + [self.plant(
                        'handout', 'The real values are in ' + needle + ' if you want them.',
                        'participants/cells.md', 20)]))
                self.fails(nc.check_leakage(found), 'carries a facilitator-only path')

    def test_a_deployment_detail_is_a_failure(self):
        for text, pattern in (('The broker lives at 172.20.4.9 behind the proxy.',
                               'a private infrastructure address'),
                              ('Set RIDGE_EVIDENCE_PUBLIC before the run.',
                               'a deployment environment variable'),
                              ('The image is built from deployment/Dockerfile.integration.',
                               'a deployment build artefact'),
                              ('Connect to box.example.invalid to reach the jump host.',
                               'a deployment hostname')):
            with self.subTest(text=text):
                found = self.copy(spans=dict(
                    self.survey.spans,
                    handout=self.survey.spans['handout'] + [self.plant(
                        'handout', text, 'participants/cells.md', 20)]))
                self.fails(nc.check_leakage(found), re.escape(pattern))

    def test_the_exercise_estate_is_not_treated_as_infrastructure(self):
        # 10.26.0.0/16 is the fictional estate the collection handout publishes, and
        # the map draws it on purpose. Only other private space is infrastructure.
        drawn = [span for span in self.survey.spans['map']
                 if re.search(r'\b10\.26\.\d+\.\d+\b', span.text)]
        self.assertTrue(drawn, 'the map should still draw the fictional estate')
        for span in drawn:
            for pattern, description in LEAK_PATTERNS:
                with self.subTest(value=span.text[:40]):
                    self.assertIsNone(pattern.search(span.text), description)

    def test_an_adversary_name_is_a_failure_on_every_surface(self):
        for text, pattern in (('The Wraith team took the documents.', 'not in canon'),
                              ('An APT29 operator left the tool behind.', 'a group or a named tool'),
                              ('The work was sponsored by a unit outside the estate.',
                               'attributes a sponsor'),
                              ('A shadow network received the upload.', 'not in canon')):
            with self.subTest(text=text):
                for surface in ('contract', 'deck', 'map', 'breadcrumbs', 'handout'):
                    found = self.copy(spans=dict(
                        self.survey.spans,
                        **{surface: self.survey.spans[surface] + [self.plant(
                            surface, text, 'x.json', 1)]}))
                    self.fails(nc.check_leakage(found), pattern)

    def test_the_contract_itself_still_forbids_attribution(self):
        self.assertTrue(self.contract['exercise']['adversary']['rule'].strip())
        self.assertIn('sponsor', self.contract['boundaries']['attribution'])
        closing = next(question for ticket in self.tickets for question in ticket['questions']
                       if question['id'] == 'T20-Q4')
        self.assertEqual(closing['answer'], 'no')

    def test_the_map_refuses_a_value_only_a_follow_up_release_carries(self):
        answers = scenario_contract.distinctive_answers(self.tickets)
        self.assertIn(FOLLOW_UP_ANSWER, answers)
        self.assertIn(FOLLOW_UP_QUESTION, answers[FOLLOW_UP_ANSWER])
        evidence = next(question['evidence'] for ticket in self.tickets
                        for question in ticket['questions'] if question['id'] == FOLLOW_UP_QUESTION)
        self.assertIn(evidence.removeprefix('/evidence/'),
                      {name for names in RELEASE_FILES.values() for name in names})
        self.fails(self.map_leak_problems(
            'Version four specified the movement window ' + FOLLOW_UP_ANSWER + '.'),
            r'names the answer to T09-Q3, whose evidence is not published')

    def map_leak_problems(self, text):
        found = self.copy(spans=dict(
            self.survey.spans,
            map=self.survey.spans['map'] + [self.plant('map', text,
                                                       'assets/t01-network-map-v1.json', 40)]))
        return nc.check_leakage(found)

    def test_the_map_record_value_is_recorded_rather_than_waved_through(self):
        # One published record value is also a locked answer. It is listed with its
        # reason, it is proved to still be locked, and it is proved to still be on
        # the map, so a second value on the same reasoning would be a failure.
        self.assertEqual(nc.check_leakage(self.copy()), [])
        self.assertEqual(sorted(nc.KNOWN_RECORD_VALUES), [RECORD_VALUE])
        self.assertIn(RECORD_VALUE, nc.leak_receipt(self.copy())['record_values'])
        self.assertNotIn(RECORD_VALUE, nc._published_at_start(self.tickets,
                                                             nc._initial_evidence()))
        found = self.copy()
        with patch.dict(nc.KNOWN_RECORD_VALUES, {'09:20:00': 'invented'}, clear=True):
            self.fails(nc.check_leakage(found), 'remove the exception')

    def test_a_stale_record_value_exception_is_a_failure(self):
        with patch.dict(nc.KNOWN_RECORD_VALUES, {'01:02:03': 'invented'}, clear=True):
            self.fails(nc.check_leakage(self.copy()), 'which the map no longer shows')

    def test_the_leak_guard_reports_fixture_only_rather_than_pretending(self):
        found = self.copy(tickets=None, guard='fixture-only')
        self.assertEqual(nc.check_leakage(found), [])
        self.assertEqual(nc.leak_receipt(found)['questions_guarded'], 0)

    def test_the_guard_fires_through_the_aggregate_entry_point(self):
        found = self.copy(spans=dict(
            self.survey.spans,
            deck=self.survey.spans['deck'] + [self.plant(
                'deck', 'Everyone knows the session was S-42 from the start.',
                'docs/event-day-deck/pages/06_loop.page', 50)]))
        with self.assertRaisesRegex(ConsistencyError, 'is not a declared session'):
            nc.validate(found=found)


class SurfaceTests(SurveyTests):
    """A surface this host cannot read is named, never silently skipped."""

    def test_a_surface_that_is_absent_from_this_host_is_reported_not_proved(self):
        found = self.copy()
        found.expected.discard('deck')
        found.absent = dict(found.absent, deck='not shipped in this image')
        found.spans = {name: spans for name, spans in found.spans.items() if name != 'deck'}
        self.assertEqual(nc.check_surfaces(found), [])
        self.assertIn('deck was not proved on this host', '\n'.join(found.unproved))

    def test_a_surface_that_is_on_this_host_and_did_not_arrive_is_a_failure(self):
        # Otherwise a reader that quietly drops a surface would narrow the whole
        # check's coverage and still report a pass.
        found = self.copy(absent=dict(self.survey.absent, map='AttributeError: str'))
        self.fails(nc.check_surfaces(found),
                   r'surfaces: map was not proved on this host \(AttributeError')

    def test_a_surface_dropped_after_it_was_read_is_a_failure(self):
        found = self.copy()
        found.spans = {name: spans for name, spans in found.spans.items() if name != 'map'}
        self.fails(nc.check_surfaces(found), 'map is on this host and was not read')

    def test_the_container_shape_reads_as_a_degraded_pass_not_a_failure(self):
        # What the integration image actually carries: the contract, ridge/, and no
        # deck, map, breadcrumbs or handouts.
        found = self.copy()
        found.deck = None
        found.document = {}
        found.expected = {'contract', 'ctfd', 'iris', 'web-template'}
        for name in ('deck', 'map', 'breadcrumbs', 'handout'):
            del found.spans[name]
            found.absent[name] = 'not shipped in this image'
        self.assertEqual(nc.check_surfaces(found), [])
        result = nc.validate(found=found)
        self.assertTrue(result['consistent'])
        for surface in ('deck', 'map', 'breadcrumbs'):
            with self.subTest(surface=surface):
                self.assertIn(surface, result['surfaces_not_proved'])
                self.assertNotIn(surface, result['surfaces'])
                self.assertNotIn(surface, result['lineage'])
        self.assertIn('ctfd', result['surfaces'])
        self.assertTrue(result['not_proved'])

    def test_an_empty_surface_is_a_failure(self):
        found = self.copy()
        found.spans = dict(found.spans, handout=[])
        self.fails(nc.check_surfaces(found), 'handout produced no participant-facing text')

    def test_every_surface_on_a_full_checkout_is_expected_and_present(self):
        found = self.copy()
        self.assertEqual(found.expected, set(found.spans))
        self.assertEqual(found.absent, {})
        self.assertEqual(nc.receipt(found)['not_proved'], [])

    def test_a_host_that_lost_only_the_deck_still_passes(self):
        # A checkout with the deck tree removed but everything else in place. The
        # deck-only sections and the four tools the deck explains move to
        # ``not_proved``; nothing is failed and nothing is overclaimed.
        found = self.copy()
        found.deck = None
        found.expected.discard('deck')
        found.absent = dict(found.absent, deck='docs/event-day-deck/ is not on this host')
        found.spans = {name: spans for name, spans in found.spans.items() if name != 'deck'}
        result = nc.validate(found=found)
        self.assertTrue(result['consistent'])
        self.assertIn('deck', result['surfaces_not_proved'])
        self.assertNotIn('deck', result['surfaces'])
        self.assertIn('ctfd', result['surfaces'])
        joined = '\n'.join(result['not_proved'])
        self.assertIn('exercise.exposure', joined)
        self.assertIn('Guacamole', joined)


class DeterminismTests(SurveyTests):
    """The narrative is a pure function of committed bytes."""

    def test_every_narrative_source_is_tracked_and_hashed(self):
        self.assertEqual(nc.check_determinism(self.copy()), [])
        digests = nc.digests()
        for name in ('assets/scenario-narrative-v1.json', 'assets/t01-network-map-v1.json',
                     'assets/breadcrumbs-v1.json', 'ridge/web.py', 'scripts/generate.py',
                     'facilitator/ground-truth.md', 'expanded/author.py',
                     'docs/event-day-deck/pages/02_brief.page',
                     'docs/event-day-deck/facilitator-pages/f01_run_of_show.page',
                     'participants/handover.md', 'expanded/guides.md'):
            with self.subTest(source=name):
                self.assertIn(name, digests)
                self.assertRegex(digests[name], r'^[0-9a-f]{64}$')
        self.assertIn('facilitator/ground-truth.md', nc._tracked())

    def test_an_untracked_source_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            stray = Path(temporary) / 'scenario-narrative-v2.json'
            stray.write_text('{}', encoding='utf-8')
            with patch.object(nc, 'narrative_sources', return_value=[stray]):
                self.fails(nc.check_determinism(self.copy()), 'is not tracked by git')

    def test_a_source_that_is_absent_is_reported_not_proved(self):
        with patch.object(nc, 'narrative_sources',
                          return_value=[ROOT / 'assets/no-such-narrative.json']):
            found = self.copy()
            self.assertEqual(nc.check_determinism(found), [])
            self.assertIn('is not on this host', '\n'.join(found.unproved))

    def test_a_host_without_git_is_reported_not_proved(self):
        found = self.copy()
        with patch.object(nc, '_tracked', return_value=None):
            self.assertEqual(nc.check_determinism(found), [])
            self.assertIn('git is unavailable', '\n'.join(found.unproved))
            self.assertFalse(nc.receipt(found)['git_tracked'])
        self.assertTrue(nc.receipt(self.copy())['git_tracked'])

    def test_a_clean_install_reproduces_the_narrative_from_the_repository_alone(self):
        before = nc.digests()
        nc.validate(found=nc.survey(self.contract, self.tickets, 'authored'))
        self.assertEqual(before, nc.digests())


class EntryPointTests(SurveyTests):
    """One entry point, wired into the path the organizer already runs."""

    def test_preflight_runs_the_consistency_check(self):
        import inspect

        import ridge.cli
        import ridge.preflight
        source = inspect.getsource(ridge.preflight.check)
        self.assertIn('check_consistency', source)
        self.assertIn('check_narrative', source)
        self.assertIn('preflight', inspect.getsource(ridge.cli))
        self.assertEqual(ridge.preflight.check_consistency.__module__, 'ridge.preflight')
        self.assertTrue(ridge.preflight.check_consistency()['consistent'])

    def test_the_module_is_runnable_on_its_own(self):
        result = subprocess.run([sys.executable, '-m', 'ridge.narrative_consistency',
                                 '--receipt'], cwd=str(ROOT), capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout)['consistent'])

    def test_the_module_reports_a_failure_on_stderr_and_exits_nonzero(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'scenario-narrative-v1.json'
            path.write_text(json.dumps(self.broken_contract()), encoding='utf-8')
            result = subprocess.run([sys.executable, '-m', 'ridge.narrative_consistency',
                                     '--contract', str(path)], cwd=str(ROOT),
                                    capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn('failed', result.stderr)
        self.assertEqual(result.stdout, '')

    def test_check_deployment_accepts_an_alternative_contract_and_refuses_a_broken_one(self):
        self.assertTrue(nc.check_deployment()['consistent'])
        broken = copy.deepcopy(self.contract)
        broken['exercise']['adversary'] = dict(broken['exercise']['adversary'],
                                              rule='Call them the Wraith group throughout.')
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'scenario-narrative-v1.json'
            path.write_text(json.dumps(broken), encoding='utf-8')
            with self.assertRaises(ConsistencyError):
                nc.check_deployment(path)

    def test_there_is_only_one_organizer_entry_point(self):
        import inspect

        import ridge.cli
        source = inspect.getsource(ridge.cli)
        for action in ('preflight', 'provision'):
            self.assertIn(action, source)
        # The consistency check is reached through preflight, not a rival subcommand.
        self.assertNotIn('narrative', source.lower())
        self.assertEqual(nc.check_deployment.__module__, 'ridge.narrative_consistency')

    def broken_contract(self):
        broken = copy.deepcopy(self.contract)
        broken['exercise']['adversary'] = dict(broken['exercise']['adversary'],
                                              rule='Call them the Wraith group throughout.')
        return broken


if __name__ == '__main__':
    unittest.main()
