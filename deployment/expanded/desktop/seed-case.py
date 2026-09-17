"""Seed a private writable case once; never overwrite participant work."""
import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path


def seed(source, parent):
    source, parent = Path(source), Path(parent)
    manifest = json.loads((source / '.template.json').read_text())
    if 'WS17.aut' not in manifest['files'] or 'autopsy.db' not in manifest['files']:
        raise ValueError('Prepared template lacks the case database or entrypoint')
    for name, digest in manifest['files'].items():
        path = (source / name).resolve()
        if not path.is_relative_to(source.resolve()):
            raise ValueError('Template path escapes source')
        with path.open('rb') as stream:
            actual = hashlib.file_digest(stream, 'sha256').hexdigest()
        if actual != digest:
            raise ValueError('Prepared case checksum mismatch: ' + name)
    parent.mkdir(parents=True, exist_ok=True)
    target = parent / 'WS17'
    if target.exists():
        if (target / '.template.json').read_text() != (source / '.template.json').read_text():
            raise ValueError('Existing case belongs to another template; preserve it and use a new volume')
        return
    with tempfile.TemporaryDirectory(prefix='.seed-', dir=parent) as temp:
        staged = Path(temp) / 'WS17'
        shutil.copytree(source, staged)
        staged.rename(target)


if __name__ == '__main__':
    seed(*sys.argv[1:])
