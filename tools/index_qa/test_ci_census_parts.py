import copy
import hashlib
import pathlib
import sys
import unittest
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import ci_census_parts as C
import run as R

class ParallelCensusTests(unittest.TestCase):
    def setUp(self):
        self.sha='a'*64; self.key='timings-staging/hafs/example.aaaaaaaa.jz'
        self.text=['بسم الله الرحمن الرحيم']*6236
        self.idx={'entries':[{'ayahId':f'{s}:1','startMs':4000,'fileRef':f'https://example.org/{s}.ogg'} for s in [2,3]],'audioSha256':['b'*64]*114,'engineVersion':'whisper','engineBySurah':{'2':'ctc','3':'ctc'}}
        self.parts=[]
        for s in [2,3]:
            text='الحمد لله رب العالمين';self.text[R.flat(s,1)]=text
            v,k,w=R.judge(text,R.BASMALA,text,'',text,no_pre=False)
            row={'aid':f'{s}:1','cluster':s,'verdict':v,'kind':k,'why':w,'heard':{'fwd':text,'dec':'','long':text}}
            self.parts.append({'key':self.key,'sha256':self.sha,'kind':'splice-census-part','source':'ci','runId':'123','engine':'pywhispercpp/ggml-q8 (tiny-ar-quran)','fatal':[],'warn':[],'openers':[],'census':{'surahs':[s],'population':1},'sample':{'rows':[row],'errors':0,'errorWindows':{}},'partProvenance':{'surah':s,'runSha':'commit','toolSha256':'tool','canonicalSha256':'text','modelSha256':'c'*64,'sourceBinding':C.source_binding(self.idx,s)}})
    def call(self,parts=None):
        return C.aggregate(self.idx,self.sha,self.key,self.parts if parts is None else parts,'123','commit',self.text,'text','tool')
    def test_complete_union_preserves_actual_transcripts(self):
        out=self.call();self.assertEqual(out['census']['surahs'],[2,3]);self.assertEqual(out['census']['population'],2)
        self.assertEqual(out['sample']['rows'],[x['sample']['rows'][0] for x in self.parts]);self.assertEqual(out['sample']['errors'],0);self.assertEqual(len(out['parallelCensus']['parts']),2)
    def test_missing_and_duplicate_parts_rejected(self):
        for parts in [self.parts[:1],[self.parts[0],copy.deepcopy(self.parts[0])]]:
            with self.assertRaises(ValueError):self.call(parts)
    def test_wrong_identity_and_provenance_rejected(self):
        for field,value in [('sha256','x'*64),('key','different'),('kind','audio'),('source','local'),('runId','124'),('engine','other')]:
            parts=copy.deepcopy(self.parts);parts[0][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):self.call(parts)
        for field,value in [('runSha','other'),('toolSha256','other'),('canonicalSha256','other'),('modelSha256','d'*64),('sourceBinding',{}),('surah',4)]:
            parts=copy.deepcopy(self.parts);parts[0]['partProvenance'][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):self.call(parts)
    def test_missing_duplicate_or_wrong_rows_rejected(self):
        for rows in [[],self.parts[0]['sample']['rows']*2,[{**self.parts[0]['sample']['rows'][0],'aid':'2:2'}],[{**self.parts[0]['sample']['rows'][0],'cluster':3}]]:
            parts=copy.deepcopy(self.parts);parts[0]['sample']['rows']=rows
            with self.assertRaises(ValueError):self.call(parts)
    def test_raw_verdict_cannot_be_changed(self):
        for field,value in [('verdict','بريء fabricated'),('kind','جسيم'),('why','invented'),('heard',{})]:
            parts=copy.deepcopy(self.parts);parts[0]['sample']['rows'][0][field]=value
            with self.assertRaises(ValueError):self.call(parts)
    def test_failed_windows_are_retained(self):
        self.parts[0]['sample'].update(errors=1,errorWindows={'D|2:1':'actual decode error'})
        out=self.call();self.assertEqual(out['sample']['errors'],1);self.assertEqual(out['sample']['errorWindows'],{'2/D|2:1':'actual decode error'})
    def test_unavailable_row_requires_failure(self):
        self.parts[0]['sample']['rows'][0]={'aid':'2:1','cluster':2,'verdict':'تعذّر','kind':'غير حاسم','why':'decode error'}
        with self.assertRaises(ValueError):self.call()
        self.parts[0]['sample']['errors']=1
        self.assertEqual(self.call()['sample']['rows'][0]['verdict'],'تعذّر')
    def test_fatal_cannot_disappear(self):
        self.parts[1]['fatal']=['actual corruption'];out=self.call();self.assertEqual(out['fatal'],['actual corruption']);self.assertTrue(out['verdict'].startswith('مرفوض'))
    def test_conflicting_openers_rejected(self):
        self.parts[0]['openers']=[{'surah':2,'heard':'one'}];self.parts[1]['openers']=[{'surah':2,'heard':'two'}]
        with self.assertRaises(ValueError):self.call()
    def test_part_namespace_is_immutable_and_bounded(self):
        self.assertEqual(C.part_key(self.sha,'123',2),f'state-census-parts/{self.sha}/123/002.json')
        for args in [('invalid','123',2),(self.sha,'../',2),(self.sha,'123',115)]:
            with self.assertRaises(ValueError):C.part_key(*args)


class PriorReplace(unittest.TestCase):
    """fixV 2026-10-05: only a same-SHA report with untranscribed windows may be replaced."""
    def test_errors_report_replaceable(self):
        from ci_census_parts import prior_has_errors
        self.assertTrue(prior_has_errors({'sample': {'errors': 1}}))

    def test_complete_report_preserved(self):
        from ci_census_parts import prior_has_errors
        for prior in ({'sample': {'errors': 0}}, {'sample': {}}, {}, {'sample': {'errors': True}},
                      {'sample': {'errors': '3'}}, None):
            self.assertFalse(prior_has_errors(prior))


if __name__=='__main__':unittest.main()
