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
                                         'up', 'start', 'pause', 'backup', 'restore',
                                         'switch', 'down', 'fence'))
    parser.add_argument('--component', choices=(*IMAGES, 'all'), default='all')
    parser.add_argument('--work', type=Path, default=ROOT / 'work/build-receipts')
    parser.add_argument('--profile', type=Path,
                        help='validated deployment profile JSON (required for lifecycle actions)')
    parser.add_argument('--runtime', type=Path, default=ROOT / 'work/deploy-runtime',
                        help='private runtime directory (journal, secrets, env, state)')
    parser.add_argument('--operator', default='deploy', help='recorded actor for mutations')
    parser.add_argument('--from', dest='from_set', type=Path, default=None,
                        help='recovery set directory for restore')
    parser.add_argument('--degraded-ok', action='store_true',
                        help='restore only: explicitly accept skipping unreadable volume '
                             'archives (documented data loss)')
    parser.add_argument('--accept-release', default=None,
                        help='restore only: accept a recovery set built from this exact '
                             'release fingerprint and migrate its schema')
    parser.add_argument('--volumes', action='store_true',
                        help='with down: also remove event-owned volumes (destructive; '
                             'requires a completed, verified recovery set first)')
    parser.add_argument('--teams', type=int, default=None,
                        help='up only: provision N teams (1-10) with neutral accounts, '
                             'regardless of the profile roster. Recorded in the runtime; '
                             'later commands reuse it automatically')
    args = parser.parse_args()
    try:
        if args.action == 'doctor':
            print(docker('version', capture=True))
            print(docker('compose', 'version', capture=True))
            docker('info', capture=True)
            return
        lifecycle = ('up', 'start', 'pause', 'status', 'down', 'backup', 'restore', 'switch')
        if args.action == 'status' and args.profile is None:
            print(json.dumps({'event_ready': False, 'next_gate': 'profile-scoped deployment',
                              'instructions': 'docs/handoff/BUILD-FIRST.md'}))
            return
        if args.action in lifecycle:
            if args.profile is None:
                raise ValueError('--profile is required for %s; no event or resources were '
                                 'changed' % args.action)
            if args.teams is not None and args.action != 'up':
                raise ValueError('--teams is only valid with up; the chosen team count is '
                                 'stored in the runtime and applied to later commands '
                                 'automatically')
            from ridge.deploy.config import MAX_DESKTOP_SERVICES
            if args.teams is not None and not 1 <= args.teams <= MAX_DESKTOP_SERVICES:
                raise ValueError('--teams must be between 1 and %d; nothing was changed'
                                 % MAX_DESKTOP_SERVICES)
            from ridge.deploy.local import LocalStack
            from ridge.docker_provider import SubprocessRunner
            profile = json.loads(args.profile.read_text(encoding='utf-8'))
            if args.teams is not None:
                args.runtime.mkdir(parents=True, exist_ok=True)
                override = args.runtime / 'overrides.json'
                if override.is_file():
                    existing = json.loads(override.read_text(encoding='utf-8'))['team_count']
                    if existing != args.teams:
                        raise ValueError('this runtime was provisioned for %d teams; use a '
                                         'fresh --runtime directory to change the team count'
                                         % existing)
                override.write_text(json.dumps({'team_count': args.teams}) + '\n',
                                    encoding='utf-8')
            stack = LocalStack(profile, args.runtime, SubprocessRunner(),
                               operator=args.operator, receipts=args.work)
            if args.action == 'up':
                print(json.dumps(stack.up(_release_fingerprint(args.work)), indent=2))
            elif args.action == 'start':
                print(json.dumps(stack.start(_release_fingerprint(args.work)), indent=2))
            elif args.action == 'pause':
                print(json.dumps(stack.pause(), indent=2))
            elif args.action == 'status':
                print(json.dumps(stack.status(), indent=2))
            elif args.action == 'down':
                print(json.dumps(stack.down(volumes=args.volumes), indent=2))
            elif args.action == 'backup':
                print(json.dumps(stack.backup(), indent=2))
            elif args.action == 'fence':
                print(json.dumps(stack.fence(), indent=2))
            elif args.action == 'restore':
                if getattr(args, 'from_set', None):
                    from ridge.deploy import recovery
                    print(json.dumps(recovery.restore(
                        profile, args.runtime, args.from_set, SubprocessRunner(),
                        operator=args.operator, receipts=args.work,
                        release_fingerprint=_release_fingerprint(args.work),
                        degraded_ok=args.degraded_ok,
                        accept_release=args.accept_release), indent=2))
                else:
                    stack.restore()
            elif args.action == 'switch':
                stack.switch()
            return
        operation = build if args.action == 'build' else verify_build
        components = IMAGES if args.component == 'all' else (args.component,)
        for component in components:
            print(json.dumps(operation(component, args.work)))
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        parser.exit(2, str(exc) + '\n')


def _release_fingerprint(work):
    """The shared source fingerprint recorded by the image builds; all four must agree."""
    from ridge.deploy.local import IMAGE_COMPONENTS
    sources = set()
    for component in IMAGE_COMPONENTS:
        receipt = Path(work) / (component + '.json')
        if not receipt.is_file():
            raise ValueError('no build receipt for %s: run `python -m ridge.deploy build` first'
                             % component)
        sources.add(json.loads(receipt.read_text(encoding='utf-8'))['source'])
    if len(sources) != 1:
        raise ValueError('build receipts disagree on the source fingerprint; rebuild all '
                         'components so every image matches the same source')
    return sources.pop()


if __name__ == '__main__':
    main()
