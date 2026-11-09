# -*- coding: utf-8 -*-
"""اختباراتُ `heard_clip`: تكرارٌ مصطنعٌ يُقصّ إلى أدائه · آيةٌ بلا تكرار لا تتغيّر · أداءٌ ناقصٌ يُردّ."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import heard_clip as H                                            # noqa: E402

NORM = lambda s: s                                                # noqa: E731
REF = {1: "a1 a2 a3 a4".split(), 2: "b1 b2 b3 b4 b5".split(), 3: "c1 c2 c3 c4".split()}


def words(ref, s, e, p=0.9, skip_tail=0):
    """كلماتٌ مصطنعةٌ موزَّعةٌ على [s,e] لنصّ الآية (‏مع إمكان بتر الذيل)."""
    ws = ref[:len(ref) - skip_tail]
    step = (e - s) / len(ref)
    return [{"w": w, "s": int(s + i * step), "e": int(s + (i + 1) * step), "p": p} for i, w in enumerate(ws)]


def hmap(occ):
    return {"heardMap": {str(a): {"occurrences": [list(o) for o in v], "anchorMs": None} for a, v in occ.items()}}


class Runner:
    """شاهدٌ مصطنع: `truth` = {آية: [(بدء، نهاية)]} الأداءاتُ الصحيحة؛ وما سواها يُفرَّغ كلاماً آخر."""
    def __init__(self, truth, tail_cut=()):
        self.truth, self.tail_cut, self.calls = truth, set(tail_cut), []

    def __call__(self, wins):
        self.calls.append(dict(wins))
        out = {}
        for key, (lo, hi) in wins.items():
            a = key // 1000
            ws = []
            for (s, e) in self.truth.get(a, []):
                if lo <= s and e <= hi:
                    ws = words(REF[a], s, e, skip_tail=1 if (a, s) in self.tail_cut else 0)
            out[str(key)] = {"words": ws or [{"w": "zz", "s": lo + 10, "e": lo + 90, "p": 0.9}]}
        return out


class ClipTest(unittest.TestCase):
    def test_artificial_repeat_clipped_to_last_complete_performance(self):
        # الآية 2 تُقرأ مرّتين: 20000–26000 ثمّ 40000–46000؛ والتالية بعد الثانية
        hm = hmap({1: [(10000, 15000, 0.95)], 2: [(20000, 26000, 0.9), (40000, 46000, 0.92)],
                   3: [(47000, 52000, 0.95)]})
        truth = {1: [(10000, 15000)], 2: [(20000, 26000), (40000, 46000)], 3: [(47000, 52000)]}
        r = H.clip_surah(hm, lambda a: REF[a], 3, Runner(truth), NORM)
        self.assertTrue(r["ok"], r["unresolved"])
        by = {e["ayahIdx"] + 1: e for e in r["entries"]}
        self.assertEqual((by[2]["startMs"], by[2]["endMs"]), (40000, 46000))      # آخرُ أداءٍ لا الأوّل
        self.assertEqual(r["evidence"]["2"]["k"], 2)
        self.assertEqual(r["evidence"]["2"]["of"], 2)
        self.assertEqual(len(r["entries"]), 3)

    def test_ayah_without_repeat_unchanged(self):
        hm = hmap({1: [(10000, 15000, 0.95)], 2: [(15500, 21000, 0.9)], 3: [(21500, 26000, 0.95)]})
        truth = {1: [(10000, 15000)], 2: [(15500, 21000)], 3: [(21500, 26000)]}
        r = H.clip_surah(hm, lambda a: REF[a], 3, Runner(truth), NORM)
        self.assertTrue(r["ok"])
        got = [(e["startMs"], e["endMs"]) for e in r["entries"]]
        self.assertEqual(got, [(10000, 15000), (15500, 21000), (21500, 26000)])

    def test_incomplete_performance_rejected_and_earlier_complete_taken(self):
        # الأداءُ الأخيرُ للآية 2 ناقصٌ (‏بُترت كلمتُها الأخيرة) فيُردّ ويُؤخذ الأقدمُ التامّ
        hm = hmap({1: [(10000, 15000, 0.95)], 2: [(16000, 21000, 0.9), (40000, 44000, 0.8)],
                   3: [(21800, 26000, 0.95)]})
        truth = {1: [(10000, 15000)], 2: [(16000, 21000), (40000, 44000)], 3: [(21800, 26000)]}
        r = H.clip_surah(hm, lambda a: REF[a], 3, Runner(truth, tail_cut={(2, 40000)}), NORM)
        self.assertTrue(r["ok"], r["unresolved"])
        by = {e["ayahIdx"] + 1: e for e in r["entries"]}
        self.assertEqual(by[2]["startMs"], 16000)
        self.assertEqual(r["evidence"]["2"]["k"], 1)

    def test_no_complete_performance_leaves_surah_unresolved(self):
        hm = hmap({1: [(10000, 15000, 0.95)], 2: [(16000, 21000, 0.9)], 3: [(21800, 26000, 0.95)]})
        truth = {1: [(10000, 15000)], 2: [(16000, 21000)], 3: [(21800, 26000)]}
        r = H.clip_surah(hm, lambda a: REF[a], 3, Runner(truth, tail_cut={(2, 16000)}), NORM)
        self.assertFalse(r["ok"])
        self.assertIn(2, r["unresolved"])
        self.assertEqual(r["entries"], [])                    # لا قصَّ تخميناً

    def test_witness_bounds_must_agree_within_300ms(self):
        perf = (10000, 15000, 0.9)
        ok, _ = H.verify(words(REF[1], 10200, 15200), REF[1], perf, NORM)
        self.assertIsNotNone(ok)
        bad, why = H.verify(words(REF[1], 10600, 15000), REF[1], perf, NORM)
        self.assertIsNone(bad)
        self.assertIn("يبعدان", why)

    def test_low_word_confidence_rejected(self):
        perf = (10000, 15000, 0.9)
        bad, why = H.verify(words(REF[1], 10000, 15000, p=0.4), REF[1], perf, NORM)
        self.assertIsNone(bad)
        self.assertIn("ثقة", why)

    def test_later_performance_after_next_ayah_is_not_chosen(self):
        # أداءٌ مثبَتٌ للآية 1 بعد بدء الآية 2 لا يُؤخذ (‏ترتيب) فيُؤخذ ما قبله
        hm = hmap({1: [(10000, 15000, 0.95), (30000, 35000, 0.95)], 2: [(16000, 21000, 0.9)],
                   3: [(21800, 26000, 0.95)]})
        truth = {1: [(10000, 15000), (30000, 35000)], 2: [(16000, 21000)], 3: [(21800, 26000)]}
        r = H.clip_surah(hm, lambda a: REF[a], 3, Runner(truth), NORM)
        self.assertTrue(r["ok"], r["unresolved"])
        by = {e["ayahIdx"] + 1: e for e in r["entries"]}
        self.assertEqual(by[1]["startMs"], 10000)

    def test_far_gap_is_not_accepted(self):
        hm = hmap({1: [(10000, 15000, 0.95)], 2: [(200000, 205000, 0.9)], 3: [(205500, 210000, 0.95)]})
        truth = {1: [(10000, 15000)], 2: [(200000, 205000)], 3: [(205500, 210000)]}
        r = H.clip_surah(hm, lambda a: REF[a], 3, Runner(truth), NORM)
        self.assertFalse(r["ok"])
        self.assertIn(1, r["unresolved"])

    def test_header_injection_records_every_ayah(self):
        hm = hmap({1: [(10000, 15000, 0.95)], 2: [(15500, 21000, 0.9)], 3: [(21500, 26000, 0.95)]})
        truth = {1: [(10000, 15000)], 2: [(15500, 21000)], 3: [(21500, 26000)]}
        res = H.clip_surah(hm, lambda a: REF[a], 3, Runner(truth), NORM)
        rec = H.apply_to_surah_json({"surah": 5, "entries": []}, res)
        idx = H.inject_header({"entries": []}, {5: rec})
        self.assertEqual(sorted(idx["heardClip"]["ayahs"]), ["5:1", "5:2", "5:3"])
        self.assertEqual(idx["heardClip"]["ayahs"]["5:2"]["performance"], [15500, 21000])


if __name__ == "__main__":
    unittest.main()
