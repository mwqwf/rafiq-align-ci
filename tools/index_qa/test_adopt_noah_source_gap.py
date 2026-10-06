import copy
import pathlib
import sys
import unittest
sys.path.insert(0,str(pathlib.Path(__file__).parent))
import adopt_noah_source_gap as A

class SourceGapAdoptionBinding(unittest.TestCase):
    def setUp(self):
        self.proof=dict(run_id=A.QA_RUN,commit=A.QA_COMMIT,intentionalDrop=dict(
            key=A.N.KEY,sha256=A.N.SHA,parentSha256=A.N.PARENT,surah=54,
            removedEntries=55,evidenceSha256=A.N.EVIDENCE_SHA))

    def test_exact_original_quality_cycle(self):
        A.validate_provenance(self.proof)

    def test_other_cycle_or_drop_scope_is_rejected(self):
        changes=[lambda p:p.update(run_id='another'),lambda p:p.update(commit='0'*40),
                 lambda p:p.pop('intentionalDrop')]
        for key,value in [('key','timings-staging/warsh/other.12345678.jz'),('sha256','0'*64),
                          ('parentSha256','0'*64),('surah',53),('removedEntries',54),('evidenceSha256','0'*64)]:
            changes.append(lambda p,k=key,v=value:p['intentionalDrop'].update({k:v}))
        for change in changes:
            proof=copy.deepcopy(self.proof);change(proof)
            with self.subTest(proof=proof),self.assertRaises(ValueError):A.validate_provenance(proof)

if __name__=='__main__':unittest.main()
