"""Narrative loader, generator and validator for the event-day deck (issue 58).

``docs/event-day-deck/`` carried its own prose for the incident, the roles and
the four investigation phases, so it drifted from the CTFd question page and the
IRIS case, which now render from ``assets/scenario-narrative-v1.json``. This
module makes the contract the only source of scenario wording in the deck.

The deck is the surface that gets projected, so its text is the most exposed of
the three. The mechanism is deliberately small.

Generated pages
    Every slide whose wording is scenario prose is emitted from the contract by
    :func:`write`, not typed. The layout is a template here; the sentences are
    not. Nothing in this module restates the scenario in its own words.

``contractRef`` markers
    Each contract-derived string carries ``contractRef: <field path>`` on its
    element, and :func:`check_contract` requires the rendered text to equal the
    contract value exactly. Drift stops being a review question and becomes a
    failing test. A ref to a list field, such as ``phases.phase-1.tickets``,
    must render the list joined by the deck's own separator, so the ticket set
    and its order are checked too.

``audience`` separation
    Participant slides live in ``pages/`` and are the projection set. Facilitator
    callouts live in ``facilitator-pages/`` behind a second project file, so the
    participant project cannot reference them even by accident.
    :func:`check_audience` fails if a page lands in the wrong directory, if the
    two sets overlap, or if either project lists the other's slides.

What this module deliberately cannot do is produce the PDF.
``event-day-deck.pdf`` is a build artifact of an external ``.pptd`` toolchain
(``kimi-slides``) that is not vendored in this repository and is not published
to any package registry, so it can be neither rebuilt nor verified here. The
``.page`` sources are therefore authoritative, :func:`pdf_freshness` reports when
the committed PDF has fallen behind them, and ``docs/event-day-deck/README.md``
records the operator command. Nothing here fabricates or hand-edits a PDF.

Reading the sources needs PyYAML, which CI pins
(``.github/workflows/validate.yml``). Everything else is stdlib and nothing
performs network access.
"""
import argparse
import html
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

try:  # pragma: no cover - see the skip guard in tests/test_deck_narrative.py
    import yaml
except ImportError:  # pragma: no cover - CI installs PyYAML, local dev may not
    yaml = None

ROOT = Path(__file__).resolve().parents[1]
DECK_DIR = ROOT / 'docs/event-day-deck'
PARTICIPANT_DIR = DECK_DIR / 'pages'
FACILITATOR_DIR = DECK_DIR / 'facilitator-pages'
PROJECT = DECK_DIR / 'event-day-deck.pptd'
FACILITATOR_PROJECT = DECK_DIR / 'facilitator-appendix.pptd'
PDF = DECK_DIR / 'event-day-deck.pdf'

# The renderer lays out on a fixed 960x540 canvas. A box outside it crops
# silently, which is the failure mode a build step would normally catch.
CANVAS_W, CANVAS_H = 960, 540

# Theme tokens the .pptd actually defines. An element naming anything else
# renders with an unintended default colour or size.
THEME_COLORS = ('paper', 'ink', 'slate', 'deep', 'amber', 'muted', 'line', 'palegreen')
THEME_STYLES = ('tag', 'title', 'body', 'small', 'stepnum')

# Every phase field the deck must carry. The deck is only allowed to be thin
# here if the contract itself is thin, which is a visible decision.
REQUIRED_PHASE_FIELDS = ('title', 'timeframe', 'purpose', 'urgency', 'tickets', 'action',
                         'transition')
REQUIRED_ROLE_FIELDS = ('name', 'duty', 'authority', 'not')
REQUIRED_EXERCISE_FIELDS = ('classification_line', 'premise', 'discovery', 'exposure',
                             'escalation', 'stakes', 'outcome')
REQUIRED_BOUNDARY_FIELDS = ('read_only', 'no_credentials', 'no_operational_detail',
                            'fiction_repeat', 'attribution')

# A ref may only address a participant-facing part of the contract.
# ``exercise_complete`` states the supported exposure and the residual unknowns,
# which is the closing statement other surfaces deliver once the exercise ends;
# projecting it from a briefing slide would pre-empt it. ``adversary`` holds the
# authoring rule for this fixture, not participant guidance.
FORBIDDEN_REF_PREFIXES = ('exercise_complete.brief', 'exercise_complete.residual',
                          'exercise_complete.scoring_note', 'exercise.adversary.')

FACILITATOR_BANNER = 'FACILITATOR ONLY — DO NOT PROJECT'
TICKET_SEPARATOR = ' · '
FOOTER = 'OPERATION SILENT RIDGE — EXERCISE ONLY'
MARGIN = 64
CONTENT_W = 832
COL_GAP = 40
COL_W = 396
COL2_X = MARGIN + COL_W + COL_GAP
RULE_Y = 116

THEME = {
    'colors': {
        'paper': '#F5F2EA', 'ink': '#1A1E24', 'slate': '#27403B', 'deep': '#16211E',
        'amber': '#C77D1F', 'muted': '#6B6E6A', 'line': '#D8D2C4', 'palegreen': '#E4E9E2',
    },
    'textStyles': {
        'tag': {'fontSize': 13, 'color': '$amber', 'bold': True, 'letterSpacing': 3},
        'title': {'fontSize': 30, 'color': '$ink', 'bold': True},
        'body': {'fontSize': 16, 'color': '$ink', 'lineHeight': 1.5},
        'small': {'fontSize': 12, 'color': '$muted', 'lineHeight': 1.4},
        'stepnum': {'fontSize': 44, 'color': '$amber', 'bold': True},
    },
}

PROJECT_TITLE = 'Operation Silent Ridge — Event Day Participant Deck'
FACILITATOR_PROJECT_TITLE = 'Operation Silent Ridge — Facilitator Appendix (do not project)'


class DeckError(ValueError):
    """Raised when a deck source is malformed, drifting or unsafe."""


# --------------------------------------------------------------------------
# reading


def read_yaml(path):
    """Parse one deck source. The ``.page`` and ``.pptd`` files are plain YAML."""
    if yaml is None:  # pragma: no cover - guarded by the test module skip
        raise DeckError('PyYAML is required to read the deck sources')
    source = Path(path)
    if not source.is_file():
        raise DeckError('deck source not found: ' + str(source))
    document = yaml.safe_load(source.read_text(encoding='utf-8'))
    if not isinstance(document, dict):
        raise DeckError('%s: expected a mapping at the top level' % source.name)
    return document


def plain(value):
    """Flatten one value to the words a participant would actually read."""
    if isinstance(value, dict):
        return plain(value.get('text', ''))
    if isinstance(value, (list, tuple)):
        return '\n'.join(part for part in (plain(item) for item in value) if part)
    text = re.sub(r'<[^>]+>', ' ', str(value))
    return re.sub(r'\s+', ' ', html.unescape(text)).strip()


def element_text(element):
    """Every reader-visible string on one element, table cells included."""
    chunks = []
    if 'content' in element:
        chunks.append(plain(element['content']))
    for row in element.get('rows') or []:
        line = ' '.join(plain(cell) for cell in row)
        if line:
            chunks.append(line)
    return '\n'.join(chunk for chunk in chunks if chunk)


@dataclass(frozen=True)
class Page:
    path: Path
    document: dict

    @property
    def name(self):
        return self.path.name

    @property
    def audience(self):
        return str(self.document.get('audience', ''))

    @property
    def page_type(self):
        return str(self.document.get('pageType', ''))

    @property
    def elements(self):
        return list(self.document.get('elements') or [])

    def text(self):
        return '\n'.join(filter(None, (element_text(el) for el in self.elements)))

    def refs(self):
        """contract field path -> [(elementId, rendered text)]"""
        found = {}
        for element in self.elements:
            ref = element.get('contractRef')
            if ref:
                found.setdefault(str(ref), []).append((element.get('elementId'),
                                                        element_text(element)))
        return found


@dataclass(frozen=True)
class Deck:
    root: Path
    projects: tuple
    pages: tuple

    @property
    def participant(self):
        return tuple(page for page in self.pages if page.audience == 'participant')

    @property
    def facilitator(self):
        return tuple(page for page in self.pages if page.audience == 'facilitator')

    def by_ref(self, ref):
        return [(page.name, element_id, text)
                for page in self.pages for element_id, text in page.refs().get(ref, ())]

    def refs(self):
        return {ref for page in self.pages for ref in page.refs()}

    def inventory(self):
        return {page.name: page.audience for page in self.pages}


def load_page(path):
    document = read_yaml(path)
    for field in ('pageType', 'audience', 'background', 'elements'):
        if field not in document:
            raise DeckError('%s: missing required key %r' % (Path(path).name, field))
    if not document.get('elements'):
        raise DeckError('%s: a slide must carry at least one element' % Path(path).name)
    return Page(Path(path), document)


def source_pages(directory):
    directory = Path(directory)
    if not directory.is_dir():
        raise DeckError('deck source directory not found: ' + str(directory))
    return sorted(directory.glob('*.page'))


def load_deck(root=None):
    """Load both projects and every slide they reference, in projection order."""
    base = Path(root) if root else DECK_DIR
    if not base.is_absolute():
        base = ROOT / base
    if not base.is_dir():
        raise DeckError('deck directory not found: ' + str(base))
    projects = []
    pages = []
    declared_everywhere = set()
    for index, project_path in enumerate((base / PROJECT.name, base / FACILITATOR_PROJECT.name)):
        if not project_path.is_file():
            raise DeckError('deck project not found: ' + str(project_path))
        project = read_yaml(project_path)
        projects.append(project)
        declared = project.get('pages') or []
        if not declared:
            raise DeckError('%s: the project lists no slides' % project_path.name)
        for entry in declared:
            if not isinstance(entry, str) or '/' not in entry:
                raise DeckError('%s: %r is not a pages/<name>.page path'
                                % (project_path.name, entry))
            if not (base / entry).is_file():
                raise DeckError('%s: lists %s, which is not in the deck source tree'
                                % (project_path.name, entry))
            if entry in declared_everywhere:
                raise DeckError('%s: %s is claimed by more than one project'
                                % (project_path.name, entry))
            declared_everywhere.add(entry)
            pages.append(load_page(base / entry))
        expected = 0 if index == 0 else 1
        if str(project.get('audience', '')) != ('participant', 'facilitator')[expected]:
            raise DeckError('%s: declares audience %r, expected %r'
                            % (project_path.name, project.get('audience'),
                               ('participant', 'facilitator')[expected]))
    on_disk = {'%s/%s' % (directory.name, path.name)
               for directory in (PARTICIPANT_DIR, FACILITATOR_DIR)
               for path in source_pages(base / directory.name)}
    unlisted = sorted(on_disk - declared_everywhere)
    if unlisted:
        raise DeckError('deck slides exist but no project lists them: ' + ', '.join(unlisted))
    return Deck(base, tuple(projects), tuple(pages))


# --------------------------------------------------------------------------
# contract resolution


def resolve(contract, ref):
    """Look up a dotted field path in the contract, or raise.

    A list is indexed either by position or, for the contract's id-keyed lists
    such as ``phases``, by the ``id`` of its entries, so ``phases.phase-1.purpose``
    reads the way the slides are labelled.
    """
    node = contract
    for part in str(ref).split('.'):
        if isinstance(node, list):
            if part.lstrip('-').isdigit():
                try:
                    node = node[int(part)]
                    continue
                except IndexError:
                    raise DeckError('contractRef %r: no such list index' % ref)
            matches = [entry for entry in node
                       if isinstance(entry, dict) and str(entry.get('id')) == part]
            if len(matches) != 1:
                raise DeckError('contractRef %r: %r matches %d contract entries'
                                % (ref, part, len(matches)))
            node = matches[0]
        elif isinstance(node, dict) and part in node:
            node = node[part]
        else:
            raise DeckError('contractRef %r: the contract has no such field' % ref)
    return node


def rendered(value):
    """The one rendering a contract value is allowed to have on a slide."""
    if isinstance(value, list):
        return TICKET_SEPARATOR.join(str(item) for item in value)
    return str(value)


def expected_refs(contract):
    """Every contract field the deck is required to project.

    Derived from the contract rather than listed, so widening the contract
    widens the deck's obligations instead of leaving a hole in it.
    """
    wanted = ['exercise.' + field for field in REQUIRED_EXERCISE_FIELDS]
    wanted += ['boundaries.' + field for field in REQUIRED_BOUNDARY_FIELDS]
    wanted += ['accepted.' + field for field in ('lead', 'credit', 'shared')]
    wanted += ['ticket_complete.' + field for field in ('generic', 'handoff')]
    wanted += ['hints.policy', 'aar.intro', 'aar.close', 'exercise_complete.handoff']
    wanted += ['phases.' + phase['id'] + '.' + field
               for phase in contract['phases'] for field in REQUIRED_PHASE_FIELDS]
    wanted += ['roles.' + role['id'] + '.' + field
               for role in contract['roles'] for field in REQUIRED_ROLE_FIELDS]
    return wanted


def check_contract(deck, contract):
    """Every contractRef must resolve, and match its contract value exactly."""
    problems = []
    for page in deck.pages:
        for ref, found in sorted(page.refs().items()):
            if ref.startswith(FORBIDDEN_REF_PREFIXES):
                problems.append('%s: contractRef %r must not be projected on a briefing slide'
                                % (page.name, ref))
                continue
            try:
                expected = rendered(resolve(contract, ref))
            except DeckError as error:
                problems.append('%s: %s' % (page.name, error))
                continue
            for element_id, text in found:
                if text != expected:
                    problems.append('%s.%s: rendered text does not match %r'
                                    % (page.name, element_id, ref))
    return problems


def check_coverage(deck, contract):
    """The deck must actually carry the contract, not merely reference it."""
    found = deck.refs()
    problems = []
    for ref in expected_refs(contract):
        # A list field may be projected as one element per item.
        covered = ref in found or any(field.startswith(ref + '.') for field in found)
        if not covered:
            problems.append('the deck never projects %r from the contract' % ref)
    return problems


def check_phases(deck, contract):
    """Every investigation phase must state a purpose, an urgency and an action.

    Enforced per phase rather than for the deck as a whole: a phase that loses
    its action line is a defect even when the other three are complete.
    """
    problems = []
    for phase in contract['phases']:
        prefix = 'phases.' + phase['id'] + '.'
        for field in REQUIRED_PHASE_FIELDS:
            if not deck.by_ref(prefix + field):
                problems.append('%s: no slide states %s' % (phase['id'], field))
    return problems


# --------------------------------------------------------------------------
# safety


def check_no_answers(deck, tickets, contract):
    """No distinctive scored answer may appear on any slide.

    Held to the contract's own standard: an exact comparison against the
    distinctive answers, with the fixture's already-public exemptions. The
    facilitator appendix is included rather than trusted, because a page that
    ends up in the wrong project is exactly the drift this is here to catch.
    """
    from ridge import scenario_contract

    exempt = scenario_contract.public_terms(contract)
    answers = scenario_contract.distinctive_answers(tickets)
    problems = []
    for page in deck.pages:
        haystack = page.text().lower()
        for answer, question_ids in sorted(answers.items()):
            if answer in exempt or answer not in haystack:
                continue
            problems.append('%s: shows the answer to %s' % (page.name, ', '.join(question_ids)))
    return problems


# Shapes that would put a credential, a private address or a live target on a
# projected slide. The deck legitimately shows service ports, the
# <event-address> placeholder and the words "the password from the handout", so
# none of those is a finding; a value bound to a label is.
SECRET_PATTERNS = (
    (re.compile(r'-----BEGIN [A-Z ]*PRIVATE KEY'), 'a private key block'),
    (re.compile(r'\b(?:password|passwd|secret|token|api[_-]?key|passphrase)\b\s*[:=]\s*\S',
                re.IGNORECASE), 'a credential assignment'),
    (re.compile(r'\b(?:ssh-rsa|ssh-ed25519)AAAA'), 'an embedded public key'),
    (re.compile(r'\$[2aby]\$\d{2}\$[A-Za-z0-9./]{10,}'), 'a password hash'),
    (re.compile(r'file:/etc/silent-ridge/'), 'a private secret reference'),
    (re.compile(r'\b(?:192\.0\.2|198\.51\.100|203\.0\.113)\.\d{1,3}\b'),
     'a documentation-range host address'),
    (re.compile(r'\b[A-Za-z0-9-]+\.example\.invalid\b'), 'a deployment hostname'),
    (re.compile(r'\b(?:10\.\d{1,3}|192\.168|172\.(?:1[6-9]|2\d|3[01]))'
                r'\.\d{1,3}\.\d{1,3}\b'), 'a private infrastructure address'),
    (re.compile(r'[A-Za-z0-9+/]{48,}={0,2}'), 'an encoded credential blob'),
)

# No adversary name is in canon and the closing ticket scores "no" for intent,
# so no slide may attribute the activity to a person, a group or a sponsor.
ATTRIBUTION_PATTERNS = (
    (re.compile(r'wraith', re.IGNORECASE), 'names an adversary group that is not in canon'),
    (re.compile(r'\b(?:APT\d*|threat actor group|state[- ]sponsored)\b', re.IGNORECASE),
     'attributes the activity to a group'),
    (re.compile(r'\bsponsor(?:ed|ship)?\s+by\b', re.IGNORECASE), 'attributes a sponsor'),
    (re.compile(r'\b(?:hacktivists?|cybercriminals?|nation[- ]state)\b', re.IGNORECASE),
     'names an adversary'),
)


def check_secrets(deck):
    """No credential, private address, encoded secret or attribution on a slide."""
    problems = []
    for page in deck.pages:
        haystack = page.text()
        for pattern, description in SECRET_PATTERNS:
            found = pattern.search(haystack)
            if found:
                problems.append('%s: %s (%r)' % (page.name, description, found.group(0)[:40]))
        for pattern, description in ATTRIBUTION_PATTERNS:
            found = pattern.search(haystack)
            if found:
                problems.append('%s: %s (%r)' % (page.name, description, found.group(0)))
    return problems


# --------------------------------------------------------------------------
# audience separation


def check_audience(deck):
    """The projection set and the facilitator appendix must stay disjoint."""
    problems = []
    participant_project, facilitator_project = deck.projects
    participant_names = {page.path.name for page in deck.participant}
    facilitator_names = {page.path.name for page in deck.facilitator}
    if not participant_names:
        problems.append('there are no participant slides to project')
    if not facilitator_names:
        problems.append('the facilitator appendix is missing')
    overlap = participant_names & facilitator_names
    if overlap:
        problems.append('slides are in both sets: ' + ', '.join(sorted(overlap)))
    unknown = {page.name for page in deck.pages} - participant_names - facilitator_names
    if unknown:
        problems.append('slides declare no usable audience: ' + ', '.join(sorted(unknown)))

    for project, project_name, directory in (
            (participant_project, PROJECT.name, PARTICIPANT_DIR.name),
            (facilitator_project, FACILITATOR_PROJECT.name, FACILITATOR_DIR.name)):
        for entry in project.get('pages') or []:
            if not entry.startswith(directory + '/'):
                problems.append('%s lists %s, which is not under %s/'
                                % (project_name, entry, directory))
    for page in deck.participant:
        if page.path.parent.name != PARTICIPANT_DIR.name:
            problems.append('%s: a participant slide lives outside pages/' % page.name)
    for page in deck.facilitator:
        if page.path.parent.name != FACILITATOR_DIR.name:
            problems.append('%s: a facilitator slide lives outside facilitator-pages/' % page.name)
        if FACILITATOR_BANNER not in page.text():
            problems.append('%s: a facilitator slide is not visibly marked %r'
                            % (page.name, FACILITATOR_BANNER))
    return problems


# --------------------------------------------------------------------------
# geometry and offline legibility


def _check_tokens(where, node):
    if not isinstance(node, dict):
        return []
    problems = []
    style = node.get('style')
    if isinstance(style, str) and style.startswith('$') and style[1:] not in THEME_STYLES:
        problems.append('%s: %r is not a theme text style' % (where, style))
    for key in ('color', 'background-color'):
        value = node.get(key)
        if isinstance(value, str) and value.startswith('$') and value[1:] not in THEME_COLORS:
            problems.append('%s: %r is not a theme color' % (where, value))
    for nested in ('cellStyle', 'firstRowStyle', 'border', 'fill'):
        problems.extend(_check_tokens(where, node.get(nested)))
    return problems


def check_geometry(deck):
    """Bounds and theme references must survive the .pptd toolchain.

    A box outside the canvas crops silently and an undefined token renders as an
    unintended default, so both are caught here rather than on a projector.
    Decorative shapes are exempt from the canvas bound: a ring that bleeds off
    the edge is a deliberate part of the cover and the closing slide, and the
    pages that shipped before this module rely on it.
    """
    problems = []
    for page in deck.pages:
        seen = set()
        for element in page.elements:
            element_id = str(element.get('elementId', ''))
            if not element_id:
                problems.append('%s: an element has no elementId' % page.name)
            elif element_id in seen:
                problems.append('%s: duplicate elementId %r' % (page.name, element_id))
            seen.add(element_id)
            bounds = element.get('bounds')
            if not isinstance(bounds, list) or len(bounds) != 4:
                problems.append('%s.%s: bounds must be [x, y, w, h]' % (page.name, element_id))
                continue
            if not all(isinstance(value, int) and not isinstance(value, bool)
                       for value in bounds):
                problems.append('%s.%s: bounds must be integers' % (page.name, element_id))
                continue
            x, y, w, h = bounds
            if w <= 0 or h <= 0:
                problems.append('%s.%s: bounds must be positive' % (page.name, element_id))
            if element.get('elementType') in ('text', 'line'):
                if x < 0 or y < 0 or x + w > CANVAS_W or y + h > CANVAS_H:
                    problems.append('%s.%s: bounds %r fall outside the %dx%d canvas'
                                    % (page.name, element_id, bounds, CANVAS_W, CANVAS_H))
            for key in ('content', 'border', 'fill', 'style'):
                problems.extend(_check_tokens('%s.%s' % (page.name, element_id),
                                              element.get(key)))
    return problems


# A conservative estimate of the vertical space a text block needs, and the only
# source of box heights in the generated slides. A line is taken from the box
# width and the body size because that is what the renderer wraps on. It is the
# offline stand-in for a render: with the .pptd toolchain unavailable it is the
# only way to know a slide is legible before it reaches a projector, so
# :func:`measure` sizes the generated boxes and :func:`check_overflow` then
# holds the hand-authored ones to the same standard.
#
# The constants are calibrated so every page that shipped before this module
# passes unchanged. They are deliberately not tighter, because a check that
# cries wolf on known-good slides gets ignored.
_LINE_FACTOR = 0.47
_PARA_GAP = 2
_DEFAULT_LINE_HEIGHT = 1.25
_STYLE_SIZES = {'tag': 13, 'title': 30, 'body': 16, 'small': 12, 'stepnum': 44}
_STYLE_LINE_HEIGHTS = {'tag': 1.25, 'title': 1.15, 'body': 1.5, 'small': 1.4, 'stepnum': 1.15}


def _paragraphs(text):
    return [chunk for chunk in re.split(r'</p>', text) if chunk.strip()] or ['']


def _font_size(content):
    size = content.get('fontSize')
    if isinstance(size, int):
        return size
    return _STYLE_SIZES.get(str(content.get('style', '')).lstrip('$'), 16)


def _line_height(content):
    if isinstance(content.get('lineHeight'), (int, float)):
        return float(content['lineHeight'])
    return _STYLE_LINE_HEIGHTS.get(str(content.get('style', '')).lstrip('$'),
                                   _DEFAULT_LINE_HEIGHT)


def measure(value, width, content):
    """Pixels ``value`` needs in a box ``width`` wide, under ``content`` styling.

    Shared by the generator and the checker so a generated box cannot be
    declared smaller than the text that goes in it.
    """
    paragraphs = value if isinstance(value, (list, tuple)) else _paragraphs(str(value))
    size = _font_size(content)
    step = size * _line_height(content)
    per_line = max(8, int(width / (size * _LINE_FACTOR)))
    lines = sum(max(1, -(-len(plain(paragraph)) // per_line)) for paragraph in paragraphs)
    return int(round(lines * step + max(0, lines - 1) * _PARA_GAP))


# Average glyph advance as a fraction of the body size, for the no-wrap width
# check. The same relation the wrap estimate uses, and calibrated to the tightest
# line that shipped before this module.
_ADVANCE = _LINE_FACTOR


def check_nowrap_width(deck):
    """A ``wrap: false`` element is one line, so it must also fit its box width.

    The existing pages use no-wrap for short heads, labels, footers and page
    numbers. One that outgrows its box runs off the slide instead of wrapping,
    which the height check cannot see.
    """
    problems = []
    for page in deck.pages:
        for element in page.elements:
            bounds = element.get('bounds')
            content = element.get('content')
            if not (isinstance(bounds, list) and len(bounds) == 4
                    and isinstance(content, dict) and content.get('wrap') is False):
                continue
            value = str(content.get('text', ''))
            for line in value.split('\n'):
                needed = int(len(plain(line)) * _font_size(content) * _ADVANCE)
                if needed > bounds[2]:
                    problems.append('%s.%s: a no-wrap line needs about %dpx, box is %dpx'
                                    % (page.name, element.get('elementId'), needed, bounds[2]))
    return problems


def check_overflow(deck, tolerance=0):
    """Report text blocks that cannot fit their declared box."""
    problems = []
    for page in deck.pages:
        for element in page.elements:
            bounds = element.get('bounds')
            content = element.get('content')
            if not (isinstance(bounds, list) and len(bounds) == 4
                    and isinstance(content, dict)):
                continue
            raw = content.get('text')
            if not isinstance(raw, str) or not raw.strip():
                continue
            needed = measure(raw, bounds[2], content)
            if needed > bounds[3] + tolerance:
                problems.append('%s.%s: needs about %dpx, box is %dpx'
                                % (page.name, element.get('elementId'), needed, bounds[3]))
    return problems


def _boxes_overlap(first, second):
    ax, ay, aw, ah = first
    bx, by, bw, bh = second
    return ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah


def check_overlap(deck):
    """Two text boxes on one slide must not sit on top of each other.

    The generated slides lay themselves out top-down from measured heights, so a
    collision means a height was wrong; the hand-authored ones get the same
    check. Tables and shapes are excluded: a table legitimately sits inside a
    region and a card is meant to sit behind its own text.
    """
    problems = []
    for page in deck.pages:
        boxes = [(element.get('elementId'), element['bounds']) for element in page.elements
                 if element.get('elementType') == 'text'
                 and isinstance(element.get('bounds'), list)
                 and len(element['bounds']) == 4]
        for index, (name, bounds) in enumerate(boxes):
            for other, other_bounds in boxes[index + 1:]:
                if _boxes_overlap(bounds, other_bounds):
                    problems.append('%s: %s %r overlaps %s %r'
                                    % (page.name, name, bounds, other, other_bounds))
    return problems


def sha256(path):
    import hashlib

    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for block in iter(lambda: handle.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def pdf_freshness(root=None):
    """Report whether the committed PDF is older than the sources it renders.

    A warning rather than a build: the PDF comes from a toolchain this
    repository does not vendor, so this only tells the operator that the binary
    on disk no longer matches the committed ``.page`` sources.
    """
    base = Path(root) if root else DECK_DIR
    pdf = base / PDF.name
    if not pdf.is_file():
        return {'pdf': str(pdf), 'present': False, 'stale': True, 'reason': 'not built'}
    sources = [base / PROJECT.name, base / FACILITATOR_PROJECT.name]
    sources += source_pages(base / PARTICIPANT_DIR.name)
    sources += source_pages(base / FACILITATOR_DIR.name)
    sources = [path for path in sources if path.is_file()]
    if not sources:
        return {'pdf': str(pdf), 'present': True, 'stale': True, 'reason': 'no sources'}
    newest = max(sources, key=lambda path: path.stat().st_mtime)
    pdf_mtime = pdf.stat().st_mtime
    return {
        'pdf': str(pdf),
        'present': True,
        'pdf_sha256': sha256(pdf),
        'newest_source': newest.name,
        'stale': newest.stat().st_mtime > pdf_mtime,
        'pdf_older_by_seconds': max(0, int(newest.stat().st_mtime - pdf_mtime)),
    }


# --------------------------------------------------------------------------
# reporting and the single entry point


def validate(deck, contract, tickets, overflow_tolerance=0):
    """Run every guard. Raises DeckError listing everything that is wrong."""
    problems = []
    problems += check_geometry(deck)
    problems += check_overlap(deck)
    problems += check_nowrap_width(deck)
    problems += check_audience(deck)
    problems += check_contract(deck, contract)
    problems += check_coverage(deck, contract)
    problems += check_phases(deck, contract)
    problems += check_secrets(deck)
    problems += check_no_answers(deck, tickets, contract)
    problems += check_overflow(deck, overflow_tolerance)
    if problems:
        raise DeckError('event-day deck validation failed:\n  - ' + '\n  - '.join(problems))


def report(deck, contract, tickets):
    """The deterministic validation receipt: what the deck says, and whether it holds."""
    phases = {}
    for phase in contract['phases']:
        prefix = 'phases.' + phase['id'] + '.'
        slides = sorted({name for field in REQUIRED_PHASE_FIELDS
                         for name, _, _ in deck.by_ref(prefix + field)})
        phases[phase['id']] = {
            'title': phase['title'],
            'tickets': list(phase['tickets']),
            'slides': slides,
            'purpose': bool(deck.by_ref(prefix + 'purpose')),
            'urgency': bool(deck.by_ref(prefix + 'urgency')),
            'action': bool(deck.by_ref(prefix + 'action')),
            'transition': bool(deck.by_ref(prefix + 'transition')),
        }
    inventory = deck.inventory()
    return {
        'slides': len(inventory),
        'contract_refs': sum(len(page.refs()) for page in deck.pages),
        'participant_facing': sorted(name for name, audience in inventory.items()
                                     if audience == 'participant'),
        'facilitator_only': sorted(name for name, audience in inventory.items()
                                   if audience == 'facilitator'),
        'phases': phases,
        'overflow': check_overflow(deck),
        'pdf': pdf_freshness(deck.root),
    }


# --------------------------------------------------------------------------
# generation

# Pages whose wording is scenario prose. They are emitted from the contract, so
# their content cannot drift. The other slides are operational walkthroughs that
# the contract has nothing to say about, and stay hand-authored.
GENERATED = ('01_cover.page', '02_brief.page', '03_stakes.page', '04_role.page',
             '05_urgency.page', '07_phases.page', '08_phase1.page', '09_phase2.page',
             '10_phase3.page', '11_phase4.page', '18_reminders.page', '21_aar.page',
             '22_close.page', 'f01_run_of_show.page', 'f02_callouts.page')

# A plain scalar is only emitted when the reader can parse it back identically.
# The allowlist is deliberately narrow: a bare scalar also has to survive being a
# value inside a flow mapping, where the closing brace would otherwise be
# swallowed, and it must not resolve to a number or a YAML 1.1 keyword.
_PLAIN = re.compile(r"[A-Za-z0-9][A-Za-z0-9 ._\-/()'’·—+=]*$")
_KEYWORDS = frozenset(('true', 'false', 'null', '~', 'yes', 'no', 'on', 'off'))
_NUMBER = re.compile(r'[-+]?[0-9][0-9_]*(\.[0-9]+)?$')


def _bare(value):
    text = str(value)
    return (bool(_PLAIN.match(text)) and not text.endswith(('.', ':'))
            and not _NUMBER.match(text) and text.lower() not in _KEYWORDS)


def _scalar(value):
    if value is None:
        return 'null'
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, (list, tuple)):
        return '[' + ', '.join(_scalar(item) for item in value) + ']'
    if isinstance(value, dict):
        return '{' + ', '.join('%s: %s' % (key, _scalar(item))
                               for key, item in value.items()) + '}'
    if _bare(value):
        return str(value)
    return '"' + str(value).replace('\\', '\\\\').replace('"', '\\"') + '"'


class Canvas:
    """Emits one ``.page`` source.

    The layout vocabulary is the existing one: a tag, a title, a rule, column
    heads with their own rules, tagged blocks, and a footer with a page number.
    Keeping it in one place is what lets fifteen generated slides stay visually
    consistent without a hand-tuned pass over each one.
    """

    def __init__(self, page_type='content', audience='participant', background='$paper',
                 title_size=30, footer=FOOTER):
        self.page_type = page_type
        self.audience = audience
        self.background = background
        self.title_size = title_size
        self.footer = footer
        self.elements = []

    def shape(self, element_id, bounds, color, border=None, shape_name='rect', adjustments=None):
        element = {'elementId': element_id, 'elementType': 'shape', 'bounds': list(bounds),
                   'shapeName': shape_name}
        if adjustments:
            element['adjustments'] = list(adjustments)
        element['fill'] = {'type': 'solid', 'color': color}
        if border:
            element['border'] = border
        self.elements.append(element)
        return self

    def line(self, element_id, x, y, w, h=2, width=2, color='$line', arrow=None):
        element = {'elementId': element_id, 'elementType': 'line', 'bounds': [x, y, w, h],
                   'viewBox': [w, h], 'points': '0,%s %s,%s' % (h / 2.0, w, h / 2.0),
                   'curve': 'sharp'}
        if arrow:
            element['arrow'] = list(arrow)
        element['border'] = {'style': 'solid', 'width': width, 'color': color}
        self.elements.append(element)
        return self

    def text(self, element_id, bounds, content, ref=None):
        """A text element. The box grows to fit its text; returns that height.

        Self-sizing everywhere is what keeps the generated slides legible without
        a render pass, and :func:`check_overflow` then holds the hand-authored
        slides to the same standard.
        """
        x, y, w = bounds[0], bounds[1], bounds[2]
        needed = measure(str(content.get('text', '')), w, content)
        element = {'elementId': element_id, 'elementType': 'text', 'bounds': [x, y, w, needed]}
        if ref:
            element['contractRef'] = ref
        element['content'] = content
        self.elements.append(element)
        return needed

    def head(self, element_id, y, label, x=MARGIN, w=CONTENT_W, color='$slate', size=15,
             align=None, ref=None):
        content = {'fontSize': size, 'bold': True, 'color': color, 'wrap': False}
        if align:
            content['align'] = list(align)
        content['text'] = label
        return self.text(element_id, [x, y, w, 0], content, ref=ref)

    def body(self, element_id, bounds, value, ref=None, size=15, style='$body',
             line_height=None, color=None, width=None):
        """A text block. The box grows to fit the text, never the other way round.

        A contract string is never reflowed across source lines: the deck is
        compared with the contract literally, so a line break introduced by the
        author would change the rendered words and fail that comparison.
        """
        content = {}
        if style:
            content['style'] = style
        if size:
            content['fontSize'] = size
        if line_height:
            content['lineHeight'] = line_height
        if color:
            content['color'] = color
        paragraphs = value if isinstance(value, (list, tuple)) else ['<p>%s</p>' % value]
        content['text'] = '\n'.join(paragraphs)
        return self.text(element_id, [bounds[0], bounds[1], width or bounds[2], 0], content,
                         ref=ref)

    def block(self, element_id, y, label, value, ref=None, x=MARGIN, w=CONTENT_W, size=15,
              color='$amber', line_height=None, gap=10):
        """A tagged prose block: label, rule, then the text. Returns the next y."""
        label_height = self.head(element_id + '-label', y, label, x=x, w=w, color=color,
                                 size=13)
        rule_y = y + label_height + 6
        self.line(element_id + '-rule', x, rule_y, w, 2, width=2, color=color)
        text_y = rule_y + 12
        used = self.body(element_id, [x, text_y, w, 0], value, ref=ref, size=size,
                         line_height=line_height, width=w)
        return text_y + used + gap

    def card(self, name, x, y, w, label, color='$slate', fill='$palegreen', pad=14):
        """Draw a card and its label. Returns the y for content and the shape index.

        The index is returned rather than recomputed later: the card is drawn
        before its text so it sits behind it, and resizing it by arithmetic on
        ``len(self.elements)`` is how a card ends up swallowing its own label.
        """
        label_height = measure(label, w - 2 * pad, {'fontSize': 13, 'wrap': False})
        index = len(self.elements)
        self.shape(name + '-card', [x, y, w, label_height + 54], fill,
                   border={'style': 'solid', 'width': 1, 'color': color})
        self.head(name + '-label', y + pad, label, x=x + pad, w=w - 2 * pad, color=color,
                  size=13)
        self.line(name + '-rule', x + pad, y + pad + label_height + 8, w - 2 * pad, 2, width=2,
                  color=color)
        return y + pad + label_height + 20, index

    def resize(self, index, height):
        self.elements[index]['bounds'][3] = height
        return self

    def to_yaml(self):
        lines = ['# Generated by python -m ridge.deck_narrative --write. Scenario wording is',
                 '# rendered from assets/scenario-narrative-v1.json; do not retype it here.',
                 'pageType: ' + _scalar(self.page_type),
                 'audience: ' + _scalar(self.audience),
                 'background:',
                 '  type: solid',
                 '  color: ' + _scalar(self.background),
                 'elements:']
        for element in self.elements:
            lines.extend(_emit_element(element))
        lines.append('')
        return '\n'.join(lines)

    def finish(self, page_number):
        self.text('footer', [MARGIN, 505, 700, 18],
                  {'fontSize': 12, 'color': '#7E877F', 'wrap': False, 'text': self.footer})
        if page_number is not None:
            self.text('pagenum', [880, 505, 40, 18],
                      {'fontSize': 12, 'color': '#7E877F', 'align': ['right', 'top'],
                       'wrap': False, 'text': str(page_number)})
        return self.to_yaml()


def _emit_element(element):
    indent = '  '
    lines = [indent + '- elementId: ' + _scalar(element['elementId']),
             indent + '  elementType: ' + _scalar(element['elementType']),
             indent + '  bounds: ' + _scalar(element['bounds'])]
    for key in ('contractRef', 'shapeName', 'adjustments', 'viewBox', 'points', 'curve',
                'arrow', 'columnWidths', 'rowHeights'):
        if key in element:
            lines.append(indent + '  ' + key + ': ' + _scalar(element[key]))
    for key in ('fill', 'border'):
        if key in element:
            lines.append(indent + '  ' + key + ': ' + _scalar(element[key]))
    content = element.get('content')
    if isinstance(content, dict):
        text = str(content.get('text', ''))
        if '\n' in text or len(text) > 110:
            lines.append(indent + '  content:')
            for key, value in content.items():
                if key == 'text':
                    continue
                lines.append(indent + '    ' + key + ': ' + _scalar(value))
            lines.append(indent + '    text: |')
            for row in text.rstrip('\n').split('\n'):
                lines.append(indent + '      ' + row)
        else:
            lines.append(indent + '  content: ' + _scalar(content))
    elif content is not None:
        lines.append(indent + '  content: ' + _scalar(content))
    return lines


def _columns(count, x=MARGIN, total=CONTENT_W, gap=COL_GAP):
    width = int((total - gap * (count - 1)) / count)
    return [(x + index * (width + gap), width) for index in range(count)]


def _header(canvas, tag, title, title_size=30, title_width=832, title_ref=None):
    canvas.text('tag', [MARGIN, 40, 400, 20], {'style': '$tag', 'wrap': False, 'text': tag})
    canvas.text('title', [MARGIN, 66, title_width, 40],
                {'style': '$title', 'fontSize': title_size, 'wrap': False, 'text': title},
                ref=title_ref)
    canvas.line('rule', MARGIN, RULE_Y, CONTENT_W)
    return RULE_Y + 20


def _column_pair(canvas, y, left, right, gap=28):
    """Two labelled prose columns. Returns the y below the taller of the two."""
    bottom = y
    for (x, w), (name, label, value, ref, color) in zip(_columns(2), (left, right)):
        head = canvas.head(name + '-head', y, label, x=x, w=w, color=color, size=15)
        canvas.line(name + '-rule', x, y + head + 8, w, 2, width=2, color=color)
        used = canvas.body(name, [x, y + head + 20, w, 0], value, ref=ref, size=14)
        bottom = max(bottom, y + head + 20 + used)
    return bottom + gap


def generate(contract):
    """Build every generated slide from the contract. Returns name -> source text."""
    pages = {
        '01_cover.page': _cover(contract),
        '02_brief.page': _brief(contract),
        '03_stakes.page': _stakes(contract),
        '04_role.page': _roles(contract),
        '05_urgency.page': _urgency(contract),
        '07_phases.page': _phases(contract),
        '18_reminders.page': _reminders(contract),
        '21_aar.page': _aar(contract),
        '22_close.page': _close(contract),
        'f01_run_of_show.page': _run_of_show(contract),
        'f02_callouts.page': _callouts(contract),
    }
    for index, phase in enumerate(contract['phases'], start=1):
        pages['%02d_phase%d.page' % (index + 7, index)] = _phase(phase, index,
                                                                len(contract['phases']))
    return pages


def _cover(contract):
    exercise = contract['exercise']
    canvas = Canvas(page_type='cover', background='$deep')
    canvas.shape('ring-outer', [600, 90, 380, 380], '#3A524B66', shape_name='donut',
                 adjustments=[4000])
    canvas.shape('ring-mid', [660, 150, 260, 260], '#3A524B88', shape_name='donut',
                 adjustments=[5000])
    canvas.shape('ring-inner', [720, 210, 140, 140], '#3A524BAA', shape_name='donut',
                 adjustments=[7000])
    canvas.shape('patrol-dot', [852, 168, 16, 16], '$amber', shape_name='ellipse')
    canvas.text('patrol-label', [700, 400, 180, 22],
                {'fontSize': 13, 'color': '#C9CFC7', 'letterSpacing': 2,
                 'align': ['center', 'middle'], 'wrap': False, 'text': 'PATROL LANTERN'})
    canvas.text('kicker', [64, 116, 480, 24],
                {'style': '$tag', 'wrap': False, 'text': 'DEFENSIVE CYBERSECURITY EXERCISE'})
    canvas.text('title', [64, 148, 560, 120],
                {'fontSize': 52, 'bold': True, 'color': '#F5F2EA', 'lineHeight': 1.1,
                 'text': '<p>Operation</p>\n<p>Silent Ridge</p>'})
    canvas.line('rule', 64, 288, 120, 3, width=3, color='$amber')
    y = canvas.body('outcome', [64, 312, 512, 0], exercise['outcome'], ref='exercise.outcome',
                    size=15, style=None, color='#C9CFC7') + 334
    canvas.head('classification-label', y, 'CLASSIFICATION', x=64, w=200, color='$amber',
                size=12)
    canvas.text('classification', [64, y + 18, 512, 20],
                {'fontSize': 13, 'color': '#C9CFC7', 'wrap': False,
                 'text': exercise['classification_line']},
                ref='exercise.classification_line')
    canvas.body('fiction', [64, 456, 512, 0], contract['boundaries']['fiction_repeat'],
                ref='boundaries.fiction_repeat', size=12, style=None, color='#7E877F',
                line_height=1.4)
    return canvas.finish(1)


def _brief(contract):
    """The opening brief: what the situation is, what the review found, what is open."""
    exercise = contract['exercise']
    canvas = Canvas()
    y = _header(canvas, 'PART 1 · THE INCIDENT', 'The incident brief')
    y += canvas.body('premise', [64, y, 832, 0], exercise['premise'],
                     ref='exercise.premise', size=15) + 28
    _column_pair(canvas, y,
                 ('discovery', 'WHAT THE REVIEW FOUND', exercise['discovery'],
                  'exercise.discovery', '$slate'),
                 ('exposure', 'WHAT IS STILL UNKNOWN', exercise['exposure'],
                  'exercise.exposure', '$amber'))
    return canvas.finish(2)


def _stakes(contract):
    """Why it matters, how far the response got, and the limit of any claim."""
    exercise = contract['exercise']
    canvas = Canvas()
    y = _header(canvas, 'PART 1 · THE INCIDENT',
                'How far the response got, and what is at stake')
    y = _column_pair(canvas, y + 8,
                     ('escalation', 'HOW THE RESPONSE WENT', exercise['escalation'],
                      'exercise.escalation', '$slate'),
                     ('stakes', 'WHY IT MATTERS', exercise['stakes'], 'exercise.stakes',
                      '$slate'), gap=32)
    canvas.block('attribution', y, 'AND WHAT NO FINDING MAY SUPPORT',
                 contract['boundaries']['attribution'], ref='boundaries.attribution', size=14)
    return canvas.finish(3)


def _roles(contract):
    """The three participant roles, each with its authority and its limit."""
    canvas = Canvas()
    _header(canvas, 'PART 1 · THE INCIDENT', 'Your role, and what you are not')
    for (x, w), role in zip(_columns(3, gap=20), contract['roles']):
        prefix = 'role-' + role['id']
        ref = 'roles.' + role['id'] + '.'
        cursor = canvas.head(prefix + '-name', 140, role['name'], x=x, w=w, color='$slate',
                             size=15, ref=ref + 'name') + 150
        canvas.line(prefix + '-rule', x, cursor, w, 2, width=2, color='$slate')
        cursor += 16
        cursor += canvas.body(prefix + '-duty', [x, cursor, w, 0], role['duty'],
                              ref=ref + 'duty', size=13) + 24
        cursor += canvas.head(prefix + '-authority-label', cursor, 'YOU DECIDE', x=x, w=w,
                              color='$amber', size=11) + 8
        cursor += canvas.body(prefix + '-authority', [x, cursor, w, 0], role['authority'],
                              ref=ref + 'authority', size=13) + 24
        cursor += canvas.head(prefix + '-not-label', cursor, 'YOU DO NOT', x=x, w=w,
                              color='$amber', size=11) + 8
        canvas.body(prefix + '-not', [x, cursor, w, 0], role['not'], ref=ref + 'not', size=13)
    return canvas.finish(4)


def _urgency(contract):
    """The four cues the briefing has to make unmissable before any tool is opened."""
    boundaries = contract['boundaries']
    first = contract['phases'][0]
    first_ref = 'phases.' + first['id'] + '.'
    canvas = Canvas()
    y = _header(canvas, 'PART 1 · THE INCIDENT',
                'Four things that are urgent, and what urgent means here') + 8
    cues = (
        ('start', 'THE START WINDOW', '$amber',
         [(first['timeframe'], first_ref + 'timeframe'), (first['urgency'], first_ref + 'urgency')]),
        ('preserve', 'PRESERVE WHAT IS THERE', '$slate',
         [(boundaries['no_operational_detail'], 'boundaries.no_operational_detail')]),
        ('own', 'OWN THE TICKET', '$amber',
         [(contract['ticket_complete']['handoff'], 'ticket_complete.handoff'),
          (contract['accepted']['credit'], 'accepted.credit')]),
        ('escalate', 'ESCALATE, DO NOT STALL', '$slate',
         [(boundaries['no_credentials'], 'boundaries.no_credentials')]),
    )
    rows = []
    row = 0
    first = 0
    for index, (name, label, color, entries) in enumerate(cues):
        x, w = _columns(2)[index % 2]
        top = y if index < 2 else y + row
        cursor, card_index = canvas.card(name, x, top, w, label, color=color)
        for value, ref in entries:
            cursor += canvas.body(name + '-' + ref.rsplit('.', 1)[-1],
                                  [x + 14, cursor, w - 28, 0], value, ref=ref, size=13,
                                  line_height=1.4) + 8
        height = cursor - top + 8
        canvas.resize(card_index, height)
        rows.append((card_index, height))
        if index == 0:
            first = height
        if index == 1:
            # Both cards in a row share a height, so the four cues read as a set.
            row = max(first, height)
            for card in rows[:2]:
                canvas.resize(card[0], row)
    return canvas.finish(5)


def _phases(contract):
    """The four phases at a glance, before any of them is worked."""
    canvas = Canvas()
    y = _header(canvas, 'PART 2 · HOW THE DAY WORKS', 'Four investigation phases, in order')
    y += canvas.body('lead', [64, y, 832, 0],
                     'The twenty tickets partition across four phases. A phase is a group of '
                     'questions that answer each other; do not cherry-pick across them.',
                     size=13, style='$small') + 16
    cards = []
    row = 0
    first = 0
    for index, phase in enumerate(contract['phases']):
        prefix = 'phases.' + phase['id'] + '.'
        x, w = _columns(2)[index % 2]
        top = y if index < 2 else y + row
        cursor, card_index = canvas.card('phase%d' % (index + 1), x, top, w,
                                        'PHASE %d' % (index + 1), color='$amber')
        cursor += canvas.text('phase%d-tickets' % (index + 1), [x + 14, cursor, w - 28, 0],
                              {'fontSize': 13, 'bold': True, 'color': '$amber',
                               'text': TICKET_SEPARATOR.join(phase['tickets'])},
                              ref=prefix + 'tickets') + 8
        cursor += canvas.text('phase%d-title' % (index + 1), [x + 14, cursor, w - 28, 0],
                              {'fontSize': 19, 'bold': True, 'color': '$slate',
                               'text': phase['title']}, ref=prefix + 'title') + 10
        cursor += canvas.body('phase%d-urgency' % (index + 1), [x + 14, cursor, w - 28, 0],
                              phase['urgency'], ref=prefix + 'urgency', size=12,
                              line_height=1.4)
        cursor -= top
        canvas.resize(card_index, cursor + 6)
        cards.append(card_index)
        if index == 0:
            first = cursor + 6
        if index == 1:
            row = max(first, cursor + 6)
    for index in cards[2:]:
        canvas.resize(index, row)
    return canvas.finish(7)


def _phase(phase, index, total):
    """One investigation phase: what it is for, why now, what to do, what follows."""
    prefix = 'phases.' + phase['id'] + '.'
    canvas = Canvas()
    y = _header(canvas, 'PART 2 \u00b7 HOW THE DAY WORKS \u2014 PHASE %d OF %d'
                % (index, total), phase['title'], title_size=27, title_width=528,
                title_ref=prefix + 'title')
    canvas.head('tickets-label', 64, 'TICKETS IN THIS PHASE', x=600, w=296, color='$amber',
                size=11, align=['right', 'top'])
    # The widest phase lists eight tickets, so this wraps rather than running off
    # the header; the no-wrap check would otherwise shrink every ticket list to
    # fit the shortest phase.
    canvas.text('tickets', [600, 82, 296, 0],
                {'fontSize': 13, 'bold': True, 'color': '$slate', 'align': ['right', 'top'],
                 'text': TICKET_SEPARATOR.join(phase['tickets'])},
                ref=prefix + 'tickets')
    canvas.text('timeframe', [64, y - 8, 832, 0],
                {'style': '$small', 'wrap': False, 'text': phase['timeframe']},
                ref=prefix + 'timeframe')
    y = _column_pair(canvas, y + 30,
                     ('purpose', 'PURPOSE', phase['purpose'], prefix + 'purpose', '$slate'),
                     ('urgency', 'URGENCY', phase['urgency'], prefix + 'urgency', '$amber'),
                     gap=32)
    y = canvas.block('action', y, 'WHAT YOU DO HERE', phase['action'], ref=prefix + 'action')
    canvas.block('transition', y, 'AND THEN', phase['transition'], ref=prefix + 'transition',
                 size=14)
    return canvas.finish(index + 7)


def _reminders(contract):
    canvas = Canvas()
    y = _header(canvas, 'PART 4 \u00b7 WORKING RULES',
                'Reminders: how solo work becomes shared work')
    cards_spec = (
        ('nothing', 'NOTHING YOU DO SHOULD CHANGE A SYSTEM', '$slate',
         [(contract['boundaries']['read_only'], 'boundaries.read_only')]),
        ('shared', 'EVERY ANSWER BECOMES A SHARED FINDING', '$slate',
         [(contract['accepted']['lead'], 'accepted.lead'),
          (contract['accepted']['shared'], 'accepted.shared')]),
        ('closed', 'A CLOSED TICKET STAYS ON THE RECORD', '$slate',
         [(contract['ticket_complete']['generic'], 'ticket_complete.generic')]),
    )
    tallest = 0
    cards = []
    for (x, w), (name, label, color, entries) in zip(_columns(3, gap=20), cards_spec):
        cursor, card_index = canvas.card(name, x, y, w, label, color=color)
        for value, ref in entries:
            cursor += canvas.body(name + '-' + ref.rsplit('.', 1)[-1],
                                  [x + 14, cursor, w - 28, 0], value, ref=ref, size=13) + 10
        canvas.resize(card_index, cursor - y + 6)
        cards.append(card_index)
        tallest = max(tallest, cursor - y + 6)
    for index in cards:
        canvas.resize(index, tallest)
    canvas.block('hints', y + tallest + 26, 'AND IF YOU GET STUCK', contract['hints']['policy'],
                 ref='hints.policy', size=14)
    return canvas.finish(18)


def _aar(contract):
    aar = contract['aar']
    canvas = Canvas()
    y = _header(canvas, 'PART 5 \u00b7 CLOSING', 'Closing: the after-action review')
    y += canvas.body('intro', [64, y, 832, 0], aar['intro'], ref='aar.intro', size=15) + 20
    y += canvas.body('handoff', [64, y, 832, 0], contract['exercise_complete']['handoff'],
                     ref='exercise_complete.handoff', size=15) + 28
    y += canvas.head('prompts-head', y, 'THE FIVE QUESTIONS, IN ORDER', x=64, w=832, size=13) + 8
    canvas.line('prompts-rule', 64, y, 832, 2, width=2, color='$amber')
    y += 14
    for index, prompt in enumerate(aar['prompts']):
        used = canvas.text('prompt%d' % (index + 1), [96, y, 800, 0],
                           {'fontSize': 15, 'color': '$ink', 'wrap': False, 'text': prompt},
                           ref='aar.prompts.%d' % index)
        used = max(used, canvas.text('prompt%d-num' % (index + 1), [64, y, 30, 0],
                                     {'fontSize': 15, 'bold': True, 'color': '$amber',
                                      'wrap': False, 'text': '%d.' % (index + 1)}))
        y += used + 8
    return canvas.finish(21)


def _close(contract):
    canvas = Canvas(page_type='final', background='$deep')
    canvas.shape('ring-outer', [760, 320, 260, 260], '#3A524B66', shape_name='donut',
                 adjustments=[5000])
    canvas.shape('ring-inner', [820, 380, 140, 140], '#3A524B99', shape_name='donut',
                 adjustments=[8000])
    canvas.text('tag', [64, 88, 400, 22], {'style': '$tag', 'wrap': False,
                                           'text': "YOU'RE READY"})
    canvas.text('title', [64, 116, 700, 60],
                {'fontSize': 36, 'bold': True, 'color': '#F5F2EA', 'wrap': False,
                 'text': 'What successful completion looks like'})
    canvas.line('rule', 64, 190, 120, 3, width=3, color='$amber')
    y = canvas.body('close', [64, 214, 700, 0], contract['aar']['close'], ref='aar.close',
                    size=16, style=None, color='#C9CFC7') + 242
    y += canvas.head('urls-title', y, 'YOUR FOUR ADDRESSES', x=64, w=300, color='$amber',
                     size=13) + 12
    canvas.text('urls', [64, y, 700, 44],
                {'fontSize': 14, 'color': '#C9CFC7', 'lineHeight': 1.6,
                 'text': 'IRIS :8081 \u00b7 CTFd :8083 \u00b7 Wazuh :8443 (HTTPS) '
                         '\u00b7 Team desktop :8082'})
    canvas.body('fiction', [64, 460, 700, 0], contract['boundaries']['fiction_repeat'],
                ref='boundaries.fiction_repeat', size=13, style=None, color='#7E877F',
                line_height=1.4)
    return canvas.finish(22)


# -- facilitator appendix --------------------------------------------------


def _banner(canvas):
    canvas.shape('facilitator-banner', [0, 0, CANVAS_W, 52], '$amber')
    canvas.text('facilitator-banner-text', [0, 12, CANVAS_W, 28],
                {'fontSize': 18, 'bold': True, 'color': '#16211E',
                 'align': ['center', 'middle'], 'wrap': False, 'text': FACILITATOR_BANNER})


def _run_of_show(contract):
    canvas = Canvas(audience='facilitator', background='$deep')
    _banner(canvas)
    canvas.text('title', [64, 92, 832, 36],
                {'fontSize': 26, 'bold': True, 'color': '#F5F2EA', 'wrap': False,
                 'text': 'Facilitator appendix: run of show'})
    canvas.body('intro', [64, 140, 832, 56],
                'Project the participant deck only. The detailed procedure lives in '
                'docs/event-day-commands.md and docs/runbook.md; this slide records which '
                'slide goes up when, so a facilitator covering the room is never guessing.',
                size=14, style=None, color='#C9CFC7', line_height=1.5)
    canvas.head('order-head', 212, 'SLIDE ORDER', x=64, w=832, color='$amber', size=13)
    canvas.line('order-rule', 64, 238, 832, 2, width=2, color='$amber')
    for index, item in enumerate((
            '1-5   incident brief, role and urgency',
            '6-7   how the day works, and the four investigation phases',
            '8-11  one slide per phase — show the phase a team is in, not all four',
            '12-17 the four-tab setup and the tools',
            '18-22 reminders, ground rules, troubleshooting, AAR and close')):
        canvas.text('order%d' % (index + 1), [64, 250 + index * 26, 832, 22],
                    {'fontSize': 13, 'color': '#C9CFC7', 'wrap': False, 'text': item})
    canvas.body('boundary', [64, 396, 832, 72], contract['boundaries']['no_credentials'],
                ref='boundaries.no_credentials', size=13, style=None, color='#C9CFC7',
                line_height=1.4)
    return canvas.finish('F1')


def _callouts(contract):
    canvas = Canvas(audience='facilitator', background='$deep')
    _banner(canvas)
    canvas.text('title', [64, 92, 832, 36],
                {'fontSize': 26, 'bold': True, 'color': '#F5F2EA', 'wrap': False,
                 'text': 'Facilitator appendix: pause, inject, delay, recover'})
    cards = (
        ('pause', 'PAUSE THE CLOCK',
         'python -m ridge.deploy pause --profile event-profile.json --runtime R',
         'For a floor interruption, a failed login sweep or a room-wide announcement. '
         'Announce the pause before you stop, and resume deliberately.'),
        ('inject', 'INJECT BRIEFING',
         'python -m ridge.cli announce --operator EXCON --text "..."',
         'Injects are authored on the day, not in this deck. Send text only: no answers, no '
         'adversary names, nothing a team has not already earned.'),
        ('delay', 'SYNCHRONISATION DELAY',
         'wait about ten seconds, then re-check',
         'Scoring and finding publication run in the background. A finding that has not '
         'appeared yet is a delay, not a fault. Do not recover a ticket over it.'),
        ('recover', 'RECOVER A STUCK TICKET',
         'python -m ridge.cli recover T03 --generation 1 --operator EXCON --reason "..."',
         'Only when a ticket is unusable, not when it is hard. Points already earned on it '
         'stay earned. Read docs/runbook.md before recovering.'),
    )
    for index, (name, label, command, note) in enumerate(cards):
        (x, w) = _columns(2)[index % 2]
        y = 140 + (index // 2) * 180
        canvas.shape(name + '-card', [x, y, w, 164], '#22302C',
                     border={'style': 'solid', 'width': 1, 'color': '$amber'})
        canvas.head(name + '-label', y + 12, label, x=x + 14, w=w - 28, color='$amber', size=13)
        canvas.line(name + '-rule', x + 14, y + 40, w - 28, 2, width=2, color='$amber')
        used = canvas.text(name + '-command', [x + 14, y + 50, w - 28, 0],
                           {'fontSize': 11, 'color': '#C9CFC7', 'lineHeight': 1.4,
                            'text': command}) + 10
        canvas.text(name + '-note', [x + 14, y + 50 + used, w - 28, 0],
                    {'fontSize': 12, 'color': '#C9CFC7', 'lineHeight': 1.4, 'text': note})
    return canvas.finish('F2')


# --------------------------------------------------------------------------
# writing


def write(root=None):
    """Regenerate every contract-derived slide and both project files.

    Returns ``{filename: path}``. The ``.page`` files stay committed: an operator
    does not have to run this for the deck to be correct, because ``validate``
    checks the committed text against the contract. It exists so that an
    intentional narrative change lands as a mechanical diff.
    """
    from ridge import scenario_contract

    base = Path(root) if root else DECK_DIR
    contract = scenario_contract.build()
    generated = generate(contract)
    written = {}
    for name in sorted(generated):
        directory = FACILITATOR_DIR.name if name.startswith('f') else PARTICIPANT_DIR.name
        target = base / directory / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(generated[name], encoding='utf-8', newline='\n')
        written[name] = str(target)
    # The project lists every slide in the deck, generated or hand-authored, in
    # projection order. Naming the hand-authored ones here too is what stops a
    # new slide from being added to a directory and quietly left unrendered.
    participant = ['%s/%s' % (PARTICIPANT_DIR.name, path.name)
                   for path in source_pages(base / PARTICIPANT_DIR.name)]
    facilitator = ['%s/%s' % (FACILITATOR_DIR.name, path.name)
                   for path in source_pages(base / FACILITATOR_DIR.name)]
    _write_project(base / PROJECT.name, 'participant', PROJECT_TITLE, participant,
                   facilitator_project=FACILITATOR_PROJECT.name)
    _write_project(base / FACILITATOR_PROJECT.name, 'facilitator', FACILITATOR_PROJECT_TITLE,
                   facilitator, participant_project=PROJECT.name)
    return written


def _write_project(path, audience, title, pages, participant_project=None,
                   facilitator_project=None):
    lines = [
        '# The .page sources are authoritative. This project file is generated by',
        '# python -m ridge.deck_narrative --write from the scenario contract.',
        'version: v2',
        'title: ' + _scalar(title),
        'audience: ' + audience,
        'size: [%d, %d]' % (CANVAS_W, CANVAS_H),
        'theme:',
        '  colors:',
    ]
    for name, value in THEME['colors'].items():
        lines.append('    %s: %s' % (name, _scalar(value)))
    lines.append('  textStyles:')
    for name, value in THEME['textStyles'].items():
        lines.append('    %s:' % name)
        for key, item in value.items():
            lines.append('      %s: %s' % (key, _scalar(item)))
    if participant_project:
        lines.append('participantProject: ' + _scalar(participant_project))
    if facilitator_project:
        lines.append('facilitatorProject: ' + _scalar(facilitator_project))
    lines.append('pages:')
    for entry in pages:
        lines.append('  - ' + entry)
    lines.append('')
    path.write_text('\n'.join(lines), encoding='utf-8', newline='\n')


def main(argv=None):
    parser = argparse.ArgumentParser(description='Validate and regenerate the event-day deck.')
    parser.add_argument('--write', action='store_true',
                        help='regenerate the contract-derived slides and both project files')
    parser.add_argument('--report', action='store_true', help='print the validation receipt')
    parser.add_argument('--pdf', action='store_true',
                        help='report whether the committed PDF is older than its sources')
    parser.add_argument('--tolerance', type=int, default=0,
                        help='pixels of text-box overflow to tolerate')
    parser.add_argument('--root', type=Path, default=None, help='override the deck directory')
    arguments = parser.parse_args(argv)

    base = arguments.root or DECK_DIR
    if arguments.write:
        print(json.dumps({'written': sorted(write(base))}, indent=2))
        return 0

    from ridge import scenario_contract

    tickets = _authored()
    contract = scenario_contract.build(tickets=tickets)
    deck = load_deck(base)
    if arguments.pdf:
        print(json.dumps(pdf_freshness(base), indent=2))
        return 0
    validate(deck, contract, tickets, overflow_tolerance=arguments.tolerance)
    if arguments.report:
        print(json.dumps(report(deck, contract, tickets), indent=2))
    else:
        print('event-day deck OK: %d participant slides, %d facilitator-only, %d contract refs'
              % (len(deck.participant), len(deck.facilitator),
                 sum(len(page.refs()) for page in deck.pages)))
    return 0


def _authored():
    from expanded.author import build as author

    return author()


if __name__ == '__main__':
    sys.exit(main())
