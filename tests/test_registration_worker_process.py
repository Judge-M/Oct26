import subprocess
import unittest
from unittest.mock import patch

from ridge.deploy.local import _windows_process_exists


class RegistrationWorkerProcessTests(unittest.TestCase):
    @patch('ridge.deploy.local.subprocess.run')
    def test_tasklist_zero_exit_without_a_row_is_not_alive(self, run):
        run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0,
            stdout='INFO: No tasks are running which match the specified criteria.\n',
            stderr='')

        self.assertFalse(_windows_process_exists(21444))

    @patch('ridge.deploy.local.subprocess.run')
    def test_exact_csv_pid_row_is_alive(self, run):
        run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0,
            stdout='"python.exe","21444","Console","1","12,345 K"\n',
            stderr='')

        self.assertTrue(_windows_process_exists(21444))
        run.assert_called_once_with(
            ['tasklist', '/FI', 'PID eq 21444', '/FO', 'CSV', '/NH'],
            capture_output=True, text=True, timeout=5)

    @patch('ridge.deploy.local.subprocess.run')
    def test_different_pid_row_is_not_alive(self, run):
        run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0,
            stdout='"python.exe","21445","Console","1","12,345 K"\n',
            stderr='')

        self.assertFalse(_windows_process_exists(21444))


if __name__ == '__main__':
    unittest.main()
