import tempfile
import unittest
from pathlib import Path

from ridge.deploy import Deployment, DeploymentError


class FakeProvider:
    def __init__(self, fail=None, health=True):
        self.calls = []
        self.fail = fail
        self.ready = health

    def probe(self):
        self.calls.append('probe')
        return {'ready': True}

    def provision(self, step):
        self.calls.append('provision:' + step)
        if self.fail == step:
            raise DeploymentError('Missing artifact for ' + step)
        return {'verified': True, 'resources': {step: 'res-' + step}}

    def health(self):
        self.calls.append('health')
        return {'ready': self.ready, 'reason': 'not ready'}

    def start(self):
        self.calls.append('start')
        return {}

    def pause(self):
        self.calls.append('pause')
        return {}

    def backup(self, destination):
        self.calls.append('backup')
        return {'verified': True, 'destination': str(destination)}

    def restore(self, recovery_set):
        self.calls.append('restore')
        return {'verified': True}

    def down(self, retain_backup):
        self.calls.append('down')
        return {'retained': ['snapshot-1'] if retain_backup else []}

    def resources(self):
        return {}


class DeploymentTests(unittest.TestCase):
    def test_up_paused_by_default_and_resumable(self):
        with tempfile.TemporaryDirectory() as folder:
            work = Path(folder) / 'work'
            first = FakeProvider()
            document = Deployment('ridge-oct26', work, first).up('v1.0.0', {'region': 'local'})
            self.assertEqual(document['state'], 'PROVISIONED_PAUSED')
            self.assertNotIn('start', first.calls)
            self.assertEqual(document['pending'], [])
            self.assertIn('paused', document['summary'])
            second = FakeProvider()
            resumed = Deployment('ridge-oct26', work, second).up('v1.0.0', {'region': 'local'})
            self.assertEqual(resumed['state'], 'PROVISIONED_PAUSED')
            self.assertEqual(second.calls, [])
            running = Deployment('ridge-oct26', work, second).start()
            self.assertEqual(running['state'], 'RUNNING')
            self.assertIn('start', second.calls)

    def test_start_cannot_skip_failed_check_and_resumes(self):
        with tempfile.TemporaryDirectory() as folder:
            work = Path(folder) / 'work'
            provider = FakeProvider(fail='evidence')
            with self.assertRaisesRegex(DeploymentError, 'Missing artifact'):
                Deployment('e', work, provider).up('v1.0.0', {})
            status = Deployment('e', work, provider).status()
            self.assertEqual(status['state'], 'DESKTOPS_READY')
            self.assertEqual(status['pending'], ['evidence'])
            with self.assertRaisesRegex(DeploymentError, 'before every readiness step'):
                Deployment('e', work, provider).start()
            fixed = FakeProvider()
            result = Deployment('e', work, fixed).up('v1.0.0', {})
            self.assertEqual(result['state'], 'PROVISIONED_PAUSED')
            self.assertEqual(fixed.calls, ['provision:evidence'])

    def test_missing_artifact_never_resets_and_release_binding(self):
        with tempfile.TemporaryDirectory() as folder:
            work = Path(folder) / 'work'
            provider = FakeProvider(fail='artifacts')
            with self.assertRaisesRegex(DeploymentError, 'Missing artifact'):
                Deployment('e', work, provider).up('v1.0.0', {})
            journal = Deployment('e', work, provider)
            self.assertEqual(journal.status()['state'], 'NEW')
            with self.assertRaisesRegex(DeploymentError, 'different release'):
                journal.up('v2.0.0', {})
            result = Deployment('e', work, FakeProvider()).up('v1.0.0', {})
            self.assertEqual(result['state'], 'PROVISIONED_PAUSED')

    def test_health_gate_and_backup_down_guards(self):
        with tempfile.TemporaryDirectory() as folder:
            work = Path(folder) / 'work'
            provider = FakeProvider(health=False)
            Deployment('e', work, provider).up('v1.0.0', {})
            with self.assertRaisesRegex(DeploymentError, 'Readiness check failed'):
                Deployment('e', work, provider).start()
            with self.assertRaisesRegex(DeploymentError, 'without a verified backup'):
                Deployment('e', work, provider).down()
            verified = Deployment('e', work, provider).backup(Path(folder) / 'backup')
            self.assertEqual(verified['state'], 'BACKUP_VERIFIED')
            teardown = Deployment('e', work, provider).down()
            self.assertEqual(teardown['state'], 'DESTROYED')

    def test_event_lock_is_exclusive(self):
        with tempfile.TemporaryDirectory() as folder:
            work = Path(folder) / 'work'
            deployment = Deployment('e', work, FakeProvider())
            with deployment.lock():
                with self.assertRaisesRegex(DeploymentError, 'event lock'):
                    Deployment('e', work, FakeProvider()).up('v1.0.0', {})


if __name__ == '__main__':
    unittest.main()
