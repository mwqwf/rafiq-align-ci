#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""اختباراتُ شاهد large-v3 لقاعدة المِرساة الضعيفة (‏`heard_gate.large_v3_weak` · heard-weak-lv3-1 · قرار القائد 2026-11-20).

القاعدة: يُقبل شاهدُ المرساة الضعيفة إذا شهد medium كما اليوم، **أو** شهد large-v3 بالنصّ ضمن 300م.ث وكان medium
«لا يناقض» (‏لا يسمع داخل حدود الآية W_K كلماتٍ متّصلةً من آيةٍ أخرى مسمّاة بالثقة نفسِها)؛ والصمتُ أو النصُّ الناقص
ليس مناقضة. وبلا شاهد medium للآية لا قبولَ بهذا المسار. السندُ: `docs/qa/WITNESS_CALIBRATION_2026-11.md`.

الطفراتُ التي يجب أن تُسقط هذا الملفّ: حذفُ شرط 300م.ث من المسار الجديد · حذفُ شرط عدم المناقضة · قبولُ large-v3 بلا medium."""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import heard_gate as H  # noqa: E402
import test_heard_weak as TW  # noqa: E402

S, REF, SHA = TW.S, TW.REF, TW.SHA
OTHER = ["قل", "هو", "الله", "احد"]            # نصُّ «آيةٍ أخرى مسمّاة» (‏9:99 في هذا المصحف المصغَّر)
OTHER_KEY = (S, 99)


def grams_of(g):
    """ثلاثيّاتُ المصحف المصغَّر: كلُّ آيات السورة نصُّها BASE، و9:99 نصُّها OTHER."""
    out = set()
    if any(list(g) == TW.BASE[i:i + 3] for i in range(len(TW.BASE) - 2)):
        out |= {(S, a) for a in range(1, TW.N + 1)}
    if any(list(g) == OTHER[i:i + 3] for i in range(len(OTHER) - 2)):
        out.add(OTHER_KEY)
    return out


LV3_TEXT = (lambda _s, _a: list(TW.BASE), grams_of)


def wit(ayahs, model, shift=0, words=None, sha=SHA, p=.9):
    w = TW.wit(ayahs, sha=sha, words=TW.BASE if words is None else words, shift=shift)
    w["model"] = model
    if p != .9:
        for rec in w["ayahs"].values():
            for x in rec["words"]:
                x["p"] = p
    return w


def silent(ayahs, model="medium"):
    """شاهدُ medium صامتٌ (‏نافذةٌ بلا كلمات) — الصمتُ ليس مناقضة."""
    w = wit(ayahs, model)
    for rec in w["ayahs"].values():
        rec["words"] = []
    return w


def judge(med, lv3, q=None):
    q = q or {**TW.Q_ALL, 4: .2}
    return H.judge(TW.idx(TW.CAND), TW.idx([]), "c" * 64, {S: TW.cmap(q)},
                   witness={S: med} if med else None, witness_l={S: lv3} if lv3 else None,
                   dual={}, ref_words=TW.ref_words, lv3_text=LV3_TEXT)


class LargeV3Path(unittest.TestCase):
    def test_medium_misses_large_in_place_medium_silent_accepted(self):
        j = judge(silent([4]), wit([4], "large-v3"))
        self.assertTrue(j["ok"], j["reason"])
        ev = j["weak"][str(S)]
        self.assertEqual(ev["witnessed"], [])
        self.assertEqual(ev[H.LV3_KEY], [4])
        self.assertEqual(ev["missing"], [])
        self.assertEqual(ev["largeV3"]["version"], H.LV3_VERSION)

    def test_medium_partial_text_is_not_contradiction(self):
        # medium سمع بعضَ الآية نفسِها متأخّراً (‏فلا يشهد) — النصُّ الناقصُ ليس مناقضة
        j = judge(wit([4], "medium", shift=5000, words=TW.BASE[:4]), wit([4], "large-v3"))
        self.assertTrue(j["ok"], j["reason"])
        self.assertEqual(j["weak"][str(S)][H.LV3_KEY], [4])

    def test_medium_still_first(self):
        # ما شهد له medium يبقى بمساره القديم ولا يُسجَّل لـlarge-v3
        j = judge(wit([4], "medium"), wit([4], "large-v3"))
        self.assertTrue(j["ok"], j["reason"])
        self.assertEqual(j["weak"][str(S)]["witnessed"], [4])
        self.assertNotIn(H.LV3_KEY, j["weak"][str(S)])

    def test_no_large_keeps_old_behaviour(self):
        j = judge(silent([4]), None)
        self.assertFalse(j["ok"])
        self.assertIn("الآيات 4", j["reason"])
        self.assertNotIn(H.LV3_KEY, j["weak"][str(S)])

    # ── شرط 300م.ث (‏W_AGREE_MS) في المسار الجديد ──
    def test_large_far_from_candidate_start_rejected(self):
        j = judge(silent([4]), wit([4], "large-v3", shift=H_AGREE() + 200))
        self.assertFalse(j["ok"])
        self.assertEqual(j["weak"][str(S)][H.LV3_KEY], [])
        self.assertIn("4", j["weak"][str(S)]["largeV3"]["refused"])

    def test_large_early_beyond_300_rejected(self):
        j = judge(silent([4]), wit([4], "large-v3", shift=-(H_AGREE() + 380)))
        self.assertFalse(j["ok"])

    def test_large_within_300_accepted(self):
        j = judge(silent([4]), wit([4], "large-v3", shift=H_AGREE() - 50))
        self.assertTrue(j["ok"], j["reason"])

    # ── شرط عدم المناقضة ──
    def test_medium_hears_other_named_ayah_rejected(self):
        med = wit([4], "medium", words=OTHER + TW.BASE[4:])
        j = judge(med, wit([4], "large-v3"))
        self.assertFalse(j["ok"])
        why = j["weak"][str(S)]["largeV3"]["refused"]["4"]
        self.assertIn("يناقض", why)
        self.assertIn(f"{OTHER_KEY[0]}:{OTHER_KEY[1]}", why)

    def test_other_ayah_outside_claimed_bounds_is_not_contradiction(self):
        # كلماتُ الآية الأخرى في حشو النافذة قبل بدء المدخل (‏ذيلُ الجارة) لا تُعدّ مناقضة: الحكمُ داخل حدود الآية
        med = silent([4])
        st = 4 * 10000
        med["ayahs"]["4"]["words"] = [{"w": w, "s": st - 2500 + i * 400, "e": st - 2500 + i * 400 + 300, "p": .9}
                                      for i, w in enumerate(OTHER[:3])]
        j = judge(med, wit([4], "large-v3"))
        self.assertTrue(j["ok"], j["reason"])

    def test_own_text_repeat_is_not_contradiction(self):
        # ثلاثيّةٌ من نصّ الآية نفسِها (‏ولو وردت في غيرها) ليست مناقضة
        j = judge(wit([4], "medium", shift=5000), wit([4], "large-v3"))
        self.assertTrue(j["ok"], j["reason"])

    def test_low_confidence_other_text_is_not_contradiction(self):
        # «بالثقة نفسِها» (‏`_span_ok` باب المتنازَع): كلماتٌ دون W_MIN_WORD_P لا تُعدّ سماعاً لآيةٍ أخرى
        med = wit([4], "medium", words=OTHER + TW.BASE[4:], p=.3)
        j = judge(med, wit([4], "large-v3"))
        self.assertTrue(j["ok"], j["reason"])

    # ── لا قبولَ بلا medium ──
    def test_large_without_medium_rejected(self):
        j = judge(None, wit([4], "large-v3"))
        self.assertFalse(j["ok"])
        self.assertEqual(j["weak"][str(S)][H.LV3_KEY], [])
        self.assertIn("medium", j["weak"][str(S)]["largeV3"]["invalid"])

    def test_medium_without_this_ayah_rejected(self):
        j = judge(silent([6]), wit([4], "large-v3"), q={**TW.Q_ALL, 4: .2})
        self.assertFalse(j["ok"])
        self.assertIn("لا تفريغَ medium", j["weak"][str(S)]["largeV3"]["refused"]["4"])

    def test_large_passed_as_medium_rejected(self):
        # شاهدُ large-v3 نفسُه في خانة medium ليس شاهداً مستقلّاً
        j = judge(wit([4], "large-v3", shift=5000), wit([4], "large-v3"))
        self.assertFalse(j["ok"])

    def test_medium_of_other_audio_rejected(self):
        j = judge(silent([4]) | {"sha256": "cd" * 32}, wit([4], "large-v3"))
        self.assertFalse(j["ok"])

    # ── صلاحيةُ شاهد large-v3 ──
    def test_path_witness_must_be_large_v3(self):
        j = judge(silent([4]), wit([4], "medium"))
        self.assertFalse(j["ok"])
        self.assertIn("large-v3", j["weak"][str(S)]["largeV3"]["invalid"])

    def test_large_of_other_audio_rejected(self):
        j = judge(silent([4]), wit([4], "large-v3", sha="cd" * 32))
        self.assertFalse(j["ok"])

    def test_large_of_other_text_rejected(self):
        j = judge(silent([4]), wit([4], "large-v3", words=OTHER + TW.BASE[4:]))
        self.assertFalse(j["ok"])

    def test_large_float16_rejected(self):
        w = wit([4], "large-v3")
        w["computeType"] = "float16"
        self.assertFalse(judge(silent([4]), w)["ok"])

    def test_partial_acceptance_still_rejects_rest(self):
        q = {**TW.Q_ALL, 4: .2, 6: .1}
        j = judge(silent([4, 6]), wit([4], "large-v3"), q=q)
        self.assertFalse(j["ok"])
        self.assertEqual(j["weak"][str(S)][H.LV3_KEY], [4])
        self.assertEqual(j["weak"][str(S)]["missing"], [6])

    # ── الإثبات: يُعاد الحكمُ من state-heard ولا يُقرأ حكمٌ مكتوب ──
    def test_gate_error_recomputes_from_state(self):
        from unittest import mock
        import pin_heard as PH
        q = {**TW.Q_ALL, 4: .2}
        rep = {"sha256": "c" * 64, "maps": {str(S): TW.cmap(q)},
               "witness": {str(S): silent([4])}, "witnessL": {str(S): wit([4], "large-v3")},
               "weak": {str(S): {H.LV3_KEY: [4], "missing": []}}, "ok": True}

        class G:                                     # مصحفٌ مصغَّرٌ لما تقرؤه gate_error من النصّ الموثَّق
            get = staticmethod(grams_of)
        with mock.patch.object(PH, "ref_words_for", TW.ref_words), \
                mock.patch.object(H, "disputed_ref_words", lambda _r, _s, _a: list(TW.BASE)), \
                mock.patch.object(H, "mushaf_grams", lambda _r: G):
            self.assertIsNone(H.gate_error(TW.idx(TW.CAND), TW.idx([]), "c" * 64, rep))
            rep2 = dict(rep)
            del rep2["witnessL"]                     # الدليلُ المكتوبُ وحده («weakWitnessLargeV3») لا يُصدَّق
            self.assertIn("الآيات 4", H.gate_error(TW.idx(TW.CAND), TW.idx([]), "c" * 64, rep2))
            rep3 = dict(rep, witnessL={str(S): wit([4], "large-v3", shift=H_AGREE() + 200)})
            self.assertIsNotNone(H.gate_error(TW.idx(TW.CAND), TW.idx([]), "c" * 64, rep3))


class RealText(unittest.TestCase):
    """المناقضةُ بنصّ المصحف الموثَّق (‏`mushaf_grams` و`disputed_ref_words`) لا بمصحفٍ مصغَّر."""

    def rec(self, text):
        return {"windowMs": [0, 20000],
                "words": [{"w": w, "s": 1000 + i * 400, "e": 1300 + i * 400, "p": .9} for i, w in enumerate(text.split())]}

    def test_other_ayah_named(self):
        own = H.disputed_ref_words("hafs", 1, 3)
        why = H.medium_contradiction(self.rec("الرحمن الرحيم مالك يوم الدين"), 1, 3, 0, 15000, own,
                                     H.mushaf_grams("hafs").get)
        self.assertIsNotNone(why)
        self.assertIn("1:4", why)

    def test_own_text_not_contradiction(self):
        own = H.disputed_ref_words("hafs", 1, 2)
        self.assertIsNone(H.medium_contradiction(self.rec("الحمد لله رب العالمين"), 1, 2, 0, 15000, own,
                                                 H.mushaf_grams("hafs").get))


def H_AGREE():
    import pin_heard as PH
    return PH.W_AGREE_MS


if __name__ == "__main__":
    unittest.main()
