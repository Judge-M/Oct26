"""Tests for ridge.bundle.split_file and its contract with offline_install."""
import shutil
import tempfile
import unittest
from pathlib import Path

from ridge.bundle import save_refs, split_file
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


if __name__ == '__main__':
    unittest.main()
