import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import zipfile

from ridge import distribution as dist
from ridge.artifacts import sha256


class DistributionTests(unittest.TestCase):
    def images(self):
        return {name: f'ghcr.io/judge-m/oct26-{name}@sha256:' + 'a' * 64
                for name in dist.COMPONENTS}

    def fixture(self, root):
        files = {}
        for name in ('source.zip', 'fixtures.zip'):
            (root / name).write_bytes(b'fixture archive')
            files[name] = dict(bytes=(root / name).stat().st_size, sha256=sha256(root / name))
        manifest = dict(schema=1, repository=dist.REPOSITORY, release='v0.1.0',
                        source_commit='b' * 40, images=self.images(), files=files)
        (root / 'distribution.json').write_text(json.dumps(manifest), encoding='utf-8')

    def test_mutable_and_incomplete_image_locks_rejected(self):
        with self.assertRaises(ValueError):
            dist.image_lock({})
        images = self.images()
        images['ctfd'] = 'ghcr.io/judge-m/oct26-ctfd:latest'
        with self.assertRaises(ValueError):
            dist.image_lock(images)

    def test_corruption_and_wrong_release_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root)
            dist.verify(root, 'v0.1.0')
            with self.assertRaises(ValueError):
                dist.verify(root, 'v0.2.0')
            (root / 'source.zip').write_bytes(b'corrupted')
            with self.assertRaises(ValueError):
                dist.verify(root, 'v0.1.0')

    def test_archive_uses_explicit_inventory_and_rejects_lfs_pointer(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'tracked.txt').write_text('source')
            (root / '.env').write_text('do not ship')
            dist.archive(root, ['tracked.txt'], root / 'source.zip')
            with zipfile.ZipFile(root / 'source.zip') as archive:
                self.assertEqual(archive.namelist(), ['tracked.txt'])
            (root / 'large.img').write_text('version https://git-lfs.github.com/spec/v1\n')
            with self.assertRaisesRegex(ValueError, 'Git LFS'):
                dist.archive(root, ['large.img'], root / 'bad.zip')
            with self.assertRaises(ValueError):
                dist.archive(root, ['../outside'], root / 'escape.zip')

    def test_failed_fetch_does_not_publish_or_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / 'download'
            def download(command, **kwargs):
                stage = Path(command[command.index('--dir') + 1])
                self.fixture(stage)
                (stage / 'fixtures.zip').write_bytes(b'broken')
            with patch.object(dist.subprocess, 'run', side_effect=download):
                with self.assertRaises(ValueError):
                    dist.fetch('v0.1.0', target)
            self.assertFalse(target.exists())
            self.assertEqual(list(Path(temp).iterdir()), [])
            target.mkdir()
            with patch.object(dist.subprocess, 'run') as run:
                with self.assertRaises(ValueError):
                    dist.fetch('v0.1.0', target)
                run.assert_not_called()

    def test_successful_fetch_publishes_verified_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / 'download'
            def download(command, **kwargs):
                self.fixture(Path(command[command.index('--dir') + 1]))
            with patch.object(dist.subprocess, 'run', side_effect=download):
                self.assertEqual(dist.fetch('v0.1.0', target), target.resolve())
            dist.verify(target, 'v0.1.0')


if __name__ == '__main__':
    unittest.main()
