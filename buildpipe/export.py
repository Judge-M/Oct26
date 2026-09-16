"""H01d - seal, compact, offline-boot, split and hash the desktop export.

Every validation field is set only from an observed result. Compaction refuses a
running or foreign guest, `seal_checks` reports exactly what it observed, and the
offline boot must print its marker before `boot_passed` is recorded. Live block-device
work requires a Linux host and raises `BuildEnvironmentError` otherwise.
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from buildpipe import BuildEnvironmentError
from buildpipe.desktop import allocate_nbd, connect_nbd, disconnect_nbd, require_linux
from ridge.artifacts import safe, sha256

BOOT_MARKER = 'SILENT_RIDGE_OFFLINE_BOOT_PASSED'
REQUIRED_SEAL_CHECKS = ('temporary_access_removed', 'ssh_host_keys_removed',
                        'machine_identity_reset', 'cloud_init_cache_removed',
                        'native_capture_present', 'prepared_case_present', 'credential_gate')


def assert_stopped(build_root, proc=Path('/proc')):
    pidfile = Path(build_root) / 'qemu.pid'
    if not pidfile.exists():
        return
    try:
        pid = int(pidfile.read_text(encoding='utf-8').strip())
    except (OSError, ValueError) as error:
        raise ValueError('Malformed qemu.pid; refusing to touch an unknown guest') from error
    if (Path(proc) / str(pid)).exists():
        raise ValueError('Build guest is still running; stop it before export')


def seal_checks(mount, expected):
    mount = Path(mount)
    checks = {
        'temporary_access_removed': not any((mount / name).exists() for name in (
            'home/builder/.ssh/authorized_keys', 'root/.ssh/authorized_keys',
            'etc/sudoers.d/90-cloud-init-users')),
        'ssh_host_keys_removed': not list((mount / 'etc/ssh').glob('ssh_host_*')),
        'cloud_init_cache_removed': not list((mount / 'var/lib/cloud/instances').glob('*')),
        'native_capture_present': (mount / expected['native_capture']).is_file(),
        'prepared_case_present': (mount / expected['prepared_case']).is_file(),
        'credential_gate': not (mount / 'etc/silent-ridge/vnc-password').exists(),
    }
    machine = mount / 'etc/machine-id'
    checks['machine_identity_reset'] = (not machine.exists()) or \
        machine.read_text(encoding='utf-8', errors='replace').strip() in ('', 'uninitialized')
    return checks


def validate_seal(checks):
    failed = sorted(name for name in REQUIRED_SEAL_CHECKS if checks.get(name) is not True)
    if failed:
        raise ValueError('Sealing checks failed: ' + ', '.join(failed))
    return checks


def compact(source, output, device=None, sys_block=Path('/sys/block')):
    source, output = Path(source), Path(output)
    if output.exists():
        raise ValueError('Choose a new compacted image; existing exports are never overwritten')
    require_linux('qemu-nbd/zerofree')
    device = device or allocate_nbd(sys_block=sys_block)
    connect_nbd(source, device)
    try:
        partition = Path(str(device) + 'p1')
        subprocess.run(['e2fsck', '-f', '-p', str(partition)], check=True)
        subprocess.run(['zerofree', str(partition)], check=True)
    finally:
        disconnect_nbd(device)
    subprocess.run(['qemu-img', 'convert', '-p', '-c', '-O', 'qcow2', str(source), str(output)], check=True)
    subprocess.run(['qemu-img', 'check', str(output)], check=True)
    return output


def split_and_hash(image, destination, version, part_limit=900 * 1024 * 1024):
    image, destination = Path(image), Path(destination)
    if destination.exists():
        raise ValueError('Choose a new release directory; existing releases are never overwritten')
    if not image.is_file():
        raise ValueError('Exported image not found: ' + str(image))
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix='.desktop-release-', dir=destination.parent))
    try:
        whole, size = hashlib.sha256(), 0
        parts = []
        with image.open('rb') as stream:
            while True:
                first = stream.read(min(1024 * 1024, part_limit))
                if not first:
                    break
                name = f'{version}.part{len(parts) + 1:03d}'
                digest, count = hashlib.sha256(), 0
                with (temporary / name).open('xb') as output:
                    block, remaining = first, part_limit
                    while block:
                        output.write(block)
                        digest.update(block)
                        whole.update(block)
                        count += len(block)
                        size += len(block)
                        remaining -= len(block)
                        block = stream.read(min(1024 * 1024, remaining)) if remaining > 0 else b''
                parts.append(dict(path=name, bytes=count, sha256=digest.hexdigest()))
        manifest = dict(schema=1, format='qcow2', version=version, bytes=size,
                        sha256=whole.hexdigest(), parts=parts, event_ready=False)
        (temporary / (version + '.json')).write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n', encoding='utf-8')
        os.replace(temporary, destination)
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return manifest


def verify_release(destination, version):
    destination = Path(destination)
    manifest = json.loads((destination / (version + '.json')).read_text(encoding='utf-8'))
    if manifest.get('version') != version or not manifest.get('parts'):
        raise ValueError('Versioned part manifest required')
    whole, size = hashlib.sha256(), 0
    for part in manifest['parts']:
        path = safe(destination, part['path'])
        if not path.is_file() or path.stat().st_size != part['bytes'] or sha256(path) != part['sha256']:
            raise ValueError('Corrupt or missing desktop part: ' + part['path'])
        with path.open('rb') as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b''):
                whole.update(block)
                size += len(block)
    if size != manifest['bytes'] or whole.hexdigest() != manifest['sha256']:
        raise ValueError('Reassembled desktop checksum mismatch')
    return manifest


def offline_boot_marker(log_text, marker=BOOT_MARKER):
    return marker in log_text


def offline_boot_command(disk, seed, log, memory_mib=8192, vcpus=4):
    return ['qemu-system-x86_64', '-enable-kvm', '-cpu', 'host', '-smp', str(vcpus),
            '-m', str(memory_mib),
            '-drive', f'file={disk},if=virtio,format=qcow2,snapshot=on',
            '-drive', f'file={seed},if=virtio,format=raw,readonly=on',
            '-netdev', 'user,id=net0,restrict=on', '-device', 'virtio-net-pci,netdev=net0',
            '-display', 'none', '-serial', f'file={log}', '-no-reboot']


def offline_boot(disk, seed, log, memory_mib=8192, vcpus=4, timeout=240):
    require_linux('offline desktop boot')
    subprocess.run(offline_boot_command(disk, seed, log, memory_mib, vcpus), check=True, timeout=timeout)
    data = Path(log).read_text(encoding='utf-8', errors='replace')
    if not offline_boot_marker(data):
        raise ValueError('Offline boot did not reach the verification marker')
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', type=Path)
    parser.add_argument('--destination', type=Path)
    parser.add_argument('--version', default='desktop-v2')
    parser.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    if args.verify:
        print(json.dumps(verify_release(args.destination, args.version), indent=2))
    else:
        print(json.dumps(split_and_hash(args.image, args.destination, args.version), indent=2))


if __name__ == '__main__':
    main()
