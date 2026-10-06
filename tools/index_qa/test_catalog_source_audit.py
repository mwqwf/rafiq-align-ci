import gzip,io,json,pathlib,sys,unittest
sys.path.insert(0,str(pathlib.Path(__file__).parent))
import catalog_source_audit as A

class CatalogSourceAuditTest(unittest.TestCase):
    def fixture(self):
        base='https://example.org/reader/'
        idx={'riwaya':'hafs','reciterId':'reader','entries':[{'ayahId':f'2:{i+1}','fileRef':base+'002.mp3'} for i in range(300)]+[{'ayahId':'114:6','fileRef':'https://another.example/114.mp3'}]}
        return gzip.compress(json.dumps(idx).encode()),{'hafs':{'reader':{'base':base}}}
    def test_late_source_is_reported_from_complete_index(self):
        raw,cat=self.fixture();r=A.check_index('timings/hafs/reader.jz',raw,cat)
        self.assertFalse(r['ok']);self.assertEqual(r['entriesScanned'],301);self.assertEqual(r['surahsScanned'],2)
    def test_missing_catalog_cannot_imply_identity_success(self):
        raw,_=self.fixture()
        with self.assertRaisesRegex(ValueError,'catalog unavailable'):A.check_index('timings/hafs/reader.jz',raw,{})
    def test_wrong_key_identity_is_rejected(self):
        raw,cat=self.fixture()
        with self.assertRaisesRegex(ValueError,'identity mismatch'):A.check_index('timings/hafs/other.jz',raw,cat)
    def test_bounded_read_closes_body_and_rejects_oversize(self):
        body=io.BytesIO(b'12345')
        class Client:
            def get_object(self,**kw):return {'Body':body,'ETag':'etag'}
        with self.assertRaisesRegex(ValueError,'bounded read'):A.read_object(Client(),'bucket','key',4)
        self.assertTrue(body.closed)

if __name__=='__main__':unittest.main()
