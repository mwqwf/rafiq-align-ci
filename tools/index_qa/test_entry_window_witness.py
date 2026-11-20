#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""اختباراتُ التحوّر للشاهد الأقوى والتشديداتِ الثلاثة (‏2026-11-08).

    python -m unittest tools/index_qa/test_entry_window_witness.py

القياساتُ اصطناعيّةٌ (‏لا نماذجَ ولا صوت)، والنصوصُ كلماتٌ مجرّدةٌ لا قرآنَ مولَّداً.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import entry_window_census as E                                       # noqa: E402
import entry_window_witness as W                                      # noqa: E402

T = {1: "الف باء جيم دال هاء واو زاي".split(),
     2: "حاء طاء ياء كاف لام ميم نون".split(),
     3: "سين عين غين فاء صاد قاف راء شين".split(),
     4: "ظاء ذال ضاد خاء ثاء تاء".split(),
     5: "الف باء جيم دال هاء واو زاي".split()}        # 5 مطابقةٌ نصّاً للآية 1 (‏بعيدةٌ عنها: ليست ±2)
T2 = dict(T)
T2[3] = list(T[2])                                      # 3 مطابقةٌ نصّاً للآية 2 (‏جارةٌ ±1)

ENTRY = (10000, 18000)


def toks(words, p=0.9):
    return [(w, i * 400, p) for i, w in enumerate(words)]


def model(conf=0.8, own=(10100, 17900), rivals=None, frame=20.0, audio=(9500, 18800), clip=(False, False)):
    return {"own": [own[0], own[1], conf], "rivals": dict(rivals if rivals is not None else {"1": 0.3, "3": 0.2, "4": 0.1}),
            "frameMs": frame, "audioMs": list(audio), "clipLo": clip[0], "clipHi": clip[1]}


def good():
    return {"generic": model(), "quran": model(conf=0.75)}


class Witness(unittest.TestCase):
    def test_both_models_pass(self):
        r = W.judge_witness(ENTRY, good())
        self.assertTrue(r["pass"], r)

    # --- اختبارات التحوّر الإلزاميّة ---
    def test_neighbour_text_rejected(self):
        # الجارةُ 3 تحاذي النافذةَ بثقةٍ أعلى من الآية ⇒ الصوتُ لها لا للآية
        m = good()
        m["generic"]["rivals"]["3"] = 0.81
        r = W.judge_witness(ENTRY, m)
        self.assertFalse(r["pass"])
        self.assertTrue(any("الجارة 3" in x for x in r["why"]), r)

    def test_neighbour_win_in_one_model_only_still_rejected(self):
        m = good()
        m["quran"]["rivals"]["1"] = 0.76
        self.assertFalse(W.judge_witness(ENTRY, m)["pass"])

    def test_truncated_window_rejected(self):
        # نافذةٌ مبتورة: نصُّ الآية يمتدّ خارج الصوت المقصوص فتلتصق نهايتُه بالحافّة
        m = good()
        m["generic"]["own"] = [10100, 18780, 0.8]
        r = W.judge_witness(ENTRY, m)
        self.assertFalse(r["pass"])
        self.assertTrue(any("حافّة" in x for x in r["why"]), r)

    def test_truncated_window_low_conf_rejected(self):
        m = good()
        m["quran"]["own"][2] = 0.31
        self.assertFalse(W.judge_witness(ENTRY, m)["pass"])

    def test_edge_exempt_when_file_edge(self):
        # الحافّةُ التي قصّها طرفُ الملفّ نفسُه لا تُعدّ بتراً
        m = good()
        for k in m:
            m[k]["audioMs"] = [0, 18800]
            m[k]["own"] = [60, 17900, 0.8] if k == "generic" else [40, 17900, 0.75]
            m[k]["clipLo"] = True
        self.assertTrue(W.judge_witness((100, 18000), m)["pass"])

    def test_two_ayahs_in_window_rejected(self):
        # مدخلٌ بآيتين: المحاذاةُ المطوَّلة لنصّ آيةٍ واحدةٍ على صوتَين تنهار ثقتُها أو تخرج حدودُها
        m = good()
        m["generic"]["own"] = [10100, 17900, 0.42]
        self.assertFalse(W.judge_witness(ENTRY, m)["pass"])
        m = good()
        m["generic"]["own"] = [10100, 19300, 0.7]          # نهايتُها بعد النافذة بأكثر من END_TOL
        self.assertFalse(W.judge_witness(ENTRY, m)["pass"])

    def test_boundary_outside_window_rejected(self):
        m = good()
        m["quran"]["own"] = [9400, 17900, 0.8]             # بدءٌ قبل نافذة المدخل − START_TOL
        self.assertFalse(W.judge_witness(ENTRY, m)["pass"])
        m = good()
        m["quran"]["own"] = [10100, 18900, 0.8]            # نهايةٌ بعد نهاية المدخل + END_TOL
        self.assertFalse(W.judge_witness(ENTRY, m)["pass"])

    def test_silence_inside_entry_is_not_a_defect(self):
        # الآيةُ تبدأ بعد بدء المدخل وتنتهي قبل نهايته (‏صمتٌ في طرفيه): داخل النافذة ⇒ تمرّ
        m = good()
        m["generic"]["own"] = [11500, 16000, 0.8]
        m["quran"]["own"] = [11400, 16200, 0.75]
        self.assertTrue(W.judge_witness(ENTRY, m)["pass"])

    def test_single_model_not_enough(self):
        for only in W.MODELS:
            m = {only: good()[only]}
            r = W.judge_witness(ENTRY, m)
            self.assertFalse(r["pass"], only)
            self.assertTrue(any("نموذجٍ واحد" in x for x in r["why"]))
        self.assertFalse(W.judge_witness(ENTRY, {})["pass"])

    def test_conf_below_target_rejected(self):
        for c, ok in ((W.TARGET_CONF - 0.001, False), (W.TARGET_CONF, True)):
            m = good()
            m["generic"]["own"][2] = c
            m["generic"]["rivals"] = {"1": 0.0}
            self.assertEqual(W.judge_witness(ENTRY, m)["pass"], ok, c)
        self.assertEqual(W.TARGET_CONF, 0.60)             # الثابتُ الموجود لا مخترَع

    def test_invalid_measures_rejected(self):
        m = good()
        m["generic"]["own"] = [10100, 17900, float("nan")]
        self.assertFalse(W.judge_witness(ENTRY, m)["pass"])
        m = good()
        m["quran"]["rivals"]["3"] = float("nan")
        self.assertFalse(W.judge_witness(ENTRY, m)["pass"])

    def test_identical_text_rival_undecided_rejected(self):
        self.assertFalse(W.judge_witness(ENTRY, good(), undecided_identical=[3])["pass"])

    # --- ما يحسمه الشاهدُ وما لا يحسمه ---
    def row(self, reason="نقص", eligible=True):
        return {"verdict": "reject", "reason": reason, "witnessEligible": eligible, "startMs": ENTRY[0],
                "endMs": ENTRY[1], "detail": "د"}

    def test_rescues_naqs_only(self):
        r = W.apply_witness(self.row(), good())
        self.assertEqual((r["verdict"], r.get("witnessRescued")), ("pass", True), r)
        for reason in ("زيادة", "آية أخرى"):
            r = W.apply_witness(self.row(reason), good())
            self.assertEqual(r["verdict"], "reject", reason)
            self.assertNotIn("witnessRescued", r)

    def test_not_eligible_naqs_not_rescued(self):
        r = W.apply_witness(self.row(eligible=False), good())
        self.assertEqual(r["verdict"], "reject")

    def test_failed_witness_keeps_reject_and_records(self):
        m = good()
        m["generic"]["own"][2] = 0.2
        r = W.apply_witness(self.row(), m)
        self.assertEqual(r["verdict"], "reject")
        self.assertFalse(r["witness"]["pass"])

    def test_classify_three_classes(self):
        self.assertEqual(W.classify(ENTRY, good())["class"], "الآيةُ نفسُها مسموعة")
        other = good()
        for k in other:
            other[k]["rivals"]["3"] = 0.95
        c = W.classify(ENTRY, other)
        self.assertEqual((c["class"], c["winners"]), ("غيرها مسموع", ["3"]))
        low = good()
        low["generic"]["own"][2] = 0.3
        self.assertEqual(W.classify(ENTRY, low)["class"], "غير محسوم")
        half = good()
        half["generic"]["rivals"]["3"] = 0.95              # نموذجٌ واحدٌ فقط يرى الجارة ⇒ لا اتّفاق
        self.assertEqual(W.classify(ENTRY, half)["class"], "غير محسوم")
        self.assertEqual(W.classify(ENTRY, {"generic": good()["generic"]})["class"], "غير محسوم")

    def test_window_of_clips(self):
        self.assertEqual(W.window_of(200, 5000, 100000), (0, 5800, True, False))
        self.assertEqual(W.window_of(10000, 99500, 100000), (9500, 100000, False, True))


class Tightenings(unittest.TestCase):
    # (أ) حدٌّ أدنى لتشابه الآية بالتفريغ
    def test_a_sim_floor_blocks_low_similarity_pass(self):
        # الآية أقربُ من الجارات بهامشٍ لكنّ التشابه متدنٍّ: 3 كلماتٍ صحيحةٍ من 7 وبقيّتُها شاذّة
        heard = T[1][:2] + ["صصصصصصص", "ضضضضضضض", "ططططططط", "ظظظظظظظظ", "ثثثثثثثثث"]
        r = E.judge_entry(1, toks(heard), T)
        self.assertLess(r["simSelf"], E.SIM_FLOOR, r)
        self.assertEqual((r["verdict"], r["reason"], r["witnessEligible"]), ("reject", "نقص", False), r)

    def test_a_floor_keeps_documented_sound_entries(self):
        # أدنى مدخلٍ سليمٍ موثّقٍ في المعايرة مرّ بتشابه 0.411 (‏33:53 fakhfakh_qalun)؛ والأرضيّةُ تحته
        self.assertLessEqual(E.SIM_FLOOR, 0.411)
        self.assertEqual(E.SIM_FLOOR, 0.40)
        r = E.judge_entry(2, toks(T[2]), T)
        self.assertEqual(r["verdict"], "pass", r)

    # (ب) كلماتُ الجارة تُردّ «زيادة» لا تُسجَّل فقط
    def test_b_neighbour_words_reject_as_excess_even_within_count(self):
        # الآية 2 (7 كلمات) بعد استبدال ثلاثٍ منها بكلمات الجارة 3 ⇒ العددُ في الحدّ لكنّ فيه كلماتِ جارة
        heard = T[2][:4] + T[3][:3]
        r = E.judge_entry(2, toks(heard), T)
        self.assertEqual((r["verdict"], r["reason"]), ("reject", "زيادة"), r)
        self.assertEqual(r["containsAyah"], 3)

    def test_b_not_triggered_by_own_text(self):
        r = E.judge_entry(2, toks(T[2]), T)
        self.assertEqual(r["verdict"], "pass", r)
        self.assertNotIn("containsAyah", r)

    # (ج) الجارةُ المطابقةُ نصّاً منافِسة
    def test_c_identical_neighbour_undecided_rejected(self):
        r = E.judge_entry(2, toks(T2[2]), T2)               # بلا نوافذ ⇒ لا حسمَ بالموضع
        self.assertEqual((r["verdict"], r["reason"]), ("reject", "آية أخرى"), r)
        self.assertEqual(r["identicalRival"], [3])

    def test_c_identical_neighbour_overlapping_windows_rejected(self):
        win = {2: (0, 5000), 3: (4000, 9000)}
        r = E.judge_entry(2, toks(T2[2]), T2, win)
        self.assertEqual(r["reason"], "آية أخرى", r)

    def test_c_identical_neighbour_out_of_order_rejected(self):
        win = {2: (6000, 9000), 3: (0, 5000)}               # الآية 3 قبل 2 زمناً
        self.assertEqual(E.judge_entry(2, toks(T2[2]), T2, win)["reason"], "آية أخرى")

    def test_c_identical_neighbour_decided_by_position_passes(self):
        win = {2: (0, 5000), 3: (5000, 9000)}
        r = E.judge_entry(2, toks(T2[2]), T2, win)
        self.assertEqual(r["verdict"], "pass", r)
        r3 = E.judge_entry(3, toks(T2[3]), T2, win)
        self.assertEqual(r3["verdict"], "pass", r3)

    def test_c_non_neighbour_identical_is_not_a_rival(self):
        # 1 و5 متطابقتان لكن بينهما أكثر من ±2
        r = E.judge_entry(1, toks(T[1]), T)
        self.assertEqual(r["verdict"], "pass", r)

    # أصنافُ «نقص» المؤهَّلة للشاهد
    def test_witness_eligibility(self):
        low_conf = E.judge_entry(2, toks(T[2], p=0.2), T)
        self.assertEqual((low_conf["reason"], low_conf["witnessEligible"]), ("نقص", True), low_conf)
        silent = E.judge_entry(2, [], T)
        self.assertFalse(silent["witnessEligible"])
        excess = E.judge_entry(2, toks(T[2] + T[2]), T)
        self.assertEqual((excess["reason"], excess["witnessEligible"]), ("زيادة", False), excess)

    def test_baseline_kept_for_before_column(self):
        # القاعدةُ السابقةُ تمرّر ما تردّه (ج) و(ب): هذا هو الفرقُ الذي يقيسه جدولُ قبل/بعد
        self.assertEqual(E.judge_entry_baseline(2, toks(T2[2]), T2)["verdict"], "pass")
        self.assertEqual(E.judge_entry_baseline(2, toks(T[2][:4] + T[3][:3]), T)["verdict"], "pass")


if __name__ == "__main__":
    unittest.main()
