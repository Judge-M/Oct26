"""Host-only facilitator service. Never expose this port on participant networks.

Operator URL is http://127.0.0.1:8084/ by default (see DEFAULT_PORT). This
panel is host-only and is not part of the documented event-day runbook; the
retired operator guide is docs/admin-panel.md.
"""
import argparse
import hashlib
import hmac
import json
import secrets
import sqlite3
import threading
import time
from contextlib import closing
from http.server import BaseHTTPRequestHandler
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bounded_http import BoundedThreadingHTTPServer, RequestBodyTimeout, read_request_body
import control
import exercise

ROOT=Path(__file__).resolve().parents[1]
ACCOUNTS=ROOT/'runtime/admin-accounts.json'
ASSETS=ROOT/'admin'

def provision(name):
    if not name or len(name)>80: raise ValueError('Use a named facilitator account')
    accounts=json.loads(ACCOUNTS.read_text()) if ACCOUNTS.exists() else {}
    if name in accounts: raise ValueError('Account exists; no password changed')
    password=secrets.token_urlsafe(24);salt=secrets.token_bytes(16)
    accounts[name]={'salt':salt.hex(),'hash':hashlib.pbkdf2_hmac('sha256',password.encode(),salt,200000).hex()}
    ACCOUNTS.write_text(json.dumps(accounts));ACCOUNTS.chmod(0o600)
    path=ROOT/'runtime/admin-logins.txt'
    with path.open('a') as f:f.write(name+': '+password+'\n')
    path.chmod(0o600)
    print('Account created. Retrieve password from runtime/admin-logins.txt.')

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def send(self,status,data,kind='application/json'):
        data=data if isinstance(data,bytes) else (json.dumps(data) if kind=='application/json' else data).encode()
        self.send_response(status)
        for key,value in [('Content-Type',kind),('Content-Length',str(len(data))),('Cache-Control','no-store'),('X-Content-Type-Options','nosniff'),('Content-Security-Policy',"default-src 'self'; frame-ancestors 'none'; script-src 'self'; style-src 'self'")]:self.send_header(key,value)
        self.end_headers();self.wfile.write(data)
    def user(self):
        token=self.headers.get('Authorization','').removeprefix('Bearer ')
        with self.server.lock:
            item=self.server.sessions.get(token)
        return item[0] if item and item[1]>time.monotonic() else None
    def do_GET(self):
        if self.path in ('/','/admin.js','/admin.css'):
            name='index.html' if self.path=='/' else self.path[1:]
            return self.send(200,(ASSETS/name).read_bytes(),{'/':'text/html; charset=utf-8','/admin.js':'text/javascript; charset=utf-8','/admin.css':'text/css'}[self.path])
        if not self.user():return self.send(401,{'error':'Facilitator login required'})
        if self.path=='/api/state':
            docs={}
            for name in ('controller-guide.md','ground-truth.md','solutions.md','cell-coaching.md'):
                p=ROOT/'facilitator'/name
                if p.exists():docs[name]=p.read_text(encoding='utf-8')
            docs['Full run schedule']=(ROOT/'runtime/vault/controller-schedule.md').read_text(encoding='utf-8')
            for p in sorted((ROOT/'runtime/vault').glob('inject-*/command.md')):docs[p.parent.name]=p.read_text(encoding='utf-8')
            tickets=[]
            path=ROOT/'runtime/state/tickets.sqlite'
            if path.exists():
                with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)) as con:
                    for row in con.execute('SELECT id,owner,status FROM tickets'):
                        comments=con.execute('SELECT id,author,created,body FROM comments WHERE ticket=? ORDER BY id',(row[0],)).fetchall()
                        tickets.append({'id':row[0],'owner':row[1],'status':row[2],'comments':comments})
            return self.send(200,{'user':self.user(),'events':control.read(exercise.RUNTIME),'documents':docs,'tickets':tickets})
        if self.path=='/api/logins':
            return self.send(200,{'logins':(ROOT/'runtime/cell-logins.txt').read_text()})
        return self.send(404,{'error':'Unknown resource'})
    def do_POST(self):
        if self.headers.get('Content-Type')!='application/json' or self.headers.get('X-Admin-Request')!='1':
            return self.send(403,{'error':'Use the facilitator panel'})
        if self.path!='/api/login' and not self.user():
            return self.send(401,{'error':'Facilitator login required'})
        try:
            size=int(self.headers.get('Content-Length','0'))
            if not 0<size<=16000:raise ValueError('Invalid request size')
            data=json.loads(read_request_body(self,size))
            if not isinstance(data,dict):raise ValueError('Invalid request')
            if self.path=='/api/login':
                with self.server.lock:
                    self.server.attempts=[t for t in self.server.attempts if t>time.monotonic()-60]
                    if len(self.server.attempts)>=20:return self.send(429,{'error':'Too many attempts; wait one minute'})
                    self.server.attempts.append(time.monotonic())
                accounts=json.loads(ACCOUNTS.read_text());name=data.get('name','');password=data.get('password','')
                entry=accounts.get(name)
                if not entry or not isinstance(password,str) or not hmac.compare_digest(entry['hash'],hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(entry['salt']),200000).hex()):
                    return self.send(401,{'error':'Incorrect facilitator name or password'})
                token=secrets.token_urlsafe(32)
                with self.server.lock:self.server.sessions[token]=(name,time.monotonic()+4*3600)
                return self.send(200,{'token':token})
            user=self.user()
            if self.path=='/api/logout':
                with self.server.lock:self.server.sessions.pop(self.headers.get('Authorization','').removeprefix('Bearer '),None)
                return self.send(200,{'ok':True})
            if self.path!='/api/action':return self.send(404,{'error':'Unknown resource'})
            action=data.get('action');text=data.get('text','')
            if action=='export':
                path=exercise.export()
                return self.send(200,{'message':'Private export saved: '+str(path)})
            if action=='release':
                number=data.get('number')
                if type(number)is not int or number not in (1,2,3) or data.get('confirm')!='RELEASE '+str(number):raise ValueError('Type the release confirmation')
                exercise.release(number,user)
            elif action in ('start','pause','resume','note','decision'):
                if not isinstance(text,str) or not text.strip() or len(text)>8000:raise ValueError('A reason or note is required')
                details={'text':text}
                if action=='decision':
                    if data.get('confirm')!='PUBLISH':raise ValueError('Confirm publication to participants')
                    outcome=data.get('outcome');minute=data.get('effective_minute');reference=data.get('request')
                    duration=json.loads((exercise.RUNTIME/'run-config.json').read_text())['duration_minutes']
                    if outcome not in ('approved','denied','pending') or not isinstance(reference,str) or not reference.strip():raise ValueError('Request reference and outcome required')
                    if minute is not None and (type(minute)not in (int,float) or not 0<=minute<=duration):raise ValueError('Effective minute must fit the run')
                    if outcome=='approved' and minute is None:raise ValueError('Approved decisions require an effective minute')
                    details.update(request=reference,outcome=outcome,effective_minute=minute)
                with control.locked(exercise.RUNTIME):control.append(exercise.RUNTIME,action,user,details)
            else:raise ValueError('Unsupported action')
            self.send(200,{'message':'Recorded '+action})
        except RequestBodyTimeout:self.send(408,{'error':'Request body timed out; retry'})
        except (ValueError,TypeError,KeyError,OSError,sqlite3.Error) as error:self.send(400,{'error':str(error)})

# 8084 is deliberately outside the participant-published range (8080 CRL,
# 8081 IRIS, 8082 Guacamole, 8083 CTFd). The previous default of 8082 collided
# with Guacamole's loopback publish in deployment/expanded/compose.central.yaml
# whenever BIND_IP is left at its 127.0.0.1 default.
DEFAULT_PORT = 8084

def serve(port=DEFAULT_PORT,request_timeout=5.0,max_handlers=16):
    server=BoundedThreadingHTTPServer(('127.0.0.1',port),Handler,
                                      request_timeout=request_timeout,max_handlers=max_handlers)
    server.sessions={};server.lock=threading.Lock();server.attempts=[]
    return server

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--add-user');parser.add_argument('--port',type=int,default=DEFAULT_PORT);args=parser.parse_args()
    if args.add_user:provision(args.add_user)
    else:serve(args.port).serve_forever()
