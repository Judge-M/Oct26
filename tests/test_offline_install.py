"""Tests for ridge.offline_install (F05 local slice)."""
import json
import io
import shutil
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path

from ridge.artifacts import sha256
from ridge.offline_install import (IMAGE_TAR, InstallError, image_parts, install,
                                   preflight_disk, verify_bundle)

KINDS = ['containers', 'desktop', 'disk', 'memory', 'autopsy', 'dependencies',
         'guides', 'evidence']


def make_bundle(root, certified=True, split_parts=1):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(root / 'source.zip', 'w') as archive:
        archive.writestr('ridge/__init__.py', '# source\n')
    # One small file per required kind (duplicate artifact paths are rejected).
    kind_files = {'guides': 'guides.md', 'evidence': 'evidence.bin',
                  'desktop': 'desktop.bin', 'disk': 'disk.bin',
                  'memory': 'memory.bin', 'autopsy': 'autopsy.bin'}
    for name in kind_files.values():
        (root / name).write_bytes(b'content-' + name.encode())
    def tree_archive(name, entries):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with tarfile.open(path, 'w:gz') as archive:
            for target, contents in entries.items():
                data = contents.encode()
                info = tarfile.TarInfo(target)
                info.size = len(data)
                archive.addfile(info, io.BytesIO(data))
        return path
    tree_archive('evidence/evidence-public.tar.gz',
                 {'evidence-public/readme.txt': 'public evidence'})
    tree_archive('dependencies/case-and-wazuh-config.tar.gz',
                 {'case-template/WS17.aut': 'case',
                  'wazuh-config/manifest.json': '{}'})
    tree_archive('dependencies/release-vault.tar.gz',
                 {'release-vault/manifest.json': '{}'})
    tree_archive('memory/WS17-native-v1.tar.gz', {'memory.raw': 'memory'})
    tar_content = b'fake-image-tar' * 100
    if split_parts == 1:
        (root / IMAGE_TAR).write_bytes(tar_content)
        container_path = IMAGE_TAR
    else:
        chunk = len(tar_content) // split_parts + 1
        for index in range(split_parts):
            piece = tar_content[index * chunk:(index + 1) * chunk]
            (root / f'{IMAGE_TAR}.part-{index + 1:03d}').write_bytes(piece)
        container_path = f'{IMAGE_TAR}.part-001'

    def artifact(path, kind):
        file = root / path
        return {'path': path, 'kind': kind, 'version': 'c1', 'release': 'r1',
                'bytes': file.stat().st_size, 'sha256': sha256(file)}

    artifacts = [artifact('source.zip', 'dependencies'), artifact(container_path, 'containers')]
    artifacts += [artifact(path, kind) for kind, path in kind_files.items()]
    artifacts += [artifact('evidence/evidence-public.tar.gz', 'evidence'),
                  artifact('dependencies/case-and-wazuh-config.tar.gz', 'dependencies'),
                  artifact('dependencies/release-vault.tar.gz', 'dependencies'),
                  artifact('memory/WS17-native-v1.tar.gz', 'memory')]
    images = {name: 'sha256:' + digit * 64 for name, digit in
              [('integration', '1'), ('iris', '2'), ('ctfd', '3'), ('desktop', '4')]}
    tags = {name: 'silent-ridge-' + name + ':dev' for name in images}
    manifest = {'schema': 1, 'release': 'r1', 'source_commit': 'abc123',
                'compatibility_verified': certified,
                'source_fingerprint': 'f' * 64,
                'images': images, 'image_tags': tags,
                'artifacts': artifacts}
    (root / 'release-manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    sums = {p.relative_to(root).as_posix(): sha256(p)
            for p in root.rglob('*') if p.is_file()}
    (root / 'SHA256SUMS.json').write_text(json.dumps(sums), encoding='utf-8')
    return manifest


class VerifyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.bundle = self.tmp / 'bundle'
        make_bundle(self.bundle)

    def test_happy_path_certified(self):
        _, certified = verify_bundle(self.bundle)
        self.assertIs(certified, True)

    def test_missing_part_named(self):
        (self.bundle / 'evidence.bin').unlink()
        (self.bundle / 'SHA256SUMS.json').write_text(json.dumps({
            p.relative_to(self.bundle).as_posix(): sha256(p)
            for p in self.bundle.rglob('*') if p.is_file()} | {'evidence.bin': '0' * 64}))
        with self.assertRaises(InstallError) as ctx:
            verify_bundle(self.bundle)
        self.assertIn('missing parts', str(ctx.exception))

    def test_corrupt_part_named(self):
        (self.bundle / 'evidence.bin').write_bytes(b'tampered')
        with self.assertRaises(InstallError) as ctx:
            verify_bundle(self.bundle)
        self.assertIn('corrupt bundle part: evidence.bin', str(ctx.exception))

    def test_lfs_stub_rejected(self):
        (self.bundle / 'evidence.bin').write_text(
            'version https://git-lfs.github.com/spec/v1\noid sha256:abc\nsize 10\n')
        sums = json.loads((self.bundle / 'SHA256SUMS.json').read_text())
        sums['evidence.bin'] = sha256(self.bundle / 'evidence.bin')
        (self.bundle / 'SHA256SUMS.json').write_text(json.dumps(sums))
        with self.assertRaises(InstallError) as ctx:
            verify_bundle(self.bundle)
        self.assertIn('LFS pointer stub', str(ctx.exception))

    def test_nested_lfs_stub_rejected_even_with_valid_outer_checksums(self):
        with zipfile.ZipFile(self.bundle / 'source.zip', 'w') as archive:
            archive.writestr('assets/large/native/capture.tar.gz',
                             'version https://git-lfs.github.com/spec/v1\n'
                             'oid sha256:' + 'a' * 64 + '\nsize 100\n')
        sums = json.loads((self.bundle / 'SHA256SUMS.json').read_text())
        sums['source.zip'] = sha256(self.bundle / 'source.zip')
        (self.bundle / 'SHA256SUMS.json').write_text(json.dumps(sums))
        with self.assertRaises(InstallError) as ctx:
            verify_bundle(self.bundle)
        self.assertIn('source.zip: assets/large/native/capture.tar.gz', str(ctx.exception))

    def test_source_commit_must_match_checkout_and_distribution(self):
        distribution = self.tmp / 'distribution.json'
        distribution.write_text(json.dumps({'repository': 'Judge-M/Oct26',
                                            'source_commit': 'different'}))
        with self.assertRaises(InstallError) as ctx:
            verify_bundle(self.bundle, distribution_manifest=distribution)
        self.assertIn('distribution source commit', str(ctx.exception))
        distribution.write_text(json.dumps({'repository': 'Judge-M/Oct26',
                                            'source_commit': 'abc123'}))
        with self.assertRaises(InstallError) as ctx:
            verify_bundle(self.bundle, expected_source_commit='other',
                          distribution_manifest=distribution)
        self.assertIn('expected checkout', str(ctx.exception))
        self.assertTrue(verify_bundle(self.bundle, expected_source_commit='abc123',
                                      distribution_manifest=distribution)[1])

    def test_uncertified_bundle_still_installs_with_gap_recorded(self):
        manifest = json.loads((self.bundle / 'release-manifest.json').read_text())
        manifest['compatibility_verified'] = False
        (self.bundle / 'release-manifest.json').write_text(json.dumps(manifest))
        sums = json.loads((self.bundle / 'SHA256SUMS.json').read_text())
        sums['release-manifest.json'] = sha256(self.bundle / 'release-manifest.json')
        (self.bundle / 'SHA256SUMS.json').write_text(json.dumps(sums))
        _, certified = verify_bundle(self.bundle)
        self.assertIsInstance(certified, str)


class PartsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def test_single_and_split_detection(self):
        single = self.tmp / 'single'
        make_bundle(single)
        self.assertEqual(len(image_parts(single)), 1)
        split = self.tmp / 'split'
        make_bundle(split, split_parts=3)
        self.assertEqual(len(image_parts(split)), 3)

    def test_gap_in_parts_rejected(self):
        bundle = self.tmp / 'gap'
        make_bundle(bundle, split_parts=3)
        (bundle / f'{IMAGE_TAR}.part-002').unlink()
        with self.assertRaises(InstallError):
            image_parts(bundle)


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.bundle = self.tmp / 'bundle'
        make_bundle(self.bundle, split_parts=2)
        self.dest = self.tmp / 'installed'

    def fake_runner(self, *args):
        if args[:2] == ('docker', 'load'):
            return 'Loaded image ID: sha256:' + '1' * 64 + '\n'
        if args[:3] == ('docker', 'image', 'ls'):
            return '\n'.join('sha256:' + digit * 64 for digit in '1234') + '\n'
        if args[:3] == ('docker', 'image', 'inspect'):
            digits = {'silent-ridge-integration:dev': '1', 'silent-ridge-iris:dev': '2',
                      'silent-ridge-ctfd:dev': '3', 'silent-ridge-desktop:dev': '4'}
            return 'sha256:' + digits[args[-1]] * 64 + '\n'
        raise AssertionError(args)

    def test_install_reconstructs_and_receipts(self):
        receipt = install(self.bundle, self.dest, runner=self.fake_runner)
        self.assertTrue((self.dest / 'source/ridge/__init__.py').is_file())
        self.assertTrue((self.dest / 'install-receipt.json').is_file())
        self.assertTrue((self.dest / 'assets/evidence-public/readme.txt').is_file())
        self.assertTrue((self.dest / 'assets/case-template/WS17.aut').is_file())
        self.assertTrue((self.dest / 'assets/wazuh-config/manifest.json').is_file())
        self.assertTrue((self.dest / 'assets/release-vault/manifest.json').is_file())
        self.assertTrue((self.dest / 'assets/originals/memory.raw').is_file())
        self.assertTrue((self.dest / 'runtime-local.example.json').is_file())
        for component in ('integration', 'iris', 'ctfd', 'desktop'):
            path = self.dest / 'source/work/build-receipts' / (component + '.json')
            self.assertTrue(path.is_file())
            self.assertEqual(json.loads(path.read_text())['origin'],
                             'verified-offline-bundle')
        self.assertTrue(receipt['certified_complete'])
        self.assertTrue(receipt['assets_materialized'])
        self.assertTrue(receipt['build_receipts_created'])
        self.assertEqual(receipt['release'], 'r1')
        self.assertEqual(receipt['source_archive_sha256'], sha256(self.bundle / 'source.zip'))
        self.assertIn('runtime-local.example.json', receipt['next'][0])
        self.assertIn('cd source && python -m ridge.deploy doctor', receipt['next'][1])

    def test_no_load_skips_docker(self):
        receipt = install(self.bundle, self.dest, load=False)
        self.assertFalse(receipt['images_loaded'])
        self.assertFalse(receipt['build_receipts_created'])

    def test_existing_destination_refused(self):
        self.dest.mkdir()
        with self.assertRaises(InstallError):
            install(self.bundle, self.dest, runner=self.fake_runner)

    def test_low_disk_fails_before_staging(self):
        with self.assertRaises(InstallError) as ctx:
            install(self.bundle, self.dest, runner=self.fake_runner, free_bytes=1)
        self.assertIn('insufficient disk', str(ctx.exception))
        self.assertFalse(self.dest.exists())
        self.assertFalse((self.tmp / '.installed.staging').exists())

    def test_interruption_leaves_no_partial_destination(self):
        def broken_runner(*args):
            raise OSError('simulated docker failure')
        with self.assertRaises(OSError):
            install(self.bundle, self.dest, runner=broken_runner)
        self.assertFalse(self.dest.exists())
        self.assertFalse((self.tmp / '.installed.staging').exists())

    def test_missing_image_after_load_fails(self):
        def lying_runner(*args):
            if args[:2] == ('docker', 'load'):
                return ''
            return 'sha256:' + '9' * 64 + '\n'
        with self.assertRaises(InstallError) as ctx:
            install(self.bundle, self.dest, runner=lying_runner)
        self.assertIn('docker load did not produce', str(ctx.exception))
        self.assertFalse(self.dest.exists())

    def test_missing_source_fingerprint_refuses_fake_build_receipts(self):
        manifest_path = self.bundle / 'release-manifest.json'
        manifest = json.loads(manifest_path.read_text())
        manifest.pop('source_fingerprint')
        manifest_path.write_text(json.dumps(manifest))
        sums = json.loads((self.bundle / 'SHA256SUMS.json').read_text())
        sums['release-manifest.json'] = sha256(manifest_path)
        (self.bundle / 'SHA256SUMS.json').write_text(json.dumps(sums))
        with self.assertRaisesRegex(InstallError, 'source fingerprint'):
            install(self.bundle, self.dest, runner=self.fake_runner)
        self.assertFalse(self.dest.exists())

    def test_asset_archive_links_are_rejected_before_publish(self):
        archive_path = self.bundle / 'dependencies/release-vault.tar.gz'
        with tarfile.open(archive_path, 'w:gz') as archive:
            entry = tarfile.TarInfo('release-vault/escape')
            entry.type = tarfile.SYMTYPE
            entry.linkname = '../../outside'
            archive.addfile(entry)
        manifest_path = self.bundle / 'release-manifest.json'
        manifest = json.loads(manifest_path.read_text())
        artifact = next(row for row in manifest['artifacts']
                        if row['path'] == 'dependencies/release-vault.tar.gz')
        artifact.update(bytes=archive_path.stat().st_size, sha256=sha256(archive_path))
        manifest_path.write_text(json.dumps(manifest))
        sums = json.loads((self.bundle / 'SHA256SUMS.json').read_text())
        sums['dependencies/release-vault.tar.gz'] = sha256(archive_path)
        sums['release-manifest.json'] = sha256(manifest_path)
        (self.bundle / 'SHA256SUMS.json').write_text(json.dumps(sums))
        with self.assertRaisesRegex(InstallError, 'link or special file'):
            install(self.bundle, self.dest, runner=self.fake_runner)
        self.assertFalse(self.dest.exists())

    def test_preflight_reports_bytes(self):
        needed = preflight_disk(self.bundle, self.dest, runner_free_bytes=10 ** 12)
        self.assertGreater(needed, 0)

    def _add_image_tags(self):
        manifest = json.loads((self.bundle / 'release-manifest.json').read_text())
        manifest['image_tags'] = {name: 'silent-ridge-' + name + ':dev'
                                  for name in ('integration', 'iris', 'ctfd', 'desktop')}
        (self.bundle / 'release-manifest.json').write_text(json.dumps(manifest),
                                                           encoding='utf-8')
        sums = json.loads((self.bundle / 'SHA256SUMS.json').read_text())
        sums['release-manifest.json'] = sha256(self.bundle / 'release-manifest.json')
        (self.bundle / 'SHA256SUMS.json').write_text(json.dumps(sums), encoding='utf-8')

    def _tag_runner(self, tag_map):
        def runner(*args):
            if args[:2] == ('docker', 'load'):
                return ''
            if args[:3] == ('docker', 'image', 'ls'):
                return '\n'.join('sha256:' + digit * 64 for digit in '1234') + '\n'
            if args[:3] == ('docker', 'image', 'inspect'):
                return tag_map[args[-1]] + '\n'
            raise AssertionError(args)
        return runner

    def test_tags_verified_after_load(self):
        """A load that restores only untagged <none> images passes the ID check but
        breaks compose (pull_policy: never); tags must be verified too."""
        self._add_image_tags()
        runner = self._tag_runner({'silent-ridge-integration:dev': 'sha256:' + '1' * 64,
                                   'silent-ridge-iris:dev': 'sha256:' + '2' * 64,
                                   'silent-ridge-ctfd:dev': 'sha256:' + '3' * 64,
                                   'silent-ridge-desktop:dev': 'sha256:' + '4' * 64})
        receipt = install(self.bundle, self.dest, runner=runner)
        self.assertTrue(receipt['tags_verified'])

    def test_wrong_tag_after_load_fails(self):
        self._add_image_tags()
        runner = self._tag_runner({'silent-ridge-integration:dev': 'sha256:' + '1' * 64,
                                   'silent-ridge-iris:dev': 'sha256:' + '9' * 64,
                                   'silent-ridge-ctfd:dev': 'sha256:' + '3' * 64,
                                   'silent-ridge-desktop:dev': 'sha256:' + '4' * 64})
        with self.assertRaises(InstallError) as ctx:
            install(self.bundle, self.dest, runner=runner)
        self.assertIn('did not restore expected tags', str(ctx.exception))
        self.assertFalse(self.dest.exists())


if __name__ == '__main__':
    unittest.main()
