"""Small server-rendered, escaped queue and coached question interfaces."""
PAGE = '''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Operation Silent Ridge</title><style>
body{font:18px system-ui;max-width:980px;margin:2rem auto;padding:1rem;background:#f4f6fa;color:#14243b}
nav,a{color:#155bbb}nav{display:flex;gap:2rem}article{background:white;padding:1.5rem;margin:1rem 0;border:1px solid #bccada;border-radius:12px}
button,input{font:inherit;padding:.6rem;margin:.4rem}button{cursor:pointer}summary{cursor:pointer;padding:.5rem}pre{white-space:pre-wrap}small{display:block}
</style><nav><a href="{{iris}}/silent-ridge">Incident queue</a><a href="{{ctfd}}/silent-ridge">Questions and help</a><a href="{{ctfd}}/scoreboard">Scoreboard</a></nav>
<h1>Operation Silent Ridge</h1><p>Investigate the suspected disclosure of fictional patrol LANTERN's movement information. All target interactions are read-only.</p>
<p>Team: {{snapshot.team}} · Exercise: {{snapshot.mode}} · <span id="pending">{{snapshot.pending}}</span> updates awaiting synchronization.</p>
<p id="notice" role="status">{{message}}</p>
<p>Activity elapsed: <span id="clock">{{snapshot.elapsed_seconds|round|int}}</span> seconds.</p>
{% for a in snapshot.announcements %}<article><strong>Published announcement · {{a.timestamp}}</strong><p>{{a.text}}</p></article>{% endfor %}
{% if lane=='iris' %}<h2>Choose one available ticket</h2>
{% for t in snapshot.tickets %}<article><h3>{{t.id}} · {{t.title}}</h3><p>{{t.subject}} · {{t.status}} · Owner: {{t.owner or 'available'}}</p>
{% if t.iris_id %}<a href="{{iris}}/case/tasks?cid={{case}}">Open IRIS tasks and shared findings</a>{% endif %}
{% if snapshot.mode=='running' and t.status=='available' and t.iris_id %}<form method="post"><input type="hidden" name="csrf_token" value="{{csrf}}"><input type="hidden" name="nonce" value="{{csrf}}"><input type="hidden" name="ticket" value="{{t.id}}"><input type="hidden" name="generation" value="{{t.generation}}"><button name="action" value="claim">Claim ticket</button></form>{% endif %}
{% if snapshot.mode=='running' and t.owner==snapshot.team %}<form method="post"><input type="hidden" name="csrf_token" value="{{csrf}}"><input type="hidden" name="nonce" value="{{csrf}}"><input type="hidden" name="ticket" value="{{t.id}}"><input type="hidden" name="generation" value="{{t.generation}}"><button name="action" value="release">Relinquish — keep completed answers</button></form><a href="{{ctfd}}/silent-ridge">Start this ticket's questions</a>{% endif %}</article>{% endfor %}
{% else %}<h2>Your questions and completed shared history</h2><p>One point per correct answer. All help is free. No report or approval is needed.</p>
{% for q in questions %}<article id="{{q.id}}"><h3>{{q.id}} · {{q.prompt}}</h3>
{% if q.solved_by %}<p>Answered by {{q.solved_by}} at {{q.answered_at}}.</p><p>{{q.finding.text}}</p><p>{{q.finding.limitation}}</p><pre>{{q.finding.evidence|join('\n')}}</pre>
{% else %}<p>{{q.purpose}}</p><p>Tool: {{q.tool}} · Evidence: {{q.evidence}}</p><pre>{{q.steps|join('\n')}}</pre><p>Answer format: {{q.format}}</p><p>Recovery: {{q.recovery}}</p>
{% for hint in q.hints %}<details><summary>Help level {{loop.index}}{% if loop.last %} — explicit walkthrough{% endif %}</summary><p>{{hint}}</p></details>{% endfor %}
<form method="post"><input type="hidden" name="nonce" value="{{csrf}}"><input type="hidden" name="question" value="{{q.id}}"><label>Answer <input name="answer" maxlength="1024" required></label><button>Check answer</button></form>{% endif %}</article>{% endfor %}{% endif %}
<script>let previous=null,seconds={{snapshot.elapsed_seconds}},running={{(snapshot.mode=='running')|tojson}},anchor=performance.now();
setInterval(()=>{document.getElementById('clock').textContent=Math.floor(seconds+(running?(performance.now()-anchor)/1000:0));},250);
setInterval(async()=>{try{const r=await fetch('/silent-ridge/status',{cache:'no-store'});if(!r.ok)return;const s=await r.json();document.getElementById('pending').textContent=s.pending;seconds=s.elapsed_seconds;running=s.mode==='running';anchor=performance.now();delete s.server_time;delete s.elapsed_seconds;const v=JSON.stringify(s);if(previous&&previous!==v){document.getElementById('notice').textContent='Progress changed. Reload to see new tasks and findings.';if(![...document.querySelectorAll('input[name=answer]')].some(i=>i.value))location.reload();}previous=v;}catch(e){document.getElementById('notice').textContent='Connection interrupted. Accepted answers are retained. Retrying…';}},5000);</script></html>'''
