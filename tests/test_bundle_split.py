"""Tests for ridge.bundle.split_file and its contract with offline_install."""
import shutil
import tempfile
import unittest
from pathlib import Path

from ridge.bundle import split_file
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


if __name__ == '__main__':
    unittest.main()
