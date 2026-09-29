import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from ridge.service import Handler
import test_ridge as core_tests


class APITests(unittest.TestCase):
    sink=core_tests.WorkflowTests.sink
    drain=core_tests.WorkflowTests.drain

    def setUp(self):
        core_tests.WorkflowTests.setUp(self)
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        self.server.state=self.state
        self.server.secrets={'iris':'i'*40,'ctfd':'c'*40}
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()

    def tearDown(self):
        self.server.shutdown();self.thread.join();self.server.server_close()
        core_tests.WorkflowTests.tearDown(self)

    def request(self,application,identity,action,key=None,**payload):
        if action=='claim':
            payload.setdefault('generation',0)
        body=json.dumps(dict(payload,application=application,identity=identity,action=action)).encode()
        request=Request('http://127.0.0.1:'+str(self.server.server_port)+'/action',body,
                        {'Content-Type':'application/json','Authorization':'Bearer '+(key or self.server.secrets[application])})
        try:
            with urlopen(request) as response:return response.status,json.load(response)
        except HTTPError as error:return error.code,json.load(error)

    def test_application_roles_direct_access_and_cross_identity(self):
        self.assertEqual(self.request('iris','10','claim',key='c'*40,ticket='A')[0],401)
        self.assertEqual(self.request('ctfd',20,'claim',ticket='A')[0],403)
        self.assertEqual(self.request('iris','10','answer',question='A0',answer='answer')[0],403)
        self.assertEqual(self.request('iris','10','claim',ticket='A')[0],200)
        self.assertEqual(self.request('ctfd',21,'questions',question='A0')[0],403)
        self.assertEqual(self.request('ctfd',20,'questions',question='B0')[0],403)
        status,result=self.request('ctfd',20,'answer',question='A0',answer='answer')
        self.assertEqual(status,200);self.assertEqual(result['synchronization'],'pending')
        self.assertEqual(self.request('ctfd',20,'answer',question='A0',answer='answer')[0],409)


if __name__=='__main__':unittest.main()
