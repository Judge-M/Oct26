import concurrent.futures
import json
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from ridge.state import State, Conflict


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.state=State(Path(self.tmp.name)/'state.sqlite',retry_delay=0)
        teams=[dict(id=str(i),iris=str(i+10),ctfd=i+20,name='Team '+str(i)) for i in range(3)]
        def ticket(id,requires=None):
            return dict(id=id,title=id,subject='general',requires=requires or [],questions=[
                dict(id=id+str(i),prompt='Question',answer='answer',finding=dict(text='Finding',evidence=['ref'],limitation='Scope only')) for i in range(2)])
        self.state.initialize(teams,[ticket('A'),ticket('B'),ticket('C',['A'])])
        self.deliveries={}
        self.state.provision('controller')
        self.drain()
        self.state.mode('controller','running')

    def tearDown(self):
        self.tmp.cleanup()

    def sink(self,kind,key,payload,con):
        if key not in self.deliveries:
            self.deliveries[key]=(kind,payload,len(self.deliveries)+1)
        return self.deliveries[key][2]

    def drain(self):
        while self.state.sync_once(self.sink):
            pass

    def test_simultaneous_claim_one_winner(self):
        def claim(team):
            try:
                self.state.claim(team,'A');return True
            except Conflict:
                return False
        with concurrent.futures.ThreadPoolExecutor(3) as pool:
            self.assertEqual(sum(pool.map(claim,['0','1','2'])),1)
        owner=self.state.snapshot()['tickets'][0]['owner']
        with self.assertRaises(Conflict):
            self.state.claim(owner,'B')

    def test_same_team_simultaneous_different_tickets(self):
        def claim(ticket):
            try:
                self.state.claim('0',ticket);return True
            except Conflict:
                return False
        with concurrent.futures.ThreadPoolExecutor(2) as pool:
            self.assertEqual(sum(pool.map(claim,['A','B'])),1)

    def test_transfer_global_close_history_followup(self):
        self.state.claim('0','A')
        self.assertTrue(self.state.answer('0','A0',' ANSWER ')['correct'])
        self.state.release('0','A',1)
        self.state.claim('1','A',1)
        questions=self.state.questions('1')
        self.assertEqual(questions[0]['solved_by'],'0')
        self.assertFalse(questions[0]['answerable'])
        self.assertTrue(self.state.answer('1','A1','answer')['closed'])
        self.assertEqual(len(self.state.questions('2')),2)
        self.assertTrue(all(not q['answerable'] for q in self.state.questions('2')))
        self.assertEqual({r['id']:r['points'] for r in self.state.snapshot()['scores']},{'0':1,'1':1,'2':0})
        self.drain();self.state.claim('1','C')
        self.assertEqual(sum(v[0]=='ticket' for v in self.deliveries.values()),3)
        self.assertEqual(sum(v[0]=='finding' for v in self.deliveries.values()),2)
        self.assertEqual(sum(v[0]=='close' for v in self.deliveries.values()),1)

    def test_unrelated_direct_read_submission_and_wrong_owner(self):
        self.state.claim('0','A')
        for team,q in [('0','B0'),('0','C0'),('1','A0'),('0','missing')]:
            with self.subTest(team=team,q=q):
                with self.assertRaises(PermissionError):self.state.questions(team,q)
                with self.assertRaises(PermissionError):self.state.answer(team,q,'answer')
        with self.assertRaises(PermissionError):self.state.release('1','A',1)
        self.assertNotIn('digest',json.dumps(self.state.questions('0')))
        self.assertNotIn('Finding',json.dumps(self.state.questions('0')))
        self.assertEqual(self.state.answer('0','A0','wrong'),{'correct':False})

    def test_concurrent_duplicate_submissions(self):
        self.state.claim('0','A')
        def answer(_):
            try:return self.state.answer('0','A0','answer')['correct']
            except Conflict:return False
        with concurrent.futures.ThreadPoolExecutor(8) as pool:
            self.assertEqual(sum(pool.map(answer,range(8))),1)
        self.drain()
        self.assertEqual(sum(v[0]=='point' for v in self.deliveries.values()),1)

    def test_ambiguous_remote_success_retry_restart(self):
        self.state.claim('0','A');self.drain()
        self.state.answer('0','A0','answer')
        def lost_response(kind,key,payload,con):
            self.sink(kind,key,payload,con)
            raise TimeoutError('response lost after commit')
        self.assertFalse(self.state.sync_once(lost_response))
        self.assertGreater(self.state.snapshot()['pending'],0)
        self.state=State(self.state.path,retry_delay=0)
        self.drain()
        self.assertEqual(sum(v[0]=='point' for v in self.deliveries.values()),1)
        self.assertEqual(sum(v[0]=='finding' for v in self.deliveries.values()),1)
        self.assertEqual(self.state.snapshot()['pending'],0)

    def test_pause_recovery_export_and_no_destructive_reinit(self):
        self.state.claim('0','A');self.state.answer('0','A0','answer')
        self.state.mode('controller','paused')
        with self.assertRaises(Conflict):self.state.answer('0','A1','answer')
        self.state.release(None,'A',1,recovery_actor='controller',reason='Absent team')
        path=self.state.export(Path(self.tmp.name)/'export.json')
        data=json.loads(path.read_text())
        self.assertEqual(len(data['answers']),1)
        self.assertTrue(any(r['action']=='recover' for r in data['audit']))
        with self.assertRaises(ValueError):self.state.export(path)
        self.assertEqual(self.state.identity('iris','10'),'0')
        self.assertEqual(self.state.identity('ctfd',20),'0')
        with self.assertRaises(PermissionError):self.state.identity('iris','unknown')

    def test_no_claim_before_iris_creation(self):
        self.state.claim('0','A')
        self.state.answer('0','A0','answer');self.state.answer('0','A1','answer')
        with self.assertRaises(Conflict) as ctx:
            self.state.claim('0','C')
        # The unlocked-but-undelivered window is transient; the message must
        # tell API callers to retry rather than implying the ticket is gone.
        self.assertIn('retry shortly', str(ctx.exception))
        self.drain();self.state.claim('0','C')

    def test_clock_advances_without_events_and_freezes_when_paused(self):
        self.state.mode('controller','paused')
        with self.state.transaction() as con:
            con.execute("DELETE FROM audit WHERE action IN ('running','paused')")
        with patch('ridge.state.now',return_value='2026-10-15T10:00:00+00:00'):
            self.state.mode('controller','running')
        with patch('ridge.state.now',return_value='2026-10-15T10:00:30+00:00'):
            self.assertEqual(self.state.snapshot()['elapsed_seconds'],30)
            self.state.mode('controller','paused')
        with patch('ridge.state.now',return_value='2026-10-15T10:05:00+00:00'):
            self.assertEqual(self.state.snapshot()['elapsed_seconds'],30)
            self.state.announce('controller','Revised end 14:40 local')
            self.assertEqual(self.state.snapshot()['announcements'][0]['text'],'Revised end 14:40 local')


class RegressionTests(unittest.TestCase):
    def test_duplicate_sql_columns_rejected(self):
        from app.analysis_tools import query_database
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'browser.sqlite'
            con=sqlite3.connect(path)
            con.executescript('CREATE TABLE downloads(id INTEGER); INSERT INTO downloads VALUES(1);')
            con.close()
            with self.assertRaisesRegex(ValueError,'Duplicate column'):
                query_database(path,'SELECT id, id + 100 AS id FROM downloads')


if __name__=='__main__':unittest.main()
