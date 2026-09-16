import hashlib
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest

from expanded.materialize_native import materialize


class NativeMaterializeTests(unittest.TestCase):
    def fixture(self, root, unsafe=False):
        files = {'WS17.raw': b'test memory', 'symbols/kernel.json.xz': b'symbol fixture',
                 'memory-layer.json': json.dumps({'kernel.symbol_table_name.isf_url':
                     'file:///originals/windows/symbols/kernel.json.xz'}).encode()}
        if unsafe:
            files['../../outside'] = b'escape'
        archive = root / 'native.tar.gz'
        with tarfile.open(archive, 'w:gz') as out:
            for name, data in files.items():
                member = tarfile.TarInfo('originals/windows/'+name)
                member.size = len(data)
                out.addfile(member, io.BytesIO(data))
        manifest = dict(artifact=archive.name, bytes=archive.stat().st_size,
            sha256=hashlib.sha256(archive.read_bytes()).hexdigest(), files={
                name: dict(bytes=len(data), sha256=hashlib.sha256(data).hexdigest()) for name,data in files.items()})
        location = root / 'assets/native-windows-v1'
        location.mkdir(parents=True)
        (location / 'archive.json').write_text(json.dumps(manifest))

    def test_verified_relocation_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.fixture(root)
            self.assertTrue(materialize(root)['archive_verified'])
            destination = root / 'new-workspace'
            materialize(root, destination)
            native = destination / 'originals/windows'
            config = json.loads((native / 'memory-layer.local.json').read_text())
            self.assertEqual(config['kernel.layer_name.memory_layer.location'], (native/'WS17.raw').as_uri())
            self.assertTrue((destination / 'VERIFIED.json').exists())
            with self.assertRaises(ValueError):
                materialize(root, destination)

    def test_corruption_and_escape_leave_no_completed_output(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.fixture(root, unsafe=True)
            with self.assertRaises(ValueError):
                materialize(root, root/'bad')
            self.assertFalse((root/'bad').exists())
            self.assertFalse((root/'outside').exists())
            (root/'native.tar.gz').write_bytes(b'broken')
            with self.assertRaises(ValueError):
                materialize(root, root/'corrupt')
            self.assertFalse((root/'corrupt').exists())
