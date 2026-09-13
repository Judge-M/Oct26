"""Offline rehearsal board. No outbound requests, upload, or controller HTTP API."""
import argparse
import base64
import hashlib
import hmac
import html
import json
import sqlite3
import secrets
import threading
import time
from contextlib import closing
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit
from exercise_clock import elapsed_at

CELLS = ('network', 'endpoint', 'identity', 'server', 'hunting')


def database(state):
    con = sqlite3.connect(state / 'tickets.sqlite', timeout=15)
    con.execute('PRAGMA foreign_keys=ON')
    con.executescript('''
        CREATE TABLE IF NOT EXISTS tickets(id INTEGER PRIMARY KEY, owner TEXT, status TEXT);
        CREATE TABLE IF NOT EXISTS comments(id INTEGER PRIMARY KEY, ticket INTEGER REFERENCES tickets(id),
          author TEXT, created TEXT, body TEXT);
    ''')
    columns={row[1] for row in con.execute('PRAGMA table_info(comments)')}
    for name,kind in [('elapsed_seconds','REAL'),('clock_event','TEXT')]:
        if name not in columns:
            con.execute(f'ALTER TABLE comments ADD COLUMN {name} {kind}')
    for i, cell in enumerate(CELLS, 1):
        con.execute('INSERT OR IGNORE INTO tickets VALUES (?, ?, ?)', (i, cell, 'Investigating'))
    con.commit()
    return con


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # Never log Authorization headers or participant text.

    def send(self, status, body, kind='application/json'):
        if not isinstance(body, bytes):
            body = (json.dumps(body) if kind == 'application/json' else body).encode()
        self.send_response(status)
        self.send_header('Content-Type', kind)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(body)

    def auth(self):
        try:
            method, token = self.headers.get('Authorization', '').split(' ', 1)
            if method == 'Bearer':
                with self.server.session_lock:
                    session = self.server.sessions.get(token)
                    if session and session[1] > time.monotonic():
                        return session[0]
                    self.server.sessions.pop(token, None)
                self.send(401, {'error': 'Session expired. Sign in again.'})
                return None
            user, password = base64.b64decode(token, validate=True).decode().split(':', 1)
            entry = self.server.credentials.get(user)
            if method == 'Basic' and entry:
                digest = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(entry['salt']), 200000).hex()
                if hmac.compare_digest(digest, entry['hash']):
                    return user
        except (ValueError, UnicodeError):
            pass
        self.send(401, {'error': 'Authentication required'})
        return None

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == '/health':
            return self.send(200, {'status': 'ok'})
        if path in ('/', '/ui.js', '/style.css'):
            filename = {'/': 'index.html', '/ui.js': 'ui.js', '/style.css': 'style.css'}[path]
            mime = {'/': 'text/html; charset=utf-8', '/ui.js': 'text/javascript', '/style.css': 'text/css'}[path]
            return self.send(200, (Path(__file__).parent / filename).read_bytes(), mime)
        if path == '/api/me':
            user = self.auth()
            if user:
                self.send(200, {'cell': user})
            return
        if not self.auth():
            return
        if path == '/api/control':
            return self.send(200, self.control_events())
        if path == '/api/tickets':
            with closing(database(self.server.state)) as con, con:
                tickets = [dict(zip(('id', 'owner', 'status'), row)) for row in con.execute('SELECT * FROM tickets ORDER BY id')]
                for ticket in tickets:
                    ticket['comments'] = [dict(zip(('id', 'author', 'created', 'body', 'elapsed_seconds', 'clock_event'), row)) for row in con.execute(
                        'SELECT id,author,created,body,elapsed_seconds,clock_event FROM comments WHERE ticket=? ORDER BY id', (ticket['id'],))]
            return self.send(200, tickets)
        if path == '/api/files':
            return self.send(200, sorted(p.relative_to(self.server.root).as_posix() for p in self.server.root.rglob('*') if p.is_file() and not p.is_symlink()))
        if path.startswith('/files/'):
            relative = unquote(path[7:])
            if '\\' in relative or ':' in relative or any(x in ('.', '..') for x in relative.split('/')):
                return self.send(404, {'error': 'Unknown file'})
            candidate = (self.server.root / relative).resolve()
            if candidate.is_relative_to(self.server.root) and candidate.is_file():
                return self.send(200, candidate.read_bytes(), 'application/octet-stream')
        self.send(404, {'error': 'Unknown resource'})

    def do_POST(self):
        path = urlsplit(self.path).path
        if path == '/api/login':
            if self.headers.get('X-Exercise-Request') != '1' or self.headers.get('Content-Type') != 'application/json':
                return self.send(403, {'error': 'Use the exercise client'})
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 4096:
                    raise ValueError()
                payload = json.loads(self.rfile.read(length))
                user, password = payload['cell'], payload['password']
                if not isinstance(user, str) or not isinstance(password, str):
                    raise ValueError()
                entry = self.server.credentials.get(user)
                if not entry or not hmac.compare_digest(entry['hash'], hashlib.pbkdf2_hmac(
                        'sha256', password.encode(), bytes.fromhex(entry['salt']), 200000).hex()):
                    return self.send(401, {'error': 'Incorrect cell or password'})
                token = secrets.token_urlsafe(32)
                with self.server.session_lock:
                    now = time.monotonic()
                    self.server.sessions = {k: v for k, v in self.server.sessions.items() if v[1] > now}
                    if len(self.server.sessions) >= 1000:
                        return self.send(503, {'error': 'Session capacity reached; sign out unused tabs'})
                    self.server.sessions[token] = (user, now + 8 * 3600)
                return self.send(200, {'cell': user, 'token': token})
            except (ValueError, KeyError, TypeError):
                return self.send(400, {'error': 'Choose a cell and enter its password'})
        user = self.auth()
        if not user:
            return
        # JSON plus explicit custom header prevents browser cross-origin form requests.
        if self.headers.get('X-Exercise-Request') != '1' or self.headers.get('Content-Type') != 'application/json':
            return self.send(403, {'error': 'Use the exercise client'})
        if path == '/api/logout':
            token = self.headers.get('Authorization', '').removeprefix('Bearer ')
            with self.server.session_lock:
                self.server.sessions.pop(token, None)
            return self.send(200, {'signed_out': True})
        if urlsplit(self.path).path != '/api/update':
            return self.send(404, {'error': 'Unknown resource'})
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 16384:
                return self.send(413, {'error': 'Request too large or empty'})
            payload = json.loads(self.rfile.read(length))
            ticket = payload['ticket']
            body = payload.get('body', '')
            status = payload.get('status')
            if type(ticket) is not int or ticket not in range(1, 6) or not isinstance(body, str) or not 1 <= len(body.strip()) <= 8000:
                raise ValueError()
            if status not in (None, 'Investigating', 'Assessment sent', 'Closed'):
                raise ValueError()
            with closing(database(self.server.state)) as con, con:
                owner = con.execute('SELECT owner FROM tickets WHERE id=?', (ticket,)).fetchone()[0]
                if status and owner != user:
                    return self.send(403, {'error': 'Only the owning cell changes status; all cells may comment'})
                created=datetime.now(timezone.utc).isoformat()
                events=self.control_events()
                con.execute('INSERT INTO comments(ticket,author,created,body,elapsed_seconds,clock_event) VALUES(?,?,?,?,?,?)',
                            (ticket, user, created, body.strip(), elapsed_at(events,created), events[-1]['id'] if events else None))
                if status:
                    con.execute('UPDATE tickets SET status=? WHERE id=?', (status, ticket))
            self.send(201, {'saved': True})
        except (ValueError, KeyError, TypeError):
            self.send(400, {'error': 'Invalid ticket, text, or status'})


    def control_events(self):
        path=self.server.control/'ledger.json'
        return json.loads(path.read_text()) if path.exists() else []


def serve(host, port, root, state, credentials, control=None):
    root, state = Path(root).resolve(), Path(state).resolve()
    if not root.is_dir() or not state.is_dir():
        raise ValueError('Run exercise.py init first')
    server = ThreadingHTTPServer((host, port), Handler)
    server.root, server.state = root, state
    server.control=Path(control).resolve() if control else root.parent/'control'
    server.credentials = json.loads(Path(credentials).read_text())
    server.sessions = {}
    server.session_lock = threading.Lock()
    if set(server.credentials) != set(CELLS):
        raise ValueError('Expected five cell credentials')
    database(state).close()
    return server


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8080)
    parser.add_argument('--root', default='runtime/public')
    parser.add_argument('--state', default='runtime/state')
    parser.add_argument('--credentials', default='runtime/credentials.json')
    parser.add_argument('--control', default='runtime/control')
    args = parser.parse_args()
    serve(**vars(args)).serve_forever()
