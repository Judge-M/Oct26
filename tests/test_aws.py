import json
import tempfile
import unittest
from pathlib import Path

from ridge import aws_image, aws_infra, aws_teardown
from ridge.aws import Aws, AwsAuthError, AwsEnvironmentError


class FakeRunner:
    def __init__(self, fail_on=None, auth_error=False):
        self.calls = []
        self.fail_on = fail_on
        self.auth_error = auth_error

    def __call__(self, command):
        self.calls.append(command)
        if self.auth_error:
            raise AwsAuthError('expired credentials')
        if self.fail_on and self.fail_on in ' '.join(command):
            raise RuntimeError('simulated failure')
        return {'id': 'id-%02d' % len(self.calls), 'ImageId': 'ami-%02d' % len(self.calls)}


class AwsImageTests(unittest.TestCase):
    def test_convert_and_import_commands(self):
        with self.assertRaisesRegex(ValueError, 'Unsupported'):
            aws_image.convert_command('a', 'b', fmt='qcow2')
        self.assertEqual(aws_image.convert_command('a', 'b')[:3], ['qemu-img', 'convert', '-O'])
        command = aws_image.import_image_command('bucket', 'key', 'us-east-1')
        self.assertIn('Format=raw', ' '.join(command))
        self.assertIn('import-image', command)
        self.assertIn('import-snapshot', aws_image.import_snapshot_command('b', 'k', 'r'))

    def test_cache_by_hash_and_launch_guard(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            image = root / 'desktop.raw'
            image.write_bytes(b'disk bytes')
            inventory = root / 'inventory.json'
            runner = FakeRunner()
            first = aws_image.ensure_image(Aws(runner), image, 'bucket', 'key', 'us-east-1',
                                           'v1.0.0', inventory)
            self.assertFalse(first['cached'])
            calls = len(runner.calls)
            second = aws_image.ensure_image(Aws(runner), image, 'bucket', 'key', 'us-east-1',
                                            'v1.0.0', inventory)
            self.assertTrue(second['cached'])
            self.assertEqual(len(runner.calls), calls)
            with self.assertRaises(AwsEnvironmentError):
                aws_image.launch_guard(False)

    def test_default_runner_is_blocked(self):
        with self.assertRaises(AwsEnvironmentError):
            Aws().call('aws', 'ec2', 'describe-instances')


class AwsInfraTests(unittest.TestCase):
    def test_plan_scales_and_validation(self):
        self.assertEqual(aws_infra.plan({'teams': 2, 'region': 'us-east-1'})['resources']['desktop_instance'], 2)
        self.assertEqual(aws_infra.plan({'teams': 10, 'region': 'us-east-1'})['resources']['desktop_instance'], 10)
        with self.assertRaisesRegex(ValueError, 'at least one team'):
            aws_infra.plan({'teams': 0})
        bad = dict(schema=1, region='r', resources={'central_instance': 1, 'desktop_instance': 1},
                   ingress=[dict(cidr='0.0.0.0/0', internal=True)])
        with self.assertRaisesRegex(ValueError, 'must not be public'):
            aws_infra.validate(bad)

    def test_create_is_idempotent_and_resumable(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            journal = root / 'infra.json'
            document = aws_infra.plan({'teams': 2, 'region': 'us-east-1'})
            runner = FakeRunner()
            first = aws_infra.create(Aws(runner), document, journal, 'ridge-oct26')
            total = len(first['resources'])
            self.assertEqual(total, sum(document['resources'].values()))
            calls = len(runner.calls)
            aws_infra.create(Aws(runner), document, journal, 'ridge-oct26')
            self.assertEqual(len(runner.calls), calls)
            # Interrupted create resumes from the first missing resource.
            journal2 = root / 'infra2.json'
            failing = FakeRunner(fail_on='create-volume')
            with self.assertRaises(AwsEnvironmentError):
                aws_infra.create(Aws(failing), document, journal2, 'ridge-oct26')
            partial = json.loads(journal2.read_text())
            self.assertTrue(partial['resources'])
            resuming = FakeRunner()
            completed = aws_infra.create(Aws(resuming), document, journal2, 'ridge-oct26')
            self.assertEqual(len(completed['resources']), total)
            self.assertTrue(any('create-volume' in ' '.join(call) for call in resuming.calls))
            self.assertFalse(any('create-vpc' in ' '.join(call) for call in resuming.calls))


class AwsTeardownTests(unittest.TestCase):
    def journal(self, root):
        document = aws_infra.plan({'teams': 1, 'region': 'us-east-1'})
        runner = FakeRunner()
        aws_infra.create(Aws(runner), document, root / 'infra.json', 'ridge-oct26')
        return root / 'infra.json'

    def test_teardown_requires_backup_and_deletes_only_owned(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            journal = self.journal(root)
            with self.assertRaisesRegex(ValueError, 'verified restorable backup'):
                aws_teardown.teardown(Aws(FakeRunner()), journal, backup_verified=False)
            runner = FakeRunner()
            dry = aws_teardown.teardown(Aws(runner), journal, backup_verified=True)
            self.assertEqual(runner.calls, [])
            self.assertTrue(dry['planned'])
            applied = aws_teardown.teardown(Aws(runner), journal, backup_verified=True, apply=True)
            self.assertEqual(len(applied['deleted']), len(applied['planned']))
            self.assertEqual(len(runner.calls), len(applied['planned']))

    def test_expired_credentials_safe_outcome_and_cost_report(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            journal = self.journal(root)
            result = aws_teardown.teardown(Aws(FakeRunner(auth_error=True)), journal,
                                           backup_verified=True, apply=True)
            self.assertTrue(result['safe'])
            self.assertEqual(result['action'], 'reauthenticate')
            retained = [dict(kind='instance', state='stopped'), dict(kind='instance', state='running'),
                        dict(kind='volume')]
            report = aws_teardown.cost_report(retained)
            self.assertEqual(report['stopped_compute_ebs'], 2)
            self.assertEqual(report['running_compute'], 1)

    def test_expiry_requires_policy(self):
        with self.assertRaisesRegex(ValueError, 'TTL expiry'):
            aws_teardown.expiry_check(now=100, expires=None)
        self.assertTrue(aws_teardown.expiry_check(now=100, expires=50)['expired'])
        self.assertFalse(aws_teardown.expiry_check(now=10, expires=50)['expired'])


if __name__ == '__main__':
    unittest.main()
