"""The T01 exfiltration network map (issue 66).

An additional analytical view, not a second source of truth. The published
evidence and the canonical scenario document stay authoritative; where this map
and a record disagree, the record is right. It replaces no T01 question, adds
none, and scores nothing.

Two properties make the map safe to hand a participant, and both are enforced
here rather than trusted to review.

*Observation before inference.* Every edge carries a ``confidence`` of
``observed`` or ``inferred``. An observed edge is stated in full by one published
record. An inferred edge joins two or more records and says so in its own
``basis`` and ``caveat``. Nothing on the map establishes human receipt, intent
or attribution, and ``disclaimer`` states why in the participant's own words: a
status code, a byte count and an address describe a request, not a reader.

*No live reference to the external address.* ``198.51.100.77`` is RFC 5737
TEST-NET-2 documentation space. It is rendered as text so the finding can be
quoted, and :func:`offline_report` refuses to produce a document that could
cause a browser to contact it, or that references any external resource at all.
The document is a single file: inline CSS, inline script, no fonts, no images,
no network of any kind, so it opens from ``file:///`` in the desktop's Firefox.

Publication is deliberately *not* a released evidence file.
``ridge.transport`` publishes a ticket's release files when the ticket unlocks,
and T01 unlocks at run start, so a released map would hand a participant all
four T01 answers before the ticket was answered. Instead ``ridge.web`` links
the map from the T01 completion state, the controller checks the same condition
before serving it, and ``assets/t01-network-map-v1.json`` is the only source of
the data.

Records are joined on ``request``, ``path`` and ``time_utc`` only.
``expanded/prepare.py`` rewrites the ``id`` column of every published CSV to a
twelve-character hash, so the authoring labels (N101, S101, D01 and so on) are
not in the participant evidence and must never appear here as a join key.
"""
import html
import json
import re
from pathlib import Path

SCHEMA = 1
MAP_ID = 'silent-ridge-t01-network-map'
FIXTURE = Path(__file__).resolve().parents[1] / 'assets/t01-network-map-v1.json'
UNLOCKS_AFTER = 'T01'

NODE_KINDS = ('host', 'service', 'external', 'object', 'evidence-source')
CONFIDENCE = ('observed', 'inferred')
KEY_FIELDS = ('request', 'path', 'time_utc')
NODE_FIELDS = ('id', 'kind', 'label', 'x', 'y', 'detail', 'provenance')
EDGE_FIELDS = ('id', 'source', 'target') + KEY_FIELDS + ('evidence', 'confidence', 'basis', 'caveat')
LEGEND_FIELDS = ('kind', 'label', 'shape', 'meaning')
DISCLAIMER_FIELDS = ('headline', 'receipt', 'identity', 'intent', 'inference', 'scope')

VIEWBOX = (0, 0, 1320, 720)
NODE_WIDTH = 210
EVIDENCE_WIDTH = 220
NODE_HEIGHT = 56
ARROW = 15

# A document failing any of these is refused rather than shipped: the map must
# resolve nothing at all, and must not be able to reach the address it draws.
SCHEMES = ('http://', 'https://', 'ftp://', 'ws://', 'wss://', 'gopher://', 'telnet://', 'data:')
RETRIEVERS = ('fetch(', 'XMLHttpRequest', 'importScripts', 'sendBeacon', 'WebSocket',
              'EventSource', '<link', '<img', '<iframe', '<embed', '<object', '<audio',
              '<video', '<source', '@import', 'url(', 'srcset', 'ping=', 'formaction')
TAG = re.compile(r'<[^>]*>')


class MapError(ValueError):
    """Raised when the network map is missing, malformed or unsafe to render."""


def _escape(value):
    return html.escape(str(value), quote=True)


def _text(record, field):
    if not str(record.get(field, '')).strip():
        raise MapError('%s.%s: required text is empty' % (record.get('id', '?'), field))
    return str(record[field])


def parse(document):
    """Schema-check an already-decoded map document."""
    if document.get('schema') != SCHEMA:
        raise MapError('Unknown network map schema: ' + repr(document.get('schema')))
    if document.get('map') != MAP_ID:
        raise MapError('Unknown network map id: ' + repr(document.get('map')))
    return document


def load(path=None):
    """Read and schema-check the map fixture."""
    source = Path(path) if path else FIXTURE
    if not source.is_file():
        raise MapError('network map not found: ' + str(source))
    return parse(json.loads(source.read_text(encoding='utf-8')))


def validate(document):
    """Structural, provenance and reference checks over the whole map."""
    if document.get('unlocks_after') != UNLOCKS_AFTER:
        raise MapError('unlocks_after: the map is a T01 follow-up')
    if tuple(document.get('key_fields', ())) != KEY_FIELDS:
        raise MapError('key_fields: records are joined on %s' % ', '.join(KEY_FIELDS))
    for field in ('authority', 'caption', 'unlock_note', 'key_fields_note', 'companion'):
        _text(document, field)
    for field in ('headline', 'brief', 'action'):
        _text(dict(document.get('link', {}), id='link'), field)
    legend = {entry.get('kind'): entry for entry in document.get('legend', [])}
    if sorted(legend) != sorted(NODE_KINDS):
        raise MapError('legend: every node kind needs exactly one legend entry')
    for kind, entry in sorted(legend.items()):
        for field in LEGEND_FIELDS:
            _text(dict(entry, id='legend.' + kind), field)
    nodes = {}
    for node in document.get('nodes', []):
        for field in NODE_FIELDS:
            if field not in node:
                raise MapError('nodes.%s: missing %s' % (node.get('id'), field))
        if node['id'] in nodes:
            raise MapError('nodes.%s: duplicate node' % node['id'])
        if node['kind'] not in NODE_KINDS:
            raise MapError('nodes.%s: unknown kind %r' % (node['id'], node['kind']))
        _text(node, 'label')
        _text(node, 'detail')
        if not isinstance(node['x'], int) or not isinstance(node['y'], int):
            raise MapError('nodes.%s: x and y must be integers' % node['id'])
        if not 0 <= node['x'] <= VIEWBOX[2] or not 0 <= node['y'] <= VIEWBOX[3]:
            raise MapError('nodes.%s: position is outside the viewBox' % node['id'])
        provenance = node['provenance']
        if provenance.get('confidence') not in CONFIDENCE:
            raise MapError('nodes.%s: provenance must be observed or inferred' % node['id'])
        if not str(provenance.get('basis', '')).strip():
            raise MapError('nodes.%s: provenance needs a basis' % node['id'])
        for path in provenance.get('evidence', []):
            _check_evidence(path, node['id'])
        nodes[node['id']] = node
    if not document.get('edges'):
        raise MapError('edges: the map needs at least one edge')
    seen = set()
    for edge in document['edges']:
        for field in EDGE_FIELDS:
            if field not in edge:
                raise MapError('edges.%s: missing %s' % (edge.get('id'), field))
        if edge['id'] in seen:
            raise MapError('edges.%s: duplicate edge' % edge['id'])
        seen.add(edge['id'])
        for end in ('source', 'target'):
            if edge[end] not in nodes:
                raise MapError('edges.%s: %s %r is not a node' % (edge['id'], end, edge[end]))
        if edge['confidence'] not in CONFIDENCE:
            raise MapError('edges.%s: confidence must be observed or inferred' % edge['id'])
        if not str(edge['method']).strip():
            raise MapError('edges.%s: method is required' % edge['id'])
        if not str(edge['basis']).strip() or not str(edge['caveat']).strip():
            raise MapError('edges.%s: basis and caveat are required' % edge['id'])
        if edge['confidence'] == 'inferred' and not str(edge['path'] or '').strip():
            raise MapError('edges.%s: an inferred edge must name what it joins' % edge['id'])
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z', str(edge['time_utc'])):
            raise MapError('edges.%s: time_utc must be normalized UTC' % edge['id'])
        if not edge['evidence']:
            raise MapError('edges.%s: an edge must cite its supporting record' % edge['id'])
        for path in edge['evidence']:
            _check_evidence(path, edge['id'])
        for banned in ('record_id', 'source_id', 'source_record', 'id_column'):
            if banned in edge:
                raise MapError('edges.%s: %s is a rewritten column and cannot be a key'
                               % (edge['id'], banned))
        if _rewritten(edge.get('request')):
            raise MapError('edges.%s: request looks like a rewritten id column' % edge['id'])
    tags = {edge['confidence'] for edge in document['edges']}
    if tags != set(CONFIDENCE):
        raise MapError('edges: both an observed and an inferred edge are required')
    cited = {path for edge in document['edges'] for path in edge['evidence']}
    for node in document['nodes']:
        if node['kind'] != 'evidence-source':
            continue
        node['cited'] = sorted(cited & set(node['provenance'].get('evidence', [])))
        if not node['cited']:
            raise MapError('nodes.%s: no edge cites this evidence source' % node['id'])
    declared = {path for node in nodes.values() if node['kind'] == 'evidence-source'
                for path in node['provenance'].get('evidence', [])}
    for edge in document['edges']:
        for path in edge['evidence']:
            if path not in declared:
                raise MapError('edges.%s: %s is not a declared evidence source' % (edge['id'], path))
    external = document.get('external_address', {})
    if not re.fullmatch(r'198\.51\.100\.\d{1,3}', str(external.get('address', ''))):
        raise MapError('external_address: expected RFC 5737 documentation space')
    for field in ('block', 'registry', 'reason', 'rule'):
        if not str(external.get(field, '')).strip():
            raise MapError('external_address.%s is required' % field)
    if external.get('live_reference') != 'none':
        raise MapError('external_address: the map must make no live reference')
    for field in DISCLAIMER_FIELDS:
        _text(dict(document.get('disclaimer', {}), id='disclaimer'), field)
    return len(nodes), len(document['edges'])


def _rewritten(value):
    """The published id column is a twelve-character hash prefix, not a request id."""
    return bool(re.fullmatch(r'[0-9a-f]{12}', str(value)))


def _check_evidence(path, owner):
    if not str(path).startswith('/evidence/') or '..' in str(path):
        raise MapError('%s: evidence must be an explicit /evidence path' % owner)


def build(path=None):
    """Load, validate and return the map ready for rendering."""
    document = load(path)
    validate(document)
    return document


def _width(node):
    return EVIDENCE_WIDTH if node['kind'] == 'evidence-source' else NODE_WIDTH


def _polygon(points, attributes=''):
    return '<polygon points="%s" %s/>' % (' '.join('%g,%g' % point for point in points), attributes)


def shape(node, x, y, width, height, attributes=''):
    """A distinct outline per legend kind; nothing here can load an external resource."""
    left, right = x - width / 2.0, x + width / 2.0
    top, bottom = y - height / 2.0, y + height / 2.0
    kind = node.get('kind')
    if kind == 'host':
        return '<rect x="%g" y="%g" width="%g" height="%g" rx="12" ry="12" %s/>' % (
            left, top, width, height, attributes)
    if kind == 'service':
        cut = 18
        return _polygon([(left + cut, top), (right - cut, top), (right, y),
                         (right - cut, bottom), (left + cut, bottom), (left, y)], attributes)
    if kind == 'external':
        cut_x, cut_y = width / 2.0 - 26, height / 2.0 - 10
        return _polygon([(left + cut_x, top), (right - cut_x, top), (right, y - cut_y),
                         (right - cut_x, bottom), (left + cut_x, bottom), (left, y + cut_y),
                         (left, y - cut_y)], attributes)
    if kind == 'object':
        fold = 16
        return _polygon([(left, top), (right - fold, top), (right, top + fold),
                         (right, bottom), (left, bottom)], attributes)
    return '<ellipse cx="%g" cy="%g" rx="%g" ry="%g" %s/>' % (x, y, width / 2.0, height / 2.0, attributes)


def _trim(x1, y1, x2, y2, box):
    """The last point at which the segment touches the target box.

    Endpoints are offset sideways so overlapping flows stay legible, so the box
    crossing has to be solved on the offset line rather than assumed to be the
    centre. Taking the largest crossing at or before the target centre keeps the
    arrowhead on the shape whether the line arrives from outside or leaves it.
    """
    cx, cy, half_width, half_height = box
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        return x2, y2
    scale = None
    for delta, extent, origin, start in ((dx, half_width, cx, x1), (dy, half_height, cy, y1)):
        if delta == 0:
            continue
        side = 1.0 if delta > 0 else -1.0
        crossings = [(origin - side * extent - start) / delta, (origin + side * extent - start) / delta]
        for crossing in crossings:
            if 0 < crossing <= 1 and (scale is None or crossing > scale):
                scale = crossing
    if scale is None:
        return x2, y2
    return x1 + dx * scale, y1 + dy * scale


def _edge_geometry(edge, nodes, index):
    source, target = nodes[edge['source']], nodes[edge['target']]
    dx, dy = target['x'] - source['x'], target['y'] - source['y']
    length = (dx * dx + dy * dy) ** 0.5 or 1.0
    # A fixed per-edge offset keeps overlapping flows legible and stays deterministic.
    offset = ((index % 5) - 2) * 13.0
    x1 = source['x'] - dy / length * offset
    y1 = source['y'] + dx / length * offset
    x2 = target['x'] - dy / length * offset
    y2 = target['y'] + dx / length * offset
    tip_x, tip_y = _trim(x1, y1, x2, y2, (target['x'], target['y'], _width(target) / 2.0,
                                         NODE_HEIGHT / 2.0))
    ux, uy = tip_x - x1, tip_y - y1
    span = (ux * ux + uy * uy) ** 0.5 or 1.0
    ux, uy = ux / span, uy / span
    base_x, base_y = tip_x - ux * ARROW, tip_y - uy * ARROW
    # Arrowheads are drawn as plain polygons rather than SVG markers, so the
    # document contains no url() reference of any kind.
    head = [(tip_x, tip_y), (base_x - uy * 7, base_y + ux * 7), (base_x + uy * 7, base_y - ux * 7)]
    return ((x1, y1), (base_x, base_y), head, (x1 + ux * span * 0.55, y1 + uy * span * 0.55))


def _edge_label(edge):
    stamp = str(edge['time_utc'])[11:19] + 'Z'
    return ' · '.join(part for part in (edge['request'] or edge['method'], stamp) if part)


def _shown(value, empty='<em>not recorded</em>'):
    return empty if value is None or value == '' else _escape(value)


def _facts(pairs):
    return ''.join('<div class="fact"><dt>%s</dt><dd>%s</dd></div>' % (name, value) for name, value in pairs)


def _edge_panel(edge):
    return ('<article class="record" id="rec-%s" hidden>'
            '<h3>%s <span class="tag %s">%s</span></h3>'
            '<dl class="facts">%s</dl>'
            '<p class="basis"><strong>Why this edge is %s.</strong> %s</p>'
            '<p class="caveat"><strong>What it does not show.</strong> %s</p>'
            '<h4>Supporting records</h4><ul class="sources">%s</ul>'
            '<h4>Keyed on</h4><p class="keys">request <code>%s</code> · path <code>%s</code> · '
            'time <code>%s</code></p></article>') % (
        _escape(edge['id']), _escape(_edge_label(edge)), edge['confidence'], edge['confidence'],
        _facts([('UTC', _escape(edge['time_utc'])), ('Method', _escape(edge['method'])),
                ('Path', _shown(edge['path'], '<em>no path in this record</em>')),
                ('Status', _shown(edge['status'])), ('Body bytes', _shown(edge['body_bytes'])),
                ('Request', _shown(edge['request'], '<em>none</em>'))]),
        _escape(edge['confidence']), _escape(edge['basis']), _escape(edge['caveat']),
        ''.join('<li><code>%s</code></li>' % _escape(path) for path in edge['evidence']),
        _escape(edge['request'] or 'none'), _escape(edge['path'] or 'not recorded'),
        _escape(edge['time_utc']))


def _node_panel(node):
    return ('<article class="record" id="node-%s" hidden>'
            '<h3>%s <span class="tag %s">%s</span></h3><p>%s</p>'
            '<p class="basis"><strong>Provenance is %s.</strong> %s</p>'
            '<h4>Supporting records</h4><ul class="sources">%s</ul></article>') % (
        _escape(node['id']), _escape(node['label']), node['kind'], _escape(node['kind']),
        _escape(node['detail']), _escape(node['provenance']['confidence']),
        _escape(node['provenance']['basis']),
        ''.join('<li><code>%s</code></li>' % _escape(path)
                for path in node['provenance'].get('evidence', [])))


def _graph(document):
    nodes = {node['id']: node for node in document['nodes']}
    by_evidence = {path: node['id'] for node in document['nodes']
                   if node['kind'] == 'evidence-source'
                   for path in node['provenance'].get('evidence', [])}
    parts = ['<svg class="graph" viewBox="%s" role="group" aria-label="Directed transfer graph '
             'for the reconstructed outbound path">' % ' '.join(str(v) for v in VIEWBOX)]
    for index, edge in enumerate(document['edges']):
        (x1, y1), (x2, y2), head, (label_x, label_y) = _edge_geometry(edge, nodes, index)
        cited = ' '.join(by_evidence[path] for path in edge['evidence'] if path in by_evidence)
        parts.append('<g class="edge %s" data-edge="%s" data-cites="%s" tabindex="0" role="button" '
                     'aria-controls="rec-%s"><title>%s — %s</title>'
                     '<line x1="%g" y1="%g" x2="%g" y2="%g"/>%s'
                     '<text x="%g" y="%g">%s</text></g>' % (
                         edge['confidence'], _escape(edge['id']), _escape(cited),
                         _escape(edge['id']), _escape(edge['confidence']), _escape(_edge_label(edge)),
                         x1, y1, x2, y2, _polygon(head, 'class="head"'),
                         label_x, label_y, _escape(_edge_label(edge))))
    for node in document['nodes']:
        parts.append('<g class="node %s" data-node="%s" tabindex="0" role="button" '
                     'aria-controls="node-%s"><title>%s — %s</title>%s'
                     '<text x="%g" y="%g">%s</text><text x="%g" y="%g" class="sub">%s</text></g>' % (
                         node['kind'], _escape(node['id']), _escape(node['id']),
                         _escape(node['label']), _escape(node['kind']),
                         shape(node, node['x'], node['y'], _width(node), NODE_HEIGHT),
                         node['x'], node['y'] - 3, _escape(node['label']),
                         node['x'], node['y'] + 16, _escape(node.get('sublabel', ''))))
    parts.append('</svg>')
    return ''.join(parts)


def _legend(document):
    items = []
    for kind in NODE_KINDS:
        entry = next(item for item in document['legend'] if item['kind'] == kind)
        glyph = '<svg class="glyph" viewBox="0 0 120 60" aria-hidden="true">%s</svg>' % shape(
            entry, 60, 30, 92, 34)
        items.append('<li class="legend-%s"><div class="glyphwrap">%s</div><div><strong>%s</strong> '
                     '<em>%s</em><p>%s</p></div></li>' % (
                         kind, glyph, _escape(entry['label']), _escape(entry['shape']),
                         _escape(entry['meaning'])))
    return '<ul class="legend">%s</ul>' % ''.join(items)


def offline_report(document):
    """Every reason a rendered map would be refused, as a list of strings."""
    rendered = render(document)
    faults = [('external resource reference: ' + marker) for marker in SCHEMES if marker in rendered]
    faults += [('retrieval construct: ' + marker) for marker in RETRIEVERS if marker in rendered]
    address = document['external_address']['address']
    if rendered.count(address) != TAG.sub('', rendered).count(address):
        faults.append('external address appears inside a tag')
    return faults


def render(document=None):
    """Render the map as one self-contained offline HTML document."""
    document = document or build()
    disclaimer = document['disclaimer']
    external = document['external_address']
    return _PAGE.format(
        title=_escape('Silent Ridge T01 network map'),
        exercise=_escape(document['exercise_date']),
        caption=_escape(document['caption']),
        unlock=_escape(document['unlock_note']),
        authority=_escape(document['authority']),
        keynote=_escape(document['key_fields_note']),
        address=_escape(external['address']),
        registry=_escape('%s, %s' % (external['registry'], external['block'])),
        reason=_escape(external['reason']),
        rule=_escape(external['rule']),
        boundary='<ul class="boundary">%s</ul>' % ''.join(
            '<li><strong>%s</strong> %s</li>' % (_escape(field), _escape(disclaimer[field]))
            for field in ('receipt', 'identity', 'intent', 'inference', 'scope')),
        legend=_legend(document),
        graph=_graph(document),
        panels=''.join([_edge_panel(edge) for edge in document['edges']]
                       + [_node_panel(node) for node in document['nodes']]),
        companion=_escape(document['companion']),
        style=_STYLE,
        script=_SCRIPT,
    )


def write(destination, document=None):
    """Write the offline document to disk, refusing anything that could reach out."""
    document = document or build()
    faults = offline_report(document)
    if faults:
        raise MapError('network map is not offline-safe: ' + '; '.join(faults))
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(render(document), encoding='utf-8')
    return destination


_STYLE = """
body{margin:0;padding:0 0 4rem;background:#f4f6fa;color:#14243b;
font:16px/1.5 system-ui,-apple-system,'Segoe UI',sans-serif}
main{max-width:1180px;margin:0 auto;padding:1.5rem}
h1{font-size:1.6rem;margin:0 0 .3rem}
h2{font-size:1.15rem;margin:2rem 0 .6rem;border-bottom:2px solid #bccada;padding-bottom:.3rem}
h3{margin:0 0 .5rem;font-size:1rem}
h4{margin:1rem 0 .3rem;font-size:.8rem;text-transform:uppercase;letter-spacing:.06em;color:#41597a}
p{margin:.4rem 0}
code{font-family:ui-monospace,'DejaVu Sans Mono',monospace;font-size:.92em;background:#e6ebf3;
padding:0 .25em;border-radius:4px}
.meta{color:#41597a;font-size:.9rem}
.banner{background:#fff;border:1px solid #bccada;border-left:6px solid #155bbb;
border-radius:10px;padding:1rem 1.2rem;margin:1rem 0}
.banner.doc{border-left-color:#8a5a00;background:#fffaf0}
.banner strong{display:block;margin-bottom:.2rem}
.legend{list-style:none;display:grid;grid-template-columns:repeat(auto-fit,minmax(310px,1fr));
gap:.6rem;padding:0;margin:0}
.legend li{display:flex;gap:.7rem;align-items:flex-start;background:#fff;border:1px solid #bccada;
border-radius:10px;padding:.6rem .8rem}
.legend .glyphwrap{flex:0 0 74px}
.glyph{width:74px;height:38px}
.legend em{color:#41597a;font-size:.85rem}
.legend p{font-size:.88rem;margin:.15rem 0 0}
.boundary{background:#fff;border:1px solid #bccada;border-radius:10px;padding:.8rem 1.2rem .8rem 2.2rem}
.boundary li{margin:.35rem 0}
.graph{width:100%;height:auto;background:#fff;border:1px solid #bccada;border-radius:12px}
.graph .edge line{stroke:#155bbb;stroke-width:2.4}
.graph .edge.inferred line{stroke:#8a5a00;stroke-dasharray:7 5}
.graph .edge text{font-size:12px;fill:#14243b;text-anchor:middle;
paint-order:stroke;stroke:#fff;stroke-width:4px}
.graph .edge{outline:none;cursor:pointer}
.graph .edge:hover line,.graph .edge:focus line{stroke-width:4}
.graph .edge.sel line{stroke-width:4.5}
.graph .edge.sel text{font-weight:700}
.graph .node{outline:none;cursor:pointer}
.graph .node text{font-size:14px;font-weight:600;text-anchor:middle;fill:#14243b}
.graph .node text.sub{font-size:11px;font-weight:400;fill:#41597a}
.graph .node rect,.graph .node polygon{fill:#eef3fb;stroke:#155bbb;stroke-width:2}
.graph .node ellipse{fill:#f2f4f8;stroke:#5a6b82;stroke-width:2}
.graph .node.external polygon{fill:#fff6e8;stroke:#8a5a00;stroke-width:2;stroke-dasharray:6 4}
.graph .node.object polygon{fill:#eef7f0;stroke:#2f6b3d;stroke-width:2}
.graph .node.sel rect,.graph .node.sel polygon,.graph .node.sel ellipse{stroke-width:3.5;fill:#fff8d9}
.graph .node.cite ellipse{stroke-width:3.5;fill:#e2f0e6}
.graph .edge .head{fill:#155bbb;stroke:none}
.graph .edge.inferred .head{fill:#8a5a00}
.record{background:#fff;border:1px solid #bccada;border-radius:10px;padding:1rem 1.2rem;margin:.6rem 0}
.facts{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:.3rem .8rem;margin:.6rem 0}
.fact{display:flex;gap:.5rem;border-bottom:1px dotted #c6d0e0;padding:.15rem 0}
.fact dt{font-weight:600;min-width:7.5rem}
.fact dd{margin:0}
.tag{font-size:.72rem;text-transform:uppercase;letter-spacing:.05em;padding:.1rem .45rem;
border-radius:999px;vertical-align:middle}
.tag.observed,.tag.host,.tag.service{background:#dce9fb;color:#123a75}
.tag.inferred,.tag.external{background:#fbeccc;color:#6b4600}
.tag.object{background:#dff0e2;color:#20512c}
.tag.evidence-source{background:#e6e8ee;color:#3b4658}
.caveat{background:#fffaf0;border-left:4px solid #8a5a00;padding:.5rem .7rem;border-radius:6px}
.sources{margin:.2rem 0;padding-left:1.2rem}
.keys{font-size:.9rem;color:#41597a}
footer{margin-top:2rem;border-top:1px solid #bccada;padding-top:.8rem;font-size:.9rem;color:#41597a}
"""

_SCRIPT = """
(function(){
  var graph=document.querySelector('.graph');
  var records=[].slice.call(document.querySelectorAll('.record'));
  function clear(){
    records.forEach(function(record){record.hidden=true;});
    [].slice.call(graph.querySelectorAll('.edge.sel,.node.sel,.node.cite')).forEach(function(item){
      item.classList.remove('sel');item.classList.remove('cite');});
  }
  function show(identifier){
    clear();
    var record=document.getElementById(identifier);
    if(!record){return;}
    record.hidden=false;
    var edge=graph.querySelector('[data-edge="'+identifier.slice(4)+'"]');
    if(edge){
      edge.classList.add('sel');
      edge.getAttribute('data-cites').split(' ').filter(Boolean).forEach(function(node){
        var cited=graph.querySelector('[data-node="'+node+'"]');
        if(cited){cited.classList.add('cite');}
      });
    }
    var node=graph.querySelector('[data-node="'+identifier.slice(5)+'"]');
    if(node){node.classList.add('sel');}
    record.scrollIntoView({block:'nearest'});
  }
  [].slice.call(graph.querySelectorAll('[aria-controls]')).forEach(function(item){
    var open=function(){show(item.getAttribute('aria-controls'));};
    item.addEventListener('click',open);
    item.addEventListener('keydown',function(event){
      if(event.key==='Enter'||event.key===' '){event.preventDefault();open();}
    });
  });
  var first=graph.querySelector('.edge');
  if(first){show(first.getAttribute('aria-controls'));}
})();
"""

_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="referrer" content="no-referrer">
<title>{title}</title>
<style>{style}</style>
</head>
<body>
<main>
<h1>Operation Silent Ridge — the outbound path, reconstructed</h1>
<p class="meta">Exercise date {exercise} · additional analytical view · unlocks when T01 is
closed · adds no question and no point</p>

<div class="banner"><strong>Read this first</strong><p>{unlock}</p><p>{authority}</p></div>

<div class="banner"><strong>How to join records</strong><p>{keynote}</p><p>{caption}</p></div>

<h2>What this map does not establish</h2>
{boundary}

<h2>Legend</h2>
{legend}

<h2>Graph</h2>
<p class="meta">Select an edge or a node. Selecting an edge opens the record behind it and
highlights the published files that support it. Solid lines are observed in a single record;
dashed lines are inferred by joining records, and the panel says which and why.</p>
{graph}

<h2>Selected record</h2>
{panels}

<div class="banner doc"><strong>{address} is documentation space, not a destination</strong>
<p>{registry}. {reason}</p><p>{rule}</p></div>

<footer><p>{companion}</p></footer>
</main>
<script>{script}</script>
</body>
</html>
"""


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('output', type=Path, help='destination for the offline HTML file')
    arguments = parser.parse_args()
    print(write(arguments.output))
