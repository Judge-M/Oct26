import csv
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from expanded.author import build as author
from expanded.prepare import build
from ridge.artifacts import verify,sha256
from app.analysis_tools import packets


class EvidenceTests(unittest.TestCase):
    def test_coherent_native_disk_packets_and_protected_release(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=build(Path(tmp)/'release');public=root/'initial'
            with (public/'network/proxy.csv').open(newline='',encoding='utf-8') as source:
                rows=list(csv.DictReader(source))
            capture=packets((public/'network/sensor.pcap').read_bytes())
            for row,packet in zip(rows,capture):
                embedded=json.loads(packet['payload'][packet['payload'].index('{'):])
                self.assertEqual(row,embedded)
            self.assertEqual(len(rows),len(capture))
            data=(public/'disk/WS17-fat16.img').read_bytes()
            self.assertEqual(data[510:512],b'\x55\xaa')
            self.assertIn(b'Patrol LANTERN movement brief v3',data)
            self.assertFalse((public/'network/dlp-body.txt').exists())
            self.assertTrue((root/'controller/releases/T19/network/dlp-body.txt').exists())
            telemetry=[json.loads(line) for line in (public/'wazuh/telemetry.jsonl').read_text().splitlines()]
            process=[r for r in telemetry if r['data'].get('process')=='brief-viewer.exe' and r['data'].get('event')=='ProcessStart']
            self.assertEqual(process[0]['timestamp'],'2026-10-15T08:58:00Z')
            self.assertGreater(len(telemetry),450)
            self.assertFalse(any(r['data'].get('time')=='2026-10-15T09:26:00Z' for r in telemetry))
            self.assertTrue(all('provenance' in json.loads(p.read_text()) for p in (root/'controller/preparation-fixtures').glob('*.json')))

    def test_content_references_help_and_estimates(self):
        tickets=author();questions=[q for t in tickets for q in t['questions']]
        self.assertEqual(len({q['id'] for q in questions}),80)
        self.assertGreaterEqual(sum(t['estimate_minutes'] for t in tickets)/5,240)
        for q in questions:
            self.assertGreaterEqual(len(q['hints']),3)
            self.assertIn(q['answer'],q['hints'][-1])
            self.assertNotEqual(q['finding']['text'],q['answer'])
            self.assertTrue(q['finding']['limitation'])
        self.assertGreaterEqual(sum(not t['requires'] for t in tickets),5)

    def test_artifacts_tamper_paths_and_incomplete_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);file=root/'fixture.bin';file.write_bytes(b'fixture')
            manifest=dict(schema=1,release='r1',source_commit='abc',compatibility_verified=False,artifacts=[
                dict(path='fixture.bin',kind='disk',version='1',release='r1',bytes=7,sha256=sha256(file))])
            self.assertEqual(verify(root,manifest,complete=False),1)
            with self.assertRaisesRegex(ValueError,'Incomplete'):verify(root,manifest)
            file.write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'corrupt'):verify(root,manifest,False)
            manifest['artifacts'][0]['path']='../outside'
            with self.assertRaisesRegex(ValueError,'Unsafe'):verify(root,manifest,False)

    def test_offline_rejects_stale_application_image(self):
        from scripts import offline
        with patch.object(offline,'run',return_value='{}'):
            with self.assertRaisesRegex(ValueError,'differs from current source'):
                offline.verify_application_image('sha256:fixture')

    def test_expanded_bundle_rejects_stale_extended_image(self):
        from ridge.bundle import image_sources
        with patch('ridge.bundle.command',return_value='{}'):
            with self.assertRaisesRegex(ValueError,'Source/image mismatch'):
                image_sources('integration','sha256:fixture')

    def test_guacamole_adjustable_shared_and_exclusive(self):
        path=Path(__file__).resolve().parents[1]/'deployment/expanded/guacamole.py'
        spec=importlib.util.spec_from_file_location('guac',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        config=dict(desktops=[dict(id='desk',address='192.0.2.10',shared=False,max_connections=9)],
                    teams=[dict(id='team',desktop='desk')])
        credentials=dict(desktops={'desk':{'password':'vnc-pass'}},teams={'team':{'username':'team','password':'a-long-generated-password'}})
        sql=module.generate(config,credentials)
        self.assertIn("'vnc',1,1",sql)
        self.assertNotIn('a-long-generated-password',sql)
        config['desktops'][0]['shared']=True
        self.assertIn("'vnc',9,9",module.generate(config,credentials))


if __name__=='__main__':unittest.main()
