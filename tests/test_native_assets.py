import json
from pathlib import Path
import shutil
import tempfile
import unittest

from expanded.author import build
from expanded.native import ROOT, records


class NativeAssetsTests(unittest.TestCase):
    def test_questions_use_measured_ids_without_rewriting_history(self):
        data = records()
        tickets = {ticket['id']: ticket for ticket in build()}
        self.assertEqual(tickets['T15']['questions'][0]['answer'], str(data['memory-processes']['pid']))
        self.assertEqual(tickets['T15']['questions'][1]['answer'], str(data['memory-processes']['ppid']))
        self.assertEqual(tickets['T04']['questions'][3]['answer'], '09:08:00')
        self.assertEqual(tickets['T13']['questions'][3]['answer'], data['windows-process']['utc'][11:19])
        self.assertIn('snapshot', tickets['T16']['title'])
        self.assertIn('not a validated memory', tickets['T16']['questions'][3]['finding']['text'])

    def test_native_record_tampering_stops_authoring(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)/'native'
            shutil.copytree(ROOT, root, ignore=shutil.ignore_patterns('archive.json'))
            path = root/'prepared/memory-processes.json'
            data = json.loads(path.read_text())
            data['pid'] = 4240
            path.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
                records(root)
