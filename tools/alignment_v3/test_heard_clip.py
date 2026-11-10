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
    def __init__(self, truth, tail_cut=(), snap=False):
        self.truth, self.tail_cut, self.snap, self.calls = truth, set(tail_cut), snap, []

    def __call__(self, wins):
        self.calls.append(dict(wins))
        out = {}
        for key, (lo, hi) in wins.items():
            ws, a, s0, e0 = [], None, None, None
            if key < 10_000_000:
                a = key // 1000
                fits = [(a, s, e) for (s, e) in self.truth.get(a, []) if lo <= s and e <= hi]
            else:                                     # نافذةُ شاهد البدء: الأداءُ الأقربُ بدءاً إلى بدء النافذة
                fits = [(aa, s, e) for aa, v in self.truth.items() for (s, e) in v if lo <= s and e <= hi]
                fits.sort(key=lambda f: f[1] - lo)
                fits = fits[:1]
            for (a, s, e) in fits:
                ws = words(REF[a], s, e, skip_tail=1 if (a, s) in self.tail_cut else 0)
                if self.snap and ws:
                    ws[0]["s"] = lo                    # Whisper يلصق أوّلَ كلمةٍ ببدء النافذة
            out[str(key)] = {"words": ws or [{"w": "zz", "s": lo + 10, "e": lo + 90, "p": 0.9}]}
        return out


def sil_of(truth):
    """صمتُ VAD مصطنعٌ قبل كلّ أداءٍ: (بدء−500، بدء−50)."""
    return [(s - 500, s - 50) for v in truth.values() for (s, e) in v]


def ctc_for(truth, shift=0):
    """محاذاةُ CTC مصطنعة: تُرجع حدَّي الأداء الصحيح داخل النافذة (‏مع إزاحةٍ اختياريّة)."""
    def run(lo, hi, a):
        for (s, e) in truth.get(a, []):
            if lo <= s and e <= hi:
                return s + shift, e + shift
        return None
    return run


class ClipTest(unittest.TestCase):
    def test_artificial_repeat_clipped_to_last_complete_performance(self):
        # الآية 2 تُقرأ مرّتين: 20000–26000 ثمّ 40000–46000؛ والتالية بعد الثانية
        hm = hmap({1: [(10000, 15000, 0.95)], 2: [(20000, 26000, 0.9), (40000, 46000, 0.92)],
                   3: [(47000, 52000, 0.95)]})
        truth = {1: [(10000, 15000)], 2: [(20000, 26000), (40000, 46000)], 3: [(47000, 52000)]}
        r = H.clip_surah(hm, lambda a: REF[a], 3, Runner(truth), ctc_for(truth), NORM, sil_of(truth))
        self.assertTrue(r["ok"], r["unresolved"])
        by = {e["ayahIdx"] + 1: e for e in r["entries"]}
        self.assertEqual((by[2]["startMs"], by[2]["endMs"]), (40000, 46000))      # آخرُ أداءٍ لا الأوّل
        self.assertEqual(r["evidence"]["2"]["occurrence"], [2, 2])
        self.assertEqual(r["evidence"]["2"]["ctc"], [40000, 46000])
        self.assertEqual(len(r["entries"]), 3)

    def test_ayah_without_repeat_unchanged(self):
        hm = hmap({1: [(10000, 15000, 0.95)], 2: [(15500, 21000, 0.9)], 3: [(21500, 26000, 0.95)]})
        truth = {1: [(10000, 15000)], 2: [(15500, 21000)], 3: [(21500, 26000)]}
        r = H.clip_surah(hm, lambda a: REF[a], 3, Runner(truth), ctc_for(truth), NORM, sil_of(truth))
        self.assertTrue(r["ok"])
        got = [(e["startMs"], e["endMs"]) for e in r["entries"]]
        self.assertEqual(got, [(10000, 15000), (15500, 21000), (21500, 26000)])

    def test_incomplete_performance_rejected_and_earlier_complete_taken(self):
        # الأداءُ الأخيرُ للآية 2 ناقصٌ (‏بُترت كلمتُها الأخيرة) فيُردّ ويُؤخذ الأقدمُ التامّ
        hm = hmap({1: [(10000, 15000, 0.95)], 2: [(16000, 21000, 0.9), (40000, 44000, 0.8)],
                   3: [(21800, 26000, 0.95)]})
        truth = {1: [(10000, 15000)], 2: [(16000, 21000), (40000, 44000)], 3: [(21800, 26000)]}
        r = H.clip_surah(hm, lambda a: REF[a], 3, Runner(truth, tail_cut={(2, 40000)}), ctc_for(truth), NORM, sil_of(truth))
        self.assertTrue(r["ok"], r["unresolved"])
        by = {e["ayahIdx"] + 1: e for e in r["entries"]}
        self.assertEqual(by[2]["startMs"], 16000)
        self.assertEqual(r["evidence"]["2"]["occurrence"][0], 1)

    def test_no_complete_performance_leaves_surah_unresolved(self):
        hm = hmap({1: [(10000, 15000, 0.95)], 2: [(16000, 21000, 0.9)], 3: [(21800, 26000, 0.95)]})
        truth = {1: [(10000, 15000)], 2: [(16000, 21000)], 3: [(21800, 26000)]}
        r = H.clip_surah(hm, lambda a: REF[a], 3, Runner(truth, tail_cut={(2, 16000)}), ctc_for(truth), NORM, sil_of(truth))
        self.assertFalse(r["ok"])
        self.assertIn(2, r["unresolved"])
        self.assertEqual(r["entries"], [])                    # لا قصَّ تخميناً

    def test_ctc_and_whisper_bounds_must_agree_within_300ms(self):
        m = {"ws": 10200, "we": 15200}
        ok, _ = H.confirm(m, lambda lo, hi: (10000, 15000))
        self.assertIsNotNone(ok)
        bad, why = H.confirm(m, lambda lo, hi: (10600, 15000))
        self.assertIsNone(bad)
        self.assertIn("يبعدان", why)

    def test_orthographic_variant_accepted_but_other_ayah_rejected(self):
        ref = "تلك ايت الكتب الحكيم".split()
        ws = [{"w": w, "s": 1000 + i * 500, "e": 1400 + i * 500, "p": 0.9}
              for i, w in enumerate("تلك ايه الكتاب الحكيم".split())]
        ms, _ = H.find_matches(ws, ref, NORM)
        self.assertEqual(len(ms), 1)
        other = [{"w": w, "s": 1000 + i * 500, "e": 1400 + i * 500, "p": 0.9}
                 for i, w in enumerate("ان الذين امنوا وعملوا".split())]
        ms2, _ = H.find_matches(other, ref, NORM)
        self.assertEqual(ms2, [])

    def test_low_word_confidence_rejected(self):
        ms, why = H.find_matches(words(REF[1], 10000, 15000, p=0.4), REF[1], NORM)
        self.assertEqual(ms, [])
        self.assertIn("ثقة", why)

    def test_two_complete_matches_inside_one_window_take_the_last(self):
        # نافذةٌ واحدةٌ فيها أداءان تامّان (‏موضعٌ فضفاضٌ يضمّ التكرار)
        ws = words(REF[2], 20000, 26000) + words(REF[2], 40000, 46000)
        ms, _ = H.find_matches(ws, REF[2], NORM)
        self.assertEqual(len(ms), 2)
        hm = hmap({1: [(10000, 15000, 0.95)], 2: [(19000, 47000, 0.9)], 3: [(47500, 52000, 0.95)]})
        truth = {1: [(10000, 15000)], 2: [(20000, 26000), (40000, 46000)], 3: [(47500, 52000)]}
        r = H.clip_surah(hm, lambda a: REF[a], 3, Runner(truth), ctc_for(truth), NORM, sil_of(truth))
        self.assertTrue(r["ok"], r["unresolved"])
        by = {e["ayahIdx"] + 1: e for e in r["entries"]}
        self.assertEqual((by[2]["startMs"], by[2]["endMs"]), (40000, 46000))

    def test_later_performance_after_next_ayah_is_not_chosen(self):
        # أداءٌ مثبَتٌ للآية 1 بعد بدء الآية 2 لا يُؤخذ (‏ترتيب) فيُؤخذ ما قبله
        hm = hmap({1: [(10000, 15000, 0.95), (30000, 35000, 0.95)], 2: [(16000, 21000, 0.9)],
                   3: [(21800, 26000, 0.95)]})
        truth = {1: [(10000, 15000), (30000, 35000)], 2: [(16000, 21000)], 3: [(21800, 26000)]}
        r = H.clip_surah(hm, lambda a: REF[a], 3, Runner(truth), ctc_for(truth), NORM, sil_of(truth))
        self.assertTrue(r["ok"], r["unresolved"])
        by = {e["ayahIdx"] + 1: e for e in r["entries"]}
        self.assertEqual(by[1]["startMs"], 10000)

    def test_far_gap_is_not_accepted(self):
        hm = hmap({1: [(10000, 15000, 0.95)], 2: [(200000, 205000, 0.9)], 3: [(205500, 210000, 0.95)]})
        truth = {1: [(10000, 15000)], 2: [(200000, 205000)], 3: [(205500, 210000)]}
        r = H.clip_surah(hm, lambda a: REF[a], 3, Runner(truth), ctc_for(truth), NORM, sil_of(truth))
        self.assertFalse(r["ok"])
        self.assertIn(1, r["unresolved"])

    def test_start_witness_with_window_snapping_still_accepts_true_start(self):
        hm = hmap({1: [(10000, 15000, 0.95)], 2: [(15500, 21000, 0.9)], 3: [(21500, 26000, 0.95)]})
        truth = {1: [(10000, 15000)], 2: [(15500, 21000)], 3: [(21500, 26000)]}
        r = H.clip_surah(hm, lambda a: REF[a], 3, Runner(truth, snap=True), ctc_for(truth), NORM, sil_of(truth))
        self.assertTrue(r["ok"], r["unresolved"])
        self.assertEqual(r["evidence"]["2"]["onsetSilence"], [15300, 15450])

    def test_no_silence_before_ayah_means_unresolved(self):
        hm = hmap({1: [(10000, 15000, 0.95)], 2: [(15500, 21000, 0.9)], 3: [(21500, 26000, 0.95)]})
        truth = {1: [(10000, 15000)], 2: [(15500, 21000)], 3: [(21500, 26000)]}
        r = H.clip_surah(hm, lambda a: REF[a], 3, Runner(truth), ctc_for(truth), NORM, [])
        self.assertFalse(r["ok"])
        self.assertIn("لا صمتَ", r["unresolved"][1])

    def test_selftest_rejects_shifted_starts_even_when_whisper_snaps(self):
        truth = {1: [(10000, 15000)], 2: [(15500, 21000)], 3: [(21500, 26000)]}
        samples = [(1, 10000, 15000), (2, 15500, 21000), (3, 21500, 26000)]
        rows = H.selftest_rows(samples, lambda a: REF[a], Runner(truth, snap=True), sil_of(truth), NORM)
        for r in rows:
            if r["shift"] == 0:
                self.assertEqual(r["verdict"], "accepted", r)
            else:
                self.assertEqual(r["verdict"], "rejected", r)

    def test_header_injection_records_every_ayah(self):
        hm = hmap({1: [(10000, 15000, 0.95)], 2: [(15500, 21000, 0.9)], 3: [(21500, 26000, 0.95)]})
        truth = {1: [(10000, 15000)], 2: [(15500, 21000)], 3: [(21500, 26000)]}
        res = H.clip_surah(hm, lambda a: REF[a], 3, Runner(truth), ctc_for(truth), NORM, sil_of(truth))
        rec = H.apply_to_surah_json({"surah": 5, "entries": []}, res)
        idx = H.inject_header({"entries": []}, {5: rec})
        self.assertEqual(sorted(idx["heardClip"]["ayahs"]), ["5:1", "5:2", "5:3"])
        self.assertEqual(idx["heardClip"]["ayahs"]["5:2"]["performance"], [15500, 21000])


if __name__ == "__main__":
    unittest.main()
