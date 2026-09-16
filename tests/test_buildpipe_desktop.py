import os
import tempfile
import unittest
from pathlib import Path

from buildpipe import BuildEnvironmentError, desktop
from ridge.artifacts import sha256


class DesktopTests(unittest.TestCase):
    def test_allocate_nbd_skips_busy(self):
        with tempfile.TemporaryDirectory() as folder:
            sys_block = Path(folder)
            for name, busy in [('nbd0', 'pid'), ('nbd1', 'holders'), ('nbd2', 'free')]:
                device = sys_block / name
                device.mkdir()
                if busy == 'pid':
                    (device / 'pid').write_text('1')
                elif busy == 'holders':
                    (device / 'holders').mkdir()
                    (device / 'holders' / 'x').write_text('held')
            selected = desktop.allocate_nbd(sys_block=sys_block, device_root=Path('/dev'))
            self.assertEqual(selected, Path('/dev/nbd2'))
            for name in ('nbd0', 'nbd1', 'nbd2'):
                (sys_block / name / 'pid').write_text('1')
            with self.assertRaisesRegex(ValueError, 'No free NBD'):
                desktop.allocate_nbd(sys_block=sys_block, device_root=Path('/dev'))

    def test_inputs_boot_files_guest_command_and_credentials(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            base = root / 'base.img'
            base.write_bytes(b'base')
            desktop.verify_inputs(root, {'base.img': sha256(base)})
            with self.assertRaisesRegex(ValueError, 'missing or changed'):
                desktop.verify_inputs(root, {'base.img': '0' * 64})
            files = desktop.generic_boot_files()
            self.assertIn('6.8.0-139-generic', files['etc/default/grub.d/99-silent-ridge.cfg'])
            self.assertIn('NoCloud', files['etc/cloud/cloud.cfg.d/99-silent-ridge-datasources.cfg'])
            command = desktop.guest_command(root)
            self.assertIn('-display', command)
            self.assertTrue(any('readonly=on' in part for part in command))
            self.assertTrue(any('qemu.pid' in part for part in command))
            first = desktop.new_credential(root / 'secrets' / 'key')
            second = desktop.new_credential(root / 'secrets' / 'key2')
            self.assertNotEqual(first.read_text(), second.read_text())
            with self.assertRaisesRegex(ValueError, 'already exists'):
                desktop.new_credential(first)

    def test_live_operations_blocked_without_linux(self):
        if os.name == 'posix':
            self.skipTest('guard is for non-Linux hosts')
        with self.assertRaises(BuildEnvironmentError):
            desktop.connect_nbd('image.qcow2', Path('/dev/nbd0'))
        with self.assertRaises(BuildEnvironmentError):
            desktop.start_guest(Path('build'))


if __name__ == '__main__':
    unittest.main()
