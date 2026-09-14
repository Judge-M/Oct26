import hashlib
import json
import tempfile
import unittest
import zipfile
from datetime import datetime, timezone, timedelta
from pathlib import Path

import test_exercise as baseline
import control
import exercise
import generate
import offline
import schedule
from exercise_clock import elapsed_at


class TimingTests(unittest.TestCase):
    def test_default_and_compressed_outputs(self):
        config=json.loads((baseline.REPO/'config.json').read_text())
        with tempfile.TemporaryDirectory() as tmp:
            roots=[]
            for duration,initial,release,deadline,joint,close in [
                    (180,25,[35,75,115],[45,85,130],150,150),
                    (120,20,[25,50,75],[35,60,90],95,100)]:
                config['duration_minutes']=duration
                resolved,timing=schedule.validate(config)
                self.assertEqual(timing['initial_report'],initial)
                self.assertEqual(timing['inject_minutes'],release)
                self.assertEqual(timing['inject_deadlines'],deadline)
                self.assertEqual(timing['joint_report'],joint)
                self.assertEqual(timing['investigation_end'],close)
                root=generate.generate(Path(tmp)/str(duration),config); roots.append(root)
                handout=(root/'initial/handouts/handover.md').read_text(encoding='utf-8')
                self.assertIn(f'elapsed minute {initial}',handout)
                self.assertNotIn('{{',handout)
                self.assertNotIn('planned release',(root/'initial/common/schedule.md').read_text())
                self.assertIn('planned release',(root/'controller-schedule.md').read_text())
                for i in range(3):
                    command=(root/f'inject-{i+1}/command.md').read_text(encoding='utf-8')
                    self.assertIn(schedule.clock(release[i]),command)
                    self.assertIn(f'elapsed minute {deadline[i]}',command)
            for cell in generate.CELLS:
                self.assertEqual(generate.manifest(roots[0]/'initial'/cell),generate.manifest(roots[1]/'initial'/cell))

    def test_reject_invalid_configuration_before_generation(self):
        config=json.loads((baseline.REPO/'config.json').read_text())
        invalid=[{'duration_minutes':True},{'duration_minutes':90},{'participants':0},
                 {'inject_minutes':[35,75,115]}, {'timing':{'inject_minutes':[75,35,115]}},
                 {'timing':{'response_minutes':[9,10,15]}}, {'timing':{'joint_report':181}},
                 {'timing':{'inject_minutes':'bad'}},{'timing':{'initial_report':35}},
                 {'cells':['network']},{'timing':{'unknown':42}}]
        for change in invalid:
            with self.subTest(change=change),self.assertRaises((ValueError,TypeError)):
                schedule.validate({**config,**change})

    def test_hunting_example_includes_identity_host(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=generate.generate(Path(tmp)/'evidence')
            rows=[json.loads(line) for line in (root/'initial/hunting/siem.jsonl').read_text().splitlines()]
            correlated=sorted((r for r in rows if r['user']=='m.ellis'),key=lambda r:r['time'])
            self.assertEqual([r['id'] for r in correlated],['H101','H102','H103','H104'])
            session=[r for r in correlated if 'S-41' in r['value']]
            self.assertEqual(session[0]['host'],'IDP-1')

    def test_offline_checksums(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); (root/'source').mkdir()
            (root/'source/config.json').write_text('{}')
            (root/'images.tar').write_bytes(b'fixture only')
            (root/'SHA256SUMS.json').write_text(json.dumps(offline.files(root)))
            offline.verify(root)
            (root/'source/config.json').write_text('{"changed":true}')
            with self.assertRaises(ValueError): offline.verify(root)


class ReviewRuntimeTests(unittest.TestCase):
    setUp=baseline.RuntimeTests.setUp
    tearDown=baseline.RuntimeTests.tearDown
    start=baseline.RuntimeTests.start
    stop=baseline.RuntimeTests.stop
    request=baseline.RuntimeTests.request

    def test_empty_initial_manifest_rejected(self):
        (self.runtime/'public/SHA256SUMS.json').write_text('{}')
        with self.assertRaisesRegex(ValueError,'Initial manifest'): exercise.verify()

    def test_rehashed_public_inject_rejected(self):
        exercise.release(1)
        (self.runtime/'public/inject-1/dlp-body.txt').write_text('forged')
        generate.stamp(self.runtime/'public/inject-1')
        with self.assertRaisesRegex(ValueError,'differs from vault'): exercise.verify()
        with self.assertRaises(ValueError): exercise.release(1)

    def test_release_log_and_directory_consistency(self):
        exercise.release(1)
        path=self.runtime/'release-log.json'; original=path.read_bytes()
        path.write_text('[]')
        with self.assertRaisesRegex(ValueError,'disagree'): exercise.verify()
        path.write_bytes(original)
        path.write_text(json.dumps(json.loads(original)*2))
        with self.assertRaisesRegex(ValueError,'disagree'): exercise.verify()
        path.write_bytes(original)
        extra=self.runtime/'public/inject-4'; extra.mkdir()
        with self.assertRaisesRegex(ValueError,'directory'): exercise.verify()
        extra.rmdir()
        (self.runtime/'public/inject-1').rename(self.runtime/'public/inject-2')
        with self.assertRaises(ValueError): exercise.verify()

    def test_pause_clock_decisions_comments_and_exports(self):
        now=datetime.now(timezone.utc)
        def record(kind, seconds, details=None):
            return control.append(self.runtime,kind,'EXCON-A',details,now=(now+timedelta(seconds=seconds)).isoformat())
        record('start',-120)
        record('pause',-90)
        record('resume',-30)
        decision=record('decision',-20,{'request':'T1-C1','outcome':'approved','effective_minute':3,'text':'Preserve and isolate'})
        self.assertEqual(decision['elapsed_seconds'],40)
        self.assertEqual(decision['operator'],'EXCON-A')
        self.assertTrue(decision['host_user'])
        self.assertEqual(elapsed_at(control.read(self.runtime),(now-timedelta(seconds=60)).isoformat()),30)
        record('note',-10,{'text':'PRIVATE SPOILER: next inject answer'})
        public=json.loads(self.request('/api/control')[1])
        self.assertNotIn('PRIVATE SPOILER',json.dumps(public))
        self.assertNotIn('host_user',json.dumps(public))
        self.assertEqual(public[-1]['id'],decision['id'])
        for path in ('/files/../vault/controller-schedule.md','/files/facilitator/cell-coaching.md','/files/control/ledger.json'):
            self.assertEqual(self.request(path)[0],404)
        self.assertEqual(self.request('/api/control',None)[0],401)
        self.assertEqual(self.request('/api/control',payload={'kind':'decision'})[0],404)
        for cell in generate.CELLS:
            self.assertEqual(json.loads(self.request('/api/control',cell)[1])[-1]['id'],decision['id'])
        self.request('/api/update',payload={'ticket':1,'body':'request preserved'})
        comment=json.loads(self.request('/api/tickets')[1])[0]['comments'][0]
        self.assertEqual(comment['clock_event'],control.read(self.runtime)[-1]['id'])
        self.assertGreaterEqual(comment['elapsed_seconds'],60)
        self.assertLess(comment['elapsed_seconds'],90)
        exercise.release(1,'EXCON-B'); exercise.verify()
        with zipfile.ZipFile(exercise.export()) as archive:
            events=json.loads(archive.read('control/ledger.json'))
            releases=json.loads(archive.read('release-log.json'))
            self.assertEqual(events[-1]['operator'],'EXCON-B')
            self.assertEqual(releases[-1]['event_id'],events[-1]['id'])
        self.stop(); self.start()
        self.assertEqual(json.loads(self.request('/api/tickets')[1])[0]['comments'][0],comment)

    def test_clock_transitions_lock_and_false_mapping(self):
        with self.assertRaises(ValueError): control.append(self.runtime,'pause')
        control.append(self.runtime,'start')
        with self.assertRaises(ValueError): control.append(self.runtime,'start')
        control.append(self.runtime,'pause')
        with self.assertRaises(ValueError): control.append(self.runtime,'pause')
        with control.locked(self.runtime):
            with self.assertRaises(ValueError): exercise.release(1)
        events=control.read(self.runtime); events[-1]['elapsed_seconds']=999
        control.save(self.runtime,events)
        with self.assertRaisesRegex(ValueError,'mapping'): exercise.verify()

    def test_init_uses_selected_configuration(self):
        self.stop()
        config=json.loads((exercise.REPO/'config.json').read_text()); config['duration_minutes']=120
        (exercise.REPO/'config.json').write_text(json.dumps(config))
        exercise.reset(True)
        self.assertEqual(json.loads((self.runtime/'run-config.json').read_text())['timing']['joint_report'],95)
        self.assertIn('elapsed minute 20',(self.runtime/'public/handouts/handover.md').read_text())

    def test_login_attempts_are_throttled(self):
        for _ in range(20):
            self.assertEqual(self.request('/api/login',None,{'cell':'network','password':'wrong'})[0],401)
        self.assertEqual(self.request('/api/login',None,{'cell':'network','password':'wrong'})[0],429)
        self.assertEqual(self.request('/api/login',None,{'cell':'network','password':self.logins['network']})[0],429)

    def test_lock_error_reports_holder(self):
        with control.locked(self.runtime):
            with self.assertRaisesRegex(ValueError,'pid='):
                with control.locked(self.runtime):
                    pass

    def test_clock_projection_is_shared(self):
        now=datetime.now(timezone.utc)
        def record(kind,seconds):
            return control.append(self.runtime,kind,'EXCON-A',now=(now+timedelta(seconds=seconds)).isoformat())
        record('start',-300); record('pause',-240); record('resume',-120)
        events=control.read(self.runtime)
        for seconds,expected in [(-300,0.0),(-240,60.0),(-180,60.0),(-120,60.0),(-60,120.0)]:
            at=now+timedelta(seconds=seconds)
            self.assertEqual(control.position(events,at)[0],expected)
            self.assertEqual(elapsed_at(events,at.isoformat()),expected)
        self.assertTrue(control.position(events,now+timedelta(seconds=-180))[1])
        self.assertFalse(control.position(events,now+timedelta(seconds=-60))[1])



if __name__=='__main__': unittest.main()
