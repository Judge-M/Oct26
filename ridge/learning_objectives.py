"""Learning objectives and the NICE mapping, rendered from one fixture (issue 157).

``docs/learning-objectives.md`` used to be prose that had drifted from the
exercise it describes. It told participants to use a single ``silent-ridge-*``
Wazuh view with an absolute UTC range, which cannot produce T12's answers; it
credited four tickets with the 120-second device correction that the code applies
to one; it quoted ticket titles that upstream has since retitled; and it asserted
NICE task identifiers from a framework revision that has been superseded. A
document naming the exercises own views, clock semantics and ticket titles must
not be able to disagree with them, so it is rendered here from
``assets/learning-objectives-v1.json`` and validated against the tree.

Derived, never typed
    The ticket set comes from ``expanded/author.py``, the Wazuh view names from
    ``ridge.wazuh_provision``, the device offset from ``ridge.scenario``, the map
    counts from the T01 network map fixture, the phase partitions from both
    narrative fixtures, the acquisition date from the native manifest and the
    workload figures from ``expanded/config.json``. Widening the tree widens this
    documents obligations instead of leaving a hole in them.

The NICE gate
    The 2.0-era work role and task identifiers are carried as unverified
    candidates. :func:`nice_status` is a gate rather than a claim: it reports
    ``verified: false`` with the number of unverified mappings and refuses to
    call a mapping verified until ``framework.verified_against`` names a dated
    release. The rendered document therefore states the uncertainty instead of
    asserting identifiers nobody has checked. :func:`validate` passes with the
    gate open so the branch is not red on arrival; ``--strict`` is what fails
    while it is open, and ``ridge.preflight`` carries the receipt.

Phase partitions
    Two fixtures in the tree disagree about which ticket belongs to which phase.
    The document names both, names which module reads which, and defers to the
    open decision instead of picking a winner.

No scored answer is reproduced here: the document is published, and a learning
objective that states an answer is a walkthrough with extra steps. :func:`validate`
refuses any fixture string containing a distinctive answer from
``expanded/author.py``, exempting only names that are already participant-visible
in the narrative canon or in the contract's verified ``public_terms``.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = 1
FIXTURE = ROOT / ('assets/learning-objectives-v%d.json' % SCHEMA)
DOCUMENT = ROOT / 'docs/learning-objectives.md'
CONFIG = ROOT / 'expanded/config.json'
NATIVE_MANIFEST = ROOT / 'assets/native-windows-v1/manifest.json'
PHASE_FIXTURES = (ROOT / 'assets/scenario-narrative-v1.json',
                  ROOT / 'ridge/scenario_narrative_v1.json')
PHASE_READERS = (('ridge/scenario_contract.py', PHASE_FIXTURES[0]),
                 ('ridge/narrative.py', PHASE_FIXTURES[1]))
WORKLOAD_TEAMS = 10

REQUIRED_OBJECTIVE_FIELDS = ('id', 'title', 'statement', 'tickets', 'mechanism',
                             'achievement_evidence', 'nice')
REQUIRED_NICE_FIELDS = ('status', 'roles')
REQUIRED_ROLE_FIELDS = ('role_id', 'role', 'candidate_tasks')
REQUIRED_CANDIDATE_FIELDS = ('id', 'statement', 'verified')
REQUIRED_SECTION_FIELDS = ('id', 'heading', 'blocks')
BLOCK_TYPES = ('text', 'bullets', 'numbered', 'table', 'framework', 'phases', 'views',
               'clock', 'map', 'workload', 'objectives', 'crosswalk', 'aar_map',
               'limits', 'maintenance')

# Capabilities the exercise states it does not demonstrate. A candidate mapping is
# a claim that a scored question exercises the capability, so a mapping that names
# one of these is an over-claim whatever its identifier says.
BANNED_CAPABILITIES = ('duplicate', 'notify', 'contain', 'imaging')

# A dated release is what turns an unverified candidate into a verified mapping.
DATED_RELEASE = re.compile(r'\b\d{4}-\d{2}-\d{2}\b')
VIEW_NAME = re.compile(r'silent-ridge-[a-z0-9-]+')
CLOCK_CLAIM = re.compile(r'(T\d{2})[^.\n]{0,80}?(?:120-second|device offset|device clock|'
                         r'corrected time|corrected registration)')
CLOCK_PERMITTED = frozenset({'T04', 'T12'})

WIDTH = 79


class ObjectivesError(ValueError):
    """Raised when the objectives fixture is missing, malformed, drifted or unsafe."""


# --------------------------------------------------------------------------
# reading


def parse(document):
    """Schema-check an already-decoded fixture."""
    if document.get('schema') != SCHEMA:
        raise ObjectivesError('Unknown learning objectives schema: ' + repr(document.get('schema')))
    for field in ('revision', 'title', 'framework', 'objectives', 'sections'):
        if not document.get(field):
            raise ObjectivesError('%s: required fixture section is missing' % field)
    return document


def load(path=None):
    """Read and schema-check the fixture."""
    source = Path(path) if path else FIXTURE
    if not source.is_file():
        raise ObjectivesError('learning objectives fixture not found: ' + str(source))
    return parse(json.loads(source.read_text(encoding='utf-8')))


def authored():
    """The authored tickets, with the native title and answer overrides applied."""
    from expanded.author import build as author

    return author()


def tickets_by_id(tickets=None):
    return {ticket['id']: ticket for ticket in (tickets if tickets is not None else authored())}


def titles(tickets=None):
    return {tid: ticket['title'] for tid, ticket in tickets_by_id(tickets).items()}


# --------------------------------------------------------------------------
# derived facts


def wazuh_views(tickets=None):
    """Which ticket must be read in which saved view, derived from the ticket steps.

    A coverage or catalogue record describes a collection interval and carries no
    event timestamp, so its opening step is overridden to a view without a time
    field. Deriving the partition from the step means an instruction that merges
    every Wazuh ticket into one absolute-range view fails validation instead of
    sending a team to a range that cannot return the rows.
    """
    from ridge.wazuh_provision import TIMED_VIEW, TIMELESS_VIEW

    timeless, timed = [], []
    for ticket in authored_tickets(tickets):
        if ticket['subject'] != 'Wazuh':
            continue
        steps = ' '.join(str(step) for question in ticket['questions']
                         for step in question.get('steps', []))
        (timeless if 'without a time field' in steps else timed).append(ticket['id'])
    return {TIMED_VIEW: timed, TIMELESS_VIEW: timeless}


def authored_tickets(tickets=None):
    return sorted((tickets if tickets is not None else authored()), key=lambda t: t['id'])


def clock_facts(tickets=None):
    """Which ticket applies the device offset, which asks for it, which must not.

    ``ridge.scenario.timestamp`` subtracts ``DEVICE_OFFSETS`` from a ``device_time``
    field and from no other field, so the offset applies to a source that carries
    that field. Among the authored tickets, one asks for a corrected time and one
    asks for the offset value itself; the native reconstruction is a different
    evidence system on a different date and answers that question with ``no``.
    """
    from ridge.scenario import DEVICE_OFFSETS

    host, seconds = next(iter(sorted(DEVICE_OFFSETS.items())))
    applied, asked, forbidden = [], [], []
    for ticket in authored_tickets(tickets):
        native = ticket['title'].startswith('Inspect acquired') or \
            ticket['title'].startswith('Inspect the prepared memory') or \
            ticket['title'].startswith('Correlate the acquired')
        if native:
            forbidden.append(ticket['id'])
        for question in ticket['questions']:
            prompt = str(question['prompt']).lower()
            if 'corrected' in prompt:
                applied.append(ticket['id'])
            if 'seconds fast' in prompt:
                asked.append(ticket['id'])
    return {'host': host, 'seconds': seconds,
            'applied_by': sorted(set(applied)),
            'asked_about': sorted(set(asked)),
            'must_not_apply': sorted(set(forbidden))}


def acquisition_dates():
    """The scenario date and the native acquisition date, which are not the same day."""
    config = json.loads(CONFIG.read_text(encoding='utf-8'))
    manifest = json.loads(NATIVE_MANIFEST.read_text(encoding='utf-8'))
    scenario = str(config['exercise_date'])
    captured = str(manifest['capture']['capture_time_utc'])[:10]
    return {'scenario_date': scenario, 'acquisition_date': captured,
            'scenario_minutes': int(config['activity_minutes']),
            'teams_configured': len(config['teams'])}


def map_facts():
    """Node and edge counts of the T01 network map, read from its own fixture."""
    from ridge.network_map import build as build_map

    document = build_map()
    edges = [edge['confidence'] for edge in document['edges']]
    return {'nodes': len(document['nodes']), 'edges': len(edges),
            'observed': edges.count('observed'), 'inferred': edges.count('inferred'),
            'unlocks_after': document['unlocks_after'],
            'fixture': 'assets/t01-network-map-v1.json'}


def phase_facts():
    """Both ticket-to-phase partitions in the tree, and where they disagree.

    Two fixtures partition the same twenty tickets differently, and which one a
    reader sees depends on which surface rendered it. The disagreement is counted
    per ticket - the sets are identical, so only the phase assignment differs.
    """
    partitions = {}
    for reader, path in PHASE_READERS:
        document = json.loads(path.read_text(encoding='utf-8'))
        entries = [{'id': phase['id'], 'title': phase['title'],
                    'tickets': list(phase['tickets'])} for phase in document['phases']]
        assignment = {ticket: entry['id'] for entry in entries for ticket in entry['tickets']}
        partitions[str(path.relative_to(ROOT)).replace('\\', '/')] = {
            'reader': reader, 'phases': entries, 'assignment': assignment,
            'sizes': [len(entry['tickets']) for entry in entries]}
    names = list(partitions)
    left, right = partitions[names[0]], partitions[names[1]]
    shared = set(left['assignment']) & set(right['assignment'])
    disagreements = sorted(ticket for ticket in shared
                           if left['assignment'][ticket] != right['assignment'][ticket])
    for reader, path in PHASE_READERS:
        if path.name not in (ROOT / reader).read_text(encoding='utf-8'):
            raise ObjectivesError('%s: phase partition reader does not name %s'
                                  % (reader, path.name))
    return {'sources': [dict(partitions[name], fixture=name) for name in names],
            'differ': bool(disagreements),
            'disagreements': len(disagreements),
            'tickets': sorted(shared),
            'total': len(shared)}


def deck_facts():
    """Slide counts of the participant deck and the facilitator appendix."""
    deck = ROOT / 'docs/event-day-deck'
    return {'participant': len(list((deck / 'pages').glob('*.page'))),
            'facilitator': len(list((deck / 'facilitator-pages').glob('*.page')))}


def breadcrumb_facts():
    document = json.loads((ROOT / 'assets/breadcrumbs-v1.json').read_text(encoding='utf-8'))
    return {'count': len(document['breadcrumbs']), 'bonus': bool(document['scoring']['bonus']),
            'rule': str(document['scoring']['rule'])}


def workload_facts(tickets=None):
    from expanded.workload import summary

    dates = acquisition_dates()
    data = summary(tickets if tickets is not None else authored(), teams=WORKLOAD_TEAMS,
                   target_minutes=dates['scenario_minutes'])
    return {'teams': WORKLOAD_TEAMS, 'target_minutes': data['target_minutes'],
            'estimated_team_minutes': data['estimated_team_minutes'],
            'average_team_minutes': data['average_team_minutes'],
            'critical_path_minutes': data['critical_path_minutes'],
            'critical_path': ' -> '.join(data['critical_path_tickets']),
            'makespan_minutes': data['makespan_minutes'], 'tickets': data['tickets'],
            'questions': data['questions']}


def facts(tickets=None):
    """Every derived fact the document and the guards need, computed once."""
    return {'titles': titles(tickets), 'views': wazuh_views(tickets),
            'clock': clock_facts(tickets), 'dates': acquisition_dates(),
            'map': map_facts(), 'phases': phase_facts(), 'deck': deck_facts(),
            'breadcrumbs': breadcrumb_facts(), 'workload': workload_facts(tickets)}


# --------------------------------------------------------------------------
# the NICE gate


def mappings(document):
    """Every candidate mapping as (objective id, role id, task id, statement, verified)."""
    found = []
    for objective in document['objectives']:
        for role in objective['nice']['roles']:
            for task in role['candidate_tasks']:
                found.append((objective['id'], role['role_id'], task['id'],
                              str(task['statement']), bool(task['verified'])))
    return found


def nice_status(document):
    """Report whether the NICE mapping may be called verified. It may not, yet.

    ``verified_against`` has to name a dated release before any mapping counts as
    verified, and a mapping that claims ``verified`` without one is refused
    outright rather than reported: a gate that quietly accepts an undated claim is
    not a gate.
    """
    framework = document['framework']
    release = framework.get('verified_against')
    dated = bool(DATED_RELEASE.search(str(release or '')))
    found = mappings(document)
    claimed = [entry for entry in found if entry[4]]
    if claimed and not dated:
        raise ObjectivesError(
            'objectives[].nice: %d mapping(s) claim verified (%s) but '
            'framework.verified_against is not a dated release; set it to the '
            'catalogue release the identifiers were checked against, or clear '
            'verified' % (len(claimed), ', '.join(entry[2] for entry in claimed)))
    unverified = [entry for entry in found if not entry[4]]
    status = {
        'verified': dated and not unverified,
        'verified_against': release,
        'release_is_dated': dated,
        'mappings': len(found),
        'verified_mappings': len(found) - len(unverified),
        'unverified_mappings': len(unverified),
        'unverified_ids': sorted({entry[2] for entry in unverified}),
        'framework': str(framework.get('current', '')),
        'superseded': str(framework.get('superseded', '')),
    }
    if status['verified']:
        status['reason'] = 'every mapping is checked against ' + str(release)
    elif not dated:
        status['reason'] = ('framework.verified_against is null, so no mapping may be '
                            'called verified; set it to the dated NICE release the '
                            'identifiers were checked against')
    else:
        status['reason'] = ('%d of %d mappings are still unverified candidates'
                            % (len(unverified), len(found)))
    return status


# --------------------------------------------------------------------------
# guards


def visible_terms():
    """Answer strings that are already participant-visible, so exempt from the guard."""
    from ridge.narrative_consistency import CANON
    from ridge.scenario_contract import load as load_contract, public_terms

    exempt = set(public_terms(load_contract()))
    for names in CANON.values():
        exempt.update(str(name) for name in names)
    return {term.lower() for term in exempt}


def fixture_strings(node, path='fixture'):
    """Every prose string in the fixture, as (field, text)."""
    if isinstance(node, dict):
        for key in sorted(node):
            yield from fixture_strings(node[key], '%s.%s' % (path, key))
    elif isinstance(node, list):
        for index, item in enumerate(node):
            yield from fixture_strings(item, '%s.%d' % (path, index))
    elif isinstance(node, str):
        yield path, node


def check_no_answers(document, tickets=None) -> None:
    """Refuse fixture prose that states a distinctive scored answer.

    The document is published. An objective that names its own answer teaches
    nothing the hints do not, and the repository already refuses the same leak in
    the participant-facing narrative, so it is refused here too.
    """
    from ridge.scenario_contract import distinctive_answers

    exempt = visible_terms()
    answers = distinctive_answers(tickets if tickets is not None else authored())
    for field, text in fixture_strings(document):
        haystack = text.lower()
        for answer, question_ids in sorted(answers.items()):
            if answer in exempt or answer not in haystack:
                continue
            raise ObjectivesError('%s: states the answer to %s'
                                  % (field, ', '.join(question_ids)))


def check_objectives(document, known) -> None:
    objectives = document['objectives']
    seen = {}
    for index, objective in enumerate(objectives):
        where = 'objectives[%d]' % index
        for field in REQUIRED_OBJECTIVE_FIELDS:
            if not objective.get(field) and objective.get(field) != []:
                raise ObjectivesError('%s.%s: required field is empty' % (where, field))
        if objective['id'] in seen:
            raise ObjectivesError('%s.id: %s is declared twice' % (where, objective['id']))
        seen[objective['id']] = objective
        for ticket in objective['tickets']:
            if ticket not in known:
                raise ObjectivesError('%s.tickets: %s is not an authored ticket'
                                      % (where, ticket))
            known[ticket].append(objective['id'])
        nice = objective['nice']
        for field in REQUIRED_NICE_FIELDS:
            if not nice.get(field) and nice.get(field) != []:
                raise ObjectivesError('%s.nice.%s: required field is empty'
                                      % (where, field))
        if not nice['roles']:
            raise ObjectivesError('%s.nice.roles: an objective needs at least one '
                                  'candidate work role' % where)
        for position, role in enumerate(nice['roles']):
            role_where = '%s.nice.roles[%d]' % (where, position)
            for field in REQUIRED_ROLE_FIELDS:
                if not role.get(field) and role.get(field) != []:
                    raise ObjectivesError('%s.%s: required field is empty'
                                          % (role_where, field))
            if not role['candidate_tasks']:
                raise ObjectivesError('%s.candidate_tasks: a role needs at least one '
                                      'candidate task' % role_where)
            for task in role['candidate_tasks']:
                for field in REQUIRED_CANDIDATE_FIELDS:
                    if field not in task:
                        raise ObjectivesError('%s.candidate_tasks: missing %s'
                                              % (role_where, field))
                statement = str(task['statement']).lower()
                for banned in BANNED_CAPABILITIES:
                    if banned in statement:
                        raise ObjectivesError(
                            '%s.candidate_tasks: %s %r claims %r, which the exercise '
                            'states it does not demonstrate; an unverified mapping is '
                            'not the place to assert it'
                            % (role_where, task['id'], task['statement'], banned))
    missing = sorted(ticket for ticket, owners in known.items() if not owners)
    if missing:
        raise ObjectivesError('objectives: no objective claims %s' % ', '.join(missing))
    for entry in document['objectives']:
        nice = entry['nice']
        if nice['status'] not in ('unverified', 'verified'):
            raise ObjectivesError('objectives[%s].nice.status: %r is not unverified '
                                  'or verified' % (entry['id'], nice['status']))


def check_views(document, derived) -> None:
    """The document may only name real saved views, and T12 must be the timeless one."""
    from ridge.wazuh_provision import TIMED_VIEW, TIMELESS_VIEW

    views = {name: entry for name, entry in (document.get('views') or {}).items()
             if name.startswith('silent-ridge-')}
    meta = {name: value for name, value in (document.get('views') or {}).items()
            if not name.startswith('silent-ridge-')}
    for name in sorted(views):
        if name not in derived:
            raise ObjectivesError('views: %r is not a Wazuh saved view; the deployment '
                                  'provisions %s' % (name, ' and '.join(sorted(derived))))
    for field, text in fixture_strings(document):
        for name in VIEW_NAME.findall(text):
            if name not in derived and not name.endswith('-*'):
                raise ObjectivesError('%s: names %r, which is not a provisioned view; '
                                      'use %s or %s'
                                      % (field, name, TIMED_VIEW, TIMELESS_VIEW))
    if not str(meta.get('rule', '')).strip():
        raise ObjectivesError('views.rule: state how a participant chooses the view')
    if TIMELESS_VIEW not in views:
        raise ObjectivesError('views.%s: the timeless view must be documented; a '
                              'coverage record carries no event timestamp'
                              % TIMELESS_VIEW)
    documented = set(views[TIMELESS_VIEW]['tickets'])
    expected = set(derived[TIMELESS_VIEW])
    if documented != expected:
        raise ObjectivesError(
            'views.%s.tickets: documented %s, but the authored ticket steps put %s in '
            'the view without a time field. One absolute-range view cannot answer a '
            'coverage record; fix the fixture, not the check'
            % (TIMELESS_VIEW,
               ', '.join(sorted(documented)) or 'nothing',
               ', '.join(sorted(expected)) or 'nothing'))
    timed = set(views.get(TIMED_VIEW, {}).get('tickets', ()))
    if timed & documented:
        raise ObjectivesError('views: %s is documented in both saved views'
                              % ', '.join(sorted(timed & documented)))
    for name in sorted(views):
        for ticket in views[name]['tickets']:
            if ticket in derived[TIMELESS_VIEW] and name != TIMELESS_VIEW:
                raise ObjectivesError('views.%s.tickets: %s is a coverage record and is '
                                      'read in the view without a time field'
                                      % (name, ticket))
    if timed | documented != set(derived[TIMED_VIEW]) | set(derived[TIMELESS_VIEW]):
        raise ObjectivesError('views: the documented Wazuh tickets do not match the '
                              'authored Wazuh tickets %s'
                              % ', '.join(sorted(set(derived[TIMED_VIEW])
                                                 | set(derived[TIMELESS_VIEW]))))


def check_clock(document, derived) -> None:
    """Only the ticket the code corrects may be documented as applying the offset."""
    clock = document.get('clock') or {}
    for field in ('host', 'seconds', 'applied_by', 'asked_about', 'must_not_apply'):
        if field not in clock:
            raise ObjectivesError('clock.%s: required field is missing' % field)
    if clock['host'] != derived['host'] or int(clock['seconds']) != derived['seconds']:
        raise ObjectivesError('clock: documented a %s s offset for %s; ridge.scenario.'
                              'DEVICE_OFFSETS says %s s for %s'
                              % (clock['seconds'], clock['host'], derived['seconds'],
                                 derived['host']))
    for field in ('applied_by', 'asked_about', 'must_not_apply'):
        documented = sorted(set(clock[field]))
        if documented != derived[field]:
            raise ObjectivesError('clock.%s: documented %s; derived from expanded/author.py '
                                  'it is %s. A correction is applied where the source '
                                  'carries a device_time field, nowhere else'
                                  % (field, ', '.join(documented) or 'nothing',
                                     ', '.join(derived[field]) or 'nothing'))
    for field, text in fixture_strings(document):
        for ticket in CLOCK_CLAIM.findall(text):
            if ticket not in CLOCK_PERMITTED:
                raise ObjectivesError(
                    '%s: attributes the device clock correction to %s; only %s applies '
                    'it and only %s asks for it'
                    % (field, ticket, ', '.join(sorted(CLOCK_PERMITTED - {'T12'})),
                       ', '.join(sorted(CLOCK_PERMITTED - {'T04'}))))


def check_dates(document, derived) -> None:
    dates = document.get('acquisition') or {}
    for field in ('scenario_date', 'acquisition_date'):
        if not dates.get(field):
            raise ObjectivesError('acquisition.%s: both dates must be stated' % field)
    if dates['scenario_date'] == dates['acquisition_date']:
        raise ObjectivesError('acquisition: the scenario date and the native acquisition '
                              'date are stated as the same day; their divergence is the '
                              'provenance lesson')
    if dates['scenario_date'] != derived['scenario_date']:
        raise ObjectivesError('acquisition.scenario_date: documented %s; expanded/config.json'
                              ' sets %s' % (dates['scenario_date'], derived['scenario_date']))
    if dates['acquisition_date'] != derived['acquisition_date']:
        raise ObjectivesError('acquisition.acquisition_date: documented %s; the native '
                              'manifest records %s'
                              % (dates['acquisition_date'], derived['acquisition_date']))


def check_workload(document, derived) -> None:
    """The duration figures are derived, and the block must actually state them."""
    workload = document.get('workload') or {}
    if not str(workload.get('text', '')).strip():
        raise ObjectivesError('workload.text: the estimate note is required')
    notes = [str(workload['text'])] + [str(note) for note in workload.get('notes', ())]
    placeholders = set()
    for note in notes:
        placeholders.update(re.findall(r'\{([a-z_]+)\}', note))
    unknown = sorted(placeholders - set(derived))
    if unknown:
        raise ObjectivesError('workload: %s are not derived figures'
                              % ', '.join('{%s}' % name for name in unknown))
    for required in ('makespan_minutes', 'target_minutes'):
        if required not in placeholders:
            raise ObjectivesError('workload: the simulated makespan and the configured '
                                  'target must be stated as derived figures; a vaguer '
                                  'restatement of the goal is what this block replaced')


def check_crosswalk(document, derived) -> None:
    """A quoted ticket title must be the title the tree carries today."""
    current = derived['titles']
    crosswalk = (document.get('crosswalk') or {}).get('rows') or []
    if not crosswalk:
        raise ObjectivesError('crosswalk: at least one ticket group is required')
    covered = set()
    for index, row in enumerate(crosswalk):
        where = 'crosswalk[%d]' % index
        for field in ('id', 'tickets', 'titles', 'theme', 'primary_role', 'supporting'):
            if field not in row:
                raise ObjectivesError('%s.%s: required field is missing' % (where, field))
        if len(row['titles']) != len(row['tickets']):
            raise ObjectivesError('%s.titles: one title is required per ticket' % where)
        for ticket, title in sorted(zip(row['tickets'], row['titles'])):
            covered.add(ticket)
            if title != current.get(ticket):
                raise ObjectivesError('%s.titles: %s is %r in expanded/author.py, not %r'
                                      % (where, ticket, current.get(ticket), title))
    missing = sorted(set(current) - covered)
    if missing:
        raise ObjectivesError('crosswalk: no row covers %s' % ', '.join(missing))
    for index, row in enumerate((document.get('aar_map') or {}).get('rows') or []):
        if 'prompt' not in row or 'objectives' not in row:
            raise ObjectivesError('aar_map[%d]: prompt and objectives are required' % index)
        for name in row['objectives']:
            if name not in {entry['id'] for entry in document['objectives']}:
                raise ObjectivesError('aar_map[%d].objectives: %s is not an objective'
                                      % (index, name))


def check_phases(document, derived) -> None:
    phases = document.get('phases') or {}
    sources = phases.get('sources') or []
    if len(sources) != len(PHASE_FIXTURES):
        raise ObjectivesError('phases.sources: name both fixtures that partition the '
                              'tickets; there are %d in the tree' % len(PHASE_FIXTURES))
    known = {entry['fixture'] for entry in derived['sources']}
    for source in sources:
        if source['fixture'] not in known:
            raise ObjectivesError('phases.sources: %s is not a phase fixture in the tree'
                                  % source['fixture'])
        if not str(phases.get('decision', '')).strip():
            raise ObjectivesError('phases.decision: the open decision must be named')
    if not derived['differ']:
        raise ObjectivesError('phases: the two fixtures now agree, so this document must '
                              'not keep calling the partition a conflict')
    if not str(phases.get('consequence', '')).strip():
        raise ObjectivesError('phases.consequence: state what a reader must do while the '
                              'partition is undecided')


def check_sections(document) -> None:
    ids = set()
    for index, section in enumerate(document['sections']):
        where = 'sections[%d]' % index
        for field in REQUIRED_SECTION_FIELDS:
            if field not in section:
                raise ObjectivesError('%s.%s: required field is missing' % (where, field))
        if section['id'] in ids:
            raise ObjectivesError('%s.id: %s is declared twice' % (where, section['id']))
        ids.add(section['id'])
        if not section['blocks']:
            raise ObjectivesError('%s.blocks: a section needs at least one block'
                                  % where)
        for position, block in enumerate(section['blocks']):
            if block.get('type') not in BLOCK_TYPES:
                raise ObjectivesError('%s.blocks[%d].type: %r is not a block type (%s)'
                                      % (where, position, block.get('type'),
                                         ', '.join(BLOCK_TYPES)))
    for needed in ('objectives', 'crosswalk', 'limits', 'maintenance'):
        if needed not in ids:
            raise ObjectivesError('sections: the %r section is required' % needed)


def validate(document, tickets=None, strict=False, derived=None):
    """Every guard. Raises ObjectivesError naming the field that is wrong."""
    facts_ = derived if derived is not None else facts(tickets)
    known = {tid: [] for tid in facts_['titles']}
    check_sections(document)
    check_objectives(document, known)
    check_views(document, facts_['views'])
    check_clock(document, facts_['clock'])
    check_dates(document, facts_['dates'])
    check_workload(document, facts_['workload'])
    check_crosswalk(document, facts_)
    check_phases(document, facts_['phases'])
    check_no_answers(document, tickets)
    status = nice_status(document)
    if strict and not status['verified']:
        raise ObjectivesError('nice gate: %d unverified mapping(s) against %s; %s'
                              % (status['unverified_mappings'], status['framework'] or '?',
                                 status['reason']))
    return status


def build(path=None, tickets=None):
    """Load, validate and return the fixture ready for rendering."""
    document = load(path)
    validate(document, tickets)
    return document


def report(document, tickets=None, derived=None):
    """The deterministic receipt: what the document asserts, and what gates it."""
    facts_ = derived if derived is not None else facts(tickets)
    owners = {tid: [] for tid in facts_['titles']}
    for objective in document['objectives']:
        for ticket in objective['tickets']:
            owners[ticket].append(objective['id'])
    return {
        'schema': SCHEMA,
        'revision': document['revision'],
        'document': str(DOCUMENT.relative_to(ROOT)).replace('\\', '/'),
        'tickets': len(facts_['titles']),
        'objectives': len(document['objectives']),
        'claims': {tid: owners[tid] for tid in sorted(owners)},
        'unclaimed': sorted(tid for tid, held in owners.items() if not held),
        'views': facts_['views'],
        'clock': facts_['clock'],
        'dates': facts_['dates'],
        'phases': {'sources': [{'fixture': source['fixture'], 'reader': source['reader'],
                                'sizes': source['sizes']} for source in facts_['phases']['sources']],
                   'disagreements': facts_['phases']['disagreements'],
                   'differ': facts_['phases']['differ']},
        'map': facts_['map'],
        'workload': facts_['workload'],
        'nice': nice_status(document),
    }


# --------------------------------------------------------------------------
# rendering

HEADER = ('<!-- Generated by python -m ridge.learning_objectives --write from\n'
          '     assets/learning-objectives-v%d.json. Edit the fixture, not this file. -->\n' % SCHEMA)


def _wrap(text, indent='', first=None):
    """Wrap one fixture string to the document width, honouring its own breaks.

    A fixture string may place a line break where the reader should see one; every
    other break is mechanical. Rendering is therefore deterministic and reviewable
    without the generator having to guess where a sentence wanted to end.
    """
    lead = indent if first is None else first
    return '\n'.join(
        textwrap.fill(part, width=WIDTH, initial_indent=lead if index == 0 else indent,
                      subsequent_indent=indent, break_long_words=False,
                      break_on_hyphens=False)
        for index, part in enumerate(str(text).split('\n')))


def _table(columns, rows):
    lines = ['| ' + ' | '.join(columns) + ' |',
             '|' + '|'.join('---' for _ in columns) + '|']
    for row in rows:
        lines.append('| ' + ' | '.join(str(cell) for cell in row) + ' |')
    return lines


def _tickets(ids):
    return ', '.join('`%s`' % tid for tid in ids)


def _framework(document, facts_):
    framework = document['framework']
    status = nice_status(document)
    lines = ['## ' + framework['heading'], '']
    for field in ('base', 'supersession_note', 'verification_required', 'withdrawn'):
        if framework.get(field):
            lines += [_wrap(str(framework[field])), '']
    lines += _table(['Publication', 'Status in this document'], [
        [framework.get('current', ''), 'current base publication'],
        [framework.get('superseded', ''), 'superseded; recorded as provenance only'],
        ['`framework.verified_against`',
         'null' if not status['verified_against'] else status['verified_against']],
    ]) + ['']
    lines += [_wrap('**Gate.** `verified: %s`. %d of %d candidate mappings (%d distinct '
                    'identifiers) are unverified. %s.'
                    % (str(status['verified']).lower(), status['unverified_mappings'],
                       status['mappings'], len(status['unverified_ids']), status['reason'])),
             '']
    return lines


def _phases(document, facts_):
    phases = document['phases']
    lines = ['## ' + phases['heading'], '']
    for field in ('intro', 'conflict', 'decision', 'consequence'):
        if phases.get(field):
            lines += [_wrap(str(phases[field])), '']
    rows = []
    for source in facts_['phases']['sources']:
        rows.append(['`%s`' % source['fixture'], source['reader'],
                     ', '.join(entry['id'] for entry in source['phases']),
                     ' / '.join(str(size) for size in source['sizes'])])
    lines += _table(['Fixture', 'Read by', 'Phase ids', 'Tickets per phase'], rows) + ['']
    lines += [_wrap('The two partitions assign a different phase to %d of the %d tickets.'
                    % (facts_['phases']['disagreements'], facts_['phases']['total'])), '']
    return lines


def _views(document, facts_):
    block = document['views']
    views = {name: entry for name, entry in block.items()
             if name.startswith('silent-ridge-')}
    lines = ['## ' + block['heading'], '']
    for field in ('intro', 'rule', 'history'):
        if block.get(field):
            lines += [_wrap(str(block[field])), '']
    rows = []
    for name in sorted(views, key=lambda entry: (entry != 'silent-ridge-timed', entry)):
        entry = views[name]
        rows.append([_tickets(entry['tickets']), '`%s`' % name, entry['reason']])
    lines += _table(['Tickets', 'Saved view', 'Why'], rows) + ['']
    return lines


def _clock(document, facts_):
    clock = document['clock']
    dates = document['acquisition']
    lines = ['## ' + clock['heading'], '']
    for field in ('intro', 'rule', 'dates'):
        if clock.get(field):
            lines += [_wrap(str(clock[field]).format(**dates)), '']
    rows = [
        ['Device offset', '%s is %d seconds fast'
         % (clock['host'], clock['seconds']), '`ridge/scenario.py` `DEVICE_OFFSETS`'],
        ['Tickets that apply the correction', _tickets(clock['applied_by']),
         'their questions ask for a corrected time'],
        ['Tickets that ask for the offset itself', _tickets(clock['asked_about']),
         'the coverage record states the drift'],
        ['Tickets that must not be corrected', _tickets(clock['must_not_apply']),
         'native records; one of them answers that question with `no`'],
        ['Scenario date', dates['scenario_date'], '`expanded/config.json`'],
        ['Native acquisition date', dates['acquisition_date'],
         '`assets/native-windows-v1/manifest.json`'],
    ]
    lines += _table(['Fact', 'Value', 'Source'], rows) + ['']
    return lines


def _map(document, facts_):
    block = document['network_map']
    facts_map = facts_['map']
    lines = ['## ' + block['heading'], '']
    for field in ('intro', 'gating', 'labels'):
        if block.get(field):
            lines += [_wrap(str(block[field])), '']
    lines += [_wrap('Counts read from `%s`: %d nodes, %d edges, %d observed in a single '
                    'record and %d inferred by joining records.'
                    % (facts_map['fixture'], facts_map['nodes'], facts_map['edges'],
                       facts_map['observed'], facts_map['inferred'])), '']
    return lines

def _workload(document, facts_):
    block = document['workload']
    derived = facts_['workload']
    lines = ['## ' + block['heading'], '']
    lines += [_wrap(str(block['text']).format(**derived)), '']
    for note in block.get('notes', ()):
        lines += [_wrap(str(note).format(**derived)), '']
    return lines


def _objectives(document, facts_):
    lines = ['## ' + document['objectives_heading'], '']
    for field in ('objectives_intro', 'objectives_axis_note'):
        if document.get(field):
            lines += [_wrap(str(document[field])), '']
    for objective in document['objectives']:
        lines.append('### %s - %s' % (objective['id'], objective['title']))
        lines.append('')
        lines += [_wrap(objective['statement']), '']
        lines += [_wrap('**Tickets.** ' + _tickets(objective['tickets'])
                        + ' (%d of %d).' % (len(objective['tickets']),
                                           len(facts_['titles']))), '']
        lines += [_wrap('**Mechanism.** ' + objective['mechanism']), '']
        lines += [_wrap('**Achievement evidence.** ' + objective['achievement_evidence']), '']
        rows = []
        for role in objective['nice']['roles']:
            tasks = '; '.join('`%s` %s' % (task['id'], task['statement'])
                              for task in role['candidate_tasks'])
            rows.append(['%s `%s`' % (role['role'], role['role_id']), tasks])
        lines += _table(['Work role (candidate)', 'Candidate tasks (unverified)'], rows) + ['']
    return lines


def _crosswalk(document, facts_):
    lines = ['## ' + document['crosswalk']['heading'], '']
    if document['crosswalk'].get('intro'):
        lines += [_wrap(str(document['crosswalk']['intro'])), '']
    rows = []
    for row in document['crosswalk']['rows']:
        rows.append([_tickets(row['tickets']), ' / '.join(row['theme']) if isinstance(
            row['theme'], list) else row['theme'], row['primary_role'],
                     ' / '.join(row['supporting'])])
    lines += _table(['Tickets', 'Tool / theme', 'Primary work role',
                     'Supporting roles'], rows) + ['']
    lines += ['| Ticket | Current title |', '|---|---|']
    for tid, title in sorted(facts_['titles'].items()):
        lines.append('| `%s` | %s |' % (tid, title))
    lines.append('')
    return lines


def _aar_map(document, facts_):
    block = document['aar_map']
    lines = ['## ' + block['heading'], '']
    if block.get('intro'):
        lines += [_wrap(str(block['intro'])), '']
    lines += _table(['AAR prompt', 'Objectives most exercised'],
                    [[row['prompt'], ', '.join(row['objectives'])]
                     for row in document['aar_map']['rows']]) + ['']
    return lines


def _limits(document, facts_):
    lines = ['## ' + document['limits']['heading'], '']
    for entry in document['limits']['entries']:
        lines += ['- ' + _wrap(entry['title'] + ' ' + entry['text'], indent='  ')[2:], '']
    return lines


def _maintenance(document, facts_):
    block = document['maintenance']
    lines = ['## ' + block['heading'], '']
    for field in ('commands', 'derived', 'nice'):
        if block.get(field):
            lines += [_wrap(str(block[field])), '']
    return lines


def render(document, tickets=None, derived=None):
    """Render the committed document from the fixture. Deterministic, offline."""
    facts_ = derived if derived is not None else facts(tickets)
    lines = ['# ' + document['title'], '', HEADER.rstrip('\n'), '']
    for field in ('intro', 'status'):
        if document.get(field):
            lines += [_wrap(str(document[field])), '']
    handlers = {'framework': _framework, 'phases': _phases, 'views': _views, 'clock': _clock,
                'map': _map, 'workload': _workload, 'objectives': _objectives,
                'crosswalk': _crosswalk, 'aar_map': _aar_map, 'limits': _limits,
                'maintenance': _maintenance}
    for section in document['sections']:
        if section.get('heading'):
            lines += ['## ' + section['heading'], '']
        for block in section['blocks']:
            kind = block['type']
            if kind in handlers:
                lines += handlers[kind](document, facts_)
                continue
            if kind == 'text':
                lines += [_wrap(block['text']), '']
            elif kind in ('bullets', 'numbered'):
                if lines and lines[-1] != '':
                    lines.append('')
                for index, item in enumerate(block['items'], 1):
                    lead = '- ' if kind == 'bullets' else '%d. ' % index
                    lines.append(textwrap.fill(str(item), width=WIDTH, initial_indent=lead,
                                               subsequent_indent=' ' * len(lead),
                                               break_long_words=False,
                                               break_on_hyphens=False))
                lines.append('')
            elif kind == 'table':
                lines += _table(block['columns'], block['rows']) + ['']
            else:  # pragma: no cover - check_sections refuses anything else
                raise ObjectivesError('unknown block type: ' + kind)
    while lines and not lines[-1]:
        lines.pop()
    return '\n'.join(lines) + '\n'


def write(path=None, document=None, tickets=None):
    """Write the generated document. Returns the path written."""
    document = document or build(tickets=tickets)
    target = Path(path) if path else DOCUMENT
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render(document, tickets), encoding='utf-8', newline='\n')
    return target


def main(argv=None):
    parser = argparse.ArgumentParser(
        description='Validate and regenerate docs/learning-objectives.md.')
    parser.add_argument('--write', action='store_true',
                        help='regenerate the committed document from the fixture')
    parser.add_argument('--report', action='store_true', help='print the validation receipt')
    parser.add_argument('--strict', action='store_true',
                        help='also fail while the NICE mapping gate is open')
    parser.add_argument('--path', type=Path, default=None, help='override the fixture path')
    parser.add_argument('--document', type=Path, default=None,
                        help='override the document path')
    arguments = parser.parse_args(argv)

    document = load(arguments.path)
    tickets = authored()
    derived = facts(tickets)
    try:
        if arguments.write:
            target = write(arguments.document, document, tickets)
            validate(document, tickets, derived=derived)
            print(json.dumps({'written': str(target), 'revision': document['revision']}, indent=2))
            return 0
        status = validate(document, tickets, strict=arguments.strict, derived=derived)
    except ObjectivesError as error:
        print('learning objectives check failed: %s' % error, file=sys.stderr)
        return 1
    if arguments.report:
        print(json.dumps(report(document, tickets, derived), indent=2))
        return 0
    print('learning objectives OK: %d objectives over %d tickets; NICE gate open with '
          '%d unverified mapping(s) (%s)'
          % (len(document['objectives']), len(derived['titles']),
             status['unverified_mappings'], status['framework']))
    return 0


if __name__ == '__main__':
    sys.exit(main())
