"""Small server-rendered, escaped queue and coached question interfaces."""
PAGE = '''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Operation Silent Ridge</title><style>
body{font:18px system-ui;max-width:980px;margin:2rem auto;padding:1rem;background:#f4f6fa;color:#14243b}
nav,a{color:#155bbb}nav{display:flex;gap:2rem}article{background:white;padding:1.5rem;margin:1rem 0;border:1px solid #bccada;border-radius:12px}
button,input{font:inherit;padding:.6rem;margin:.4rem}button{cursor:pointer}summary{cursor:pointer;padding:.5rem}pre{white-space:pre-wrap}small{display:block}
.briefing{background:#14243b;color:white;padding:1.5rem;border-radius:12px;margin:1rem 0}.briefing strong{color:#9ed0ff}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:.8rem}.card{background:#e8eef6;padding:1rem;border-radius:8px}.phase{color:#385675;font-weight:700}.why{border-left:4px solid #c77700;padding-left:1rem}.conclusion{background:#102d29;color:#f4fbf8;border:4px solid #d79a24;padding:1.5rem;border-radius:12px;margin:1.5rem 0}.conclusion h2{color:#ffd174;margin-top:0}.conclusion h3{color:#b7e3d6}.conclusion li{margin:.45rem 0}
</style><nav><a href="{{iris}}/silent-ridge">Incident queue</a><a href="{{ctfd}}/silent-ridge">Questions and help</a><a href="{{ctfd}}/scoreboard">Scoreboard</a></nav>
<h1>{{story.title}}</h1><section class="briefing"><p><strong>{{story.fiction_notice}}</strong></p><p>{{story.premise}}</p><p>{{story.discovery}}</p><p><strong>Mission:</strong> {{story.stakes}}</p></section>
<p>{{story.participant_role}}</p><div class="grid">{% for role in story.roles %}<div class="card"><strong>{{role.name}}</strong><p>{{role.purpose}}</p></div>{% endfor %}</div>
<details><summary>How the tools fit together</summary><div class="grid">{% for name,purpose in story.tools.items() %}<div class="card"><strong>{{name}}</strong><p>{{purpose}}</p></div>{% endfor %}</div></details>
<p><strong>Operating rule:</strong> {{story.operating_rule}}</p>
<p>Team: {{snapshot.team}} · Exercise: {{snapshot.mode}} · <span id="pending">{{snapshot.pending}}</span> updates awaiting synchronization.</p>
<p id="notice" role="status">{{message}}</p>
<p id="queue-status" role="status">{{queue.status}}</p>
<p>Activity elapsed: <span id="clock">{{snapshot.elapsed_seconds|round|int}}</span> seconds.</p>
{% if story.conclusion %}<section class="conclusion" id="final-assessment" aria-labelledby="final-assessment-title">
<h2 id="final-assessment-title">{{story.conclusion.status}}</h2><p>{{story.conclusion.summary}}</p>
<div class="grid"><div><h3>Confirmed</h3><ul>{% for item in story.conclusion.confirmed %}<li>{{item}}</li>{% endfor %}</ul></div>
<div><h3>Not established</h3><ul>{% for item in story.conclusion.not_established %}<li>{{item}}</li>{% endfor %}</ul></div>
<div><h3>Unresolved</h3><ul>{% for item in story.conclusion.unresolved %}<li>{{item}}</li>{% endfor %}</ul></div></div>
<h3>Required containment</h3><ol>{% for item in story.conclusion.actions %}<li>{{item}}</li>{% endfor %}</ol>
<p><strong>Room-wide closing brief ready:</strong> remain in place while the facilitator presents the conclusion to everyone together. Participant-controlled playback is intentionally unavailable.</p>
</section>{% endif %}
{% for a in snapshot.announcements %}<article><strong>{{'Published final assessment' if a.kind=='final_assessment' else 'Published announcement'}} · {{a.timestamp}}</strong><p>{{a.text}}</p></article>{% endfor %}
{% if lane=='iris' %}<h2>{{'Choose one available ticket' if queue.claimable else 'Ticket queue'}}</h2>
{% for t in snapshot.tickets %}{% set context=story.ticket_context.get(t.id) %}<article><h3>{{t.id}} · {{t.title}}</h3><p>{{t.subject}} · {{t.status}} · Owner: {{t.owner or 'available'}}</p>
{% if context %}<p class="phase">{{context.phase_title}}</p><p>{{context.briefing}}</p><p class="why"><strong>Why now:</strong> {{context.stakes}}</p><p><strong>Handoff:</strong> {{context.handoff}}</p>{% endif %}
{% if t.iris_id %}<a href="{{iris}}/case/tasks?cid={{case}}">Open IRIS tasks and shared findings</a>{% endif %}
{% if snapshot.mode=='running' and t.status=='available' and t.iris_id %}<form method="post"><input type="hidden" name="csrf_token" value="{{csrf}}"><input type="hidden" name="nonce" value="{{csrf}}"><input type="hidden" name="ticket" value="{{t.id}}"><input type="hidden" name="generation" value="{{t.generation}}"><button name="action" value="claim">Claim ticket</button></form>{% else %}<p class="why"><strong>Claiming:</strong> {{ queue.notes.get(t.id,'Claiming is not open for this ticket right now.') }}</p>{% endif %}
{% if snapshot.mode=='running' and t.owner==snapshot.team %}<form method="post"><input type="hidden" name="csrf_token" value="{{csrf}}"><input type="hidden" name="nonce" value="{{csrf}}"><input type="hidden" name="ticket" value="{{t.id}}"><input type="hidden" name="generation" value="{{t.generation}}"><button name="action" value="release">Relinquish — keep completed answers</button></form><a href="{{ctfd}}/silent-ridge">Start this ticket's questions</a>{% endif %}</article>{% endfor %}
{% else %}<h2>Your questions and completed shared history</h2><p>Each question is worth 4 points. Help levels 1 and 2 are free. Unlocking the explicit walkthrough costs 75% of that question's value, leaving 1 point. No report or approval is needed.</p>
{% for q in questions %}{% set context=story.ticket_context.get(q.ticket) %}<article id="{{q.id}}"><h3>{{q.id}} · {{q.prompt}}</h3>
{% if context %}<p class="phase">{{context.phase_title}}</p><p class="why"><strong>Why this question matters:</strong> {{context.stakes}}</p>{% endif %}
{% if q.solved_by %}<p>Answered by {{q.solved_by}} at {{q.answered_at}}.</p><p>{{q.finding.text}}</p><p>{{q.finding.limitation}}</p><pre>{{q.finding.evidence|join('\n')}}</pre>
{% else %}<p>{{q.purpose}}</p><p>Tool: {{q.tool}} · Evidence: {{q.evidence}}</p><pre>{{q.steps|join('\n')}}</pre><p>Answer format: {{q.format}}</p><p>Recovery: {{q.recovery}}</p>
{% for hint in q.hints %}<details><summary>Help level {{loop.index}}{% if q.hint_unlocked and loop.last %} — explicit walkthrough (unlocked){% else %} — free{% endif %}</summary><p>{{hint}}</p></details>{% endfor %}
{% if q.paid_hint_available %}<form method="post"><input type="hidden" name="nonce" value="{{csrf}}"><input type="hidden" name="action" value="unlock_hint"><input type="hidden" name="question" value="{{q.id}}"><button>Unlock Help level 3 — explicit walkthrough (costs 3 of 4 points)</button></form>{% elif q.hint_unlocked %}<p class="why"><strong>Assisted scoring:</strong> the explicit walkthrough is unlocked; this answer is now worth 1 of 4 points.</p>{% endif %}
<form method="post"><input type="hidden" name="nonce" value="{{csrf}}"><input type="hidden" name="action" value="answer"><input type="hidden" name="question" value="{{q.id}}"><label>Answer <input name="answer" maxlength="1024" required></label><button>Check answer — worth {{q.available_points}} point{% if q.available_points != 1 %}s{% endif %}</button></form>{% endif %}</article>{% endfor %}{% endif %}
<section class="card"><strong>Shared progress: {{story.completed}} of {{story.total}} ticket stages complete.</strong><p>{{story.completion}}</p></section>
<script>let previous=null,seconds={{snapshot.elapsed_seconds}},running={{(snapshot.mode=='running')|tojson}},anchor=performance.now();
setInterval(()=>{document.getElementById('clock').textContent=Math.floor(seconds+(running?(performance.now()-anchor)/1000:0));},250);
setInterval(async()=>{try{const r=await fetch('/silent-ridge/status',{cache:'no-store'});if(!r.ok)return;const s=await r.json();document.getElementById('pending').textContent=s.pending;seconds=s.elapsed_seconds;running=s.mode==='running';anchor=performance.now();delete s.server_time;delete s.elapsed_seconds;const v=JSON.stringify(s);if(previous&&previous!==v){document.getElementById('notice').textContent='Progress changed. Reload to see new tasks and findings.';if(![...document.querySelectorAll('input[name=answer]')].some(i=>i.value))location.reload();}previous=v;}catch(e){document.getElementById('notice').textContent='Connection interrupted. Accepted answers are retained. Retrying…';}},5000);</script></html>'''


def queue_state(snapshot):
    """Explain the queue in plain language so a page with no controls still says why.

    The claim form renders only when the exercise is running, the ticket is
    available, and its IRIS case tasks exist. Every other combination is a
    normal queue state, so each one gets an explicit reason — paused, claimed
    by another team, still being prepared in IRIS, or exercise complete —
    instead of a silently missing form (issue #194).
    """
    snapshot=snapshot or {}
    tickets=list(snapshot.get('tickets') or [])
    team=str(snapshot.get('team') or '')
    mode=snapshot.get('mode') or 'paused'
    running=mode=='running'
    def same(owner):
        return str(owner or '')==team
    held=[t['id'] for t in tickets if t.get('owner') and same(t.get('owner'))]
    claimable=[t['id'] for t in tickets if running and t.get('status')=='available' and t.get('iris_id')]
    preparing=[t['id'] for t in tickets if t.get('status')=='available' and not t.get('iris_id')]
    others=[(t['id'],t.get('owner')) for t in tickets if t.get('status')=='active' and not same(t.get('owner'))]
    complete=[t['id'] for t in tickets if t.get('status')=='complete']
    notes={}
    for t in tickets:
        if t['id'] in claimable:
            continue
        if t.get('status')=='complete':
            notes[t['id']]='Complete — every stage is answered and its findings are published. Nothing left to claim.'
        elif same(t.get('owner')):
            notes[t['id']]='You hold this ticket. Work its questions on the Questions page, or relinquish it below.' if running else 'You hold this ticket. Relinquishing and new claims resume when the exercise is running again.'
        elif t.get('status')=='active':
            notes[t['id']]='Claimed by %s. It returns to the queue only if that team relinquishes it.' % (t.get('owner') or 'another team')
        elif t.get('status')=='available' and not t.get('iris_id'):
            notes[t['id']]='Being prepared in IRIS — the Claim button appears as soon as its case tasks exist. This is normal for the first minutes after a ticket unlocks.'
        elif not running:
            notes[t['id']]='Claiming is closed while the exercise is %s. It reopens automatically when the organizer resumes the exercise.' % mode
        else:
            notes[t['id']]='Claiming is not open for this ticket right now (status: %s).' % t.get('status')
    if tickets and len(complete)==len(tickets):
        status=('Assessment complete — LIMITED DISCLOSURE CONFIRMED. Every ticket is closed, '
                'the final incident assessment is published, and required containment actions are available below. '
                'Nothing further can be claimed. This is the expected end state, not an outage.')
    else:
        parts=[]
        if not running:
            parts.append('Exercise %s: claiming is paused until the organizer resumes it.' % mode)
        parts.append('You hold: %s.' % ', '.join(held) if held else 'You hold no ticket.')
        if claimable:
            parts.append('Available to claim: %s.' % ', '.join(claimable))
        else:
            reasons=[]
            if others:
                reasons.append('claimed by others: '+', '.join('%s (%s)' % (tid,owner or 'another team') for tid,owner in others))
            if preparing:
                reasons.append('preparing in IRIS: '+', '.join(preparing))
            if complete:
                reasons.append('complete: '+', '.join(complete))
            parts.append('Nothing is available to claim right now'+(' — '+ '; '.join(reasons)+'.' if reasons else '.'))
        if not held and not claimable:
            parts.append('This is a normal queue state; the page refreshes itself when something changes.')
        status=' '.join(parts)
    return {'status':status,'notes':notes,'held':held,'claimable':claimable,
            'preparing':preparing,'paused':not running,
            'complete':bool(tickets) and len(complete)==len(tickets)}
