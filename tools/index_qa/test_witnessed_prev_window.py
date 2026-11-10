#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""اختباراتُ «سماعُ السابقة بأيّ W_K كلماتٍ متّصلةٍ من آخر ستّ كلماتٍ منها» في قاعدة `witnessedAbsent` (‏ctc-absent-witnessed-1 · أمر القائد 2026-11-10).

الحالةُ الحقيقيّة (‏kurdi 4:127 · أوّلُ تشغيلٍ حقيقيّ): ردّ الشاهدَ 42772750710 «لا يسمع الجارةَ السابقةَ بلفظها (‏آخرَ 3 كلماتٍ «بكل شيا محيطا»)»
لأنّ Whisper يكتب «من كل شيء محيطا» لا «بكل شيء محيطا». وتفريغُ الشاهدين الجديدين float32 (‏medium 42783782493 · small 42783787598) كما أبلغه القائد:
  medium: وكان@4157.68 (‏0.97) الله@4158.98 (‏0.98) من@4160.04 (‏0.75) كل@4160.42 شيء@4161.2 محيطاً@4162.86 ولا شيءَ بعدها حتى 4170؛
  small:  وكان@4158.0 (‏0.98) الله@4158.72 (‏0.96) من@4159.64 (‏0.45) كل شيء محيطا@4162.02 ثمّ وإن@4165.26 (‏0.68) امرأة خافت…؛ و«الأرض» قبل «وكان» بثقة ≥0.81 فيهما.
⚠️ **ما لم يُحفظ في المستودع يُركَّب معلَّماً**: أزمنةُ «الأرض» وثقاتُ كلمات الجارة اللاحقة غيرِ المذكورة وأزمنةُ نهايات الكلمات (‏`_real`)،
ونافذةُ التفريغ 4125–4170 (‏التي غطّاها الشاهدان الأوّلان) في القبول، لأنّ النافذةَ الحقيقيّةَ للجديدين 4142–4170 **لا تغطّي** نافذةَ الخريطة
المدّعاة [4133566، 4163246] فتردّها القاعدةُ كما هي (‏`test_real_windows_do_not_cover_the_claim`) — وmedium الجديد لا يسمع 4:128 (‏`test_real_medium_hears_no_next_neighbour`).

    python -m unittest tools.index_qa.test_witnessed_prev_window
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "alignment_v3"))

import heard_gate as H                                           # noqa: E402

S, A, N = 4, 127, 176
SHA = "k" * 64
URL = "https://example.invalid/kurdi/004.mp3"
META = {"sha256": SHA, "fileRef": URL}
CLAIM = [4133566, 4163246]
G_REC = {"anchorMs": list(CLAIM), "anchorQuality": 0.3, "heardMs": None, "score": None, "occurrences": [[5527000, 5540000, 0.514]]}


def ref(s, a):
    return H.disputed_ref_words("hafs", s, a)


OWN, PREV, NXT = ref(S, A), ref(S, A - 1), ref(S, A + 1)
EXPECTED = sum(len(w) for w in OWN) * 190.0                   # ≈33630م.ث (‏وتيرةُ 190م.ث للحرف) ⇒ نصفُها ≈16815


def _real(word, start_s, p, dur=0.3):
    return {"w": word, "s": int(round(start_s * 1000)), "e": int(round((start_s + dur) * 1000)), "p": p}


def _wit(model, words, window):
    return {"surah": S, "riwaya": "hafs", "fileRef": URL, "sha256": SHA, "model": model, "computeType": "float32",
            "ayahs": {"126": {"windowMs": list(window), "words": words}}}


def medium_real(window=(4142000, 4170000), with_next=False):
    w = [_real("الأرض", 4156.9, 0.85), _real("وكان", 4157.68, 0.97), _real("الله", 4158.98, 0.98), _real("من", 4160.04, 0.75),
         _real("كل", 4160.42, 0.9), _real("شيء", 4161.2, 0.9), _real("محيطاً", 4162.86, 0.9)]
    if with_next:                                              # ⚠️ تركيب: medium الأوّلُ (‏42772750710) سمع «وإن امرأة خافت» ≈4165
        w += [_real("وإن", 4165.3, 0.8), _real("امرأة", 4165.7, 0.9), _real("خافت", 4166.1, 0.9)]
    return _wit("medium", w, window)


def small_real(window=(4142000, 4170000)):
    w = [_real("الأرض", 4157.4, 0.85), _real("وكان", 4158.0, 0.98), _real("الله", 4158.72, 0.96, dur=0.25), _real("من", 4159.64, 0.45),
         _real("كل", 4160.6, 0.9), _real("شيء", 4161.3, 0.9), _real("محيطا", 4162.02, 0.9),
         _real("وإن", 4165.26, 0.68), _real("امرأة", 4165.6, 0.9), _real("خافت", 4166.0, 0.9)]
    return _wit("small", w, window)


def _src(wits):
    return {r: H.disputed_src_rec(w) for r, w in wits.items()}


def one(wits, g=G_REC, bounds=None, expected=EXPECTED):
    return H.witnessed_absent_one(S, A, N, g, None, wits, _src(wits), ref, META, SHA, expected, bounds=bounds)


WIDE = (4125000, 4170000)


class RealKurdi(unittest.TestCase):
    def test_accepts_new_witnesses_when_they_cover_the_claim(self):
        why, ev = one({"42783782493": medium_real(WIDE, with_next=True), "42783787598": small_real(WIDE)})
        self.assertIsNone(why, why)
        sm = ev["witnesses"]["42783787598"]
        self.assertEqual(sm["gapMs"], 4165260 - 4158970)        # من نهاية «الله» (‏المقطعُ المطابَق «الأرض وكان الله») إلى «وإن»
        self.assertLess(sm["gapMs"], 0.5 * EXPECTED)
        self.assertAlmostEqual(sm["gapMs"] / 1000, 6.3, delta=0.3)
        self.assertEqual(sm["prevEndMs"], 4158970)               # لا من نهاية الآية 4162860/4162270

    def test_the_old_tail_rule_would_have_refused_both(self):
        # «شيا محيطا» وحدَها (‏آخرُ W_K) لا تُطابق «من كل شيء محيطا»: الطلبُ القديم كان يردّ.
        for w in (medium_real(WIDE, True), small_real(WIDE)):
            toks = [x[0] for x in H._wtoks(w["ayahs"]["126"])]
            self.assertNotIn(PREV[-3:], [toks[i:i + 3] for i in range(len(toks) - 2)])
            self.assertIn(PREV[-6:-3], [toks[i:i + 3] for i in range(len(toks) - 2)])        # «الأرض وكان الله»

    def test_real_windows_do_not_cover_the_claim(self):
        # النافذةُ الحقيقيّةُ 4142–4170 لا تغطّي [4133566، 4163246] (‏الشرط ٢ باقٍ لم يُرخَ).
        why, _ = one({"42783782493": medium_real(with_next=True), "42783787598": small_real()})
        self.assertIn("كاملةً", why)

    def test_real_medium_hears_no_next_neighbour(self):
        # medium 42783782493 كما أُبلغ: لا شيءَ بعد «محيطاً» حتى 4170 ⇒ لا يسمع 4:128 فيُردّ (‏الشرط ٢ باقٍ).
        why, _ = one({"42783782493": medium_real(WIDE), "42783787598": small_real(WIDE)})
        self.assertIn("اللاحقةَ", why)
        self.assertIn("42783782493", why)

    def test_next_neighbour_confidence_still_required(self):
        w = small_real(WIDE)
        for x in w["ayahs"]["126"]["words"]:
            if x["w"] == "وإن":
                x["p"] = 0.3
        why, _ = one({"42783782493": medium_real(WIDE, True), "42783787598": w})
        self.assertIn("اللاحقةَ", why)


class PrevWindow(unittest.TestCase):
    """⛔ المقطعُ المطابَق داخل آخر ستّ كلماتٍ وحدَها، وW_K لا يتغيّر."""

    def _wits(self, prev_words, prev_start=4150.0, nxt_start=4163.0, window=WIDE):
        def mk(model):
            w = [_real(x, prev_start + i * 0.4, 0.9) for i, x in enumerate(prev_words)]
            w += [_real(x, nxt_start + i * 0.4, 0.9) for i, x in enumerate(NXT[:3])]
            return _wit(model, w, window)
        return {"r1": mk("medium"), "r2": mk("small")}

    def test_every_trigram_inside_last_six_is_accepted(self):
        n = len(PREV)
        for i in range(n - 6, n - 3 + 1):
            why, _ = one(self._wits(PREV[i:i + 3]))
            self.assertIsNone(why, f"i={i} {PREV[i:i + 3]}: {why}")

    def test_trigram_outside_last_six_refused(self):
        n = len(PREV)
        for i in (0, 2, n - 7):                                   # «في الأرض وكان» تبدأ قبل آخر ستّ كلمات
            why, _ = one(self._wits(PREV[i:i + 3]))
            self.assertIn("السابقةَ", why, f"i={i} {PREV[i:i + 3]}")

    def test_wk_is_not_reduced_two_words_do_not_suffice(self):
        why, _ = one(self._wits(PREV[-2:]))
        self.assertIn("السابقةَ", why)
        why, _ = one(self._wits([PREV[-3], PREV[-1]]))            # غيرُ متّصلة
        self.assertIn("السابقةَ", why)

    def test_confidence_not_relaxed_for_the_matched_trigram(self):
        wits = self._wits(PREV[-6:-3])
        for w in wits.values():
            w["ayahs"]["126"]["words"][0]["p"] = 0.3
        why, _ = one(wits)
        self.assertIn("السابقةَ", why)

    def test_gap_is_from_the_end_of_the_matched_segment_not_the_verse_end(self):
        # المقطعُ «الأرض وكان الله» ينتهي T؛ واللاحقةُ بعده بـ17000م.ث ≥ نصف المتوقَّع (‏16815) ⇒ ردّ،
        # ولو حُسبت من نهاية الآية المقدَّرة (‏T + 11 حرفاً × 190 = +2090) لكانت 14910 < 16815 فتُقبل خطأً.
        seg_end = int(round((4150.0 + 2 * 0.4 + 0.3) * 1000))
        wits = self._wits(PREV[-6:-3], nxt_start=(seg_end + 17000) / 1000, window=(4125000, 4200000))
        why, _ = one(wits)
        self.assertIn("متّسعٌ", why)
        self.assertIn(f"{seg_end}", why)
        ok_wits = self._wits(PREV[-6:-3], nxt_start=(seg_end + 16000) / 1000, window=(4125000, 4200000))
        self.assertIsNone(one(ok_wits)[0])

    def test_other_conditions_remain_head_of_absent_heard(self):
        wits = self._wits(PREV[-6:-3])
        wits["r2"]["ayahs"]["126"]["words"] += [_real(x, 4155.0 + i * 0.4, 0.2) for i, x in enumerate(OWN[:3])]
        why, _ = one(wits)
        self.assertIn("الآية الغائبة", why)

    def test_other_conditions_remain_quality_half(self):
        why, _ = one(self._wits(PREV[-6:-3]), g=dict(G_REC, anchorQuality=0.5))
        self.assertIn("الردُّ القديمُ باقٍ", why)

    def test_other_conditions_remain_meeting_in_claim(self):
        why, _ = one(self._wits(PREV[-6:-3], prev_start=4180.0, nxt_start=4183.0, window=(4125000, 4200000)))
        self.assertIn("لا يقع في الموضع المدّعى", why)


class GateBounds(unittest.TestCase):
    """البوّابةُ والبناءُ يعيدان الحكمَ نفسَه، **بلا تقديرٍ بوتيرة الأقران**:
    (١) المقطعُ هو آخرُ W_K كلماتٍ بلا شيءٍ بعده ⇒ القيدُ القديمُ حرفاً (‏نهايتُه ضمن ±TOL_MS من نهاية مدخل a−1)؛
    (٢) بقيت بعده كلماتٌ ⇒ نهايتُه المقيسةُ داخل مدخل a−1: بين بدئه ونهايته + TOL_MS؛ وبدءُ اللاحقة ضمن ±TOL_MS كما كان."""

    NEXT_START = 4163000

    def _wits(self, seg):
        def mk(model):
            w = [_real(x, 4150.0 + i * 0.4, 0.9) for i, x in enumerate(seg)]
            w += [_real(x, 4163.0 + i * 0.4, 0.9) for i, x in enumerate(NXT[:3])]
            return _wit(model, w, WIDE)
        return {"r1": mk("medium"), "r2": mk("small")}

    SEG_END = 4150000 + 800 + 300                                # نهايةُ المقطع المطابَق (‏3 كلماتٍ × 0.4 ثم 0.3)

    # --- (٢) كلماتٌ بعد المقطع -------------------------------------------------------------------------------------
    def test_tail_segment_inside_entry_accepted(self):
        why, _ = one(self._wits(PREV[-6:-3]), bounds=(self.SEG_END + 3000, self.NEXT_START, self.SEG_END - 5000))
        self.assertIsNone(why, why)

    def test_tail_segment_end_tolerance_is_tol_ms_after_entry_end(self):
        ok, _ = one(self._wits(PREV[-6:-3]), bounds=(self.SEG_END - H.TOL_MS, self.NEXT_START, self.SEG_END - 5000))
        self.assertIsNone(ok, ok)
        bad, _ = one(self._wits(PREV[-6:-3]), bounds=(self.SEG_END - H.TOL_MS - 1, self.NEXT_START, self.SEG_END - 5000))
        self.assertIn("لا يقع في الموضع المدّعى", bad)

    def test_tail_segment_before_entry_start_refused(self):
        # المقطعُ ينتهي قبل بدء مدخل a−1 بميلّي ثانيةٍ واحدةٍ ⇒ ليس داخلَ المدخل ⇒ ردّ.
        bad, _ = one(self._wits(PREV[-6:-3]), bounds=(self.SEG_END + 3000, self.NEXT_START, self.SEG_END + 1))
        self.assertIn("لا يقع في الموضع المدّعى", bad)
        ok, _ = one(self._wits(PREV[-6:-3]), bounds=(self.SEG_END + 3000, self.NEXT_START, self.SEG_END))
        self.assertIsNone(ok, ok)

    def test_tail_segment_without_entry_start_refused(self):
        # بلا بدء مدخل a−1 لا يُتحقَّق من أنّ المقطع داخله ⇒ لا يُقبل مقطعٌ تبقّت بعده كلمات.
        bad, _ = one(self._wits(PREV[-6:-3]), bounds=(self.SEG_END + 3000, self.NEXT_START))
        self.assertIn("لا يقع في الموضع المدّعى", bad)

    def test_tail_segment_next_start_still_within_tol(self):
        ok, _ = one(self._wits(PREV[-6:-3]), bounds=(self.SEG_END + 3000, self.NEXT_START + H.TOL_MS, self.SEG_END - 5000))
        self.assertIsNone(ok, ok)
        bad, _ = one(self._wits(PREV[-6:-3]), bounds=(self.SEG_END + 3000, self.NEXT_START + H.TOL_MS + 1, self.SEG_END - 5000))
        self.assertIn("لا يقع في الموضع المدّعى", bad)

    # --- (١) المقطع آخرُ W_K بلا كلماتٍ بعده: القيدُ القديمُ حرفاً (‏حتى مع تمرير بدء المدخل) -------------------------------
    def test_last_words_keep_old_constraint_literally(self):
        wits = self._wits(PREV[-3:])
        seg_end = 4150000 + 800 + 300
        ok, _ = one(wits, bounds=(seg_end + H.TOL_MS, self.NEXT_START, seg_end - 5000))
        self.assertIsNone(ok, ok)
        bad, _ = one(wits, bounds=(seg_end + H.TOL_MS + 1, self.NEXT_START, seg_end - 5000))
        self.assertIn("لا يقع في الموضع المدّعى", bad)
        bad2, _ = one(wits, bounds=(seg_end - H.TOL_MS - 1, self.NEXT_START, seg_end - 5000))
        self.assertIn("لا يقع في الموضع المدّعى", bad2)

    def test_last_words_ignore_entry_start(self):
        # القيدُ القديم لا يعرف بدءَ المدخل: بدءٌ بعد المقطع لا يغيّر الحكم.
        wits = self._wits(PREV[-3:])
        ok, _ = one(wits, bounds=(4150000 + 1100, self.NEXT_START, 4160000))
        self.assertIsNone(ok, ok)


if __name__ == "__main__":
    unittest.main()
