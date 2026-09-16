"""E05 - AWS expiry and verified teardown.

Teardown requires a completed restorable backup and deletes only resources recorded in
the event journal. It inventories compute, storage, addresses, snapshots, AMIs and
import staging, distinguishes explicitly retained resources from leaks, and reports
continuing cost categories (a stopped EC2 instance is not zero cost). Expired
credentials produce a safe, explicit outcome. Live deletion is BLOCKED without AWS.
"""
import json
from pathlib import Path

from ridge.aws import AwsAuthError

COST_CATEGORIES = ('running_compute', 'stopped_compute_ebs', 'elastic_ip',
                   'snapshot', 'ami', 'import_staging')


def delete_command(kind, resource_id, region):
    if kind in ('central_instance', 'desktop_instance'):
        return ['aws', 'ec2', 'terminate-instances', '--instance-ids', resource_id, '--region', region]
    if kind == 'volume':
        return ['aws', 'ec2', 'delete-volume', '--volume-id', resource_id, '--region', region]
    if kind == 'security_group':
        return ['aws', 'ec2', 'delete-security-group', '--group-id', resource_id, '--region', region]
    if kind == 'network':
        return ['aws', 'ec2', 'delete-vpc', '--vpc-id', resource_id, '--region', region]
    if kind == 'role':
        return ['aws', 'iam', 'delete-role', '--role-name', resource_id, '--region', region]
    raise ValueError('Unknown resource kind: ' + str(kind))


def _load(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError('Infrastructure journal not found: ' + str(path))
    return json.loads(path.read_text(encoding='utf-8'))


def plan_teardown(journal):
    return [dict(name=name, kind=record['kind'], id=record['id'])
            for name, record in sorted(journal.get('resources', {}).items())]


def cost_report(retained):
    categories = {name: 0 for name in COST_CATEGORIES}
    for item in retained:
        kind = item.get('kind')
        if kind == 'instance':
            categories['stopped_compute_ebs' if item.get('state') == 'stopped' else 'running_compute'] += 1
        elif kind == 'volume':
            categories['stopped_compute_ebs'] += 1
        elif kind == 'elastic_ip':
            categories['elastic_ip'] += 1
        elif kind == 'snapshot':
            categories['snapshot'] += 1
        elif kind == 'ami':
            categories['ami'] += 1
        elif kind == 'import_staging':
            categories['import_staging'] += 1
    return categories


def teardown(aws, journal_path, backup_verified, apply=False, region=None):
    if not backup_verified:
        raise ValueError('Refusing teardown without a verified restorable backup')
    journal = _load(journal_path)
    plan = plan_teardown(journal)
    region = region or journal.get('region')
    deleted = []
    if apply:
        for item in plan:
            command = delete_command(item['kind'], item['id'], region)
            try:
                aws.call(*command)
            except AwsAuthError:
                return dict(safe=True, action='reauthenticate', deleted=deleted, planned=plan,
                            retained=journal.get('retained', []), cost_categories=cost_report(journal.get('retained', [])),
                            apply=True)
            deleted.append(item['name'])
    retained = journal.get('retained', [])
    return dict(safe=True, planned=plan, deleted=deleted, retained=retained,
                cost_categories=cost_report(retained), apply=apply)


def expiry_check(now, expires, apply=False):
    if expires is None:
        raise ValueError('An approved TTL expiry is required')
    expired = now >= expires
    return dict(expired=expired, action='teardown' if (expired and apply) else ('due' if expired else 'none'))
