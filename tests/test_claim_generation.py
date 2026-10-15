"""Regression tests for issue #189: State.claim must not default generation to 0.

The old ``generation=0`` default was correct only for a never-claimed
ticket. Any re-claim through the default failed with a misleading
"Ticket changed" Conflict and the ticket could never be claimed again
without reaching into SQLite for the live generation. ``generation`` is
now a required argument, ``State.ticket_state`` exposes the observed
generation, and the Conflict names the expected value.
"""
import tempfile
import unittest
from pathlib import Path

from ridge.state import State, Conflict


class ClaimGenerationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.state = State(Path(self.tmp.name) / 'state.sqlite', retry_delay=0)
        teams = [dict(id=str(i), iris=str(10 + i), ctfd=20 + i, name='Team ' + str(i))
                 for i in range(2)]
        ticket = dict(id='T01', title='T01', subject='general', requires=[], questions=[
            dict(id='T01-Q1', prompt='Question', answer='yes',
                 finding=dict(text='Finding', evidence=['ref'], limitation='Scope only'))])
        self.state.initialize(teams, [ticket])
        self.receipts = {}
        self.state.provision('controller')
        self.drain()
        self.state.mode('controller', 'running')

    def sink(self, kind, key, payload, context):
        self.receipts.setdefault(key, (kind, len(self.receipts) + 1))
        return self.receipts[key][1]

    def drain(self):
        while self.state.sync_once(self.sink):
            pass

    def test_claim_without_generation_is_a_type_error(self):
        # The trap is now impossible: omitting the argument fails loudly
        # instead of silently using 0.
        with self.assertRaises(TypeError):
            self.state.claim('0', 'T01')

    def test_ticket_state_rejects_unknown_ticket(self):
        with self.assertRaises(PermissionError):
            self.state.ticket_state('T99')

    def test_first_claim_with_observed_generation(self):
        before = self.state.ticket_state('T01')
        self.assertEqual((before['status'], before['owner'], before['generation']),
                         ('available', None, 0))
        self.assertIsNotNone(before['iris_id'])
        self.state.claim('0', 'T01', before['generation'])
        after = self.state.ticket_state('T01')
        self.assertEqual((after['status'], after['owner'], after['generation']),
                         ('active', '0', 1))

    def test_reclaim_with_current_generation_after_release(self):
        # The stranded-ticket scenario from the issue: claim, relinquish,
        # then claim again. The stale 0 (old default) must be refused with
        # a message that names the expected generation, and the freshly
        # observed generation must succeed.
        self.state.claim('0', 'T01', 0)
        self.state.release('0', 'T01', self.state.ticket_state('T01')['generation'])
        released = self.state.ticket_state('T01')
        self.assertEqual((released['status'], released['owner'], released['generation']),
                         ('available', None, 1))
        with self.assertRaises(Conflict) as stale:
            self.state.claim('1', 'T01', 0)
        self.assertIn('expected generation 1', str(stale.exception))
        self.state.claim('1', 'T01', released['generation'])
        self.assertEqual(self.state.ticket_state('T01'),
                         {**released, 'status': 'active', 'owner': '1', 'generation': 2})

    def test_stale_generation_is_rejected_and_changes_nothing(self):
        self.state.claim('0', 'T01', 0)
        self.state.release('0', 'T01', 1)
        observed = self.state.ticket_state('T01')  # available, generation 1
        for stale in (0, 2, '1'):
            with self.subTest(generation=stale):
                with self.assertRaises(Conflict):
                    self.state.claim('1', 'T01', stale)
                self.assertEqual(self.state.ticket_state('T01'), observed)
        self.state.claim('1', 'T01', observed['generation'])
        claimed = self.state.ticket_state('T01')
        with self.assertRaises(Conflict) as ctx:
            self.state.release('1', 'T01', observed['generation'])
        self.assertIn('expected generation 2', str(ctx.exception))
        self.assertEqual(self.state.ticket_state('T01'), claimed)
        self.state.release('1', 'T01', self.state.ticket_state('T01')['generation'])
        self.assertIsNone(self.state.ticket_state('T01')['owner'])


if __name__ == '__main__':
    unittest.main()
