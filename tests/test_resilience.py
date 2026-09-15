"""Regression tests for outages, stale actions, export fencing, and release facts."""
import csv
import hashlib
import io
import json
import os
import shutil
import sqlite3
import struct
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from ridge.state import State, Conflict
from ridge.export_run import export
from ridge.evidence_release import publish, index
from ridge.scenario import timestamp
from ridge.storage import prune, require_space
from expanded.prepare import build
from expanded.author import build as author


class StateTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        self.state=State(self.root/'state.sqlite',retry_delay=0)
        self.state.initialize([dict(id='a',iris='1',ctfd=1,name='A')], [
            dict(id=tid,title=tid,subject='x',requires=requires,questions=[
                dict(id=tid+'q',answer='yes',finding=dict(text='yes',evidence=['ref'],limitation='scope'))])
            for tid,requires in [('T01',[]),('T02',[]),('T03',['T01'])]])
        self.receipts={}

    def tearDown(self):
        self.tmp.cleanup()

    def sink(self,kind,key,payload,context):
        self.receipts.setdefault(key,(kind,len(self.receipts)+1))
        return self.receipts[key][1]

    def ready(self):
        self.state.provision('operator')
        while self.state.sync_once(self.sink):
            pass
        self.state.mode('operator','running')

    def test_no_side_effects_before_explicit_provision(self):
        self.assertFalse(self.state.sync_once(self.sink))
        self.assertEqual(self.receipts,{})
        with self.assertRaises(Conflict):
            self.state.mode('operator','running')
        self.ready()
        self.assertEqual(len(self.receipts),2)

    def test_slow_remote_does_not_block_reads_writes_or_pause(self):
        self.ready()
        self.state.claim('a','T01')
        entered=threading.Event();finish=threading.Event()
        def slow(*args):
            entered.set()
            self.assertTrue(finish.wait(5))
            return self.sink(*args)
        worker=threading.Thread(target=lambda:self.state.sync_once(slow))
        worker.start()
        try:
            self.assertTrue(entered.wait(2))
            begin=time.monotonic()
            self.state.snapshot()
            self.state.answer('a','T01q','yes')
            self.state.mode('operator','paused')
            self.assertLess(time.monotonic()-begin,1)
        finally:
            finish.set();worker.join()

    def test_failed_ticket_does_not_block_other_ticket(self):
        self.state.provision('operator')
        self.state.retry_delay=30
        def fail_first(kind,key,payload,context):
            if payload['ticket']=='T01':
                raise TimeoutError()
            return self.sink(kind,key,payload,context)
        self.assertFalse(self.state.sync_once(fail_first))
        self.assertTrue(self.state.sync_once(fail_first))
        self.assertTrue(any('ticket:T02' in key for key in self.receipts))
        self.assertFalse(any('ticket:T01' in key for key in self.receipts))

    def test_stale_release_and_claim_rejected(self):
        self.ready()
        self.state.claim('a','T01',0)
        self.state.release('a','T01',1)
        with self.assertRaises(Conflict):
            self.state.claim('a','T01',0)
        self.state.claim('a','T01',1)
        with self.assertRaises(Conflict):
            self.state.release('a','T01',1)
        self.assertEqual(self.state.snapshot()['tickets'][0]['owner'],'a')

    def test_expired_lease_replays_same_key(self):
        self.state.provision('operator')
        with self.state.transaction() as con:
            con.execute("UPDATE outbox SET lease='dead',lease_until=? WHERE ticket='T01'",(time.time()-1,))
        self.assertTrue(self.state.sync_once(self.sink))
        self.assertEqual(len(self.receipts),1)

    def test_stale_worker_cannot_acknowledge_reassigned_lease(self):
        self.state.provision('operator')
        entered=threading.Event();finish=threading.Event();results=[]
        def late(*args):
            entered.set();finish.wait(5)
            return 999
        worker=threading.Thread(target=lambda:results.append(self.state.sync_once(late)))
        worker.start()
        try:
            self.assertTrue(entered.wait(2))
            with self.state.transaction() as con:
                con.execute("UPDATE outbox SET lease_until=0 WHERE ticket='T01'")
            self.assertTrue(self.state.sync_once(self.sink))
        finally:
            finish.set();worker.join()
        self.assertEqual(results,[False])
        self.assertNotEqual(self.state.snapshot()['tickets'][0]['iris_id'],999)

    def test_two_workers_and_causal_followups(self):
        self.ready();self.state.claim('a','T01');self.state.answer('a','T01q','yes')
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(2) as pool:
            for _ in range(6):
                list(pool.map(lambda _:self.state.sync_once(self.sink),range(2)))
        keys=list(self.receipts)
        def position(suffix):
            return next(i for i,key in enumerate(keys) if key.endswith(suffix))
        self.assertLess(position('point:T01q'),position('finding:T01q'))
        self.assertLess(position('finding:T01q'),position('close:T01'))
        self.assertLess(position('close:T01'),position('ticket:T03'))

    def test_export_blocks_resume_recovery_and_announcements(self):
        self.ready();self.state.claim('a','T01')
        while self.state.sync_once(self.sink):pass
        self.state.mode('operator','paused')
        def remote(url,*args,**kwargs):
            for action in (lambda:self.state.mode('other','running'),
                           lambda:self.state.release(None,'T01',1,recovery_actor='other',reason='retry'),
                           lambda:self.state.announce('other','change')):
                with self.assertRaises(Conflict):action()
            if url.startswith('IRIS'):
                return {'receipts':[{'key':key,'remote':value[1]} for key,value in self.receipts.items() if value[0]!='point']}
            return {'credits':[]}
        with patch('ridge.export_run.post',side_effect=remote),patch('ridge.export_run.secret',return_value='x'),patch.dict(os.environ,IRIS_URL='IRIS',CTFD_URL='CTFD'):
            result=export(self.state,self.root/'export')
        self.assertTrue((result/'SHA256SUMS.json').exists())
        self.assertIsNone(self.state.diagnostics()['export_token'])

    def test_export_failure_unfreezes_without_completion_marker(self):
        self.ready();self.state.mode('operator','paused')
        with patch('ridge.export_run.post',side_effect=TimeoutError),patch('ridge.export_run.secret',return_value='x'),patch.dict(os.environ,IRIS_URL='IRIS',CTFD_URL='CTFD'):
            with self.assertRaises(TimeoutError):export(self.state,self.root/'export')
        self.assertFalse((self.root/'export/SHA256SUMS.json').exists())
        self.assertIsNone(self.state.diagnostics()['export_token'])

    def test_revoked_export_cannot_complete(self):
        self.ready();self.state.mode('operator','paused')
        with self.state.export_barrier() as token:
            self.state.cancel_export('operator',token)
            with self.assertRaises(Conflict):self.state.verify_export_token(token)


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.release=build(self.root/'release',{'exercise_date':'2027-02-03'})
        self.env=patch.dict(os.environ,RIDGE_RELEASE_VAULT=str(self.release/'controller/releases'),
                            RIDGE_EVIDENCE_PUBLIC=str(self.release/'initial'))
        self.env.start()

    def tearDown(self):
        self.env.stop();self.tmp.cleanup()

    def test_date_dns_and_browser_agree(self):
        public=self.release/'initial'
        with (public/'network/dns.csv').open(newline='') as f:rows=list(csv.DictReader(f))
        raw=(public/'network/dns.pcap').read_bytes();offset=24;ttls=[]
        while offset<len(raw):
            _,_,size,_=struct.unpack_from('<IIII',raw,offset)
            packet=raw[offset+16:offset+16+size];offset+=16+size
            dns=packet[42:]
            if struct.unpack_from('!H',dns,6)[0]:ttls.append(struct.unpack_from('!I',dns,len(dns)-10)[0])
        self.assertEqual(ttls,[int(r['ttl']) for r in rows])
        telemetry=[json.loads(line) for line in (public/'wazuh/telemetry.jsonl').read_text().splitlines()]
        browser=next(r for r in telemetry if r['data']['source']=='browser/downloads.csv')
        self.assertEqual(browser['timestamp'],'2027-02-03T08:57:00Z')
        self.assertTrue(all(r.get('timestamp','2027-02-03').startswith('2027-02-03') for r in telemetry))
        self.assertTrue(any(r.get('timeless') for r in telemetry))
        self.assertIn('2027-02-03',json.dumps(author({'exercise_date':'2027-02-03'})))

    def test_missing_and_corrupt_required_release_fail_closed(self):
        source=self.release/'controller/releases/T07/identity/late-auth.csv'
        source.write_text('corrupt',encoding='utf-8')
        with self.assertRaises(ValueError):publish('T07',['identity/late-auth.csv'])
        self.assertFalse((self.release/'initial/identity/late-auth.csv').exists())
        source.unlink()
        with self.assertRaises(ValueError):publish('T07',['identity/late-auth.csv'])
        with self.assertRaises(ValueError):publish('T07',[])
        publish('T01',[])

    def test_index_failure_does_not_publish_files_and_retry_succeeds(self):
        with patch('ridge.evidence_release.index',side_effect=TimeoutError):
            with self.assertRaises(TimeoutError):publish('T07',['identity/late-auth.csv'])
        self.assertFalse((self.release/'initial/identity/late-auth.csv').exists())
        with patch('ridge.evidence_release.index') as indexed:
            publish('T07',['identity/late-auth.csv'])
            publish('T07',['identity/late-auth.csv'])
        self.assertEqual(indexed.call_count,2)
        self.assertTrue((self.release/'initial/identity/late-auth.csv').exists())

    def test_unknown_clock_or_time_schema_rejected(self):
        with self.assertRaises(ValueError):timestamp({'device_time':'2027-02-03T09:00:00Z','host':'unknown'},'endpoint.csv')
        with self.assertRaises(ValueError):timestamp({'time':'2027-02-03T09:00:00'},'endpoint.csv')
        with self.assertRaises(ValueError):timestamp({},'new.csv')

    def test_reproducible_expanded_outputs(self):
        other=build(self.root/'other',{'exercise_date':'2027-02-03'})
        a=json.loads((self.release/'SHA256SUMS.json').read_text())
        b=json.loads((other/'SHA256SUMS.json').read_text())
        self.assertEqual(a,b)

    def test_preflight_reconciles_names_and_required_paths(self):
        from ridge.preflight import check
        state=State(self.root/'state.sqlite')
        team=dict(id='a',name='A',iris='1',ctfd=2,iris_login='iris-a',ctfd_name='ctfd-a')
        ticket=dict(id='T07',title='T07',subject='x',release_files=['identity/late-auth.csv'],questions=[
            dict(id='q',answer='yes',evidence='/evidence/wazuh/telemetry.jsonl',finding=dict(text='yes',evidence=['ref'],limitation='scope'))])
        state.initialize([team],[ticket])
        credential=self.root/'credential';credential.write_text('user:password')
        def remote(url,*args,**kwargs):
            identity={'id':'1','name':'iris-a'} if url.startswith('IRIS') else {'id':'2','name':'ctfd-a'}
            return {'ready':True,'identities':[identity]}
        with patch.dict(os.environ,IRIS_URL='IRIS',CTFD_URL='CTFD',WAZUH_INDEX='silent-ridge-test',
                        WAZUH_INDEXER_URL='https://local',WAZUH_INDEX_CREDENTIAL_FILE=str(credential)),\
             patch('ridge.preflight.secret',return_value='x'),patch('ridge.preflight.post',side_effect=remote),\
             patch('urllib.request.urlopen',side_effect=lambda *args,**kwargs:io.BytesIO(b'{"silent-ridge-test":{}}')):
            self.assertTrue(check(state,{'teams':[team]})['ready'])
            with self.assertRaises(ValueError):check(state,{'teams':[{**team,'ctfd_name':'wrong'}]})
            (self.release/'initial/wazuh/telemetry.jsonl').unlink()
            with self.assertRaises(ValueError):check(state,{'teams':[team]})


class UtilityTests(unittest.TestCase):
    def test_migrate_existing_database_preserves_delivery_order(self):
        from ridge.schema import migrate
        with tempfile.TemporaryDirectory() as tmp:
            con=sqlite3.connect(Path(tmp)/'old.sqlite',isolation_level=None)
            con.row_factory=sqlite3.Row
            try:
                con.executescript('''CREATE TABLE tickets(id TEXT PRIMARY KEY);
                    CREATE TABLE outbox(id TEXT PRIMARY KEY,kind TEXT,payload TEXT,done INTEGER,attempts INTEGER,error TEXT,remote TEXT);
                    CREATE TABLE audit(id INTEGER PRIMARY KEY,action TEXT);''')
                con.execute('INSERT INTO outbox VALUES (?,?,?,?,?,?,?)',('old','ticket','{"ticket":"T01"}',1,1,None,'9'))
                con.execute('INSERT INTO outbox VALUES (?,?,?,?,?,?,?)',('next','point','{"ticket":"T01"}',0,0,None,None))
                con.execute('BEGIN IMMEDIATE');migrate(con);con.commit()
                self.assertEqual(con.execute('SELECT remote FROM outbox WHERE id="old"').fetchone()[0],'9')
                self.assertEqual(tuple(con.execute('SELECT * FROM delivery_dependencies').fetchone()),('next','old'))
                con.execute('BEGIN IMMEDIATE');migrate(con);con.commit()
                self.assertEqual(con.execute('SELECT COUNT(*) FROM delivery_dependencies').fetchone()[0],1)
            finally:
                con.close()

    def test_bulk_partial_failure_rejected_and_ids_stable(self):
        with tempfile.TemporaryDirectory() as tmp:
            credential=Path(tmp)/'secret';credential.write_text('user:password')
            bodies=[]
            def response(request,**kwargs):
                bodies.append(request.data)
                return io.BytesIO(json.dumps({'errors':False,'items':[{'index':{'status':201}}]}).encode())
            with patch.dict(os.environ,WAZUH_INDEX_CREDENTIAL_FILE=str(credential),WAZUH_INDEXER_URL='https://local',WAZUH_INDEX='silent-ridge-test'),patch('ridge.evidence_release.urlopen',side_effect=response):
                index([{'timestamp':'2027-02-03T09:00:00Z'}]);index([{'timestamp':'2027-02-03T09:00:00Z'}])
                self.assertEqual(bodies[0],bodies[1])
                with self.assertRaises(ValueError):index([{},{}])

    def test_storage_low_space_and_verified_backup_pruning(self):
        with patch('ridge.storage.shutil.disk_usage',return_value=shutil._ntuple_diskusage(100,99,1)):
            with self.assertRaises(ValueError):require_space(Path.cwd())
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'exports';backup=Path(tmp)/'backup';folder=root/'old'
            folder.mkdir(parents=True);backup.mkdir()
            for name in ('iris.json','ctfd.json','integration.json'):(folder/name).write_text('{}')
            sums={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.iterdir()}
            marker=folder/'SHA256SUMS.json';marker.write_text(json.dumps(sums))
            shutil.copytree(folder,backup/'old')
            os.utime(marker,(0,0))
            self.assertEqual(prune(root,backup,1),['old']);self.assertTrue(folder.exists())
            (backup/'old/iris.json').write_text('changed')
            with self.assertRaises(ValueError):prune(root,backup,1,True)
            (backup/'old/iris.json').write_text('{}')
            self.assertEqual(prune(root,backup,1,True),['old']);self.assertFalse(folder.exists())


if __name__=='__main__':unittest.main()
