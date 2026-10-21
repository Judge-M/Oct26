import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BOOT = ROOT / 'scripts' / 'windows' / 'Start-SilentRidgeBoot.ps1'
INSTALL = ROOT / 'scripts' / 'windows' / 'Install-SilentRidgeBootTask.ps1'
PRIMARY = ROOT / 'deployment' / 'windows' / 'primary-boot.example.json'
WORKER = ROOT / 'deployment' / 'windows' / 'worker-boot.example.json'


class WindowsBootAutomationTests(unittest.TestCase):
    def test_examples_are_valid_role_specific_json_without_secrets(self):
        primary = json.loads(PRIMARY.read_text(encoding='utf-8'))
        worker = json.loads(WORKER.read_text(encoding='utf-8'))
        self.assertEqual(1, primary['schema_version'])
        self.assertEqual('primary', primary['role'])
        self.assertEqual(['ridge-worker-02'], primary['remote_docker_contexts'])
        self.assertEqual(3, primary['status_attempts'])
        self.assertEqual(10, primary['status_retry_seconds'])
        self.assertEqual('worker', worker['role'])
        self.assertNotIn('source_path', worker)
        for document in (primary, worker):
            serialized = json.dumps(document).lower()
            self.assertNotIn('password', serialized)
            self.assertNotIn('private_key', serialized)

    def test_boot_action_is_bounded_and_non_destructive(self):
        source = BOOT.read_text(encoding='utf-8')
        self.assertIn('Wait-DockerContext', source)
        self.assertIn('deployment_command_timeout_seconds', source)
        self.assertIn('function Get-DeploymentStatus', source)
        self.assertIn('remained unknown', source)
        self.assertGreaterEqual(source.count('Get-DeploymentStatus $pythonPath'), 3)
        self.assertIn("'up'", source)
        self.assertIn("'start'", source)
        self.assertIn("'pause'", source)
        self.assertLess(source.index('$up = Invoke-BoundedProcess'),
                        source.index('$start = Invoke-BoundedProcess'))
        self.assertIn("'RUNNING'", source)
        self.assertIn('event_ready', source)
        for forbidden in ('down --volumes', "'restore'", "'build'", "'fence'"):
            self.assertNotIn(forbidden, source)

    def test_installer_has_separate_startup_and_interactive_tasks(self):
        source = INSTALL.read_text(encoding='utf-8')
        self.assertIn('New-ScheduledTaskTrigger -AtStartup', source)
        self.assertIn('New-ScheduledTaskTrigger -AtLogOn', source)
        self.assertIn('$startupTaskName = "Silent Ridge - $Role Boot"', source)
        self.assertIn('$logonTaskName = "Silent Ridge - $Role Logon"', source)
        self.assertIn('New-ScheduledTaskPrincipal', source)
        self.assertIn('-LogonType Interactive', source)
        self.assertIn('-Principal $interactivePrincipal', source)
        self.assertIn('Register-ScheduledTask', source)
        self.assertIn('-Force', source)
        self.assertIn('RestartCount 5', source)
        self.assertIn('[PSCredential]$TaskCredential', source)
        self.assertIn('[switch]$CurrentUserInteractive', source)
        self.assertNotRegex(source, re.compile(r'password\s*=\s*["\'][^"\']+["\']', re.I))

    def test_task_limit_is_computed_from_the_configured_worst_case(self):
        source = INSTALL.read_text(encoding='utf-8')
        self.assertIn('$worstCaseSeconds', source)
        self.assertIn('$statusEnvelope', source)
        self.assertIn('$upEnvelope', source)
        self.assertIn('$remoteEnvelope', source)
        self.assertIn('New-TimeSpan -Seconds $worstCaseSeconds', source)
        self.assertNotIn('New-TimeSpan -Hours 2', source)

    def test_unknown_initial_status_gates_up(self):
        source = BOOT.read_text(encoding='utf-8')
        status_call = source.index("'initial deployment status'")
        up_call = source.index('$up = Invoke-BoundedProcess')
        self.assertLess(status_call, up_call)
        self.assertIn('refusing lifecycle mutation', source)


if __name__ == '__main__':
    unittest.main()
