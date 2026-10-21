import subprocess
import json
import tempfile
import unittest
from unittest.mock import Mock, patch
from pathlib import Path

from ridge.deploy.local import (LocalStack, _windows_process_exists,
                                _windows_process_identity)
from ridge.deploy.registration_worker import _publish_shared_heartbeat


ROOT = Path(__file__).resolve().parents[1]


class RegistrationWorkerProcessTests(unittest.TestCase):
    IDENTITY = {
        'creation_time': '134209440000000000',
        'executable': r'c:\program files\python312\python.exe',
        'command_line': 'python.exe -m ridge.deploy.registration_worker',
    }

    def stack(self, runtime):
        stack = object.__new__(LocalStack)
        stack.runtime = runtime
        stack.profile = {'registration': {'enabled': True}}
        return stack

    def write_worker_metadata(self, runtime, identity=None, updated=None,
                              heartbeat_pid=21444):
        saved = {'pid': 21444, 'token': 'worker-token', 'started': 1000.0}
        if identity is not None:
            saved['identity'] = identity
        (runtime / 'registration-worker.pid').write_text(
            json.dumps(saved), encoding='utf-8')
        (runtime / 'registration-worker-heartbeat.json').write_text(
            json.dumps({'pid': heartbeat_pid, 'token': 'worker-token',
                        'updated': updated if updated is not None else 1000.0}),
            encoding='utf-8')

    def test_worker_publishes_shared_ready_heartbeat_atomically(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'work') as temporary:
            runtime = Path(temporary)
            path = _publish_shared_heartbeat(runtime, now=1234.5)

            self.assertEqual(path, runtime / 'registration' /
                             'registration-worker-heartbeat.json')
            self.assertEqual(json.loads(path.read_text(encoding='utf-8'))['updated'],
                             1234.5)
            self.assertTrue(json.loads(path.read_text(encoding='utf-8'))['ready'])
            self.assertFalse(path.with_name(path.name + '.tmp').exists())

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

    def test_windows_identity_reads_os_owned_creation_and_executable(self):
        api = Mock()
        api.OpenProcess.return_value = 123

        def get_times(_handle, creation, _exit, _kernel, _user):
            creation._obj.dwHighDateTime = 1
            creation._obj.dwLowDateTime = 2
            return 1

        def get_image(_handle, _flags, executable, size):
            executable.value = r'C:\Program Files\Python312\python.exe'
            size._obj.value = len(executable.value)
            return 1

        api.GetProcessTimes.side_effect = get_times
        api.QueryFullProcessImageNameW.side_effect = get_image

        self.assertEqual(_windows_process_identity(21444, api), {
            'creation_time': str((1 << 32) | 2),
            'executable': r'c:\program files\python312\python.exe',
        })
        api.OpenProcess.assert_called_once_with(0x1000, False, 21444)
        api.CloseHandle.assert_called_once_with(123)

    @patch('ridge.deploy.local.time.time', return_value=1001.0)
    @patch('ridge.deploy.local._process_identity')
    def test_worker_status_requires_exact_os_process_identity(self, identity, _now):
        with tempfile.TemporaryDirectory(dir=ROOT / 'work') as temporary:
            runtime = Path(temporary)
            self.write_worker_metadata(runtime, self.IDENTITY)
            identity.return_value = dict(self.IDENTITY)

            status = self.stack(runtime)._registration_worker_status()

            self.assertTrue(status['healthy'])
            self.assertTrue(status['identity_verified'])
            identity.assert_called_once_with(21444)

    @patch('ridge.deploy.local.subprocess.run')
    @patch('ridge.deploy.local._process_identity')
    def test_reused_prior_boot_pid_retires_metadata_without_taskkill(self, identity, run):
        with tempfile.TemporaryDirectory(dir=ROOT / 'work') as temporary:
            runtime = Path(temporary)
            self.write_worker_metadata(runtime, self.IDENTITY, updated=1.0)
            identity.return_value = {
                **self.IDENTITY,
                'creation_time': '134209999999999999',
                'command_line': 'unrelated.exe --service',
            }

            stopped = self.stack(runtime)._stop_registration_worker()

            self.assertFalse(stopped)
            run.assert_not_called()
            self.assertFalse((runtime / 'registration-worker.pid').exists())
            self.assertFalse((runtime / 'registration-worker-heartbeat.json').exists())

    @patch('ridge.deploy.local.subprocess.run')
    @patch('ridge.deploy.local._process_identity')
    def test_legacy_pid_record_retires_without_taskkill(self, identity, run):
        with tempfile.TemporaryDirectory(dir=ROOT / 'work') as temporary:
            runtime = Path(temporary)
            self.write_worker_metadata(runtime, identity=None)
            identity.return_value = dict(self.IDENTITY)

            stopped = self.stack(runtime)._stop_registration_worker()

            self.assertFalse(stopped)
            run.assert_not_called()
            self.assertFalse((runtime / 'registration-worker.pid').exists())

    @patch('ridge.deploy.local.subprocess.run')
    @patch('ridge.deploy.local._process_identity')
    def test_exact_identity_is_required_before_taskkill(self, identity, run):
        with tempfile.TemporaryDirectory(dir=ROOT / 'work') as temporary:
            runtime = Path(temporary)
            self.write_worker_metadata(runtime, self.IDENTITY, updated=1.0)
            identity.return_value = dict(self.IDENTITY)

            with patch('ridge.deploy.local.os.name', 'nt'):
                stopped = self.stack(runtime)._stop_registration_worker()

            self.assertTrue(stopped)
            run.assert_called_once_with(
                ['taskkill', '/PID', '21444', '/T', '/F'],
                capture_output=True, timeout=10)

    @patch('ridge.deploy.local._secure_private', side_effect=lambda path: path)
    @patch('ridge.deploy.local._process_identity')
    @patch('ridge.deploy.local.subprocess.Popen')
    def test_start_persists_os_process_identity(self, popen, identity, _secure):
        with tempfile.TemporaryDirectory(dir=ROOT / 'work') as temporary:
            runtime = Path(temporary)
            stack = self.stack(runtime)
            stack.host = Mock()
            stack.host.randhex.return_value = 'worker-token'
            stack._registration_worker_status = Mock(
                return_value={'healthy': True, 'pid': 21444})
            process = popen.return_value
            process.pid = 21444
            process.poll.return_value = None
            identity.return_value = dict(self.IDENTITY)

            self.assertEqual(stack._start_registration_worker(), 21444)

            saved = json.loads((runtime / 'registration-worker.pid').read_text(
                encoding='utf-8'))
            self.assertEqual(saved['identity'], self.IDENTITY)
            identity.assert_called_once_with(21444)


if __name__ == '__main__':
    unittest.main()
