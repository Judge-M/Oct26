import json
import tempfile
import unittest
from pathlib import Path

from buildpipe import pipeline
from buildpipe_fixtures import case_fixture, native_source


class PipelineTests(unittest.TestCase):
    def config(self, root, **extra):
        config = dict(version='test-v1', release_root=str(root / 'release'),
                      native_source=str(root / 'source'),
                      case=dict(case=str(root / 'cases/WS17'), evidence=str(root / 'evidence')),
                      desktop=dict(build_root=str(root / 'desktop-build')))
        config.update(extra)
        return config

    def test_run_resume_blocked_and_inventory(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            native_source(root / 'source')
            case_fixture(root)
            config = self.config(root)
            results = pipeline.run(config, root / 'work')
            self.assertEqual(results['native']['status'], 'done')
            self.assertEqual(results['case']['status'], 'done')
            self.assertEqual(results['desktop']['status'], 'blocked')
            self.assertIn('inventory', results)
            self.assertTrue((root / 'release' / 'native-test-v1' / 'manifest.json').is_file())
            self.assertTrue((root / 'release' / 'case-test-v1.json').is_file())
            self.assertTrue((root / 'work' / 'receipts' / 'desktop.json').is_file())
            self.assertTrue(results['inventory']['files'])
            resumed = pipeline.run(config, root / 'work')
            self.assertTrue(resumed['native']['skipped'])
            self.assertTrue(resumed['case']['skipped'])
            self.assertTrue(resumed['desktop']['skipped'])

    def test_tampered_input_changes_digest_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = native_source(root / 'source')
            case_fixture(root)
            config = self.config(root)
            first = pipeline.run_stage('native', config, root / 'work')
            (source / 'native-provenance.json').write_text(json.dumps(dict(
                scenario_host='WS-17', viewer_pid=1, parent_pid=2)))
            self.assertNotEqual(first['digest'], pipeline._stage_digest('native', config))
            with self.assertRaisesRegex(ValueError, 'new record directory'):
                pipeline.run_stage('native', config, root / 'work')

    def test_secrets_separation_and_immutable_inventory(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            native_source(root / 'source')
            case_fixture(root)
            config = self.config(root)
            with self.assertRaisesRegex(ValueError, 'separate directories'):
                pipeline.run(config, root / 'release' / 'secrets-parent' / 'work')
            pipeline.run(config, root / 'work')
            (root / 'release' / 'build-key').write_text('secret')
            with self.assertRaisesRegex(ValueError, 'must never enter a release'):
                pipeline.assert_no_secrets(root / 'release')
            (root / 'release' / 'build-key').unlink()
            (root / 'release' / 'new-file').write_text('changed')
            with self.assertRaisesRegex(ValueError, 'immutable'):
                pipeline.write_inventory(root / 'work', config)
            with self.assertRaisesRegex(ValueError, 'requires'):
                pipeline.validate_config({'version': 'x'})
            with self.assertRaisesRegex(ValueError, 'no stage inputs'):
                pipeline.validate_config({'version': 'x', 'release_root': 'r'})


if __name__ == '__main__':
    unittest.main()
