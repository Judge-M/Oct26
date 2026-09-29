import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ridge.deploy import Journal, LockError
from ridge.deploy.__main__ import verify_build

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
