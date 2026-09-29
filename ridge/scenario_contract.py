"""The approved Operation Silent Ridge narrative contract (issues 56, 58, 60, 59, 66).

Three participant-facing surfaces describe this scenario: the CTFd question page,
the IRIS case and the event-day deck. Before this module they each carried their
own prose, which is how they drifted apart. They now render from one versioned
fixture, ``assets/scenario-narrative-v1.json``, and this module is the only
supported way to read it.

The contract holds participant-facing text only. Answer keys stay in
``expanded/author.py`` and facilitator material stays under ``facilitator/``;
neither is imported here.

Two guards make the contract safe to extend:

``check_no_answers``
    Refuses any narrative string that contains a distinctive scored answer. This is
    what stops a rewrite from accidentally pre-answering a ticket. Answers that
    are already participant-visible in published material are exempted through the
    fixture's ``public_terms`` list, and ``check_public_terms`` verifies that each
    exemption really is already public, so the list cannot be used to leak a new one.

``validate``
    Requires a narrative entry for every authored ticket, rejects entries for
    tickets that do not exist, and requires every phase to reference real tickets.

The answer-leak guard compares exact answer strings. It deliberately does not
compare the HH:MM truncation of a time answer, because the event-day deck already
publishes shift events such as the 09:20 credential change; that is existing,
approved content rather than a leak.
"""
import json
from pathlib import Path

SCHEMA = 1
CONTRACT_ID = 'silent-ridge-narrative'
FIXTURE = Path(__file__).resolve().parents[1] / ('assets/scenario-narrative-v%d.json' % SCHEMA)

REQUIRED_TICKET_FIELDS = ('headline', 'brief', 'stakes', 'why_now', 'transition')
REQUIRED_PHASE_FIELDS = ('id', 'title', 'timeframe', 'purpose', 'urgency', 'tickets',
                         'action', 'transition')
REQUIRED_EXERCISE_FIELDS = ('codename', 'fiction_notice', 'classification_line', 'premise',
                            'discovery', 'stakes', 'exposure', 'escalation', 'outcome')
REQUIRED_BOUNDARY_FIELDS = ('read_only', 'no_credentials', 'no_operational_detail',
                            'fiction_repeat', 'attribution')

# Answer values that are too short or too generic to guard against.
_UNGUARDABLE = frozenset({'no', 'yes', 'none', 'other', '0', '1', '3'})


class ContractError(ValueError):
    """Raised when the narrative contract is missing, malformed or unsafe."""


def parse(document):
    """Schema-check an already-decoded contract document."""
    if document.get('schema') != SCHEMA:
        raise ContractError('Unknown narrative contract schema: ' + repr(document.get('schema')))
    if document.get('contract') != CONTRACT_ID:
        raise ContractError('Unknown narrative contract id: ' + repr(document.get('contract')))
    return document


def load(path=None):
    """Read and schema-check the contract fixture."""
    source = Path(path) if path else FIXTURE
    if not source.is_file():
        raise ContractError('narrative contract not found: ' + str(source))
    return parse(json.loads(source.read_text(encoding='utf-8')))


def distinctive_answers(tickets):
    """Scored answers long and specific enough to detect an accidental leak."""
    found = {}
    for ticket in tickets:
        for question in ticket['questions']:
            answer = str(question.get('answer', '')).strip()
            if len(answer) < 4 or answer.isdigit() or answer.lower() in _UNGUARDABLE:
                continue
            found.setdefault(answer.lower(), []).append(question['id'])
    return found


def public_terms(contract):
    return {str(term).strip().lower() for term in contract.get('public_terms', []) if str(term).strip()}


def narrative_strings(contract, ticket_id=None):
    """Every participant-facing string the contract renders, optionally for one ticket.

    Yielded as (field, text) so a validation failure can name the field.
    """
    for field in REQUIRED_EXERCISE_FIELDS:
        yield 'exercise.' + field, str(contract['exercise'].get(field, ''))
    adversary = contract['exercise'].get('adversary', {})
    for field in ('rule', 'rationale'):
        yield 'exercise.adversary.' + field, str(adversary.get(field, ''))
    for role in contract.get('roles', []):
        for field in ('name', 'duty', 'authority', 'not'):
            yield 'roles.' + str(role.get('id')), str(role.get(field, ''))
    for entry in contract.get('tool_map', []):
        yield 'tool_map.' + str(entry.get('surface')), '%s %s' % (entry.get('lane', ''),
                                                                   entry.get('text', ''))
    for phase in contract.get('phases', []):
        for field in REQUIRED_PHASE_FIELDS:
            if field != 'tickets':
                yield 'phases.' + str(phase.get('id')) + '.' + field, str(phase.get(field, ''))
    for tid, entry in sorted(contract.get('tickets', {}).items()):
        if ticket_id and tid != ticket_id:
            continue
        for field in REQUIRED_TICKET_FIELDS:
            yield 'tickets.' + tid + '.' + field, str(entry.get(field, ''))
    for field, value in sorted(contract.get('hints', {}).items()):
        yield 'hints.' + field, str(value)
    for field, value in sorted(contract.get('accepted', {}).items()):
        yield 'accepted.' + field, str(value)
    for field, value in sorted(contract.get('ticket_complete', {}).items()):
        yield 'ticket_complete.' + field, str(value)
    for field, value in sorted(contract.get('exercise_complete', {}).items()):
        yield 'exercise_complete.' + field, str(value)
    for field, value in sorted(contract.get('boundaries', {}).items()):
        yield 'boundaries.' + field, str(value)
    yield 'aar.intro', str(contract.get('aar', {}).get('intro', ''))
    for field in REQUIRED_BOUNDARY_FIELDS:
        yield 'boundaries.' + field, str(contract.get('boundaries', {}).get(field, ''))


def check_no_answers(contract, tickets) -> None:
    """Refuse narrative text that pre-answers a scored question.

    The rule is deliberately absolute: no distinctive answer may appear anywhere in
    the participant-facing contract, including in the entry for the ticket it
    scores. Narrative that needs to name an already-earned fact belongs on a
    post-completion surface, such as the T01 network map, not here.
    """
    exempt = public_terms(contract)
    answers = distinctive_answers(tickets)
    for field, text in narrative_strings(contract):
        if not text:
            continue
        haystack = text.lower()
        for answer, question_ids in sorted(answers.items()):
            if answer in exempt or answer not in haystack:
                continue
            raise ContractError('%s: narrative text contains the answer to %s'
                                % (field, ', '.join(question_ids)))


def check_public_terms(contract, surfaces) -> None:
    """Every exemption must already be participant-visible in published material.

    Guards the exemption list against being widened to hide a new answer.
    """
    haystack = '\n'.join(surfaces).lower()
    for term in sorted(public_terms(contract)):
        if term not in haystack:
            raise ContractError('public_terms: %r is not already participant-visible; '
                                'remove it rather than expanding it' % term)


def validate(contract, tickets) -> None:
    """Structural and safety validation of the whole contract."""
    for field in REQUIRED_EXERCISE_FIELDS:
        if not str(contract.get('exercise', {}).get(field, '')).strip():
            raise ContractError('exercise.%s: required narrative section is empty' % field)
    for field in REQUIRED_BOUNDARY_FIELDS:
        if not str(contract.get('boundaries', {}).get(field, '')).strip():
            raise ContractError('boundaries.%s: required boundary statement is empty' % field)
    if not contract.get('roles'):
        raise ContractError('roles: at least one participant role is required')
    for role in contract['roles']:
        for field in ('id', 'name', 'duty', 'authority', 'not'):
            if not str(role.get(field, '')).strip():
                raise ContractError('roles.%s: %s is empty' % (role.get('id'), field))
    if not str(contract.get('aar', {}).get('intro', '')).strip():
        raise ContractError('aar.intro: the after-action section is required')
    if not contract.get('aar', {}).get('prompts'):
        raise ContractError('aar.prompts: at least one after-action prompt is required')

    known = {ticket['id'] for ticket in tickets}
    for tid, entry in sorted(contract.get('tickets', {}).items()):
        if tid not in known:
            raise ContractError('tickets.%s: no such ticket in expanded/author.py' % tid)
        for field in REQUIRED_TICKET_FIELDS:
            if not str(entry.get(field, '')).strip():
                raise ContractError('tickets.%s.%s: required narrative field is empty' % (tid, field))
    missing = sorted(known - set(contract.get('tickets', {})))
    if missing:
        raise ContractError('tickets: no narrative for %s' % ', '.join(missing))

    phases = contract.get('phases', [])
    if not phases:
        raise ContractError('phases: at least one investigation phase is required')
    seen = set()
    for phase in phases:
        for field in REQUIRED_PHASE_FIELDS:
            if not phase.get(field) and phase.get(field) != []:
                raise ContractError('phases.%s.%s: required phase field is empty'
                                    % (phase.get('id'), field))
        for tid in phase['tickets']:
            if tid not in known:
                raise ContractError('phases.%s: references unknown ticket %s' % (phase['id'], tid))
            if tid in seen:
                raise ContractError('phases: ticket %s is claimed by more than one phase' % tid)
            seen.add(tid)
    if seen != known:
        raise ContractError('phases: tickets with no phase: %s' % ', '.join(sorted(known - seen)))

    check_no_answers(contract, tickets)


def phase_id(contract, ticket_id):
    for phase in contract.get('phases', []):
        if ticket_id in phase.get('tickets', []):
            return phase.get('id')
    return None


def phase_of(contract, ticket_id):
    """The narrative entry for the phase that contains a ticket, or None."""
    for phase in contract.get('phases', []):
        if ticket_id in phase.get('tickets', []):
            return phase
    return None


def ticket(contract, ticket_id):
    entry = contract.get('tickets', {}).get(ticket_id)
    if entry is None:
        raise ContractError('tickets.%s: no narrative entry' % ticket_id)
    return entry


def build(path=None, tickets=None):
    """Load, validate and return the contract ready for rendering."""
    document = load(path)
    if tickets is None:
        from expanded.author import build as author
        tickets = author()
    validate(document, tickets)
    return document


def inventory(contract, tickets) -> dict:
    """Deterministic summary for validation receipts and the organizer review."""
    return {
        'schema': SCHEMA,
        'contract': contract['contract'],
        'revision': contract['revision'],
        'status': contract.get('status', ''),
        'tickets': len(contract.get('tickets', {})),
        'phases': len(contract.get('phases', [])),
        'roles': len(contract.get('roles', [])),
        'surfaces': ['ctfd', 'iris', 'deck'],
        'questions_guarded': sum(len(v) for v in distinctive_answers(tickets).values()),
        'public_terms': sorted(public_terms(contract)),
    }


if __name__ == '__main__':
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from expanded.author import build as author
    authored = author()
    print(json.dumps(inventory(build(tickets=authored), authored), indent=2))
