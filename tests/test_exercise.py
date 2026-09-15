import base64
import csv
import hashlib
import json
import shutil
import socket
import sqlite3
import struct
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
import zipfile
from contextlib import closing
from datetime import datetime, timedelta
from pathlib import Path

REPO=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(REPO/'app'),str(REPO/'scripts')]
import server
import generate
import exercise


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.bundle=generate.generate(self.root/'a')
        self.initial=self.bundle/'initial'

    def tearDown(self):
        self.temp.cleanup()

    def rows(self,path):
        with (self.initial/path).open() as f:
            return list(csv.DictReader(f))

    def test_reproducibility_and_tamper(self):
        other=generate.generate(self.root/'b')
        self.assertEqual(generate.manifest(self.bundle),generate.manifest(other))
        generate.check(self.initial)
        (self.initial/'common/collection.md').write_text('tampered')
        with self.assertRaises(ValueError): generate.check(self.initial)

    def test_exposure_chain_and_alternatives(self):
        net={r['id']:r for r in self.rows('network/proxy.csv')}
        access={r['id']:r for r in self.rows('server/access.csv')}
        catalog={r['object']:r for r in self.rows('server/catalog.csv')}
        endpoint={r['id']:r for r in self.rows('endpoint/events.csv')}
        body=(self.bundle/'inject-1/dlp-body.txt').read_bytes()
        digest=hashlib.sha256(body).hexdigest()
        self.assertEqual(digest,catalog['plan-v3']['sha256'])
        self.assertIn(digest,endpoint['E103']['detail'])
        self.assertEqual(len(body),int(net['N102']['body_bytes']))
        self.assertEqual(net['N101']['request'],access['S101']['request'])
        self.assertEqual(access['S101']['session'],'S-41')
        self.assertEqual(access['S102']['status'],'403')
        self.assertEqual(access['S102']['bytes'],'0')
        self.assertEqual(access['S103']['actor'],'r.chen')
        for eid,nid in [('E103','N101'),('E104','N102')]:
            corrected=datetime.fromisoformat(endpoint[eid]['device_time'])-timedelta(seconds=120)
            self.assertEqual(corrected,datetime.fromisoformat(net[nid]['time']))

    def test_session_and_version_injects(self):
        auth={r['id']:r for r in self.rows('identity/auth.csv')}
        with (self.bundle/'inject-2/late-auth.csv').open() as f: late=next(csv.DictReader(f))
        self.assertEqual(auth['I101']['session'],auth['I102']['session'])
        self.assertEqual(late['session'],auth['I102']['session'])
        self.assertGreater(late['time'],auth['I104']['time'])
        with (self.bundle/'inject-2/version-comparison.csv').open() as f: version={r['field']:r for r in csv.DictReader(f)}
        self.assertEqual(version['check_in_word']['v3'],version['check_in_word']['v4'])
        self.assertNotEqual(version['sector']['v3'],version['sector']['v4'])

    def test_pcap_valid_frames_and_clock(self):
        data=(self.initial/'network/sensor.pcap').read_bytes()
        self.assertEqual(struct.unpack('<IHHIIII',data[:24]),(0xa1b2c3d4,2,4,0,0,65535,1))
        offset=24; rows=[]
        while offset<len(data):
            seconds,microseconds,included,original=struct.unpack('<IIII',data[offset:offset+16]); offset+=16
            packet=data[offset:offset+included]; offset+=included
            self.assertEqual(included,original)
            self.assertEqual(packet[12:14],b'\x08\x00')
            ip=packet[14:34]
            checksum=sum(struct.unpack('!10H',ip)); checksum=(checksum&65535)+(checksum>>16)
            self.assertEqual(checksum,65535)
            self.assertEqual(struct.unpack('!H',ip[2:4])[0],len(packet)-14)
            self.assertEqual(struct.unpack('!H',packet[36:38])[0],514)
            payload=packet[42:].decode()
            row=json.loads(payload[payload.index('{'):]); rows.append(row)
            self.assertEqual(seconds,int(datetime.fromisoformat(row['time']).timestamp()))
        self.assertEqual(rows,self.rows('network/proxy.csv'))

    def test_sqlite_and_independent_cell_evidence(self):
        with closing(sqlite3.connect(self.initial/'endpoint/browser.sqlite')) as con:
            self.assertEqual(con.execute('PRAGMA integrity_check').fetchone()[0],'ok')
            self.assertEqual(con.execute('SELECT count(*) FROM downloads').fetchone()[0],1)
        for cell in generate.CELLS:
            self.assertGreaterEqual(len(list((self.initial/cell).iterdir())),2)
        hunt=[json.loads(line) for line in (self.initial/'hunting/siem.jsonl').read_text().splitlines()]
        self.assertTrue(any(r['type']=='rare_egress' for r in hunt))
        self.assertTrue(any('offline' in r['endpoint'] for r in self.rows('hunting/coverage.csv')))

    def test_configurable_date(self):
        config=json.loads((REPO/'config.json').read_text()); config['exercise_date']='2026-10-28'
        other=generate.generate(self.root/'date',config)
        self.assertIn('2026-10-28T09:06:00Z',(other/'initial/network/proxy.csv').read_text())
        self.assertIn('2026-10-28T09:26:00Z',(other/'inject-2/late-auth.csv').read_text())


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.oldrepo,self.oldruntime=exercise.REPO,exercise.RUNTIME
        exercise.REPO=self.root; exercise.RUNTIME=self.root/'runtime'
        shutil.copy(REPO/'config.json',self.root/'config.json')
        exercise.init()
        self.runtime=exercise.RUNTIME
        self.logins=dict(line.split(': ',1) for line in (self.runtime/'cell-logins.txt').read_text().splitlines())
        self.start()

    def start(self):
        self.server=server.serve('127.0.0.1',0,self.runtime/'public',self.runtime/'state',self.runtime/'credentials.json')
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True); self.thread.start()
        self.url=f'http://127.0.0.1:{self.server.server_port}'

    def stop(self):
        if self.server:
            self.server.shutdown(); self.server.server_close(); self.thread.join(); self.server=None

    def tearDown(self):
        self.stop()
        exercise.REPO,self.oldrepo=self.oldrepo,exercise.REPO
        exercise.RUNTIME=self.oldruntime
        self.temp.cleanup()

    def request(self,path,user='network',payload=None,headers=None):
        h={}
        if user:
            token=base64.b64encode(f'{user}:{self.logins.get(user,"bad")}'.encode()).decode()
            h['Authorization']='Basic '+token
        if payload is not None:
            h.update({'Content-Type':'application/json','X-Exercise-Request':'1'})
        if headers: h.update(headers)
        req=urllib.request.Request(self.url+path,data=json.dumps(payload).encode() if payload is not None else None,headers=h)
        try:
            with urllib.request.urlopen(req) as response: return response.status,response.read()
        except urllib.error.HTTPError as e: return e.code,e.read()

    def test_auth_access_and_inject_separation(self):
        self.assertEqual(self.request('/health',None)[0],200)
        self.assertEqual(self.request('/api/files',None)[0],401)
        self.assertEqual(self.request('/api/files','wrong')[0],401)
        for user in generate.CELLS: self.assertEqual(self.request('/api/tickets',user)[0],200)
        for path in ['/files/../credentials.json','/files/%2e%2e/credentials.json','/files/..%5ccredentials.json','/files/C:/Windows/win.ini','/files/inject-1/dlp-body.txt','/facilitator/solutions.md','/files/vault/inject-1/dlp-body.txt']:
            self.assertEqual(self.request(path)[0],404,path)
        self.assertEqual(self.request('/api/release',payload={'number':1})[0],404)
        files=json.loads(self.request('/api/files')[1]); self.assertFalse(any('inject' in name for name in files))
        exercise.release(1)
        self.assertEqual(self.request('/files/inject-1/dlp-body.txt')[0],200)
        self.assertEqual(self.request('/files/inject-2/late-auth.csv')[0],404)
        exercise.verify()

    def test_independent_tab_sessions(self):
        exercise.control.append(self.runtime,'start')
        self.assertEqual(self.request('/', None)[0], 200)
        tokens = {}
        for cell in generate.CELLS:
            status, body = self.request('/api/login', None, {'cell': cell, 'password': self.logins[cell]})
            self.assertEqual(status, 200)
            tokens[cell] = json.loads(body)['token']
        self.assertEqual(len(set(tokens.values())), 5)
        for cell, token in tokens.items():
            headers = {'Authorization': 'Bearer ' + token}
            self.assertEqual(json.loads(self.request('/api/me', None, headers=headers)[1])['cell'], cell)
            self.assertEqual(self.request('/files/common/collection.md', None, headers=headers)[0], 200)
            self.assertEqual(self.request('/api/update', None, {'ticket': 1, 'body': cell}, headers)[0], 201)
        endpoint = {'Authorization': 'Bearer ' + tokens['endpoint']}
        self.assertEqual(self.request('/api/update', None, {'ticket': 1, 'body': 'deny', 'status': 'Closed'}, endpoint)[0], 403)
        network = {'Authorization': 'Bearer ' + tokens['network']}
        self.assertEqual(self.request('/api/logout', None, {}, network)[0], 200)
        self.assertEqual(self.request('/api/me', None, headers=network)[0], 401)
        self.assertEqual(self.request('/api/me', None, headers=endpoint)[0], 200)
        self.server.sessions[tokens['endpoint']] = ('endpoint', 0)
        self.assertEqual(self.request('/api/me', None, headers=endpoint)[0], 401)
        self.assertEqual(self.request('/api/login', None, {'cell': 'network', 'password': 'wrong'})[0], 401)
        self.stop(); self.start()
        self.assertEqual(self.request('/api/me', None, headers={'Authorization': 'Bearer ' + tokens['server']})[0], 401)

    def test_shared_comments_owner_status_and_restart(self):
        exercise.control.append(self.runtime,'start')
        for user in generate.CELLS:
            self.assertEqual(self.request('/api/update',user,{'ticket':1,'body':f'{user}: evidence comment'})[0],201)
        self.assertEqual(self.request('/api/update','identity',{'ticket':1,'body':'close','status':'Closed'})[0],403)
        self.assertEqual(self.request('/api/update','network',{'ticket':1,'body':'report sent','status':'Assessment sent'})[0],201)
        self.stop(); self.start()
        ticket=json.loads(self.request('/api/tickets','server')[1])[0]
        self.assertEqual(len(ticket['comments']),6)
        self.assertEqual(ticket['status'],'Assessment sent')

    def test_updates_rejected_before_start_and_while_paused(self):
        payload={'ticket':1,'body':'premature','status':'Closed'}
        self.assertEqual(self.request('/api/update',payload=payload)[0],409)
        exercise.control.append(self.runtime,'start')
        self.assertEqual(self.request('/api/update',payload=payload)[0],201)
        exercise.control.append(self.runtime,'pause')
        self.assertEqual(self.request('/api/update',payload=payload)[0],409)
        self.assertEqual(len(json.loads(self.request('/api/tickets')[1])[0]['comments']),1)

    def test_input_validation_and_csrf(self):
        for payload in [[],{}, {'ticket':99,'body':'x'},{'ticket':True,'body':'x'},{'ticket':1,'body':' '},{'ticket':1,'body':'x','status':'Hacked'}]:
            self.assertEqual(self.request('/api/update',payload=payload)[0],400)
        self.assertEqual(self.request('/api/update',payload={'ticket':1,'body':'x'},headers={'X-Exercise-Request':'0'})[0],403)
        self.assertEqual(self.request('/api/update',payload={'ticket':1,'body':'x'*20000})[0],413)

    def test_release_order_export_reset_and_new_credentials(self):
        exercise.control.append(self.runtime,'start')
        with self.assertRaises(ValueError): exercise.release(2)
        exercise.release(1); exercise.release(1); exercise.release(2); exercise.release(3)
        self.request('/api/update',payload={'ticket':1,'body':'preserve me'})
        exported=exercise.export()
        with zipfile.ZipFile(exported) as z:
            self.assertIn('tickets.sqlite',z.namelist())
            self.assertFalse(any('credentials' in name or 'logins' in name for name in z.namelist()))
            self.assertEqual(len(json.loads(z.read('release-log.json'))),3)
        with self.assertRaises(ValueError): exercise.reset(False)
        previous=(self.runtime/'credentials.json').read_bytes()
        self.stop(); exercise.reset(True)
        self.assertNotEqual(previous,(self.runtime/'credentials.json').read_bytes())
        self.assertFalse((self.runtime/'public/inject-1').exists())
        exercise.verify(); self.start()
        self.assertEqual(self.request('/api/tickets')[0],401)
        self.logins=dict(line.split(': ',1) for line in (self.runtime/'cell-logins.txt').read_text().splitlines())
        self.assertEqual(json.loads(self.request('/api/tickets')[1])[0]['comments'],[])


if __name__=='__main__': unittest.main()
