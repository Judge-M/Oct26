"""Static safety and contract checks for the Windows participant handoff."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts' / 'setup-participant-windows.ps1'


class ParticipantSetupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = SCRIPT.read_text(encoding='utf-8')

    def test_script_exists_and_has_safe_modes(self):
        self.assertTrue(SCRIPT.is_file())
        for term in ('DryRun', 'VerifyOnly', 'ImportCertificate', 'OpenTabs'):
            self.assertIn(term, self.text)

    def test_requires_https_and_validates_all_services(self):
        self.assertIn("$name in 'ctfd','iris','wazuh','guacamole'", self.text)
        self.assertIn("$value -notmatch '^https://", self.text)
        self.assertIn('Test-TcpEndpoint', self.text)

    def test_trust_change_is_explicit_and_current_user_scoped(self):
        self.assertIn('ShouldProcess', self.text)
        self.assertIn('Cert:\\CurrentUser\\Root', self.text)
        self.assertNotIn('Cert:\\LocalMachine\\Root', self.text)

    def test_credentials_are_file_input_and_acl_protected(self):
        self.assertIn('$CredentialFile', self.text)
        self.assertIn('team-credentials.json', self.text)
        self.assertIn('SetAccessRuleProtection', self.text)
        self.assertNotRegex(self.text, re.compile(r'password\s*=\s*["\'][^"\']+["\']', re.I))
        self.assertNotIn('Write-Host $credential', self.text)

    def test_outputs_sanitized_results_and_opens_https_tabs(self):
        self.assertIn('ca_fingerprint', self.text)
        self.assertIn('endpoints_reachable', self.text)
        self.assertIn('Start-Process $url', self.text)
        self.assertNotIn('http://', self.text)


if __name__ == '__main__':
    unittest.main()
