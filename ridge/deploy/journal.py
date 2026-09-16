"""Private deployment journal, event-scoped lock and step verification.

The journal is a SQLite file kept separate from the event scoring database
(``ridge.state``). It stores the deployment identity, release/configuration
fingerprints, provider resource IDs, per-step attempts and *verified* completion.

A returned handle or "receipt" is never acceptance: a step is marked ``verified``
only after the provider's ``probe`` confirms the resource exists. A crash between
``create`` and the journal write leaves the step ``started``; the next attempt probes
first, so a lost acknowledgment reconciles to one resource instead of two.

Failure boundaries and cleanup:

- Each step is one atomic transaction; a failed step is left ``failed`` for retry.
- :meth:`Deployment.up` holds the event lock for the whole run; concurrent attempts
  serialize instead of interleaving.
- :meth:`Deployment.stop` stops every recorded resource and marks the run ``STOPPED``,
  which is the partial-run cleanup contract.
"""
import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from ridge.deploy.config import fingerprint as profile_fingerprint

JOURNAL_SCHEMA = 1
LOCK_STALE_SECONDS = 120
STAGES = ('ARTIFACTS_VERIFIED', 'INFRASTRUCTURE_READY', 'APPLICATIONS_READY',
          'IDENTITIES_READY', 'DESKTOPS_READY', 'EVIDENCE_READY', 'PROVISIONED_PAUSED')
TERMINAL_STATES = ('STOPPED', 'DESTROYED')

_SCHEMA = '''
CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE steps(name TEXT PRIMARY KEY, state TEXT NOT NULL DEFAULT 'pending',
  attempt INTEGER NOT NULL DEFAULT 0, resource_id TEXT, detail TEXT, updated_at TEXT NOT NULL);
CREATE TABLE resources(kind TEXT NOT NULL, name TEXT NOT NULL, provider_id TEXT NOT NULL,
  detail TEXT, created_at TEXT NOT NULL, PRIMARY KEY(kind, name));
CREATE TABLE lock(id INTEGER PRIMARY KEY CHECK(id=1), holder TEXT,
  acquired_at REAL NOT NULL DEFAULT 0, heartbeat REAL NOT NULL DEFAULT 0);
CREATE TABLE events(id INTEGER PRIMARY KEY, timestamp TEXT NOT NULL, actor TEXT,
  action TEXT NOT NULL, detail TEXT);
'''


class JournalError(RuntimeError):
    pass


class LockError(JournalError):
    pass


class FingerprintError(JournalError):
    pass


def _now():
    return datetime.now(timezone.utc).isoformat()


class Journal:
    def __init__(self, path):
        self.path = Path(path)

    @classmethod
    def create(cls, path, profile, release_id, release_fingerprint):
        path = Path(path)
        if path.exists() and path.stat().st_size:
            raise JournalError('journal already exists: ' + str(path))
        path.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(path, timeout=30, isolation_level=None)
        try:
            con.execute('PRAGMA journal_mode=WAL')
            con.executescript(_SCHEMA)
            con.execute('BEGIN IMMEDIATE')
            deployment_id = str(uuid.uuid4())
            meta = {
                'schema': str(JOURNAL_SCHEMA),
                'event_id': profile['event']['id'],
                'release_id': release_id,
                'release_fingerprint': release_fingerprint,
                'config_fingerprint': profile_fingerprint(profile),
                'deployment_id': deployment_id,
                'state': 'NEW',
                'active_site_generation': '0',
                'created_at': _now(),
            }
            con.executemany('INSERT INTO meta(key,value) VALUES (?,?)', meta.items())
            for stage in STAGES:
                con.execute('INSERT INTO steps(name,state,attempt,updated_at) VALUES (?,?,?,?)',
                            (stage, 'pending', 0, _now()))
            con.execute('INSERT INTO lock(id,holder,acquired_at,heartbeat) VALUES (1,NULL,0,0)')
            cls._event(con, 'system', 'create', {'deployment_id': deployment_id})
            con.commit()
        except BaseException:
            con.rollback()
            con.close()
            path.unlink(missing_ok=True)
            raise
        con.close()
        return cls(path)

    @classmethod
    def open(cls, path):
        path = Path(path)
        if not path.is_file() or not path.stat().st_size:
            raise JournalError('journal is missing or empty: ' + str(path))
        con = sqlite3.connect(path, timeout=30)
        try:
            try:
                integrity = con.execute('PRAGMA integrity_check').fetchone()[0]
            except sqlite3.DatabaseError as exc:
                raise JournalError('corrupt journal: ' + str(exc))
            if integrity != 'ok':
                raise JournalError('journal failed integrity check: ' + str(integrity))
            try:
                row = con.execute("SELECT value FROM meta WHERE key='schema'").fetchone()
            except sqlite3.DatabaseError as exc:
                raise JournalError('not a deployment journal: ' + str(exc))
            if row is None or row[0] != str(JOURNAL_SCHEMA):
                raise JournalError('unsupported or missing journal schema')
        finally:
            con.close()
        return cls(path)

    @contextmanager
    def transaction(self, write=True):
        con = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        con.row_factory = sqlite3.Row
        con.execute('PRAGMA foreign_keys=ON')
        try:
            con.execute('BEGIN IMMEDIATE' if write else 'BEGIN')
            yield con
            con.commit()
        except BaseException:
            con.rollback()
            raise
        finally:
            con.close()

    @staticmethod
    def _event(con, actor, action, detail):
        con.execute('INSERT INTO events(timestamp,actor,action,detail) VALUES (?,?,?,?)',
                    (_now(), actor, action, json.dumps(detail)))

    def meta(self):
        with self.transaction(write=False) as con:
            return {row['key']: row['value'] for row in con.execute('SELECT key,value FROM meta')}

    @property
    def state(self):
        return self.meta()['state']

    @contextmanager
    def lock(self, holder, timeout=30, poll=0.05, stale=LOCK_STALE_SECONDS):
        """Event-scoped lock. Concurrent holders serialize or time out."""
        deadline = time.monotonic() + timeout
        while True:
            acquired = False
            with self.transaction() as con:
                now = time.time()
                acquired = con.execute(
                    'UPDATE lock SET holder=?, acquired_at=?, heartbeat=? '
                    'WHERE id=1 AND (holder IS NULL OR heartbeat<?)',
                    (holder, now, now, now - stale)).rowcount == 1
                if acquired:
                    self._event(con, holder, 'lock', {})
            if acquired:
                break
            if time.monotonic() >= deadline:
                raise LockError('another deployment is running for this event')
            time.sleep(poll)
        try:
            yield
        finally:
            with self.transaction() as con:
                con.execute('UPDATE lock SET holder=NULL,acquired_at=0,heartbeat=0 WHERE holder=?', (holder,))

    def steps(self):
        with self.transaction(write=False) as con:
            return [dict(row) for row in con.execute('SELECT * FROM steps ORDER BY rowid')]

    def step(self, name):
        with self.transaction(write=False) as con:
            row = con.execute('SELECT * FROM steps WHERE name=?', (name,)).fetchone()
            return dict(row) if row else None

    def begin_step(self, name):
        with self.transaction() as con:
            row = con.execute('SELECT state FROM steps WHERE name=?', (name,)).fetchone()
            if row is None:
                raise JournalError('unknown step: ' + name)
            if row['state'] == 'verified':
                return
            con.execute("UPDATE steps SET state='started', attempt=attempt+1, updated_at=? WHERE name=?",
                        (_now(), name))
            self._event(con, 'system', 'begin_step', {'step': name})

    def complete_step(self, name, provider_id):
        with self.transaction() as con:
            row = con.execute('SELECT state FROM steps WHERE name=?', (name,)).fetchone()
            if row is None or row['state'] != 'started':
                raise JournalError('step is not started: ' + name)
            con.execute("UPDATE steps SET state='verified', resource_id=?, updated_at=? WHERE name=?",
                        (provider_id, _now(), name))
            self._event(con, 'system', 'complete_step', {'step': name, 'resource_id': provider_id})

    def fail_step(self, name, error):
        with self.transaction() as con:
            con.execute("UPDATE steps SET state='failed', detail=?, updated_at=? WHERE name=?",
                        (str(error)[:500], _now(), name))

    def record_resource(self, kind, name, provider_id, detail=None):
        with self.transaction() as con:
            con.execute('INSERT INTO resources(kind,name,provider_id,detail,created_at) '
                        'VALUES (?,?,?,?,?) ON CONFLICT(kind,name) DO UPDATE SET '
                        'provider_id=excluded.provider_id, detail=excluded.detail',
                        (kind, name, provider_id, json.dumps(detail or {}), _now()))

    def resource(self, kind, name):
        with self.transaction(write=False) as con:
            row = con.execute('SELECT * FROM resources WHERE kind=? AND name=?', (kind, name)).fetchone()
            return dict(row) if row else None

    def resources(self):
        with self.transaction(write=False) as con:
            return [dict(row) for row in con.execute('SELECT * FROM resources ORDER BY kind,name')]

    def set_state(self, state):
        with self.transaction() as con:
            con.execute("UPDATE meta SET value=? WHERE key='state'", (state,))
            self._event(con, 'system', 'state', {'state': state})

    def check_fingerprints(self, profile, release_id, release_fingerprint, migrate=False):
        """Reject a changed release/profile unless the caller explicitly migrates."""
        with self.transaction() as con:
            meta = {row['key']: row['value'] for row in con.execute('SELECT key,value FROM meta')}
            current = profile_fingerprint(profile)
            changed = []
            if meta['release_id'] != release_id or meta['release_fingerprint'] != release_fingerprint:
                changed.append('release')
            if meta['config_fingerprint'] != current:
                changed.append('profile')
            if changed and not migrate:
                raise FingerprintError('changed ' + '/'.join(changed) +
                                       ' requires an explicit new run or migration')
            if changed:
                generation = int(meta['active_site_generation']) + 1
                updates = {'deployment_id': str(uuid.uuid4()), 'release_id': release_id,
                           'release_fingerprint': release_fingerprint,
                           'config_fingerprint': current, 'active_site_generation': str(generation)}
                con.executemany('UPDATE meta SET value=? WHERE key=?', [(value, key) for key, value in updates.items()])
                con.execute("UPDATE steps SET state='pending', resource_id=NULL, detail=NULL")
                self._event(con, 'system', 'migrate', {'changed': changed, 'generation': generation})
            return changed


class DeploymentError(RuntimeError):
    pass


def ensure_resource(journal, provider, kind, name, spec=None):
    """Probe before create so a lost acknowledgment reconciles to one resource."""
    existing = provider.probe(kind, name)
    if existing is not None:
        journal.record_resource(kind, name, existing)
        return existing
    provider_id = provider.create(kind, name, spec or {})
    if not provider_id:
        raise DeploymentError('provider returned no handle for ' + name)
    journal.record_resource(kind, name, provider_id)
    return provider_id


def verify_resource(provider, kind, name, provider_id):
    """A resource is verified only when probe independently confirms it."""
    return provider.probe(kind, name) == provider_id


class Deployment:
    """Minimal orchestration over the journal and a provider.

    Does not implement any cloud or hypervisor; it defines the contract the Wave 1+
    providers must honor.
    """

    def __init__(self, journal, provider, actor='up'):
        self.journal = journal
        self.provider = provider
        self.actor = actor

    def up(self, plan, timeout=30):
        with self.journal.lock(self.actor, timeout=timeout):
            for step in plan:
                current = self.journal.step(step['name'])
                if current and current['state'] == 'verified':
                    continue
                self.journal.begin_step(step['name'])
                try:
                    provider_id = ensure_resource(self.journal, self.provider, step['kind'],
                                                  step['name'], step.get('spec'))
                    if not verify_resource(self.provider, step['kind'], step['name'], provider_id):
                        raise DeploymentError('unverified resource: ' + step['name'])
                    self.journal.complete_step(step['name'], provider_id)
                except Exception as exc:
                    self.journal.fail_step(step['name'], exc)
                    raise
            self.journal.set_state('PROVISIONED_PAUSED')
            return self.journal.state

    def stop(self, timeout=30):
        with self.journal.lock(self.actor, timeout=timeout):
            for resource in self.journal.resources():
                self.provider.stop(resource['kind'], resource['name'], resource['provider_id'])
            self.journal.set_state('STOPPED')
            return self.journal.state
