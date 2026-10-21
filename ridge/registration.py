"""Persistent self-service team registration and desktop allocation.

The event has a fixed *capacity* but no fixed participant roster.  This module
is the small, dependency-free state machine shared by the participant landing
page and the host-side provisioning worker:

* a registration reserves one team slot and three GUI desktop slots;
* the reservation is idempotent and serialized with SQLite's write lock;
* credentials are generated once and never rotated by a retry; and
* the participant receives a random retrieval code rather than an enumerable
  team number.

The module deliberately does not start containers or call application APIs.
Those actions belong to the privileged host worker, which consumes
``claim_pending`` records and marks them ready with :meth:`complete`.
Keeping that boundary explicit prevents a public Flask request from gaining
Docker access.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import secrets
import sqlite3
import string
import time
from typing import Any
from contextlib import contextmanager


DEFAULT_MAX_TEAMS = 10
DEFAULT_MEMBERS_PER_TEAM = 5
DEFAULT_DESKTOPS_PER_TEAM = 3
DESKTOP_ROLES = (
    ('forensics-a', 'Desktop 1 — disk and filesystem triage',
     'Start with disk images, recovered files, browser records, and document versions.',
     ('Autopsy', 'Wireshark', 'Cutter', 'Evidence browser', 'Linux evidence tools')),
    ('forensics-b', 'Desktop 2 — timeline and endpoint correlation',
     'Start with endpoint exports, task records, timestamps, and cross-source correlation.',
     ('Autopsy', 'Wireshark', 'Cutter', 'Evidence browser', 'Linux evidence tools')),
    ('analysis', 'Desktop 3 — network, identity, and binary analysis',
     'Start with PCAPs, Wazuh searches, identity records, and harmless training binaries.',
     ('Autopsy', 'Wireshark', 'Cutter', 'Evidence browser', 'Linux evidence tools')),
)


class RegistrationError(ValueError):
    """A participant-facing registration request is invalid or unavailable."""


class RegistrationCapacity(RegistrationError):
    """The configured team or desktop capacity is already reserved."""


@dataclass(frozen=True)
class RegistrationConfig:
    max_teams: int = DEFAULT_MAX_TEAMS
    members_per_team: int = DEFAULT_MEMBERS_PER_TEAM
    desktops_per_team: int = DEFAULT_DESKTOPS_PER_TEAM

    def validate(self) -> None:
        if not 1 <= self.max_teams <= 10:
            raise RegistrationError('max_teams must be between 1 and 10')
        if not 1 <= self.members_per_team <= 10:
            raise RegistrationError('members_per_team must be between 1 and 10')
        if self.desktops_per_team != len(DESKTOP_ROLES):
            raise RegistrationError('desktops_per_team must be exactly 3')


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def _token() -> str:
    return secrets.token_urlsafe(24)


def _password(length: int = 18) -> str:
    alphabet = string.ascii_letters + string.digits + '-_'
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def _team_slug(value: str) -> str:
    value = ' '.join(value.split()).strip()
    if not 2 <= len(value) <= 48:
        raise RegistrationError('team_name must be between 2 and 48 characters')
    allowed = string.ascii_letters + string.digits + ' _-.'
    if any(char not in allowed for char in value):
        raise RegistrationError('team_name contains an unsupported character')
    return value


class RegistrationStore:
    """SQLite-backed allocator safe for concurrent web and host processes."""

    MAX_ATTEMPTS = 4
    LEASE_SECONDS = 300

    def __init__(self, path: str, config: RegistrationConfig | None = None,
                 enrollment_code: str | None = None, read_only: bool = False):
        self.path = str(path)
        self.config = config or RegistrationConfig()
        self.config.validate()
        self.enrollment_hash = _hash(enrollment_code.strip()) if enrollment_code else None
        self.read_only = read_only
        if read_only:
            if not Path(self.path).is_file():
                raise RegistrationError('registration database is unavailable')
        else:
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
            self._initialize()

    @contextmanager
    def _connect(self):
        target = 'file:%s?mode=ro' % Path(self.path).resolve().as_posix() if self.read_only else self.path
        connection = sqlite3.connect(target, timeout=30, isolation_level=None,
                                     uri=self.read_only)
        connection.row_factory = sqlite3.Row
        connection.execute('PRAGMA busy_timeout=30000')
        connection.execute('PRAGMA foreign_keys=ON')
        try:
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connect() as con:
            con.execute('PRAGMA foreign_keys=OFF')
            con.executescript("""
                CREATE TABLE IF NOT EXISTS registration_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                """)
            existing = con.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name='registrations'"
            ).fetchone()
            if existing is not None and 'needs_operator' not in (existing['sql'] or ''):
                # Upgrade the original four-state allocator without losing retrieval
                # tokens, reserved slots, or generated credentials.
                con.executescript("""
                    ALTER TABLE desktop_slots RENAME TO desktop_slots_legacy;
                    ALTER TABLE registrations RENAME TO registrations_legacy;
                """)
            con.executescript(
                """
                CREATE TABLE IF NOT EXISTS registrations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    team_name TEXT NOT NULL UNIQUE,
                    captain_name TEXT NOT NULL,
                    member_count INTEGER NOT NULL,
                    access_hash TEXT NOT NULL UNIQUE,
                    status TEXT NOT NULL CHECK(status IN
                        ('pending','provisioning','ready','needs_operator','cancelled')),
                    slots_json TEXT NOT NULL,
                    credentials_json TEXT NOT NULL,
                    result_json TEXT,
                    error TEXT,
                    attempt_count INTEGER NOT NULL DEFAULT 0,
                    retry_at REAL NOT NULL DEFAULT 0,
                    lease_until REAL NOT NULL DEFAULT 0,
                    worker_token TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS desktop_slots (
                    slot TEXT PRIMARY KEY,
                    role TEXT NOT NULL,
                    registration_id INTEGER REFERENCES registrations(id),
                    status TEXT NOT NULL CHECK(status IN ('available','reserved','running'))
                );
                CREATE INDEX IF NOT EXISTS registrations_status_idx
                    ON registrations(status);
                """)
            legacy = con.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='registrations_legacy'"
            ).fetchone()
            if legacy:
                con.execute('''INSERT INTO registrations(
                    id,team_name,captain_name,member_count,access_hash,status,slots_json,
                    credentials_json,result_json,error,created_at,updated_at)
                    SELECT id,team_name,captain_name,member_count,access_hash,
                      CASE WHEN status='failed' THEN 'cancelled' ELSE status END,
                      slots_json,credentials_json,result_json,error,created_at,updated_at
                    FROM registrations_legacy''')
                con.execute('''INSERT INTO desktop_slots(slot,role,registration_id,status)
                               SELECT slot,role,registration_id,status
                               FROM desktop_slots_legacy''')
                con.executescript('DROP TABLE desktop_slots_legacy; DROP TABLE registrations_legacy;')
                con.execute('''CREATE INDEX IF NOT EXISTS registrations_status_idx
                               ON registrations(status)''')
            self._configure_meta(con)
            self._ensure_slots(con)
            con.execute('PRAGMA foreign_keys=ON')

    def _configure_meta(self, con: sqlite3.Connection) -> None:
        # Production runtimes provide an enrollment code and start closed so
        # an exposed landing page cannot consume event capacity early.  Bare
        # stores remain open for backwards-compatible library/test use.
        default_open = '0' if self.enrollment_hash else '1'
        con.execute("INSERT OR IGNORE INTO registration_meta(key,value) VALUES ('open',?)",
                    (default_open,))
        stored = con.execute(
            "SELECT value FROM registration_meta WHERE key='enrollment_hash'"
        ).fetchone()
        if stored is None and self.enrollment_hash:
            con.execute("INSERT INTO registration_meta(key,value) VALUES ('enrollment_hash',?)",
                        (self.enrollment_hash,))
        elif stored is not None and self.enrollment_hash and not hmac_compare(
                stored['value'], self.enrollment_hash):
            raise RegistrationError('configured enrollment code does not match this event runtime')

    def _ensure_slots(self, con: sqlite3.Connection) -> None:
        expected = self.config.max_teams * self.config.desktops_per_team
        count = int(con.execute('SELECT COUNT(*) FROM desktop_slots').fetchone()[0])
        if count and count != expected:
            raise RegistrationError(
                'registration database was created for %d desktop slots; expected %d; '
                'start a fresh event runtime to change capacity' % (count, expected))
        if count:
            return
        rows = []
        for team_index in range(1, self.config.max_teams + 1):
            for desktop_index, (role, _label, _guidance, _tools) in enumerate(DESKTOP_ROLES, 1):
                slot_number = ((team_index - 1) * self.config.desktops_per_team) + desktop_index
                rows.append(('desktop-slot%02d' % slot_number, role,
                             'available'))
        con.executemany(
            'INSERT INTO desktop_slots(slot, role, status) VALUES (?,?,?)', rows)

    def capacity(self) -> dict[str, int]:
        return {'max_teams': self.config.max_teams,
                'members_per_team': self.config.members_per_team,
                'desktops_per_team': self.config.desktops_per_team,
                'registered': self.count(),
                'available': self.config.max_teams - self.count()}

    def is_open(self) -> bool:
        with self._connect() as con:
            row = con.execute("SELECT value FROM registration_meta WHERE key='open'").fetchone()
            return bool(row and row['value'] == '1')

    def set_open(self, value: bool) -> None:
        if self.read_only:
            raise RegistrationError('registration store is read-only')
        with self._connect() as con:
            con.execute("INSERT INTO registration_meta(key,value) VALUES ('open',?) "
                        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                        ('1' if value else '0',))

    def list(self) -> list[dict[str, Any]]:
        with self._connect() as con:
            return [self._public_row(row, False) for row in con.execute(
                'SELECT * FROM registrations ORDER BY id')]

    def count(self) -> int:
        with self._connect() as con:
            return int(con.execute(
                "SELECT COUNT(*) FROM registrations WHERE status <> 'cancelled'"
            ).fetchone()[0])

    def register(self, team_name: str, captain_name: str, member_count: int | None = None,
                 enrollment_code: str | None = None) -> dict[str, Any]:
        """Reserve a team and return its one-time retrieval code.

        The returned code is intentionally not stored in plaintext.  The
        participant should bookmark the returned URL; the code is the only
        authentication needed to retrieve the team's generated handout.
        """
        team_name = _team_slug(team_name)
        captain_name = _team_slug(captain_name)
        if not self.is_open():
            raise RegistrationError('team registration is currently closed; ask a facilitator')
        with self._connect() as con:
            expected = con.execute(
                "SELECT value FROM registration_meta WHERE key='enrollment_hash'"
            ).fetchone()
        if expected is not None and not hmac_compare(
                expected['value'], _hash((enrollment_code or '').strip())):
            raise RegistrationError('the event enrollment code is invalid')
        member_count = self.config.members_per_team if member_count is None else member_count
        if member_count != self.config.members_per_team:
            raise RegistrationError(
                'member_count must be %d for this event' % self.config.members_per_team)
        access = _token()
        now = _utc()
        credentials = {
            'iris': {'username': 'pending', 'password': _password()},
            'ctfd': {'team': 'pending', 'password': _password(), 'members': []},
            'guacamole': {'username': 'pending', 'password': _password()},
        }
        credentials['ctfd']['members'] = [
            {'username': 'pending-%02d' % index, 'password': _password()}
            for index in range(1, member_count + 1)
        ]
        with self._connect() as con:
            con.execute('BEGIN IMMEDIATE')
            existing = con.execute(
                'SELECT id, status FROM registrations WHERE team_name=?', (team_name,)
            ).fetchone()
            if existing is not None:
                raise RegistrationError('that team name is already registered')
            used = int(con.execute(
                "SELECT COUNT(*) FROM registrations WHERE status <> 'cancelled'"
            ).fetchone()[0])
            if used >= self.config.max_teams:
                raise RegistrationCapacity('all team slots are currently reserved')
            slots = [row['slot'] for row in con.execute(
                "SELECT slot FROM desktop_slots WHERE status='available' ORDER BY slot LIMIT ?",
                (self.config.desktops_per_team,))]
            if len(slots) != self.config.desktops_per_team:
                raise RegistrationCapacity('not enough desktop slots are available')
            con.execute(
                "INSERT INTO registrations(team_name,captain_name,member_count,access_hash,status,"
                "slots_json,credentials_json,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
                (team_name, captain_name, member_count, _hash(access), 'pending',
                 json.dumps(slots), json.dumps(credentials), now, now))
            registration_id = int(con.execute('SELECT last_insert_rowid()').fetchone()[0])
            con.executemany(
                "UPDATE desktop_slots SET registration_id=?, status='reserved' WHERE slot=?",
                [(registration_id, slot) for slot in slots])
        return {'id': registration_id, 'access_code': access, 'status': 'pending',
                'team_name': team_name, 'slots': slots,
                'retrieve_path': '/silent-ridge/registration/' + access}

    def _row_for_access(self, con: sqlite3.Connection, access_code: str) -> sqlite3.Row:
        if not access_code or len(access_code) > 200:
            raise RegistrationError('invalid registration code')
        row = con.execute(
            'SELECT * FROM registrations WHERE access_hash=?', (_hash(access_code),)
        ).fetchone()
        if row is None:
            raise RegistrationError('registration not found')
        return row

    def get(self, access_code: str, include_private: bool = False) -> dict[str, Any]:
        with self._connect() as con:
            row = self._row_for_access(con, access_code)
            return self._public_row(row, include_private)

    def get_by_id(self, registration_id: int, include_private: bool = False) -> dict[str, Any]:
        with self._connect() as con:
            row = con.execute('SELECT * FROM registrations WHERE id=?',
                              (registration_id,)).fetchone()
            if row is None:
                raise RegistrationError('registration not found')
            return self._public_row(row, include_private)

    @staticmethod
    def _public_row(row: sqlite3.Row, include_private: bool) -> dict[str, Any]:
        result = json.loads(row['result_json']) if row['result_json'] else None
        payload = {
            'id': int(row['id']), 'team_name': row['team_name'],
            'captain_name': row['captain_name'], 'member_count': int(row['member_count']),
            'status': row['status'], 'slots': json.loads(row['slots_json']),
            'result': result, 'error': row['error'],
            'attempt_count': int(row['attempt_count']),
            'created_at': row['created_at'], 'updated_at': row['updated_at'],
        }
        if include_private:
            payload['credentials'] = json.loads(row['credentials_json'])
        return payload

    def claim_pending(self) -> dict[str, Any] | None:
        """Lease one due request without allowing a poisoned row to block later teams."""
        with self._connect() as con:
            con.execute('BEGIN IMMEDIATE')
            moment = time.time()
            con.execute("""UPDATE registrations SET status='pending',worker_token=NULL,
                lease_until=0,error=COALESCE(error,'worker lease expired'),updated_at=?
                WHERE status='provisioning' AND lease_until>0 AND lease_until<=?""",
                        (_utc(), moment))
            row = con.execute(
                "SELECT * FROM registrations WHERE status='pending' AND retry_at<=? "
                "ORDER BY retry_at,id LIMIT 1", (moment,)
            ).fetchone()
            if row is None:
                return None
            now = _utc()
            token = _token()
            con.execute("""UPDATE registrations SET status='provisioning',updated_at=?,
                worker_token=?,lease_until=?,attempt_count=attempt_count+1 WHERE id=?""",
                        (now, token, moment + self.LEASE_SECONDS, row['id']))
            return self._private_row(row, status='provisioning', worker_token=token,
                                     attempt_count=int(row['attempt_count']) + 1)

    def activate_credentials(self, registration_id: int) -> dict[str, Any]:
        """Assign stable application usernames to a claimed registration.

        Passwords were generated at reservation time and are preserved.  The
        host worker calls this after claiming the row, so a retry never creates
        a second credential set or changes what the participant saw.
        """
        with self._connect() as con:
            con.execute('BEGIN IMMEDIATE')
            row = con.execute('SELECT * FROM registrations WHERE id=?',
                              (registration_id,)).fetchone()
            if row is None:
                raise RegistrationError('registration not found')
            credentials = json.loads(row['credentials_json'])
            team_id = 'team-%02d' % int(registration_id)
            credentials['iris']['username'] = team_id
            credentials['ctfd']['team'] = team_id
            credentials['ctfd']['members'] = [
                dict(member, username='%s-p%02d' % (team_id, index))
                for index, member in enumerate(credentials['ctfd']['members'], 1)]
            credentials['guacamole']['username'] = team_id
            con.execute('UPDATE registrations SET credentials_json=?,updated_at=? WHERE id=?',
                        (json.dumps(credentials), _utc(), registration_id))
            return credentials

    def complete(self, registration_id: int, result: dict[str, Any],
                 credentials: dict[str, Any] | None = None) -> None:
        """Mark a provisioned registration ready, preserving its credentials."""
        if not isinstance(result, dict) or not result.get('desktop_urls'):
            raise RegistrationError('result.desktop_urls is required')
        with self._connect() as con:
            con.execute('BEGIN IMMEDIATE')
            row = con.execute('SELECT status,slots_json FROM registrations WHERE id=?',
                              (registration_id,)).fetchone()
            if row is None:
                raise RegistrationError('registration not found')
            if row['status'] == 'ready':
                return
            if row['status'] != 'provisioning':
                raise RegistrationError('registration is not being provisioned')
            slots = json.loads(row['slots_json'])
            now = _utc()
            if credentials is None:
                con.execute("UPDATE registrations SET status='ready', result_json=?, updated_at=?, worker_token=NULL,lease_until=0 WHERE id=?",
                            (json.dumps(result), now, registration_id))
            else:
                con.execute("UPDATE registrations SET status='ready', result_json=?, credentials_json=?, "
                            "updated_at=?,worker_token=NULL,lease_until=0 WHERE id=?",
                            (json.dumps(result), json.dumps(credentials), now, registration_id))
            con.executemany("UPDATE desktop_slots SET status='running' WHERE slot=?",
                            [(slot,) for slot in slots])

    def cancel(self, registration_id: int, error: str = 'cancelled by facilitator') -> None:
        with self._connect() as con:
            con.execute('BEGIN IMMEDIATE')
            row = con.execute('SELECT slots_json FROM registrations WHERE id=?',
                              (registration_id,)).fetchone()
            if row is None:
                raise RegistrationError('registration not found')
            slots = json.loads(row['slots_json'])
            con.execute("UPDATE registrations SET status='cancelled',error=?,updated_at=?,worker_token=NULL,lease_until=0 WHERE id=?",
                         (str(error)[:500], _utc(), registration_id))
            con.executemany(
                "UPDATE desktop_slots SET registration_id=NULL,status='available' WHERE slot=?",
                [(slot,) for slot in slots])

    # Backwards-compatible name used by earlier tests/operator scripts.
    fail = cancel

    def requeue(self, registration_id: int, error: str) -> None:
        """Return a transient provisioning failure to the worker queue.

        Reserved slots and generated passwords are preserved, so an IRIS or
        Docker restart does not force a participant to register twice.
        """
        with self._connect() as con:
            con.execute('BEGIN IMMEDIATE')
            row = con.execute('SELECT status,attempt_count FROM registrations WHERE id=?',
                              (registration_id,)).fetchone()
            if row is None:
                raise RegistrationError('registration not found')
            if row['status'] == 'ready':
                return
            attempts = int(row['attempt_count'])
            if attempts >= self.MAX_ATTEMPTS:
                con.execute("""UPDATE registrations SET status='needs_operator',error=?,
                    updated_at=?,worker_token=NULL,lease_until=0 WHERE id=?""",
                            (str(error)[:500], _utc(), registration_id))
            else:
                delay = min(120, 2 ** max(attempts, 1))
                con.execute("""UPDATE registrations SET status='pending',error=?,updated_at=?,
                    retry_at=?,worker_token=NULL,lease_until=0 WHERE id=?""",
                            (str(error)[:500], _utc(), time.time() + delay, registration_id))

    def retry(self, registration_id: int) -> None:
        with self._connect() as con:
            con.execute('BEGIN IMMEDIATE')
            row = con.execute('SELECT status FROM registrations WHERE id=?',
                              (registration_id,)).fetchone()
            if row is None:
                raise RegistrationError('registration not found')
            if row['status'] not in ('needs_operator', 'pending'):
                raise RegistrationError('only a pending or needs-operator registration can be retried')
            con.execute("""UPDATE registrations SET status='pending',error=NULL,retry_at=0,
                lease_until=0,worker_token=NULL,updated_at=? WHERE id=?""",
                        (_utc(), registration_id))

    def rotate_access(self, registration_id: int) -> str:
        access = _token()
        with self._connect() as con:
            if con.execute('UPDATE registrations SET access_hash=?,updated_at=? WHERE id=?',
                           (_hash(access), _utc(), registration_id)).rowcount != 1:
                raise RegistrationError('registration not found')
        return access

    def _private_row(self, row: sqlite3.Row, status: str | None = None,
                     worker_token: str | None = None,
                     attempt_count: int | None = None) -> dict[str, Any]:
        result = {
            'id': int(row['id']), 'team_name': row['team_name'],
            'captain_name': row['captain_name'], 'member_count': int(row['member_count']),
            'status': status or row['status'], 'slots': json.loads(row['slots_json']),
            'credentials': json.loads(row['credentials_json']),
        }
        if worker_token is not None:
            result['worker_token'] = worker_token
        if attempt_count is not None:
            result['attempt_count'] = attempt_count
        return result


def desktop_handout(slots: list[str], public_guacamole_url: str) -> list[dict[str, Any]]:
    """Return the participant-facing tool map for a three-desktop allocation."""
    if len(slots) != len(DESKTOP_ROLES):
        raise RegistrationError('a team must receive exactly three desktop slots')
    return [
        {'slot': slot, 'role': role, 'name': label, 'guidance': guidance,
         'tools': list(tools),
         'connection_name': slot}
        for slot, (role, label, guidance, tools) in zip(slots, DESKTOP_ROLES)
    ]


def hmac_compare(left: str, right: str) -> bool:
    import hmac
    return hmac.compare_digest(str(left), str(right))
