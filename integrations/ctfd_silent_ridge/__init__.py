"""CTFd 3.7.7 OSS plugin. Dedicated coached questions, globally unique credits.

Do not also create stock challenges for this run: stock solve semantics are per team.
"""
import hmac
import os
from urllib.parse import urlsplit
from urllib.error import HTTPError, URLError
from flask import abort, jsonify, redirect, render_template_string, request, session, Response
from sqlalchemy.exc import IntegrityError
from CTFd.models import db, Awards
from CTFd.utils.decorators import authed_only
from CTFd.utils.user import get_current_user, is_admin
from ridge.network_map import render as render_network_map
from ridge.transport import bridge, secret, TRANSPORT_ERRORS
from ridge.narrative import participant_context
from ridge.scenario_contract import load as load_contract
from ridge.web import PAGE, network_map_link
from ridge.web_narrative import context as narrative_context


class RidgeCredit(db.Model):
    __tablename__='silent_ridge_credits'
    key=db.Column(db.String(200),primary_key=True)
    award_id=db.Column(db.Integer,db.ForeignKey('awards.id'),nullable=False)


def load(app):
    # Cookies are scoped by host/path, not port. IRIS and CTFd share a host in
    # the local kit, so a stock "session" cookie breaks CTFd's CSRF nonce.
    app.config['SESSION_COOKIE_NAME'] = os.environ.get(
        'CTFD_SESSION_COOKIE_NAME', 'silent_ridge_ctfd_session')
    public_scheme = urlsplit(os.environ['CTFD_PUBLIC_URL']).scheme.lower()
    if public_scheme not in ('http', 'https'):
        raise ValueError('CTFD_PUBLIC_URL must use http or https')
    secure_setting = os.environ.get('CTFD_SESSION_COOKIE_SECURE')
    if secure_setting is None:
        secure = public_scheme == 'https'
    elif secure_setting.lower() in ('true', 'false'):
        secure = secure_setting.lower() == 'true'
    else:
        raise ValueError('CTFD_SESSION_COOKIE_SECURE must be true or false')
    if secure != (public_scheme == 'https'):
        raise ValueError('CTFD_SESSION_COOKIE_SECURE must match CTFD_PUBLIC_URL scheme')
    app.config['SESSION_COOKIE_SECURE'] = secure
    with app.app_context():
        db.create_all()
        # Existing installed kits may already have identities and awards, so
        # don't depend on a fresh provisioning pass to repair the stock
        # scoreboard's missing visibility settings.
        from CTFd.utils import set_config
        set_config('score_visibility', 'private')
        set_config('account_visibility', 'private')
    from .provision import register as register_provision
    register_provision(app)

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
            # Two narrative implementations reach this one template on purpose:
            # ``story`` is the organizer-approved markup, the narrative context is
            # the validated layer that adds the sections that markup has no
            # equivalent for. Neither is dropped until the organizer chooses.
            return render_template_string(PAGE,story=participant_context(snapshot,questions),
                **narrative_context(load_contract(),snapshot,questions),
                lane='ctfd',snapshot=snapshot,network_map=network_map_link(snapshot),
                iris=os.environ['IRIS_PUBLIC_URL'],
                ctfd=os.environ['CTFD_PUBLIC_URL'],csrf=session['nonce'],message=message)
        except HTTPError as exc:
            return 'Question unavailable or exercise paused. Return to the incident queue.',exc.code
        except TRANSPORT_ERRORS:
            return 'Connection interrupted. Accepted answers are retained; retry shortly.',503

    @app.route('/silent-ridge/network-map')
    @authed_only
    def ridge_network_map():
        # The controller refuses this until T01 is closed, so the page cannot link
        # to a view that would hand over the destination before the ticket is answered.
        try:
            bridge('ctfd',identity(),'network_map')
        except HTTPError as exc:
            return 'The network map unlocks once T01 is closed.',exc.code
        except TRANSPORT_ERRORS:
            return 'Network map temporarily unavailable. Accepted answers are retained; retry shortly.',503
        return Response(render_network_map(),mimetype='text/html')

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
