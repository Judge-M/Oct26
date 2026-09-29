"""Reassemble the published desktop disk, verifying every part and the result."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile

from ridge.artifacts import safe


def assemble(root, manifest, destination):
    root, destination = Path(root).resolve(), Path(destination).resolve()
    if destination.exists():
        raise ValueError('Choose a new destination; existing disks are never overwritten')
    if manifest.get('schema') != 1 or manifest.get('format') != 'qcow2':
        raise ValueError('Expected a versioned QCOW2 desktop manifest')
    parts = manifest['parts']
    if not parts or len({part['path'] for part in parts}) != len(parts):
        raise ValueError('Empty or duplicate disk parts')
    destination.parent.mkdir(parents=True, exist_ok=True)
    digest, size = hashlib.sha256(), 0
    descriptor, temporary = tempfile.mkstemp(prefix='.desktop-', dir=destination.parent)
    temporary = Path(temporary)
    try:
        with os.fdopen(descriptor, 'wb') as output:
            for part in parts:
                part_digest, part_size = hashlib.sha256(), 0
                with safe(root, part['path']).open('rb') as stream:
                    for block in iter(lambda: stream.read(1024 * 1024), b''):
                        output.write(block)
                        part_digest.update(block)
                        digest.update(block)
                        size += len(block)
                        part_size += len(block)
                if part_size != part['bytes'] or part_digest.hexdigest() != part['sha256']:
                    raise ValueError('Corrupt desktop part: ' + part['path'])
            output.flush()
            os.fsync(output.fileno())
        if size != manifest['bytes'] or digest.hexdigest() != manifest['sha256']:
            raise ValueError('Reassembled desktop checksum mismatch')
        # Hard-link publication refuses an existing target even if another process
        # creates it during assembly. The temporary file is on the same filesystem.
        os.link(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path.cwd())
    parser.add_argument('--manifest', type=Path, default=Path('assets/desktop-v1.json'))
    parser.add_argument('--destination', required=True, type=Path)
    args = parser.parse_args()
    try:
        print(assemble(args.root, json.loads(args.manifest.read_text(encoding='utf-8')), args.destination))
    except (ValueError, KeyError, OSError) as error:
        parser.exit(1, f'Desktop assembly failed: {error}\n')


if __name__ == '__main__':
    main()
