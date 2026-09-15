"""CTFd 3.7.7 OSS plugin. Dedicated coached questions, globally unique credits.

Do not also create stock challenges for this run: stock solve semantics are per team.
"""
import hmac
import os
from urllib.error import HTTPError, URLError
from flask import abort, jsonify, redirect, render_template_string, request, session
from sqlalchemy.exc import IntegrityError
from CTFd.models import db, Awards
from CTFd.utils.decorators import authed_only
from CTFd.utils.user import get_current_user, is_admin
from ridge.transport import bridge, secret, TRANSPORT_ERRORS
from ridge.web import PAGE


class RidgeCredit(db.Model):
    __tablename__='silent_ridge_credits'
    key=db.Column(db.String(200),primary_key=True)
    award_id=db.Column(db.Integer,db.ForeignKey('awards.id'),nullable=False)


def load(app):
    with app.app_context():
        db.create_all()

    def identity():
        user=get_current_user()
        if user is None or user.team_id is None:
            abort(403)
        return user.team_id

    @app.before_request
    def protect_stock_routes():
        # Dedicated event instance: no alternate submission, attachment, hint or API path.
        if request.path.startswith('/api/v1/') and not is_admin():
            if request.path not in ('/api/v1/scoreboard','/api/v1/scoreboard/top/10') or request.method!='GET':
                abort(403)
        if request.path=='/challenges':
            return redirect('/silent-ridge')

    @app.route('/silent-ridge',methods=['GET','POST'])
    @authed_only
    def ridge_questions():
        message=''
        try:
            team=identity()
            if request.method=='POST':
                if not hmac.compare_digest(request.form.get('nonce',''),session.get('nonce','!')):
                    abort(403)
                result=bridge('ctfd',team,'answer',question=request.form['question'],answer=request.form['answer'])
                message='Correct — one point earned. Findings synchronization pending.' if result['correct'] else 'Not yet. Try the next help level.'
            snapshot=bridge('ctfd',team,'snapshot')
            questions=bridge('ctfd',team,'questions',question=request.args.get('question'))
            return render_template_string(PAGE,lane='ctfd',snapshot=snapshot,questions=questions,
                iris=os.environ['IRIS_PUBLIC_URL'],ctfd=os.environ['CTFD_PUBLIC_URL'],csrf=session['nonce'],message=message)
        except HTTPError as exc:
            return 'Question unavailable or exercise paused. Return to the incident queue.',exc.code
        except TRANSPORT_ERRORS:
            return 'Connection interrupted. Accepted answers are retained; retry shortly.',503

    @app.route('/silent-ridge/status')
    @authed_only
    def ridge_status():
        try:
            return jsonify(bridge('ctfd',identity(),'snapshot'))
        except TRANSPORT_ERRORS:
            return jsonify(error='Questions temporarily unavailable'),503

    @app.route('/silent-ridge/internal',methods=['POST'])
    def ridge_credit():
        if not hmac.compare_digest(request.headers.get('X-Ridge-Key',''),'Bearer '+secret('RIDGE_CTFD')):
            abort(401)
        body=request.get_json(); key=body['key']; p=body['payload']
        if body['kind']=='preflight':
            from CTFd.models import Teams
            from CTFd.utils import get_config
            if get_config('user_mode')!='teams':
                abort(409)
            identities=[]
            for identifier in p['identities']:
                team=db.session.get(Teams,int(identifier))
                if team is None or team.banned or team.hidden:
                    abort(409)
                identities.append({'id':str(team.id),'name':team.name})
            db.session.query(RidgeCredit).limit(1).all()
            return jsonify(ready=True,identities=identities)
        if body['kind']=='export':
            credits=db.session.query(RidgeCredit).all()
            awards=db.session.query(Awards).join(RidgeCredit,RidgeCredit.award_id==Awards.id).all()
            return jsonify(credits=[dict(key=c.key,award_id=c.award_id) for c in credits],
                awards=[dict(id=a.id,team_id=a.team_id,value=a.value,name=a.name,description=a.description,date=a.date.isoformat()) for a in awards])
        if body['kind']!='point' or p['value']!=1 or len(key)>200:
            abort(400)
        existing=db.session.get(RidgeCredit,key)
        if existing:
            invalidate_scores()
            return jsonify(id=existing.award_id)
        try:
            award=Awards(team_id=p['ctfd_team'],name=p['question'],description='Silent Ridge accepted answer '+p['event'],
                         value=1,category='Silent Ridge')
            db.session.add(award);db.session.flush()
            db.session.add(RidgeCredit(key=key,award_id=award.id))
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            existing=db.session.get(RidgeCredit,key)
            if existing:
                invalidate_scores()
                return jsonify(id=existing.award_id)
            raise
        invalidate_scores()
        return jsonify(id=award.id)
    ridge_credit._bypass_csrf=True  # Machine endpoint authenticates its own distinct secret.


def invalidate_scores():
    # Retry invalidation even when the receipt already exists after an ambiguous commit.
    from CTFd.cache import clear_standings
    clear_standings()
