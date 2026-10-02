import copy, pathlib, sys, unittest
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from qa_dispatch_guard import has_current_manual_sample as sample
import cancel_duplicate_kalbani_qa as C

class DispatchGuardTests(unittest.TestCase):
    def test_only_actual_current_manual_evidence_suppresses_duplicate(self):
        r = {'sha256': 'a'*64, 'source': 'ci', 'sample': {'seedSalt': 'rs1', 'rows': [{'aid': '2:1'}]}}
        self.assertTrue(sample(r, 'a'*64))
        for field, val in [('sha256', 'b'*64), ('source', 'local'), ('sample', {}),
                           ('sample', {'seedSalt':'k1', 'rows':[{}]})]:
            q = copy.deepcopy(r); q[field] = val
            self.assertFalse(sample(q, 'a'*64))
    def test_only_bound_duplicate_run_can_be_cancelled(self):
        r = {'id':36955080830, 'path':'.github/workflows/audio_qa.yml',
             'display_title':f'qa {C.KEY} · salt=k1 · n=20', 'event':'workflow_dispatch',
             'status':'in_progress', 'repository':{'full_name':'mwqwf/rafiq-align-ci','private':False}}
        self.assertTrue(C.eligible(r))
        for field, val in [('id',36953321617), ('path','.github/workflows/splice_census.yml'),
                           ('display_title','other'), ('event','schedule'), ('status','completed'),
                           ('repository',{'full_name':'mwqwf/QuranRafiq','private':True})]:
            q = copy.deepcopy(r); q[field] = val
            self.assertFalse(C.eligible(q))

if __name__ == '__main__': unittest.main()
