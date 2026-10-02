import pathlib,sys,unittest,copy,json
from unittest.mock import Mock
sys.path.insert(0,str(pathlib.Path(__file__).parent))
import ci_census_plan as C
class ImmutablePlanTests(unittest.TestCase):
 def setUp(self):self.rows=[{'key':'timings-staging/hafs/a_klb.f033e3fe.jz','sha':'a'*64,'surahs':[2,3,5]}];self.run='42';self.commit='b'*40
 def test_exact_snapshot_is_written_once_without_job_output_sha(self):
  cl=Mock();d=C.write_plan(cl,'bucket',self.rows,self.run,self.commit);kw=cl.put_object.call_args.kwargs
  self.assertEqual(kw['IfNoneMatch'],'*');self.assertEqual(kw['Key'],'state-census-plans/42/plan.json');self.assertEqual(json.loads(kw['Body']),d);C.validate_plan(d,self.run,self.commit)
 def test_wrong_actual_run_commit_producer_or_source_digest_is_rejected(self):
  plan=C.make_plan(self.rows,self.run,self.commit)
  for field,val in [('runId','43'),('runSha','c'*40),('toolSha256','d'*64)]:
   d=copy.deepcopy(plan);d[field]=val
   with self.assertRaises(ValueError):C.validate_plan(d,self.run,self.commit)
  for field,val in [('sha','not-a-digest'),('key','timings/hafs/a_klb.jz'),('surahs',[2,2]),('surahs',[0]),('surahs',[3,2])]:
   d=copy.deepcopy(plan);d['candidates'][0][field]=val
   with self.assertRaises(ValueError):C.validate_plan(d,self.run,self.commit)
 def test_duplicate_candidates_and_foreign_run_namespace_are_rejected(self):
  with self.assertRaises(ValueError):C.make_plan(self.rows*2,self.run,self.commit)
  with self.assertRaises(ValueError):C.plan_key('../42')
if __name__=='__main__':unittest.main()
