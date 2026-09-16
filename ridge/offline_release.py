"""F05 - complete versioned offline release.

Unifies the distribution and offline-bundle inventories without breaking old downloads,
pins every image to an immutable digest, and verifies a cold-cache release. Publishing
and the no-Internet install require the release environment and are BLOCKED here; the
merge, pinning and verification logic is deterministic and tested.
"""
import json
import re
from pathlib import Path

from ridge.artifacts import safe, sha256

LFS_POINTER = b'version https://git-lfs.github.com/spec/v1'
REQUIRED_CATEGORIES = {'containers', 'desktop', 'disk', 'memory', 'autopsy',
                       'dependencies', 'guides', 'evidence'}
DIGEST = re.compile(r'(?:^|@)sha256:[0-9a-f]{64}$')
MUTABLE_TAGS = re.compile(r'(?i)(:latest$|:main$|:master$)')


def pin_image(reference):
    if not isinstance(reference, str) or not DIGEST.search(reference):
        raise ValueError('Image must be pinned to an immutable sha256 digest: ' + str(reference))
    if MUTABLE_TAGS.search(reference):
        raise ValueError('Mutable tag is not an immutable identity: ' + reference)
    return reference


def merge_inventories(distribution, bundle):
    release = distribution.get('release') or bundle.get('release')
    commit = distribution.get('source_commit') or bundle.get('source_commit')
    if not release or not commit:
        raise ValueError('Both inventories must identify a release and source commit')
    images = dict(bundle.get('images', {}))
    for name, reference in distribution.get('images', {}).items():
        images.setdefault(name, reference)
    return dict(schema=1, release=release, source_commit=commit, images=images,
                artifacts=list(bundle.get('artifacts', [])),
                files=dict(distribution.get('files', {})))


def require_complete(manifest, required_images):
    missing = sorted(set(required_images) - set(manifest.get('images', {})))
    if missing:
        raise ValueError('Missing pinned images: ' + ', '.join(missing))
    for name, reference in manifest['images'].items():
        pin_image(reference)
    kinds = {artifact.get('kind') for artifact in manifest.get('artifacts', [])}
    absent = sorted(REQUIRED_CATEGORIES - kinds)
    if absent:
        raise ValueError('Incomplete offline bundle; missing categories: ' + ', '.join(absent))
    return manifest


def verify_offline(root, manifest):
    root = Path(root)
    for name, record in manifest.get('files', {}).items():
        path = safe(root, name)
        if not path.is_file() or path.stat().st_size != record['bytes'] or sha256(path) != record['sha256']:
            raise ValueError('Missing or corrupt release file: ' + name)
        with path.open('rb') as stream:
            if stream.read(128).startswith(LFS_POINTER):
                raise ValueError('Git LFS pointer stub present: ' + name)
    for reference in manifest.get('images', {}).values():
        pin_image(reference)
    return manifest


def load_manifest(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))
