import tempfile
import unittest
from pathlib import Path

from ridge.fencing import Fence, FenceError
from ridge.switching import SWITCH_STEPS, Switch, SwitchError, plan_directions


class FencingTests(unittest.TestCase):
    def test_generation_and_mutual_exclusion(self):
        with tempfile.TemporaryDirectory() as folder:
            fence = Fence(Path(folder) / 'authority.json')
            authority = fence.activate('A')
            self.assertEqual(authority.generation, 1)
            self.assertTrue(fence.accepts('A', 1))
            self.assertFalse(fence.accepts('B', 1))
            fence.activate('B', source_confirmed=True)
            self.assertFalse(fence.accepts('A', 2))
            self.assertTrue(fence.accepts('B', 2))
            self.assertFalse(fence.accepts('B', 1))

    def test_unreachable_source_requires_external_fence(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'authority.json'
            blocked = Fence(path)
            blocked.activate('A')
            with self.assertRaisesRegex(FenceError, 'Fence the source'):
                blocked.activate('B')
            self.assertTrue(blocked.accepts('A', 1))
            revoking = Fence(path, revoke=lambda site: 'network-revoked:' + site)
            authority = revoking.activate('B')
            self.assertEqual(authority.generation, 2)
            self.assertIn('A', authority.fenced)
            self.assertEqual(authority.receipts['A'], 'network-revoked:A')

    def test_crash_persists_authority(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'authority.json'
            Fence(path).activate('A')
            restarted = Fence(path)
            self.assertTrue(restarted.accepts('A', 1))
            self.assertTrue(str(restarted.authority_location()).endswith('authority.json'))


class SwitchingTests(unittest.TestCase):
    def steps(self, fail=None):
        calls = []

        def make(name):
            def step():
                calls.append(name)
                if fail == name:
                    raise SwitchError('failed: ' + name)
            return step

        record = {name: make(name) for name in SWITCH_STEPS}
        record['last_backup'] = lambda: 'backup-7'
        record['recovery_point'] = lambda: '2026-09-16T10:00:00Z'
        record['calls'] = calls
        return record

    def test_successful_switch_orders_steps(self):
        steps = self.steps()
        result = Switch(steps).execute('local->aws')
        self.assertEqual(result['completed'], list(SWITCH_STEPS))
        self.assertEqual(steps['calls'], list(SWITCH_STEPS))
        self.assertEqual(result['recovery_point'], '2026-09-16T10:00:00Z')
        self.assertFalse(result['lost_work'])

    def test_failure_rolls_back_completed_steps(self):
        steps = self.steps(fail='restore')
        rolled = []
        for name in SWITCH_STEPS:
            steps['rollback_' + name] = (lambda n: (lambda: rolled.append(n)))(name)
        with self.assertRaisesRegex(SwitchError, 'restore'):
            Switch(steps).execute('local->aws')
        self.assertEqual(rolled, ['fence_source', 'backup', 'pause_drain', 'verify_destination'])

    def test_source_unreachable_uses_last_backup_and_reports_lost_work(self):
        steps = self.steps()
        skipped = []
        steps['pause_drain'] = lambda: skipped.append('pause_drain')
        steps['backup'] = lambda: skipped.append('backup')
        result = Switch(steps).execute('aws->local', source_unreachable=True)
        self.assertEqual(skipped, [])
        self.assertEqual(result['backup_source'], 'last-completed')
        self.assertTrue(result['lost_work'])
        self.assertNotIn('pause_drain', result['completed'])

    def test_missing_backup_fails_safely_and_directions(self):
        steps = self.steps()
        steps.pop('last_backup')
        with self.assertRaisesRegex(SwitchError, 'no completed backup'):
            Switch(steps).execute('aws->local', source_unreachable=True)
        with self.assertRaisesRegex(ValueError, 'must differ'):
            plan_directions('local', 'local')
        self.assertEqual(plan_directions('local', 'aws')['direction'], 'local->aws')
        with self.assertRaisesRegex(ValueError, 'missing steps'):
            Switch({'verify_destination': lambda: None})


if __name__ == '__main__':
    unittest.main()
