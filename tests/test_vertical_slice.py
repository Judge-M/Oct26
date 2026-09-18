"""Orchestration tests for the two-team vertical slice harness (B05).

LIVE ACCEPTANCE BLOCKED: real IRIS/CTFd/Wazuh services are unavailable on this
host. These tests verify the harness guardrails and phase ordering only; they do
not accept the slice and no mock sink is used as acceptance evidence.
"""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ridge.state import State, Conflict
from ridge.vertical_slice import REQUIRED_ENV, SliceError, drain, main, run, verify_no_remote_tasks

ENV = {name: 'x' for name in REQUIRED_ENV}


class FakeClient:
    def __init__(self, tasks=0):
        self.tasks = tasks

    def effects(self):
        self.reads = getattr(self, "reads", 0) + 1
        return {"findings": int(self.reads > 1), "points": int(self.reads > 1)}

    def count_tasks(self):
        return self.tasks


def build_state(root):
    state = State(root / 'state.sqlite', retry_delay=0)
    tickets = [
        dict(id='T01', title='T01', subject='x', requires=[], questions=[
            dict(id='T01-Q1', answer='yes', finding=dict(text='t', evidence=['ref'], limitation='scope')),
            dict(id='T01-Q2', answer='two', finding=dict(text='t', evidence=['ref'], limitation='scope'))]),
        dict(id='T02', title='T02', subject='x', requires=[], questions=[
            dict(id='T02-Q1', answer='yes', finding=dict(text='t', evidence=['ref'], limitation='scope'))]),
    ]
    state.initialize([dict(id='a', iris='1', ctfd=1, name='A'),
                      dict(id='b', iris='2', ctfd=2, name='B')], tickets)
    return state


class VerticalSliceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.state = build_state(self.root)
        self.config = {'teams': [{'id': 'a'}, {'id': 'b'}]}
        self.receipts = {}

    def tearDown(self):
        self.tmp.cleanup()

    def sink(self, kind, key, payload, context):
        self.receipts.setdefault(key, len(self.receipts) + 1)
        return self.receipts[key]

    def test_environment_and_remote_guardrails_fail_closed(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(SliceError, 'environment'):
                run(self.state, self.config, FakeClient(), self.sink, 'op', 'T01', 'T01-Q1', 'yes')
        with patch.dict(os.environ, ENV):
            with self.assertRaisesRegex(SliceError, 'remote tasks already exist'):
                verify_no_remote_tasks(FakeClient(tasks=3))
        self.assertEqual(self.receipts, {})

    def test_paused_setup_allows_delivery_but_rejects_participants(self):
        with patch.dict(os.environ, ENV):
            report = run(self.state, self.config, FakeClient(), self.sink, 'op',
                         'T01', 'T01-Q1', 'yes', start=False, preflight=lambda *a: None)
        self.assertIn('paused', report.phases)
        self.assertGreaterEqual(report.receipts['initial_deliveries'], 2)
        with self.assertRaises(Conflict):
            self.state.claim('a', 'T01')

    def test_start_slice_runs_phases_in_order(self):
        with patch.dict(os.environ, ENV):
            report = run(self.state, self.config, FakeClient(), self.sink, 'op',
                         'T01', 'T01-Q1', 'yes', start=True, preflight=lambda *a: None)
        phases = report.phases
        for earlier, later in (('preflight', 'provision'), ('provision', 'start'),
                               ('start', 'claim'), ('claim', 'answer'),
                               ('answer', 'finding'), ('finding', 'point'),
                               ('point', 'relinquish'), ('relinquish', 'takeover')):
            self.assertLess(phases.index(earlier), phases.index(later), (earlier, later))
        self.assertEqual(self.state.snapshot()['tickets'][0]['owner'], 'b')

    def test_missing_native_effects_fail_acceptance(self):
        client = FakeClient()
        client.effects = lambda: {'findings': 0, 'points': 0}
        with patch.dict(os.environ, ENV):
            with self.assertRaisesRegex(SliceError, 'native effects'):
                run(self.state, self.config, client, self.sink, 'op',
                    'T01', 'T01-Q1', 'yes', start=True, preflight=lambda *a: None)


if __name__ == '__main__':
    unittest.main()
