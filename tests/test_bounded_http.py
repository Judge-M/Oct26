import socket
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler

from bounded_http import BoundedThreadingHTTPServer, RequestBodyTimeout, read_request_body


class SlowHandler(BaseHTTPRequestHandler):
    entered = threading.Event()

    def log_message(self, *args):
        pass

    def do_POST(self):
        self.entered.set()
        try:
            read_request_body(self, int(self.headers['Content-Length']))
            code = 200
        except RequestBodyTimeout:
            code = 408
        self.send_response(code)
        self.send_header('Content-Length', '0')
        self.end_headers()


class BoundedServerTests(unittest.TestCase):
    def setUp(self):
        SlowHandler.entered.clear()
        self.server = BoundedThreadingHTTPServer(('127.0.0.1', 0), SlowHandler,
                                                 request_timeout=0.2,
                                                 max_handlers=1)
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.worker.join()

    def connect(self):
        return socket.create_connection(('127.0.0.1', self.server.server_port), timeout=2)

    def test_rejection_survives_a_request_still_in_flight(self):
        # Regression: a rejected connection must receive the 503, never a TCP
        # reset. The rejecting server used to sample the peer's request bytes
        # with one non-blocking recv; when the request was still in flight that
        # read nothing, the socket was closed with data unread, and Windows
        # answered with an RST that discarded the 503. The drain is retried
        # until the request is consumed, so the peer's own timing cannot decide
        # whether it gets a response or a reset.
        for attempt in range(25):
            with self.subTest(attempt=attempt):
                first = self.connect()
                try:
                    first.sendall(
                        b'POST / HTTP/1.1\r\nHost: test\r\nContent-Length: 10\r\n\r\nx')
                    self.assertTrue(SlowHandler.entered.wait(1))
                    second = self.connect()
                    try:
                        second.sendall(
                            b'POST / HTTP/1.1\r\nHost: test\r\nContent-Length: 1\r\n\r\nx')
                        try:
                            response = second.recv(4096)
                        except ConnectionAbortedError as exc:
                            self.fail('connection reset instead of 503: %r' % (exc,))
                        self.assertIn(b'503 Service Unavailable', response)
                    finally:
                        second.close()
                    # The in-flight handler must time out and free its slot, or
                    # the next attempt would be rejected for the wrong reason.
                    self.assertIn(b'408 Request Timeout', first.recv(4096))
                finally:
                    first.close()

    def test_slow_body_times_out_and_handler_cap_rejects_excess(self):
        first = self.connect()
        try:
            first.sendall(b'POST / HTTP/1.1\r\nHost: test\r\nContent-Length: 10\r\n\r\nx')
            self.assertTrue(SlowHandler.entered.wait(1))
            second = self.connect()
            try:
                second.sendall(b'POST / HTTP/1.1\r\nHost: test\r\nContent-Length: 1\r\n\r\nx')
                self.assertIn(b'503 Service Unavailable', second.recv(4096))
            finally:
                second.close()
            self.assertIn(b'408 Request Timeout', first.recv(4096))
        finally:
            first.close()
        deadline = time.monotonic() + 1
        response = b''
        while time.monotonic() < deadline:
            recovered = self.connect()
            try:
                recovered.sendall(b'POST / HTTP/1.1\r\nHost: test\r\nContent-Length: 1\r\n\r\nx')
                response = recovered.recv(4096)
            finally:
                recovered.close()
            if b'200 OK' in response:
                break
            time.sleep(0.02)
        self.assertIn(b'200 OK', response)


if __name__ == '__main__':
    unittest.main()
