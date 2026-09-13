"""Mutating rehearsal/CI smoke test; never run on a live event."""
import argparse
import base64
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

parser=argparse.ArgumentParser()
parser.add_argument('--url',default='http://127.0.0.1:8080')
parser.add_argument('--expect-persistence',action='store_true')
parser.add_argument('--released',action='store_true')
parser.add_argument('--expect-control',action='store_true')
args=parser.parse_args()
root=Path(__file__).resolve().parents[1]
logins=dict(line.split(': ',1) for line in (root/'runtime/cell-logins.txt').read_text().splitlines())


def request(path,cell=None,payload=None):
    headers={}
    if cell:
        headers['Authorization']='Basic '+base64.b64encode(f'{cell}:{logins[cell]}'.encode()).decode()
    if payload is not None:
        headers.update({'Content-Type':'application/json','X-Exercise-Request':'1'})
    req=urllib.request.Request(args.url+path,headers=headers,data=json.dumps(payload).encode() if payload else None)
    try:
        with urllib.request.urlopen(req,timeout=5) as response: return response.status,response.read()
    except urllib.error.HTTPError as error: return error.code,error.read()


for attempt in range(30):
    try:
        if request('/health')[0]==200: break
    except (urllib.error.URLError,TimeoutError): pass
    time.sleep(1)
else: raise SystemExit('Service did not become healthy')
assert request('/api/files')[0]==401
assert request('/api/control')[0]==401
assert request('/api/control','network',{'kind':'decision'})[0]==404
for cell in logins:
    assert request('/api/tickets',cell)[0]==200
assert request('/files/%2e%2e/credentials.json','network')[0]==404
assert request('/files/inject-1/dlp-body.txt','network')[0]==(200 if args.released else 404)
assert request('/files/inject-2/late-auth.csv','network')[0]==404
tickets=json.loads(request('/api/tickets','network')[1])
if args.expect_persistence:
    assert any(c['body']=='CI shared comment' for c in tickets[0]['comments'])
else:
    assert not any(t['comments'] for t in tickets)
    assert request('/api/update','identity',{'ticket':1,'body':'CI shared comment'})[0]==201
assert request('/api/update','identity',{'ticket':1,'body':'reject','status':'Closed'})[0]==403
if args.expect_control:
    ledger=json.loads(request('/api/control','network')[1])
    assert any(e['kind']=='decision' and e['operator']=='CI-controller' for e in ledger)
    assert request('/api/update','hunting',{'ticket':5,'body':'CI clock comment'})[0]==201
    comment=json.loads(request('/api/tickets','hunting')[1])[4]['comments'][-1]
    assert comment['elapsed_seconds'] is not None and comment['clock_event']==ledger[-1]['id']
print('HTTP smoke passed: auth, five cells, traversal, inject gating, shared comments and persistence state.')
