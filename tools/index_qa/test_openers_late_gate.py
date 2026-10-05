"""حارسُ التأخّر في `promote.gate` — شاهدُ المطالع الذي لم يسأل عن التأخّر لا يشهد (2026-09-30).

    python -m unittest tools/index_qa/test_openers_late_gate.py

يُختبر بطرفيه: ما يجب ردُّه يُردّ (‏شاهدٌ قديمٌ بلا `late` · `late` بلا شاهد CTC · مؤكَّدٌ بشاهدين)،
**وما يجب مرورُه لا يُردّ بهذا الحارس** (‏لا متأخّر · متأخّرٌ فحصه CTC فلم يؤكّده).
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import promote                                                   # noqa: E402

SHA = "a" * 64
REP = {"riwaya": "hafs", "reciterId": "x", "key": "timings-staging/hafs/x.aaaaaaaa.jz",
       "sha256": SHA, "verdict": promote.ACCEPTED, "sample": {"rows": []}}
BASE = {"kind": "openers", "sha256": SHA, "scope": "full",
        "commit": promote.OPENERS_FIX_COMMIT, "swallowed": [], "suspect": []}
RULE = "CTC ≥1500م.ث بعد بدء المدخل بثقة ≥0.3"
PREC = "float32-1thread-avx2 · tail 6000"


def why(op):
    return promote.gate(dict(REP), {}, "", {}, None, None, {SHA: op})[1] or ""


class LateGate(unittest.TestCase):
    def test_old_witness_without_late_refused(self):
        self.assertIn("قبل حارس التأخّر", why(dict(BASE)))

    def test_late_without_ctc_witness_refused(self):
        self.assertIn("لم يجرِ", why(dict(BASE, late=[4, 22])))

    def test_late_confirmed_refused(self):
        w = why(dict(BASE, late=[22], lateConfirmed=[22], lateCtcRule=RULE))
        self.assertIn("مبتلعةً متحقَّقة", w)

    def test_no_late_not_refused_by_this_guard(self):
        w = why(dict(BASE, late=[]))
        self.assertNotIn("التأخّر", w)
        self.assertNotIn("مبتلعة", w)

    def test_late_unconfirmed_not_refused(self):
        w = why(dict(BASE, late=[4], lateConfirmed=[], lateCtcRule=RULE, lateCtcPrecision=PREC))
        self.assertNotIn("لم يجرِ", w)
        self.assertNotIn("مبتلعةً متحقَّقة", w)
        self.assertNotIn("غيرُ حتميّ", w)

    # ⛔ fixV 2026-10-05: المسبارُ int8 وذيلُ 1.5ث أبرأا صادقاتٍ (‏الحارثي 89 بثقة 0.0) ⇒ لا يُبرّئ.
    def test_late_unconfirmed_by_nondeterministic_probe_refused(self):
        self.assertIn("غيرُ حتميّ", why(dict(BASE, late=[89], lateConfirmed=[], lateCtcRule=RULE)))

    def test_late_unconfirmed_by_short_tail_refused(self):
        w = why(dict(BASE, late=[89], lateConfirmed=[], lateCtcRule=RULE,
                     lateCtcPrecision="float32-1thread-avx2 · tail 1500"))
        self.assertIn("غيرُ حتميّ", w)

    def test_precision_parser(self):
        self.assertTrue(promote.late_ctc_trusted({"lateCtcPrecision": PREC}))
        for bad in (None, "", "int8", "float32-1thread-avx2 · tail 1500", "float32 · tail 6000x"):
            self.assertFalse(promote.late_ctc_trusted({"lateCtcPrecision": bad}))

    def test_probe_writes_trusted_precision(self):
        src = (Path(__file__).resolve().parents[1] / "alignment_v3" / "ctc_opener_probe.py").read_text(encoding="utf-8")
        import re
        tail = int(re.search(r"^TAIL_MS = (\d+)", src, re.M).group(1))
        self.assertTrue(promote.late_ctc_trusted(
            {"lateCtcPrecision": f"float32-1thread-avx2 · tail {tail}"}))
        self.assertIn('f"float32-1thread-avx2 · tail {TAIL_MS}"', src)


if __name__ == "__main__":
    unittest.main()
