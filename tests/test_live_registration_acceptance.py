from __future__ import annotations

import importlib.util
import contextlib
import io
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
import tempfile
import threading
import unittest
import urllib.parse


TOOL_PATH = Path(__file__).with_name("live_registration_acceptance.py")
SPEC = importlib.util.spec_from_file_location("live_registration_acceptance", TOOL_PATH)
acceptance = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = acceptance
SPEC.loader.exec_module(acceptance)

from ridge.registration import RegistrationConfig, RegistrationStore


class _QuietHandler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def send_body(self, body: bytes, status: int = 200,
                  content_type: str = "text/html") -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def form(self) -> dict[str, str]:
        length = int(self.headers.get("Content-Length", "0"))
        values = urllib.parse.parse_qs(self.rfile.read(length).decode("utf-8"))
        return {key: rows[-1] for key, rows in values.items()}


def _start(handler):
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


class LiveRegistrationAcceptanceTests(unittest.TestCase):
    def setUp(self):
        # Keep SQLite and cleanup inside the repository workspace.  The Codex
        # Windows sandbox's system TEMP ACL does not permit sqlite3 to create
        # files reliably.
        self.tmp = tempfile.TemporaryDirectory(dir=TOOL_PATH.parents[1] / "work")
        self.db = Path(self.tmp.name) / "registrations.sqlite"
        self.store = RegistrationStore(
            str(self.db), RegistrationConfig(max_teams=1), enrollment_code="ROOM-CODE")
        self.expected = {}
        owner = self

        class Ctfd(_QuietHandler):
            def do_GET(self):
                if self.path == "/silent-ridge/register":
                    self.send_body(b'<input name="nonce" value="register-nonce">')
                elif self.path == "/login":
                    self.send_body(b"'csrfNonce': \"aabbccdd\"")
                elif self.path.startswith("/silent-ridge/registration/"):
                    self.send_body(b"ready")
                elif self.path == "/silent-ridge":
                    if "ctfd=ok" not in self.headers.get("Cookie", ""):
                        self.send_response(302)
                        self.send_header("Location", "/login")
                        self.end_headers()
                    else:
                        self.send_body(b"Your questions and completed shared history")
                else:
                    self.send_body(b"not found", 404)

            def do_POST(self):
                data = self.form()
                if self.path == "/silent-ridge/register":
                    if data.get("nonce") != "register-nonce":
                        self.send_body(b"forbidden", 403)
                        return
                    created = owner.store.register(
                        data["team_name"], data["captain_name"],
                        enrollment_code=data["enrollment_code"])
                    claimed = owner.store.claim_pending()
                    credentials = owner.store.activate_credentials(
                        claimed["id"], claimed["worker_token"])
                    owner.expected = credentials
                    owner.store.complete(
                        claimed["id"], {"desktop_urls": ["one", "two", "three"]},
                        claimed["worker_token"], credentials=credentials)
                    self.send_response(302)
                    self.send_header("Location", created["retrieve_path"])
                    self.end_headers()
                elif self.path == "/login":
                    seat = owner.expected["ctfd"]["members"][0]
                    if (data.get("name") == seat["username"]
                            and data.get("password") == seat["password"]
                            and data.get("nonce") == "aabbccdd"):
                        self.send_response(302)
                        self.send_header("Set-Cookie", "ctfd=ok; Path=/")
                        self.send_header("Location", "/silent-ridge")
                        self.end_headers()
                    else:
                        self.send_response(302)
                        self.send_header("Location", "/login")
                        self.end_headers()
                else:
                    self.send_body(b"not found", 404)

        class Iris(_QuietHandler):
            def do_GET(self):
                if self.path == "/login":
                    self.send_body(b'<input name="csrf_token" value="iris-csrf">')
                elif self.path == "/dashboard":
                    if "iris=ok" in self.headers.get("Cookie", ""):
                        self.send_body(b"Dashboard Logout")
                    else:
                        self.send_response(302)
                        self.send_header("Location", "/login")
                        self.end_headers()
                else:
                    self.send_body(b"not found", 404)

            def do_POST(self):
                data = self.form()
                expected = owner.expected["iris"]
                if (data.get("username") == expected["username"]
                        and data.get("password") == expected["password"]
                        and data.get("csrf_token") == "iris-csrf"):
                    self.send_response(302)
                    self.send_header("Set-Cookie", "iris=ok; Path=/")
                    self.send_header("Location", "/dashboard")
                    self.end_headers()
                else:
                    self.send_response(302)
                    self.send_header("Location", "/login")
                    self.end_headers()

        class Guacamole(_QuietHandler):
            reject = False

            def do_POST(self):
                if self.path != "/guacamole/api/tokens":
                    self.send_body(b"not found", 404)
                    return
                data = self.form()
                expected = owner.expected["guacamole"]
                if (not type(self).reject
                        and data.get("username") == expected["username"]
                        and data.get("password") == expected["password"]):
                    self.send_body(json.dumps({
                        "authToken": "ephemeral-token",
                        "username": expected["username"],
                        "availableDataSources": ["postgresql"],
                    }).encode(), content_type="application/json")
                else:
                    self.send_body(b"denied", 403)

        self.guac_handler = Guacamole
        self.ctfd, self.ctfd_thread = _start(Ctfd)
        self.iris, self.iris_thread = _start(Iris)
        self.guac, self.guac_thread = _start(Guacamole)
        self.config = acceptance.AcceptanceConfig(
            ctfd_url="http://127.0.0.1:%d" % self.ctfd.server_port,
            iris_url="http://127.0.0.1:%d" % self.iris.server_port,
            guacamole_url="http://127.0.0.1:%d" % self.guac.server_port,
            registration_db=self.db, max_wait=2, poll_interval=0.01,
            team_name="Disposable Acceptance")

    def tearDown(self):
        for server, thread in ((self.ctfd, self.ctfd_thread),
                               (self.iris, self.iris_thread),
                               (self.guac, self.guac_thread)):
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
        self.tmp.cleanup()

    def test_registration_to_ready_and_all_three_authentications(self):
        report = acceptance.run_acceptance(self.config, "ROOM-CODE")
        self.assertEqual(report["registration"], "ready")
        self.assertEqual(report["authentication"], {
            "ctfd": "passed", "iris": "passed", "guacamole": "passed"})
        serialized = json.dumps(report)
        for service in ("ctfd", "iris", "guacamole"):
            self.assertNotIn(self.expected[service]["password"], serialized)
        for member in self.expected["ctfd"]["members"]:
            self.assertNotIn(member["password"], serialized)

    def test_platform_mismatch_fails_without_leaking_secret(self):
        access_code = acceptance.reserve_registration(self.config, "ROOM-CODE")
        registration = acceptance.wait_until_ready(self.config, access_code)
        self.guac_handler.reject = True
        secret = registration["credentials"]["guacamole"]["password"]
        with self.assertRaises(acceptance.AcceptanceError) as caught:
            acceptance.verify_guacamole(
                self.config, registration["credentials"]["guacamole"])
        self.assertIn("Guacamole authentication", str(caught.exception))
        self.assertNotIn(secret, str(caught.exception))

    def test_command_line_requires_explicit_disposable_confirmation(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                acceptance.parse_args([
                    "--ctfd-url", "http://ctfd.invalid",
                    "--iris-url", "http://iris.invalid",
                    "--guacamole-url", "http://guac.invalid",
                    "--registration-db", str(self.db),
                ])


if __name__ == "__main__":
    unittest.main()
