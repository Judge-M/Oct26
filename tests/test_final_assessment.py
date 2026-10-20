import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ridge.schema import VERSION
from ridge.state import State


class FinalAssessmentTests(unittest.TestCase):
    def build_completed_capstone(self, root):
        state=State(Path(root)/'state.sqlite',retry_delay=0)
        state.initialize([dict(id='team-01',iris='10',ctfd=20,name='Team 01')],[dict(
            id='T20',title='Capstone',subject='assessment',questions=[dict(
                id='T20-Q1',prompt='Final question',answer='yes',
                hints=['one','two','yes'],
                finding=dict(text='Capstone finding',evidence=['req-72'],
                             limitation='Intent is not established.'))])])
        state.provision('controller')
        state.mode('controller','running')
        # The focused state test does not run the external IRIS worker; model
        # its acknowledged task creation before exercising participant claim.
        with state.transaction() as con:
            con.execute("UPDATE tickets SET iris_id=100 WHERE id='T20'")
        state.claim('team-01','T20',0)
        result=state.answer('team-01','T20-Q1','yes')
        self.assertTrue(result['assessment_published'])
        return state

    def test_capstone_queues_one_native_iris_assessment_and_announcement(self):
        with tempfile.TemporaryDirectory() as root:
            state=self.build_completed_capstone(root)
            with state.transaction(write=False) as con:
                rows=con.execute("SELECT id,kind,payload FROM outbox WHERE kind='assessment'").fetchall()
                audit=con.execute("SELECT detail FROM audit WHERE action='final_assessment'").fetchall()
            self.assertEqual(len(rows),1)
            payload=json.loads(rows[0]['payload'])
            self.assertEqual(payload['ticket'],'T20')
            self.assertIn('LIMITED DISCLOSURE CONFIRMED',payload['text'])
            self.assertEqual(len(audit),1)
            announcements=state.snapshot('team-01')['announcements']
            self.assertEqual(announcements[-1]['kind'],'final_assessment')
            self.assertIn('rotate CEDAR',announcements[-1]['text'])

    def test_migration_backfills_a_completed_live_run_idempotently(self):
        with tempfile.TemporaryDirectory() as root:
            state=self.build_completed_capstone(root)
            with state.transaction() as con:
                assessment=con.execute("SELECT id FROM outbox WHERE kind='assessment'").fetchone()[0]
                con.execute('DELETE FROM delivery_dependencies WHERE event=? OR prerequisite=?',
                            (assessment,assessment))
                con.execute('DELETE FROM outbox WHERE id=?',(assessment,))
                con.execute("DELETE FROM audit WHERE action='final_assessment'")
                con.execute('PRAGMA user_version=4')
            state.migrate()
            state.migrate()
            with state.transaction(write=False) as con:
                self.assertEqual(con.execute('PRAGMA user_version').fetchone()[0],VERSION)
                self.assertEqual(con.execute("SELECT COUNT(*) FROM outbox WHERE kind='assessment'").fetchone()[0],1)
                self.assertEqual(con.execute("SELECT COUNT(*) FROM audit WHERE action='final_assessment'").fetchone()[0],1)

    def test_activity_clock_freezes_when_the_final_assessment_publishes(self):
        with tempfile.TemporaryDirectory() as root:
            state=self.build_completed_capstone(root)
            baseline=state.snapshot('team-01')
            with patch('ridge.state.now',return_value='2099-01-01T00:00:00+00:00'):
                later=state.snapshot('team-01')
            self.assertTrue(later['activity_complete'])
            self.assertEqual(later['elapsed_seconds'],baseline['elapsed_seconds'])


if __name__=='__main__':
    unittest.main()
