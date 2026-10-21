import unittest

from ridge.participant_handout import credential_handout_text


class ParticipantHandoutTextTests(unittest.TestCase):
    def setUp(self):
        self.registration = {
            'team_name': 'Blue Lanterns',
            'result': {'desktop_urls': [{
                'connection_name': 'desktop-slot01',
                'name': 'Endpoint analysis',
                'guidance': 'Start with the endpoint image.',
            }]},
        }
        self.credentials = {
            'ctfd': {
                'team': 'team-01',
                'password': 'operator-only-team-password',
                'members': [
                    {'username': 'team-01-p01', 'password': 'seat-one-secret'},
                    {'username': 'team-01-p02', 'password': 'seat-two-secret'},
                ],
            },
            'iris': {'username': 'team-01', 'password': 'iris-secret'},
            'wazuh': {'username': 'ridge-reader', 'password': 'wazuh-secret'},
            'guacamole': {'username': 'team-01', 'password': 'guac-secret'},
        }

    def render(self):
        return credential_handout_text(
            self.registration, self.credentials,
            retrieval_url='https://ctfd.example/silent-ridge/registration/private-token',
            ctfd_url='https://ctfd.example/login',
            iris_url='https://iris.example/silent-ridge',
            wazuh_url='https://wazuh.example/app/discover',
            guac_url='https://guac.example')

    def test_labels_every_participant_platform_and_recovery_link(self):
        text = self.render()
        for expected in (
            'Return to this handout: https://ctfd.example/silent-ridge/registration/private-token',
            'CTFd - questions, answers, and help',
            'URL: https://ctfd.example/login',
            'Team ID: team-01',
            'Seat 1 username: team-01-p01',
            'Seat 1 password: seat-one-secret',
            'IRIS - incident queue and shared findings',
            'URL: https://iris.example/silent-ridge',
            'Username: ridge-reader',
            'Wazuh Discover - prepared telemetry view',
            'Guacamole - three investigation desktops',
            'desktop-slot01: Endpoint analysis - Start with the endpoint image.',
        ):
            self.assertIn(expected, text)

    def test_omits_operator_only_team_and_direct_vnc_passwords(self):
        text = self.render()
        self.assertNotIn('operator-only-team-password', text)
        self.assertIn('no team join password is required', text)
        self.assertIn('no separate direct VNC password is participant-facing', text)


if __name__ == '__main__':
    unittest.main()

