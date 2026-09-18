"""Pinned Wazuh 4.9.2 historical-stack bootstrap: roles, views, TLS trust.

Cross-lane note (B03): the private deployment profile (A03/A04) is owned by a
parallel lane and is not imported here. The bootstrap takes explicit arguments
and vendored payloads so it can be unit tested without a live stack.

LIVE VALIDATED 2026-09-18 (N1): exercised against a real Wazuh 4.9.2 single-node
stack (upstream wazuh-docker commit 574c7b05) with a local CA. Writer-role writes
require 'indices:data/write/bulk*' (see WRITER_ACTIONS). Never disable TLS
verification.
"""
from __future__ import annotations
import base64
import json
import re
import ssl
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable

INDEX_PATTERN = 'silent-ridge-*'
WRITER_ROLE = 'silent-ridge-writer'
READER_ROLE = 'silent-ridge-participant'
TIMED_VIEW = 'silent-ridge-timed'
TIMELESS_VIEW = 'silent-ridge-timeless'

WRITER_ACTIONS = (
    'create_index', 'indices:data/write/index', 'indices:data/write/bulk',
    # Live 4.9.2 finding: single-doc and bulk writes are also checked against the
    # shard-level action 'indices:data/write/bulk[s]'; the plain bulk grant does not
    # cover it, so the wildcard is required for any write to succeed.
    'indices:data/write/bulk*',
    'indices:admin/mappings/put', 'indices:admin/template/put',
    'indices:data/read/search', 'indices:data/read/get',
)
READER_ACTIONS = ('indices:data/read/search', 'indices:data/read/get', 'indices:admin/mappings/get')


class WazuhError(ValueError):
    """Raised when the historical stack cannot be reconciled safely."""


def validate_index_name(index_name: str) -> str:
    if not re.fullmatch(r'silent-ridge-[a-z0-9-]+', index_name or ''):
        raise WazuhError('index: a dedicated silent-ridge-* index is required')
    return index_name


def index_template(pattern: str = INDEX_PATTERN) -> dict[str, Any]:
    return {
        'index_patterns': [pattern],
        'priority': 500,
        'template': {
            'settings': {'index': {'number_of_shards': 1, 'number_of_replicas': 0}},
            'mappings': {'properties': {
                'timestamp': {'type': 'date'},
                'timeless': {'type': 'boolean'},
                'observation': {'type': 'keyword'},
                'record_id': {'type': 'keyword'},
                'data': {'type': 'object', 'enabled': True},
            }},
        },
    }


def _role(actions: Iterable[str], pattern: str) -> dict[str, Any]:
    return {'cluster_permissions': [], 'index_permissions': [
        {'index_patterns': [pattern], 'allowed_actions': list(actions)}]}


def writer_role(pattern: str = INDEX_PATTERN) -> dict[str, Any]:
    return _role(WRITER_ACTIONS, pattern)


def reader_role(pattern: str = INDEX_PATTERN) -> dict[str, Any]:
    return _role(READER_ACTIONS, pattern)


def saved_objects() -> list[dict[str, Any]]:
    """A timestamped view and a timeless view over the same historical index.

    Coverage/catalog facts carry no timestamp; the timeless view must not apply a
    date filter or those facts would disappear.
    """
    return [
        {'type': 'index-pattern', 'id': TIMED_VIEW,
         'attributes': {'title': INDEX_PATTERN, 'timeFieldName': 'timestamp'}},
        {'type': 'index-pattern', 'id': TIMELESS_VIEW,
         'attributes': {'title': INDEX_PATTERN, 'timeFieldName': None}},
    ]


@dataclass(frozen=True)
class Request:
    method: str
    path: str
    body: dict[str, Any] | None = None
    idempotent: tuple[int, ...] = (200, 201, 409)


@dataclass(frozen=True)
class UserSpec:
    name: str
    password: str
    role: str


def build_plan(index_name: str, users: Iterable[UserSpec], pattern: str = INDEX_PATTERN) -> list[Request]:
    validate_index_name(index_name)
    plan = [
        Request('PUT', '/_index_template/silent-ridge', index_template(pattern)),
        Request('PUT', '/_plugins/_security/api/roles/' + WRITER_ROLE, writer_role(pattern)),
        Request('PUT', '/_plugins/_security/api/roles/' + READER_ROLE, reader_role(pattern)),
        Request('PUT', '/_plugins/_security/api/rolesmapping/' + WRITER_ROLE,
                {'backend_roles': [WRITER_ROLE]}),
        Request('PUT', '/_plugins/_security/api/rolesmapping/' + READER_ROLE,
                {'backend_roles': [READER_ROLE]}),
    ]
    seen = set()
    for user in users:
        if user.role not in (WRITER_ROLE, READER_ROLE):
            raise WazuhError('users: %s has an unknown role' % user.name)
        if not user.name or not user.password:
            raise WazuhError('users: name and password are required')
        if user.name in seen:
            raise WazuhError('users: duplicate user '+user.name)
        seen.add(user.name)
        plan.append(Request('PUT', '/_plugins/_security/api/internalusers/' + user.name,
                            {'password': user.password, 'backend_roles': [user.role]}))
    for view in saved_objects():
        plan.append(Request('POST', '/api/saved_objects/index-pattern/' + view['id'],
                            {'attributes': view['attributes']}))
    return plan


def apply_plan(transport: Callable[[str, str, dict | None], int], plan: Iterable[Request]) -> int:
    """Apply a plan idempotently. A conflict is success only for idempotent ops."""
    applied = 0
    for request in plan:
        status = transport(request.method, request.path, request.body)
        if status not in request.idempotent:
            raise WazuhError('%s %s failed with status %s' % (request.method, request.path, status))
        applied += 1
    return applied


def preflight_facts(transport: Callable[[str, str, dict | None], int],
                    index_name: str, facts: Iterable[dict[str, str]]) -> dict[str, Any]:
    """Confirm known incident facts are queryable; no fact means no readiness."""
    validate_index_name(index_name)
    checked = []
    for fact in facts:
        if not fact.get('field') or not fact.get('value'):
            raise WazuhError('facts: field and value are required')
        body = {'size': 1, 'query': {'match': {fact['field']: fact['value']}}}
        status = transport('POST', '/' + index_name + '/_search', body)
        if status != 200:
            raise WazuhError('facts: query for %s failed with status %s' % (fact['field'], status))
        checked.append(dict(fact))
    return {'ready': bool(checked), 'facts': checked}


def record_id(record: dict[str, Any]) -> str:
    """Stable document ID: re-indexing the same record must not duplicate it."""
    import hashlib
    return hashlib.sha256(json.dumps(record, sort_keys=True).encode()).hexdigest()


def ca_context(ca_file) -> ssl.SSLContext:
    """Explicit local-CA trust. Verification is always enabled; never disabled."""
    path = Path(ca_file)
    if not path.is_file():
        raise WazuhError('ca: CA bundle is missing at '+str(path))
    context = ssl.create_default_context(cafile=str(path))
    context.check_hostname = True
    context.verify_mode = ssl.CERT_REQUIRED
    return context


def authorization(credential: str) -> str:
    return 'Basic '+base64.b64encode(credential.encode()).decode()


def validate_manifest(manifest: dict[str, Any], require_digests: bool = True) -> int:
    """Validate the vendored manifest. Missing digests fail closed."""
    if manifest.get('schema') != 1:
        raise WazuhError('manifest: schema 1 is required')
    source = manifest.get('source', {})
    if not source.get('url') or not source.get('commit'):
        raise WazuhError('manifest: source url and commit are required')
    images = manifest.get('images')
    if not images:
        raise WazuhError('manifest: images are required')
    for image in images:
        if not image.get('name') or not image.get('version'):
            raise WazuhError('manifest: image name and version are required')
        if require_digests and not image.get('digest'):
            raise WazuhError('manifest: image %s is missing an immutable digest' % image.get('name'))
    return len(images)


def load_vendored(root) -> dict[str, Any]:
    root = Path(root)
    manifest = json.loads((root / 'manifest.json').read_text(encoding='utf-8'))
    validate_manifest(manifest, require_digests=False)
    template = json.loads((root / 'index-template.json').read_text(encoding='utf-8'))
    views = json.loads((root / 'saved-objects.json').read_text(encoding='utf-8'))
    if template != index_template() or views != saved_objects():
        raise WazuhError('vendored Wazuh config differs from the reviewed module output')
    return {'manifest': manifest, 'index_template': template, 'saved_objects': views}
