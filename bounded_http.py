"""Small HTTP server guardrails shared by the offline Python services."""
import socket
import threading
from http.server import ThreadingHTTPServer


class RequestBodyTimeout(Exception):
    """The peer did not deliver its declared request body in time."""


def read_request_body(handler, length):
    """Read exactly *length* bytes or raise a controlled timeout error."""
    try:
        body = handler.rfile.read(length)
    except (TimeoutError, socket.timeout) as exc:
        raise RequestBodyTimeout() from exc
    if len(body) != length:
        raise RequestBodyTimeout()
    return body


class BoundedThreadingHTTPServer(ThreadingHTTPServer):
    """Threading server with per-socket deadlines and a hard handler cap."""

    daemon_threads = True

    def __init__(self, address, handler, *, request_timeout=5.0, max_handlers=32):
        if request_timeout <= 0 or max_handlers < 1:
            raise ValueError('Positive request timeout and handler limit required')
        self.request_timeout = request_timeout
        self.max_handlers = max_handlers
        self._handler_slots = threading.BoundedSemaphore(max_handlers)
        super().__init__(address, handler)

    def get_request(self):
        request, address = super().get_request()
        request.settimeout(self.request_timeout)
        return request, address

    def process_request(self, request, client_address):
        if not self._handler_slots.acquire(blocking=False):
            self._reject_busy(request)
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self._handler_slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._handler_slots.release()

    def _reject_busy(self, request):
        body = b'{"error":"Server is busy; retry shortly"}'
        response = (b'HTTP/1.1 503 Service Unavailable\r\n'
                    b'Content-Type: application/json\r\n'
                    b'Cache-Control: no-store\r\n'
                    b'Connection: close\r\n'
                    b'Content-Length: ' + str(len(body)).encode() + b'\r\n\r\n' + body)
        try:
            # Drain bytes already queued by the peer. Closing a Windows socket
            # with unread request data can turn the intended 503 into a reset.
            request.setblocking(False)
            while request.recv(4096):
                pass
        except (BlockingIOError, OSError):
            pass
        try:
            request.setblocking(True)
            request.settimeout(self.request_timeout)
            request.sendall(response)
            request.shutdown(socket.SHUT_WR)
        except OSError:
            pass
        self.shutdown_request(request)
