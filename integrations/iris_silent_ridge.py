"""Pinned IRIS 2.4.20 extension: native tasks/comments plus atomic delivery receipts.

Import and call install(app) after `from app import views` in app/__init__.py.
Participant accounts must have read-only access to the one exercise case.
Ownership mutations use the bridge; native task edits remain controller-only.
"""
import hmac
import os
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from flask import abort, jsonify, render_template_string, request
from flask_login import current_user, login_required
from flask_wtf.csrf import generate_csrf, validate_csrf
from wtforms.validators import ValidationError
from sqlalchemy.exc import IntegrityError
from app import db
from app.models.models import CaseTasks, Comments, TaskComments
from ridge.transport import bridge, secret, TRANSPORT_ERRORS
from ridge.web import PAGE


class RidgeReceipt(db.Model):
    __tablename__='silent_ridge_receipts'
    key=db.Column(db.String(200),primary_key=True)
    remote=db.Column(db.BigInteger,nullable=False)


def install(app):
    @app.cli.command('silent-ridge-init')
    def initialize():
        RidgeReceipt.__table__.create(db.engine,checkfirst=True)

    @app.route('/silent-ridge',methods=['GET','POST'])
    @login_required
    def ridge_queue():
        try:
            if request.method=='POST':
                try:
                    validate_csrf(request.form.get('csrf_token'))
                except ValidationError:
                    abort(403)
                action=request.form.get('action')
                if action not in ('claim','release'):
                    abort(400)
                payload={'ticket':request.form['ticket'],'generation':int(request.form['generation'])}
                bridge('iris',current_user.id,action,**payload)
            snapshot=bridge('iris',current_user.id,'snapshot')
            return render_template_string(PAGE,lane='iris',snapshot=snapshot,
                iris=os.environ['IRIS_PUBLIC_URL'],ctfd=os.environ['CTFD_PUBLIC_URL'],
                csrf=generate_csrf(),case=os.environ['RIDGE_IRIS_CASE'],message='')
        except HTTPError as exc:
            return 'Ticket unavailable, another team claimed it, or exercise paused. Reload the queue.',exc.code
        except TRANSPORT_ERRORS:
            return 'Queue connection interrupted. Existing work is retained; retry shortly.',503

    @app.route('/silent-ridge/status')
    @login_required
    def ridge_status():
        try:
            return jsonify(bridge('iris',current_user.id,'snapshot'))
        except TRANSPORT_ERRORS:
            return jsonify(error='Queue temporarily unavailable'),503

    @app.route('/silent-ridge/internal',methods=['POST'])
    def ridge_event():
        if not hmac.compare_digest(request.headers.get('X-Ridge-Key',''),'Bearer '+secret('RIDGE_IRIS')):
            abort(401)
        body=request.get_json();key=body['key'];kind=body['kind'];p=body['payload']
        if kind=='preflight':
            from app.models.authorization import User, UserCaseEffectiveAccess, CaseAccessLevel
            from app.models.cases import Cases
            from app.models.models import TaskStatus
            case=int(os.environ['RIDGE_IRIS_CASE'])
            if db.session.get(Cases,case) is None:
                abort(409)
            status_ids=[int(os.environ['RIDGE_IRIS_'+value+'_STATUS']) for value in ('OPEN','CLOSED')]
            if len(set(status_ids))!=2 or any(db.session.get(TaskStatus,value) is None for value in status_ids):
                abort(409)
            service=db.session.get(User,int(os.environ['RIDGE_IRIS_SERVICE_USER']))
            if service is None or not service.active:
                abort(409)
            identities=[]
            for identifier in p['identities']:
                user=db.session.get(User,int(identifier))
                access=db.session.query(UserCaseEffectiveAccess).filter_by(user_id=int(identifier),case_id=case).one_or_none()
                if user is None or not user.active or access is None or access.access_level!=CaseAccessLevel.read_only.value:
                    abort(409)
                identities.append({'id':str(user.id),'name':user.user})
            db.session.query(RidgeReceipt).limit(1).all()
            return jsonify(ready=True,identities=identities)
        if kind=='export':
            case=int(os.environ['RIDGE_IRIS_CASE'])
            tasks=db.session.query(CaseTasks).filter_by(task_case_id=case).all()
            comments=db.session.query(Comments).filter_by(comment_case_id=case).all()
            links=db.session.query(TaskComments).join(CaseTasks,TaskComments.comment_task_id==CaseTasks.id).filter(CaseTasks.task_case_id==case).all()
            def serialize(row):
                return {c.name:(getattr(row,c.name).isoformat() if isinstance(getattr(row,c.name),datetime) else str(getattr(row,c.name)) if c.name.endswith('uuid') else getattr(row,c.name)) for c in row.__table__.columns}
            return jsonify(tasks=[serialize(t) for t in tasks],comments=[serialize(c) for c in comments],
                           links=[serialize(link) for link in links],receipts=[dict(key=r.key,remote=r.remote) for r in db.session.query(RidgeReceipt).all()])
        if kind not in ('ticket','finding','close','ownership') or len(key)>200:
            abort(400)
        receipt=db.session.get(RidgeReceipt,key)
        if receipt:
            return jsonify(id=receipt.remote)
        case=int(os.environ['RIDGE_IRIS_CASE']);user=int(os.environ['RIDGE_IRIS_SERVICE_USER'])
        # Pinned IRIS columns store naive UTC; normalize explicitly at this ORM boundary.
        stamp=datetime.now(timezone.utc).replace(tzinfo=None)
        try:
            if kind=='ticket':
                task=CaseTasks(task_title=p['ticket']+' · '+p['title'],
                    task_description='Choose ownership through /silent-ridge. Correct answers add findings automatically.',
                    task_tags='Silent Ridge',task_case_id=case,task_status_id=int(os.environ['RIDGE_IRIS_OPEN_STATUS']),
                    task_open_date=stamp,task_last_update=stamp,task_userid_open=user,task_userid_update=user,
                    custom_attributes={},modification_history={})
                db.session.add(task);db.session.flush();remote=task.id
            else:
                task=db.session.query(CaseTasks).filter_by(id=p['iris_id'],task_case_id=case).one()
                task.task_last_update=stamp;task.task_userid_update=user
                if kind=='close':
                    task.task_status_id=int(os.environ['RIDGE_IRIS_CLOSED_STATUS'])
                    task.task_close_date=stamp;task.task_userid_close=user;remote=task.id
                else:
                    text=('Ownership: '+str(p['team'] or 'available')) if kind=='ownership' else (
                        p['text']+'\nEvidence: '+', '.join(p['evidence'])+'\nLimitation: '+p['limitation']+
                        '\nQuestion: '+p['question']+'\nSolved by: '+p['team_name']+'\nUTC: '+p['timestamp']+
                        '\nAnswer event: '+p['event'])
                    comment=Comments(comment_text=text,comment_date=stamp,comment_update_date=stamp,
                                     comment_user_id=user,comment_case_id=case)
                    db.session.add(comment);db.session.flush()
                    db.session.add(TaskComments(comment_id=comment.comment_id,comment_task_id=task.id))
                    remote=comment.comment_id
            db.session.add(RidgeReceipt(key=key,remote=remote));db.session.commit()
        except IntegrityError:
            db.session.rollback()
            receipt=db.session.get(RidgeReceipt,key)
            if receipt:
                return jsonify(id=receipt.remote)
            raise
        return jsonify(id=remote)
    if 'csrf' in app.extensions:
        app.extensions['csrf'].exempt(ridge_event)
