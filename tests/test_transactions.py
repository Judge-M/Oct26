"""Live transactional failure and pause-race tests (D01).

Uses the existing simulated-sink/local-server patterns (see test_resilience.py).
A local HTTP server commits a receipt then drops the response, exercising the
durable-retry plus transactional-receipt guarantee. REAL multi-service fault
injection against IRIS/CTFd/Wazuh remains BLOCKED (no Docker/Linux host).
"""
import json
import os
import socket
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.request import Request, urlopen

from ridge.state import State, Conflict
from ridge.transport import remote_sink


class DroppingServer:
    """Records one receipt per key, then optionally drops the HTTP response."""

    def __init__(self):
        self.records = {}
        self.lock = threading.Lock()
        self.drop = True
        server = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                length = int(self.headers.get('Content-Length', '0'))
                body = json.loads(self.rfile.read(length))
                key = body['key']
                with server.lock:
                    if key not in server.records:
                        server.records[key] = len(server.records) + 1
                    remote = server.records[key]
                if server.drop:
                    self.close_connection = True
                    try:
                        self.connection.shutdown(socket.SHUT_RDWR)
                    except OSError:
                        pass
                    self.connection.close()
                    return
                data = json.dumps({'id': remote}).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        self.httpd = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    @property
    def url(self):
        host, port = self.httpd.server_address
        return 'http://%s:%d' % (host, port)

    def stop(self):
        self.httpd.shutdown()
        self.httpd.server_close()


class TransactionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.state = State(self.root / 'state.sqlite', retry_delay=0)
        self.state.initialize([dict(id='a', iris='1', ctfd=1, name='A'),
                               dict(id='b', iris='2', ctfd=2, name='B')], [
            dict(id='T01', title='T01', subject='x', release_files=['network/x.csv'], questions=[
                dict(id='T01-Q1', answer='yes', finding=dict(text='t', evidence=['ref'], limitation='scope'))]),
            dict(id='T02', title='T02', subject='x', release_files=[], questions=[
                dict(id='T02-Q1', answer='yes', finding=dict(text='t', evidence=['ref'], limitation='scope'))]),
        ])
        self.server = DroppingServer()

    def tearDown(self):
        self.server.stop()
        self.tmp.cleanup()

    def sink(self):
        def deliver(kind, key, payload, context):
            request = Request(self.server.url + '/internal',
                              json.dumps({'key': key, 'kind': kind, 'payload': payload}).encode(),
                              {'Content-Type': 'application/json'})
            with urlopen(request, timeout=5) as response:
                return json.load(response)['id']
        return deliver

    def test_remote_commit_then_lost_response_yields_one_effect(self):
        self.state.provision('operator')
        sink = self.sink()
        self.assertFalse(self.state.sync_once(sink))
        failures = self.state.diagnostics()['failures']
        self.assertEqual(failures[0]['attempts'], 1)
        self.assertTrue(failures[0]['error'])
        self.server.drop = False
        while self.state.sync_once(sink):
            pass
        t01 = [key for key in self.server.records if key.endswith(':ticket:T01')]
        self.assertEqual(len(t01), 1)
        self.assertEqual(self.server.records[t01[0]], 1)
        self.assertEqual(self.state.diagnostics()['failures'], [])

    def test_simultaneous_duplicate_deliveries_one_effect(self):
        sink = self.sink()
        self.server.drop = False
        with ThreadPoolExecutor(4) as pool:
            results = list(pool.map(lambda _: sink('point', 'run:point:T01-Q1', {}, {}), range(4)))
        self.assertEqual(set(results), {1})
        self.assertEqual(len(self.server.records), 1)

    def test_stale_generation_takeover_rejected(self):
        self.state.provision('operator')
        self.server.drop = False
        while self.state.sync_once(self.sink()):
            pass
        self.state.mode('operator', 'running')
        self.state.claim('a', 'T01', 0)
        self.state.release('a', 'T01', 1)
        self.state.claim('b', 'T01', 1)
        with self.assertRaises(Conflict):
            self.state.release('b', 'T01', 0)
        with self.assertRaises(Conflict):
            self.state.claim('a', 'T01', 1)
        self.assertEqual(self.state.snapshot()['tickets'][0]['owner'], 'b')

    def test_dead_worker_lease_replays_same_key(self):
        self.state.provision('operator')
        with self.state.transaction() as con:
            con.execute("UPDATE outbox SET lease='dead',lease_until=?,attempts=3 WHERE ticket='T01'",
                        (time.time() - 1,))
        self.server.drop = False
        self.assertTrue(self.state.sync_once(self.sink()))
        self.assertEqual(len([key for key in self.server.records if key.endswith(':ticket:T01')]), 1)
        self.assertLessEqual(self.state.diagnostics()['active_leases'], 0)

    def test_wazuh_failure_does_not_block_unrelated_ticket(self):
        self.state.provision('operator')
        self.state.retry_delay = 30

        def failing_publish(ticket, required):
            if ticket == 'T01':
                raise TimeoutError('wazuh index unavailable')

        def fake_post(url, token, body, header='Authorization'):
            return {'id': 7}

        with patch.dict(os.environ, IRIS_URL='http://iris', CTFD_URL='http://ctfd'), \
             patch('ridge.evidence_release.publish', side_effect=failing_publish), \
             patch('ridge.transport.post', side_effect=fake_post), \
             patch('ridge.transport.secret', return_value='x' * 40):
            self.assertFalse(self.state.sync_once(remote_sink))
            self.assertTrue(self.state.sync_once(remote_sink))
        with self.state.transaction(write=False) as con:
            done = {row['id']: row['done'] for row in con.execute('SELECT id,done FROM outbox')}
        t02 = next(key for key in done if key.endswith(':ticket:T02'))
        t01 = next(key for key in done if key.endswith(':ticket:T01'))
        self.assertEqual(done[t02], 1)
        self.assertEqual(done[t01], 0)
        failures = {row['id']: row for row in self.state.diagnostics()['failures']}
        self.assertEqual(failures[t01]['error'], 'TimeoutError')

    def test_pause_and_export_race_with_inflight_delivery(self):
        self.state.provision('operator')
        entered = threading.Event()
        finish = threading.Event()

        def slow(kind, key, payload, context):
            entered.set()
            self.assertTrue(finish.wait(5))
            return 1

        worker = threading.Thread(target=lambda: self.state.sync_once(slow))
        worker.start()
        try:
            self.assertTrue(entered.wait(2))
            begin = time.monotonic()
            self.state.mode('operator', 'paused')
            self.assertLess(time.monotonic() - begin, 1)
            with self.assertRaises(Conflict):
                with self.state.export_barrier():
                    pass
            with self.state.transaction(write=False) as con:
                self.assertEqual(con.execute('SELECT COUNT(*) FROM outbox WHERE done=0').fetchone()[0], 2)
        finally:
            finish.set()
            worker.join()

    def test_no_network_io_holds_the_sqlite_transaction(self):
        self.state.provision('operator')
        entered = threading.Event()
        finish = threading.Event()

        def slow(*args):
            entered.set()
            self.assertTrue(finish.wait(5))
            return 1

        worker = threading.Thread(target=lambda: self.state.sync_once(slow))
        worker.start()
        try:
            self.assertTrue(entered.wait(2))
            begin = time.monotonic()
            self.state.snapshot()
            self.state.provision('operator')
            self.assertLess(time.monotonic() - begin, 1)
        finally:
            finish.set()
            worker.join()

    def test_failures_are_recorded_with_backoff_not_swallowed(self):
        self.state.provision('operator')

        def broken(*args):
            raise ConnectionError('destination down')

        self.assertFalse(self.state.sync_once(broken))
        failure = self.state.diagnostics()['failures'][0]
        self.assertEqual(failure['error'], 'ConnectionError')
        self.assertGreaterEqual(failure['attempts'], 1)


if __name__ == '__main__':
    unittest.main()
