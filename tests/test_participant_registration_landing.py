"""Participant registration remains the complete event-day start page."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ParticipantRegistrationLandingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (ROOT / 'integrations' / 'ctfd_silent_ridge' /
                      '__init__.py').read_text(encoding='utf-8')

    def test_public_landing_contains_the_complete_start_sequence(self):
        for text in (
            'Start here',
            'Register once.',
            'Save the private handout.',
            'Work from your own laptop browser.',
            'Use Guacamole only for investigation tools.',
            'Repeat the investigation loop.',
            'Scoring and help',
            'Read-only work',
            'Need a facilitator?',
        ):
            self.assertIn(text, self.source)

    def test_private_handout_repeats_the_first_actions(self):
        for text in (
            'Your first five moves',
            'personal CTFd seat',
            'opens IRIS with the team login',
            'prepared Wazuh view',
            'divide the three desktop connections',
            'Claim one available IRIS ticket',
            'Keep this page open.',
        ):
            self.assertIn(text, self.source)


if __name__ == '__main__':
    unittest.main()
