import json
import socket
import threading
import time
import urllib.request
import urllib.error
import unittest
from pathlib import Path
import test_exercise as baseline
import admin_server
import control
import exercise

class AdminTests(unittest.TestCase):
    setUpRuntime=baseline.RuntimeTests.setUp
    tearDownRuntime=baseline.RuntimeTests.tearDown
    start=baseline.RuntimeTests.start
    stop=baseline.RuntimeTests.stop
    request=baseline.RuntimeTests.request
    def setUp(self):
        self.setUpRuntime()
        self.saved=(admin_server.ROOT,admin_server.ACCOUNTS)
        admin_server.ROOT=self.root;admin_server.ACCOUNTS=self.runtime/'admin-accounts.json'
        admin_server.provision('facilitator-one')
        self.password=(self.runtime/'admin-logins.txt').read_text().split(': ',1)[1].strip()
        self.admin=admin_server.serve(0)
        self.worker=threading.Thread(target=self.admin.serve_forever,daemon=True);self.worker.start()
        self.adminurl='http://127.0.0.1:'+str(self.admin.server_port);self.token=''
    def tearDown(self):
        self.admin.shutdown();self.admin.server_close();self.worker.join()
        admin_server.ROOT,admin_server.ACCOUNTS=self.saved
        self.tearDownRuntime()
    def call(self,path,data=None,custom=True):
        headers={'Authorization':'Bearer '+self.token}
        if data is not None:
            headers['Content-Type']='application/json'
            if custom:headers['X-Admin-Request']='1'
        req=urllib.request.Request(self.adminurl+path,data=None if data is None else json.dumps(data).encode(),headers=headers)
        try:
            with urllib.request.urlopen(req) as r:return r.status,json.loads(r.read())
        except urllib.error.HTTPError as e:return e.code,json.loads(e.read())
    def login(self):
        code,data=self.call('/api/login',{'name':'facilitator-one','password':self.password})
        self.assertEqual(code,200);self.token=data['token']
    def test_auth_and_private_material(self):
        self.assertEqual(self.call('/api/state')[0],401)
        self.assertEqual(self.call('/api/logins')[0],401)
        self.assertEqual(self.call('/api/login',{'name':'network','password':self.logins['network']})[0],401)
        self.login()
        self.assertEqual(self.call('/api/state')[0],200)
        self.assertEqual(self.call('/api/action',{'action':'start','text':'ready'},False)[0],403)
        self.assertEqual(self.request('/api/state')[0],404)
        self.assertEqual(self.request('/files/../admin-accounts.json')[0],404)
        self.assertEqual(self.call('/api/action',{'action':'reset'})[0],400)
        self.call('/api/logout',{})
        self.assertEqual(self.call('/api/state')[0],401)
    def test_workflow_publication_and_export(self):
        self.login()
        for action in ('start','pause','resume','note'):
            self.assertEqual(self.call('/api/action',{'action':action,'text':'PRIVATE spoiler'})[0],200)
        visible=json.loads(self.request('/api/control')[1])
        self.assertNotIn('PRIVATE',json.dumps(visible))
        decision={'action':'decision','text':'Approved isolation','request':'T1-C1','outcome':'approved','effective_minute':10}
        self.assertEqual(self.call('/api/action',decision)[0],400)
        self.assertEqual(self.call('/api/action',{**decision,'confirm':'PUBLISH'})[0],200)
        self.assertEqual(json.loads(self.request('/api/control')[1])[-1]['operator'],'facilitator-one')
        self.assertEqual(self.call('/api/action',{'action':'release','number':2,'confirm':'RELEASE 2'})[0],400)
        self.assertEqual(self.call('/api/action',{'action':'release','number':1})[0],400)
        self.assertEqual(self.call('/api/action',{'action':'release','number':1,'confirm':'RELEASE 1'})[0],200)
        exercise.verify()
        self.assertEqual(self.call('/api/action',{'action':'export'})[0],200)
        self.assertTrue(list((self.root/'exports').glob('*.zip')))
        self.assertEqual(control.read(self.runtime)[-1]['operator'],'facilitator-one')
    def test_nonlogin_auth_precedes_body_and_slow_login_times_out(self):
        self.admin.request_timeout=0.2
        with socket.create_connection(('127.0.0.1',self.admin.server_port),timeout=2) as client:
            started=time.monotonic()
            client.sendall(b'POST /api/action HTTP/1.1\r\nHost: test\r\n'
                           b'Content-Type: application/json\r\nX-Admin-Request: 1\r\n'
                           b'Authorization: Bearer invalid\r\nContent-Length: 100\r\n\r\n')
            self.assertIn(b'401 Unauthorized',client.recv(4096))
            self.assertLess(time.monotonic()-started,0.2)
        with socket.create_connection(('127.0.0.1',self.admin.server_port),timeout=2) as client:
            client.sendall(b'POST /api/login HTTP/1.1\r\nHost: test\r\n'
                           b'Content-Type: application/json\r\nX-Admin-Request: 1\r\n'
                           b'Content-Length: 100\r\n\r\n{}')
            self.assertIn(b'408 Request Timeout',client.recv(4096))
