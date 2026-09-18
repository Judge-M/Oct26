"""Idempotent CTFd settings, team, membership and participant provisioning.

Cross-lane note (B02): the private deployment profile schema is owned by tasks
A03/A04 in a parallel lane and is not imported here. This module accepts an
explicit ``ProvisionSpec`` so it can be unit tested without CTFd. Wiring a
validated A03/A04 profile into ``ProvisionSpec`` is PENDING on that contract.

One shared IRIS login maps to one CTFd *team*; each participant is an individual
CTFd membership inside that team. Provisioning never deletes awards, never
rotates an existing password and is safe to repeat.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Protocol


class ProvisionError(ValueError):
    """Raised when provisioning cannot proceed safely; message names the field."""


class Admin(Protocol):
    def get_config(self, key: str, default: Any = None) -> Any: ...

    def set_config(self, key: str, value: Any) -> None: ...

    def find_team(self, name: str) -> dict[str, Any] | None: ...

    def create_team(self, name: str, password: str) -> dict[str, Any]: ...

    def find_user(self, name: str) -> dict[str, Any] | None: ...

    def create_user(self, name: str, email: str, password: str) -> dict[str, Any]: ...

    def set_user_team(self, user_id: int, team_id: int) -> None: ...

    def user_team(self, user_id: int) -> int | None: ...

    def count_awards(self) -> int: ...


@dataclass(frozen=True)
class TeamSpec:
    team: str
    name: str
    password: str = field(repr=False)


@dataclass(frozen=True)
class UserSpec:
    name: str
    email: str
    team: str
    password: str = field(repr=False)


@dataclass(frozen=True)
class ProvisionSpec:
    teams: tuple[TeamSpec, ...]
    users: tuple[UserSpec, ...]
    user_mode: str = 'teams'
    registration_visible: bool = False
    schema: str = 'ctfd-3.7.7'


def _require(spec: ProvisionSpec) -> None:
    if spec.user_mode != 'teams':
        raise ProvisionError('user_mode: only team mode is supported')
    if not spec.teams:
        raise ProvisionError('teams: at least one team is required')
    seen = set()
    for team in spec.teams:
        if not team.team or not team.name or not team.password:
            raise ProvisionError('teams: each team requires team, name and password')
        if team.team in seen:
            raise ProvisionError('teams: duplicate team '+team.team)
        seen.add(team.team)
    names = set()
    for user in spec.users:
        if not user.name or not user.email or not user.password:
            raise ProvisionError('users: each user requires name, email and password')
        if user.name in names:
            raise ProvisionError('users: duplicate user '+user.name)
        if user.team not in seen:
            raise ProvisionError('users: %s references unmapped team %s' % (user.name, user.team))
        names.add(user.name)


def _find_or_create_team(admin: Admin, team: TeamSpec) -> dict[str, Any]:
    existing = admin.find_team(team.name)
    if existing is not None:
        return existing
    return admin.create_team(team.name, team.password)


def _find_or_create_user(admin: Admin, user: UserSpec, team_id: int) -> dict[str, Any]:
    existing = admin.find_user(user.name)
    if existing is not None:
        if admin.user_team(int(existing['id'])) != team_id:
            raise ProvisionError('users: %s already belongs to another team' % user.name)
        return existing
    created = admin.create_user(user.name, user.email, user.password)
    admin.set_user_team(int(created['id']), team_id)
    return created


def provision(admin: Admin, spec: ProvisionSpec) -> dict[str, Any]:
    """Apply settings, teams and memberships; return the resolved inventory."""
    _require(spec)
    awards_before = admin.count_awards()

    admin.set_config('user_mode', spec.user_mode)
    admin.set_config('registration_visible', spec.registration_visible)
    admin.set_config('setup', True)

    teams: dict[str, dict[str, Any]] = {}
    for team in spec.teams:
        row = _find_or_create_team(admin, team)
        teams[team.team] = {'id': int(row['id']), 'name': team.name}

    users: dict[str, dict[str, Any]] = {}
    for user in spec.users:
        row = _find_or_create_user(admin, user, teams[user.team]['id'])
        users[user.name] = {'id': int(row['id']), 'name': user.name, 'team': user.team}

    if admin.count_awards() != awards_before:
        raise ProvisionError('awards: provisioning must not change existing awards')
    return {'user_mode': spec.user_mode, 'registration_visible': spec.registration_visible,
            'teams': teams, 'users': users}


def preflight(admin: Admin, spec: ProvisionSpec, inventory: dict[str, Any]) -> dict[str, Any]:
    """Read-only reconciliation used before an event starts."""
    _require(spec)
    if admin.get_config('user_mode') != 'teams':
        raise ProvisionError('user_mode: application is not in team mode')
    for key, expected in inventory['teams'].items():
        row = admin.find_team(expected['name'])
        if row is None or int(row['id']) != int(expected['id']):
            raise ProvisionError('teams: %s is missing or has a different ID' % key)
        if row.get('banned') or row.get('hidden'):
            raise ProvisionError('teams: %s is banned or hidden' % key)
    identities = []
    for name, expected in inventory['users'].items():
        row = admin.find_user(name)
        if row is None or int(row['id']) != int(expected['id']):
            raise ProvisionError('users: %s is missing or has a different ID' % name)
        if admin.user_team(int(row['id'])) != int(inventory['teams'][expected['team']]['id']):
            raise ProvisionError('users: %s membership changed' % name)
        identities.append({'id': str(inventory['teams'][expected['team']]['id']),
                           'name': inventory['teams'][expected['team']]['name']})
    unique = {row['id']: row for row in identities}
    return {'ready': True, 'identities': list(unique.values())}
