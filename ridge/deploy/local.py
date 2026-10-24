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
FACILITATOR_USERNAME = 'admin'
FACILITATOR_PASSWORD = 'Access4n/a'


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
        creationflags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
        result = subprocess.run(
            ['icacls', str(path), '/inheritance:r', '/grant:r',
             '%s:(F)' % user, '*S-1-5-18:(F)'],
            capture_output=True, text=True, timeout=15,
            creationflags=creationflags)
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
    modifying the file (immutable URI — recovery sets are hash-verified).
    A missing file reads as (0, False); an unreadable schema refuses the wipe
    by raising — silence here would defeat the staleness check."""
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
        # Facilitators use one memorable room credential across the four admin
        # interfaces. Internal service and database credentials remain random.
        _write_private(self.secrets_dir / 'iris-admin-password',
                       FACILITATOR_PASSWORD + '\n')
        # Wazuh credentials are "username:password". These are the accounts
        # shown to organizers/participants; machine-to-machine API secrets are
        # still generated independently below.
        _write_private(self.secrets_dir / 'wazuh_admin',
                       FACILITATOR_USERNAME + ':' + FACILITATOR_PASSWORD)
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
            _write_private(self.secrets_dir / name, FACILITATOR_PASSWORD + '\n')
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
            'IRIS_ADM_USERNAME': FACILITATOR_USERNAME,
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
            'MARIADB_DATABASE': 'ctfd', 'MARIADB_USER': 'ctfd', 'MARIADB_PASSWORD': mariadb_pw,
        }
        central = {
            'RIDGE_PROJECT': self.event,
            'RIDGE_CENTRAL_NETWORK': self.event + '-central',
            'IRIS_IMAGE': 'silent-ridge-iris:dev', 'CTFD_IMAGE': 'silent-ridge-ctfd:dev',
            'RABBITMQ_IMAGE': 'rabbitmq:3-management-alpine', 'MARIADB_IMAGE': 'mariadb:10.11',
            'REDIS_IMAGE': 'redis:7-alpine',
            'IRIS_ENV_FILE': self.env_dir / 'iris.env',
            'CTFD_ENV_FILE': self.env_dir / 'ctfd.env',
            'CTFD_DB_ENV_FILE': self.env_dir / 'ctfd-db.env',
            'RIDGE_IRIS_SECRET_FILE': secrets / 'ridge-iris-bridge',
            'RIDGE_CTFD_SECRET_FILE': secrets / 'ridge-ctfd-bridge',
            'PARTICIPANT_CERTS_DIR': self.runtime / 'wazuh-certs',
            'PARTICIPANT_TLS_CONFIG': self._render_participant_tls_config(),
            'BIND_IP': bind,
            'EDGE_PORT': str(self.port('edge', 443)),
            'CRL_PORT': str(ports['crl']),
            'IRIS_PORT': str(ports['iris']), 'CTFD_PORT': str(ports['ctfd']),
            'GUAC_PORT': str(ports['guac']),
            'IRIS_PUBLIC_URL': public['iris'],
            'CTFD_PUBLIC_URL': public['ctfd'],
            'GUACAMOLE_PUBLIC_URL': public['guac'],
            'WAZUH_PUBLIC_URL': public['wazuh'],
            'CTFD_SESSION_COOKIE_NAME': 'silent_ridge_ctfd_session',
            'CTFD_SESSION_COOKIE_SECURE': 'true',
            'RIDGE_REGISTRATION_MAX_TEAMS': str(self.profile.get('registration', {}).get('max_teams', 10)),
            'RIDGE_REGISTRATION_MEMBERS': str(self.profile.get('registration', {}).get('members_per_team', 5)),
            'RIDGE_REGISTRATION_DIR': self.registration_dir,
            'RIDGE_REGISTRATION_CODE_FILE': self.secrets_dir / 'registration-enrollment-code',
        }
        # Placeholder IDs on first boot: IRIS services start before identities exist and
        # are recreated with the discovered IDs at the end of the identities stage.
        for key in ('case', 'service_user', 'open_status', 'closed_status'):
            central['RIDGE_IRIS_' + key.upper()] = str(discovered.get(key, '0'))
        files['central'] = central
        files['wazuh'] = {
            'RIDGE_PROJECT': self.event,
            'WAZUH_INDEXER_IMAGE': 'wazuh/wazuh-indexer:4.9.2',
            'WAZUH_MANAGER_IMAGE': 'wazuh/wazuh-manager:4.9.2',
            'WAZUH_DASHBOARD_IMAGE': 'wazuh/wazuh-dashboard:4.9.2',
            'WAZUH_CERTS_DIR': self.runtime / 'wazuh-certs',
            'WAZUH_CONFIG_DIR': self.asset('wazuh_config'),
            'WAZUH_RUNTIME_CONFIG_DIR': self.runtime / 'wazuh-config',
            'WAZUH_ADMIN_SECRET_FILE': self.secrets_dir / 'wazuh_admin',
            'WAZUH_API_PASSWORD': self._wazuh_api_password(),
            'BIND_IP': bind,
            'WAZUH_INDEXER_BIND_IP': '127.0.0.1',
            'WAZUH_DASHBOARD_BIND_IP': bind if self._tls_mode() != 'external' else '127.0.0.1',
            'RIDGE_CENTRAL_NETWORK': self.event + '-central',
            'WAZUH_DASHBOARD_PORT': str(ports['wazuh']),
            'WAZUH_INDEXER_PORT': str(ports['wazuh_indexer']),
        }
        files['guacamole'] = {
            'RIDGE_PROJECT': self.event,
            'RIDGE_DESKTOP_NETWORK': self.event + '-desktop',
            'RIDGE_CENTRAL_NETWORK': self.event + '-central',
            'GUAC_INIT_SQL': self.runtime / 'guac-init',
            'GUAC_DATABASE_PASSWORD': self._secret('guac-db-password'),
            'GUAC_DATABASE_PASSWORD_FILE': secrets / 'guac-db-password',
            'GUAC_PORT': str(ports['guac']), 'BIND_IP': bind,
        }
        files['desktops'] = {
            'RIDGE_PROJECT': self.event,
            'RIDGE_DESKTOP_NETWORK': self.event + '-desktop',
            'RIDGE_VNC_PASSWORD_DIR': secrets / 'vnc',
            'RIDGE_CASE_DIR': self.asset('case_template'),
            'RIDGE_EVIDENCE_DIR': self.asset('evidence_public'),
            'RIDGE_ORIGINALS_DIR': self.asset('originals'),
            # Keep the Compose resource limits aligned with the profile.  The
            # dynamic pool is deliberately one-lightweight desktop per slot;
            # leaving the compose defaults at 2 CPU / 4 GiB would make the
            # advertised 30-slot capacity impossible on the example host.
            'RIDGE_DESKTOP_CPUS': str(self.profile['capacity']['desktop']['vcpus']),
            'RIDGE_DESKTOP_MEMORY': '%dm' % self.profile['capacity']['desktop']['memory_mib'],
            'IRIS_PUBLIC_URL': public['iris'],
            'CTFD_PUBLIC_URL': public['ctfd'],
            'WAZUH_PUBLIC_URL': public['wazuh'],
        }
        for worker_id in self._remote_worker_ids():
            worker = self._worker(worker_id)
            remote = dict(files['desktops'])
            remote.update({
                'RIDGE_VNC_PASSWORD_DIR': worker['vnc_password_dir'],
                'RIDGE_CASE_DIR': worker['assets']['case_template'],
                'RIDGE_EVIDENCE_DIR': worker['assets']['evidence_public'],
                'RIDGE_ORIGINALS_DIR': worker['assets']['originals'],
            })
            files['desktops-' + worker_id] = remote
        files['integration'] = {
            'RIDGE_PROJECT': self.event,
            'RIDGE_IMAGE': 'silent-ridge-integration:dev',
            'RIDGE_STATE_DIR': self.state_dir,
            'RIDGE_RELEASE_VAULT': self.asset('release_vault'),
            'RIDGE_EVIDENCE_PUBLIC': self.asset('evidence_public'),
            'WAZUH_CA_FILE': self.runtime / 'wazuh-certs' / 'root-ca.pem',
            'IRIS_INTERNAL_URL': 'http://iris:8000', 'CTFD_INTERNAL_URL': 'http://ctfd:8000',
            'WAZUH_INDEXER_URL': 'https://wazuh-indexer:9200',
            'WAZUH_INDEX': self._index_name(),
            'WAZUH_INDEX_CREDENTIAL_FILE': secrets / 'wazuh_writer',
            'RIDGE_IRIS_SECRET_FILE': secrets / 'ridge-iris-bridge',
            'RIDGE_CTFD_SECRET_FILE': secrets / 'ridge-ctfd-bridge',
            'RIDGE_CENTRAL_NETWORK': self.event + '-central',
            'RIDGE_WAZUH_NETWORK': self.event + '-wazuh_wazuh-backend',
        }
        for name, values in files.items():
            text = '\n'.join('%s=%s' % (key, value) for key, value in values.items()) + '\n'
            _write_private(self.env_dir / (name + '.env'), text)
        for worker_id in self._remote_worker_ids():
            rows = ['services:']
            for service in self._configured_desktop_services():
                desktop = self._desktop_spec(service)
                if desktop.get('worker', 'local') != worker_id:
                    continue
                rows.extend([
                    '  %s:' % service,
                    '    ports:',
                    '      - "%s:%d:5901"' % (desktop['address'], desktop['vnc_port']),
                ])
            if len(rows) == 1:
                raise LifecycleError('desktop worker %s has no assigned services' % worker_id)
            (self.runtime / ('desktops-%s.override.yaml' % worker_id)).write_text(
                '\n'.join(rows) + '\n', encoding='utf-8')
        return files

    def _render_wazuh_config(self):
        source = self.asset('wazuh_config') / 'wazuh_cluster' / 'wazuh_manager.conf'
        if not source.is_file():
            raise LifecycleError('vendored Wazuh manager config missing at %s' % source)
        dashboard_source = (self.asset('wazuh_config') / 'wazuh_dashboard'
                            / 'opensearch_dashboards.yml')
        if not dashboard_source.is_file():
            raise LifecycleError('vendored Wazuh dashboard config missing at %s'
                                 % dashboard_source)
        target_dir = self.runtime / 'wazuh-config'
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / 'ossec.conf').write_text(
            offline_wazuh_config(source.read_text(encoding='utf-8')), encoding='utf-8')
        (target_dir / 'opensearch_dashboards.yml').write_text(
            offline_wazuh_dashboard_config(
                dashboard_source.read_text(encoding='utf-8')), encoding='utf-8')
        users = target_dir / 'internal_users.yml'
        if not users.is_file():
            password = self._secret('wazuh_admin').split(':', 1)[1]
            # Windows text-mode subprocess stdin sends CRLF. Bash read removes
            # LF but keeps CR; hashing that extra byte makes the saved password
            # unusable. The generated password is hex, so CR is never valid.
            command = ('IFS= read -r password; '
                       "password=${password%$'\\r'}; "
                       '/usr/share/wazuh-indexer/plugins/opensearch-security/tools/hash.sh '
                       '-p "$password"')
            result = self._pipe([
                'docker', 'run', '-i', '--rm', '--network', 'none', '--pull', 'never',
                '-e', 'OPENSEARCH_JAVA_HOME=/usr/share/wazuh-indexer/jdk',
                '--entrypoint', 'bash', 'wazuh/wazuh-indexer:4.9.2', '-lc', command,
            ], password + '\n')
            hash_lines = [line.strip() for line in result.splitlines()
                          if re.fullmatch(r'\$2[aby]\$12\$[./A-Za-z0-9]{53}', line.strip())]
            if len(hash_lines) != 1:
                raise LifecycleError('Wazuh indexer hash tool did not return one bcrypt hash')
            source_users = (self.asset('wazuh_config') / 'wazuh_indexer'
                            / 'internal_users.yml').read_text(encoding='utf-8')
            extra_users = []
            for secret_name, role in (('wazuh_writer', 'silent-ridge-writer'),
                                      ('wazuh_reader', 'silent-ridge-participant')):
                username, secret_password = self._secret(secret_name).split(':', 1)
                if len(secret_password) < 8:
                    extra_result = self._pipe([
                        'docker', 'run', '-i', '--rm', '--network', 'none', '--pull', 'never',
                        '-e', 'OPENSEARCH_JAVA_HOME=/usr/share/wazuh-indexer/jdk',
                        '--entrypoint', 'bash', 'wazuh/wazuh-indexer:4.9.2', '-lc', command,
                    ], secret_password + '\n')
                    extra_hashes = [line.strip() for line in extra_result.splitlines()
                                    if re.fullmatch(r'\$2[aby]\$12\$[./A-Za-z0-9]{53}', line.strip())]
                    if len(extra_hashes) != 1:
                        raise LifecycleError('Wazuh indexer hash tool did not return one bcrypt hash')
                    extra_users.append((username, extra_hashes[0], role))
            users.write_text(render_indexer_admin(source_users, hash_lines[0], extra_users),
                             encoding='utf-8')

    def _relay_for_desktop(self, desktop):
        worker_id = desktop.get('worker', 'local')
        if worker_id == 'local':
            return None
        relay = self._worker(worker_id).get('guacamole_relay')
        if relay is None:
            return None
        return relay['address'], relay['ports'][desktop['name']]

    def _guacamole_desktop(self, desktop):
        row = {
            'id': desktop['name'],
            'shared': desktop.get('shared', True),
            'max_connections': desktop.get(
                'max_connections', 4 if desktop.get('shared', True) else 1),
        }
        if desktop.get('worker', 'local') == 'local':
            row['container'] = True
        else:
            relay = self._relay_for_desktop(desktop)
            if relay is None:
                row.update(address=desktop['address'], port=desktop['vnc_port'])
            else:
                row.update(address=relay[0], port=relay[1])
        return row

    def _render_specs(self):
        """Create missing bootstrap/provisioning specs from the runtime credentials.
        Existing credential-bearing specs are preserved: credentials are never rotated.
        Guacamole connection endpoints are reconciled from host-local topology so
        an intentional relay change can be applied after a clean stop."""
        self.specs_dir.mkdir(parents=True, exist_ok=True)
        credentials = self._team_credentials()
        dynamic = self.profile.get('registration', {}).get('enabled', False)
        iris_path = self.specs_dir / 'iris-bootstrap-spec.json'
        if not iris_path.is_file():
            iris_spec = {
                'case_name': 'Operation Silent Ridge',
                'case_description': 'Cooperative incident-response exercise case. All content fictional.',
                'service_login': 'silent-ridge-service',
                'service_name': 'Silent Ridge Integration',
                'service_password': self.host.randhex(12),
                'open_status': 'To do', 'closed_status': 'Done',
                'registration_enabled': dynamic,
                'identities': [
                    {'team': team['name'],
                     'login': credentials['teams'][team['name']]['iris_login'],
                     'name': credentials['teams'][team['name']]['iris_login'],
                     'password': credentials['teams'][team['name']]['iris_password']}
                    for team in self.teams],
            }
            _write_private(iris_path, json.dumps(iris_spec, indent=2))
        ctfd_path = self.specs_dir / 'ctfd-provision-spec.json'
        if not ctfd_path.is_file():
            ctfd_users = []
            for team in self.teams:
                friendly = credentials['teams'][team['name']]['ctfd_name']
                account_passwords = list(credentials['teams'][team['name']]['accounts'].values())
                for account_index, account in enumerate(team['accounts']):
                    # Keep the first participant login as the memorable team
                    # name; suffix additional roster accounts predictably.
                    login = friendly if account_index == 0 else '%s-p%02d' % (
                        friendly, account_index + 1)
                    ctfd_users.append({
                        'name': login,
                        'email': '%s@silent-ridge.invalid' % login,
                        'team': team['name'],
                        # Match by roster position so inventories written by
                        # older releases (legacy keys) remain restorable.
                        'password': account_passwords[account_index],
                    })
            ctfd_spec = {
                'teams': [{'team': team['name'],
                           'name': credentials['teams'][team['name']]['ctfd_name'],
                           'password': credentials['teams'][team['name']]['ctfd_password']}
                          for team in self.teams],
                'users': ctfd_users,
                'user_mode': 'teams', 'registration_visible': dynamic, 'schema': 'ctfd-3.7.7',
                'facilitator': {'name': FACILITATOR_USERNAME,
                                'email': 'facilitator@silent-ridge.invalid',
                                'password': self._secret('ctfd-facilitator-password')},
            }
            _write_private(ctfd_path, json.dumps(ctfd_spec, indent=2))
        guac_config_path = self.specs_dir / 'guac-config.json'
        if not guac_config_path.is_file():
            _write_private(guac_config_path, json.dumps({
                'desktops': [self._guacamole_desktop(desktop)
                             for desktop in self.profile['desktops']],
                'teams': ([{'id': 'team%02d' % (i + 1), 'desktop': team['desktop']}
                           for i, team in enumerate(self.teams)]
                          if not dynamic else []),
            }, indent=2))
        else:
            guac_config = json.loads(guac_config_path.read_text(encoding='utf-8'))
            expected = {desktop['id']: desktop for desktop in
                        (self._guacamole_desktop(row) for row in self.profile['desktops'])}
            current = {desktop.get('id'): desktop
                       for desktop in guac_config.get('desktops', [])}
            if set(current) != set(expected):
                raise LifecycleError(
                    'existing Guacamole desktop inventory differs from the profile; '
                    'restore the original profile/runtime instead of changing slot identity')
            changed = False
            for desktop_id, row in current.items():
                before = dict(row)
                for key in ('address', 'port', 'container'):
                    row.pop(key, None)
                row.update(expected[desktop_id])
                changed = changed or row != before
            if changed:
                _write_private(guac_config_path, json.dumps(guac_config, indent=2))
        guac_creds_path = self.specs_dir / 'guac-credentials.json'
        if not guac_creds_path.is_file():
            guac_config = json.loads(guac_config_path.read_text(encoding='utf-8'))
            _write_private(guac_creds_path, json.dumps({
                'teams': ({tag: {'username': credentials['teams'][team['name']]['guac_username'],
                                 'password': credentials['teams'][team['name']]['guac_password']}
                           for tag, team in zip((t['id'] for t in guac_config['teams']), self.teams)}
                          if not dynamic else {}),
                'desktops': {name: {'password': credentials['desktops'][name]['password']}
                             for name in credentials['desktops']},
                'facilitator': {'username': FACILITATOR_USERNAME,
                                'password': self._secret('guac-facilitator-password')},
            }, indent=2))

        for private_spec in (iris_path, ctfd_path, guac_config_path, guac_creds_path):
            _secure_private(private_spec)

    # ----------------------------------------------------------------- stages

    STAGES = ('ARTIFACTS_VERIFIED', 'INFRASTRUCTURE_READY', 'APPLICATIONS_READY',
              'IDENTITIES_READY', 'DESKTOPS_READY', 'EVIDENCE_READY', 'PROVISIONED_PAUSED')

    # S1 -------------------------------------------------------- artifacts
    def _probe_artifacts(self):
        problems = []
        for component in IMAGE_COMPONENTS:
            receipt = self.receipts / (component + '.json')
            if not receipt.is_file():
                problems.append('no build receipt for %s: run `python -m ridge.deploy build '
                                '--component %s`' % (component, component))
                continue
            recorded = json.loads(receipt.read_text(encoding='utf-8'))
            try:
                actual = self._run(['docker', 'image', 'inspect', '--format', '{{.Id}}',
                                    recorded['image']])
            except Exception:
                problems.append('image %s is not loaded: rebuild with `python -m ridge.deploy '
                                'build --component %s`' % (recorded['image'], component))
                continue
            if actual != recorded['image_id']:
                problems.append('image %s changed since its receipt: rebuild component %s'
                                % (recorded['image'], component))
        desktop_receipt = self.receipts / 'desktop.json'
        if desktop_receipt.is_file():
            recorded = json.loads(desktop_receipt.read_text(encoding='utf-8'))
            for worker_id in self._remote_worker_ids():
                context = self._worker(worker_id)['docker_context']
                try:
                    actual = self._run(['docker', '--context', context, 'image', 'inspect',
                                        '--format', '{{.Id}}', recorded['image']])
                except Exception:
                    problems.append('desktop image %s is not loaded on worker %s (Docker '
                                    'context %s)' % (recorded['image'], worker_id, context))
                    continue
                if actual != recorded['image_id']:
                    problems.append('desktop image %s on worker %s differs from the reviewed '
                                    'build receipt; transfer the reviewed image instead of '
                                    'rebuilding independently' % (recorded['image'], worker_id))
                    continue
                worker = self._worker(worker_id)
                checks = ['test -f /case/WS17.aut',
                          'test -f /evidence/network/sensor.pcap',
                          'test -d /originals']
                try:
                    self._run([
                        'docker', '--context', context, 'run', '--rm', '--pull', 'never',
                        '--network', 'none', '--entrypoint', 'bash',
                        '-v', worker['assets']['case_template'] + ':/case:ro',
                        '-v', worker['assets']['evidence_public'] + ':/evidence:ro',
                        '-v', worker['assets']['originals'] + ':/originals:ro',
                        recorded['image'], '-c', ' && '.join(checks),
                    ])
                except Exception:
                    problems.append('worker %s cannot read the staged case, evidence, or '
                                    'originals; verify local.json remote asset paths'
                                    % worker_id)
        for key, check in (('evidence_public', 'dir'), ('release_vault', 'dir'),
                           ('case_template', 'dir'), ('originals', 'dir')):
            if not self.asset(key).is_dir():
                problems.append('asset %s missing at %s' % (key, self.asset(key)))
        case = self.asset('case_template') / 'WS17.aut'
        if self.asset('case_template').is_dir() and not case.is_file():
            problems.append('prepared case %s is missing; extract the published case template'
                            % case)
        problems.extend(self._probe_wazuh_config_assets())
        from ridge.wazuh_provision import validate_manifest, load_vendored
        try:
            validate_manifest(load_vendored(WAZUH_DIR)['manifest'], require_digests=True)
        except Exception as exc:
            problems.append('Wazuh vendored manifest fails digest validation: %s' % exc)
        if problems:
            raise LifecycleError('; '.join(problems))
        return {'images': len(IMAGE_COMPONENTS)}

    @staticmethod
    def _wazuh_config_remedy(wazuh_config):
        """Actionable remedy for a missing or broken Wazuh config tree (issue #187).

        Names the source-path fetcher from scripts/ when the repo ships one
        (PR #185's fetch_wazuh_config.py); otherwise names the pinned upstream
        commit recorded in the vendored manifest so the operator can vendor the
        four mounted files by hand. Either way the message carries the exact
        destination directory, not just expected file paths.
        """
        fetch = ROOT / 'scripts' / 'fetch_wazuh_config.py'
        if fetch.is_file():
            return 'produce it with `python scripts/fetch_wazuh_config.py %s`' % wazuh_config
        manifest = WAZUH_DIR / 'manifest.json'
        commit = json.loads(manifest.read_text(encoding='utf-8'))['source']['commit']
        return ('vendor the upstream single-node config from wazuh/wazuh-docker commit %s '
                '(pinned in %s) into %s' % (commit, manifest, wazuh_config))

    def _probe_wazuh_config_assets(self):
        """Fail closed when required Wazuh config assets are missing or malformed.

        The previous check only fired when the asset directory already existed
        and covered three of the four files the Wazuh compose project mounts,
        so an absent tree, the dashboard config, or a corrupt file passed
        preflight and surfaced late as a crash inside the Wazuh project.
        """
        wazuh_config = self.asset('wazuh_config')
        if not wazuh_config.is_dir():
            return ['Wazuh config asset missing at %s: %s'
                    % (wazuh_config, self._wazuh_config_remedy(wazuh_config))]
        problems = []
        for rel, fmt in WAZUH_CONFIG_ASSET_FILES:
            path = wazuh_config / rel
            if not path.is_file():
                problems.append('Wazuh config %s missing under %s: %s'
                                % (rel, wazuh_config, self._wazuh_config_remedy(wazuh_config)))
                continue
            try:
                text = path.read_text(encoding='utf-8')
            except (OSError, UnicodeDecodeError) as exc:
                problems.append('Wazuh config %s under %s is unreadable: %s' % (rel, wazuh_config, exc))
                continue
            if not text.strip():
                problems.append('Wazuh config %s under %s is empty: %s'
                                % (rel, wazuh_config, self._wazuh_config_remedy(wazuh_config)))
                continue
            try:
                if fmt == 'xml':
                    offline_wazuh_config(text)  # reuses the renderer's own XML checks
                elif _yaml is not None:
                    _yaml.safe_load(text)
            except Exception as exc:
                problems.append('Wazuh config %s under %s is not valid %s: %s'
                                % (rel, wazuh_config, fmt, exc))
        return problems

    # S2 ------------------------------------------------------ infrastructure
    def _ensure_networks(self):
        """Create the external networks every compose file references.

        The central and desktop networks are declared ``external: true`` across
        compose projects, so create those two explicitly. The Wazuh Compose
        project owns its backend network and marks it internal; pre-creating it
        here would silently discard that isolation setting.
        """
        for suffix in ('-central', '-desktop'):
            name = self.event + suffix
            try:
                self._run(['docker', 'network', 'inspect', name])
            except CommandError:
                self._run(['docker', 'network', 'create', name])
        desktop_network = self.event + '-desktop'
        for worker_id in self._remote_worker_ids():
            context = self._worker(worker_id)['docker_context']
            try:
                self._run(['docker', '--context', context, 'network', 'inspect', desktop_network])
            except CommandError:
                self._run(['docker', '--context', context, 'network', 'create', desktop_network])

    def _stage_worker_vnc_secrets(self):
        """Stream generated VNC passwords to worker-local bind paths.

        The secret value travels on stdin through the authenticated Docker
        context. It is never placed in an argv, Compose override, or Git file.
        This runs only after ARTIFACTS_VERIFIED has confirmed that the exact
        reviewed desktop image is present on each worker.
        """
        if not self._remote_worker_ids():
            return
        receipt = json.loads((self.receipts / 'desktop.json').read_text(encoding='utf-8'))
        for worker_id in self._remote_worker_ids():
            worker = self._worker(worker_id)
            context = worker['docker_context']
            for name in self._worker_vnc_secret_names(worker_id):
                source = self.secrets_dir / 'vnc' / name
                self._pipe([
                    'docker', '--context', context, 'run', '--rm', '-i', '--pull', 'never',
                    '--network', 'none', '--entrypoint', 'bash',
                    '-v', worker['vnc_password_dir'] + ':/vnc',
                    receipt['image'], '-c', 'umask 077; cat > /vnc/%s' % name,
                ], source.read_text(encoding='utf-8'))

    def _worker_vnc_secret_names(self, worker_id):
        dynamic = self.profile.get('registration', {}).get('enabled', False)
        result = []
        for service in self._configured_desktop_services():
            if self._desktop_spec(service).get('worker', 'local') != worker_id:
                continue
            result.append(service if dynamic else service.removeprefix('desktop-'))
        return result

    def _probe_worker_vnc_secrets(self):
        if not self._remote_worker_ids():
            return
        receipt = json.loads((self.receipts / 'desktop.json').read_text(encoding='utf-8'))
        for worker_id in self._remote_worker_ids():
            worker = self._worker(worker_id)
            checks = ' && '.join('test -s /vnc/%s' % name
                                 for name in self._worker_vnc_secret_names(worker_id))
            try:
                self._run([
                    'docker', '--context', worker['docker_context'], 'run', '--rm',
                    '--pull', 'never', '--network', 'none', '--entrypoint', 'bash',
                    '-v', worker['vnc_password_dir'] + ':/vnc:ro',
                    receipt['image'], '-c', checks,
                ])
            except Exception:
                raise LifecycleError(
                    'worker %s is missing one or more generated VNC secrets at %s; '
                    'rerun up to restage them through the Docker context'
                    % (worker_id, worker['vnc_password_dir']))

    def _guacamole_relays(self):
        """Return configured Windows host relays in deterministic order.

        Docker Desktop runs ``guacd`` behind its own VM/NAT boundary. On hosts
        where that boundary cannot route directly to a LAN worker, an explicit
        host-local relay gives Guacamole a reachable endpoint without exposing
        worker VNC to participant devices.
        """
        rows = []
        by_name = {desktop['name']: desktop for desktop in self.profile['desktops']}
        for worker_id in self._remote_worker_ids():
            worker = self._worker(worker_id)
            relay = worker.get('guacamole_relay')
            if relay is None:
                continue
            for desktop_name, relay_port in sorted(relay['ports'].items()):
                rows.append((worker_id, by_name[desktop_name], relay, relay_port))
        return rows

    def _guacamole_relay_rule_name(self, worker_id, relay_port):
        slug = re.sub(r'[^A-Za-z0-9_-]+', '-', '%s-%s' % (self.event, worker_id))
        return 'Silent-Ridge-Guac-Relay-%s-%d' % (slug[:100], relay_port)

    def _apply_guacamole_relays(self):
        """Create narrowly scoped Windows portproxy and firewall entries.

        Every relay is explicit in private ``local.json``. The firewall source
        is the Guacamole Docker subnet, not the participant LAN, and cleanup
        targets only the deterministic event-owned rule and portproxy tuple.
        """
        relays = self._guacamole_relays()
        if not relays:
            return
        try:
            self._run([
                'powershell.exe', '-NoProfile', '-NonInteractive', '-Command',
                ("$service = Get-Service -Name iphlpsvc -ErrorAction Stop; "
                 "if ($service.Status -ne 'Running') { "
                 "Start-Service -Name iphlpsvc -ErrorAction Stop }"),
            ])
            for worker_id, desktop, relay, relay_port in relays:
                rule = self._guacamole_relay_rule_name(worker_id, relay_port)
                source = str(ipaddress.IPv4Network(relay['source_cidr'], strict=False))
                self._run([
                    'powershell.exe', '-NoProfile', '-NonInteractive', '-Command',
                    ("$Error.Clear(); $existing = Get-NetFirewallRule -Name '%s' "
                     "-ErrorAction SilentlyContinue; if ($Error.Count -and "
                     "$Error[0].FullyQualifiedErrorId -notlike 'CmdletizationQuery_NotFound*') "
                     "{ throw $Error[0] }; if ($null -ne $existing) { $existing | "
                     "Remove-NetFirewallRule -ErrorAction Stop }; exit 0") % rule,
                ])
                self._run([
                    'powershell.exe', '-NoProfile', '-NonInteractive', '-Command',
                    ("New-NetFirewallRule -Name '%s' -DisplayName '%s' "
                     "-Direction Inbound -Action Allow -Enabled True -Profile Private "
                     "-Protocol TCP -LocalPort %d -RemoteAddress '%s' -ErrorAction Stop"
                     % (rule, rule, relay_port, source)),
                ])
                listen = relay.get('listen_address', '0.0.0.0')
                self._run([
                    'netsh', 'interface', 'portproxy', 'delete', 'v4tov4',
                    'listenaddress=%s' % listen, 'listenport=%d' % relay_port,
                ], check=False)
                self._run([
                    'netsh', 'interface', 'portproxy', 'add', 'v4tov4',
                    'listenaddress=%s' % listen, 'listenport=%d' % relay_port,
                    'connectaddress=%s' % desktop['address'],
                    'connectport=%d' % desktop['vnc_port'], 'protocol=tcp',
                ])
        except CommandError as exc:
            raise LifecycleError(
                'could not configure the Windows Guacamole relay; run the lifecycle from '
                'an elevated terminal and verify the IP Helper service is available: %s' % exc)

    def _probe_guacamole_relays(self):
        """Verify exact portproxy targets and source-scoped firewall rules."""
        for worker_id, desktop, relay, relay_port in self._guacamole_relays():
            rule = self._guacamole_relay_rule_name(worker_id, relay_port)
            listen = relay.get('listen_address', '0.0.0.0')
            source_network = ipaddress.IPv4Network(relay['source_cidr'], strict=False)
            source = str(source_network)
            source_netmask = '%s/%s' % (source_network.network_address,
                                        source_network.netmask)
            property_name = '%s/%d' % (listen, relay_port)
            expected_target = '%s/%d' % (desktop['address'], desktop['vnc_port'])
            script = (
                "$path = 'HKLM:\\SYSTEM\\CurrentControlSet\\Services\\PortProxy\\v4tov4\\tcp'; "
                "$item = Get-ItemProperty -LiteralPath $path -ErrorAction Stop; "
                "$property = $item.PSObject.Properties['%s']; "
                "if ($null -eq $property -or $property.Value -ne '%s') { exit 31 }; "
                "$rule = Get-NetFirewallRule -Name '%s' -ErrorAction Stop; "
                "$port = $rule | Get-NetFirewallPortFilter; "
                "$address = $rule | Get-NetFirewallAddressFilter; "
                "if ($rule.Enabled -ne 'True' -or $rule.Direction -ne 'Inbound' "
                "-or $rule.Action -ne 'Allow' -or $port.Protocol -ne 'TCP' "
                "-or $port.LocalPort -ne '%d' -or "
                "(@($address.RemoteAddress) -notcontains '%s' -and "
                "@($address.RemoteAddress) -notcontains '%s')) { exit 32 }"
                % (property_name, expected_target, rule, relay_port, source,
                   source_netmask))
            try:
                self._run([
                    'powershell.exe', '-NoProfile', '-NonInteractive', '-Command', script,
                ])
            except CommandError as exc:
                raise LifecycleError(
                    'Guacamole relay %s:%d does not match %s:%d or its firewall source '
                    '%s; rerun up from an elevated terminal: %s'
                    % (listen, relay_port, desktop['address'], desktop['vnc_port'], source, exc))

    def _remove_guacamole_relays(self):
        """Remove only relay resources owned by this event runtime."""
        for worker_id, _desktop, relay, relay_port in self._guacamole_relays():
            listen = relay.get('listen_address', '0.0.0.0')
            self._run([
                'netsh', 'interface', 'portproxy', 'delete', 'v4tov4',
                'listenaddress=%s' % listen, 'listenport=%d' % relay_port,
            ], check=False)
            rule = self._guacamole_relay_rule_name(worker_id, relay_port)
            self._run([
                'powershell.exe', '-NoProfile', '-NonInteractive', '-Command',
                ("$Error.Clear(); $existing = Get-NetFirewallRule -Name '%s' "
                 "-ErrorAction SilentlyContinue; if ($Error.Count -and "
                 "$Error[0].FullyQualifiedErrorId -notlike 'CmdletizationQuery_NotFound*') "
                 "{ throw $Error[0] }; if ($null -ne $existing) { $existing | "
                 "Remove-NetFirewallRule -ErrorAction Stop }; exit 0") % rule,
            ])

    def _dashboard_bind_ip(self):
        bind = str(self.local.get('bind_ip') or '127.0.0.1')
        try:
            address = ipaddress.IPv4Address(bind)
        except ipaddress.AddressValueError as exc:
            raise LifecycleError('local.json bind_ip must be an IPv4 address: %s' % exc)
        if (address.is_unspecified or address.is_multicast or address.is_link_local
                or not (address.is_private or address.is_loopback)):
            raise LifecycleError('local.json bind_ip must be a private or loopback IPv4 address')
        return bind

    def _verify_public_certificate(self, certs, bind, name):
        certificate = certs / (name + '.pem')
        if not certificate.is_file():
            raise LifecycleError('missing %s certificate at %s' % (name, certificate))
        match = self._run([
            'docker', 'run', '--rm', '--network', 'none', '--pull', 'never',
            '-v', str(certs) + ':/certs:ro', '--entrypoint', 'openssl',
            'wazuh/wazuh-manager:4.9.2', 'x509', '-in', '/certs/' + name + '.pem',
            '-noout', '-checkip', bind,
        ], check=False)
        if 'does match certificate' not in match:
            raise LifecycleError('%s certificate does not cover local.json '
                                 'bind_ip %s; preserve the current CA and certificates, '
                                 'then plan a certificate rotation for this address' % (name, bind))

    def _install_external_edge_certificate(self, certs):
        """Install and verify the public edge certificate for browser endpoints.

        Only participant.pem is replaced.  The generated root CA, dashboard,
        manager, indexer and admin certificates remain available for Wazuh's
        private backend trust graph.
        """
        tls = self.local['tls']
        source_cert = Path(tls['certificate']).resolve()
        source_key = Path(tls['key']).resolve()
        for source, label in ((source_cert, 'certificate'), (source_key, 'key')):
            if not source.is_file() or source.stat().st_size == 0:
                raise LifecycleError('external TLS %s is missing or empty: %s' % (label, source))
        shutil.copyfile(source_cert, certs / 'participant.pem')
        shutil.copyfile(source_key, certs / 'participant-key.pem')
        hosts = self._service_hosts()
        for name in ('iris', 'ctfd', 'guac', 'wazuh'):
            match = self._run([
                'docker', 'run', '--rm', '--network', 'none', '--pull', 'never',
                '-v', str(certs) + ':/certs:ro', '--entrypoint', 'openssl',
                'wazuh/wazuh-manager:4.9.2', 'x509', '-in', '/certs/participant.pem',
                '-noout', '-checkhost', hosts[name],
            ], check=False)
            if 'does match certificate' not in match:
                raise LifecycleError('external TLS certificate does not cover hostname %s; '
                                     'request a certificate containing every configured service '
                                     'hostname' % hosts[name])
        # Nginx will report a key mismatch, but fail early with an actionable
        # message when the image can inspect both public files.
        key_check = self._run([
            'docker', 'run', '--rm', '--network', 'none', '--pull', 'never',
            '-v', str(certs) + ':/certs:ro', '--entrypoint', 'sh',
            'wazuh/wazuh-manager:4.9.2', '-ec',
            "openssl x509 -in /certs/participant.pem -pubkey -noout | "
            "openssl pkey -pubin -outform DER | sha256sum; "
            "openssl pkey -in /certs/participant-key.pem -pubout -outform DER | sha256sum",
        ], check=False)
        hashes = [line.split()[0] for line in key_check.splitlines()
                  if re.fullmatch(r'[0-9a-fA-F]{64}', line.split()[0] if line.split() else '')]
        if len(hashes) != 2 or hashes[0].lower() != hashes[1].lower():
            raise LifecycleError('external TLS certificate and private key do not match')

    def _verify_revocation_material(self, certs, bind):
        crl = certs / 'root-ca.crl'
        if not crl.is_file() or crl.stat().st_size == 0:
            raise LifecycleError('missing signed offline CRL at %s; rotate the event CA '
                                 'and certificates before participant setup' % crl)
        try:
            # OpenSSL writes ``verify OK`` to stderr, while CommandRunner returns
            # stdout. The exit status is the portable verification contract.
            self._run([
                'docker', 'run', '--rm', '--network', 'none', '--pull', 'never',
                '-v', str(certs) + ':/certs:ro', '--entrypoint', 'openssl',
                'wazuh/wazuh-manager:4.9.2', 'crl', '-in', '/certs/root-ca.crl',
                '-inform', 'DER', '-noout', '-verify', '-CAfile', '/certs/root-ca.pem',
            ])
        except CommandError:
            raise LifecycleError('offline CRL signature verification failed; rotate the '
                                 'event CA and certificates')
        expected = 'http://%s:%d/root-ca.crl' % (bind, self.port('crl', 8080))
        for name in ('dashboard', 'participant'):
            points = self._run([
                'docker', 'run', '--rm', '--network', 'none', '--pull', 'never',
                '-v', str(certs) + ':/certs:ro', '--entrypoint', 'openssl',
                'wazuh/wazuh-manager:4.9.2', 'x509', '-in', '/certs/' + name + '.pem',
                '-noout', '-ext', 'crlDistributionPoints',
            ], check=False)
            if expected not in points:
                raise LifecycleError('%s certificate does not publish expected offline CRL '
                                     'URL %s; rotate the event CA and certificates'
                                     % (name, expected))

    def _prepare_wazuh_certificates(self, certs, bind):
        """Prepare internal node TLS and the participant-facing edge certificate.

        In external TLS mode the configured public certificate replaces the
        generated participant edge pair.  A later ``up`` must therefore not
        ask the private-CA generator to validate that public certificate's CRL
        extension.  Preserve the existing internal CA/node material, fail
        closed if any of it is incomplete, and reinstall the configured edge
        pair idempotently.
        """
        external_reuse = self._tls_mode() == 'external' and (certs / 'root-ca.pem').is_file()
        if external_reuse:
            internal = (
                'root-ca.pem', 'root-ca-key.pem', 'root-ca.crl',
                'dashboard.pem', 'dashboard-key.pem',
                'indexer.pem', 'indexer-key.pem',
                'manager.pem', 'manager-key.pem',
                'admin.pem', 'admin-key.pem',
            )
            missing = [name for name in internal
                       if not (certs / name).is_file() or (certs / name).stat().st_size == 0]
            if missing:
                raise LifecycleError(
                    'external TLS runtime has incomplete internal Wazuh certificate material: '
                    + ', '.join(missing) + '; restore the runtime backup or use a fresh runtime')
        else:
            self._run([
                'docker', 'run', '--rm', '--network', 'none', '--pull', 'never',
                '-e', 'RIDGE_CRL_PORT=%d' % self.port('crl', 8080),
                '-v', str(WAZUH_DIR / 'generate-certs.sh') + ':/generate-certs.sh:ro',
                '-v', str(certs) + ':/certs', '--entrypoint', 'bash',
                'wazuh/wazuh-manager:4.9.2', '/generate-certs.sh', '/certs', bind,
            ])
        if self._tls_mode() == 'external':
            self._install_external_edge_certificate(certs)
            self._verify_public_certificate(certs, bind, 'dashboard')
        else:
            self._verify_public_certificate(certs, bind, 'dashboard')
            self._verify_public_certificate(certs, bind, 'participant')
            self._verify_revocation_material(certs, bind)

    def _apply_infrastructure(self):
        self._ensure_secrets()
        self._apply_guacamole_relays()
        self._render_specs()
        self._render_wazuh_config()
        self._render_env()
        self._ensure_networks()
        self._stage_worker_vnc_secrets()
        certs = self.runtime / 'wazuh-certs'
        bind = self._dashboard_bind_ip()
        certs.mkdir(parents=True, exist_ok=True)
        self._prepare_wazuh_certificates(certs, bind)
        guac_init = self.runtime / 'guac-init'
        guac_init.mkdir(parents=True, exist_ok=True)
        if not (guac_init / '001-initdb.sql').is_file():
            schema = self._run(['docker', 'run', '--rm', 'guacamole/guacamole:1.5.5',
                                '/opt/guacamole/bin/initdb.sh', '--postgresql'])
            (guac_init / '001-initdb.sql').write_text(schema + '\n', encoding='utf-8')
        import sys
        sys.path.insert(0, str(COMPOSE_DIR))
        import guacamole as guac_module
        config = json.loads((self.specs_dir / 'guac-config.json').read_text(encoding='utf-8'))
        credentials = json.loads((self.specs_dir / 'guac-credentials.json').read_text(encoding='utf-8'))
        # The generator is idempotent and refuses credential rotation. Rewrite
        # this private SQL so a stopped deployment can adopt an intentional
        # direct-to-relay endpoint change when DESKTOPS_READY is re-applied.
        _write_private(guac_init / '002-provision.sql',
                       guac_module.generate(config, credentials))
        for kind, services in INFRA_SERVICES.items():
            if kind in ('wazuh', 'guacamole'):
                # A running manager can still have no Wazuh daemons, and the
                # Guacamole database/guacd need a bounded startup window before
                # the immediate stage probe. Wait for Compose health rather than
                # turning normal first-boot timing into a failed lifecycle step.
                self._compose(kind, 'up', '-d', '--wait', '--wait-timeout', '300', *services)
            else:
                self._compose(kind, 'up', '-d', *services)

    def _probe_infrastructure(self):
        existing = [name for name in SECRET_FILES if (self.secrets_dir / name).is_file()]
        if len(existing) != len(SECRET_FILES):
            raise LifecycleError('incomplete secrets in %s: missing %s. Restore the runtime; '
                                 'secrets are never regenerated beneath a verified deployment'
                                 % (self.secrets_dir,
                                    ', '.join(sorted(set(SECRET_FILES) - set(existing)))))
        self._wazuh_api_password()
        self._probe_worker_vnc_secrets()
        private_users = self.runtime / 'wazuh-config' / 'internal_users.yml'
        if not private_users.is_file():
            raise LifecycleError('missing private Wazuh indexer users at %s; restore the '
                                 'runtime or run up on a fresh deployment' % private_users)
        if self._tls_mode() == 'external':
            self._install_external_edge_certificate(self.runtime / 'wazuh-certs')
            self._verify_public_certificate(self.runtime / 'wazuh-certs',
                                            self._dashboard_bind_ip(), 'dashboard')
        else:
            for name in ('dashboard', 'participant'):
                self._verify_public_certificate(self.runtime / 'wazuh-certs',
                                                self._dashboard_bind_ip(), name)
            self._verify_revocation_material(self.runtime / 'wazuh-certs',
                                             self._dashboard_bind_ip())
        for kind, services in INFRA_SERVICES.items():
            self._require_services(kind, services,
                                   allow_exit0=INFRA_ONE_SHOT.get(kind, ()))
        self._probe_guacamole_relays()
        return {'services': sum(len(s) for s in INFRA_SERVICES.values())}

    # S3 ------------------------------------------------------- applications
    def _apply_applications(self):
        for kind, services in APP_SERVICES.items():
            self._compose(kind, 'up', '-d', '--wait', '--wait-timeout', '300', *services)

    def _probe_applications(self):
        for kind, services in APP_SERVICES.items():
            self._require_services(kind, services)
        hosts = self._service_hosts()
        # A fresh CTFd database serves /setup until silent-ridge-provision runs
        # in the next stage. /login redirects there using its internal default
        # port, so requiring /login here would make first boot impossible.
        ctfd_path = ('/login' if (self.runtime / 'inventories' / 'ctfd-inventory.json').is_file()
                     else '/setup')
        checks = ((self._public_url(hosts['iris'], self._public_port('iris', 8081)) + '/login', 'IRIS'),
                  (self._public_url(hosts['ctfd'], self._public_port('ctfd', 8083)) + ctfd_path, 'CTFd'),
                  (self._public_url(hosts['guac'], self._public_port('guac', 8082)) + '/guacamole/', 'Guacamole'),
                  (self._public_url(hosts['wazuh'], self._public_port('wazuh', 8443)) + '/app/login', 'Wazuh'))
        ca_file = self._participant_ca_file()
        for url, name in checks:
            status, _ = self.host.http_json('GET', url, ca_file=ca_file)
            if status != 200:
                raise LifecycleError('%s participant page returned HTTP %s at %s; the application is '
                                     'not ready' % (name, status, url))
        return {'services': sum(len(s) for s in APP_SERVICES.values())}

    # S4 --------------------------------------------------------- identities
    def _container_name(self, project_kind, service):
        out = self._compose(project_kind, 'ps', '-a', '-q', service)
        container_id = out.strip().splitlines()[0] if out.strip() else ''
        if not container_id:
            raise LifecycleError('no container for %s/%s; run up first' % (project_kind, service))
        name = self._run(['docker', 'inspect', '--format', '{{.Name}}', container_id])
        return name.strip().lstrip('/')

    def _bootstrap_one(self, project_kind, service, spec_name, command, inventory_name):
        spec = self.specs_dir / spec_name
        target_spec = '/tmp/silent-ridge-spec.json'
        target_inventory = '/tmp/silent-ridge-inventory.json'
        container = self._container_name(project_kind, service)
        self._run(['docker', 'cp', spec, '%s:%s' % (container, target_spec)])
        self._compose(project_kind, 'exec', '-T', service, 'flask', command,
                      '--spec', target_spec, '--inventory', target_inventory)
        local_inventory = self.runtime / 'inventories' / inventory_name
        local_inventory.parent.mkdir(parents=True, exist_ok=True)
        if local_inventory.is_file():
            previous = local_inventory.read_bytes()
            staging = self.runtime / 'inventories' / ('.next-' + inventory_name)
            self._run(['docker', 'cp', '%s:%s' % (container, target_inventory), staging])
            if staging.read_bytes() != previous:
                staging.unlink(missing_ok=True)
                raise LifecycleError(
                    'repeated %s returned a different inventory; refusing to adopt changed '
                    'identities. Investigate %s vs the container state' % (command, local_inventory))
            staging.unlink(missing_ok=True)
        else:
            self._run(['docker', 'cp', '%s:%s' % (container, target_inventory), local_inventory])
        return json.loads(local_inventory.read_text(encoding='utf-8'))

    def _apply_identities(self):
        iris = self._bootstrap_one('central', 'iris', 'iris-bootstrap-spec.json',
                                   'silent-ridge-bootstrap', 'iris-inventory.json')
        self._bootstrap_one('central', 'ctfd', 'ctfd-provision-spec.json',
                            'silent-ridge-provision', 'ctfd-inventory.json')
        inventory = iris['inventory']
        ctfd_inventory = json.loads((self.runtime / 'inventories' / 'ctfd-inventory.json')
                                    .read_text(encoding='utf-8'))['inventory']
        discovered = _derive_discovered(inventory, ctfd_inventory)
        self.discovered_path.write_text(json.dumps(discovered, indent=2), encoding='utf-8')
        self._render_env()  # central.env now carries the discovered RIDGE_IRIS_* IDs
        self._compose('central', 'up', '-d', 'iris', 'iris-worker')

    def _probe_identities(self):
        for name in ('iris-inventory.json', 'ctfd-inventory.json'):
            path = self.runtime / 'inventories' / name
            if not path.is_file():
                raise LifecycleError('missing %s: identities were never provisioned; run up'
                                     % path)
        if not self.discovered_path.is_file():
            raise LifecycleError('missing %s: discovered application IDs are not recorded; '
                                 'run up' % self.discovered_path)
        hosts = self._service_hosts()
        url = self._public_url(hosts['ctfd'], self._public_port('ctfd', 8083)) + '/login'
        status, _ = self.host.http_json('GET', url,
                                        ca_file=self._participant_ca_file())
        if status != 200:
            raise LifecycleError('provisioned CTFd login returned HTTP %s at %s' % (status, url))
        return {'inventories': 2}

    # S5 ----------------------------------------------------------- desktops
    def _desktop_services(self):
        from ridge.docker_provider import team_service
        if self.profile.get('registration', {}).get('enabled', False):
            return []
        return [team_service('team%02d' % (i + 1)) for i in range(len(self.teams))]

    def _configured_desktop_services(self):
        if self.profile.get('registration', {}).get('enabled', False):
            return [desktop['name'] for desktop in self.profile['desktops']]
        return self._desktop_services()

    def _apply_desktops(self):
        if not self.profile.get('registration', {}).get('enabled', False):
            self._start_desktop_services(self._desktop_services())
        sql = (self.runtime / 'guac-init' / '002-provision.sql').read_text(encoding='utf-8')
        self._pipe(['docker', 'compose', '--env-file', self.env_dir / 'guacamole.env',
                    '-f', COMPOSE_FILES['guacamole'], 'exec', '-T', 'database',
                    'psql', '-U', 'guacamole', '-d', 'guacamole', '-v', 'ON_ERROR_STOP=1'],
                   sql)

    def _pipe(self, argv, text):
        """Run argv with stdin text through the real subprocess runner."""
        if hasattr(self.runner, 'run_stdin'):
            return self.runner.run_stdin([str(a) for a in argv], text, check=True)
        creationflags = getattr(subprocess, 'CREATE_NO_WINDOW', 0) if os.name == 'nt' else 0
        completed = subprocess.run([str(a) for a in argv], input=text, capture_output=True,
                                   text=True, timeout=120, creationflags=creationflags)
        if completed.returncode != 0:
            raise LifecycleError('provisioning SQL failed: %s' % completed.stderr.strip()[:300])
        return completed.stdout.strip()

    def register_once(self):
        """Provision one pending self-service registration.

        This method runs on the event host, outside participant containers. It
        is intentionally the only path that can start a new desktop service or
        apply Guacamole SQL. The public CTFd registration page only writes the
        allocator's SQLite row.
        """
        from ridge.registration import (RegistrationConfig, RegistrationStore,
                                        desktop_handout)
        registration_path = self.registration_dir / 'registrations.sqlite'
        registration = RegistrationStore(
            str(registration_path),
            RegistrationConfig(
                max_teams=self.profile['registration']['max_teams'],
                members_per_team=self.profile['registration']['members_per_team']),
            enrollment_code=self._secret('registration-enrollment-code'))
        if not getattr(self, '_registration_acl_secured', False):
            _secure_private(registration_path)
            self._registration_acl_secured = True
        claimed = registration.claim_pending()
        if claimed is None:
            return None
        worker_token = claimed['worker_token']
        credentials = registration.activate_credentials(claimed['id'], worker_token)
        wazuh_username, separator, wazuh_password = self._secret('wazuh_reader').partition(':')
        if not separator or not wazuh_username or not wazuh_password:
            raise LifecycleError('wazuh_reader must contain username:password')
        # Wazuh is intentionally one shared read-only classroom account. Include
        # it only in the private retrieval handout; never in public registration
        # state or repository configuration.
        credentials['wazuh'] = {
            'username': wazuh_username,
            'password': wazuh_password,
        }
        services = list(claimed['slots'])
        try:
            self._start_desktop_services(services)
            ctfd = self._compose('central', 'exec', '-T', 'ctfd', 'flask',
                                 'silent-ridge-register', '--registration-id', str(claimed['id']))
            iris = self._compose('central', 'exec', '-T', 'iris', 'flask',
                                 'silent-ridge-register', '--registration-id', str(claimed['id']))
            ctfd_row = self._last_json(ctfd, 'CTFd registration')
            iris_row = self._last_json(iris, 'IRIS registration')
            team_id = 'team-%02d' % claimed['id']
            self._apply_registration_guacamole(team_id, services, credentials)
            self._register_controller_team(team_id, claimed['team_name'],
                                           iris_row['iris_id'], ctfd_row['team_id'],
                                           credentials)
            result = {'desktop_urls': desktop_handout(
                services, self.profile['addresses']['guacamole_public_url'])}
            registration.complete(claimed['id'], result, worker_token,
                                  credentials=credentials)
            return {'id': claimed['id'], 'team': team_id, 'desktops': services}
        except Exception as exc:
            if registration.requeue(claimed['id'], str(exc), worker_token):
                self._stop_desktop_services(services)
            raise

    def registration_admin(self, action, registration_id=None):
        """Audited host-side controls for the public allocator; never exposes passwords."""
        if not self.profile.get('registration', {}).get('enabled', False):
            raise LifecycleError('dynamic registration is not enabled for this profile')
        from ridge.registration import RegistrationConfig, RegistrationStore
        registration_path = self.registration_dir / 'registrations.sqlite'
        store = RegistrationStore(
            str(registration_path),
            RegistrationConfig(
                max_teams=self.profile['registration']['max_teams'],
                members_per_team=self.profile['registration']['members_per_team']),
            enrollment_code=self._secret('registration-enrollment-code'))
        _secure_private(registration_path)
        if action == 'status':
            return {'gate': 'enrollment_code', 'capacity': store.capacity(),
                    'worker': self._registration_worker_status(),
                    'registrations': store.list()}
        if registration_id is None:
            raise LifecycleError('registration ID is required for %s' % action)
        if action == 'retry':
            store.retry(registration_id)
            return {'id': registration_id, 'status': 'pending'}
        if action == 'cancel':
            store.cancel(registration_id)
            return {'id': registration_id, 'status': 'cancelled'}
        if action == 'rotate-link':
            code = store.rotate_access(registration_id)
            return {'id': registration_id,
                    'retrieve_path': '/silent-ridge/registration/' + code,
                    'sensitive': True}
        raise LifecycleError('unknown registration action %s' % action)

    @staticmethod
    def _last_json(output, label):
        for line in reversed(str(output).splitlines()):
            try:
                value = json.loads(line)
            except ValueError:
                continue
            if isinstance(value, dict):
                return value
        raise LifecycleError('%s returned no JSON result' % label)

    def _register_controller_team(self, team_id, name, iris_id, ctfd_id, credentials):
        config_path = self.state_dir / 'config.json'
        config = json.loads(config_path.read_text(encoding='utf-8'))
        existing = {team['id']: team for team in config.get('teams', [])}
        row = {'id': team_id, 'name': name, 'iris': str(iris_id), 'ctfd': int(ctfd_id),
               'iris_login': credentials['iris']['username'],
               'ctfd_name': name}
        if team_id in existing and existing[team_id] != row:
            raise LifecycleError('registration team mapping differs from controller config')
        if team_id not in existing:
            config.setdefault('teams', []).append(row)
            config_path.write_text(json.dumps(config, indent=2), encoding='utf-8')
        self.host.state(self.state_path).register_team({
            'id': team_id, 'name': name, 'iris': str(iris_id), 'ctfd': int(ctfd_id)})

    def _apply_registration_guacamole(self, team_id, services, credentials):
        import sys
        sys.path.insert(0, str(COMPOSE_DIR))
        import guacamole as guac_module
        all_credentials = self._team_credentials()
        desktops = {desktop['name']: desktop for desktop in self.profile['desktops']}
        config = {'desktops': [self._guacamole_desktop(desktops[slot])
                               for slot in services],
            'teams': [{'id': team_id, 'desktops': services}]}
        guac_credentials = {
            'teams': {team_id: {'username': credentials['guacamole']['username'],
                                'password': credentials['guacamole']['password']}},
            'desktops': {slot: {'password': all_credentials['desktops'][slot]['password']}
                         for slot in services},
            'facilitator': {'username': 'admin',
                            'password': self._secret('guac-facilitator-password')},
        }
        sql = guac_module.generate(config, guac_credentials)
        self._pipe(['docker', 'compose', '--env-file', self.env_dir / 'guacamole.env',
                    '-f', COMPOSE_FILES['guacamole'], 'exec', '-T', 'database',
                    'psql', '-U', 'guacamole', '-d', 'guacamole', '-v', 'ON_ERROR_STOP=1'], sql)

    def registration_loop(self, interval=1.0):
        """Run the host allocator until interrupted; no participant code runs here."""
        stopped = threading.Event()
        def beat():
            while not stopped.is_set():
                self._write_registration_heartbeat()
                stopped.wait(5)
        heartbeat = threading.Thread(target=beat, daemon=True)
        heartbeat.start()
        try:
            while True:
                try:
                    self.register_once()
                except Exception as exc:
                    # Keep the service alive for later registrations; the failed
                    # row is visible through its retrieval page and in host logs.
                    logging.error('registration provisioning failed: %s', exc)
                time.sleep(interval)
        finally:
            stopped.set()
            heartbeat.join(timeout=6)

    @property
    def registration_pid_path(self):
        return self.runtime / 'registration-worker.pid'

    @property
    def registration_heartbeat_path(self):
        return self.runtime / 'registration-worker-heartbeat.json'

    def _write_registration_heartbeat(self):
        token = os.environ.get('RIDGE_REGISTRATION_WORKER_TOKEN', '')
        value = json.dumps({
            'pid': os.getpid(), 'token': token, 'updated': time.time()}) + '\n'
        if getattr(self, '_registration_heartbeat_acl_secured', False):
            self.registration_heartbeat_path.write_text(value, encoding='utf-8')
            os.chmod(self.registration_heartbeat_path, stat.S_IRUSR | stat.S_IWUSR)
        else:
            _write_private(self.registration_heartbeat_path, value)
            self._registration_heartbeat_acl_secured = True

    def _registration_worker_status(self):
        if not self.profile.get('registration', {}).get('enabled', False):
            return {'enabled': False, 'healthy': True}
        try:
            saved = json.loads(self.registration_pid_path.read_text(encoding='utf-8'))
            heartbeat = json.loads(self.registration_heartbeat_path.read_text(encoding='utf-8'))
            pid = int(saved['pid'])
            token_ok = bool(saved.get('token')) and saved.get('token') == heartbeat.get('token')
            heartbeat_pid_ok = int(heartbeat['pid']) == pid
            fresh = time.time() - float(heartbeat.get('updated', 0)) < 15
            saved_identity = _normalize_process_identity(saved.get('identity'))
            current_identity = _process_identity(pid)
            alive = current_identity is not None
            identity_ok = (saved_identity is not None and
                           current_identity == saved_identity)
            identity_verified = bool(token_ok and heartbeat_pid_ok and identity_ok)
            return {'enabled': True, 'healthy': bool(identity_verified and fresh),
                    'pid': pid, 'alive': alive, 'heartbeat_fresh': fresh,
                    'identity_verified': identity_verified}
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
            return {'enabled': True, 'healthy': False,
                    'error': 'registration worker PID/heartbeat is missing or invalid'}

    def _start_registration_worker(self):
        if not self.profile.get('registration', {}).get('enabled', False):
            return None
        if self.registration_pid_path.is_file():
            status = self._registration_worker_status()
            if status.get('healthy'):
                return status['pid']
            # Never kill an unverified reused PID. A verified stale worker is
            # stopped before replacement; an unverified record is simply retired.
            if status.get('identity_verified'):
                self._stop_registration_worker()
            self.registration_pid_path.unlink(missing_ok=True)
            self.registration_heartbeat_path.unlink(missing_ok=True)
        log_path = self.runtime / 'registration-worker.log'
        log = log_path.open('a', encoding='utf-8')
        command = [sys.executable, '-m', 'ridge.deploy.registration_worker',
                   '--profile', str(self.runtime / 'registration-profile.json'),
                   '--runtime', str(self.runtime)]
        (self.runtime / 'registration-profile.json').write_text(
            json.dumps(self.profile, indent=2), encoding='utf-8')
        creationflags = (getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0) |
                         getattr(subprocess, 'DETACHED_PROCESS', 0) |
                         getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        token = self.host.randhex(24)
        environment = dict(os.environ, RIDGE_REGISTRATION_WORKER_TOKEN=token)
        process = subprocess.Popen(command, cwd=str(ROOT), stdout=log, stderr=log,
                                   creationflags=creationflags, env=environment,
                                   start_new_session=(os.name != 'nt'))
        log.close()
        identity = None
        for _ in range(20):
            if process.poll() is not None:
                break
            identity = _process_identity(process.pid)
            if identity is not None:
                break
            time.sleep(.1)
        if identity is None:
            try:
                process.terminate()
                process.wait(timeout=5)
            except (OSError, subprocess.SubprocessError, subprocess.TimeoutExpired):
                try:
                    process.kill()
                except OSError:
                    pass
            self.registration_heartbeat_path.unlink(missing_ok=True)
            raise LifecycleError('registration worker process identity could not be verified; '
                                 'the worker was stopped before publishing a PID record')
        _write_private(self.registration_pid_path, json.dumps({
            'pid': process.pid, 'token': token, 'started': time.time(),
            'identity': identity}) + '\n')
        for _ in range(50):
            status = self._registration_worker_status()
            if status.get('healthy'):
                return process.pid
            if process.poll() is not None:
                break
            time.sleep(.1)
        raise LifecycleError('registration worker failed to publish a healthy heartbeat; '
                             'inspect %s' % log_path)

    def _stop_registration_worker(self):
        if not self.registration_pid_path.is_file():
            return False
        status = self._registration_worker_status()
        if not status.get('identity_verified'):
            self.registration_pid_path.unlink(missing_ok=True)
            self.registration_heartbeat_path.unlink(missing_ok=True)
            return False
        try:
            pid = int(status['pid'])
            if os.name == 'nt':
                subprocess.run(['taskkill', '/PID', str(pid), '/T', '/F'],
                               capture_output=True, timeout=10)
            else:
                os.killpg(pid, signal.SIGTERM)
        except (OSError, ValueError, subprocess.SubprocessError):
            pass
        self.registration_pid_path.unlink(missing_ok=True)
        self.registration_heartbeat_path.unlink(missing_ok=True)
        return True

    def _probe_desktops(self):
        self._require_desktop_services(self._desktop_services())
        out = self._compose('guacamole', 'exec', '-T', 'database', 'psql', '-U', 'guacamole',
                            '-d', 'guacamole', '-tA', '-c',
                            'SELECT count(*) FROM guacamole_connection')
        try:
            count = int(out.strip().splitlines()[-1])
        except (ValueError, IndexError):
            raise LifecycleError('could not read guacamole_connection count: %r' % out[:200])
        expected = (len(self.profile['desktops'])
                    if self.profile.get('registration', {}).get('enabled', False)
                    else len(self.teams))
        if count < expected:
            raise LifecycleError('guacamole has %d connections for %d desktop slots; provisioning SQL '
                                 'was not applied' % (count, expected))
        return {'desktops': expected, 'connections': count}

    # S6 ----------------------------------------------------------- evidence
    def _index_name(self):
        name = self.local.get('index_name') or 'silent-ridge-' + self.event.replace('silent-ridge-', '')
        from ridge.wazuh_provision import validate_index_name
        return validate_index_name(name)

    def _wazuh(self, method, base, path, credential, body=None, headers=None):
        status, payload = self.host.wazuh_request(
            method, base + path, self._participant_ca_file(),
            credential, body, headers=headers)
        return status, payload

    def _indexer_job(self, action, backup_dir=None):
        """Run apply/probe/dump/load inside the integration image on the Wazuh
        backend network.

        The indexer is on an `internal: true` network with no host-published port,
        so indexer traffic must come from a container, never from the host.
        """
        index_name = self._index_name()
        network = self.event + '-wazuh_wazuh-backend'
        argv = ['docker', 'run', '--rm', '--network', network,
                '-e', 'WAZUH_INDEXER_URL=https://wazuh-indexer:9200',
                '-v', str(ROOT / 'ridge') + ':/opt/silent-ridge/ridge:ro',
                '-v', str(self.runtime / 'wazuh-certs') + ':/certs:ro',
                '-v', str(self.secrets_dir) + ':/secrets:ro',
                '-v', str(self.asset('evidence_public')) + ':/evidence:ro']
        if backup_dir is not None:
            argv += ['-v', str(Path(backup_dir).resolve()) + ':/backup']
        argv += ['--entrypoint', 'python', 'silent-ridge-integration:dev',
                 '-m', 'ridge.deploy.indexer_job', action, index_name]
        out = self._run(argv)
        try:
            return json.loads(out.strip().splitlines()[-1])
        except (ValueError, IndexError):
            raise LifecycleError('indexer job %s returned no JSON result: %s'
                                 % (action, out.strip()[-300:]))

    def _apply_evidence(self):
        from ridge.wazuh_provision import saved_objects
        index_name = self._index_name()
        applied = self._indexer_job('apply')
        # Reach the dashboard on the address it is actually published on. It is
        # bound to local.json's bind_ip, not necessarily loopback, so a hardcoded
        # 127.0.0.1 fails with ECONNREFUSED on a host that binds a LAN address.
        dashboard = self._public_url(self._service_hosts()['wazuh'],
                                     self._public_port('wazuh', 8443))
        admin = self._secret('wazuh_admin')
        for view in saved_objects(applied['field_caps']):
            status, payload = self._wazuh(
                'POST', dashboard,
                '/api/saved_objects/index-pattern/%s?overwrite=true' % view['id'],
                admin, {'attributes': view['attributes']}, headers={'osd-xsrf': 'true'})
            if status != 200:
                raise LifecycleError('saved view %s failed with HTTP %s: %s'
                                     % (view['id'], status, str(payload)[:200]))
        return {'index': index_name}

    def _probe_evidence(self):
        index_name = self._index_name()
        result = self._indexer_job('probe')
        status, payload = result['status'], {'count': result.get('count', 0)}
        if status != 200:
            raise LifecycleError('historical index %s unavailable (HTTP %s); run up to '
                                 'reconcile evidence' % (index_name, status))
        try:
            self._compose('wazuh', 'exec', '-T', 'wazuh-manager', 'filebeat',
                          'test', 'output', '-c', '/etc/filebeat/filebeat.yml')
        except Exception as exc:
            raise LifecycleError('Filebeat cannot authenticate to the CA-verified Wazuh '
                                 'indexer: %s' % str(exc)[:250])
        telemetry = self.asset('evidence_public') / 'wazuh' / 'telemetry.jsonl'
        if telemetry.is_file():
            # ridge.evidence_release.index derives each document ID from a
            # canonical hash of the record body, so duplicate lines collapse
            # to one document by design; expect unique records, not raw lines.
            bodies = {json.dumps(json.loads(line), sort_keys=True)
                      for line in telemetry.read_text(encoding='utf-8').splitlines()
                      if line.strip()}
            expected = len(bodies)
            if payload.get('count', 0) < expected:
                raise LifecycleError('historical index has %d documents; expected at least %d '
                                     'from %s' % (payload.get('count', 0), expected, telemetry))
        from ridge.docker_provider import team_service
        if self.profile.get('registration', {}).get('enabled', False):
            return {'deferred': 'desktop evidence probe runs after each team registration'}
        for i in range(len(self.teams)):
            service = team_service('team%02d' % (i + 1))
            worker_id = self._desktop_spec(service).get('worker', 'local')
            out = self._desktop_compose(
                worker_id, 'exec', '-T', service, 'bash', '-c',
                'ls /evidence/network/sensor.pcap /evidence/wazuh/telemetry.jsonl',
                check=False)
            if 'sensor.pcap' not in out:
                raise LifecycleError('evidence is not visible on desktop %s under /evidence'
                                     % service)
        return {'index': index_name, 'documents': payload.get('count', 0)}

    # S7 -------------------------------------------------- provisioned-paused
    def _controller_config(self):
        if self.profile.get('registration', {}).get('enabled', False):
            registration = self.profile['registration']
            return {
                'exercise_date': self.profile['event']['incident_date'],
                'teams': [],
                'registration': {
                    'enabled': True, 'max_teams': registration['max_teams'],
                    'members_per_team': registration['members_per_team'],
                    'desktops_per_team': registration['desktops_per_team'],
                },
            }
        discovered = json.loads(self.discovered_path.read_text(encoding='utf-8'))
        credentials = self._team_credentials()
        teams = []
        for team in self.teams:
            ids = discovered['teams'][team['name']]
            teams.append({'id': team['name'], 'name': team['name'],
                          'iris': str(ids['iris_id']), 'ctfd': int(ids['ctfd_id']),
                          'iris_login': credentials['teams'][team['name']]['iris_login'],
                          'ctfd_name': credentials['teams'][team['name']]['ctfd_name']})
        return {'exercise_date': self.profile['event']['incident_date'], 'teams': teams}

    def _apply_provisioned(self):
        self.state_dir.mkdir(parents=True, exist_ok=True)
        config_path = self.state_dir / 'config.json'
        if config_path.is_file() and self.state_path.is_file():
            # Adopted runtime: never rewrite a live controller config or state.
            config = json.loads(config_path.read_text(encoding='utf-8'))
        else:
            config = self._controller_config()
            config_path.write_text(json.dumps(config, indent=2), encoding='utf-8')
            if not self.state_path.is_file():
                tickets = self.host.author_tickets(config)
                self.host.state(self.state_path).initialize(
                    config['teams'], tickets,
                    allow_empty=self.profile.get('registration', {}).get('enabled', False))
        self._compose('integration', 'up', '-d', '--wait', '--wait-timeout', '300')
        state = self.host.state(self.state_path)
        with state.transaction(write=False) as con:
            provisioned = con.execute('SELECT provisioned FROM control').fetchone()[0]
        if not provisioned:
            state.provision(self.operator)

    def _controller_preflight(self):
        """Run the real controller preflight inside the integration container.

        The container spans the central and Wazuh backend networks and carries
        the bridge secrets; the host can reach neither the internal IRIS/CTFd
        URLs nor the indexer.
        """
        try:
            out = self._compose('integration', 'exec', '-T', 'integration',
                                'python', '-m', 'ridge.cli', '--state', '/state/state.sqlite',
                                'preflight', '--config', '/state/config.json')
        except Exception as exc:
            raise LifecycleError('controller preflight could not run: %s' % exc)
        try:
            return json.loads(out.strip().splitlines()[-1])
        except (ValueError, IndexError):
            raise LifecycleError('controller preflight returned no JSON result: %s'
                                 % out.strip()[-300:])

    def _probe_exercise(self, expected_mode):
        if not self.state_path.is_file():
            raise LifecycleError('exercise state %s is missing; run up' % self.state_path)
        state = self.host.state(self.state_path)
        mode = self._state_mode(state)
        if mode != expected_mode:
            raise LifecycleError("exercise mode is %r, expected %r" % (mode, expected_mode))
        config = json.loads((self.state_dir / 'config.json').read_text(encoding='utf-8'))
        ready = self._controller_preflight()
        if ready.get('ready') is not True:
            raise LifecycleError('controller preflight failed: %s' % ready)
        services = self._ps('integration')
        controller = services.get('integration')
        if controller is None or controller['state'] != 'running':
            raise LifecycleError('integration controller is not running; run up to reconcile')
        return {'mode': mode, 'teams': ready.get('teams'), 'tickets': ready.get('tickets')}

    def _probe_provisioned(self):
        return self._probe_exercise('paused')

    def _probe_running(self):
        return self._probe_exercise('running')

    def _state_mode(self, state):
        with state.transaction(write=False) as con:
            return con.execute('SELECT mode FROM run').fetchone()[0]

    def _state_pending(self, state):
        with state.transaction(write=False) as con:
            return con.execute('SELECT COUNT(*) FROM outbox WHERE done=0').fetchone()[0]

    # -------------------------------------------------------------- lifecycle

    def _journal(self, release_fingerprint):
        path = self.runtime / 'deploy-journal.sqlite'
        if path.is_file() and path.stat().st_size:
            journal = Journal.open(path)
            # A failed first provisioning can leave an empty NEW journal before
            # the controller state database exists.  A reviewed rebuild should
            # be able to resume that setup without treating it as a live-run
            # migration; there is no participant state to migrate at this point.
            journal.check_fingerprints(
                self.profile,
                self.profile['event']['release_id'],
                release_fingerprint,
                migrate=(journal.state == 'NEW' and not self.state_path.is_file()),
            )
            return journal
        return Journal.create(path, self.profile, self.profile['event']['release_id'],
                              release_fingerprint)

    def _stage_ops(self, stage):
        return {
            'ARTIFACTS_VERIFIED': (None, self._probe_artifacts),
            'INFRASTRUCTURE_READY': (self._apply_infrastructure, self._probe_infrastructure),
            'APPLICATIONS_READY': (self._apply_applications, self._probe_applications),
            'IDENTITIES_READY': (self._apply_identities, self._probe_identities),
            'DESKTOPS_READY': (self._apply_desktops, self._probe_desktops),
            'EVIDENCE_READY': (self._apply_evidence, self._probe_evidence),
            'PROVISIONED_PAUSED': (self._apply_provisioned, self._probe_provisioned),
        }[stage]

    def up(self, release_fingerprint):
        """Bring the run to PROVISIONED_PAUSED. Repeating preserves state; a verified
        stage whose probe now fails is an actionable error, never a reset."""
        self.release_fingerprint = release_fingerprint
        journal = self._journal(release_fingerprint)
        with journal.lock(self.operator):
            resumable = journal.state == 'STOPPED'
            summary = {}
            for stage in self.STAGES:
                apply, probe = self._stage_ops(stage)
                step = journal.step(stage)
                if step and step['state'] == 'verified':
                    try:
                        summary[stage] = probe()
                        continue
                    except LifecycleError as exc:
                        if not resumable:
                            raise LifecycleError(
                                'previously verified stage %s no longer verifies: %s. The '
                                'missing or changed resource must be restored; up will not '
                                'recreate it silently' % (stage, exc))
                        # After an intentional `down`, stopped resources are expected:
                        # re-apply and re-verify rather than refusing.
                        journal.reopen_step(stage)
                        try:
                            if apply is not None:
                                apply()
                            summary[stage] = probe()
                            journal.complete_step(stage, json.dumps(summary[stage],
                                                                    sort_keys=True)[:400])
                        except Exception as exc2:
                            journal.fail_step(stage, exc2)
                            raise
                        continue
                journal.begin_step(stage)
                try:
                    if apply is not None:
                        apply()
                    detail = probe()
                    journal.complete_step(stage, json.dumps(detail, sort_keys=True)[:400])
                    summary[stage] = detail
                except Exception as exc:
                    journal.fail_step(stage, exc)
                    raise
            journal.set_state('PROVISIONED_PAUSED')
            return {'state': journal.state, 'stages': summary}

    def _require_paused(self, action):
        try:
            journal = Journal.open(self.runtime / 'deploy-journal.sqlite')
        except JournalError as exc:
            raise LifecycleError('%s requires a deployment journal; run `python -m '
                                 'ridge.deploy up` first (%s)' % (action, exc))
        if journal.state != 'PROVISIONED_PAUSED':
            raise LifecycleError('%s requires journal state PROVISIONED_PAUSED, found %s; '
                                 'run `python -m ridge.deploy up` first' % (action, journal.state))
        for step in journal.steps():
            if step['state'] != 'verified':
                raise LifecycleError('%s refused: stage %s is %s. Resolve it with up; start '
                                     'never skips failed checks' % (action, step['name'], step['state']))
        return journal

    def start(self, release_fingerprint):
        """Explicitly start the exercise. Only runs after full readiness."""
        journal = self._require_paused('start')
        journal.check_fingerprints(self.profile, self.profile['event']['release_id'],
                                   release_fingerprint)
        with journal.lock(self.operator):
            # Re-probe every stage: start is refused when any gate fails now.
            for stage in self.STAGES:
                _, probe = self._stage_ops(stage)
                probe()
            state = self.host.state(self.state_path)
            ready = self._controller_preflight()
            if ready.get('ready') is not True:
                raise LifecycleError('start refused: preflight failed: %s' % ready)
            state.mode(self.operator, 'running')
            actual = self._state_mode(state)
            if actual != 'running':
                raise LifecycleError("mode transition did not persist (found %r)" % actual)
            try:
                worker = self._start_registration_worker()
            except Exception:
                state.mode(self.operator, 'paused')
                raise
            journal.set_state('RUNNING')
            return {'state': 'RUNNING', 'mode': actual, **({'registration_worker_pid': worker}
                                                            if worker else {})}

    def pause(self):
        journal = Journal.open(self.runtime / 'deploy-journal.sqlite')
        with journal.lock(self.operator):
            self._stop_registration_worker()
            state = self.host.state(self.state_path)
            before = self._state_mode(state)
            state.mode(self.operator, 'paused')
            actual = self._state_mode(state)
            if actual != 'paused':
                raise LifecycleError("pause did not persist (mode is %r)" % actual)
            if journal.state == 'RUNNING':
                journal.set_state('PROVISIONED_PAUSED')
            return {'previous': before, 'mode': actual, 'state': journal.state}

    def status(self):
        """Truthful structured status: journal facts plus live re-probes. A probe
        failure is reported, never hidden."""
        document = {'event': self.event, 'journal': None, 'steps': [], 'live': {},
                    'event_ready': False}
        path = self.runtime / 'deploy-journal.sqlite'
        journal = None
        if path.is_file() and path.stat().st_size:
            journal = Journal.open(path)
            document['journal'] = journal.state
            document['steps'] = [{'name': s['name'], 'state': s['state'],
                                  'attempt': s['attempt'], 'detail': s.get('detail')}
                                 for s in journal.steps()]
        for stage in self.STAGES:
            _, probe = self._stage_ops(stage)
            if stage == 'PROVISIONED_PAUSED' and journal is not None and journal.state == 'RUNNING':
                probe = self._probe_running
            try:
                document['live'][stage] = {'ok': True, 'detail': probe()}
            except Exception as exc:
                document['live'][stage] = {'ok': False, 'error': str(exc)[:300]}
        if self.state_path.is_file():
            try:
                exercise_state = self.host.state(self.state_path)
                document['live']['exercise'] = {'ok': True, 'mode': self._state_mode(exercise_state),
                                                'pending': self._state_pending(exercise_state)}
            except Exception as exc:
                document['live']['exercise'] = {'ok': False, 'error': str(exc)[:300]}
        if self.profile.get('registration', {}).get('enabled', False):
            worker = self._registration_worker_status()
            try:
                from ridge.registration import RegistrationConfig, RegistrationStore
                registration_path = self.registration_dir / 'registrations.sqlite'
                store = RegistrationStore(
                    str(registration_path),
                    RegistrationConfig(
                        max_teams=self.profile['registration']['max_teams'],
                        members_per_team=self.profile['registration']['members_per_team']),
                    enrollment_code=self._secret('registration-enrollment-code'))
                _secure_private(registration_path)
                pending = store.list()
                worker['queue'] = {
                    'pending': sum(row['status']=='pending' for row in pending),
                    'provisioning': sum(row['status']=='provisioning' for row in pending),
                    'needs_operator': sum(row['status']=='needs_operator' for row in pending)}
            except Exception as exc:
                worker = {'enabled': True, 'healthy': False, 'error': str(exc)[:300]}
            running_expected = journal is not None and journal.state == 'RUNNING'
            document['live']['registration_worker'] = {
                'ok': bool(worker.get('healthy')) if running_expected else True,
                'detail': dict(worker, expected='running' if running_expected else 'stopped while paused')}
        steps_ok = (journal is not None
                    and all(s['state'] == 'verified' for s in journal.steps()))
        probes_ok = all(entry.get('ok') for entry in document['live'].values())
        document['event_ready'] = bool(steps_ok and probes_ok
                                       and document['live'].get('exercise', {}).get('ok'))
        return document

    def down(self, volumes=False):
        """Stop every project, preserving volumes and state. With --volumes, also
        remove event-owned volumes — destructive, and refused unless a completed,
        verified recovery set exists under runtime/backups that still matches the
        live exercise state. Both checks run BEFORE anything is stopped: a refused
        wipe must never take the event offline."""
        journal = Journal.open(self.runtime / 'deploy-journal.sqlite')
        with journal.lock(self.operator):
            if volumes and self._remote_worker_ids():
                remote_volumes = []
                prefix = self.event + '-'
                for worker_id in self._remote_worker_ids():
                    context = self._worker(worker_id)['docker_context']
                    names = self._run([
                        'docker', '--context', context, 'volume', 'ls',
                        '--format', '{{.Name}}',
                    ]).splitlines()
                    remote_volumes.extend('%s:%s' % (worker_id, name)
                                          for name in names if name.startswith(prefix))
                if remote_volumes:
                    raise LifecycleError(
                        'down --volumes refused: remote desktop workers own event volumes '
                        'that the current recovery-set format does not capture (%s). Stop '
                        'without --volumes; do not erase worker volumes until a verified '
                        'export has been collected from every worker. Nothing was stopped '
                        'or removed.' % ', '.join(remote_volumes[:3]))
            verified = None
            if volumes:
                from ridge.deploy import recovery
                backups = self.runtime / 'backups'
                sets = sorted(backups.iterdir()) if backups.is_dir() else []
                for candidate in reversed(sets):
                    try:
                        recovery.verify_set(candidate)
                        verified = candidate
                        break
                    except recovery.RecoveryError:
                        continue
                if verified is None:
                    raise LifecycleError('down --volumes refused: no completed, verified '
                                         'recovery set under %s; run backup first. Nothing '
                                         'was stopped or removed.' % backups)
                backup_mark, _ = _state_watermark(verified / 'state' / 'state.sqlite')
                live_mark, live_fenced = _state_watermark(self.state_path)
                if live_mark > backup_mark and not live_fenced:
                    raise LifecycleError('down --volumes refused: the exercise progressed '
                                         '(audit watermark %d) after the newest verified '
                                         'recovery set was taken (%d); run backup again to '
                                         'capture the newer scores and work. Nothing was '
                                         'stopped or removed.' % (live_mark, backup_mark))
                # A fenced site is exempt from the freshness check: fencing only
                # appends control-plane audit rows, and backup deliberately refuses
                # fenced sites — the pre-fence set is the final state by design.
            self._stop_registration_worker()
            stopped = []
            for worker_id in self._remote_worker_ids():
                self._desktop_compose(worker_id, 'stop', check=False)
                stopped.append('desktops@' + worker_id)
            for kind in ('integration', 'desktops', 'guacamole', 'central', 'wazuh'):
                if volumes:
                    # Remove containers and networks so volume removal is possible.
                    self._compose(kind, 'down')
                else:
                    self._compose(kind, 'stop', check=False)
                stopped.append(kind)
            self._remove_guacamole_relays()
            removed = []
            if volumes:
                names = recovery.event_volumes(
                    self.event, self.teams,
                    self.registration_dir / 'registrations.sqlite'
                    if self.profile.get('registration', {}).get('enabled', False) else None)
                before = set(self._run(
                    ['docker', 'volume', 'ls', '--format', '{{.Name}}']).splitlines())
                for name in names:
                    if name in before:
                        self._run(['docker', 'volume', 'rm', '-f', name])
                after = set(self._run(
                    ['docker', 'volume', 'ls', '--format', '{{.Name}}']).splitlines())
                remaining = sorted(after.intersection(names))
                if remaining:
                    raise LifecycleError('down --volumes failed: event-owned volumes remain '
                                         '(%s); restore is unsafe until they are removed'
                                         % ', '.join(remaining[:3]))
                removed = [name for name in names if name in before]
            journal.set_state('STOPPED')
            return {'state': 'STOPPED', 'projects': stopped, 'volumes_removed': removed}

    def backup(self):
        """D02 full recovery set: paused+drained, native DB dumps, Wazuh index
        snapshot, app data and per-team volumes, evidence, vault, encrypted
        secrets, resource mapping and receipt watermarks. Completion marker last."""
        from ridge.deploy import recovery
        journal = Journal.open(self.runtime / 'deploy-journal.sqlite')
        with journal.lock(self.operator):
            if getattr(self, 'release_fingerprint', None) is None:
                self.release_fingerprint = journal.meta().get('release_fingerprint')
            try:
                return recovery.create(self, self.runtime / 'backups'
                                       / _utcnow().strftime('%Y%m%dT%H%M%SZ'),
                                       cipher=getattr(self, 'cipher', None),
                                       export_job=getattr(self, 'export_job', None))
            except recovery.RecoveryError as exc:
                raise LifecycleError(str(exc))

    def fence(self):
        """F01: permanently disable writes on this site (paused + drained first),
        then stop the mutation paths so stale workers cannot resume writes."""
        journal = Journal.open(self.runtime / 'deploy-journal.sqlite')
        with journal.lock(self.operator):
            state = self.host.state(self.state_path)
            from ridge.state import Conflict
            try:
                state.fence(self.operator)
            except Conflict as exc:
                raise LifecycleError(str(exc))
            self._compose('integration', 'stop', check=False)
            for worker_id in self._remote_worker_ids():
                self._desktop_compose(worker_id, 'stop', check=False)
            self._compose('desktops', 'stop', check=False)
            self._remove_guacamole_relays()
            journal.set_state('FENCED')
            return dict({'state': 'FENCED'}, **state.site_info())

    def restore(self):
        raise LifecycleError('restore needs an explicit clean destination runtime: run '
                             '`python -m ridge.deploy restore --profile <profile> '
                             '--runtime <clean runtime> --from <recovery set>`. '
                             'No state was changed.')

    def switch(self):
        raise LifecycleError('provider switch to AWS is blocked on E04 (no authorized AWS '
                             'provider in this environment). Local fencing (fence action) and '
                             'clean-destination restore are implemented; no state was changed.')
