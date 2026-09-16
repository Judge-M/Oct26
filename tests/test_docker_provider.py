import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from ridge.docker_provider import (
    CommandError,
    DesktopUnavailable,
    DockerDesktopProvider,
    ImageUnavailable,
    SubprocessRunner,
    team_id,
    team_number,
    team_service,
)

COMPOSE = Path('deployment/expanded/compose.desktops.yaml')
IMAGE = 'silent-ridge-desktop:dev'


class FakeRunner:
    """Records argv lists and replays scripted results. Never touches Docker."""

    def __init__(self):
        self.calls = []
        self.rules = []

    def when(self, predicate, result):
        self.rules.append((predicate, result))
        return self

    def run(self, argv, *, check=True):
        argv = list(argv)
        self.calls.append(argv)
        for predicate, result in self.rules:
            if predicate(argv):
                if isinstance(result, Exception):
                    raise result
                return result
        return ''


def inspect_entry(name, service, *, state='running', health='healthy',
                  cpus=2, memory=4 * 1024 ** 3, mounts=()):
    entry = {
        'Name': '/' + name,
        'Config': {'Image': IMAGE, 'Labels': {'com.docker.compose.service': service}},
        'State': {'Status': state},
        'HostConfig': {'NanoCpus': int(cpus * 1_000_000_000), 'Memory': memory},
        'NetworkSettings': {'Networks': {'desktop': {}}},
        'Mounts': [{'Destination': mount} for mount in mounts],
    }
    if health:
        entry['State']['Health'] = {'Status': health}
    return entry


class TeamIdentifierTests(unittest.TestCase):
    def test_normalizes_team_identifiers(self):
        for value in (1, '1', '01', 'team-01', 'team01', 'desktop-01', 'desktop-team01'):
            self.assertEqual(team_number(value), 1)
            self.assertEqual(team_id(value), 'team01')
            self.assertEqual(team_service(value), 'desktop-team01')

    def test_rejects_unknown_identifiers(self):
        for value in ('alpha', '', 'team-123', 0, 100, None, True):
            with self.assertRaises(ValueError):
                team_service(value)


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.runner = FakeRunner()
        self.runner.when(lambda argv: argv[:3] == ['docker', 'image', 'inspect'], '[]')
        self.provider = DockerDesktopProvider(self.runner, teams=10)

    def test_create_checks_image_then_creates_service(self):
        argv = self.provider.create('team-01')
        self.assertEqual(self.runner.calls[0], ['docker', 'image', 'inspect', IMAGE])
        self.assertEqual(argv, ['docker', 'compose', '-f', str(COMPOSE), 'create', 'desktop-team01'])
        self.assertEqual(self.runner.calls[1], argv)

    def test_start_and_stop_use_service_names(self):
        self.assertEqual(self.provider.start('team02'),
                         ['docker', 'compose', '-f', str(COMPOSE), 'start', 'desktop-team02'])
        self.assertEqual(self.provider.stop('desktop-team02'),
                         ['docker', 'compose', '-f', str(COMPOSE), 'stop', 'desktop-team02'])

    def test_create_fails_closed_when_image_is_missing(self):
        runner = FakeRunner()
        runner.when(lambda argv: argv[:3] == ['docker', 'image', 'inspect'],
                    CommandError(['docker', 'image', 'inspect', IMAGE], 1, 'No such image'))
        provider = DockerDesktopProvider(runner)
        with self.assertRaises(ImageUnavailable):
            provider.create('team01')
        self.assertEqual(len(runner.calls), 1)

    def test_every_command_is_a_shell_free_argv_list(self):
        self.provider.create('team01')
        self.provider.start('team01')
        self.provider.stop('team01')
        self.assertTrue(self.runner.calls)
        for call in self.runner.calls:
            self.assertIsInstance(call, list)
            self.assertTrue(all(isinstance(part, str) for part in call))
            self.assertNotIn('shell', call)


class ProbeTests(unittest.TestCase):
    def _provider(self, entry, ps='container-id'):
        runner = FakeRunner()
        runner.when(lambda argv: argv[1:3] == ['compose', '-f'] and 'ps' in argv, ps)
        runner.when(lambda argv: argv[:2] == ['docker', 'inspect'], json.dumps([entry]))
        return runner, DockerDesktopProvider(runner)

    def test_probe_reports_running_healthy_desktop(self):
        entry = inspect_entry('silent-ridge-desktops-desktop-team01-1', 'desktop-team01',
                              mounts=('/evidence', '/originals', '/home/participant/Cases'))
        runner, provider = self._provider(entry)
        status = provider.probe('team01')
        self.assertEqual(status['team'], 'team01')
        self.assertEqual(status['service'], 'desktop-team01')
        self.assertEqual(status['state'], 'running')
        self.assertEqual(status['health'], 'healthy')
        self.assertEqual(status['cpus'], 2.0)
        self.assertEqual(status['memory'], 4 * 1024 ** 3)
        self.assertIn('/evidence', status['mounts'])
        self.assertIn('desktop', status['networks'])
        self.assertEqual(status['container'], 'silent-ridge-desktops-desktop-team01-1')

    def test_probe_fails_closed_when_absent(self):
        runner, provider = self._provider(inspect_entry('x', 'desktop-team01'), ps='')
        with self.assertRaises(DesktopUnavailable):
            provider.probe('team01')

    def test_probe_fails_closed_when_stopped(self):
        entry = inspect_entry('x', 'desktop-team01', state='exited', health=None)
        runner, provider = self._provider(entry)
        with self.assertRaises(DesktopUnavailable):
            provider.probe('team01')

    def test_probe_fails_closed_when_unhealthy(self):
        entry = inspect_entry('x', 'desktop-team01', health='unhealthy')
        runner, provider = self._provider(entry)
        with self.assertRaises(DesktopUnavailable):
            provider.probe('team01')


class InventoryTests(unittest.TestCase):
    def test_inventory_reports_every_container_sorted(self):
        entries = [
            inspect_entry('silent-ridge-desktops-desktop-team02-1', 'desktop-team02', health='unhealthy'),
            inspect_entry('silent-ridge-desktops-desktop-team01-1', 'desktop-team01'),
        ]
        runner = FakeRunner()
        runner.when(lambda argv: argv[1:3] == ['compose', '-f'] and 'ps' in argv, 'id1\nid2')
        runner.when(lambda argv: argv[:2] == ['docker', 'inspect'], json.dumps(entries))
        provider = DockerDesktopProvider(runner)
        result = provider.inventory()
        self.assertEqual([entry['service'] for entry in result], ['desktop-team01', 'desktop-team02'])
        self.assertEqual(result[1]['health'], 'unhealthy')

    def test_inventory_is_empty_without_containers(self):
        runner = FakeRunner()
        runner.when(lambda argv: 'ps' in argv, '')
        provider = DockerDesktopProvider(runner)
        self.assertEqual(provider.inventory(), [])
        self.assertEqual(len(runner.calls), 1)


class SpecTests(unittest.TestCase):
    def test_spec_declares_limits_volumes_and_secret(self):
        provider = DockerDesktopProvider(FakeRunner(), teams=10, cpus='3', memory='6g')
        self.assertEqual(len(provider.teams), 10)
        self.assertEqual(provider.teams[0], 'team01')
        spec = provider.spec('team07')
        self.assertEqual(spec['service'], 'desktop-team07')
        self.assertEqual(spec['cpus'], '3')
        self.assertEqual(spec['memory'], '6g')
        self.assertEqual(spec['vnc_port'], 5901)
        self.assertEqual(spec['network'], 'desktop')
        self.assertEqual(spec['vnc_password_file'], '/run/secrets/vnc_password')
        self.assertEqual(spec['volumes'],
                         {'Cases': 'team07-cases', 'Workspace': 'team07-workspace', 'Scratch': 'team07-scratch'})

    def test_limits_follow_environment(self):
        with patch.dict(os.environ, {'RIDGE_DESKTOP_CPUS': '8', 'RIDGE_DESKTOP_MEMORY': '16g'}):
            provider = DockerDesktopProvider(FakeRunner())
        self.assertEqual(provider.cpus, '8')
        self.assertEqual(provider.memory, '16g')


class SubprocessRunnerTests(unittest.TestCase):
    def test_runs_an_argv_list_without_a_shell(self):
        output = SubprocessRunner().run([sys.executable, '-c', 'print("ok")'])
        self.assertEqual(output, 'ok')


if __name__ == '__main__':
    unittest.main()
