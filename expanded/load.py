"""F03 load scenario: authenticated participant sessions against the live stack.

Drives N teams x 3 participant sessions through the real CTFd and IRIS HTTP
flows (login, challenge listing, answer attempts, scoreboard/case polling)
with think times, while a sampler records container CPU/RAM, per-endpoint
latency percentiles, and integration-outbox depth. Emits a sanitized JSON
report and a Markdown summary.

This tool measures; it never certifies by itself. Results are labeled with
host facts, and any run whose host does not meet the declared event profile
is stamped "non-certifying". F03 acceptance additionally requires a desktop
usability pass and a ten-team-capable host; see docs/handoff/tasks/F03.md.

Usage:
    PYTHONPATH=. python -m expanded.load --config load-profile.json \
        --duration 600 --output work/f03/run1

Config JSON (secrets stay in the runtime directory; never commit them):
    {
      "teams": 10, "sessions_per_team": 3,
      "ctfd_url": "auto",
      "iris_url": "auto",
      "ca_file": "<runtime>/wazuh-certs/root-ca.pem",
      "credentials": "<runtime>/secrets/team-credentials.json",
      "state_sqlite": "<runtime>/state/state.sqlite",
      "containers": ["silent-ridge-n1-central-ctfd-1", "..."],
      "host": {"ram_gib": 64, "cores": 16},
      "event_profile": {"teams": 10, "min_host_ram_gib": 32}
    }
"""
import argparse
import ipaddress
import json
import os
import queue
import random
import re
import shutil
import ssl
import sqlite3
import statistics
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from http.cookiejar import CookieJar
from pathlib import Path

NONCE = re.compile(r"""csrfNonce['"]?\s*[:=]\s*["']([0-9a-f]+)["']""")
MAX_429_ATTEMPTS = 5
MAX_429_WAIT_S = 10.0
LOGIN_STAGGER_S = 0.5


class LoadError(RuntimeError):
    """A load-run precondition failed; the message names what."""


def percentile(values, q):
    """Nearest-rank percentile; raises on empty input so reports never lie."""
    if not values:
        raise LoadError('no samples for percentile')
    ordered = sorted(values)
    rank = max(1, round(q / 100 * len(ordered)))
    return ordered[min(rank, len(ordered)) - 1]


class TimedClient:
    """urllib opener that records (endpoint, seconds, ok) samples."""

    def __init__(self, base, samples, ca_file=None):
        self.base = base.rstrip('/')
        self.samples = samples
        handlers = [urllib.request.HTTPCookieProcessor(CookieJar())]
        if self.base.startswith('https://'):
            if not ca_file:
                raise LoadError('HTTPS target requires a trusted ca_file')
            try:
                context = ssl.create_default_context(cafile=str(ca_file))
            except OSError as exc:
                raise LoadError(f'Cannot load trusted CA from {ca_file}') from exc
            handlers.append(urllib.request.HTTPSHandler(
                context=context))
        self.opener = urllib.request.build_opener(*handlers)

    def request(self, endpoint, path, data=None, headers=None, method=None,
                require_authenticated=False, required_marker=None):
        url = self.base + path
        body = urllib.parse.urlencode(data).encode() if isinstance(data, dict) else data
        req = urllib.request.Request(url, data=body, headers=headers or {}, method=method)
        start = time.monotonic()
        for attempt in range(MAX_429_ATTEMPTS):
            attempt_start = time.monotonic()
            try:
                with self.opener.open(req, timeout=30) as response:
                    payload = response.read()
                    final_path = urllib.parse.urlsplit(response.geturl()).path.rstrip('/')
                    if require_authenticated and final_path == '/login':
                        raise LoadError(f'{endpoint} ended on the login page after redirects')
                    if required_marker and required_marker.lower() not in payload.lower():
                        raise LoadError(f'{endpoint} did not contain the expected authenticated page')
                    ok = response.status < 400
                    detail = None if ok else f'http {response.status}'
            except urllib.error.HTTPError as exc:
                self.samples.append({'endpoint': endpoint,
                                     'seconds': time.monotonic() - attempt_start,
                                     'ok': False, 'detail': f'http {exc.code}'})
                if exc.code != 429:
                    raise
                if attempt == MAX_429_ATTEMPTS - 1:
                    raise LoadError(f'{endpoint} still rate-limited after '
                                    f'{MAX_429_ATTEMPTS} attempts') from exc
                delay = retry_after_seconds(exc.headers.get('Retry-After'), attempt)
                exc.close()
                time.sleep(delay)
                continue
            except Exception as exc:
                self.samples.append({'endpoint': endpoint, 'seconds': time.monotonic() - start,
                                     'ok': False, 'detail': (str(exc)[:160] if isinstance(exc, LoadError)
                                                           else type(exc).__name__)})
                raise
            sample = {'endpoint': endpoint, 'seconds': time.monotonic() - start, 'ok': ok}
            if detail:
                sample['detail'] = detail
            self.samples.append(sample)
            return payload

    def get_json(self, endpoint, path, headers=None):
        return json.loads(self.request(endpoint, path, headers=headers))


def retry_after_seconds(value, attempt):
    """Bound server-requested 429 wait; invalid headers use exponential backoff."""
    fallback = min(MAX_429_WAIT_S, 0.5 * 2 ** attempt)
    if not value:
        return fallback
    if value.strip().isdigit():
        delay = float(value)
    else:
        try:
            at = parsedate_to_datetime(value)
            if at.tzinfo is None:
                at = at.replace(tzinfo=timezone.utc)
            delay = (at - datetime.now(timezone.utc)).total_seconds()
        except (TypeError, ValueError, OverflowError):
            return fallback
    return min(MAX_429_WAIT_S, max(fallback, delay))


def login_bots(bots, pause=LOGIN_STAGGER_S):
    """Space preflight logins to avoid a burst before the timed run starts."""
    for index, bot in enumerate(bots):
        if index:
            time.sleep(pause)
        try:
            bot.login()
        except urllib.error.HTTPError:
            raise
        except urllib.error.URLError as exc:
            raise LoadError(f'{bot.client.base} login preflight failed; check the URL '
                            'against runtime/local.json bind_ip and published port') from exc


def resolve_target_urls(config):
    """Resolve `auto` URLs from the same runtime that supplied participant logins."""
    result = dict(config)
    requested = [service for service in ('ctfd', 'iris')
                 if result[service + '_url'] == 'auto']
    if not requested:
        return result
    local_path = Path(config['credentials']).parent.parent / 'local.json'
    try:
        local = json.loads(local_path.read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        raise LoadError(f'Cannot derive participant URLs from {local_path}') from exc
    bind = local.get('bind_ip') or '127.0.0.1'
    try:
        address = ipaddress.IPv4Address(bind)
    except (ipaddress.AddressValueError, TypeError) as exc:
        raise LoadError(f'{local_path} bind_ip must be an IPv4 address') from exc
    if address.is_unspecified:
        raise LoadError(f'{local_path} bind_ip is a wildcard, not a participant URL')
    ports = local.get('ports') or {}
    if not isinstance(ports, dict):
        raise LoadError(f'{local_path} ports must be an object')
    for service, default_port in (('ctfd', 8083), ('iris', 8081)):
        if service not in requested:
            continue
        port = ports.get(service, default_port)
        if not isinstance(port, int) or isinstance(port, bool) or not 1 <= port <= 65535:
            raise LoadError(f'{local_path} ports.{service} must be a TCP port')
        result[service + '_url'] = f'https://{bind}:{port}'
    return result


def resolve_iris_case_path(config):
    """Resolve the seeded IRIS case route from the same runtime as credentials."""
    explicit = config.get('iris_case_path')
    if explicit:
        return explicit
    runtime = Path(config['credentials']).parent.parent
    inventory_path = runtime / 'inventories' / 'iris-inventory.json'
    try:
        inventory = json.loads(inventory_path.read_text(encoding='utf-8'))
        case_id = inventory['inventory']['case']['id']
        if isinstance(case_id, bool) or int(case_id) <= 0:
            raise ValueError('case id must be positive')
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        raise LoadError(f'Cannot resolve IRIS case from {inventory_path}') from exc
    return '/case/tasks?cid=' + str(int(case_id))

PAGE_NONCE = re.compile(rb'name="nonce"\s+value="([^"]+)"')
PAGE_QUESTION = re.compile(rb'name="question"\s+value="([^"]+)"')


class CtfdBot:
    """One CTFd participant on the Silent Ridge question queue.

    The stock CTFd challenge API is deliberately closed to participants
    (integrations/ctfd_silent_ridge aborts 403); the real flow is
    GET /silent-ridge, the 5 s /silent-ridge/status poll, GET
    /api/v1/scoreboard, and POST /silent-ridge answers.
    """

    def __init__(self, base, name, password, samples, ca_file=None):
        self.client = TimedClient(base, samples, ca_file)
        self.name, self.password = name, password

    def login(self):
        page = self.client.request('ctfd:login-page', '/login')
        match = NONCE.search(page.decode('utf-8', 'replace'))
        if not match:
            raise LoadError('CTFd login page without csrfNonce')
        self.nonce = match.group(1)
        self.client.request('ctfd:login', '/login',
                            data={'name': self.name, 'password': self.password,
                                  '_submit': 'Submit', 'nonce': self.nonce},
                            require_authenticated=True)

    def act(self, rng):
        page = self.client.request('ctfd:questions', '/silent-ridge',
                                   require_authenticated=True,
                                   required_marker=b'name="question"')
        nonces = PAGE_NONCE.findall(page)
        questions = PAGE_QUESTION.findall(page)
        roll = rng.random()
        if roll < 0.3:
            self.client.request('ctfd:status', '/silent-ridge/status')
        elif roll < 0.5:
            self.client.get_json('ctfd:scoreboard', '/api/v1/scoreboard')
        if nonces and questions and rng.random() < 0.35:
            # Attempts use a deliberately wrong synthetic answer: we measure
            # the write path, we never farm real points.
            self.client.request('ctfd:answer', '/silent-ridge',
                                data={'nonce': nonces[0].decode(),
                                      'question': rng.choice(questions).decode(),
                                      'answer': 'load-test-probe'},
                                method='POST')


class IrisBot:
    """One IRIS case participant: login and poll case/activity views."""

    def __init__(self, base, login_name, password, samples, ca_file=None,
                 case_path='/case/tasks'):
        self.client = TimedClient(base, samples, ca_file)
        self.login_name, self.password = login_name, password
        self.case_path = case_path

    def login(self):
        page = self.client.request('iris:login-page', '/login')
        csrf = re.search(rb'name="csrf_token"[^>]*value="([^"]+)"', page)
        data = {'username': self.login_name, 'password': self.password}
        if csrf:
            data['csrf_token'] = csrf.group(1).decode()
        self.client.request('iris:login', '/login', data=data,
                            require_authenticated=True, required_marker=b'Logout')

    def act(self, rng):
        self.client.request('iris:dashboard', '/dashboard',
                            require_authenticated=True, required_marker=b'Logout')
        if rng.random() < 0.5:
            self.client.request('iris:case', self.case_path,
                                require_authenticated=True)


def outbox_depth(state_sqlite):
    """Pending integration-outbox rows; 0 when the table is absent or drained.

    Never opens the live database: SQLite locks do not cross Docker Desktop
    bind mounts reliably, and a host-side reader stalls the in-container
    writer (observed as integration 503s). Byte-copy first; a mid-write copy
    may fail to read, which reports None rather than touching the writer.
    """
    for query in ("SELECT COUNT(*) FROM outbox WHERE delivered IS NULL",
                  'SELECT COUNT(*) FROM outbox'):
        try:
            with tempfile.NamedTemporaryFile(suffix='.sqlite', delete=False) as tmp:
                shutil.copyfile(state_sqlite, tmp.name)
            try:
                db = sqlite3.connect(f'file:{tmp.name}?mode=ro', uri=True, timeout=1)
                try:
                    return db.execute(query).fetchone()[0]
                finally:
                    db.close()
            finally:
                os.unlink(tmp.name)
        except (OSError, sqlite3.OperationalError, sqlite3.DatabaseError):
            continue
    return None


def sample_containers(containers, stop, out, interval=5.0):
    while not stop.is_set():
        try:
            raw = subprocess.check_output(
                ['docker', 'stats', '--no-stream', '--format', '{{json .}}', *containers],
                text=True, timeout=30)
            out.put({'timestamp': time.time(),
                     'containers': [json.loads(line) for line in raw.splitlines()]})
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            out.put({'timestamp': time.time(), 'error': str(exc)})
        stop.wait(interval)


def mib(usage):
    match = re.match(r'([\d.]+)\s*([GMTK]i?B)', usage or '')
    if not match:
        return 0.0
    value = float(match.group(1))
    return value * {'GiB': 1024, 'MiB': 1, 'KiB': 1 / 1024,
                    'GB': 1000, 'MB': 1000 / 1.048576, 'B': 0}.get(match.group(2), 0)


def host_memory():
    """Read physical host RAM, including Docker/WSL overhead on Windows."""
    gib = 1024 ** 3
    if os.name == 'nt':
        import ctypes

        class MemoryStatus(ctypes.Structure):
            _fields_ = [('length', ctypes.c_ulong), ('load', ctypes.c_ulong),
                        ('total', ctypes.c_ulonglong), ('available', ctypes.c_ulonglong),
                        ('total_page', ctypes.c_ulonglong), ('available_page', ctypes.c_ulonglong),
                        ('total_virtual', ctypes.c_ulonglong), ('available_virtual', ctypes.c_ulonglong),
                        ('available_extended', ctypes.c_ulonglong)]

        status = MemoryStatus()
        status.length = ctypes.sizeof(status)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return None
        return {'total_gib': status.total / gib, 'available_gib': status.available / gib}
    try:
        values = {}
        for line in Path('/proc/meminfo').read_text(encoding='ascii').splitlines():
            key, _, value = line.partition(':')
            if key in ('MemTotal', 'MemAvailable'):
                values[key] = int(value.strip().split()[0]) * 1024 / gib
        return {'total_gib': values['MemTotal'], 'available_gib': values['MemAvailable']}
    except (OSError, ValueError, KeyError):
        return None


def build_report(config, samples, container_samples, outbox_samples, duration,
                 host_samples=None):
    endpoints = {}
    for sample in samples:
        endpoints.setdefault(sample['endpoint'], []).append(sample)
    latency = {}
    for endpoint, rows in sorted(endpoints.items()):
        times = [r['seconds'] for r in rows]
        failures = sum(1 for r in rows if not r['ok'])
        latency[endpoint] = {'count': len(rows), 'failures': failures,
                             'p50_s': round(percentile(times, 50), 3),
                             'p95_s': round(percentile(times, 95), 3)}
    peaks = {}
    for snap in container_samples:
        for container in snap.get('containers', []):
            name = container.get('Name', '?')
            peaks[name] = max(peaks.get(name, 0.0), mib(container.get('MemUsage', '').split('/')[0].strip()))
    used_gib = sum(peaks.values()) / 1024
    host_samples = host_samples or []
    valid_host = (bool(host_samples) and all(sample is not None for sample in host_samples))
    host_ram = min(sample['total_gib'] for sample in host_samples) if valid_host else None
    available_min = min(sample['available_gib'] for sample in host_samples) if valid_host else None
    reserve = available_min / host_ram if host_ram else None
    profile = config.get('event_profile', {})
    certifying = (profile.get('teams') == config.get('teams')
                  and profile.get('sessions_per_team', 3) == config.get('sessions_per_team')
                  and duration >= 1800 and reserve is not None and reserve >= 0.2
                  and bool(samples) and all(sample['ok'] for sample in samples)
                  and bool(container_samples)
                  and all(sample.get('containers') for sample in container_samples)
                  and sum(sample['endpoint'] == 'ctfd:login' for sample in samples)
                      >= config['teams'] * config['sessions_per_team']
                  and sum(sample['endpoint'] == 'iris:login' for sample in samples)
                      >= config['teams']
                  and {'ctfd:questions', 'iris:dashboard'}
                      <= {sample['endpoint'] for sample in samples})
    return {
        'schema': 2, 'duration_s': duration,
        'teams': config['teams'], 'sessions': config['teams'] * config['sessions_per_team'],
        'latency': latency, 'container_peak_mib': {k: round(v, 1) for k, v in sorted(peaks.items())},
        'peak_working_set_gib': round(used_gib, 2),
        'host_ram_gib': round(host_ram, 2) if host_ram is not None else None,
        'host_available_min_gib': round(available_min, 2) if available_min is not None else None,
        'declared_host_ram_gib': config.get('host', {}).get('ram_gib'),
        'measured_reserve_pct': round(reserve * 100, 1) if reserve is not None else None,
        'outbox_depth_minmax': ([min(outbox_samples), max(outbox_samples)]
                                if outbox_samples and all(v is not None for v in outbox_samples)
                                else None),
        'certifying': certifying,
        'label': ('F03 capacity evidence'
                  if certifying else
                  'NON-CERTIFYING run — check duration, requests, container samples and host reserve'),
    }


def markdown(report):
    lines = ['# F03 load run — ' + report['label'], '',
             f"- teams/sessions: {report['teams']}/{report['sessions']}, duration {report['duration_s']}s",
             f"- container peak working set: {report['peak_working_set_gib']} GiB",
             f"- observed host RAM: {report['host_ram_gib']} GiB; minimum available: "
             f"{report['host_available_min_gib']} GiB ({report['measured_reserve_pct']}% reserve)",
             f"- outbox depth min/max: {report['outbox_depth_minmax']}", '',
             '| endpoint | count | failures | p50 s | p95 s |', '|---|---|---|---|---|']
    for endpoint, row in report['latency'].items():
        lines.append(f"| {endpoint} | {row['count']} | {row['failures']} | {row['p50_s']} | {row['p95_s']} |")
    lines += ['', '| container | peak MiB |', '|---|---|']
    for name, peak in report['container_peak_mib'].items():
        lines.append(f'| {name} | {peak} |')
    return '\n'.join(lines) + '\n'


def run(config, duration, output):
    output = Path(output)
    if output.exists():
        raise LoadError('Choose a new output directory; runs are never overwritten')
    config = resolve_target_urls(config)
    ca_file = config.get('ca_file')
    creds = json.loads(Path(config['credentials']).read_text(encoding='utf-8'))
    samples, container_q, outbox_samples = [], queue.Queue(), []
    bots = []
    for team in sorted(creds['teams'])[: config['teams']]:
        entry = creds['teams'][team]
        accounts = entry.get('accounts', {})
        for seat in range(1, config['sessions_per_team'] + 1):
            user = f'{team}-p{seat:02d}'
            password = accounts.get(user)
            if password:
                bots.append(CtfdBot(config['ctfd_url'], user, password, samples, ca_file))
        bots.append(IrisBot(config['iris_url'], entry['iris_login'],
                            entry['iris_password'], samples, ca_file,
                            resolve_iris_case_path(config)))
    if not bots:
        raise LoadError('No credentials matched the requested team count')
    login_bots(bots)  # fail fast on auth problems before the clock starts
    host_samples = [host_memory()]
    stop = threading.Event()
    sampler = threading.Thread(target=sample_containers,
                               args=(config.get('containers', []), stop, container_q),
                               daemon=True)
    sampler.start()
    rng = random.Random(20261026)
    deadline = time.monotonic() + duration
    threads = []
    def loop(bot):
        local = random.Random(rng.random())
        while time.monotonic() < deadline:
            try:
                bot.act(local)
            except Exception:
                pass  # failures are recorded in samples; the run continues
            time.sleep(local.uniform(2, 8))
    for bot in bots:
        thread = threading.Thread(target=loop, args=(bot,), daemon=True)
        thread.start()
        threads.append(thread)
    state_sqlite = config.get('state_sqlite')
    while time.monotonic() < deadline:
        host_samples.append(host_memory())
        if state_sqlite:
            outbox_samples.append(outbox_depth(state_sqlite))
        time.sleep(5)
    stop.set()
    for thread in threads:
        thread.join(timeout=10)
    sampler.join(timeout=10)
    container_samples = []
    while not container_q.empty():
        container_samples.append(container_q.get())
    report = build_report(config, samples, container_samples, outbox_samples, duration,
                          host_samples)
    output.mkdir(parents=True)
    (output / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    (output / 'report.md').write_text(markdown(report), encoding='utf-8')
    (output / 'samples.json').write_text(json.dumps(samples) + '\n', encoding='utf-8')
    return report


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', type=Path, required=True)
    p.add_argument('--duration', type=float, default=600)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args(argv)
    config = json.loads(args.config.read_text(encoding='utf-8'))
    for key in ('teams', 'sessions_per_team', 'ctfd_url', 'iris_url', 'credentials'):
        if key not in config:
            raise LoadError('config missing: ' + key)
    if args.duration < 30:
        raise LoadError('runs shorter than 30s measure nothing useful')
    report = run(config, args.duration, args.output)
    print(json.dumps({'label': report['label'], 'reserve_pct': report['measured_reserve_pct'],
                      'peak_gib': report['peak_working_set_gib']}, indent=2))


if __name__ == '__main__':
    main()
