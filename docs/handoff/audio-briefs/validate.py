#!/usr/bin/env python3
"""Read-only validation for the two in-world watch-floor scripts."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shlex
from html.parser import HTMLParser

HERE = Path(__file__).resolve().parent
STEMS = ['brief-01-introduction', 'brief-02-exit']


def check(repo):
    failures = []
    def need(value, message):
        if not value:
            failures.append(message)
    def hits(text, term):
        return re.search(r'(?<!\w)' + re.escape(term) + r'(?!\w)', text, re.I)

    data = json.loads((HERE/'briefs.json').read_text(encoding='utf-8'))
    audit = json.loads((HERE/'spoiler-audit.json').read_text(encoding='utf-8'))
    echoes = json.loads((HERE/'ANNOUNCE-TEXTS.json').read_text(encoding='utf-8'))
    handoff = (HERE/'NEXT-AI-HANDOFF.md').read_text(encoding='utf-8')
    need([b['stem'] for b in data] == STEMS, 'Exactly two ordered assets')
    need([b['id'] for b in data] == ['01','02'], 'Ordered IDs')
    need(re.findall(r'```text\n(.*?)```', handoff, re.S) == [b['text'] for b in data], 'Handoff appendix parity')
    need(set(echoes) == set(STEMS), 'Two full text echoes')
    need({p.stem for p in (HERE/'spoken').glob('*.txt')} == set(STEMS), 'Two clean texts')
    need({p.stem for p in HERE.glob('brief-*.md')} == set(STEMS), 'Two production sheets')
    key = (repo/audit['answer_key_relative_path']).read_text(encoding='utf-8')
    answers = []
    for line in key.splitlines():
        if re.match(r'\| T\d\d \| `', line):
            answers.extend(re.findall(r'`([^`]+)`', line.split('|')[2]))
    need(len(answers) == 80, '80 answer-key entries')
    protected = set(answers) - {'LANTERN','no'}
    for b in data:
        stem, text = b['stem'], b['text']
        label = stem + ': '
        need((HERE/'spoken'/(stem+'.txt')).read_text(encoding='utf-8') == text, label+'spoken parity')
        sheet = (HERE/(stem+'.md')).read_text(encoding='utf-8')
        need(sheet.split('## Script\n\n',1)[1].split('\n## Full written echo',1)[0] == text, label+'sheet parity')
        need(echoes[stem] == ' '.join(text.split()), label+'echo parity')
        need(len(echoes[stem]) <= 4000, label+'announcement text limit')
        need(hashlib.sha256(text.encode()).hexdigest() == b['text_sha256'], label+'source hash')
        need(b['speaker'] == 'Watch floor supervisor in charge of Operation Silent Ridge', label+'role/operation')
        need('Operation Silent Ridge' in text, label+'operation named')
        need(b['trigger_kind'] == 'agenda' and b['ticket'] is None and not b['requires'] and not b['release_files'], label+'independent agenda cue')
        words = len(re.findall(r"\b[\w]+(?:[-’'][\w]+)*\b",text))
        need(words == b['words'], label+'word count')
        need(round(words/140*60) == b['estimated_seconds_at_140_wpm'], label+'duration estimate')
        need('[' not in text and ']' not in text, label+'no stage tags')
        for term in audit['prohibited_spoken_meta_terms']:
            need(not hits(text,term), label+'unwanted spoken meta term '+term)
        for term in audit['forbidden_literals']:
            need(term.casefold() not in text.casefold(), label+'forbidden literal '+term)
        for term in protected:
            need(not hits(text,term), label+'protected answer '+term)
        stripped = text.replace('No harm is confirmed.','') if b['id']=='01' else text
        need(not hits(stripped,'no'), label+'unreviewed generic negative answer')
    player = (HERE/'player.html').read_text(encoding='utf-8')
    embedded = re.search(r'<script id="brief-data" type="application/json">(.*?)</script>',player,re.S)
    need(embedded is not None, 'Player data present')
    if embedded:
        need(json.loads(embedded.group(1)) == data, 'Player data parity')
    need(not re.search(r'\b(?:fetch|XMLHttpRequest|WebSocket)\s*\(',player), 'Player stays offline')
    class Links(HTMLParser):
        def __init__(self):
            super().__init__(); self.links=[]
        def handle_starttag(self,tag,attrs):
            for key,value in attrs:
                if key=='href': self.links.append(value)
    links=Links(); links.feed(player)
    for target in links.links:
        need(not target.startswith(('https:','http:')), 'Player reference stays local')
        need((HERE/target.split('#')[0]).exists(), 'Player link exists: '+target)
    need((HERE/'START-HERE.md').read_text(encoding='utf-8') == handoff, 'Start handoff parity')
    need({p.stem for p in HERE.glob('brief-*.md')} == set(STEMS), 'Only two active sheets')
    runbook=(HERE/'RUNBOOK.md').read_text(encoding='utf-8')
    for b in data:
        full=echoes[b['stem']]
        for location in [runbook,(HERE/(b['stem']+'.md')).read_text(encoding='utf-8')]:
            commands=re.findall(r'^python -m ridge.cli --state .* announce .*$',location,re.M)
            matching=[]
            for command in commands:
                tokens=shlex.split(command)
                if '--text' in tokens and tokens[tokens.index('--text')+1]==full:
                    matching.append(tokens)
            need(len(matching)==1,b['stem']+': exact command echo')
            for tokens in matching:
                need(tokens[:9]==['python','-m','ridge.cli','--state','$RIDGE_STATE','announce','--operator','EXCON','--text'],b['stem']+': explicit state syntax')
    intro, exit_text = data[0]['text'], data[1]['text']
    need("I'm the watch floor supervisor in charge of Operation Silent Ridge." in intro, 'Supervisor owns operation')
    need('The S6 IT department has flagged issues' in intro, 'User-requested S6 referral')
    need("I've brought your teams in" in intro, 'Assisting teams brought in')
    need('read-only' in intro and 'original evidence untouched' in intro, 'Evidence boundaries retained')
    need('stand down from this assignment' in exit_text, 'Exit releases assisting teams')
    if failures:
        for failure in failures:
            print('FAIL:',failure)
        return 1
    print('PASS: two scripts; watch floor supervisor leads Operation Silent Ridge; S6 referral and assisting teams present.')
    print('PASS: 80 answer-key entries and inherited forbidden literals checked; spoken exercise/meta markers absent.')
    print('PASS: clean text, JSON, sheets, handoff and echoes match; hashes, counts and agenda independence verified.')
    print('PASS: offline player data/links and explicit-state runbook/production-sheet echoes verified.')
    print('Estimates: '+', '.join('{} words / {} s'.format(b['words'],b['estimated_seconds_at_140_wpm']) for b in data)+'.')
    print('Scope: source/player integration only; no matching audio, live acceptance or event readiness claimed.')
    return 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo',type=Path,default=HERE.parents[2])
    raise SystemExit(check(parser.parse_args().repo.resolve()))
