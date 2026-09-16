import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

LAUNCHER = Path(__file__).resolve().parents[1] / 'ridge.ps1'


def powershell():
    return shutil.which('powershell') or shutil.which('pwsh')


@unittest.skipUnless(os.name == 'nt' and powershell(), 'Windows PowerShell required')
class LauncherTests(unittest.TestCase):
    def run_launcher(self, *arguments):
        return subprocess.run([powershell(), '-NoProfile', '-ExecutionPolicy', 'Bypass',
                               '-File', str(LAUNCHER), *arguments],
                              capture_output=True, text=True, timeout=120)

    def test_check_only_reports_prerequisites(self):
        result = self.run_launcher('-CheckOnly')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Python', result.stdout)
        self.assertIn('PowerShell', result.stdout)

    def test_invalid_profile_and_secret_argument_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            bad = Path(folder) / 'profile.json'
            bad.write_text('{not json')
            result = self.run_launcher('-CheckOnly', '-Profile', str(bad))
            self.assertEqual(result.returncode, 2)
            self.assertIn('not valid JSON', result.stdout)
            result = self.run_launcher('-CheckOnly', 'password=hunter2')
            self.assertEqual(result.returncode, 2)
            self.assertIn('secrets', result.stdout)

    def test_spaces_in_paths_and_status_invocation(self):
        with tempfile.TemporaryDirectory() as folder:
            work = Path(folder) / 'work with spaces'
            result = self.run_launcher('-CheckOnly', '-Work', str(work))
            self.assertEqual(result.returncode, 0, result.stderr)
            result = self.run_launcher('-Action', 'status', '-Event', 'ridge-oct26', '-Work', str(work))
            self.assertEqual(result.returncode, 0, result.stderr)
            document = json.loads(result.stdout)
            self.assertEqual(document['state'], 'NEW')
            self.assertEqual(document['event'], 'ridge-oct26')


if __name__ == '__main__':
    unittest.main()
