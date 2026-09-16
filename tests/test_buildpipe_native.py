import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from buildpipe import BuildEnvironmentError, native_records
from buildpipe_fixtures import native_source


class NativeRecordTests(unittest.TestCase):
    def test_pids_from_provenance_and_times_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = native_source(root / 'source')
            manifest = native_records.build(source, root / 'records', 'native-test')
            self.assertEqual(manifest['viewer_pid'], 6364)
            process = json.loads((root / 'records/prepared/windows-process.json').read_text())
            self.assertEqual(process['pid'], 6364)
            self.assertEqual(process['ppid'], 7644)
            self.assertEqual(process['utc'], '2026-09-15T23:22:00.0000000Z')
            task = json.loads((root / 'records/prepared/windows-task.json').read_text())
            self.assertEqual(task['pid'], 6364)
            self.assertEqual(task['executable'], 'C:\\Fixture\\brief-viewer.exe')
            memory = json.loads((root / 'records/prepared/memory-processes.json').read_text())
            self.assertEqual(memory['utc'], '2026-09-15T23:22:00+00:00')
            other = native_source(root / 'other', viewer_pid=1111, parent_pid=2222)
            native_records.build(other, root / 'records-other', 'native-test')
            other_process = json.loads((root / 'records-other/prepared/windows-process.json').read_text())
            self.assertEqual(other_process['pid'], 1111)
            self.assertEqual(other_process['ppid'], 2222)

    def test_corrupt_source_and_existing_destination_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = native_source(root / 'source')
            (source / 'WS17.raw').write_bytes(b'tampered')
            with self.assertRaisesRegex(ValueError, 'recorded hash'):
                native_records.build(source, root / 'records', 'native-test')
            self.assertFalse((root / 'records').exists())
            source = native_source(root / 'source2')
            with self.assertRaisesRegex(ValueError, 'Source hash mismatch'):
                native_records.build(source, root / 'records2', 'native-test',
                                     {'Security.evtx': '0' * 64})
            native_records.build(source, root / 'records3', 'native-test')
            with self.assertRaisesRegex(ValueError, 'never overwritten'):
                native_records.build(source, root / 'records3', 'native-test')

    def test_missing_sidecar_and_export_guard(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = native_source(root / 'source')
            (source / 'Security.evtx.records.json').unlink()
            with self.assertRaisesRegex(ValueError, 'export it with'):
                native_records.build(source, root / 'records', 'native-test')
            self.assertFalse((root / 'records').exists())
        command = native_records.evtx_export_command('Security.evtx', 'out.json')
        self.assertEqual(command[0], 'powershell')
        self.assertIn("'Security.evtx'", command[-1])
        with patch.object(native_records.os, 'name', 'posix'):
            with self.assertRaises(BuildEnvironmentError):
                native_records.export_evtx('Security.evtx', 'out.json')


if __name__ == '__main__':
    unittest.main()
