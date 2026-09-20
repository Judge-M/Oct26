"""Tests for expanded.schedule (F04 event-day model) and walkthrough ordering."""
import json
import tempfile
import unittest
from pathlib import Path

from expanded.schedule import (DEFAULT_SEGMENTS, WINDOW_MIN, WINDOW_MAX, plan,
                               render, scaled_tickets, sensitivity)
from expanded.walkthrough import topological_order, WalkthroughError


TICKETS = [
    {'id': 'T01', 'subject': 'Wireshark', 'estimate_minutes': 65,
     'questions': [{'id': 'T01-Q1', 'answer': 'a'}]},
    {'id': 'T02', 'subject': 'Wazuh', 'estimate_minutes': 65,
     'questions': [{'id': 'T02-Q1', 'answer': 'b'}]},
    {'id': 'T03', 'subject': 'Wazuh', 'estimate_minutes': 65, 'requires': ['T02'],
     'questions': [{'id': 'T03-Q1', 'answer': 'c'}]},
    {'id': 'T04', 'subject': 'Wazuh', 'estimate_minutes': 65, 'requires': ['T03'],
     'questions': [{'id': 'T04-Q1', 'answer': 'd'}]},
]


class TopologicalOrderTests(unittest.TestCase):
    def test_respects_dependencies(self):
        order = [t['id'] for t in topological_order(list(reversed(TICKETS)))]
        self.assertLess(order.index('T02'), order.index('T03'))
        self.assertLess(order.index('T03'), order.index('T04'))

    def test_cycle_named(self):
        cyclic = [{'id': 'A', 'requires': ['B'], 'questions': []},
                  {'id': 'B', 'requires': ['A'], 'questions': []}]
        with self.assertRaises(WalkthroughError) as ctx:
            topological_order(cyclic)
        self.assertIn('dependency cycle', str(ctx.exception))


class ScaledTicketsTests(unittest.TestCase):
    def test_scales_and_floors(self):
        scaled = scaled_tickets(TICKETS, 1.5)
        self.assertEqual([t['estimate_minutes'] for t in scaled], [98, 98, 98, 98])

    def test_rejects_nonpositive(self):
        with self.assertRaises(ValueError):
            scaled_tickets(TICKETS, 0)


class PlanTests(unittest.TestCase):
    def test_accounts_segments_separately(self):
        result = plan(TICKETS, teams=2, multiplier=1.0)
        self.assertEqual(result['investigation_minutes'], 195)  # T01||T02->T03->T04
        self.assertEqual(result['facilitated_minutes'], 35)     # orientation + inject
        self.assertEqual(result['break_minutes'], 15)
        self.assertEqual(result['aar_minutes'], 30)
        self.assertEqual(result['total_minutes'],
                         result['investigation_minutes'] + 35 + 15 + 30)

    def test_fits_window_flags(self):
        result = plan(TICKETS, teams=2, multiplier=1.0)
        self.assertEqual(result['total_minutes'], 275)
        self.assertTrue(result['fits_window'])
        stretched = plan(TICKETS, teams=2, multiplier=1.5)
        self.assertEqual(stretched['investigation_minutes'], 294)
        self.assertFalse(stretched['fits_window'])

    def test_monotonic_in_multiplier(self):
        plans = sensitivity(TICKETS, teams=2, multipliers=(1.0, 1.5, 2.0))
        makespans = [p['investigation_minutes'] for p in plans]
        self.assertEqual(makespans, sorted(makespans))

    def test_deterministic(self):
        self.assertEqual(plan(TICKETS, 2), plan(TICKETS, 2))

    def test_rejects_zero_teams(self):
        with self.assertRaises(ValueError):
            plan(TICKETS, teams=0)

    def test_render_mentions_separate_accounting(self):
        text = render(sensitivity(TICKETS, 2, (1.0, 1.5)))
        self.assertIn('accounted separately', text)
        self.assertIn('Pace sensitivity', text)


if __name__ == '__main__':
    unittest.main()
