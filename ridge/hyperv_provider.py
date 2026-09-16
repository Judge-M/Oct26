"""Local Hyper-V desktop provider: convert, clone and seed team desktops (C01).

Cross-lane note: the provider interface is specified by A04 in a parallel lane.
This module defines a narrow local protocol and is wired to the frozen provider
contract later (PENDING). It never installs anything on the host OS.

LIVE ACCEPTANCE BLOCKED: Hyper-V is unavailable on this Windows host, so no
guest boots here. Conversion is cached by source content hash (never filename);
a wrong hash or insufficient disk fails before any clone is created. Hyper-V
boot, driver and cloud-init behavior still require a real host.
"""
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable

Runner = Callable[[list[str]], None]


class ProviderError(RuntimeError):
    """Raised when the desktop provider cannot proceed; the field is named."""


def sha256_file(path) -> str:
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


@dataclass(frozen=True)
class HyperVProfile:
    base_sha256: str
    virtual_bytes: int
    vcpus: int = 4
    memory_mib: int = 8192
    switch_name: str = 'SilentRidge'
    disk_headroom_bytes: int = 20 * 1024 ** 3
    require_sha256: bool = True


@dataclass(frozen=True)
class TeamDesktop:
    team: str
    hostname: str
    admin_user: str
    admin_ssh_public_key: str
    vnc_password: str = field(repr=False)
    endpoints: dict = field(default_factory=dict)


def cache_path(cache_dir, profile: HyperVProfile) -> Path:
    if not profile.base_sha256 or len(profile.base_sha256) < 16:
        raise ProviderError('base_sha256: a full source digest is required')
    return Path(cache_dir) / ('silent-ridge-desktop-' + profile.base_sha256[:16] + '.vhdx')


def require_source(source, profile: HyperVProfile) -> Path:
    path = Path(source)
    if not path.is_file():
        raise ProviderError('source: desktop image not found at '+str(path))
    if profile.require_sha256 and sha256_file(path) != profile.base_sha256:
        raise ProviderError('base_sha256: source image does not match the verified manifest')
    return path


def require_capacity(free_bytes: int, profile: HyperVProfile, clones: int) -> int:
    if clones < 1:
        raise ProviderError('clones: at least one clone is required')
    required = profile.virtual_bytes + profile.disk_headroom_bytes
    if free_bytes < required:
        raise ProviderError('free_bytes: %d available but %d required' % (free_bytes, required))
    return required


def convert(source, profile: HyperVProfile, cache_dir, runner: Runner, free_bytes: int) -> Path:
    """Convert the verified QCOW2 to VHDX once, cached by source hash."""
    source = require_source(source, profile)
    require_capacity(free_bytes, profile, 1)
    destination = cache_path(cache_dir, profile)
    if destination.is_file():
        return destination
    Path(cache_dir).mkdir(parents=True, exist_ok=True)
    runner(['qemu-img', 'convert', '-f', 'qcow2', '-O', 'vhdx', str(source), str(destination)])
    if not destination.is_file():
        raise ProviderError('convert: qemu-img produced no output')
    return destination


def user_data(team: TeamDesktop) -> str:
    if not team.admin_ssh_public_key.startswith(('ssh-', 'ecdsa-')):
        raise ProviderError('admin_ssh_public_key: an SSH public key is required')
    if len(team.vnc_password) < 8:
        raise ProviderError('vnc_password: at least 8 characters are required')
    endpoints = json.dumps(team.endpoints, sort_keys=True)
    return '\n'.join([
        '#cloud-config',
        'hostname: '+team.hostname,
        'manage_etc_hosts: true',
        'users:',
        '  - name: '+team.admin_user,
        '    sudo: ALL=(ALL) NOPASSWD:ALL',
        '    ssh_authorized_keys:',
        '      - '+team.admin_ssh_public_key,
        'write_files:',
        '  - path: /etc/silent-ridge/vnc-password',
        '    permissions: "0600"',
        '    owner: participant:participant',
        '    content: |',
        '      '+team.vnc_password,
        '  - path: /etc/silent-ridge/endpoints.json',
        '    permissions: "0644"',
        '    content: |',
        '      '+endpoints,
        'runcmd:',
        '  - [systemctl, start, silent-ridge-desktop.service]',
        '',
    ])


def meta_data(team: TeamDesktop) -> str:
    return '\n'.join([
        'instance-id: silent-ridge-'+team.team,
        'local-hostname: '+team.hostname,
        '',
    ])


def seed_files(team: TeamDesktop) -> dict[str, str]:
    """NoCloud seed. Unique instance-id and hostname give each clone a distinct
    machine and SSH identity on first boot."""
    return {'user-data': user_data(team), 'meta-data': meta_data(team)}


def clone_commands(profile: HyperVProfile, base, team: TeamDesktop, workdir) -> list[list[str]]:
    workdir = Path(workdir)
    disk = workdir / (team.team + '.vhdx')
    seed = workdir / (team.team + '-seed.iso')
    return [
        ['qemu-img', 'create', '-f', 'vhdx', '-b', str(base), '-F', 'vhdx', str(disk)],
        ['cloud-localds', str(seed), str(workdir / (team.team + '-user-data')),
         str(workdir / (team.team + '-meta-data'))],
        ['powershell', '-NoProfile', '-Command',
         'New-VM -Name %s -MemoryStartupBytes %dMB -VHD $args[0] -SwitchName %s'
         % (team.team, profile.memory_mib, profile.switch_name)],
        ['powershell', '-NoProfile', '-Command',
         'Set-VMProcessor -VMName %s -Count %d' % (team.team, profile.vcpus)],
    ]


def provision(profile: HyperVProfile, source, cache_dir, teams: Iterable[TeamDesktop],
              workdir, runner: Runner, free_bytes: int) -> dict:
    """Convert the base disk once and create one seeded clone per team."""
    teams = list(teams)
    if not teams:
        raise ProviderError('teams: at least one team desktop is required')
    if len({team.team for team in teams}) != len(teams):
        raise ProviderError('teams: duplicate team ID')
    require_capacity(free_bytes, profile, len(teams))
    base = convert(source, profile, cache_dir, runner, free_bytes)
    inventory = {'base': str(base), 'clones': {}}
    for team in teams:
        workdir_team = Path(workdir) / team.team
        workdir_team.mkdir(parents=True, exist_ok=True)
        files = seed_files(team)
        (workdir_team / (team.team + '-user-data')).write_text(files['user-data'], encoding='utf-8')
        (workdir_team / (team.team + '-meta-data')).write_text(files['meta-data'], encoding='utf-8')
        for command in clone_commands(profile, base, team, workdir_team):
            runner(command)
        inventory['clones'][team.team] = {'disk': str(workdir_team / (team.team + '.vhdx')),
                                          'seed': str(workdir_team / (team.team + '-seed.iso')),
                                          'hostname': team.hostname, 'vcpus': profile.vcpus,
                                          'memory_mib': profile.memory_mib}
    return inventory


def probe(profile: HyperVProfile, source, inventory: dict) -> dict:
    """Read-only reconciliation: the verified base and each clone must exist."""
    require_source(source, profile)
    missing = [team for team, item in inventory.get('clones', {}).items()
               if not Path(item['disk']).is_file() or not Path(item['seed']).is_file()]
    if missing:
        raise ProviderError('clones: missing desktop artifacts for '+', '.join(sorted(missing)))
    return {'ready': True, 'clones': len(inventory['clones'])}
