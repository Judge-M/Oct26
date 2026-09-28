"""Tests for expanded.load (F03 tooling); no live services required."""
import json
import os
import tempfile
import threading
import unittest
import urllib.error
from unittest import mock
from http.server import BaseHTTPRequestHandler, HTTPServer

from expanded.load import (CtfdBot, IrisBot, LoadError, TimedClient, build_report,
                           login_bots, markdown, mib, outbox_depth, percentile,
                           resolve_target_urls, retry_after_seconds)


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
            self.send_response(302)
            self.send_header('Location', '/silent-ridge')
            self.end_headers()
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


class RateLimitTests(unittest.TestCase):
    def test_retries_429_and_records_both_attempts(self):
        class OnceLimited(FakeCtfd):
            requests = 0

            def do_GET(self):
                type(self).requests += 1
                if type(self).requests == 1:
                    self.send_response(429)
                    self.send_header('Retry-After', '0')
                    self.end_headers()
                else:
                    self._send(b'ok')

        server = HTTPServer(('127.0.0.1', 0), OnceLimited)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            samples = []
            with mock.patch('expanded.load.time.sleep') as sleeper:
                payload = TimedClient(f'http://127.0.0.1:{server.server_port}', samples).request(
                    'test:retry', '/login')
            self.assertEqual(payload, b'ok')
            self.assertEqual([s['ok'] for s in samples], [False, True])
            self.assertEqual(samples[0]['detail'], 'http 429')
            sleeper.assert_called_once_with(0.5)
        finally:
            server.shutdown()
            server.server_close()

    def test_persistent_429_stops_after_five_attempts(self):
        class AlwaysLimited(FakeCtfd):
            def do_GET(self):
                self.send_response(429)
                self.end_headers()

        server = HTTPServer(('127.0.0.1', 0), AlwaysLimited)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            samples = []
            with mock.patch('expanded.load.time.sleep') as sleeper:
                with self.assertRaisesRegex(LoadError, 'still rate-limited after 5 attempts'):
                    TimedClient(f'http://127.0.0.1:{server.server_port}', samples).request(
                        'test:retry', '/login')
            self.assertEqual(len(samples), 5)
            self.assertTrue(all(s['detail'] == 'http 429' for s in samples))
            self.assertEqual(sleeper.call_count, 4)
        finally:
            server.shutdown()
            server.server_close()

    def test_retry_after_is_bounded_and_login_burst_is_paced(self):
        self.assertEqual(retry_after_seconds('3', 0), 3.0)
        self.assertEqual(retry_after_seconds('999', 0), 10.0)
        self.assertEqual(retry_after_seconds('bad-header', 2), 2.0)
        calls = []
        class Bot:
            def login(self):
                calls.append('login')
        with mock.patch('expanded.load.time.sleep', side_effect=lambda seconds: calls.append(seconds)):
            login_bots([Bot(), Bot(), Bot()])
        self.assertEqual(calls, ['login', 0.5, 'login', 0.5, 'login'])


class TargetUrlTests(unittest.TestCase):
    def test_auto_urls_follow_runtime_bind_and_ports(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime = os.path.join(tmp, 'runtime')
            os.mkdir(runtime)
            os.mkdir(os.path.join(runtime, 'secrets'))
            with open(os.path.join(runtime, 'local.json'), 'w', encoding='utf-8') as stream:
                json.dump({'bind_ip': '192.168.1.200',
                           'ports': {'ctfd': 18083, 'iris': 18081}}, stream)
            config = {'credentials': os.path.join(runtime, 'secrets', 'team-credentials.json'),
                      'ctfd_url': 'auto', 'iris_url': 'auto'}
            resolved = resolve_target_urls(config)
            self.assertEqual(resolved['ctfd_url'], 'http://192.168.1.200:18083')
            self.assertEqual(resolved['iris_url'], 'http://192.168.1.200:18081')
            self.assertEqual(config['ctfd_url'], 'auto')

    def test_unreachable_login_names_configured_target(self):
        class OfflineBot:
            client = type('Client', (), {'base': 'http://192.168.1.200:8083'})()

            def login(self):
                raise urllib.error.URLError('connection refused')

        with self.assertRaisesRegex(LoadError, '192.168.1.200:8083'):
            login_bots([OfflineBot()])


class AuthPageTests(unittest.TestCase):
    def test_missing_authenticated_page_marker_is_a_failed_sample(self):
        class LoginHtml(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                body = b'<form><input name="password"></form>'
                self.send_response(200)
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        server = HTTPServer(('127.0.0.1', 0), LoginHtml)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            samples = []
            with self.assertRaisesRegex(LoadError, 'expected authenticated page'):
                TimedClient(f'http://127.0.0.1:{server.server_port}', samples).request(
                    'iris:dashboard', '/dashboard', require_authenticated=True,
                    required_marker=b'Logout')
            self.assertFalse(samples[-1]['ok'])
        finally:
            server.shutdown()
            server.server_close()

    def test_ctfd_login_redirect_back_to_login_is_failure(self):
        class Bounce(FakeCtfd):
            def do_POST(self):
                self.send_response(302)
                self.send_header('Location', '/login')
                self.end_headers()

        server = HTTPServer(('127.0.0.1', 0), Bounce)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            samples = []
            with self.assertRaisesRegex(LoadError, 'ended on the login page'):
                CtfdBot(f'http://127.0.0.1:{server.server_port}', 'team-01-p01', 'pw', samples).login()
            self.assertFalse(samples[-1]['ok'])
            self.assertEqual(samples[-1]['endpoint'], 'ctfd:login')
        finally:
            server.shutdown()
            server.server_close()

    def test_iris_dashboard_bounce_is_failure_even_when_final_status_is_200(self):
        class Bounce(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                if self.path.startswith('/login'):
                    body = b'<form><input name="password"></form>'
                    self.send_response(200)
                    self.send_header('Content-Length', str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                else:
                    self.send_response(302)
                    self.send_header('Location', '/login?next=/dashboard')
                    self.end_headers()

            def do_POST(self):
                self.send_response(302)
                self.send_header('Location', '/dashboard')
                self.end_headers()

        server = HTTPServer(('127.0.0.1', 0), Bounce)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            samples = []
            with self.assertRaisesRegex(LoadError, 'ended on the login page'):
                IrisBot(f'http://127.0.0.1:{server.server_port}', 'team-01', 'pw', samples).login()
            self.assertFalse(samples[-1]['ok'])
            self.assertEqual(samples[-1]['endpoint'], 'iris:login')
        finally:
            server.shutdown()
            server.server_close()


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
