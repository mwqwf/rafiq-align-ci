"""Mutation tests for the one explicitly authorized whole-surah drop."""
import copy
import gzip
import json
import unittest
from pathlib import Path
import noah_source_gap_quality as N

class BoundSourceGapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.blob=(N.ROOT/'ops/source-repair/candidates/codex-noah-warsh54-drop-20261006.jz').read_bytes()
        cls.parent_blob=(N.ROOT/'ops/source-repair/parents/codex-warsh-noah_warsh-17191c80.jz').read_bytes()
        cls.idx=json.loads(gzip.decompress(cls.blob))
        cls.parent=json.loads(gzip.decompress(cls.parent_blob))

    def test_exact_authorized_drop_and_measured_source(self):
        idx,parent=N.validate_binding(N.KEY,N.SHA,N.PARENT,self.blob,self.parent_blob)
        N.validate_evidence(parent)
        self.assertEqual(len(idx['entries']),6181)

    def test_changed_bytes_or_other_candidate_rejected(self):
        for args in [(N.KEY,N.SHA,N.PARENT,self.blob+b'x',self.parent_blob),
                     (N.KEY,N.SHA,N.PARENT,self.blob,self.parent_blob+b'x'),
                     (N.KEY,'0'*64,N.PARENT,self.blob,self.parent_blob),
                     ('timings-staging/warsh/other.b99262ae.jz',N.SHA,N.PARENT,self.blob,self.parent_blob)]:
            with self.subTest(args=args[:3]),self.assertRaises(ValueError):
                N.validate_binding(*args)

    def test_unrelated_or_partial_changes_rejected(self):
        def timing(d): d['entries'][0]['startMs']+=1
        def confidence(d): d['entries'][0]['conf']=0.99
        def partial(d): d['entries'].append(next(e for e in self.parent['entries'] if e['ayahId']=='54:1'))
        def missing(d): d['missing']['count']=54
        def source(d): d['audioSha256'][0]='0'*64
        def low(d): d['lowCount']+=1
        def reason(d): d['transform']['reasonCode']='UNKNOWN'
        def engine(d): d['engineBySurah']['54']='ctc-quran-window-1'
        for mutate in (timing,confidence,partial,missing,source,low,reason,engine):
            candidate=copy.deepcopy(self.idx);mutate(candidate)
            with self.subTest(mutation=mutate.__name__),self.assertRaises(ValueError):
                N.validate_documents(candidate,self.parent)

if __name__=='__main__': unittest.main()
