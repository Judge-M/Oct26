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
            'Use IRIS for ownership and shared findings.',
            'Use CTFd for the investigation workflow.',
            'Use Guacamole only for investigation tools.',
            'Repeat the investigation loop.',
            'Scoring and help',
            'Read-only work',
            'Need a facilitator?',
        ):
            self.assertIn(text, self.source)

    def test_start_guide_explains_scoring_and_platform_roles(self):
        guide=(ROOT/'expanded'/'guides.md').read_text(encoding='utf-8')
        for text in ('Each question starts at **4 points**',
                     'levels 1 and 2 are free',
                     "**3 of the question's 4 points**",
                     "team's incident-management view",
                     'CTFd to investigate a claimed ticket'):
            self.assertIn(text,guide)
        self.assertNotIn('without a\npoint penalty',guide)
        self.assertNotIn('one ticket at a time',guide)

    def test_private_handout_repeats_the_first_actions(self):
        for text in (
            '— Team Handout',
            'Your first five moves',
            'personal CTFd seat',
            'opens IRIS with the team login',
            'prepared Wazuh view',
            'divide the three desktop connections',
            'Claim up to three available IRIS tickets',
            'Keep this page open.',
        ):
            self.assertIn(text, self.source)

    def test_private_handout_has_a_five_person_delegation_plan(self):
        for text in ('Divide the work before anyone starts',
                     'captain is not a required technical role',
                     'Person 1 — queue coordinator',
                     'Person 2 — network and Wazuh analyst',
                     'Person 3 — disk and endpoint analyst',
                     'Person 4 — binary and file analyst',
                     'Person 5 — CTFd recorder and verifier',
                     'If the captain leaves'):
            self.assertIn(text,self.source)

    def test_private_handout_has_persistent_safe_recovery_actions(self):
        for text in (
            'Your permanent private return link',
            'Copy return link',
            'Download private handout',
            'Copy labelled handout',
            "@app.route('/silent-ridge/registration/<access_code>/download')",
            'silent-ridge-private-team-handout.txt',
            "Cache-Control'] = 'no-store, private'",
            "Referrer-Policy'] = 'no-referrer'",
        ):
            self.assertIn(text, self.source)
        self.assertNotIn('retrieve_url = request.base_url', self.source)

    def test_handout_explains_platform_access_without_vnc_or_team_passwords(self):
        for text in (
            'credentials.ctfd.team',
            'no team join password to enter',
            'No separate VNC or desktop password is needed',
        ):
            self.assertIn(text, self.source)
        self.assertNotIn('credentials.ctfd.password', self.source)

    def test_new_reservations_fail_closed_when_worker_heartbeat_is_stale(self):
        for text in (
            'registration-worker-heartbeat.json',
            'REGISTRATION_WORKER_HEARTBEAT_MAX_AGE = 15',
            'if not registration_open:',
            'Team setup is temporarily unavailable.',
            'raise your hand for a facilitator',
            'Do not submit a second registration.',
        ):
            self.assertIn(text, self.source)

    def test_needs_operator_preserves_recovery_without_internal_error(self):
        for text in (
            "view == 'needs_operator'",
            'facilitator assistance needed',
            'Do not register again.',
            'Keep your private return link',
            "registration.get('status') == 'needs_operator'",
        ):
            self.assertIn(text, self.source)
        needs_operator_template = self.source.split(
            "{% elif view == 'needs_operator' %}", 1)[1].split(
                "{% elif view == 'ready' %}", 1)[0]
        self.assertNotIn('registration.error', needs_operator_template)


if __name__ == '__main__':
    unittest.main()

