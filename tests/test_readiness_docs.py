"""A01: readiness documents reconcile current artifacts and link to recorded checks."""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(relative):
    return (ROOT / relative).read_text(encoding='utf-8')


class ReadinessDocumentTests(unittest.TestCase):
    def test_versions_record_delivered_tools(self):
        versions = json.loads(read('deployment/expanded/versions.json'))
        self.assertEqual(versions['cutter'], '2.5.0')
        self.assertEqual(versions['autopsy'], '4.22.0')
        self.assertEqual(versions['sleuthkit'], '4.13.0')
        desktop = json.loads(read('assets/desktop-v1.json'))
        self.assertEqual(desktop['tools']['cutter']['version'], versions['cutter'])
        self.assertEqual(desktop['tools']['autopsy'], versions['autopsy'])

    def test_learning_objectives_links_current_manifests(self):
        text = read('docs/learning-objectives.md')
        for manifest in ('assets/native-windows-v1/manifest.json',
                         'assets/desktop-v1.json',
                         'assets/autopsy-case-v2.json'):
            self.assertIn(manifest, text)

    def test_native_acquisition_and_connection_claims_are_precise(self):
        text = read('docs/learning-objectives.md')
        self.assertIn('actual\nacquisition UTC', text)
        self.assertIn('not a validated memory connection', text)
        self.assertNotIn('exactly-once', text.lower())
        self.assertNotIn('native Windows EVTX and memory sources and\nready-to-open Autopsy cases are still required', text)

    def test_native_evidence_index_registers_the_archive_manifest(self):
        """versions.json must name the authoritative archive manifest, not just
        the prepared-record companion (#134).

        It previously registered only manifest.json, which covers the four
        prepared sidecars and carries none of the archive hash, byte count,
        per-file checksums or acquisition provenance, while
        assets/desktop-v1.json already pointed at archive.json. Nothing read
        the delivered_evidence block, so the two indexes could disagree
        unnoticed with CI green.
        """
        delivered = json.loads(read('deployment/expanded/versions.json'))['delivered_evidence']
        archive_path = delivered['native_windows_archive']
        records_path = delivered['native_windows_records']
        self.assertTrue((ROOT / archive_path).is_file(), archive_path)
        self.assertTrue((ROOT / records_path).is_file(), records_path)
        self.assertNotEqual(archive_path, records_path)

        archive = json.loads(read(archive_path))
        for field in ('artifact', 'bytes', 'sha256', 'files'):
            self.assertIn(field, archive)
        self.assertRegex(archive['sha256'], r'^[0-9a-f]{64}$')
        self.assertIsInstance(archive['bytes'], int)
        self.assertGreater(archive['bytes'], 0)
        self.assertTrue(archive['files'])
        for name, record in archive['files'].items():
            self.assertRegex(record['sha256'], r'^[0-9a-f]{64}$', name)
            self.assertIsInstance(record['bytes'], int, name)

        # The desktop index must name the same authoritative manifest.
        desktop = json.loads(read('assets/desktop-v1.json'))
        self.assertEqual(desktop['native_capture'], archive_path)

    def test_local_links_resolve(self):
        files = ['README.md', 'docs/learning-objectives.md', 'docs/expanded-validation.md',
                 'docs/expanded-deployment.md', 'docs/expanded-evidence.md']
        missing = []
        for name in files:
            base = (ROOT / name).parent
            for target in re.findall(r'\]\(([^)]+)\)', read(name)):
                if re.match(r'^(https?:|mailto:|#)', target):
                    continue
                relative = target.split('#', 1)[0]
                if not relative:
                    continue
                if not (base / relative).exists():
                    missing.append(name + ' -> ' + target)
        self.assertEqual(missing, [])


if __name__ == '__main__':
    unittest.main()
