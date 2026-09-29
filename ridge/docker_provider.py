"""Deterministic Docker orchestration for per-team desktop containers.

The Docker-only desktop pivot keeps the Hyper-V path working and adds a
container provider with the same lifecycle shape: create, start, stop, probe and
inventory. Every Docker command is emitted as an argv list (never through a
shell) so orchestration is auditable and can be driven by a fake runner in
tests.

Containers are declared in ``deployment/expanded/compose.desktops.yaml`` and
join the external ``desktop`` network under their service name, so Guacamole
reaches each desktop at ``<service-name>:5901``. VNC is never published to the
host.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Protocol, Sequence

COMPOSE_FILE = Path('deployment/expanded/compose.desktops.yaml')
PROJECT = 'silent-ridge-desktops'
DEFAULT_IMAGE = 'silent-ridge-desktop:dev'
DEFAULT_CPUS = '2'
DEFAULT_MEMORY = '4g'
VNC_PORT = 5901
DEFAULT_TEAMS = 10
_TEAM = re.compile(r'(?:desktop-)?(?:team-?)?(\d{1,2})')


class CommandError(RuntimeError):
    """A runner command exited non-zero while ``check`` was requested."""

    def __init__(self, argv, returncode, stderr=''):
        message = 'command failed (%s): %s' % (returncode, ' '.join(argv))
        if stderr:
            message += '\n' + stderr
        super().__init__(message)
        self.argv = list(argv)
        self.returncode = returncode
        self.stderr = stderr


class DockerDesktopError(RuntimeError):
    """Base class for provider failures that must fail closed."""


class ImageUnavailable(DockerDesktopError):
    """The locally loaded desktop image is missing; ``pull_policy: never``."""


class DesktopUnavailable(DockerDesktopError):
    """The requested desktop container is absent, stopped or unhealthy."""


class CommandRunner(Protocol):
    """Runs an argv list and returns captured standard output."""

    def run(self, argv: Sequence[str], *, check: bool = True) -> str:
        ...


class SubprocessRunner:
    """Real runner. Executes argv directly; ``shell=True`` is never used."""

    def run(self, argv, *, check=True):
        completed = subprocess.run(list(argv), capture_output=True, text=True, timeout=300)
        if check and completed.returncode != 0:
            raise CommandError(list(argv), completed.returncode, completed.stderr.strip())
        return completed.stdout.strip()


def team_number(team):
    """Normalize ``1``, ``'01'``, ``'team-01'`` or ``'desktop-team01'`` to an int."""
    if isinstance(team, bool) or not isinstance(team, (int, str)):
        raise ValueError('Unknown team identifier: %r' % (team,))
    if isinstance(team, int):
        number = team
    else:
        match = _TEAM.fullmatch(team.strip())
        if not match:
            raise ValueError('Unknown team identifier: %r' % (team,))
        number = int(match.group(1))
    if not 1 <= number <= 99:
        raise ValueError('Team number out of range: %r' % (team,))
    return number


def team_id(team):
    """Canonical team id, for example ``team01``."""
    return 'team%02d' % team_number(team)


def team_service(team):
    """Compose service name, for example ``desktop-team01``."""
    return 'desktop-%s' % team_id(team)


class DockerDesktopProvider:
    """Drive the ``compose.desktops.yaml`` services through Docker.

    ``create``/``start``/``stop`` change lifecycle, ``probe`` fails closed unless
    a container is running and healthy, and ``inventory`` reports every declared
    team desktop. All commands are deterministic argv lists.
    """

    def __init__(self, runner, *, teams=DEFAULT_TEAMS, compose_file=COMPOSE_FILE,
                 project=PROJECT, image=None, cpus=None, memory=None, vnc_port=VNC_PORT):
        self.runner = runner
        self.compose_file = Path(compose_file)
        self.project = project
        self.image = image or os.environ.get('RIDGE_DESKTOP_IMAGE', DEFAULT_IMAGE)
        self.cpus = str(cpus if cpus is not None else os.environ.get('RIDGE_DESKTOP_CPUS', DEFAULT_CPUS))
        self.memory = str(memory if memory is not None else os.environ.get('RIDGE_DESKTOP_MEMORY', DEFAULT_MEMORY))
        self.vnc_port = vnc_port
        self._teams = tuple(team_id(number) for number in range(1, teams + 1))

    @property
    def teams(self):
        return self._teams

    def compose(self, *args):
        """Return a ``docker compose`` argv list for this project."""
        return ['docker', 'compose', '--project-name', self.project, '-f', str(self.compose_file), *args]

    def service(self, team):
        return team_service(team)

    def spec(self, team):
        """Deterministic declaration of one team desktop container."""
        identifier = team_id(team)
        return {
            'team': identifier,
            'service': team_service(identifier),
            'image': self.image,
            'vnc_port': self.vnc_port,
            'cpus': self.cpus,
            'memory': self.memory,
            'network': 'desktop',
            'vnc_password_file': '/run/secrets/vnc_password',
            'evidence': '/evidence',
            'originals': '/originals',
            'volumes': {
                'Cases': identifier + '-cases',
                'Workspace': identifier + '-workspace',
                'Scratch': identifier + '-scratch',
            },
        }

    def require_image(self):
        """Fail closed unless the desktop image is already loaded locally."""
        argv = ['docker', 'image', 'inspect', self.image]
        try:
            self.runner.run(argv)
        except CommandError as error:
            raise ImageUnavailable(
                'Desktop image %r is not loaded locally and pull_policy is never' % self.image) from error
        return argv

    def create(self, team):
        self.require_image()
        argv = self.compose('create', self.service(team))
        self.runner.run(argv)
        return argv

    def start(self, team):
        argv = self.compose('start', self.service(team))
        self.runner.run(argv)
        return argv

    def stop(self, team):
        argv = self.compose('stop', self.service(team))
        self.runner.run(argv)
        return argv

    def probe(self, team):
        """Return health/limits, failing closed unless running and healthy."""
        service = self.service(team)
        identifiers = self._container_ids(team)
        if not identifiers:
            raise DesktopUnavailable('No container for %s; create and start it first' % service)
        status = self._status(self._inspect(identifiers)[0])
        if status['state'] != 'running':
            raise DesktopUnavailable('%s is %r, not running' % (service, status['state']))
        if status['health'] != 'healthy':
            raise DesktopUnavailable('%s health is %r' % (service, status['health']))
        return {'team': team_id(team), 'service': service, **status}

    def inventory(self):
        """Report every existing team desktop container, healthy or not."""
        identifiers = self._container_ids()
        if not identifiers:
            return []
        entries = []
        for data in self._inspect(identifiers):
            labels = (data.get('Config') or {}).get('Labels') or {}
            service = labels.get('com.docker.compose.service') or str(data.get('Name', '')).lstrip('/')
            entries.append({'service': service, **self._status(data)})
        return sorted(entries, key=lambda entry: entry['service'])

    def _container_ids(self, team=None):
        args = ['ps', '-a', '-q']
        if team is not None:
            args.append(self.service(team))
        output = self.runner.run(self.compose(*args))
        return [line.strip() for line in output.splitlines() if line.strip()]

    def _inspect(self, identifiers):
        return json.loads(self.runner.run(['docker', 'inspect', *identifiers]))

    @staticmethod
    def _status(data):
        state = data.get('State') or {}
        health = (state.get('Health') or {}).get('Status')
        host = data.get('HostConfig') or {}
        nanocpus = host.get('NanoCpus') or 0
        return {
            'container': str(data.get('Name', '')).lstrip('/'),
            'state': state.get('Status'),
            'health': health,
            'image': (data.get('Config') or {}).get('Image'),
            'cpus': nanocpus / 1_000_000_000 if nanocpus else None,
            'memory': host.get('Memory') or None,
            'networks': sorted(((data.get('NetworkSettings') or {}).get('Networks') or {})),
            'mounts': sorted(mount['Destination'] for mount in data.get('Mounts', []) if mount.get('Destination')),
        }
