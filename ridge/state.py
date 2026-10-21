"""Durable global progress and serialized ownership, independent of service uptime.

Only trusted application adapters call this module. Never accept a team ID from
participant JSON: derive it from the authenticated IRIS/CTFd application identity.
SQLite is local to the integration host, not an NFS/shared case database.
"""
from __future__ import annotations
import hashlib
import hmac
import json
import re
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol, TypedDict, Any
from ridge.narrative import final_assessment, ticket_delivery
from ridge.schema import migrate, VERSION

FULL_QUESTION_POINTS = 4
ASSISTED_QUESTION_POINTS = 1
WALKTHROUGH_COST_PERCENT = 75


def now():
    return datetime.now(timezone.utc).isoformat()


class Conflict(ValueError):
    pass


# Submission-side relaxations for the answer-format failures observed in the
# 5-team run (issue #195): a version prefix, a bare clock where HH:MM:SS is
# expected, Windows path separators, a full path where a parent directory is
# wanted, and a leading qualifier word in front of the requested phrase.
_ANSWER_QUALIFIERS = frozenset(('explicit', 'separate', 'actual'))
_VERSION_ANSWER = re.compile(r'^(?:[a-z]+-v|v|version[ -]?)(\d+)$')
_ISO_STAMP = re.compile(r'^\d{4}-\d{2}-\d{2}[t ](\d{1,2}):(\d{2})(?::(\d{2}))?(?:z|[+-]\d{2}:?\d{2})?$')
_CLOCK_ONLY = re.compile(r'^(\d{1,2}):(\d{2})(?::(\d{2}))?(?: ?utc)?$')


def normalize_answer(text):
    """Canonical answer form shared by stored digests and submissions: case
    and outer whitespace are ignored (as the question format field promises),
    internal whitespace runs collapse, Windows path separators and trailing
    slashes unify, and any full ISO timestamp or bare HH:MM collapses to the
    canonical HH:MM:SS clock time. Range answers such as 10:30-11:30Z do not
    match the anchored clock patterns and are left intact."""
    form = ' '.join(str(text).split()).casefold().replace('\\', '/')
    while len(form) > 1 and form.endswith('/'):
        form = form[:-1]
    stamp = _ISO_STAMP.fullmatch(form) or _CLOCK_ONLY.fullmatch(form)
    if stamp:
        hour, minute, second = stamp.groups()
        form = '%02d:%s:%s' % (int(hour), minute, second or '00')
    return form


class DeliveryContext(TypedDict):
    iris_id: int | None
    release_files: str


class Sink(Protocol):
    def __call__(self, kind: str, key: str, payload: dict[str, Any], context: DeliveryContext) -> int | str: ...


class State:
    def __init__(self, path, retry_delay=2):
        self.path = Path(path)
        self.retry_delay = retry_delay

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

    def initialize(self, teams, tickets, allow_empty=False):
        if (not allow_empty and not teams) or len({t['id'] for t in teams}) != len(teams):
            raise ValueError('Unique teams required')
        if not tickets or any(not t['questions'] for t in tickets):
            raise ValueError('Each ticket needs questions')
        ids = {t['id'] for t in tickets}
        if len(ids) != len(tickets):
            raise ValueError('Duplicate ticket')
        for t in tickets:
            if not set(t.get('requires', [])) <= ids or t['id'] in t.get('requires', []):
                raise ValueError('Invalid dependencies')
        reachable = set()
        while True:
            expanded = reachable | {t['id'] for t in tickets if set(t.get('requires', [])) <= reachable}
            if expanded == reachable:
                break
            reachable = expanded
        if reachable != ids:
            raise ValueError('Cyclic ticket dependencies')
        self.path.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(self.path)
        try:
            con.executescript('''
            PRAGMA journal_mode=WAL;
            PRAGMA foreign_keys=ON;
            CREATE TABLE IF NOT EXISTS run(id TEXT PRIMARY KEY, mode TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS teams(id TEXT PRIMARY KEY, iris TEXT UNIQUE NOT NULL,
              ctfd INTEGER UNIQUE NOT NULL, name TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS tickets(id TEXT PRIMARY KEY, title TEXT NOT NULL,
              subject TEXT NOT NULL, owner TEXT UNIQUE REFERENCES teams(id),
              status TEXT NOT NULL CHECK(status IN ('locked','available','active','complete')),
              iris_id INTEGER UNIQUE, requires TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS questions(id TEXT PRIMARY KEY, ticket TEXT NOT NULL REFERENCES tickets(id),
              body TEXT NOT NULL, digest TEXT NOT NULL, finding TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS answers(team TEXT NOT NULL REFERENCES teams(id),
              question TEXT NOT NULL REFERENCES questions(id), timestamp TEXT NOT NULL,
              event TEXT UNIQUE NOT NULL, value INTEGER NOT NULL DEFAULT 1,
              PRIMARY KEY(team,question));
            CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY, timestamp TEXT NOT NULL,
              actor TEXT NOT NULL, action TEXT NOT NULL, detail TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS outbox(id TEXT PRIMARY KEY, kind TEXT NOT NULL,
              payload TEXT NOT NULL, done INTEGER NOT NULL DEFAULT 0, attempts INTEGER NOT NULL DEFAULT 0,
              error TEXT, remote TEXT);
            ''')
        finally:
            con.close()
        with self.transaction() as con:
            migrate(con)
            if con.execute('SELECT 1 FROM run').fetchone():
                raise Conflict('Run exists; export before resetting')
            con.execute('INSERT INTO run VALUES (?,?)', (str(uuid.uuid4()), 'paused'))
            for t in teams:
                con.execute('INSERT INTO teams(id,iris,ctfd,name,started_at) VALUES (?,?,?,?,NULL)',
                            (t['id'], str(t['iris']), t['ctfd'], t['name']))
            for t in tickets:
                requires = t.get('requires', [])
                con.execute('INSERT INTO tickets(id,title,subject,owner,status,iris_id,requires) VALUES (?,?,?,?,?,?,?)',
                            (t['id'], t['title'], t['subject'], None, 'locked' if requires else 'available', None, json.dumps(requires)))
                con.execute('UPDATE tickets SET release_files=? WHERE id=?',
                            (json.dumps(t.get('release_files', [])), t['id']))
                for q in t['questions']:
                    if not q['answer'].strip() or not q['finding']['evidence'] or not q['finding']['limitation']:
                        raise ValueError('Answer and traceable finding required')
                    body = {k:v for k,v in q.items() if k not in ('answer', 'finding')}
                    con.execute('INSERT INTO questions VALUES (?,?,?,?,?)',
                                (q['id'], t['id'], json.dumps(body), self.digest(q['answer']), json.dumps(q['finding'])))
                if not requires:
                    self.enqueue(con, 'ticket:'+t['id'], 'ticket', ticket_delivery(t['id'],t['title']))
            con.execute('''INSERT INTO team_tickets(team,ticket,status,generation)
                SELECT teams.id,tickets.id,
                  CASE WHEN tickets.requires='[]' THEN 'available' ELSE 'locked' END,0
                FROM teams CROSS JOIN tickets''')

    def register_team(self, team):
        """Add one dynamically provisioned team to a running event.

        The application IDs are resolved by the registration worker before this
        method is called. Repeating the same message is safe; a reused team ID
        with different application mappings is rejected.
        """
        required = ('id', 'iris', 'ctfd', 'name')
        if not isinstance(team, dict) or any(team.get(key) in (None, '') for key in required):
            raise ValueError('team requires id, iris, ctfd and name')
        with self.transaction() as con:
            self.mutable(con)
            existing = con.execute('SELECT * FROM teams WHERE id=?', (team['id'],)).fetchone()
            if existing is not None:
                if (str(existing['iris']) != str(team['iris'])
                        or int(existing['ctfd']) != int(team['ctfd'])
                        or existing['name'] != team['name']):
                    raise Conflict('team ID is already mapped to different identities')
                return
            for field in ('iris', 'ctfd'):
                if con.execute('SELECT 1 FROM teams WHERE %s=?' % field,
                               (team[field],)).fetchone():
                    raise Conflict('application identity is already mapped to another team')
            started_at = now() if con.execute('SELECT mode FROM run').fetchone()[0] == 'running' else None
            con.execute('INSERT INTO teams(id,iris,ctfd,name,started_at) VALUES (?,?,?,?,?)',
                        (team['id'], str(team['iris']), int(team['ctfd']), team['name'], started_at))
            con.execute('''INSERT INTO team_tickets(team,ticket,status,generation)
                SELECT ?,id,CASE WHEN requires='[]' THEN 'available' ELSE 'locked' END,0
                FROM tickets''', (team['id'],))
            self.record(con, team['id'], 'register_team',
                        {'name': team['name'], 'iris': str(team['iris']), 'ctfd': int(team['ctfd'])})

    @staticmethod
    def digest(answer):
        return hashlib.sha256(normalize_answer(answer).encode()).hexdigest()

    @staticmethod
    def answer_digests(answer):
        """Digests accepted for a submission: the canonical digest plus
        submission-only relaxations for the surface forms reported in issue
        #195 — a version prefix (``v3``/``plan-v3`` for a numeric version), a
        full path where its parent directory is the expected value, and a
        leading qualifier word (``explicit session revocation`` for ``session
        revocation``). The stored expected-answer digest is never relaxed, so
        these forms only widen a submission; ``3`` never becomes correct for a
        question whose answer is ``plan-v3``, and a directory never satisfies
        a full-path question."""
        forms = {normalize_answer(answer)}
        for form in list(forms):
            version = _VERSION_ANSWER.match(form)
            if version:
                forms.add(version.group(1))
            if '/' in form:
                parent = form.rsplit('/', 1)[0]
                if parent:
                    forms.add(parent)
            words = form.split(' ')
            while len(words) > 1 and words[0] in _ANSWER_QUALIFIERS:
                words = words[1:]
                forms.add(' '.join(words))
        return [hashlib.sha256(form.encode()).hexdigest() for form in forms]

    @staticmethod
    def record(con, actor, action, detail):
        con.execute('INSERT INTO audit(timestamp,actor,action,detail) VALUES (?,?,?,?)',
                    (now(), actor, action, json.dumps(detail)))

    @staticmethod
    def enqueue(con, key, kind, payload):
        run = con.execute('SELECT id FROM run').fetchone()[0]
        identifier = run+':'+key
        if con.execute('SELECT 1 FROM outbox WHERE id=?', (identifier,)).fetchone():
            return
        team = payload.get('team')
        previous = con.execute('''SELECT id FROM outbox WHERE ticket=? AND COALESCE(team,'')=?
                                  ORDER BY rowid DESC LIMIT 1''',
                               (payload['ticket'], team or '')).fetchone()
        con.execute('INSERT INTO outbox(id,kind,payload,ticket,created,team) VALUES (?,?,?,?,?,?)',
                    (identifier, kind, json.dumps(payload), payload['ticket'], time.time(), team))
        dependencies = [previous[0]] if previous else []
        con.executemany('INSERT INTO delivery_dependencies VALUES (?,?)',
                        [(identifier, dependency) for dependency in dependencies])

    def _ensure_final_assessment(self, con, team=None, event=None):
        """Publish the canonical ending exactly once after the capstone closes.

        New runs call this from the final T20 answer. Migrations call it again
        to backfill an already-completed live rehearsal; the audit marker and
        deterministic outbox key make both paths idempotent.
        """
        tables={row[0] for row in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        if not {'tickets','questions','answers','teams','audit','outbox'} <= tables:
            return False
        if team is not None and con.execute(
                "SELECT 1 FROM audit WHERE action='final_assessment' AND actor=?", (team,)).fetchone():
            return False
        if team is None:
            last=con.execute('''SELECT a.team,a.event FROM answers a
                JOIN questions q ON q.id=a.question
                WHERE q.ticket='T20' ORDER BY a.timestamp DESC LIMIT 1''').fetchone()
            if last is None:
                return False
            team,event=last['team'],last['event']
        if con.execute("SELECT 1 FROM audit WHERE action='final_assessment' AND actor=?",
                       (team,)).fetchone():
            return False
        totals=con.execute("""SELECT COUNT(*) total,
            SUM(CASE WHEN status='complete' THEN 1 ELSE 0 END) complete
            FROM team_tickets WHERE team=?""", (team,)).fetchone()
        if not totals['total'] or totals['complete'] != totals['total']:
            return False
        if not con.execute("""SELECT 1 FROM team_tickets
            WHERE team=? AND ticket='T20' AND status='complete'""", (team,)).fetchone():
            return False
        if event is None:
            last=con.execute('''SELECT a.team,a.event FROM answers a
                JOIN questions q ON q.id=a.question
                WHERE q.ticket='T20' AND a.team=? ORDER BY a.timestamp DESC LIMIT 1''',
                (team,)).fetchone()
            if last is None:
                return False
            event=last['event']
        teamrow=con.execute('SELECT name FROM teams WHERE id=?',(team,)).fetchone()
        if teamrow is None:
            return False
        assessment=final_assessment()
        payload={'ticket':'T20','text':assessment['announcement'],
                 'status':assessment['status'],'event':event,
                 'team':team,'team_name':teamrow['name']}
        self.enqueue(con,'assessment:final:'+team,'assessment',payload)
        self.record(con,team,'final_assessment',
                    {'text':assessment['announcement'],'event':event,
                     'status':assessment['status']})
        return True

    def migrate(self):
        with self.transaction() as con:
            migrate(con)
            for row in con.execute('SELECT id FROM teams').fetchall():
                self._ensure_final_assessment(con,row['id'])

    @staticmethod
    def mutable(con):
        if con.execute('SELECT export_token FROM control').fetchone()[0]:
            raise Conflict('Export in progress; mutations are frozen')
        row = con.execute('SELECT fenced, site_generation FROM control').fetchone()
        if row['fenced']:
            raise Conflict('This site is fenced (generation %s); it was superseded by an '
                           'activated destination and must not accept writes'
                           % row['site_generation'])

    def site_info(self):
        with self.transaction(write=False) as con:
            row = con.execute('SELECT fenced, site_generation FROM control').fetchone()
            return {'fenced': bool(row['fenced']), 'generation': row['site_generation']}

    def fence(self, actor):
        """Permanently disable writes on this site before a destination activates."""
        with self.transaction() as con:
            if con.execute('SELECT fenced FROM control').fetchone()[0]:
                raise Conflict('Site is already fenced')
            if con.execute('SELECT mode FROM run').fetchone()[0] != 'paused':
                raise Conflict('Pause before fencing')
            if con.execute('SELECT 1 FROM outbox WHERE done=0').fetchone():
                raise Conflict('Drain the outbox before fencing')
            con.execute('UPDATE control SET fenced=1')
            self.record(con, actor, 'fence', {})

    def unfence(self, actor):
        """Rollback aid only: permitted while no destination has activated a newer
        generation. The switch flow records the activation generation in the
        recovery set; unfence beyond that is a deliberate operator action."""
        with self.transaction() as con:
            if not con.execute('SELECT fenced FROM control').fetchone()[0]:
                raise Conflict('Site is not fenced')
            con.execute('UPDATE control SET fenced=0')
            self.record(con, actor, 'unfence', {})

    def activate_generation(self, actor, generation):
        """Destination activation: adopt the next generation; refuses to move
        backwards or to re-activate an already-active generation."""
        with self.transaction() as con:
            row = con.execute('SELECT fenced, site_generation FROM control').fetchone()
            if row['fenced']:
                raise Conflict('A fenced site cannot activate; unfence is an explicit '
                               'operator rollback, never automatic')
            if generation <= row['site_generation']:
                raise Conflict('Activation generation %s must exceed current %s'
                               % (generation, row['site_generation']))
            con.execute('UPDATE control SET site_generation=?', (generation,))
            self.record(con, actor, 'activate_generation', {'generation': generation})

    def provision(self, actor):
        """Explicitly permit initial delivery while participant mutations stay paused."""
        with self.transaction() as con:
            self.mutable(con)
            con.execute('UPDATE control SET provisioned=1')
            self.record(con, actor, 'provision', {})

    @contextmanager
    def export_barrier(self):
        token = str(uuid.uuid4())
        with self.transaction() as con:
            self.mutable(con)
            if con.execute('SELECT mode FROM run').fetchone()[0] != 'paused' or con.execute(
                    'SELECT 1 FROM outbox WHERE done=0').fetchone():
                raise Conflict('Pause and drain before export')
            con.execute('UPDATE control SET export_token=?', (token,))
        try:
            yield token
        finally:
            with self.transaction() as con:
                con.execute('UPDATE control SET export_token=NULL WHERE export_token=?', (token,))

    def verify_export_token(self, token):
        with self.transaction(write=False) as con:
            if con.execute('SELECT export_token FROM control').fetchone()[0] != token:
                raise Conflict('Export barrier was revoked; discard this export')

    def cancel_export(self, actor, token):
        with self.transaction() as con:
            if con.execute('UPDATE control SET export_token=NULL WHERE export_token=?', (token,)).rowcount != 1:
                raise Conflict('Export token does not match')
            self.record(con, actor, 'cancel_export', {'token':token})

    def identity(self, application, external):
        if application not in ('iris', 'ctfd'):
            raise ValueError('Unknown application')
        with self.transaction(write=False) as con:
            row = con.execute(f'SELECT id FROM teams WHERE {application}=?', (external,)).fetchone()
            if row is None:
                raise PermissionError('Identity is not mapped to a team')
            return row[0]

    @staticmethod
    def running(con):
        State.mutable(con)
        if con.execute('SELECT mode FROM run').fetchone()[0] != 'running':
            raise Conflict('Exercise is paused')

    def mode(self, actor, value):
        if value not in ('running', 'paused'):
            raise ValueError('Invalid mode')
        with self.transaction() as con:
            self.mutable(con)
            if value == 'running' and not con.execute('SELECT provisioned FROM control').fetchone()[0]:
                raise Conflict('Provision and validate the deployment before starting')
            if con.execute('SELECT mode FROM run').fetchone()[0] == value:
                return
            stamp = now()
            con.execute('UPDATE run SET mode=?', (value,))
            if value == 'running':
                con.execute('UPDATE teams SET started_at=? WHERE started_at IS NULL', (stamp,))
            con.execute('INSERT INTO audit(timestamp,actor,action,detail) VALUES (?,?,?,?)',
                        (stamp, actor, value, '{}'))

    def announce(self, actor, text):
        if not isinstance(text, str) or not text.strip() or len(text)>4000:
            raise ValueError('Announcement must contain 1–4000 characters')
        with self.transaction() as con:
            self.mutable(con)
            self.record(con, actor, 'announcement', {'text':text})

    def ticket_state(self, ticket, team=None):
        """Read a ticket's id, status, owner, generation and iris_id.

        The supported way to observe the generation that ``claim`` and
        ``release`` require, without reaching into the SQLite schema.
        """
        with self.transaction(write=False) as con:
            if team is None:
                row = con.execute('SELECT id,status,owner,generation,iris_id FROM tickets WHERE id=?',
                                  (ticket,)).fetchone()
            else:
                row = con.execute('''SELECT t.id,tt.status,
                    CASE WHEN tt.status='active' THEN tt.team END owner,
                    tt.generation,t.iris_id FROM team_tickets tt
                    JOIN tickets t ON t.id=tt.ticket WHERE tt.team=? AND tt.ticket=?''',
                                  (team,ticket)).fetchone()
            if row is None:
                raise PermissionError('Unknown ticket')
            return dict(row)

    def claim(self, team, ticket, generation):
        """Claim an available ticket for ``team`` using optimistic concurrency.

        ``generation`` is required and must be the ticket's currently
        observed generation: 0 for a never-claimed ticket, otherwise the
        value from ``ticket_state``. There is deliberately no default —
        the old ``generation=0`` default silently stranded every ticket
        that had ever been claimed, because a successful claim increments
        the stored generation and a re-claim with the stale default always
        failed. A stale (or non-integer) generation raises Conflict;
        re-read the ticket and pass the fresh value.
        """
        with self.transaction() as con:
            self.running(con)
            if not con.execute('SELECT 1 FROM teams WHERE id=?', (team,)).fetchone():
                raise PermissionError('Unknown team')
            active=con.execute("SELECT COUNT(*) FROM team_tickets WHERE team=? AND status='active'",
                               (team,)).fetchone()[0]
            if active >= 3:
                raise Conflict('Your team already has three active work lanes; complete or relinquish one first')
            row = con.execute('''SELECT t.*,tt.status team_status,tt.generation team_generation
                FROM tickets t JOIN team_tickets tt ON tt.ticket=t.id
                WHERE tt.team=? AND t.id=?''', (team,ticket)).fetchone()
            if row is None or row['team_status'] != 'available':
                raise Conflict('Ticket is not available in IRIS')
            if row['iris_id'] is None:
                # Unlocked, but the worker has not finished creating the IRIS
                # task (ticket deliveries set iris_id on completion). This is
                # a transient state; the participant UI hides the claim button
                # until iris_id is set. API callers should retry shortly.
                raise Conflict('Ticket is still being prepared in IRIS; retry shortly')
            if type(generation) is not int or generation != row['team_generation']:
                raise Conflict('Ticket changed: expected generation %s, got %r;'
                               ' re-read the ticket before claiming' % (row['team_generation'], generation))
            con.execute("""UPDATE team_tickets SET status='active',generation=generation+1
                           WHERE team=? AND ticket=?""", (team,ticket))
            self.record(con, team, 'claim', {'ticket':ticket})

    def release(self, team, ticket, generation, recovery_actor=None, reason=None):
        """Relinquish an owned ticket using optimistic concurrency.

        ``generation`` is required and must be the ticket's currently
        observed generation (read it with ``ticket_state``). Releasing
        does not rewind the generation, so the next claim must pass the
        value observed after this call. A stale generation raises
        Conflict rather than silently failing.
        """
        if recovery_actor and not reason:
            raise ValueError('Recovery requires a reason')
        with self.transaction() as con:
            self.mutable(con)
            if not recovery_actor:
                self.running(con)
            if not team:
                raise ValueError('A team is required for per-team ticket recovery')
            row = con.execute('''SELECT tt.*,t.iris_id FROM team_tickets tt
                                 JOIN tickets t ON t.id=tt.ticket
                                 WHERE tt.team=? AND tt.ticket=?''', (team,ticket)).fetchone()
            if row is None or row['status'] != 'active':
                raise PermissionError('Only the owner can relinquish this ticket')
            if type(generation) is not int or generation != row['generation']:
                raise Conflict('Ownership changed: expected generation %s, got %r;'
                               ' re-read the ticket before relinquishing' % (row['generation'], generation))
            con.execute("UPDATE team_tickets SET status='available' WHERE team=? AND ticket=?",
                        (team,ticket))
            self.record(con, recovery_actor or team, 'recover' if recovery_actor else 'release',
                        {'ticket':ticket, 'previous_owner':team, 'reason':reason})

    def questions(self, team, question=None):
        with self.transaction(write=False) as con:
            if not con.execute('SELECT 1 FROM teams WHERE id=?', (team,)).fetchone():
                raise PermissionError('Unknown team')
            rows = con.execute('''SELECT q.*,tt.team owner,tt.status,a.team solver,a.timestamp,
              h.team hint_team FROM questions q JOIN team_tickets tt ON tt.ticket=q.ticket AND tt.team=?
              LEFT JOIN answers a ON a.question=q.id AND a.team=?
              LEFT JOIN hint_usage h ON h.question=q.id AND h.team=?
              WHERE (tt.status='active' OR tt.status='complete') AND (? IS NULL OR q.id=?)''',
              (team,team,team,question,question)).fetchall()
            if question and not rows:
                raise PermissionError('Question is not available')
            result=[]
            for row in rows:
                body=json.loads(row['body'])
                hints=list(body.get('hints') or [])
                unlocked=row['hint_team'] is not None
                body['hints']=hints if unlocked else hints[:-1]
                result.append(dict(body, ticket=row['ticket'], solved_by=row['solver'],
                    answered_at=row['timestamp'], answerable=row['status']=='active' and row['solver'] is None,
                    finding=json.loads(row['finding']) if row['solver'] else None,
                    hint_unlocked=unlocked, paid_hint_available=bool(hints) and not unlocked,
                    full_points=FULL_QUESTION_POINTS,
                    available_points=ASSISTED_QUESTION_POINTS if unlocked else FULL_QUESTION_POINTS,
                    walkthrough_cost_percent=WALKTHROUGH_COST_PERCENT))
            return result

    def unlock_hint(self, team, question):
        """Unlock the explicit walkthrough and durably apply its 75% cost."""
        with self.transaction() as con:
            self.running(con)
            row=con.execute('''SELECT q.body,tt.team owner,tt.status,a.question solved
                FROM questions q JOIN team_tickets tt ON tt.ticket=q.ticket AND tt.team=?
                LEFT JOIN answers a ON a.question=q.id AND a.team=? WHERE q.id=?''',
                (team,team,question)).fetchone()
            if row is None or row['owner'] != team or row['status'] != 'active' or row['solved']:
                raise PermissionError('Claim the corresponding unsolved IRIS ticket first')
            if not (json.loads(row['body']).get('hints') or []):
                raise Conflict('This question has no explicit walkthrough')
            stamp=now()
            inserted=con.execute('''INSERT OR IGNORE INTO hint_usage(team,question,unlocked_at)
                                    VALUES (?,?,?)''', (team,question,stamp)).rowcount
            if inserted:
                self.record(con,team,'unlock_hint',{'question':question,
                    'cost_percent':WALKTHROUGH_COST_PERCENT,
                    'available_points':ASSISTED_QUESTION_POINTS})
            return {'unlocked':True,'cost_percent':WALKTHROUGH_COST_PERCENT,
                    'available_points':ASSISTED_QUESTION_POINTS}

    def answer(self, team, question, answer):
        if not isinstance(answer, str) or len(answer) > 1024:
            raise ValueError('Answer must be at most 1024 characters')
        with self.transaction() as con:
            self.running(con)
            row = con.execute('''SELECT q.*,tt.team owner,tt.status FROM questions q
                JOIN team_tickets tt ON q.ticket=tt.ticket AND tt.team=? WHERE q.id=?''',
                (team,question)).fetchone()
            # Ownership is checked before the correctness oracle, even on duplicate submissions.
            if row is None or row['owner'] != team or row['status'] != 'active':
                raise PermissionError('Claim the corresponding IRIS ticket first')
            if con.execute('SELECT 1 FROM answers WHERE team=? AND question=?',
                           (team,question)).fetchone():
                raise Conflict('Question already answered; points are preserved')
            if not any(hmac.compare_digest(candidate, row['digest'])
                       for candidate in self.answer_digests(answer)):
                return {'correct':False}
            assisted=con.execute('SELECT 1 FROM hint_usage WHERE team=? AND question=?',
                                 (team,question)).fetchone() is not None
            value=ASSISTED_QUESTION_POINTS if assisted else FULL_QUESTION_POINTS
            stamp = now()
            event = str(uuid.uuid4())
            con.execute('INSERT INTO answers(team,question,timestamp,event,value) VALUES (?,?,?,?,?)',
                        (team,question,stamp,event,value))
            teamrow = con.execute('SELECT * FROM teams WHERE id=?', (team,)).fetchone()
            finding = dict(json.loads(row['finding']), question=question, team=team,
                           team_name=teamrow['name'], timestamp=stamp, event=event, ticket=row['ticket'])
            self.enqueue(con, 'point:'+team+':'+question, 'point',
                         dict(finding, ctfd_team=teamrow['ctfd'], value=value))
            self.enqueue(con, 'finding:'+team+':'+question, 'finding', finding)
            self.record(con, team, 'answer', {'question':question, 'event':event,
                        'ticket':row['ticket'], 'value':value, 'assisted':assisted})
            remaining = con.execute('''SELECT COUNT(*) FROM questions q
                LEFT JOIN answers a ON q.id=a.question AND a.team=?
                WHERE q.ticket=? AND a.question IS NULL''', (team,row['ticket'])).fetchone()[0]
            if not remaining:
                con.execute("""UPDATE team_tickets SET status='complete'
                               WHERE team=? AND ticket=?""", (team,row['ticket']))
                self.record(con, team, 'close', {'ticket':row['ticket'], 'event':event})
                completed = {r[0] for r in con.execute(
                    "SELECT ticket FROM team_tickets WHERE team=? AND status='complete'", (team,))}
                for lead in con.execute('''SELECT t.* FROM tickets t JOIN team_tickets tt
                    ON tt.ticket=t.id WHERE tt.team=? AND tt.status='locked' ''', (team,)).fetchall():
                    if set(json.loads(lead['requires'])) <= completed:
                        con.execute("""UPDATE team_tickets SET status='available'
                                       WHERE team=? AND ticket=?""", (team,lead['id']))
                        self.enqueue(con, 'ticket:'+lead['id'], 'ticket', ticket_delivery(lead['id'],lead['title']))
                assessment_published=self._ensure_final_assessment(con,team,event)
            else:
                assessment_published=False
            return {'correct':True, 'event':event, 'closed':not remaining,
                    'synchronization':'pending', 'value':value, 'assisted':assisted,
                    'assessment_published':assessment_published}

    def snapshot(self, team=None):
        with self.transaction(write=False) as con:
            stamp=now();total=0;anchor=None
            if team is not None:
                ticket_counts=con.execute("""SELECT COUNT(*) total,
                    SUM(CASE WHEN status='complete' THEN 1 ELSE 0 END) complete
                    FROM team_tickets WHERE team=?""", (team,)).fetchone()
            else:
                ticket_counts=con.execute("""SELECT COUNT(*) total,
                    SUM(CASE WHEN complete_count=team_count THEN 1 ELSE 0 END) complete
                    FROM (SELECT ticket,COUNT(*) team_count,
                      SUM(CASE WHEN status='complete' THEN 1 ELSE 0 END) complete_count
                      FROM team_tickets GROUP BY ticket)""").fetchone()
            activity_complete=bool(ticket_counts['total'] and
                                   ticket_counts['complete']==ticket_counts['total'])
            final_row=con.execute("""SELECT timestamp FROM audit
                WHERE action='final_assessment' AND (? IS NULL OR actor=?)
                ORDER BY id LIMIT 1""", (team,team)).fetchone()
            # The activity clock is a participant pacing measure. Once the
            # capstone publishes, freeze it at that durable event even if the
            # facilitator leaves the exercise in running mode for review.
            cutoff=final_row['timestamp'] if activity_complete and final_row else stamp
            cutoff_time=datetime.fromisoformat(cutoff)
            team_started=None
            if team is not None:
                row=con.execute('SELECT started_at FROM teams WHERE id=?',(team,)).fetchone()
                if row is None:
                    raise PermissionError('Unknown team')
                team_started=datetime.fromisoformat(row['started_at']) if row['started_at'] else None
            for event in con.execute("SELECT timestamp,action FROM audit WHERE action IN ('running','paused') ORDER BY id"):
                at=datetime.fromisoformat(event['timestamp'])
                if at>cutoff_time:
                    break
                if event['action']=='running':
                    anchor=at
                elif anchor is not None:
                    start=max(anchor,team_started) if team_started else anchor
                    total+=max((at-start).total_seconds(),0);anchor=None
            if anchor is not None:
                start=max(anchor,team_started) if team_started else anchor
                total+=max((cutoff_time-start).total_seconds(),0)
            if team is not None and team_started is None:
                total=0
            if team is not None:
                ticket_rows=con.execute('''SELECT t.id,t.title,t.subject,
                    CASE WHEN tt.status='active' THEN tt.team END owner,
                    tt.status,t.iris_id,tt.generation FROM team_tickets tt
                    JOIN tickets t ON t.id=tt.ticket WHERE tt.team=? AND tt.status!='locked'
                    ORDER BY t.id''', (team,)).fetchall()
            else:
                ticket_rows=con.execute('''SELECT * FROM (SELECT t.id,t.title,t.subject,
                    CASE WHEN SUM(CASE WHEN tt.status='active' THEN 1 ELSE 0 END)=1
                      THEN MAX(CASE WHEN tt.status='active' THEN tt.team END) END owner,
                    CASE WHEN MIN(tt.status='complete')=1 THEN 'complete'
                         WHEN MAX(tt.status='active')=1 THEN 'active'
                         WHEN MAX(tt.status='available')=1 THEN 'available' ELSE 'locked' END status,
                    t.iris_id,MAX(tt.generation) generation
                    FROM tickets t JOIN team_tickets tt ON tt.ticket=t.id
                    GROUP BY t.id) WHERE status!='locked' ORDER BY id''').fetchall()
            return {'mode':con.execute('SELECT mode FROM run').fetchone()[0],
                    'elapsed_seconds':max(total,0),'server_time':stamp,
                    'activity_complete':activity_complete,
                    'announcements':[dict(id=r['id'],timestamp=r['timestamp'],kind=r['action'],
                                          text=json.loads(r['detail'])['text'])
                                     for r in con.execute("""SELECT * FROM audit
                                       WHERE action='announcement' OR
                                         (action='final_assessment' AND (? IS NULL OR actor=?))
                                       ORDER BY id""", (team,team))],
                    'tickets':[dict(r) for r in ticket_rows],
                    'scores':[dict(r) for r in con.execute('''SELECT t.id,t.name,COALESCE(SUM(a.value),0) points FROM teams t
                                  LEFT JOIN answers a ON a.team=t.id GROUP BY t.id ORDER BY points DESC,t.id''')],
                    'pending':con.execute('SELECT COUNT(*) FROM outbox WHERE done=0').fetchone()[0]}

    def sync_once(self, sink: Sink) -> bool:
        """Lease one eligible delivery; no database lock spans network or filesystem I/O.

        Leases recover after worker death. Application receipts make late/retried
        deliveries safe. Ticket chains and prerequisite closures preserve causality.
        """
        token = str(uuid.uuid4())
        with self.transaction() as con:
            control = con.execute('SELECT * FROM control').fetchone()
            if not control['provisioned'] or control['export_token']:
                return False
            row = con.execute('''SELECT o.* FROM outbox o WHERE o.done=0 AND o.retry_at<=?
                AND o.lease_until<=? AND NOT EXISTS (
                  SELECT 1 FROM delivery_dependencies d JOIN outbox p ON p.id=d.prerequisite
                  WHERE d.event=o.id AND p.done=0) ORDER BY o.rowid LIMIT 1''',
                (time.time(), time.time())).fetchone()
            if not row:
                return False
            con.execute('UPDATE outbox SET lease=?,lease_until=?,attempts=attempts+1 WHERE id=?',
                        (token, time.time()+30, row['id']))
            context = dict(con.execute('SELECT iris_id,release_files FROM tickets WHERE id=?',
                                       (row['ticket'],)).fetchone())
        stopped = threading.Event()
        def renew():
            while not stopped.wait(5):
                try:
                    with self.transaction() as con:
                        con.execute('UPDATE outbox SET lease_until=? WHERE id=? AND lease=?',
                                    (time.time()+30, row['id'], token))
                except sqlite3.Error:
                    # Lost leases cannot acknowledge. The next worker retries the same key.
                    return
        heartbeat = threading.Thread(target=renew, daemon=True)
        heartbeat.start()
        try:
            result = sink(row['kind'], row['id'], json.loads(row['payload']), context)
            if row['kind'] == 'ticket':
                result = int(result)
            with self.transaction() as con:
                if not con.execute('SELECT 1 FROM outbox WHERE id=? AND lease=?',
                                   (row['id'], token)).fetchone():
                    return False
                if row['kind'] == 'ticket':
                    con.execute('UPDATE tickets SET iris_id=? WHERE id=?',
                                (result, row['ticket']))
                con.execute('UPDATE outbox SET done=1,error=NULL,remote=?,lease=NULL,lease_until=0 WHERE id=?',
                            (str(result), row['id']))
            return True
        except Exception as exc:
            with self.transaction() as con:
                con.execute('''UPDATE outbox SET error=?,lease=NULL,lease_until=0,retry_at=?
                               WHERE id=? AND lease=?''',
                            (type(exc).__name__, time.time()+min(30, self.retry_delay*2**min(row['attempts'], 4)), row['id'], token))
            return False
        finally:
            stopped.set()
            heartbeat.join()

    def diagnostics(self):
        with self.transaction(write=False) as con:
            if con.execute('PRAGMA user_version').fetchone()[0] != VERSION:
                raise ValueError('Stop old workers and run ridge.cli migrate')
            control = dict(con.execute('SELECT * FROM control').fetchone())
            row = con.execute('SELECT COUNT(*) pending,MIN(created) oldest FROM outbox WHERE done=0').fetchone()
            return dict(control, pending=row['pending'], oldest_pending_seconds=max(0, time.time()-(row['oldest'] or time.time())),
                        active_leases=con.execute('SELECT COUNT(*) FROM outbox WHERE done=0 AND lease_until>?',(time.time(),)).fetchone()[0],
                        failures=[dict(r) for r in con.execute('SELECT id,kind,attempts,error FROM outbox WHERE done=0 AND error IS NOT NULL')])

    def export(self, destination):
        """A complete, coherent private integration snapshot; no stored submitted flags."""
        destination = Path(destination)
        if destination.exists():
            raise ValueError('Export destination already exists')
        with self.transaction(write=False) as con:
            with destination.open('x', encoding='utf-8') as f:
                f.write('{')
                for number,name in enumerate(('run','teams','tickets','team_tickets','questions','answers','hint_usage',
                                               'audit','outbox','delivery_dependencies')):
                    if number:
                        f.write(',')
                    f.write(json.dumps(name)+':[')
                    for row_number,row in enumerate(con.execute('SELECT * FROM '+name)):
                        if row_number:
                            f.write(',')
                        json.dump(dict(row),f)
                    f.write(']')
                f.write('}\n')
        return destination
