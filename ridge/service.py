"""Internal-only authenticated integration API. No participant-accessible port."""
import argparse
import hmac
import json
import os
import threading
import time
import logging
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from ridge.state import State, Conflict
from ridge.transport import secret, remote_sink


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def send(self, code, body):
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header('Content-Type','application/json')
        self.send_header('Content-Length',str(len(data)))
        self.send_header('Cache-Control','no-store')
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path != '/health':
            return self.send(404, {})
        try:
            status = self.server.state.diagnostics()
            alive = time.monotonic()-self.server.worker_heartbeat < 45 or status['active_leases'] > 0
            healthy = alive and not status['failures']
            self.send(200 if healthy else 503, {'service':'silent-ridge', 'healthy':healthy})
        except Exception:
            self.send(503, {'service':'silent-ridge', 'healthy':False})

    def do_POST(self):
        try:
            if self.path != '/action':
                return self.send(404, {})
            count = int(self.headers.get('Content-Length', '0'))
            if not 0 < count <= 8192:
                return self.send(413, {'error':'Invalid request size'})
            data = json.loads(self.rfile.read(count))
            app = data.get('application')
            if app not in ('iris','ctfd') or not hmac.compare_digest(
                    self.headers.get('Authorization',''), 'Bearer '+self.server.secrets[app]):
                return self.send(401, {'error':'Authentication required'})
            state = self.server.state
            team = state.identity(app, data['identity'])
            action = data['action']
            if action == 'snapshot':
                return self.send(200, dict(state.snapshot(), team=team))
            if app == 'iris' and action in ('claim','release'):
                if action == 'release':
                    state.release(team, data['ticket'], data['generation'])
                else:
                    state.claim(team, data['ticket'], data['generation'])
                return self.send(200, {'ok':True})
            if app == 'ctfd' and action == 'questions':
                return self.send(200, state.questions(team, data.get('question')))
            if app == 'ctfd' and action == 'answer':
                return self.send(200, state.answer(team, data['question'], data['answer']))
            self.send(403, {'error':'Action not allowed for this application'})
        except PermissionError as exc:
            self.send(403, {'error':str(exc)})
        except Conflict as exc:
            self.send(409, {'error':str(exc)})
        except (ValueError,KeyError,TypeError):
            self.send(400, {'error':'Invalid request'})
        except Exception:
            self.send(503, {'error':'Service unavailable; accepted work is retained'})


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--host',default='127.0.0.1')
    parser.add_argument('--port',type=int,default=8091)
    args=parser.parse_args()
    state=State(os.environ['RIDGE_STATE'])
    state.diagnostics()  # Refuse old/uninitialized schemas before starting the worker.
    server=ThreadingHTTPServer((args.host,args.port),Handler)
    server.state=state
    server.secrets={app:secret('RIDGE_'+app.upper()) for app in ('iris','ctfd')}
    if server.secrets['iris'] == server.secrets['ctfd']:
        raise ValueError('Use distinct application credentials')
    stop=threading.Event()
    server.worker_heartbeat=time.monotonic()
    def sync():
        while not stop.is_set():
            try:
                success=state.sync_once(remote_sink)
            except Exception as exc:
                logging.error('Synchronization failed: %s', type(exc).__name__)
                success=False
            server.worker_heartbeat=time.monotonic()
            stop.wait(0.05 if success else 1)
    threading.Thread(target=sync,daemon=True).start()
    try:
        server.serve_forever()
    finally:
        stop.set()
        server.server_close()


if __name__=='__main__':
    main()
