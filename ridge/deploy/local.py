"""One-command local lifecycle (N4): up to PROVISIONED_PAUSED, gated start,
truthful status/pause, down and logical backup.

Every Docker interaction is an argv list through a ``runner`` (see
``ridge.docker_provider.SubprocessRunner``); host-side operations that need
real cryptography, the ticket author or the Wazuh HTTPS API go through
:class:`HostOps` so tests can drive a fully scripted fake. Nothing here ever
resets existing state: each stage probes first, a verified resource that no
longer probes healthy is an actionable error, and missing private inputs
(secrets, assets, certificates) fail with the exact path and remedy.

The runtime directory is private and gitignored. Layout::

    <runtime>/
      deploy-journal.sqlite     deployment journal (see ridge.deploy.journal)
      local.json                host-specific asset paths and ports (not fingerprinted)
      secrets/                  generated once, preserved on every retry
      env/*.env                 rendered Compose environment (secret file refs + app env)
      specs/*.json              bootstrap/provisioning specs (contain passwords; private)
      guac-init/                001-initdb.sql (from the guacamole image) + 002-provision.sql
      wazuh-certs/              local CA + node certs (and optional public edge certs)
      state/state.sqlite        exercise core state (paused by default)
      state/config.json         controller config materialized from discovered identities
      inventories/              IRIS/CTFd provisioning inventories (no passwords)
      discovered.json           application IDs discovered from live inventories
      backups/<utc>/            logical backups with SHA256 manifest
"""
from __future__ import annotations

import csv
import ctypes
import getpass
import hashlib
import ipaddress
import json
import logging
import os
import re
import signal
import shutil
import sqlite3
import stat
import subprocess
import sys
import time
import threading
import xml.etree.ElementTree as ET
from ctypes import wintypes
from datetime import datetime, timezone
from pathlib import Path

from ridge.deploy import config as deploy_config
from ridge.deploy.journal import Journal, JournalError
from ridge.docker_provider import CommandError

ROOT = Path(__file__).resolve().parents[2]
COMPOSE_DIR = ROOT / 'deployment' / 'expanded'
WAZUH_DIR = COMPOSE_DIR / 'wazuh'

COMPOSE_FILES = {
    'central': COMPOSE_DIR / 'compose.central.yaml',
    'guacamole': COMPOSE_DIR / 'compose.guacamole.yaml',
    'desktops': COMPOSE_DIR / 'compose.desktops.yaml',
    'integration': COMPOSE_DIR / 'compose.integration.yaml',
    'wazuh': WAZUH_DIR / 'compose.wazuh.yaml',
}

# Services brought up per stage. iris-db-init is a one-shot initializer.
INFRA_SERVICES = {
    'central': ['iris-db', 'iris-db-init', 'ctfd-db', 'ctfd-cache', 'rabbitmq'],
    'wazuh': ['wazuh-indexer', 'wazuh-manager'],
    'guacamole': ['database', 'guacd'],
}
INFRA_ONE_SHOT = {'central': ('iris-db-init',)}
APP_SERVICES = {
    'wazuh': ['wazuh-dashboard'],
    'guacamole': ['guacamole'],
    # participant-tls uses static proxy_pass targets when public TLS is
    # terminated here. Start the other participant-facing upstreams first;
    # these are separate Compose projects, so cross-file depends_on cannot
    # express this cold-start ordering.
    'central': ['iris', 'iris-worker', 'ctfd', 'participant-tls'],
}
IMAGE_COMPONENTS = ('iris', 'ctfd', 'integration', 'desktop')


def _windows_process_exists(pid):
    """Return True only when tasklist reports an exact process row for *pid*.

    ``tasklist`` exits zero when its filter matches no process, so its return
    code alone cannot validate a saved worker PID.
    """
    result = subprocess.run(
        ['tasklist', '/FI', 'PID eq %d' % pid, '/FO', 'CSV', '/NH'],
        capture_output=True, text=True, timeout=5)
    if result.returncode != 0:
        return False
    for row in csv.reader(result.stdout.splitlines()):
        if len(row) > 1 and row[1].strip() == str(pid):
            return True
    return False


def _process_exists(pid):
    if os.name == 'nt':
        return _windows_process_exists(pid)
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def _normalize_process_identity(document):
    """Return the stable fields used to bind a saved PID to one OS process."""
    if not isinstance(document, dict):
        return None
    creation_time = str(document.get('creation_time', '')).strip()
    executable = str(document.get('executable', '')).strip()
    if not creation_time or not executable:
        return None
    normalized = {
        'creation_time': creation_time,
        'executable': os.path.normcase(executable),
    }
    command_line = str(document.get('command_line', '')).strip()
    if command_line:
        normalized['command_line'] = command_line
    return normalized


def _windows_process_identity(pid, api=None):
    """Read kernel creation time and executable path for one Windows PID.

    A PID and registration token can both survive in private files across a
    reboot while Windows reuses the PID.  The limited-information process APIs
    supply OS-owned identity without relying on CIM/WMI availability.
    """
    kernel32 = api
    try:
        if kernel32 is None:
            kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.GetProcessTimes.argtypes = [
            wintypes.HANDLE, ctypes.POINTER(wintypes.FILETIME),
            ctypes.POINTER(wintypes.FILETIME), ctypes.POINTER(wintypes.FILETIME),
            ctypes.POINTER(wintypes.FILETIME)]
        kernel32.GetProcessTimes.restype = wintypes.BOOL
        kernel32.QueryFullProcessImageNameW.argtypes = [
            wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
            ctypes.POINTER(wintypes.DWORD)]
        kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL

        handle = kernel32.OpenProcess(0x1000, False, int(pid))
        if not handle:
            return None
        try:
            creation = wintypes.FILETIME()
            exit_time = wintypes.FILETIME()
            kernel = wintypes.FILETIME()
            user = wintypes.FILETIME()
            if not kernel32.GetProcessTimes(
                    handle, ctypes.byref(creation), ctypes.byref(exit_time),
                    ctypes.byref(kernel), ctypes.byref(user)):
                return None
            size = wintypes.DWORD(32768)
            executable = ctypes.create_unicode_buffer(size.value)
            if not kernel32.QueryFullProcessImageNameW(
                    handle, 0, executable, ctypes.byref(size)):
                return None
            ticks = (int(creation.dwHighDateTime) << 32) | int(creation.dwLowDateTime)
            return _normalize_process_identity({
                'creation_time': str(ticks),
                'executable': executable.value,
            })
        finally:
            kernel32.CloseHandle(handle)
    except (OSError, ValueError, AttributeError):
        return None


def _posix_process_identity(pid):
    """Read a Linux process identity tied to the current kernel boot."""
    process = Path('/proc') / str(int(pid))
    try:
        stat_text = (process / 'stat').read_text(encoding='utf-8')
        end = stat_text.rfind(')')
        if end < 0:
            return None
        fields = stat_text[end + 2:].split()
        # fields starts with proc(5) field 3; starttime is field 22.
        start_ticks = fields[19]
        boot_id = Path('/proc/sys/kernel/random/boot_id').read_text(
            encoding='ascii').strip()
        executable = str((process / 'exe').resolve(strict=True))
        command_line = (process / 'cmdline').read_bytes().replace(b'\0', b' ').decode(
            'utf-8', errors='surrogateescape').strip()
        return _normalize_process_identity({
            'creation_time': '%s:%s' % (boot_id, start_ticks),
            'executable': executable,
            'command_line': command_line,
        })
    except (OSError, ValueError, IndexError):
        return None


def _process_identity(pid):
    if os.name == 'nt':
        return _windows_process_identity(pid)
    return _posix_process_identity(pid)


def _secure_private(path):
    """Enforce an owner/SYSTEM-only host ACL on an existing runtime file."""
    path = Path(path)
    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    if os.name == 'nt':
        user = getpass.getuser()
        result = subprocess.run(
            ['icacls', str(path), '/inheritance:r', '/grant:r',
             '%s:(F)' % user, '*S-1-5-18:(F)'],
            capture_output=True, text=True, timeout=15)
        if result.returncode != 0:
            raise LifecycleError('could not secure private runtime file %s: %s'
                                 % (path, result.stderr.strip()[:200]))
    return path


def _write_private(path, value):
    """Write a runtime secret and enforce an owner/SYSTEM-only host ACL."""
    path = Path(path)
    path.write_text(value, encoding='utf-8')
    return _secure_private(path)

# Upstream Wazuh single-node config files that compose.wazuh.yaml bind-mounts
# out of the wazuh_config asset, with the format each must parse as. Issue #187:
# a missing or malformed tree must fail preflight with its remedy, not surface
# late as an indexer/dashboard crash inside the Wazuh compose project.
WAZUH_CONFIG_ASSET_FILES = (
    ('wazuh_indexer/wazuh.indexer.yml', 'yaml'),
    ('wazuh_indexer/internal_users.yml', 'yaml'),
    ('wazuh_cluster/wazuh_manager.conf', 'xml'),
    ('wazuh_dashboard/opensearch_dashboards.yml', 'yaml'),
)

try:  # asset validation uses PyYAML when the host has it (issue #187)
    import yaml as _yaml
except ImportError:  # pragma: no cover - hosts without PyYAML get weaker checks
    _yaml = None

SECRET_FILES = (
    'postgres-password', 'iris-secret-key', 'iris-password-salt', 'iris-admin-password',
    'ctfd-secret-key', 'mariadb-root-password', 'mariadb-ctfd-password',
    'ridge-iris-bridge', 'ridge-ctfd-bridge',
    'wazuh_admin', 'wazuh_writer', 'wazuh_reader', 'guac-db-password',
)
WAZUH_API_SECRET = 'wazuh-api-password'
WAZUH_PARTICIPANT_DEFAULT_INDEX = 'silent-ridge-timed'


def _set_unique_wazuh_option(source, section_name, option_name, value):
    """Replace one direct option in one Wazuh section without reformatting XML."""
    section_tag = re.escape(section_name)
    section_pattern = re.compile(
        r'(<%s(?:\s[^>]*)?>)(.*?)(</%s\s*>)' % (section_tag, section_tag),
        flags=re.IGNORECASE | re.DOTALL,
    )
    sections = list(section_pattern.finditer(source))
    if len(sections) != 1:
        raise LifecycleError('vendored Wazuh manager config must contain exactly one '
                             '<%s> section' % section_name)
    section = sections[0]
    option_tag = re.escape(option_name)
    option_pattern = re.compile(
        r'(<%s(?:\s[^>]*)?>\s*)([^<]*?)(\s*</%s\s*>)' % (option_tag, option_tag),
        flags=re.IGNORECASE,
    )
    body = section.group(2)
    replaced_body, count = option_pattern.subn(
        lambda match: match.group(1) + value + match.group(3), body,
    )
    if count != 1:
        raise LifecycleError('vendored Wazuh <%s> section must contain exactly one '
                             'direct <%s> option' % (section_name, option_name))
    replacement = section.group(1) + replaced_body + section.group(3)
    return source[:section.start()] + replacement + source[section.end():]


def offline_wazuh_config(source):
    """Render the manager config for the bundle's deliberately offline runtime."""
    try:
        root = ET.fromstring('<ridge>' + source + '</ridge>')
    except ET.ParseError as exc:
        raise LifecycleError('vendored Wazuh manager config is invalid XML: %s' % exc)
    globals_ = root.findall('.//global')
    if not globals_:
        raise LifecycleError('vendored Wazuh manager config has no <global> section')
    updates = [entry for section in globals_ for entry in section.findall('update_check')]
    if updates:
        rendered, count = re.subn(r'(<update_check>\s*)([^<]*?)(\s*</update_check>)',
                                  lambda match: match.group(1) + 'no' + match.group(3),
                                  source, flags=re.IGNORECASE)
        if count != len(updates):
            raise LifecycleError('vendored Wazuh update_check entries are ambiguous')
    else:
        rendered, count = re.subn(r'(<global(?:\s[^>]*)?>)',
                                  r'\1\n    <update_check>no</update_check>', source, count=1)
        if count != 1:
            raise LifecycleError('vendored Wazuh manager config has no usable <global> tag')
    # The exercise consumes a separately provisioned historical index through
    # Filebeat and the dashboard. It has no monitored endpoint agents and does
    # not ship an offline CTI feed. Disable the manager's unrelated vulnerability
    # inventory path and its indexer connector rather than leaving retry loops
    # that require Internet access, manager keystore credentials, and client
    # certificates. This does not change Filebeat's independent output.
    rendered = _set_unique_wazuh_option(
        rendered, 'vulnerability-detection', 'enabled', 'no')
    rendered = _set_unique_wazuh_option(
        rendered, 'vulnerability-detection', 'index-status', 'no')
    rendered = _set_unique_wazuh_option(rendered, 'indexer', 'enabled', 'no')
    verified = ET.fromstring('<ridge>' + rendered + '</ridge>')
    if any((entry.text or '').strip().lower() != 'no'
           for section in verified.findall('.//global')
           for entry in section.findall('update_check')):
        raise LifecycleError('Wazuh update check must be disabled for the offline kit')
    expected_disabled = (
        ('vulnerability-detection', 'enabled'),
        ('vulnerability-detection', 'index-status'),
        ('indexer', 'enabled'),
    )
    for section_name, option_name in expected_disabled:
        sections = verified.findall('.//' + section_name)
        options = [entry for section in sections for entry in section.findall(option_name)]
        if (len(sections) != 1 or len(options) != 1
                or (options[0].text or '').strip().lower() != 'no'):
            raise LifecycleError('Wazuh <%s>/<%s> must be uniquely disabled for the '
                                 'offline kit' % (section_name, option_name))
    return rendered


def offline_wazuh_dashboard_config(source):
    """Pin the participant's prepared Discover view without granting UI writes.

    Wazuh calls ``uiSettings.set('defaultIndex', ...)`` when this setting is
    absent.  A participant must not be able to write the shared dashboard
    tenant, so that otherwise-cosmetic first-login initialization correctly
    returns 403 and produces an alarming toast.  An override is immutable from
    the browser and prevents the write while retaining the read-only role.
    """
    if _yaml is not None:
        try:
            parsed = _yaml.safe_load(source)
        except Exception as exc:
            raise LifecycleError('vendored Wazuh dashboard config is invalid YAML: %s' % exc)
        if not isinstance(parsed, dict):
            raise LifecycleError('vendored Wazuh dashboard config must be a YAML mapping')
    pattern = re.compile(
        r'^[ \t]*uiSettings\.overrides\.defaultIndex[ \t]*:[^\r\n]*$',
        flags=re.MULTILINE,
    )
    setting = ('uiSettings.overrides.defaultIndex: '
               + WAZUH_PARTICIPANT_DEFAULT_INDEX)
    matches = list(pattern.finditer(source))
    if len(matches) > 1:
        raise LifecycleError('vendored Wazuh dashboard config has duplicate defaultIndex overrides')
    if matches:
        rendered = pattern.sub(setting, source, count=1)
    else:
        rendered = source.rstrip('\r\n') + '\n' + setting + '\n'
    if _yaml is not None:
        verified = _yaml.safe_load(rendered)
        if verified.get('uiSettings.overrides.defaultIndex') != WAZUH_PARTICIPANT_DEFAULT_INDEX:
            raise LifecycleError('Wazuh dashboard defaultIndex override was not rendered')
    return rendered


def render_indexer_admin(source, password_hash, extra_users=()):
    """Render the private indexer user file with the generated admin hash.

    The Wazuh REST API rejects classroom passwords such as ``team1`` as weak,
    even though the event intentionally uses those memorable values.  Fresh
    runtimes therefore seed those users with bcrypt hashes before the indexer
    starts; the API is still used for roles, mappings, and any strong account.
    """
    if not re.fullmatch(r'\$2[aby]\$12\$[./A-Za-z0-9]{53}', password_hash):
        raise LifecycleError('indexer hash tool returned an invalid bcrypt hash')
    lines = source.splitlines(keepends=True)
    admin_line = next((i for i, line in enumerate(lines) if line.strip() == 'admin:'
                       and line.startswith('admin:')), None)
    if admin_line is None:
        raise LifecycleError('vendored internal_users.yml has no admin user')
    hashes = []
    for i in range(admin_line + 1, len(lines)):
        if lines[i].strip() and not lines[i][0].isspace():
            break
        if re.match(r'^[ \t]+hash:', lines[i]):
            hashes.append(i)
    if len(hashes) != 1:
        raise LifecycleError('vendored admin entry must have exactly one hash')
    old = lines[hashes[0]]
    newline = '\r\n' if old.endswith('\r\n') else '\n'
    lines[hashes[0]] = '  hash: "' + password_hash + '"' + newline
    rendered = ''.join(lines)
    for username, user_hash, role in extra_users:
        if not re.fullmatch(r'[A-Za-z0-9_-]+', username):
            raise LifecycleError('invalid indexer username %r' % username)
        if not re.fullmatch(r'\$2[aby]\$12\$[./A-Za-z0-9]{53}', user_hash):
            raise LifecycleError('indexer hash tool returned an invalid bcrypt hash')
        if not re.fullmatch(r'[A-Za-z0-9_-]+', role):
            raise LifecycleError('invalid indexer backend role %r' % role)
        if re.search(r'^' + re.escape(username) + r':\s*$', rendered, re.MULTILINE):
            continue
        rendered += ('\n%s:\n  hash: "%s"\n  reserved: false\n'
                     '  backend_roles:\n  - "%s"\n  description: "Silent Ridge event account"\n'
                     % (username, user_hash, role))
    return rendered


def _derive_discovered(iris_inventory, ctfd_inventory):
    """Flatten the IRIS/CTFd bootstrap inventories into the discovered-ID record.

    Real shapes (N1):
      iris:  {case:{id,name}, statuses:{open,closed}, service_user:{id,login},
              identities:{team:{id,login,name}}}
      ctfd:  {teams:{team:{id,name}}, users:{...}}
    """
    discovered = {
        'case': iris_inventory['case']['id'],
        'service_user': iris_inventory['service_user']['id'],
        'open_status': iris_inventory['statuses']['open'],
        'closed_status': iris_inventory['statuses']['closed'],
        'teams': {team: {'iris_id': row['id']}
                  for team, row in iris_inventory['identities'].items()},
    }
    for team, row in ctfd_inventory.get('teams', {}).items():
        discovered['teams'].setdefault(team, {})['ctfd_id'] = row['id']
    return discovered


class LifecycleError(RuntimeError):
    """An actionable lifecycle failure; the message names the cause and remedy."""


class HostOps:
    """Real host operations. Tests subclass or replace with a scripted fake."""

    def randhex(self, count=24):
        import secrets
        return secrets.token_hex(count)

    def http_json(self, method, url, headers=None, body=None, timeout=10, ca_file=None):
        from urllib.request import Request, urlopen
        from urllib.error import HTTPError
        import ssl
        data = json.dumps(body).encode() if body is not None else None
        request = Request(url, data=data, method=method,
                          headers={'Content-Type': 'application/json', **(headers or {})})
        try:
            context = ssl.create_default_context(cafile=str(ca_file)) if ca_file else None
            with urlopen(request, timeout=timeout, context=context) as response:
                text = response.read()
                try:
                    return response.status, json.loads(text or b'{}')
                except ValueError:
                    return response.status, {}
        except HTTPError as exc:
            try:
                return exc.code, json.loads(exc.read() or b'{}')
            except Exception:
                return exc.code, {}

    def wazuh_request(self, method, url, ca_file, credential, body=None, timeout=15, headers=None):
        import base64
        from urllib.request import Request, urlopen
        from urllib.error import HTTPError
        from ridge.wazuh_provision import ca_context
        data = json.dumps(body).encode() if body is not None else None
        request = Request(url, data=data, method=method,
                          headers={'Content-Type': 'application/json',
                                   'Authorization': 'Basic ' + base64.b64encode(credential.encode()).decode(),
                                   **(headers or {})})
        try:
            with urlopen(request, timeout=timeout, context=ca_context(ca_file)) as response:
                text = response.read().decode()
                return response.status, json.loads(text) if text else {}
        except HTTPError as exc:
            text = exc.read().decode()
            try:
                return exc.code, json.loads(text)
            except ValueError:
                return exc.code, {'error': text[:300]}

    def author_tickets(self, config):
        from expanded.author import build
        return build(config)

    def state(self, path):
        from ridge.state import State
        return State(path)

    def preflight(self, state, config, env):
        import os
        from ridge.preflight import check
        saved = {key: os.environ.get(key) for key in env}
        os.environ.update(env)
        try:
            return check(state, config)
        finally:
            for key, value in saved.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    def index_telemetry(self, records, indexer_url, index_name, credential_file, ca_file):
        """Bulk-index records through the real release path (stable IDs, no duplicates)."""
        import os
        from ridge.evidence_release import index as index_records
        env = {'WAZUH_INDEXER_URL': indexer_url, 'WAZUH_INDEX': index_name,
               'WAZUH_INDEX_CREDENTIAL_FILE': str(credential_file),
               'SSL_CERT_FILE': str(ca_file)}
        saved = {key: os.environ.get(key) for key in env}
        os.environ.update(env)
        try:
            index_records(records)
        finally:
            for key, value in saved.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


def _utcnow():
    return datetime.now(timezone.utc)


def _state_watermark(path):
    """(audit high-water mark, fenced) for an exercise state DB, read without
    modifying the file (immutable URI â€” recovery sets are hash-verified).
    A missing file reads as (0, False); an unreadable schema refuses the wipe
    by raising â€” silence here would defeat the staleness check."""
    path = Path(path)
    if not path.is_file():
        return 0, False
    con = sqlite3.connect('file:%s?mode=ro&immutable=1' % path.as_posix(), uri=True)
    try:
        mark = con.execute('SELECT COALESCE(MAX(id), 0) FROM audit').fetchone()[0]
        fenced = bool(con.execute('SELECT fenced FROM control').fetchone()[0])
        return mark, fenced
    finally:
        con.close()


class LocalStack:
    """Stage-by-stage local lifecycle over one runtime directory."""

    def __init__(self, profile, runtime, runner, host=None, operator='deploy', receipts=None):
        self.runtime = Path(runtime).resolve()
        override = self.runtime / 'overrides.json'
        if override.is_file():
            # `up --teams N` persists the chosen roster here so every later
            # lifecycle command sees the same effective profile (and the same
            # journal fingerprint) without repeating the flag.
            team_count = json.loads(override.read_text(encoding='utf-8'))['team_count']
            profile = deploy_config.apply_team_override(profile, team_count)
        self.profile = deploy_config.validate(profile)
        self.runner = runner
        self.host = host or HostOps()
        self.operator = operator
        self.receipts = Path(receipts) if receipts else ROOT / 'work' / 'build-receipts'
        self.event = self.profile['event']['id']
        teams = self.profile['roster']['teams']
        self.teams = teams
        self.local = self._load_local()

    # ------------------------------------------------------------------ paths

    def _load_local(self):
        path = self.runtime / 'local.json'
        if not path.is_file():
            raise LifecycleError(
                'missing %s: create it with {"assets": {"evidence_public": ..., '
                '"release_vault": ..., "case_template": ..., "originals": ..., '
                '"wazuh_config": ...}, "ports": {...}} for this host' % path)
        local = json.loads(path.read_text(encoding='utf-8'))
        for key in ('evidence_public', 'release_vault', 'case_template', 'originals', 'wazuh_config'):
            if not local.get('assets', {}).get(key):
                raise LifecycleError('local.json assets.%s: required host path' % key)
        self._validate_tls_config(local)
        self._validate_desktop_workers(local)
        return local

    def _validate_desktop_workers(self, local):
        """Validate host-local Docker context and remote bind-mount paths.

        Placement belongs in the versioned profile, but Docker context names and
        paths on another operator-owned machine are deliberately local.json-only.
        This keeps credentials and host details out of reusable profiles.
        """
        workers = local.get('desktop_workers') or {}
        if not isinstance(workers, dict):
            raise LifecycleError('local.json desktop_workers: expected an object')
        required = {desktop.get('worker', 'local') for desktop in self.profile['desktops']}
        required.discard('local')
        missing = sorted(required.difference(workers))
        if missing:
            raise LifecycleError('local.json desktop_workers: missing configuration for %s'
                                 % ', '.join(missing))
        relay_ports = {}
        for worker_id in sorted(required):
            worker = workers[worker_id]
            field = 'local.json desktop_workers.%s' % worker_id
            if not isinstance(worker, dict):
                raise LifecycleError('%s: expected an object' % field)
            context = worker.get('docker_context')
            if not isinstance(context, str) or not context.strip():
                raise LifecycleError('%s.docker_context: required Docker context name' % field)
            assets = worker.get('assets')
            if not isinstance(assets, dict):
                raise LifecycleError('%s.assets: expected an object of remote host paths' % field)
            for key in ('case_template', 'evidence_public', 'originals'):
                if not isinstance(assets.get(key), str) or not assets[key].strip():
                    raise LifecycleError('%s.assets.%s: required remote host path' % (field, key))
            password_dir = worker.get('vnc_password_dir')
            if not isinstance(password_dir, str) or not password_dir.strip():
                raise LifecycleError('%s.vnc_password_dir: required remote host path' % field)
            relay = worker.get('guacamole_relay')
            if relay is None:
                continue
            relay_field = field + '.guacamole_relay'
            if not isinstance(relay, dict):
                raise LifecycleError('%s: expected an object' % relay_field)
            address = relay.get('address')
            if (not isinstance(address, str) or not address.strip()
                    or not re.fullmatch(
                        r'[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?', address)):
                raise LifecycleError(
                    '%s.address: required Guacamole-visible hostname or IPv4 address'
                    % relay_field)
            listen_address = relay.get('listen_address', '0.0.0.0')
            try:
                listen_ip = ipaddress.IPv4Address(listen_address)
            except ipaddress.AddressValueError as exc:
                raise LifecycleError('%s.listen_address: expected an IPv4 address: %s'
                                     % (relay_field, exc))
            if not (listen_ip.is_unspecified or listen_ip.is_private or listen_ip.is_loopback):
                raise LifecycleError('%s.listen_address: must be private, loopback, or 0.0.0.0'
                                     % relay_field)
            source_cidr = relay.get('source_cidr')
            try:
                source_network = ipaddress.IPv4Network(source_cidr, strict=False)
            except (ipaddress.AddressValueError, TypeError) as exc:
                raise LifecycleError('%s.source_cidr: required private IPv4 network: %s'
                                     % (relay_field, exc))
            if not source_network.is_private:
                raise LifecycleError('%s.source_cidr: must be a private IPv4 network'
                                     % relay_field)
            ports = relay.get('ports')
            if not isinstance(ports, dict) or not ports:
                raise LifecycleError('%s.ports: expected a non-empty desktop-to-port object'
                                     % relay_field)
            assigned = {desktop['name'] for desktop in self.profile['desktops']
                        if desktop.get('worker', 'local') == worker_id}
            if set(ports) != assigned:
                raise LifecycleError(
                    '%s.ports: must map every desktop assigned to %s exactly (%s)'
                    % (relay_field, worker_id, ', '.join(sorted(assigned))))
            for desktop_name, port in ports.items():
                if not isinstance(port, int) or isinstance(port, bool) or not 1024 <= port <= 65535:
                    raise LifecycleError('%s.ports.%s: expected TCP port 1024-65535'
                                         % (relay_field, desktop_name))
                if port in relay_ports:
                    raise LifecycleError(
                        '%s.ports.%s: relay port %d is already assigned to %s'
                        % (relay_field, desktop_name, port, relay_ports[port]))
                relay_ports[port] = '%s/%s' % (worker_id, desktop_name)

    def _remote_worker_ids(self):
        return sorted({desktop.get('worker', 'local') for desktop in self.profile['desktops']
                       if desktop.get('worker', 'local') != 'local'})

    def _worker(self, worker_id):
        if worker_id == 'local':
            return None
        return self.local['desktop_workers'][worker_id]

    @staticmethod
    def _validate_tls_config(local):
        """Validate host-local edge TLS settings without accepting secrets in profiles.

        The default remains the event CA.  ``external`` is intentionally a
        local.json-only setting: certificate paths and private keys are host
        material and must never become part of the versioned event profile.
        """
        tls = local.get('tls') or {}
        if not isinstance(tls, dict):
            raise LifecycleError('local.json tls: expected an object')
        mode = tls.get('mode', 'generated')
        if mode not in ('generated', 'external'):
            raise LifecycleError('local.json tls.mode: expected generated or external')
        if mode == 'generated':
            return
        for key in ('certificate', 'key'):
            value = tls.get(key)
            if not value or not Path(value).is_file():
                raise LifecycleError('local.json tls.%s: required certificate material path' % key)
        hosts = tls.get('hostnames')
        required = ('iris', 'ctfd', 'guac', 'wazuh')
        if not isinstance(hosts, dict) or any(not hosts.get(name) for name in required):
            raise LifecycleError('local.json tls.hostnames: set iris, ctfd, guac and wazuh')
        for name in required:
            host = str(hosts[name])
            if '://' in host or '/' in host or ':' in host or not re.fullmatch(
                    r'[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?', host):
                raise LifecycleError('local.json tls.hostnames.%s: expected a DNS hostname' % name)

    @property
    def secrets_dir(self):
        return self.runtime / 'secrets'

    @property
    def env_dir(self):
        return self.runtime / 'env'

    @property
    def specs_dir(self):
        return self.runtime / 'specs'

    @property
    def state_dir(self):
        return self.runtime / 'state'

    @property
    def state_path(self):
        return self.state_dir / 'state.sqlite'

    @property
    def registration_dir(self):
        """Private bind mount shared by the landing page and host allocator."""
        return self.runtime / 'registration'

    @property
    def discovered_path(self):
        return self.runtime / 'discovered.json'

    def asset(self, key):
        path = Path(self.local['assets'][key])
        return path.resolve() if path.is_absolute() else (ROOT / path).resolve()

    def port(self, name, default):
        return int(self.local.get('ports', {}).get(name, default))

    def _tls_mode(self):
        return (self.local.get('tls') or {}).get('mode', 'generated')

    def _service_hosts(self):
        bind = self._dashboard_bind_ip()
        if self._tls_mode() != 'external':
            return {name: bind for name in ('iris', 'ctfd', 'guac', 'wazuh')}
        return {name: str(self.local['tls']['hostnames'][name])
                for name in ('iris', 'ctfd', 'guac', 'wazuh')}

    def _participant_ca_file(self):
        # Publicly trusted edge certificates use the platform trust store.
        # Wazuh's indexer and manager continue to use root-ca.pem internally.
        return None if self._tls_mode() == 'external' else self.runtime / 'wazuh-certs' / 'root-ca.pem'

    def _public_port(self, service, default):
        return (self.port('edge', 443) if self._tls_mode() == 'external'
                else self.port(service, default))

    @staticmethod
    def _public_url(host, port):
        return 'https://%s' % host if port == 443 else 'https://%s:%d' % (host, port)

    def _render_participant_tls_config(self):
        """Render the edge proxy config for this host's TLS mode."""
        target = self.runtime / 'participant-tls.conf'
        if self._tls_mode() != 'external':
            shutil.copyfile(COMPOSE_DIR / 'participant-tls.conf', target)
            return target
        hosts = self._service_hosts()
        common = '''worker_processes auto;
events { worker_connections 1024; }

http {
    include /etc/nginx/mime.types;
    resolver 127.0.0.11 valid=10s ipv6=off;
    map $http_upgrade $connection_upgrade {
        default upgrade;
        '' close;
    }
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_certificate /etc/silent-ridge/participant.pem;
    ssl_certificate_key /etc/silent-ridge/participant-key.pem;
    client_max_body_size 128m;
    proxy_set_header Host $http_host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Host $http_host;
    proxy_set_header X-Forwarded-Proto https;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection $connection_upgrade;
    proxy_redirect off;
    proxy_read_timeout 3600s;
    proxy_send_timeout 3600s;

    server {
        listen 8080;
        location = /root-ca.crl {
            alias /etc/silent-ridge/root-ca.crl;
            default_type application/pkix-crl;
            add_header Cache-Control "no-store" always;
        }
        location / { return 404; }
    }
'''
        blocks = {
            hosts['iris']: 'http://iris:8000',
            hosts['ctfd']: 'http://ctfd:8000',
            hosts['guac']: 'http://guacamole:8080',
        }
        rendered = [common]
        for hostname, upstream in blocks.items():
            rendered.append('''    server {
        listen 443 ssl;
        server_name %s;
%s
        location / {
            proxy_pass %s;
        }
    }
''' % (hostname,
       '        location = / { return 302 /guacamole/; }' if hostname==hosts['guac'] else '',
       upstream))
        rendered.append('''    server {
        listen 443 ssl;
        server_name %s;
        proxy_ssl_trusted_certificate /etc/silent-ridge/root-ca.pem;
        proxy_ssl_verify on;
        proxy_ssl_server_name on;
        proxy_ssl_name wazuh-dashboard;
        location / {
            proxy_pass https://wazuh-dashboard:5601;
        }
    }
}
''' % hosts['wazuh'])
        target.write_text(''.join(rendered), encoding='utf-8')
        return target

    def _secret(self, name):
        path = self.secrets_dir / name
        if not path.is_file():
            raise LifecycleError('missing secret %s: the runtime is incomplete; restore it '
                                 'or remove the runtime directory and run up again' % path)
        return path.read_text(encoding='utf-8').strip()

    def _wazuh_api_password(self):
        password = self._secret(WAZUH_API_SECRET)
        if (not 8 <= len(password) <= 64 or '\n' in password or '\r' in password
                or not re.search(r'[A-Z]', password) or not re.search(r'[a-z]', password)
                or not re.search(r'[0-9]', password) or not re.search(r'[^A-Za-z0-9]', password)):
            raise LifecycleError('Wazuh API secret must be 8-64 characters with uppercase, '
                                 'lowercase, digit and symbol; restore the generated secret')
        marker = self.runtime / 'wazuh-api-secret.sha256'
        if marker.is_file() and marker.read_text(encoding='utf-8').strip() != hashlib.sha256(
                password.encode()).hexdigest():
            raise LifecycleError('Wazuh API secret changed since initialization; restore '
                                 'the original runtime secret')
        return password

    def _ensure_wazuh_api_secret(self):
        """Add this new secret to older runtimes without rotating existing secrets."""
        path = self.secrets_dir / WAZUH_API_SECRET
        marker = self.runtime / 'wazuh-api-secret.sha256'
        if marker.is_file() and not path.is_file():
            raise LifecycleError('Wazuh API secret is missing from %s; restore the runtime'
                                 % path)
        if not path.is_file():
            _write_private(path, 'Aa1!' + self.host.randhex(20) + '\n')
        password = self._wazuh_api_password()
        if not marker.is_file():
            _write_private(marker, hashlib.sha256(password.encode()).hexdigest() + '\n')

    # ------------------------------------------------------------------ docker

    def _run(self, argv, check=True):
        return self.runner.run([str(a) for a in argv], check=check)

    def _compose(self, project_kind, *args, check=True):
        env_file = self.env_dir / (project_kind + '.env')
        return self._run(['docker', 'compose', '--env-file', env_file,
                          '-f', COMPOSE_FILES[project_kind], *args], check=check)

    def _desktop_compose(self, worker_id, *args, check=True):
        """Run the desktop Compose project on its assigned Docker host."""
        if worker_id == 'local':
            return self._compose('desktops', *args, check=check)
        worker = self._worker(worker_id)
        return self._run([
            'docker', '--context', worker['docker_context'], 'compose',
            '--env-file', self.env_dir / ('desktops-%s.env' % worker_id),
            '-f', COMPOSE_FILES['desktops'],
            '-f', self.runtime / ('desktops-%s.override.yaml' % worker_id),
            *args,
        ], check=check)

    def _desktop_spec(self, service):
        """Resolve a Compose service to its normalized desktop profile row."""
        by_name = {desktop['name']: desktop for desktop in self.profile['desktops']}
        if service in by_name:
            return by_name[service]
        from ridge.docker_provider import team_service
        for index, team in enumerate(self.teams):
            if team_service('team%02d' % (index + 1)) == service:
                return by_name[team['desktop']]
        raise LifecycleError('desktop service %s has no profile placement' % service)

    def _desktop_groups(self, services):
        groups = {}
        for service in services:
            worker_id = self._desktop_spec(service).get('worker', 'local')
            groups.setdefault(worker_id, []).append(service)
        return groups

    def _start_desktop_services(self, services):
        started = []
        for worker_id, names in self._desktop_groups(services).items():
            self._desktop_compose(worker_id, 'up', '-d', '--wait', '--wait-timeout', '300',
                                  *names)
            started.extend((worker_id, name) for name in names)
        return started

    def _stop_desktop_services(self, services):
        for worker_id, names in self._desktop_groups(services).items():
            self._desktop_compose(worker_id, 'stop', *names, check=False)

    def _desktop_ps(self, worker_id):
        try:
            out = self._desktop_compose(worker_id, 'ps', '-a', '--format', 'json')
        except Exception:
            return {}
        services = {}
        for line in out.splitlines():
            line = line.strip().strip(',')
            if not line or not line.startswith('{'):
                continue
            row = json.loads(line)
            name = row.get('Service') or row.get('Name', '')
            services[name] = {'state': row.get('State', ''),
                              'health': row.get('Health') or row.get('Status', ''),
                              'exit_code': row.get('ExitCode')}
        return services

    def _ps(self, project_kind):
        """Compose ps as {service: {'state':..., 'health':...}}; empty when project absent."""
        try:
            out = self._compose(project_kind, 'ps', '-a', '--format', 'json')
        except Exception:
            return {}
        services = {}
        for line in out.splitlines():
            line = line.strip().strip(',')
            if not line or not line.startswith('{'):
                continue
            row = json.loads(line)
            name = row.get('Service') or row.get('Name', '')
            services[name] = {'state': row.get('State', ''),
                              'health': row.get('Health') or row.get('Status', ''),
                              'exit_code': row.get('ExitCode')}
        return services

    def _require_services(self, project_kind, names, allow_exit0=()):
        services = self._ps(project_kind)
        problems = []
        for name in names:
            entry = services.get(name)
            if entry is None:
                problems.append('%s/%s is absent' % (project_kind, name))
                continue
            if name in allow_exit0 and entry['state'] == 'exited' and entry.get('exit_code') == 0:
                continue
            if name in allow_exit0 and entry['state'] == 'running':
                continue
            if entry['state'] != 'running':
                problems.append('%s/%s is %s' % (project_kind, name, entry['state']))
            elif entry['health'] not in ('', 'healthy', 'running') \
                    and not entry['health'].startswith('Up'):
                problems.append('%s/%s health is %s' % (project_kind, name, entry['health']))
        if problems:
            raise LifecycleError('services not ready: ' + '; '.join(problems) +
                                 '. Run `python -m ridge.deploy up` to reconcile; '
                                 'state is never reset automatically')
        return services

    def _require_desktop_services(self, names):
        problems = []
        result = {}
        for worker_id, worker_names in self._desktop_groups(names).items():
            services = self._desktop_ps(worker_id)
            result.update(services)
            label = 'desktops' if worker_id == 'local' else 'desktops@' + worker_id
            for name in worker_names:
                entry = services.get(name)
                if entry is None:
                    problems.append('%s/%s is absent' % (label, name))
                elif entry['state'] != 'running':
                    problems.append('%s/%s is %s' % (label, name, entry['state']))
                elif (entry['health'] not in ('', 'healthy', 'running')
                      and not entry['health'].startswith('Up')):
                    problems.append('%s/%s health is %s' % (label, name, entry['health']))
        if problems:
            raise LifecycleError('services not ready: ' + '; '.join(problems) +
                                 '. Run `python -m ridge.deploy up` to reconcile; '
                                 'state is never reset automatically')
        return result

    # ------------------------------------------------------------- generation

    def _ensure_secrets(self):
        """Generate event credentials once; never rotate them in place.

        This is an educational exercise, so the credentials participants type
        are intentionally memorable and consistent across services. Internal
        API/database secrets remain generated separately.
        """
        existing = [name for name in SECRET_FILES if (self.secrets_dir / name).is_file()]
        if existing and len(existing) != len(SECRET_FILES):
            missing = sorted(set(SECRET_FILES) - set(existing))
            raise LifecycleError('incomplete secrets in %s: missing %s. Restore the runtime '
                                 'or remove it and run up again; secrets are never rotated '
                                 'in place' % (self.secrets_dir, ', '.join(missing)))
        team_creds = self.secrets_dir / 'team-credentials.json'
        vnc_dir = self.secrets_dir / 'vnc'
        dynamic = self.profile.get('registration', {}).get('enabled', False)
        vnc_names = ([desktop['name'] for desktop in self.profile['desktops']]
                     if dynamic else ['team%02d' % (i + 1) for i in range(len(self.teams))])
        vnc_ok = vnc_dir.is_dir() and all(
            (vnc_dir / name).is_file() for name in vnc_names)
        if existing and team_creds.is_file() and vnc_ok:
            self._ensure_wazuh_api_secret()
            self._ensure_facilitator_secrets()
            self._ensure_registration_enrollment_code()
            return False
        if existing and (not team_creds.is_file() or not vnc_ok):
            raise LifecycleError('incomplete secrets in %s: team credentials or VNC passwords '
                                 'missing; restore the runtime' % self.secrets_dir)
        self.secrets_dir.mkdir(parents=True, exist_ok=True)
        vnc_dir.mkdir(exist_ok=True)
        for name in SECRET_FILES:
            _write_private(self.secrets_dir / name, self.host.randhex(24) + '\n')
        # Administrative and participant-service credentials are random even on
        # an isolated classroom LAN. Friendly participant identities do not
        # require predictable privileged passwords.
        _write_private(self.secrets_dir / 'iris-admin-password', self.host.randhex(24) + '\n')
        # Wazuh credentials are "username:password". These are the accounts
        # shown to organizers/participants; machine-to-machine API secrets are
        # still generated independently below.
        _write_private(self.secrets_dir / 'wazuh_admin',
                       'admin:' + self.host.randhex(24))
        _write_private(self.secrets_dir / 'wazuh_writer',
                       'writer:' + self.host.randhex(24))
        _write_private(self.secrets_dir / 'wazuh_reader',
                       'participant:' + self.host.randhex(16))
        credentials = {'teams': {}, 'desktops': {}}
        import string
        import secrets as _secrets
        alphabet = string.ascii_letters + string.digits
        for index, desktop in enumerate(self.profile['desktops']):
            tag = desktop['name'] if dynamic else 'team%02d' % (index + 1)
            friendly = 'team%d' % (index + 1)
            vnc = ''.join(_secrets.choice(alphabet) for _ in range(8))  # VncAuth truncates at 8
            _write_private(vnc_dir / tag, vnc + '\n')
            credentials['desktops'][desktop['name']] = {'password': vnc}
        if not dynamic:
            for index, team in enumerate(self.teams):
                friendly = 'team%d' % (index + 1)
                account_names = [
                    (friendly if account_index == 0 else '%s-p%02d' %
                     (friendly, account_index + 1))
                    for account_index, _account in enumerate(team['accounts'])]
                credentials['teams'][team['name']] = {
                    'iris_login': friendly,
                    'iris_password': self.host.randhex(12),
                    'ctfd_name': friendly,
                    'ctfd_password': self.host.randhex(12),
                    'guac_username': friendly,
                    'guac_password': self.host.randhex(12),
                    # Publish the actual CTFd usernames.  The first seat uses the
                    # memorable team name; additional seats receive predictable
                    # suffixes.  The roster's internal team-XX-pNN names are not
                    # CTFd logins and must not leak into the participant inventory.
                    'accounts': {name: self.host.randhex(12) for name in account_names},
                }
        _write_private(team_creds, json.dumps(credentials, indent=2))
        self._ensure_wazuh_api_secret()
        self._ensure_facilitator_secrets()
        self._ensure_registration_enrollment_code()
        return True

    def _ensure_facilitator_secrets(self):
        """Create admin passwords once; never rotate a lost one."""
        marker = self.secrets_dir / 'facilitator-secrets.ready'
        names = ('ctfd-facilitator-password', 'guac-facilitator-password')
        missing = [name for name in names if not (self.secrets_dir / name).is_file()]
        if marker.is_file() and missing:
            raise LifecycleError('facilitator secret missing (%s); restore the runtime, do not '
                                 'rotate an existing admin password' % ', '.join(missing))
        if missing and len(missing) != len(names):
            raise LifecycleError('partial facilitator secrets; restore the runtime before '
                                 'continuing')
        for name in missing:
            _write_private(self.secrets_dir / name, self.host.randhex(24) + '\n')
        _write_private(marker, 'ready\n')

    def _ensure_registration_enrollment_code(self):
        """Install the stable room code used to authorize one team reservation."""
        from ridge.registration import DEFAULT_ENROLLMENT_CODE
        path = self.secrets_dir / 'registration-enrollment-code'
        expected = DEFAULT_ENROLLMENT_CODE + '\n'
        if not path.is_file() or path.read_text(encoding='utf-8') != expected:
            _write_private(path, expected)
        return path

    def _team_credentials(self):
        path = self.secrets_dir / 'team-credentials.json'
        if not path.is_file():
            raise LifecycleError('missing %s: run up to generate secrets' % path)
        return json.loads(path.read_text(encoding='utf-8'))

    def _discovered(self):
        """Discovered application IDs: recorded file, or derived from adopted inventories."""
        if self.discovered_path.is_file():
            return json.loads(self.discovered_path.read_text(encoding='utf-8'))
        inventories = self.runtime / 'inventories'
        iris_inv = inventories / 'iris-inventory.json'
        ctfd_inv = inventories / 'ctfd-inventory.json'
        if iris_inv.is_file() and ctfd_inv.is_file():
            return _derive_discovered(
                json.loads(iris_inv.read_text(encoding='utf-8'))['inventory'],
                json.loads(ctfd_inv.read_text(encoding='utf-8'))['inventory'])
        return {}

    def _render_env(self):
        """Deterministically render every Compose env file (idempotent)."""
        self.env_dir.mkdir(parents=True, exist_ok=True)
        discovered = self._discovered()
        ports = {'crl': self.port('crl', 8080), 'iris': self.port('iris', 8081),
                 'ctfd': self.port('ctfd', 8083), 'guac': self.port('guac', 8082),
                 'wazuh': self.port('wazuh_dashboard', 8443),
                 'wazuh_indexer': self.port('wazuh_indexer', 9200)}
        # Host-side publish address is a host property, not the profile's container-side
        # central_bind_ip; default loopback, override via local.json "bind_ip".
        bind = self._dashboard_bind_ip()
        hosts = self._service_hosts()
        public = {name: self._public_url(hosts[name], self._public_port(name, ports[name]))
                  for name in ('iris', 'ctfd', 'guac', 'wazuh')}
        secrets = self.secrets_dir
        files = {}

        postgres_pw = self._secret('postgres-password')
        files['iris'] = {
            # The pinned IRIS DB image connects as POSTGRES_USER before its
            # init script creates POSTGRES_ADMIN_USER and switches to iris_db.
            # POSTGRES_USER therefore must name the built-in postgres database;
            # the application itself maps POSTGRES_ADMIN_USER to DB_USER.
            'POSTGRES_USER': 'postgres', 'POSTGRES_PASSWORD': postgres_pw,
            'POSTGRES_DB': 'iris_db',
            'POSTGRES_ADMIN_USER': 'iris', 'POSTGRES_ADMIN_PASSWORD': postgres_pw,
            'POSTGRES_SERVER': 'iris-db', 'POSTGRES_PORT': '5432',
            'IRIS_SECRET_KEY': self._secret('iris-secret-key'),
            'IRIS_SECURITY_PASSWORD_SALT': self._secret('iris-password-salt'),
            'IRIS_ADM_PASSWORD': self._secret('iris-admin-password'),
            'IRIS_AUTHENTICATION_TYPE': 'local',
        }
        mariadb_pw = self._secret('mariadb-ctfd-password')
        self.registration_dir.mkdir(parents=True, exist_ok=True)
        files['ctfd'] = {
            'DATABASE_URL': 'mysql+pymysql://ctfd:%s@ctfd-db/ctfd' % mariadb_pw,
            'SECRET_KEY': self._secret('ctfd-secret-key'),
            'REDIS_URL': 'redis://ctfd-cache:6379',
            'CTFD_NAME': 'Operation Silent Ridge',
            'CTFD_SESSION_COOKIE_NAME': 'silent_ridge_ctfd_session',
            'CTFD_SESSION_COOKIE_SECURE': 'true',
            'REVERSE_PROXY': 'true',
            'RIDGE_REGISTRATION_DB': '/registration/registrations.sqlite',
            'RIDGE_REGISTRATION_MAX_TEAMS': str(self.profile.get('registration', {}).get('max_teams', 10)),
            'RIDGE_REGISTRATION_MEMBERS': str(self.profile.get('registration', {}).get('members_per_team', 5)),
        }
        files['ctfd-db'] = {
            'MARIADB_ROOT_PASSWORD': self._secret('mariadb-root-password'),
            'MARIADB_DATABASE': 'ctfd', 'MARIADB_USER': 'ctfd'<ë¯m¢G§²ÚîÆ­y×&ö¦V7B÷vç2—G2&6¶VæBæWGv÷&²æBÖ&·2—B–çFW&æÃ²&RÖ7&VF–ær—@Ð¢†W&Rv÷VÆB6–ÆVçFÇ’F—66&BF†B—6öÆF–öâ6WGF–æràÐ¢"" Ð¢f÷"7Vff—‚–â‚rÖ6VçG&ÂrÂrÖFW6·F÷r“ Ð¢æÖRÒ6VÆbæWfVçB²7Vff—€Ð¢G'“ Ð¢6VÆbå÷'Vâ…²vFö6¶W"rÂvæWGv÷&²rÂv–ç7V7BrÂæÖUÒÐ¢W†6WB6öÖÖæDW'&÷# Ð¢6VÆbå÷'Vâ…²vFö6¶W"rÂvæWGv÷&²rÂv7&VFRrÂæÖUÒÐ¢FW6·F÷öæWGv÷&²Ò6VÆbæWfVçB²rÖFW6·F÷pÐ¢f÷"v÷&¶W%ö–B–â6VÆbå÷&VÖ÷FU÷v÷&¶W%ö–G2‚“ Ð¢6öçFW‡BÒ6VÆbå÷v÷&¶W"‡v÷&¶W%ö–B•²vFö6¶W%ö6öçFW‡BuÐÐ¢G'“ Ð¢6VÆbå÷'Vâ…²vFö6¶W"rÂrÒÖ6öçFW‡BrÂ6öçFW‡BÂvæWGv÷&²rÂv–ç7V7BrÂFW6·F÷öæWGv÷&µÒÐ¢W†6WB6öÖÖæDW'&÷# Ð¢6VÆbå÷'Vâ…²vFö6¶W"rÂrÒÖ6öçFW‡BrÂ6öçFW‡BÂvæWGv÷&²rÂv7&VFRrÂFW6·F÷öæWGv÷&µÒÐ Ð¢FVb÷7FvU÷v÷&¶W%÷fæ5÷6V7&WG2‡6VÆb“ Ð¢""%7G&VÒvVæW&FVBdä277v÷&G2Fòv÷&¶W"ÖÆö6Â&–æBF‡2àÐ Ð¢F†R6V7&WBfÇVRG&fVÇ2öâ7FF–âF‡&÷Vv‚F†RWF†VçF–6FVBFö6¶W Ð¢6öçFW‡Bâ—B—2æWfW"Æ6VB–ââ&wbÂ6ö×÷6R÷fW'&–FRÂ÷"v—Bf–ÆRàÐ¢F†—2'Vç2öæÇ’gFW"%D”d5E5õdU$”d”TB†26öæf—&ÖVBF†BF†RW†7@Ð¢&Wf–WvVBFW6·F÷–ÖvR—2&W6VçBöâV6‚v÷&¶W"àÐ¢"" Ð¢–bæ÷B6VÆbå÷&VÖ÷FU÷v÷&¶W%ö–G2‚“ Ð¢&WGW&àÐ¢&V6V—BÒ§6öâæÆöG2‚‡6VÆbç&V6V—G2òvFW6·F÷æ§6öâr’ç&VE÷FW‡B†Væ6öF–æsÒwWFbÓ‚r’Ð¢f÷"v÷&¶W%ö–B–â6VÆbå÷&VÖ÷FU÷v÷&¶W%ö–G2‚“ Ð¢v÷&¶W"Ò6VÆbå÷v÷&¶W"‡v÷&¶W%ö–BÐ¢6öçFW‡BÒv÷&¶W%²vFö6¶W%ö6öçFW‡BuÐÐ¢f÷"æÖR–â6VÆbå÷v÷&¶W%÷fæ5÷6V7&WEöæÖW2‡v÷&¶W%ö–B“ Ð¢6÷W&6RÒ6VÆbç6V7&WG5öF—"òwfæ2ròæÖPÐ¢6VÆbå÷—R…°Ð¢vFö6¶W"rÂrÒÖ6öçFW‡BrÂ6öçFW‡BÂw'VârÂrÒ×&ÒrÂrÖ’rÂrÒ×VÆÂrÂvæWfW"rÀÐ¢rÒÖæWGv÷&²rÂvæöæRrÂrÒÖVçG'—ö–çBrÂv&6‚rÀÐ¢r×brÂv÷&¶W%²wfæ5÷77v÷&EöF—"uÒ²s¢÷fæ2rÀÐ¢&V6V—E²v–ÖvRuÒÂrÖ2rÂwVÖ6²ss²6Bâ÷fæ2òW2rRæÖRÀÐ¢ÒÂ6÷W&6Rç&VE÷FW‡B†Væ6öF–æsÒwWFbÓ‚r’Ð Ð¢FVb÷v÷&¶W%÷fæ5÷6V7&WEöæÖW2‡6VÆbÂv÷&¶W%ö–B“ Ð¢G–æÖ–2Ò6VÆbç&öf–ÆRævWB‚w&Vv—7G&F–öârÂ·Ò’ævWB‚vVæ&ÆVBrÂfÇ6RÐ¢&W7VÇBÒµÐÐ¢f÷"6W'f–6R–â6VÆbåö6öæf–wW&VEöFW6·F÷÷6W'f–6W2‚“ Ð¢–b6VÆbåöFW6·F÷÷7V2‡6W'f–6R’ævWB‚wv÷&¶W"rÂvÆö6Âr’Òv÷&¶W%ö–C Ð¢6öçF–çVPÐ¢&W7VÇBæVæB‡6W'f–6R–bG–æÖ–2VÇ6R6W'f–6Rç&VÖ÷fW&Vf—‚‚vFW6·F÷Òr’Ð¢&WGW&â&W7VÇ@Ð Ð¢FVb÷&ö&U÷v÷&¶W%÷fæ5÷6V7&WG2‡6VÆb“ Ð¢–bæ÷B6VÆbå÷&VÖ÷FU÷v÷&¶W%ö–G2‚“ Ð¢&WGW&àÐ¢&V6V—BÒ§6öâæÆöG2‚‡6VÆbç&V6V—G2òvFW6·F÷æ§6öâr’ç&VE÷FW‡B†Væ6öF–æsÒwWFbÓ‚r’Ð¢f÷"v÷&¶W%ö–B–â6VÆbå÷&VÖ÷FU÷v÷&¶W%ö–G2‚“ Ð¢v÷&¶W"Ò6VÆbå÷v÷&¶W"‡v÷&¶W%ö–BÐ¢6†V6·2Òrbbræ¦ö–â‚wFW7B×2÷fæ2òW2rRæÖPÐ¢f÷"æÖR–â6VÆbå÷v÷&¶W%÷fæ5÷6V7&WEöæÖW2‡v÷&¶W%ö–B’Ð¢G'“ Ð¢6VÆbå÷'Vâ…°Ð¢vFö6¶W"rÂrÒÖ6öçFW‡BrÂv÷&¶W%²vFö6¶W%ö6öçFW‡BuÒÂw'VârÂrÒ×&ÒrÀÐ¢rÒ×VÆÂrÂvæWfW"rÂrÒÖæWGv÷&²rÂvæöæRrÂrÒÖVçG'—ö–çBrÂv&6‚rÀÐ¢r×brÂv÷&¶W%²wfæ5÷77v÷&EöF—"uÒ²s¢÷fæ3§&òrÀÐ¢&V6V—E²v–ÖvRuÒÂrÖ2rÂ6†V6·2ÀÐ¢ÒÐ¢W†6WBW†6WF–öã Ð¢&—6RÆ–fV7–6ÆTW'&÷"€Ð¢wv÷&¶W"W2—2Ö—76–æröæR÷"Ö÷&RvVæW&FVBdä26V7&WG2BW3²pÐ¢w&W'VâWFò&W7FvRF†VÒF‡&÷Vv‚F†RFö6¶W"6öçFW‡BpÐ¢R‡v÷&¶W%ö–BÂv÷&¶W%²wfæ5÷77v÷&EöF—"uÒ’Ð Ð¢FVböwV6ÖöÆU÷&VÆ—2‡6VÆb“ Ð¢""%&WGW&â6öæf–wW&VBv–æF÷w2†÷7B&VÆ—2–âFWFW&Ö–æ—7F–2÷&FW"àÐ Ð¢Fö6¶W"FW6·F÷'Vç2wV6F&V†–æB—G2÷vâdÒôäB&÷VæF'’âöâ†÷7G0Ð¢v†W&RF†B&÷VæF'’6ææ÷B&÷WFRF—&V7FÇ’FòÄâv÷&¶W"ÂâW‡Æ–6—@Ð¢†÷7BÖÆö6Â&VÆ’v—fW2wV6ÖöÆR&V6†&ÆRVæGö–çBv—F†÷WBW‡÷6–æpÐ¢v÷&¶W"dä2Fò'F–6—çBFWf–6W2àÐ¢"" Ð¢&÷w2ÒµÐÐ¢'•öæÖRÒ¶FW6·F÷²væÖRuÓ¢FW6·F÷f÷"FW6·F÷–â6VÆbç&öf–ÆU²vFW6·F÷2u×ÐÐ¢f÷"v÷&¶W%ö–B–â6VÆbå÷&VÖ÷FU÷v÷&¶W%ö–G2‚“ Ð¢v÷&¶W"Ò6VÆbå÷v÷&¶W"‡v÷&¶W%ö–BÐ¢&VÆ’Òv÷&¶W"ævWB‚vwV6ÖöÆU÷&VÆ’rÐ¢–b&VÆ’—2æöæS Ð¢6öçF–çVPÐ¢f÷"FW6·F÷öæÖRÂ&VÆ•÷÷'B–â6÷'FVB‡&VÆ•²w÷'G2uÒæ—FV×2‚’“ Ð¢&÷w2æVæB‚‡v÷&¶W%ö–BÂ'•öæÖU¶FW6·F÷öæÖUÒÂ&VÆ’Â&VÆ•÷÷'B’Ð¢&WGW&â&÷w0Ð Ð¢FVböwV6ÖöÆU÷&VÆ•÷'VÆUöæÖR‡6VÆbÂv÷&¶W%ö–BÂ&VÆ•÷÷'B“ Ð¢6ÇVrÒ&Rç7V"‡"uµäÕ¦×£Ó•òÕÒ²rÂrÒrÂrW2ÒW2rR‡6VÆbæWfVçBÂv÷&¶W%ö–B’Ð¢&WGW&âu6–ÆVçBÕ&–FvRÔwV2Õ&VÆ’ÒW2ÒVBrR‡6ÇVu³£ÒÂ&VÆ•÷÷'BÐ Ð¢FVböÇ•öwV6ÖöÆU÷&VÆ—2‡6VÆb“ Ð¢""$7&VFRæ'&÷vÇ’66÷VBv–æF÷w2÷'G&÷‡’æBf—&WvÆÂVçG&–W2àÐ Ð¢WfW'’&VÆ’—2W‡Æ–6—B–â&—fFRÆö6Âæ§6öæâF†Rf—&WvÆÂ6÷W&6PÐ¢—2F†RwV6ÖöÆRFö6¶W"7V&æWBÂæ÷BF†R'F–6—çBÄâÂæB6ÆVçW Ð¢F&vWG2öæÇ’F†RFWFW&Ö–æ—7F–2WfVçBÖ÷væVB'VÆRæB÷'G&÷‡’GWÆRàÐ¢"" Ð¢&VÆ—2Ò6VÆbåöwV6ÖöÆU÷&VÆ—2‚Ð¢–bæ÷B&VÆ—3 Ð¢&WGW&àÐ¢G'“ Ð¢6VÆbå÷'Vâ…°Ð¢w÷vW'6†VÆÂæW†RrÂrÔæõ&öf–ÆRrÂrÔæöä–çFW&7F—fRrÂrÔ6öÖÖæBrÀÐ¢u7F'BÕ6W'f–6RÔæÖR—†Ç7f2ÔW'&÷$7F–öâ7F÷rÀÐ¢ÒÐ¢f÷"v÷&¶W%ö–BÂFW6·F÷Â&VÆ’Â&VÆ•÷÷'B–â&VÆ—3 Ð¢'VÆRÒ6VÆbåöwV6ÖöÆU÷&VÆ•÷'VÆUöæÖR‡v÷&¶W%ö–BÂ&VÆ•÷÷'BÐ¢6÷W&6RÒ7G"†—FG&W72ä•cDæWGv÷&²‡&VÆ•²w6÷W&6Uö6–G"uÒÂ7G&–7CÔfÇ6R’Ð¢6VÆbå÷'Vâ…°Ð¢w÷vW'6†VÆÂæW†RrÂrÔæõ&öf–ÆRrÂrÔæöä–çFW&7F—fRrÂrÔ6öÖÖæBrÀÐ¢‚"DW'&÷"ä6ÆV"‚“²FW†—7F–ærÒvWBÔæWDf—&WvÆÅ'VÆRÔæÖRrW2r Ð¢"ÔW'&÷$7F–öâ6–ÆVçFÇ”6öçF–çVS²–b‚DW'&÷"ä6÷VçBÖæB Ð¢"DW'&÷%³ÒägVÆÇ•VÆ–f–VDW'&÷$–BÖæ÷FÆ–¶Rt6ÖFÆWF—¦F–öåVW'•ôæ÷Df÷VæB¢r’ Ð¢'²F‡&÷rDW'&÷%³ÒÓ²–b‚FçVÆÂÖæRFW†—7F–ær’²FW†—7F–ærÂ Ð¢%&VÖ÷fRÔæWDf—&WvÆÅ'VÆRÔW'&÷$7F–öâ7F÷Ó²W†—B"’R'VÆRÀÐ¢ÒÐ¢6VÆbå÷'Vâ…°Ð¢w÷vW'6†VÆÂæW†RrÂrÔæõ&öf–ÆRrÂrÔæöä–çFW&7F—fRrÂrÔ6öÖÖæBrÀÐ¢‚$æWrÔæWDf—&WvÆÅ'VÆRÔæÖRrW2rÔF—7Æ”æÖRrW2r Ð¢"ÔF—&V7F–öâ–æ&÷VæBÔ7F–öâÆÆ÷rÔVæ&ÆVBG'VRÕ&öf–ÆR&—fFR Ð¢"Õ&÷Fö6öÂD5ÔÆö6Å÷'BVBÕ&VÖ÷FTFG&W72rW2rÔW'&÷$7F–öâ7F÷ Ð¢R‡'VÆRÂ'VÆRÂ&VÆ•÷÷'BÂ6÷W&6R’’ÀÐ¢ÒÐ¢Æ—7FVâÒ&VÆ’ævWB‚vÆ—7FVåöFG&W72rÂsãããrÐ¢6VÆbå÷'Vâ…°Ð¢væWG6‚rÂv–çFW&f6RrÂw÷'G&÷‡’rÂvFVÆWFRrÂwcGF÷cBrÀÐ¢vÆ—7FVæFG&W73ÒW2rRÆ—7FVâÂvÆ—7FVç÷'CÒVBrR&VÆ•÷÷'BÀÐ¢ÒÂ6†V6³ÔfÇ6RÐ¢6VÆbå÷'Vâ…°Ð¢væWG6‚rÂv–çFW&f6RrÂw÷'G&÷‡’rÂvFBrÂwcGF÷cBrÀÐ¢vÆ—7FVæFG&W73ÒW2rRÆ—7FVâÂvÆ—7FVç÷'CÒVBrR&VÆ•÷÷'BÀÐ¢v6öææV7FFG&W73ÒW2rRFW6·F÷²vFG&W72uÒÀÐ¢v6öææV7G÷'CÒVBrRFW6·F÷²wfæ5÷÷'BuÒÂw&÷Fö6öÃ×F7rÀÐ¢ÒÐ¢W†6WB6öÖÖæDW'&÷"2W†3 Ð¢&—6RÆ–fV7–6ÆTW'&÷"€Ð¢v6÷VÆBæ÷B6öæf–wW&RF†Rv–æF÷w2wV6ÖöÆR&VÆ“²'VâF†RÆ–fV7–6ÆRg&öÒpÐ¢vâVÆWfFVBFW&Ö–æÂæBfW&–g’F†R•†VÇW"6W'f–6R—2f–Æ&ÆS¢W2rRW†2Ð Ð¢FVb÷&ö&UöwV6ÖöÆU÷&VÆ—2‡6VÆb“ Ð¢""%fW&–g’W†7B÷'G&÷‡’F&vWG2æB6÷W&6R×66÷VBf—&WvÆÂ'VÆW2â"" Ð¢f÷"v÷&¶W%ö–BÂFW6·F÷Â&VÆ’Â&VÆ•÷÷'B–â6VÆbåöwV6ÖöÆU÷&VÆ—2‚“ Ð¢'VÆRÒ6VÆbåöwV6ÖöÆU÷&VÆ•÷'VÆUöæÖR‡v÷&¶W%ö–BÂ&VÆ•÷÷'BÐ¢Æ—7FVâÒ&VÆ’ævWB‚vÆ—7FVåöFG&W72rÂsãããrÐ¢6÷W&6UöæWGv÷&²Ò—FG&W72ä•cDæWGv÷&²‡&VÆ•²w6÷W&6Uö6–G"uÒÂ7G&–7CÔfÇ6RÐ¢6÷W&6RÒ7G"‡6÷W&6UöæWGv÷&²Ð¢6÷W&6UöæWFÖ6²ÒrW2òW2rR‡6÷W&6UöæWGv÷&²ææWGv÷&µöFG&W72ÀÐ¢6÷W&6UöæWGv÷&²ææWFÖ6²Ð¢&÷W'G•öæÖRÒrW2òVBrR†Æ—7FVâÂ&VÆ•÷÷'BÐ¢W‡V7FVE÷F&vWBÒrW2òVBrR†FW6·F÷²vFG&W72uÒÂFW6·F÷²wfæ5÷÷'BuÒÐ¢67&—BÒ€Ð¢"GF‚Òt„´ÄÓ¥ÅÅ5•5DTÕÅÄ7W'&VçD6öçG&öÅ6WEÅÅ6W'f–6W5ÅÅ÷'E&÷‡•ÅÇcGF÷cEÅÇF7s² Ð¢"F—FVÒÒvWBÔ—FVÕ&÷W'G’ÔÆ—FW&ÅF‚GF‚ÔW'&÷$7F–öâ7F÷² Ð¢"G&÷W'G’ÒF—FVÒå4ö&¦V7Bå&÷W'F–W5²rW2uÓ² Ð¢&–b‚FçVÆÂÖWG&÷W'G’Ö÷"G&÷W'G’åfÇVRÖæRrW2r’²W†—B3Ó² Ð¢"G'VÆRÒvWBÔæWDf—&WvÆÅ'VÆRÔæÖRrW2rÔW'&÷$7F–öâ7F÷² Ð¢"G÷'BÒG'VÆRÂvWBÔæWDf—&WvÆÅ÷'Df–ÇFW#² Ð¢"FFG&W72ÒG'VÆRÂvWBÔæWDf—&WvÆÄFG&W74f–ÇFW#² Ð¢&–b‚G'VÆRäVæ&ÆVBÖæRuG'VRrÖ÷"G'VÆRäF—&V7F–öâÖæRt–æ&÷VæBr Ð¢"Ö÷"G'VÆRä7F–öâÖæRtÆÆ÷rrÖ÷"G÷'Bå&÷Fö6öÂÖæRuD5r Ð¢"Ö÷"G÷'BäÆö6Å÷'BÖæRrVBrÖ÷" Ð¢"„‚FFG&W72å&VÖ÷FTFG&W72’Öæ÷F6öçF–ç2rW2rÖæB Ð¢$‚FFG&W72å&VÖ÷FTFG&W72’Öæ÷F6öçF–ç2rW2r’’²W†—B3"Ò Ð¢R‡&÷W'G•öæÖRÂW‡V7FVE÷F&vWBÂ'VÆRÂ&VÆ•÷÷'BÂ6÷W&6RÀÐ¢6÷W&6UöæWFÖ6²’Ð¢G'“ Ð¢6VÆbå÷'Vâ…°Ð¢w÷vW'6†VÆÂæW†RrÂrÔæõ&öf–ÆRrÂrÔæöä–çFW&7F—fRrÂrÔ6öÖÖæBrÂ67&—BÀÐ¢ÒÐ¢W†6WB6öÖÖæDW'&÷"2W†3 Ð¢&—6RÆ–fV7–6ÆTW'&÷"€Ð¢twV6ÖöÆR&VÆ’W3¢VBFöW2æ÷BÖF6‚W3¢VB÷"—G2f—&WvÆÂ6÷W&6RpÐ¢rW3²&W'VâWg&öÒâVÆWfFVBFW&Ö–æÃ¢W2pÐ¢R†Æ—7FVâÂ&VÆ•÷÷'BÂFW6·F÷²vFG&W72uÒÂFW6·F÷²wfæ5÷÷'BuÒÂ6÷W&6RÂW†2’Ð Ð¢FVb÷&VÖ÷fUöwV6ÖöÆU÷&VÆ—2‡6VÆb“ Ð¢""%&VÖ÷fRöæÇ’&VÆ’&W6÷W&6W2÷væVB'’F†—2WfVçB'VçF–ÖRâ"" Ð¢f÷"v÷&¶W%ö–BÂöFW6·F÷Â&VÆ’Â&VÆ•÷÷'B–â6VÆbåöwV6ÖöÆU÷&VÆ—2‚“ Ð¢Æ—7FVâÒ&VÆ’ævWB‚vÆ—7FVåöFG&W72rÂsãããrÐ¢6VÆbå÷'Vâ…°Ð¢væWG6‚rÂv–çFW&f6RrÂw÷'G&÷‡’rÂvFVÆWFRrÂwcGF÷cBrÀÐ¢vÆ—7FVæFG&W73ÒW2rRÆ—7FVâÂvÆ—7FVç÷'CÒVBrR&VÆ•÷÷'BÀÐ¢ÒÂ6†V6³ÔfÇ6RÐ¢'VÆRÒ6VÆbåöwV6ÖöÆU÷&VÆ•÷'VÆUöæÖR‡v÷&¶W%ö–BÂ&VÆ•÷÷'BÐ¢6VÆbå÷'Vâ…°Ð¢w÷vW'6†VÆÂæW†RrÂrÔæõ&öf–ÆRrÂrÔæöä–çFW&7F—fRrÂrÔ6öÖÖæBrÀÐ¢‚"DW'&÷"ä6ÆV"‚“²FW†—7F–ærÒvWBÔæWDf—&WvÆÅ'VÆRÔæÖRrW2r Ð¢"ÔW'&÷$7F–öâ6–ÆVçFÇ”6öçF–çVS²–b‚DW'&÷"ä6÷VçBÖæB Ð¢"DW'&÷%³ÒägVÆÇ•VÆ–f–VDW'&÷$–BÖæ÷FÆ–¶Rt6ÖFÆWF—¦F–öåVW'•ôæ÷Df÷VæB¢r’ Ð¢'²F‡&÷rDW'&÷%³ÒÓ²–b‚FçVÆÂÖæRFW†—7F–ær’²FW†—7F–ærÂ Ð¢%&VÖ÷fRÔæWDf—&WvÆÅ'VÆRÔW'&÷$7F–öâ7F÷Ó²W†—B"’R'VÆRÀÐ¢ÒÐ Ð¢FVböF6†&ö&Eö&–æEö—‡6VÆb“ Ð¢&–æBÒ7G"‡6VÆbæÆö6ÂævWB‚v&–æEö—r’÷"s#rãããrÐ¢G'“ Ð¢FG&W72Ò—FG&W72ä•cDFG&W72†&–æBÐ¢W†6WB—FG&W72äFG&W75fÇVTW'&÷"2W†3 Ð¢&—6RÆ–fV7–6ÆTW'&÷"‚vÆö6Âæ§6öâ&–æEö—×W7B&Râ•cBFG&W73¢W2rRW†2Ð¢–b†FG&W72æ—5÷Vç7V6–f–VB÷"FG&W72æ—5ö×VÇF–67B÷"FG&W72æ—5öÆ–æµöÆö6ÀÐ¢÷"æ÷B†FG&W72æ—5÷&—fFR÷"FG&W72æ—5öÆö÷&6²’“ Ð¢&—6RÆ–fV7–6ÆTW'&÷"‚vÆö6Âæ§6öâ&–æEö—×W7B&R&—fFR÷"Æö÷&6²•cBFG&W72rÐ¢&WGW&â&–æ@Ð Ð¢FVb÷fW&–g•÷V&Æ–5ö6W'F–f–6FR‡6VÆbÂ6W'G2Â&–æBÂæÖR“ Ð¢6W'F–f–6FRÒ6W'G2ò†æÖR²rçVÒrÐ¢–bæ÷B6W'F–f–6FRæ—5öf–ÆR‚“ Ð¢&—6RÆ–fV7–6ÆTW'&÷"‚vÖ—76–ærW26W'F–f–6FRBW2rR†æÖRÂ6W'F–f–6FR’Ð¢ÖF6‚Ò6VÆbå÷'Vâ…°Ð¢vFö6¶W"rÂw'VârÂrÒ×&ÒrÂrÒÖæWGv÷&²rÂvæöæRrÂrÒ×VÆÂrÂvæWfW"rÀÐ¢r×brÂ7G"†6W'G2’²s¢ö6W'G3§&òrÂrÒÖVçG'—ö–çBrÂv÷Vç76ÂrÀÐ¢wv§V‚÷v§V‚ÖÖævW#£Bã’ã"rÂwƒS’rÂrÖ–ârÂrö6W'G2òr²æÖR²rçVÒrÀÐ¢rÖæö÷WBrÂrÖ6†V6¶—rÂ&–æBÀÐ¢ÒÂ6†V6³ÔfÇ6RÐ¢–bvFöW2ÖF6‚6W'F–f–6FRræ÷B–âÖF6ƒ Ð¢&—6RÆ–fV7–6ÆTW'&÷"‚rW26W'F–f–6FRFöW2æ÷B6÷fW"Æö6Âæ§6öâpÐ¢v&–æEö—W3²&W6W'fRF†R7W'&VçB4æB6W'F–f–6FW2ÂpÐ¢wF†VâÆâ6W'F–f–6FR&÷FF–öâf÷"F†—2FG&W72rR†æÖRÂ&–æB’Ð Ð¢FVbö–ç7FÆÅöW‡FW&æÅöVFvUö6W'F–f–6FR‡6VÆbÂ6W'G2“ Ð¢""$–ç7FÆÂæBfW&–g’F†RV&Æ–2VFvR6W'F–f–6FRf÷"'&÷w6W"VæGö–çG2àÐ Ð¢öæÇ’'F–6—çBçVÒ—2&WÆ6VBâF†RvVæW&FVB&ö÷B4ÂF6†&ö&BÀÐ¢ÖævW"Â–æFW†W"æBFÖ–â6W'F–f–6FW2&VÖ–âf–Æ&ÆRf÷"v§V‚w0Ð¢&—fFR&6¶VæBG'W7Bw&‚àÐ¢"" Ð¢FÇ2Ò6VÆbæÆö6Å²wFÇ2uÐÐ¢6÷W&6Uö6W'BÒF‚‡FÇ5²v6W'F–f–6FRuÒ’ç&W6öÇfR‚Ð¢6÷W&6Uö¶W’ÒF‚‡FÇ5²v¶W’uÒ’ç&W6öÇfR‚Ð¢f÷"6÷W&6RÂÆ&VÂ–â‚‡6÷W&6Uö6W'BÂv6W'F–f–6FRr’Â‡6÷W&6Uö¶W’Âv¶W’r’“ Ð¢–bæ÷B6÷W&6Ræ—5öf–ÆR‚’÷"6÷W&6Rç7FB‚’ç7E÷6—¦RÓÒ Ð¢&—6RÆ–fV7–6ÆTW'&÷"‚vW‡FW&æÂDÅ2W2—2Ö—76–ær÷"V×G“¢W2rR†Æ&VÂÂ6÷W&6R’Ð¢6‡WF–Âæ6÷–f–ÆR‡6÷W&6Uö6W'BÂ6W'G2òw'F–6—çBçVÒrÐ¢6‡WF–Âæ6÷–f–ÆR‡6÷W&6Uö¶W’Â6W'G2òw'F–6—çBÖ¶W’çVÒrÐ¢†÷7G2Ò6VÆbå÷6W'f–6Uö†÷7G2‚Ð¢f÷"æÖR–â‚v—&—2rÂv7FfBrÂvwV2rÂwv§V‚r“ Ð¢ÖF6‚Ò6VÆbå÷'Vâ…°Ð¢vFö6¶W"rÂw'VârÂrÒ×&ÒrÂrÒÖæWGv÷&²rÂvæöæRrÂrÒ×VÆÂrÂvæWfW"rÀÐ¢r×brÂ7G"†6W'G2’²s¢ö6W'G3§&òrÂrÒÖVçG'—ö–çBrÂv÷Vç76ÂrÀÐ¢wv§V‚÷v§V‚ÖÖævW#£Bã’ã"rÂwƒS’rÂrÖ–ârÂrö6W'G2÷'F–6—çBçVÒrÀÐ¢rÖæö÷WBrÂrÖ6†V6¶†÷7BrÂ†÷7G5¶æÖUÒÀÐ¢ÒÂ6†V6³ÔfÇ6RÐ¢–bvFöW2ÖF6‚6W'F–f–6FRræ÷B–âÖF6ƒ Ð¢&—6RÆ–fV7–6ÆTW'&÷"‚vW‡FW&æÂDÅ26W'F–f–6FRFöW2æ÷B6÷fW"†÷7FæÖRW3²pÐ¢w&WVW7B6W'F–f–6FR6öçF–æ–ærWfW'’6öæf–wW&VB6W'f–6RpÐ¢v†÷7FæÖRrR†÷7G5¶æÖUÒÐ¢2æv–ç‚v–ÆÂ&W÷'B¶W’Ö—6ÖF6‚Â'WBf–ÂV&Ç’v—F‚â7F–öæ&ÆPÐ¢2ÖW76vRv†VâF†R–ÖvR6â–ç7V7B&÷F‚V&Æ–2f–ÆW2àÐ¢¶W•ö6†V6²Ò6VÆbå÷'Vâ…°Ð¢vFö6¶W"rÂw'VârÂrÒ×&ÒrÂrÒÖæWGv÷&²rÂvæöæRrÂrÒ×VÆÂrÂvæWfW"rÀÐ¢r×brÂ7G"†6W'G2’²s¢ö6W'G3§&òrÂrÒÖVçG'—ö–çBrÂw6‚rÀÐ¢wv§V‚÷v§V‚ÖÖævW#£Bã’ã"rÂrÖV2rÀÐ¢&÷Vç76ÂƒS’Ö–âö6W'G2÷'F–6—çBçVÒ×V&¶W’Öæö÷WBÂ Ð¢&÷Vç76Â¶W’×V&–âÖ÷WFf÷&ÒDU"Â6†#Sg7VÓ² Ð¢&÷Vç76Â¶W’Ö–âö6W'G2÷'F–6—çBÖ¶W’çVÒ×V&÷WBÖ÷WFf÷&ÒDU"Â6†#Sg7VÒ"ÀÐ¢ÒÂ6†V6³ÔfÇ6RÐ¢†6†W2Ò¶Æ–æRç7Æ—B‚•³Òf÷"Æ–æR–â¶W•ö6†V6²ç7Æ—FÆ–æW2‚Ð¢–b&RægVÆÆÖF6‚‡"u³Ó–ÖdÔe×³cGÒrÂÆ–æRç7Æ—B‚•³Ò–bÆ–æRç7Æ—B‚’VÇ6Rrr•ÐÐ¢–bÆVâ††6†W2’Ò"÷"†6†W5³ÒæÆ÷vW"‚’Ò†6†W5³ÒæÆ÷vW"‚“ Ð¢&—6RÆ–fV7–6ÆTW'&÷"‚vW‡FW&æÂDÅ26W'F–f–6FRæB&—fFR¶W’Fòæ÷BÖF6‚rÐ Ð¢FVb÷fW&–g•÷&Wfö6F–öåöÖFW&–Â‡6VÆbÂ6W'G2Â&–æB“ Ð¢7&ÂÒ6W'G2òw&ö÷BÖ6æ7&ÂpÐ¢–bæ÷B7&Âæ—5öf–ÆR‚’÷"7&Âç7FB‚’ç7E÷6—¦RÓÒ Ð¢&—6RÆ–fV7–6ÆTW'&÷"‚vÖ—76–ær6–væVBöffÆ–æR5$ÂBW3²&÷FFRF†RWfVçB4pÐ¢væB6W'F–f–6FW2&Vf÷&R'F–6—çB6WGWrR7&ÂÐ¢G'“ Ð¢2÷Vå54Âw&—FW2fW&–g’ô¶Fò7FFW'"Âv†–ÆR6öÖÖæE'VææW"&WGW&ç0Ð¢27FF÷WBâF†RW†—B7FGW2—2F†R÷'F&ÆRfW&–f–6F–öâ6öçG&7BàÐ¢6VÆbå÷'Vâ…°Ð¢vFö6¶W"rÂw'VârÂrÒ×&ÒrÂrÒÖæWGv÷&²rÂvæöæRrÂrÒ×VÆÂrÂvæWfW"rÀÐ¢r×brÂ7G"†6W'G2’²s¢ö6W'G3§&òrÂrÒÖVçG'—ö–çBrÂv÷Vç76ÂrÀÐ¢wv§V‚÷v§V‚ÖÖævW#£Bã’ã"rÂv7&ÂrÂrÖ–ârÂrö6W'G2÷&ö÷BÖ6æ7&ÂrÀÐ¢rÖ–æf÷&ÒrÂtDU"rÂrÖæö÷WBrÂr×fW&–g’rÂrÔ4f–ÆRrÂrö6W'G2÷&ö÷BÖ6çVÒrÀÐ¢ÒÐ¢W†6WB6öÖÖæDW'&÷# Ð¢&—6RÆ–fV7–6ÆTW'&÷"‚vöffÆ–æR5$Â6–væGW&RfW&–f–6F–öâf–ÆVC²&÷FFRF†RpÐ¢vWfVçB4æB6W'F–f–6FW2rÐ¢W‡V7FVBÒv‡GG¢òòW3¢VB÷&ö÷BÖ6æ7&ÂrR†&–æBÂ6VÆbç÷'B‚v7&ÂrÂƒƒ’Ð¢f÷"æÖR–â‚vF6†&ö&BrÂw'F–6—çBr“ Ð¢ö–çG2Ò6VÆbå÷'Vâ…°Ð¢vFö6¶W"rÂw'VârÂrÒ×&ÒrÂrÒÖæWGv÷&²rÂvæöæRrÂrÒ×VÆÂrÂvæWfW"rÀÐ¢r×brÂ7G"†6W'G2’²s¢ö6W'G3§&òrÂrÒÖVçG'—ö–çBrÂv÷Vç76ÂrÀÐ¢wv§V‚÷v§V‚ÖÖævW#£Bã’ã"rÂwƒS’rÂrÖ–ârÂrö6W'G2òr²æÖR²rçVÒrÀÐ¢rÖæö÷WBrÂrÖW‡BrÂv7&ÄF—7G&–'WF–öåö–çG2rÀÐ¢ÒÂ6†V6³ÔfÇ6RÐ¢–bW‡V7FVBæ÷B–âö–çG3 Ð¢&—6RÆ–fV7–6ÆTW'&÷"‚rW26W'F–f–6FRFöW2æ÷BV&Æ—6‚W‡V7FVBöffÆ–æR5$ÂpÐ¢uU$ÂW3²&÷FFRF†RWfVçB4æB6W'F–f–6FW2pÐ¢R†æÖRÂW‡V7FVB’Ð Ð¢FVb÷&W&U÷v§V…ö6W'F–f–6FW2‡6VÆbÂ6W'G2Â&–æB“ Ð¢""%&W&R–çFW&æÂæöFRDÅ2æBF†R'F–6—çBÖf6–ærVFvR6W'F–f–6FRàÐ Ð¢–âW‡FW&æÂDÅ2ÖöFRF†R6öæf–wW&VBV&Æ–26W'F–f–6FR&WÆ6W2F†PÐ¢vVæW&FVB'F–6—çBVFvR—"âÆFW"W×W7BF†W&Vf÷&Ræ÷@Ð¢6²F†R&—fFRÔ4vVæW&F÷"FòfÆ–FFRF†BV&Æ–26W'F–f–6FRw25$ÀÐ¢W‡FVç6–öââ&W6W'fRF†RW†—7F–ær–çFW&æÂ4öæöFRÖFW&–ÂÂf–ÀÐ¢6Æ÷6VB–bç’öb—B—2–æ6ö×ÆWFRÂæB&V–ç7FÆÂF†R6öæf–wW&VBVFvPÐ¢—"–FV×÷FVçFÇ’àÐ¢"" Ð¢W‡FW&æÅ÷&WW6RÒ6VÆbå÷FÇ5öÖöFR‚’ÓÒvW‡FW&æÂræB†6W'G2òw&ö÷BÖ6çVÒr’æ—5öf–ÆR‚Ð¢–bW‡FW&æÅ÷&WW6S Ð¢–çFW&æÂÒ€Ð¢w&ö÷BÖ6çVÒrÂw&ö÷BÖ6Ö¶W’çVÒrÂw&ö÷BÖ6æ7&ÂrÀÐ¢vF6†&ö&BçVÒrÂvF6†&ö&BÖ¶W’çVÒrÀÐ¢v–æFW†W"çVÒrÂv–æFW†W"Ö¶W’çVÒrÀÐ¢vÖævW"çVÒrÂvÖævW"Ö¶W’çVÒrÀÐ¢vFÖ–âçVÒrÂvFÖ–âÖ¶W’çVÒrÀÐ¢Ð¢Ö—76–ærÒ¶æÖRf÷"æÖR–â–çFW&æÀÐ¢–bæ÷B†6W'G2òæÖR’æ—5öf–ÆR‚’÷"†6W'G2òæÖR’ç7FB‚’ç7E÷6—¦RÓÒÐÐ¢–bÖ—76–æs Ð¢&—6RÆ–fV7–6ÆTW'&÷"€Ð¢vW‡FW&æÂDÅ2'VçF–ÖR†2–æ6ö×ÆWFR–çFW&æÂv§V‚6W'F–f–6FRÖFW&–Ã¢pÐ¢²rÂræ¦ö–â†Ö—76–ær’²s²&W7F÷&RF†R'VçF–ÖR&6·W÷"W6Rg&W6‚'VçF–ÖRrÐ¢VÇ6S Ð¢6VÆbå÷'Vâ…°Ð¢vFö6¶W"rÂw'VârÂrÒ×&ÒrÂrÒÖæWGv÷&²rÂvæöæRrÂrÒ×VÆÂrÂvæWfW"rÀÐ¢rÖRrÂu$”DtUô5$Åõõ%CÒVBrR6VÆbç÷'B‚v7&ÂrÂƒƒ’ÀÐ¢r×brÂ7G"…t¥T…ôD•"òvvVæW&FRÖ6W'G2ç6‚r’²s¢övVæW&FRÖ6W'G2ç6ƒ§&òrÀÐ¢r×brÂ7G"†6W'G2’²s¢ö6W'G2rÂrÒÖVçG'—ö–çBrÂv&6‚rÀÐ¢wv§V‚÷v§V‚ÖÖævW#£Bã’ã"rÂrövVæW&FRÖ6W'G2ç6‚rÂrö6W'G2rÂ&–æBÀÐ¢ÒÐ¢–b6VÆbå÷FÇ5öÖöFR‚’ÓÒvW‡FW&æÂs Ð¢6VÆbåö–ç7FÆÅöW‡FW&æÅöVFvUö6W'F–f–6FR†6W'G2Ð¢6VÆbå÷fW&–g•÷V&Æ–5ö6W'F–f–6FR†6W'G2Â&–æBÂvF6†&ö&BrÐ¢VÇ6S Ð¢6VÆbå÷fW&–g•÷V&Æ–5ö6W'F–f–6FR†6W'G2Â&–æBÂvF6†&ö&BrÐ¢6VÆbå÷fW&–g•÷V&Æ–5ö6W'F–f–6FR†6W'G2Â&–æBÂw'F–6—çBrÐ¢6VÆbå÷fW&–g•÷&Wfö6F–öåöÖFW&–Â†6W'G2Â&–æBÐ Ð¢FVböÇ•ö–æg&7G'V7GW&R‡6VÆb“ Ð¢6VÆbåöVç7W&U÷6V7&WG2‚Ð¢6VÆbåöÇ•öwV6ÖöÆU÷&VÆ—2‚Ð¢6VÆbå÷&VæFW%÷7V72‚Ð¢6VÆbå÷&VæFW%÷v§V…ö6öæf–r‚Ð¢6VÆbå÷&VæFW%öVçb‚Ð¢6VÆbåöVç7W&UöæWGv÷&·2‚Ð¢6VÆbå÷7FvU÷v÷&¶W%÷fæ5÷6V7&WG2‚Ð¢6W'G2Ò6VÆbç'VçF–ÖRòwv§V‚Ö6W'G2pÐ¢&–æBÒ6VÆbåöF6†&ö&Eö&–æEö—‚Ð¢6W'G2æÖ¶F—"‡&VçG3ÕG'VRÂW†—7Eöö³ÕG'VRÐ¢6VÆbå÷&W&U÷v§V…ö6W'F–f–6FW2†6W'G2Â&–æBÐ¢wV5ö–æ—BÒ6VÆbç'VçF–ÖRòvwV2Ö–æ—BpÐ¢wV5ö–æ—BæÖ¶F—"‡&VçG3ÕG'VRÂW†—7Eöö³ÕG'VRÐ¢–bæ÷B†wV5ö–æ—BòsÖ–æ—FF"ç7Âr’æ—5öf–ÆR‚“ Ð¢66†VÖÒ6VÆbå÷'Vâ…²vFö6¶W"rÂw'VârÂrÒ×&ÒrÂvwV6ÖöÆRöwV6ÖöÆS£ãRãRrÀÐ¢rö÷BöwV6ÖöÆRö&–âö–æ—FF"ç6‚rÂrÒ×÷7Fw&W7ÂuÒÐ¢†wV5ö–æ—BòsÖ–æ—FF"ç7Âr’çw&—FU÷FW‡B‡66†VÖ²uÆârÂVæ6öF–æsÒwWFbÓ‚rÐ¢–×÷'B7—0Ð¢7—2çF‚æ–ç6W'BƒÂ7G"„4ôÕõ4UôD•"’Ð¢–×÷'BwV6ÖöÆR2wV5öÖöGVÆPÐ¢6öæf–rÒ§6öâæÆöG2‚‡6VÆbç7V75öF—"òvwV2Ö6öæf–ræ§6öâr’ç&VE÷FW‡B†Væ6öF–æsÒwWFbÓ‚r’Ð¢7&VFVçF–Ç2Ò§6öâæÆöG2‚‡6VÆbç7V75öF—"òvwV2Ö7&VFVçF–Ç2æ§6öâr’ç&VE÷FW‡B†Væ6öF–æsÒwWFbÓ‚r’Ð¢2F†RvVæW&F÷"—2–FV×÷FVçBæB&VgW6W27&VFVçF–Â&÷FF–öââ&Ww&—FPÐ¢2F†—2&—fFR5Â6ò7F÷VBFWÆ÷–ÖVçB6âF÷Bâ–çFVçF–öæÀÐ¢2F—&V7B×Fò×&VÆ’VæGö–çB6†ævRv†VâDU4µDõ5õ$TE’—2&RÖÆ–VBàÐ¢÷w&—FU÷&—fFR†wV5ö–æ—Bòs"×&÷f—6–öâç7ÂrÀÐ¢wV5öÖöGVÆRævVæW&FR†6öæf–rÂ7&VFVçF–Ç2’Ð¢f÷"¶–æBÂ6W'f–6W2–â”äe$õ4U%d”4U2æ—FV×2‚“ Ð¢–b¶–æB–â‚wv§V‚rÂvwV6ÖöÆRr“ Ð¢2'Vææ–ærÖævW"6â7F–ÆÂ†fRæòv§V‚FVÖöç2ÂæBF†PÐ¢2wV6ÖöÆRFF&6RöwV6BæVVB&÷VæFVB7F'GWv–æF÷r&Vf÷&PÐ¢2F†R–ÖÖVF–FR7FvR&ö&Râv—Bf÷"6ö×÷6R†VÇF‚&F†W"F†àÐ¢2GW&æ–æræ÷&ÖÂf—'7BÖ&ö÷BF–Ö–ær–çFòf–ÆVBÆ–fV7–6ÆR7FWàÐ¢6VÆbåö6ö×÷6R†¶–æBÂwWrÂrÖBrÂrÒ×v—BrÂrÒ×v—B×F–ÖV÷WBrÂs3rÂ§6W'f–6W2Ð¢VÇ6S Ð¢6VÆbåö6ö×÷6R†¶–æBÂwWrÂrÖBrÂ§6W'f–6W2Ð Ð¢FVb÷&ö&Uö–æg&7G'V7GW&R‡6VÆb“ Ð¢W†—7F–ærÒ¶æÖRf÷"æÖR–â4T5$UEôd”ÄU2–b‡6VÆbç6V7&WG5öF—"òæÖR’æ—5öf–ÆR‚•ÐÐ¢–bÆVâ†W†—7F–ær’ÒÆVâ…4T5$UEôd”ÄU2“ Ð¢&—6RÆ–fV7–6ÆTW'&÷"‚v–æ6ö×ÆWFR6V7&WG2–âW3¢Ö—76–ærW2â&W7F÷&RF†R'VçF–ÖS²pÐ¢w6V7&WG2&RæWfW"&VvVæW&FVB&VæVF‚fW&–f–VBFWÆ÷–ÖVçBpÐ¢R‡6VÆbç6V7&WG5öF—"ÀÐ¢rÂræ¦ö–â‡6÷'FVB‡6WB…4T5$UEôd”ÄU2’Ò6WB†W†—7F–ær’’’’Ð¢6VÆbå÷v§V…ö•÷77v÷&B‚Ð¢6VÆbå÷&ö&U÷v÷&¶W%÷fæ5÷6V7&WG2‚Ð¢&—fFU÷W6W'2Ò6VÆbç'VçF–ÖRòwv§V‚Ö6öæf–rròv–çFW&æÅ÷W6W'2ç–ÖÂpÐ¢–bæ÷B&—fFU÷W6W'2æ—5öf–ÆR‚“ Ð¢&—6RÆ–fV7–6ÆTW'&÷"‚vÖ—76–ær&—fFRv§V‚–æFW†W"W6W'2BW3²&W7F÷&RF†RpÐ¢w'VçF–ÖR÷"'VâWöâg&W6‚FWÆ÷–ÖVçBrR&—fFU÷W6W'2Ð¢–b6VÆbå÷FÇ5öÖöFR‚’ÓÒvW‡FW&æÂs Ð¢6VÆbåö–ç7FÆÅöW‡FW&æÅöVFvUö6W'F–f–6FR‡6VÆbç'VçF–ÖRòwv§V‚Ö6W'G2rÐ¢6VÆbå÷fW&–g•÷V&Æ–5ö6W'F–f–6FR‡6VÆbç'VçF–ÖRòwv§V‚Ö6W'G2rÀÐ¢6VÆbåöF6†&ö&Eö&–æEö—‚’ÂvF6†&ö&BrÐ¢VÇ6S Ð¢f÷"æÖR–â‚vF6†&ö&BrÂw'F–6—çBr“ Ð¢6VÆbå÷fW&–g•÷V&Æ–5ö6W'F–f–6FR‡6VÆbç'VçF–ÖRòwv§V‚Ö6W'G2rÀÐ¢6VÆbåöF6†&ö&Eö&–æEö—‚’ÂæÖRÐ¢6VÆbå÷fW&–g•÷&Wfö6F–öåöÖFW&–Â‡6VÆbç'VçF–ÖRòwv§V‚Ö6W'G2rÀÐ¢6VÆbåöF6†&ö&Eö&–æEö—‚’Ð¢f÷"¶–æBÂ6W'f–6W2–â”äe$õ4U%d”4U2æ—FV×2‚“ Ð¢6VÆbå÷&WV—&U÷6W'f–6W2†¶–æBÂ6W'f–6W2ÀÐ¢ÆÆ÷uöW†—CÔ”äe$ôôäUõ4„õBævWB†¶–æBÂ‚’’Ð¢6VÆbå÷&ö&UöwV6ÖöÆU÷&VÆ—2‚Ð¢&WGW&â²w6W'f–6W2s¢7VÒ†ÆVâ‡2’f÷"2–â”äe$õ4U%d”4U2çfÇVW2‚’—ÐÐ Ð¢232ÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÆ–6F–öç0Ð¢FVböÇ•öÆ–6F–öç2‡6VÆb“ Ð¢f÷"¶–æBÂ6W'f–6W2–âõ4U%d”4U2æ—FV×2‚“ Ð¢6VÆbåö6ö×÷6R†¶–æBÂwWrÂrÖBrÂrÒ×v—BrÂrÒ×v—B×F–ÖV÷WBrÂs3rÂ§6W'f–6W2Ð Ð¢FVb÷&ö&UöÆ–6F–öç2‡6VÆb“ Ð¢f÷"¶–æBÂ6W'f–6W2–âõ4U%d”4U2æ—FV×2‚“ Ð¢6VÆbå÷&WV—&U÷6W'f–6W2†¶–æBÂ6W'f–6W2Ð¢†÷7G2Ò6VÆbå÷6W'f–6Uö†÷7G2‚Ð¢2g&W6‚5DfBFF&6R6W'fW2÷6WGWVçF–Â6–ÆVçB×&–FvR×&÷f—6–öâ'Vç0Ð¢2–âF†RæW‡B7FvRâöÆöv–â&VF—&V7G2F†W&RW6–ær—G2–çFW&æÂFVfVÇ@Ð¢2÷'BÂ6ò&WV—&–æröÆöv–â†W&Rv÷VÆBÖ¶Rf—'7B&ö÷B–×÷76–&ÆRàÐ¢7FfE÷F‚Ò‚röÆöv–âr–b‡6VÆbç'VçF–ÖRòv–çfVçF÷&–W2ròv7FfBÖ–çfVçF÷'’æ§6öâr’æ—5öf–ÆR‚Ð¢VÇ6Rr÷6WGWrÐ¢6†V6·2Ò‚‡6VÆbå÷V&Æ–5÷W&Â††÷7G5²v—&—2uÒÂ6VÆbå÷V&Æ–5÷÷'B‚v—&—2rÂƒƒ’’²röÆöv–ârÂt•$•2r’ÀÐ¢‡6VÆbå÷V&Æ–5÷W&Â††÷7G5²v7FfBuÒÂ6VÆbå÷V&Æ–5÷÷'B‚v7FfBrÂƒƒ2’’²7FfE÷F‚Ât5DfBr’ÀÐ¢‡6VÆbå÷V&Æ–5÷W&Â††÷7G5²vwV2uÒÂ6VÆbå÷V&Æ–5÷÷'B‚vwV2rÂƒƒ"’’²röwV6ÖöÆRòrÂtwV6ÖöÆRr’ÀÐ¢‡6VÆbå÷V&Æ–5÷W&Â††÷7G5²wv§V‚uÒÂ6VÆbå÷V&Æ–5÷÷'B‚wv§V‚rÂƒCC2’’²rööÆöv–ârÂuv§V‚r’Ð¢6öf–ÆRÒ6VÆbå÷'F–6—çEö6öf–ÆR‚Ð¢f÷"W&ÂÂæÖR–â6†V6·3 Ð¢7FGW2ÂòÒ6VÆbæ†÷7Bæ‡GGö§6öâ‚ttUBrÂW&ÂÂ6öf–ÆSÖ6öf–ÆRÐ¢–b7FGW2Ò# Ð¢&—6RÆ–fV7–6ÆTW'&÷"‚rW2'F–6—çBvR&WGW&æVB…EEW2BW3²F†RÆ–6F–öâ—2pÐ¢væ÷B&VG’rR†æÖRÂ7FGW2ÂW&Â’Ð¢&WGW&â²w6W'f–6W2s¢7VÒ†ÆVâ‡2’f÷"2–âõ4U%d”4U2çfÇVW2‚’—ÐÐ Ð¢23BÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒ–FVçF—F–W0Ð¢FVbö6öçF–æW%öæÖR‡6VÆbÂ&ö¦V7Eö¶–æBÂ6W'f–6R“ Ð¢÷WBÒ6VÆbåö6ö×÷6R‡&ö¦V7Eö¶–æBÂw2rÂrÖrÂr×rÂ6W'f–6RÐ¢6öçF–æW%ö–BÒ÷WBç7G&—‚’ç7Æ—FÆ–æW2‚•³Ò–b÷WBç7G&—‚’VÇ6RrpÐ¢–bæ÷B6öçF–æW%ö–C Ð¢&—6RÆ–fV7–6ÆTW'&÷"‚væò6öçF–æW"f÷"W2òW3²'VâWf—'7BrR‡&ö¦V7Eö¶–æBÂ6W'f–6R’Ð¢æÖRÒ6VÆbå÷'Vâ…²vFö6¶W"rÂv–ç7V7BrÂrÒÖf÷&ÖBrÂw·²äæÖW×ÒrÂ6öçF–æW%ö–EÒÐ¢&WGW&âæÖRç7G&—‚’æÇ7G&—‚ròrÐ Ð¢FVbö&ö÷G7G&ööæR‡6VÆbÂ&ö¦V7Eö¶–æBÂ6W'f–6RÂ7V5öæÖRÂ6öÖÖæBÂ–çfVçF÷'•öæÖR“ Ð¢7V2Ò6VÆbç7V75öF—"ò7V5öæÖPÐ¢F&vWE÷7V2Òr÷F×÷6–ÆVçB×&–FvR×7V2æ§6öâpÐ¢F&vWEö–çfVçF÷'’Òr÷F×÷6–ÆVçB×&–FvRÖ–çfVçF÷'’æ§6öâpÐ¢6öçF–æW"Ò6VÆbåö6öçF–æW%öæÖR‡&ö¦V7Eö¶–æBÂ6W'f–6RÐ¢6VÆbå÷'Vâ…²vFö6¶W"rÂv7rÂ7V2ÂrW3¢W2rR†6öçF–æW"ÂF&vWE÷7V2•ÒÐ¢6VÆbåö6ö×÷6R‡&ö¦V7Eö¶–æBÂvW†V2rÂrÕBrÂ6W'f–6RÂvfÆ6²rÂ6öÖÖæBÀÐ¢rÒ×7V2rÂF&vWE÷7V2ÂrÒÖ–çfVçF÷'’rÂF&vWEö–çfVçF÷'’Ð¢Æö6Åö–çfVçF÷'’Ò6VÆbç'VçF–ÖRòv–çfVçF÷&–W2rò–çfVçF÷'•öæÖPÐ¢Æö6Åö–çfVçF÷'’ç&VçBæÖ¶F—"‡&VçG3ÕG'VRÂW†—7Eöö³ÕG'VRÐ¢–bÆö6Åö–çfVçF÷'’æ—5öf–ÆR‚“ Ð¢&Wf–÷W2ÒÆö6Åö–çfVçF÷'’ç&VEö'—FW2‚Ð¢7Fv–ærÒ6VÆbç'VçF–ÖRòv–çfVçF÷&–W2rò‚rææW‡BÒr²–çfVçF÷'•öæÖRÐ¢6VÆbå÷'Vâ…²vFö6¶W"rÂv7rÂrW3¢W2rR†6öçF–æW"ÂF&vWEö–çfVçF÷'’’Â7Fv–æuÒÐ¢–b7Fv–ærç&VEö'—FW2‚’Ò&Wf–÷W3 Ð¢7Fv–ærçVæÆ–æ²†Ö—76–æuöö³ÕG'VRÐ¢&—6RÆ–fV7–6ÆTW'&÷"€Ð¢w&WVFVBW2&WGW&æVBF–ffW&VçB–çfVçF÷'“²&VgW6–ærFòF÷B6†ævVBpÐ¢v–FVçF—F–W2â–çfW7F–vFRW2g2F†R6öçF–æW"7FFRrR†6öÖÖæBÂÆö6Åö–çfVçF÷'’’Ð¢7Fv–ærçVæÆ–æ²†Ö—76–æuöö³ÕG'VRÐ¢VÇ6S Ð¢6VÆbå÷'Vâ…²vFö6¶W"rÂv7rÂrW3¢W2rR†6öçF–æW"ÂF&vWEö–çfVçF÷'’’ÂÆö6Åö–çfVçF÷'•ÒÐ¢&WGW&â§6öâæÆöG2†Æö6Åö–çfVçF÷'’ç&VE÷FW‡B†Væ6öF–æsÒwWFbÓ‚r’Ð Ð¢FVböÇ•ö–FVçF—F–W2‡6VÆb“ Ð¢—&—2Ò6VÆbåö&ö÷G7G&ööæR‚v6VçG&ÂrÂv—&—2rÂv—&—2Ö&ö÷G7G&×7V2æ§6öârÀÐ¢w6–ÆVçB×&–FvRÖ&ö÷G7G&rÂv—&—2Ö–çfVçF÷'’æ§6öârÐ¢6VÆbåö&ö÷G7G&ööæR‚v6VçG&ÂrÂv7FfBrÂv7FfB×&÷f—6–öâ×7V2æ§6öârÀÐ¢w6–ÆVçB×&–FvR×&÷f—6–öârÂv7FfBÖ–çfVçF÷'’æ§6öârÐ¢–çfVçF÷'’Ò—&—5²v–çfVçF÷'’uÐÐ¢7FfEö–çfVçF÷'’Ò§6öâæÆöG2‚‡6VÆbç'VçF–ÖRòv–çfVçF÷&–W2ròv7FfBÖ–çfVçF÷'’æ§6öârÐ¢ç&VE÷FW‡B†Væ6öF–æsÒwWFbÓ‚r’•²v–çfVçF÷'’uÐÐ¢F—66÷fW&VBÒöFW&—fUöF—66÷fW&VB†–çfVçF÷'’Â7FfEö–çfVçF÷'’Ð¢6VÆbæF—66÷fW&VE÷F‚çw&—FU÷FW‡B†§6öâæGV×2†F—66÷fW&VBÂ–æFVçCÓ"’ÂVæ6öF–æsÒwWFbÓ‚rÐ¢6VÆbå÷&VæFW%öVçb‚’26VçG&ÂæVçbæ÷r6'&–W2F†RF—66÷fW&VB$”DtUô•$•5ò¢”G0Ð¢6VÆbåö6ö×÷6R‚v6VçG&ÂrÂwWrÂrÖBrÂv—&—2rÂv—&—2×v÷&¶W"rÐ Ð¢FVb÷&ö&Uö–FVçF—F–W2‡6VÆb“ Ð¢f÷"æÖR–â‚v—&—2Ö–çfVçF÷'’æ§6öârÂv7FfBÖ–çfVçF÷'’æ§6öâr“ Ð¢F‚Ò6VÆbç'VçF–ÖRòv–çfVçF÷&–W2ròæÖPÐ¢–bæ÷BF‚æ—5öf–ÆR‚“ Ð¢&—6RÆ–fV7–6ÆTW'&÷"‚vÖ—76–ærW3¢–FVçF—F–W2vW&RæWfW"&÷f—6–öæVC²'VâWpÐ¢RF‚Ð¢–bæ÷B6VÆbæF—66÷fW&VE÷F‚æ—5öf–ÆR‚“ Ð¢&—6RÆ–fV7–6ÆTW'&÷"‚vÖ—76–ærW3¢F—66÷fW&VBÆ–6F–öâ”G2&Ræ÷B&V6÷&FVC²pÐ¢w'VâWrR6VÆbæF—66÷fW&VE÷F‚Ð¢†÷7G2Ò6VÆbå÷6W'f–6Uö†÷7G2‚Ð¢W&ÂÒ6VÆbå÷V&Æ–5÷W&Â††÷7G5²v7FfBuÒÂ6VÆbå÷V&Æ–5÷÷'B‚v7FfBrÂƒƒ2’’²röÆöv–âpÐ¢7FGW2ÂòÒ6VÆbæ†÷7Bæ‡GGö§6öâ‚ttUBrÂW&ÂÀÐ¢6öf–ÆS×6VÆbå÷'F–6—çEö6öf–ÆR‚’Ð¢–b7FGW2Ò# Ð¢&—6RÆ–fV7–6ÆTW'&÷"‚w&÷f—6–öæVB5DfBÆöv–â&WGW&æVB…EEW2BW2rR‡7FGW2ÂW&Â’Ð¢&WGW&â²v–çfVçF÷&–W2s¢'ÐÐ Ð¢23RÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒFW6·F÷0Ð¢FVböFW6·F÷÷6W'f–6W2‡6VÆb“ Ð¢g&öÒ&–FvRæFö6¶W%÷&÷f–FW"–×÷'BFVÕ÷6W'f–6PÐ¢–b6VÆbç&öf–ÆRævWB‚w&Vv—7G&F–öârÂ·Ò’ævWB‚vVæ&ÆVBrÂfÇ6R“ Ð¢&WGW&âµÐÐ¢&WGW&â·FVÕ÷6W'f–6R‚wFVÒS&BrR†’²’’f÷"’–â&ævR†ÆVâ‡6VÆbçFV×2’•ÐÐ Ð¢FVbö6öæf–wW&VEöFW6·F÷÷6W'f–6W2‡6VÆb“ Ð¢–b6VÆbç&öf–ÆRævWB‚w&Vv—7G&F–öârÂ·Ò’ævWB‚vVæ&ÆVBrÂfÇ6R“ Ð¢&WGW&â¶FW6·F÷²væÖRuÒf÷"FW6·F÷–â6VÆbç&öf–ÆU²vFW6·F÷2uÕÐÐ¢&WGW&â6VÆbåöFW6·F÷÷6W'f–6W2‚Ð Ð¢FVböÇ•öFW6·F÷2‡6VÆb“ Ð¢–bæ÷B6VÆbç&öf–ÆRævWB‚w&Vv—7G&F–öârÂ·Ò’ævWB‚vVæ&ÆVBrÂfÇ6R“ Ð¢6VÆbå÷7F'EöFW6·F÷÷6W'f–6W2‡6VÆbåöFW6·F÷÷6W'f–6W2‚’Ð¢7ÂÒ‡6VÆbç'VçF–ÖRòvwV2Ö–æ—Bròs"×&÷f—6–öâç7Âr’ç&VE÷FW‡B†Væ6öF–æsÒwWFbÓ‚rÐ¢6VÆbå÷—R…²vFö6¶W"rÂv6ö×÷6RrÂrÒÖVçbÖf–ÆRrÂ6VÆbæVçeöF—"òvwV6ÖöÆRæVçbrÀÐ¢rÖbrÂ4ôÕõ4Uôd”ÄU5²vwV6ÖöÆRuÒÂvW†V2rÂrÕBrÂvFF&6RrÀÐ¢w7ÂrÂrÕRrÂvwV6ÖöÆRrÂrÖBrÂvwV6ÖöÆRrÂr×brÂtôåôU%$õ%õ5DõÓuÒÀÐ¢7ÂÐ Ð¢FVb÷—R‡6VÆbÂ&wbÂFW‡B“ Ð¢""%'Vâ&wbv—F‚7FF–âFW‡BF‡&÷Vv‚F†R&VÂ7V'&ö6W72'VææW"â"" Ð¢–b†6GG"‡6VÆbç'VææW"Âw'Vå÷7FF–âr“ Ð¢&WGW&â6VÆbç'VææW"ç'Vå÷7FF–â…·7G"†’f÷"–â&weÒÂFW‡BÂ6†V6³ÕG'VRÐ¢6ö×ÆWFVBÒ7V'&ö6W72ç'Vâ…·7G"†’f÷"–â&weÒÂ–çWC×FW‡BÂ6GW&Uö÷WGWCÕG'VRÀÐ¢FW‡CÕG'VRÂF–ÖV÷WCÓ#Ð¢–b6ö×ÆWFVBç&WGW&æ6öFRÒ Ð¢&—6RÆ–fV7–6ÆTW'&÷"‚w&÷f—6–öæ–ær5Âf–ÆVC¢W2rR6ö×ÆWFVBç7FFW'"ç7G&—‚•³£3ÒÐ¢&WGW&â6ö×ÆWFVBç7FF÷WBç7G&—‚Ð Ð¢FVb&Vv—7FW%ööæ6R‡6VÆb“ Ð¢""%&÷f—6–öâöæRVæF–ær6VÆb×6W'f–6R&Vv—7G&F–öâàÐ Ð¢F†—2ÖWF†öB'Vç2öâF†RWfVçB†÷7BÂ÷WG6–FR'F–6—çB6öçF–æW'2â—@Ð¢—2–çFVçF–öæÆÇ’F†RöæÇ’F‚F†B6â7F'BæWrFW6·F÷6W'f–6R÷ Ð¢Ç’wV6ÖöÆR5ÂâF†RV&Æ–25DfB&Vv—7G&F–öâvRöæÇ’w&—FW2F†PÐ¢ÆÆö6F÷"w25Æ—FR&÷ràÐ¢"" Ð¢g&öÒ&–FvRç&Vv—7G&F–öâ–×÷'B…&Vv—7G&F–öä6öæf–rÂ&Vv—7G&F–öå7F÷&RÀÐ¢FW6·F÷ö†æF÷WBÐ¢&Vv—7G&F–öå÷F‚Ò6VÆbç&Vv—7G&F–öåöF—"òw&Vv—7G&F–öç2ç7Æ—FRpÐ¢&Vv—7G&F–öâÒ&Vv—7G&F–öå7F÷&R€Ð¢7G"‡&Vv—7G&F–öå÷F‚’ÀÐ¢&Vv—7G&F–öä6öæf–r€Ð¢Ö…÷FV×3×6VÆbç&öf–ÆU²w&Vv—7G&F–öâuÕ²vÖ…÷FV×2uÒÀÐ¢ÖVÖ&W'5÷W%÷FVÓ×6VÆbç&öf–ÆU²w&Vv—7G&F–öâuÕ²vÖVÖ&W'5÷W%÷FVÒuÒ’ÀÐ¢Vç&öÆÆÖVçEö6öFS×6VÆbå÷6V7&WB‚w&Vv—7G&F–öâÖVç&öÆÆÖVçBÖ6öFRr’Ð¢÷6V7W&U÷&—fFR‡&Vv—7G&F–öå÷F‚Ð¢6Æ–ÖVBÒ&Vv—7G&F–öâæ6Æ–Õ÷VæF–ær‚Ð¢–b6Æ–ÖVB—2æöæS Ð¢&WGW&âæöæPÐ¢v÷&¶W%÷Fö¶VâÒ6Æ–ÖVE²wv÷&¶W%÷Fö¶VâuÐÐ¢7&VFVçF–Ç2Ò&Vv—7G&F–öâæ7F—fFUö7&VFVçF–Ç2†6Æ–ÖVE²v–BuÒÂv÷&¶W%÷Fö¶VâÐ¢v§V…÷W6W&æÖRÂ6W&F÷"Âv§V…÷77v÷&BÒ6VÆbå÷6V7&WB‚wv§V…÷&VFW"r’ç'F—F–öâ‚s¢rÐ¢–bæ÷B6W&F÷"÷"æ÷Bv§V…÷W6W&æÖR÷"æ÷Bv§V…÷77v÷&C Ð¢&—6RÆ–fV7–6ÆTW'&÷"‚wv§V…÷&VFW"×W7B6öçF–âW6W&æÖS§77v÷&BrÐ¢2v§V‚—2–çFVçF–öæÆÇ’öæR6†&VB&VBÖöæÇ’6Æ77&ööÒ66÷VçBâ–æ6ÇVFPÐ¢2—BöæÇ’–âF†R&—fFR&WG&–WfÂ†æF÷WC²æWfW"–âV&Æ–2&Vv—7G&F–öàÐ¢27FFR÷"&W÷6—F÷'’6öæf–wW&F–öâàÐ¢7&VFVçF–Ç5²wv§V‚uÒÒ°Ð¢wW6W&æÖRs¢v§V…÷W6W&æÖRÀÐ¢w77v÷&Bs¢v§V…÷77v÷&BÀÐ¢ÐÐ¢6W'f–6W2ÒÆ—7B†6Æ–ÖVE²w6Æ÷G2uÒÐ¢G'“ Ð¢6VÆbå÷7F'EöFW6·F÷÷6W'f–6W2‡6W'f–6W2Ð¢7FfBÒ6VÆbåö6ö×÷6R‚v6VçG&ÂrÂvW†V2rÂrÕBrÂv7FfBrÂvfÆ6²rÀÐ¢w6–ÆVçB×&–FvR×&Vv—7FW"rÂrÒ×&Vv—7G&F–öâÖ–BrÂ7G"†6Æ–ÖVE²v–BuÒ’Ð¢—&—2Ò6VÆbåö6ö×÷6R‚v6VçG&ÂrÂvW†V2rÂrÕBrÂv—&—2rÂvfÆ6²rÀÐ¢w6–ÆVçB×&–FvR×&Vv—7FW"rÂrÒ×&Vv—7G&F–öâÖ–BrÂ7G"†6Æ–ÖVE²v–BuÒ’Ð¢7FfE÷&÷rÒ6VÆbåöÆ7Eö§6öâ†7FfBÂt5DfB&Vv—7G&F–öârÐ¢—&—5÷&÷rÒ6VÆbåöÆ7Eö§6öâ†—&—2Ât•$•2&Vv—7G&F–öârÐ¢FVÕö–BÒwFVÒÒS&BrR6Æ–ÖVE²v–BuÐÐ¢6VÆbåöÇ•÷&Vv—7G&F–öåöwV6ÖöÆR‡FVÕö–BÂ6W'f–6W2Â7&VFVçF–Ç2Ð¢6VÆbå÷&Vv—7FW%ö6öçG&öÆÆW%÷FVÒ‡FVÕö–BÂ6Æ–ÖVE²wFVÕöæÖRuÒÀÐ¢—&—5÷&÷u²v—&—5ö–BuÒÂ7FfE÷&÷u²wFVÕö–BuÒÀÐ¢7&VFVçF–Ç2Ð¢&W7VÇBÒ²vFW6·F÷÷W&Ç2s¢FW6·F÷ö†æF÷WB€Ð¢6W'f–6W2Â6VÆbç&öf–ÆU²vFG&W76W2uÕ²vwV6ÖöÆU÷V&Æ–5÷W&ÂuÒ—ÐÐ¢&Vv—7G&F–öâæ6ö×ÆWFR†6Æ–ÖVE²v–BuÒÂ&W7VÇBÂv÷&¶W%÷Fö¶VâÀÐ¢7&VFVçF–Ç3Ö7&VFVçF–Ç2Ð¢&WGW&â²v–Bs¢6Æ–ÖVE²v–BuÒÂwFVÒs¢FVÕö–BÂvFW6·F÷2s¢6W'f–6W7ÐÐ¢W†6WBW†6WF–öâ2W†3 Ð¢–b&Vv—7G&F–öâç&WVWVR†6Æ–ÖVE²v–BuÒÂ7G"†W†2’Âv÷&¶W%÷Fö¶Vâ“ Ð¢6VÆbå÷7F÷öFW6·F÷÷6W'f–6W2‡6W'f–6W2Ð¢&—6PÐ Ð¢FVb&Vv—7G&F–öåöFÖ–â‡6VÆbÂ7F–öâÂ&Vv—7G&F–öåö–CÔæöæR“ Ð¢""$VF—FVB†÷7B×6–FR6öçG&öÇ2f÷"F†RV&Æ–2ÆÆö6F÷#²æWfW"W‡÷6W277v÷&G2â"" Ð¢–bæ÷B6VÆbç&öf–ÆRævWB‚w&Vv—7G&F–öârÂ·Ò’ævWB‚vVæ&ÆVBrÂfÇ6R“ Ð¢&—6RÆ–fV7–6ÆTW'&÷"‚vG–æÖ–2&Vv—7G&F–öâ—2æ÷BVæ&ÆVBf÷"F†—2&öf–ÆRrÐ¢g&öÒ&–FvRç&Vv—7G&F–öâ–×÷'B&Vv—7G&F–öä6öæf–rÂ&Vv—7G&F–öå7F÷&PÐ¢&Vv—7G&F–öå÷F‚Ò6VÆbç&Vv—7G&F–öåöF—"òw&Vv—7G&F–öç2ç7Æ—FRpÐ¢7F÷&RÒ&Vv—7G&F–öå7F÷&R€Ð¢7G"‡&Vv—7G&F–öå÷F‚’ÀÐ¢&Vv—7G&F–öä6öæf–r€Ð¢Ö…÷FV×3×6VÆbç&öf–ÆU²w&Vv—7G&F–öâuÕ²vÖ…÷FV×2uÒÀÐ¢ÖVÖ&W'5÷W%÷FVÓ×6VÆbç&öf–ÆU²w&Vv—7G&F–öâuÕ²vÖVÖ&W'5÷W%÷FVÒuÒ’ÀÐ¢Vç&öÆÆÖVçEö6öFS×6VÆbå÷6V7&WB‚w&Vv—7G&F–öâÖVç&öÆÆÖVçBÖ6öFRr’Ð¢÷6V7W&U÷&—fFR‡&Vv—7G&F–öå÷F‚Ð¢–b7F–öâÓÒw7FGW2s Ð¢&WGW&â²vvFRs¢vVç&öÆÆÖVçEö6öFRrÂv66—G’s¢7F÷&Ræ66—G’‚’ÀÐ¢wv÷&¶W"s¢6VÆbå÷&Vv—7G&F–öå÷v÷&¶W%÷7FGW2‚’ÀÐ¢w&Vv—7G&F–öç2s¢7F÷&RæÆ—7B‚—ÐÐ¢–b&Vv—7G&F–öåö–B—2æöæS Ð¢&—6RÆ–fV7–6ÆTW'&÷"‚w&Vv—7G&F–öâ”B—2&WV—&VBf÷"W2rR7F–öâÐ¢–b7F–öâÓÒw&WG'’s Ð¢7F÷&Rç&WG'’‡&Vv—7G&F–öåö–BÐ¢&WGW&â²v–Bs¢&Vv—7G&F–öåö–BÂw7FGW2s¢wVæF–ærwÐÐ¢–b7F–öâÓÒv6æ6VÂs Ð¢7F÷&Ræ6æ6VÂ‡&Vv—7G&F–öåö–BÐ¢&WGW&â²v–Bs¢&Vv—7G&F–öåö–BÂw7FGW2s¢v6æ6VÆÆVBwÐÐ¢–b7F–öâÓÒw&÷FFRÖÆ–æ²s Ð¢6öFRÒ7F÷&Rç&÷FFUö66W72‡&Vv—7G&F–öåö–BÐ¢&WGW&â²v–Bs¢&Vv—7G&F–öåö–BÀÐ¢w&WG&–WfU÷F‚s¢r÷6–ÆVçB×&–FvR÷&Vv—7G&F–öâòr²6öFRÀÐ¢w6Vç6—F—fRs¢G'VWÐÐ¢&—6RÆ–fV7–6ÆTW'&÷"‚wVæ¶æ÷vâ&Vv—7G&F–öâ7F–öâW2rR7F–öâÐ Ð¢7FF–6ÖWF†ö@Ð¢FVböÆ7Eö§6öâ†÷WGWBÂÆ&VÂ“ Ð¢f÷"Æ–æR–â&WfW'6VB‡7G"†÷WGWB’ç7Æ—FÆ–æW2‚’“ Ð¢G'“ Ð¢fÇVRÒ§6öâæÆöG2†Æ–æRÐ¢W†6WBfÇVTW'&÷# Ð¢6öçF–çVPÐ¢–b—6–ç7Fæ6R‡fÇVRÂF–7B“ Ð¢&WGW&âfÇVPÐ¢&—6RÆ–fV7–6ÆTW'&÷"‚rW2&WGW&æVBæò¥4ôâ&W7VÇBrRÆ&VÂÐ Ð¢FVb÷&Vv—7FW%ö6öçG&öÆÆW%÷FVÒ‡6VÆbÂFVÕö–BÂæÖRÂ—&—5ö–BÂ7FfEö–BÂ7&VFVçF–Ç2“ Ð¢6öæf–u÷F‚Ò6VÆbç7FFUöF—"òv6öæf–ræ§6öâpÐ¢6öæf–rÒ§6öâæÆöG2†6öæf–u÷F‚ç&VE÷FW‡B†Væ6öF–æsÒwWFbÓ‚r’Ð¢W†—7F–ærÒ·FVÕ²v–BuÓ¢FVÒf÷"FVÒ–â6öæf–rævWB‚wFV×2rÂµÒ—ÐÐ¢&÷rÒ²v–Bs¢FVÕö–BÂvæÖRs¢æÖRÂv—&—2s¢7G"†—&—5ö–B’Âv7FfBs¢–çB†7FfEö–B’ÀÐ¢v—&—5öÆöv–âs¢7&VFVçF–Ç5²v—&—2uÕ²wW6W&æÖRuÒÀÐ¢v7FfEöæÖRs¢æÖWÐÐ¢–bFVÕö–B–âW†—7F–æræBW†—7F–æu·FVÕö–EÒÒ&÷s Ð¢&—6RÆ–fV7–6ÆTW'&÷"‚w&Vv—7G&F–öâFVÒÖ–ærF–ffW'2g&öÒ6öçG&öÆÆW"6öæf–rrÐ¢–bFVÕö–Bæ÷B–âW†—7F–æs Ð¢6öæf–rç6WFFVfVÇB‚wFV×2rÂµÒ’æVæB‡&÷rÐ¢6öæf–u÷F‚çw&—FU÷FW‡B†§6öâæGV×2†6öæf–rÂ–æFVçCÓ"’ÂVæ6öF–æsÒwWFbÓ‚rÐ¢6VÆbæ†÷7Bç7FFR‡6VÆbç7FFU÷F‚’ç&Vv—7FW%÷FVÒ‡°Ð¢v–Bs¢FVÕö–BÂvæÖRs¢æÖRÂv—&—2s¢7G"†—&—5ö–B’Âv7FfBs¢–çB†7FfEö–B—ÒÐ Ð¢FVböÇ•÷&Vv—7G&F–öåöwV6ÖöÆR‡6VÆbÂFVÕö–BÂ6W'f–6W2Â7&VFVçF–Ç2“ Ð¢–×÷'B7—0Ð¢7—2çF‚æ–ç6W'BƒÂ7G"„4ôÕõ4UôD•"’Ð¢–×÷'BwV6ÖöÆR2wV5öÖöGVÆPÐ¢ÆÅö7&VFVçF–Ç2Ò6VÆbå÷FVÕö7&VFVçF–Ç2‚Ð¢FW6·F÷2Ò¶FW6·F÷²væÖRuÓ¢FW6·F÷f÷"FW6·F÷–â6VÆbç&öf–ÆU²vFW6·F÷2u×ÐÐ¢6öæf–rÒ²vFW6·F÷2s¢·6VÆbåöwV6ÖöÆUöFW6·F÷†FW6·F÷5·6Æ÷EÒÐ¢f÷"6Æ÷B–â6W'f–6W5ÒÀÐ¢wFV×2s¢·²v–Bs¢FVÕö–BÂvFW6·F÷2s¢6W'f–6W7Õ×ÐÐ¢wV5ö7&VFVçF–Ç2Ò°Ð¢wFV×2s¢·FVÕö–C¢²wW6W&æÖRs¢7&VFVçF–Ç5²vwV6ÖöÆRuÕ²wW6W&æÖRuÒÀÐ¢w77v÷&Bs¢7&VFVçF–Ç5²vwV6ÖöÆRuÕ²w77v÷&Bu××ÒÀÐ¢vFW6·F÷2s¢·6Æ÷C¢²w77v÷&Bs¢ÆÅö7&VFVçF–Ç5²vFW6·F÷2uÕ·6Æ÷EÕ²w77v÷&Bu×ÐÐ¢f÷"6Æ÷B–â6W'f–6W7ÒÀÐ¢vf6–Æ—FF÷"s¢²wW6W&æÖRs¢vFÖ–ârÀÐ¢w77v÷&Bs¢6VÆbå÷6V7&WB‚vwV2Öf6–Æ—FF÷"×77v÷&Br—ÒÀÐ¢ÐÐ¢7ÂÒwV5öÖöGVÆRævVæW&FR†6öæf–rÂwV5ö7&VFVçF–Ç2Ð¢6VÆbå÷—R…²vFö6¶W"rÂv6ö×÷6RrÂrÒÖVçbÖf–ÆRrÂ6VÆbæVçeöF—"òvwV6ÖöÆRæVçbrÀÐ¢rÖbrÂ4ôÕõ4Uôd”ÄU5²vwV6ÖöÆRuÒÂvW†V2rÂrÕBrÂvFF&6RrÀÐ¢w7ÂrÂrÕRrÂvwV6ÖöÆRrÂrÖBrÂvwV6ÖöÆRrÂr×brÂtôåôU%$õ%õ5DõÓuÒÂ7ÂÐ Ð¢FVb&Vv—7G&F–öåöÆö÷‡6VÆbÂ–çFW'fÃÓã“ Ð¢""%'VâF†R†÷7BÆÆö6F÷"VçF–Â–çFW''WFVC²æò'F–6—çB6öFR'Vç2†W&Râ"" Ð¢7F÷VBÒF‡&VF–æräWfVçB‚Ð¢FVb&VB‚“ Ð¢v†–ÆRæ÷B7F÷VBæ—5÷6WB‚“ Ð¢6VÆbå÷w&—FU÷&Vv—7G&F–öåö†V'F&VB‚Ð¢7F÷VBçv—BƒRÐ¢†V'F&VBÒF‡&VF–æråF‡&VB‡F&vWCÖ&VBÂFVÖöãÕG'VRÐ¢†V'F&VBç7F'B‚Ð¢G'“ Ð¢v†–ÆRG'VS Ð¢G'“ Ð¢6VÆbç&Vv—7FW%ööæ6R‚Ð¢W†6WBW†6WF–öâ2W†3 Ð¢2¶VWF†R6W'f–6RÆ—fRf÷"ÆFW"&Vv—7G&F–öç3²F†Rf–ÆV@Ð¢2&÷r—2f—6–&ÆRF‡&÷Vv‚—G2&WG&–WfÂvRæB–â†÷7BÆöw2àÐ¢Æövv–æræW'&÷"‚w&Vv—7G&F–öâ&÷f—6–öæ–ærf–ÆVC¢W2rÂW†2Ð¢F–ÖRç6ÆVW†–çFW'fÂÐ¢f–æÆÇ“ Ð¢7F÷VBç6WB‚Ð¢†V'F&VBæ¦ö–â‡F–ÖV÷WCÓbÐ Ð¢&÷W'GÐ¢FVb&Vv—7G&F–öå÷–E÷F‚‡6VÆb“ Ð¢&WGW&â6VÆbç'VçF–ÖRòw&Vv—7G&F–öâ×v÷&¶W"ç–BpÐ Ð¢&÷W'GÐ¢FVb&Vv—7G&F–öåö†V'F&VE÷F‚‡6VÆb“ Ð¢&WGW&â6VÆbç'VçF–ÖRòw&Vv—7G&F–öâ×v÷&¶W"Ö†V'F&VBæ§6öâpÐ Ð¢FVb÷w&—FU÷&Vv—7G&F–öåö†V'F&VB‡6VÆb“ Ð¢Fö¶VâÒ÷2æVçf—&öâævWB‚u$”DtUõ$Tt•5E$D”ôåõtõ$´U%õDô´TârÂrrÐ¢÷w&—FU÷&—fFR‡6VÆbç&Vv—7G&F–öåö†V'F&VE÷F‚Â§6öâæGV×2‡°Ð¢w–Bs¢÷2ævWG–B‚’ÂwFö¶Vâs¢Fö¶VâÂwWFFVBs¢F–ÖRçF–ÖR‚—Ò’²uÆârÐ Ð¢FVb÷&Vv—7G&F–öå÷v÷&¶W%÷7FGW2‡6VÆb“ Ð¢–bæ÷B6VÆbç&öf–ÆRævWB‚w&Vv—7G&F–öârÂ·Ò’ævWB‚vVæ&ÆVBrÂfÇ6R“ Ð¢&WGW&â²vVæ&ÆVBs¢fÇ6RÂv†VÇF‡’s¢G'VWÐÐ¢G'“ Ð¢6fVBÒ§6öâæÆöG2‡6VÆbç&Vv—7G&F–öå÷–E÷F‚ç&VE÷FW‡B†Væ6öF–æsÒwWFbÓ‚r’Ð¢†V'F&VBÒ§6öâæÆöG2‡6VÆbç&Vv—7G&F–öåö†V'F&VE÷F‚ç&VE÷FW‡B†Væ6öF–æsÒwWFbÓ‚r’Ð¢–BÒ–çB‡6fVE²w–BuÒÐ¢Fö¶Våöö²Ò&ööÂ‡6fVBævWB‚wFö¶Vâr’’æB6fVBævWB‚wFö¶Vâr’ÓÒ†V'F&VBævWB‚wFö¶VârÐ¢†V'F&VE÷–Eöö²Ò–çB††V'F&VE²w–BuÒ’ÓÒ–@Ð¢g&W6‚ÒF–ÖRçF–ÖR‚’ÒfÆöB††V'F&VBævWB‚wWFFVBrÂ’’ÂPÐ¢6fVEö–FVçF—G’Òöæ÷&ÖÆ—¦U÷&ö6W75ö–FVçF—G’‡6fVBævWB‚v–FVçF—G’r’Ð¢7W'&VçEö–FVçF—G’Ò÷&ö6W75ö–FVçF—G’‡–BÐ¢Æ—fRÒ7W'&VçEö–FVçF—G’—2æ÷BæöæPÐ¢–FVçF—G•öö²Ò‡6fVEö–FVçF—G’—2æ÷BæöæRæ@Ð¢7W'&VçEö–FVçF—G’ÓÒ6fVEö–FVçF—G’Ð¢–FVçF—G•÷fW&–f–VBÒ&ööÂ‡Fö¶Våöö²æB†V'F&VE÷–Eöö²æB–FVçF—G•öö²Ð¢&WGW&â²vVæ&ÆVBs¢G'VRÂv†VÇF‡’s¢&ööÂ†–FVçF—G•÷fW&–f–VBæBg&W6‚’ÀÐ¢w–Bs¢–BÂvÆ—fRs¢Æ—fRÂv†V'F&VEög&W6‚s¢g&W6‚ÀÐ¢v–FVçF—G•÷fW&–f–VBs¢–FVçF—G•÷fW&–f–VGÐÐ¢W†6WB„õ4W'&÷"ÂfÇVTW'&÷"Â¶W”W'&÷"ÂG—TW'&÷"Â§6öâä¥4ôäFV6öFTW'&÷"“ Ð¢&WGW&â²vVæ&ÆVBs¢G'VRÂv†VÇF‡’s¢fÇ6RÀÐ¢vW'&÷"s¢w&Vv—7G&F–öâv÷&¶W"”Bö†V'F&VB—2Ö—76–ær÷"–çfÆ–BwÐÐ Ð¢FVb÷7F'E÷&Vv—7G&F–öå÷v÷&¶W"‡6VÆb“ Ð¢–bæ÷B6VÆbç&öf–ÆRævWB‚w&Vv—7G&F–öârÂ·Ò’ævWB‚vVæ&ÆVBrÂfÇ6R“ Ð¢&WGW&âæöæPÐ¢–b6VÆbç&Vv—7G&F–öå÷–E÷F‚æ—5öf–ÆR‚“ Ð¢7FGW2Ò6VÆbå÷&Vv—7G&F–öå÷v÷&¶W%÷7FGW2‚Ð¢–b7FGW2ævWB‚v†VÇF‡’r“ Ð¢&WGW&â7FGW5²w–BuÐÐ¢2æWfW"¶–ÆÂâVçfW&–f–VB&WW6VB”BâfW&–f–VB7FÆRv÷&¶W"—0Ð¢27F÷VB&Vf÷&R&WÆ6VÖVçC²âVçfW&–f–VB&V6÷&B—26–×Ç’&WF—&VBàÐ¢–b7FGW2ævWB‚v–FVçF—G•÷fW&–f–VBr“ Ð¢6VÆbå÷7F÷÷&Vv—7G&F–öå÷v÷&¶W"‚Ð¢6VÆbç&Vv—7G&F–öå÷–E÷F‚çVæÆ–æ²†Ö—76–æuöö³ÕG'VRÐ¢6VÆbç&Vv—7G&F–öåö†V'F&VE÷F‚çVæÆ–æ²†Ö—76–æuöö³ÕG'VRÐ¢Æöu÷F‚Ò6VÆbç'VçF–ÖRòw&Vv—7G&F–öâ×v÷&¶W"æÆörpÐ¢ÆörÒÆöu÷F‚æ÷Vâ‚vrÂVæ6öF–æsÒwWFbÓ‚rÐ¢6öÖÖæBÒ·7—2æW†V7WF&ÆRÂrÖÒrÂw&–FvRæFWÆ÷’ç&Vv—7G&F–öå÷v÷&¶W"rÀÐ¢rÒ×&öf–ÆRrÂ7G"‡6VÆbç'VçF–ÖRòw&Vv—7G&F–öâ×&öf–ÆRæ§6öâr’ÀÐ¢rÒ×'VçF–ÖRrÂ7G"‡6VÆbç'VçF–ÖR•ÐÐ¢‡6VÆbç'VçF–ÖRòw&Vv—7G&F–öâ×&öf–ÆRæ§6öâr’çw&—FU÷FW‡B€Ð¢§6öâæGV×2‡6VÆbç&öf–ÆRÂ–æFVçCÓ"’ÂVæ6öF–æsÒwWFbÓ‚rÐ¢7&VF–öæfÆw2Ò†vWFGG"‡7V'&ö6W72Ât5$TDUôäUuõ$ô4U55ôu$õUrÂ’ÀÐ¢vWFGG"‡7V'&ö6W72ÂtDUD4„TEõ$ô4U52rÂ’Ð¢Fö¶VâÒ6VÆbæ†÷7Bç&æF†W‚ƒ#BÐ¢Vçf—&öæÖVçBÒF–7B†÷2æVçf—&öâÂ$”DtUõ$Tt•5E$D”ôåõtõ$´U%õDô´Tã×Fö¶VâÐ¢&ö6W72Ò7V'&ö6W72å÷Vâ†6öÖÖæBÂ7vC×7G"…$ôõB’Â7FF÷WCÖÆörÂ7FFW'#ÖÆörÀÐ¢7&VF–öæfÆw3Ö7&VF–öæfÆw2ÂVçcÖVçf—&öæÖVçBÀÐ¢7F'EöæWu÷6W76–öãÒ†÷2ææÖRÒvçBr’Ð¢Æöræ6Æ÷6R‚Ð¢–FVçF—G’ÒæöæPÐ¢f÷"ò–â&ævRƒ#“ Ð¢–b&ö6W72çöÆÂ‚’—2æ÷BæöæS Ð¢'&V°Ð¢–FVçF—G’Ò÷&ö6W75ö–FVçF—G’‡&ö6W72ç–BÐ¢–b–FVçF—G’—2æ÷BæöæS Ð¢'&V°Ð¢F–ÖRç6ÆVW‚ãÐ¢–b–FVçF—G’—2æöæS Ð¢G'“ Ð¢&ö6W72çFW&Ö–æFR‚Ð¢&ö6W72çv—B‡F–ÖV÷WCÓRÐ¢W†6WB„õ4W'&÷"Â7V'&ö6W72å7V'&ö6W74W'&÷"Â7V'&ö6W72åF–ÖV÷WDW‡—&VB“ Ð¢G'“ Ð¢&ö6W72æ¶–ÆÂ‚Ð¢W†6WBõ4W'&÷# Ð¢70Ð¢6VÆbç&Vv—7G&F–öåö†V'F&VE÷F‚çVæÆ–æ²†Ö—76–æuöö³ÕG'VRÐ¢&—6RÆ–fV7–6ÆTW'&÷"‚w&Vv—7G&F–öâv÷&¶W"&ö6W72–FVçF—G’6÷VÆBæ÷B&RfW&–f–VC²pÐ¢wF†Rv÷&¶W"v27F÷VB&Vf÷&RV&Æ—6†–ær”B&V6÷&BrÐ¢÷w&—FU÷&—fFR‡6VÆbç&Vv—7G&F–öå÷–E÷F‚Â§6öâæGV×2‡°Ð¢w–Bs¢&ö6W72ç–BÂwFö¶Vâs¢Fö¶VâÂw7F'FVBs¢F–ÖRçF–ÖR‚’ÀÐ¢v–FVçF—G’s¢–FVçF—G—Ò’²uÆârÐ¢f÷"ò–â&ævRƒS“ Ð¢7FGW2Ò6VÆbå÷&Vv—7G&F–öå÷v÷&¶W%÷7FGW2‚Ð¢–b7FGW2ævWB‚v†VÇF‡’r“ Ð¢&WGW&â&ö6W72ç–@Ð¢–b&ö6W72çöÆÂ‚’—2æ÷BæöæS Ð¢'&V°Ð¢F–ÖRç6ÆVW‚ãÐ¢&—6RÆ–fV7–6ÆTW'&÷"‚w&Vv—7G&F–öâv÷&¶W"f–ÆVBFòV&Æ—6‚†VÇF‡’†V'F&VC²pÐ¢v–ç7V7BW2rRÆöu÷F‚Ð Ð¢FVb÷7F÷÷&Vv—7G&F–öå÷v÷&¶W"‡6VÆb“ Ð¢–bæ÷B6VÆbç&Vv—7G&F–öå÷–E÷F‚æ—5öf–ÆR‚“ Ð¢&WGW&âfÇ6PÐ¢7FGW2Ò6VÆbå÷&Vv—7G&F–öå÷v÷&¶W%÷7FGW2‚Ð¢–bæ÷B7FGW2ævWB‚v–FVçF—G•÷fW&–f–VBr“ Ð¢6VÆbç&Vv—7G&F–öå÷–E÷F‚çVæÆ–æ²†Ö—76–æuöö³ÕG'VRÐ¢6VÆbç&Vv—7G&F–öåö†V'F&VE÷F‚çVæÆ–æ²†Ö—76–æuöö³ÕG'VRÐ¢&WGW&âfÇ6PÐ¢G'“ Ð¢–BÒ–çB‡7FGW5²w–BuÒÐ¢–b÷2ææÖRÓÒvçBs Ð¢7V'&ö6W72ç'Vâ…²wF6¶¶–ÆÂrÂrõ”BrÂ7G"‡–B’ÂrõBrÂrôbuÒÀÐ¢6GW&Uö÷WGWCÕG'VRÂF–ÖV÷WCÓÐ¢VÇ6S Ð¢÷2æ¶–ÆÇr‡–BÂ6–væÂå4”uDU$ÒÐ¢W†6WB„õ4W'&÷"ÂfÇVTW'&÷"Â7V'&ö6W72å7V'&ö6W74W'&÷"“ Ð¢70Ð¢6VÆbç&Vv—7G&F–öå÷–E÷F‚çVæÆ–æ²†Ö—76–æuöö³ÕG'VRÐ¢6VÆbç&Vv—7G&F–öåö†V'F&VE÷F‚çVæÆ–æ²†Ö—76–æuöö³ÕG'VRÐ¢&WGW&âG'VPÐ Ð¢FVb÷&ö&UöFW6·F÷2‡6VÆb“ Ð¢6VÆbå÷&WV—&UöFW6·F÷÷6W'f–6W2‡6VÆbåöFW6·F÷÷6W'f–6W2‚’Ð¢÷WBÒ6VÆbåö6ö×÷6R‚vwV6ÖöÆRrÂvW†V2rÂrÕBrÂvFF&6RrÂw7ÂrÂrÕRrÂvwV6ÖöÆRrÀÐ¢rÖBrÂvwV6ÖöÆRrÂr×DrÂrÖ2rÀÐ¢u4TÄT5B6÷VçB‚¢’e$ôÒwV6ÖöÆUö6öææV7F–öârÐ¢G'“ Ð¢6÷VçBÒ–çB†÷WBç7G&—‚’ç7Æ—FÆ–æW2‚•²ÓÒÐ¢W†6WB…fÇVTW'&÷"Â–æFW„W'&÷"“ Ð¢&—6RÆ–fV7–6ÆTW'&÷"‚v6÷VÆBæ÷B&VBwV6ÖöÆUö6öææV7F–öâ6÷VçC¢W"rR÷WE³£#ÒÐ¢W‡V7FVBÒ†ÆVâ‡6VÆbç&öf–ÆU²vFW6·F÷2uÒÐ¢–b6VÆbç&öf–ÆRævWB‚w&Vv—7G&F–öârÂ·Ò’ævWB‚vVæ&ÆVBrÂfÇ6RÐ¢VÇ6RÆVâ‡6VÆbçFV×2’Ð¢–b6÷VçBÂW‡V7FVC Ð¢&—6RÆ–fV7–6ÆTW'&÷"‚vwV6ÖöÆR†2VB6öææV7F–öç2f÷"VBFW6·F÷6Æ÷G3²&÷f—6–öæ–ær5ÂpÐ¢wv2æ÷BÆ–VBrR†6÷VçBÂW‡V7FVB’Ð¢&WGW&â²vFW6·F÷2s¢W‡V7FVBÂv6öææV7F–öç2s¢6÷VçGÐÐ Ð¢23bÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒWf–FVæ6PÐ¢FVbö–æFW…öæÖR‡6VÆb“ Ð¢æÖRÒ6VÆbæÆö6ÂævWB‚v–æFW…öæÖRr’÷"w6–ÆVçB×&–FvRÒr²6VÆbæWfVçBç&WÆ6R‚w6–ÆVçB×&–FvRÒrÂrrÐ¢g&öÒ&–FvRçv§V…÷&÷f—6–öâ–×÷'BfÆ–FFUö–æFW…öæÖPÐ¢&WGW&âfÆ–FFUö–æFW…öæÖR†æÖRÐ Ð¢FVb÷v§V‚‡6VÆbÂÖWF†öBÂ&6RÂF‚Â7&VFVçF–ÂÂ&öG“ÔæöæRÂ†VFW'3ÔæöæR“ Ð¢7FGW2Â–ÆöBÒ6VÆbæ†÷7Bçv§V…÷&WVW7B€Ð¢ÖWF†öBÂ&6R²F‚Â6VÆbå÷'F–6—çEö6öf–ÆR‚’ÀÐ¢7&VFVçF–ÂÂ&öG’Â†VFW'3Ö†VFW'2Ð¢&WGW&â7FGW2Â–Æö@Ð Ð¢FVbö–æFW†W%ö¦ö"‡6VÆbÂ7F–öâÂ&6·WöF—#ÔæöæR“ Ð¢""%'VâÇ’÷&ö&RöGV×öÆöB–ç6–FRF†R–çFVw&F–öâ–ÖvRöâF†Rv§V€Ð¢&6¶VæBæWGv÷&²àÐ Ð¢F†R–æFW†W"—2öââ–çFW&æÃ¢G'VVæWGv÷&²v—F‚æò†÷7B×V&Æ—6†VB÷'BÀÐ¢6ò–æFW†W"G&ff–2×W7B6öÖRg&öÒ6öçF–æW"ÂæWfW"g&öÒF†R†÷7BàÐ¢"" Ð¢–æFW…öæÖRÒ6VÆbåö–æFW…öæÖR‚Ð¢æWGv÷&²Ò6VÆbæWfVçB²r×v§V…÷v§V‚Ö&6¶VæBpÐ¢&wbÒ²vFö6¶W"rÂw'VârÂrÒ×&ÒrÂrÒÖæWGv÷&²rÂæWGv÷&²ÀÐ¢rÖRrÂut¥T…ô”äDU„U%õU$ÃÖ‡GG3¢ò÷v§V‚Ö–æFW†W#£“#rÀÐ¢r×brÂ7G"…$ôõBòw&–FvRr’²s¢ö÷B÷6–ÆVçB×&–FvR÷&–FvS§&òrÀÐ¢r×brÂ7G"‡6VÆbç'VçF–ÖRòwv§V‚Ö6W'G2r’²s¢ö6W'G3§&òrÀÐ¢r×brÂ7G"‡6VÆbç6V7&WG5öF—"’²s¢÷6V7&WG3§&òrÀÐ¢r×brÂ7G"‡6VÆbæ76WB‚vWf–FVæ6U÷V&Æ–2r’’²s¢öWf–FVæ6S§&òuÐÐ¢–b&6·WöF—"—2æ÷BæöæS Ð¢&wb³Ò²r×brÂ7G"…F‚†&6·WöF—"’ç&W6öÇfR‚’’²s¢ö&6·WuÐÐ¢&wb³Ò²rÒÖVçG'—ö–çBrÂw—F†öârÂw6–ÆVçB×&–FvRÖ–çFVw&F–öã¦FWbrÀÐ¢rÖÒrÂw&–FvRæFWÆ÷’æ–æFW†W%ö¦ö"rÂ7F–öâÂ–æFW…öæÖUÐÐ¢÷WBÒ6VÆbå÷'Vâ†&wbÐ¢G'“ Ð¢&WGW&â§6öâæÆöG2†÷WBç7G&—‚’ç7Æ—FÆ–æW2‚•²ÓÒÐ¢W†6WB…fÇVTW'&÷"Â–æFW„W'&÷"“ Ð¢&—6RÆ–fV7–6ÆTW'&÷"‚v–æFW†W"¦ö"W2&WGW&æVBæò¥4ôâ&W7VÇC¢W2pÐ¢R†7F–öâÂ÷WBç7G&—‚•²Ó3¥Ò’Ð Ð¢FVböÇ•öWf–FVæ6R‡6VÆb“ Ð¢g&öÒ&–FvRçv§V…÷&÷f—6–öâ–×÷'B6fVEöö&¦V7G0Ð¢–æFW…öæÖRÒ6VÆbåö–æFW…öæÖR‚Ð¢Æ–VBÒ6VÆbåö–æFW†W%ö¦ö"‚vÇ’rÐ¢2&V6‚F†RF6†&ö&BöâF†RFG&W72—B—27GVÆÇ’V&Æ—6†VBöââ—B—0Ð¢2&÷VæBFòÆö6Âæ§6öâw2&–æEö—Âæ÷BæV6W76&–Ç’Æö÷&6²Â6ò†&F6öFV@Ð¢2#rãããf–Ç2v—F‚T4ôäå$TeU4TBöâ†÷7BF†B&–æG2ÄâFG&W72àÐ¢F6†&ö&BÒ6VÆbå÷V&Æ–5÷W&Â‡6VÆbå÷6W'f–6Uö†÷7G2‚•²wv§V‚uÒÀÐ¢6VÆbå÷V&Æ–5÷÷'B‚wv§V‚rÂƒCC2’Ð¢FÖ–âÒ6VÆbå÷6V7&WB‚wv§V…öFÖ–ârÐ¢f÷"f–Wr–â6fVEöö&¦V7G2†Æ–VE²vf–VÆEö62uÒ“ Ð¢7FGW2Â–ÆöBÒ6VÆbå÷v§V‚€Ð¢uõ5BrÂF6†&ö&BÀÐ¢rö’÷6fVEöö&¦V7G2ö–æFW‚×GFW&âòW3ö÷fW'w&—FS×G'VRrRf–Wu²v–BuÒÀÐ¢FÖ–âÂ²vGG&–'WFW2s¢f–Wu²vGG&–'WFW2u×ÒÂ†VFW'3×²v÷6B×‡7&bs¢wG'VRwÒÐ¢–b7FGW2Ò# Ð¢&—6RÆ–fV7–6ÆTW'&÷"‚w6fVBf–WrW2f–ÆVBv—F‚…EEW3¢W2pÐ¢R‡f–Wu²v–BuÒÂ7FGW2Â7G"‡–ÆöB•³£#Ò’Ð¢&WGW&â²v–æFW‚s¢–æFW…öæÖWÐÐ Ð¢FVb÷&ö&UöWf–FVæ6R‡6VÆb“ Ð¢–æFW…öæÖRÒ6VÆbåö–æFW…öæÖR‚Ð¢&W7VÇBÒ6VÆbåö–æFW†W%ö¦ö"‚w&ö&RrÐ¢7FGW2Â–ÆöBÒ&W7VÇE²w7FGW2uÒÂ²v6÷VçBs¢&W7VÇBævWB‚v6÷VçBrÂ—ÐÐ¢–b7FGW2Ò# Ð¢&—6RÆ–fV7–6ÆTW'&÷"‚v†—7F÷&–6Â–æFW‚W2Væf–Æ&ÆR„…EEW2“²'VâWFòpÐ¢w&V6öæ6–ÆRWf–FVæ6RrR†–æFW…öæÖRÂ7FGW2’Ð¢G'“ Ð¢6VÆbåö6ö×÷6R‚wv§V‚rÂvW†V2rÂrÕBrÂwv§V‚ÖÖævW"rÂvf–ÆV&VBrÀÐ¢wFW7BrÂv÷WGWBrÂrÖ2rÂröWF2öf–ÆV&VBöf–ÆV&VBç–ÖÂrÐ¢W†6WBW†6WF–öâ2W†3 Ð¢&—6RÆ–fV7–6ÆTW'&÷"‚tf–ÆV&VB6ææ÷BWF†VçF–6FRFòF†R4×fW&–f–VBv§V‚pÐ¢v–æFW†W#¢W2rR7G"†W†2•³£#SÒÐ¢FVÆVÖWG'’Ò6VÆbæ76WB‚vWf–FVæ6U÷V&Æ–2r’òwv§V‚ròwFVÆVÖWG'’æ§6öæÂpÐ¢–bFVÆVÖWG'’æ—5öf–ÆR‚“ Ð¢2&–FvRæWf–FVæ6U÷&VÆV6Ræ–æFW‚FW&—fW2V6‚Fö7VÖVçB”Bg&öÒÐ¢26æöæ–6Â†6‚öbF†R&V6÷&B&öG’Â6òGWÆ–6FRÆ–æW26öÆÆ6PÐ¢2FòöæRFö7VÖVçB'’FW6–vã²W‡V7BVæ—VR&V6÷&G2Âæ÷B&rÆ–æW2àÐ¢&öF–W2Ò¶§6öâæGV×2†§6öâæÆöG2†Æ–æR’Â6÷'Eö¶W—3ÕG'VRÐ¢f÷"Æ–æR–âFVÆVÖWG'’ç&VE÷FW‡B†Væ6öF–æsÒwWFbÓ‚r’ç7Æ—FÆ–æW2‚Ð¢–bÆ–æRç7G&—‚—ÐÐ¢W‡V7FVBÒÆVâ†&öF–W2Ð¢–b–ÆöBævWB‚v6÷VçBrÂ’ÂW‡V7FVC Ð¢&—6RÆ–fV7–6ÆTW'&÷"‚v†—7F÷&–6Â–æFW‚†2VBFö7VÖVçG3²W‡V7FVBBÆV7BVBpÐ¢vg&öÒW2rR‡–ÆöBævWB‚v6÷VçBrÂ’ÂW‡V7FVBÂFVÆVÖWG'’’Ð¢g&öÒ&–FvRæFö6¶W%÷&÷f–FW"–×÷'BFVÕ÷6W'f–6PÐ¢–b6VÆbç&öf–ÆRævWB‚w&Vv—7G&F–öârÂ·Ò’ævWB‚vVæ&ÆVBrÂfÇ6R“ Ð¢&WGW&â²vFVfW'&VBs¢vFW6·F÷Wf–FVæ6R&ö&R'Vç2gFW"V6‚FVÒ&Vv—7G&F–öâwÐÐ¢f÷"’–â&ævR†ÆVâ‡6VÆbçFV×2’“ Ð¢6W'f–6RÒFVÕ÷6W'f–6R‚wFVÒS&BrR†’²’Ð¢v÷&¶W%ö–BÒ6VÆbåöFW6·F÷÷7V2‡6W'f–6R’ævWB‚wv÷&¶W"rÂvÆö6ÂrÐ¢÷WBÒ6VÆbåöFW6·F÷ö6ö×÷6R€Ð¢v÷&¶W%ö–BÂvW†V2rÂrÕBrÂ6W'f–6RÂv&6‚rÂrÖ2rÀÐ¢vÇ2öWf–FVæ6RöæWGv÷&²÷6Vç6÷"ç6öWf–FVæ6R÷v§V‚÷FVÆVÖWG'’æ§6öæÂrÀÐ¢6†V6³ÔfÇ6RÐ¢–bw6Vç6÷"ç6ræ÷B–â÷WC Ð¢&—6RÆ–fV7–6ÆTW'&÷"‚vWf–FVæ6R—2æ÷Bf—6–&ÆRöâFW6·F÷W2VæFW"öWf–FVæ6RpÐ¢R6W'f–6RÐ¢&WGW&â²v–æFW‚s¢–æFW…öæÖRÂvFö7VÖVçG2s¢–ÆöBævWB‚v6÷VçBrÂ—ÐÐ Ð¢23rÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒ&÷f—6–öæVB×W6V@Ð¢FVbö6öçG&öÆÆW%ö6öæf–r‡6VÆb“ Ð¢–b6VÆbç&öf–ÆRævWB‚w&Vv—7G&F–öârÂ·Ò’ævWB‚vVæ&ÆVBrÂfÇ6R“ Ð¢&Vv—7G&F–öâÒ6VÆbç&öf–ÆU²w&Vv—7G&F–öâuÐÐ¢&WGW&â°Ð¢vW†W&6—6UöFFRs¢6VÆbç&öf–ÆU²vWfVçBuÕ²v–æ6–FVçEöFFRuÒÀÐ¢wFV×2s¢µÒÀÐ¢w&Vv—7G&F–öâs¢°Ð¢vVæ&ÆVBs¢G'VRÂvÖ…÷FV×2s¢&Vv—7G&F–öå²vÖ…÷FV×2uÒÀÐ¢vÖVÖ&W'5÷W%÷FVÒs¢&Vv—7G&F–öå²vÖVÖ&W'5÷W%÷FVÒuÒÀÐ¢vFW6·F÷5÷W%÷FVÒs¢&Vv—7G&F–öå²vFW6·F÷5÷W%÷FVÒuÒÀÐ¢ÒÀÐ¢ÐÐ¢F—66÷fW&VBÒ§6öâæÆöG2‡6VÆbæF—66÷fW&VE÷F‚ç&VE÷FW‡B†Væ6öF–æsÒwWFbÓ‚r’Ð¢7&VFVçF–Ç2Ò6VÆbå÷FVÕö7&VFVçF–Ç2‚Ð¢FV×2ÒµÐÐ¢f÷"FVÒ–â6VÆbçFV×3 Ð¢–G2ÒF—66÷fW&VE²wFV×2uÕ·FVÕ²væÖRuÕÐÐ¢FV×2æVæB‡²v–Bs¢FVÕ²væÖRuÒÂvæÖRs¢FVÕ²væÖRuÒÀÐ¢v—&—2s¢7G"†–G5²v—&—5ö–BuÒ’Âv7FfBs¢–çB†–G5²v7FfEö–BuÒ’ÀÐ¢v—&—5öÆöv–âs¢7&VFVçF–Ç5²wFV×2uÕ·FVÕ²væÖRuÕÕ²v—&—5öÆöv–âuÒÀÐ¢v7FfEöæÖRs¢7&VFVçF–Ç5²wFV×2uÕ·FVÕ²væÖRuÕÕ²v7FfEöæÖRu×ÒÐ¢&WGW&â²vW†W&6—6UöFFRs¢6VÆbç&öf–ÆU²vWfVçBuÕ²v–æ6–FVçEöFFRuÒÂwFV×2s¢FV×7ÐÐ Ð¢FVböÇ•÷&÷f—6–öæVB‡6VÆb“ Ð¢6VÆbç7FFUöF—"æÖ¶F—"‡&VçG3ÕG'VRÂW†—7Eöö³ÕG'VRÐ¢6öæf–u÷F‚Ò6VÆbç7FFUöF—"òv6öæf–ræ§6öâpÐ¢–b6öæf–u÷F‚æ—5öf–ÆR‚’æB6VÆbç7FFU÷F‚æ—5öf–ÆR‚“ Ð¢2F÷FVB'VçF–ÖS¢æWfW"&Ww&—FRÆ—fR6öçG&öÆÆW"6öæf–r÷"7FFRàÐ¢6öæf–rÒ§6öâæÆöG2†6öæf–u÷F‚ç&VE÷FW‡B†Væ6öF–æsÒwWFbÓ‚r’Ð¢VÇ6S Ð¢6öæf–rÒ6VÆbåö6öçG&öÆÆW%ö6öæf–r‚Ð¢6öæf–u÷F‚çw&—FU÷FW‡B†§6öâæGV×2†6öæf–rÂ–æFVçCÓ"’ÂVæ6öF–æsÒwWFbÓ‚rÐ¢–bæ÷B6VÆbç7FFU÷F‚æ—5öf–ÆR‚“ Ð¢F–6¶WG2Ò6VÆbæ†÷7BæWF†÷%÷F–6¶WG2†6öæf–rÐ¢6VÆbæ†÷7Bç7FFR‡6VÆbç7FFU÷F‚’æ–æ—F–Æ—¦R€Ð¢6öæf–u²wFV×2uÒÂF–6¶WG2ÀÐ¢ÆÆ÷uöV×G“×6VÆbç&öf–ÆRævWB‚w&Vv—7G&F–öârÂ·Ò’ævWB‚vVæ&ÆVBrÂfÇ6R’Ð¢6VÆbåö6ö×÷6R‚v–çFVw&F–öârÂwWrÂrÖBrÂrÒ×v—BrÂrÒ×v—B×F–ÖV÷WBrÂs3rÐ¢7FFRÒ6VÆbæ†÷7Bç7FFR‡6VÆbç7FFU÷F‚Ð¢v—F‚7FFRçG&ç67F–öâ‡w&—FSÔfÇ6R’26öã Ð¢&÷f—6–öæVBÒ6öâæW†V7WFR‚u4TÄT5B&÷f—6–öæVBe$ôÒ6öçG&öÂr’æfWF6†öæR‚•³ÐÐ¢–bæ÷B&÷f—6–öæVC Ð¢7FFRç&÷f—6–öâ‡6VÆbæ÷W&F÷"Ð Ð¢FVbö6öçG&öÆÆW%÷&VfÆ–v‡B‡6VÆb“ Ð¢""%'VâF†R&VÂ6öçG&öÆÆW"&VfÆ–v‡B–ç6–FRF†R–çFVw&F–öâ6öçF–æW"àÐ Ð¢F†R6öçF–æW"7ç2F†R6VçG&ÂæBv§V‚&6¶VæBæWGv÷&·2æB6'&–W0Ð¢F†R'&–FvR6V7&WG3²F†R†÷7B6â&V6‚æV—F†W"F†R–çFW&æÂ•$•2ô5Df@Ð¢U$Ç2æ÷"F†R–æFW†W"àÐ¢"" Ð¢G'“ Ð¢÷WBÒ6VÆbåö6ö×÷6R‚v–çFVw&F–öârÂvW†V2rÂrÕBrÂv–çFVw&F–öârÀÐ¢w—F†öârÂrÖÒrÂw&–FvRæ6Æ’rÂrÒ×7FFRrÂr÷7FFR÷7FFRç7Æ—FRrÀÐ¢w&VfÆ–v‡BrÂrÒÖ6öæf–rrÂr÷7FFRö6öæf–ræ§6öârÐ¢W†6WBW†6WF–öâ2W†3 Ð¢&—6RÆ–fV7–6ÆTW'&÷"‚v6öçG&öÆÆW"&VfÆ–v‡B6÷VÆBæ÷B'Vã¢W2rRW†2Ð¢G'“ Ð¢&WGW&â§6öâæÆöG2†÷WBç7G&—‚’ç7Æ—FÆ–æW2‚•²ÓÒÐ¢W†6WB…fÇVTW'&÷"Â–æFW„W'&÷"“ Ð¢&—6RÆ–fV7–6ÆTW'&÷"‚v6öçG&öÆÆW"&VfÆ–v‡B&WGW&æVBæò¥4ôâ&W7VÇC¢W2pÐ¢R÷WBç7G&—‚•²Ó3¥ÒÐ Ð¢FVb÷&ö&UöW†W&6—6R‡6VÆbÂW‡V7FVEöÖöFR“ Ð¢–bæ÷B6VÆbç7FFU÷F‚æ—5öf–ÆR‚“ Ð¢&—6RÆ–fV7–6ÆTW'&÷"‚vW†W&6—6R7FFRW2—2Ö—76–æs²'VâWrR6VÆbç7FFU÷F‚Ð¢7FFRÒ6VÆbæ†÷7Bç7FFR‡6VÆbç7FFU÷F‚Ð¢ÖöFRÒ6VÆbå÷7FFUöÖöFR‡7FFRÐ¢–bÖöFRÒW‡V7FVEöÖöFS Ð¢&—6RÆ–fV7–6ÆTW'&÷"‚&W†W&6—6RÖöFR—2W"ÂW‡V7FVBW""R†ÖöFRÂW‡V7FVEöÖöFR’Ð¢6öæf–rÒ§6öâæÆöG2‚‡6VÆbç7FFUöF—"òv6öæf–ræ§6öâr’ç&VE÷FW‡B†Væ6öF–æsÒwWFbÓ‚r’Ð¢&VG’Ò6VÆbåö6öçG&öÆÆW%÷&VfÆ–v‡B‚Ð¢–b&VG’ævWB‚w&VG’r’—2æ÷BG'VS Ð¢&—6RÆ–fV7–6ÆTW'&÷"‚v6öçG&öÆÆW"&VfÆ–v‡Bf–ÆVC¢W2rR&VG’Ð¢6W'f–6W2Ò6VÆbå÷2‚v–çFVw&F–öârÐ¢6öçG&öÆÆW"Ò6W'f–6W2ævWB‚v–çFVw&F–öârÐ¢–b6öçG&öÆÆW"—2æöæR÷"6öçG&öÆÆW%²w7FFRuÒÒw'Vææ–ærs Ð¢&—6RÆ–fV7–6ÆTW'&÷"‚v–çFVw&F–öâ6öçG&öÆÆW"—2æ÷B'Vææ–æs²'VâWFò&V6öæ6–ÆRrÐ¢&WGW&â²vÖöFRs¢ÖöFRÂwFV×2s¢&VG’ævWB‚wFV×2r’ÂwF–6¶WG2s¢&VG’ævWB‚wF–6¶WG2r—ÐÐ Ð¢FVb÷&ö&U÷&÷f—6–öæVB‡6VÆb“ Ð¢&WGW&â6VÆbå÷&ö&UöW†W&6—6R‚wW6VBrÐ Ð¢FVb÷&ö&U÷'Vææ–ær‡6VÆb“ Ð¢&WGW&â6VÆbå÷&ö&UöW†W&6—6R‚w'Vææ–ærrÐ Ð¢FVb÷7FFUöÖöFR‡6VÆbÂ7FFR“ Ð¢v—F‚7FFRçG&ç67F–öâ‡w&—FSÔfÇ6R’26öã Ð¢&WGW&â6öâæW†V7WFR‚u4TÄT5BÖöFRe$ôÒ'Vâr’æfWF6†öæR‚•³ÐÐ Ð¢FVb÷7FFU÷VæF–ær‡6VÆbÂ7FFR“ Ð¢v—F‚7FFRçG&ç67F–öâ‡w&—FSÔfÇ6R’26öã Ð¢&WGW&â6öâæW†V7WFR‚u4TÄT5B4õTåB‚¢’e$ôÒ÷WF&÷‚t„U$RFöæSÓr’æfWF6†öæR‚•³ÐÐ Ð¢2ÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÒÆ–fV7–6ÆPÐ Ð¢FVbö¦÷W&æÂ‡6VÆbÂ&VÆV6Uöf–ævW'&–çB“ Ð¢F‚Ò6VÆbç'VçF–ÖRòvFWÆ÷’Ö¦÷W&æÂç7Æ—FRpÐ¢–bF‚æ—5öf–ÆR‚’æBF‚ç7FB‚’ç7E÷6—¦S Ð¢¦÷W&æÂÒ¦÷W&æÂæ÷Vâ‡F‚Ð¢¦÷W&æÂæ6†V6µöf–ævW'&–çG2‡6VÆbç&öf–ÆRÂ6VÆbç&öf–ÆU²vWfVçBuÕ²w&VÆV6Uö–BuÒÀÐ¢&VÆV6Uöf–ævW'&–çBÐ¢&WGW&â¦÷W&æÀÐ¢&WGW&â¦÷W&æÂæ7&VFR‡F‚Â6VÆbç&öf–ÆRÂ6VÆbç&öf–ÆU²vWfVçBuÕ²w&VÆV6Uö–BuÒÀÐ¢&VÆV6Uöf–ævW'&–çBÐ Ð¢FVb÷7FvUö÷2‡6VÆbÂ7FvR“ Ð¢&WGW&â°Ð¢t%D”d5E5õdU$”d”TBs¢„æöæRÂ6VÆbå÷&ö&Uö'F–f7G2’ÀÐ¢t”äe$5E%T5EU$Uõ$TE’s¢‡6VÆbåöÇ•ö–æg&7G'V7GW&RÂ6VÆbå÷&ö&Uö–æg&7G'V7GW&R’ÀÐ¢tÄ”4D”ôå5õ$TE’s¢‡6VÆbåöÇ•öÆ–6F–öç2Â6VÆbå÷&ö&UöÆ–6F–öç2’ÀÐ¢t”DTåD•D”U5õ$TE’s¢‡6VÆbåöÇ•ö–FVçF—F–W2Â6VÆbå÷&ö&Uö–FVçF—F–W2’ÀÐ¢tDU4µDõ5õ$TE’s¢‡6VÆbåöÇ•öFW6·F÷2Â6VÆbå÷&ö&UöFW6·F÷2’ÀÐ¢tUd”DTä4Uõ$TE’s¢‡6VÆbåöÇ•öWf–FVæ6RÂ6VÆbå÷&ö&UöWf–FVæ6R’ÀÐ¢u$õd•4”ôäTEõU4TBs¢‡6VÆbåöÇ•÷&÷f—6–öæVBÂ6VÆbå÷&ö&U÷&÷f—6–öæVB’ÀÐ¢Õ·7FvUÐÐ Ð¢FVbW‡6VÆbÂ&VÆV6Uöf–ævW'&–çB“ Ð¢""$'&–ærF†R'VâFò$õd•4”ôäTEõU4TBâ&WVF–ær&W6W'fW27FFS²fW&–f–V@Ð¢7FvRv†÷6R&ö&Ræ÷rf–Ç2—2â7F–öæ&ÆRW'&÷"ÂæWfW"&W6WBâ"" Ð¢6VÆbç&VÆV6Uöf–ævW'&–çBÒ&VÆV6Uöf–ævW'&–ç@Ð¢¦÷W&æÂÒ6VÆbåö¦÷W&æÂ‡&VÆV6Uöf–ævW'&–çBÐ¢v—F‚¦÷W&æÂæÆö6²‡6VÆbæ÷W&F÷"“ Ð¢&W7VÖ&ÆRÒ¦÷W&æÂç7FFRÓÒu5DõTBpÐ¢7VÖÖ'’Ò·ÐÐ¢f÷"7FvR–â6VÆbå5DtU3 Ð¢Ç’Â&ö&RÒ6VÆbå÷7FvUö÷2‡7FvRÐ¢7FWÒ¦÷W&æÂç7FW‡7FvRÐ¢–b7FWæB7FW²w7FFRuÒÓÒwfW&–f–VBs Ð¢G'“ Ð¢7VÖÖ'•·7FvUÒÒ&ö&R‚Ð¢6öçF–çVPÐ¢W†6WBÆ–fV7–6ÆTW'&÷"2W†3 Ð¢–bæ÷B&W7VÖ&ÆS Ð¢&—6RÆ–fV7–6ÆTW'&÷"€Ð¢w&Wf–÷W6Ç’fW&–f–VB7FvRW2æòÆöævW"fW&–f–W3¢W2âF†RpÐ¢vÖ—76–ær÷"6†ævVB&W6÷W&6R×W7B&R&W7F÷&VC²Wv–ÆÂæ÷BpÐ¢w&V7&VFR—B6–ÆVçFÇ’rR‡7FvRÂW†2’Ð¢2gFW"â–çFVçF–öæÂF÷væÂ7F÷VB&W6÷W&6W2&RW‡V7FVC Ð¢2&RÖÇ’æB&R×fW&–g’&F†W"F†â&VgW6–æràÐ¢¦÷W&æÂç&V÷Vå÷7FW‡7FvRÐ¢G'“ Ð¢–bÇ’—2æ÷BæöæS Ð¢Ç’‚Ð¢7VÖÖ'•·7FvUÒÒ&ö&R‚Ð¢¦÷W&æÂæ6ö×ÆWFU÷7FW‡7FvRÂ§6öâæGV×2‡7VÖÖ'•·7FvUÒÀÐ¢6÷'Eö¶W—3ÕG'VR•³£CÒÐ¢W†6WBW†6WF–öâ2W†3# Ð¢¦÷W&æÂæf–Å÷7FW‡7FvRÂW†3"Ð¢&—6PÐ¢6öçF–çVPÐ¢¦÷W&æÂæ&Vv–å÷7FW‡7FvRÐ¢G'“ Ð¢–bÇ’—2æ÷BæöæS Ð¢Ç’‚Ð¢FWF–ÂÒ&ö&R‚Ð¢¦÷W&æÂæ6ö×ÆWFU÷7FW‡7FvRÂ§6öâæGV×2†FWF–ÂÂ6÷'Eö¶W—3ÕG'VR•³£CÒÐ¢7VÖÖ'•·7FvUÒÒFWF–ÀÐ¢W†6WBW†6WF–öâ2W†3 Ð¢¦÷W&æÂæf–Å÷7FW‡7FvRÂW†2Ð¢&—6PÐ¢¦÷W&æÂç6WE÷7FFR‚u$õd•4”ôäTEõU4TBrÐ¢&WGW&â²w7FFRs¢¦÷W&æÂç7FFRÂw7FvW2s¢7VÖÖ'—ÐÐ Ð¢FVb÷&WV—&U÷W6VB‡6VÆbÂ7F–öâ“ Ð¢G'“ Ð¢¦÷W&æÂÒ¦÷W&æÂæ÷Vâ‡6VÆbç'VçF–ÖRòvFWÆ÷’Ö¦÷W&æÂç7Æ—FRrÐ¢W†6WB¦÷W&æÄW'&÷"2W†3 Ð¢&—6RÆ–fV7–6ÆTW'&÷"‚rW2&WV—&W2FWÆ÷–ÖVçB¦÷W&æÃ²'Vâ—F†öâÖÒpÐ¢w&–FvRæFWÆ÷’Wf—'7B‚W2’rR†7F–öâÂW†2’Ð¢–b¦÷W&æÂç7FFRÒu$õd•4”ôäTEõU4TBs Ð¢&—6RÆ–fV7–6ÆTW'&÷"‚rW2&WV—&W2¦÷W&æÂ7FFR$õd•4”ôäTEõU4TBÂf÷VæBW3²pÐ¢w'Vâ—F†öâÖÒ&–FvRæFWÆ÷’Wf—'7BrR†7F–öâÂ¦÷W&æÂç7FFR’Ð¢f÷"7FW–â¦÷W&æÂç7FW2‚“ Ð¢–b7FW²w7FFRuÒÒwfW&–f–VBs Ð¢&—6RÆ–fV7–6ÆTW'&÷"‚rW2&VgW6VC¢7FvRW2—2W2â&W6öÇfR—Bv—F‚W²7F'BpÐ¢væWfW"6¶—2f–ÆVB6†V6·2rR†7F–öâÂ7FW²væÖRuÒÂ7FW²w7FFRuÒ’Ð¢&WGW&â¦÷W&æÀÐ Ð¢FVb7F'B‡6VÆbÂ&VÆV6Uöf–ævW'&–çB“ Ð¢""$W‡Æ–6—FÇ’7F'BF†RW†W&6—6RâöæÇ’'Vç2gFW"gVÆÂ&VF–æW72â"" Ð¢¦÷W&æÂÒ6VÆbå÷&WV—&U÷W6VB‚w7F'BrÐ¢¦÷W&æÂæ6†V6µöf–ævW'&–çG2‡6VÆbç&öf–ÆRÂ6VÆbç&öf–ÆU²vWfVçBuÕ²w&VÆV6Uö–BuÒÀÐ¢&VÆV6Uöf–ævW'&–çBÐ¢v—F‚¦÷W&æÂæÆö6²‡6VÆbæ÷W&F÷"“ Ð¢2&R×&ö&RWfW'’7FvS¢7F'B—2&VgW6VBv†Vâç’vFRf–Ç2æ÷ràÐ¢f÷"7FvR–â6VÆbå5DtU3 Ð¢òÂ&ö&RÒ6VÆbå÷7FvUö÷2‡7FvRÐ¢&ö&R‚Ð¢7FFRÒ6VÆbæ†÷7Bç7FFR‡6VÆbç7FFU÷F‚Ð¢&VG’Ò6VÆbåö6öçG&öÆÆW%÷&VfÆ–v‡B‚Ð¢–b&VG’ævWB‚w&VG’r’—2æ÷BG'VS Ð¢&—6RÆ–fV7–6ÆTW'&÷"‚w7F'B&VgW6VC¢&VfÆ–v‡Bf–ÆVC¢W2rR&VG’Ð¢7FFRæÖöFR‡6VÆbæ÷W&F÷"Âw'Vææ–ærrÐ¢7GVÂÒ6VÆbå÷7FFUöÖöFR‡7FFRÐ¢–b7GVÂÒw'Vææ–ærs Ð¢&—6RÆ–fV7–6ÆTW'&÷"‚&ÖöFRG&ç6—F–öâF–Bæ÷BW'6—7B†f÷VæBW"’"R7GVÂÐ¢G'“ Ð¢v÷&¶W"Ò6VÆbå÷7F'E÷&Vv—7G&F–öå÷v÷&¶W"‚Ð¢W†6WBW†6WF–öã Ð¢7FFRæÖöFR‡6VÆbæ÷W&F÷"ÂwW6VBrÐ¢&—6PÐ¢¦÷W&æÂç6WE÷7FFR‚u%Tää”ärrÐ¢&WGW&â²w7FFRs¢u%Tää”ärrÂvÖöFRs¢7GVÂÂ¢¢‡²w&Vv—7G&F–öå÷v÷&¶W%÷–Bs¢v÷&¶W'ÐÐ¢–bv÷&¶W"VÇ6R·Ò—ÐÐ Ð¢FVbW6R‡6VÆb“ Ð¢¦÷W&æÂÒ¦÷W&æÂæ÷Vâ‡6VÆbç'VçF–ÖRòvFWÆ÷’Ö¦÷W&æÂç7Æ—FRrÐ¢v—F‚¦÷W&æÂæÆö6²‡6VÆbæ÷W&F÷"“ Ð¢6VÆbå÷7F÷÷&Vv—7G&F–öå÷v÷&¶W"‚Ð¢7FFRÒ6VÆbæ†÷7Bç7FFR‡6VÆbç7FFU÷F‚Ð¢&Vf÷&RÒ6VÆbå÷7FFUöÖöFR‡7FFRÐ¢7FFRæÖöFR‡6VÆbæ÷W&F÷"ÂwW6VBrÐ¢7GVÂÒ6VÆbå÷7FFUöÖöFR‡7FFRÐ¢–b7GVÂÒwW6VBs Ð¢&—6RÆ–fV7–6ÆTW'&÷"‚'W6RF–Bæ÷BW'6—7B†ÖöFR—2W"’"R7GVÂÐ¢–b¦÷W&æÂç7FFRÓÒu%Tää”ärs Ð¢¦÷W&æÂç6WE÷7FFR‚u$õd•4”ôäTEõU4TBrÐ¢&WGW&â²w&Wf–÷W2s¢&Vf÷&RÂvÖöFRs¢7GVÂÂw7FFRs¢¦÷W&æÂç7FFWÐÐ Ð¢FVb7FGW2‡6VÆb“ Ð¢""%G'WF†gVÂ7G'V7GW&VB7FGW3¢¦÷W&æÂf7G2ÇW2Æ—fR&R×&ö&W2â&ö&PÐ¢f–ÇW&R—2&W÷'FVBÂæWfW"†–FFVââ"" Ð¢Fö7VÖVçBÒ²vWfVçBs¢6VÆbæWfVçBÂv¦÷W&æÂs¢æöæRÂw7FW2s¢µÒÂvÆ—fRs¢·ÒÀÐ¢vWfVçE÷&VG’s¢fÇ6WÐÐ¢F‚Ò6VÆbç'VçF–ÖRòvFWÆ÷’Ö¦÷W&æÂç7Æ—FRpÐ¢¦÷W&æÂÒæöæPÐ¢–bF‚æ—5öf–ÆR‚’æBF‚ç7FB‚’ç7E÷6—¦S Ð¢¦÷W&æÂÒ¦÷W&æÂæ÷Vâ‡F‚Ð¢Fö7VÖVçE²v¦÷W&æÂuÒÒ¦÷W&æÂç7FFPÐ¢Fö7VÖVçE²w7FW2uÒÒ·²væÖRs¢5²væÖRuÒÂw7FFRs¢5²w7FFRuÒÀÐ¢vGFV×Bs¢5²vGFV×BuÒÂvFWF–Âs¢2ævWB‚vFWF–Âr—ÐÐ¢f÷"2–â¦÷W&æÂç7FW2‚•ÐÐ¢f÷"7FvR–â6VÆbå5DtU3 Ð¢òÂ&ö&RÒ6VÆbå÷7FvUö÷2‡7FvRÐ¢–b7FvRÓÒu$õd•4”ôäTEõU4TBræB¦÷W&æÂ—2æ÷BæöæRæB¦÷W&æÂç7FFRÓÒu%Tää”ärs Ð¢&ö&RÒ6VÆbå÷&ö&U÷'Vææ–æpÐ¢G'“ Ð¢Fö7VÖVçE²vÆ—fRuÕ·7FvUÒÒ²vö²s¢G'VRÂvFWF–Âs¢&ö&R‚—ÐÐ¢W†6WBW†6WF–öâ2W†3 Ð¢Fö7VÖVçE²vÆ—fRuÕ·7FvUÒÒ²vö²s¢fÇ6RÂvW'&÷"s¢7G"†W†2•³£3×ÐÐ¢–b6VÆbç7FFU÷F‚æ—5öf–ÆR‚“ Ð¢G'“ Ð¢W†W&6—6U÷7FFRÒ6VÆbæ†÷7Bç7FFR‡6VÆbç7FFU÷F‚Ð¢Fö7VÖVçE²vÆ—fRuÕ²vW†W&6—6RuÒÒ²vö²s¢G'VRÂvÖöFRs¢6VÆbå÷7FFUöÖöFR†W†W&6—6U÷7FFR’ÀÐ¢wVæF–ærs¢6VÆbå÷7FFU÷VæF–ær†W†W&6—6U÷7FFR—ÐÐ¢W†6WBW†6WF–öâ2W†3 Ð¢Fö7VÖVçE²vÆ—fRuÕ²vW†W&6—6RuÒÒ²vö²s¢fÇ6RÂvW'&÷"s¢7G"†W†2•³£3×ÐÐ¢–b6VÆbç&öf–ÆRævWB‚w&Vv—7G&F–öârÂ·Ò’ævWB‚vVæ&ÆVBrÂfÇ6R“ Ð¢v÷&¶W"Ò6VÆbå÷&Vv—7G&F–öå÷v÷&¶W%÷7FGW2‚Ð¢G'“ Ð¢g&öÒ&–FvRç&Vv—7G&F–öâ–×÷'B&Vv—7G&F–öä6öæf–rÂ&Vv—7G&F–öå7F÷&PÐ¢&Vv—7G&F–öå÷F‚Ò6VÆbç&Vv—7G&F–öåöF—"òw&Vv—7G&F–öç2ç7Æ—FRpÐ¢7F÷&RÒ&Vv—7G&F–öå7F÷&R€Ð¢7G"‡&Vv—7G&F–öå÷F‚’ÀÐ¢&Vv—7G&F–öä6öæf–r€Ð¢Ö…÷FV×3×6VÆbç&öf–ÆU²w&Vv—7G&F–öâuÕ²vÖ…÷FV×2uÒÀÐ¢ÖVÖ&W'5÷W%÷FVÓ×6VÆbç&öf–ÆU²w&Vv—7G&F–öâuÕ²vÖVÖ&W'5÷W%÷FVÒuÒ’ÀÐ¢Vç&öÆÆÖVçEö6öFS×6VÆbå÷6V7&WB‚w&Vv—7G&F–öâÖVç&öÆÆÖVçBÖ6öFRr’Ð¢÷6V7W&U÷&—fFR‡&Vv—7G&F–öå÷F‚Ð¢VæF–ærÒ7F÷&RæÆ—7B‚Ð¢v÷&¶W%²wVWVRuÒÒ°Ð¢wVæF–ærs¢7VÒ‡&÷u²w7FGW2uÓÓÒwVæF–ærrf÷"&÷r–âVæF–ær’ÀÐ¢w&÷f—6–öæ–ærs¢7VÒ‡&÷u²w7FGW2uÓÓÒw&÷f—6–öæ–ærrf÷"&÷r–âVæF–ær’ÀÐ¢væVVG5ö÷W&F÷"s¢7VÒ‡&÷u²w7FGW2uÓÓÒvæVVG5ö÷W&F÷"rf÷"&÷r–âVæF–ær—ÐÐ¢W†6WBW†6WF–öâ2W†3 Ð¢v÷&¶W"Ò²vVæ&ÆVBs¢G'VRÂv†VÇF‡’s¢fÇ6RÂvW'&÷"s¢7G"†W†2•³£3×ÐÐ¢'Vææ–æuöW‡V7FVBÒ¦÷W&æÂ—2æ÷BæöæRæB¦÷W&æÂç7FFRÓÒu%Tää”ärpÐ¢Fö7VÖVçE²vÆ—fRuÕ²w&Vv—7G&F–öå÷v÷&¶W"uÒÒ°Ð¢vö²s¢&ööÂ‡v÷&¶W"ævWB‚v†VÇF‡’r’’–b'Vææ–æuöW‡V7FVBVÇ6RG'VRÀÐ¢vFWF–Âs¢F–7B‡v÷&¶W"ÂW‡V7FVCÒw'Vææ–ærr–b'Vææ–æuöW‡V7FVBVÇ6Rw7F÷VBv†–ÆRW6VBr—ÐÐ¢7FW5öö²Ò†¦÷W&æÂ—2æ÷BæöæPÐ¢æBÆÂ‡5²w7FFRuÒÓÒwfW&–f–VBrf÷"2–â¦÷W&æÂç7FW2‚’’Ð¢&ö&W5öö²ÒÆÂ†VçG'’ævWB‚vö²r’f÷"VçG'’–âFö7VÖVçE²vÆ—fRuÒçfÇVW2‚’Ð¢Fö7VÖVçE²vWfVçE÷&VG’uÒÒ&ööÂ‡7FW5öö²æB&ö&W5öö°Ð¢æBFö7VÖVçE²vÆ—fRuÒævWB‚vW†W&6—6RrÂ·Ò’ævWB‚vö²r’Ð¢&WGW&âFö7VÖVç@Ð Ð¢FVbF÷vâ‡6VÆbÂföÇVÖW3ÔfÇ6R“ Ð¢""%7F÷WfW'’&ö¦V7BÂ&W6W'f–ærföÇVÖW2æB7FFRâv—F‚Ò×föÇVÖW2ÂÇ6ðÐ¢&VÖ÷fRWfVçBÖ÷væVBföÇVÖW2(	BFW7G'V7F—fRÂæB&VgW6VBVæÆW726ö×ÆWFVBÀÐ¢fW&–f–VB&V6÷fW'’6WBW†—7G2VæFW"'VçF–ÖRö&6·W2F†B7F–ÆÂÖF6†W2F†PÐ¢Æ—fRW†W&6—6R7FFRâ&÷F‚6†V6·2'Vâ$Tdõ$Rç—F†–ær—27F÷VC¢&VgW6V@Ð¢v—R×W7BæWfW"F¶RF†RWfVçBöffÆ–æRâ"" Ð¢¦÷W&æÂÒ¦÷W&æÂæ÷Vâ‡6VÆbç'VçF–ÖRòvFWÆ÷’Ö¦÷W&æÂç7Æ—FRrÐ¢v—F‚¦÷W&æÂæÆö6²‡6VÆbæ÷W&F÷"“ Ð¢–bföÇVÖW2æB6VÆbå÷&VÖ÷FU÷v÷&¶W%ö–G2‚“ Ð¢&VÖ÷FU÷föÇVÖW2ÒµÐÐ¢&Vf—‚Ò6VÆbæWfVçB²rÒpÐ¢f÷"v÷&¶W%ö–B–â6VÆbå÷&VÖ÷FU÷v÷&¶W%ö–G2‚“ Ð¢6öçFW‡BÒ6VÆbå÷v÷&¶W"‡v÷&¶W%ö–B•²vFö6¶W%ö6öçFW‡BuÐÐ¢æÖW2Ò6VÆbå÷'Vâ…°Ð¢vFö6¶W"rÂrÒÖ6öçFW‡BrÂ6öçFW‡BÂwföÇVÖRrÂvÇ2rÀÐ¢rÒÖf÷&ÖBrÂw·²äæÖW×ÒrÀÐ¢Ò’ç7Æ—FÆ–æW2‚Ð¢&VÖ÷FU÷föÇVÖW2æW‡FVæB‚rW3¢W2rR‡v÷&¶W%ö–BÂæÖRÐ¢f÷"æÖR–âæÖW2–bæÖRç7F'G7v—F‚‡&Vf—‚’Ð¢–b&VÖ÷FU÷föÇVÖW3 Ð¢&—6RÆ–fV7–6ÆTW'&÷"€Ð¢vF÷vâÒ×föÇVÖW2&VgW6VC¢&VÖ÷FRFW6·F÷v÷&¶W'2÷vâWfVçBföÇVÖW2pÐ¢wF†BF†R7W'&VçB&V6÷fW'’×6WBf÷&ÖBFöW2æ÷B6GW&R‚W2’â7F÷pÐ¢wv—F†÷WBÒ×föÇVÖW3²Fòæ÷BW&6Rv÷&¶W"föÇVÖW2VçF–ÂfW&–f–VBpÐ¢vW‡÷'B†2&VVâ6öÆÆV7FVBg&öÒWfW'’v÷&¶W"âæ÷F†–ærv27F÷VBpÐ¢v÷"&VÖ÷fVBârRrÂræ¦ö–â‡&VÖ÷FU÷föÇVÖW5³£5Ò’Ð¢fW&–f–VBÒæöæPÐ¢–bföÇVÖW3 Ð¢g&öÒ&–FvRæFWÆ÷’–×÷'B&V6÷fW'Ð¢&6·W2Ò6VÆbç'VçF–ÖRòv&6·W2pÐ¢6WG2Ò6÷'FVB†&6·W2æ—FW&F—"‚’’–b&6·W2æ—5öF—"‚’VÇ6RµÐÐ¢f÷"6æF–FFR–â&WfW'6VB‡6WG2“ Ð¢G'“ Ð¢&V6÷fW'’çfW&–g•÷6WB†6æF–FFRÐ¢fW&–f–VBÒ6æF–FFPÐ¢'&V°Ð¢W†6WB&V6÷fW'’å&V6÷fW'”W'&÷# Ð¢6öçF–çVPÐ¢–bfW&–f–VB—2æöæS Ð¢&—6RÆ–fV7–6ÆTW'&÷"‚vF÷vâÒ×föÇVÖW2&VgW6VC¢æò6ö×ÆWFVBÂfW&–f–VBpÐ¢w&V6÷fW'’6WBVæFW"W3²'Vâ&6·Wf—'7Bâæ÷F†–ærpÐ¢wv27F÷VB÷"&VÖ÷fVBârR&6·W2Ð¢&6·WöÖ&²ÂòÒ÷7FFU÷vFW&Ö&²‡fW&–f–VBòw7FFRròw7FFRç7Æ—FRrÐ¢Æ—fUöÖ&²ÂÆ—fUöfVæ6VBÒ÷7FFU÷vFW&Ö&²‡6VÆbç7FFU÷F‚Ð¢–bÆ—fUöÖ&²â&6·WöÖ&²æBæ÷BÆ—fUöfVæ6VC Ð¢&—6RÆ–fV7–6ÆTW'&÷"‚vF÷vâÒ×föÇVÖW2&VgW6VC¢F†RW†W&6—6R&öw&W76VBpÐ¢r†VF—BvFW&Ö&²VB’gFW"F†RæWvW7BfW&–f–VBpÐ¢w&V6÷fW'’6WBv2F¶Vâ‚VB“²'Vâ&6·Wv–âFòpÐ¢v6GW&RF†RæWvW"66÷&W2æBv÷&²âæ÷F†–ærv2pÐ¢w7F÷VB÷"&VÖ÷fVBârR†Æ—fUöÖ&²Â&6·WöÖ&²’Ð¢2fVæ6VB6—FR—2W†V×Bg&öÒF†Rg&W6†æW726†V6³¢fVæ6–æröæÇÐ¢2VæG26öçG&öÂ×ÆæRVF—B&÷w2ÂæB&6·WFVÆ–&W&FVÇ’&VgW6W0Ð¢2fVæ6VB6—FW2(	BF†R&RÖfVæ6R6WB—2F†Rf–æÂ7FFR'’FW6–vâàÐ¢6VÆbå÷7F÷÷&Vv—7G&F–öå÷v÷&¶W"‚Ð¢7F÷VBÒµÐÐ¢f÷"v÷&¶W%ö–B–â6VÆbå÷&VÖ÷FU÷v÷&¶W%ö–G2‚“ Ð¢6VÆbåöFW6·F÷ö6ö×÷6R‡v÷&¶W%ö–BÂw7F÷rÂ6†V6³ÔfÇ6RÐ¢7F÷VBæVæB‚vFW6·F÷4r²v÷&¶W%ö–BÐ¢f÷"¶–æB–â‚v–çFVw&F–öârÂvFW6·F÷2rÂvwV6ÖöÆRrÂv6VçG&ÂrÂwv§V‚r“ Ð¢–bföÇVÖW3 Ð¢2&VÖ÷fR6öçF–æW'2æBæWGv÷&·26òföÇVÖR&VÖ÷fÂ—2÷76–&ÆRàÐ¢6VÆbåö6ö×÷6R†¶–æBÂvF÷vârÐ¢VÇ6S Ð¢6VÆbåö6ö×÷6R†¶–æBÂw7F÷rÂ6†V6³ÔfÇ6RÐ¢7F÷VBæVæB†¶–æBÐ¢6VÆbå÷&VÖ÷fUöwV6ÖöÆU÷&VÆ—2‚Ð¢&VÖ÷fVBÒµÐÐ¢–bföÇVÖW3 Ð¢æÖW2Ò&V6÷fW'’æWfVçE÷föÇVÖW2€Ð¢6VÆbæWfVçBÂ6VÆbçFV×2ÀÐ¢6VÆbç&Vv—7G&F–öåöF—"òw&Vv—7G&F–öç2ç7Æ—FRpÐ¢–b6VÆbç&öf–ÆRævWB‚w&Vv—7G&F–öârÂ·Ò’ævWB‚vVæ&ÆVBrÂfÇ6R’VÇ6RæöæRÐ¢&Vf÷&RÒ6WB‡6VÆbå÷'Vâ€Ð¢²vFö6¶W"rÂwföÇVÖRrÂvÇ2rÂrÒÖf÷&ÖBrÂw·²äæÖW×ÒuÒ’ç7Æ—FÆ–æW2‚’Ð¢f÷"æÖR–âæÖW3 Ð¢–bæÖR–â&Vf÷&S Ð¢6VÆbå÷'Vâ…²vFö6¶W"rÂwföÇVÖRrÂw&ÒrÂrÖbrÂæÖUÒÐ¢gFW"Ò6WB‡6VÆbå÷'Vâ€Ð¢²vFö6¶W"rÂwföÇVÖRrÂvÇ2rÂrÒÖf÷&ÖBrÂw·²äæÖW×ÒuÒ’ç7Æ—FÆ–æW2‚’Ð¢&VÖ–æ–ærÒ6÷'FVB†gFW"æ–çFW'6V7F–öâ†æÖW2’Ð¢–b&VÖ–æ–æs Ð¢&—6RÆ–fV7–6ÆTW'&÷"‚vF÷vâÒ×föÇVÖW2f–ÆVC¢WfVçBÖ÷væVBföÇVÖW2&VÖ–âpÐ¢r‚W2“²&W7F÷&R—2Vç6fRVçF–ÂF†W’&R&VÖ÷fVBpÐ¢RrÂræ¦ö–â‡&VÖ–æ–æu³£5Ò’Ð¢&VÖ÷fVBÒ¶æÖRf÷"æÖR–âæÖW2–bæÖR–â&Vf÷&UÐÐ¢¦÷W&æÂç6WE÷7FFR‚u5DõTBrÐ¢&WGW&â²w7FFRs¢u5DõTBrÂw&ö¦V7G2s¢7F÷VBÂwföÇVÖW5÷&VÖ÷fVBs¢&VÖ÷fVGÐÐ Ð¢FVb&6·W‡6VÆb“ Ð¢""$C"gVÆÂ&V6÷fW'’6WC¢W6VB¶G&–æVBÂæF—fRD"GV×2Âv§V‚–æFW€Ð¢6æ6†÷BÂFFæBW"×FVÒföÇVÖW2ÂWf–FVæ6RÂfVÇBÂVæ7'—FV@Ð¢6V7&WG2Â&W6÷W&6RÖ–æræB&V6V—BvFW&Ö&·2â6ö×ÆWF–öâÖ&¶W"Æ7Bâ"" Ð¢g&öÒ&–FvRæFWÆ÷’–×÷'B&V6÷fW'Ð¢¦÷W&æÂÒ¦÷W&æÂæ÷Vâ‡6VÆbç'VçF–ÖRòvFWÆ÷’Ö¦÷W&æÂç7Æ—FRrÐ¢v—F‚¦÷W&æÂæÆö6²‡6VÆbæ÷W&F÷"“ Ð¢–bvWFGG"‡6VÆbÂw&VÆV6Uöf–ævW'&–çBrÂæöæR’—2æöæS Ð¢6VÆbç&VÆV6Uöf–ævW'&–çBÒ¦÷W&æÂæÖWF‚’ævWB‚w&VÆV6Uöf–ævW'&–çBrÐ¢G'“ Ð¢&WGW&â&V6÷fW'’æ7&VFR‡6VÆbÂ6VÆbç'VçF–ÖRòv&6·W2pÐ¢ò÷WF6æ÷r‚’ç7G&gF–ÖR‚rU’VÒVEBT‚TÒU5¢r’ÀÐ¢6—†W#ÖvWFGG"‡6VÆbÂv6—†W"rÂæöæR’ÀÐ¢W‡÷'Eö¦ö#ÖvWFGG"‡6VÆbÂvW‡÷'Eö¦ö"rÂæöæR’Ð¢W†6WB&V6÷fW'’å&V6÷fW'”W'&÷"2W†3 Ð¢&—6RÆ–fV7–6ÆTW'&÷"‡7G"†W†2’Ð Ð¢FVbfVæ6R‡6VÆb“ Ð¢""$c¢W&ÖæVçFÇ’F—6&ÆRw&—FW2öâF†—26—FR‡W6VB²G&–æVBf—'7B’ÀÐ¢F†Vâ7F÷F†R×WFF–öâF‡26ò7FÆRv÷&¶W'26ææ÷B&W7VÖRw&—FW2â"" Ð¢¦÷W&æÂÒ¦÷W&æÂæ÷Vâ‡6VÆbç'VçF–ÖRòvFWÆ÷’Ö¦÷W&æÂç7Æ—FRrÐ¢v—F‚¦÷W&æÂæÆö6²‡6VÆbæ÷W&F÷"“ Ð¢7FFRÒ6VÆbæ†÷7Bç7FFR‡6VÆbç7FFU÷F‚Ð¢g&öÒ&–FvRç7FFR–×÷'B6öæfÆ–7@Ð¢G'“ Ð¢7FFRæfVæ6R‡6VÆbæ÷W&F÷"Ð¢W†6WB6öæfÆ–7B2W†3 Ð¢&—6RÆ–fV7–6ÆTW'&÷"‡7G"†W†2’Ð¢6VÆbåö6ö×÷6R‚v–çFVw&F–öârÂw7F÷rÂ6†V6³ÔfÇ6RÐ¢f÷"v÷&¶W%ö–B–â6VÆbå÷&VÖ÷FU÷v÷&¶W%ö–G2‚“ Ð¢6VÆbåöFW6·F÷ö6ö×÷6R‡v÷&¶W%ö–BÂw7F÷rÂ6†V6³ÔfÇ6RÐ¢6VÆbåö6ö×÷6R‚vFW6·F÷2rÂw7F÷rÂ6†V6³ÔfÇ6RÐ¢6VÆbå÷&VÖ÷fUöwV6ÖöÆU÷&VÆ—2‚Ð¢¦÷W&æÂç6WE÷7FFR‚tdTä4TBrÐ¢&WGW&âF–7B‡²w7FFRs¢tdTä4TBwÒÂ¢§7FFRç6—FUö–æfò‚’Ð Ð¢FVb&W7F÷&R‡6VÆb“ Ð¢&—6RÆ–fV7–6ÆTW'&÷"‚w&W7F÷&RæVVG2âW‡Æ–6—B6ÆVâFW7F–æF–öâ'VçF–ÖS¢'VâpÐ¢v—F†öâÖÒ&–FvRæFWÆ÷’&W7F÷&RÒ×&öf–ÆRÇ&öf–ÆSâpÐ¢rÒ×'VçF–ÖRÆ6ÆVâ'VçF–ÖSâÒÖg&öÒÇ&V6÷fW'’6WCæâpÐ¢tæò7FFRv26†ævVBârÐ Ð¢FVb7v—F6‚‡6VÆb“ Ð¢&—6RÆ–fV7–6ÆTW'&÷"‚w&÷f–FW"7v—F6‚Fòu2—2&Æö6¶VBöâSB†æòWF†÷&—¦VBu2pÐ¢w&÷f–FW"–âF†—2Vçf—&öæÖVçB’âÆö6ÂfVæ6–ær†fVæ6R7F–öâ’æBpÐ¢v6ÆVâÖFW7F–æF–öâ&W7F÷&R&R–×ÆVÖVçFVC²æò7FFRv26†ævVBârÐ