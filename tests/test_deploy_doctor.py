"""Doctor reports its scope and backup prerequisite without changing state."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ridge.deploy.__main__ import doctor
from ridge.deploy import recovery


class DoctorTests(unittest.TestCase):
    @patch('ridge.deploy.__main__.docker', return_value='ok')
    def test_unscoped_doctor_only_claims_docker(self, unused):
        result = doctor()
        self.assertEqual(result['scope'], 'docker-only')
        self.assertNotIn('backup_key', result['checks'])
        self.assertFalse(result['event_ready'])

    @patch('ridge.deploy.__main__.docker', return_value='ok')
    def test_scoped_doctor_reports_bad_profile_and_missing_backup_key(self, unused):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'profile.json'
            path.write_text('{}', encoding='utf-8')
            with patch.dict(os.environ, {'RIDGE_BACKUP_KEY': ''}):
                result = doctor(path, Path(folder) / 'runtime', Path(folder))
        self.assertEqual(result['scope'], 'deployment')
        self.assertFalse(result['checks']['profile']['ok'])
        self.assertFalse(result['checks']['backup_key']['ok'])
        self.assertFalse(result['ready_for_up'])
        self.assertNotIn('secret', json.dumps(result).lower())

    def test_missing_backup_key_refuses_before_creating_recovery_set(self):
        with tempfile.TemporaryDirectory() as folder:
            destination = Path(folder) / 'recovery'
            with patch.dict(os.environ, {'RIDGE_BACKUP_KEY': ''}):
                with self.assertRaisesRegex(recovery.RecoveryError, 'RIDGE_BACKUP_KEY'):
                    recovery.create(object(), destination)
            self.assertFalse(destination.exists())


if __name__ == '__main__':
    unittest.main()
