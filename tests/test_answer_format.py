"""Issue #195: format-rejected but factually correct answers.

Covers the four surface forms observed in the 5-team run: a version prefix
(v3/plan-v3 vs 3), a full ISO timestamp vs HH:MM:SS, a full file path vs a
directory, and a leading qualifier word on a phrase answer. Grading must
accept these without relaxing the stored expected-answer digest.
"""
import tempfile
import unittest
from pathlib import Path
from ridge.state import State, normalize_answer
from expanded.author import answer_format, build


class NormalizeTests(unittest.TestCase):
    def test_clock_forms_collapse_to_hhmmss(self):
        self.assertEqual(normalize_answer('2026-10-15T09:06:00Z'), '09:06:00')
        self.assertEqual(normalize_answer('2026-10-15 09:06:00+00:00'), '09:06:00')
        self.assertEqual(normalize_answer('09:06'), '09:06:00')
        self.assertEqual(normalize_answer('09:06:00 UTC'), '09:06:00')
        self.assertEqual(normalize_answer(' 09:06:00 '), '09:06:00')

    def test_ranges_and_non_clocks_survive(self):
        self.assertEqual(normalize_answer('10:30-11:30Z'), '10:30-11:30z')
        self.assertEqual(normalize_answer('10.26.10.17'), '10.26.10.17')
        self.assertEqual(normalize_answer('no'), 'no')

    def test_path_separators_unify(self):
        self.assertEqual(normalize_answer('C:\\Downloads\\'), 'c:/downloads')


class GradingTests(unittest.TestCase):
    EXPECTED = {
        'Q-VERSION': '3',
        'Q-OBJECT': 'plan-v3',
        'Q-TIME': '09:06:00',
        'Q-WINDOW': '10:30-11:30Z',
        'Q-DIR': 'C:/Downloads',
        'Q-EXE': 'C:/Program Files/Approved/briefsync.exe',
        'Q-PHRASE': 'session revocation',
    }

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.state = State(Path(self.tmp.name) / 'state.sqlite', retry_delay=0)
        self.deliveries = {}
        teams = [dict(id='0', iris='10', ctfd='20', name='Team 0')]
        ticket = dict(id='A', title='A', subject='general', requires=[], questions=[
            dict(id=qid, prompt=qid, answer=answer,
                 finding=dict(text='Finding', evidence=['ref'], limitation='Scope only'))
            for qid, answer in self.EXPECTED.items()])
        self.state.initialize(teams, [ticket])
        self.state.provision('controller')
        self.drain()
        self.state.mode('controller', 'running')
        self.state.claim('0', 'A', 0)

    def tearDown(self):
        self.tmp.cleanup()

    def sink(self, kind, key, payload, context):
        if key not in self.deliveries:
            self.deliveries[key] = len(self.deliveries) + 1
        return self.deliveries[key]

    def drain(self):
        while self.state.sync_once(self.sink):
            pass

    def check(self, question, *submissions):
        """All but the final submission must be rejected; the final accepted."""
        for text, expected in submissions[:-1]:
            self.assertEqual(self.state.answer('0', question, text), {'correct': False},
                             'expected rejection of %r for %s' % (text, question))
        text = submissions[-1][0]
        self.assertTrue(self.state.answer('0', question, text)['correct'],
                        'expected acceptance of %r for %s' % (text, question))

    def test_version_prefix(self):
        self.check('Q-VERSION', ('4', False), ('cached v3', False),
                   ('plan-v3', True))

    def test_version_prefix_bare_v(self):
        self.check('Q-VERSION', ('v3', True))

    def test_numeric_answer_is_not_enough_for_object_name(self):
        self.check('Q-OBJECT', ('3', False), ('plan-v3', True))

    def test_iso_timestamp_for_clock_answer(self):
        self.check('Q-TIME', ('10:06:00', False), ('2026-10-15T09:06:00Z', True))

    def test_time_range_answer_is_not_clock_collapsed(self):
        self.check('Q-WINDOW', ('11:30', False), ('10:30-11:30Z', True))

    def test_full_path_accepted_for_directory_answer(self):
        self.check('Q-DIR', ('C:/Temp', False),
                   ('C:\\Downloads\\brief-viewer.exe', True))

    def test_directory_not_accepted_for_full_path_answer(self):
        self.check('Q-EXE', ('C:\\Program Files\\Approved', False),
                   ('C:\\Program Files\\Approved\\briefsync.exe', True))

    def test_phrase_leading_qualifier(self):
        self.check('Q-PHRASE', ('session revocations', False),
                   ('Explicit session revocation', True))


class AuthorFormatTests(unittest.TestCase):
    def test_per_question_guidance(self):
        self.assertIn('number only',
                      answer_format('What version appears in the cached brief?', '3'))
        self.assertIn('without a date',
                      answer_format('What upload time is recorded, UTC?', '09:06:00'))
        self.assertIn('directory path only',
                      answer_format('What was the recorded target directory?', 'C:/Downloads'))
        self.assertIn('full path',
                      answer_format('What is its executable path?',
                                    'C:/Program Files/Approved/briefsync.exe'))
        self.assertIn('Case and outer whitespace are ignored.',
                      answer_format('Which check-in word is present?', 'CEDAR'))
        self.assertIn('filename only',
                      answer_format('What is the basename of its parent executable?',
                                    'browser.exe'))

    def test_cross_source_routes_do_not_publish_answers_as_steps(self):
        questions = {question['id']: question
                     for ticket in build()
                     for question in ticket['questions']}
        self.assertEqual(questions['T07-Q1']['selection'], 'data.action:password_reset')
        self.assertEqual(questions['T07-Q1']['source_record'], 'wazuh/telemetry.jsonl')
        self.assertEqual(questions['T07-Q2']['source_record'], 'identity/late-auth.csv')
        self.assertEqual(questions['T07-Q4']['source_record'], 'identity/policy.txt')
        self.assertEqual(questions['T12-Q2']['source_record'], 'server/collection.txt')
        self.assertIn('filename only', questions['T13-Q2']['format'])
        self.assertIn('Process-to-network correlation board',
                      '\n'.join(questions['T16-Q1']['steps']))
        self.assertIn('Capstone assessment workspace',
                      '\n'.join(questions['T20-Q1']['steps']))
        ordinary_steps = '\n'.join(questions['T01-Q1']['steps'] +
                                   questions['T07-Q2']['steps'] +
                                   questions['T07-Q4']['steps'])
        for leaked_answer in ('10.26.10.17', 'm.ellis', '09:26:00',
                              'explicit session revocation'):
            self.assertNotIn(leaked_answer, ordinary_steps)

    def test_help_level_two_is_question_specific_and_sensor_filter_works(self):
        questions = {question['id']: question
                     for ticket in build()
                     for question in ticket['questions']}
        second_hints = []
        for question in questions.values():
            self.assertGreaterEqual(len(question['hints']), 3)
            self.assertNotEqual(question['hints'][0], question['hints'][1])
            self.assertNotIn('Compare the selected record with adjacent events',
                             question['hints'][1])
            second_hints.append(question['hints'][1])
        self.assertEqual(len(second_hints), len(set(second_hints)))
        self.assertEqual(questions['T01-Q2']['selection'], 'udp.dstport == 514')
        self.assertIn('24 matching packets', questions['T01-Q2']['hints'][1])
        self.assertIn('not udp == 514', questions['T01-Q2']['hints'][1])


if __name__ == '__main__':
    unittest.main()

