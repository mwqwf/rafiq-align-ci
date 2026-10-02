import copy,json,pathlib,sys,unittest,shutil,subprocess,tempfile
sys.path.insert(0,str(pathlib.Path(__file__).parent))
import ci_kalbani_generic as C
class SourcePlanTests(unittest.TestCase):
 def setUp(self):
  self.plan=json.loads((C.ROOT/'ops/source-repair/kalbani-float-generic-plan-20261002.json').read_text());self.sources=json.loads((C.ROOT/'ops/source-repair/kalbani-clean-vorbis-source-evidence-20261001.json').read_text())['sources'];self.s=self.plan['surahs'][0]['surah']
 def test_actual_sources_and_physical_contexts_validate(self):
  for row in self.plan['surahs']:C.validated_plan(self.plan,self.sources,row['surah'])
 def test_arbitrary_identity_and_source_rejected(self):
  for field,value in [('reciterId','other'),('riwaya','warsh'),('canonicalTextChanged',True),('productionChanged',True)]:
   d=copy.deepcopy(self.plan);d[field]=value
   with self.assertRaises(ValueError):C.validated_plan(d,self.sources,self.s)
  for field,value in [('sourceSha256','f'*64),('sourceUrl','https://other.example/audio')]:
   d=copy.deepcopy(self.plan);d['surahs'][0][field]=value
   with self.assertRaises(ValueError):C.validated_plan(d,self.sources,self.s)
 def test_missing_and_duplicate_sources_rejected(self):
  for rows in [[],self.sources+self.sources]:
   with self.assertRaises(ValueError):C.validated_plan(self.plan,rows,self.s)
 def test_modified_publisher_bytes_rejected(self):
  for field,value in [('sourceBytesChanged',True),('locallyTranscoded',True),('decoderErrors','actual error'),('decodeRc',1)]:
   sources=copy.deepcopy(self.sources);next(x for x in sources if x['surah']==self.s)[field]=value
   with self.assertRaises(ValueError):C.validated_plan(self.plan,sources,self.s)
 def test_unbounded_or_nonphysical_context_rejected(self):
  for win in [{'range':[1,1000],'windowMs':[0,10000]},{'range':[1,5],'windowMs':[-1,10000]},{'range':[1,5],'windowMs':[0,99999999]},{'range':[1,5],'windowMs':[0,1200001]}]:
   d=copy.deepcopy(self.plan);d['surahs'][0]['windows']=[win]
   with self.assertRaises(ValueError):C.validated_plan(d,self.sources,self.s)
 @unittest.skipUnless(shutil.which('ffmpeg'),'Native integration requires ffmpeg')
 def test_real_vorbis_decoder_api_and_millisecond_units(self):
  with tempfile.TemporaryDirectory() as td:
   audio=pathlib.Path(td)/'physical.ogg'
   subprocess.run(['ffmpeg','-nostdin','-v','error','-f','lavfi','-i','sine=frequency=440:sample_rate=16000','-t','1.2','-c:a','libvorbis',str(audio)],check=True)
   pcm=C.native_pcm(audio,1200)
   self.assertEqual(str(pcm.dtype),'float32');self.assertLessEqual(abs(len(pcm)-19200),32)
   with self.assertRaises(ValueError):C.native_pcm(audio,1000)
if __name__=='__main__':unittest.main()
