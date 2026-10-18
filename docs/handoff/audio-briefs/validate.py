#!/usr/bin/env python3
"""Read-only content checks. Does not connect to or mutate an event."""
import argparse
import json
from pathlib import Path
import re
import shlex
from html.parser import HTMLParser

HERE = Path(__file__).resolve().parent
NOTICE = ('All names, hosts, addresses and artifacts are fictional exercise material. '
          'Nothing here is a real system or person.')
FOOTER = 'OPERATION SILENT RIDGE — EXERCISE ONLY.'
REQUIRES = {'T07':['T06'], 'T09':['T08'], 'T11':['T10'],
            'T19':['T01','T05'], 'T20':['T07','T09','T11','T19']}
RELEASES = {'T07':['identity/late-auth.csv'],
            'T09':['server/version-comparison.csv'],
            'T11':['hunting/late-inventory.csv'],
            'T19':['network/dlp-body.txt','network/dlp-metadata.json'], 'T20':[]}
FORBIDDEN = ['WS-17','WS-22','WS-31','brief-viewer.exe','BriefSync','S-41',
             'm.ellis','r.chen','plan-v3','plan-v4','AMBER','BLUE','CEDAR',
             '198.51.100.77','10.26.10.17','relay.archive.example',
             'briefs.helpdesk.example','req-71','req-72','req-75',
             'previous_claim','session revocation','6364','7644',
             'C:/Temp/move-cache.txt','classify_version','cached v3',
             '08:57','08:58','09:03','09:04','09:06','09:08','09:10','09:20','09:26']

class Links(HTMLParser):
    def __init__(self):
        super().__init__(); self.links=[]
    def handle_starttag(self, tag, attrs):
        for key,value in attrs:
            if key=='href': self.links.append(value)

def normalize(text):
    return ' '.join(text.split())

def check(repo):
    failures=[]
    def need(ok,message):
        if not ok: failures.append(message)
    def hits(value,answer):
        return re.search(r'(?<!\w)'+re.escape(answer)+r'(?!\w)',value,re.I) is not None
    data=json.loads((HERE/'briefs.json').read_text())
    need([b['id'] for b in data]==[f'{i:02}' for i in range(1,8)],'Need exactly seven ordered assets')
    need(len(list(HERE.glob('brief-*.md')))==7,'Unexpected active brief markdown files')
    key=(repo/'docs/rehearsal/evidence/rehearsal-20261018/completed-rerun.md').read_text()
    answers=[]
    for line in key.splitlines():
        if re.match(r'\| T\d\d \| `',line):
            answers.extend(re.findall(r'`([^`]+)`',line.split('|')[2]))
    need(len(answers)==80,'Rehearsal answer table must contain 80 values')
    # LANTERN is the disclosed premise. The generic "no" is allowed only in
    # two opening safety/premise statements, never as a scored answer.
    protected=set(answers)-{'LANTERN','no'}
    total=0
    runbook=(HERE/'RUNBOOK.md').read_text()
    player=(HERE/'player.html').read_text()
    embedded=re.search(r'<script id="brief-data" type="application/json">(.*?)</script>',player,re.S)
    need(embedded is not None,'Missing embedded cue data')
    if embedded: need(json.loads(embedded.group(1))==data,'Player script data drift')
    for b in data:
        name=b['stem']; txt=b['text']; md=(HERE/(name+'.md')).read_text()
        need((HERE/'spoken'/(name+'.txt')).read_text()==txt,name+': spoken file drift')
        need(md.split('## Script\n\n',1)[1].split('\n## Key facts carried',1)[0]==txt,name+': markdown script drift')
        need(txt.endswith(NOTICE+'\n'+FOOTER+'\n'),name+': exact final notices missing')
        need(txt.startswith('All stations, this is EXCON. Exercise, exercise, exercise.'),name+': opening missing')
        need('Good hunting. EXCON, out.' in txt,name+': closing missing')
        need(len(normalize(txt))<=4000,name+': announcement exceeds actual State.announce limit')
        for term in FORBIDDEN:
            need(term.casefold() not in txt.casefold(),name+': handoff forbidden literal '+term)
        for term in protected:
            need(not hits(txt,term),name+': protected answer-key value '+term)
        stripped=txt.replace('No harm is confirmed.','').replace('No attack is required.','') if b['id']=='01' else txt
        need(not hits(stripped,'no'),name+': unreviewed generic negative answer')
        if b['ticket']:
            need(b['requires']==REQUIRES[b['ticket']],name+': incorrect dependencies')
            need(b['release_files']==RELEASES[b['ticket']],name+': incorrect release files')
        word_count=len(re.findall(r"\b[\w]+(?:[-’'][\w]+)*\b",txt))
        need(word_count==b['words'],name+': word-count drift')
        need(round(word_count/140*60)==b['estimated_seconds_at_140_wpm'],name+': duration drift')
        total+=b['estimated_seconds_at_140_wpm']
        commands=re.findall(r'^python -m ridge.cli --state .* announce .*$',md+'\n'+runbook,re.M)
        echoes=[]
        for cmd in commands:
            tokens=shlex.split(cmd)
            if '--text' in tokens and normalize(txt)==tokens[tokens.index('--text')+1]: echoes.append(tokens)
        need(len(echoes)==2,name+': brief and runbook must each carry an exact echo')
        for tokens in echoes:
            need(tokens[:5]==['python','-m','ridge.cli','--state','$RIDGE_STATE'],name+': wrong state syntax')
            need(tokens[5:9]==['announce','--operator','EXCON','--text'],name+': wrong announce syntax')
    links=Links();links.feed(player)
    for target in links.links:
        need(not target.startswith(('http:','https:')), 'Player references network URL')
        need((HERE/target.split('#')[0]).exists(),'Broken player link: '+target)
    need(not re.search(r'\b(?:fetch|XMLHttpRequest|WebSocket)\s*\(',player),'Player must stay offline')
    if failures:
        for f in failures: print('FAIL:',f)
        return 1
    print(f'PASS: seven scripts; {len(answers)} answer-key values checked; exact spoken/markdown/player/echo parity; {total}s estimated speech; dependency, notice, command and local-link checks.')
    print('Reviewed lexical exceptions: LANTERN premise; opening only: “No harm is confirmed” and “No attack is required”. Semantic spoiler review remains required.')
    return 0

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo',type=Path,default=HERE.parents[2])
    raise SystemExit(check(parser.parse_args().repo.resolve()))
