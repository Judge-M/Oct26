import tempfile
import unittest
from pathlib import Path

from buildpipe import export


class ExportTests(unittest.TestCase):
    def test_assert_stopped(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            export.assert_stopped(root)
            proc = root / 'proc'
            (proc / '1234').mkdir(parents=True)
            (root / 'qemu.pid').write_text('1234')
            with self.assertRaisesRegex(ValueError, 'still running'):
                export.assert_stopped(root, proc=proc)
            (root / 'qemu.pid').write_text('9999')
            export.assert_stopped(root, proc=proc)
            (root / 'qemu.pid').write_text('not-a-pid')
            with self.assertRaisesRegex(ValueError, 'Malformed'):
                export.assert_stopped(root, proc=proc)

    def test_seal_checks_report_observed_results(self):
        with tempfile.TemporaryDirectory() as folder:
            mount = Path(folder) / 'mount'
            (mount / 'etc/ssh').mkdir(parents=True)
            (mount / 'var/lib/cloud/instances').mkdir(parents=True)
            (mount / 'opt/silent-ridge/originals/windows').mkdir(parents=True)
            (mount / 'opt/silent-ridge/originals/windows/WS17.raw').write_bytes(b'raw')
            (mount / 'home/participant/Cases/WS17').mkdir(parents=True)
            (mount / 'home/participant/Cases/WS17/WS17.aut').write_text('case')
            expected = {'native_capture': 'opt/silent-ridge/originals/windows/WS17.raw',
                        'prepared_case': 'home/participant/Cases/WS17/WS17.aut'}
            checks = export.seal_checks(mount, expected)
            export.validate_seal(checks)
            self.assertTrue(all(checks.values()))
            (mount / 'etc/silent-ridge').mkdir(parents=True)
            (mount / 'etc/silent-ridge/vnc-password').write_text('secret')
            failed = export.seal_checks(mount, expected)
            self.assertFalse(failed['credential_gate'])
            with self.assertRaisesRegex(ValueError, 'credential_gate'):
                export.validate_seal(failed)

    def test_split_verify_corruption_and_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            image = root / 'disk.qcow2'
            image.write_bytes(b'0123456789' * 5)
            manifest = export.split_and_hash(image, root / 'release', 'desktop-test', part_limit=7)
            self.assertEqual(sum(part['bytes'] for part in manifest['parts']), image.stat().st_size)
            self.assertGreater(len(manifest['parts']), 1)
            self.assertEqual(export.verify_release(root / 'release', 'desktop-test')['sha256'], manifest['sha256'])
            (root / 'release' / manifest['parts'][0]['path']).write_bytes(b'corrupt')
            with self.assertRaisesRegex(ValueError, 'Corrupt or missing'):
                export.verify_release(root / 'release', 'desktop-test')
            with self.assertRaisesRegex(ValueError, 'never overwritten'):
                export.split_and_hash(image, root / 'release', 'desktop-test')

    def test_marker_and_compact_guards(self):
        self.assertTrue(export.offline_boot_marker('log ' + export.BOOT_MARKER + ' end'))
        self.assertFalse(export.offline_boot_marker('no marker here'))
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'out.qcow2').write_bytes(b'existing')
            with self.assertRaisesRegex(ValueError, 'never overwritten'):
                export.compact(root / 'in.qcow2', root / 'out.qcow2')


if __name__ == '__main__':
    unittest.main()
