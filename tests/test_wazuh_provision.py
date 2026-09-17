"""Deterministic tests for the Wazuh historical-stack bootstrap (B03).

No live Wazuh stack is available (BLOCKED: no Docker/Linux host). These tests
cover the vendored config, role/view payloads, idempotent apply, stable record
IDs and TLS trust behavior.
"""
import json
import tempfile
import unittest
from pathlib import Path

from ridge.scenario import telemetry_record
from ridge.wazuh_provision import (
    INDEX_PATTERN, READER_ROLE, TIMED_VIEW, TIMELESS_VIEW, WRITER_ROLE, Request, UserSpec,
    WazuhError, apply_plan, build_plan, ca_context, index_template, load_vendored, preflight_facts,
    reader_role, record_id, saved_objects, validate_manifest, writer_role,
)

ROOT = Path(__file__).resolve().parents[1]
WAZUH = ROOT / 'deployment/expanded/wazuh'


class VendoredConfigTests(unittest.TestCase):
    def test_vendored_files_match_reviewed_module_output(self):
        loaded = load_vendored(WAZUH)
        self.assertEqual(loaded['index_template'], index_template())
        self.assertEqual(loaded['saved_objects'], saved_objects())
        roles = json.loads((WAZUH / 'roles.json').read_text(encoding='utf-8'))
        self.assertEqual(roles[WRITER_ROLE], writer_role())
        self.assertEqual(roles[READER_ROLE], reader_role())

    def test_roles_are_index_scoped_and_reader_is_read_only(self):
        writer = writer_role()
        reader = reader_role()
        self.assertEqual(writer['index_permissions'][0]['index_patterns'], [INDEX_PATTERN])
        self.assertEqual(reader['index_permissions'][0]['index_patterns'], [INDEX_PATTERN])
        self.assertNotIn('*', writer['index_permissions'][0]['index_patterns'])
        self.assertNotIn('indices:data/write/bulk', reader['index_permissions'][0]['allowed_actions'])

    def test_timed_and_timeless_views_differ_only_by_time_field(self):
        views = {view['id']: view for view in saved_objects()}
        self.assertEqual(views[TIMED_VIEW]['attributes']['timeFieldName'], 'timestamp')
        self.assertIsNone(views[TIMELESS_VIEW]['attributes']['timeFieldName'])

    def test_manifest_fails_closed_without_digests(self):
        manifest = json.loads((WAZUH / 'manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(validate_manifest(manifest, require_digests=False), 3)
        with self.assertRaisesRegex(WazuhError, 'immutable digest'):
            validate_manifest(manifest)
        with self.assertRaisesRegex(WazuhError, 'source'):
            validate_manifest({'schema': 1, 'images': manifest['images']}, require_digests=False)


class PlanTests(unittest.TestCase):
    def test_plan_scopes_roles_and_users(self):
        plan = build_plan('silent-ridge-oct26', [UserSpec('writer', 'w' * 40, WRITER_ROLE),
                                                 UserSpec('reader', 'r' * 40, READER_ROLE)])
        paths = [request.path for request in plan]
        self.assertIn('/_plugins/_security/api/roles/' + WRITER_ROLE, paths)
        self.assertIn('/_plugins/_security/api/rolesmapping/' + READER_ROLE, paths)
        self.assertIn('/api/saved_objects/index-pattern/' + TIMELESS_VIEW, paths)
        user = next(request for request in plan if 'internalusers/writer' in request.path)
        self.assertEqual(user.body['backend_roles'], [WRITER_ROLE])

    def test_plan_rejects_bad_input(self):
        with self.assertRaisesRegex(WazuhError, 'dedicated silent-ridge'):
            build_plan('other-index', [])
        with self.assertRaisesRegex(WazuhError, 'unknown role'):
            build_plan('silent-ridge-oct26', [UserSpec('x', 'y' * 40, 'admin')])
        with self.assertRaisesRegex(WazuhError, 'duplicate user'):
            build_plan('silent-ridge-oct26', [UserSpec('x', 'y' * 40, READER_ROLE),
                                              UserSpec('x', 'z' * 40, READER_ROLE)])

    def test_apply_is_idempotent_and_fails_on_unexpected_status(self):
        plan = build_plan('silent-ridge-oct26', [UserSpec('writer', 'w' * 40, WRITER_ROLE)])
        calls = []

        def transport(method, path, body):
            calls.append((method, path))
            return 200 if 'roles/' in path else 409

        self.assertEqual(apply_plan(transport, plan), len(plan))
        self.assertEqual(apply_plan(transport, plan), len(plan))
        self.assertEqual(len(calls), 2 * len(plan))

        def failing(method, path, body):
            return 500

        with self.assertRaisesRegex(WazuhError, 'failed with status 500'):
            apply_plan(failing, [Request('PUT', '/_index_template/silent-ridge', {})])

    def test_preflight_requires_queryable_facts(self):
        facts = [{'field': 'data.session', 'value': 'S-41'},
                 {'field': 'data.host', 'value': 'WS-31'},
                 {'field': 'data.type', 'value': 'coverage'}]
        self.assertTrue(preflight_facts(lambda *a: 200, 'silent-ridge-oct26', facts)['ready'])
        with self.assertRaisesRegex(WazuhError, 'failed with status'):
            preflight_facts(lambda *a: 500, 'silent-ridge-oct26', facts)
        with self.assertRaisesRegex(WazuhError, 'field and value'):
            preflight_facts(lambda *a: 200, 'silent-ridge-oct26', [{}])


class RecordAndTlsTests(unittest.TestCase):
    def test_record_ids_are_stable_and_distinct(self):
        first = telemetry_record({'time': '2026-10-15T09:03:00Z', 'host': 'IDP-1'}, 'identity/late-auth.csv')
        again = telemetry_record({'time': '2026-10-15T09:03:00Z', 'host': 'IDP-1'}, 'identity/late-auth.csv')
        other = telemetry_record({'time': '2026-10-15T09:04:00Z', 'host': 'IDP-1'}, 'identity/late-auth.csv')
        self.assertEqual(record_id(first), record_id(again))
        self.assertNotEqual(record_id(first), record_id(other))

    def test_timeless_coverage_records_carry_no_timestamp(self):
        record = telemetry_record({'host': 'WS-31', 'note': 'gap'}, 'hunting/coverage.csv')
        self.assertTrue(record['timeless'])
        self.assertNotIn('timestamp', record)

    def test_ca_context_requires_real_ca_and_never_disables_verification(self):
        with self.assertRaisesRegex(WazuhError, 'CA bundle is missing'):
            ca_context('/definitely/not/here.pem')
        with tempfile.TemporaryDirectory() as tmp:
            bogus = Path(tmp) / 'bogus.pem'
            bogus.write_text('not a certificate', encoding='utf-8')
            with self.assertRaises(Exception):
                ca_context(bogus)


if __name__ == '__main__':
    unittest.main()
