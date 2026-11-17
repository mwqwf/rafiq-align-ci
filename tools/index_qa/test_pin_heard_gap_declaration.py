"""حفظ حجب الآيات عبر التثبيت: دليل موروث لا توقيت مصطنع."""
import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import pin_heard
import promote
from test_drop_ayahs import _make

class GapInheritance(unittest.TestCase):
    def candidate(self, idx):
        out = copy.deepcopy(idx)
        out['transform'] = {'op': 'heard_pin:79', 'reason': 'تثبيت جديد',
                            **pin_heard.inherit_declaration(idx, 'timings/hafs/x.jz', 'a'*64)}
        return out

    def test_preserves_evidence_entries_and_original_reason(self):
        idx = _make(); before = copy.deepcopy(idx); out = self.candidate(idx)
        pin_heard.preserve_gap_declarations(idx, out)
        self.assertTrue(promote.declared_truncated_gaps(out, 79)[0])
        self.assertEqual(out['entries'], idx['entries'])
        self.assertEqual(out['missing'], idx['missing'])
        self.assertEqual(out['transform']['truncatedGaps'], idx['transform']['truncatedGaps'])
        self.assertEqual(out['transform']['declarations']['79']['reason'], idx['transform']['reason'])
        out['transform']['truncatedGaps']['79']['evidence'].clear()
        self.assertEqual(idx, before)

    def test_missing_or_invalid_source_evidence_fails_closed(self):
        for mut in (lambda t:t.pop('truncatedGaps'),
                    lambda t:t['truncatedGaps']['79']['evidence'].clear(),
                    lambda t:t.update(reasonUser='')):
            idx = _make(); mut(idx['transform'])
            with self.assertRaises(SystemExit):pin_heard.preserve_gap_declarations(idx, self.candidate(idx))

    def test_changed_missing_or_entry_set_fails_closed(self):
        for mutate in (lambda o:o['entries'].pop(), lambda o:o['missing']['ids'].remove('79:15')):
            idx = _make();out=self.candidate(idx);mutate(out)
            with self.assertRaises(SystemExit):pin_heard.preserve_gap_declarations(idx,out)

    def test_witnessed_absence_preserved_and_claim_outside_absent_rejected(self):
        idx = _make()
        idx['transform']['witnessedAbsent'] = {'79': {'15': {'witnesses': [{'runId': 'proof'}]}}}
        idx['transform']['witnessedAbsentVersion'] = 'ctc-absent-witnessed-1'
        out = self.candidate(idx)
        pin_heard.preserve_gap_declarations(idx, out)
        for k in ('witnessedAbsent', 'witnessedAbsentVersion'):
            self.assertEqual(out['transform'][k], idx['transform'][k])
        out['transform']['witnessedAbsent']['79']['15']['witnesses'].clear()
        self.assertTrue(idx['transform']['witnessedAbsent']['79']['15']['witnesses'])
        idx['transform']['witnessedAbsent']['79']['20'] = {}
        with self.assertRaises(SystemExit):
            pin_heard.preserve_gap_declarations(idx, self.candidate(idx))

    def test_no_internal_gap_unchanged(self):
        idx={'entries':[{'ayahId':'1:1'},{'ayahId':'1:2'}]};out={'transform':{'op':'heard_pin:1'}}
        before=copy.deepcopy(out);pin_heard.preserve_gap_declarations(idx,out);self.assertEqual(out,before)

if __name__ == '__main__':unittest.main()
