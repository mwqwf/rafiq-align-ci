import copy,datetime,unittest
from tools.ci_fleet.qa_recover_stalled import eligible
class RecoveryGuard(unittest.TestCase):
 def test_only_old_install_is_cancelled(self):
  now=datetime.datetime(2026,10,1,19,tzinfo=datetime.timezone.utc)
  run={'event':'workflow_dispatch','path':'.github/workflows/audio_qa.yml','status':'in_progress'}
  jobs=[{'status':'in_progress','steps':[{'status':'in_progress','name':'أدوات النظام','started_at':'2026-10-01T18:00:00Z'}]}]
  self.assertTrue(eligible(run,jobs,now))
  for field,value in [('event','push'),('path','.github/workflows/align.yml'),('status','completed')]:
   wrong=dict(run);wrong[field]=value;self.assertFalse(eligible(wrong,jobs,now))
  for field,value in [('name','تدقيق'),('started_at','2026-10-01T18:40:00Z'),('status','completed')]:
   wrong=copy.deepcopy(jobs);wrong[0]['steps'][0][field]=value;self.assertFalse(eligible(run,wrong,now))
  second=copy.deepcopy(jobs[0]);second['steps'][0]['name']='تدقيق';self.assertFalse(eligible(run,jobs+[second],now))
  self.assertFalse(eligible(run,[],now))
if __name__=='__main__':unittest.main()
