"""D02/D03 - coherent full-event recovery set and clean-destination restore.

The recovery set is built while the run is paused and drained, using a SQLite-consistent
copy of the core state plus caller-supplied native application backups. Secret
restoration material is encrypted separately and never stored as plaintext. A completion
marker is written last; restore refuses an incomplete, corrupt, wrong-release or
already-live destination.

The provider that enumerates native application databases, Wazuh snapshots and desktop
workspaces is owned by the deployment-profile lane (A03/A04). This module consumes that
inventory through the plain `Source` records below and does not invent the profile
schema; wiring the real provider remains PENDING.
"""
import json
import shutil
import sqlite3
from contextlib import closing
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from ridge.artifacts import safe, sha256
from ridge.schema import VERSION

SCHEMA = 1
MARKER = 'RESTORABLE'
CORE_NAME = 'core.sqlite'


@dataclass(frozen=True)
class Source:
    name: str
    kind: str
    path: Path
    sha256: str | None = None


def _now():
    return datetime.now(timezone.utc).isoformat()


def _sqlite_backup(source, target):
    with closing(sqlite3.connect(source)) as origin, closing(sqlite3.connect(target)) as copy:
        origin.backup(copy)


def watermarks(state):
    with state.transaction(write=False) as con:
        count = lambda table: con.execute('SELECT COUNT(*) FROM ' + table).fetchone()[0]
        return dict(schema_version=VERSION, mode=con.execute('SELECT mode FROM run').fetchone()[0],
                    provisioned=con.execute('SELECT provisioned FROM control').fetchone()[0],
                    teams=count('teams'), tickets=count('tickets'), answers=count('answers'),
                    outbox_done=con.execute('SELECT COUNT(*) FROM outbox WHERE done=1').fetchone()[0],
                    outbox_pending=con.execute('SELECT COUNT(*) FROM outbox WHERE done=0').fetchone()[0])


def _encrypt(data, encryptor):
    if encryptor is None:
        raise ValueError('Encrypt secret restoration material; supply a real encryptor')
    result = encryptor(data)
    if not isinstance(result, (bytes, bytearray)):
        raise ValueError('Encryptor must return bytes')
    return bytes(result)


def fernet_encryptor(key):
    try:
        from cryptography.fernet import Fernet
    except ImportError as error:
        raise ValueError('Install cryptography or supply an encryptor') from error
    return Fernet(key).encrypt


def backup(state, destination, release, sources=(), secrets=(), encryptor=None,
           key_reference=None, resources=None):
    destination = Path(destination)
    if destination.exists():
        raise ValueError('Choose a new recovery-set directory; existing backups are never overwritten')
    if not release:
        raise ValueError('An immutable release identifier is required')
    if secrets and encryptor is None:
        raise ValueError('Encrypt secret restoration material; supply a real encryptor')
    with state.export_barrier():
        try:
            destination.mkdir(parents=True)
            core = destination / CORE_NAME
            _sqlite_backup(state.path, core)
            entries = []
            for source in sources:
                source_path = Path(source.path)
                if not source_path.is_file():
                    raise ValueError('Recovery source is missing: ' + source.name)
                digest = sha256(source_path)
                if source.sha256 and digest != source.sha256:
                    raise ValueError('Recovery source changed: ' + source.name)
                target = safe(destination, 'data/' + source.name)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source_path, target)
                entries.append(dict(name=source.name, kind=source.kind, path=target.relative_to(destination).as_posix(),
                                    bytes=target.stat().st_size, sha256=digest))
            secret_entries = []
            for source in secrets:
                source_path = Path(source.path)
                if not source_path.is_file():
                    raise ValueError('Secret source is missing: ' + source.name)
                target = safe(destination, 'secrets/' + source.name)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(_encrypt(source_path.read_bytes(), encryptor))
                secret_entries.append(dict(name=source.name, encrypted=True,
                                           sha256=sha256(target), plaintext_sha256=sha256(source_path)))
            manifest = dict(schema=SCHEMA, release=release, created=_now(),
                            core=dict(path=CORE_NAME, bytes=core.stat().st_size, sha256=sha256(core)),
                            sources=entries, secrets=secret_entries, watermarks=watermarks(state),
                            resources=resources or {}, key_reference=key_reference,
                            provider_inventory='PENDING A04')
            (destination / 'manifest.json').write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n', encoding='utf-8')
            (destination / MARKER).write_text(json.dumps(dict(release=release, created=manifest['created'])) + '\n', encoding='utf-8')
        except BaseException:
            shutil.rmtree(destination, ignore_errors=True)
            raise
    return manifest


def verify(recovery_set):
    recovery_set = Path(recovery_set)
    manifest_path = recovery_set / 'manifest.json'
    if not (recovery_set / MARKER).is_file():
        raise ValueError('Recovery set has no completion marker; it is incomplete')
    if not manifest_path.is_file():
        raise ValueError('Recovery set manifest is missing')
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    if manifest.get('schema') != SCHEMA or not manifest.get('release'):
        raise ValueError('Unknown recovery-set schema or missing release')
    core = safe(recovery_set, manifest['core']['path'])
    if not core.is_file() or core.stat().st_size != manifest['core']['bytes'] or sha256(core) != manifest['core']['sha256']:
        raise ValueError('Core state backup is missing or corrupt')
    for entry in manifest['sources']:
        path = safe(recovery_set, entry['path'])
        if not path.is_file() or path.stat().st_size != entry['bytes'] or sha256(path) != entry['sha256']:
            raise ValueError('Recovery source is missing or corrupt: ' + entry['name'])
    for entry in manifest['secrets']:
        path = safe(recovery_set, 'secrets/' + entry['name'])
        if not path.is_file() or sha256(path) != entry['sha256']:
            raise ValueError('Secret material is missing or corrupt: ' + entry['name'])
    return manifest


def restore(recovery_set, destination, release):
    recovery_set, destination = Path(recovery_set), Path(destination)
    manifest = verify(recovery_set)
    if manifest['release'] != release:
        raise ValueError('Recovery set is for a different release')
    if destination.exists():
        raise ValueError('Refusing to restore onto an existing destination')
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        destination.mkdir()
        restored = destination / CORE_NAME
        shutil.copyfile(safe(recovery_set, manifest['core']['path']), restored)
        with closing(sqlite3.connect(restored)) as con:
            if con.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
                raise ValueError('Restored core state failed integrity verification')
            if con.execute('SELECT COUNT(*) FROM run').fetchone()[0] != 1:
                raise ValueError('Restored core state has no run')
    except BaseException:
        shutil.rmtree(destination, ignore_errors=True)
        raise
    return dict(release=release, core=str(restored), watermarks=manifest['watermarks'],
                provider_restore='PENDING A04', paused=True)
