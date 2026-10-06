"""رفض السياق الناقص أو المتعارض قبل إنشاء أي مرشح."""
import copy,json,sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent))
import build_short_final_repairs as B
class Rejections(unittest.TestCase):
    def setUp(self):
        self.spec=json.loads((B.ROOT/'ops/source-repair/codex-short-final-shuba-deban-shuba-89-spec.json').read_text())
        self.report=B.checked(self.spec['reportPath'],self.spec['reportSha256'])
    def reject(self,change,message):
        report=copy.deepcopy(self.report);change(report);original=B.checked
        def checked(path,sha,z=False):
            return report if path==self.spec['reportPath'] else original(path,sha,z)
        with patch.object(B,'checked',side_effect=checked),self.assertRaisesRegex(ValueError,message):B.build(self.spec)
    def test_reject_missing_native_channel(self):
        self.reject(lambda r:r['measurements'].pop(),'مصفوفة')
    def test_reject_weak_final_verse(self):
        self.reject(lambda r:r['measurements'][0]['rawEntries'][-1].update(conf=.59),'ثقة ضعيفة')
    def test_reject_disagreeing_final_start(self):
        self.reject(lambda r:r['measurements'][0]['rawEntries'][-1].update(startMs=190000),'خلاف بداية')
    def test_reject_clipped_eof(self):
        self.reject(lambda r:r['audio']['decoded'].update(windowEndSampleExclusive=2000000),'لم يقس الملف')
    def test_reject_missing_raw_free_evidence(self):
        self.reject(lambda r:r['freeResults'][0]['rawChunks'][0].update(rawPartSha256='0'*64),'الخام ناقص')
    def test_reject_unknown_native_channels(self):
        self.reject(lambda r:r['audio']['decoded'].update(nativeChannels=3),'عدد القنوات')
    def test_reject_changed_audio_source(self):
        self.reject(lambda r:r['source'].update(sha256='0'*64),'خطة القياس')
if __name__=='__main__':unittest.main()
