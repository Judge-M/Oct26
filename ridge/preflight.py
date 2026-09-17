"""Read-only deployment reconciliation before provisioning or going live.

The controller's :func:`check` verifies the read-only released source inventory under
``RIDGE_EVIDENCE_PUBLIC``. It never requires the writable Autopsy case database: an
Autopsy question references a released source under ``/evidence`` and names its
desktop case entrypoint separately (``ridge.scenario.AUTOPSY_CASE_ENTRYPOINT``).
Each desktop verifies its own writable case with :func:`check_desktop`.

Backward compatibility: tickets generated before this contract referenced
``/evidence/autopsy/WS17/WS17.aut``, which never existed on the evidence mount.
:func:`check` now rejects those paths with an explicit message. Regenerate tickets
with ``python expanded/author.py``.
"""
import json
import os
from pathlib import Path
from ridge.transport import post, secret
from ridge.evidence_release import validate_release
from ridge.storage import require_space
from ridge.artifacts import safe
from ridge.scenario import AUTOPSY_CASE_ENTRYPOINT


def check(state, config):
    state.diagnostics()
    with state.transaction(write=False) as con:
        teams=[dict(r) for r in con.execute('SELECT * FROM teams ORDER BY id')]
        tickets=[dict(r) for r in con.execute('SELECT * FROM tickets')]
        questions=[json.loads(r[0]) for r in con.execute('SELECT body FROM questions')]
    configured={team['id']:team for team in config['teams']}
    if set(configured) != {team['id'] for team in teams}:
        raise ValueError('Configured teams differ from initialized state')
    for team in teams:
        expected=configured[team['id']]
        if str(expected['iris']) != team['iris'] or expected['ctfd'] != team['ctfd']:
            raise ValueError('Application mapping differs from initialized state')
        if not expected.get('iris_login') or not expected.get('ctfd_name'):
            raise ValueError('Record expected iris_login and ctfd_name for every team')
    for application in ('IRIS','CTFD'):
        identities=[team[application.lower()] for team in teams]
        result=post(os.environ[application+'_URL']+'/silent-ridge/internal',secret('RIDGE_'+application),
                    {'kind':'preflight','key':'preflight','payload':{'identities':identities}},header='X-Ridge-Key')
        if result.get('ready') is not True:
            raise ValueError(application+' adapter is not ready')
        actual={str(row['id']):row['name'] for row in result['identities']}
        for team in teams:
            field='iris_login' if application=='IRIS' else 'ctfd_name'
            if actual.get(str(team[application.lower()])) != configured[team['id']][field]:
                raise ValueError(application+' identity does not match configured name')
    target=Path(os.environ['RIDGE_EVIDENCE_PUBLIC'])
    if not target.is_dir():
        raise ValueError('Published evidence directory is not mounted')
    require_space(target)
    require_space(state.path.parent)
    for ticket in tickets:
        validate_release(ticket['id'],json.loads(ticket['release_files']))
    delayed={name for ticket in tickets for name in json.loads(ticket['release_files'])}
    for question in questions:
        evidence=question.get('evidence','')
        if not evidence.startswith('/evidence/'):
            raise ValueError('Question lacks an explicit evidence path')
        name=evidence.removeprefix('/evidence/')
        # The Autopsy .aut case is a writable desktop entrypoint, never released evidence.
        if name.startswith('autopsy/') or name.endswith('.aut'):
            raise ValueError('Autopsy case paths are desktop entrypoints, not released evidence; regenerate tickets')
        if name not in delayed and not safe(target,name).is_file():
            raise ValueError('Required initial evidence is missing: '+name)
        if question.get('tool')=='Autopsy' and question.get('case_entrypoint')!=AUTOPSY_CASE_ENTRYPOINT:
            raise ValueError('Autopsy question must name the desktop case entrypoint: '+AUTOPSY_CASE_ENTRYPOINT)
    # Verify the local TLS trust chain, credential, and historical index without writing.
    import base64
    import re
    from urllib.request import Request, urlopen
    index_name=os.environ['WAZUH_INDEX']
    if not re.fullmatch(r'silent-ridge-[a-z0-9-]+',index_name):
        raise ValueError('Dedicated historical index required')
    credential=Path(os.environ['WAZUH_INDEX_CREDENTIAL_FILE']).read_text(encoding='utf-8').strip()
    request=Request(os.environ['WAZUH_INDEXER_URL'].rstrip('/')+'/'+index_name,
                    headers={'Authorization':'Basic '+base64.b64encode(credential.encode()).decode()})
    with urlopen(request,timeout=8) as response:
        if index_name not in json.load(response):
            raise ValueError('Historical index is not available')
    return {'ready':True,'teams':len(teams),'tickets':len(tickets)}


def check_desktop(questions, home, template=None):
    """Desktop readiness: each declared writable case must exist on this desktop.

    Deliberately separate from :func:`check`. The controller verifies the read-only
    released sources; the desktop verifies its own writable prepared case, so no
    writable case database is ever required on the shared evidence mount.
    """
    home=Path(home)
    cases=set()
    for question in questions:
        entry=question.get('case_entrypoint')
        if not entry:
            continue
        if not entry.startswith('~/'):
            raise ValueError('Desktop case entrypoint must be home-relative: '+str(entry))
        cases.add(home/entry.removeprefix('~/'))
    if not cases:
        raise ValueError('No prepared-case entrypoint is declared')
    for path in sorted(cases):
        if not path.is_file() or path.stat().st_size==0:
            raise ValueError('Desktop prepared case is missing: '+str(path))
    if template is not None and not Path(template).exists():
        raise ValueError('Prepared case template is missing: '+str(template))
    return {'ready':True,'cases':len(cases)}
