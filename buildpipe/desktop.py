"""H01c - prepare the disposable desktop build guest.

Provides an explicit guest provider, a configurable build root, verified base/tool
inputs, freshly generated credentials and the generic-kernel/NoCloud/Solr fixes. Live
operations require a Linux host with qemu/nbd and raise `BuildEnvironmentError`
otherwise; no stage assumes `/dev/nbd0` is free.
"""
import argparse
import json
import os
import secrets
import shutil
import subprocess
from pathlib import Path

from buildpipe import BuildEnvironmentError
from ridge.artifacts import safe, sha256

GENERIC_KERNEL = '6.8.0-139-generic'
DATASOURCE_LIST = 'datasource_list: [ NoCloud, Ec2, None ]\n'


def require_commands(*names):
    missing = [name for name in names if shutil.which(name) is None]
    if missing:
        raise BuildEnvironmentError('Missing required build tool(s): ' + ', '.join(missing))


def require_linux(capability='qemu/nbd', commands=()):
    if os.name != 'posix':
        raise BuildEnvironmentError(f'{capability} requires a Linux build host')
    require_commands(*commands)


def verify_inputs(root, expected):
    root = Path(root)
    verified = {}
    for name, digest in expected.items():
        path = safe(root, name)
        if not path.is_file() or sha256(path) != digest:
            raise ValueError('Verified input missing or changed: ' + name)
        verified[name] = digest
    return verified


def allocate_nbd(sys_block=Path('/sys/block'), device_root=Path('/dev')):
    sys_block, device_root = Path(sys_block), Path(device_root)
    devices = []
    for entry in sorted(sys_block.glob('nbd*'), key=lambda path: int(path.name[3:])):
        if not entry.is_dir() or (entry / 'pid').exists():
            continue
        holders = entry / 'holders'
        if holders.is_dir() and any(holders.iterdir()):
            continue
        devices.append(device_root / entry.name)
    if not devices:
        raise ValueError('No free NBD device; disconnect an export or wait for it')
    return devices[0]


def connect_nbd(image, device, read_only=False):
    require_linux('qemu-nbd', ('qemu-nbd',))
    command = ['qemu-nbd']
    if read_only:
        command.append('--read-only')
    command.append('--connect=' + str(device))
    command.append(str(image))
    subprocess.run(command, check=True)


def disconnect_nbd(device):
    require_linux('qemu-nbd', ('qemu-nbd',))
    subprocess.run(['qemu-nbd', '--disconnect', str(device)], check=True)


def generic_boot_files(kernel=GENERIC_KERNEL):
    return {
        'etc/default/grub.d/99-silent-ridge.cfg':
            "GRUB_DEFAULT='Advanced options for Ubuntu>Ubuntu, with Linux " + kernel + "'\nGRUB_TIMEOUT=1\n",
        'etc/cloud/cloud.cfg.d/99-silent-ridge-datasources.cfg': DATASOURCE_LIST,
    }


def solr_environment(home):
    home = Path(home)
    return {'SOLR_LOGS_DIR': str(home / '.local/state/autopsy-solr/logs'),
            'SOLR_PID_DIR': str(home / '.local/state/autopsy-solr')}


def new_credential(path):
    path = Path(path)
    if path.exists():
        raise ValueError('Credential already exists; generate a fresh one: ' + str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    secret = secrets.token_urlsafe(32)
    path.write_text(secret + '\n', encoding='utf-8')
    if os.name == 'posix':
        os.chmod(path, 0o600)
    return path


def guest_command(build_root, memory_mib=8192, vcpus=4, ssh_port=2222):
    build_root = Path(build_root)
    return ['qemu-system-x86_64', '-enable-kvm', '-cpu', 'host', '-smp', str(vcpus),
            '-m', str(memory_mib),
            '-drive', f'file={build_root}/desktop-build.qcow2,if=virtio,format=qcow2',
            '-drive', f'file={build_root}/seed.img,if=virtio,format=raw,readonly=on',
            '-netdev', f'user,id=net0,hostfwd=tcp:127.0.0.1:{ssh_port}-:22',
            '-device', 'virtio-net-pci,netdev=net0', '-display', 'none',
            '-serial', f'file={build_root}/console.log', '-daemonize',
            '-pidfile', f'{build_root}/qemu.pid']


def start_guest(build_root, memory_mib=8192, vcpus=4, ssh_port=2222):
    require_linux('qemu-system-x86_64', ('qemu-system-x86_64',))
    build_root = Path(build_root)
    if (build_root / 'qemu.pid').exists():
        raise ValueError('Build guest is already running under this build root')
    build_root.mkdir(parents=True, exist_ok=True)
    subprocess.run(guest_command(build_root, memory_mib, vcpus, ssh_port), check=True)


def copy_inputs(root, files):
    root = Path(root)
    for relative, source in files.items():
        target = safe(root, relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    return root


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build-root', required=True, type=Path)
    parser.add_argument('--inputs', type=Path, help='JSON mapping of verified input path to sha256')
    args = parser.parse_args()
    if args.inputs:
        print(json.dumps(verify_inputs(args.build_root, json.loads(args.inputs.read_text(encoding='utf-8'))), indent=2))
    else:
        print(json.dumps(generic_boot_files(), indent=2))


if __name__ == '__main__':
    main()
