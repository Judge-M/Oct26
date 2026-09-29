"""Small server-rendered, escaped queue and coached question interfaces.

One template, two lanes, one narrative source. Every scenario sentence below is
rendered from the approved contract by ``ridge.web_narrative``; the only literal
prose left here is the standfirst, which is the copy the published term guard
already treats as participant-visible. Keep it that way: adding a sentence to
this file instead of to the contract is how the three surfaces drifted apart.
"""
from ridge.scenario import NETWORK_MAP, NETWORK_MAP_UNLOCKS_AFTER
PAGE = '''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Operation Silent Ridge</title><style>
body{font:18px system-ui;max-width:980px;margin:2rem auto;padding:1rem;background:#f4f6fa;color:#14243b}
nav,a{color:#155bbb}nav{display:flex;gap:2rem}article{background:white;padding:1.5rem;margin:1rem 0;border:1px solid #bccada;border-radius:12px}
button,input{font:inherit;padding:.6rem;margin:.4rem}button{cursor:pointer}summary{cursor:pointer;padding:.5rem}pre{white-space:pre-wrap}small{display:block}
h2,h3{margin:1rem 0 .4rem}h3{font-size:1.05rem}
</style><nav><a href="{{iris}}/silent-ridge">Incident queue</a><a href="{{ctfd}}/silent-ridge">Questions and help</a><a href="{{ctfd}}/scoreboard">Scoreboard</a></nav>
<h1>{{briefing.codename}}</h1><p>Investigate the suspected disclosure of fictional patrol LANTERN's movement information. All target interactions are read-only.</p>
<p>Team: {{snapshot.team}} · Exercise: {{snapshot.mode}} · <span id="pending">{{snapshot.pending}}</span> updates awaiting synchronization.</p>
<p id="notice" role="status">{{message}}</p>
<p>Activity elapsed: <span id="clock">{{snapshot.elapsed_seconds|round|int}}</span> seconds.</p>
{% for a in snapshot.announcements %}<article><strong>Published announcement · {{a.timestamp}}</strong><p>{{a.text}}</p></article>{% endfor %}
<article><strong>{{briefing.classification_line}}</strong><p>{{briefing.fiction_notice}}</p>
<h2>Situation</h2><p>{{briefing.premise}}</p><p>{{briefing.discovery}}</p><p>{{briefing.stakes}}</p>
<h2>Your role</h2>{% for role in roles %}<p><strong>{{role.name}}</strong> — {{role.duty}} {{role.authority}} {{role['not']}}</p>{% endfor %}
<h2>Scoring and sharing</h2>{% for line in accepted %}<p>{{line}}</p>{% endfor %}
<details><summary>What each surface can and cannot show</summary>{% for tool in tool_map %}<p><strong>{{tool.surface}}</strong> — {{tool.lane}}: {{tool.text}}</p>{% endfor %}</details>
<details><summary>How the investigation is phased</summary>{% for phase in phases %}<p><strong>{{phase.id}} · {{phase.title}}</strong> — {{phase.timeframe}} · {{phase.tickets|join(' ')}}</p><p>{{phase.purpose}} {{phase.urgency}} {{phase.action}}</p><p>{{phase.transition}}</p>{% endfor %}</details>
</article>
{% if lane=='iris' %}<h2>Choose one available ticket</h2>
{% for t in snapshot.tickets %}{% set tn = narrative_tickets[t.id] %}<article><h3>{{t.id}} · {{t.title}}</h3>
{% if tn %}<p><strong>{{tn.phase_id}} · {{tn.phase_title}}</strong> — {{tn.phase_timeframe}} · <strong>{{tn.headline}}</strong></p><p>{{tn.brief}}</p><p>{{tn.stakes}}</p><p>{{tn.why_now}}</p><p>{{tn.next}}</p><p>{{tn.phase_transition}}</p>
{% if tn.complete %}<p>{{ticket_complete.generic}}</p><p>{{ticket_complete.handoff}}</p>{% endif %}{% endif %}
<p>{{t.subject}} · {{t.status}} · Owner: {{t.owner or 'available'}}</p>
{% if t.iris_id %}<a href="{{iris}}/case/tasks?cid={{case}}">Open IRIS tasks and shared findings</a>{% endif %}
{% if snapshot.mode=='running' and t.status=='available' and t.iris_id %}<form method="post"><input type="hidden" name="csrf_token" value="{{csrf}}"><input type="hidden" name="nonce" value="{{csrf}}"><input type="hidden" name="ticket" value="{{t.id}}"><input type="hidden" name="generation" value="{{t.generation}}"><button name="action" value="claim">Claim ticket</button></form>{% endif %}
{% if snapshot.mode=='running' and t.owner==snapshot.team %}<form method="post"><input type="hidden" name="csrf_token" value="{{csrf}}"><input type="hidden" name="nonce" value="{{csrf}}"><input type="hidden" name="ticket" value="{{t.id}}"><input type="hidden" name="generation" value="{{t.generation}}"><button name="action" value="release">Relinquish — keep completed answers</button></form><a href="{{ctfd}}/silent-ridge">Start this ticket's questions</a>{% endif %}</article>{% endfor %}
{% else %}<h2>Your questions and completed shared history</h2><p>{{hints_policy}}</p>
{% for q in questions %}<article id="{{q.id}}"><h3>{{q.id}} · {{q.prompt}}</h3>
<p><strong>{{q.phase_id}} · {{q.phase_title}}</strong> — <strong>{{q.headline}}</strong></p><p>{{q.brief}}</p><p><strong>Why this question matters.</strong> {{q.matters}}</p><p>{{q.next}}</p>
{% if q.solved_by %}<p>Answered by {{q.solved_by}} at {{q.answered_at}}.</p>{% for line in q.accepted %}<p>{{line}}</p>{% endfor %}<p>{{q.finding.text}}</p><p>{{q.finding.limitation}}</p><pre>{{q.finding.evidence|join('\n')}}</pre>
{% if q.complete %}<p>{{ticket_complete.generic}}</p><p>{{ticket_complete.handoff}}</p>{% endif %}
{% else %}<p>{{q.purpose}}</p><p>Tool: {{q.tool}} · Evidence: {{q.evidence}}</p><pre>{{q.steps|join('\n')}}</pre><p>Answer format: {{q.format}}</p><p>Recovery: {{q.recovery}}</p>
{% for hint in q.hints %}<details><summary>Help level {{hint.level}}{% if loop.last %} — explicit walkthrough{% endif %}</summary><p>{{hint.lead}}</p><p>{{hint.text}}</p></details>{% endfor %}
<form method="post"><input type="hidden" name="nonce" value="{{csrf}}"><input type="hidden" name="question" value="{{q.id}}"><label>Answer <input name="answer" maxlength="1024" required></label><button>Check answer</button></form>{% endif %}</article>{% endfor %}{% if network_map %}<article id="t01-network-map"><h3>{{network_map.headline}}</h3><p>{{network_map.brief}}</p><p><a href="{{network_map.path}}">{{network_map.action}}</a></p></article>{% endif %}{% endif %}
{% if exercise_complete.done %}<article><h2>The investigation is closed</h2><p>{{exercise_complete.brief}}</p><p>{{exercise_complete.handoff}}</p><p>{{exercise_complete.residual}}</p><p>{{exercise_complete.scoring_note}}</p></article>{% endif %}
<details><summary>Ground rules for this exercise</summary><p>{{boundaries.read_only}}</p><p>{{boundaries.no_credentials}}</p><p>{{boundaries.no_operational_detail}}</p><p>{{boundaries.fiction_repeat}}</p><p>{{boundaries.attribution}}</p></details>
<script>let previous=null,seconds={{snapshot.elapsed_seconds}},running={{(snapshot.mode=='running')|tojson}},anchor=performance.now();
setInterval(()=>{document.getElementById('clock').textContent=Math.floor(seconds+(running?(performance.now()-anchor)/1000:0));},250);
setInterval(async()=>{try{const r=await fetch('/silent-ridge/status',{cache:'no-store'});if(!r.ok)return;const s=await r.json();document.getElementById('pending').textContent=s.pending;seconds=s.elapsed_seconds;running=s.mode==='running';anchor=performance.now();delete s.server_time;delete s.elapsed_seconds;const v=JSON.stringify(s);if(previous&&previous!==v){document.getElementById('notice').textContent='Progress changed. Reload to see new tasks and findings.';if(![...document.querySelectorAll('input[name=answer]')].some(i=>i.value))location.reload();}previous=v;}catch(e){document.getElementById('notice').textContent='Connection interrupted. Accepted answers are retained. Retrying…';}},5000);</script></html>'''


def network_map_link(snapshot, document=None):
    """The T01 network map, offered from the T01 completion state and nowhere else.

    Placement is deliberate. A released evidence file would be published when its
    ticket unlocks, and T01 unlocks at run start, so the map would name the
    destination before the ticket that scores it was answered. Deriving the link
    from the same condition the controller enforces (``State.ticket_complete``)
    keeps the page from offering something the controller would refuse to serve.
    The prose lives in the map fixture, not here, so the map has one source.
    """
    complete = any(ticket.get('id') == NETWORK_MAP_UNLOCKS_AFTER
                   and ticket.get('status') == 'complete' for ticket in snapshot.get('tickets', []))
    if not complete:
        return None
    from ridge.network_map import build
    link = (document or build())['link']
    return dict(path=NETWORK_MAP, headline=link['headline'], brief=link['brief'],
                action=link['action'])
