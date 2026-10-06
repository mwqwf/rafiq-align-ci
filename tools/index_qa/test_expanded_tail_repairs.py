"""رفض الفجوات وضعف القياس والمصفوفات الناقصة قبل كتابة المرشح."""
import copy,json,sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent))
import build_expanded_tail_repairs as B
class Rejections(unittest.TestCase):
    def setUp(self):self.spec=json.loads((B.ROOT/'ops/source-repair/codex-badr56-expanded-tail-spec.json').read_text())
    def reject_report(self,change,message):
        ctx=self.spec['contexts'][0];report=B.S.checked(ctx['reportPath'],ctx['reportSha256']);change(report);original=B.S.checked
        def checked(path,sha,z=False):return report if path==ctx['reportPath'] else original(path,sha,z)
        with patch.object(B.S,'checked',side_effect=checked),self.assertRaisesRegex(ValueError,message):B.build(self.spec)
    def test_reject_missing_channel(self):self.reject_report(lambda r:r['measurements'].pop(),'مصفوفة ناقصة')
    def test_reject_weak_alignment(self):self.reject_report(lambda r:r['measurements'][0]['rawEntries'][0].update(conf=.44),'ثقة دون')
    def test_reject_model_disagreement(self):self.reject_report(lambda r:r['measurements'][0]['rawEntries'][0].update(startMs=372000),'خلاف بين')
    def test_reject_gap_between_contexts(self):
        self.spec['contexts'][0]['targetAyahs']=list(range(79,86))
        with self.assertRaisesRegex(ValueError,'الخاتمة غير متصلة'):B.build(self.spec)
    def test_reject_source_from_another_parent(self):
        self.spec['parentSha256']='0'*64
        with self.assertRaisesRegex(ValueError,'تغير الدليل'):B.build(self.spec)
    def test_reject_tail_without_eof(self):
        self.spec['contexts']=self.spec['contexts'][:1]
        with self.assertRaisesRegex(ValueError,'الخاتمة غير متصلة'):B.build(self.spec)
if __name__=='__main__':unittest.main()
