import tempfile
import unittest
from pathlib import Path

from buildpipe import case_package
from buildpipe_fixtures import case_fixture


class CasePackageTests(unittest.TestCase):
    def test_package_manifest_and_verify(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            case, evidence = case_fixture(root)
            manifest = case_package.package(case, evidence, root / 'WS17-case.tar.gz',
                                            root / 'case.json', 'case-test')
            self.assertEqual(manifest['database_integrity'], 'ok')
            self.assertTrue(manifest['ingest_complete'])
            self.assertTrue(manifest['saved_keyword_index'])
            self.assertTrue(manifest['logical_evidence'])
            self.assertTrue(manifest['native_disk_included'])
            self.assertTrue(manifest['native_windows_records_included'])
            self.assertFalse(manifest['native_windows_memory_included'])
            self.assertEqual(case_package.verify(root / 'WS17-case.tar.gz', root / 'case.json')['version'], 'case-test')
            self.assertFalse((root / 'WS17-case.tar.gz.tmp').exists())

    def test_rejects_unclean_incomplete_corrupt_and_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            case, evidence = case_fixture(root / 'ok')
            (case / 'autopsy.db-wal').write_bytes(b'active')
            with self.assertRaisesRegex(ValueError, 'active or unclean'):
                case_package.inspect_case(case)
            case, evidence = case_fixture(root / 'incomplete', ingest=1)
            with self.assertRaisesRegex(ValueError, 'completed ingest'):
                case_package.inspect_case(case)
            case, evidence = case_fixture(root / 'corrupt')
            (case / 'autopsy.db').write_bytes(b'not a database')
            with self.assertRaisesRegex(ValueError, 'unreadable or corrupt'):
                case_package.inspect_case(case)
            case, evidence = case_fixture(root / 'good')
            case_package.package(case, evidence, root / 'archive.tar.gz', root / 'manifest.json')
            with self.assertRaisesRegex(ValueError, 'never overwritten'):
                case_package.package(case, evidence, root / 'archive.tar.gz', root / 'other.json')
            (evidence / 'controller').mkdir()
            with self.assertRaisesRegex(ValueError, 'released initial evidence'):
                case_package.package(case, evidence, root / 'second.tar.gz', root / 'second.json')


if __name__ == '__main__':
    unittest.main()
