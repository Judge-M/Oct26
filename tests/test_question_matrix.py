"""Deterministic acceptance-matrix tests for all 80 questions (C04).

Real tool workflows require the desktop release (LIVE ACCEPTANCE BLOCKED). These
tests verify the matrix is complete and that the clock/claim guards hold.
"""
import unittest
from pathlib import Path

from expanded.native import records
from ridge.question_matrix import (
    EXPECTED_QUESTIONS, MatrixError, build, clock_guards, guide_inventory, render_markdown, validate,
)

ROOT = Path(__file__).resolve().parents[1]


class QuestionMatrixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = build()

    def test_every_question_has_a_complete_route(self):
        self.assertEqual(len(self.rows), EXPECTED_QUESTIONS)
        self.assertEqual(len({row['question_id'] for row in self.rows}), EXPECTED_QUESTIONS)
        for row in self.rows:
            self.assertTrue(row['evidence_path'].startswith('/evidence/'))
            self.assertTrue(row['selection'])
            self.assertTrue(row['expected_value'])
            self.assertTrue(row['source_record'])
            self.assertTrue(row['limitation'])
            self.assertTrue(row['route'])

    def test_all_distinct_tool_workflows_are_covered(self):
        tools = {row['tool'] for row in self.rows}
        self.assertEqual(tools, {'Wireshark', 'Autopsy', 'Wazuh', 'Cutter', 'Linux file manager'})

    def test_t13_t14_acquisition_time_is_not_shifted(self):
        native = records()
        guards = clock_guards(self.rows)
        self.assertEqual(guards['t13_acquisition_utc'], native['windows-process']['utc'][11:19])
        self.assertEqual(guards['t14_acquisition_utc'], native['windows-task']['utc'][11:19])
        t14 = [row for row in self.rows if row['ticket'] == 'T14']
        self.assertIn('no', {row['expected_value'] for row in t14})

    def test_t16_never_claims_memory_connection_validation(self):
        guards = clock_guards(self.rows)
        self.assertFalse(guards['memory_connection_validated'])
        self.assertTrue(guards['live_connection_snapshot_validated'])
        t16 = [row for row in self.rows if row['ticket'] == 'T16']
        self.assertTrue(any('not a validated memory connection' in row['finding_text'] for row in t16))
        for row in t16:
            self.assertNotIn('validated memory connection', row['finding_text'].replace(
                'not a validated memory connection', ''))

    def test_markdown_contains_every_question(self):
        markdown = render_markdown(self.rows)
        self.assertEqual(markdown.count('\n| T'), EXPECTED_QUESTIONS)
        self.assertIn('| Question | Ticket | Tool |', markdown)

    def test_guide_inventory_records_hashes(self):
        inventory = guide_inventory(self.rows, ROOT / 'expanded/guides.md')
        self.assertEqual(inventory['questions'], EXPECTED_QUESTIONS)
        self.assertEqual(len(inventory['guides_sha256']), 64)
        self.assertEqual(len(inventory['matrix_sha256']), 64)

    def test_validate_rejects_incomplete_or_missing_evidence(self):
        with self.assertRaisesRegex(MatrixError, 'expected 80'):
            validate(self.rows[:-1])
        broken = [dict(row) for row in self.rows]
        broken[0]['evidence_path'] = 'network/sensor.pcap'
        with self.assertRaisesRegex(MatrixError, 'explicit /evidence'):
            validate(broken)
        broken = [dict(row) for row in self.rows]
        broken[0]['selection'] = ''
        with self.assertRaisesRegex(MatrixError, 'selection is empty'):
            validate(broken)


if __name__ == '__main__':
    unittest.main()
