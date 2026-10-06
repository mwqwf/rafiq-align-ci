"""اختبارات رفض العبث بأدلة استعادة المصدر؛ لا نماذج ولا شبكة."""
import copy,json,unittest
from pathlib import Path
import build_iraoui_publisher_repair as B
class EvidenceTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.specs=json.loads((B.ROOT/'ops/source-repair/codex-iraoui-full-native-spec.json').read_text())
  cls.reports={s['id']:B.context(s) for s in cls.specs}
  cls.full=B.S.checked(B.REPORT,B.REPORT_SHA)['alignment']
 def test_complete_actual_evidence_and_confidence(self):
  a,changes=B.refine(self.full,self.reports)
  self.assertEqual(len(changes),8);self.assertEqual(a['entries'][-1]['endMs'],B.FRAMES*1000//16000)
  for i in [14,43]:self.assertEqual(a['entries'][i]['conf'],self.full['entries'][i]['conf'])
 def test_missing_context_fails(self):
  d=dict(self.reports);del d['iraoui41_new_50_full']
  with self.assertRaises(ValueError):B.refine(self.full,d)
 def test_wrong_raw_hash_fails(self):
  s=dict(self.specs[0]);s['bundleSha256']='0'*64
  with self.assertRaises(ValueError):B.context(s)
 def test_wrong_job_fails(self):
  s=dict(self.specs[0]);s['jobId']+=1
  with self.assertRaises(ValueError):B.context(s)
 def test_model_disagreement_fails(self):
  d=copy.deepcopy(self.reports);d['iraoui41_new_50_full']['measurements'][0]['rawEntries'][0]['startMs']+=2000
  with self.assertRaises(ValueError):B.refine(self.full,d)
 def test_weak_tail_quran_fails(self):
  d=copy.deepcopy(self.reports)
  next(m for m in d['iraoui41_new_50_full']['measurements'] if m['model']=='quran')['rawEntries'][0]['conf']=.1
  with self.assertRaises(ValueError):B.refine(self.full,d)
 def test_incomplete_eof_fails(self):
  d=copy.deepcopy(self.reports);d['iraoui41_new_53_54']['audio']['decoded']['windowEndSampleExclusive']-=1
  with self.assertRaises(ValueError):B.refine(self.full,d)
if __name__=='__main__':unittest.main()
