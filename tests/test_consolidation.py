import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ridge.deploy import Journal, LockError
from ridge.deploy.__main__ import IMAGES, base_images, build, verify_build

ROOT = Path(__file__).resolve().parents[1]


class ConsolidationTests(unittest.TestCase):
    def test_elapsed_wall_clock_cannot_steal_a_live_lock(self):
        profile = json.loads((ROOT / 'deployment/profiles/example-two-team.json').read_text())
        with tempfile.TemporaryDirectory() as temp:
            journal = Journal.create(Path(temp) / 'journal.sqlite', profile, 'v1', 'digest')
            with journal.lock('first'):
                with patch('time.time', return_value=99999999999):
                    with self.assertRaises(LockError):
                        with journal.lock('second', timeout=0):
                            self.fail('live lock was stolen')

    def test_process_exit_releases_lock(self):
        with tempfile.TemporaryDirectory() as temp:
            lock = Path(temp) / 'lock'
            script = ('from ridge.deploy.locking import process_lock; import os; '
                      'lock=process_lock(' + repr(str(lock)) + '); lock.__enter__(); os._exit(0)')
            subprocess.run([sys.executable, '-c', script], cwd=ROOT, check=True, timeout=15)
            from ridge.deploy.locking import process_lock
            with process_lock(lock, timeout=0):
                pass

    def test_no_module_package_collision_and_no_unsafe_lifecycle(self):
        self.assertFalse((ROOT / 'ridge/deploy.py').exists())
        for action in ('--help', 'up', 'start', 'backup', 'restore', 'switch', 'down'):
            result = subprocess.run([sys.executable, '-m', 'ridge.deploy', action], cwd=ROOT,
                                    capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0 if action == '--help' else 2)
            if action != '--help':
                self.assertIn('no event or resources were changed', result.stderr)

    def test_online_build_prefers_cached_base_without_claiming_offline(self):
        """Cache preference must not be presented as an air-gap control.

        Dockerfiles download packages and tool archives in RUN steps even when
        their base images are cached. The build command therefore describes the
        online preparation-host contract and directs event hosts to the bundle.
        """
        calls = []
        notes = []

        def recorder(*args, **kwargs):
            calls.append(list(args))
            return 'sha256:built'

        with tempfile.TemporaryDirectory() as temp:
            with patch('ridge.deploy.__main__.docker', side_effect=recorder), \
                    patch('ridge.deploy.__main__.fingerprint', return_value='fp'), \
                    patch('builtins.print', side_effect=notes.append):
                build('ctfd', Path(temp))

        build_argv = next(c for c in calls if c[0] == 'build')
        self.assertIn('--pull=false', build_argv)
        # --pull with no value is the spelling that forces the pull this path
        # exists to avoid, so it must not appear on its own in any argv.
        for argv in calls:
            self.assertNotIn('--pull', argv)
            self.assertNotIn('manifest', argv)
            self.assertNotIn('search', argv)
        self.assertTrue(any('online preparation-host' in note for note in notes), notes)
        self.assertTrue(any('does not make this build offline' in note for note in notes),
                        notes)
        self.assertTrue(any('complete offline bundle' in note for note in notes), notes)

    def test_build_warns_but_still_builds_when_a_base_is_not_cached(self):
        """A first build on a cold host legitimately has to fetch its base.

        An earlier version of this precheck refused instead, which made a
        first build impossible and turned the desktop-build workflow red on
        every clean CI runner. The uncached case is a preparation-host build:
        warn, keep --pull=false, and let it proceed.
        """
        cached = 'ctfd/ctfd:3.7.7'
        calls = []
        notes = []

        def recorder(*args, **kwargs):
            argv = list(args)
            calls.append(argv)
            if argv[:2] == ['image', 'inspect'] and argv[2] == cached:
                raise subprocess.CalledProcessError(1, 'docker')
            return 'sha256:built'

        with tempfile.TemporaryDirectory() as temp:
            with patch('ridge.deploy.__main__.docker', side_effect=recorder), \
                    patch('ridge.deploy.__main__.fingerprint', return_value='fp'), \
                    patch('builtins.print', side_effect=notes.append):
                result = build('ctfd', Path(temp))
            built = [c for c in calls if c[0] == 'build']
            receipt = Path(temp) / 'ctfd.json'
            receipt_exists = receipt.exists()

        self.assertTrue(built, 'must still build')
        self.assertEqual(result['image_id'], 'sha256:built')
        self.assertTrue(receipt_exists, 'writes a receipt')
        self.assertTrue(any(cached in note for note in notes), notes)
        self.assertTrue(any('preparation host' in note for note in notes), notes)
        self.assertTrue(any('complete offline bundle' in note for note in notes), notes)

    def test_base_images_resolves_non_registry_from_forms(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'Dockerfile.probe'
            path.write_text('\n'.join([
                '# FROM commented:out:should-not-appear',
                'FROM --platform=linux/amd64 ubuntu:24.04 AS builder',
                'FROM builder AS middle',
                'FROM scratch',
                'ARG BASE',
                'FROM ${BASE}',
                'RUN echo "FROM not:a:base"',
                'FROM debian:bookworm',
            ]) + '\n', encoding='utf-8')
            # ROOT-relative is how build() calls it, so probe the parser
            # directly with the same shape rather than a synthetic path.
            import ridge.deploy.__main__ as deploy_main
            original = deploy_main.ROOT
            deploy_main.ROOT = Path(temp)
            try:
                images, unresolved = deploy_main.base_images('Dockerfile.probe')
            finally:
                deploy_main.ROOT = original
        # The --platform flag is not mistaken for an image; the stage alias and
        # scratch are not registry refs; the build-arg base is reported rather
        # than silently dropped.
        self.assertEqual(images, ['ubuntu:24.04', 'debian:bookworm'])
        self.assertEqual(unresolved, ['${BASE}'])

    def test_base_images_are_read_from_the_dockerfile(self):
        self.assertEqual(base_images('deployment/expanded/Dockerfile.ctfd'),
                         (['ctfd/ctfd:3.7.7'], []))
        # Multi-stage: the repeated base is deduplicated and "AS name" ignored.
        self.assertEqual(base_images('deployment/expanded/desktop/Dockerfile'),
                         (['ubuntu:24.04'], []))
        for component, dockerfile in IMAGES.items():
            self.assertTrue(base_images(dockerfile)[0], component)

    def test_run_requires_successful_build_of_current_inputs_and_image(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, 'Build first'):
                verify_build('desktop', temp)
            receipt = Path(temp) / 'desktop.json'
            receipt.write_text(json.dumps({'source': 'old', 'image': 'desktop', 'image_id': 'sha256:old'}))
            with patch('ridge.deploy.__main__.fingerprint', return_value='new'):
                with self.assertRaisesRegex(ValueError, 'inputs changed'):
                    verify_build('desktop', temp)
            with patch('ridge.deploy.__main__.fingerprint', return_value='old'), \
                    patch('ridge.deploy.__main__.docker', return_value='sha256:new'):
                with self.assertRaisesRegex(ValueError, 'image changed'):
                    verify_build('desktop', temp)

    def test_case_seed_preserves_work_and_rejects_changed_template(self):
        import hashlib
        spec = importlib.util.spec_from_file_location('seed_case', ROOT / 'deployment/expanded/desktop/seed-case.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            template = root / 'template'
            template.mkdir()
            for name in ('WS17.aut', 'autopsy.db'):
                (template / name).write_bytes(b'isolated unit fixture')
            files = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in template.iterdir()}
            (template / '.template.json').write_text(json.dumps({'archive': 'v1', 'files': files}))
            module.seed(template, root / 'Cases')
            work = root / 'Cases/WS17/notes.txt'
            work.write_text('participant work')
            module.seed(template, root / 'Cases')
            self.assertEqual(work.read_text(), 'participant work')
            (template / 'WS17.aut').write_text('corrupt')
            with self.assertRaisesRegex(ValueError, 'checksum'):
                module.seed(template, root / 'Cases')
            self.assertEqual(work.read_text(), 'participant work')


if __name__ == '__main__':
    unittest.main()
