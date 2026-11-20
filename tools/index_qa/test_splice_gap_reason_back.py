#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""العائدُ يُطرح من سببِ إعلانه (‏noah_warsh 2026-11-20).

① `splice_surah`: استرجاعُ آيتين معلَنتين بسبب timing_under_repair يُنقص ذلك العدّادَ وحده،
   ويبقى source_truncated لسورةٍ أخرى (‏54:16-17) كما هو.
② العائدُ غيرُ المعلَن في truncatedGaps يُطرح من source_truncated كما كان (‏لا تغيير في السلوك القديم).
③ `promote.gap_reason_count_error` (‏تشخيصٌ مطلق) يردّ عدّاداً لا يطابق الإعلان ويقبل المتطابق.
④ الحارسُ في index_gate وstage_transform هو `gap_reason_shift_error` المقارِنُ بالأصل: يردّ مرشّح noah
   البعطوب (‏6 بعد عودة اثنتين من 6) ويقبل المصلَح (‏4)، ولا يردّ فهرساً حيّاً بعدّادٍ تاريخيّ لم يتغيّر.
"""
import copy
import gzip
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from splice_surah import COUNTS  # noqa: E402
import promote  # noqa: E402

TPL = "https://h.example/r/{s:03d}.mp3"
GAPS5 = [12, 20, 36, 48, 72, 117]
TRUNC54 = [16, 17]


def _parent():
    ents = []
    for s in range(1, 115):
        for a in range(1, COUNTS[s - 1] + 1):
            if (s == 5 and a in GAPS5) or (s == 54 and a in TRUNC54):
                continue
            st = a * 4000
            ents.append({"ayahId": f"{s}:{a}", "fileRef": TPL.format(s=s), "startMs": st,
                         "endMs": st + 4000, "conf": 0.9, "confBand": "HIGH"})
    ids = [f"5:{a}" for a in GAPS5] + [f"54:{a}" for a in TRUNC54]
    ev = {f"5:{a}": {"method": "whisper", "detail": f"قياس {a}"} for a in GAPS5}
    return {"riwaya": "warsh", "reciterId": "x", "engineVersion": "align-0.2", "entries": ents,
            "missing": {"count": len(ids), "ids": ids,
                        "byReason": {"unknown": 0, "source_truncated": 2, "timing_under_repair": 6}},
            "transform": {"op": "declare_gap:5", "reasonCode": "TIMING_UNDER_REPAIR", "reasonUser": "س",
                          "gapAyahs": 6, "droppedEntries": 6,
                          "truncatedGaps": {"5": {"absent": list(GAPS5), "reason": "timing_under_repair",
                                                  "evidence": ev}}}}


def _aligned(back):
    rows = [{"ayahIdx": a - 1, "startMs": a * 4000, "endMs": (a + 1) * 4000, "conf": 0.8, "snapped": True}
            if (a not in GAPS5 or a in back) else {"ayahIdx": a - 1, "startMs": None, "endMs": None, "conf": 0.0}
            for a in range(1, COUNTS[4] + 1)]
    return {"fileRef": TPL.format(s=5), "sha256": "c" * 64, "entries": rows}


def _run(back, parent=None):
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        with gzip.open(tmp / "p.jz", "wt", encoding="utf-8") as f:
            json.dump(parent or _parent(), f, ensure_ascii=False)
        (tmp / "s.json").write_text(json.dumps(_aligned(back)), encoding="utf-8")
        r = subprocess.run([sys.executable, str(HERE / "splice_surah.py"), "--index", str(tmp / "p.jz"),
                            "--surah", "5", "--aligned", str(tmp / "s.json"), "--url", TPL,
                            "--skip-unresolved", "--engine-tag", "ctc-gapsplit-1", "--keep-parent-gaps",
                            "--out", str(tmp / "o.jz")],
                           capture_output=True, text=True, encoding="utf-8")
        if r.returncode:
            raise AssertionError(r.stdout + r.stderr)
        with gzip.open(tmp / "o.jz", "rt", encoding="utf-8") as f:
            return json.load(f)


class SpliceBack(unittest.TestCase):
    def test_declared_back_decrements_its_own_reason(self):
        out = _run([20, 36])
        by = out["missing"]["byReason"]
        self.assertEqual(by.get("timing_under_repair"), 4)
        self.assertEqual(by.get("source_truncated"), 2)          # عذرُ 54:16-17 باقٍ
        self.assertEqual(out["missing"]["count"], 6)

    def test_undeclared_back_still_from_source_truncated(self):
        p = _parent()
        p["transform"].pop("truncatedGaps")
        p["missing"]["byReason"] = {"source_truncated": 8}
        out = _run([20, 36], parent=p)
        self.assertEqual(out["missing"]["byReason"].get("source_truncated"), 6)


def _idx(tur, absent):
    return {"missing": {"byReason": {"timing_under_repair": tur, "source_truncated": 2}},
            "transform": {"truncatedGaps": {"5": {"absent": absent, "reason": "timing_under_repair"}}}}


class Guard(unittest.TestCase):
    def test_match_passes(self):
        self.assertIsNone(promote.gap_reason_count_error(_idx(4, [12, 48, 72, 117])))

    def test_inflated_counter_refused(self):           # المرشّحُ d643f291 بعينه: 6 مقابل 4
        self.assertIn("timing_under_repair", promote.gap_reason_count_error(_idx(6, [12, 48, 72, 117])))

    def test_undercounted_refused(self):
        self.assertIsNotNone(promote.gap_reason_count_error(_idx(3, [12, 48, 72, 117])))

    def test_counter_without_declaration_refused(self):
        self.assertIsNotNone(promote.gap_reason_count_error({"missing": {"byReason": {"timing_under_repair": 2}}}))

    def test_source_truncated_reason_not_counted(self):
        idx = {"missing": {"byReason": {"source_truncated": 4}},
               "transform": {"truncatedGaps": {"5": {"absent": [12, 48, 72, 117], "reason": "source_truncated"}}}}
        self.assertIsNone(promote.gap_reason_count_error(idx))

    def test_index_gate_calls_shift_guard(self):
        src = (HERE / "promote.py").read_text(encoding="utf-8")
        body = src[src.index("def index_gate"):]
        self.assertIn("gap_reason_shift_error(idx, parent)", body[:4000])
        st = (HERE / "stage_transform.py").read_text(encoding="utf-8")
        self.assertIn("promote.gap_reason_shift_error(idx, pidx)", st)


def _p(tur, gaps5, ents5, st=2):
    tg = {"5": {"absent": gaps5, "reason": "timing_under_repair"}} if gaps5 else {}
    return {"entries": [{"ayahId": f"5:{a}"} for a in ents5],
            "missing": {"byReason": {"timing_under_repair": tur, "source_truncated": st}},
            "transform": {"truncatedGaps": tg}}


ALL = list(range(1, 121))


class Shift(unittest.TestCase):
    P = _p(6, GAPS5, [a for a in ALL if a not in GAPS5])
    BACK = [a for a in ALL if a not in (12, 48, 72, 117)]

    def test_buggy_noah_refused(self):                 # d643f291: عادت 20 و36 وبقي العدّاد 6
        self.assertIn("timing_under_repair", promote.gap_reason_shift_error(_p(6, [12, 48, 72, 117], self.BACK, 0), self.P))

    def test_fixed_noah_passes(self):                  # 0b6818fc
        self.assertIsNone(promote.gap_reason_shift_error(_p(4, [12, 48, 72, 117], self.BACK), self.P))

    def test_no_parent_no_verdict(self):
        self.assertIsNone(promote.gap_reason_shift_error(_p(6, [], self.BACK), None))

    def test_historic_inflated_counter_unchanged_passes(self):   # harraz: 190 وغائباتٌ 4 بلا عودة
        par = _p(190, [], [a for a in ALL if a not in (1, 2, 3, 4)])
        self.assertIsNone(promote.gap_reason_shift_error(copy.deepcopy(par), par))

    def test_new_missing_allows_increase(self):
        cand = _p(5, [12, 48, 72, 117], [a for a in self.BACK if a != 50])
        self.assertIsNone(promote.gap_reason_shift_error(cand, self.P))

    def test_live_reciters_not_blocked_by_absolute_rule(self):
        par = {"entries": [], "missing": {"byReason": {"timing_under_repair": 135}}, "transform": {}}
        self.assertIsNone(promote.gap_reason_shift_error(copy.deepcopy(par), par))


if __name__ == "__main__":
    unittest.main()
