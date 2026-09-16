import json
import tempfile
import unittest
from pathlib import Path

from ridge import capacity, offline_release, rehearsal, schedule_model
from ridge.artifacts import sha256

REQUIRED_IMAGES = {'integration', 'iris', 'ctfd', 'iris_db', 'rabbitmq', 'ctfd_db',
                   'ctfd_cache', 'wazuh_manager', 'wazuh_indexer', 'wazuh_dashboard',
                   'guacamole', 'guacd', 'guacamole_db'}


class CapacityTests(unittest.TestCase):
    def measurements(self, **overrides):
        values = dict(app_p95_seconds=1.5, score_delivery_p95_seconds=8.0, cpu_percent=55,
                      memory_percent=70, swap_used_mib=0, capacity_reserve_fraction=0.25,
                      oom_events=0, desktop_sessions=10, measured=True)
        values.update(overrides)
        return values

    def test_scenario_and_evaluation(self):
        self.assertEqual(capacity.scenario(teams=2, participants=6, desktops=2)['participants'], 6)
        self.assertTrue(capacity.evaluate(self.measurements())['passed'])
        self.assertFalse(capacity.evaluate(self.measurements(app_p95_seconds=3.0))['passed'])
        self.assertFalse(capacity.evaluate(self.measurements(capacity_reserve_fraction=0.05))['passed'])
        self.assertFalse(capacity.evaluate(self.measurements(oom_events=1))['passed'])
        with self.assertRaisesRegex(ValueError, 'incomplete'):
            capacity.evaluate({'app_p95_seconds': 1.0})
        with self.assertRaisesRegex(ValueError, 'unsupported'):
            capacity.require_supported_host({'supported': False})


class ScheduleModelTests(unittest.TestCase):
    def test_capacity_arithmetic_matches_assessment(self):
        result = schedule_model.model(dict(teams=10, tickets=20, estimate_minutes=65))
        self.assertEqual(result['total_team_minutes'], 1300)
        self.assertEqual(result['per_team_available'], 130)
        self.assertFalse(result['meets'])
        self.assertEqual(result['gap'], 110)
        five = schedule_model.model(dict(teams=5, tickets=20, estimate_minutes=65))
        self.assertTrue(five['meets'])

    def test_human_observations_required(self):
        with self.assertRaisesRegex(ValueError, 'human rehearsal'):
            schedule_model.record_observations({'human_rehearsal': False})
        observed = schedule_model.record_observations(dict(
            human_rehearsal=True, teams=[dict(active_minutes=200, idle_minutes=40)],
            required_team_minutes=180, aar_minutes=30, breaks_minutes=15))
        self.assertEqual(observed['active_team_minutes'], 200)
        self.assertTrue(observed['meets'])


class OfflineReleaseTests(unittest.TestCase):
    def test_pinning_and_merge(self):
        digest = 'sha256:' + 'a' * 64
        self.assertEqual(offline_release.pin_image(digest), digest)
        self.assertEqual(offline_release.pin_image('ghcr.io/judge-m/oct26-iris@' + digest),
                         'ghcr.io/judge-m/oct26-iris@' + digest)
        for bad in ('latest', 'ghcr.io/x/y:latest', 'ghcr.io/x/y:v1.0.0'):
            with self.assertRaises(ValueError):
                offline_release.pin_image(bad)
        merged = offline_release.merge_inventories(
            dict(release='v1.0.0', source_commit='a' * 40, images={'iris': digest}, files={}),
            dict(images={'ctfd': digest}, artifacts=[]))
        self.assertEqual(set(merged['images']), {'iris', 'ctfd'})
        with self.assertRaisesRegex(ValueError, 'release and source commit'):
            offline_release.merge_inventories({}, {})

    def test_require_complete_and_verify(self):
        images = {name: 'sha256:' + ('%x' % index) * 64 for index, name in enumerate(sorted(REQUIRED_IMAGES))}
        artifacts = [dict(kind=kind) for kind in offline_release.REQUIRED_CATEGORIES]
        manifest = dict(release='v1.0.0', source_commit='a' * 40, images=images, artifacts=artifacts, files={})
        offline_release.require_complete(manifest, REQUIRED_IMAGES)
        with self.assertRaisesRegex(ValueError, 'Missing pinned images'):
            offline_release.require_complete(manifest, REQUIRED_IMAGES | {'extra'})
        with self.assertRaisesRegex(ValueError, 'missing categories'):
            offline_release.require_complete(dict(manifest, artifacts=[]), REQUIRED_IMAGES)

    def test_verify_rejects_lfs_stub_and_corruption(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            good = root / 'source.zip'
            good.write_bytes(b'real release bytes')
            stub = root / 'asset-0000.bin'
            stub.write_bytes(offline_release.LFS_POINTER + b'\noid sha256:abc\nsize 1\n')
            manifest = dict(release='v1.0.0', source_commit='a' * 40, images={}, artifacts=[],
                            files={'source.zip': dict(bytes=good.stat().st_size, sha256=sha256(good)),
                                   'asset-0000.bin': dict(bytes=stub.stat().st_size, sha256=sha256(stub))})
            with self.assertRaisesRegex(ValueError, 'pointer stub'):
                offline_release.verify_offline(root, manifest)
            manifest['files'].pop('asset-0000.bin')
            offline_release.verify_offline(root, manifest)
            good.write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'corrupt'):
                offline_release.verify_offline(root, manifest)


class RehearsalTests(unittest.TestCase):
    def test_freeze_gate(self):
        with self.assertRaisesRegex(ValueError, 'incomplete'):
            rehearsal.freeze({})
        blocked = {phase: dict(status='pass') for phase in rehearsal.PHASES}
        blocked['provider_switch'] = dict(status='blocked', reason='no AWS credentials')
        with self.assertRaisesRegex(ValueError, 'non-passing'):
            rehearsal.freeze(blocked)
        document = rehearsal.record(blocked)
        self.assertTrue(document['complete'])
        self.assertEqual(document['exceptions'][0]['reason'], 'no AWS credentials')
        passing = {phase: dict(status='pass') for phase in rehearsal.PHASES}
        passing['lost_host'] = dict(status='pass', rto_seconds=600, rpo_seconds=60)
        passing['teardown'] = dict(status='pass', remaining_billable=['snapshot-1'])
        frozen = rehearsal.freeze(passing)
        self.assertTrue(frozen['frozen'])
        self.assertEqual(frozen['rto_seconds'], 600)


if __name__ == '__main__':
    unittest.main()
