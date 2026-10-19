"""CTFd 3.7.7 OSS plugin. Dedicated coached questions, globally unique credits.

Do not also create stock challenges for this run: stock solve semantics are per team.
"""
import hmac
import os
from urllib.parse import urlsplit
from urllib.error import HTTPError, URLError
from flask import abort, jsonify, make_response, redirect, render_template_string, request, session
from sqlalchemy.exc import IntegrityError
from CTFd.models import db, Awards
from CTFd.utils.decorators import authed_only
from CTFd.utils.user import get_current_user, is_admin
from ridge.transport import bridge, secret, TRANSPORT_ERRORS
from ridge.narrative import participant_context
from ridge.web import PAGE, queue_state
from ridge.registration import (RegistrationConfig, RegistrationError,
                                 RegistrationStore, desktop_handout)


class RidgeCredit(db.Model):
    __tablename__ = 'silent_ridge_credits'
    key = db.Column(db.String(200), primary_key=True)
    award_id = db.Column(db.Integer, db.ForeignKey('awards.id'), nullable=False)


REGISTRATION_PAGE = r'''
<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Operation Silent Ridge — team registration</title>
<style>
body{font:16px system-ui,sans-serif;max-width:960px;margin:2rem auto;padding:0 1rem;color:#17212b}
main{border:1px solid #ccd6df;border-radius:12px;padding:2rem;box-shadow:0 4px 18px #0001}
h1{margin-top:0}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:1rem}
.card{background:#f4f7fa;border-radius:8px;padding:1rem}.error{background:#fee9e7;color:#8c1d18;padding:1rem;border-radius:8px}
label{display:block;font-weight:600;margin:.8rem 0}.field{display:block;width:100%;box-sizing:border-box;padding:.65rem;border:1px solid #aab7c4;border-radius:6px;font-size:1rem}
button{margin-top:1rem;padding:.7rem 1.2rem;border:0;border-radius:6px;background:#1257a6;color:#fff;font-weight:700;cursor:pointer}
code{background:#eef1f4;padding:.15rem .3rem;border-radius:4px}.secret{font-family:ui-monospace,monospace;background:#fff6cf;padding:.15rem .3rem}
table{border-collapse:collapse;width:100%}td,th{border-bottom:1px solid #d7dee5;text-align:left;padding:.55rem}
</style></head><body><main>
{% if view == 'register' %}
<h1>Operation Silent Ridge</h1>
<p><strong>Team registration</strong></p>
<p>Welcome to the incident-response exercise. Register your team once. The event
will assign three isolated GUI workstations and create the CTFd, IRIS, and
Guacamole logins your team needs. Keep the retrieval link: it is your team's
persistent handout.</p>
<div class="grid">
  <div class="card"><strong>Browser services</strong><br>IRIS, CTFd, and Wazuh run from your own laptop browser.</div>
  <div class="card"><strong>Three GUI workstations</strong><br>Two Autopsy seats plus one Wireshark/Cutter/Linux seat.</div>
  <div class="card"><strong>Five seats</strong><br>Each team receives five participant CTFd accounts.</div>
</div>
{% if error %}<p class="error">{{ error }}</p>{% endif %}
<form method="post">
<input type="hidden" name="nonce" value="{{ nonce }}">
<label>Team name<input class="field" name="team_name" maxlength="48" required value="{{ team_name }}"></label>
<label>Captain / facilitator contact<input class="field" name="captain_name" maxlength="48" required value="{{ captain_name }}"></label>
<button type="submit">Reserve our team</button>
</form>
{% elif view == 'pending' %}
<h1>{{ registration.team_name }}</h1><p>Your team slot is reserved. The event host is starting your three workstations and creating the application accounts.</p>
<p>Status: <strong>{{ registration.status }}</strong>. Refresh this page in a few seconds.</p>
<p>Your retrieval path is <code>{{ retrieve_path }}</code>. Bookmark it.</p>
<meta http-equiv="refresh" content="5">
{% elif view == 'ready' %}
<h1>{{ registration.team_name }} — team handout</h1>
<p>Registration is complete. Bookmark this page. Do not post these passwords in a public chat.</p>
<h2>Browser services</h2>
<table><tr><th>Service</th><th>URL</th><th>Username</th><th>Password</th></tr>
<tr><td>IRIS</td><td><a href="{{ iris_url }}">{{ iris_url }}</a></td><td><code>{{ credentials.iris.username }}</code></td><td><span class="secret">{{ credentials.iris.password }}</span></td></tr>
<tr><td>CTFd team</td><td><a href="{{ ctfd_url }}">{{ ctfd_url }}</a></td><td><code>{{ credentials.ctfd.team }}</code></td><td><span class="secret">{{ credentials.ctfd.password }}</span></td></tr>
</table>
<h2>Participant CTFd seats</h2>
<table><tr><th>Seat</th><th>Username</th><th>Password</th></tr>
{% for member in credentials.ctfd.members %}<tr><td>{{ loop.index }}</td><td><code>{{ member.username }}</code></td><td><span class="secret">{{ member.password }}</span></td></tr>{% endfor %}
</table>
<h2>GUI workstations</h2>
<p>Log into Guacamole once with the account below. Each connection opens the role-specific desktop assigned to your team.</p>
<p>Guacamole username: <code>{{ credentials.guacamole.username }}</code><br>Password: <span class="secret">{{ credentials.guacamole.password }}</span><br><a href="{{ guac_url }}">{{ guac_url }}</a></p>
<table><tr><th>Desktop</th><th>Tools</th><th>Open</th></tr>
{% for desktop in registration.result.desktop_urls %}<tr><td>{{ desktop.name }}</td><td>{{ desktop.tools|join(', ') }}</td><td><a href="{{ desktop.url }}">Open connection</a></td></tr>{% endfor %}
</table>
{% else %}<h1>Registration unavailable</h1><p>{{ registration.error or 'The registration code is invalid.' }}</p>{% endif %}
</main></body></html>
'''


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
    registration_path = os.environ.get('RIDGE_REGISTRATION_DB', '/registration/registrations.sqlite')
    registration_store = RegistrationStore(
        registration_path,
        RegistrationConfig(
            max_teams=int(os.environ.get('RIDGE_REGISTRATION_MAX_TEAMS', '10')),
            members_per_team=int(os.environ.get('RIDGE_REGISTRATION_MEMBERS', '5'))))
    from .provision import register as register_provision
    register_provision(app)

    def identity():
        user = get_current_user()
        if user is None or user.team_id is None:
            abort(403)
        return user.team_id

    @app.before_request
    def protect_stock_routes():
        # Dedicated event instance: no alternate submission, attachment, hint or API path.
        if request.path.startswith('/api/v1/') and not is_admin():
            if request.path not in ('/api/v1/scoreboard', '/api/v1/scoreboard/top/10') or request.method != 'GET':
                abort(403)
        if request.path == '/challenges':
            return redirect('/silent-ridge')

    @app.route('/silent-ridge/register', methods=['GET', 'POST'])
    def ridge_register():
        """Public landing page and self-service team reservation."""
        # CTFd validates every form POST against session['nonce'] in its global
        # before-request hook.  Using a second registration-only nonce makes the
        # global check reject the request before this handler can validate it.
        # Reuse CTFd's nonce so the public form receives the same CSRF protection
        # as the rest of the application.
        session.setdefault('nonce', os.urandom(24).hex())
        error = ''
        team_name = request.form.get('team_name', '')
        captain_name = request.form.get('captain_name', '')
        if request.method == 'POST':
            if not hmac.compare_digest(request.form.get('nonce', ''),
                                       session.get('nonce', '!')):
                abort(403)
            try:
                created = registration_store.register(team_name, captain_name)
                return redirect(created['retrieve_path'])
            except RegistrationError as exc:
                error = str(exc)
        return render_template_string(REGISTRATION_PAGE, view='register', error=error,
                                      team_name=team_name, captain_name=captain_name,
                                      nonce=session['nonce'])

    @app.route('/silent-ridge/registration/<access_code>')
    def ridge_registration(access_code):
        try:
            registration = registration_store.get(access_code)
        except RegistrationError:
            registration = {'status': 'invalid', 'error': 'This registration link is invalid.'}
        if registration.get('status') == 'ready':
            private = registration_store.get(access_code, include_private=True)
            registration['result'] = registration.get('result') or {}
            credentials = private['credentials']
            return render_template_string(
                REGISTRATION_PAGE, view='ready', registration=registration,
                credentials=credentials, iris_url=os.environ['IRIS_PUBLIC_URL'],
                ctfd_url=os.environ['CTFD_PUBLIC_URL'],
                guac_url=os.environ.get('GUACAMOLE_PUBLIC_URL',
                                        os.environ.get('CTFD_PUBLIC_URL', '').rstrip('/') + ':8082'))
        if registration.get('status') in ('pending', 'provisioning'):
            return render_template_string(REGISTRATION_PAGE, view='pending',
                                          registration=registration,
                                          retrieve_path=request.path)
        return render_template_string(REGISTRATION_PAGE, view='error', registration=registration), 404

    @app.route('/silent-ridge', methods=['GET', 'POST'])
    @authed_only
    def ridge_questions():
        message = ''
        try:
            # CTFd's stock CSRF session does not guarantee a value for this
            # event-specific nonce on every authenticated session.  Generate
            # one before rendering or validating the form so a fresh team
            # browser never receives an empty hidden nonce and then gets a
            # misleading 403 on its first answer.
            session.setdefault('nonce', os.urandom(24).hex())
            team = identity()
            if request.method == 'POST':
                if not hmac.compare_digest(request.form.get('nonce', ''), session.get('nonce', '!')):
                    abort(403)
                action=request.form.get('action','answer')
                if action == 'unlock_hint':
                    bridge('ctfd', team, 'hint', question=request.form['question'])
                    message = 'Explicit walkthrough unlocked. Assisted scoring is active: this question is now worth 1 of 4 points.'
                elif action == 'answer':
                    result = bridge('ctfd', team, 'answer', question=request.form['question'], answer=request.form['answer'])
                    if result['correct']:
                        if result.get('assessment_published'):
                            message = ('Correct — %d point%s earned. Capstone complete: the final incident '
                                       'assessment and containment actions are now unlocked below.') % (
                                result['value'], '' if result['value'] == 1 else 's')
                        else:
                            message = 'Correct — %d point%s earned. Findings synchronization pending.' % (
                                result['value'], '' if result['value'] == 1 else 's')
                    else:
                        message = 'Not yet. Try the next free help level or unlock the explicit walkthrough.'
                else:
                    abort(400)
            snapshot = bridge('ctfd', team, 'snapshot')
            questions = bridge('ctfd', team, 'questions', question=request.args.get('question'))
            response = make_response(render_template_string(
                PAGE, lane='ctfd', snapshot=snapshot, questions=questions,
                queue=queue_state(snapshot),
                iris=os.environ['IRIS_PUBLIC_URL'], ctfd=os.environ['CTFD_PUBLIC_URL'], csrf=session['nonce'],
                message=message, story=participant_context(snapshot, questions),
                final_brief_url=os.environ.get('RIDGE_FINAL_BRIEF_URL','').strip()))
            # Claim and answer state is shared and changes outside the CTFd
            # process. Prevent a cached pre-claim page from hiding the current
            # ticket's question forms; the status poll already uses no-store.
            response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Vary'] = 'Cookie'
            return response
        except HTTPError as exc:
            return 'Question unavailable or exercise paused. Return to the incident queue.', exc.code
        except TRANSPORT_ERRORS:
            return 'Connection interrupted. Accepted answers are retained; retry shortly.', 503

    @app.route('/silent-ridge/status')
    @authed_only
    def ridge_status():
        try:
            return jsonify(bridge('ctfd', identity(), 'snapshot'))
        except TRANSPORT_ERRORS:
            return jsonify(error='Questions temporarily unavailable'), 503

    @app.route('/silent-ridge/internal', methods=['POST'])
    def ridge_credit():
        if not hmac.compare_digest(request.headers.get('X-Ridge-Key', ''), 'Bearer ' + secret('RIDGE_CTFD')):
            abort(401)
        body = request.get_json(); key = body['key']; p = body['payload']
        if body['kind'] == 'preflight':
            from CTFd.models import Teams
            from CTFd.utils import get_config
            if get_config('user_mode') != 'teams':
                abort(409)
            identities = []
            for identifier in p['identities']:
                team = db.session.get(Teams, int(identifier))
                if team is None or team.banned or team.hidden:
                    abort(409)
                identities.append({'id': str(team.id), 'name': team.name})
            db.session.query(RidgeCredit).limit(1).all()
            return jsonify(ready=True, identities=identities)
        if body['kind'] == 'export':
            credits = db.session.query(RidgeCredit).all()
            awards = db.session.query(Awards).join(RidgeCredit, RidgeCredit.award_id == Awards.id).all()
            return jsonify(credits=[dict(key=c.key, award_id=c.award_id) for c in credits],
                awards=[dict(id=a.id, team_id=a.team_id, value=a.value, name=a.name,
                             description=a.description, date=a.date.isoformat()) for a in awards])
        if body['kind'] != 'point' or p['value'] not in (1, 4) or len(key) > 200:
            abort(400)
        existing = db.session.get(RidgeCredit, key)
        if existing:
            invalidate_scores()
            return jsonify(id=existing.award_id)
        try:
            award = Awards(team_id=p['ctfd_team'], name=p['question'],
                           description='Silent Ridge accepted answer ' + p['event'],
                           value=p['value'], category='Silent Ridge')
            db.session.add(award); db.session.flush()
            db.session.add(RidgeCredit(key=key, award_id=award.id))
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            existing = db.session.get(RidgeCredit, key)
            if existing:
                invalidate_scores()
                return jsonify(id=existing.award_id)
            raise
        invalidate_scores()
        return jsonify(id=award.id)
    ridge_credit._bypass_csrf = True  # Machine endpoint authenticates its own distinct secret.


def invalidate_scores():
    # Retry invalidation even when the receipt already exists after an ambiguous commit.
    from CTFd.cache import clear_standings
    clear_standings()
