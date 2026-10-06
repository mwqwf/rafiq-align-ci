import pathlib,sys,json,copy,unittest
sys.path.insert(0,str(pathlib.Path(__file__).parent));import promote as P
sys.path.insert(0,str(pathlib.Path(__file__).parents[1]/'ci_fleet'));from source_registry import registered_source
class RegisteredIdentityTest(unittest.TestCase):
 def setUp(self):
  self.source=registered_source('hafs','qasm',2);self.base='https://server8.mp3quran.net/qasm/';self.cat={'hafs':{'qasm':{'base':self.base}}};self.idx={'riwaya':'hafs','reciterId':'qasm','entries':[{'ayahId':'1:1','fileRef':self.base+'001.mp3'},{'ayahId':'2:1','fileRef':self.source['url']}],'sourceBySurah':{'2':self.source['url']},'audioSha256':['a'*64,self.source['audio_sha256']]}
 def test_registered_exact_source_and_audio_sha_pass_same_catalog_identity(self):
  self.assertIsNone(P.catalog_gate(self.idx,self.cat));f=P.facts_of(self.idx)
  self.assertIsNone(P.catalog_gate_sources(f['riwaya'],f['reciterId'],f['catalogSourceRefsBySurah'],f['catalogSourceBySurah'],f['catalogAudioSha256'],self.cat))
 def test_declaration_without_actual_registered_identity_and_sha_is_rejected(self):
  changes=[lambda i:i.pop('sourceBySurah'),lambda i:i['sourceBySurah'].update({'2':'https://archive.org/download/'}),lambda i:i['audioSha256'].__setitem__(1,'b'*64),lambda i:i.pop('audioSha256'),lambda i:i['entries'][1].update(fileRef=self.source['url']+'?other=1'),lambda i:i.update(reciterId='another-reader'),lambda i:i['entries'][1].update(ayahId='3:1')]
  for change in changes:
   idx=copy.deepcopy(self.idx);change(idx)
   with self.subTest(change=change):self.assertIsNotNone(P.catalog_gate(idx,self.cat))
 def test_cached_facts_use_same_exact_identity_evidence(self):
  idx=copy.deepcopy(self.idx);idx.update(entries=[{'ayahId':f'{s}:1','fileRef':self.source['url'] if s==2 else self.base+f'{s:03d}.mp3'} for s in range(1,115)],refineVersion=6,ayahCount=6236,missing={'count':0,'ids':[]});idx['entries'] += [{'ayahId':'1:2','fileRef':self.base+'001.mp3'}]*(6236-114)
  f=P.facts_of(idx)
  # Stub only structural reconstruction: this test isolates identity parity.
  from unittest.mock import patch
  with patch.object(P,'index_gate',return_value=None):
   self.assertEqual(P.gate_facts(f,self.cat),P.catalog_gate(idx,self.cat));f['catalogAudioSha256'][1]='b'*64;self.assertIsNotNone(P.gate_facts(f,self.cat))
 def test_external_source_after_first_300_entries_is_checked(self):
  idx=copy.deepcopy(self.idx)
  idx['entries']=[{'ayahId':f'1:{i+1}','fileRef':self.base+'001.mp3'} for i in range(300)]+[idx['entries'][1]]
  self.assertIsNone(P.catalog_gate(idx,self.cat))
  idx['entries'][-1]['fileRef']='https://unregistered.example/another-reader/002.mp3'
  self.assertIsNotNone(P.catalog_gate(idx,self.cat))
  f=P.facts_of(idx)
  self.assertIn('https://unregistered.example/another-reader/002.mp3',f['refs'])
  self.assertIn('2',f['catalogSourceRefsBySurah'])
  from unittest.mock import patch
  with patch.object(P,'index_gate',return_value=None):self.assertIsNotNone(P.gate_facts(f,self.cat))
 def test_legacy_or_incomplete_cached_source_scan_requires_refresh(self):
  from unittest.mock import patch
  for field in ('catalogSourceScanVersion','catalogSourceScanEntries'):
   f=P.facts_of(self.idx);f.pop(field)
   with patch.object(P,'index_gate',return_value=None):self.assertIn('قديمة أو جزئية',P.gate_facts(f,self.cat))
  f=P.facts_of(self.idx);f['catalogSourceScanEntries']=1
  with patch.object(P,'index_gate',return_value=None):self.assertIn('قديمة أو جزئية',P.gate_facts(f,self.cat))
if __name__=='__main__':unittest.main()
