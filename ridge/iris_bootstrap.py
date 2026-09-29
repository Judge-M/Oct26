"""Idempotent IRIS bootstrap planning, independent of the pinned ORM.

Cross-lane note (B01): the private deployment profile schema is owned by tasks
A03/A04 in a parallel lane and is intentionally not imported here. This module
accepts an explicit, narrow ``BootstrapSpec`` so it can be unit tested on a host
without IRIS. Wiring a validated A03/A04 profile into ``BootstrapSpec`` is
PENDING on that contract; no profile fields are invented.

All identity material is supplied by the private caller. Passwords are never
logged and never included in the returned inventory. Numeric status IDs are
discovered from the live application; none are guessed here.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Protocol


class BootstrapError(ValueError):
    """Raised when bootstrap cannot be completed safely; message names the field."""


class Admin(Protocol):
    """Minimal surface implemented by the pinned IRIS ORM adapter."""

    def schema_version(self) -> str: ...

    def ensure_receipt_table(self) -> None: ...

    def list_task_statuses(self) -> list[dict[str, Any]]: ...

    def find_case(self, name: str) -> dict[str, Any] | None: ...

    def create_case(self, name: str, description: str) -> dict[str, Any]: ...

    def find_user(self, login: str) -> dict[str, Any] | None: ...

    def create_user(self, login: str, name: str, password: str) -> dict[str, Any]: ...

    def set_case_access(self, user_id: int, case_id: int, level: str) -> None: ...

    def case_access(self, user_id: int, case_id: int) -> str | None: ...

    def user_active(self, user_id: int) -> bool: ...

    def create_task(self, case_id: int, ticket: str, title: str,
                    open_status_id: int, service_user_id: int) -> int: ...

    def create_finding(self, case_id: int, iris_id: int, service_user_id: int,
                       finding: dict[str, Any]) -> int: ...


@dataclass(frozen=True)
class IdentitySpec:
    team: str
    login: str
    name: str
    password: str = field(repr=False)


@dataclass(frozen=True)
class BootstrapSpec:
    case_name: str
    case_description: str
    service_login: str
    service_name: str
    service_password: str = field(repr=False)
    open_status: str
    closed_status: str
    identities: tuple[IdentitySpec, ...]
    schema: str = 'iris-2.4.20'


def _require(spec: BootstrapSpec) -> None:
    for name in ('case_name', 'case_description', 'service_login', 'service_name',
                 'open_status', 'closed_status', 'schema'):
        if not getattr(spec, name):
            raise BootstrapError('Missing required field: '+name)
    if not spec.identities:
        raise BootstrapError('At least one identity is required')
    seen = set()
    for identity in spec.identities:
        if not identity.team or not identity.login or not identity.name:
            raise BootstrapError('Identity requires team, login and name')
        if identity.team in seen:
            raise BootstrapError('Duplicate team identity: '+identity.team)
        seen.add(identity.team)


def resolve_statuses(statuses: list[dict[str, Any]], spec: BootstrapSpec) -> dict[str, int]:
    """Map the configured status *names* to actual IDs. Never guess a number."""
    by_name: dict[str, list[int]] = {}
    for row in statuses:
        by_name.setdefault(str(row['name']).strip().casefold(), []).append(int(row['id']))
    resolved: dict[str, int] = {}
    for field_name, wanted in (('open_status', spec.open_status), ('closed_status', spec.closed_status)):
        matches = by_name.get(wanted.strip().casefold(), [])
        if len(matches) != 1:
            raise BootstrapError(
                'Status name %r for %s must match exactly one live status row (found %d)'
                % (wanted, field_name, len(matches)))
        resolved[field_name] = matches[0]
    if resolved['open_status'] == resolved['closed_status']:
        raise BootstrapError('open_status and closed_status must be distinct')
    return resolved


def _find_or_create_user(admin: Admin, login: str, name: str, password: str) -> dict[str, Any]:
    existing = admin.find_user(login)
    if existing is not None:
        # Reuse the account; never silently rotate an existing password.
        return existing
    return admin.create_user(login, name, password)


def bootstrap(admin: Admin, spec: BootstrapSpec) -> dict[str, Any]:
    """Create or find the exercise case, service user and restricted team users.

    Safe to run repeatedly: a second run creates no duplicate case, user or access
    grant and returns the same IDs. Any ORM failure propagates to the caller.
    """
    _require(spec)
    version = admin.schema_version()
    if version != spec.schema:
        raise BootstrapError('schema: expected %s but application reports %s' % (spec.schema, version))

    admin.ensure_receipt_table()
    statuses = resolve_statuses(admin.list_task_statuses(), spec)

    service = _find_or_create_user(admin, spec.service_login, spec.service_name, spec.service_password)

    case = admin.find_case(spec.case_name)
    if case is None:
        case = admin.create_case(spec.case_name, spec.case_description)
    case_id = int(case['id'])


    identities: dict[str, dict[str, Any]] = {}
    for identity in spec.identities:
        user = _find_or_create_user(admin, identity.login, identity.name, identity.password)
        admin.set_case_access(int(user['id']), case_id, 'read_only')
        identities[identity.team] = {'id': int(user['id']), 'login': identity.login, 'name': identity.name}

    return {
        'case': {'id': case_id, 'name': spec.case_name},
        'statuses': {'open': statuses['open_status'], 'closed': statuses['closed_status']},
        'service_user': {'id': int(service['id']), 'login': spec.service_login},
        'identities': identities,
    }


def preflight(admin: Admin, spec: BootstrapSpec, inventory: dict[str, Any]) -> dict[str, Any]:
    """Read-only reconciliation of the inventory returned by :func:`bootstrap`."""
    _require(spec)
    version = admin.schema_version()
    if version != spec.schema:
        raise BootstrapError('schema: expected %s but application reports %s' % (spec.schema, version))
    case = admin.find_case(spec.case_name)
    if case is None or int(case['id']) != int(inventory['case']['id']):
        raise BootstrapError('case: configured exercise case is not available')
    statuses = resolve_statuses(admin.list_task_statuses(), spec)
    for key, resolved in (('open', statuses['open_status']), ('closed', statuses['closed_status'])):
        if resolved != int(inventory['statuses'][key]):
            raise BootstrapError('statuses: %s status ID changed since bootstrap' % key)
    service = admin.find_user(spec.service_login)
    if service is None or int(service['id']) != int(inventory['service_user']['id']) or not admin.user_active(int(service['id'])):
        raise BootstrapError('service_user: service account is missing or inactive')
    for team, expected in inventory['identities'].items():
        user = admin.find_user(expected['login'])
        if user is None or int(user['id']) != int(expected['id']) or not admin.user_active(int(user['id'])):
            raise BootstrapError('identities: %s account is missing or inactive' % team)
        if admin.case_access(int(user['id']), int(inventory['case']['id'])) != 'read_only':
            raise BootstrapError('identities: %s must have read-only case access' % team)
    return {'ready': True, 'case': inventory['case']['id'],
            'identities': [{'id': str(v['id']), 'name': v['name']} for v in inventory['identities'].values()]}


def post_task(admin: Admin, spec: BootstrapSpec, inventory: dict[str, Any], ticket: str, title: str) -> int:
    if not ticket or not title:
        raise BootstrapError('Task requires ticket and title')
    return admin.create_task(int(inventory['case']['id']), ticket, title,
                             int(inventory['statuses']['open']), int(inventory['service_user']['id']))


def post_finding(admin: Admin, spec: BootstrapSpec, inventory: dict[str, Any], iris_id: int,
                 finding: dict[str, Any]) -> int:
    if not iris_id or not finding.get('text') or not finding.get('evidence'):
        raise BootstrapError('Finding requires iris_id, text and evidence')
    return admin.create_finding(int(inventory['case']['id']), int(iris_id),
                                int(inventory['service_user']['id']), finding)
