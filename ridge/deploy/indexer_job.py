"""Indexer-side evidence provisioning, run inside the integration image on the
Wazuh backend network. The indexer deliberately sits on an `internal: true`
network with no host-published port, so all indexer traffic must originate
from a container attached to that network; only the dashboard is host-exposed.

Usage (container): python -m ridge.deploy.indexer_job apply|probe <index_name>

Mounts expected: /certs (root-ca.pem), /secrets (wazuh_admin, wazuh_writer,
wazuh_reader), /evidence (public evidence tree with wazuh/telemetry.jsonl).
Prints one JSON result line on stdout; exits nonzero with a message on failure.
"""
from __future__ import annotations

import base64
import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

CERTS = Path('/certs')
SECRETS = Path('/secrets')
EVIDENCE = Path('/evidence')
BASE = os.environ.get('WAZUH_INDEXER_URL', 'https://wazuh-indexer:9200').rstrip('/')

WRITER_ACCOUNT = 'silent-ridge-writer-account'
READER_ACCOUNT = 'silent-ridge-participant-account'


def _transport(credential):
    from ridge.wazuh_provision import ca_context
    context = ca_context(str(CERTS / 'root-ca.pem'))
    authorization = 'Basic ' + base64.b64encode(credential.encode()).decode()

    def call(method, path, body=None, raw=None):
        if raw is not None:
            data, content_type = raw.encode(), 'application/x-ndjson'
        else:
            data, content_type = (json.dumps(body).encode() if body is not None else None,
                                  'application/json')
        request = Request(BASE + path, data=data, method=method,
                          headers={'Content-Type': content_type,
                                   'Authorization': authorization})
        try:
            with urlopen(request, timeout=15, context=context) as response:
                text = response.read().decode()
                return response.status, json.loads(text) if text else {}
        except HTTPError as exc:
            text = exc.read().decode()
            try:
                return exc.code, json.loads(text)
            except ValueError:
                return exc.code, {'raw': text[:200]}

    return call


def _apply(index_name):
    from ridge.wazuh_provision import (READER_ROLE, WRITER_ROLE, UserSpec,
                                       apply_plan, build_plan)
    admin = (SECRETS / 'wazuh_admin').read_text(encoding='utf-8').strip()
    writer_pw = (SECRETS / 'wazuh_writer').read_text(encoding='utf-8').strip().split(':', 1)[1]
    reader_pw = (SECRETS / 'wazuh_reader').read_text(encoding='utf-8').strip().split(':', 1)[1]
    users = [UserSpec(WRITER_ACCOUNT, writer_pw, WRITER_ROLE),
             UserSpec(READER_ACCOUNT, reader_pw, READER_ROLE)]
    plan = [r for r in build_plan(index_name, users) if not r.path.startswith('/api/')]
    call = _transport(admin)

    def transport(method, path, body):
        status, payload = call(method, path, body)
        if status >= 300:
            raise SystemExit('wazuh admin %s %s -> HTTP %s: %s'
                             % (method, path, status, str(payload)[:200]))
        return status

    apply_plan(transport, plan)
    indexed = 0
    telemetry = EVIDENCE / 'wazuh' / 'telemetry.jsonl'
    if telemetry.is_file():
        records = [json.loads(line) for line in
                   telemetry.read_text(encoding='utf-8').splitlines() if line.strip()]
        os.environ['WAZUH_INDEX_CREDENTIAL_FILE'] = str(SECRETS / 'wazuh_writer')
        os.environ['WAZUH_INDEXER_URL'] = BASE
        os.environ['WAZUH_INDEX'] = index_name
        os.environ.setdefault('SSL_CERT_FILE', str(CERTS / 'root-ca.pem'))
        from ridge.evidence_release import index
        index(records)  # stable document IDs: re-applying creates no duplicates
        indexed = len(records)
    return {'ok': True, 'indexed': indexed}


def _probe(index_name):
    admin = (SECRETS / 'wazuh_admin').read_text(encoding='utf-8').strip()
    status, payload = _transport(admin)('GET', '/' + index_name + '/_count')
    return {'status': status, 'count': payload.get('count', 0)}


def _dump(index_name):
    """Dump every document (with stable IDs) to /evidence-writer-readable NDJSON file
    at /backup/index.ndjson for coherent, restorable index snapshots."""
    admin = (SECRETS / 'wazuh_admin').read_text(encoding='utf-8').strip()
    call = _transport(admin)
    status, payload = call('GET', '/%s/_search?size=1000&scroll=2m' % index_name)
    if status != 200:
        raise SystemExit('index dump failed at first page: HTTP %s: %s'
                         % (status, str(payload)[:200]))
    out = Path('/backup/index.ndjson')
    out.unlink(missing_ok=True)
    total = payload['hits']['total']['value']
    written = 0
    while True:
        hits = payload['hits']['hits']
        if not hits:
            break
        with out.open('a', encoding='utf-8') as fh:
            for hit in hits:
                fh.write(json.dumps({'_id': hit['_id'], '_source': hit['_source']},
                                    sort_keys=True) + '\n')
                written += 1
        status, payload = call('POST', '/_search/scroll',
                               {'scroll': '2m', 'scroll_id': payload['_scroll_id']})
        if status != 200:
            raise SystemExit('index dump scroll failed: HTTP %s' % status)
    if written != total:
        out.unlink(missing_ok=True)
        raise SystemExit('index dump incomplete: %d of %d documents; discarded' % (written, total))
    return {'ok': True, 'documents': written}


def _load(index_name):
    """Bulk-load /backup/index.ndjson with original stable IDs; retries do not
    duplicate documents."""
    admin = (SECRETS / 'wazuh_admin').read_text(encoding='utf-8').strip()
    call = _transport(admin)
    source = Path('/backup/index.ndjson')
    lines = []
    for raw_line in source.read_text(encoding='utf-8').splitlines():
        if not raw_line.strip():
            continue
        doc = json.loads(raw_line)
        lines.append(json.dumps({'index': {'_id': doc['_id']}}))
        lines.append(json.dumps(doc['_source'], sort_keys=True))
    count = len(lines) // 2
    for offset in range(0, len(lines), 2000):
        batch = '\n'.join(lines[offset:offset + 2000]) + '\n'
        status, payload = call('POST', '/%s/_bulk?refresh=true' % index_name, raw=batch)
        if status != 200 or payload.get('errors'):
            raise SystemExit('index load bulk failed: HTTP %s: %s'
                             % (status, str(payload)[:300]))
    return {'ok': True, 'loaded': count}


def main(argv=None):
    argv = argv or sys.argv
    action, index_name = argv[1], argv[2]
    from ridge.wazuh_provision import validate_index_name
    index_name = validate_index_name(index_name)
    if action == 'apply':
        result = _apply(index_name)
    elif action == 'probe':
        result = _probe(index_name)
    elif action == 'dump':
        result = _dump(index_name)
    elif action == 'load':
        result = _load(index_name)
    else:
        raise SystemExit('unknown indexer job action %r' % action)
    print(json.dumps(result))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
