"""CTFd 3.7.7 OSS plugin. Dedicated coached questions with per-team credit.

Do not also create stock challenges for this run: stock solve semantics are per team.
"""
import hmac
import json
import os
import time
from pathlib import Path
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
from ridge.participant_handout import credential_handout_text


WAZUH_DISCOVER_PATH = (
    "/app/data-explorer/discover#?"
    "_g=(filters:!(),refreshInterval:(pause:!t,value:0),"
    "time:(from:'2026-10-15T08:00:00.000Z',to:'2026-10-15T10:30:00.000Z'))&"
    "_q=(filters:!(),query:(language:kuery,query:''))"
)

REGISTRATION_WORKER_HEARTBEAT_MAX_AGE = 15


def _registration_worker_ready(registration_path, *, now=None):
    """Fail closed unless the host worker recently published shared readiness."""
    configured = os.environ.get('RIDGE_REGISTRATION_WORKER_HEARTBEAT')
    heartbeat_path = (Path(configured) if configured else
                      Path(registration_path).parent / 'registration-worker-heartbeat.json')
    try:
        heartbeat = json.loads(heartbeat_path.read_text(encoding='utf-8'))
        updated = float(heartbeat['updated'])
        age = (time.time() if now is None else float(now)) - updated
        return heartbeat.get('ready') is True and -5 <= age < REGISTRATION_WORKER_HEARTBEAT_MAX_AGE
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        return False


def participant_wazuh_url(base_url):
    """Land participants in the prepared Discover view, not the admin wizard."""
    return base_url.rstrip('/') + WAZUH_DISCOVER_PATH


def _private_handout_response(response):
    """Prevent browsers and intermediaries from retaining credential pages."""
    response.headers['Cache-Control'] = 'no-store, private'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Robots-Tag'] = 'noindex, nofollow'
    return response


class RidgeCredit(db.Model):
    __tablename__ = 'silent_ridge_credits'
    key = db.Column(db.String(200), primary_key=True)
    award_id = db.Column(db.Integer, db.ForeignKey('awards.id'), nullable=False)


REGISTRATION_PAGE = r'''
<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Operation Silent Ridge — team registration</title>
<style>
body{font:16px system-ui,sans-serif;max-width:960px;margin:2rem auto;padding:0 1rem;color:#17212b}
main{border:1px solid #ccd6df;border-radius:12px;padding:2rem;box-shadow:0 4px 18px #0001}
h1{margin-top:0}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:1rem}
.card{background:#f4f7fa;border-radius:8px;padding:1rem}.error{background:#fee9e7;color:#8c1d18;padding:1rem;border-radius:8px}
.start{background:#eaf2fb;border-left:5px solid #1257a6;border-radius:8px;padding:1rem 1.25rem;margin:1.25rem 0}
.start h2{margin-top:0}.start ol{padding-left:1.4rem}.start li{margin:.65rem 0;line-height:1.45}
.notice{background:#fff6cf;border-radius:8px;padding:.85rem 1rem;margin:1rem 0}.recovery{background:#e8f5ec;border-left:5px solid #287a3d;border-radius:8px;padding:1rem 1.25rem;margin:1rem 0}.recovery p{overflow-wrap:anywhere}.compact li{margin:.45rem 0}
label{display:block;font-weight:600;margin:.8rem 0}.field{display:block;width:100%;box-sizing:border-box;padding:.65rem;border:1px solid #aab7c4;border-radius:6px;font-size:1rem}
button,.button{display:inline-block;margin-top:1rem;padding:.7rem 1.2rem;border:0;border-radius:6px;background:#1257a6;color:#fff;font-weight:700;cursor:pointer;text-decoration:none}
code{background:#eef1f4;padding:.15rem .3rem;border-radius:4px}.secret{font-family:ui-monospace,monospace;background:#fff6cf;padding:.15rem .3rem}
table{border-collapse:collapse;width:100%}td,th{border-bottom:1px solid #d7dee5;text-align:left;padding:.55rem}.table-wrap{overflow-x:auto}.copy{margin:.15rem;padding:.25rem .5rem;background:#46596b}.actions{display:flex;gap:.7rem;flex-wrap:wrap;align-items:center}@media print{button,.no-print{display:none}main{border:0;box-shadow:none}}
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
<section class="start">
  <h2>Start here</h2>
  <ol>
    <li><strong>Register once.</strong> One captain enters the team name, a contact name, and the enrollment code below.</li>
    <li><strong>Save the private handout.</strong> Bookmark its retrieval link and use <em>Print / save handout</em>. It is the way back to every generated login.</li>
    <li><strong>Use IRIS for ownership and shared findings.</strong> Claim up to three tickets in the IRIS Incident queue. IRIS records what your team is working and receives verified findings; its native task status controls are read-only.</li>
    <li><strong>Use CTFd for the investigation workflow.</strong> Open the claimed tickets' questions, hints, answer forms, and scoring in CTFd. Correct answers publish findings back to IRIS.</li>
    <li><strong>Use Guacamole only for investigation tools.</strong> Open the three team desktops for Autopsy, Wireshark, Cutter, and the evidence files. Do not browse ordinary websites inside those desktops.</li>
    <li><strong>Repeat the investigation loop.</strong> Claim in IRIS, investigate the named evidence, answer in CTFd, and review the verified finding that publishes back to IRIS.</li>
  </ol>
</section>
<div class="grid">
  <div class="card"><strong>Scoring and help</strong><br>Wrong answers cost nothing. Help 1 and Help 2 are free. Help 3 gives the full walkthrough and reduces that question from 4 points to 1.</div>
  <div class="card"><strong>Read-only work</strong><br>Do not execute recovered programs, scan or contact external systems, or change the original evidence.</div>
  <div class="card"><strong>Need a facilitator?</strong><br>Raise a hand for a lost retrieval link, failed login, stuck desktop, or service outage. Your accepted answers are retained.</div>
</div>
{% if error %}<p class="error">{{ error }}</p>{% endif %}
{% if not registration_open and not error %}<p class="error"><strong>Team setup is temporarily unavailable.</strong> Please wait a minute and try again. If this message remains, raise your hand for a facilitator. Do not submit a second registration.</p>{% endif %}
<h2>Register your team</h2>
<form method="post">
<input type="hidden" name="nonce" value="{{ nonce }}">
<label>Team name<input class="field" name="team_name" maxlength="48" required value="{{ team_name }}"></label>
<label>Captain / facilitator contact<input class="field" name="captain_name" maxlength="48" required value="{{ captain_name }}"></label>
<label>Event enrollment code<input class="field" name="enrollment_code" maxlength="64" required autocomplete="one-time-code"></label>
<button type="submit"{% if not registration_open %} disabled aria-disabled="true"{% endif %}>Reserve our team</button>
</form>
{% elif view == 'pending' %}
<h1>{{ registration.team_name }}</h1><p>Your team slot is reserved. The event host is starting your three workstations and creating the application accounts.</p>
<p>Status: <strong id="registration-status">{{ registration.status }}</strong>. This page will update when provisioning finishes.</p>
<section class="recovery"><h2>Save your private return link now</h2><p><a href="{{ retrieve_url }}">{{ retrieve_url }}</a></p><p>This unguessable link is the only participant-facing way back to your generated credentials. Bookmark it or copy it somewhere private.</p></section>
<div class="actions"><button type="button" onclick="copyValue({{ retrieve_url|tojson }},'pending-copy-status')">Copy private return link</button><button type="button" onclick="location.reload()">Check now</button><span id="pending-copy-status" role="status"></span></div><script>async function copyValue(value,statusId){await navigator.clipboard.writeText(value);document.getElementById(statusId).textContent='Copied.';}setInterval(async()=>{try{const r=await fetch({{ status_url|tojson }},{cache:'no-store'}),s=await r.json();document.getElementById('registration-status').textContent=s.status;if(!['pending','provisioning'].includes(s.status))location.reload();}catch(e){}},5000);</script>
{% elif view == 'needs_operator' %}
<h1>{{ registration.team_name }} — facilitator assistance needed</h1>
<p>Your team registration is saved, but automated setup could not finish. <strong>Raise your hand for a facilitator.</strong> Do not register again.</p>
<section class="recovery"><h2>Keep your private return link</h2><p><a href="{{ retrieve_url }}">{{ retrieve_url }}</a></p><p>Bookmark or copy this link. Return to it after a facilitator repairs your team setup.</p></section>
<div class="actions"><button type="button" onclick="copyValue({{ retrieve_url|tojson }},'operator-copy-status')">Copy private return link</button><button type="button" onclick="location.reload()">Check again</button><span id="operator-copy-status" role="status"></span></div>
<script>async function copyValue(value,statusId){await navigator.clipboard.writeText(value);document.getElementById(statusId).textContent='Copied.';}</script>
{% elif view == 'ready' %}
<h1>{{ registration.team_name }} — Team Handout</h1>
<p>Registration is complete. Do not post this page, its link, or these passwords in a public chat.</p>
<section class="recovery"><h2>Your permanent private return link</h2><p><a href="{{ retrieve_url }}">{{ retrieve_url }}</a></p><p>Bookmark this link. Anyone who has it can read your team credentials.</p></section>
<div class="actions no-print"><button type="button" onclick="copyValue({{ retrieve_url|tojson }},'copy-status')">Copy return link</button><a class="button" href="{{ download_url }}" download>Download private handout</a><button type="button" onclick="window.print()">Print / save handout</button><button type="button" onclick="copyAll()">Copy labelled handout</button><span id="copy-status" role="status"></span></div>
<section class="start">
  <h2>Your first five moves</h2>
  <ol>
    <li>Every participant chooses one personal CTFd seat below and signs in. Do not use the IRIS team login in CTFd.</li>
    <li>One teammate opens IRIS with the team login. IRIS controls ticket ownership and displays the team's shared verified findings; CTFd holds the questions, hints, answers, and scoring.</li>
    <li>Open the prepared Wazuh view in a normal laptop browser. Use its historical time range when a question names Wazuh.</li>
    <li>Open Guacamole, divide the three desktop connections across the team, and use them only for the evidence tools.</li>
    <li>Claim up to three available IRIS tickets, open their questions in CTFd, investigate the named evidence, and submit only the requested value.</li>
  </ol>
</section>
<section class="start" aria-labelledby="delegation-title">
  <h2 id="delegation-title">Divide the work before anyone starts</h2>
  <p><strong>The captain is not a required technical role.</strong> Any teammate with this private handout can take over coordination. Say the assignments out loud and keep the handout open on at least two team laptops.</p>
  <div class="grid">
    <div class="card"><strong>Person 1 — queue coordinator</strong><br>Open IRIS with the shared team login. Claim up to three tickets, announce each ticket ID and assigned analyst, watch ownership, and claim replacements as tickets finish.</div>
    <div class="card"><strong>Person 2 — network and Wazuh analyst</strong><br>Take one Guacamole desktop. Start with tickets naming Wireshark or Wazuh. Follow the ticket's exact filter, query, and evidence path.</div>
    <div class="card"><strong>Person 3 — disk and endpoint analyst</strong><br>Take one Guacamole desktop. Start with tickets naming Autopsy and use the prepared case and evidence path shown on the ticket.</div>
    <div class="card"><strong>Person 4 — binary and file analyst</strong><br>Take the third Guacamole desktop. Start with Cutter or Evidence file manager tickets, and do not execute recovered files.</div>
    <div class="card"><strong>Person 5 — CTFd recorder and verifier</strong><br>Keep CTFd open. Read questions and answer formats aloud, submit the analysts' values, track free Help 1–2 versus paid Help 3, and confirm accepted findings.</div>
  </div>
  <ol>
    <li>Each person signs into a different numbered CTFd seat.</li>
    <li>The coordinator claims up to three tickets and assigns one analyst to each ticket ID.</li>
    <li>Each analyst follows the ticket's <strong>Start here</strong> directions and reports the answer, source path, and any limitation to the recorder.</li>
    <li>The recorder submits in CTFd and tells the coordinator when a ticket closes. The coordinator confirms the finding in IRIS and assigns the next available ticket.</li>
    <li>If someone is stuck, rotate the ticket or desktop. If the captain leaves, another teammate uses this same handout and continues the coordinator checklist.</li>
  </ol>
</section>
<p class="notice"><strong>Keep this page open.</strong> It is your permanent credential and recovery sheet. Help 1 and 2 are free; Help 3 is the full walkthrough and leaves the question worth 1 point.</p>
<h2>Browser services</h2>
<div class="table-wrap"><table><tr><th>Service</th><th>URL</th><th>Username</th><th>Password</th></tr>
<tr><td>IRIS</td><td><a href="{{ iris_url }}">{{ iris_url }}</a></td><td><code data-copy>{{ credentials.iris.username }}</code></td><td><span class="secret" data-copy>{{ credentials.iris.password }}</span></td></tr>
  <tr><td>Wazuh Discover</td><td><a href="{{ wazuh_url }}">Open prepared telemetry view</a></td><td><code>{{ credentials.wazuh.username }}</code></td><td><span class="secret">{{ credentials.wazuh.password }}</span></td></tr>
</table></div>
<h2>Participant CTFd seats</h2>
<p>Open <a href="{{ ctfd_url }}">{{ ctfd_url }}</a>. CTFd requires one of the personal seat logins below. Your internal team ID is <code>{{ credentials.ctfd.team }}</code>; your seats are already attached to it, so there is no team join password to enter.</p>
<div class="table-wrap"><table><tr><th>Seat</th><th>Username</th><th>Password</th></tr>
{% for member in credentials.ctfd.members %}<tr><td>{{ loop.index }}</td><td><code data-copy>{{ member.username }}</code></td><td><span class="secret" data-copy>{{ member.password }}</span></td></tr>{% endfor %}
</table></div>
<h2>GUI workstations</h2>
  <p>Log into Guacamole once with the account below. All three desktops contain the same complete evidence toolbox. The labels are suggested starting roles so five people can divide the work; they are not tool restrictions. <strong>No separate VNC or desktop password is needed:</strong> Guacamole provides the participant-facing connection.</p>
<p>Guacamole username: <code data-copy>{{ credentials.guacamole.username }}</code><br>Password: <span class="secret" data-copy>{{ credentials.guacamole.password }}</span><br><a href="{{ guac_url }}">Open Guacamole</a></p>
  <div class="table-wrap"><table><tr><th>Connection name</th><th>Suggested role</th><th>Best starting work</th><th>Installed tools</th></tr>
  {% for desktop in registration.result.desktop_urls %}<tr><td><code>{{ desktop.connection_name }}</code></td><td>{{ desktop.name }}</td><td>{{ desktop.guidance }}</td><td>{{ desktop.tools|join(', ') }}</td></tr>{% endfor %}
</table></div>
<script>async function copyValue(value,statusId){await navigator.clipboard.writeText(value);document.getElementById(statusId).textContent='Copied.';}async function copyAll(){await copyValue({{ copy_text|tojson }},'copy-status');}</script>
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
    code_file = os.environ.get('RIDGE_REGISTRATION_CODE_FILE')
    enrollment_code = open(code_file, encoding='utf-8').read().strip() if code_file else None
    registration_store = RegistrationStore(
        registration_path,
        RegistrationConfig(
            max_teams=int(os.environ.get('RIDGE_REGISTRATION_MAX_TEAMS', '10')),
            members_per_team=int(os.environ.get('RIDGE_REGISTRATION_MEMBERS', '5'))),
        enrollment_code=enrollment_code)
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
        registration_open = _registration_worker_ready(registration_path)
        if request.method == 'POST':
            if not hmac.compare_digest(request.form.get('nonce', ''),
                                       session.get('nonce', '!')):
                abort(403)
            if not registration_open:
                error = ('Team setup is temporarily unavailable. Please wait a minute and '
                         'try again. If it remains unavailable, raise your hand for a '
                         'facilitator. Do not submit a second registration.')
                return render_template_string(
                    REGISTRATION_PAGE, view='register', error=error,
                    team_name=team_name, captain_name=captain_name,
                    nonce=session['nonce'], registration_open=False), 503
            try:
                created = registration_store.register(
                    team_name, captain_name,
                    enrollment_code=request.form.get('enrollment_code', ''))
                return redirect(created['retrieve_path'])
            except RegistrationError as exc:
                error = str(exc)
        return render_template_string(REGISTRATION_PAGE, view='register', error=error,
                                      team_name=team_name, captain_name=captain_name,
                                      nonce=session['nonce'],
                                      registration_open=registration_open)

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
            iris_url = os.environ['IRIS_PUBLIC_URL'].rstrip('/') + '/silent-ridge'
            ctfd_base_url = os.environ['CTFD_PUBLIC_URL'].rstrip('/')
            ctfd_url = ctfd_base_url + '/login'
            wazuh_url = participant_wazuh_url(os.environ['WAZUH_PUBLIC_URL'])
            guac_url = os.environ.get(
                'GUACAMOLE_PUBLIC_URL', ctfd_base_url + ':8082')
            retrieve_url = ctfd_base_url + request.path
            copy_text = credential_handout_text(
                registration, credentials, retrieval_url=retrieve_url,
                ctfd_url=ctfd_url, iris_url=iris_url, wazuh_url=wazuh_url,
                guac_url=guac_url)
            response = make_response(render_template_string(
                REGISTRATION_PAGE, view='ready', registration=registration,
                credentials=credentials, iris_url=iris_url, ctfd_url=ctfd_url,
                wazuh_url=wazuh_url, guac_url=guac_url,
                retrieve_url=retrieve_url,
                download_url=retrieve_url.rstrip('/') + '/download',
                copy_text=copy_text))
            return _private_handout_response(response)
        if registration.get('status') in ('pending', 'provisioning'):
            retrieve_url = os.environ['CTFD_PUBLIC_URL'].rstrip('/') + request.path
            response = make_response(render_template_string(
                REGISTRATION_PAGE, view='pending', registration=registration,
                retrieve_url=retrieve_url,
                status_url=request.path.rstrip('/') + '/status'))
            return _private_handout_response(response)
        if registration.get('status') == 'needs_operator':
            retrieve_url = os.environ['CTFD_PUBLIC_URL'].rstrip('/') + request.path
            response = make_response(render_template_string(
                REGISTRATION_PAGE, view='needs_operator', registration=registration,
                retrieve_url=retrieve_url))
            return _private_handout_response(response)
        return render_template_string(REGISTRATION_PAGE, view='error', registration=registration), 404

    @app.route('/silent-ridge/registration/<access_code>/download')
    def ridge_registration_download(access_code):
        try:
            registration = registration_store.get(access_code)
        except RegistrationError:
            abort(404)
        if registration.get('status') != 'ready':
            return _private_handout_response(
                make_response('The private handout is not ready yet.\n', 409))
        credentials = registration_store.get(access_code, include_private=True)['credentials']
        ctfd_base_url = os.environ['CTFD_PUBLIC_URL'].rstrip('/')
        ctfd_url = ctfd_base_url + '/login'
        text = credential_handout_text(
            registration, credentials,
            retrieval_url=(ctfd_base_url +
                           request.path.rsplit('/download', 1)[0]),
            ctfd_url=ctfd_url,
            iris_url=os.environ['IRIS_PUBLIC_URL'].rstrip('/') + '/silent-ridge',
            wazuh_url=participant_wazuh_url(os.environ['WAZUH_PUBLIC_URL']),
            guac_url=os.environ.get('GUACAMOLE_PUBLIC_URL',
                                    ctfd_base_url + ':8082'))
        response = make_response(text)
        response.headers['Content-Type'] = 'text/plain; charset=utf-8'
        response.headers['Content-Disposition'] = (
            'attachment; filename="silent-ridge-private-team-handout.txt"')
        return _private_handout_response(response)

    @app.route('/silent-ridge/registration/<access_code>/status')
    def ridge_registration_status(access_code):
        try:
            registration = registration_store.get(access_code)
            if registration['status'] == 'needs_operator':
                return jsonify(status='needs_operator',
                               message='Raise your hand for a facilitator. Do not register again.')
            return jsonify(status=registration['status'])
        except RegistrationError:
            return jsonify(status='invalid', error='registration not found'), 404

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
                session['ridge_message'] = message
                return redirect('/silent-ridge#' + request.form.get('question',''), code=303)
            message = session.pop('ridge_message', '')
            snapshot = bridge('ctfd', team, 'snapshot')
            questions = bridge('ctfd', team, 'questions', question=request.args.get('question'))
            response = make_response(render_template_string(
                PAGE, lane='ctfd', snapshot=snapshot, questions=questions,
                queue=queue_state(snapshot),
                iris=os.environ['IRIS_PUBLIC_URL'], ctfd=os.environ['CTFD_PUBLIC_URL'], csrf=session['nonce'],
                message=message, story=participant_context(snapshot, questions)))
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

