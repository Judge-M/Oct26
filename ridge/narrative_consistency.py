"""One command that proves the integrated event tells one story (issue 60).

``assets/scenario-narrative-v1.json`` is the approved source, and issues 56, 58,
59 and 66 made five participant-facing surfaces render from it: the CTFd question
page, the IRIS incident queue, the event-day deck, the T01 network map and the
optional evidence breadcrumbs. Five renderers are five chances to drift. This
module is the check that closes the loop, and it is the last item the programme
needed: the content is written, the plumbing exists, and nothing yet proves the
five still agree.

It runs offline and read-only. No network, no Docker, no browser, no database and
no clock, so the organizer can run it on a laptop the week of the event and CI can
run it on every push. ``ridge.preflight`` calls it; ``python -m
ridge.narrative_consistency`` runs it on its own. It never enters a
``ConsistencyError`` guard by being absent: a surface this host cannot read is
named in ``surfaces_not_proved`` in the receipt, which is how the integration
container - the host ``python -m ridge.cli preflight`` actually runs on, holding
the contract and no answer key - says what it did not check instead of implying
it checked everything.

The guards
----------

``check_canon``
    The fictional entity registry is not a hand-maintained list. Every declared
    name must still appear in the file that declares it, and every name-shaped
    token found in participant-facing text must be a declared entity, spelled the
    way it was declared and filed under the category it belongs to. The registry
    is pinned to the collection handout glossary (``scripts/generate.py:74-90``),
    to ``facilitator/ground-truth.md`` and to ``expanded/author.py``, so canon
    cannot drift away from the validator that polices it. A name used on one
    surface and spelled any other way on another is a failure, not a variation.

``check_lineage``
    Every surface declares the contract revision it renders. The deck and the two
    lanes are derived from a contract object, so their revision is the contract's
    by construction and is proved by regenerating and re-rendering them. The map
    and the breadcrumbs are committed fixtures and declare the revision they were
    written against, which is the only honest way to notice a narrative change
    that nobody revisited.

``check_drift``
    The drift detector the programme exists for, in two strengths.

    *Provenance.* A committed deck slide must equal, byte for byte, what
    ``ridge.deck_narrative`` generates from this contract, and every string a
    lane's render context carries must be a contract value or a space-join of
    contract values. Those are exact: any hand-edit to a contract-derived slide,
    and any sentence a renderer introduces of its own, fails.

    *Restatement.* A participant-facing sentence may not share a run of six
    consecutive content words with a contract section unless it is the contract's
    own text. Six is calibrated, not guessed: every shipped surface passes and a
    one-line rewrite of any of them does not. This catches near-verbatim
    restatement, which is the drift that actually happens when a surface acquires
    a second copy of a sentence. It is a similarity test and not a proof: a free
    paraphrase that shares no six-word run is not detected, and the provenance
    checks above are what cover a surface that invents rather than copies.

``check_sections``
    Every section the issue requires is present and non-empty, on the surfaces
    that render it, and each one is carried by at least one surface that is
    present. The per-surface plan is deliberate: the deck is a projection set and
    carries the whole exercise narrative, while a question page carries what a
    participant reads mid-investigation, which is why exposure, escalation and
    outcome are the deck's obligation rather than the page's.

``check_tools``
    Every tool the issue names - IRIS, CTFd, Wazuh, Guacamole, Wireshark, Autopsy
    and the prepared evidence - is placed by a passage a participant can read, and
    every tool in the contract's tool map is named on the deck too, so the two
    cannot describe different toolkits.

``check_leakage`` and ``check_attribution``
    No distinctive scored answer, credential, answer key, facilitator-only path or
    deployment detail reaches a participant, and no surface names an adversary
    group, codename, operator or sponsor. Both run over every surface, including
    the ones the other branches added.

    The network map is the one sanctioned post-completion view, so it is held to
    the evidence rule rather than the narrative rule. A value it names has to be
    one a team could already read in the evidence published at run start; a value
    that only a follow-up release carries is a leak. One exception is recorded
    rather than waved through: the map projects a corrected endpoint event's
    ``time_utc`` on a graph edge, and that value is also T19-Q3's answer while
    T19 is still locked. It is a published record field, not a sentence, so it
    lives in ``KNOWN_RECORD_VALUES`` with the reason, and a second value cannot
    be added to the map on the same reasoning without failing.

    A surface's record values and its prose are kept apart. Entities, credentials
    and attribution are checked in both; the answer guard and the restatement
    guard run on prose, because a value drawn out of a published CSV is evidence
    and a value asserted in a sentence is a spoiler.

``check_determinism`` and ``receipt``
    Every narrative source is tracked by git and hashed, and the deck is
    regenerated from the contract and compared with the committed slides. So a
    clean install reproduces the whole event from the repository alone, and the
    receipt - no timestamps, no absolute paths, sorted keys - is a pure function
    of those bytes. A reset or reseed that changed a byte changes the receipt.
"""
import argparse
import hashlib
import html
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field as dataclass_field
from pathlib import Path

from ridge import scenario_contract
from ridge.scenario_contract import CONTRACT_ID

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_FIXTURE = scenario_contract.FIXTURE
MAP_FIXTURE = ROOT / 'assets/t01-network-map-v1.json'
BREADCRUMB_FIXTURE = ROOT / 'assets/breadcrumbs-v1.json'
DECK_DIR = ROOT / 'docs/event-day-deck'
DECK_PAGES = DECK_DIR / 'pages'
DECK_FACILITATOR_PAGES = DECK_DIR / 'facilitator-pages'
HANDOUTS = ROOT / 'participants'
GUIDES = ROOT / 'expanded/guides.md'
TEMPLATE = ROOT / 'ridge/web.py'

# The three files that declare canon, and the file that declares the estate. The
# entity registry below is pinned to them, so a rename in any of them is a
# validation failure rather than a divergence nobody notices.
GLOSSARY = ROOT / 'scripts/generate.py'
GROUND_TRUTH = ROOT / 'facilitator/ground-truth.md'
ANSWER_KEY = ROOT / 'expanded/author.py'
CASE_MANIFEST = ROOT / 'assets/autopsy-case-v2.json'

# Prose of six consecutive content words is a restatement, not a coincidence.
NGRAM = 6

STOPWORDS = frozenset("""
a an and are as at be been but by can did do does for from had has have he her his how
if in into is it its me my no not of on one or our out she should so than that the their
them then there these they this to too two up us was we were what when where which while
who whom why will with would you your
""".split())


class ConsistencyError(ValueError):
    """Raised when the integrated event does not tell one story."""


# --------------------------------------------------------------------------
# the fictional canon
# --------------------------------------------------------------------------

# category -> canonical name -> the files that declare it. A declared name is
# canon only while it still appears where it says it does.
CANON = {
    'unit': {'LANTERN': (GLOSSARY, GROUND_TRUTH, HANDOUTS / 'handover.md')},
    'zone': {'AMBER': (GLOSSARY, GROUND_TRUTH),
             'BLUE': (ANSWER_KEY,)},
    'check-in': {'CEDAR': (GLOSSARY, GROUND_TRUTH)},
    'host': {'WS-17': (GLOSSARY, GROUND_TRUTH),
             'WS-22': (GLOSSARY, GROUND_TRUTH),
             'WS-31': (GROUND_TRUTH, GLOSSARY)},
    'service': {'DOCS-1': (GLOSSARY, ANSWER_KEY),
                'IDP-1': (GLOSSARY,)},
    'session': {'S-41': (GROUND_TRUTH, GLOSSARY)},
    'account': {'m.ellis': (GLOSSARY, GROUND_TRUTH),
                'r.chen': (GLOSSARY, GROUND_TRUTH),
                'svc-index': (GLOSSARY,),
                'Exercise IT': (ANSWER_KEY, GLOSSARY)},
    'document': {'plan-v3': (GLOSSARY,),
                 'plan-v4': (GLOSSARY,),
                 'roster-v2': (GLOSSARY,)},
    'program': {'brief-viewer.exe': (GROUND_TRUTH, ANSWER_KEY),
                'brief-viewer-training': (ANSWER_KEY,),
                'briefsync.exe': (ANSWER_KEY,),
                'browser.exe': (ANSWER_KEY, GLOSSARY)},
    'task': {'BriefSync': (ANSWER_KEY, GLOSSARY)},
    'path': {'C:/Temp/move-cache.txt': (ANSWER_KEY, GLOSSARY)},
    'resolver': {'relay.archive.example': (GLOSSARY, ANSWER_KEY),
                 'docs.exercise.test': (GLOSSARY,),
                 'briefs.helpdesk.example': (GLOSSARY, ANSWER_KEY)},
}

# Shapes a reader would read as a name in this fiction. Anything these match has
# to be declared above, which is what turns a new workstation into a validation
# failure instead of a variation nobody notices. Case-sensitive on purpose: the
# deck's ``$amber`` theme token and a lowercase host are not the sector AMBER.
ENTITY_PATTERNS = (
    ('host', re.compile(r'\bWS-\d{1,2}\b')),
    ('service', re.compile(r'\b(?:DOCS|IDP)-\d\b')),
    ('session', re.compile(r'\bS-\d{2}\b')),
    ('document', re.compile(r'\b(?:plan|roster)-v\d\b')),
    ('account', re.compile(r'\b(?:m|r)\.[a-z]{3,}\b')),
    ('account', re.compile(r'\bsvc-[a-z]{3,}\b')),
    ('account', re.compile(r'\bExercise IT\b')),
    ('program', re.compile(r'\b(?:brief-viewer(?:\.exe|-training)?|briefsync\.exe|browser\.exe)\b')),
    ('task', re.compile(r'\bBriefSync\b')),
    ('unit', re.compile(r'\bLANTERN\b')),
    ('zone', re.compile(r'\b(?:AMBER|BLUE)\b')),
    ('check-in', re.compile(r'\bCEDAR\b')),
    ('path', re.compile(r'\bC:/Temp/[A-Za-z0-9._-]+')),
    ('resolver', re.compile(r'\b[a-z0-9-]+(?:\.[a-z0-9-]+)*\.(?:example|test)\b')),
)

# Names that are also ordinary English once lowercased, so only their exact
# spelling counts as canon. "Exercise IT" is a publisher name; the sentence "in
# this exercise it is documentation space" is not a misspelt copy of it.
EXACT_CASE = frozenset({'Exercise IT'})

# The tools the issue names, and how a reader is shown one. A tool is placed when
# a participant can read a passage that names it and says what it is for; a bare
# mention on a slide is navigation, not an explanation.
REQUIRED_TOOLS = ('IRIS', 'CTFd', 'Wazuh', 'Guacamole', 'Wireshark', 'Autopsy')
REQUIRED_ARTEFACTS = {'the prepared evidence':
                     re.compile(r'/evidence\b|prepared case|published evidence|released evidence',
                                re.IGNORECASE)}
# The deck's tool table calls one of the contract's entries by its short name.
# Declared once, here, so a second spelling is a failure rather than a variant.
TOOL_ALIASES = {'File manager': 'Linux file manager'}

# Shapes that would put a credential, an answer key, facilitator material or a
# deployment detail in front of a participant. The exercise estate in
# ``10.26.0.0/16`` is the fictional one the collection handout publishes, so only
# other private space counts as infrastructure here.
LEAK_PATTERNS = (
    (re.compile(r'-----BEGIN [A-Z ]*PRIVATE KEY'), 'a private key block'),
    (re.compile(r'\b(?:password|passwd|secret|token|api[_-]?key|passphrase)\b\s*[:=]\s*\S',
                re.IGNORECASE), 'a credential assignment'),
    (re.compile(r'\$[2aby][aby]?\$\d{2}\$[A-Za-z0-9./]{10,}'), 'a password hash'),
    (re.compile(r'file:/etc/silent-ridge/'), 'a private secret reference'),
    (re.compile(r'\b[A-Za-z0-9-]+\.example\.invalid\b'), 'a deployment hostname'),
    (re.compile(r'\b(?:10\.(?!26\.)\d{1,3}|192\.168|172\.(?:1[6-9]|2\d|3[01]))'
                r'\.\d{1,3}\.\d{1,3}\b'), 'a private infrastructure address'),
    (re.compile(r'\b(?:RIDGE|CTFD|IRIS|WAZUH|GUACAMOLE)_[A-Z0-9_]{3,}\b'),
     'a deployment environment variable'),
    (re.compile(r'\bDockerfile\b|\bdocker compose\b|\bcompose\.[a-z]+\b|\bnginx\.conf\b'),
     'a deployment build artefact'),
    (re.compile(r'facilitator/|facilitator\\|ground-truth|solutions\.md|expanded/author|'
                r'EXPECTED_QUESTIONS'), 'a facilitator-only path'),
)

# No adversary name is in canon and T20-Q4 scores "no" for intent, so no surface
# may attribute the activity to a person, a group, a codename or a sponsor. This
# is the union of the deck's and the breadcrumbs' own patterns, so the cross-
# surface guard is at least as strict as either of them.
ATTRIBUTION_PATTERNS = (
    (re.compile(r'wraith', re.IGNORECASE), 'names an adversary group that is not in canon'),
    (re.compile(r'shadow network', re.IGNORECASE),
     'names an adversary network that is not in canon'),
    (re.compile(r'\b(?:APT\d*|lazarus|gamaredon|cobalt ?strike|mimikatz|meterpreter|'
                r'darkhydrus|finfisher|threat actor group|state[- ]sponsored|sliver)\b',
                re.IGNORECASE), 'attributes the activity to a group or a named tool'),
    (re.compile(r'\b(?:hacktivists?|cybercriminals?|nation[- ]state)\b', re.IGNORECASE),
     'names an adversary'),
    (re.compile(r'\b(?:sponsor(?:ed|ship)?\s+by|attributed to|carried out by|known as|'
                r'codename[ds]?\s*[:=])\b', re.IGNORECASE), 'attributes a sponsor'),
)

# The one value on the T01 network map that is a record value rather than prose
# and is not yet readable from published evidence. The map projects a corrected
# endpoint event's time on a graph edge; that value is also T19-Q3's answer, and
# T19's evidence arrives on T19's unlock, long after the map appears. Recorded
# here, with the reason, so a second value cannot be added on the same reasoning
# without failing.
KNOWN_RECORD_VALUES = {
    '09:06:00': 'assets/t01-network-map-v1.json: edges[e-endpoint-connect].time_utc, '
                'projected from endpoint/events.csv; T19-Q3 is still locked when the map unlocks',
}

# section -> (the render-context key a lane must fill, what the deck must project)
# A deck requirement is either an exact list of contractRefs or PREFIX, meaning the
# deck has to project at least one ref under that prefix. None means the section is
# not that surface's obligation.
#
# The lane column is deliberately about the render *context*, not the template.
# Two narrative implementations now coexist in ``ridge/web.py`` pending an
# organizer decision - Side A's approved ``story`` markup and this contract's
# assembler - and Side A is the primary narrative, so the overlapping sections
# (``briefing``, ``roles``, ``tool_map``, ``narrative_tickets``, the per-question
# decorations) are carried and proved here while the page shows Side A's wording
# for them. The receipt therefore reports what each lane can render and the
# consistency guards can check, not which of the two implementations a
# participant reads. The duplicates were removed from the template, not the
# context, so nothing here lost coverage.
PREFIX = 'prefix'

SECTION_PLAN = (
    ('exercise.premise', 'briefing.premise', ('exercise.premise',)),
    ('exercise.discovery', 'briefing.discovery', ('exercise.discovery',)),
    ('exercise.stakes', 'briefing.stakes', ('exercise.stakes',)),
    ('exercise.fiction_notice', 'briefing.fiction_notice', None),
    ('exercise.classification_line', 'briefing.classification_line',
     ('exercise.classification_line',)),
    ('exercise.exposure', None, ('exercise.exposure',)),
    ('exercise.escalation', None, ('exercise.escalation',)),
    ('exercise.outcome', None, ('exercise.outcome',)),
    ('roles', 'roles', PREFIX),
    ('tool_map', 'tool_map', None),
    ('phases', 'phases', PREFIX),
    ('tickets', 'narrative_tickets', None),
    ('hints.policy', 'hints_policy', ('hints.policy',)),
    ('accepted', 'accepted', ('accepted.lead', 'accepted.credit', 'accepted.shared')),
    ('ticket_complete', 'ticket_complete',
     ('ticket_complete.generic', 'ticket_complete.handoff')),
    ('exercise_complete', 'exercise_complete', ('exercise_complete.handoff',)),
    ('boundaries', 'boundaries', PREFIX),
    ('aar', None, ('aar.intro', 'aar.close')),
)

# The two committed post-completion fixtures, and the only field of the
# breadcrumbs a reader ever sees. Everything else in either fixture is a maintainer
# note about how it is written, not text a participant reads, and several of those
# notes name files under ``facilitator/`` and ``expanded/`` on purpose.
BREADCRUMB_PROSE = ('text',)


@dataclass(frozen=True)
class Span:
    """One piece of participant-facing text, and where a reader would see it.

    ``unit`` is the whole value the sentence was cut from, so a provenance test
    can ask whether the value is the contract's own text even when the sentence
    is only part of it. ``kind`` separates prose from a record value: entities,
    credentials and attribution are checked in both, while the answer guard and
    the restatement guard read only the prose.
    """

    surface: str
    file: str
    line: int
    text: str
    unit: str
    kind: str = 'prose'


@dataclass
class Survey:
    """Everything one run of the check read, so no guard re-reads a fixture.

    ``unproved`` is the list of things this host could not check. It is not the
    list of things that are wrong: a surface that is absent is reported there, and
    only a surface that is present and wrong is a failure. That distinction is
    what lets the integration container - the host ``python -m ridge.cli preflight``
    actually runs on, holding the contract and no deck, no map and no breadcrumbs -
    prove what it can and say plainly what it could not.
    """

    contract: dict
    tickets: list
    guard: str
    spans: dict = dataclass_field(default_factory=dict)
    absent: dict = dataclass_field(default_factory=dict)
    contexts: dict = dataclass_field(default_factory=dict)
    unproved: list = dataclass_field(default_factory=list)
    expected: set = dataclass_field(default_factory=set)
    deck: object = None
    document: dict = dataclass_field(default_factory=dict)


# --------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------


def relative(path) -> str:
    path = Path(path)
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:  # pragma: no cover - only if the tree moves wholesale
        return path.name


def read(path) -> str:
    path = Path(path)
    return path.read_text(encoding='utf-8', errors='replace') if path.is_file() else ''


def locate(path, needle) -> int:
    """The 1-based line a reader would be shown for this string, or 0."""
    path = Path(path)
    if not path.is_file() or not needle:
        return 0
    first = str(needle).strip().splitlines()[0].strip()
    if len(first) > 24:
        first = first[:24]
    for number, line in enumerate(path.read_text(encoding='utf-8',
                                                 errors='replace').splitlines(), start=1):
        if first and first in line:
            return number
    return 0


def words(text) -> list:
    return [word for word in re.findall(r"[a-z0-9']+", str(text).lower())
            if word not in STOPWORDS]


def ngrams(text, size=NGRAM) -> set:
    tokens = words(text)
    return {tuple(tokens[index:index + size]) for index in range(len(tokens) - size + 1)}


def sentences(text) -> list:
    """Prose units. A bullet, a table cell and a paragraph are each one unit."""
    body = re.sub(r'<style>.*?</style>|<script>.*?</script>', ' ', str(text), flags=re.S)
    body = html.unescape(re.sub(r'<[^>]*>', ' ', body))
    body = re.sub(r'[ \t]+', ' ', body)
    return [chunk.strip()
            for chunk in re.split(r'\n+|(?<=[.?;:])\s+(?=[A-Z0-9])', body) if chunk.strip()]


def _spans(surface, path, unit, kind='prose') -> list:
    """One span per sentence of a value, each pointing at the value's own line."""
    if not str(unit or '').strip():
        return []
    line = locate(path, unit)
    return [Span(surface, relative(path), line, sentence, str(unit), kind)
            for sentence in sentences(unit)]


def _values(node, into) -> set:
    """Every string a JSON document holds, at any depth, including list items."""
    if isinstance(node, str):
        if node.strip():
            into.add(node.strip())
    elif isinstance(node, dict):
        for item in node.values():
            _values(item, into)
    elif isinstance(node, (list, tuple)):
        for item in node:
            _values(item, into)
    return into


def contract_values(contract) -> set:
    """Every string the contract renders, and every string it holds.

    The renderers compose values by joining contract strings, so a joiner such as
    ``"%s: %s"`` over the tool map is itself contract text and is included.
    """
    values = {text.strip() for _, text in scenario_contract.narrative_strings(contract)
              if str(text).strip()}
    return _values(contract, values)


# --------------------------------------------------------------------------
# reading the surfaces
# --------------------------------------------------------------------------


def _json_prose(document, path, surface, pairs) -> list:
    spans = []
    for record, field in pairs:
        spans += _spans(surface, path, record.get(field))
    return spans


def _json_records(document, key, fields) -> list:
    """(record, field) pairs for a list-valued or a dict-valued fixture key."""
    value = document.get(key, [])
    records = [value] if isinstance(value, dict) else list(value)
    return [(record, field) for record in records for field in fields]


def map_spans(document) -> list:
    """What a participant reads on the T01 network map, and where it is written."""
    pairs = [(document, field) for field in ('authority', 'caption', 'unlock_note',
                                             'key_fields_note')]
    pairs += _json_records(document, 'link', ('headline', 'brief', 'action'))
    pairs += _json_records(document, 'disclaimer',
                           ('receipt', 'identity', 'intent', 'inference', 'scope'))
    pairs += _json_records(document, 'external_address', ('block', 'registry', 'reason', 'rule'))
    pairs += [(entry, 'meaning') for entry in document['legend']]
    pairs += _json_records(document, 'nodes', ('detail',))
    pairs += _json_records(document, 'edges', ('basis', 'caveat'))
    spans = _json_prose(document, MAP_FIXTURE, 'map', pairs)
    # The map's node and edge values are drawn from published records rather than
    # asserted, so they are scanned as data: an entity still has to be canon, but a
    # value that happens to be a scored answer is evidence, not a spoiler.
    for node in document['nodes']:
        spans += _spans('map', MAP_FIXTURE, node['label'], 'data')
        spans += _spans('map', MAP_FIXTURE, node.get('sublabel', ''), 'data')
    for edge in document['edges']:
        for field in ('time_utc', 'method', 'path', 'status', 'body_bytes', 'request'):
            spans += _spans('map', MAP_FIXTURE, edge.get(field, ''), 'data')
    source = Path(__file__).resolve().parent / 'network_map.py'
    body = source.read_text(encoding='utf-8')
    template = body[body.index('_PAGE = '):]
    spans += _spans('map', source, re.sub(r'\{[a-z_]+\}', ' ', template))
    return spans


def breadcrumb_spans(document) -> list:
    """What a participant reads in the published notes, which is only the note.

    ``framing``, ``scoring``, ``delivery`` and ``authority`` are maintainer notes
    about how the fixture is written, not text a participant ever reads, and
    several of them name files under ``facilitator/`` and ``expanded/`` on purpose.
    """
    return _json_prose(document, BREADCRUMB_FIXTURE, 'breadcrumbs',
                       _json_records(document, 'breadcrumbs', BREADCRUMB_PROSE))


def contract_spans(contract) -> list:
    return [Span('contract', relative(CONTRACT_FIXTURE), locate(CONTRACT_FIXTURE, text), text, text)
            for _, text in scenario_contract.narrative_strings(contract) if str(text).strip()]


def handout_spans() -> list:
    """The published handout tree: participants/, which generation copies verbatim."""
    spans = []
    for path in sorted(HANDOUTS.glob('*.md')):
        for number, line in enumerate(read(path).splitlines(), start=1):
            for sentence in sentences(line):
                spans.append(Span('handout', relative(path), number, sentence, line))
    if GUIDES.is_file():
        for number, line in enumerate(read(GUIDES).splitlines(), start=1):
            for sentence in sentences(line):
                spans.append(Span('handout', relative(GUIDES), number, sentence, line))
    return spans


def template_spans() -> list:
    """The literal prose ``ridge/web.py`` keeps outside the contract.

    The template may hold labels, form fields and one declared standfirst.
    Anything else it starts stating is a second source of scenario text, which is
    the failure this whole programme was created to stop.
    """
    from ridge.web import PAGE
    body = read(TEMPLATE)
    anchor = locate(TEMPLATE, "PAGE = '''")
    page = re.sub(r'<script>.*?</script>', ' ', PAGE, flags=re.S)
    page = re.sub(r'\{%.*?%\}', ' ', page, flags=re.S)
    page = re.sub(r'\{\{.*?\}\}', ' ', page, flags=re.S)
    spans = []
    for sentence in sentences(page):
        spans.append(Span('web-template', relative(TEMPLATE), locate(body, sentence) or anchor,
                          sentence, sentence))
    return spans


def deck_spans(deck) -> list:
    """Every slide a facilitator could project, with the line the text sits on."""
    from ridge import deck_narrative
    spans = []
    for page in deck.pages:
        for element in page.elements:
            text = deck_narrative.element_text(element)
            if not text.strip():
                continue
            line = (locate(page.path, text)
                    or locate(page.path, str(element.get('elementId'))))
            for sentence in sentences(text):
                spans.append(Span('deck', relative(page.path), line, sentence, text))
    return spans


def lane_contexts(contract) -> dict:
    """The two lanes, each proved complete by the assembler before it is read."""
    from ridge.web_narrative import context, validate
    snapshot = {'mode': 'running', 'team': 'team-01', 'pending': 0, 'elapsed_seconds': 0,
                'announcements': [],
                'tickets': [{'id': tid, 'status': 'complete'}
                            for tid in sorted(contract['tickets'])]}
    rendered = {}
    for lane in ('ctfd', 'iris'):
        context_value = context(contract, snapshot, None, lane)
        validate(context_value, contract['revision'])
        rendered[lane] = context_value
    return rendered


def context_spans(contexts) -> dict:
    """The contract-derived part of each lane, which is all of it but the cards."""
    from ridge.web_narrative import CONTEXT_KEYS
    spans = {'ctfd': [], 'iris': []}
    for lane, rendered in contexts.items():
        for value in _flatten([rendered[key] for key in CONTEXT_KEYS if key != 'questions']):
            spans[lane] += _spans(lane, CONTRACT_FIXTURE, value)
        for card in rendered['questions']:
            for field in ('headline', 'brief', 'next', 'matters', 'phase_title'):
                spans[lane] += _spans(lane, CONTRACT_FIXTURE, card.get(field))
            for hint in card.get('hints', []):
                spans[lane] += _spans(lane, CONTRACT_FIXTURE, hint.get('lead'))
    return spans


def _flatten(value) -> list:
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, dict):
        return [token for item in value.values() for token in _flatten(item)]
    if isinstance(value, (list, tuple)):
        return [token for item in value for token in _flatten(item)]
    return []


# --------------------------------------------------------------------------
# the survey
# --------------------------------------------------------------------------


def survey(contract=None, tickets=None, guard=None, root=None) -> Survey:
    """Read every participant-facing surface once and hand the result to the guards.

    ``expected`` is the set of surfaces this host *ought* to be able to prove, and
    it is decided from what is on disk rather than from what succeeded. A surface
    that is expected and did not arrive is a failure in :func:`check_surfaces`, not
    an excuse: otherwise a reader that raised on a well-formed fixture would quietly
    reduce the coverage of the whole check and still report a pass.
    """
    if guard is None:
        guard = 'authored' if tickets is not None else 'fixture-only'
    contract = contract if contract is not None else scenario_contract.build(tickets=tickets)
    result = Survey(contract, tickets, guard)
    result.spans['contract'] = contract_spans(contract)
    result.expected.add('contract')

    from ridge import deck_narrative
    if deck_narrative.yaml is None:
        result.absent['deck'] = 'PyYAML is not installed on this host'
    else:
        result.expected.add('deck')
        try:
            result.deck = deck_narrative.load_deck(root or DECK_DIR)
            result.spans['deck'] = deck_spans(result.deck)
        except deck_narrative.DeckError as error:
            result.absent['deck'] = str(error)

    if MAP_FIXTURE.is_file():
        result.expected.add('map')
        try:
            from ridge import network_map
            result.document['map'] = network_map.build()
            result.spans['map'] = map_spans(result.document['map'])
        except Exception as error:  # noqa: BLE001 - a surface that will not load is named
            result.absent['map'] = '%s: %s' % (type(error).__name__, error)

    if BREADCRUMB_FIXTURE.is_file():
        result.expected.add('breadcrumbs')
        try:
            from ridge import breadcrumbs
            result.document['breadcrumbs'] = breadcrumbs.build(tickets=tickets, contract=contract)
            result.spans['breadcrumbs'] = breadcrumb_spans(result.document['breadcrumbs'])
        except Exception as error:  # noqa: BLE001
            result.absent['breadcrumbs'] = '%s: %s' % (type(error).__name__, error)

    if HANDOUTS.is_dir():
        result.expected.add('handout')
        result.spans['handout'] = handout_spans()
    else:
        result.absent['handout'] = 'participants/ is not on this host'
    if TEMPLATE.is_file():
        result.expected.add('web-template')
        result.spans['web-template'] = template_spans()
    else:
        result.absent['web-template'] = 'ridge/web.py is not on this host'
    # The two lanes are always provable if the contract loaded, so a NarrativeError
    # here is a broken narrative rather than a missing host, and it propagates with
    # its own message instead of being reported as an unreadable surface.
    result.expected.update(('ctfd', 'iris'))
    result.contexts = lane_contexts(contract)
    for lane, spans in context_spans(result.contexts).items():
        result.spans[lane] = spans
    return result


# --------------------------------------------------------------------------
# guards
# --------------------------------------------------------------------------
#
# Every guard returns the list of things that are wrong. A thing this host could
# not check is not wrong: it goes on ``found.unproved`` instead, and the receipt
# reports it. That distinction is the whole reason the integration container can
# run this at all - it ships the contract and no deck, no map and no breadcrumbs,
# and it has to say so rather than either failing or claiming coverage it does
# not have.


def _unproved(found, message) -> None:
    found.unproved.append(message)


def check_canon(found) -> list:
    """Every declared entity still exists where it says it does."""
    problems = []
    for category, entries in sorted(CANON.items()):
        for name, sources in sorted(entries.items()):
            for source in sources:
                if not Path(source).is_file():
                    _unproved(found, 'canon: %s %s is declared by %s, which is not on this host'
                              % (category, name, relative(source)))
                elif name not in read(source):
                    problems.append('canon: %s %s no longer appears in %s'
                                    % (category, name, relative(source)))
    return problems


def check_surfaces(found) -> list:
    """A surface this host cannot read is named; one that should be here is a failure.

    The distinction is the point. The integration image genuinely does not carry
    the deck, the map or the breadcrumbs, so those are reported as unproved. A
    surface that *is* on this host and still did not arrive - because its reader
    raised, or its fixture is malformed - is a failure, because a reader that
    quietly drops a surface would otherwise narrow the whole check's coverage and
    still report a pass.
    """
    problems = []
    for name in sorted(found.absent):
        message = 'surfaces: %s was not proved on this host (%s)' % (name, found.absent[name])
        if name in found.expected:
            problems.append(message)
        else:
            _unproved(found, message)
    for name in sorted(found.expected - set(found.spans)):
        problems.append('surfaces: %s is on this host and was not read' % name)
    for name in sorted(found.spans):
        if not [span for span in found.spans[name] if span.text.strip()]:
            problems.append('surfaces: %s produced no participant-facing text' % name)
    return problems


def check_entities(found) -> list:
    """Every name a participant can read is canon, spelled the declared way.

    Three failure modes, all of them drift. A token that reads as a name in this
    fiction and is not declared is canon nobody policed. A declared name spelled
    any other way is a variation, and the issue is explicit that a variation is a
    failure rather than a synonym. A name filed under one category and used as
    another is the same defect wearing a different hat.

    The spelling test is case-insensitive and bounded by something other than a
    word boundary, so ``$amber`` in a slide's theme tokens is a colour and not the
    sector, and the ``briefsync`` inside ``briefsync.exe`` is part of a declared
    program name rather than a misspelt ``BriefSync``.
    """
    declared = {name: category for category, entries in CANON.items() for name in entries}
    variants = {name: re.compile('(?<![$\\w.\\-/])%s(?![$\\w.\\-/])' % re.escape(name),
                                 0 if name in EXACT_CASE else re.IGNORECASE)
                for name in declared}
    problems = []
    for name in sorted(found.spans):
        for span in found.spans[name]:
            for category, pattern in ENTITY_PATTERNS:
                for token in sorted(set(pattern.findall(span.text))):
                    if token not in declared:
                        problems.append('%s: %s:%d: %r is not a declared %s'
                                        % (name, span.file, span.line, token, category))
                    elif declared[token] != category:
                        problems.append('%s: %s:%d: %r is declared as a %s but reads as a %s'
                                        % (name, span.file, span.line, token,
                                           declared[token], category))
            for token in sorted(declared):
                if token in span.text or not variants[token].search(span.text):
                    continue
                problems.append('%s: %s:%d: %s is spelled differently here'
                                % (name, span.file, span.line, token))
    return problems


def check_sections(found) -> list:
    """Every required section exists, and every surface that renders it is non-empty.

    The per-surface plan is deliberate. The deck is a projection set and carries
    the whole exercise narrative, including exposure, escalation, the outcome and
    the after-action review; a question page carries what a participant reads
    mid-investigation, so it owes the briefing, the roles, the tool map, the phases
    and the per-ticket narrative instead.     A section whose every carrier is missing
    from this host is reported as unproved rather than as a failure; a section a
    surface that is present does not carry is a failure.

    "Carries" means the lane's render context holds and fills the section. While
    the two narrative implementations coexist, the page may show the other one's
    wording for the overlapping sections; see ``SECTION_PLAN``. Holding a
    complete context that the page does not read is still the stronger claim,
    because the alternative is losing the guard.
    """
    from ridge import deck_narrative
    problems = []
    for field in scenario_contract.REQUIRED_EXERCISE_FIELDS:
        if not str(found.contract.get('exercise', {}).get(field, '')).strip():
            problems.append('contract: exercise.%s is a required section and is empty' % field)

    carriers = {}
    for lane in ('ctfd', 'iris'):
        if lane not in found.contexts:
            _unproved(found, '%s: the lane was not assembled on this host' % lane)
            continue
        carried, missing = _lane_carriers(found.contexts[lane])
        for section, fields in sorted(missing.items()):
            problems.append('%s: does not render %s (%s)' % (lane, section, ', '.join(fields)))
        carriers[lane] = carried
    if found.deck is not None:
        refs = found.deck.refs()
        for ref in deck_narrative.expected_refs(found.contract):
            if not (ref in refs or any(name.startswith(ref + '.') for name in refs)):
                problems.append('deck: never projects %r from the contract' % ref)
        carriers['deck'] = _deck_carriers(found.deck)

    for section in sorted(_obligations()):
        present = [name for name in _obligations()[section] if name in carriers]
        if not present:
            _unproved(found, 'sections: %s is required but no surface on this host renders it'
                      % section)
            continue
        for name in present:
            if section not in carriers[name]:
                problems.append('%s: does not render %s' % (name, section))
    return problems


def _obligations() -> dict:
    """section -> the surfaces that owe it."""
    owed = {}
    for section, lane_key, wanted in SECTION_PLAN:
        names = [lane for lane in ('ctfd', 'iris') if lane_key is not None]
        if wanted is not None:
            names.append('deck')
        owed[section] = names
    return owed


def _deck_carriers(deck) -> set:
    """The sections the deck actually projects, resolved against its own refs."""
    refs = deck.refs()
    carried = set()
    for section, _, wanted in SECTION_PLAN:
        if wanted is None:
            continue
        if wanted == PREFIX:
            if any(ref.startswith(_deck_prefix(section)) for ref in refs):
                carried.add(section)
        elif all(ref in refs for ref in wanted):
            carried.add(section)
    return carried


def _deck_prefix(section) -> str:
    """The contractRef prefix a prefix-shaped deck requirement means."""
    return {'roles': 'roles.', 'phases': 'phases.', 'boundaries': 'boundaries.'}[section]


def _lane_carriers(rendered) -> tuple:
    """The sections a lane is obliged to carry and does, and the ones it misses."""
    missing = _lane_missing(rendered)
    return ({section for section, key, _ in SECTION_PLAN
             if key is not None and section not in missing}, missing)


def _lane_missing(rendered) -> dict:
    """Required sections the lane's own render context does not carry.

    Defensive throughout: a render context that has lost a key outright is a
    failure this guard has to report, not a KeyError it has to raise.
    """
    from ridge.scenario_contract import REQUIRED_BOUNDARY_FIELDS, REQUIRED_TICKET_FIELDS
    missing = {}
    briefing = rendered.get('briefing') or {}
    for field in ('codename', 'fiction_notice', 'classification_line', 'premise', 'discovery',
                  'stakes'):
        if not str(briefing.get(field, '')).strip():
            missing.setdefault('exercise.%s' % field, []).append('exercise.%s' % field)
    for section in ('roles', 'tool_map', 'phases'):
        if not rendered.get(section):
            missing[section] = [section]
    tickets = rendered.get('narrative_tickets') or {}
    for ticket_id, entry in sorted(tickets.items()):
        for field in REQUIRED_TICKET_FIELDS:
            if not str(entry.get('next' if field == 'transition' else field, '')).strip():
                missing.setdefault('tickets', []).append('%s.%s' % (ticket_id, field))
        if not str(entry.get('phase_transition', '')).strip():
            missing.setdefault('tickets', []).append('%s.phase_transition' % ticket_id)
    if not tickets:
        missing.setdefault('tickets', []).append('narrative_tickets')
    if not str(rendered.get('hints_policy', '')).strip():
        missing['hints.policy'] = ['hints.policy']
    if not all(str(line).strip() for line in rendered.get('accepted') or []):
        missing['accepted'] = ['accepted']
    completion = rendered.get('ticket_complete') or {}
    for field in ('generic', 'handoff'):
        if not str(completion.get(field, '')).strip():
            missing.setdefault('ticket_complete', []).append('ticket_complete.%s' % field)
    closing = rendered.get('exercise_complete') or {}
    for field in ('brief', 'handoff', 'residual', 'scoring_note'):
        if not str(closing.get(field, '')).strip():
            missing.setdefault('exercise_complete', []).append('exercise_complete.%s' % field)
    boundaries = rendered.get('boundaries') or {}
    for field in REQUIRED_BOUNDARY_FIELDS:
        if not str(boundaries.get(field, '')).strip():
            missing.setdefault('boundaries', []).append('boundaries.%s' % field)
    return missing


def check_lineage(found) -> list:
    """Every surface names the contract revision it renders.

    The deck and the two lanes are derived from a contract object, so their
    revision is the contract's by construction. The map and the breadcrumbs are
    committed fixtures and declare the revision they were written against, which
    is the only honest way to notice a narrative change nobody revisited.
    """
    revision = found.contract.get('revision')
    problems = []
    for name, fixture, reader in (('map', MAP_FIXTURE, _map_document),
                                  ('breadcrumbs', BREADCRUMB_FIXTURE, _breadcrumb_document)):
        if not Path(fixture).is_file():
            _unproved(found, '%s: %s is not on this host' % (name, relative(fixture)))
            continue
        document = reader()
        if document is None:
            _unproved(found, '%s: %s could not be read on this host' % (name, relative(fixture)))
            continue
        declared = document.get('narrative_contract')
        if not isinstance(declared, dict):
            problems.append('%s: %s declares no narrative_contract block, so it cannot be tied '
                            'to a contract revision' % (name, relative(fixture)))
            continue
        if declared.get('contract') != CONTRACT_ID:
            problems.append('%s: %s:7 names contract %r, expected %r'
                            % (name, relative(fixture), declared.get('contract'), CONTRACT_ID))
        if declared.get('revision') != revision:
            problems.append('%s: %s was written against narrative revision %r and the contract '
                            'is at %r; re-read the fixture before the event'
                            % (name, relative(fixture), declared.get('revision'), revision))
    return problems


def _map_document():
    try:
        from ridge import network_map
        return network_map.build()
    except Exception:  # noqa: BLE001 - the fixture may legitimately be absent here
        return None


def _breadcrumb_document():
    try:
        from ridge import breadcrumbs
        return breadcrumbs.load()
    except Exception:  # noqa: BLE001
        return None


def check_provenance(found) -> list:
    """Exact drift: the committed and the regenerated surfaces are the same bytes.

    A contract-derived slide is regenerated from the contract and compared with
    what is committed, and every string a lane renders must be a contract value or
    a space-join of contract values. A hand-edit to either fails here whatever it
    says, because the contract is the only thing either is allowed to say.
    """
    from ridge import deck_narrative
    problems = []
    if found.deck is not None:
        generated = deck_narrative.generate(found.contract)
        for name in sorted(generated):
            directory = 'facilitator-pages' if name.startswith('f') else 'pages'
            committed = found.deck.root / directory / name
            if not committed.is_file():
                problems.append('deck: %s is generated from the contract but is not committed'
                                % name)
            elif committed.read_text(encoding='utf-8') != generated[name]:
                problems.append('deck: %s:1 does not match the contract it is generated from'
                                % relative(committed))
    values = contract_values(found.contract)
    for lane in sorted(found.contexts):
        for value in _rendered_values(found.contexts[lane]):
            if _composed(value, values):
                continue
            problems.append('%s: the render context states %r, which is not the contract wording'
                            % (lane, value[:90]))
    return problems


def _rendered_values(rendered) -> list:
    from ridge.web_narrative import CONTEXT_KEYS
    values = [rendered[key] for key in CONTEXT_KEYS if key != 'questions']
    for card in rendered['questions']:
        values.append({field: card[field] for field in
                       ('headline', 'brief', 'next', 'matters', 'phase_id', 'phase_title')})
        values.append([hint['lead'] for hint in card['hints']])
    return _flatten(values)


def _boundaries(token):
    for index in range(1, len(token) - 1):
        if token[index] == ' ' or (token[index] == ':' and token[index + 1] == ' '):
            yield index + 1 if token[index] == ':' else index


def _composed(token, values, seen=None) -> bool:
    """True when a value is a contract string, or a join of contract strings.

    The joiners the renderers actually use are a space and ``": "``, so those are
    the two boundaries tried. Negative results are memoised, which is sound
    because the question asked of a suffix does not depend on the prefix.
    """
    if token in values:
        return True
    seen = set() if seen is None else seen
    if token in seen or len(token) < 16:
        return False
    seen.add(token)
    for cut in _boundaries(token):
        left, right = token[:cut].strip(), token[cut:].strip()
        if left in values and _composed(right, values, seen):
            return True
    return False


def check_restatement(found) -> list:
    """No surface may restate the contract in words of its own.

    A sentence that shares a run of six content words with a contract section,
    and is not the contract's own text, is a restatement. A value drawn out of a
    published record is not a sentence and is not checked here; that is
    :func:`check_leakage`'s evidence rule to decide, and it has its own standard.
    """
    values = contract_values(found.contract)
    signature = {}
    for field, text in scenario_contract.narrative_strings(found.contract):
        for shared in ngrams(text):
            signature.setdefault(shared, field)
    problems = []
    for name in sorted(found.spans):
        for span in found.spans[name]:
            if span.kind != 'prose' or span.unit in values:
                continue
            shared = sorted(ngrams(span.text) & set(signature))
            if not shared:
                continue
            problems.append('%s: %s:%d: restates %s without saying it the same way (%r)'
                            % (name, span.file, span.line, _owner(signature, shared[0]),
                               span.text[:80]))
    return problems


def _owner(signature, shared) -> str:
    for grams, field in sorted(signature.items()):
        if grams == shared:
            return field
    return 'the contract'


def check_tools(found) -> list:
    """Every tool the issue names is placed, and the deck names the contract's set.

    A tool is placed when a participant can read a passage that names it and says
    what it is for. A bare mention on a slide is navigation, not an explanation, so
    the passage has to carry real words around the name. A tool with no passage at
    all is a failure, unless a surface that could have carried one is missing from
    this host.
    """
    problems = []
    unplaced = []
    corpus = [(name, span) for name in sorted(found.spans) for span in found.spans[name]]
    for tool in REQUIRED_TOOLS:
        if not _places(corpus, re.compile(r'\b%s\b' % re.escape(tool))):
            unplaced.append('tools: %s is never explained in participant-facing content' % tool)
    for artefact, pattern in sorted(REQUIRED_ARTEFACTS.items()):
        if not _places(corpus, pattern):
            unplaced.append('tools: %s is never explained in participant-facing content'
                            % artefact)
    for message in unplaced:
        if found.absent:
            _unproved(found, message)
        else:
            problems.append(message)
    if 'deck' in found.spans:
        deck_text = '\n'.join(span.unit for span in found.spans['deck'])
        for surface_name in sorted(_tool_spellings(found.contract)):
            spellings = _tool_spellings(found.contract)[surface_name]
            if not any(re.search(r'\b%s\b' % re.escape(word), deck_text)
                       for word in sorted(spellings)):
                problems.append('deck: never names %r, which the contract tool map explains'
                                % surface_name)
    return problems


def _tool_spellings(contract) -> dict:
    """Each contract tool surface, with the spellings the deck is allowed to use."""
    spellings = {}
    for entry in contract.get('tool_map', []):
        spellings.setdefault(str(entry.get('surface')), set()).add(str(entry.get('surface')))
    for alias, canonical in TOOL_ALIASES.items():
        spellings.setdefault(canonical, set()).add(alias)
    return spellings


def _places(corpus, pattern) -> list:
    return ['%s:%s:%d' % (name, span.file, span.line)
            for name, span in corpus
            if pattern.search(span.text) and len(words(span.text)) >= 4]


def tool_coverage(found) -> dict:
    """Where each required tool is placed, for the receipt."""
    corpus = [(name, span) for name in sorted(found.spans) for span in found.spans[name]]
    coverage = {tool: _places(corpus, re.compile(r'\b%s\b' % re.escape(tool)))
                for tool in REQUIRED_TOOLS}
    for artefact, pattern in sorted(REQUIRED_ARTEFACTS.items()):
        coverage[artefact] = _places(corpus, pattern)
    return coverage


def check_leakage(found) -> list:
    """No answer key, credential, facilitator path or deployment detail, anywhere.

    The contract and the two lanes are held to the contract's own standard: an
    exact comparison against the distinctive answers, with the fixture's
    already-public exemptions, over the text the assembler derives from the
    contract rather than over the authored question bodies behind it. The deck,
    the handouts and the template are held to the same standard, which is what
    stops a projected slide or a published handout from becoming a second answer
    key.

    The network map is the sanctioned post-completion view, so it is held to the
    evidence rule instead: a value it names has to be one a team could already
    read in the evidence published at run start, and a value only a follow-up
    release carries is a leak. ``KNOWN_RECORD_VALUES`` records the one record
    value that sits on that boundary, and the guard proves the exception is still
    needed rather than trusting it.
    """
    from ridge.scenario_contract import distinctive_answers, public_terms
    problems = []
    answers = distinctive_answers(found.tickets) if found.tickets is not None else {}
    exempt = public_terms(found.contract)
    published = _published_at_start(found.tickets, _initial_evidence())

    for name in sorted(found.spans):
        for span in found.spans[name]:
            for pattern, description in LEAK_PATTERNS:
                match = pattern.search(span.text)
                if match:
                    problems.append('%s: %s:%d carries %s (%r)'
                                    % (name, span.file, span.line, description, match.group(0)[:48]))
            for pattern, description in ATTRIBUTION_PATTERNS:
                match = pattern.search(span.text)
                if match:
                    problems.append('%s: %s:%d %s (%r)'
                                    % (name, span.file, span.line, description, match.group(0)))
            if name == 'map' or span.kind == 'data':
                continue
            haystack = span.text.lower()
            for answer, question_ids in sorted(answers.items()):
                if answer in haystack and answer not in exempt:
                    problems.append('%s: %s:%d names the answer to %s'
                                    % (name, span.file, span.line, ', '.join(question_ids)))
    for answer, question_ids in sorted(answers.items()):
        if answer in exempt or answer in published or answer in KNOWN_RECORD_VALUES:
            continue
        for span in found.spans.get('map', ()):
            if span.kind == 'prose' and answer in span.text.lower():
                problems.append('map: %s:%d names the answer to %s, whose evidence is not '
                                'published when the map unlocks'
                                % (span.file, span.line, ', '.join(question_ids)))
    for value in sorted(KNOWN_RECORD_VALUES):
        if 'map' not in found.spans:
            # Nothing to be stale against. The exception is still on the books and
            # is proved on the next host that does carry the map.
            _unproved(found, 'map: KNOWN_RECORD_VALUES lists %r and the map is not on this '
                             'host, so the exception was not proved necessary' % value)
        elif value in published or value in exempt:
            problems.append('map: KNOWN_RECORD_VALUES lists %r, which a team can now read in the '
                            'evidence published at run start; remove the exception' % value)
        elif not any(value in span.text for span in found.spans['map']):
            problems.append('map: KNOWN_RECORD_VALUES lists %r, which the map no longer shows; '
                            'remove the exception' % value)
    return problems


def leak_receipt(found) -> dict:
    """The answer-key half of the receipt: how much was guarded, over what."""
    from ridge.scenario import RELEASE_FILES
    from ridge.scenario_contract import distinctive_answers
    answers = distinctive_answers(found.tickets) if found.tickets is not None else {}
    released = {name for names in RELEASE_FILES.values() for name in names}
    return {
        'questions_guarded': sum(len(ids) for ids in answers.values()),
        'initial_evidence': len(_initial_evidence(released)),
        'follow_up_evidence': len(released),
        'record_values': sorted(KNOWN_RECORD_VALUES),
    }


def _initial_evidence(released=None) -> set:
    """The published tree as it stands before any ticket unlocks anything."""
    from ridge.scenario import RELEASE_FILES
    if released is None:
        released = {name for names in RELEASE_FILES.values() for name in names}
    if not CASE_MANIFEST.is_file():
        return set()
    document = json.loads(read(CASE_MANIFEST))
    return {str(entry.get('path')).removeprefix('/evidence/')
            for entry in document.get('evidence_files', [])} - released


def _published_at_start(tickets, initial) -> set:
    """Answers a team could already read in the evidence on the mount at run start.

    Keyed on the evidence path each question names, not on the ticket, because
    what decides whether a value is available is whether the record carrying it
    has been published yet. Where this host ships no answer key the set is empty
    and the receipt says the leak guard was ``fixture-only``.
    """
    found = set()
    for ticket in tickets or []:
        for question in ticket['questions']:
            path = str(question.get('evidence', '')).removeprefix('/evidence/')
            if path and path in initial:
                found.add(str(question.get('answer', '')).strip().lower())
    return {value for value in found if value}


def check_determinism(found) -> list:
    """The narrative is a pure function of committed bytes.

    Every source the event renders from has to be tracked by git, so a clean
    install reads the same bytes a run start did. Where git is unavailable the
    tracking check is skipped and the receipt says so, rather than being reported
    as a pass. Regenerating the deck is :func:`check_provenance`'s job; here the
    claim is only that the deck was in hand to be regenerated.
    """
    problems = []
    tracked = _tracked()
    for path in narrative_sources():
        if not Path(path).is_file():
            _unproved(found, 'determinism: %s is not on this host' % relative(path))
        elif tracked is not None and relative(path) not in tracked:
            problems.append('determinism: %s is not tracked by git, so a clean install cannot '
                            'reproduce the narrative' % relative(path))
    if found.deck is None:
        _unproved(found, 'determinism: the deck was not read, so it was not regenerated')
    elif tracked is None:
        _unproved(found, 'determinism: git is unavailable, so the sources were not proved '
                         'tracked')
    return problems


def _tracked():
    try:
        output = subprocess.check_output(['git', '-C', str(ROOT), 'ls-files'],
                                         text=True, stderr=subprocess.DEVNULL)
    except (OSError, subprocess.CalledProcessError):  # pragma: no cover - git is present in CI
        return None
    return set(output.splitlines())


def narrative_sources() -> list:
    """Every committed file the participant-facing narrative is rendered from."""
    sources = [CONTRACT_FIXTURE, MAP_FIXTURE, BREADCRUMB_FIXTURE, TEMPLATE, GLOSSARY,
               GROUND_TRUTH, ANSWER_KEY, GUIDES]
    for directory in (DECK_PAGES, DECK_FACILITATOR_PAGES, HANDOUTS):
        if directory.is_dir():
            sources += sorted(directory.glob('*.md' if directory == HANDOUTS else '*.page'))
    return sources


def digests() -> dict:
    """SHA-256 of every committed narrative source, in a stable order."""
    return {relative(path): hashlib.sha256(Path(path).read_bytes()).hexdigest()
            for path in narrative_sources() if Path(path).is_file()}


# --------------------------------------------------------------------------
# the single entry point
# --------------------------------------------------------------------------

# The guards, in the order a reader should hear about them. Naming them here
# rather than calling each by hand keeps ``validate`` to one loop and keeps the
# order stable, so a receipt and a failure list read the same way.
GUARDS = ('canon', 'surfaces', 'entities', 'sections', 'lineage', 'provenance', 'restatement',
          'tools', 'determinism', 'leakage')
_GUARDS = {
    'canon': check_canon,
    'surfaces': check_surfaces,
    'entities': check_entities,
    'sections': check_sections,
    'lineage': check_lineage,
    'provenance': check_provenance,
    'restatement': check_restatement,
    'tools': check_tools,
    'determinism': check_determinism,
    'leakage': check_leakage,
}


def run_guard(name, found) -> list:
    """Run one named guard and return what it found wrong."""
    return _GUARDS[name](found)


def validate(contract=None, tickets=None, root=None, found=None) -> dict:
    """Run every guard. Raises ConsistencyError listing everything that is wrong."""
    if found is None:
        if tickets is None:
            try:
                from expanded.author import build as author
                tickets = author()
                guard = 'authored'
            except ImportError:  # pragma: no cover - the integration container
                tickets, guard = None, 'fixture-only'
        else:
            guard = 'authored'
        found = survey(contract, tickets, guard, root)
    problems = []
    for name in GUARDS:
        problems += run_guard(name, found)
    if problems:
        raise ConsistencyError('narrative consistency check failed:\n  - '
                               + '\n  - '.join(sorted(set(problems))))
    return receipt(found)


def receipt(found) -> dict:
    """The deterministic receipt: what was proved, from which bytes, on which surfaces."""
    from ridge import deck_narrative
    carriers = {}
    for lane in ('ctfd', 'iris'):
        if lane in found.contexts:
            carriers[lane] = sorted(_lane_carriers(found.contexts[lane])[0])
    if found.deck is not None:
        carriers['deck'] = sorted(_deck_carriers(found.deck))
    lineage = {name: found.contract['revision'] for name in ('ctfd', 'iris', 'deck')
               if name in found.spans}
    for name in ('map', 'breadcrumbs'):
        declared = (found.document.get(name) or {}).get('narrative_contract') or {}
        if declared:
            lineage[name] = declared.get('revision')
    leak = leak_receipt(found)
    return {
        'contract': CONTRACT_ID,
        'revision': found.contract['revision'],
        'consistent': True,
        'surfaces': sorted(found.spans),
        'surfaces_not_proved': {name: found.absent[name] for name in sorted(found.absent)},
        'not_proved': sorted(set(found.unproved)),
        'lineage': {name: lineage[name] for name in sorted(lineage)},
        'sections': carriers,
        'entities': {'declared': sum(len(entries) for entries in CANON.values()),
                     'categories': sorted(CANON)},
        'tools': tool_coverage(found),
        'answers_guarded': leak['questions_guarded'],
        'leak_guard': found.guard,
        'initial_evidence_files': leak['initial_evidence'],
        'follow_up_evidence_files': leak['follow_up_evidence'],
        'record_values_on_the_map': leak['record_values'],
        'deck_slides_regenerated': (len(deck_narrative.GENERATED)
                                    if found.deck is not None else 0),
        'git_tracked': _tracked() is not None,
        'sha256': digests(),
    }


def check_deployment(path=None) -> dict:
    """Load the contract and prove the whole integrated event tells one story.

    The preflight entry point. Raises :class:`ConsistencyError` for an integrated
    event that has drifted, and lets the contract's own errors through unchanged,
    so a malformed contract is never reported as a consistency problem.
    """
    return validate(contract=scenario_contract.load(path))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description='Prove the CTFd, IRIS, deck, map and breadcrumb surfaces tell one story.')
    parser.add_argument('--receipt', action='store_true', help='print the JSON receipt')
    parser.add_argument('--contract', type=Path, default=None,
                        help='validate an alternative contract fixture')
    arguments = parser.parse_args(argv)
    from ridge.web_narrative import NarrativeError
    try:
        result = check_deployment(arguments.contract)
    except (ConsistencyError, scenario_contract.ContractError, NarrativeError) as error:
        print(str(error), file=sys.stderr)
        return 1
    if arguments.receipt:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print('narrative consistent across %s at contract revision %s: %d entities, %d tools, '
              '%d answers guarded%s'
              % (', '.join(result['surfaces']), result['revision'],
                 result['entities']['declared'], len(result['tools']),
                 result['answers_guarded'],
                 ('; not proved here: %d item(s)' % len(result['not_proved']))
                 if result['not_proved'] else ''))
    return 0


if __name__ == '__main__':
    sys.exit(main())
