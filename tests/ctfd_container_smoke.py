"""Execute inside the actual extended CTFd 3.7.7 image, using a disposable database."""
import concurrent.futures
import os
from unittest.mock import patch
from pathlib import Path

os.environ.update(DATABASE_URL='sqlite:////tmp/ctfd-smoke.sqlite',SECRET_KEY='disposable-ci-key-only-000000000000',
    UPLOAD_FOLDER='/tmp/uploads',LOG_FOLDER='/tmp/logs',RIDGE_CTFD_FILE='/tmp/ridge-ctfd-secret',
    IRIS_PUBLIC_URL='http://iris.invalid',CTFD_PUBLIC_URL='http://ctfd.invalid')
Path('/tmp/ridge-ctfd-secret').write_text('c'*40)

from CTFd import create_app
from CTFd.models import db,Awards,Teams,Users
from CTFd.utils import set_config

app=create_app()
with app.app_context():
    set_config('setup',True);set_config('user_mode','teams')
    team=Teams(name='Smoke team',password='disposable password')
    db.session.add(team);db.session.flush()
    user=Users(name='smoke-user',email='smoke@example.test',password='disposable password',type='user')
    user.team_id=team.id;db.session.add(user);db.session.commit()
    team_id=team.id;user_id=user.id

body={'key':'smoke-run:point:T01-Q1','kind':'point','payload':{
    'question':'T01-Q1','ctfd_team':team_id,'value':1,'event':'smoke-event'}}

def deliver(_):
    with app.test_client() as client:
        response=client.post('/silent-ridge/internal',json=body,headers={'X-Ridge-Key':'Bearer '+'c'*40})
        assert response.status_code==200,(response.status_code,response.get_data(as_text=True))
        return response.get_json()['id']

with concurrent.futures.ThreadPoolExecutor(4) as pool:
    assert len(set(pool.map(deliver,range(4))))==1
with app.app_context():
    assert Awards.query.count()==1
    assert Awards.query.first().value==1

# The award survives failed cache invalidation; a receipt retry must invalidate again.
from CTFd.plugins import ctfd_silent_ridge as plugin
retry_body={**body,'key':'smoke-run:point:T01-Q2'}
with app.test_client() as client:
    with patch.object(plugin,'invalidate_scores',side_effect=ConnectionError('cache unavailable')):
        try:
            response=client.post('/silent-ridge/internal',json=retry_body,headers={'X-Ridge-Key':'Bearer '+'c'*40})
            assert response.status_code==500
        except ConnectionError:
            pass  # Some test configurations propagate application exceptions.
    with patch.object(plugin,'invalidate_scores') as invalidated:
        response=client.post('/silent-ridge/internal',json=retry_body,headers={'X-Ridge-Key':'Bearer '+'c'*40})
        assert response.status_code==200
        invalidated.assert_called_once()
with app.app_context():
    assert Awards.query.count()==2

with app.test_client() as client:
    assert client.post('/silent-ridge/internal',json=body).status_code in (401,403)
    with client.session_transaction() as session:
        session.update(id=user_id,name='smoke-user',email='smoke@example.test',type='user',nonce='smoke-nonce')
    assert client.get('/api/v1/challenges').status_code==403
    assert client.post('/api/v1/challenges/attempt',json={'challenge_id':1,'submission':'anything'},
                       headers={'CSRF-Token':'smoke-nonce'}).status_code==403
    assert client.get('/silent-ridge/internal').status_code in (404,405)
print('Actual CTFd image: unique credits, retry race, authentication and stock API blocking passed.')
