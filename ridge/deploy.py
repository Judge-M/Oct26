"""E01 - shared deployment CLI and lifecycle state machine.

`python -m ridge.deploy prepare/up/status/start/pause/backup/restore/down` drives a
provider through the state machine in EXECUTION.md. It enforces per-event locking,
resumable step receipts, paused-by-default setup and an explicit `--start` that only
runs after every readiness check passes. Provider logic lives behind the `Provider`
protocol; the concrete deployment-profile provider is owned by the A03/A04 lane and is
PENDING, so this module never invents profile fields.
"""
import argparse
import importlib
import json
import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Protocol

STATES = ('NEW', 'ARTIFACTS_VERIFIED', 'INFRASTRUCTURE_READY', 'APPLICATIONS_READY',
          'IDENTITIES_READY', 'DESKTOPS_READY', 'EVIDENCE_READY', 'PROVISIONED_PAUSED',
          'RUNNING', 'PAUSED', 'BACKUP_VERIFIED', 'STOPPED', 'DESTROYED')

STEPS = (('artifacts', 'ARTIFACTS_VERIFIED'),
         ('infrastructure', 'INFRASTRUCTURE_READY'),
         ('applications', 'APPLICATIONS_READY'),
         ('identities', 'IDENTITIES_READY'),
         ('desktops', 'DESKTOPS_READY'),
         ('evidence', 'EVIDENCE_READY'))

PROFILE_SCHEMA = 'PENDING A04'


class DeploymentError(RuntimeError):
    """A deployment step failed; the journal is preserved for a safe retry."""


class Provider(Protocol):
    def probe(self) -> dict[str, Any]: ...
    def provision(self, step: str) -> dict[str, Any]: ...
    def health(self) -> dict[str, Any]: ...
    def start(self) -> dict[str, Any]: ...
    def pause(self) -> dict[str, Any]: ...
    def backup(self, destination) -> dict[str, Any]: ...
    def restore(self, recovery_set) -> dict[str, Any]: ...
    def down(self, retain_backup: bool) -> dict[str, Any]: ...
    def resources(self) -> dict[str, Any]: ...


class Deployment:
    def __init__(self, event, work, provider):
        self.event = event
        self.work = Path(work)
        self.provider = provider
        self.event_dir = self.work / 'events' / event
        self.journal_path = self.event_dir / 'journal.json'
        self.lock_path = self.event_dir / 'lock'

    @contextmanager
    def lock(self):
        self.event_dir.mkdir(parents=True, exist_ok=True)
        try:
            descriptor = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError as error:
            raise DeploymentError('Another deployment holds the event lock') from error
        try:
            os.write(descriptor, str(os.getpid()).encode())
            yield
        finally:
            os.close(descriptor)
            self.lock_path.unlink(missing_ok=True)

    def _load(self):
        if self.journal_path.is_file():
            return json.loads(self.journal_path.read_text(encoding='utf-8'))
        return dict(event=self.event, state='NEW', release=None, completed={}, receipts={},
                    resources={}, active_site_generation=0)

    def _save(self, journal):
        self.event_dir.mkdir(parents=True, exist_ok=True)
        self.journal_path.write_text(json.dumps(journal, indent=2, sort_keys=True) + '\n', encoding='utf-8')

    def _step_state(self, journal):
        state = 'NEW'
        for step, reached in STEPS:
            if journal['completed'].get(step):
                state = reached
        return state

    def prepare(self, release, profile):
        with self.lock():
            journal = self._load()
            if journal.get('release') and journal['release'] != release:
                raise DeploymentError('Event is bound to a different release; refusing to reset')
            journal['release'] = release
            journal['profile_fingerprint'] = _fingerprint(profile)
            probe = self.provider.probe()
            if probe.get('ready') is not True:
                journal['probe'] = probe
                self._save(journal)
                raise DeploymentError('Prerequisites are not ready: ' + _reason(probe))
            journal['probe'] = probe
            self._save(journal)
            return self.status()

    def up(self, release, profile, start=False):
        with self.lock():
            journal = self._load()
            if journal.get('release') and journal['release'] != release:
                raise DeploymentError('Event is bound to a different release; refusing to reset')
            journal['release'] = release
            journal['profile_fingerprint'] = _fingerprint(profile)
            for step, reached in STEPS:
                if journal['completed'].get(step):
                    continue
                try:
                    result = self.provider.provision(step)
                except DeploymentError:
                    journal['state'] = self._step_state(journal)
                    self._save(journal)
                    raise
                if result.get('verified') is not True:
                    journal['state'] = self._step_state(journal)
                    self._save(journal)
                    raise DeploymentError('Step was not verified: ' + step)
                journal['completed'][step] = True
                journal['receipts'][step] = dict(result, recorded=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()))
                journal['resources'] = dict(journal.get('resources', {}), **result.get('resources', {}))
                journal['state'] = reached
                self._save(journal)
            journal['state'] = 'PROVISIONED_PAUSED'
            self._save(journal)
            if start:
                return self._start_locked()
            return self.status()

    def _require(self, journal, states):
        if journal['state'] not in states:
            raise DeploymentError('Operation is unsafe in state ' + journal['state'])

    def start(self):
        with self.lock():
            return self._start_locked()

    def _start_locked(self):
        journal = self._load()
        if not all(journal['completed'].get(step) for step, _ in STEPS):
            raise DeploymentError('Refusing to start before every readiness step is verified')
        self._require(journal, ('PROVISIONED_PAUSED', 'PAUSED'))
        health = self.provider.health()
        if health.get('ready') is not True:
            journal['health'] = health
            self._save(journal)
            raise DeploymentError('Readiness check failed: ' + _reason(health))
        self.provider.start()
        journal['state'] = 'RUNNING'
        self._save(journal)
        return self.status()

    def pause(self):
        with self.lock():
            journal = self._load()
            self._require(journal, ('RUNNING',))
            self.provider.pause()
            journal['state'] = 'PAUSED'
            self._save(journal)
            return self.status()

    def backup(self, destination):
        with self.lock():
            journal = self._load()
            self._require(journal, ('PROVISIONED_PAUSED', 'PAUSED'))
            result = self.provider.backup(destination)
            if result.get('verified') is not True:
                raise DeploymentError('Backup was not verified; refusing to mark it restorable')
            journal['state'] = 'BACKUP_VERIFIED'
            journal['last_backup'] = result
            self._save(journal)
            return self.status()

    def restore(self, recovery_set):
        with self.lock():
            journal = self._load()
            self._require(journal, ('BACKUP_VERIFIED', 'STOPPED'))
            result = self.provider.restore(recovery_set)
            journal['state'] = 'PROVISIONED_PAUSED'
            journal['restore'] = result
            self._save(journal)
            return self.status()

    def down(self, retain_backup=False):
        with self.lock():
            journal = self._load()
            self._require(journal, ('PROVISIONED_PAUSED', 'PAUSED', 'BACKUP_VERIFIED', 'RUNNING'))
            if not journal.get('last_backup', {}).get('verified') and not retain_backup:
                raise DeploymentError('Refusing to tear down without a verified backup')
            result = self.provider.down(retain_backup)
            journal['state'] = 'DESTROYED'
            journal['teardown'] = result
            self._save(journal)
            return self.status()

    def status(self):
        journal = self._load()
        pending = [step for step, _ in STEPS if not journal['completed'].get(step)]
        document = dict(event=self.event, state=journal['state'], release=journal.get('release'),
                        active_site_generation=journal.get('active_site_generation', 0),
                        steps={step: bool(journal['completed'].get(step)) for step, _ in STEPS},
                        pending=pending, resources=journal.get('resources', {}),
                        last_backup=journal.get('last_backup'),
                        profile_schema=PROFILE_SCHEMA)
        document['summary'] = _summary(document)
        return document


def _reason(result):
    return str(result.get('reason') or result.get('error') or 'unspecified')


def _summary(document):
    if document['state'] in ('PROVISIONED_PAUSED', 'PAUSED', 'BACKUP_VERIFIED'):
        return 'Event is paused and ready'
    if document['state'] == 'RUNNING':
        return 'Event is running'
    if document['state'] in ('STOPPED', 'DESTROYED'):
        return 'Event is stopped'
    return 'Event is not ready; pending: ' + ', '.join(document['pending'])


def _fingerprint(profile):
    import hashlib
    return hashlib.sha256(json.dumps(profile, sort_keys=True, default=str).encode()).hexdigest()


def load_provider(reference):
    if not reference:
        raise DeploymentError('No deployment provider configured; the A03/A04 provider interface is PENDING')
    module_name, _, attribute = reference.partition(':')
    try:
        module = importlib.import_module(module_name)
        factory = getattr(module, attribute or 'provider')
    except (ImportError, AttributeError) as error:
        raise DeploymentError('Cannot load provider: ' + reference) from error
    return factory()


def main():
    parser = argparse.ArgumentParser(prog='python -m ridge.deploy', description=__doc__)
    parser.add_argument('action', choices=('prepare', 'up', 'status', 'start', 'pause',
                                           'backup', 'restore', 'down'))
    parser.add_argument('--event', required=True)
    parser.add_argument('--work', type=Path, default=Path('work'))
    parser.add_argument('--provider', help='dotted package.module:factory (PENDING A04)')
    parser.add_argument('--profile', type=Path)
    parser.add_argument('--release')
    parser.add_argument('--destination', type=Path)
    parser.add_argument('--start', action='store_true')
    parser.add_argument('--retain-backup', action='store_true')
    args = parser.parse_args()
    profile = json.loads(args.profile.read_text(encoding='utf-8')) if args.profile else {}
    provider = None if args.action == 'status' else load_provider(args.provider)
    deployment = Deployment(args.event, args.work, provider)
    if args.action == 'status':
        result = deployment.status()
    elif args.action == 'prepare':
        result = deployment.prepare(args.release, profile)
    elif args.action == 'up':
        result = deployment.up(args.release, profile, args.start)
    elif args.action == 'start':
        result = deployment.start()
    elif args.action == 'pause':
        result = deployment.pause()
    elif args.action == 'backup':
        result = deployment.backup(args.destination)
    elif args.action == 'restore':
        result = deployment.restore(args.destination)
    else:
        result = deployment.down(args.retain_backup)
    print(json.dumps(result, indent=2, default=str))


if __name__ == '__main__':
    main()
