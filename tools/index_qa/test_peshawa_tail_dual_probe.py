import types
import unittest
from tools.index_qa import peshawa_tail_dual_probe as P


class TargetDiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.contract = types.SimpleNamespace(TARGET_CONF=.60, START_TOL=500, END_TOL=800)
        self.target = {'startMs': 264706, 'endMs': 282300}

    def row(self, start=264706, end=282300, conf=.6):
        return {'windowMs': [264000,284724],
                'entries': [{'startMs':start,'endMs':end,'conf':conf}]}

    def test_existing_thresholds_are_preserved(self):
        for kwargs, accepted in (({},True), ({'conf':.599},False),
                                 ({'start':265207},False), ({'end':281499},False)):
            row=self.row(**kwargs)
            P.assess(row,self.target,self.contract)
            self.assertEqual(row['withinExistingTargetThresholds'],accepted)

    def test_partial_or_invalid_audio_interval_is_rejected(self):
        for kwargs in ({'start':263999},{'end':284725},{'end':264706},
                       {'conf':float('nan')},{'conf':1.1}):
            with self.assertRaises(ValueError):
                P.assess(self.row(**kwargs),self.target,self.contract)


if __name__=='__main__':
    unittest.main()
