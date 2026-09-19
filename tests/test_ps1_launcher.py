"""E02 launcher static checks: the PowerShell wrapper stays thin, safe and
secret-free. Behavioral lifecycle coverage lives in test_deploy_lifecycle.py.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PS1 = ROOT / 'ridge.ps1'


class LauncherTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = PS1.read_text(encoding='utf-8')

    def test_launcher_exists_at_repo_root(self):
        self.assertTrue(PS1.is_file())

    def test_no_secret_values_or_arguments(self):
        # No plaintext credentials, and no parameter that could carry a password.
        self.assertNotRegex(self.text, re.compile(r'password\s*=\s*["\'][^"\']+["\']', re.I))
        self.assertNotIn('[string]$Password', self.text)
        self.assertNotIn('--password', self.text)
        self.assertNotIn('ConvertTo-SecureString', self.text)

    def test_prerequisite_checks_present(self):
        for needle in ('PSVersionTable', 'docker info', 'LASTEXITCODE', 'DockerDesktop'):
            self.assertIn(needle, self.text)

    def test_no_unexpected_host_changes(self):
        # The launcher must never install, reboot or pull on event day.
        self.assertNotIn('Enable-WindowsOptionalFeature', self.text)
        self.assertNotIn('Restart-Computer', self.text)
        self.assertNotIn('docker pull', self.text)
        self.assertNotIn('Invoke-WebRequest', self.text)
        self.assertNotIn('Invoke-RestMethod', self.text)

    def test_exit_codes_passthrough(self):
        self.assertIn('exit $LASTEXITCODE', self.text)

    def test_quoting_and_argument_array_safety(self):
        # Arguments are passed as separate tokens (no string-built command lines).
        self.assertNotIn('Invoke-Expression', self.text)
        self.assertNotIn('iex ', self.text)
        self.assertIn('--profile $Profile --runtime $Runtime', self.text)

    def test_actions_match_cli(self):
        for action in ('prepare', 'doctor', 'build', 'verify-build', 'up', 'status',
                       'start', 'pause', 'backup', 'restore', 'switch', 'down'):
            self.assertIn("'%s'" % action, self.text)


if __name__ == '__main__':
    unittest.main()
