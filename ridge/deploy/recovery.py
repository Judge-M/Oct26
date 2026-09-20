"""Coherent full-event recovery sets (D02) and restore onto a clean local
destination (D03), with active-site fencing (F01) wired through the state.

A recovery set is complete only when every component is present and hashed;
the completion marker RECOVERY-COMPLETE.json is written last, and only after
the set verifies its own hashes. An incomplete set is never restorable.

Layout of a recovery set directory:
  manifest.json            schema, event, release fingerprint, resource mapping,
                           site generation, encryption key *reference* (never the key)
  export/                  receipt watermarks (iris.json, ctfd.json, integration.json)
  state/state.sqlite       consistent SQLite backup (backup API, under barrier)
  state/config.json        controller config
  deploy-journal.sqlite    lifecycle journal
  discovered.json          discovered application IDs
  inventories/             native bootstrap inventories
  db/iris-db.dump          pg_dump -Fc of iris_db
  db/ctfd-db.sql           mysqldump of ctfd
  db/guacamole-db.dump     pg_dump -Fc of guacamole
  wazuh/index.ndjson       every index document with stable IDs
  volumes/<name>.tar.gz    native app data + per-team cases/workspace/scratch
  evidence/                published public evidence tree
  release-vault/           authored release vault
  secrets.tar.gz.enc       all secrets, encrypted; the key comes from the
                           environment named in manifest.json, never from the set
  SHA256SUMS.json          hashes of every file above
  RECOVERY-COMPLETE.json   written LAST, only after the sums verify
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import tarfile
import tempfile
from pathlib import Path

RECOVERY_SCHEMA = 1
MARKER = 'RECOVERY-COMPLETE.json'
SUMS = 'SHA256SUMS.json'

# Event-owned volume suffixes that hold native application data worth restoring.
CENTRAL_DATA_VOLUMES = ('iris-data', 'iris-templates', 'iris-downloads',
                        'ctfd-uploads', 'ctfd-logs')
TEAM_VOLUME_KINDS = ('cases', 'workspace', 'scratch')


class RecoveryError(RuntimeError):
    """An actionable recovery failure; the message names the cause and remedy."""


class Cipher:
    """Secret-at-rest protection. Default: openssl AES-256-CBC/PBKDF2 with the key
    supplied through the environment; tests inject a fake. The key is referenced
    by environment variable name only and is never stored in the set."""

    def __init__(self, key_env='RIDGE_BACKUP_KEY', runner=subprocess.run):
        self.key_env = key_env
        self.runner = runner

    def _key(self):
        key = os.environ.get(self.key_env, '')
        if len(key) < 16:
            raise RecoveryError('set %s (>=16 chars) to encrypt the recovery-set secrets; '
                                'the key is never written into the set' % self.key_env)
        return key

    def encrypt(self, source, destination):
        self._pipe(['openssl', 'enc', '-aes-256-cbc', '-pbkdf2', '-salt',
                    '-pass', 'env:' + self.key_env, '-in', str(source),
                    '-out', str(destination)])

    def decrypt(self, source, destination):
        self._pipe(['openssl', 'enc', '-d', '-aes-256-cbc', '-pbkdf2',
                    '-pass', 'env:' + self.key_env, '-in', str(source),
                    '-out', str(destination)])

    def _pipe(self, argv):
        env = dict(os.environ)
        self._key()  # fail before spawning openssl without a key
        completed = self.runner(argv, capture_output=True, text=True, env=env)
        if completed.returncode != 0:
            raise RecoveryError('openssl failed: %s' % completed.stderr.strip()[:200])


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _write_sums(root):
    manifest = {}
    for file in sorted(Path(root).rglob('*')):
        if file.is_file() and file.name not in (SUMS, MARKER):
            manifest[str(file.relative_to(root)).replace('\\', '/')] = _sha256(file)
    (Path(root) / SUMS).write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    return manifest


def verify_set(folder):
    """Fail closed unless the set is complete and every hash matches."""
    folder = Path(folder)
    marker = folder / MARKER
    if not marker.is_file():
        raise RecoveryError('%s is not a completed recovery set (no %s); an incomplete '
                            'set is never restorable' % (folder, MARKER))
    sums_path = folder / SUMS
    if not sums_path.is_file():
        raise RecoveryError('corrupt recovery set %s: %s is missing' % (folder, SUMS))
    sums = json.loads(sums_path.read_text(encoding='utf-8'))
    required = ('manifest.json', 'state/state.sqlite', 'db/iris-db.dump',
                'db/ctfd-db.sql', 'db/guacamole-db.dump', 'wazuh/index.ndjson',
                'secrets.tar.gz.enc')
    missing = [name for name in required if name not in sums]
    if missing:
        raise RecoveryError('incomplete recovery set %s: missing %s' % (folder, ', '.join(missing)))
    for name, digest in sums.items():
        path = folder / name
        if not path.is_file() or _sha256(path) != digest:
            raise RecoveryError('corrupt recovery set: %s fails its recorded hash' % name)
    return json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))


def _volume_tar(runner, volume, destination):
    """Tar a named volume read-only through the integration image (no new pulls).
    The tarfile is closed inside the container and the archive is re-opened for
    readability before the set can be marked complete."""
    runner(['docker', 'run', '--rm', '-v', volume + ':/data:ro',
            '-v', str(destination.parent.resolve()) + ':/backup',
            '--entrypoint', 'python', 'silent-ridge-integration:dev', '-c',
            "import tarfile,sys\n"
            "with tarfile.open(sys.argv[1],'w:gz') as tar: tar.add(sys.argv[2],arcname='.')",
            '/backup/' + destination.name, '/data'])
    try:
        with tarfile.open(destination) as tar:
            tar.getnames()
    except (tarfile.TarError, OSError, EOFError) as exc:
        destination.unlink(missing_ok=True)
        raise RecoveryError('volume archive %s is not readable (%s); the set is incomplete'
                            % (destination.name, exc))


def _volume_untar(runner, volume, archive):
    runner(['docker', 'volume', 'create', volume])
    runner(['docker', 'run', '--rm', '-v', volume + ':/data',
            '-v', str(archive.parent.resolve()) + ':/backup:ro',
            '--entrypoint', 'python', 'silent-ridge-integration:dev', '-c',
            "import tarfile,sys\n"
            "with tarfile.open(sys.argv[1]) as tar: tar.extractall(sys.argv[2])",
            '/backup/' + archive.name, '/data'])


def archive_readable(path):
    try:
        with tarfile.open(path) as tar:
            tar.getnames()
        return True
    except (tarfile.TarError, OSError, EOFError):
        return False


def team_volumes(event, teams):
    return ['%s-desktops_team%02d-%s' % (event, index + 1, kind)
            for index in range(len(teams)) for kind in TEAM_VOLUME_KINDS]


def data_volumes(event):
    return ['%s-%s' % (event, name) for name in CENTRAL_DATA_VOLUMES]


def create(stack, destination, cipher=None, export_job=None):
    """D02: full coherent recovery set. Requires a paused, drained exercise; the
    export barrier freezes native writes while watermarks and state are captured."""
    from ridge.state import Conflict
    cipher = cipher or Cipher()
    destination = Path(destination)
    if destination.exists():
        raise RecoveryError('use a new destination directory: %s' % destination)
    state = stack.host.state(stack.state_path)
    # Consistency contract: the exercise must be paused and drained, which makes the
    # state quiescent; the in-controller export then holds the export barrier while
    # receipt watermarks are captured. We must NOT hold the barrier on the host at
    # the same time — the controller-side export takes it through the same database.
    from ridge.state import Conflict
    try:
        with state.transaction(write=False) as con:
            if con.execute('SELECT mode FROM run').fetchone()[0] != 'paused':
                raise Conflict('exercise is not paused')
            if con.execute('SELECT 1 FROM outbox WHERE done=0').fetchone():
                raise Conflict('outbox is not drained')
            if con.execute('SELECT fenced FROM control').fetchone()[0]:
                raise Conflict('site is fenced; restore from the last completed set instead')
    except Conflict as exc:
        raise RecoveryError('backup requires a paused, drained exercise (%s). Pause and '
                            'let the worker drain, then retry' % exc)
    try:
        destination.mkdir(parents=True)
        # 1. Receipt watermarks through the real export path (inside the controller
        #    network, where IRIS/CTFd internal URLs are reachable).
        if export_job is None:
            export_job = _default_export_job(stack)
        export_job(destination / 'export')
        # 2. Consistent core state backup (SQLite backup API, never a live file copy).
        (destination / 'state').mkdir()
        clone = sqlite3.connect(str(destination / 'state' / 'state.sqlite'))
        source = sqlite3.connect(str(stack.state_path))
        try:
            source.backup(clone)
        finally:
            clone.close()
            source.close()
        if (stack.state_dir / 'config.json').is_file():
            shutil.copy2(stack.state_dir / 'config.json', destination / 'state' / 'config.json')
        # 3. Journal, discovered IDs, inventories.
        shutil.copy2(stack.runtime / 'deploy-journal.sqlite', destination / 'deploy-journal.sqlite')
        if stack.discovered_path.is_file():
            shutil.copy2(stack.discovered_path, destination / 'discovered.json')
        inventories = stack.runtime / 'inventories'
        if inventories.is_dir():
            shutil.copytree(inventories, destination / 'inventories')
        # 4. Native database dumps.
        db_dir = destination / 'db'
        db_dir.mkdir()
        _dump_databases(stack, db_dir)
        # 5. Wazuh index snapshot (document-level, stable IDs).
        wazuh_dir = destination / 'wazuh'
        wazuh_dir.mkdir()
        stack._indexer_job('dump', backup_dir=wazuh_dir)
        # 6. Native app data and per-team volumes.
        volumes_dir = destination / 'volumes'
        volumes_dir.mkdir()
        for volume in data_volumes(stack.event) + team_volumes(stack.event, stack.teams):
            _volume_tar(stack._run, volume, volumes_dir / (volume + '.tar.gz'))
        # 7. Public evidence + release vault.
        shutil.copytree(stack.asset('evidence_public'), destination / 'evidence')
        shutil.copytree(stack.asset('release_vault'), destination / 'release-vault')
        # 8. Secrets, encrypted separately; key reference recorded, key never stored.
        with tempfile.TemporaryDirectory() as staging:
            archive = Path(staging) / 'secrets.tar.gz'
            with tarfile.open(archive, 'w:gz') as tar:
                tar.add(stack.secrets_dir, arcname='secrets')
                if stack.specs_dir.is_dir():
                    # Bootstrap specs embed account passwords: encrypted with secrets.
                    tar.add(stack.specs_dir, arcname='specs')
                certs = stack.runtime / 'wazuh-certs'
                if certs.is_dir():
                    # Node/admin/CA private keys travel encrypted with the secrets.
                    tar.add(certs, arcname='wazuh-certs')
            cipher.encrypt(archive, destination / 'secrets.tar.gz.enc')
        # 9. Non-secret host wiring, for provenance (contains no secrets).
        shutil.copy2(stack.runtime / 'local.json', destination / 'local.json')
        # 10. Resource mapping + receipt watermarks.
        site = state.site_info()
        manifest = {
            'schema': RECOVERY_SCHEMA,
            'event': stack.event,
            'release_fingerprint': stack.release_fingerprint,
            'site_generation': site['generation'],
            'index_name': stack._index_name(),
            'volumes': data_volumes(stack.event) + team_volumes(stack.event, stack.teams),
            'teams': [team['name'] for team in stack.teams],
            'secrets_encryption': {'tool': 'openssl enc -aes-256-cbc -pbkdf2',
                                   'key_env': cipher.key_env,
                                   'note': 'the key itself is never stored in the set'},
            'created': _now(),
        }
        (destination / 'manifest.json').write_text(json.dumps(manifest, indent=2),
                                                   encoding='utf-8')
        sums = _write_sums(destination)
        # Publish the completion marker last, and only if the sums verify.
        verify_sums_only(destination, sums)
        (destination / MARKER).write_text(json.dumps({'complete': True, 'created': manifest['created']}),
                                          encoding='utf-8')
        return {'recovery_set': str(destination), 'files': len(sums),
                'generation': site['generation']}
    except Exception:
        # An incomplete set is never marked complete; leave it for diagnosis but
        # make its incompleteness unmistakable.
        marker = destination / MARKER
        if marker.exists():
            marker.unlink()
        raise


def verify_sums_only(folder, sums=None):
    folder = Path(folder)
    sums = sums or json.loads((folder / SUMS).read_text(encoding='utf-8'))
    for name, digest in sums.items():
        path = folder / name
        if not path.is_file() or _sha256(path) != digest:
            raise RecoveryError('recovery set failed self-verification at %s; completion '
                                'marker withheld' % name)


def _now():
    from ridge.deploy.local import _utcnow
    return _utcnow().isoformat()


def _default_export_job(stack):
    """Run ridge.export_run inside a one-shot integration container on the central
    network (internal IRIS/CTFd URLs), writing watermarks to <dest>/export."""
    from ridge.deploy.local import ROOT

    def job(destination):
        destination.mkdir(parents=True, exist_ok=False)
        stack._run(['docker', 'run', '--rm', '--network', stack.event + '-central',
                    '-e', 'IRIS_URL=http://iris:8000', '-e', 'CTFD_URL=http://ctfd:8000',
                    '-e', 'RIDGE_IRIS_FILE=/secrets/ridge-iris-bridge',
                    '-e', 'RIDGE_CTFD_FILE=/secrets/ridge-ctfd-bridge',
                    '-e', 'RIDGE_EVIDENCE_PUBLIC=/evidence',
                    '-e', 'RIDGE_RELEASE_VAULT=/release-vault',
                    '-v', str(ROOT / 'ridge') + ':/opt/silent-ridge/ridge:ro',
                    '-v', str(stack.secrets_dir) + ':/secrets:ro',
                    '-v', str(stack.state_dir) + ':/state',
                    '-v', str(stack.asset('evidence_public')) + ':/evidence:ro',
                    '-v', str(stack.asset('release_vault')) + ':/release-vault:ro',
                    '-v', str(destination.resolve()) + ':/backup-export',
                    '--entrypoint', 'python', 'silent-ridge-integration:dev',
                    '-m', 'ridge.export_run', '--state', '/state/state.sqlite',
                    '/backup-export/watermarks'])
    return job


def _dump_databases(stack, db_dir):
    """Binary-safe dumps: write inside the container, then docker cp out (stdout
    capture would corrupt pg_dump custom format)."""
    targets = [('central', 'iris-db', '/tmp/ridge-iris.dump', db_dir / 'iris-db.dump'),
               ('central', 'ctfd-db', '/tmp/ridge-ctfd.sql', db_dir / 'ctfd-db.sql'),
               ('guacamole', 'database', '/tmp/ridge-guac.dump', db_dir / 'guacamole-db.dump')]
    stack._compose('central', 'exec', '-T', 'iris-db',
                   'pg_dump', '-U', 'iris', '-Fc', '-f', '/tmp/ridge-iris.dump', 'iris_db')
    stack._compose('central', 'exec', '-T', '-e',
                   'PW=' + stack._secret('mariadb-root-password'), 'ctfd-db', 'sh', '-c',
                   'exec mysqldump -uroot -p"$PW" --databases ctfd > /tmp/ridge-ctfd.sql')
    stack._compose('guacamole', 'exec', '-T', 'database',
                   'pg_dump', '-U', 'guacamole', '-Fc', '-f', '/tmp/ridge-guac.dump', 'guacamole')
    for kind, service, remote, local in targets:
        container = stack._container_name(kind, service)
        stack._run(['docker', 'cp', '%s:%s' % (container, remote), str(local)])
        stack._compose(kind, 'exec', '-T', service, 'rm', '-f', remote, check=False)


# --------------------------------------------------------------------- restore


def restore(profile, runtime, backup, runner, host=None, operator='deploy',
            receipts=None, cipher=None, release_fingerprint=None, degraded_ok=False,
            accept_release=None):
    """D03: restore a verified recovery set onto a clean local destination.

    Refuses: a corrupt/incomplete set, a wrong release fingerprint, or an
    already-live destination (existing runtime state or running containers).
    Leaves the destination PROVISIONED_PAUSED.
    """
    from ridge.deploy.local import LocalStack
    cipher = cipher or Cipher()
    backup = Path(backup)
    runtime = Path(runtime)
    manifest = verify_set(backup)  # corrupt/incomplete sets die here

    stack = LocalStack(profile, runtime, runner, host=host, operator=operator,
                       receipts=receipts)
    fingerprint = manifest.get('release_fingerprint')
    if fingerprint and release_fingerprint and fingerprint != release_fingerprint:
        if accept_release != fingerprint:
            raise RecoveryError('recovery set was built from release %s but this checkout '
                                'builds %s; refusing a wrong-release restore. To upgrade '
                                'across a release, re-run with --accept-release %s (schema '
                                'is migrated during restore)'
                                % (fingerprint[:16], release_fingerprint[:16], fingerprint))

    # Already-live destination refusal: only local.json may exist in the runtime.
    if runtime.exists():
        extras = [p.name for p in runtime.iterdir() if p.name != 'local.json']
        if extras:
            raise RecoveryError('destination runtime %s is not clean (%s present); restore '
                                'refuses to overwrite a live or partial runtime'
                                % (runtime, ', '.join(sorted(extras))))
    else:
        if not (runtime / 'local.json').is_file():
            raise RecoveryError('destination runtime %s must contain only a local.json '
                                'describing this host (assets/ports) before restore' % runtime)
    runtime.mkdir(parents=True, exist_ok=True)
    out = runner.run(['docker', 'ps', '--format', '{{.Names}}'], check=False) \
        if hasattr(runner, 'run') else ''
    live = [name for name in out.splitlines() if name.startswith(manifest['event'] + '-')]
    if live:
        raise RecoveryError('containers for %s are still running (%s); stop the source '
                            'with `down` (and wipe disposable volumes with `down --volumes`) '
                            'before restoring onto this host'
                            % (manifest['event'], ', '.join(live[:3])))

    # Materialize the runtime: secrets (decrypted), state, journal, inventories, specs.
    with tempfile.TemporaryDirectory() as staging:
        archive = Path(staging) / 'secrets.tar.gz'
        cipher.decrypt(backup / 'secrets.tar.gz.enc', archive)
        with tarfile.open(archive) as tar:
            tar.extractall(staging)
        shutil.copytree(Path(staging) / 'secrets', stack.secrets_dir)
        if (Path(staging) / 'specs').is_dir():
            shutil.copytree(Path(staging) / 'specs', stack.specs_dir)
        if (Path(staging) / 'wazuh-certs').is_dir():
            shutil.copytree(Path(staging) / 'wazuh-certs', runtime / 'wazuh-certs')
    (runtime / 'state').mkdir(exist_ok=True)
    shutil.copy2(backup / 'state' / 'state.sqlite', stack.state_path)
    if (backup / 'state' / 'config.json').is_file():
        shutil.copy2(backup / 'state' / 'config.json', stack.state_dir / 'config.json')
    if (backup / 'discovered.json').is_file():
        shutil.copy2(backup / 'discovered.json', stack.discovered_path)
    if (backup / 'inventories').is_dir():
        shutil.copytree(backup / 'inventories', runtime / 'inventories')
    # Cross-release upgrade: migrate the restored state to this checkout's schema.
    from ridge.schema import migrate
    with stack.host.state(stack.state_path).transaction() as con:
        migrate(con)

    # Infrastructure first: fresh volumes are created by compose; DB dumps are then
    # loaded before the applications boot against them. On any failure, containers
    # this restore started are stopped so a retry does not trip the live check.
    try:
        stack._render_env()
        stack._compose('central', 'up', '-d', 'iris-db', 'ctfd-db')
        stack._compose('guacamole', 'up', '-d', 'database')
        _wait_healthy(stack, 'central', 'iris-db')
        _wait_healthy(stack, 'central', 'ctfd-db')
        _wait_healthy(stack, 'guacamole', 'database')
        _restore_databases(stack, backup / 'db')

        # Native app data and team workspaces/cases into the fresh volumes.
        # Default fail-closed: an unreadable archive aborts the restore. With the
        # explicit operator override (degraded_ok), unreadable archives are skipped
        # and named in the result — a documented data-loss decision, never silent.
        skipped_volumes = []
        for archive in sorted((backup / 'volumes').glob('*.tar.gz')):
            if not archive_readable(archive):
                if not degraded_ok:
                    raise RecoveryError('volume archive %s is unreadable; restore refuses a '
                                        'corrupt backup. Re-run with explicit degraded_ok only '
                                        'after accepting the data loss in writing'
                                        % archive.name)
                skipped_volumes.append(archive.name)
                continue
            _volume_untar(stack._run, archive.name[:-7], archive)

        # Wazuh: bring the indexer/manager up, re-apply roles/template, load documents.
        stack._compose('wazuh', 'up', '-d', 'wazuh-indexer', 'wazuh-manager')
        _wait_healthy(stack, 'wazuh', 'wazuh-indexer')
        stack._indexer_job('apply')
        stack._indexer_job('load', backup_dir=backup / 'wazuh')

        # Public evidence and release vault return to the host asset directories.
        _restore_tree(backup / 'evidence', stack.asset('evidence_public'))
        _restore_tree(backup / 'release-vault', stack.asset('release_vault'))

        # Reconcile everything else through the normal stage machine; restores are
        # idempotent, so a retried restore repeats without duplicates.
        stack.up(release_fingerprint or fingerprint)
        state = stack.host.state(stack.state_path)
        mode = stack._state_mode(state)
        if mode != 'paused':
            raise RecoveryError("restored exercise mode is %r, expected 'paused'; leaving "
                                "destination paused requires explicit correction" % mode)
    except Exception:
        for kind in ('integration', 'desktops', 'guacamole', 'central', 'wazuh'):
            try:
                stack._compose(kind, 'stop', check=False)
            except Exception:
                pass
        raise
    result = {'restored': str(runtime), 'mode': mode, 'event': manifest['event'],
              'generation': manifest.get('site_generation')}
    if skipped_volumes:
        result['data_loss'] = {'skipped_volumes': skipped_volumes,
                               'note': 'operator accepted degraded restore; these volumes '
                                       'were not recovered'}
    return result


def _wait_healthy(stack, kind, service, attempts=60):
    import time
    for _ in range(attempts):
        services = stack._ps(kind)
        entry = services.get(service)
        if entry and entry['state'] == 'running' \
                and entry['health'] in ('healthy', ''):
            return
        if entry and entry['health'] == 'unhealthy':
            raise RecoveryError('%s/%s is unhealthy during restore' % (kind, service))
        time.sleep(2)
    raise RecoveryError('%s/%s did not become healthy during restore' % (kind, service))


def _restore_databases(stack, db_dir):
    iris_container = stack._container_name('central', 'iris-db')
    stack._run(['docker', 'cp', str(db_dir / 'iris-db.dump'),
                '%s:/tmp/ridge-iris.dump' % iris_container])
    stack._compose('central', 'exec', '-T', 'iris-db', 'pg_restore', '-U', 'iris',
                   '-d', 'iris_db', '--clean', '--if-exists', '/tmp/ridge-iris.dump')
    ctfd_container = stack._container_name('central', 'ctfd-db')
    stack._run(['docker', 'cp', str(db_dir / 'ctfd-db.sql'),
                '%s:/tmp/ridge-ctfd.sql' % ctfd_container])
    stack._compose('central', 'exec', '-T', '-e',
                   'PW=' + stack._secret('mariadb-root-password'), 'ctfd-db', 'sh', '-c',
                   'exec mysql -uroot -p"$PW" < /tmp/ridge-ctfd.sql')
    guac_container = stack._container_name('guacamole', 'database')
    stack._run(['docker', 'cp', str(db_dir / 'guacamole-db.dump'),
                '%s:/tmp/ridge-guac.dump' % guac_container])
    stack._compose('guacamole', 'exec', '-T', 'database', 'pg_restore', '-U', 'guacamole',
                   '-d', 'guacamole', '--clean', '--if-exists', '/tmp/ridge-guac.dump')


def _restore_tree(source, destination):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    for item in Path(source).iterdir():
        target = destination / item.name
        if item.is_dir():
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(item, target)
        else:
            shutil.copy2(item, target)
