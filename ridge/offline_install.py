"""Atomic offline-bundle installer (F05 local slice).

Consumes a bundle produced by ``ridge.bundle.pack`` (a directory with
``release-manifest.json``, ``SHA256SUMS.json``, ``source.zip`` and
``validated-images.tar`` — the latter optionally split into bounded
``validated-images.tar.part-NNN`` pieces) and installs it:

1. Verify — every file hashed against ``SHA256SUMS.json`` and the manifest
   checked with ``ridge.artifacts.verify``; missing parts, corrupt files,
   wrong release and LFS pointer stubs all fail before anything changes.
2. Preflight — free disk must cover extraction plus image load; the error
   names required vs available bytes.
3. Stage + rename — source and images are staged in a sibling temporary
   directory and moved into place only when complete, so an interruption
   never leaves a half-installed destination; rerunning is always safe.
4. Load — image archives are reassembled if split and handed to
   ``docker load``; every manifest image ID must be present afterwards.
5. Receipt — an install receipt records the release, source commit and
   image IDs, plus the exact next commands.

This module never publishes anything and never touches a live runtime.
"""
import argparse
import json
import os
import shutil
import zipfile
from pathlib import Path

from ridge.artifacts import safe, sha256, verify

IMAGE_TAR = 'validated-images.tar'
METADATA = {'release-manifest.json', 'SHA256SUMS.json', 'source-image-checks.json'}


class InstallError(RuntimeError):
    """A named preflight/verification failure; nothing was installed."""


def _read_manifest(bundle):
    for name in ('release-manifest.json', 'SHA256SUMS.json'):
        if not (bundle / name).is_file():
            raise InstallError('bundle is missing ' + name)
    return json.loads((bundle / 'release-manifest.json').read_text(encoding='utf-8')), \
           json.loads((bundle / 'SHA256SUMS.json').read_text(encoding='utf-8'))


def verify_bundle(bundle):
    """Hash every bundle file against SHA256SUMS.json; verify the manifest."""
    bundle = Path(bundle)
    manifest, sums = _read_manifest(bundle)
    on_disk = {p.relative_to(bundle).as_posix() for p in bundle.rglob('*') if p.is_file()}
    # SHA256SUMS.json cannot list its own digest; it is verified implicitly by
    # every other file matching its recorded hash.
    on_disk.discard('SHA256SUMS.json')
    expected = set(sums)
    if on_disk != expected:
        missing = expected - on_disk
        extra = on_disk - expected
        detail = []
        if missing:
            detail.append('missing parts: ' + ', '.join(sorted(missing)))
        if extra:
            detail.append('unrecorded files: ' + ', '.join(sorted(extra)))
        raise InstallError('bundle incomplete (' + '; '.join(detail) + ')')
    for name in sorted(expected):
        path = safe(bundle, name)
        if sha256(path) != sums[name]:
            raise InstallError('corrupt bundle part: ' + name)
        if name.endswith(('.zip', '.tar', '.bin')):
            with path.open('rb') as stream:
                if stream.read(128).splitlines()[:1] == [b'version https://git-lfs.github.com/spec/v1']:
                    raise InstallError('Git LFS pointer stub instead of content: ' + name)
    # The manifest itself is integrity-checked, but a bundle assembled before
    # the capacity/restore gates is not a certified offline release; inspect
    # with the same fail-closed rules and report (not waive) incompleteness.
    try:
        verify(bundle, manifest, complete=True)
        certified = True
    except ValueError as exc:
        verify(bundle, manifest, complete=False)
        certified = str(exc)
    return manifest, certified


def image_parts(bundle):
    """Ordered image-archive pieces: single tar or .part-NNN series."""
    bundle = Path(bundle)
    single = bundle / IMAGE_TAR
    if single.is_file():
        return [single]
    parts = sorted(bundle.glob(IMAGE_TAR + '.part-*'))
    if not parts:
        raise InstallError('no image archive (validated-images.tar[.part-NNN]) in bundle')
    for index, part in enumerate(parts, 1):
        if part.name != f'{IMAGE_TAR}.part-{index:03d}':
            raise InstallError('gap in image archive parts at ' + part.name)
    return parts


def preflight_disk(bundle, destination, runner_free_bytes=None):
    """Fail cleanly when extraction + image load cannot fit."""
    needed = sum(p.stat().st_size for p in Path(bundle).rglob('*') if p.is_file())
    needed *= 2  # extracted copies beside the bundle plus docker's load working space
    free = runner_free_bytes if runner_free_bytes is not None \
        else shutil.disk_usage(Path(destination).parent).free
    if free < needed:
        raise InstallError(f'insufficient disk: need ~{needed} bytes, have {free}')
    return needed


def _assemble(parts, target):
    with target.open('wb') as out:
        for part in parts:
            with part.open('rb') as stream:
                shutil.copyfileobj(stream, out, 1024 * 1024)
    return target


def install(bundle, destination, runner=None, load=True, free_bytes=None):
    """Verify, then atomically install source + images. Returns a receipt."""
    bundle = Path(bundle).resolve()
    destination = Path(destination).resolve()
    manifest, certified = verify_bundle(bundle)
    parts = image_parts(bundle)
    preflight_disk(bundle, destination, free_bytes)
    if destination.exists():
        raise InstallError('destination already exists: ' + str(destination))
    staging = destination.parent / ('.' + destination.name + '.staging')
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True)
    try:
        with zipfile.ZipFile(safe(bundle, 'source.zip')) as archive:
            archive.extractall(staging / 'source')
        tar = _assemble(parts, staging / IMAGE_TAR)
        images = []
        if load:
            if runner is None:
                import subprocess
                runner = lambda *args: subprocess.check_output(args, text=True)
            output = runner('docker', 'load', '--input', str(tar))
            images = sorted(set(manifest.get('images', {}).values()))
            listed = runner('docker', 'image', 'ls', '--format', '{{.ID}}', '--no-trunc')
            missing = [image for image in images if image not in listed]
            if missing:
                raise InstallError('docker load did not produce image IDs: ' + ', '.join(missing))
        receipt = {
            'schema': 1,
            'release': manifest['release'],
            'source_commit': manifest['source_commit'],
            'certified_complete': certified is True,
            'certification_gap': None if certified is True else certified,
            'images': sorted(set(manifest.get('images', {}).values())),
            'images_loaded': bool(load),
            'source': 'source',
            'next': [
                'cd source && python -m ridge.deploy doctor',
                'python -m ridge.deploy up --profile <profile.json> --runtime <runtime-dir>',
            ],
        }
        (staging / 'install-receipt.json').write_text(json.dumps(receipt, indent=2))
        os.replace(staging, destination)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bundle', type=Path)
    parser.add_argument('destination', type=Path)
    parser.add_argument('--no-load', action='store_true',
                        help='verify and unpack only; skip docker load')
    args = parser.parse_args()
    receipt = install(args.bundle, args.destination, load=not args.no_load)
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
