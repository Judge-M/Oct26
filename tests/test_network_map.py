"""Deterministic tests for the T01 exfiltration network map (issue 66).

The map is an additional view of evidence T01 already exposes. These tests are
what stop it becoming a second source of truth, a pre-answer to the ticket it
follows, or a document that could reach the address it draws.

No CTFd, IRIS, Docker, browser or network is required: the map is a committed
fixture plus a renderer over it. The published-evidence checks build a real
release with ``expanded.prepare`` and join the map's keys against it, which is
the only honest way to prove the map keys on ``request``/``path``/``time`` and
not on the ``id`` column that preparation rewrites.
"""
import csv
import html
import json
import math
import re
import tempfile
import unittest
from pathlib import Path

try:
    import jinja2
except ImportError:  # jinja2 ships with the deployment images, not with the source tree
    jinja2 = None

from ridge.network_map import (
    CONFIDENCE, FIXTURE, KEY_FIELDS, MAP_ID, NODE_HEIGHT, NODE_KINDS, SCHEMA, UNLOCKS_AFTER,
    MapError, build, load, offline_report, parse, render, validate, write, _edge_geometry, _width,
)
from ridge.scenario import NETWORK_MAP
from ridge.web import network_map_link

ROOT = Path(__file__).resolve().parents[1]
VIEW_WIDTH = 1320
CASED = json.loads((ROOT / 'assets/autopsy-case-v2.json').read_text(encoding='utf-8'))
PUBLISHED = {entry['path'] for entry in CASED['evidence_files']}

# Record labels used when the evidence was authored. expanded/prepare.py replaces
# the id column of every published CSV with a twelve-character hash, so these are
# facilitator shorthand and must never appear in a participant-facing map.
AUTHORING_LABELS = ('N101', 'N102', 'N103', 'N104', 'S101', 'S102', 'S103', 'D01', 'D02',
                    'E103', 'E104', 'E105', 'H102', 'H103', 'I102', 'I103')
# The caption names a representative sample so the warning is concrete.
NAMED_IN_NOTE = ('N101', 'S101', 'D01', 'E104', 'H103', 'I102')

REWRITTEN_SOURCES = ('network/proxy.csv', 'network/dns.csv', 'identity/auth.csv',
                     'server/access.csv', 'endpoint/events.csv')

# A status code, a byte count and an address describe a request. The map may
# discuss receipt, identity and intent, but only to deny them. Any clause naming
# an attribution, a motive or a sponsor, or pairing a person with a receipt verb,
# has to carry a negation; anything that could only ever be an assertion is
# rejected outright.
NEGATED_NOUNS = re.compile(r'\b(attribution|motive|sponsor|adversary)\b', re.I)
PERSON = r'(?:a person|a human|someone|an individual|an operator|an attacker|who)'
RECEIPT = r'(?:received|receives|read|reading|opened|understood|intended)'
PERSON_RECEIPT = re.compile(
    r'\b' + PERSON + r'\b[^.;!?]{0,80}?\b' + RECEIPT + r'\b'
    r'|\b' + RECEIPT + r'\b[^.;!?]{0,40}?\b' + PERSON + r'\b', re.I)
NEGATION = re.compile(r'\b(not|no|none|nothing|neither|never|cannot|absent|unattributed)\b', re.I)
CLAIM_PATTERNS = (r'\b(establishes|confirms|proves|demonstrates)\s+(that\s+)?intent\b',
                  r'\bintent is established\b', r'\bmotive is established\b',
                  r'\battributed to\b', r'\bthe attacker\b', r'\bthe operator\b',
                  r'\bconfirmed receipt\b', r'\bwraith\b', r'\bshadow network\b')

RECEIVERS = ('fetch(', 'xmlhttprequest', 'importscripts', 'sendbeacon', 'websocket',
             'eventsource', '<link', '<img', '<iframe', '<embed', '<object', '<audio',
             '<video', '<source', '@import', 'url(', 'srcset', 'ping=', 'formaction')
ATTRIBUTES = re.compile(r'\b(src|href|srcset|action|poster|data|formaction|srcdoc)\s*=', re.I)
SCHEMES = re.compile(r'\b[a-z][a-z0-9+.-]*://', re.I)
TAG = re.compile(r'<[^>]*>')


BLOCK_END = re.compile(r'</(?:li|p|h[1-6]|div|article|footer|section|main|body|html|title|dt|dd|ul|ol|table|tr)>|<br\s*/?>', re.I)
STYLE_OR_SCRIPT = re.compile(r'<(style|script)\b[^>]*>.*?</\1>', re.I | re.S)


def text_of(document):
    """Visible text with entities resolved, so prose is compared as it reads.

    Block boundaries become newlines and the inline style and script are dropped,
    so a bullet and the paragraph after it are not mistaken for one clause.
    """
    return html.unescape(TAG.sub(' ', BLOCK_END.sub('\n', STYLE_OR_SCRIPT.sub('\n', document))))


def clauses(text):
    return [part.strip() for part in re.split(r'[.;!?]\s+|\n', text) if part.strip()]


class FixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = build()
        cls.rendered = render(cls.document)
        cls.text = text_of(cls.rendered)

    def test_fixture_is_versioned_and_declares_its_identity(self):
        self.assertEqual(self.document['schema'], SCHEMA)
        self.assertEqual(self.document['map'], MAP_ID)
        self.assertEqual(FIXTURE.name, 't01-network-map-v1.json')
        self.assertEqual(self.document['unlocks_after'], UNLOCKS_AFTER)
        self.assertIn(self.document['status'], ('proposed', 'approved'))

    def test_unknown_schema_or_identity_is_rejected(self):
        for broken in (dict(self.document, schema=2), dict(self.document, schema='v1'),
                       dict(self.document, map='something-else')):
            with self.subTest(broken=broken.get('schema', broken.get('map'))):
                with self.assertRaises(MapError):
                    parse(broken)

    def test_missing_fixture_is_reported_by_path(self):
        with self.assertRaisesRegex(MapError, 'not found'):
            load(ROOT / 'assets/no-such-map.json')

    def test_every_node_kind_has_a_legend_entry(self):
        legend = [entry['kind'] for entry in self.document['legend']]
        self.assertEqual(sorted(legend), sorted(NODE_KINDS))
        for entry in self.document['legend']:
            self.assertTrue(entry['shape'].strip())
            self.assertTrue(entry['meaning'].strip())
        for node in self.document['nodes']:
            self.assertIn(node['kind'], NODE_KINDS)

    def test_every_edge_endpoint_is_a_declared_node(self):
        nodes = {node['id'] for node in self.document['nodes']}
        for edge in self.document['edges']:
            for end in ('source', 'target'):
                self.assertIn(edge[end], nodes, '%s %s is not a node' % (edge['id'], end))

    def test_every_edge_is_directed_and_carries_its_transfer_metadata(self):
        self.assertTrue(self.document['edges'])
        for edge in self.document['edges']:
            with self.subTest(edge=edge['id']):
                self.assertNotEqual(edge['source'], edge['target'])
                self.assertTrue(edge['method'].strip())
                self.assertRegex(edge['time_utc'], r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$')
                for field in ('status', 'body_bytes', 'request', 'path'):
                    self.assertIn(field, edge)

    def test_every_edge_is_observed_or_inferred_and_both_exist(self):
        tags = {edge['confidence'] for edge in self.document['edges']}
        self.assertEqual(tags, set(CONFIDENCE))
        for edge in self.document['edges']:
            with self.subTest(edge=edge['id']):
                self.assertIn(edge['confidence'], CONFIDENCE)
                self.assertTrue(edge['basis'].strip())
                self.assertTrue(edge['caveat'].strip())
                if edge['confidence'] == 'inferred':
                    self.assertTrue(edge['path'], 'an inferred edge must name what it joins')

    def test_every_edge_cites_evidence_that_is_in_the_published_set(self):
        for edge in self.document['edges']:
            self.assertTrue(edge['evidence'], '%s cites nothing' % edge['id'])
            for path in edge['evidence']:
                with self.subTest(edge=edge['id'], path=path):
                    self.assertTrue(path.startswith('/evidence/'))
                    self.assertIn(path.removeprefix('/evidence/'), PUBLISHED)

    def test_every_node_carries_observed_or_inferred_provenance(self):
        for node in self.document['nodes']:
            with self.subTest(node=node['id']):
                self.assertIn(node['provenance']['confidence'], CONFIDENCE)
                self.assertTrue(node['provenance']['basis'].strip())
                for path in node['provenance']['evidence']:
                    self.assertIn(path.removeprefix('/evidence/'), PUBLISHED)

    def test_dangling_edge_or_node_is_rejected(self):
        broken = json.loads(json.dumps(self.document))
        broken['edges'][0]['target'] = 'nowhere'
        with self.assertRaisesRegex(MapError, 'is not a node'):
            validate(broken)
        broken = json.loads(json.dumps(self.document))
        broken['edges'][0]['confidence'] = 'probably'
        with self.assertRaisesRegex(MapError, 'observed or inferred'):
            validate(broken)
        broken = json.loads(json.dumps(self.document))
        broken['edges'][0]['evidence'] = ['/evidence/network/not-published.csv']
        with self.assertRaisesRegex(MapError, 'not a declared evidence source'):
            validate(broken)

    def test_a_map_with_only_one_confidence_is_rejected(self):
        broken = json.loads(json.dumps(self.document))
        broken['edges'] = [edge for edge in broken['edges'] if edge['confidence'] == 'observed']
        with self.assertRaisesRegex(MapError, 'observed and an inferred edge'):
            validate(broken)

    def test_keys_are_request_path_and_time_never_a_rewritten_id(self):
        self.assertEqual(tuple(self.document['key_fields']), KEY_FIELDS)
        # The caption has to explain the rewrite, so it may name the labels it warns
        # about. What it must never do is use one as a value the graph joins on.
        note = self.document['key_fields_note']
        self.assertIn('rewrites the id column', note)
        for label in NAMED_IN_NOTE:
            with self.subTest(label=label):
                self.assertIn(label, note)
        joinable = []
        for edge in self.document['edges']:
            joinable += [str(edge.get(field) or '') for field in
                         ('id', 'source', 'target', 'method', 'path', 'status', 'request', 'time_utc')]
        for node in self.document['nodes']:
            joinable += [str(node.get(field) or '') for field in ('id', 'label', 'sublabel', 'kind')]
        joined = ' '.join(joinable)
        for label in AUTHORING_LABELS:
            with self.subTest(label=label, field='joined value'):
                self.assertNotIn(label, joined)
        for edge in self.document['edges']:
            for banned in ('record_id', 'source_id', 'source_record', 'id_column'):
                self.assertNotIn(banned, edge)
            if edge.get('request'):
                self.assertNotRegex(str(edge['request']), r'^[0-9a-f]{12}$')

    def test_the_map_never_repeats_a_scenario_the_contract_owns(self):
        # The map is a view of evidence, not a retelling. Narrative stays in the
        # approved contract, and this map must not grow its own adversary framing.
        lowered = self.text.lower()
        for claim in ('wraith', 'shadow network', 'the adversary', 'the attackers'):
            self.assertNotIn(claim, lowered)


class OfflineRenderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = build()
        cls.rendered = render(cls.document)
        cls.text = text_of(cls.rendered)

    def test_rendering_is_deterministic_and_the_file_matches_the_document(self):
        self.assertEqual(render(build()), self.rendered)
        again = json.loads(FIXTURE.read_text(encoding='utf-8'))
        self.assertEqual(render(again), self.rendered)
        with tempfile.TemporaryDirectory() as tmp:
            path = write(Path(tmp) / 'nested' / 'map.html', self.document)
            self.assertEqual(path.read_text(encoding='utf-8'), self.rendered)

    def test_document_is_fully_self_contained(self):
        self.assertNotIn('http://', self.rendered)
        self.assertNotIn('https://', self.rendered)
        self.assertIsNone(SCHEMES.search(self.rendered), 'no scheme reference of any kind')
        for receiver in RECEIVERS:
            with self.subTest(receiver=receiver):
                self.assertNotIn(receiver, self.rendered.lower())
        for banned in ('<link', '<img', '@font-face', 'srcset', '<iframe'):
            self.assertNotIn(banned, self.rendered.lower())
        self.assertIn('<style>', self.rendered)
        self.assertIn('<script>', self.rendered)
        self.assertNotIn('</style></head>\n<link', self.rendered)

    def test_external_address_cannot_trigger_a_request(self):
        address = self.document['external_address']['address']
        self.assertEqual(address, '198.51.100.77')
        self.assertEqual(self.rendered.count(address), self.text.count(address),
                         'the address may only appear as text, never inside a tag')
        for match in ATTRIBUTES.finditer(self.rendered):
            value = self.rendered[match.end():self.rendered.find('>', match.end()) + 1]
            self.assertNotIn(address, value, 'attribute %s points at the address' % match.group())
        self.assertNotIn('//' + address, self.rendered)
        self.assertIsNone(SCHEMES.search(self.rendered.replace(address, '')))
        self.assertEqual(offline_report(self.document), [])

    def test_external_address_is_declared_as_documentation_space(self):
        external = self.document['external_address']
        self.assertEqual(external['block'], '198.51.100.0/24')
        self.assertIn('RFC 5737', external['registry'])
        self.assertIn('TEST-NET-2', external['registry'])
        self.assertEqual(external['live_reference'], 'none')
        self.assertTrue(external['reason'].strip())
        self.assertTrue(external['rule'].strip())
        for field in ('registry', 'reason', 'rule', 'address'):
            with self.subTest(field=field):
                self.assertIn(str(external[field]), self.text)

    def test_a_planted_reference_is_refused_rather_than_rendered(self):
        broken = json.loads(json.dumps(self.document))
        broken['external_address']['rule'] = 'See http://198.51.100.77/ for the operator.'
        with self.assertRaisesRegex(MapError, 'not offline-safe'):
            write(Path(tempfile.mkdtemp()) / 'map.html', broken)

    def test_a_planted_retrieval_construct_is_refused(self):
        broken = json.loads(json.dumps(self.document))
        broken['companion'] = 'Also fetch(/silent-ridge/other) for more.'
        self.assertTrue(offline_report(broken))

    def test_graph_renders_every_node_and_edge_with_a_legend_shape(self):
        for node in self.document['nodes']:
            with self.subTest(node=node['id']):
                self.assertIn('data-node="%s"' % node['id'], self.rendered)
        for edge in self.document['edges']:
            with self.subTest(edge=edge['id']):
                self.assertIn('data-edge="%s"' % edge['id'], self.rendered)
                self.assertIn('id="rec-%s"' % edge['id'], self.rendered)
        self.assertEqual(self.rendered.count('class="edge '),
                         len(self.document['edges']))
        for kind in NODE_KINDS:
            self.assertIn('class="legend-%s"' % kind, self.rendered)
        shapes = set(re.findall(r'<(rect|polygon|ellipse) ', self.rendered))
        self.assertEqual(shapes, {'rect', 'polygon', 'ellipse'},
                         'each legend kind needs its own outline')

    def test_selecting_an_edge_reveals_its_record_and_source_path(self):
        for edge in self.document['edges']:
            with self.subTest(edge=edge['id']):
                self.assertIn('aria-controls="rec-%s"' % edge['id'], self.rendered)
                self.assertIn('addEventListener', self.rendered)
                for path in edge['evidence']:
                    self.assertIn(path, self.text, '%s must show %s' % (edge['id'], path))
        upload = next(edge for edge in self.document['edges'] if edge['request'] == 'req-72'
                      and edge['method'] == 'POST')
        self.assertIn('/evidence/network/sensor.pcap', upload['evidence'])

    def test_every_arrowhead_lands_on_its_target_node(self):
        # The edge lines are offset sideways so overlapping flows stay legible,
        # which means the box crossing has to be solved on the offset line. A
        # regression here points an arrow into empty space.
        nodes = {node['id']: node for node in self.document['nodes']}
        for index, edge in enumerate(self.document['edges']):
            target = nodes[edge['target']]
            tip_x, tip_y = _edge_geometry(edge, nodes, index)[2][0]
            with self.subTest(edge=edge['id']):
                self.assertLessEqual(abs(tip_x - target['x']), _width(target) / 2.0 + 0.5)
                self.assertLessEqual(abs(tip_y - target['y']), NODE_HEIGHT / 2.0 + 0.5)
                for value in (tip_x, tip_y):
                    self.assertTrue(math.isfinite(value))
                    self.assertTrue(0 <= value <= VIEW_WIDTH)

    def test_observed_and_inferred_are_visibly_distinct(self):
        self.assertIn('.graph .edge.inferred line', self.rendered)
        self.assertIn('stroke-dasharray', self.rendered)
        for edge in self.document['edges']:
            self.assertIn('class="edge %s"' % edge['confidence'], self.rendered)
            self.assertIn('<span class="tag %s">' % edge['confidence'], self.rendered)
        self.assertIn('Solid lines are observed', self.text)
        self.assertIn('dashed lines are inferred', self.text)

    def test_map_does_not_claim_receipt_intent_or_attribution(self):
        disclaimer = self.document['disclaimer']
        for field in ('receipt', 'identity', 'intent', 'inference', 'scope'):
            with self.subTest(field=field):
                self.assertTrue(disclaimer[field].strip())
                self.assertIn(disclaimer[field], self.text)
        for claim in CLAIM_PATTERNS:
            with self.subTest(claim=claim):
                self.assertIsNone(re.search(claim, self.text, re.I))
        asserted = [clause for clause in clauses(self.text)
                    if (NEGATED_NOUNS.search(clause) or PERSON_RECEIPT.search(clause))
                    and not NEGATION.search(clause)]
        self.assertEqual(asserted, [], 'the map asserts rather than denies: %r' % asserted)
        # The disclaimer has to say the three things out loud, not merely imply them.
        self.assertIn('do not establish that a person received', disclaimer['receipt'])
        self.assertIn('identifies a person', disclaimer['identity'])
        self.assertIn('do not establish motive', disclaimer['intent'])
        for edge in self.document['edges']:
            with self.subTest(edge=edge['id']):
                self.assertIn('What it does not show.', self.rendered)

    def test_sensor_wrapper_addresses_are_not_treated_as_endpoints(self):
        collector = next(node for node in self.document['nodes'] if node['id'] == 'collector')
        self.assertIn('10.26.20.30', collector['sublabel'])
        self.assertIn('collection transport', collector['detail'])
        self.assertIn('are the incident endpoints', collector['detail'])
        for edge in self.document['edges']:
            self.assertNotIn('10.26.20.31', (edge.get('path') or ''))

    def test_corrected_endpoint_time_is_applied_exactly_once(self):
        connect = next(edge for edge in self.document['edges']
                       if edge['method'] == 'NETWORK_CONNECT')
        self.assertEqual(connect['time_utc'], '2026-10-15T09:06:00Z')
        self.assertIn('120-second fast offset', connect['basis'])
        self.assertIn('09:08:00Z', connect['basis'])
        self.assertIn('no request identifier', connect['caveat'])


class PublishedEvidenceTests(unittest.TestCase):
    """Join the map's keys against a real prepared release, offline."""

    @classmethod
    def setUpClass(cls):
        from expanded.prepare import build as prepare
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = prepare(Path(cls.tmp.name) / 'release')
        cls.public = cls.root / 'initial'
        cls.document = build()
        cls.tables = {}
        for path in sorted(cls.public.rglob('*.csv')):
            with path.open(newline='', encoding='utf-8-sig') as source:
                cls.tables[path.relative_to(cls.public).as_posix()] = list(csv.DictReader(source))
        cls.jsonl = {}
        for path in sorted(cls.public.rglob('*.jsonl')):
            cls.jsonl[path.relative_to(cls.public).as_posix()] = [
                json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line]

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_published_id_column_is_a_rewritten_hash(self):
        # The premise of the whole keying rule. If this ever stops holding, the
        # map's refusal to key on id is protecting against nothing.
        for name in REWRITTEN_SOURCES:
            rows = self.tables[name]
            self.assertTrue(rows, name)
            for row in rows:
                self.assertRegex(row['id'], r'^[0-9a-f]{12}$', '%s/%s' % (name, row['id']))
        for row in self.jsonl['hunting/siem.jsonl']:
            self.assertRegex(row['id'], r'^[0-9a-f]{12}$')
        published_ids = {row['id'] for name in REWRITTEN_SOURCES for row in self.tables[name]}
        self.assertGreater(len(published_ids), 50)
        for edge in self.document['edges']:
            for value in (edge.get('request'), edge.get('path')):
                self.assertNotIn(str(value), published_ids)

    def test_every_request_identifier_resolves_in_the_published_evidence(self):
        for edge in self.document['edges']:
            if not edge.get('request'):
                continue
            with self.subTest(edge=edge['id'], request=edge['request']):
                rows = [row for rows in self.tables.values() for row in rows
                        if row.get('request') == edge['request']]
                self.assertTrue(rows, 'no published row carries %s' % edge['request'])
                self.assertIn(edge['time_utc'], {row['time'] for row in rows})
                # A cited source only has to carry the request if it has the column.
                for path in edge['evidence']:
                    name = path.removeprefix('/evidence/')
                    cited = [row for row in self.tables.get(name, []) if 'request' in row]
                    if cited:
                        self.assertIn(edge['request'], {row['request'] for row in cited})

    def test_proxy_edges_match_a_published_proxy_row_field_for_field(self):
        proxies = {row['request']: row for row in self.tables['network/proxy.csv']}
        for edge in self.document['edges']:
            if 'network/proxy.csv' not in [p.removeprefix('/evidence/') for p in edge['evidence']]:
                continue
            if not edge.get('request'):
                continue
            with self.subTest(edge=edge['id']):
                row = proxies[edge['request']]
                self.assertEqual(row['time'], edge['time_utc'])
                self.assertEqual(row['status'], str(edge['status']))
                self.assertEqual(row['body_bytes'], str(edge['body_bytes']))
                if row['path'] != edge['path']:
                    # server/access.csv records the object rather than a URL path.
                    self.assertIn('server/access.csv',
                                  [p.removeprefix('/evidence/') for p in edge['evidence']])
                self.assertEqual(row['method'], edge['method'] if edge['method'] in ('GET', 'POST') else row['method'])

    def test_dns_edge_matches_the_published_resolution_row(self):
        edge = next(item for item in self.document['edges'] if item['method'] == 'DNS')
        row = next(row for row in self.tables['network/dns.csv'] if row['query'] == edge['path'])
        self.assertEqual(row['time'], edge['time_utc'])
        self.assertEqual(row['answer'], self.document['external_address']['address'])
        self.assertEqual(str(row['ttl']), str(edge['ttl']))
        self.assertIn('no status code', edge['caveat'])

    def test_identity_edges_match_the_published_identity_rows(self):
        auth = self.tables['identity/auth.csv']
        refresh = next(edge for edge in self.document['edges'] if edge['method'] == 'SESSION_REFRESH')
        failure = next(edge for edge in self.document['edges'] if edge['method'] == 'PASSWORD_LOGIN')
        row = next(item for item in auth if item['time'] == refresh['time_utc'])
        self.assertEqual(row['action'], 'session_refresh')
        self.assertEqual(row['result'], refresh['status'])
        self.assertEqual(row['mfa'], refresh['mfa'])
        self.assertEqual(row['session'], refresh['path'])
        row = next(item for item in auth if item['time'] == failure['time_utc'])
        self.assertEqual(row['result'], failure['status'])
        self.assertEqual(row['mfa'], failure['mfa'])

    def test_the_denial_is_drawn_as_a_denial(self):
        denied = next(edge for edge in self.document['edges'] if edge['status'] == 403)
        self.assertEqual(denied['body_bytes'], 0)
        self.assertEqual(denied['confidence'], 'observed')
        rows = [row for row in self.tables['server/access.csv'] if row['request'] == denied['request']]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['status'], '403')
        self.assertEqual(rows[0]['bytes'], '0')
        self.assertEqual(rows[0]['object'], 'roster-v2')

    def test_inferred_edges_are_the_ones_without_a_single_stating_record(self):
        inferred = {edge['id']: edge for edge in self.document['edges']
                    if edge['confidence'] == 'inferred'}
        self.assertEqual(sorted(inferred), ['e-ack-correlation', 'e-body-identity'])
        for edge in inferred.values():
            with self.subTest(edge=edge['id']):
                self.assertIn('no single record', edge['basis'].lower())
        self.assertIn('Equal size is not identity of content', inferred['e-body-identity']['caveat'])
        self.assertIn('carries its own request identifier', inferred['e-ack-correlation']['caveat'])

    def test_no_edge_claims_a_payload_identity_the_evidence_does_not_carry(self):
        # The released DLP body arrives with T19. Before that, the map may only
        # assert the byte count, and the catalogue hash is the catalogue's.
        for edge in self.document['edges']:
            if edge['confidence'] == 'inferred' and edge['id'] == 'e-body-identity':
                self.assertIn('Equal size is not identity of content', edge['caveat'])
                continue
            self.assertNotIn('sha256', json.dumps(edge).lower())

    def test_catalog_hash_never_appears_in_the_map(self):
        catalog = self.tables['server/catalog.csv']
        plan = next(row for row in catalog if row['object'] == 'plan-v3')
        self.assertEqual(plan['size'], '137')
        self.assertEqual(len(plan['sha256']), 64)
        self.assertNotIn(plan['sha256'], json.dumps(self.document))
        self.assertNotIn(plan['sha256'], self.rendered if hasattr(self, 'rendered') else render(self.document))


class PlacementTests(unittest.TestCase):
    """The map is a T01 follow-up and stays behind the ticket it follows."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        from ridge.state import State
        self.state = State(Path(self.tmp.name) / 'state.sqlite', retry_delay=0)
        teams = [dict(id='0', iris='10', ctfd='20', name='Team 0')]
        ticket = dict(id=UNLOCKS_AFTER, title='Trace document traffic', subject='Wireshark',
                      requires=[], questions=[dict(id='T01-Q%d' % i, prompt='Question',
                                                    answer='answer',
                                                    finding=dict(text='Finding', evidence=['ref'],
                                                                 limitation='Scope only'))
                                               for i in range(1, 5)])
        self.state.initialize(teams, [ticket])
        self.state.provision('controller')
        self.sink = lambda kind, key, payload, context: 1
        while self.state.sync_once(self.sink):
            pass
        self.state.mode('controller', 'running')

    def tearDown(self):
        self.tmp.cleanup()

    def test_map_is_locked_until_every_t01_answer_is_scored(self):
        self.assertFalse(self.state.ticket_complete(UNLOCKS_AFTER))
        self.state.claim('0', UNLOCKS_AFTER)
        for index in range(1, 4):
            self.assertTrue(self.state.answer('0', 'T01-Q%d' % index, 'answer')['correct'])
            self.assertFalse(self.state.ticket_complete(UNLOCKS_AFTER))
        self.assertTrue(self.state.answer('0', 'T01-Q4', 'answer')['correct'])
        self.assertTrue(self.state.ticket_complete(UNLOCKS_AFTER))

    def test_question_page_offers_the_map_only_from_the_completion_state(self):
        active = network_map_link({'tickets': [dict(id=UNLOCKS_AFTER, status='active')]})
        self.assertIsNone(active)
        self.assertIsNone(network_map_link({'tickets': []}))
        self.assertIsNone(network_map_link(
            {'tickets': [dict(id='T02', status='complete')]}))
        unlocked = network_map_link({'tickets': [dict(id=UNLOCKS_AFTER, status='complete')]})
        self.assertEqual(unlocked['path'], '/silent-ridge/network-map')
        for field in ('headline', 'brief', 'action'):
            self.assertTrue(unlocked[field].strip())

    def test_the_link_text_never_names_the_destination(self):
        from expanded.author import build as author
        from ridge.scenario_contract import distinctive_answers
        answers = distinctive_answers(author())
        self.assertGreaterEqual(sum(len(v) for v in answers.values()), 50)
        unlocked = network_map_link({'tickets': [dict(id=UNLOCKS_AFTER, status='complete')]})
        body = ' '.join(unlocked[key] for key in ('headline', 'brief', 'action')).lower()
        for answer in sorted(answers):
            with self.subTest(answer=answer):
                self.assertNotIn(answer, body)

    def test_the_map_is_not_a_released_evidence_file(self):
        from ridge.scenario import RELEASE_FILES
        for names in RELEASE_FILES.values():
            for name in names:
                self.assertFalse(name.endswith(('.html', '.htm')), name)
        # T01 unlocks at run start, so any release attached to it would be published
        # before the ticket that scores 198.51.100.77 was answered.
        self.assertEqual(RELEASE_FILES.get(UNLOCKS_AFTER, []), [])

    def test_the_map_adds_no_question_and_preserves_t01_scoring(self):
        from expanded.author import build as author
        from ridge.question_matrix import EXPECTED_QUESTIONS
        tickets = author()
        self.assertEqual(sum(len(t['questions']) for t in tickets), EXPECTED_QUESTIONS)
        t01 = next(ticket for ticket in tickets if ticket['id'] == UNLOCKS_AFTER)
        self.assertEqual([question['answer'] for question in t01['questions']],
                         ['WS-17', 'req-71', 'req-72', '198.51.100.77'])
        self.assertEqual(t01['release_files'], [])
        self.assertEqual(len(t01['questions']), 4)
        self.assertNotIn(UNLOCKS_AFTER, [ticket['id'] for ticket in tickets
                                         if any(q['evidence'].endswith('network-map')
                                                for q in ticket['questions'])])

    @unittest.skipUnless(jinja2, 'jinja2 is a deployment dependency')
    def test_the_question_page_carries_the_link_only_on_the_ctfd_lane(self):
        from ridge.web import PAGE
        page = jinja2.Environment().from_string(PAGE)
        base = dict(snapshot={'team': '0', 'mode': 'running', 'pending': 0, 'elapsed_seconds': 0,
                              'announcements': [], 'tickets': []},
                    questions=[], iris='i', ctfd='c', csrf='n', message='', case='1')
        queue = page.render(lane='iris', **base)
        self.assertNotIn('t01-network-map', queue)
        self.assertNotIn('/silent-ridge/network-map', queue)
        # An unlocked map must not appear on the queue lane even once T01 is closed.
        closed = dict(base, snapshot=dict(base['snapshot'],
                                          tickets=[dict(id=UNLOCKS_AFTER, status='complete')]))
        self.assertNotIn('/silent-ridge/network-map', page.render(lane='iris', **closed))
        unlocked = network_map_link(closed['snapshot'])
        questions = page.render(lane='ctfd', network_map=unlocked, **closed)
        self.assertIn('t01-network-map', questions)
        self.assertIn('href="%s"' % NETWORK_MAP, questions)
        self.assertIn('Open the T01 network map', questions)


if __name__ == '__main__':
    unittest.main()
