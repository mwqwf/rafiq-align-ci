import copy
import gzip
import json
import pathlib
import tempfile
import unittest
from unittest import mock
import original_audio_fixture as F

class OriginalFixtureTests(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads((F.ROOT / F.MANIFEST).read_text())
        self.idx = {'reciterId': 'a_klb', 'riwaya': 'hafs', 'audioSha256': [None]*11+[F.SHA], 'entries': [{'ayahId':'12:1','fileRef':F.URL}]}
    def test_binding(self):
        self.assertTrue(F.eligible(self.idx))
        for key, value in [('reciterId','kurdi'),('riwaya','qalun'),('audioSha256',[]),('entries',[{'ayahId':'12:1','fileRef':'https://other/012.ogg'}])]:
            d=copy.deepcopy(self.idx);d[key]=value;self.assertFalse(F.eligible(d))
    def rejected(self, manifest, corrupt_path=None):
        with tempfile.TemporaryDirectory() as td:
            dst=pathlib.Path(td)/'original.mp3';dst.write_bytes(b'previous-complete-file')
            native_read=pathlib.Path.read_bytes
            def read(p):
                if corrupt_path and str(p).endswith(corrupt_path): return b'corrupt'
                return native_read(p)
            with mock.patch.object(pathlib.Path,'read_text',return_value=json.dumps(manifest)), mock.patch.object(pathlib.Path,'read_bytes',read):
                with self.assertRaises((ValueError,FileNotFoundError)):F.assemble(dst)
            self.assertEqual(dst.read_bytes(),b'previous-complete-file')
            self.assertEqual(list(pathlib.Path(td).glob('*.part')),[])
    def test_wrong_identity(self):
        for key,value in [('originalUrl','wrong'),('sourceSha256','0'*64),('bytes',F.SIZE-1),('sourceBytesChanged',True),('canonicalTextChanged',True),('partsCount',50)]:
            m=copy.deepcopy(self.manifest);m[key]=value;self.rejected(m)
    def test_parts_order_path_count_hash_size(self):
        m=copy.deepcopy(self.manifest);m['transportParts'].pop();self.rejected(m)
        for key,value in [('path','../../secrets'),('index',1),('bytes',1),('sha256','0'*64)]:
            m=copy.deepcopy(self.manifest);m['transportParts'][0][key]=value;self.rejected(m)
        self.rejected(self.manifest, F.PREFIX+'001')
    def test_full_hash_atomic_and_native_duration(self):
        with tempfile.TemporaryDirectory() as td:
            dst=pathlib.Path(td)/'exact.mp3'
            F.assemble(dst)
            import hashlib
            self.assertEqual(hashlib.sha256(dst.read_bytes()).hexdigest(),F.SHA)
            import run as R
            proof=F.prime(self.idx,R,dst)
            self.assertTrue(proof['wholeDecodeStrict'])
            self.assertLess(abs(proof['nativeMs']-F.DURATION_MS),2)
            R._DECODED.pop(str(dst),None)
    def test_changed_full_pin_rejects_even_matching_parts(self):
        with mock.patch.object(F,'SHA','0'*64):
            m=copy.deepcopy(self.manifest);m['sourceSha256']='0'*64;self.rejected(m)

if __name__=='__main__':unittest.main()
