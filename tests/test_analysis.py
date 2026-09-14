import hashlib
import json
import unittest
import test_exercise as baseline
import analysis_tools

class AnalysisTests(unittest.TestCase):
    setUp = baseline.RuntimeTests.setUp
    tearDown = baseline.RuntimeTests.tearDown
    start = baseline.RuntimeTests.start
    stop = baseline.RuntimeTests.stop
    request = baseline.RuntimeTests.request

    def test_viewers_and_boundary(self):
        self.assertEqual(self.request('/api/analyze',None,{'file':'network/proxy.csv'})[0],401)
        for path in ('../vault/inject-1/dlp-body.txt','inject-1/dlp-body.txt','handouts/cells.md','common/schedule.md','/etc/passwd'):
            self.assertEqual(self.request('/api/analyze',payload={'file':path})[0],400)
        for file in ('network/proxy.csv','hunting/siem.jsonl','network/sensor.pcap','identity/policy.txt'):
            status,body=self.request('/api/analyze',payload={'file':file})
            self.assertEqual(status,200)
            data=json.loads(body)
            self.assertEqual(data['sha256'],hashlib.sha256((self.runtime/'public'/file).read_bytes()).hexdigest())
        packets=json.loads(self.request('/api/analyze',payload={'file':'network/sensor.pcap'})[1])['rows']
        self.assertEqual(packets[0]['protocol'],'UDP')
        self.assertIn('N001',packets[0]['payload'])

    def test_sql_read_only_and_budget(self):
        path=self.runtime/'public/endpoint/browser.sqlite'
        before=path.read_bytes()
        status,body=self.request('/api/analyze',payload={'file':'endpoint/browser.sqlite','query':'SELECT * FROM downloads'})
        self.assertEqual(status,200)
        self.assertEqual(json.loads(body)['rows'][0]['id'],1)
        for query in ("DELETE FROM downloads","ATTACH DATABASE ':memory:' AS other","PRAGMA database_list","SELECT load_extension('x')","SELECT * FROM downloads; SELECT 1","WITH RECURSIVE x(n) AS (VALUES(1) UNION ALL SELECT n+1 FROM x) SELECT sum(n) FROM x","SELECT zeroblob(100000000)"):
            self.assertEqual(self.request('/api/analyze',payload={'file':'endpoint/browser.sqlite','query':query})[0],400,query)
        self.assertEqual(path.read_bytes(),before)
