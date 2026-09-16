import hashlib
from pathlib import Path
import tempfile
import unittest

from ridge.desktop_image import assemble


class DesktopImageTests(unittest.TestCase):
    def test_integrity_order_and_existing_disk_protection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            parts = []
            for name, data in [('part1', b'first'), ('part2', b'second')]:
                (root / name).write_bytes(data)
                parts.append(dict(path=name, bytes=len(data), sha256=hashlib.sha256(data).hexdigest()))
            manifest = dict(schema=1, format='qcow2', parts=parts, bytes=11,
                            sha256=hashlib.sha256(b'firstsecond').hexdigest())
            output = root / 'disk.qcow2'
            assemble(root, manifest, output)
            self.assertEqual(output.read_bytes(), b'firstsecond')
            with self.assertRaises(ValueError):
                assemble(root, manifest, output)
            manifest['parts'] = list(reversed(parts))
            with self.assertRaisesRegex(ValueError, 'Reassembled'):
                assemble(root, manifest, root / 'wrong-order')
            self.assertFalse((root / 'wrong-order').exists())
            (root / 'part1').write_bytes(b'broken')
            with self.assertRaisesRegex(ValueError, 'Corrupt'):
                assemble(root, manifest, root / 'corrupt')
            self.assertFalse(list(root.glob('.desktop-*')))
