"""Small server-rendered, escaped queue and coached question interfaces."""
PAGE = '''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Operation Silent Ridge</title><style>
body{font:18px system-ui;max-width:980px;margin:2rem auto;padding:1rem;background:#f4f6fa;color:#14243b}
nav,a{color:#155bbb}nav{display:flex;gap:2rem}article{background:white;padding:1.5rem;margin:1rem 0;border:1px solid #bccada;border-radius:12px}
button,input{font:inherit;padding:.6rem;margin:.4rem}button{cursor:pointer}summary{cursor:pointer;padding:.5rem}pre{white-space:pre-wrap}small{display:block}
.briefing{background:#14243b;color:white;padding:1.5rem;border-radius:12px;margin:1rem 0}.briefing strong{color:#9ed0ff}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:.8rem}.card{background:#e8eef6;padding:1rem;border-radius:8px}.phase{color:#385675;font-weight:700}.why{border-left:4px solid #c77700;padding-left:1rem}.conclusion{background:#102d29;color:#f4fbf8;border:4px solid #d79a24;padding:1.5rem;border-radius:12px;margin:1.5rem 0}.conclusion h2{color:#ffd174;margin-top:0}.conclusion h3{color:#b7e3d6}.conclusion li{margin:.45rem 0}.update{background:linear-gradient(135deg,#fff8e8,#ffedbd);border:4px solid #a84d00;padding:1.35rem;border-radius:12px;margin:1.5rem 0;box-shadow:0 8px 24px #7c50003d}.update h2{font-size:1.65rem;margin:.2rem 0 .35rem}.update h3{margin:1rem 0 .35rem}.update .sender{color:#5c4300;font-weight:800;margin:.25rem 0 1rem}.update-classification{font-size:.84rem;font-weight:900;letter-spacing:.08em;color:#6e3000;margin:0 0 .25rem}.evidence-badge{display:inline-block;background:#7d3000;color:white;font-weight:900;letter-spacing:.06em;padding:.45rem .7rem;border-radius:999px;margin:0 0 .7rem}.sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}.update-detail{border-top:1px solid #d9a962;padding-top:.65rem;margin-top:.7rem}.update-detail>summary{color:#623000;font-weight:800;display:flex;justify-content:space-between;gap:1rem}.update-detail>summary small{font-weight:500}.update-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(270px,1fr));gap:.85rem;margin:.8rem 0}.update-panel{background:#fffdf7;border:1px solid #e0bd7e;border-radius:9px;padding:.9rem}.update-panel h3{margin-top:0}.update-panel ul{padding-left:1.25rem}.update-panel li{margin:.45rem 0}.update-decision{background:#14243b;color:white;padding:1rem;border-radius:9px}.update-guardrail{border-left:5px solid #a84d00;background:#fff;padding:.8rem 1rem}.update-actions{display:flex;align-items:center;gap:1.25rem;flex-wrap:wrap}.update.acknowledged{border-width:2px;box-shadow:none}.update.acknowledged .evidence-badge{background:#4e5e68}.question-nav{background:#e8eef6;border-radius:10px;padding:.75rem 1rem;display:flex;gap:1.25rem;flex-wrap:wrap}.question-history{background:#dde7f1;border:2px solid #7890a8;border-radius:12px;padding:.5rem 1rem;margin:1.25rem 0}.question-history>summary{font-size:1.15rem}.timeline{background:#fff;border:1px solid #bccada;border-radius:12px;padding:1.25rem;margin:1rem 0}.timeline ol{list-style:none;padding:0}.timeline li{display:grid;grid-template-columns:7rem 1fr;gap:1rem;border-top:1px solid #d8e0e8;padding:.8rem 0}.timeline time{font-weight:800;color:#174f80}.workspace{background:#eef5fb;border:2px solid #6c94b8;border-radius:12px;padding:1.25rem;margin:1.25rem 0}.workspace label{display:block;font-weight:700;margin:.6rem 0}.workspace input:not([type=checkbox]),.workspace textarea{width:100%;box-sizing:border-box;margin:.25rem 0 .5rem}.workspace input[type=checkbox]{width:auto;margin-right:.4rem}.workspace textarea{min-height:5rem}.relation{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:.7rem}.relation label{background:white;padding:.7rem;border-radius:8px}.workspace-note{color:#385675;font-size:.95rem}
</style><nav><a href="{{iris}}/silent-ridge">Incident queue</a><a href="{{ctfd}}/silent-ridge">Questions and help</a><a href="{{ctfd}}/scoreboard">Scoreboard</a></nav>
<h1>{{story.title}}</h1><section class="briefing"><p><strong>{{story.fiction_notice}}</strong></p><p>{{story.premise}}</p><p>{{story.discovery}}</p><p><strong>Mission:</strong> {{story.stakes}}</p></section>
<p>{{story.participant_role}}</p><div class="grid">{% for role in story.roles %}<div class="card"><strong>{{role.name}}</strong><p>{{role.purpose}}</p></div>{% endfor %}</div>
<details><summary>How the tools fit together</summary><div class="grid">{% for name,purpose in story.tools.items() %}<div class="card"><strong>{{name}}</strong><p>{{purpose}}</p></div>{% endfor %}</div></details>
<p><strong>Operating rule:</strong> {{story.operating_rule}}</p>
<p>Team: {{snapshot.team}} · Exercise: {{snapshot.mode}} · <span id="pending">{{snapshot.pending}}</span> updates awaiting synchronization.</p>
<p id="notice" role="status">{{message}}</p>
<p id="queue-status" role="status">{{queue.status}}</p>
<p>Activity elapsed: <span id="clock">{{story.elapsed_display}}</span>{% if story.activity_complete %} (complete){% endif %}.</p>
{% if story.operational_update %}<p role="status" class="sr-only">New Phase 3 operational update available.</p><section class="update" id="operational-update" role="region" aria-labelledby="operational-update-title">
<p class="evidence-badge">NEW EVIDENCE RELEASED · PHASE 3 AVAILABLE</p>
<p class="update-classification">{{story.operational_update.classification}}</p><h2 id="operational-update-title">{{story.operational_update.title}}</h2>
<p class="sender">From {{story.operational_update.sender}}</p><details class="update-detail" id="operational-update-detail" open>
<summary><span>Situation, operational significance, and tasking</span><small>Open this briefing again at any time</small></summary>
<h3>What command now knows</h3><p>{{story.operational_update.message}}</p>
<div class="update-grid"><section class="update-panel"><h3>Why command is widening scope</h3><p>{{story.operational_update.significance}}</p></section>
<section class="update-panel"><h3>Evidence and records now in scope</h3><ul>{% for item in story.operational_update.available_now %}<li>{{item}}</li>{% endfor %}</ul></section></div>
<section class="update-decision"><h3>Decision requirement</h3><p>{{story.operational_update.decision_requirement}}</p></section>
<h3>Immediate tasking</h3><ol>{% for item in story.operational_update.priorities %}<li>{{item}}</li>{% endfor %}</ol>
<p class="update-guardrail"><strong>Assessment standard:</strong> {{story.operational_update.guardrail}}</p></details>
<div class="update-actions"><p>{% if lane=='ctfd' %}<a href="#current-questions">Jump to newly released questions</a>{% else %}<a href="{{ctfd}}/silent-ridge#current-questions">Open newly released questions</a>{% endif %}</p>
<button type="button" id="dismiss-update">Acknowledge and continue</button></div></section>{% endif %}
{% if story.conclusion %}<section class="conclusion" id="final-assessment" aria-labelledby="final-assessment-title">
<h2 id="final-assessment-title">{{story.conclusion.status}}</h2><p>{{story.conclusion.summary}}</p>
<div class="grid"><div><h3>Confirmed</h3><ul>{% for item in story.conclusion.confirmed %}<li>{{item}}</li>{% endfor %}</ul></div>
<div><h3>Not established</h3><ul>{% for item in story.conclusion.not_established %}<li>{{item}}</li>{% endfor %}</ul></div>
<div><h3>Unresolved</h3><ul>{% for item in story.conclusion.unresolved %}<li>{{item}}</li>{% endfor %}</ul></div></div>
<h3>Required containment</h3><ol>{% for item in story.conclusion.actions %}<li>{{item}}</li>{% endfor %}</ol>
<p><strong>Room-wide closing brief ready:</strong> remain in place while the facilitator presents the conclusion to everyone together. Participant-controlled playback is intentionally unavailable.</p>
</section>{% endif %}
{% for a in snapshot.announcements %}<article><strong>{{'Published final assessment' if a.kind=='final_assessment' else 'Published announcement'}} · {{a.timestamp}}</strong><p>{{a.text}}</p></article>{% endfor %}
{% if lane=='iris' %}<section class="card" aria-labelledby="ticket-workflow-title"><h2 id="ticket-workflow-title">How to start work</h2><p>Your team may hold <strong>up to three tickets at the same time</strong>. Use <strong>Claim ticket — start working</strong> on this Incident queue. The native IRIS task view is read-only for participants, so its status controls will deny changes.</p></section>{% if story.timeline %}<section class="timeline" aria-labelledby="timeline-title"><h2 id="timeline-title">Verified incident chronology</h2>
<p>Events appear only after their supporting ticket is complete. Times are incident UTC, not participant submission times.</p><ol>
{% for item in story.timeline %}<li><time>{{item.time}} UTC</time><div><strong>{{item.event}}</strong><br><small>{{item.ticket}} · {{item.source}}</small></div></li>{% endfor %}
</ol></section>{% endif %}<h2>{{'Choose up to three available tickets' if queue.claimable else 'Ticket queue'}}</h2>
{% for t in snapshot.tickets %}{% set context=story.ticket_context.get(t.id) %}{% set route=story.ticket_routes.get(t.id) %}<article><h3>{{t.id}} · {{t.title}}</h3><p>{{t.subject}} · {{t.status}} · Owner: {{t.owner or 'available'}}</p>
{% if context %}<p class="phase">{{context.phase_title}}</p><p>{{context.briefing}}</p><p class="why"><strong>Why now:</strong> {{context.stakes}}</p><p><strong>Handoff:</strong> {{context.handoff}}</p>{% endif %}
{% if route %}<section class="card"><strong>Start here</strong><p><strong>Tool:</strong> {{route.tools|join(', ')}}<br><strong>Evidence:</strong> <code>{{route.evidence|join('</code><br><code>')|safe}}</code></p><ol>{% for step in route.directions %}<li>{{step}}</li>{% endfor %}</ol></section>{% endif %}
{% if t.iris_id %}<a href="{{iris}}/case/tasks?cid={{case}}">View read-only IRIS tasks and shared findings</a>{% endif %}
{% if snapshot.mode=='running' and t.status=='available' and t.iris_id %}<form method="post"><input type="hidden" name="csrf_token" value="{{csrf}}"><input type="hidden" name="nonce" value="{{csrf}}"><input type="hidden" name="ticket" value="{{t.id}}"><input type="hidden" name="generation" value="{{t.generation}}"><button name="action" value="claim">Claim ticket — start working</button></form>{% else %}<p class="why"><strong>Claiming:</strong> {{ queue.notes.get(t.id,'Claiming is not open for this ticket right now.') }}</p>{% endif %}
{% if snapshot.mode=='running' and t.owner==snapshot.team %}<form method="post"><input type="hidden" name="csrf_token" value="{{csrf}}"><input type="hidden" name="nonce" value="{{csrf}}"><input type="hidden" name="ticket" value="{{t.id}}"><input type="hidden" name="generation" value="{{t.generation}}"><button name="action" value="release">Relinquish — keep completed answers</button></form><a href="{{ctfd}}/silent-ridge">Start this ticket's questions</a>{% endif %}</article>{% endfor %}
{% else %}{% if story.correlation_workspace %}<section class="workspace" id="correlation-workspace" aria-labelledby="correlation-title"><h2 id="correlation-title">Process-to-network correlation board</h2>
<p>Build the relationship from the T13–T16 records before treating adjacent fields as one event. This scratchpad stays in this browser and is never submitted.</p><div class="relation">
<label>Parent executable<input data-ridge-note="parent-executable" placeholder="From process tree"></label>
<label>Parent PID<input data-ridge-note="parent-pid" placeholder="From memory process record"></label>
<label>Viewer PID<input data-ridge-note="viewer-pid" placeholder="Join key"></label>
<label>Cache argument<input data-ridge-note="cache-path" placeholder="From command line"></label>
<label>Remote endpoint<input data-ridge-note="remote-endpoint" placeholder="Address:port"></label>
<label>Evidence limitation<input data-ridge-note="correlation-limit" placeholder="What this graph cannot prove"></label>
</div><label><input type="checkbox" data-ridge-check="correlation-reviewed"> I compared the process, task, memory, and connection records rather than treating one prepared JSON file as the whole finding.</label>
<p class="workspace-note" id="correlation-status" role="status"></p></section>{% endif %}
{% if story.capstone_workspace %}<section class="workspace" id="capstone-workspace" aria-labelledby="capstone-title"><h2 id="capstone-title">Capstone assessment workspace</h2>
<p>Draft the assessment before answering T20. Notes remain only in this browser; the platform publishes only verified question findings.</p>
<label>Confirmed — what happened and which evidence proves it?<textarea data-ridge-note="capstone-confirmed"></textarea></label>
<label>Not established — which tempting claims are unsupported?<textarea data-ridge-note="capstone-not-established"></textarea></label>
<label>Unresolved — what collection gap prevents closure?<textarea data-ridge-note="capstone-unresolved"></textarea></label>
<label>Recommended action — what should command do next, and why?<textarea data-ridge-note="capstone-action"></textarea></label>
<label><input type="checkbox" data-ridge-check="capstone-cited"> I can cite a source for each confirmed statement and have kept uncertainty beside the conclusion.</label>
<p class="workspace-note" id="capstone-status" role="status"></p></section>{% endif %}
{% macro render_question(q) %}{% set context=story.ticket_context.get(q.ticket) %}<article id="{{q.id}}"><h3>{{q.id}} · {{q.prompt}}</h3>
{% if context %}<p class="phase">{{context.phase_title}}</p><p class="why"><strong>Why this question matters:</strong> {{context.stakes}}</p>{% endif %}
{% if q.solved_by %}<p>Answered by {{q.solved_by}} at {{q.answered_at}}.</p><p>{{q.finding.text}}</p><p>{{q.finding.limitation}}</p><pre>{{q.finding.evidence|join('\n')}}</pre>
{% else %}<p>{{q.purpose}}</p><p>Tool: {{q.tool}} · Evidence: {{q.evidence}}</p><pre>{{q.steps|join('\n')}}</pre><p>Answer format: {{q.format}}</p><p>Recovery: {{q.recovery}}</p>
{% for hint in q.hints %}<details><summary>Help level {{loop.index}}{% if q.hint_unlocked and loop.last %} — explicit walkthrough (unlocked){% else %} — free{% endif %}</summary><p>{{hint}}</p></details>{% endfor %}
{% if q.paid_hint_available %}<form method="post"><input type="hidden" name="nonce" value="{{csrf}}"><input type="hidden" name="action" value="unlock_hint"><input type="hidden" name="question" value="{{q.id}}"><button>Unlock Help level 3 — explicit walkthrough (costs 3 of 4 points)</button></form>{% elif q.hint_unlocked %}<p class="why"><strong>Assisted scoring:</strong> the explicit walkthrough is unlocked; this answer is now worth 1 of 4 points.</p>{% endif %}
<form method="post"><input type="hidden" name="nonce" value="{{csrf}}"><input type="hidden" name="action" value="answer"><input type="hidden" name="question" value="{{q.id}}"><label>Answer <input name="answer" maxlength="1024" required></label><button>Check answer — worth {{q.available_points}} point{% if q.available_points != 1 %}s{% endif %}</button></form>{% endif %}</article>{% endmacro %}
<h2>Your questions and completed shared history</h2><p>Each question is worth 4 points. Help levels 1 and 2 are free. Unlocking the explicit walkthrough costs 75% of that question's value, leaving 1 point. No report or approval is needed.</p>
<nav class="question-nav" aria-label="Question sections"><a href="#current-questions">Jump to current questions</a><a href="#completed-history">Review completed history</a></nav>
<section id="current-questions"><h2>Current questions</h2>
{% set current_questions=questions|rejectattr('solved_by')|list %}{% for q in current_questions %}{{render_question(q)}}{% else %}<p class="card">No unanswered questions are available right now. Claim the next IRIS ticket or wait for the evidence release.</p>{% endfor %}</section>
{% set completed_questions=questions|selectattr('solved_by')|list %}<details class="question-history" id="completed-history"><summary><strong>Completed shared history · {{completed_questions|length}} answered</strong></summary>
<p>Completed findings are collapsed so the active work stays easy to scan.</p>{% for q in completed_questions %}{{render_question(q)}}{% else %}<p>No completed questions yet.</p>{% endfor %}</details>{% endif %}
<section class="card"><strong>Shared progress: {{story.completed}} of {{story.total}} ticket stages complete.</strong><p>{{story.completion}}</p></section>
<script>
const ridgeTeam={{snapshot.team|tojson}},ridgePrefix='silent-ridge:'+ridgeTeam+':';
function formatElapsed(value){const total=Math.max(0,Math.floor(Number(value)||0)),hours=Math.floor(total/3600),minutes=Math.floor((total%3600)/60),seconds=total%60;return [hours,minutes,seconds].map(v=>String(v).padStart(2,'0')).join(':');}
function readLocal(key){try{return localStorage.getItem(key);}catch(e){return null;}}
function writeLocal(key,value){try{localStorage.setItem(key,value);}catch(e){}}
let previous=null,seconds={{snapshot.elapsed_seconds}},running={{(snapshot.mode=='running' and not story.activity_complete)|tojson}},anchor=performance.now();
setInterval(()=>{document.getElementById('clock').textContent=formatElapsed(seconds+(running?(performance.now()-anchor)/1000:0));},250);
const update=document.getElementById('operational-update'),updateDetail=document.getElementById('operational-update-detail'),dismiss=document.getElementById('dismiss-update'),updateKey=ridgePrefix+'update:scope-expansion:v3';
function acknowledgeUpdate(){if(!update)return;update.classList.add('acknowledged');if(updateDetail)updateDetail.removeAttribute('open');if(dismiss){dismiss.disabled=true;dismiss.textContent='Update acknowledged';}}
if(update&&readLocal(updateKey)==='acknowledged')acknowledgeUpdate();
if(dismiss)dismiss.addEventListener('click',()=>{writeLocal(updateKey,'acknowledged');acknowledgeUpdate();document.getElementById('notice').textContent='Operational update acknowledged. The new-evidence badge and released questions remain available.';});
const noteFields=[...document.querySelectorAll('[data-ridge-note]')],checkFields=[...document.querySelectorAll('[data-ridge-check]')];
function workspaceStatus(){for(const [workspace,statusId] of [['correlation-workspace','correlation-status'],['capstone-workspace','capstone-status']]){const root=document.getElementById(workspace),status=document.getElementById(statusId);if(!root||!status)continue;const fields=[...root.querySelectorAll('[data-ridge-note]')],checks=[...root.querySelectorAll('[data-ridge-check]')];const filled=fields.filter(field=>field.value.trim()).length,checked=checks.filter(field=>field.checked).length;status.textContent=filled+' of '+fields.length+' evidence fields drafted'+(checks.length?' · '+checked+' of '+checks.length+' review checks complete':'')+'.';}}
for(const field of noteFields){const key=ridgePrefix+'note:'+field.dataset.ridgeNote;field.value=readLocal(key)||'';field.addEventListener('input',()=>{writeLocal(key,field.value);workspaceStatus();});}
for(const field of checkFields){const key=ridgePrefix+'check:'+field.dataset.ridgeCheck;field.checked=readLocal(key)==='true';field.addEventListener('change',()=>{writeLocal(key,String(field.checked));workspaceStatus();});}
workspaceStatus();
setInterval(async()=>{try{const r=await fetch('/silent-ridge/status',{cache:'no-store'});if(!r.ok)return;const s=await r.json();document.getElementById('pending').textContent=s.pending;seconds=s.elapsed_seconds;running=s.mode==='running'&&!s.activity_complete;anchor=performance.now();delete s.server_time;delete s.elapsed_seconds;const v=JSON.stringify(s);if(previous&&previous!==v){const notice=document.getElementById('notice');notice.innerHTML='Updates are available. <button type="button" id="ridge-refresh">Refresh when ready</button>';document.getElementById('ridge-refresh').addEventListener('click',()=>location.reload());}previous=v;}catch(e){document.getElementById('notice').textContent='Connection interrupted. Accepted answers are retained. Retrying…';}},5000);
</script></html>'''


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

