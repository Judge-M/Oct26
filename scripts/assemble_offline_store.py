"""Assemble the versioned offline store + release manifest for `python -m ridge.bundle`.

Reads the published large artifacts (desktop parts, native capture, prepared
case), the generated asset trees named by a runtime's `local.json`
(evidence-public, case-template, wazuh-config), and resolves immutable image
IDs from the local Docker daemon. Requires Docker on PATH and a clean git
checkout at the commit the manifest should pin. Output: `work/offline-store/`
and `work/offline-manifest.json` ready for:

    python -m ridge.bundle work/offline-store work/offline-manifest.json \\
        work/offline-bundle --allow-incomplete --max-part-bytes 2147483648
"""
import json
import shutil
import subprocess
import tarfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
def sha256(path):
    import hashlib
    d = hashlib.sha256()
    with open(path, 'rb') as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b''):
            d.update(block)
    return d.hexdigest()


def tar_tree(out, sources):
    out.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(out, 'w:gz') as tar:
        for base, arc in sources:
            tar.add(base, arcname=arc)


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--include-vm', action='store_true',
                        help='also pack the parked Hyper-V QCOW2 desktop when its parts '
                             'are materialized. Excluded by default: container desktops '
                             'are the event path and the VM is dropped from releases.')
    parser.add_argument('--store', type=Path, required=True,
                        help='empty output directory for the assembled artifact store')
    parser.add_argument('--manifest', type=Path, required=True,
                        help='output path for the offline bundle manifest')
    parser.add_argument('--evidence', type=Path, required=True,
                        help='generated evidence-public directory')
    parser.add_argument('--case-template', type=Path, required=True,
                        help='generated Autopsy case-template directory')
    parser.add_argument('--wazuh-config', type=Path, required=True,
                        help='generated Wazuh configuration directory')
    parser.add_argument('--release-vault', type=Path, required=True,
                        help='generated controller release-vault directory')
    parser.add_argument('--release', default='silent-ridge-expanded-1',
                        help='release identifier recorded in the manifest')
    parser.add_argument('--compatibility-verified', action='store_true',
                        help='mark compatibility verified only after the release gate passed')
    args = parser.parse_args()
    store = args.store.resolve()
    manifest_path = args.manifest.resolve()
    evidence = args.evidence.resolve()
    case_template = args.case_template.resolve()
    wazuh_config = args.wazuh_config.resolve()
    release_vault = args.release_vault.resolve()
    for label, path in {
        'evidence': evidence, 'case template': case_template,
        'Wazuh config': wazuh_config, 'release vault': release_vault,
    }.items():
        if not path.is_dir():
            raise SystemExit(f'{label} directory does not exist: {path}')
    if manifest_path == store or manifest_path.is_relative_to(store):
        raise SystemExit('manifest must be outside the artifact store: ' + str(manifest_path))
    inputs = (evidence, case_template, wazuh_config, release_vault)
    if any(store == path or store.is_relative_to(path) or path.is_relative_to(store)
           for path in inputs):
        raise SystemExit('store must not contain or be contained by an input directory')
    if store.exists() and (not store.is_dir() or any(store.iterdir())):
        raise SystemExit('store must be a new or empty directory: ' + str(store))
    store.mkdir(parents=True, exist_ok=True)
    artifacts = []

    def put(src, dest, kind):
        src, dest = Path(src), store / dest
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest)
        artifacts.append({'path': dest.relative_to(store).as_posix(), 'kind': kind,
                          'bytes': dest.stat().st_size, 'sha256': sha256(dest)})

    # Large published artifacts (native memory capture, prepared case).
    # The desktop QCOW2 is the parked Hyper-V path (assets/vm-desktop/, outside
    # the shipped distribution): packed only with --include-vm. Dropped from
    # releases by organizer decision — container desktops are the event path.
    desktop_manifest = json.loads((REPO / 'assets/desktop-v1.json').read_text(encoding='utf-8'))
    if args.include_vm and all((REPO / part['path']).is_file() for part in desktop_manifest['parts']):
        for part in desktop_manifest['parts']:
            put(REPO / part['path'], 'desktop/' + Path(part['path']).name, 'desktop')
    else:
        print('parked VM desktop excluded (pass --include-vm to pack it)')
    put(REPO / 'assets/large/native/WS17-native-v1.tar.gz',
        'memory/WS17-native-v1.tar.gz', 'memory')
    put(REPO / 'assets/large/autopsy/WS17-prepared-case-v2.tar.gz',
        'autopsy/WS17-prepared-case-v2.tar.gz', 'autopsy')
    put(evidence / 'disk/WS17-fat16.img', 'disk/WS17-fat16.img', 'disk')

    # Trees -> single-file artifacts.
    tar_tree(store / 'evidence/evidence-public.tar.gz', [(evidence, 'evidence-public')])
    artifacts.append({'path': 'evidence/evidence-public.tar.gz', 'kind': 'evidence',
                      'bytes': (store / 'evidence/evidence-public.tar.gz').stat().st_size,
                      'sha256': sha256(store / 'evidence/evidence-public.tar.gz')})
    tar_tree(store / 'dependencies/case-and-wazuh-config.tar.gz',
             [(case_template, 'case-template'),
              (wazuh_config, 'wazuh-config')])
    artifacts.append({'path': 'dependencies/case-and-wazuh-config.tar.gz', 'kind': 'dependencies',
                      'bytes': (store / 'dependencies/case-and-wazuh-config.tar.gz').stat().st_size,
                      'sha256': sha256(store / 'dependencies/case-and-wazuh-config.tar.gz')})
    # The release vault (follow-up evidence + manifest.json) is required by
    # local.json's release_vault; without it the first follow-up ticket fails
    # mid-event on a cold install.
    tar_tree(store / 'dependencies/release-vault.tar.gz',
             [(release_vault, 'release-vault')])
    artifacts.append({'path': 'dependencies/release-vault.tar.gz', 'kind': 'dependencies',
                      'bytes': (store / 'dependencies/release-vault.tar.gz').stat().st_size,
                      'sha256': sha256(store / 'dependencies/release-vault.tar.gz')})
    tar_tree(store / 'guides/guides.tar.gz',
             [(evidence / 'guides', 'getting-started'),
              (REPO / 'expanded/guides.md', 'beginner-guide.md'),
              (REPO / 'participants', 'participants')])
    artifacts.append({'path': 'guides/guides.tar.gz', 'kind': 'guides',
                      'bytes': (store / 'guides/guides.tar.gz').stat().st_size,
                      'sha256': sha256(store / 'guides/guides.tar.gz')})

    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True).strip()
    for a in artifacts:
        a['version'] = commit
        a['release'] = args.release
    # Resolve immutable image IDs from the local daemon at assembly time.
    tags = {
        'integration': 'silent-ridge-integration:dev', 'iris': 'silent-ridge-iris:dev',
        'ctfd': 'silent-ridge-ctfd:dev', 'desktop': 'silent-ridge-desktop:dev',
        'iris_db': 'postgres:16.8-alpine', 'guacamole_db': 'postgres:16.8-alpine',
        'ctfd_db': 'mariadb:10.11', 'ctfd_cache': 'redis:7-alpine',
        'rabbitmq': 'rabbitmq:3-management-alpine',
        'wazuh_manager': 'wazuh/wazuh-manager:4.9.2',
        'wazuh_indexer': 'wazuh/wazuh-indexer:4.9.2',
        'wazuh_dashboard': 'wazuh/wazuh-dashboard:4.9.2',
        'guacamole': 'guacamole/guacamole:1.5.5', 'guacd': 'guacamole/guacd:1.5.5',
        'participant_tls': 'nginx:alpine',
    }
    listing = subprocess.check_output(
        ['docker', 'images', '--no-trunc', '--format', '{{.Repository}}:{{.Tag}} {{.ID}}'],
        text=True).splitlines()
    by_tag = dict(line.split(' ', 1) for line in listing if line.strip())
    missing = [tag for tag in tags.values() if tag not in by_tag]
    if missing:
        raise SystemExit('images not loaded locally: ' + ', '.join(missing))
    images = {name: by_tag[tag] for name, tag in tags.items()}
    missing_gates = [] if args.compatibility_verified else [
        'ten-team capacity gate (F03)', 'dress rehearsal (F06)',
        'GHCR image publishing',
    ]
    manifest = {'schema': 1, 'release': args.release,
                'source_commit': commit,
                'compatibility_verified': args.compatibility_verified,
                'images': images, 'image_tags': dict(tags),
                'artifacts': artifacts,
                'missing': missing_gates}
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2))
    print('store:', store)
    print('manifest:', manifest_path)
    print('artifacts:', len(artifacts), 'commit:', commit[:12])


if __name__ == '__main__':
    main()
