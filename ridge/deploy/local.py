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
      wazuh-certs/              local CA + node certs (generate-certs.sh output)
      state/state.sqlite        exercise core state (paused by default)
      state/config.json         controller config materialized from discovered identities
      inventories/              IRIS/CTFd provisioning inventories (no passwords)
      discovered.json           application IDs discovered from live inventories
      backups/<utc>/            logical backups with SHA256 manifest
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import subprocess
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
    'central': ['iris', 'iris-worker', 'ctfd'],
    'wazuh': ['wazuh-dashboard'],
    'guacamole': ['guacamole'],
}
IMAGE_COMPONENTS = ('iris', 'ctfd', 'integration', 'desktop')
SECRET_FILES = (
    'postgres-password', 'iris-secret-key', 'iris-password-salt', 'iris-admin-password',
    'ctfd-secret-key', 'mariadb-root-password', 'mariadb-ctfd-password',
    'ridge-iris-bridge', 'ridge-ctfd-bridge',
    'wazuh_admin', 'wazuh_writer', 'wazuh_reader', 'guac-db-password',
)


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

    def http_json(self, method, url, headers=None, body=None, timeout=10):
        from urllib.request import Request, urlopen
        from urllib.error import HTTPError
        data = json.dumps(body).encode() if body is not None else None
        request = Request(url, data=data, method=method,
                          headers={'Content-Type': 'application/json', **(headers or {})})
        try:
            with urlopen(request, timeout=timeout) as response:
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
        return local

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
    def discovered_path(self):
        return self.runtime / 'discovered.json'

    def asset(self, key):
        path = Path(self.local['assets'][key])
        return path.resolve() if path.is_absolute() else (ROOT / path).resolve()

    def port(self, name, default):
        return int(self.local.get('ports', {}).get(name, default))

    def _secret(self, name):
        path = self.secrets_dir / name
        if not path.is_file():
            raise LifecycleError('missing secret %s: the runtime is incomplete; restore it '
                                 'or remove the runtime directory and run up again' % path)
        return path.read_text(encoding='utf-8').strip()

    # ------------------------------------------------------------------ docker

    def _run(self, argv, check=True):
        return self.runner.run([str(a) for a in argv], check=check)

    def _compose(self, project_kind, *args, check=True):
        env_file = self.env_dir / (project_kind + '.env')
        return self._run(['docker', 'compose', '--env-file', env_file,
                          '-f', COMPOSE_FILES[project_kind], *args], check=check)

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

    # ------------------------------------------------------------- generation

    def _ensure_secrets(self):
        """Generate secrets once; never rotate. A partial secrets dir is an error."""
        existing = [name for name in SECRET_FILES if (self.secrets_dir / name).is_file()]
        if existing and len(existing) != len(SECRET_FILES):
            missing = sorted(set(SECRET_FILES) - set(existing))
            raise LifecycleError('incomplete secrets in %s: missing %s. Restore the runtime '
                                 'or remove it and run up again; secrets are never rotated '
                                 'in place' % (self.secrets_dir, ', '.join(missing)))
        team_creds = self.secrets_dir / 'team-credentials.json'
        vnc_dir = self.secrets_dir / 'vnc'
        vnc_ok = vnc_dir.is_dir() and all(
            (vnc_dir / ('team%02d' % (i + 1))).is_file() for i in range(len(self.teams)))
        if existing and team_creds.is_file() and vnc_ok:
            return False
        if existing and (not team_creds.is_file() or not vnc_ok):
            raise LifecycleError('incomplete secrets in %s: team credentials or VNC passwords '
                                 'missing; restore the runtime' % self.secrets_dir)
        self.secrets_dir.mkdir(parents=True, exist_ok=True)
        vnc_dir.mkdir(exist_ok=True)
        for name in SECRET_FILES:
            (self.secrets_dir / name).write_text(self.host.randhex(24) + '\n', encoding='utf-8')
        # Wazuh credentials are "username:password"; usernames are stable identities.
        (self.secrets_dir / 'wazuh_admin').write_text('admin:%s' % self.host.randhex(12),
                                                      encoding='utf-8')
        (self.secrets_dir / 'wazuh_writer').write_text(
            'silent-ridge-writer-account:%s' % self.host.randhex(12), encoding='utf-8')
        (self.secrets_dir / 'wazuh_reader').write_text(
            'silent-ridge-participant-account:%s' % self.host.randhex(12), encoding='utf-8')
        credentials = {'teams': {}, 'desktops': {}}
        import string
        import secrets as _secrets
        alphabet = string.ascii_letters + string.digits
        for index, team in enumerate(self.teams):
            tag = 'team%02d' % (index + 1)
            vnc = ''.join(_secrets.choice(alphabet) for _ in range(8))  # VncAuth truncates at 8
            (vnc_dir / tag).write_text(vnc + '\n', encoding='utf-8')
            credentials['teams'][team['name']] = {
                'iris_login': team['name'],
                'iris_password': self.host.randhex(12),
                'ctfd_name': team['name'],
                'ctfd_password': self.host.randhex(12),
                'guac_username': tag,
                'guac_password': ''.join(_secrets.choice(alphabet) for _ in range(24)),
                'accounts': {account: self.host.randhex(12) for account in team['accounts']},
            }
            credentials['desktops'][team['desktop']] = {'password': vnc}
        team_creds.write_text(json.dumps(credentials, indent=2), encoding='utf-8')
        return True

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
        addresses = self.profile['addresses']
        ports = {'iris': self.port('iris', 8081), 'ctfd': self.port('ctfd', 8083),
                 'guac': self.port('guac', 8082), 'wazuh': self.port('wazuh_dashboard', 8443)}
        # Host-side publish address is a host property, not the profile's container-side
        # central_bind_ip; default loopback, override via local.json "bind_ip".
        bind = str(self.local.get('bind_ip') or '127.0.0.1')
        secrets = self.secrets_dir
        files = {}

        postgres_pw = self._secret('postgres-password')
        files['iris'] = {
            'POSTGRES_USER': 'iris', 'POSTGRES_PASSWORD': postgres_pw, 'POSTGRES_DB': 'iris_db',
            'POSTGRES_ADMIN_USER': 'iris', 'POSTGRES_ADMIN_PASSWORD': postgres_pw,
            'POSTGRES_SERVER': 'iris-db', 'POSTGRES_PORT': '5432',
            'IRIS_SECRET_KEY': self._secret('iris-secret-key'),
            'IRIS_SECURITY_PASSWORD_SALT': self._secret('iris-password-salt'),
            'IRIS_ADM_PASSWORD': self._secret('iris-admin-password'),
            'IRIS_AUTHENTICATION_TYPE': 'local',
        }
        mariadb_pw = self._secret('mariadb-ctfd-password')
        files['ctfd'] = {
            'DATABASE_URL': 'mysql+pymysql://ctfd:%s@ctfd-db/ctfd' % mariadb_pw,
            'SECRET_KEY': self._secret('ctfd-secret-key'),
            'REDIS_URL': 'redis://ctfd-cache:6379',
            'CTFD_NAME': 'Operation Silent Ridge',
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
            'BIND_IP': bind,
            'IRIS_PORT': str(ports['iris']), 'CTFD_PORT': str(ports['ctfd']),
            'IRIS_PUBLIC_URL': addresses['iris_public_url'],
            'CTFD_PUBLIC_URL': addresses['ctfd_public_url'],
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
            'BIND_IP': bind, 'WAZUH_DASHBOARD_PORT': str(ports['wazuh']),
        }
        files['guacamole'] = {
            'RIDGE_PROJECT': self.event,
            'RIDGE_DESKTOP_NETWORK': self.event + '-desktop',
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
            'IRIS_PUBLIC_URL': addresses['iris_public_url'],
            'CTFD_PUBLIC_URL': addresses['ctfd_public_url'],
            'WAZUH_PUBLIC_URL': 'https://%s:%d' % (addresses['guacamole_public_url']
                                                   .split('//', 1)[-1].split(':')[0], ports['wazuh']),
        }
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
            (self.env_dir / (name + '.env')).write_text(text, encoding='utf-8')
        return files

    def _render_specs(self):
        """Create missing bootstrap/provisioning specs from the runtime credentials.
        Existing specs are preserved byte-for-byte: credentials are never rotated."""
        self.specs_dir.mkdir(parents=True, exist_ok=True)
        credentials = self._team_credentials()
        iris_path = self.specs_dir / 'iris-bootstrap-spec.json'
        if not iris_path.is_file():
            iris_spec = {
                'case_name': 'Operation Silent Ridge',
                'case_description': 'Cooperative incident-response exercise case. All content fictional.',
                'service_login': 'silent-ridge-service',
                'service_name': 'Silent Ridge Integration',
                'service_password': self.host.randhex(12),
                'open_status': 'To do', 'closed_status': 'Done',
                'identities': [
                    {'team': team['name'], 'login': team['name'], 'name': team['name'],
                     'password': credentials['teams'][team['name']]['iris_password']}
                    for team in self.teams],
            }
            iris_path.write_text(json.dumps(iris_spec, indent=2), encoding='utf-8')
        ctfd_path = self.specs_dir / 'ctfd-provision-spec.json'
        if not ctfd_path.is_file():
            ctfd_spec = {
                'teams': [{'team': team['name'], 'name': team['name'],
                           'password': credentials['teams'][team['name']]['ctfd_password']}
                          for team in self.teams],
                'users': [{'name': account, 'email': '%s@silent-ridge.invalid' % account,
                           'team': team['name'],
                           'password': credentials['teams'][team['name']]['accounts'][account]}
                          for team in self.teams for account in team['accounts']],
                'user_mode': 'teams', 'registration_visible': False, 'schema': 'ctfd-3.7.7',
            }
            ctfd_path.write_text(json.dumps(ctfd_spec, indent=2), encoding='utf-8')
        guac_config_path = self.specs_dir / 'guac-config.json'
        if not guac_config_path.is_file():
            guac_config_path.write_text(json.dumps({
                'desktops': [{'id': desktop['name'], 'container': True,
                              'shared': desktop.get('shared', True),
                              'max_connections': desktop.get('max_connections',
                                                             4 if desktop.get('shared', True) else 1)}
                             for desktop in self.profile['desktops']],
                'teams': [{'id': 'team%02d' % (i + 1), 'desktop': team['desktop']}
                          for i, team in enumerate(self.teams)],
            }, indent=2), encoding='utf-8')
        guac_creds_path = self.specs_dir / 'guac-credentials.json'
        if not guac_creds_path.is_file():
            guac_config = json.loads(guac_config_path.read_text(encoding='utf-8'))
            guac_creds_path.write_text(json.dumps({
                'teams': {tag: {'username': credentials['teams'][team['name']]['guac_username'],
                                'password': credentials['teams'][team['name']]['guac_password']}
                          for tag, team in zip((t['id'] for t in guac_config['teams']), self.teams)},
                'desktops': {name: {'password': credentials['desktops'][name]['password']}
                             for name in credentials['desktops']},
            }, indent=2), encoding='utf-8')

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
        for key, check in (('evidence_public', 'dir'), ('release_vault', 'dir'),
                           ('case_template', 'dir'), ('originals', 'dir')):
            if not self.asset(key).is_dir():
                problems.append('asset %s missing at %s' % (key, self.asset(key)))
        case = self.asset('case_template') / 'WS17.aut'
        if self.asset('case_template').is_dir() and not case.is_file():
            problems.append('prepared case %s is missing; extract the published case template'
                            % case)
        wazuh_config = self.asset('wazuh_config')
        for rel in ('wazuh_indexer/wazuh.indexer.yml', 'wazuh_indexer/internal_users.yml',
                    'wazuh_cluster/wazuh_manager.conf'):
            if wazuh_config.is_dir() and not (wazuh_config / rel).is_file():
                problems.append('vendored Wazuh config %s missing under %s: vendor the pinned '
                                'upstream single-node config' % (rel, wazuh_config))
        from ridge.wazuh_provision import validate_manifest, load_vendored
        try:
            validate_manifest(load_vendored(WAZUH_DIR)['manifest'], require_digests=True)
        except Exception as exc:
            problems.append('Wazuh vendored manifest fails digest validation: %s' % exc)
        if problems:
            raise LifecycleError('; '.join(problems))
        return {'images': len(IMAGE_COMPONENTS)}

    # S2 ------------------------------------------------------ infrastructure
    def _ensure_networks(self):
        """Create the external networks every compose file references.

        central/desktop/wazuh-backend are declared `external: true` (they span
        compose projects), so nothing creates them implicitly and a fresh
        `up` fails without this step. Idempotent.
        """
        for suffix in ('-central', '-desktop', '-wazuh_wazuh-backend'):
            name = self.event + suffix
            try:
                self._run(['docker', 'network', 'inspect', name])
            except CommandError:
                self._run(['docker', 'network', 'create', name])

    def _apply_infrastructure(self):
        self._ensure_secrets()
        self._render_specs()
        self._render_env()
        self._ensure_networks()
        certs = self.runtime / 'wazuh-certs'
        if not (certs / 'root-ca.pem').is_file():
            self._run(['bash', str(WAZUH_DIR / 'generate-certs.sh'), str(certs)])
        guac_init = self.runtime / 'guac-init'
        guac_init.mkdir(parents=True, exist_ok=True)
        if not (guac_init / '001-initdb.sql').is_file():
            schema = self._run(['docker', 'run', '--rm', 'guacamole/guacamole:1.5.5',
                                '/opt/guacamole/bin/initdb.sh', '--postgresql'])
            (guac_init / '001-initdb.sql').write_text(schema + '\n', encoding='utf-8')
        if not (guac_init / '002-provision.sql').is_file():
            import sys
            sys.path.insert(0, str(COMPOSE_DIR))
            import guacamole as guac_module
            config = json.loads((self.specs_dir / 'guac-config.json').read_text(encoding='utf-8'))
            credentials = json.loads((self.specs_dir / 'guac-credentials.json').read_text(encoding='utf-8'))
            (guac_init / '002-provision.sql').write_text(
                guac_module.generate(config, credentials), encoding='utf-8')
        for kind, services in INFRA_SERVICES.items():
            self._compose(kind, 'up', '-d', *services)

    def _probe_infrastructure(self):
        existing = [name for name in SECRET_FILES if (self.secrets_dir / name).is_file()]
        if len(existing) != len(SECRET_FILES):
            raise LifecycleError('incomplete secrets in %s: missing %s. Restore the runtime; '
                                 'secrets are never regenerated beneath a verified deployment'
                                 % (self.secrets_dir,
                                    ', '.join(sorted(set(SECRET_FILES) - set(existing)))))
        for kind, services in INFRA_SERVICES.items():
            self._require_services(kind, services,
                                   allow_exit0=INFRA_ONE_SHOT.get(kind, ()))
        return {'services': sum(len(s) for s in INFRA_SERVICES.values())}

    # S3 ------------------------------------------------------- applications
    def _apply_applications(self):
        for kind, services in APP_SERVICES.items():
            self._compose(kind, 'up', '-d', *services)

    def _probe_applications(self):
        for kind, services in APP_SERVICES.items():
            self._require_services(kind, services)
        addresses = self.profile['addresses']
        checks = ((addresses['iris_public_url'] + '/login', 'IRIS'),
                  (addresses['ctfd_public_url'] + '/login', 'CTFd'))
        for url, name in checks:
            status, _ = self.host.http_json('GET', url)
            if status != 200:
                raise LifecycleError('%s login page returned HTTP %s at %s; the application is '
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
        return {'inventories': 2}

    # S5 ----------------------------------------------------------- desktops
    def _desktop_services(self):
        from ridge.docker_provider import team_service
        return [team_service('team%02d' % (i + 1)) for i in range(len(self.teams))]

    def _apply_desktops(self):
        self._compose('desktops', 'up', '-d', *self._desktop_services())
        sql = (self.runtime / 'guac-init' / '002-provision.sql').read_text(encoding='utf-8')
        self._pipe(['docker', 'compose', '--env-file', self.env_dir / 'guacamole.env',
                    '-f', COMPOSE_FILES['guacamole'], 'exec', '-T', 'database',
                    'psql', '-U', 'guacamole', '-d', 'guacamole', '-v', 'ON_ERROR_STOP=1'],
                   sql)

    def _pipe(self, argv, text):
        """Run argv with stdin text through the real subprocess runner."""
        if hasattr(self.runner, 'run_stdin'):
            return self.runner.run_stdin([str(a) for a in argv], text, check=True)
        completed = subprocess.run([str(a) for a in argv], input=text, capture_output=True,
                                   text=True, timeout=120)
        if completed.returncode != 0:
            raise LifecycleError('provisioning SQL failed: %s' % completed.stderr.strip()[:300])
        return completed.stdout.strip()

    def _probe_desktops(self):
        self._require_services('desktops', self._desktop_services())
        out = self._compose('guacamole', 'exec', '-T', 'database', 'psql', '-U', 'guacamole',
                            '-d', 'guacamole', '-tA', '-c',
                            'SELECT count(*) FROM guacamole_connection')
        try:
            count = int(out.strip().splitlines()[-1])
        except (ValueError, IndexError):
            raise LifecycleError('could not read guacamole_connection count: %r' % out[:200])
        if count < len(self.teams):
            raise LifecycleError('guacamole has %d connections for %d teams; provisioning SQL '
                                 'was not applied' % (count, len(self.teams)))
        return {'desktops': len(self.teams), 'connections': count}

    # S6 ----------------------------------------------------------- evidence
    def _index_name(self):
        name = self.local.get('index_name') or 'silent-ridge-' + self.event.replace('silent-ridge-', '')
        from ridge.wazuh_provision import validate_index_name
        return validate_index_name(name)

    def _wazuh(self, method, base, path, credential, body=None, headers=None):
        status, payload = self.host.wazuh_request(
            method, base + path, self.runtime / 'wazuh-certs' / 'root-ca.pem',
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
        self._indexer_job('apply')
        dashboard = 'https://127.0.0.1:%d' % self.port('wazuh_dashboard', 8443)
        admin = self._secret('wazuh_admin')
        for view in saved_objects():
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
        for i in range(len(self.teams)):
            service = team_service('team%02d' % (i + 1))
            out = self._compose('desktops', 'exec', '-T', service, 'bash', '-c',
                                'ls /evidence/network/sensor.pcap /evidence/wazuh/telemetry.jsonl',
                                check=False)
            if 'sensor.pcap' not in out:
                raise LifecycleError('evidence is not visible on desktop %s under /evidence'
                                     % service)
        return {'index': index_name, 'documents': payload.get('count', 0)}

    # S7 -------------------------------------------------- provisioned-paused
    def _controller_config(self):
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
                self.host.state(self.state_path).initialize(config['teams'], tickets)
        self._compose('integration', 'up', '-d')
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

    def _probe_provisioned(self):
        if not self.state_path.is_file():
            raise LifecycleError('exercise state %s is missing; run up' % self.state_path)
        state = self.host.state(self.state_path)
        mode = self._state_mode(state)
        if mode != 'paused':
            raise LifecycleError("exercise mode is %r, expected 'paused' after provisioning; "
                                 "pause it with `python -m ridge.deploy pause` before "
                                 "re-verifying" % mode)
        config = json.loads((self.state_dir / 'config.json').read_text(encoding='utf-8'))
        ready = self._controller_preflight()
        if ready.get('ready') is not True:
            raise LifecycleError('controller preflight failed: %s' % ready)
        services = self._ps('integration')
        controller = services.get('integration')
        if controller is None or controller['state'] != 'running':
            raise LifecycleError('integration controller is not running; run up to reconcile')
        return {'mode': mode, 'teams': ready.get('teams'), 'tickets': ready.get('tickets')}

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
            journal.check_fingerprints(self.profile, self.profile['event']['release_id'],
                                       release_fingerprint)
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
            journal.set_state('RUNNING')
            return {'state': 'RUNNING', 'mode': actual}

    def pause(self):
        journal = Journal.open(self.runtime / 'deploy-journal.sqlite')
        with journal.lock(self.operator):
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
            stopped = []
            for kind in ('integration', 'desktops', 'guacamole', 'central', 'wazuh'):
                if volumes:
                    # Remove containers and networks so volume removal is possible.
                    self._compose(kind, 'down', check=False)
                else:
                    self._compose(kind, 'stop', check=False)
                stopped.append(kind)
            journal.set_state('STOPPED')
            removed = []
            if volumes:
                names = recovery.data_volumes(self.event) + \
                    recovery.team_volumes(self.event, self.teams) + [
                        self.event + '-iris-db', self.event + '-ctfd-db',
                        self.event + '-guacamole-database',
                        self.event + '-wazuh_wazuh-indexer-data',
                        self.event + '-wazuh_wazuh-manager-data']
                for name in names:
                    self._run(['docker', 'volume', 'rm', '-f', name], check=False)
                    removed.append(name)
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
            for kind in ('integration', 'desktops'):
                self._compose(kind, 'stop', check=False)
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
