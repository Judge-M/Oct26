"""Versioned, private deployment profile schema and validator.

A profile describes one event deployment: identifiers, provider, roster shape, host
capacity, addresses, secret *references*, retention and a spending/TTL envelope. It
never contains application account IDs or secret values; those are resolved after
provisioning through :func:`desired_inventory` and :func:`resolve_inventory`.

The schema is frozen for Wave 0. Dependent agents must consume it through this module
rather than re-parsing profile JSON.
"""
import hashlib
import ipaddress
import json
import re
from copy import deepcopy
from datetime import date, datetime
from urllib.parse import urlsplit

SCHEMA_VERSION = 1
PROVIDERS = ('local', 'aws')
PROFILE_KINDS = ('example', 'production')
DEFAULT_TEAM_COUNT = 10
DEFAULT_MEMBERS = 3

SECRET_REF = re.compile(r'^(env|file|vault|ref):[A-Za-z0-9_./@-]+$')
SECRET_KEY = re.compile(r'password|secret|token|api[_-]?key|access[_-]?key|private[_-]?key|credential', re.I)
NAME = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]*$')
FIXED_ID_KEYS = frozenset({'iris', 'iris_id', 'ctfd', 'ctfd_id'})
DOC_NETWORKS = tuple(ipaddress.ip_network(net) for net in
                     ('192.0.2.0/24', '198.51.100.0/24', '203.0.113.0/24'))
UNUSABLE_NETWORKS = tuple(ipaddress.ip_network(net) for net in
                          ('0.0.0.0/8', '127.0.0.0/8', '169.254.0.0/16', '::/128', '::1/128'))
DOC_HOST_SUFFIXES = ('.example', '.invalid', '.test', '.localhost')


class ProfileError(ValueError):
    """A profile field is invalid; ``field`` names the exact JSON path."""

    def __init__(self, field, message):
        super().__init__(field + ': ' + message)
        self.field = field


def _fail(field, message):
    raise ProfileError(field, message)


def _require(mapping, key, field):
    if not isinstance(mapping, dict) or key not in mapping or mapping[key] in (None, ''):
        _fail(field, 'required')
    return mapping[key]


def _parse_date(value, field):
    if not isinstance(value, str):
        _fail(field, 'must be an ISO date')
    try:
        return date.fromisoformat(value)
    except ValueError:
        _fail(field, 'must be an ISO date (YYYY-MM-DD)')


def _parse_datetime(value, field):
    if not isinstance(value, str):
        _fail(field, 'must be an ISO datetime with a timezone offset')
    try:
        stamp = datetime.fromisoformat(value)
    except ValueError:
        _fail(field, 'must be an ISO datetime with a timezone offset')
    if stamp.tzinfo is None:
        _fail(field, 'timezone offset required')
    return stamp


def _validate_event(profile):
    event = _require(profile, 'event', 'event')
    if not isinstance(event, dict):
        _fail('event', 'must be an object')
    for key in ('id', 'release_id', 'timezone'):
        value = _require(event, key, 'event.' + key)
        if not isinstance(value, str) or not value.strip():
            _fail('event.' + key, 'must be a nonempty string')
    incident = _parse_date(_require(event, 'incident_date', 'event.incident_date'), 'event.incident_date')
    start = _parse_datetime(_require(event, 'event_start', 'event.event_start'), 'event.event_start')
    if start.date() < incident:
        _fail('event.event_start', 'must not precede event.incident_date')
    duration = _require(event, 'duration_minutes', 'event.duration_minutes')
    if not isinstance(duration, int) or isinstance(duration, bool) or duration <= 0:
        _fail('event.duration_minutes', 'must be a positive integer')
    if 'activity_minutes' in event:
        activity = event['activity_minutes']
        if not isinstance(activity, int) or isinstance(activity, bool) or activity <= 0 or activity > duration:
            _fail('event.activity_minutes', 'must be a positive integer no greater than event.duration_minutes')
    return event


def _validate_resources(entry, field):
    if not isinstance(entry, dict):
        _fail(field, 'must be an object')
    result = {}
    for key in ('vcpus', 'memory_mib', 'disk_gib'):
        value = _require(entry, key, field + '.' + key)
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            _fail(field + '.' + key, 'must be a positive integer')
        result[key] = value
    return result


def _validate_capacity(profile):
    capacity = _require(profile, 'capacity', 'capacity')
    if not isinstance(capacity, dict):
        _fail('capacity', 'must be an object')
    return {name: _validate_resources(_require(capacity, name, 'capacity.' + name), 'capacity.' + name)
            for name in ('host', 'central', 'desktop')}


def _validate_ip(value, field, profile_kind):
    if not isinstance(value, str):
        _fail(field, 'must be an IP address')
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        _fail(field, 'must be an IP address')
    if any(address in network for network in UNUSABLE_NETWORKS):
        _fail(field, 'must be a routable host address')
    if profile_kind == 'production' and any(address in network for network in DOC_NETWORKS):
        _fail(field, 'documentation-only address is not allowed in a production profile')
    return address


def _validate_url(value, field, profile_kind):
    if not isinstance(value, str):
        _fail(field, 'must be an HTTP(S) URL')
    parsed = urlsplit(value)
    if parsed.scheme not in ('http', 'https') or not parsed.hostname:
        _fail(field, 'must be an HTTP(S) URL')
    if profile_kind == 'production':
        host = parsed.hostname.lower()
        if host == 'localhost' or any(host.endswith(suffix) for suffix in DOC_HOST_SUFFIXES):
            _fail(field, 'documentation-only host is not allowed in a production profile')
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            address = None
        if address is not None and any(address in network for network in DOC_NETWORKS):
            _fail(field, 'documentation-only address is not allowed in a production profile')
    return value


def _validate_desktops(profile, profile_kind):
    desktops = _require(profile, 'desktops', 'desktops')
    if not isinstance(desktops, list) or not desktops:
        _fail('desktops', 'must be a nonempty list')
    seen = set()
    result = []
    for index, desktop in enumerate(desktops):
        field = 'desktops[%d]' % index
        if not isinstance(desktop, dict):
            _fail(field, 'must be an object')
        name = _require(desktop, 'name', field + '.name')
        if not isinstance(name, str) or not NAME.match(name):
            _fail(field + '.name', 'must be a short identifier')
        if name in seen:
            _fail(field + '.name', 'duplicate desktop name')
        seen.add(name)
        _validate_ip(_require(desktop, 'address', field + '.address'), field + '.address', profile_kind)
        shared = desktop.get('shared', True)
        if not isinstance(shared, bool):
            _fail(field + '.shared', 'must be a boolean')
        connections = desktop.get('max_connections', 4 if shared else 1)
        if not isinstance(connections, int) or isinstance(connections, bool) or connections < 1:
            _fail(field + '.max_connections', 'must be a positive integer')
        if not shared and connections != 1:
            _fail(field + '.max_connections', 'an exclusive desktop allows exactly one connection')
        result.append(dict(desktop, name=name, shared=shared, max_connections=connections))
    return result


def neutral_accounts(team_name, members=DEFAULT_MEMBERS):
    """Neutral participant account names for a team with no supplied roster."""
    return ['%s-p%02d' % (team_name, index + 1) for index in range(members)]


def neutral_roster(team_count=DEFAULT_TEAM_COUNT, desktop_names=None):
    """One neutral team per desktop, with neutral participant accounts."""
    if not isinstance(team_count, int) or isinstance(team_count, bool) or team_count < 1:
        _fail('roster.team_count', 'must be a positive integer')
    desktop_names = desktop_names or ['desktop-%02d' % (index + 1) for index in range(team_count)]
    if len(desktop_names) < team_count:
        _fail('roster.team_count', 'exceeds the %d configured desktops' % len(desktop_names))
    teams = []
    for index in range(team_count):
        name = 'team-%02d' % (index + 1)
        teams.append({'name': name, 'members': DEFAULT_MEMBERS, 'desktop': desktop_names[index],
                      'accounts': neutral_accounts(name)})
    return teams


def _validate_roster(profile, desktops):
    desktop_names = [desktop['name'] for desktop in desktops]
    roster = profile.get('roster')
    if not roster or not roster.get('teams'):
        if isinstance(roster, dict) and roster.get('team_count') is not None:
            count = roster['team_count']
        else:
            count = len(desktop_names)
        teams = neutral_roster(count, desktop_names)
        return {'team_count': len(teams), 'teams': teams}
    if not isinstance(roster, dict):
        _fail('roster', 'must be an object')
    teams = roster['teams']
    if not isinstance(teams, list) or not teams:
        _fail('roster.teams', 'must be a nonempty list')
    seen = set()
    result = []
    for index, team in enumerate(teams):
        field = 'roster.teams[%d]' % index
        if not isinstance(team, dict):
            _fail(field, 'must be an object')
        name = _require(team, 'name', field + '.name')
        if not isinstance(name, str) or not NAME.match(name):
            _fail(field + '.name', 'must be a short identifier')
        if name in seen:
            _fail(field + '.name', 'duplicate team name')
        seen.add(name)
        members = team.get('members', DEFAULT_MEMBERS)
        if not isinstance(members, int) or isinstance(members, bool) or not 1 <= members <= 10:
            _fail(field + '.members', 'must be an integer between 1 and 10')
        desktop = _require(team, 'desktop', field + '.desktop')
        if desktop not in desktop_names:
            _fail(field + '.desktop', 'is not a configured desktop')
        accounts = team.get('accounts')
        if accounts is None:
            accounts = neutral_accounts(name, members)
        if (not isinstance(accounts, list) or len(accounts) != members
                or not all(isinstance(account, str) and NAME.match(account) for account in accounts)):
            _fail(field + '.accounts', 'must list one neutral name per member')
        if len(set(accounts)) != len(accounts):
            _fail(field + '.accounts', 'must be unique')
        result.append(dict(team, name=name, members=members, desktop=desktop, accounts=accounts))
    return {'team_count': len(result), 'teams': result}


def _validate_addresses(profile, profile_kind):
    addresses = _require(profile, 'addresses', 'addresses')
    if not isinstance(addresses, dict):
        _fail('addresses', 'must be an object')
    result = {}
    for key in ('central_bind_ip', 'iris_public_url', 'ctfd_public_url', 'guacamole_public_url'):
        value = _require(addresses, key, 'addresses.' + key)
        if key.endswith('_ip'):
            _validate_ip(value, 'addresses.' + key, profile_kind)
        else:
            _validate_url(value, 'addresses.' + key, profile_kind)
        result[key] = value
    return result


def _join(field, key):
    return str(key) if not field else field + '.' + str(key)


def _reject_embedded_secrets(node, field=''):
    if isinstance(node, dict):
        for key, value in node.items():
            child = _join(field, key)
            if SECRET_KEY.search(str(key)) and not isinstance(value, (dict, list)):
                if not (isinstance(value, str) and SECRET_REF.match(value)):
                    _fail(child, 'secret values must be references such as env:NAME, not embedded literals')
            _reject_embedded_secrets(value, child)
    elif isinstance(node, list):
        for index, value in enumerate(node):
            _reject_embedded_secrets(value, '%s[%d]' % (field, index))


def _validate_secrets(profile):
    refs = _require(profile, 'secret_refs', 'secret_refs')
    if not isinstance(refs, dict) or not refs:
        _fail('secret_refs', 'must be a nonempty object of secret references')
    result = {}
    for key, value in refs.items():
        if not isinstance(value, str) or not SECRET_REF.match(value):
            _fail('secret_refs.' + key, 'must be a reference such as env:NAME, file:/path or vault:path')
        result[key] = value
    _reject_embedded_secrets(profile)
    return result


def _validate_retention(profile):
    retention = _require(profile, 'retention', 'retention')
    if not isinstance(retention, dict):
        _fail('retention', 'must be an object')
    result = {}
    for key in ('backup_days', 'export_days'):
        value = _require(retention, key, 'retention.' + key)
        if not isinstance(value, int) or isinstance(value, bool) or value < 1:
            _fail('retention.' + key, 'must be a positive integer')
        result[key] = value
    min_free = retention.get('min_free_bytes')
    if min_free is not None and (not isinstance(min_free, int) or isinstance(min_free, bool) or min_free < 0):
        _fail('retention.min_free_bytes', 'must be a nonnegative integer')
    return dict(retention, **result)


def _validate_spending(profile):
    spending = _require(profile, 'spending', 'spending')
    if not isinstance(spending, dict):
        _fail('spending', 'must be an object')
    ttl = _require(spending, 'ttl_hours', 'spending.ttl_hours')
    if not isinstance(ttl, int) or isinstance(ttl, bool) or ttl < 1:
        _fail('spending.ttl_hours', 'must be a positive integer')
    budget = spending.get('budget_usd', 0)
    if not isinstance(budget, (int, float)) or isinstance(budget, bool) or budget < 0:
        _fail('spending.budget_usd', 'must be a nonnegative number')
    currency = spending.get('currency', 'USD')
    if not isinstance(currency, str) or len(currency) != 3:
        _fail('spending.currency', 'must be a three-letter code')
    return dict(spending, ttl_hours=ttl, budget_usd=budget, currency=currency)


def _assert_no_fixed_ids(node, field=''):
    if isinstance(node, dict):
        for key, value in node.items():
            child = _join(field, key)
            if str(key) in FIXED_ID_KEYS:
                _fail(child, 'profiles must not contain fixed application IDs; resolve them after provisioning')
            _assert_no_fixed_ids(value, child)
    elif isinstance(node, list):
        for index, value in enumerate(node):
            _assert_no_fixed_ids(value, '%s[%d]' % (field, index))


def _check_capacity(capacity, roster):
    teams = len(roster['teams'])
    for key in ('vcpus', 'memory_mib', 'disk_gib'):
        needed = capacity['central'][key] + teams * capacity['desktop'][key]
        if capacity['host'][key] < needed:
            _fail('capacity.host.' + key, 'insufficient for %d teams: need %d' % (teams, needed))


def validate(profile, kind=None):
    """Validate a profile and return a normalized copy with a materialized roster."""
    if not isinstance(profile, dict):
        _fail('profile', 'must be an object')
    if profile.get('schema_version') != SCHEMA_VERSION:
        _fail('schema_version', 'expected %d' % SCHEMA_VERSION)
    profile_kind = kind or profile.get('profile_kind', 'production')
    if profile_kind not in PROFILE_KINDS:
        _fail('profile_kind', 'must be one of ' + ', '.join(PROFILE_KINDS))
    profile_id = _require(profile, 'profile_id', 'profile_id')
    if not isinstance(profile_id, str) or not NAME.match(profile_id):
        _fail('profile_id', 'must be a short identifier')
    if _require(profile, 'provider', 'provider') not in PROVIDERS:
        _fail('provider', 'must be one of ' + ', '.join(PROVIDERS))
    _assert_no_fixed_ids(profile)
    _validate_event(profile)
    capacity = _validate_capacity(profile)
    desktops = _validate_desktops(profile, profile_kind)
    roster = _validate_roster(profile, desktops)
    _validate_addresses(profile, profile_kind)
    _validate_secrets(profile)
    _validate_retention(profile)
    _validate_spending(profile)
    _check_capacity(capacity, roster)
    normalized = deepcopy(profile)
    normalized['profile_kind'] = profile_kind
    normalized['roster'] = roster
    return normalized


def fingerprint(profile):
    """Stable content fingerprint of a validated profile for the deployment journal."""
    normalized = validate(profile)
    body = json.dumps(normalized, sort_keys=True, separators=(',', ':')).encode()
    return hashlib.sha256(body).hexdigest()


def desired_inventory(profile):
    """Names only: no application IDs and no provider resource IDs."""
    normalized = validate(profile)
    return {
        'event': {'id': normalized['event']['id'], 'release_id': normalized['event']['release_id']},
        'provider': normalized['provider'],
        'teams': [{'name': team['name'], 'members': team['members'], 'desktop': team['desktop'],
                   'accounts': list(team['accounts'])} for team in normalized['roster']['teams']],
        'desktops': [{'name': desktop['name'], 'address': desktop['address'],
                      'shared': desktop['shared'], 'max_connections': desktop['max_connections']}
                     for desktop in normalized['desktops']],
        'addresses': dict(normalized['addresses']),
        'secret_refs': dict(normalized['secret_refs']),
        'retention': dict(normalized['retention']),
        'spending': dict(normalized['spending']),
    }


def resolve_inventory(profile, resolved):
    """Attach provisioned IDs to the desired inventory, keyed by desired name."""
    inventory = desired_inventory(profile)
    if not isinstance(resolved, dict):
        _fail('resolved', 'must be an object of resolved IDs')
    teams = resolved.get('teams', {})
    desktops = resolved.get('desktops', {})
    for team in inventory['teams']:
        entry = teams.get(team['name'])
        if not isinstance(entry, dict):
            _fail('resolved.teams.' + team['name'], 'missing resolved IDs')
        for key in ('iris_id', 'ctfd_id'):
            if entry.get(key) in (None, ''):
                _fail('resolved.teams.' + team['name'] + '.' + key, 'required')
        try:
            team['resolved'] = {'iris_id': str(entry['iris_id']), 'ctfd_id': int(entry['ctfd_id'])}
        except (TypeError, ValueError):
            _fail('resolved.teams.' + team['name'], 'iris_id/ctfd_id must be integer-like')
    for desktop in inventory['desktops']:
        entry = desktops.get(desktop['name'])
        if not isinstance(entry, dict) or entry.get('provider_id') in (None, ''):
            _fail('resolved.desktops.' + desktop['name'], 'missing resolved provider ID')
        desktop['resolved'] = {'provider_id': str(entry['provider_id'])}
    return inventory
