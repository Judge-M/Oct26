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
                dict(id=id+str(i),prompt='Question',answer='answer',
                     hints=['Check the source.','Narrow the field.','The answer is answer.'],
                     finding=dict(text='Finding',evidence=['ref'],limitation='Scope only')) for i in range(2)])
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

    def test_each_team_can_claim_the_same_ticket_independently(self):
        def claim(team):
            try:
                self.state.claim(team,'A',0);return True
            except Conflict:
                return False
        with concurrent.futures.ThreadPoolExecutor(3) as pool:
            self.assertEqual(sum(pool.map(claim,['0','1','2'])),3)
        for team in ('0','1','2'):
            self.assertEqual(self.state.ticket_state('A',team)['owner'],team)

    def test_same_team_simultaneous_different_tickets(self):
        def claim(ticket):
            try:
                self.state.claim('0',ticket,0);return True
            except Conflict:
                return False
        with concurrent.futures.ThreadPoolExecutor(2) as pool:
            self.assertEqual(sum(pool.map(claim,['A','B'])),2)

    def test_fourth_parallel_lane_is_rejected(self):
        self.state.claim('0','A',0)
        self.state.claim('0','B',0)
        with self.state.transaction() as con:
            con.execute("UPDATE team_tickets SET status='available' WHERE team='0' AND ticket='C'")
            con.execute("INSERT INTO tickets(id,title,subject,owner,status,iris_id,requires,release_files,generation) VALUES ('D','D','general',NULL,'available',99,'[]','[]',0)")
            con.execute("INSERT INTO team_tickets(team,ticket,status,generation) VALUES ('0','D','available',0)")
            con.execute("INSERT INTO tickets(id,title,subject,owner,status,iris_id,requires,release_files,generation) VALUES ('E','E','general',NULL,'available',100,'[]','[]',0)")
            con.execute("INSERT INTO team_tickets(team,ticket,status,generation) VALUES ('0','E','available',0)")
        self.state.claim('0','D',0)
        with self.assertRaisesRegex(Conflict,'three active work lanes'):
            self.state.claim('0','E',0)

    def test_completion_and_followups_are_independent_per_team(self):
        self.state.claim('0','A',0)
        self.assertTrue(self.state.answer('0','A0',' ANSWER ')['correct'])
        self.assertTrue(self.state.answer('0','A1','answer')['closed'])
        self.assertEqual(self.state.ticket_state('C','0')['status'],'available')
        self.assertEqual(self.state.ticket_state('C','1')['status'],'locked')
        self.state.claim('1','A',0)
        questions=self.state.questions('1')
        self.assertTrue(all(q['solved_by'] is None and q['answerable'] for q in questions))
        self.assertTrue(self.state.answer('1','A0','answer')['correct'])
        self.assertTrue(self.state.answer('1','A1','answer')['closed'])
        self.assertEqual({q['ticket'] for q in self.state.questions('2')},{'A','B'})
        self.assertTrue(all(q['answerable'] for q in self.state.questions('2')))
        self.assertEqual({r['id']:r['points'] for r in self.state.snapshot()['scores']},{'0':8,'1':8,'2':0})
        self.drain();self.state.claim('1','C',0)
        self.assertEqual(sum(v[0]=='ticket' for v in self.deliveries.values()),3)
        self.assertEqual(sum(v[0]=='finding' for v in self.deliveries.values()),4)

    def test_released_questions_are_shared_but_locked_questions_are_hidden(self):
        self.state.claim('0','A',0)
        self.assertEqual(self.state.questions('0','B0')[0]['ticket'],'B')
        self.assertEqual(self.state.questions('1','A0')[0]['ticket'],'A')
        for team,q in [('0','C0'),('0','missing')]:
            with self.subTest(team=team,q=q):
                with self.assertRaises(PermissionError):self.state.questions(team,q)
                with self.assertRaises(PermissionError):self.state.answer(team,q,'answer')
        with self.assertRaises(PermissionError):self.state.release('1','A',1)
        self.assertNotIn('digest',json.dumps(self.state.questions('0')))
        self.assertNotIn('Finding',json.dumps(self.state.questions('0')))
        self.assertEqual(self.state.answer('0','A0','wrong'),{'correct':False})

    def test_concurrent_duplicate_submissions(self):
        self.state.claim('0','A',0)
        def answer(_):
            try:return self.state.answer('0','A0','answer')['correct']
            except Conflict:return False
        with concurrent.futures.ThreadPoolExecutor(8) as pool:
            self.assertEqual(sum(pool.map(answer,range(8))),1)
        self.drain()
        self.assertEqual(sum(v[0]=='point' for v in self.deliveries.values()),1)

    def test_explicit_walkthrough_costs_exactly_seventy_five_percent(self):
        self.state.claim('0','A',0)
        before=self.state.questions('0','A0')[0]
        self.assertEqual(before['hints'],['Check the source.','Narrow the field.'])
        self.assertTrue(before['paid_hint_available'])
        self.assertEqual(before['available_points'],4)

        unlocked=self.state.unlock_hint('0','A0')
        self.assertEqual(unlocked,{'unlocked':True,'cost_percent':75,'available_points':1})
        after=self.state.questions('0','A0')[0]
        self.assertEqual(after['hints'][-1],'The answer is answer.')
        self.assertTrue(after['hint_unlocked'])
        self.assertEqual(after['available_points'],1)
        self.assertEqual(self.state.answer('0','A0','answer')['value'],1)

        self.state.claim('1','B',0)
        self.assertEqual(self.state.answer('1','B0','answer')['value'],4)
        scores={row['id']:row['points'] for row in self.state.snapshot()['scores']}
        self.assertEqual(scores['0'],1)
        self.assertEqual(scores['1'],4)
        with self.assertRaises(PermissionError):
            self.state.unlock_hint('2','C1')

    def test_ambiguous_remote_success_retry_restart(self):
        self.state.claim('0','A',0);self.drain()
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
        self.state.claim('0','A',0);self.state.answer('0','A0','answer')
        self.state.mode('controller','paused')
        with self.assertRaises(Conflict):self.state.answer('0','A1','answer')
        self.state.release('0','A',1,recovery_actor='controller',reason='Absent team')
        path=self.state.export(Path(self.tmp.name)/'export.json')
        data=json.loads(path.read_text())
        self.assertEqual(len(data['answers']),1)
        self.assertTrue(any(r['action']=='recover' for r in data['audit']))
        with self.assertRaises(ValueError):self.state.export(path)
        self.assertEqual(self.state.identity('iris','10'),'0')
        self.assertEqual(self.state.identity('ctfd',20),'0')
        with self.assertRaises(PermissionError):self.state.identity('iris','unknown')

    def test_no_claim_before_iris_creation(self):
        self.state.claim('0','A',0)
        self.state.answer('0','A0','answer');self.state.answer('0','A1','answer')
        with self.assertRaises(Conflict) as ctx:
            self.state.claim('0','C',0)
        # The unlocked-but-undelivered window is transient; the message must
        # tell API callers to retry rather than implying the ticket is gone.
        self.assertIn('retry shortly', str(ctx.exception))
        self.drain();self.state.claim('0','C',0)

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

    def test_dynamic_team_clock_starts_at_registration(self):
        with tempfile.TemporaryDirectory() as tmp:
            state=State(Path(tmp)/'dynamic.sqlite',retry_delay=0)
            ticket=dict(id='T',title='T',subject='general',questions=[dict(
                id='T1',prompt='Question',answer='answer',hints=['one','two','answer'],
                finding=dict(text='Finding',evidence=['ref'],limitation='Scope only'))])
            state.initialize([], [ticket], allow_empty=True)
            state.provision('controller')
            with patch('ridge.state.now',return_value='2026-10-15T10:00:00+00:00'):
                state.mode('controller','running')
            with patch('ridge.state.now',return_value='2026-10-15T10:05:00+00:00'):
                state.register_team(dict(id='late',iris='99',ctfd=99,name='Late team'))
            with patch('ridge.state.now',return_value='2026-10-15T10:05:30+00:00'):
                self.assertEqual(state.snapshot('late')['elapsed_seconds'],30)
                self.assertEqual(state.snapshot()['elapsed_seconds'],330)


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
