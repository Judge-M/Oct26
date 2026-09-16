"""Provider-independent evidence delivery to team desktops (C03).

Controller: ``build_manifest`` describes one release generation with per-file
SHA-256. Desktop agent: ``DesktopAgent.sync`` fetches the manifest and new files
into root-owned staging, verifies each checksum, then atomically publishes
read-only files. Originals and the prepared case template are never touched.

LIVE ACCEPTANCE BLOCKED: no real desktops or controller endpoint are available
on this Windows host, so end-to-end delivery, reconnect and readiness are not
accepted here. Follow-ups that need Wazuh/file-manager (not Autopsy) are chosen
by ``AUTOPSY_IMMUTABLE`` consumers, not by automatic ingest.
"""
import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from ridge.artifacts import safe, sha256


class DeliveryError(RuntimeError):
    """Raised when delivery cannot proceed safely; the field is named."""


Transport = Callable[[str, Path], None]


def build_manifest(release_dir, generation: int) -> dict:
    if type(generation) is not int or generation < 1:
        raise DeliveryError('generation: a positive integer is required')
    root = Path(release_dir)
    if not root.is_dir():
        raise DeliveryError('release: directory not found at '+str(root))
    files = {}
    for path in sorted(root.rglob('*')):
        if path.is_file():
            rel = path.relative_to(root).as_posix()
            files[rel] = {'sha256': sha256(path), 'bytes': path.stat().st_size}
    if not files:
        raise DeliveryError('release: no files to publish')
    return {'schema': 1, 'generation': generation, 'files': files}


def validate_manifest(document) -> dict:
    if document.get('schema') != 1:
        raise DeliveryError('schema: release manifest schema 1 is required')
    generation = document.get('generation')
    if type(generation) is not int or generation < 1:
        raise DeliveryError('generation: a positive integer is required')
    files = document.get('files')
    if not files:
        raise DeliveryError('files: at least one released file is required')
    for name, meta in files.items():
        if not isinstance(meta, dict) or not meta.get('sha256') or type(meta.get('bytes')) is not int:
            raise DeliveryError('files: %s needs sha256 and bytes' % name)
        safe(Path('.'), name)
    return document


def _publish_readonly(path: Path) -> None:
    os.chmod(path, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)


@dataclass
class DesktopAgent:
    """Fetches and publishes one desktop's released evidence."""

    transport: Transport
    base_url: str
    staging: Path
    published: Path
    generation: int = 0
    prune: bool = True

    def sync(self, document: dict) -> dict:
        manifest = validate_manifest(document)
        if manifest['generation'] < self.generation:
            raise DeliveryError('generation: controller manifest regressed')
        Path(self.staging).mkdir(parents=True, exist_ok=True)
        Path(self.published).mkdir(parents=True, exist_ok=True)
        for name, meta in manifest['files'].items():
            destination = safe(self.published, name)
            if destination.is_file() and sha256(destination) == meta['sha256']:
                continue
            temporary = safe(self.staging, name)
            temporary.parent.mkdir(parents=True, exist_ok=True)
            try:
                self.transport(self.base_url.rstrip('/') + '/' + name, temporary)
                if not temporary.is_file() or sha256(temporary) != meta['sha256']:
                    raise DeliveryError('checksum: downloaded %s does not match manifest' % name)
                destination.parent.mkdir(parents=True, exist_ok=True)
                if destination.exists():
                    os.chmod(destination, stat.S_IWUSR)
                os.replace(temporary, destination)
                _publish_readonly(destination)
            except Exception:
                temporary.unlink(missing_ok=True)
                raise
        if self.prune:
            expected = set(manifest['files'])
            for existing in sorted(Path(self.published).rglob('*')):
                if existing.is_file() and existing.relative_to(self.published).as_posix() not in expected:
                    os.chmod(existing, stat.S_IWUSR)
                    existing.unlink()
        self.generation = manifest['generation']
        return self.status(manifest['generation'])

    def status(self, controller_generation: int | None = None) -> dict:
        if controller_generation is None:
            controller_generation = self.generation
        lag = max(0, controller_generation - self.generation)
        return {'generation': self.generation, 'controller_generation': controller_generation,
                'lag': lag, 'ready': lag == 0}
