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

    def call(method, path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        request = Request(BASE + path, data=data, method=method,
                          headers={'Content-Type': 'application/json',
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


def main(argv=None):
    argv = argv or sys.argv
    action, index_name = argv[1], argv[2]
    from ridge.wazuh_provision import validate_index_name
    index_name = validate_index_name(index_name)
    if action == 'apply':
        result = _apply(index_name)
    elif action == 'probe':
        result = _probe(index_name)
    else:
        raise SystemExit('unknown indexer job action %r' % action)
    print(json.dumps(result))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
