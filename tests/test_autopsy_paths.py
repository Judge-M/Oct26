"""A05: Autopsy evidence reference vs desktop case entrypoint, and preflight contract."""
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from expanded.author import build as author
from expanded.prepare import build as prepare
from ridge.preflight import check, check_desktop
from ridge.scenario import AUTOPSY_CASE_ENTRYPOINT
from ridge.state import State

TEAMS = [
    {'id': 'team-01', 'name': 'Team 01', 'iris': '101', 'ctfd': 1,
     'iris_login': 'iris-01', 'ctfd_name': 'ctfd-01'},
    {'id': 'team-02', 'name': 'Team 02', 'iris': '102', 'ctfd': 2,
     'iris_login': 'iris-02', 'ctfd_name': 'ctfd-02'},
]
CONFIG = {'exercise_date': '2026-10-15', 'teams': TEAMS}


def remote(url, *args, **kwargs):
    if url.startswith('IRIS'):
        return {'ready': True, 'identities': [{'id': '101', 'name': 'iris-01'},
                                              {'id': '102', 'name': 'iris-02'}]}
    return {'ready': True, 'identities': [{'id': '1', 'name': 'ctfd-01'},
                                          {'id': '2', 'name': 'ctfd-02'}]}


class AutopsyPathTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.release = prepare(self.root / 'release', {'exercise_date': '2026-10-15'})
        self.tickets = author(CONFIG)
        self.state = State(self.root / 'state.sqlite')
        self.state.initialize(TEAMS, self.tickets)
        self.credential = self.root / 'credential'
        self.credential.write_text('user:password')

    def tearDown(self):
        self.tmp.cleanup()

    def run_preflight(self, teams=TEAMS):
        environment = {
            'IRIS_URL': 'IRIS', 'CTFD_URL': 'CTFD', 'WAZUH_INDEX': 'silent-ridge-test',
            'WAZUH_INDEXER_URL': 'https://local',
            'WAZUH_INDEX_CREDENTIAL_FILE': str(self.credential),
            'RIDGE_RELEASE_VAULT': str(self.release / 'controller/releases'),
            'RIDGE_EVIDENCE_PUBLIC': str(self.release / 'initial'),
        }
        with patch.dict(os.environ, environment), \
                patch('ridge.preflight.secret', return_value='x'), \
                patch('ridge.preflight.post', side_effect=remote), \
                patch('urllib.request.urlopen',
                      side_effect=lambda *args, **kwargs: io.BytesIO(b'{"silent-ridge-test":{}}')):
            return check(self.state, {'teams': teams})

    def test_authored_autopsy_questions_separate_source_and_entrypoint(self):
        autopsy = [question for ticket in self.tickets for question in ticket['questions']
                   if question['tool'] == 'Autopsy']
        self.assertTrue(autopsy)
        for question in autopsy:
            self.assertEqual(question['case_entrypoint'], AUTOPSY_CASE_ENTRYPOINT)
            self.assertTrue(question['evidence'].startswith('/evidence/'))
            self.assertNotIn('.aut', question['evidence'])
            self.assertIn('~/Cases/WS17/WS17.aut', ' '.join(question['steps']))
            self.assertIn('/evidence', ' '.join(question['steps']))
            self.assertIn('/originals', ' '.join(question['steps']))

    def test_authored_evidence_resolves_in_generated_release(self):
        delayed = {name for ticket in self.tickets for name in ticket.get('release_files', [])}
        for ticket in self.tickets:
            for question in ticket['questions']:
                name = question['evidence'].removeprefix('/evidence/')
                if name in delayed:
                    continue
                self.assertTrue((self.release / 'initial' / name).is_file(),
                                name + ' is not in the generated release')

    def test_preflight_passes_without_a_writable_case(self):
        self.assertFalse(any(self.release.rglob('*.aut')))
        result = self.run_preflight()
        self.assertTrue(result['ready'])
        self.assertEqual(result['tickets'], 20)

    def test_missing_released_source_fails_controller_preflight(self):
        (self.release / 'initial/disk/WS17-fat16.img').unlink()
        with self.assertRaisesRegex(ValueError, 'Required initial evidence is missing'):
            self.run_preflight()

    def test_legacy_case_evidence_path_is_rejected_explicitly(self):
        state = State(self.root / 'legacy.sqlite')
        team = dict(TEAMS[0])
        ticket = {'id': 'T03', 'title': 'legacy', 'subject': 'Autopsy', 'release_files': [],
                  'questions': [{'id': 'q', 'prompt': 'p', 'answer': 'a', 'tool': 'Autopsy',
                                 'evidence': '/evidence/autopsy/WS17/WS17.aut',
                                 'finding': {'text': 't', 'evidence': ['e'], 'limitation': 'l'}}]}
        state.initialize([team], [ticket])
        self.state = state
        with self.assertRaisesRegex(ValueError, 'desktop entrypoints, not released evidence'):
            self.run_preflight([team])

    def test_desktop_readiness_requires_writable_case(self):
        questions = [question for ticket in self.tickets for question in ticket['questions']
                     if question.get('case_entrypoint')]
        home = self.root / 'home'
        with self.assertRaisesRegex(ValueError, 'Desktop prepared case is missing'):
            check_desktop(questions, home)
        case = home / 'Cases/WS17/WS17.aut'
        case.parent.mkdir(parents=True)
        case.write_text('prepared case database')
        self.assertEqual(check_desktop(questions, home)['cases'], 1)
        with self.assertRaisesRegex(ValueError, 'Prepared case template is missing'):
            check_desktop(questions, home, template=self.root / 'absent-template')


if __name__ == '__main__':
    unittest.main()
