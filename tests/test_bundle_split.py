"""Tests for ridge.bundle.split_file and its contract with offline_install."""
import shutil
import tempfile
import unittest
import hashlib
import zipfile
from pathlib import Path

from ridge.bundle import LAYOUTS, materialize_lfs_source, save_refs, split_file
from ridge.offline_install import image_parts


class SplitFileTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def test_small_file_not_split(self):
        target = self.tmp / 'data.tar'
        target.write_bytes(b'x' * 100)
        parts = split_file(target, 1000)
        self.assertEqual(parts, [target])
        self.assertTrue(target.is_file())

    def test_split_bounded_parts_preserve_bytes(self):
        blob = bytes(range(256)) * 100  # 25,600 bytes
        target = self.tmp / 'validated-images.tar'
        target.write_bytes(blob)
        parts = split_file(target, 10_000)
        self.assertEqual(len(parts), 3)
        self.assertFalse(target.exists())
        for part in parts[:-1]:
            self.assertEqual(part.stat().st_size, 10_000)
        reassembled = b''.join(p.read_bytes() for p in parts)
        self.assertEqual(reassembled, blob)

    def test_naming_matches_installer_contract(self):
        target = self.tmp / 'validated-images.tar'
        target.write_bytes(b'y' * 5000)
        split_file(target, 1000)
        # The installer must see exactly these 5 parts, in order.
        found = image_parts(self.tmp)
        self.assertEqual(len(found), 5)
        self.assertEqual(found[0].name, 'validated-images.tar.part-001')
        self.assertEqual(found[-1].name, 'validated-images.tar.part-005')

    def test_rejects_nonpositive_bound(self):
        target = self.tmp / 'data.tar'
        target.write_bytes(b'x')
        with self.assertRaises(ValueError):
            split_file(target, 0)


class SaveRefsTests(unittest.TestCase):
    """docker image save must receive tags, never bare IDs — an ID-saved archive
    loads as untagged <none> images and every compose file then fails on a cold
    host (pull_policy: never)."""

    IDS = {'integration': 'sha256:' + '1' * 64, 'iris': 'sha256:' + '2' * 64}
    TAGS = {'integration': 'silent-ridge-integration:dev', 'iris': 'silent-ridge-iris:dev'}

    def test_uses_manifest_tags(self):
        manifest = {'images': dict(self.IDS), 'image_tags': dict(self.TAGS)}
        inspect = lambda ref: self.IDS[{v: k for k, v in self.TAGS.items()}[ref]]
        refs = save_refs(manifest, inspect=inspect)
        self.assertEqual(sorted(refs), sorted(self.TAGS.values()))

    def test_missing_image_tags_named(self):
        manifest = {'images': dict(self.IDS)}
        with self.assertRaises(ValueError) as ctx:
            save_refs(manifest, inspect=lambda ref: '')
        self.assertIn('image_tags', str(ctx.exception))

    def test_tag_resolving_to_wrong_id_fails(self):
        manifest = {'images': dict(self.IDS), 'image_tags': dict(self.TAGS)}
        with self.assertRaises(ValueError) as ctx:
            save_refs(manifest, inspect=lambda ref: 'sha256:' + '9' * 64)
        self.assertIn('expected', str(ctx.exception))


class ImageLayoutTests(unittest.TestCase):
    def test_every_custom_image_copy_is_covered_by_source_matching(self):
        self.assertIn(('bounded_http.py', '/opt/silent-ridge/bounded_http.py'),
                      LAYOUTS['integration'])
        self.assertIn(('integrations/iris_bootstrap.py',
                       '/iriswebapp/iris_bootstrap.py'), LAYOUTS['iris'])
        self.assertIn(('deployment/expanded/desktop/entrypoint.sh',
                       '/usr/local/bin/silent-ridge-entrypoint'), LAYOUTS['desktop'])
        self.assertIn(('deployment/expanded/desktop/helpers',
                       '/opt/silent-ridge/helpers'), LAYOUTS['desktop'])


class MaterializeSourceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.archive = self.tmp / 'source.zip'
        self.name = 'assets/large/native/capture.tar.gz'
        self.content = b'actual native evidence\x00\xff' * 30
        digest = hashlib.sha256(self.content).hexdigest()
        self.pointer = ('version https://git-lfs.github.com/spec/v1\n'
                        f'oid sha256:{digest}\nsize {len(self.content)}\n').encode()
        with zipfile.ZipFile(self.archive, 'w') as output:
            output.writestr('ridge/__init__.py', b'# original source\n')
            output.writestr(self.name, self.pointer)
            output.writestr('assets/vm-desktop/parked.part001', self.pointer)

    def test_verified_lfs_bytes_replace_pointer_without_changing_other_source(self):
        path = self.tmp / self.name
        path.parent.mkdir(parents=True)
        path.write_bytes(self.content)
        self.assertEqual(materialize_lfs_source(
            self.archive, self.tmp, exclude_prefixes=('assets/vm-desktop/',)), [self.name])
        with zipfile.ZipFile(self.archive) as source:
            self.assertEqual(source.read(self.name), self.content)
            self.assertEqual(source.read('ridge/__init__.py'), b'# original source\n')

    def test_missing_or_wrong_lfs_content_fails_without_replacing_archive(self):
        before = self.archive.read_bytes()
        with self.assertRaisesRegex(ValueError, 'Materialize and verify'):
            materialize_lfs_source(self.archive, self.tmp)
        path = self.tmp / self.name
        path.parent.mkdir(parents=True)
        path.write_bytes(b'x' * len(self.content))
        with self.assertRaisesRegex(ValueError, 'Materialize and verify'):
            materialize_lfs_source(self.archive, self.tmp)
        self.assertEqual(self.archive.read_bytes(), before)

    def test_parked_vm_can_be_excluded_from_runtime_source(self):
        path = self.tmp / self.name
        path.parent.mkdir(parents=True)
        path.write_bytes(self.content)
        materialize_lfs_source(self.archive, self.tmp,
                               exclude_prefixes=('assets/vm-desktop/',))
        with zipfile.ZipFile(self.archive) as source:
            self.assertNotIn('assets/vm-desktop/parked.part001', source.namelist())
            self.assertEqual(source.read(self.name), self.content)


if __name__ == '__main__':
    unittest.main()
