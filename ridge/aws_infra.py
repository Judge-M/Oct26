"""E04 - minimal AWS infrastructure plan and idempotent provisioning.

One checked-in plan describes tagged central and per-team desktop EC2 instances,
networks, security groups, encrypted storage and a narrowly scoped role. There is no
Kubernetes, NAT gateway, managed database or fabricated pricing. Live creation is
BLOCKED without AWS; the plan, command builders and idempotent journal are tested.
"""
import json
from pathlib import Path

from ridge.aws import AwsEnvironmentError

RESOURCE_ORDER = ('network', 'security_group', 'central_instance', 'desktop_instance', 'volume', 'role')


def plan(profile):
    teams = int(profile.get('teams') or 0)
    if teams < 1:
        raise ValueError('Profile must declare at least one team')
    resources = dict(network=1, security_group=2, central_instance=1,
                     desktop_instance=teams, volume=1 + teams, role=1)
    return dict(schema=1, region=profile.get('region'), teams=teams, resources=resources,
                ingress=profile.get('ingress', []), budget=profile.get('budget', {}),
                public_database=False, public_vnc=False, public_integration_api=False)


def validate(plan_document):
    for rule in plan_document.get('ingress', []):
        if rule.get('cidr') == '0.0.0.0/0' and rule.get('internal'):
            raise ValueError('Internal database/indexer/VNC port must not be public')
    for key in ('central_instance', 'desktop_instance'):
        if plan_document['resources'].get(key, 0) < 1:
            raise ValueError('Plan requires at least one ' + key)
    return plan_document


def create_command(kind, index, plan_document, event):
    tag = f'--tag-specifications ResourceType=instance,Tags=[{{Key=Event,Value={event}}}]'
    region = plan_document['region']
    if kind == 'network':
        return ['aws', 'ec2', 'create-vpc', '--cidr-block', '10.60.0.0/16', '--region', region]
    if kind == 'security_group':
        return ['aws', 'ec2', 'create-security-group', '--group-name',
                f'{event}-sg-{index:02d}', '--region', region]
    if kind == 'central_instance':
        return ['aws', 'ec2', 'run-instances', '--image-id', 'ami-central', '--count', '1',
                tag, '--region', region]
    if kind == 'desktop_instance':
        return ['aws', 'ec2', 'run-instances', '--image-id', 'ami-desktop', '--count', '1',
                tag, '--region', region]
    if kind == 'volume':
        return ['aws', 'ec2', 'create-volume', '--encrypted', '--size', '100', '--region', region]
    if kind == 'role':
        return ['aws', 'iam', 'create-role', '--role-name', f'{event}-role', '--region', region]
    raise ValueError('Unknown resource kind: ' + kind)


def _load(path):
    path = Path(path)
    if not path.is_file():
        return dict(schema=1, event=None, resources={})
    document = json.loads(path.read_text(encoding='utf-8'))
    if document.get('schema') != 1 or not isinstance(document.get('resources'), dict):
        raise ValueError('Unknown infrastructure journal schema')
    return document


def _save(document, path):
    Path(path).write_text(json.dumps(document, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def dry_run(plan_document):
    validate(plan_document)
    return dict(plan=plan_document, resources=sorted(plan_document['resources'].items()))


def create(aws, plan_document, journal_path, event):
    validate(plan_document)
    journal = _load(journal_path)
    if journal.get('event') and journal['event'] != event:
        raise ValueError('Journal belongs to a different event')
    journal['event'] = event
    for kind in RESOURCE_ORDER:
        for index in range(plan_document['resources'].get(kind, 0)):
            name = f'{kind}-{index:02d}'
            if name in journal['resources']:
                continue
            result = aws.call(*create_command(kind, index, plan_document, event))
            resource_id = result.get('id') or result.get('ResourceId') or result.get('VpcId')
            if not resource_id:
                raise ValueError('Create did not return a resource id: ' + name)
            journal['resources'][name] = dict(id=resource_id, kind=kind)
            _save(journal, journal_path)
    return journal


def inventory(journal_path):
    journal = _load(journal_path)
    resources = [dict(name=name, **record) for name, record in sorted(journal['resources'].items())]
    return dict(event=journal.get('event'), count=len(resources), resources=resources,
                retained=journal.get('retained', []))
