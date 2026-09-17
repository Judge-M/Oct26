"""Build and verify prerequisites before any event deployment.

The full event lifecycle remains gated by the live two-team acceptance milestone.
No action here starts an event or creates cloud resources.
"""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from ridge.deploy.locking import process_lock

ROOT = Path(__file__).resolve().parents[2]
IMAGES = {
    'iris': 'deployment/expanded/Dockerfile.iris',
    'ctfd': 'deployment/expanded/Dockerfile.ctfd',
    'integration': 'deployment/expanded/Dockerfile.integration',
    'desktop': 'deployment/expanded/desktop/Dockerfile',
}


def fingerprint(root=ROOT):
    digest = hashlib.sha256()
    for folder in ('ridge', 'integrations', 'deployment/expanded/desktop'):
        for path in sorted((root / folder).rglob('*')):
            if path.is_file() and '__pycache__' not in path.parts and path.suffix != '.pyc':
                digest.update(path.relative_to(root).as_posix().encode())
                digest.update(path.read_bytes())
    for name in ('.dockerignore', *IMAGES.values()):
        digest.update((root / name).read_bytes())
    return digest.hexdigest()


def docker(*args, capture=False):
    result = subprocess.run(['docker', *args], cwd=ROOT, check=True, text=True,
                            stdout=subprocess.PIPE if capture else None, timeout=3600)
    return result.stdout.strip() if capture else None


def build(component, work):
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    with process_lock(work / 'build.lock'):
        docker('info', capture=True)
        tag = 'silent-ridge-' + component + ':dev'
        receipt = work / (component + '.json')
        receipt.unlink(missing_ok=True)  # A failed rebuild cannot leave a success receipt.
        source = fingerprint()
        docker('build', '-f', IMAGES[component], '-t', tag, '.')
        identity = docker('image', 'inspect', '--format', '{{.Id}}', tag, capture=True)
        if source != fingerprint():
            raise ValueError('Build inputs changed during build; rebuild before running')
        result = {'component': component, 'image': tag, 'image_id': identity, 'source': source}
        temporary = receipt.with_suffix('.tmp')
        temporary.write_text(json.dumps(result, indent=2))
        temporary.replace(receipt)
        return result


def verify_build(component, work):
    path = Path(work) / (component + '.json')
    if not path.is_file():
        raise ValueError('Build first: python -m ridge.deploy build --component ' + component)
    result = json.loads(path.read_text())
    if result['source'] != fingerprint():
        raise ValueError('Build inputs changed; rebuild ' + component)
    actual = docker('image', 'inspect', '--format', '{{.Id}}', result['image'], capture=True)
    if actual != result['image_id']:
        raise ValueError('Built image changed or is missing; rebuild ' + component)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('doctor', 'build', 'verify-build', 'status',
                                         'up', 'start', 'backup', 'restore', 'switch', 'down'))
    parser.add_argument('--component', choices=(*IMAGES, 'all'), default='all')
    parser.add_argument('--work', type=Path, default=ROOT / 'work/build-receipts')
    args = parser.parse_args()
    try:
        if args.action == 'doctor':
            print(docker('version', capture=True))
            print(docker('compose', 'version', capture=True))
            docker('info', capture=True)
            return
        if args.action == 'status':
            print(json.dumps({'event_ready': False, 'next_gate': 'live two-team acceptance',
                              'instructions': 'docs/handoff/BUILD-FIRST.md'}))
            return
        if args.action not in ('build', 'verify-build'):
            raise ValueError('Event lifecycle is not accepted yet. Follow docs/handoff/NEXT.md; '
                             'no event or resources were changed.')
        operation = build if args.action == 'build' else verify_build
        components = IMAGES if args.component == 'all' else (args.component,)
        for component in components:
            print(json.dumps(operation(component, args.work)))
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        parser.exit(2, str(exc) + '\n')


if __name__ == '__main__':
    main()
