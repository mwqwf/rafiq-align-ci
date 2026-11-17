"""استعادة دليل الغياب: سلسلة مثبتة ونسخ حرفي لا باب عام لتعديل transform."""
import copy,gzip,hashlib,json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import gap_metadata_restore as g
from test_drop_ayahs import _make
from declarations import prior_declarations

def packed(doc):return gzip.compress(json.dumps(doc,ensure_ascii=False).encode(),mtime=0)
def fixtures():
 src=_make();src['audioSha256']=['a'*64]*114
 raw=packed(src);sha=hashlib.sha256(raw).hexdigest();key=f'timings-staging/hafs/x.{sha[:8]}.jz'
 parent=copy.deepcopy(src);parent['transform']={'op':'heard_pin:79','fromKey':key,'fromSha256':sha,'reasonCode':'TIMING_UNDER_REPAIR','reasonUser':'حي'}
 # يختلف حد حاضر عن الأب؛يجب إبقاؤه وليس الرجوع إليه.
 parent['entries'][0]['startMs']+=123
 psha=hashlib.sha256(packed(parent)).hexdigest()
 cand=copy.deepcopy(parent);cand['transform'].update(declarations=prior_declarations(src),truncatedGaps=copy.deepcopy(src['transform']['truncatedGaps']),op='heard_pin:79|declare_gap:79')
 plan={'version':1,'parentSha256':psha,'nodes':[{'key':key,'sha256':sha,'file':'a.jz'}],'restore':[{'surah':79,'sourceSha256':sha}]}
 return src,parent,cand,psha,plan,{'a.jz':raw}
class Restore(unittest.TestCase):
 def test_accepts_and_keeps_later_boundaries_without_mutation(self):
  src,p,c,sha,plan,blobs=fixtures();before=copy.deepcopy((p,c,plan));v=g.verify(p,c,sha,plan,blobs.__getitem__);self.assertEqual(v['sources'][0]['surah'],79);self.assertEqual((p,c,plan),before);self.assertNotEqual(p['entries'],src['entries'])
 def test_records_original_reference_separately_from_archived_copy(self):
  _,p,c,sha,plan,b=fixtures();p['transform']['fromKey']='timings/hafs/x.jz';c['transform']['fromKey']='timings/hafs/x.jz'
  proof=g.verify(p,c,sha,plan,b.__getitem__)['sources'][0]
  self.assertEqual(proof['sourceKey'],'timings/hafs/x.jz')
  self.assertEqual(proof['archiveKey'],plan['nodes'][0]['key'])

 def test_rejects_stale_parent_and_source_bytes(self):
  _,p,c,sha,plan,b=fixtures()
  with self.assertRaises(ValueError):g.verify(p,c,'f'*64,plan,b.__getitem__)
  b['a.jz']+=b'bad'
  with self.assertRaises(ValueError):g.verify(p,c,sha,plan,b.__getitem__)
 def test_witness_copy_and_existing_live_witness_not_overwritten(self):
  for existing in (None, {'15': {'runId':'older'}}, {'15': {'runId':'newer'}}):
   src,p,c,sha,plan,b=fixtures();claims={'15': {'runId':'older'}}
   src['transform'].update(witnessedAbsent={'79':claims},witnessedAbsentVersion='v1')
   raw=packed(src);ss=hashlib.sha256(raw).hexdigest();key=f'timings-staging/hafs/x.{ss[:8]}.jz';b['a.jz']=raw;plan['nodes'][0].update(key=key,sha256=ss);plan['restore'][0]['sourceSha256']=ss
   p['transform'].update(fromKey=key,fromSha256=ss);c['transform'].update(fromKey=key,fromSha256=ss,witnessedAbsent={'79':copy.deepcopy(claims)},witnessedAbsentVersion='v1')
   if existing is not None:p['transform'].update(witnessedAbsent={'79':copy.deepcopy(existing)},witnessedAbsentVersion='v1')
   if existing is not None and existing!=claims:
    with self.assertRaisesRegex(ValueError,'شاهد حي مختلف'):g.verify(p,c,sha,plan,b.__getitem__)
   else:self.assertTrue(g.verify(p,c,sha,plan,b.__getitem__)['sources'])

 def test_rejects_candidate_changes(self):
  for mut in [lambda x:x['entries'][0].update(startMs=1),lambda x:x['audioSha256'].__setitem__(78,'c'*64),lambda x:x.update(reciterId='other'),lambda x:x['missing']['ids'].remove('79:15'),lambda x:x['transform'].update(reason='new'),lambda x:x['transform'].update(fromSha256='f'*64),lambda x:x['transform']['truncatedGaps']['79']['evidence'].clear(),lambda x:x['transform']['declarations']['79'].update(reasonCode='OTHER'),lambda x:x['transform'].update(unknown='not allowed')]:
   _,p,c,sha,plan,b=fixtures();mut(c)
   with self.subTest(mutation=mut),self.assertRaises(ValueError):g.verify(p,c,sha,plan,b.__getitem__)
 def test_rejects_unlinked_source(self):
  _,p,c,sha,plan,b=fixtures();p['transform']['fromSha256']='f'*64
  with self.assertRaises(ValueError):g.verify(p,c,sha,plan,b.__getitem__)
 def test_rejects_other_key(self):
  _,p,c,sha,plan,b=fixtures();plan['nodes'][0]['key']='timings/hafs/other.jz'
  with self.assertRaises(ValueError):g.verify(p,c,sha,plan,b.__getitem__)
 def test_rejects_existing_declaration(self):
  _,p,c,sha,plan,b=fixtures();p['transform']['truncatedGaps']=copy.deepcopy(c['transform']['truncatedGaps'])
  with self.assertRaises(ValueError):g.verify(p,c,sha,plan,b.__getitem__)
 def test_rejects_duplicate_and_extra_nodes(self):
  _,p,c,sha,plan,b=fixtures();plan['nodes']*=2
  with self.assertRaises(ValueError):g.verify(p,c,sha,plan,b.__getitem__)
 def test_rejects_duplicate_surah(self):
  _,p,c,sha,plan,b=fixtures();plan['restore']*=2
  with self.assertRaises(ValueError):g.verify(p,c,sha,plan,b.__getitem__)
 def test_rejects_intermediate_audio_or_gap_change(self):
  for kind in ('audio','gap'):
   _,p,c,sha,plan,b=fixtures();mid=copy.deepcopy(p)
   if kind=='audio':mid['audioSha256'][78]='c'*64
   else:mid['missing']['ids'].remove('79:15')
   raw=packed(mid);msha=hashlib.sha256(raw).hexdigest();mkey=f'timings-staging/hafs/x.{msha[:8]}.jz';b['mid']=raw;plan['nodes'].append({'key':mkey,'sha256':msha,'file':'mid'});p['transform'].update(fromKey=mkey,fromSha256=msha);c['transform'].update(fromKey=mkey,fromSha256=msha)
   with self.subTest(kind=kind),self.assertRaises(ValueError):g.verify(p,c,sha,plan,b.__getitem__)
if __name__=='__main__':unittest.main()
