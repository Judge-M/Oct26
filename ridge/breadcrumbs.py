"""Small believable traces left across the prepared evidence (issue 59).

The narrative contract (``assets/scenario-narrative-v1.json``) is the one approved
source for the participant narrative. It deliberately forbids naming an adversary
group, codename, operator or sponsor, and ``expanded/author.py`` scores ``no`` for
whether the evidence establishes adversary intent. So these breadcrumbs are
unattributed: they read as traces left by someone using the access, never as the
calling card of a named side. The fixture records that conflict rather than
resolving it by inventing canon.

Nothing here scores. Every breadcrumb is optional, and the fixture's ``scoring``
block says why no bonus award is possible: CTFd stock challenges are locked down in
this deployment and IRIS findings come from answers, not from events, so there is no
surface that could carry and reconcile a bonus point.

Delivery uses the mechanisms that already exist, not a new one:

``initial``
    Rendered into the published evidence tree as ``notes/<file>``. Available at run
    start, so it is only used for phases whose tickets are all available at run
    start (phase-1 and phase-2).
``release``
    Carried in the controller release vault and published on unlock through
    ``ridge/evidence_release.py``, exactly like the existing follow-up evidence.
    Used for phase-3 and phase-4 so a breadcrumb for a still-locked phase is not on
    the mount at all.

Every ticket with no prerequisites is enqueued for delivery at ``State.initialize``
(``ridge/state.py:122``), so anything hung on a root ticket's release would be
published at run start. :func:`validate` refuses any release breadcrumb whose gate
has no prerequisites, and ``tests/test_breadcrumbs.py`` covers that trap directly.

Validation is fail-closed and covers the ways a breadcrumb could actually cause
harm: a distinctive scored answer, a named adversary, a real target, a credential,
an operational instruction, or a pointer that leaves the exercise.
"""
import json
import re
from pathlib import Path

SCHEMA = 1
CONTRACT_ID = 'silent-ridge-breadcrumbs'
FIXTURE = Path(__file__).resolve().parents[1] / ('assets/breadcrumbs-v%d.json' % SCHEMA)
CASE_MANIFEST = Path(__file__).resolve().parents[1] / 'assets/autopsy-case-v2.json'

REQUIRED_FIELDS = ('id', 'phase', 'delivery', 'gate', 'path', 'surface', 'iris_ticket',
                   'text', 'points_to', 'cross_task', 'optional', 'bonus', 'reveals',
                   'must_not_reveal')
REQUIRED_FRAME_FIELDS = ('rule', 'rationale')
REQUIRED_SCORING_FIELDS = ('bonus', 'rule', 'rationale')
REQUIRED_DELIVERY_FIELDS = ('initial', 'release', 'note')
ID_PATTERN = re.compile(r'BC-[0-9]{2}')
TICKET_PATTERN = re.compile(r'T[0-9]{2}')

# Names an adversary may not acquire, whatever the reason for the breadcrumb. Canon
# has no adversary name; issue 59's framing is the thing under review. Matched on
# word boundaries so an ordinary word that merely contains one of these is not a
# false positive, and vice versa: "adapted" must not trip the APT check.
ADVERSARY_PATTERN = re.compile(
    r'(?i)\b(?:wraith|apt[0-9]*|lazarus|gamaredon|cobalt strike|cobalt|mimikatz|'
    r'meterpreter|empire|sliver|darkhydrus|finFisher)\b')
FORBIDDEN_OPERATIONAL = ('nmap ', 'mimikatz', 'powershell -enc', 'curl http', 'wget http',
                         'sudo ', 'ssh ', 'nc -l', 'chmod ', '/etc/passwd', '/etc/shadow',
                         'api key', 'api_key', 'private key', 'password=',
                         'passwd=', 'credential=', 'bearer ', 'export token')
FORBIDDEN_REAL_WORLD = ('latitude', 'longitude', '47.6', '35.6', '139.7', '.onion',
                        'pyongyang', 'gru')
# A note left by someone using the access is not exercise control writing to
# participants, so it does not carry the exercise codename.
FORBIDDEN_BRANDING = ('silent ridge', 'silent-ridge')
FORBIDDEN_CREDENTIAL_SHAPED = (re.compile(r'(?i)\b[A-Za-z0-9+/]{24,}={0,2}\b'),
                               re.compile(r'(?i)\bpassword\s*[:=]'), re.compile(r'(?i)\bsk-[A-Za-z0-9]{8,}'))
# RFC 5737 documentation space is a scored answer and RFC 1918 space is host
# infrastructure. A breadcrumb names neither.
ADDRESS_PATTERN = re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b')


class BreadcrumbError(ValueError):
    """Raised when the breadcrumb fixture is missing, malformed or unsafe."""


def parse(document):
    """Schema-check an already-decoded breadcrumb document."""
    if document.get('schema') != SCHEMA:
        raise BreadcrumbError('Unknown breadcrumb schema: ' + repr(document.get('schema')))
    if document.get('contract') != CONTRACT_ID:
        raise BreadcrumbError('Unknown breadcrumb contract id: ' + repr(document.get('contract')))
    if not isinstance(document.get('revision'), int):
        raise BreadcrumbError('Breadcrumb fixture requires an integer revision')
    return document


def load(path=None):
    """Read and schema-check the breadcrumb fixture."""
    source = Path(path) if path else FIXTURE
    if not source.is_file():
        raise BreadcrumbError('breadcrumb fixture not found: ' + str(source))
    return parse(json.loads(source.read_text(encoding='utf-8')))


def entries(document):
    return list(document.get('breadcrumbs', []))


def phase_ids(contract):
    return [str(phase.get('id')) for phase in contract.get('phases', [])]


def text_of(entry):
    return str(entry.get('text', ''))


def by_phase(document):
    """Breadcrumb ids grouped by phase, in fixture order."""
    grouped = {}
    for entry in entries(document):
        grouped.setdefault(str(entry.get('phase')), []).append(str(entry.get('id')))
    return grouped


def gate_ticket(entry):
    gate = entry.get('gate')
    return str(gate) if gate else None


def published_paths():
    """Paths a participant can actually read: the released tree plus follow-up files.

    ``assets/autopsy-case-v2.json`` records the evidence files in the prepared case,
    which is the authoritative inventory of the published tree. Follow-up evidence
    is not in the case, so the release contract is added from ``ridge.scenario``.
    The committed fixture's own paths are added last, because a pointer may
    legitimately lead to another breadcrumb.

    This is deliberately a property of the *committed* release, not of the document
    under validation: a breadcrumb that points at a path nothing publishes is a bug
    even if the document being checked declares that path itself.
    """
    from ridge.scenario import RELEASE_FILES
    published = set()
    if CASE_MANIFEST.is_file():
        manifest = json.loads(CASE_MANIFEST.read_text(encoding='utf-8'))
        for record in manifest.get('evidence_files', []):
            published.add(str(record.get('path')))
    for names in RELEASE_FILES.values():
        published.update(names)
    for entry in entries(load()):
        published.add(str(entry.get('path')))
    return published


def check_no_answers(document, tickets, contract) -> None:
    """Refuse breadcrumb text that pre-answers a scored question.

    Same standard as ``ridge.scenario_contract.check_no_answers``, and stricter in
    one respect: a breadcrumb is a note somebody left behind, so a public term is
    not an excuse. None of the exempt terms is needed to make a breadcrumb work.
    """
    from ridge.scenario_contract import distinctive_answers
    answers = distinctive_answers(tickets)
    for entry in entries(document):
        haystack = text_of(entry).lower()
        for answer, question_ids in sorted(answers.items()):
            if answer in haystack:
                raise BreadcrumbError('%s: text contains the answer to %s'
                                      % (entry.get('id'), ', '.join(question_ids)))


def check_no_documentation_address(document) -> None:
    """The external documentation address is a scored answer and stays unnamed."""
    for entry in entries(document):
        if '198.51.100.77' in text_of(entry):
            raise BreadcrumbError('%s: names the external documentation address' % entry.get('id'))


def check_no_addresses(document) -> None:
    """No breadcrumb carries an address literal of any kind."""
    for entry in entries(document):
        found = ADDRESS_PATTERN.search(text_of(entry))
        if found:
            raise BreadcrumbError('%s: text carries the address literal %s'
                                  % (entry.get('id'), found.group(0)))


def check_contained(document) -> None:
    """No adversary name, real-world target, credential or operational instruction."""
    for entry in entries(document):
        text = text_of(entry).lower()
        if ADVERSARY_PATTERN.search(text):
            raise BreadcrumbError('%s: names an adversary' % entry.get('id'))
        for needle in FORBIDDEN_OPERATIONAL:
            if needle in text:
                raise BreadcrumbError('%s: carries an operational instruction (%s)'
                                      % (entry.get('id'), needle))
        for needle in FORBIDDEN_REAL_WORLD:
            if needle in text:
                raise BreadcrumbError('%s: carries a real-world target (%s)'
                                      % (entry.get('id'), needle))
        for needle in FORBIDDEN_BRANDING:
            if needle in text:
                raise BreadcrumbError('%s: signs itself with the exercise codename' % entry.get('id'))
        for pattern in FORBIDDEN_CREDENTIAL_SHAPED:
            if pattern.search(text_of(entry)):
                raise BreadcrumbError('%s: looks like it carries a credential' % entry.get('id'))


def check_pointers(document, tickets) -> None:
    """Every pointer resolves to a released evidence path or a real ticket."""
    known = {ticket['id'] for ticket in tickets}
    published = published_paths()
    for entry in entries(document):
        points = entry.get('points_to') or []
        if not points:
            raise BreadcrumbError('%s: a breadcrumb must point at something' % entry.get('id'))
        for point in points:
            kind = str(point.get('kind'))
            ref = str(point.get('ref', ''))
            if kind == 'ticket':
                if ref not in known:
                    raise BreadcrumbError('%s: points at unknown ticket %s' % (entry.get('id'), ref))
            elif kind == 'evidence':
                if ref not in published:
                    raise BreadcrumbError('%s: points at evidence that is not published: %s'
                                          % (entry.get('id'), ref))
            else:
                raise BreadcrumbError('%s: unknown pointer kind %s' % (entry.get('id'), kind))


def check_inside_exercise(document) -> None:
    """No breadcrumb path, ticket or surface leaves the exercise."""
    known_surfaces = ('evidence', 'iris', 'ctfd')
    for entry in entries(document):
        path = str(entry.get('path', ''))
        if not path.startswith('notes/') or not path.endswith('.txt') or '..' in path:
            raise BreadcrumbError('%s: breadcrumb paths live under notes/ (%s)' % (entry.get('id'), path))
        if not TICKET_PATTERN.fullmatch(str(entry.get('iris_ticket', ''))):
            raise BreadcrumbError('%s: breadcrumb must name a real IRIS ticket' % entry.get('id'))
        if entry.get('surface') not in known_surfaces:
            raise BreadcrumbError('%s: unknown surface %s' % (entry.get('id'), entry.get('surface')))
        if ':' in path or path.startswith('/') or '\\' in path:
            raise BreadcrumbError('%s: breadcrumb path escapes the evidence mount' % entry.get('id'))


def check_flags(document) -> None:
    """Optional and bonus are declared everywhere, and bonus is only ever off."""
    for entry in entries(document):
        if not isinstance(entry.get('optional'), bool) or not isinstance(entry.get('bonus'), bool):
            raise BreadcrumbError('%s: optional and bonus must both be declared' % entry.get('id'))
        if not isinstance(entry.get('cross_task'), bool):
            raise BreadcrumbError('%s: cross_task must be declared' % entry.get('id'))
        if entry.get('bonus'):
            raise BreadcrumbError('%s: bonus scoring is not reconcilable with CTFd and IRIS; '
                                  'declare it optional instead' % entry.get('id'))
        if not entry.get('optional'):
            raise BreadcrumbError('%s: a breadcrumb may not be required' % entry.get('id'))
        if not isinstance(entry.get('must_not_reveal'), list) or not entry['must_not_reveal']:
            raise BreadcrumbError('%s: must_not_reveal must name what it may not reveal'
                                  % entry.get('id'))


def check_phases(document, contract) -> None:
    """At least one breadcrumb in every major investigation phase."""
    known = phase_ids(contract)
    grouped = by_phase(document)
    missing = [phase for phase in known if not grouped.get(phase)]
    if missing:
        raise BreadcrumbError('phases with no breadcrumb: ' + ', '.join(missing))
    for phase in grouped:
        if phase not in known:
            raise BreadcrumbError('%s: not a phase in the narrative contract' % phase)


def check_release_contract(document) -> None:
    """The release contract and the fixture must agree on every release breadcrumb.

    ``ridge.scenario.RELEASE_FILES`` is the release contract the vault build and
    the controller both trust. If a release breadcrumb's gate disagrees with the
    contract, the breadcrumb is written to the vault under a ticket that will never
    publish it, and ``validate_release`` fails closed on the next run. Compare both
    directions so neither can gain a stray entry.
    """
    from ridge.scenario import RELEASE_FILES
    contract = {ticket: [name for name in names if name.startswith('notes/')]
                for ticket, names in RELEASE_FILES.items()}
    contract = {ticket: names for ticket, names in contract.items() if names}
    declared = {}
    for entry in entries(document):
        if entry.get('delivery') != 'release':
            continue
        declared.setdefault(gate_ticket(entry), []).append(str(entry.get('path')))
    if contract != declared:
        raise BreadcrumbError('release contract %r does not match the declared release '
                              'breadcrumbs %r' % (contract, declared))


def check_delivery(document, tickets) -> None:
    """Delivery is consistent, and a release breadcrumb sits behind a real gate."""
    requires = {ticket['id']: list(ticket.get('requires', [])) for ticket in tickets}
    for entry in entries(document):
        delivery = entry.get('delivery')
        gate = gate_ticket(entry)
        if delivery == 'initial':
            if gate:
                raise BreadcrumbError('%s: initial delivery needs no gate' % entry.get('id'))
        elif delivery == 'release':
            if not gate:
                raise BreadcrumbError('%s: release delivery requires a gate ticket' % entry.get('id'))
            if gate not in requires:
                raise BreadcrumbError('%s: gate %s is not a ticket' % (entry.get('id'), gate))
            # A root ticket is enqueued at State.initialize, so its release would be
            # published at run start. A breadcrumb for a later phase must not ride one.
            if not requires[gate]:
                raise BreadcrumbError('%s: gate %s has no prerequisites, so its release is '
                                      'published at run start' % (entry.get('id'), gate))
        else:
            raise BreadcrumbError('%s: delivery must be initial or release' % entry.get('id'))


def check_structure(document) -> None:
    for field in REQUIRED_FRAME_FIELDS:
        if not str(document.get('framing', {}).get(field, '')).strip():
            raise BreadcrumbError('framing.%s: the attribution rule is required' % field)
    for field in REQUIRED_SCORING_FIELDS:
        if field not in document.get('scoring', {}):
            raise BreadcrumbError('scoring.%s: the scoring policy is required' % field)
    if document['scoring'].get('bonus'):
        raise BreadcrumbError('scoring.bonus: bonus scoring is not reconcilable with CTFd and IRIS')
    for field in REQUIRED_DELIVERY_FIELDS:
        if not str(document.get('delivery', {}).get(field, '')).strip():
            raise BreadcrumbError('delivery.%s: the delivery contract is required' % field)
    seen = set()
    for entry in entries(document):
        for field in REQUIRED_FIELDS:
            if field not in entry:
                raise BreadcrumbError('%s: required field %s is missing' % (entry.get('id'), field))
        if not ID_PATTERN.fullmatch(str(entry.get('id', ''))):
            raise BreadcrumbError('%s: breadcrumb ids are BC-<n>' % entry.get('id'))
        if entry['id'] in seen:
            raise BreadcrumbError('%s: duplicate breadcrumb id' % entry['id'])
        seen.add(entry['id'])
        if not text_of(entry).strip():
            raise BreadcrumbError('%s: text is empty' % entry['id'])
        if not str(entry.get('reveals', '')).strip():
            raise BreadcrumbError('%s: reveals must state what the breadcrumb does give' % entry['id'])
        if not isinstance(entry.get('must_not_reveal'), list) or not entry['must_not_reveal']:
            raise BreadcrumbError('%s: must_not_reveal must name what it may not reveal' % entry['id'])
    if not entries(document):
        raise BreadcrumbError('breadcrumbs: at least one breadcrumb is required')


def visible_to(document, completed):
    """Which breadcrumbs a team can see, given the tickets it has completed.

    ``initial`` breadcrumbs are on the mount from the start. A ``release``
    breadcrumb appears once its gate ticket is complete, which is the same moment
    the ticket's follow-up evidence is published. Anything still behind a gate is
    not visible, and neither is anything belonging to a phase whose gate is unopened.
    """
    completed = set(completed or ())
    available = []
    for entry in entries(document):
        gate = gate_ticket(entry)
        if entry.get('delivery') == 'initial' or (gate and gate in completed):
            available.append(entry)
    return available


def gated_behind(document, completed):
    """Breadcrumbs a team cannot see yet, for a visibility check or a facilitator note."""
    completed = set(completed or ())
    return [entry for entry in entries(document) if entry not in visible_to(document, completed)]


def inventory(document, contract) -> dict:
    """Deterministic summary for validation receipts and the organizer review."""
    return {
        'schema': SCHEMA,
        'contract': document['contract'],
        'revision': document['revision'],
        'status': document.get('status', ''),
        'breadcrumbs': len(entries(document)),
        'phases': sorted(by_phase(document)),
        'initial': sum(1 for e in entries(document) if e.get('delivery') == 'initial'),
        'release': sum(1 for e in entries(document) if e.get('delivery') == 'release'),
        'cross_task': sum(1 for e in entries(document) if e.get('cross_task')),
        'bonus': sum(1 for e in entries(document) if e.get('bonus')),
        'contract_phases': len(phase_ids(contract)),
    }


def validate(document, tickets, contract) -> None:
    """Structural and safety validation of the whole breadcrumb fixture."""
    parse(document)
    check_structure(document)
    check_phases(document, contract)
    check_delivery(document, tickets)
    check_release_contract(document)
    check_inside_exercise(document)
    check_pointers(document, tickets)
    check_flags(document)
    check_no_answers(document, tickets, contract)
    check_no_documentation_address(document)
    check_no_addresses(document)
    check_contained(document)


def build(path=None, tickets=None, contract=None):
    """Load, validate and return the fixture ready for rendering."""
    document = load(path)
    if tickets is None:
        from expanded.author import build as author
        tickets = author()
    if contract is None:
        from ridge import scenario_contract
        contract = scenario_contract.build(tickets=tickets)
    validate(document, tickets, contract)
    return document


if __name__ == '__main__':
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from expanded.author import build as author
    from ridge import scenario_contract
    authored = author()
    print(json.dumps(inventory(build(tickets=authored),
                               scenario_contract.build(tickets=authored)), indent=2))
