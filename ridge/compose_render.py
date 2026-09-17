"""Render and audit a run-scoped central Compose environment (B04).

Cross-lane note: the private deployment profile schema is owned by A03/A04 in a
parallel lane. This module accepts an explicit ``RunProfile`` and is wired to a
profile only after that contract freezes (PENDING). It never emits secret
material: secrets are file references resolved by Compose.

``docker compose config`` cannot run on this Windows host, so ``audit`` checks
the parsed Compose documents for the invariants the acceptance requires.
"""
import re
from dataclasses import dataclass, field
from typing import Any

PRIVATE_PORTS = {8091, 9200, 9300, 5432, 3306, 6379, 5901}
LOOPBACK = '127.0.0.1'


class ComposeError(ValueError):
    """Raised when a run profile or Compose document violates an invariant."""


def slug(event: str) -> str:
    value = re.sub(r'[^a-z0-9-]+', '-', (event or '').strip().lower()).strip('-')
    value = re.sub(r'-{2,}', '-', value)
    if not value or len(value) > 40 or not re.fullmatch(r'[a-z][a-z0-9-]*', value):
        raise ComposeError('event: a lowercase slug of at most 40 characters is required')
    return value


@dataclass(frozen=True)
class RunProfile:
    event: str
    release: str
    bind_ip: str = LOOPBACK
    state_dir: str = ''
    release_vault: str = ''
    evidence_public: str = ''
    ca_file: str = ''
    iris_port: int = 8081
    ctfd_port: int = 8083
    guac_port: int = 8082
    wazuh_port: int = 8443
    extra_env: dict[str, str] = field(default_factory=dict)


def names(profile: RunProfile) -> dict[str, Any]:
    project = slug(profile.event)
    return {
        'project': project,
        'central_network': project + '-central',
        'desktop_network': project + '-desktop',
        'volumes': {name: '%s-%s' % (project, name) for name in (
            'iris-downloads', 'iris-templates', 'iris-data', 'iris-db',
            'ctfd-db', 'ctfd-uploads', 'ctfd-logs', 'guacamole-database',
            'wazuh-indexer-data', 'wazuh-manager-data')},
    }


def render_env(profile: RunProfile) -> dict[str, str]:
    """Environment for the Compose files. Secret *file paths* only, never values."""
    if profile.bind_ip not in (LOOPBACK, '127.0.0.1') and not profile.bind_ip.startswith(('10.', '192.168.', '172.')):
        raise ComposeError('bind_ip: participant-facing bind must be loopback or a private address')
    resolved = names(profile)
    for field_name in ('state_dir', 'release_vault', 'evidence_public', 'ca_file'):
        if not getattr(profile, field_name):
            raise ComposeError(field_name + ': a private path is required')
    env = {
        'RIDGE_PROJECT': resolved['project'],
        'RIDGE_RELEASE': profile.release,
        'BIND_IP': profile.bind_ip,
        'RIDGE_CENTRAL_NETWORK': resolved['central_network'],
        'RIDGE_DESKTOP_NETWORK': resolved['desktop_network'],
        'RIDGE_STATE_DIR': profile.state_dir,
        'RIDGE_RELEASE_VAULT': profile.release_vault,
        'RIDGE_EVIDENCE_PUBLIC': profile.evidence_public,
        'WAZUH_CA_FILE': profile.ca_file,
        'IRIS_PORT': str(profile.iris_port),
        'CTFD_PORT': str(profile.ctfd_port),
        'GUAC_PORT': str(profile.guac_port),
        'WAZUH_DASHBOARD_PORT': str(profile.wazuh_port),
    }
    env.update(profile.extra_env)
    return env


def audit(document: dict[str, Any], filename: str = 'compose') -> list[str]:
    """Return a list of invariant violations for one parsed Compose document."""
    problems: list[str] = []
    if not str(document.get('name', '')).startswith('${RIDGE_PROJECT'):
        problems.append(filename + ': top-level name must be run-scoped via ${RIDGE_PROJECT}')
    for service_name, service in (document.get('services') or {}).items():
        if service.get('privileged'):
            problems.append(filename + ': service %s must not be privileged' % service_name)
        for port in service.get('ports') or []:
            text = str(port)
            if ':' not in text:
                continue
            published = int(text.rsplit(':', 1)[-1].split('/')[0])
            if published in PRIVATE_PORTS and '${BIND_IP' not in text and LOOPBACK not in text:
                problems.append(filename + ': service %s must bind private port %s through BIND_IP'
                                % (service_name, published))
        if not service.get('logging'):
            problems.append(filename + ': service %s lacks bounded log rotation' % service_name)
    return problems


if __name__ == '__main__':
    import argparse
    import json
    from pathlib import Path
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--event', required=True)
    parser.add_argument('--release', required=True)
    parser.add_argument('--state-dir', required=True)
    parser.add_argument('--release-vault', required=True)
    parser.add_argument('--evidence-public', required=True)
    parser.add_argument('--ca-file', required=True)
    parser.add_argument('--out', type=Path, required=True)
    arguments = parser.parse_args()
    profile = RunProfile(event=arguments.event, release=arguments.release, state_dir=arguments.state_dir,
                         release_vault=arguments.release_vault, evidence_public=arguments.evidence_public,
                         ca_file=arguments.ca_file)
    arguments.out.write_text('\n'.join('%s=%s' % item for item in render_env(profile).items()) + '\n',
                             encoding='utf-8')
    print(json.dumps(names(profile), indent=2))
