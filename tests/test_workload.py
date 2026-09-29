"""A02: ten-team workload inventory, scheduling model and rehearsal worksheet."""
import json
import unittest
from pathlib import Path

from expanded.author import build
from expanded.workload import (critical_path, inventory, render_inventory,
                               render_worksheet, schedule, summary)

ROOT = Path(__file__).resolve().parents[1]


class WorkloadTests(unittest.TestCase):
    def setUp(self):
        self.tickets = build(json.loads((ROOT / 'expanded/config.json').read_text(encoding='utf-8')))

    def test_inventory_counts_match_authored_content(self):
        data = summary(self.tickets, teams=10)
        self.assertEqual(data['tickets'], 20)
        self.assertEqual(data['questions'], 80)
        self.assertEqual(data['estimated_team_minutes'], 1300)
        self.assertEqual(data['average_team_minutes'], 130.0)
        self.assertEqual(len(inventory(self.tickets)), 20)

    def test_critical_path_and_makespan_separate_estimate_from_quotient(self):
        data = summary(self.tickets, teams=10)
        self.assertEqual(data['critical_path_minutes'], 195)
        self.assertEqual(data['makespan_minutes'], 195)
        self.assertGreater(data['makespan_minutes'], data['average_team_minutes'])

    def test_schedule_respects_dependencies_and_single_ownership(self):
        result = schedule(self.tickets, teams=10)
        by_id = {ticket['id']: ticket for ticket in self.tickets}
        completed = set()
        busy = {}
        for event in sorted(result['timeline'], key=lambda e: e['minute']):
            ticket = by_id[event['ticket']]
            self.assertTrue(set(ticket.get('requires', [])) <= completed,
                            event['ticket'] + ' ran before its prerequisites')
            self.assertNotIn((event['team'], event['minute']), busy)
            busy[(event['team'], event['minute'])] = event['ticket']
            completed.add(event['ticket'])
        self.assertEqual(sorted(e['ticket'] for e in result['timeline']),
                         sorted(by_id))

    def test_flags_free_walkthroughs_and_superficial_questions(self):
        data = summary(self.tickets, teams=10)
        self.assertEqual(data['free_walkthroughs'], 80)
        self.assertTrue(data['repeated_answers'])
        self.assertTrue(data['yes_no_questions'])

    def test_team_count_and_target_are_configurable(self):
        two = summary(self.tickets, teams=2, target_minutes=300)
        self.assertEqual(two['teams'], 2)
        self.assertEqual(two['target_minutes'], 300)
        self.assertGreaterEqual(two['makespan_minutes'], two['critical_path_minutes'])

    def test_rendered_documents_are_deterministic_and_record_required_columns(self):
        self.assertEqual(render_inventory(self.tickets), render_inventory(self.tickets))
        worksheet = render_worksheet(self.tickets)
        for column in ('Active minutes', 'Idle minutes', 'Help used', 'Tool failures'):
            self.assertIn(column, worksheet)
        self.assertIn('Estimated team-minutes: 1300', worksheet)

    def test_committed_inventory_is_not_stale(self):
        committed = (ROOT / 'docs/workload.md').read_text(encoding='utf-8')
        self.assertEqual(committed, render_inventory(self.tickets))


if __name__ == '__main__':
    unittest.main()
