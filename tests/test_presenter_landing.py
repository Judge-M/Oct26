"""#197: the presenter landing page aggregates the day-of deck and operator
material into one offline file, keeps its links and derived data honest, and
leaks no credentials.

The linked markdown documents stay authoritative; these tests fail when the
page drifts from them (dead links, agenda minutes that no longer match the
schedule model, a stale dress-rehearsal prerequisite) or when operator-only
material leaks into a file that could be projected or copied to a
participant-visible location.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE_PATH = ROOT / 'docs' / 'presenter-landing.html'


def page():
    return PAGE_PATH.read_text(encoding='utf-8')


def read(relative):
    return (ROOT / relative).read_text(encoding='utf-8')


def local_hrefs(text):
    """Every href that points into the repository (no http(s), mailto, or
    pure in-page fragments)."""
    return [
        target for target in re.findall(r'href="([^"]+)"', text)
        if not re.match(r'^(https?:|mailto:|#)', target)
    ]


class PresenterLandingTests(unittest.TestCase):
    def test_page_exists_and_is_self_contained(self):
        self.assertTrue(PAGE_PATH.is_file())
        text = page()
        # Offline single file: nothing loaded from the network, no separate
        # stylesheet or script assets, no dynamic fetching.
        self.assertIsNone(
            re.search(r'(?:src|href)\s*=\s*["\']https?:', text),
            'page references an external network resource',
        )
        self.assertNotIn('<script src', text)
        self.assertNotIn('<link rel="stylesheet"', text)
        self.assertNotIn('@import', text)
        for forbidden in ('fetch(', 'XMLHttpRequest', 'WebSocket'):
            self.assertNotIn(forbidden, text)

    def test_local_links_resolve(self):
        base = PAGE_PATH.parent
        missing = [
            target for target in local_hrefs(page())
            if not (base / target.split('#', 1)[0]).exists()
        ]
        self.assertEqual(missing, [])

    def test_deck_and_operator_docs_are_linked(self):
        text = page()
        hrefs = set(local_hrefs(text))
        # The deck, front and center, opening in its own window.
        self.assertIn('event-day-deck/event-day-deck.pdf', hrefs)
        self.assertRegex(
            text,
            r'href="event-day-deck/event-day-deck\.pdf"[^>]*target="_blank"',
        )
        for doc in ('event-day-commands.md', 'runbook.md',
                    'participant-ca-trust.md', 'event-machine-cold-start.md',
                    'dress-rehearsal-plan.md', 'schedule-model.md'):
            self.assertIn(doc, hrefs, doc)

    def test_participant_urls_cover_the_five_participant_endpoints(self):
        text = page()
        endpoints = re.findall(
            r'data-url-host="(https?)://" data-url-port="(\d+)"'
            r'(?: data-url-path="([^"]*)")?', text)
        observed = {(scheme, port) for scheme, port, _path in endpoints}
        self.assertEqual(observed, {
            ('https', '8082'), ('https', '8081'), ('https', '8083'),
            ('https', '8443'), ('http', '8080'),
        })
        crl = [path for _s, port, path in endpoints if port == '8080']
        self.assertEqual(crl, ['/root-ca.crl'])
        # The LAN address is a paste-in placeholder until the operator fills
        # it in, and the substitution is done by inline script, not the network.
        self.assertIn('&lt;LAN-IP&gt;', text)
        self.assertIn('lan-ip', text)

    def test_run_of_show_matches_schedule_model(self):
        model_rows = re.findall(
            r'^\| (.+?) \| (\w+) \| (\d+) \|$',
            read('docs/schedule-model.md'), flags=re.MULTILINE)
        # Drop the pace-sensitivity table rows if the model ever grows them:
        # agenda rows carry one of the segment kinds, sensitivity rows do not.
        kinds = {'facilitated', 'investigation', 'break', 'aar'}
        agenda = [(name, kind, int(mins)) for name, kind, mins in model_rows
                  if kind in kinds]
        self.assertEqual([mins for _n, _k, mins in agenda],
                         [25, 195, 10, 15, 30])
        page_rows = re.findall(
            r'<td>([^<]+)</td><td>(\w+)</td>\s*<td data-minutes="(\d+)">',
            page())
        self.assertEqual(
            [(name, kind, int(mins)) for name, kind, mins in page_rows],
            agenda,
        )
        total = sum(mins for _n, _k, mins in agenda)
        self.assertEqual(total, 275)
        self.assertIn('<td>275</td>', page())

    def test_runbook_quick_reference_covers_play_commands(self):
        text = page()
        names = re.findall(r'<span class="name">(\w+)</span>', text)
        self.assertTrue(
            {'status', 'up', 'start', 'pause', 'announce', 'recover',
             'backup'} <= set(names), names)
        # The condensed symptom table must be present and non-trivial.
        self.assertIn('Symptom', text)
        self.assertGreaterEqual(
            text.count('<td>Re-run') + text.count('data-copy'), 1)
        for row in ('reconciles', 'recover', 'backup'):
            self.assertIn(row, text)

    def test_page_contains_no_credentials_or_secrets_paths(self):
        text = page()
        lowered = text.lower()
        # Acceptance: no operator credential, no team credential, no runtime
        # path that holds secrets. The page may only *point* at the runbook.
        for forbidden in ('admin', 'team1', 'secrets/', 'guacadmin',
                          'ridge_backup_key'):
            self.assertNotIn(forbidden, lowered, forbidden)

    def test_dress_rehearsal_prerequisite_points_at_the_page(self):
        plan = read('docs/dress-rehearsal-plan.md')
        self.assertNotIn('Participant deck PDF and facilitator runbook copied',
                         plan)
        self.assertIn('docs/presenter-landing.html', plan)
        # The walkthrough now validates the page against the deck.
        self.assertIn('<event-address>', plan)

    def test_readme_links_the_page(self):
        self.assertIn('docs/presenter-landing.html', read('README.md'))


if __name__ == '__main__':
    unittest.main()
