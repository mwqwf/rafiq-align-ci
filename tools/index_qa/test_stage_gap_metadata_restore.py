"""تكامل الفرع الصريح: dry-run حقيقي ببديل قراءة فقط،والبوابات لا تُسقط."""
import contextlib,gzip,hashlib,io,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent))
import stage_transform as st
import promote
from test_gap_metadata_restore import fixtures,packed
class Stage(unittest.TestCase):
 def setup_case(self,tmp):
  src,p,c,sha,plan,blobs=fixtures();P=Path(tmp)
  for name,blob in blobs.items():(P/name).write_bytes(blob)
  (P/'plan.json').write_text(json.dumps(plan));(P/'input.jz').write_bytes(packed(c))
  parent_raw=packed(p);self.assertEqual(hashlib.sha256(parent_raw).hexdigest(),sha)
  class RO:
   def get_object(self,**kw):
    if kw['Key']!='timings/hafs/x.jz':raise AssertionError(kw)
    return {'Body':io.BytesIO(parent_raw)}
   def put_object(self,**kw):raise AssertionError('WRITE FORBIDDEN')
  args=['stage_transform','--file',str(P/'input.jz'),'--parent','timings/hafs/x.jz','--parent-sha',sha,'--op','restore_gap_declarations','--reason','إصلاح دليل الغياب','--metadata-only','دليل الحجب','--manual-qa-only','--restore-gap-evidence',str(P/'plan.json')]
  return p,c,sha,args,RO()
 def run_case(self,p,c,sha,args,client):
  output=[];compress=gzip.compress
  def capture(data,*a,**kw):
   b=compress(data,*a,**kw);output.append(b);return b
  with patch.object(st.promote,'s3',return_value=(client,'offline')),patch.object(sys,'argv',args),patch.object(st.promote,'index_gate',return_value=None) as ig,patch.object(st.promote,'catalog_gate',return_value=None) as cg,patch.object(st.promote,'catalog',return_value={}),patch.object(st.gzip,'compress',side_effect=capture),contextlib.redirect_stdout(io.StringIO()) as buf:
   st.main()
   self.assertTrue(ig.called and cg.called)
  self.assertEqual(len(output),1);return json.loads(gzip.decompress(output[0])),buf.getvalue()
 def test_explicit_restore_keeps_entries_origin_and_manual_policy(self):
  with tempfile.TemporaryDirectory() as tmp:
   p,c,sha,args,client=self.setup_case(tmp);out,log=self.run_case(p,c,sha,args,client)
   self.assertEqual(out['entries'],p['entries']);tr=out['transform'];self.assertEqual(tr['fromKey'],'timings/hafs/x.jz');self.assertEqual(tr['fromSha256'],sha);self.assertEqual(tr['provenance']['publishedParentTransform'],p['transform']);self.assertEqual(tr['qaDispatch']['mode'],'manual-free-only');self.assertTrue(promote.declared_truncated_gaps(out,79)[0]);self.assertIn('عرضٌ فقط',log)
 def test_legacy_transform_only_still_rejected(self):
  with tempfile.TemporaryDirectory() as tmp:
   p,c,sha,args,client=self.setup_case(tmp);args=args[:-2]
   with self.assertRaisesRegex(SystemExit,'لا مداخلَ تغيّرت ولا ترويسة'):self.run_case(p,c,sha,args,client)
 def test_missing_required_flags_wrong_op_and_short_hash_refused(self):
  for flag in ('--metadata-only','--manual-qa-only','--op','--parent-sha'):
   with tempfile.TemporaryDirectory() as tmp:
    p,c,sha,args,client=self.setup_case(tmp);i=args.index(flag)
    if flag=='--metadata-only':del args[i:i+2]
    elif flag=='--manual-qa-only':del args[i]
    elif flag=='--op':args[i+1]='arbitrary'
    elif flag=='--parent-sha':args[i+1]=sha[:8]
    with self.subTest(flag=flag),self.assertRaises(SystemExit):self.run_case(p,c,sha,args,client)
 def test_invalid_evidence_stops_before_gates(self):
  with tempfile.TemporaryDirectory() as tmp:
   p,c,sha,args,client=self.setup_case(tmp);(Path(tmp)/'a.jz').write_bytes(b'wrong')
   with self.assertRaisesRegex(SystemExit,'بايتات الأب'):self.run_case(p,c,sha,args,client)
if __name__=='__main__':unittest.main()
