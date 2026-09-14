"""Durable global progress and serialized ownership, independent of service uptime.

Only trusted application adapters call this module. Never accept a team ID from
participant JSON: derive it from the authenticated IRIS/CTFd application identity.
SQLite is local to the integration host, not an NFS/shared case database.
"""
import hashlib
import hmac
import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


def now():
    return datetime.now(timezone.utc).isoformat()


class Conflict(ValueError):
    pass


class State:
    def __init__(self, path):
        self.path = Path(path)

    @contextmanager
    def transaction(self):
        con = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        con.row_factory = sqlite3.Row
        con.execute('PRAGMA foreign_keys=ON')
        try:
            con.execute('BEGIN IMMEDIATE')
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
            if con.execute('SELECT 1 FROM run').fetchone():
                raise Conflict('Run exists; export before resetting')
            con.execute('INSERT INTO run VALUES (?,?)', (str(uuid.uuid4()), 'paused'))
            for t in teams:
                con.execute('INSERT INTO teams VALUES (?,?,?,?)', (t['id'], str(t['iris']), t['ctfd'], t['name']))
            for t in tickets:
                requires = t.get('requires', [])
                con.execute('INSERT INTO tickets VALUES (?,?,?,?,?,?,?)',
                            (t['id'], t['title'], t['subject'], None, 'locked' if requires else 'available', None, json.dumps(requires)))
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
        con.execute('INSERT OR IGNORE INTO outbox(id,kind,payload) VALUES (?,?,?)',
                    (run+':'+key, kind, json.dumps(payload)))

    def identity(self, application, external):
        if application not in ('iris', 'ctfd'):
            raise ValueError('Unknown application')
        with self.transaction() as con:
            row = con.execute(f'SELECT id FROM teams WHERE {application}=?', (external,)).fetchone()
            if row is None:
                raise PermissionError('Identity is not mapped to a team')
            return row[0]

    @staticmethod
    def running(con):
        if con.execute('SELECT mode FROM run').fetchone()[0] != 'running':
            raise Conflict('Exercise is paused')

    def mode(self, actor, value):
        if value not in ('running', 'paused'):
            raise ValueError('Invalid mode')
        with self.transaction() as con:
            if con.execute('SELECT mode FROM run').fetchone()[0] == value:
                return
            con.execute('UPDATE run SET mode=?', (value,))
            self.record(con, actor, value, {})

    def announce(self, actor, text):
        if not isinstance(text, str) or not text.strip() or len(text)>4000:
            raise ValueError('Announcement must contain 1–4000 characters')
        with self.transaction() as con:
            self.record(con, actor, 'announcement', {'text':text})

    def claim(self, team, ticket):
        with self.transaction() as con:
            self.running(con)
            if not con.execute('SELECT 1 FROM teams WHERE id=?', (team,)).fetchone():
                raise PermissionError('Unknown team')
            if con.execute('SELECT 1 FROM tickets WHERE owner=?', (team,)).fetchone():
                raise Conflict('Relinquish your current ticket first')
            row = con.execute('SELECT * FROM tickets WHERE id=?', (ticket,)).fetchone()
            if row is None or row['status'] != 'available' or row['iris_id'] is None:
                raise Conflict('Ticket is not available in IRIS')
            con.execute("UPDATE tickets SET owner=?,status='active' WHERE id=?", (team, ticket))
            self.record(con, team, 'claim', {'ticket':ticket})
            self.enqueue(con, 'ownership:'+str(uuid.uuid4()), 'ownership', {'ticket':ticket, 'team':team})

    def release(self, team, ticket, recovery_actor=None, reason=None):
        if recovery_actor and not reason:
            raise ValueError('Recovery requires a reason')
        with self.transaction() as con:
            if not recovery_actor:
                self.running(con)
            row = con.execute('SELECT * FROM tickets WHERE id=?', (ticket,)).fetchone()
            if row is None or row['status'] != 'active' or (not recovery_actor and row['owner'] != team):
                raise PermissionError('Only the owner can relinquish this ticket')
            con.execute("UPDATE tickets SET owner=NULL,status='available' WHERE id=?", (ticket,))
            self.record(con, recovery_actor or team, 'recover' if recovery_actor else 'release',
                        {'ticket':ticket, 'previous_owner':row['owner'], 'reason':reason})
            self.enqueue(con, 'ownership:'+str(uuid.uuid4()), 'ownership', {'ticket':ticket, 'team':None})

    def questions(self, team, question=None):
        with self.transaction() as con:
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
        with self.transaction() as con:
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
                    'tickets':[dict(r) for r in con.execute("SELECT id,title,subject,owner,status,iris_id FROM tickets WHERE status!='locked'")],
                    'scores':[dict(r) for r in con.execute('''SELECT t.id,t.name,COUNT(a.question) points FROM teams t
                                  LEFT JOIN answers a ON a.team=t.id GROUP BY t.id ORDER BY points DESC,t.id''')],
                    'pending':con.execute('SELECT COUNT(*) FROM outbox WHERE done=0').fetchone()[0]}

    def sync_once(self, sink):
        """One serialized consumer; remote adapters must reconcile stable IDs before creating.

        Hold the write transaction across the bounded remote request. A crash after
        remote success rolls back the local ack; the next attempt finds its marker.
        Preserve ordering: findings precede closure, and closure precedes follow-ups.
        """
        with self.transaction() as con:
            row = con.execute('SELECT rowid,* FROM outbox WHERE done=0 ORDER BY rowid LIMIT 1').fetchone()
            if not row:
                return False
            try:
                result = sink(row['kind'], row['id'], json.loads(row['payload']), con)
                if row['kind'] == 'ticket':
                    con.execute('UPDATE tickets SET iris_id=? WHERE id=?',
                                (int(result), json.loads(row['payload'])['ticket']))
                con.execute('UPDATE outbox SET done=1,error=NULL,remote=?,attempts=attempts+1 WHERE id=?',
                            (str(result), row['id']))
            except Exception as exc:
                # Never persist HTTP bodies, tokens or participant submissions in errors.
                con.execute('UPDATE outbox SET error=?,attempts=attempts+1 WHERE id=?',
                            (type(exc).__name__, row['id']))
                return False
            return True

    def export(self, destination):
        """A complete, coherent private integration snapshot; no stored submitted flags."""
        destination = Path(destination)
        if destination.exists():
            raise ValueError('Export destination already exists')
        with self.transaction() as con:
            data = {name:[dict(r) for r in con.execute('SELECT * FROM '+name)] for name in
                    ('run','teams','tickets','questions','answers','audit','outbox')}
            with destination.open('x', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
        return destination
