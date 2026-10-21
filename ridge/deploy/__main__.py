"""Build and verify prerequisites before any event deployment.

The full event lifecycle remains gated by the live two-team acceptance milestone.
No action here starts an event or creates cloud resources.
"""
import argparse
import hashlib
import json
import os
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
    for folder in ('ridge', 'integrations', 'deployment/expanded/desktop',
                   'deployment/expanded/wazuh'):
        for path in sorted((root / folder).rglob('*')):
            if path.is_file() and '__pycache__' not in path.parts and path.suffix != '.pyc':
                digest.update(path.relative_to(root).as_posix().encode())
                digest.update(path.read_bytes())
    for name in ('.dockerignore', 'bounded_http.py', *IMAGES.values()):
        digest.update((root / name).read_bytes())
    return digest.hexdigest()


def docker(*args, capture=False):
    result = subprocess.run(['docker', *args], cwd=ROOT, check=True, text=True,
                            stdout=subprocess.PIPE if capture else None, timeout=3600)
    return result.stdout.strip() if capture else None


def base_images(dockerfile):
    """Base images a Dockerfile builds FROM, in order, deduplicated.

    Read from the Dockerfile rather than a hardcoded list so a new base image
    cannot silently escape the check in build(). Resolves the FROM forms that
    are not a registry reference: a leading ``--flag=value``, a build stage
    alias, and the reserved empty ``scratch``. A base built from a build
    argument cannot be resolved statically and comes back as unresolved.
    """
    images = []
    stages = set()
    unresolved = []
    for line in (ROOT / dockerfile).read_text(encoding='utf-8').splitlines():
        parts = line.strip().split()
        if not parts or parts[0].upper() != 'FROM':
            continue
        parts = [p for p in parts[1:] if not p.startswith('--')]
        if not parts:
            continue
        image = parts[0]
        if len(parts) > 2 and parts[1].upper() == 'AS':
            stages.add(parts[2])
        if image == 'scratch' or image in stages:
            continue
        if '$' in image:
            unresolved.append(image)
            continue
        if image not in images:
            images.append(image)
    return images, unresolved


def _registry_repository(image):
    """Canonical registry repository of a FROM reference, without tag or digest.

    Mirrors Docker's own normalization: an unqualified name lives under
    ``docker.io/library``, a single-path name under ``docker.io``, and only a
    first component containing a dot or a port counts as an explicit registry.
    ``docker image inspect`` reports RepoDigests only in canonical form, so
    matching without normalizing would reject every legitimately cached base.
    """
    ref = image.split('@', 1)[0]
    last = ref.rsplit('/', 1)[-1]
    if ':' in last:
        ref = ref.rsplit(':', 1)[0]
    if '/' not in ref:
        return 'docker.io/library/' + ref
    head = ref.split('/', 1)[0]
    if '.' not in head and ':' not in head:
        return 'docker.io/' + ref
    return ref


def registry_digest_for(image, details):
    """The recorded registry pull digest of ``image``'s repository, or None.

    An image pulled from a registry carries a ``<repo>@sha256:...`` RepoDigest.
    A locally built image has none at all, and a foreign image re-tagged over
    the base name carries only the foreign repository's digest — so a missing
    digest for this exact repository means the tag no longer points at a pulled
    image. That is the overwrite failure mode of issue #184. A digest-pinned
    FROM cannot be re-tagged over (docker refuses digest targets), so it is
    exempt from the check.

    Docker Desktop may report the digest under an equivalent Docker Hub
    spelling of the same repository (``ctfd/ctfd@sha256:...`` or
    ``library/ubuntu@sha256:...`` instead of the canonical
    ``docker.io/...`` form), so both sides are run through
    ``_registry_repository`` before comparing. This also handles
    docker/containerd versions that record Docker Hub official images under
    their short repository (``ubuntu@sha256:...`` instead of
    ``docker.io/library/ubuntu@sha256:...``). Normalization is exact at the
    repository-path level: a digest from a genuinely different repository or
    registry still proves nothing here.
    """
    if '@' in image:
        return ''
    expected = _registry_repository(image)
    for digest in details.get('RepoDigests') or []:
        if _registry_repository(digest) == expected:
            return digest
    return None


def verify_base_cache(bases):
    """Inspect the local Docker cache for each base; return (problems, uncached).

    ``problems`` names every cached base whose image is not a registry pull of
    that repository, with the cached image id and the ``docker rmi`` remedy.
    Issue #184: a previous build that saved its finished image over a base tag
    made ``--pull=false`` start from a polluted base; the real cause surfaced
    hundreds of build steps later as a misleading Dockerfile error. An
    unparseable inspect output is reported loudly but does not block the
    build: it points at broken tooling, not at a polluted cache.
    """
    problems = []
    uncached = []
    unverifiable = []
    for base in bases:
        try:
            details = json.loads(docker('image', 'inspect', base, capture=True))
        except (OSError, subprocess.SubprocessError):
            uncached.append(base)
            continue
        except ValueError:
            unverifiable.append(base)
            continue
        detail = details[0] if isinstance(details, list) and details else None
        if not isinstance(detail, dict):
            unverifiable.append(base)
            continue
        if registry_digest_for(base, detail) is None:
            image_id = str(detail.get('Id', '?'))
            short_id = image_id[:19] if image_id.startswith('sha256:') else image_id[:12]
            carried = sorted(detail.get('RepoDigests') or [])
            carried = ('it carries registry digests ' + ', '.join(carried)) if carried \
                else 'it carries no registry digests at all'
            problems.append(
                'cached base image %s is not a registry pull: it resolves to local '
                'image %s, and %s, so the tag %s was overwritten by a local build or '
                'retag (issue #184). Building on it would silently bake the wrong base '
                'into the result; the Dockerfile is not at fault. Fix: `docker rmi %s` '
                'then re-run the build so Docker re-pulls the pristine base'
                % (base, short_id, carried, base, base))
    if unverifiable:
        print('Note: could not verify cache provenance for cached base image(s): '
              + ', '.join(unverifiable) + '. The docker inspect output was unreadable; '
              'the build will proceed, but a polluted base tag would not be detected.')
    return problems, uncached


def build(component, work):
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    with process_lock(work / 'build.lock'):
        docker('info', capture=True)
        tag = 'silent-ridge-' + component + ':dev'
        receipt = work / (component + '.json')
        receipt.unlink(missing_ok=True)  # A failed rebuild cannot leave a success receipt.
        source = fingerprint()
        # Source builds are preparation-host operations. Even with every base
        # image cached, Dockerfile RUN steps may download operating-system
        # packages and pinned tool archives. ``--pull=false`` only prefers a
        # cached base image; it is not an offline or air-gap control. Event hosts
        # use the complete offline bundle and do not run this command.
        print('Note: source builds are online preparation-host operations and may '
              'download packages or tool archives. --pull=false only prefers cached '
              'base images; it does not make this build offline. Air-gapped event '
              'hosts must install the complete offline bundle instead.')
        bases, unresolved = base_images(IMAGES[component])
        problems, uncached = verify_base_cache(bases)
        for base in unresolved:
            print('Note: base image ' + base + ' comes from a build argument; '
                  'its cache state cannot be checked before the build.')
        if uncached:
            print('Note: base image(s) not cached locally: ' + ', '.join(uncached)
                  + '. The online preparation host will also need registry access.')
        if problems:
            raise ValueError('; '.join(problems))
        docker('build', '--pull=false', '-f', IMAGES[component], '-t', tag, '.')
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


def doctor(profile_path=None, runtime=None, work=None):
    """Read-only host and deployment checks; never create runtime state.

    ``ready_for_up`` answers only whether the inputs to ``up`` are sound.
    ``recovery_ready`` reports backup/restore key availability separately:
    RIDGE_BACKUP_KEY gates backup and restore, never ``up``, so a first
    deployment is legitimately ready without it. Folding the key into
    ``ready_for_up`` reported a false blocker and taught operators to
    disregard the headline result.
    """
    checks = {}
    for name, command in (('docker', ('version',)),
                          ('compose', ('compose', 'version')),
                          ('engine', ('info',))):
        try:
            docker(*command, capture=True)
            checks[name] = {'ok': True}
        except (OSError, subprocess.SubprocessError) as exc:
            checks[name] = {'ok': False, 'error': str(exc)[:300]}
    if profile_path is not None:
        from ridge.deploy.local import LocalStack
        from ridge.docker_provider import SubprocessRunner
        try:
            profile = json.loads(Path(profile_path).read_text(encoding='utf-8'))
            stack = LocalStack(profile, runtime, SubprocessRunner(), receipts=work)
            checks['profile'] = {'ok': True, 'event': stack.event}
            try:
                checks['artifacts'] = {'ok': True, 'detail': stack._probe_artifacts()}
            except Exception as exc:
                checks['artifacts'] = {'ok': False, 'error': str(exc)[:1000]}
            if (stack.runtime / 'deploy-journal.sqlite').is_file():
                status = stack.status()
                checks['live'] = {'ok': status['event_ready'], 'journal': status['journal'],
                                  'stages': {name: row.get('error', 'ok')
                                             for name, row in status['live'].items()}}
            else:
                checks['live'] = {'ok': False, 'detail': 'not deployed yet; run up'}
        except (OSError, ValueError, RuntimeError, KeyError) as exc:
            checks['profile'] = {'ok': False, 'error': str(exc)[:1000]}
        checks['backup_key'] = {
            'ok': len(os.environ.get('RIDGE_BACKUP_KEY', '')) >= 16,
            'detail': 'RIDGE_BACKUP_KEY is required for backup and restore (at least 16 characters); keep it outside the runtime and recovery set',
        }
    return {'scope': 'deployment' if profile_path is not None else 'docker-only',
            'checks': checks,
            'ready_for_up': all(row['ok'] for name, row in checks.items()
                                if name not in ('live', 'backup_key')),
            'recovery_ready': checks.get('backup_key', {}).get('ok', False),
            'event_ready': checks.get('live', {}).get('ok', False)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('doctor', 'build', 'verify-build', 'status',
                                         'up', 'start', 'pause', 'backup', 'restore',
                                         'switch', 'down', 'fence', 'registration-worker',
                                         'registration-status', 'registration-open',
                                         'registration-close', 'registration-retry',
                                         'registration-cancel', 'registration-rotate-link'))
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
    parser.add_argument('--registration-id', type=int, default=None,
                        help='registration retry/cancel/rotate-link target')
    args = parser.parse_args()
    try:
        if args.action == 'doctor':
            print(json.dumps(doctor(args.profile, args.runtime, args.work), indent=2))
            return
        lifecycle = ('up', 'start', 'pause', 'status', 'down', 'backup', 'restore', 'switch',
                     'fence', 'registration-worker', 'registration-status',
                     'registration-open', 'registration-close', 'registration-retry',
                     'registration-cancel', 'registration-rotate-link')
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
            if args.action == 'registration-worker':
                stack.registration_loop()
            elif args.action == 'up':
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
            elif args.action.startswith('registration-'):
                registration_action = args.action.removeprefix('registration-')
                print(json.dumps(stack.registration_admin(
                    registration_action, args.registration_id), indent=2))
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
