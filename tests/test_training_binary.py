import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.verify_training_binary import verify


class TrainingBinaryContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / 'assets').mkdir()
        (self.root / 'src').mkdir()
        self.binary = b'published executable bytes'
        self.source = b'int main(void) {\n  return 0;\n}\n'
        (self.root / 'assets/training.bin').write_bytes(self.binary)
        (self.root / 'src/training.c').write_bytes(self.source)
        manifest = {
            'path': 'assets/training.bin',
            'source': 'src/training.c',
            'sha256': hashlib.sha256(self.binary).hexdigest(),
            'source_sha256': hashlib.sha256(self.source).hexdigest(),
            'compiler_input_sha256': hashlib.sha256(
                self.source.replace(b'\n', b'\r\n')).hexdigest(),
        }
        (self.root / 'assets/training-binary.json').write_text(
            json.dumps(manifest), encoding='utf-8')

    def tearDown(self):
        self.tmp.cleanup()

    def test_verifies_published_binary_and_both_source_forms(self):
        result = verify(self.root)
        self.assertEqual(result['published_binary'], hashlib.sha256(self.binary).hexdigest())

    def test_rejects_changed_published_binary(self):
        (self.root / 'assets/training.bin').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'published_binary SHA-256 mismatch'):
            verify(self.root)

    def test_rejects_changed_source(self):
        (self.root / 'src/training.c').write_bytes(self.source + b' ')
        with self.assertRaisesRegex(ValueError, 'tracked_lf_source SHA-256 mismatch'):
            verify(self.root)

    def test_rejects_unrecorded_normalization(self):
        manifest_path = self.root / 'assets/training-binary.json'
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        manifest['compiler_input_sha256'] = '0' * 64
        manifest_path.write_text(json.dumps(manifest), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'recorded_crlf_compiler_input SHA-256 mismatch'):
            verify(self.root)


if __name__ == '__main__':
    unittest.main()
