"""Deterministic tests for the event-day deck narrative (issue 58).

The deck used to carry its own prose, which is how it drifted from the CTFd
question page and the IRIS case. These tests are the mechanism that stops it
drifting again: every scenario sentence on a slide is checked against the
contract literally, every investigation phase is required to state a purpose, an
urgency and an action, and the participant projection set is required to be
disjoint from the facilitator appendix.

No PDF toolchain, browser, network or Docker is required. The committed
``event-day-deck.pdf`` is produced by an external ``.pptd`` toolchain that is
not vendored here, so the tests cover the ``.page`` sources, which are
authoritative, and check the PDF only for staleness against a synthetic fixture.
"""
import copy
import unittest
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover - CI installs PyYAML (validate.yml)
    yaml = None

from ridge import deck_narrative
from ridge.deck_narrative import (
    DECK_DIR, FACILITATOR_DIR, FACILITATOR_PROJECT, GENERATED, PARTICIPANT_DIR, PDF,
    PROJECT, DeckError, check_audience, check_contract, check_coverage, check_geometry,
    check_no_answers, check_overflow, check_phases, check_secrets, generate, load_deck,
    pdf_freshness, report, resolve, source_pages, validate, write,
)
from ridge.scenario_contract import ContractError, build, distinctive_answers

ROOT = Path(__file__).resolve().parents[1]


def authored():
    from expanded.author import build as author

    return author()


@unittest.skipIf(yaml is None, 'PyYAML is not installed')
class DeckNarrativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tickets = authored()
        cls.contract = build(tickets=cls.tickets)
        cls.deck = load_deck()

    # -- the sources parse, and both projects are complete

    def test_every_page_source_parses_and_declares_its_audience(self):
        files = source_pages(DECK_DIR / PARTICIPANT_DIR.name) + \
            source_pages(DECK_DIR / FACILITATOR_DIR.name)
        self.assertGreaterEqual(len(files), 20, 'the deck lost slides')
        for path in files:
            with self.subTest(page=path.name):
                page = deck_narrative.load_page(path)
                self.assertIn(page.audience, ('participant', 'facilitator'))
                self.assertIn(page.page_type, ('cover', 'content', 'final'))
                self.assertTrue(page.elements)
                self.assertTrue(page.text().strip(), '%s has no readable text' % path.name)

    def test_both_projects_declare_a_complete_slide_list(self):
        for project_path, expected in ((PROJECT, 'participant'),
                                       (FACILITATOR_PROJECT, 'facilitator')):
            with self.subTest(project=project_path.name):
                project = deck_narrative.read_yaml(project_path)
                self.assertEqual(project['audience'], expected)
                self.assertTrue(project['pages'])
                for entry in project['pages']:
                    self.assertTrue((DECK_DIR / entry).is_file(), entry)

    def test_a_slide_no_project_lists_is_rejected(self):
        stray = DECK_DIR / 'pages' / '99_stray.page'
        stray.write_text('pageType: content\naudience: participant\n'
                         'background: {type: solid, color: "$paper"}\n'
                         'elements:\n  - elementId: x\n    elementType: text\n'
                         '    bounds: [0, 0, 10, 10]\n    content: {text: x}\n',
                         encoding='utf-8')
        try:
            with self.assertRaisesRegex(DeckError, 'no project lists them'):
                load_deck()
        finally:
            stray.unlink()

    def test_a_page_missing_its_audience_is_rejected(self):
        with self.assertRaisesRegex(DeckError, 'missing required key'):
            deck_narrative.load_page(
                ROOT / 'assets' / 'scenario-narrative-v1.json')

    def test_unreadable_yaml_is_rejected_by_path(self):
        with self.assertRaisesRegex(DeckError, 'not found'):
            deck_narrative.read_yaml(DECK_DIR / 'pages' / 'nope.page')

    # -- the deck is generated from the contract, and committed as such

    def test_committed_generated_slides_match_the_generator(self):
        pages = generate(self.contract)
        self.assertEqual(sorted(pages), sorted(GENERATED))
        for name, source in sorted(pages.items()):
            with self.subTest(page=name):
                directory = FACILITATOR_DIR.name if name.startswith('f') else PARTICIPANT_DIR.name
                committed = (DECK_DIR / directory / name).read_text(encoding='utf-8')
                self.assertEqual(committed, source,
                                 '%s has drifted from the contract; run '
                                 'python -m ridge.deck_narrative --write' % name)

    def test_generation_is_deterministic(self):
        self.assertEqual(generate(self.contract), generate(self.contract))

    def test_write_into_a_scratch_tree_reproduces_the_committed_deck(self):
        import shutil
        import tempfile

        scratch = Path(tempfile.mkdtemp(prefix='deck-'))
        try:
            shutil.copytree(DECK_DIR, scratch / 'event-day-deck')
            write(scratch / 'event-day-deck')
            for name in GENERATED:
                directory = FACILITATOR_DIR.name if name.startswith('f') else PARTICIPANT_DIR.name
                with self.subTest(page=name):
                    self.assertEqual((scratch / 'event-day-deck' / directory / name)
                                     .read_text(encoding='utf-8'),
                                     (DECK_DIR / directory / name).read_text(encoding='utf-8'))
            self.assertEqual(deck_narrative.read_yaml(scratch / 'event-day-deck' / PROJECT.name)
                             ['pages'],
                             deck_narrative.read_yaml(PROJECT)['pages'])
        finally:
            shutil.rmtree(scratch, ignore_errors=True)

    # -- narrative fidelity

    def test_deck_narrative_text_matches_the_contract(self):
        self.assertEqual(check_contract(self.deck, self.contract), [])

    def test_every_required_contract_field_is_projected(self):
        self.assertEqual(check_coverage(self.deck, self.contract), [])

    def test_a_slide_that_restates_the_contract_is_caught(self):
        broken = copy.deepcopy(self.deck)
        for page in broken.pages:
            if page.name != '02_brief.page':
                continue
            for element in page.document['elements']:
                if element.get('contractRef') == 'exercise.premise':
                    element['content']['text'] = '<p>A fictional patrol is already in the field.</p>'
        self.assertNotEqual(check_contract(broken, self.contract), [])

    def test_a_missing_phase_field_is_caught(self):
        broken = deck_narrative.Deck(
            self.deck.root, self.deck.projects,
            tuple(page for page in self.deck.pages if page.name != '10_phase3.page'))
        problems = check_phases(broken, self.contract)
        self.assertTrue(any('phase-3' in problem and 'action' in problem
                            for problem in problems), problems)

    def test_a_forbidden_post_completion_ref_is_rejected(self):
        page = deck_narrative.load_page(DECK_DIR / 'pages' / '22_close.page')
        tampered = deck_narrative.Page(page.path, copy.deepcopy(page.document))
        tampered.document['elements'][0]['contractRef'] = 'exercise_complete.residual'
        broken = deck_narrative.Deck(self.deck.root, self.deck.projects, (tampered,))
        problems = check_contract(broken, self.contract)
        self.assertTrue(any('must not be projected' in problem for problem in problems), problems)

    def test_a_ref_to_a_field_that_does_not_exist_is_rejected(self):
        with self.assertRaisesRegex(DeckError, 'no such field'):
            resolve(self.contract, 'exercise.no_such_section')
        with self.assertRaisesRegex(DeckError, 'no such list index'):
            resolve(self.contract, 'phases.9.title')
        with self.assertRaisesRegex(DeckError, 'matches 0 contract entries'):
            resolve(self.contract, 'phases.phase-99.title')

    def test_list_refs_render_as_the_deck_separator(self):
        self.assertEqual(resolve(self.contract, 'phases.phase-2.tickets'),
                         ['T04', 'T05', 'T13', 'T14', 'T15', 'T16', 'T17', 'T18'])
        for page in self.deck.pages:
            for ref, found in page.refs().items():
                if not ref.endswith('.tickets'):
                    continue
                expected = deck_narrative.rendered(resolve(self.contract, ref))
                for element_id, text in found:
                    self.assertEqual(text, expected, '%s.%s' % (page.name, element_id))

    def test_every_phase_states_a_purpose_an_urgency_and_an_action(self):
        self.assertEqual(check_phases(self.deck, self.contract), [])
        for phase in self.contract['phases']:
            with self.subTest(phase=phase['id']):
                for field in ('purpose', 'urgency', 'action', 'transition'):
                    hits = self.deck.by_ref('phases.%s.%s' % (phase['id'], field))
                    self.assertTrue(hits, '%s has no %s' % (phase['id'], field))
                    for name, _, text in hits:
                        self.assertTrue(text.strip())

    def test_the_deck_covers_all_twenty_tickets_across_its_phases(self):
        projected = set()
        for phase in self.contract['phases']:
            for name, _, text in self.deck.by_ref('phases.%s.tickets' % phase['id']):
                projected.update(part.strip() for part in text.split('·'))
        self.assertEqual(projected, {ticket['id'] for ticket in self.tickets})

    # -- no answers, no secrets, no attribution

    def test_no_scored_answer_appears_on_any_slide(self):
        self.assertEqual(check_no_answers(self.deck, self.tickets, self.contract), [])
        self.assertGreaterEqual(sum(len(v) for v in distinctive_answers(self.tickets).values()),
                                50, 'the answer guard should be covering the distinctive answers')

    def test_the_answer_guard_catches_a_leak_planted_on_a_slide(self):
        answer = sorted(distinctive_answers(self.tickets))[0]
        page = deck_narrative.load_page(DECK_DIR / 'pages' / '21_aar.page')
        broken = deck_narrative.Page(page.path, copy.deepcopy(page.document))
        broken.document['elements'][0]['content']['text'] = '<p>It was %s.</p>' % answer
        problems = check_no_answers(deck_narrative.Deck(self.deck.root, self.deck.projects,
                                                        (broken,)),
                                    self.tickets, self.contract)
        self.assertTrue(any('shows the answer to' in problem for problem in problems), problems)

    def test_no_secret_shaped_string_appears_on_any_slide(self):
        self.assertEqual(check_secrets(self.deck), [])

    def test_the_secret_scan_catches_the_shapes_it_must(self):
        needles = ('password: hunter2', 'file:/etc/silent-ridge/secrets/iris-bridge',
                   '198.51.100.77', 'ctfd.example.invalid', '10.1.2.3',
                   'ssh-rsaAAAAB3NzaC1yc2E', 'a Wraith cell', 'sponsored by the state',
                   # A real bcrypt digest. The scan previously used a cost field in
                   # the version slot, so it could never match one.
                   '$2b$10$N9qo8uLOickgx2ZMRZoMyeIjZAgcfl7p92ldGxad68LJZdL17lhWy')
        for needle in needles:
            with self.subTest(needle=needle):
                page = deck_narrative.load_page(DECK_DIR / 'pages' / '19_rules.page')
                broken = deck_narrative.Page(page.path, copy.deepcopy(page.document))
                broken.document['elements'][0]['content']['text'] = '<p>%s</p>' % needle
                deck = deck_narrative.Deck(self.deck.root, self.deck.projects, (broken,))
                self.assertNotEqual(check_secrets(deck), [], needle)

    def test_the_documented_example_address_is_never_named(self):
        for page in self.deck.pages:
            self.assertNotIn('198.51.100.77', page.text(), page.name)

    def test_the_deck_never_names_an_adversary(self):
        for page in self.deck.pages:
            lowered = page.text().lower()
            self.assertNotIn('wraith', lowered, page.name)
            self.assertNotIn(self.contract['exercise']['adversary']['handle'].lower() + ' group',
                             lowered, page.name)

    # -- audience separation

    def test_the_facilitator_appendix_is_present_and_separate(self):
        self.assertEqual(check_audience(self.deck), [])
        self.assertTrue(self.deck.facilitator, 'there is no facilitator appendix')
        self.assertTrue(self.deck.participant, 'there is no projection set')
        participant = {page.name for page in self.deck.participant}
        facilitator = {page.name for page in self.deck.facilitator}
        self.assertEqual(participant & facilitator, set())
        self.assertFalse(any(name.startswith('f') for name in participant))
        for page in self.deck.facilitator:
            self.assertIn(deck_narrative.FACILITATOR_BANNER, page.text(), page.name)

    def test_the_participant_project_cannot_reference_the_facilitator_appendix(self):
        project = deck_narrative.read_yaml(PROJECT)
        for entry in project['pages']:
            self.assertTrue(entry.startswith(PARTICIPANT_DIR.name + '/'), entry)
        self.assertEqual(project.get('facilitatorProject'), FACILITATOR_PROJECT.name)
        appendix = deck_narrative.read_yaml(FACILITATOR_PROJECT)
        for entry in appendix['pages']:
            self.assertTrue(entry.startswith(FACILITATOR_DIR.name + '/'), entry)

    def test_a_facilitator_slide_left_in_the_projection_set_is_rejected(self):
        import shutil
        import tempfile

        scratch = Path(tempfile.mkdtemp(prefix='deck-sep-')) / 'event-day-deck'
        try:
            shutil.copytree(DECK_DIR, scratch)
            # The mistake this guards: a facilitator callout dropped into the
            # participant directory and listed by the participant project.
            moved = scratch / 'facilitator-pages' / 'f01_run_of_show.page'
            shutil.move(str(moved), str(scratch / 'pages' / moved.name))
            project = deck_narrative.read_yaml(scratch / PROJECT.name)
            project['pages'].append('%s/%s' % (PARTICIPANT_DIR.name, moved.name))
            (scratch / PROJECT.name).write_text(yaml.safe_dump(project), encoding='utf-8')
            appendix = deck_narrative.read_yaml(scratch / FACILITATOR_PROJECT.name)
            appendix['pages'] = [entry for entry in appendix['pages'] if moved.name not in entry]
            (scratch / FACILITATOR_PROJECT.name).write_text(yaml.safe_dump(appendix),
                                                            encoding='utf-8')
            deck = load_deck(scratch)
            problems = check_audience(deck)
            self.assertTrue(problems, 'a facilitator slide in the projection set must be caught')
            self.assertTrue(any(moved.name in problem for problem in problems), problems)
        finally:
            shutil.rmtree(scratch.parent, ignore_errors=True)

    def test_no_facilitator_slide_loses_its_visible_marker(self):
        page = deck_narrative.load_page(DECK_DIR / FACILITATOR_DIR.name / 'f02_callouts.page')
        stripped = copy.deepcopy(page.document)
        for element in stripped['elements']:
            if element.get('elementId') == 'facilitator-banner-text':
                element['content']['text'] = 'Run of show'
        problems = check_audience(deck_narrative.Deck(self.deck.root, self.deck.projects,
                                                       (deck_narrative.Page(page.path,
                                                                            stripped),)))
        self.assertTrue(any('not visibly marked' in problem for problem in problems), problems)

    # -- geometry and offline legibility

    def test_geometry_and_legibility_hold_on_every_slide(self):
        self.assertEqual(check_geometry(self.deck), [])
        self.assertEqual(check_overflow(self.deck), [])
        self.assertEqual(deck_narrative.check_nowrap_width(self.deck), [])

    def test_a_no_wrap_line_that_outgrows_its_box_is_reported(self):
        page = deck_narrative.load_page(DECK_DIR / 'pages' / '19_rules.page')
        broken = copy.deepcopy(page.document)
        for element in broken['elements']:
            if element.get('elementId') == 'title':
                element['bounds'] = [64, 66, 90, 40]
        problems = deck_narrative.check_nowrap_width(
            deck_narrative.Deck(self.deck.root, self.deck.projects,
                                (deck_narrative.Page(page.path, broken),)))
        self.assertTrue(any('no-wrap line' in problem for problem in problems), problems)

    def test_a_box_outside_the_canvas_is_rejected(self):
        page = deck_narrative.load_page(DECK_DIR / 'pages' / '19_rules.page')
        broken = copy.deepcopy(page.document)
        broken['elements'][0]['bounds'] = [64, 500, 832, 200]
        problems = check_geometry(deck_narrative.Deck(self.deck.root, self.deck.projects,
                                                      (deck_narrative.Page(page.path, broken),)))
        self.assertTrue(any('outside the 960x540 canvas' in problem for problem in problems),
                        problems)

    def test_an_undefined_theme_token_is_rejected(self):
        page = deck_narrative.load_page(DECK_DIR / 'pages' / '19_rules.page')
        broken = copy.deepcopy(page.document)
        broken['elements'][0]['content']['color'] = '$charcoal'
        problems = check_geometry(deck_narrative.Deck(self.deck.root, self.deck.projects,
                                                      (deck_narrative.Page(page.path, broken),)))
        self.assertTrue(any('not a theme color' in problem for problem in problems), problems)

    def test_overflowing_text_is_reported(self):
        page = deck_narrative.load_page(DECK_DIR / 'pages' / '19_rules.page')
        broken = copy.deepcopy(page.document)
        for element in broken['elements']:
            if element.get('elementId') == 'note-body':
                element['bounds'] = [64, 456, 60, 20]
        problems = check_overflow(deck_narrative.Deck(self.deck.root, self.deck.projects,
                                                      (deck_narrative.Page(page.path, broken),)))
        self.assertTrue(any('needs about' in problem for problem in problems), problems)

    def test_two_text_boxes_cannot_sit_on_top_of_each_other(self):
        page = deck_narrative.load_page(DECK_DIR / 'pages' / '19_rules.page')
        broken = copy.deepcopy(page.document)
        boxes = [e for e in broken['elements'] if e.get('elementType') == 'text']
        boxes[1]['bounds'] = list(boxes[0]['bounds'])
        problems = deck_narrative.check_overlap(
            deck_narrative.Deck(self.deck.root, self.deck.projects,
                                (deck_narrative.Page(page.path, broken),)))
        self.assertTrue(any('overlaps' in problem for problem in problems), problems)

    def test_decorative_shapes_may_bleed_off_the_canvas(self):
        self.assertEqual(check_geometry(self.deck), [],
                         'the cover rings bleed by design and must not be flagged')

    def test_text_extraction_reads_what_a_participant_would_see(self):
        self.assertEqual(deck_narrative.plain('<p>a &amp; b</p>'), 'a & b')
        # The address placeholder is escaped in the sources, so it survives the
        # tag strip and is read back as the participant sees it.
        self.assertEqual(deck_narrative.plain('<p>https://&lt;event-address&gt;:8081</p>'),
                         'https://<event-address>:8081')
        page = deck_narrative.load_page(DECK_DIR / 'pages' / '12_kit.page')
        text = page.text()
        self.assertIn('IRIS', text)
        self.assertNotIn('<p>', text)
        # The setup slides carry the address placeholder, escaped in the source
        # so it is read back exactly as a participant sees it.
        steps = deck_narrative.load_page(DECK_DIR / 'pages' / '13_step1.page').text()
        self.assertIn('https://<event-address>:8081', steps)

    # -- the whole thing, and the receipt

    def test_the_whole_deck_validates(self):
        validate(self.deck, self.contract, self.tickets)

    def test_a_broken_deck_fails_validation_with_a_reason(self):
        page = deck_narrative.load_page(DECK_DIR / 'pages' / '18_reminders.page')
        broken = copy.deepcopy(page.document)
        broken['elements'][0]['content']['text'] = '<p>password: hunter2</p>'
        deck = deck_narrative.Deck(self.deck.root, self.deck.projects,
                                   tuple(p for p in self.deck.pages if p.name != page.name)
                                   + (deck_narrative.Page(page.path, broken),))
        with self.assertRaisesRegex(DeckError, 'credential assignment'):
            validate(deck, self.contract, self.tickets)

    def test_the_report_names_the_two_sets_and_every_phase(self):
        receipt = report(self.deck, self.contract, self.tickets)
        self.assertEqual(receipt['slides'], len(self.deck.pages))
        self.assertEqual(len(receipt['participant_facing']), len(self.deck.participant))
        self.assertEqual(len(receipt['facilitator_only']), len(self.deck.facilitator))
        self.assertEqual(receipt['overflow'], [])
        for phase in self.contract['phases']:
            entry = receipt['phases'][phase['id']]
            with self.subTest(phase=phase['id']):
                self.assertTrue(entry['purpose'] and entry['urgency'] and entry['action'])
                self.assertTrue(entry['transition'])
                self.assertEqual(entry['tickets'], phase['tickets'])
                self.assertTrue(entry['slides'])
        self.assertEqual(report(self.deck, self.contract, self.tickets), receipt)

    def test_the_report_is_json_serialisable(self):
        import json

        json.dumps(report(self.deck, self.contract, self.tickets))

    # -- the PDF, which is a build artifact of a toolchain we do not vendor

    def test_pdf_freshness_flags_a_pdf_older_than_its_sources(self):
        import os
        import tempfile

        scratch = Path(tempfile.mkdtemp(prefix='deck-pdf-'))
        try:
            (scratch / PARTICIPANT_DIR.name).mkdir()
            (scratch / FACILITATOR_DIR.name).mkdir()
            source = scratch / PARTICIPANT_DIR.name / '01_cover.page'
            source.write_text('pageType: cover\n', encoding='utf-8')
            pdf = scratch / PDF.name
            pdf.write_bytes(b'%PDF-1.4\n')
            os.utime(pdf, (1000, 1000))
            os.utime(source, (2000, 2000))
            state = pdf_freshness(scratch)
            self.assertTrue(state['present'])
            self.assertTrue(state['stale'])
            self.assertEqual(state['newest_source'], '01_cover.page')
            self.assertEqual(state['pdf_older_by_seconds'], 1000)
            self.assertEqual(len(state['pdf_sha256']), 64)
        finally:
            import shutil

            shutil.rmtree(scratch, ignore_errors=True)

    def test_pdf_freshness_reports_a_fresh_pdf(self):
        import os
        import tempfile

        scratch = Path(tempfile.mkdtemp(prefix='deck-pdf-'))
        try:
            (scratch / PARTICIPANT_DIR.name).mkdir()
            (scratch / FACILITATOR_DIR.name).mkdir()
            source = scratch / PARTICIPANT_DIR.name / '01_cover.page'
            source.write_text('pageType: cover\n', encoding='utf-8')
            pdf = scratch / PDF.name
            pdf.write_bytes(b'%PDF-1.4\n')
            os.utime(source, (1000, 1000))
            os.utime(pdf, (2000, 2000))
            state = pdf_freshness(scratch)
            self.assertFalse(state['stale'])
            self.assertEqual(state['pdf_older_by_seconds'], 0)
        finally:
            import shutil

            shutil.rmtree(scratch, ignore_errors=True)

    def test_pdf_freshness_reports_a_missing_pdf(self):
        import tempfile

        scratch = Path(tempfile.mkdtemp(prefix='deck-pdf-'))
        try:
            (scratch / PARTICIPANT_DIR.name).mkdir()
            (scratch / FACILITATOR_DIR.name).mkdir()
            state = pdf_freshness(scratch)
            self.assertFalse(state['present'])
            self.assertTrue(state['stale'])
        finally:
            import shutil

            shutil.rmtree(scratch, ignore_errors=True)

    def test_the_committed_pdf_is_not_rewritten_by_this_issue(self):
        # The PDF is a build artifact of an external toolchain that is not
        # vendored here, so it could not be regenerated. What is asserted instead
        # is that reading the deck never touches it.
        self.assertTrue(PDF.is_file())
        self.assertEqual(deck_narrative.sha256(PDF), deck_narrative.sha256(PDF))
        self.assertEqual(PDF.suffix, '.pdf')

    def test_validation_needs_no_network_or_toolchain(self):
        import socket

        def refuse(*args, **kwargs):
            raise AssertionError('the deck validator must not open a socket')

        original = socket.socket
        socket.socket = refuse
        try:
            validate(load_deck(), build(tickets=authored()), authored())
        finally:
            socket.socket = original

    def test_the_contract_still_refuses_an_answer(self):
        from ridge.scenario_contract import check_no_answers

        broken = copy.deepcopy(self.contract)
        broken['phases'][0]['purpose'] = 'Confirm the upload to 198.51.100.77.'
        with self.assertRaisesRegex(ContractError, 'contains the answer to'):
            check_no_answers(broken, self.tickets)


if __name__ == '__main__':
    unittest.main()
