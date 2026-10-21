#!/usr/bin/env python3
"""Operator acceptance for one disposable dynamic team registration.

This intentionally exercises the participant-facing registration and login
paths.  Credentials and the private retrieval token remain in memory: they are
never accepted as command-line arguments, printed, or written by this tool.

The created ready registration is not automatically removed.  A ready team
owns live application accounts and desktops, so deleting only its allocator row
would be unsafe.  Run this against a disposable pre-event runtime or reset the
event after acceptance.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import secrets
import ssl
import sys
import time
from http.cookiejar import CookieJar
from typing import Any
import urllib.error
import urllib.parse
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ridge.registration import RegistrationConfig, RegistrationError, RegistrationStore


class AcceptanceError(RuntimeError):
    """A sanitized operator-facing acceptance failure."""


@dataclass(frozen=True)
class AcceptanceConfig:
    ctfd_url: str
    iris_url: str
    guacamole_url: str
    registration_db: Path
    ca_file: Path | None = None
    max_wait: float = 600.0
    poll_interval: float = 2.0
    team_name: str | None = None
    captain_name: str = "Acceptance Operator"


class _InputParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.inputs: dict[str, str] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "input":
            return
        values = {key.lower(): value or "" for key, value in attrs}
        name = values.get("name")
        if name:
            self.inputs[name] = values.get("value", "")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Browser:
    """Cookie-aware HTTP client whose exceptions never include secret URLs."""

    def __init__(self, base: str, ca_file: Path | None = None,
                 *, follow_redirects: bool = True):
        self.base = base.rstrip("/")
        handlers: list[Any] = [urllib.request.HTTPCookieProcessor(CookieJar())]
        if self.base.startswith("https://"):
            try:
                context = (ssl.create_default_context(cafile=str(ca_file))
                           if ca_file else ssl.create_default_context())
            except OSError as exc:
                raise AcceptanceError("TLS trust file could not be loaded") from exc
            handlers.append(urllib.request.HTTPSHandler(context=context))
        if not follow_redirects:
            handlers.append(_NoRedirect())
        self.opener = urllib.request.build_opener(*handlers)

    def request(self, label: str, path: str, *, data: dict[str, str] | None = None,
                method: str | None = None, headers: dict[str, str] | None = None,
                expected: tuple[int, ...] = (200,)) -> tuple[int, str, bytes, Any]:
        body = urllib.parse.urlencode(data).encode("utf-8") if data is not None else None
        request = urllib.request.Request(self.base + path, data=body,
                                         method=method, headers=headers or {})
        try:
            response = self.opener.open(request, timeout=30)
        except urllib.error.HTTPError as exc:
            if exc.code not in expected:
                exc.close()
                raise AcceptanceError(f"{label} returned HTTP {exc.code}") from None
            response = exc
        except (urllib.error.URLError, TimeoutError, OSError):
            raise AcceptanceError(f"{label} could not reach the configured service") from None
        try:
            status = int(response.status)
            final_url = response.geturl()
            payload = response.read()
            response_headers = response.headers
        finally:
            response.close()
        if status not in expected:
            raise AcceptanceError(f"{label} returned HTTP {status}")
        return status, final_url, payload, response_headers


def _input_value(payload: bytes, name: str, label: str) -> str:
    parser = _InputParser()
    parser.feed(payload.decode("utf-8", "replace"))
    value = parser.inputs.get(name, "")
    if not value:
        raise AcceptanceError(f"{label} did not provide its required form token")
    return value


def _generated_team_name() -> str:
    return "Acceptance-%s-%s" % (time.strftime("%H%M%S"), secrets.token_hex(3))


def reserve_registration(config: AcceptanceConfig, enrollment_code: str) -> str:
    browser = Browser(config.ctfd_url, config.ca_file)
    _, _, page, _ = browser.request(
        "registration page", "/silent-ridge/register")
    nonce = _input_value(page, "nonce", "registration page")
    team_name = config.team_name or _generated_team_name()
    _, final_url, _, _ = browser.request(
        "registration submission", "/silent-ridge/register",
        data={"team_name": team_name, "captain_name": config.captain_name,
              "enrollment_code": enrollment_code, "nonce": nonce},
        method="POST")
    path = urllib.parse.urlsplit(final_url).path.rstrip("/")
    match = re.fullmatch(r"/silent-ridge/registration/([^/]+)", path)
    if not match:
        raise AcceptanceError(
            "registration submission did not create a private retrieval link")
    return match.group(1)


def wait_until_ready(config: AcceptanceConfig, access_code: str) -> dict[str, Any]:
    try:
        store = RegistrationStore(str(config.registration_db), RegistrationConfig(),
                                  read_only=True)
    except (OSError, RegistrationError):
        raise AcceptanceError("registration database is unavailable to the operator tool") from None
    deadline = time.monotonic() + config.max_wait
    while True:
        try:
            registration = store.get(access_code, include_private=True)
        except (OSError, RegistrationError):
            raise AcceptanceError("the reserved registration could not be read") from None
        status = registration.get("status")
        if status == "ready":
            credentials = registration.get("credentials") or {}
            required = (credentials.get("ctfd"), credentials.get("iris"),
                        credentials.get("guacamole"))
            if not all(isinstance(value, dict) for value in required):
                raise AcceptanceError("ready registration is missing platform credentials")
            return registration
        if status in ("needs_operator", "cancelled"):
            raise AcceptanceError(
                "registration provisioning requires operator attention before authentication")
        if status not in ("pending", "provisioning"):
            raise AcceptanceError("registration entered an unexpected allocator state")
        if time.monotonic() >= deadline:
            raise AcceptanceError("registration did not become ready before the acceptance timeout")
        time.sleep(config.poll_interval)


def verify_ctfd(config: AcceptanceConfig, credentials: dict[str, Any]) -> None:
    members = credentials.get("members")
    if not isinstance(members, list) or not members:
        raise AcceptanceError("CTFd handout contains no participant seats")
    seat = members[0]
    username, password = seat.get("username"), seat.get("password")
    if not username or not password or str(username).startswith("pending"):
        raise AcceptanceError("CTFd handout contains an inactive participant seat")
    browser = Browser(config.ctfd_url, config.ca_file)
    _, _, page, _ = browser.request("CTFd login page", "/login")
    match = re.search(rb"csrfNonce['\"]?\s*[:=]\s*['\"]([0-9a-f]+)['\"]", page)
    if not match:
        raise AcceptanceError("CTFd login page did not provide its CSRF token")
    _, final_url, _, _ = browser.request(
        "CTFd authentication", "/login",
        data={"name": str(username), "password": str(password),
              "_submit": "Submit", "nonce": match.group(1).decode("ascii")},
        method="POST")
    if urllib.parse.urlsplit(final_url).path.rstrip("/") == "/login":
        raise AcceptanceError("CTFd authentication rejected the generated participant seat")
    _, final_url, page, _ = browser.request(
        "CTFd protected participant page", "/silent-ridge")
    if (urllib.parse.urlsplit(final_url).path.rstrip("/") == "/login"
            or b"Your questions and completed shared history" not in page):
        raise AcceptanceError("CTFd login did not establish a participant session")


def verify_iris(config: AcceptanceConfig, credentials: dict[str, Any]) -> None:
    username, password = credentials.get("username"), credentials.get("password")
    if not username or not password or str(username).startswith("pending"):
        raise AcceptanceError("IRIS handout contains an inactive participant login")
    browser = Browser(config.iris_url, config.ca_file)
    _, _, page, _ = browser.request("IRIS login page", "/login")
    parser = _InputParser()
    parser.feed(page.decode("utf-8", "replace"))
    data = {"username": str(username), "password": str(password)}
    if parser.inputs.get("csrf_token"):
        data["csrf_token"] = parser.inputs["csrf_token"]
    _, final_url, page, _ = browser.request(
        "IRIS authentication", "/login", data=data, method="POST")
    if (urllib.parse.urlsplit(final_url).path.rstrip("/") == "/login"
            or b"logout" not in page.lower()):
        raise AcceptanceError("IRIS authentication rejected the generated team login")
    _, final_url, page, _ = browser.request("IRIS protected dashboard", "/dashboard")
    if (urllib.parse.urlsplit(final_url).path.rstrip("/") == "/login"
            or b"logout" not in page.lower()):
        raise AcceptanceError("IRIS login did not establish a participant session")


def _guacamole_base(value: str) -> str:
    parsed = urllib.parse.urlsplit(value.rstrip("/"))
    path = parsed.path.rstrip("/")
    if not path.endswith("/guacamole"):
        path += "/guacamole"
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))


def verify_guacamole(config: AcceptanceConfig, credentials: dict[str, Any]) -> None:
    username, password = credentials.get("username"), credentials.get("password")
    if not username or not password or str(username).startswith("pending"):
        raise AcceptanceError("Guacamole handout contains an inactive participant login")
    browser = Browser(_guacamole_base(config.guacamole_url), config.ca_file)
    _, _, payload, _ = browser.request(
        "Guacamole authentication", "/api/tokens",
        data={"username": str(username), "password": str(password)}, method="POST")
    try:
        result = json.loads(payload)
    except (TypeError, ValueError):
        raise AcceptanceError("Guacamole authentication returned an invalid response") from None
    # A Guacamole token response is issued only after its authentication
    # provider validates the password.  Do not put that bearer token in a GET
    # query or print it; either would unnecessarily expose a fresh secret.
    if not isinstance(result, dict) or not result.get("authToken"):
        raise AcceptanceError("Guacamole authentication rejected the generated team login")
    if result.get("username") not in (None, username):
        raise AcceptanceError("Guacamole authenticated as an unexpected account")


def run_acceptance(config: AcceptanceConfig, enrollment_code: str) -> dict[str, Any]:
    if not enrollment_code.strip():
        raise AcceptanceError("enrollment code source is empty")
    access_code = reserve_registration(config, enrollment_code.strip())
    registration = wait_until_ready(config, access_code)
    credentials = registration["credentials"]
    verify_ctfd(config, credentials["ctfd"])
    verify_iris(config, credentials["iris"])
    verify_guacamole(config, credentials["guacamole"])
    return {
        "registration": "ready",
        "authentication": {"ctfd": "passed", "iris": "passed",
                           "guacamole": "passed"},
        "disposable_registration_id": int(registration["id"]),
        "team_name": registration["team_name"],
        "reset_required_before_event": True,
    }


def _read_enrollment_code(args: argparse.Namespace) -> str:
    if args.enrollment_code_file:
        try:
            return args.enrollment_code_file.read_text(encoding="utf-8").strip()
        except OSError:
            raise AcceptanceError("enrollment code file could not be read") from None
    value = os.environ.get(args.enrollment_code_env, "")
    if not value:
        raise AcceptanceError(
            f"set {args.enrollment_code_env} or use --enrollment-code-file")
    return value.strip()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ctfd-url", required=True)
    parser.add_argument("--iris-url", required=True)
    parser.add_argument("--guacamole-url", required=True)
    parser.add_argument("--registration-db", required=True, type=Path)
    parser.add_argument("--ca-file", type=Path)
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--enrollment-code-file", type=Path)
    source.add_argument("--enrollment-code-env", default="RIDGE_ENROLLMENT_CODE")
    parser.add_argument("--max-wait", type=float, default=600.0)
    parser.add_argument("--poll-interval", type=float, default=2.0)
    parser.add_argument("--team-name")
    parser.add_argument("--captain-name", default="Acceptance Operator")
    parser.add_argument(
        "--confirm-disposable", action="store_true",
        help="acknowledge that this creates a live team which must be removed by an event reset")
    args = parser.parse_args(argv)
    if not args.confirm_disposable:
        parser.error("--confirm-disposable is required")
    if args.max_wait <= 0 or args.poll_interval <= 0:
        parser.error("wait values must be positive")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config = AcceptanceConfig(
        ctfd_url=args.ctfd_url, iris_url=args.iris_url,
        guacamole_url=args.guacamole_url,
        registration_db=args.registration_db, ca_file=args.ca_file,
        max_wait=args.max_wait, poll_interval=args.poll_interval,
        team_name=args.team_name, captain_name=args.captain_name)
    try:
        report = run_acceptance(config, _read_enrollment_code(args))
    except AcceptanceError as exc:
        print("LIVE REGISTRATION ACCEPTANCE: FAILED", file=sys.stderr)
        print("Reason: " + str(exc), file=sys.stderr)
        return 1
    except Exception:
        # A traceback can contain request objects, URLs, or response bodies.
        # Keep even unexpected failures secret-safe and direct the operator to
        # the component-level tests for deeper diagnosis.
        print("LIVE REGISTRATION ACCEPTANCE: FAILED", file=sys.stderr)
        print("Reason: unexpected internal acceptance-tool error", file=sys.stderr)
        return 1
    print("LIVE REGISTRATION ACCEPTANCE: PASSED")
    print(json.dumps(report, indent=2, sort_keys=True))
    print("Reset this disposable runtime before admitting participants.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
