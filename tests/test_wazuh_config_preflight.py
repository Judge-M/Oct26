"""Issue #187: preflight must fail closed when required Wazuh config assets
are missing or malformed, and must name the remedy that produces the tree.

Drives LocalStack._probe_wazuh_config_assets directly through a bare instance
(no Docker, no receipts): the stage-S1 probe composes these problems into its
LifecycleError verbatim.
"""
import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ridge.deploy import local as deploy_local
from ridge.deploy.local import LocalStack, WAZUH_CONFIG_ASSET_FILES

VALID = {
    'wazuh_indexer/wazuh.indexer.yml':
        'cluster.name: wazuh-indexer\nnode.name: wazuh-indexer\n',
    'wazuh_indexer/internal_users.yml':
        'admin:\n  hash: "$2y$12$abcdefghijklmnopqrstuvwxyzABCDEFGHIJKL"\n',
    'wazuh_cluster/wazuh_manager.conf':
        '<ossec_config><global><update_check>yes</update_check></global>'
        '<vulnerability-detection><enabled>yes</enabled>'
        '<index-status>yes</index-status></vulnerability-detection>'
        '<indexer><enabled>yes</enabled></indexer></ossec_config>',
    'wazuh_dashboard/opensearch_dashboards.yml':
        'opensearch.hosts: https://wazuh-indexer:9200\n',
}


def stack_for(asset_dir):
    """A LocalStack bound only to a wazuh_config asset path (no docker)."""
    stack = LocalStack.__new__(LocalStack)
    stack.local = {'assets': {'wazuh_config': str(asset_dir)}}
    return stack


def build_tree(root, overrides=None):
    files = dict(VALID)
    files.update(overrides or {})
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')


class WazuhConfigPreflightTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        # LocalStack.asset() reports the resolved path; on Windows CI the raw
        # tempdir name carries an 8.3 short form (C:\Users\RUNNER~1\...), so
        # every expected-path comparison must use the same resolved spelling.
        self.assets = (Path(self.tmp.name) / 'wazuh-config').resolve()

    def problems(self):
        return stack_for(self.assets)._probe_wazuh_config_assets()

    def test_every_mounted_file_is_in_scope(self):
        # Regression: the old check covered three files and never the dashboard
        # config that compose.wazuh.yaml also mounts.
        self.assertEqual(
            {rel for rel, _fmt in WAZUH_CONFIG_ASSET_FILES},
            set(VALID))

    def test_absent_tree_fails_with_remedy_naming_a_producer(self):
        problems = self.problems()
        self.assertEqual(len(problems), 1)
        self.assertIn('Wazuh config asset missing at %s' % self.assets, problems[0])
        # Either the source-path fetcher (once PR #185 lands) or the pinned
        # upstream commit recorded in the vendored manifest must be named.
        self.assertRegex(problems[0],
                         r'fetch_wazuh_config\.py|wazuh-docker commit '
                         r'[0-9a-f]{40}')
        self.assertIn(str(self.assets), problems[0])

    def test_valid_tree_probes_clean(self):
        build_tree(self.assets)
        self.assertEqual(self.problems(), [])

    def test_directory_present_but_empty_reports_all_four_files(self):
        self.assets.mkdir()
        problems = self.problems()
        self.assertEqual(len(problems), len(WAZUH_CONFIG_ASSET_FILES))
        for rel, _fmt in WAZUH_CONFIG_ASSET_FILES:
            self.assertTrue(any(rel in problem for problem in problems), rel)

    def test_single_missing_file_is_named(self):
        build_tree(self.assets)
        (self.assets / 'wazuh_dashboard/opensearch_dashboards.yml').unlink()
        problems = self.problems()
        self.assertEqual(len(problems), 1)
        self.assertIn('wazuh_dashboard/opensearch_dashboards.yml missing', problems[0])

    def test_empty_file_fails_closed(self):
        build_tree(self.assets, {'wazuh_indexer/wazuh.indexer.yml': '   \n'})
        problems = self.problems()
        self.assertEqual(len(problems), 1)
        self.assertIn('wazuh_indexer/wazuh.indexer.yml', problems[0])
        self.assertIn('is empty', problems[0])

    def test_unreadable_file_fails_closed(self):
        build_tree(self.assets, {'wazuh_indexer/internal_users.yml': ''})
        (self.assets / 'wazuh_indexer/internal_users.yml').write_bytes(b'\xff\xfe\x00binary')
        problems = self.problems()
        self.assertEqual(len(problems), 1)
        self.assertIn('is unreadable', problems[0])

    def test_malformed_xml_manager_conf_fails_closed(self):
        build_tree(self.assets,
                   {'wazuh_cluster/wazuh_manager.conf':
                        '<ossec_config><global><update_check>yes'})
        problems = self.problems()
        self.assertEqual(len(problems), 1)
        self.assertIn('wazuh_cluster/wazuh_manager.conf', problems[0])
        self.assertIn('is not valid xml', problems[0])

    def test_malformed_yaml_fails_closed_when_pyyaml_available(self):
        if deploy_local._yaml is None:
            self.skipTest('PyYAML not installed on this host')
        build_tree(self.assets,
                   {'wazuh_dashboard/opensearch_dashboards.yml': 'hosts: [unclosed\n'})
        problems = self.problems()
        self.assertEqual(len(problems), 1)
        self.assertIn('wazuh_dashboard/opensearch_dashboards.yml', problems[0])
        self.assertIn('is not valid yaml', problems[0])

    def test_remedy_names_pinned_commit_when_no_fetcher_shipped(self):
        fetcher = deploy_local.ROOT / 'scripts' / 'fetch_wazuh_config.py'
        if fetcher.is_file():  # PR #185 merged: the remedy is the fetch command
            remedy = LocalStack._wazuh_config_remedy(self.assets)
            self.assertRegex(remedy, re.escape('scripts/fetch_wazuh_config.py'))
            return
        remedy = LocalStack._wazuh_config_remedy(self.assets)
        manifest = deploy_local.WAZUH_DIR / 'manifest.json'
        import json
        commit = json.loads(manifest.read_text(encoding='utf-8'))['source']['commit']
        self.assertIn(commit, remedy)
        self.assertIn(str(self.assets), remedy)


if __name__ == '__main__':
    unittest.main()
