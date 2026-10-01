"""شاهد بداية الملف لا يعفي المطلع من الثقة أو المدة ولا يغير الافتراضي."""
import contextlib
import gzip
import io
import json
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import ctc_gapsplit as G


class FirstAyahAnchor(unittest.TestCase):
    def run_case(self, flag=True, conf=.7, second=2500, surahs='78'):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            rows = [{'ayahId': f'78:{k}', 'fileRef': 'https://source/078.mp3',
                     'startMs': st, 'endMs': en, 'conf': .7}
                    for k, st, en in [(2, 3000, 6000), (3, 6000, 10000)]]
            parent = root / 'parent.jz'
            parent.write_bytes(gzip.compress(json.dumps({'entries': rows}).encode()))
            calls = []
            def align(x, ws, we, texts):
                calls.append(texts)
                lead = len(texts) == 4
                return ([(-100, 600, .9)] if lead else []) + [(680, second, conf), (second, 6000, .7), (6000, 10000, .7)]
            args = ['tool', '--index', str(parent), '--surahs', surahs,
                    '--riwaya', 'hafs', '--context-ayahs', '2', '--out-dir', td]
            if flag:
                args.append('--starts-with-first-ayah')
            with patch.object(sys, 'argv', args), patch.object(G, 'load_index', return_value={'surahs': [{'n': 78, 'start': 0, 'ayahs': 3}]}), patch.object(G, 'load_text', return_value=['ا' * 10] * 3), patch.object(G, 'fetch', side_effect=lambda url, dst: pathlib.Path(dst).write_bytes(b'audio')), patch.object(G, 'to_wav16k', return_value='wave'), patch.object(G, 'read_wav', return_value=G.np.zeros(160000)), patch.object(G, 'silences', return_value=[]), patch.object(G, 'split_window', side_effect=align), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                G.main()
            dest = root / 's078.json'
            return (json.loads(dest.read_text()) if dest.exists() else None), calls

    def test_explicit_anchor_omits_basmala_and_keeps_medium_cap(self):
        d, calls = self.run_case()
        self.assertEqual(len(calls[0]), 3)
        self.assertEqual(d['entries'][0]['startMs'], 0)
        self.assertFalse(d['entries'][0]['snapped'])
        self.assertLess(d['entries'][0]['conf'], .75)
        self.assertTrue(d['startsWithFirstAyah'])

    def test_default_still_includes_basmala_and_uses_ctc_start(self):
        d, calls = self.run_case(flag=False)
        self.assertEqual(len(calls[0]), 4)
        self.assertEqual(d['entries'][0]['startMs'], 680)
        self.assertNotIn('startsWithFirstAyah', d)

    def test_low_confidence_is_rejected_even_at_file_boundary(self):
        self.assertIsNone(self.run_case(conf=.44)[0])

    def test_bad_duration_is_rejected_even_at_file_boundary(self):
        self.assertIsNone(self.run_case(second=9000)[0])

    def test_one_witness_cannot_apply_to_multiple_surahs(self):
        with self.assertRaises(SystemExit):
            self.run_case(surahs='78,79')


if __name__ == '__main__':
    unittest.main()
