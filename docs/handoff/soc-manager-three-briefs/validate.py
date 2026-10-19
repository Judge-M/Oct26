#!/usr/bin/env python3
"""Read-only checks for this three-script handoff; does not operate an event."""
import argparse
import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
DEFAULT_REPO = HERE.parent / 'Oct26'
NOTICE = ('All names, hosts, addresses and artifacts are fictional exercise material. '
          'Nothing here is a real system or person.\n'
          'OPERATION SILENT RIDGE — EXERCISE ONLY.\n')
STEMS = ['brief-01-arrival', 'brief-02-post-lunch', 'brief-03-final-approach']


def check(repo):
    errors = []
    def need(value, message):
        if not value:
            errors.append(message)
    def hits(text, term):
        return re.search(r'(?<!\w)' + re.escape(term) + r'(?!\w)', text, re.I)

    data = json.loads((HERE / 'briefs.json').read_text())
    audit = json.loads((HERE / 'spoiler-audit.json').read_text())
    echoes = json.loads((HERE / 'ANNOUNCE-TEXTS.json').read_text())
    handoff = (HERE / 'START-HERE.md').read_text()
    blocks = re.findall(r'```text\n(.*?)```', handoff, re.S)
    need([b['stem'] for b in data] == STEMS, 'Exactly three ordered stems required')
    need([b['id'] for b in data] == ['01', '02', '03'], 'Ordered IDs required')
    need([b['text'] for b in data] == blocks, 'Full handoff appendix parity')
    need(set(echoes) == set(STEMS), 'Exactly three text echoes required')
    need({p.stem for p in (HERE / 'spoken').glob('*.txt')} == set(STEMS), 'Clean input file set')
    need({p.stem for p in (HERE / 'production-sheets').glob('*.md')} == set(STEMS), 'Production-sheet file set')

    key = (repo / audit['answer_key_relative_path']).read_text()
    answers = []
    for line in key.splitlines():
        if re.match(r'\| T\d\d \| `', line):
            answers.extend(re.findall(r'`([^`]+)`', line.split('|')[2]))
    need(len(answers) == 80, '80 answer-key entries required')
    protected = set(answers) - {'LANTERN', 'no'}
    for b in data:
        stem, text = b['stem'], b['text']
        prefix = stem + ': '
        need((HERE / 'spoken' / (stem + '.txt')).read_text() == text, prefix + 'clean transcript parity')
        sheet = (HERE / 'production-sheets' / (stem + '.md')).read_text()
        need(sheet.split('## Script\n\n', 1)[1].split('\n## After playback', 1)[0] == text, prefix + 'sheet parity')
        need(echoes[stem] == ' '.join(text.split()), prefix + 'full normalized echo parity')
        need(len(echoes[stem]) <= 4000, prefix + 'announcement text limit')
        need(hashlib.sha256(text.encode()).hexdigest() == b['text_sha256'], prefix + 'text hash')
        need(text.startswith('All stations, this is EXCON.\n\n'), prefix + 'exercise opening')
        need(text.endswith(NOTICE), prefix + 'exact final notices')
        need(text.count('Good hunting. EXCON, out.') == 1, prefix + 'exercise closing')
        need(b['trigger_kind'] == 'agenda' and b['ticket'] is None and b['requires'] == [] and b['release_files'] == [], prefix + 'agenda independence')
        words = len(re.findall(r"\b[\w]+(?:[-’'][\w]+)*\b", text))
        need(words == b['words'], prefix + 'word count')
        need(round(words / 140 * 60) == b['estimated_seconds_at_140_wpm'], prefix + 'duration estimate')
        need('[' not in text and ']' not in text, prefix + 'unspoken stage tags')
        for term in audit['forbidden_literals']:
            need(term.casefold() not in text.casefold(), prefix + 'forbidden literal ' + term)
        for term in protected:
            need(not hits(text, term), prefix + 'protected answer ' + term)
        stripped = text
        if b['id'] == '01':
            stripped = stripped.replace('No harm is confirmed.', '').replace('No attack is required.', '')
        need(not hits(stripped, 'no'), prefix + 'unreviewed generic negative answer')
    if errors:
        for error in errors:
            print('FAIL:', error)
        return 1
    print('PASS: three agenda scripts; 80 answer-key entries and inherited forbidden literals checked.')
    print('PASS: JSON, clean text, production sheets, handoff appendix and full text echoes match; text hashes and notices verified.')
    print('Estimates: ' + ', '.join(f"{b['words']} words / {b['estimated_seconds_at_140_wpm']} s" for b in data) + '.')
    print('Limits: lexical checks do not prove semantic safety, audio quality, listening acceptance or event readiness. No audio rendered for this edition.')
    return 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=DEFAULT_REPO)
    raise SystemExit(check(parser.parse_args().repo.resolve()))
