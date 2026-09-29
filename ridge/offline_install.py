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
5. Receipt — an install receipt records the release, source commit, verified
   source archive SHA-256 and image IDs, plus the exact next commands.

This module never publishes anything and never touches a live runtime.
"""
import argparse
import json
import os
import shutil
import tarfile
import zipfile
from pathlib import Path, PurePosixPath

from ridge.artifacts import safe, sha256, verify

IMAGE_TAR = 'validated-images.tar'
METADATA = {'release-manifest.json', 'SHA256SUMS.json', 'source-image-checks.json'}
CUSTOM_COMPONENTS = ('integration', 'iris', 'ctfd', 'desktop')
ASSET_ARCHIVES = (
    ('evidence/evidence-public.tar.gz', ''),
    ('dependencies/case-and-wazuh-config.tar.gz', ''),
    ('dependencies/release-vault.tar.gz', ''),
    ('memory/WS17-native-v1.tar.gz', 'originals'),
)


class InstallError(RuntimeError):
    """A named preflight/verification failure; nothing was installed."""


def _read_manifest(bundle):
    for name in ('release-manifest.json', 'SHA256SUMS.json'):
        if not (bundle / name).is_file():
            raise InstallError('bundle is missing ' + name)
    return json.loads((bundle / 'release-manifest.json').read_text(encoding='utf-8')), \
           json.loads((bundle / 'SHA256SUMS.json').read_text(encoding='utf-8'))


def _verify_source_archive(source):
    """Reject pointer stubs and unsafe names inside the source actually installed."""
    try:
        with zipfile.ZipFile(source) as archive:
            seen = set()
            for entry in archive.infolist():
                name = entry.filename
                parts = PurePosixPath(name).parts
                if (not parts or name.startswith('/') or '\\' in name or '..' in parts
                        or ':' in parts[0]
                        or name in seen):
                    raise InstallError('unsafe or duplicate source.zip entry: ' + name)
                seen.add(name)
                if entry.is_dir():
                    continue
                with archive.open(entry) as stream:
                    if stream.read(128).splitlines()[:1] == [
                            b'version https://git-lfs.github.com/spec/v1']:
                        raise InstallError('Git LFS pointer stub in source.zip: ' + name)
    except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
        if isinstance(exc, InstallError):
            raise
        raise InstallError('invalid source.zip: ' + str(exc)) from exc


def verify_bundle(bundle, expected_source_commit=None, distribution_manifest=None):
    """Hash every bundle file against SHA256SUMS.json; verify the manifest."""
    bundle = Path(bundle)
    manifest, sums = _read_manifest(bundle)
    source_commit = manifest.get('source_commit')
    if expected_source_commit is not None and source_commit != expected_source_commit:
        raise InstallError('bundle source commit %s differs from expected checkout %s'
                           % (source_commit, expected_source_commit))
    if distribution_manifest is not None:
        try:
            distribution = json.loads(Path(distribution_manifest).read_text(encoding='utf-8'))
        except (OSError, ValueError) as exc:
            raise InstallError('cannot read distribution manifest: ' + str(exc)) from exc
        if distribution.get('repository') != 'Judge-M/Oct26':
            raise InstallError('distribution repository is not Judge-M/Oct26')
        if distribution.get('source_commit') != source_commit:
            raise InstallError('distribution source commit %s differs from bundle %s'
                               % (distribution.get('source_commit'), source_commit))
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
    _verify_source_archive(safe(bundle, 'source.zip'))
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


def _extract_safe_tar(archive_path, destination):
    """Extract regular files/directories without trusting tar paths or links."""
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    seen = set()
    try:
        with tarfile.open(archive_path) as archive:
            for member in archive.getmembers():
                name = member.name.rstrip('/')
                parts = PurePosixPath(name).parts
                if (not name or member.name.startswith('/') or '\\' in member.name
                        or '..' in parts or ':' in parts[0] or name in seen):
                    raise InstallError('unsafe or duplicate asset archive entry: '
                                       + member.name)
                seen.add(name)
                target = safe(destination, name)
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                elif member.isfile():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    source = archive.extractfile(member)
                    if source is None:
                        raise InstallError('cannot read asset archive entry: ' + member.name)
                    with source, target.open('wb') as output:
                        shutil.copyfileobj(source, output, 1024 * 1024)
                else:
                    raise InstallError('asset archive contains a link or special file: '
                                       + member.name)
    except InstallError:
        raise
    except (OSError, tarfile.TarError, ValueError) as exc:
        raise InstallError('invalid asset archive %s: %s'
                           % (Path(archive_path).name, exc)) from exc


def _materialize_assets(bundle, staging, certified):
    missing = [name for name, _ in ASSET_ARCHIVES if not (bundle / name).is_file()]
    if missing:
        if certified:
            raise InstallError('certified bundle is missing deployable asset archives: '
                               + ', '.join(missing))
        return False
    assets = staging / 'assets'
    for name, relative in ASSET_ARCHIVES:
        _extract_safe_tar(bundle / name, assets / relative)
    expected = ('evidence-public', 'case-template', 'wazuh-config',
                'release-vault', 'originals')
    absent = [name for name in expected if not (assets / name).is_dir()]
    if absent:
        raise InstallError('asset archives did not materialize required directories: '
                           + ', '.join(absent))
    return True


def _write_build_receipts(staging, manifest, source_archive_sha256):
    fingerprint = manifest.get('source_fingerprint')
    if not isinstance(fingerprint, str) or len(fingerprint) != 64:
        raise InstallError('bundle has no source fingerprint for deployment build receipts; '
                           'rebuild it with the current ridge.bundle producer')
    tags = manifest.get('image_tags') or {}
    images = manifest.get('images') or {}
    missing = [name for name in CUSTOM_COMPONENTS if name not in tags or name not in images]
    if missing:
        raise InstallError('bundle cannot create deployment build receipts for: '
                           + ', '.join(missing))
    receipts = staging / 'source' / 'work' / 'build-receipts'
    receipts.mkdir(parents=True, exist_ok=True)
    for component in CUSTOM_COMPONENTS:
        record = {
            'schema': 2,
            'component': component,
            'image': tags[component],
            'image_id': images[component],
            'source': fingerprint,
            'origin': 'verified-offline-bundle',
            'release': manifest['release'],
            'source_commit': manifest['source_commit'],
            'source_archive_sha256': source_archive_sha256,
        }
        (receipts / (component + '.json')).write_text(
            json.dumps(record, indent=2) + '\n', encoding='utf-8')
    return receipts


def install(bundle, destination, runner=None, load=True, free_bytes=None,
            expected_source_commit=None, distribution_manifest=None):
    """Verify, then atomically install source + images. Returns a receipt."""
    bundle = Path(bundle).resolve()
    destination = Path(destination).resolve()
    manifest, certified = verify_bundle(
        bundle, expected_source_commit=expected_source_commit,
        distribution_manifest=distribution_manifest)
    _, verified_sums = _read_manifest(bundle)
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
        assets_materialized = _materialize_assets(bundle, staging, certified is True)
        tar = _assemble(parts, staging / IMAGE_TAR)
        images = []
        build_receipts = False
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
            # A load that restores only untagged <none> images passes the ID check
            # but breaks every compose file (pull_policy: never). Verify the tags.
            expected_tags = manifest.get('image_tags') or {}
            if expected_tags:
                mismatched = []
                for kind, tag in sorted(expected_tags.items()):
                    actual = runner('docker', 'image', 'inspect', '--format', '{{.Id}}',
                                    tag).strip()
                    if actual != manifest['images'].get(kind):
                        mismatched.append('%s (%s)' % (kind, tag))
                if mismatched:
                    raise InstallError('docker load did not restore expected tags: '
                                       + ', '.join(mismatched))
            _write_build_receipts(staging, manifest, verified_sums['source.zip'])
            build_receipts = True
        local_template = {
            'bind_ip': 'REPLACE_WITH_LAN_IP',
            'assets': {
                key: str(destination / 'assets' / directory)
                for key, directory in (
                    ('evidence_public', 'evidence-public'),
                    ('release_vault', 'release-vault'),
                    ('case_template', 'case-template'),
                    ('originals', 'originals'),
                    ('wazuh_config', 'wazuh-config'),
                )
            },
            'ports': {'crl': 8080, 'iris': 8081, 'ctfd': 8083, 'guac': 8082,
                      'wazuh_dashboard': 8443, 'wazuh_indexer': 9200},
            'index_name': 'silent-ridge-oct26',
        }
        (staging / 'runtime-local.example.json').write_text(
            json.dumps(local_template, indent=2) + '\n', encoding='utf-8')
        receipt = {
            'schema': 2,
            'release': manifest['release'],
            'source_commit': manifest['source_commit'],
            'source_archive_sha256': verified_sums['source.zip'],
            'source_image_checks_sha256': verified_sums.get('source-image-checks.json'),
            'certified_complete': certified is True,
            'certification_gap': None if certified is True else certified,
            'images': sorted(set(manifest.get('images', {}).values())),
            'images_loaded': bool(load),
            'tags_verified': bool(load and manifest.get('image_tags')),
            'build_receipts_created': build_receipts,
            'assets_materialized': assets_materialized,
            'source': 'source',
            'next': [
                'copy runtime-local.example.json to <runtime-dir>/local.json and set bind_ip',
                'cd source && python -m ridge.deploy doctor --profile <profile.json> --runtime <runtime-dir>',
                'python -m ridge.deploy up --teams 10 --profile <profile.json> --runtime <runtime-dir>',
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
    parser.add_argument('--expected-source-commit',
                        help='refuse a bundle built from a different checkout commit')
    parser.add_argument('--distribution-manifest', type=Path,
                        help='refuse a bundle whose source commit differs from distribution.json')
    args = parser.parse_args()
    receipt = install(args.bundle, args.destination, load=not args.no_load,
                      expected_source_commit=args.expected_source_commit,
                      distribution_manifest=args.distribution_manifest)
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
