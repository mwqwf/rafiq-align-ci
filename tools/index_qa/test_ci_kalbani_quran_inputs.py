import pathlib,sys,unittest,json,copy,unicodedata
sys.path.insert(0,str(pathlib.Path(__file__).parent))
import ci_kalbani_quran_inputs as T
class TargetInputTests(unittest.TestCase):
 def setUp(self):
  self.previous=T.Q._VOCAB;T.Q._VOCAB={chr(n):n for n in range(0x600,0x700) if unicodedata.category(chr(n)).startswith('L')}
 def tearDown(self):
  T.Q._VOCAB=self.previous
 def test_only_explicit_target_is_normalized(self):
  refs=['وَمَن يَرْغَبُ عَن مِلَّةِ إِبْرَٰهِـۧمَ','وَمَن يَرْغَبُ عَن مِلَّةِ إِبْرَٰهِـۧمَ','وَمَن يَرْغَبُ عَن مِلَّةِ إِبْرَٰهِـۧمَ'];original=copy.deepcopy(refs)
  for method in T.METHODS[1:]:
   got=T.target_inputs(refs,1,3,2,method)
   self.assertEqual(got[0],T.Q.reference_text(refs[0]));self.assertEqual(got[2],T.Q.reference_text(refs[2]));self.assertEqual(got[1],T.Q.reference_text(T.alignment_variant(refs[1],method)));self.assertEqual(refs,original)
 def test_unbounded_target_or_unknown_input_rejected(self):
  for args in [(1,3,4,'common.norm'),(0,3,2,'common.norm'),(1,4,2,'common.norm'),(1,3,2,'arbitrary'),(1,3,2,'canonical')]:
   with self.assertRaises(ValueError):T.target_inputs(['أ','ب','ج'],*args)
 def test_actual_plan_binds_original_native_sources(self):
  plan=json.loads((T.ROOT/'ops/source-repair/kalbani-float-quran-input-plan-20261002.json').read_text());sources=json.loads((T.ROOT/'ops/source-repair/kalbani-clean-vorbis-source-evidence-20261001.json').read_text())['sources']
  for s in plan['surahs']:
   req,src=T.G.validated_plan(plan,sources,s['surah']);begin,end,_=T.G.surah_slice(T.G.load_index(),s['surah']);refs=T.G.load_text('hafs')[begin:end]
   for win in req['windows']:T.target_inputs(refs,*win['range'],win['target'],'common.norm')
if __name__=='__main__':unittest.main()
