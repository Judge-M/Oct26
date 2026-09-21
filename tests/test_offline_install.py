"""Tests for ridge.offline_install (F05 local slice)."""
import json
import shutil
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
    manifest = {'schema': 1, 'release': 'r1', 'source_commit': 'abc123',
                'compatibility_verified': certified,
                'images': {'integration': 'sha256:' + '1' * 64,
                           'iris': 'sha256:' + '2' * 64},
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
            return 'sha256:' + '1' * 64 + '\n' + 'sha256:' + '2' * 64 + '\n'
        raise AssertionError(args)

    def test_install_reconstructs_and_receipts(self):
        receipt = install(self.bundle, self.dest, runner=self.fake_runner)
        self.assertTrue((self.dest / 'source/ridge/__init__.py').is_file())
        self.assertTrue((self.dest / 'install-receipt.json').is_file())
        self.assertTrue(receipt['certified_complete'])
        self.assertEqual(receipt['release'], 'r1')
        self.assertEqual(receipt['next'][0],
                         'cd source && python -m ridge.deploy doctor')

    def test_no_load_skips_docker(self):
        receipt = install(self.bundle, self.dest, load=False)
        self.assertFalse(receipt['images_loaded'])

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

    def test_preflight_reports_bytes(self):
        needed = preflight_disk(self.bundle, self.dest, runner_free_bytes=10 ** 12)
        self.assertGreater(needed, 0)


if __name__ == '__main__':
    unittest.main()
