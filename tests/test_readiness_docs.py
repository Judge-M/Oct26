"""A01: readiness documents reconcile current artifacts and link to recorded checks."""
import json
import re
import unittest
from pathlib import Path

from expanded.author import build as authored_tickets
from expanded.workload import summary as workload_summary

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

    def test_learning_objectives_match_current_ticket_semantics(self):
        text = read('docs/learning-objectives.md')
        objectives = text.split('## Objectives', 1)[1].split('## Ticket-to-role crosswalk', 1)[0]
        mechanisms = '\n'.join(re.findall(
            r'\*\*Mechanism\.\*\*(.*?)(?=\n\n\*\*Achievement evidence\.\*\*)',
            objectives,
            flags=re.DOTALL,
        ))
        self.assertEqual(
            set(re.findall(r'`(T\d{2})`', mechanisms)),
            {f'T{number:02}' for number in range(1, 21)},
        )

        self.assertIn('`silent-ridge-timed`', text)
        self.assertIn('`silent-ridge-timeless`', text)
        self.assertRegex(
            text,
            r'(?s)`T12` reports.*?`silent-ridge-timeless`.*?does not apply the correction',
        )
        self.assertNotIn('`T11` and `T20` questions', text)

        tickets = {ticket['id']: ticket for ticket in authored_tickets()}
        for ticket_id in ('T13', 'T14', 'T15', 'T16'):
            self.assertIn(tickets[ticket_id]['title'], text)
        self.assertIn('Case and outer whitespace are ignored.', text)
        self.assertIn('`/evidence` and `/originals` stay mounted read-only', text)
        self.assertIn('`original_path`', text)
        self.assertIn('`original_sha256`', text)

        workload = workload_summary(list(tickets.values()), teams=10, target_minutes=270)
        self.assertIn(f"{workload['makespan_minutes']}-minute simulated makespan", text)
        self.assertIn(f"{workload['target_minutes']}-minute planning midpoint", text)

    def test_nice_mapping_matches_checked_official_receipt(self):
        text = read('docs/learning-objectives.md')
        objective_tables = text.split('## Objectives', 1)[1].split('## Ticket-to-role crosswalk', 1)[0]
        actual = set()
        for line in objective_tables.splitlines():
            if not line.startswith('|'):
                continue
            roles = re.findall(r'`([A-Z]{2}-WRL-\d{3})`', line)
            tasks = re.findall(r'\b(T\d{4})\b', line)
            for role in roles:
                actual.update((role, task) for task in tasks)

        receipt = json.loads(read('docs/nice-components-2.2.0-mapping.json'))
        self.assertEqual(receipt['framework_publication'].split(',', 1)[0], 'NIST SP 800-181 Rev. 1')
        self.assertEqual(receipt['components_version'], '2.2.0')
        self.assertEqual(
            receipt['source_url'],
            'https://csrc.nist.gov/csrc/media/Projects/cprt/documents/nice/v2-2-0_nf_components.json',
        )
        expected = {
            (role, task)
            for role, tasks in receipt['validated_role_task_pairs'].items()
            for task in tasks
        }
        self.assertEqual(actual, expected)
        self.assertNotIn(('PD-WRL-001', 'T1428'), actual)

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
