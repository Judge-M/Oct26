"""Package and retrieve GitHub distributions; never initialize or reset live state.

Only Git-tracked files enter source archives. Large files must be materialized,
not Git LFS pointer stubs. A distribution is not a complete offline certification.
"""
import argparse
import json
import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

from ridge.artifacts import safe, sha256

COMPONENTS = {'integration', 'iris', 'ctfd'}
REPOSITORY = 'Judge-M/Oct26'
MAX_ASSET_BYTES = 1024 ** 3


def image_lock(images):
    if set(images) != COMPONENTS:
        raise ValueError('Exactly integration, iris and ctfd image digests required')
    for name, reference in images.items():
        if not isinstance(reference, str) or not re.fullmatch(
            rf'ghcr\.io/[a-z0-9_.-]+/oct26-{name}@sha256:[0-9a-f]{{64}}', reference
        ):
            raise ValueError('Expected immutable GHCR image reference: ' + name)
    return images


def archive(root, names, destination):
    """Stream files, preserving Unix modes; exclude untracked runtime material."""
    with zipfile.ZipFile(destination, 'x', compression=zipfile.ZIP_DEFLATED,
                         allowZip64=True) as output:
        for name in sorted(names):
            source = safe(root, name)
            if not source.is_file():
                raise ValueError('Missing tracked file: ' + name)
            with source.open('rb') as stream:
                if stream.read(128).splitlines()[:1] == [b'version https://git-lfs.github.com/spec/v1']:
                    raise ValueError('Download Git LFS content before packaging: ' + name)
            output.write(source, name)


def pack(root, destination, release, images):
    root, destination = Path(root).resolve(), Path(destination).resolve()
    image_lock(images)
    if not re.fullmatch(r'v[0-9]+\.[0-9]+\.[0-9]+(?:-[a-zA-Z0-9.-]+)?', release):
        raise ValueError('Use a version such as v0.1.0 or v0.1.0-rc.1')
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
    if subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=no'], cwd=root):
        raise ValueError('Commit tracked changes before building a release')
    names = subprocess.check_output(['git', 'ls-files', '-z'], cwd=root).decode().split('\0')[:-1]
    if destination.exists():
        raise ValueError('Use a new distribution destination')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=destination.parent) as scratch:
        stage = Path(scratch)
        large = sorted(name for name in names if name.startswith('assets/large/'))
        # Parked artifacts (the optional VM desktop QCOW2) are neither large
        # distribution assets nor source: they stay out of every release.
        parked = sorted(name for name in names if name.startswith('assets/vm-desktop/'))
        archive(root, [name for name in names if name not in large and name not in parked],
                stage / 'source.zip')
        assets = {}
        for index, name in enumerate(large):
            source = safe(root, name)
            if not source.is_file() or source.stat().st_size > MAX_ASSET_BYTES:
                raise ValueError('Missing asset or asset needs splitting into 1 GiB parts: ' + name)
            with source.open('rb') as stream:
                if stream.read(128).startswith(b'version https://git-lfs.github.com/spec/v1'):
                    raise ValueError('Download Git LFS content before packaging: ' + name)
            asset = f'asset-{index:04d}.bin'
            shutil.copyfile(source, stage / asset)
            assets[asset] = name
        # Import only here so fetching a release needs no fixture dependencies.
        import sys
        subprocess.run([sys.executable, str(root / 'expanded/prepare.py'), str(stage / 'fixtures')],
                       cwd=root, check=True, stdout=subprocess.DEVNULL)
        subprocess.run([sys.executable, '-c',
                        'import json,runpy,sys; from pathlib import Path; '
                        'module=runpy.run_path(sys.argv[1]); '
                        'Path(sys.argv[2]).write_text(json.dumps(module["build"](),indent=2)+"\\n",encoding="utf-8")',
                        str(root / 'expanded/author.py'), str(stage / 'fixtures/tickets.json')],
                       cwd=root, check=True)
        archive(stage / 'fixtures', [p.relative_to(stage / 'fixtures').as_posix()
                                    for p in (stage / 'fixtures').rglob('*') if p.is_file()],
                stage / 'fixtures.zip')
        manifest = dict(schema=2, repository=REPOSITORY, release=release, source_commit=commit,
                        event_ready=False, complete_offline_bundle=False,
                        images=image_lock(images), files={}, assets=assets)
        for name in ['source.zip', 'fixtures.zip', *assets]:
            file = stage / name
            if file.stat().st_size > MAX_ASSET_BYTES:
                raise ValueError('Distribution file exceeds 1 GiB: ' + name)
            manifest['files'][name] = dict(bytes=file.stat().st_size, sha256=sha256(file))
        (stage / 'distribution.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
        shutil.rmtree(stage / 'fixtures')
        # Stage beside the target so an interrupted build never looks complete.
        stage.rename(destination)
    return destination


def verify(root, release):
    root = Path(root)
    manifest = json.loads((root / 'distribution.json').read_text(encoding='utf-8'))
    if (manifest.get('schema') not in (1, 2) or manifest.get('repository') != REPOSITORY
            or manifest.get('release') != release
            or not re.fullmatch('[0-9a-f]{40}', manifest.get('source_commit', ''))):
        raise ValueError('Distribution identity mismatch')
    image_lock(manifest['images'])
    assets = manifest.get('assets', {}) if manifest['schema'] == 2 else {}
    if (not isinstance(assets, dict) or len(set(assets.values())) != len(assets)
            or any(not re.fullmatch(r'asset-[0-9]{4,}\.bin', name)
                   or not target.startswith('assets/large/') for name, target in assets.items())):
        raise ValueError('Invalid asset inventory')
    for target in assets.values():
        safe(root, target)
    if set(manifest['files']) != {'source.zip', 'fixtures.zip', *assets}:
        raise ValueError('Incomplete distribution inventory')
    for name, record in manifest['files'].items():
        file = safe(root, name)
        if not file.is_file() or file.stat().st_size != record['bytes'] or sha256(file) != record['sha256']:
            raise ValueError('Missing or corrupt distribution file: ' + name)
    return manifest


def fetch(release, destination):
    """GH CLI handles public/private authentication without embedding credentials."""
    destination = Path(destination).resolve()
    if destination.exists():
        raise ValueError('Use a new destination; existing events are never overwritten')
    if not re.fullmatch(r'v[0-9]+\.[0-9]+\.[0-9]+(?:-[a-zA-Z0-9.-]+)?', release):
        raise ValueError('Expected an explicit version tag')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=destination.parent) as scratch:
        stage = Path(scratch)
        subprocess.run(['gh', 'release', 'download', release, '--repo', REPOSITORY,
                        '--dir', str(stage), '--pattern', 'distribution.json',
                        '--pattern', 'source.zip', '--pattern', 'fixtures.zip',
                        '--pattern', 'asset-*.bin'], check=True)
        verify(stage, release)
        stage.rename(destination)
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    build = commands.add_parser('pack')
    build.add_argument('--root', type=Path, default=Path.cwd())
    build.add_argument('--images', type=Path, required=True)
    for command in (build, commands.add_parser('fetch')):
        command.add_argument('--release', required=True)
        command.add_argument('--destination', type=Path, required=True)
    check = commands.add_parser('verify')
    check.add_argument('directory', type=Path)
    check.add_argument('--release', required=True)
    args = parser.parse_args()
    try:
        if args.command == 'pack':
            print(pack(args.root, args.destination, args.release,
                       json.loads(args.images.read_text(encoding='utf-8'))))
        elif args.command == 'fetch':
            print(fetch(args.release, args.destination))
        else:
            print(json.dumps(verify(args.directory, args.release), indent=2))
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        parser.exit(1, f'Distribution failed: {error}\n')


if __name__ == '__main__':
    main()
