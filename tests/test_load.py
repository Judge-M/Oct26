"""Tests for expanded.load (F03 tooling); no live services required."""
import json
import os
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

from expanded.load import (CtfdBot, IrisBot, LoadError, build_report, markdown, mib,
                           outbox_depth, percentile)


class PercentileTests(unittest.TestCase):
    def test_nearest_rank(self):
        self.assertEqual(percentile([0.1, 0.5, 0.2, 9.0], 50), 0.2)
        self.assertEqual(percentile([0.1, 0.5, 0.2, 9.0], 95), 9.0)

    def test_empty_raises(self):
        with self.assertRaises(LoadError):
            percentile([], 95)


class MibTests(unittest.TestCase):
    def test_parses_docker_units(self):
        self.assertEqual(mib('144.6MiB'), 144.6)
        self.assertEqual(mib('1.945GiB'), 1991.68)
        self.assertEqual(mib(''), 0.0)
        self.assertEqual(mib('junk'), 0.0)


class ReportTests(unittest.TestCase):
    def config(self, teams=2, ram=20):
        return {'teams': teams, 'sessions_per_team': 3, 'host': {'ram_gib': ram},
                'event_profile': {'teams': 10, 'min_host_ram_gib': 32}}

    def test_dev_host_is_non_certifying(self):
        samples = [{'endpoint': 'ctfd:challenges', 'seconds': 0.2, 'ok': True}] * 20
        containers = [{'containers': [{'Name': 'ctfd', 'MemUsage': '300MiB / 15GiB'}]}]
        report = build_report(self.config(), samples, containers, [0, 1], 60)
        self.assertFalse(report['certifying'])
        self.assertIn('NON-CERTIFYING', report['label'])
        self.assertEqual(report['sessions'], 6)
        self.assertEqual(report['latency']['ctfd:challenges']['p95_s'], 0.2)

    def test_event_profile_run_is_certifying(self):
        report = build_report(self.config(teams=10, ram=64), [], [], [], 600)
        self.assertTrue(report['certifying'])

    def test_outbox_minmax_omitted_when_unreadable(self):
        report = build_report(self.config(), [], [], [None], 60)
        self.assertIsNone(report['outbox_depth_minmax'])

    def test_markdown_lists_endpoints_and_containers(self):
        report = build_report(self.config(),
                              [{'endpoint': 'iris:dashboard', 'seconds': 0.1, 'ok': True}],
                              [{'containers': [{'Name': 'iris', 'MemUsage': '173MiB / 15GiB'}]}],
                              [], 60)
        text = markdown(report)
        self.assertIn('iris:dashboard', text)
        self.assertIn('| iris | 173.0 |', text)


class FakeCtfd(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _send(self, body, status=200, content_type='text/html'):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == '/login':
            # Real CTFd emits the single-quoted dict form:
            self._send(b"""'csrfNonce': "aaaabbbb",""")
        elif self.path == '/silent-ridge':
            self._send(b'<form method="post"><input type="hidden" name="nonce" '
                       b'value="eeeeffff"><input type="hidden" name="question" '
                       b'value="q1"><input name="answer"></form>')
        elif self.path == '/silent-ridge/status':
            self._send(b'{"pending": 0, "mode": "running"}', content_type='application/json')
        elif self.path == '/api/v1/scoreboard':
            self._send(b'{"success": true, "data": []}', content_type='application/json')
        else:
            self._send(b'not found', 404)

    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length)
        if self.path == '/login':
            self._send(b'ok')
        elif self.path == '/silent-ridge':
            if b'nonce=eeeeffff' not in body:
                self._send(b'forbidden', 403)
            else:
                self._send(b'Not yet. Try the next help level.')
        else:
            self._send(b'not found', 404)


class CtfdBotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(('127.0.0.1', 0), FakeCtfd)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.base = f'http://127.0.0.1:{cls.server.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def test_login_and_answer_records_samples(self):
        samples = []
        bot = CtfdBot(self.base, 'team-01-p01', 'pw', samples)
        bot.login()
        self.assertEqual(bot.nonce, 'aaaabbbb')
        import random
        rng = random.Random(0)
        for _ in range(30):
            bot.act(rng)
        self.assertTrue(samples)
        self.assertTrue(all(s['ok'] for s in samples))
        endpoints = {s['endpoint'] for s in samples}
        self.assertIn('ctfd:questions', endpoints)
        self.assertIn('ctfd:answer', endpoints)

    def test_login_without_nonce_fails_loudly(self):
        class NoNonce(FakeCtfd):
            def do_GET(self):
                self._send(b'<html>no nonce here</html>')
        server = HTTPServer(('127.0.0.1', 0), NoNonce)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            bot = CtfdBot(f'http://127.0.0.1:{server.server_port}', 'u', 'p', [])
            with self.assertRaises(LoadError):
                bot.login()
        finally:
            server.shutdown()


class OutboxTests(unittest.TestCase):
    def test_missing_database_returns_none(self):
        self.assertIsNone(outbox_depth('definitely/not/here.sqlite'))

    def test_counts_pending_rows_from_a_copy(self):
        import sqlite3
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'state.sqlite')
            db = sqlite3.connect(path)
            db.execute('CREATE TABLE outbox (id INTEGER, delivered INTEGER)')
            db.executemany('INSERT INTO outbox VALUES (?, ?)',
                           [(1, None), (2, 'yes'), (3, None)])
            db.commit()
            db.close()
            self.assertEqual(outbox_depth(path), 2)


if __name__ == '__main__':
    unittest.main()
