"""Deterministic tests for desktop evidence delivery (C03).

No real desktops or controller endpoint exist here (LIVE ACCEPTANCE BLOCKED).
A fake transport copies from a local release directory to simulate the fetch.
"""
import os
import shutil
import stat
import tempfile
import unittest
from pathlib import Path

from ridge.desktop_delivery import (
    DeliveryError, DesktopAgent, build_manifest, validate_manifest,
)


def make_release(root, files):
    for name, content in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8')
    return root


class FakeTransport:
    def __init__(self, source):
        self.source = Path(source)
        self.base = 'https://controller/evidence'
        self.calls = []
        self.fail_on = None

    def __call__(self, url, destination):
        name = url[len(self.base) + 1:]
        self.calls.append(name)
        if self.fail_on == name:
            raise OSError('connection lost')
        shutil.copyfile(self.source / name, destination)


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.release = make_release(self.root / 'release',
                                    {'network/dlp-body.txt': 'body',
                                     'network/dlp-metadata.json': '{"v":1}'})
        self.transport = FakeTransport(self.release)
        self.agent = DesktopAgent(transport=self.transport, base_url=self.transport.base,
                                  staging=self.root / 'staging', published=self.root / 'published')

    def tearDown(self):
        self.tmp.cleanup()

    def test_sync_publishes_verified_read_only_files(self):
        manifest = build_manifest(self.release, 1)
        status = self.agent.sync(manifest)
        self.assertTrue(status['ready'])
        body = self.root / 'published/network/dlp-body.txt'
        self.assertEqual(body.read_text(encoding='utf-8'), 'body')
        self.assertFalse(body.stat().st_mode & stat.S_IWUSR)
        self.assertFalse(os.access(body, os.W_OK))

    def test_repeat_sync_is_a_noop(self):
        manifest = build_manifest(self.release, 1)
        self.agent.sync(manifest)
        calls = list(self.transport.calls)
        self.agent.sync(manifest)
        self.assertEqual(self.transport.calls, calls)

    def test_interrupted_transfer_leaves_no_visible_file(self):
        manifest = build_manifest(self.release, 1)
        self.transport.fail_on = 'network/dlp-metadata.json'
        with self.assertRaises(OSError):
            self.agent.sync(manifest)
        self.assertFalse((self.root / 'published/network/dlp-metadata.json').exists())
        self.assertEqual([p for p in (self.root / 'staging').rglob('*') if p.is_file()], [])
        self.assertFalse(self.agent.status(1)['ready'])

    def test_corrupt_download_is_not_published(self):
        manifest = build_manifest(self.release, 1)

        def corrupt(url, destination):
            Path(destination).write_text('tampered', encoding='utf-8')

        agent = DesktopAgent(transport=corrupt, base_url=self.transport.base,
                             staging=self.root / 'staging2', published=self.root / 'published2')
        with self.assertRaisesRegex(DeliveryError, 'checksum'):
            agent.sync(manifest)
        self.assertFalse((self.root / 'published2/network/dlp-body.txt').exists())

    def test_reconnect_catches_up_and_reports_lag(self):
        self.agent.sync(build_manifest(self.release, 1))
        self.assertFalse(self.agent.status(controller_generation=2)['ready'])
        self.assertEqual(self.agent.status(2)['lag'], 1)
        make_release(self.release, {'hunting/late-inventory.csv': 'new'})
        self.agent.sync(build_manifest(self.release, 2))
        self.assertTrue(self.agent.status(2)['ready'])
        self.assertEqual(self.agent.status(2)['lag'], 0)

    def test_prune_removes_stale_released_file(self):
        self.agent.sync(build_manifest(self.release, 1))
        (self.release / 'network/dlp-metadata.json').unlink()
        self.agent.sync(build_manifest(self.release, 2))
        self.assertFalse((self.root / 'published/network/dlp-metadata.json').exists())

    def test_manifest_rejects_unsafe_and_empty(self):
        with self.assertRaisesRegex(DeliveryError, 'positive integer'):
            build_manifest(self.release, 0)
        (self.root / 'empty').mkdir()
        with self.assertRaisesRegex(DeliveryError, 'no files'):
            build_manifest(self.root / 'empty', 1)
        with self.assertRaisesRegex(DeliveryError, 'schema'):
            validate_manifest({'generation': 1, 'files': {'a': {'sha256': 'x', 'bytes': 1}}})
        with self.assertRaises(ValueError):
            validate_manifest({'schema': 1, 'generation': 1,
                               'files': {'../escape': {'sha256': 'x', 'bytes': 1}}})

    def test_generation_regression_rejected(self):
        self.agent.sync(build_manifest(self.release, 2))
        with self.assertRaisesRegex(DeliveryError, 'regressed'):
            self.agent.sync(build_manifest(self.release, 1))


if __name__ == '__main__':
    unittest.main()
