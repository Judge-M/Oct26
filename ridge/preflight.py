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

:func:`check_narrative` is the narrative half of the same reconciliation. A
deployment that provisions cleanly but has no participant narrative still sends
ten team desktops to a page of bare prompts, and the only symptom a participant
would report is that the exercise made no sense. So the approved contract is
loaded, rendered for both lanes and refused if any section a participant reads is
missing. It is read-only, needs no service and no network.

:func:`check_consistency` is the second half. ``ridge.narrative_consistency``
proves the five participant-facing surfaces - the two lanes, the event-day deck,
the T01 network map and the breadcrumbs - all render the same contract revision,
share one set of fictional names, place every tool the issue names, and leak no
answer key, credential, adversary name or deployment detail. One page rendering
the contract is not the same as five agreeing about it, and only the second fact
is worth checking before a room fills up. Like the narrative check it is
read-only, offline and deterministic, and it names every surface it could not
prove on this host rather than implying it checked them all.
"""
import json
import os
from pathlib import Path
from ridge.transport import post, secret
from ridge.evidence_release import validate_release
from ridge.storage import require_space
from ridge.artifacts import safe
from ridge.scenario import AUTOPSY_CASE_ENTRYPOINT
from ridge.web_narrative import check_deployment


def check_narrative(snapshot=None, questions=None, path=None):
    """Prove the participant narrative is present and complete in this deployment.

    Validates the contract, renders both lanes and checks the render context.
    Read-only, no service and no network, so it runs identically on the
    controller host and inside the integration container that hosts
    ``python -m ridge.cli preflight``.
    """
    return check_deployment(path, snapshot, questions)


def check_consistency(path=None):
    """Prove the integrated surfaces still tell one story.

    Read-only, offline and deterministic, and it degrades honestly: the
    integration container ships the contract and no deck, no map and no
    breadcrumbs, so its receipt names those under ``surfaces_not_proved`` instead
    of claiming a coverage it does not have.
    """
    from ridge import narrative_consistency

    return narrative_consistency.check_deployment(path)


def check_learning_objectives(path=None):
    """Prove the learning objectives still describe this deployment, and carry the NICE gate.

    Read-only, offline and deterministic. It reports rather than raises, because
    the mapping gate is open by design: ``docs/learning-objectives.md`` states
    that its NICE identifiers are unverified candidates, and a deployment receipt
    has to say so out loud rather than fail a preflight over an honest caveat. A
    fixture that does not validate is reported the same way, with the reason, so
    the receipt never claims a coverage this host cannot prove.
    """
    from ridge import learning_objectives

    try:
        document = learning_objectives.build(path)
        receipt = learning_objectives.report(document)
    except learning_objectives.ObjectivesError as error:
        return {'ready': False, 'proved': False, 'reason': str(error)}
    return {'ready': True, 'proved': True, 'revision': receipt['revision'],
            'document': receipt['document'], 'objectives': receipt['objectives'],
            'tickets': receipt['tickets'], 'unclaimed_tickets': receipt['unclaimed'],
            'views': receipt['views'],
            'nice': {'verified': receipt['nice']['verified'],
                     'mappings': receipt['nice']['mappings'],
                     'unverified_mappings': receipt['nice']['unverified_mappings'],
                     'verified_against': receipt['nice']['verified_against'],
                     'reason': receipt['nice']['reason']}}


def check(state, config):
    state.diagnostics()
    narrative=check_narrative()
    consistency=check_consistency()
    objectives=check_learning_objectives()
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
    return {'ready':True,'teams':len(teams),'tickets':len(tickets),
            'narrative':{'contract':narrative['contract'],'revision':narrative['revision'],
                         'surfaces':['ctfd','iris']},
            'consistency':{'contract':consistency['contract'],
                           'revision':consistency['revision'],
                           'surfaces':consistency['surfaces'],
                           'surfaces_not_proved':sorted(consistency['surfaces_not_proved']),
                           'leak_guard':consistency['leak_guard']},
            'learning_objectives':objectives}


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
