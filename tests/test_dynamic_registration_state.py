import tempfile
import unittest
from pathlib import Path

from ridge.state import State


class DynamicStateTests(unittest.TestCase):
    def test_empty_bootstrap_accepts_teams_later(self):
        root = Path(__file__).resolve().parents[1] / 'work' / 'test-dynamic-state'
        root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as temp:
            state = State(Path(temp) / 'state.sqlite')
            state.initialize([], [{
                'id': 'T01', 'title': 'First ticket', 'subject': 'subject',
                'questions': [{
                    'id': 'T01-Q1', 'body': 'Question', 'answer': 'answer',
                    'finding': {'text': 'finding', 'evidence': ['evidence'],
                                'limitation': 'training'},
                }],
            }], allow_empty=True)
            state.register_team({'id': 'team-01', 'iris': '44', 'ctfd': 55,
                                 'name': 'Blue Lanterns'})
            self.assertEqual(state.identity('iris', '44'), 'team-01')
            self.assertEqual(state.identity('ctfd', 55), 'team-01')
            state.register_team({'id': 'team-01', 'iris': '44', 'ctfd': 55,
                                 'name': 'Blue Lanterns'})
            with self.assertRaises(ValueError):
                state.register_team({'id': 'team-01', 'iris': '99', 'ctfd': 55,
                                     'name': 'Blue Lanterns'})


if __name__ == '__main__':
    unittest.main()
