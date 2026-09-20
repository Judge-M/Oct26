"""Durable global progress and serialized ownership, independent of service uptime.

Only trusted application adapters call this module. Never accept a team ID from
participant JSON: derive it from the authenticated IRIS/CTFd application identity.
SQLite is local to the integration host, not an NFS/shared case database.
"""
from __future__ import annotations
import hashlib
import hmac
import json
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol, TypedDict, Any
from ridge.schema import migrate, VERSION


def now():
    return datetime.now(timezone.utc).isoformat()


class Conflict(ValueError):
    pass


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

    def initialize(self, teams, tickets):
        if not teams or len({t['id'] for t in teams}) != len(teams):
            raise ValueError('Nonempty unique teams required')
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
            CREATE TABLE IF NOT EXISTS answers(question TEXT PRIMARY KEY REFERENCES questions(id),
              team TEXT NOT NULL REFERENCES teams(id), timestamp TEXT NOT NULL, event TEXT UNIQUE NOT NULL);
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
                con.execute('INSERT INTO teams VALUES (?,?,?,?)', (t['id'], str(t['iris']), t['ctfd'], t['name']))
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
                    self.enqueue(con, 'ticket:'+t['id'], 'ticket', {'ticket':t['id'], 'title':t['title']})

    @staticmethod
    def digest(answer):
        return hashlib.sha256(answer.strip().casefold().encode()).hexdigest()

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
        previous = con.execute('SELECT id FROM outbox WHERE ticket=? ORDER BY rowid DESC LIMIT 1',
                               (payload['ticket'],)).fetchone()
        con.execute('INSERT INTO outbox(id,kind,payload,ticket,created) VALUES (?,?,?,?,?)',
                    (identifier, kind, json.dumps(payload), payload['ticket'], time.time()))
        dependencies = [previous[0]] if previous else []
        if kind == 'ticket':
            requires = json.loads(con.execute('SELECT requires FROM tickets WHERE id=?',
                                               (payload['ticket'],)).fetchone()[0])
            dependencies.extend(run+':close:'+ticket for ticket in requires)
        con.executemany('INSERT INTO delivery_dependencies VALUES (?,?)',
                        [(identifier, dependency) for dependency in dependencies])

    def migrate(self):
        with self.transaction() as con:
            migrate(con)

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
            con.execute('UPDATE run SET mode=?', (value,))
            self.record(con, actor, value, {})

    def announce(self, actor, text):
        if not isinstance(text, str) or not text.strip() or len(text)>4000:
            raise ValueError('Announcement must contain 1–4000 characters')
        with self.transaction() as con:
            self.mutable(con)
            self.record(con, actor, 'announcement', {'text':text})

    def claim(self, team, ticket, generation=0):
        with self.transaction() as con:
            self.running(con)
            if not con.execute('SELECT 1 FROM teams WHERE id=?', (team,)).fetchone():
                raise PermissionError('Unknown team')
            if con.execute('SELECT 1 FROM tickets WHERE owner=?', (team,)).fetchone():
                raise Conflict('Relinquish your current ticket first')
            row = con.execute('SELECT * FROM tickets WHERE id=?', (ticket,)).fetchone()
            if row is None or row['status'] != 'available' or row['iris_id'] is None:
                raise Conflict('Ticket is not available in IRIS')
            if type(generation) is not int or generation != row['generation']:
                raise Conflict('Ticket changed; reload before claiming')
            con.execute("UPDATE tickets SET owner=?,status='active',generation=generation+1 WHERE id=?", (team, ticket))
            self.record(con, team, 'claim', {'ticket':ticket})
            self.enqueue(con, 'ownership:'+str(uuid.uuid4()), 'ownership', {'ticket':ticket, 'team':team})

    def release(self, team, ticket, generation, recovery_actor=None, reason=None):
        if recovery_actor and not reason:
            raise ValueError('Recovery requires a reason')
        with self.transaction() as con:
            self.mutable(con)
            if not recovery_actor:
                self.running(con)
            row = con.execute('SELECT * FROM tickets WHERE id=?', (ticket,)).fetchone()
            if row is None or row['status'] != 'active' or (not recovery_actor and row['owner'] != team):
                raise PermissionError('Only the owner can relinquish this ticket')
            if type(generation) is not int or generation != row['generation']:
                raise Conflict('Ownership changed; reload before relinquishing')
            con.execute("UPDATE tickets SET owner=NULL,status='available' WHERE id=?", (ticket,))
            self.record(con, recovery_actor or team, 'recover' if recovery_actor else 'release',
                        {'ticket':ticket, 'previous_owner':row['owner'], 'reason':reason})
            self.enqueue(con, 'ownership:'+str(uuid.uuid4()), 'ownership', {'ticket':ticket, 'team':None})

    def questions(self, team, question=None):
        with self.transaction(write=False) as con:
            if not con.execute('SELECT 1 FROM teams WHERE id=?', (team,)).fetchone():
                raise PermissionError('Unknown team')
            rows = con.execute('''SELECT q.*,t.owner,t.status,a.team solver,a.timestamp FROM questions q
              JOIN tickets t ON t.id=q.ticket LEFT JOIN answers a ON a.question=q.id
              WHERE (t.owner=? OR t.status='complete') AND (? IS NULL OR q.id=?)''', (team, question, question)).fetchall()
            if question and not rows:
                raise PermissionError('Question is not available')
            return [dict(json.loads(r['body']), ticket=r['ticket'], solved_by=r['solver'],
                         answered_at=r['timestamp'], answerable=r['owner']==team and r['solver'] is None,
                         finding=json.loads(r['finding']) if r['solver'] else None) for r in rows]

    def answer(self, team, question, answer):
        if not isinstance(answer, str) or len(answer) > 1024:
            raise ValueError('Answer must be at most 1024 characters')
        with self.transaction() as con:
            self.running(con)
            row = con.execute('''SELECT q.*,t.owner,t.status FROM questions q JOIN tickets t ON q.ticket=t.id
                                 WHERE q.id=?''', (question,)).fetchone()
            # Ownership is checked before the correctness oracle, even on duplicate submissions.
            if row is None or row['owner'] != team or row['status'] != 'active':
                raise PermissionError('Claim the corresponding IRIS ticket first')
            if con.execute('SELECT 1 FROM answers WHERE question=?', (question,)).fetchone():
                raise Conflict('Question already answered; points are preserved')
            if not hmac.compare_digest(self.digest(answer), row['digest']):
                return {'correct':False}
            stamp = now()
            event = str(uuid.uuid4())
            con.execute('INSERT INTO answers VALUES (?,?,?,?)', (question, team, stamp, event))
            teamrow = con.execute('SELECT * FROM teams WHERE id=?', (team,)).fetchone()
            finding = dict(json.loads(row['finding']), question=question, team=team,
                           team_name=teamrow['name'], timestamp=stamp, event=event, ticket=row['ticket'])
            self.enqueue(con, 'point:'+question, 'point', dict(finding, ctfd_team=teamrow['ctfd'], value=1))
            self.enqueue(con, 'finding:'+question, 'finding', finding)
            self.record(con, team, 'answer', {'question':question, 'event':event, 'ticket':row['ticket'], 'value':1})
            remaining = con.execute('''SELECT COUNT(*) FROM questions q LEFT JOIN answers a ON q.id=a.question
                                       WHERE q.ticket=? AND a.question IS NULL''', (row['ticket'],)).fetchone()[0]
            if not remaining:
                con.execute("UPDATE tickets SET owner=NULL,status='complete' WHERE id=?", (row['ticket'],))
                self.enqueue(con, 'close:'+row['ticket'], 'close', {'ticket':row['ticket'], 'event':event})
                self.record(con, team, 'close', {'ticket':row['ticket'], 'event':event})
                completed = {r[0] for r in con.execute("SELECT id FROM tickets WHERE status='complete'")}
                for lead in con.execute("SELECT * FROM tickets WHERE status='locked'").fetchall():
                    if set(json.loads(lead['requires'])) <= completed:
                        con.execute("UPDATE tickets SET status='available' WHERE id=?", (lead['id'],))
                        self.enqueue(con, 'ticket:'+lead['id'], 'ticket', {'ticket':lead['id'], 'title':lead['title']})
            return {'correct':True, 'event':event, 'closed':not remaining, 'synchronization':'pending'}

    def snapshot(self):
        with self.transaction(write=False) as con:
            stamp=now();total=0;anchor=None
            for event in con.execute("SELECT timestamp,action FROM audit WHERE action IN ('running','paused') ORDER BY id"):
                at=datetime.fromisoformat(event['timestamp'])
                if event['action']=='running':
                    anchor=at
                elif anchor is not None:
                    total+=(at-anchor).total_seconds();anchor=None
            if anchor is not None:
                total+=(datetime.fromisoformat(stamp)-anchor).total_seconds()
            return {'mode':con.execute('SELECT mode FROM run').fetchone()[0],
                    'elapsed_seconds':max(total,0),'server_time':stamp,
                    'announcements':[dict(id=r['id'],timestamp=r['timestamp'],text=json.loads(r['detail'])['text'])
                                     for r in con.execute("SELECT * FROM audit WHERE action='announcement' ORDER BY id")],
                    'tickets':[dict(r) for r in con.execute("SELECT id,title,subject,owner,status,iris_id,generation FROM tickets WHERE status!='locked'")],
                    'scores':[dict(r) for r in con.execute('''SELECT t.id,t.name,COUNT(a.question) points FROM teams t
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
                for number,name in enumerate(('run','teams','tickets','questions','answers','audit','outbox','delivery_dependencies')):
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
