import copy
import json
import unittest
from pathlib import Path
from cancel_duplicate_kalbani_qa import REJECTED_RUNS, KEY, SHA, rejection_valid, rejected_run_eligible

class RejectedCandidateCancellation(unittest.TestCase):
    def test_only_two_exact_runs(self):
        for ident,(path,title) in REJECTED_RUNS.items():
            run={'id':ident,'path':path,'display_title':title,'event':'workflow_dispatch','status':'in_progress','repository':{'full_name':'mwqwf/rafiq-align-ci','private':False}}
            self.assertTrue(rejected_run_eligible(run))
            for k,v in [('id',36953321617),('path','wrong'),('display_title','wrong'),('event','push'),('status','completed'),('repository',{'full_name':'mwqwf/rafiq-align-ci','private':True})]:
                r=copy.deepcopy(run);r[k]=v;self.assertFalse(rejected_run_eligible(r))
    def test_actual_required_negative_only(self):
        r={'sha256':SHA,'source':'ci','runId':'36953910660','sample':{'rows':[{'aid':'5:34','kind':'جسيم','verdict':'LATE_START','heard':{'fwd':'فاعلموا','dec':'قبل','long':'فاعلموا'}}]}}
        self.assertTrue(rejection_valid(r))
        for k,v in [('sha256','0'*64),('source','local'),('runId','other'),('sample',{'rows':[]})]:
            d=copy.deepcopy(r);d[k]=v;self.assertFalse(rejection_valid(d))
        for k,v in [('kind','بريء'),('verdict','unknown'),('aid','5:35'),('heard',{})]:
            d=copy.deepcopy(r);d['sample']['rows'][0][k]=v;self.assertFalse(rejection_valid(d))

if __name__=='__main__':unittest.main()
