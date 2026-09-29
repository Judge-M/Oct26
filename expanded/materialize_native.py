"""Verify and extract published native evidence into a new preparation directory."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tarfile

from ridge.artifacts import sha256

REPO = Path(__file__).resolve().parents[1]


def materialize(repo, destination=None):
    repo = Path(repo).resolve()
    manifest = json.loads((repo / 'assets/native-windows-v1/archive.json').read_text(encoding='utf-8'))
    from ridge.artifacts import safe
    archive = safe(repo, manifest['artifact'])
    if archive.stat().st_size != manifest['bytes'] or sha256(archive) != manifest['sha256']:
        raise ValueError('Native archive missing/corrupt; run git lfs pull and retry')
    if destination is None:
        return {'archive_verified': True, 'files': len(manifest['files'])}
    destination = Path(destination).absolute()
    if destination.exists():
        raise ValueError('Choose a new destination; existing evidence is never overwritten')
    destination.parent.mkdir(parents=True, exist_ok=True)
    needed = sum(record['bytes'] for record in manifest['files'].values())
    if shutil.disk_usage(destination.parent).free < needed + 1024**3:
        raise ValueError('Insufficient space for extracted evidence plus 1 GiB reserve')
    # Reserve the destination exclusively. A failed extraction removes only this
    # newly created directory; the verified archive is never modified.
    destination.mkdir()
    try:
        seen = set()
        with tarfile.open(archive, 'r:gz') as source:
            for member in source:
                prefix = 'originals/windows/'
                if not member.isfile() or not member.name.startswith(prefix):
                    raise ValueError('Unexpected native archive member')
                name = member.name[len(prefix):]
                record = manifest['files'].get(name)
                if name in seen or record is None or member.size != record['bytes']:
                    raise ValueError('Native member inventory mismatch: ' + name)
                target = safe(destination, member.name)
                target.parent.mkdir(parents=True, exist_ok=True)
                digest = hashlib.sha256()
                with source.extractfile(member) as incoming, target.open('xb') as output:
                    for block in iter(lambda: incoming.read(1024*1024), b''):
                        digest.update(block)
                        output.write(block)
                if digest.hexdigest() != record['sha256']:
                    raise ValueError('Native member checksum mismatch: ' + name)
                seen.add(name)
        if seen != set(manifest['files']):
            raise ValueError('Native archive is incomplete')
        native = destination / 'originals/windows'
        config = json.loads((native / 'memory-layer.json').read_text(encoding='utf-8'))
        symbol_name = config['kernel.symbol_table_name.isf_url'].rsplit('/', 1)[1]
        symbol = safe(native / 'symbols', symbol_name)
        if not symbol.is_file():
            raise ValueError('Referenced kernel symbols missing')
        config['kernel.layer_name.memory_layer.location'] = (native / 'WS17.raw').as_uri()
        config['kernel.symbol_table_name.isf_url'] = symbol.as_uri()
        (native / 'memory-layer.local.json').write_text(json.dumps(config, indent=2)+'\n', encoding='utf-8')
        (destination / 'VERIFIED.json').write_text(json.dumps(dict(
            archive_sha256=manifest['sha256'], verified_originals=len(seen),
            derived_config='originals/windows/memory-layer.local.json'), indent=2)+'\n', encoding='utf-8')
    except BaseException:
        shutil.rmtree(destination)
        raise
    return {'destination': str(destination), 'verified_originals': len(seen)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=REPO)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--destination', type=Path)
    group.add_argument('--verify-only', action='store_true')
    args = parser.parse_args()
    try:
        print(json.dumps(materialize(args.repo, args.destination), indent=2))
    except (OSError, ValueError, KeyError, tarfile.TarError) as error:
        parser.exit(1, f'Native preparation failed: {error}\n')


if __name__ == '__main__':
    main()
