"""Internal-only authenticated integration API. No participant-accessible port."""
import argparse
import hmac
import json
import os
import threading
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
        self.send(200 if self.path == '/health' else 404, {'service':'silent-ridge'})

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
                getattr(state, action)(team, data['ticket'])
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
    state.snapshot()  # Refuse to report healthy against absent/uninitialized state.
    server=ThreadingHTTPServer((args.host,args.port),Handler)
    server.state=state
    server.secrets={app:secret('RIDGE_'+app.upper()) for app in ('iris','ctfd')}
    if server.secrets['iris'] == server.secrets['ctfd']:
        raise ValueError('Use distinct application credentials')
    stop=threading.Event()
    def sync():
        delay=1
        while not stop.is_set():
            try:
                success=state.sync_once(remote_sink)
            except Exception:
                success=False
            delay=1 if success else min(delay*2,30)
            stop.wait(0.05 if success else delay)
    threading.Thread(target=sync,daemon=True).start()
    try:
        server.serve_forever()
    finally:
        stop.set()
        server.server_close()


if __name__=='__main__':
    main()
