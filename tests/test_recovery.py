import json
import tempfile
import unittest
from pathlib import Path

from ridge.recovery import Source, backup, restore, verify
from ridge.state import State


def make_state(root):
    state = State(Path(root) / 'state.sqlite', retry_delay=0)
    teams = [dict(id='team-01', iris='101', ctfd=1, name='Team 01')]
    ticket = dict(id='T01', title='Title', subject='general', requires=[], release_files=[],
                  questions=[dict(id='T01-Q1', prompt='q', answer='a',
                                  finding=dict(text='f', evidence=['ref'], limitation='scope'))])
    state.initialize(teams, [ticket])
    with state.transaction() as con:
        con.execute('UPDATE outbox SET done=1')
    return state


class RecoverySetTests(unittest.TestCase):
    def test_backup_restore_roundtrip(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            state = make_state(root)
            source_file = root / 'iris.dump'
            source_file.write_bytes(b'application database fixture')
            secret_file = root / 'bridge.secret'
            secret_file.write_bytes(b'top secret material')
            manifest = backup(state, root / 'recovery', 'v1.0.0',
                              sources=[Source('iris.dump', 'iris_db', source_file)],
                              secrets=[Source('bridge.secret', 'secret', secret_file)],
                              encryptor=lambda data: data[::-1], key_reference='organizer-key-1',
                              resources={'central': 'i-abc'})
            self.assertTrue((root / 'recovery' / 'RESTORABLE').is_file())
            self.assertEqual(manifest['watermarks']['mode'], 'paused')
            self.assertEqual(manifest['sources'][0]['kind'], 'iris_db')
            self.assertEqual((root / 'recovery/secrets/bridge.secret').read_bytes(), b'top secret material'[::-1])
            restored = restore(root / 'recovery', root / 'clean', 'v1.0.0')
            self.assertTrue(restored['paused'])
            self.assertEqual(restored['watermarks']['answers'], 0)
            with self.assertRaisesRegex(ValueError, 'existing destination'):
                restore(root / 'recovery', root / 'clean', 'v1.0.0')

    def test_failure_leaves_no_restorable_set_and_releases_barrier(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            state = make_state(root)
            with self.assertRaisesRegex(ValueError, 'missing'):
                backup(state, root / 'recovery', 'v1.0.0',
                       sources=[Source('absent', 'iris_db', root / 'absent')])
            self.assertFalse((root / 'recovery').exists())
            # The export barrier must be released so normal mutation resumes.
            with state.transaction() as con:
                self.assertIsNone(con.execute('SELECT export_token FROM control').fetchone()[0])
            state.provision('operator')

    def test_verify_rejects_incomplete_corrupt_and_wrong_release(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            state = make_state(root)
            backup(state, root / 'recovery', 'v1.0.0')
            with self.assertRaisesRegex(ValueError, 'different release'):
                restore(root / 'recovery', root / 'clean', 'v9.9.9')
            (root / 'recovery' / 'RESTORABLE').unlink()
            with self.assertRaisesRegex(ValueError, 'completion marker'):
                verify(root / 'recovery')
            backup(state, root / 'recovery2', 'v1.0.0')
            (root / 'recovery2' / 'core.sqlite').write_bytes(b'corrupt')
            with self.assertRaisesRegex(ValueError, 'missing or corrupt'):
                verify(root / 'recovery2')
            with self.assertRaisesRegex(ValueError, 'completion marker'):
                restore(root / 'recovery', root / 'clean', 'v1.0.0')

    def test_secrets_require_encryption(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            state = make_state(root)
            secret = root / 'secret'
            secret.write_bytes(b'x')
            with self.assertRaisesRegex(ValueError, 'Encrypt secret'):
                backup(state, root / 'recovery', 'v1.0.0',
                       secrets=[Source('secret', 'secret', secret)])
            self.assertFalse((root / 'recovery').exists())


if __name__ == '__main__':
    unittest.main()
