"""Private service transport. Use local CA HTTPS across untrusted networks."""
import json
import os
from pathlib import Path
from urllib.request import Request, urlopen


def secret(name):
    value = Path(os.environ[name+'_FILE']).read_text().strip()
    if len(value) < 32:
        raise ValueError('Service secret must contain at least 32 characters')
    return value


def post(url, token, body, header='Authorization'):
    request = Request(url, json.dumps(body).encode(),
                      {header:'Bearer '+token, 'Content-Type':'application/json'})
    with urlopen(request, timeout=8) as response:
        return json.load(response)


def bridge(application, identity, action, **payload):
    return post(os.environ['RIDGE_URL']+'/action', secret('RIDGE_'+application.upper()),
                dict(payload, application=application, identity=str(identity), action=action))


def remote_sink(kind, key, payload, con):
    application = 'CTFD' if kind == 'point' else 'IRIS'
    if kind != 'ticket' and application == 'IRIS':
        payload = dict(payload, iris_id=con.execute('SELECT iris_id FROM tickets WHERE id=?',
                                                   (payload['ticket'],)).fetchone()[0])
    result=post(os.environ[application+'_URL']+'/silent-ridge/internal', secret('RIDGE_'+application),
                {'key':key, 'kind':kind, 'payload':payload}, header='X-Ridge-Key')['id']
    if kind=='ticket':
        from ridge.evidence_release import publish
        publish(payload['ticket'])
    return result
