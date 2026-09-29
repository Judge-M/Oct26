"""Participant narrative render context for the shared CTFd/IRIS page.

``ridge.web.PAGE`` is one Jinja template rendered by both lanes, and until now it
carried a one-sentence blurb plus a scoring reminder. Participants saw prompts
with no event, no role, no stake and no sense of how a ticket connects to the
IRIS case. This module turns the approved contract into the render context that
closes that gap, so both lanes read from one source.

Two properties matter more than the prose it assembles.

Pure
    Every function here is a total function of its arguments. No Jinja, no Flask,
    no HTTP, no clock, no module-level state, so the whole narrative can be
    asserted in a unit test and reproduced byte-for-byte on any host.

Unreachable facilitator material
    The assembler copies named contract fields and named question fields. It
    never walks a record generically, so the scored ``answer`` on a question body
    cannot reach the render context even if a field is added upstream, and
    nothing under ``facilitator/`` is ever read. ``ridge/preflight.py`` proves
    the rendered result is complete before an event starts.

Composition, not authorship
    Per-question prose is assembled from the ticket's own narrative and the tool
    map, never written here. A surface cannot introduce a second source of
    scenario text, which is the drift this contract exists to prevent.
"""
from ridge.scenario_contract import (
    CONTRACT_ID, REQUIRED_BOUNDARY_FIELDS, REQUIRED_TICKET_FIELDS, phase_of,
)

# Render-context keys. Every one is rendered by ridge.web.PAGE on at least one
# lane, and tests/test_web_narrative.py holds the template to that claim.
CONTEXT_KEYS = (
    'briefing', 'roles', 'tool_map', 'phases', 'narrative_tickets', 'questions',
    'hints_policy', 'accepted', 'ticket_complete', 'exercise_complete', 'boundaries',
)

# Fields copied out of an authored question (expanded/author.py). Deliberately a
# closed list: the body also carries the scored 'answer', which must never be
# rendered, and 'selection', which is already shown inside 'steps'. 'ticket' is
# the bridge's own link back to the ticket, and Side A's markup reads it to place
# the per-ticket phase, so the decorated card has to carry it.
QUESTION_FIELDS = ('id', 'ticket', 'prompt', 'purpose', 'tool', 'evidence', 'steps', 'format',
                   'recovery')
FINDING_FIELDS = ('text', 'evidence', 'limitation')
# Hint lead-ins, in the order a question offers its help levels.
HINT_LEVELS = ('level_one', 'level_two', 'level_three')
# Always-true accepted-answer lines, shown once per page rather than per card.
ACCEPTED_GUIDANCE = ('credit', 'shared')


class NarrativeError(ValueError):
    """Raised when a deployment is missing participant narrative; message names it."""


def _text(value) -> str:
    return '' if value is None else str(value)


def briefing(contract) -> dict:
    """The event introduction: what this is, how it was found, what is at stake."""
    exercise = contract.get('exercise', {})
    return {field: _text(exercise.get(field)) for field in
            ('codename', 'fiction_notice', 'classification_line', 'premise', 'discovery',
             'stakes')}


def roles(contract) -> list:
    """Participant role cards: duty, authority, and the explicit limit of each."""
    return [{'name': _text(role.get('name')), 'duty': _text(role.get('duty')),
             'authority': _text(role.get('authority')), 'not': _text(role.get('not'))}
            for role in contract.get('roles', [])]


def tool_map(contract) -> list:
    """Which surface answers which class of question, and what it cannot show."""
    return [{'surface': _text(entry.get('surface')), 'lane': _text(entry.get('lane')),
             'text': _text(entry.get('text'))}
            for entry in contract.get('tool_map', [])]


def phases(contract) -> list:
    """The investigation phases, each naming the tickets it claims."""
    return [{'id': _text(phase.get('id')), 'title': _text(phase.get('title')),
             'timeframe': _text(phase.get('timeframe')), 'purpose': _text(phase.get('purpose')),
             'urgency': _text(phase.get('urgency')), 'action': _text(phase.get('action')),
             'transition': _text(phase.get('transition')),
             'tickets': [_text(tid) for tid in phase.get('tickets', [])]}
            for phase in contract.get('phases', [])]


def ticket_narrative(contract, snapshot=None) -> dict:
    """Per-ticket headline, brief, stakes, why-now, next step and phase handoff.

    ``complete`` is derived from the snapshot so a lane can show what closing a
    ticket means; the text it shows still comes from ``ticket_complete``.
    """
    closed = {_text(row.get('id')) for row in (snapshot or {}).get('tickets', [])
              if row.get('status') == 'complete'}
    rendered = {}
    for ticket_id, entry in sorted(contract.get('tickets', {}).items()):
        phase = phase_of(contract, ticket_id)
        if phase is None:
            raise NarrativeError('tickets.%s: no phase, so the ticket has no narrative' % ticket_id)
        record = {field: _text(entry.get(field)) for field in REQUIRED_TICKET_FIELDS
                  if field != 'transition'}
        record['next'] = _text(entry.get('transition'))
        record.update(phase_id=_text(phase.get('id')), phase_title=_text(phase.get('title')),
                      phase_timeframe=_text(phase.get('timeframe')),
                      phase_transition=_text(phase.get('transition')),
                      complete=ticket_id in closed)
        rendered[ticket_id] = record
    return rendered


def tool_note(contract, tool) -> str:
    """The tool map entry for a question's tool, or '' when the tool is unmapped."""
    for entry in tool_map(contract):
        if entry['surface'] == _text(tool):
            return '%s: %s' % (entry['lane'], entry['text'])
    return ''


def matters(contract, ticket_id, question) -> str:
    """Why one question matters: its ticket's stake, then what its tool can show.

    Derived, never authored. The ticket narrative says what the answer is for; the
    tool map says what class of claim the evidence can carry. That is enough to
    stop a question card reading as an isolated prompt, and it adds no second
    prose source that could drift from the contract.
    """
    entry = contract.get('tickets', {}).get(ticket_id, {})
    parts = [_text(entry.get('stakes')), tool_note(contract, question.get('tool'))]
    return ' '.join(part for part in parts if part)


def question_narrative(contract, question, tickets) -> dict:
    """Decorate one authored question for the render context.

    Named fields only, so the scored answer on the authored body is dropped here
    and never referenced again. The bridge has to carry the whole body to reach
    this function; nothing after it needs the answer.
    """
    ticket_id = _text(question.get('ticket'))
    if not ticket_id or ticket_id not in tickets:
        raise NarrativeError('questions: %s names no known ticket, so it has no narrative'
                             % question.get('id'))
    entry = tickets[ticket_id]
    hints = contract.get('hints', {})
    levels = [_text(hints.get(name)) for name in HINT_LEVELS]
    finding = question.get('finding') if question.get('solved_by') else None
    record = {field: question.get(field) for field in QUESTION_FIELDS}
    record.update(headline=entry['headline'], brief=entry['brief'], next=entry['next'],
                  matters=matters(contract, ticket_id, question),
                  phase_id=entry['phase_id'], phase_title=entry['phase_title'],
                  complete=entry['complete'],
                  solved_by=_text(question.get('solved_by')),
                  answered_at=_text(question.get('answered_at')),
                  finding={field: (finding or {}).get(field, [] if field == 'evidence' else '')
                           for field in FINDING_FIELDS})
    record['hints'] = [{'level': number, 'lead': levels[min(number, len(levels)) - 1] if levels else '',
                        'text': _text(hint)}
                       for number, hint in enumerate(question.get('hints') or [], 1)]
    record['accepted'] = [_text(contract.get('accepted', {}).get('lead'))] if record['solved_by'] else []
    return record


def exercise_complete(contract, snapshot=None) -> dict:
    """Closing text, released only once every ticket is closed.

    The count matters as much as the status: a filtered or partial snapshot that
    happens to contain only closed tickets must not read as a finished exercise,
    so the ending cannot be opened early from a second tab.
    """
    rows = (snapshot or {}).get('tickets', [])
    total = len(contract.get('tickets', {}))
    done = total > 0 and len(rows) == total and all(row.get('status') == 'complete' for row in rows)
    closing = contract.get('exercise_complete', {})
    return {'done': done, **{field: _text(closing.get(field)) if done else ''
                             for field in ('brief', 'handoff', 'residual', 'scoring_note')}}


def context(contract, snapshot=None, questions=None, lane='ctfd') -> dict:
    """Assemble the whole participant narrative for one page render.

    ``lane`` selects which data is decorated: the CTFd lane carries the question
    cards, the IRIS lane carries the ticket queue. Both get everything else,
    because a participant who only ever opens the queue still has to learn what
    the exercise is.
    """
    if lane not in ('ctfd', 'iris'):
        raise NarrativeError('lane: unknown render lane %r' % (lane,))
    tickets = ticket_narrative(contract, snapshot)
    completion = contract.get('ticket_complete', {})
    accepted = contract.get('accepted', {})
    return {
        'briefing': briefing(contract),
        'roles': roles(contract),
        'tool_map': tool_map(contract),
        'phases': phases(contract),
        'narrative_tickets': tickets,
        'questions': [question_narrative(contract, question, tickets)
                      for question in questions or []] if lane == 'ctfd' else [],
        'hints_policy': _text(contract.get('hints', {}).get('policy')),
        'accepted': [_text(accepted.get(name)) for name in ACCEPTED_GUIDANCE],
        'ticket_complete': {field: _text(completion.get(field))
                            for field in ('generic', 'handoff')},
        'exercise_complete': exercise_complete(contract, snapshot),
        'boundaries': {field: _text(contract.get('boundaries', {}).get(field))
                       for field in REQUIRED_BOUNDARY_FIELDS},
    }


def validate(rendered, revision=None) -> dict:
    """Refuse a deployment whose rendered participant narrative is incomplete.

    A clean deployment is proved, not assumed: the organizer runs this through
    ``python -m ridge.cli preflight`` and a renamed or dropped section fails
    loudly with the section named, rather than reaching ten team desktops.
    """
    if not isinstance(rendered, dict):
        raise NarrativeError('narrative: no render context was assembled')
    missing = [key for key in CONTEXT_KEYS if key not in rendered]
    if missing:
        raise NarrativeError('narrative: the render context is missing ' + ', '.join(missing))
    for field in ('codename', 'fiction_notice', 'classification_line', 'premise', 'discovery',
                  'stakes'):
        if not rendered['briefing'].get(field, '').strip():
            raise NarrativeError('narrative: the event briefing is missing %s' % field)
    for field in ('hints_policy',):
        if not str(rendered[field]).strip():
            raise NarrativeError('narrative: the hint policy is missing')
    for section, field in (('roles', 'roles'), ('tool_map', 'tool_map'), ('phases', 'phases')):
        if not rendered[section]:
            raise NarrativeError('narrative: the %s section is empty' % field)
    if not all(_text(line).strip() for line in rendered['accepted']):
        raise NarrativeError('narrative: the accepted-answer narrative is incomplete')
    for field in ('generic', 'handoff'):
        if not rendered['ticket_complete'].get(field, '').strip():
            raise NarrativeError('narrative: ticket completion is missing %s' % field)
    closing = ['brief', 'handoff', 'residual', 'scoring_note']
    if not rendered['exercise_complete'].get('done'):
        # The ending must not be readable from a second tab before the last ticket.
        leaked = [field for field in closing
                  if str(rendered['exercise_complete'].get(field, '')).strip()]
        if leaked:
            raise NarrativeError('narrative: exercise completion is readable before the '
                                 'investigation closes: ' + ', '.join(leaked))
    elif not all(str(rendered['exercise_complete'].get(field, '')).strip() for field in closing):
        raise NarrativeError('narrative: exercise completion is missing ' + ', '.join(closing))
    for field in REQUIRED_BOUNDARY_FIELDS:
        if not str(rendered['boundaries'].get(field, '')).strip():
            raise NarrativeError('narrative: a participant boundary is missing: %s' % field)
    # A phase claims a ticket; the ticket must then have narrative. Checked here
    # as well as in the contract validator so a host that ships no answer key
    # still proves the pairing.
    orphaned = sorted({ticket_id for phase in rendered['phases'] for ticket_id in phase['tickets']}
                      - set(rendered['narrative_tickets']))
    if orphaned:
        raise NarrativeError('narrative: no narrative for ' + ', '.join(orphaned))
    for ticket_id, entry in sorted(rendered['narrative_tickets'].items()):
        for field in [name if name != 'transition' else 'next'
                      for name in REQUIRED_TICKET_FIELDS] + ['phase_transition']:
            if not _text(entry.get(field)).strip():
                raise NarrativeError('narrative: %s is missing %s' % (ticket_id, field))
        if not entry.get('phase_id'):
            raise NarrativeError('narrative: %s belongs to no phase' % ticket_id)
    for card in rendered['questions']:
        if not card.get('matters', '').strip():
            raise NarrativeError('narrative: %s has no explanation of why it matters'
                                 % card.get('id'))
        if card.get('solved_by') and not all(line.strip() for line in card['accepted']):
            raise NarrativeError('narrative: %s is solved without accepted-answer narrative'
                                 % card.get('id'))
    return {'contract': CONTRACT_ID, 'revision': _text(revision),
            'ready': True, 'tickets': len(rendered['narrative_tickets']),
            'phases': len(rendered['phases']), 'roles': len(rendered['roles']),
            'tools': len(rendered['tool_map'])}


def probe_question(contract, ticket_id=None):
    """A shape-only question, for hosts that ship no authored content.

    The integration container runs preflight and deliberately carries neither
    ``expanded/`` nor the answer key, so the accepted-answer and ticket-closure
    branches are exercised with an empty body rather than real authored content.
    It carries no prose of its own; everything rendered from it comes from the
    contract, which is the property being checked.
    """
    ticket_id = ticket_id or sorted(contract.get('tickets', {}))[0]
    return {'id': ticket_id + '-Q1', 'ticket': ticket_id, 'prompt': '', 'purpose': '',
            'tool': '', 'evidence': '', 'steps': [], 'format': '', 'recovery': '',
            'hints': [], 'solved_by': 'preflight', 'answered_at': 'preflight',
            'finding': {'text': '', 'evidence': [], 'limitation': ''}}


def authored_probe(ticket_id):
    """The first authored question of a ticket, marked solved. Requires expanded/."""
    from expanded.author import build as author
    ticket = next(t for t in author() if t['id'] == ticket_id)
    return dict(ticket['questions'][0], ticket=ticket_id, solved_by='preflight',
                answered_at='preflight',
                finding={'text': 'preflight', 'evidence': ['preflight'],
                         'limitation': 'preflight'})


def check_deployment(path=None, snapshot=None, questions=None) -> dict:
    """Load, render and prove the participant narrative, on every host that runs it.

    The preflight entry point. Raises :class:`ridge.scenario_contract.ContractError`
    for a missing or malformed contract and :class:`NarrativeError` for one that
    renders an incomplete participant page, so neither can be read as a pass.

    The accepted-answer and closing text only render once a question is solved and
    a ticket is closed, so both are rendered here too: a facilitator finds a
    missing ending at preflight rather than at the end of the day.

    The answer-leak guard needs the authored answer key. Where ``expanded/`` is
    absent the container cannot run it, so the receipt says ``fixture-only``
    instead of pretending; ``ridge.bundle`` separately hash-verifies that the
    image carries the fixture this host would have validated.
    """
    from ridge.scenario_contract import load, validate as validate_contract
    contract = load(path)
    ticket_ids = sorted(contract.get('tickets', {}))
    if not ticket_ids:
        raise NarrativeError('narrative: the contract declares no tickets')
    try:
        from expanded.author import build as author
        validate_contract(contract, author())
        solved, guard = authored_probe(ticket_ids[0]), 'authored'
    except ImportError:
        solved, guard = probe_question(contract), 'fixture-only'
    revision = contract.get('revision')
    closed = {'tickets': [{'id': ticket_id, 'status': 'complete'} for ticket_id in ticket_ids]}
    for lane, frame, cards in (('ctfd', snapshot, questions), ('iris', snapshot, None),
                               ('ctfd', closed, [solved]), ('iris', closed, None)):
        validate(context(contract, frame, cards, lane), revision)
    return {'contract': CONTRACT_ID, 'revision': _text(revision), 'ready': True,
            'leak_guard': guard, 'tickets': len(contract.get('tickets', {})),
            'phases': len(contract.get('phases', [])), 'roles': len(contract.get('roles', [])),
            'tools': len(contract.get('tool_map', []))}


if __name__ == '__main__':
    import json
    print(json.dumps(check_deployment(), indent=2))
