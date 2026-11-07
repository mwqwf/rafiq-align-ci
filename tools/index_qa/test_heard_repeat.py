#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""اختباراتُ الباب الثالث في بوّابة السماع: آيةٌ مكرّرةٌ مشهودة (‏إذنُ المالك 2026-11-07 20:40Z).

الآيةُ المنحرفةُ عن المِرساة العامّة تمرّ **بثلاثةٍ مجتمعة** وحدَها: شاهدُ Whisper حاسمٌ ≤300م.ث عن البدء المنشور · مدخلُها يمرّ إحصاءَ
النوافذ بقاعدة الأقرب · تكرارُها مقيسٌ في الخريطة (‏أداءٌ آخر بجودة ≥0.5). والتحوّر: لا يكفي شرطٌ ولا اثنان، والبدءُ المزاح ±1ث لا يمرّ."""
import itertools
import os
import sys
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "alignment"))
import heard_gate as H  # noqa: E402
from common import norm  # noqa: E402

S, N, DEV = 5, 10, 7                           # السورةُ وعددُ آياتها والآيةُ المنحرفة
SHA = "aa" * 32
REF = "https://h/005.mp3"
CAND_SHA = "c" * 64
LET = "بتثجحخدذرزسشصضطظعغفقكلمنهو"             # حروفٌ لا يمسّها التطبيع
PUB_SHIFT = 1                                  # يخالف المنشورُ المرشّحَ في كلّ مدخل ⇒ السورةُ معدّلة


def word(a, i):
    return LET[a % 26] + LET[(i * 5 + a) % 26] + LET[(a * 3 + i * 7 + 1) % 26]


def texts():
    """نصٌّ لكلّ آيةٍ من ثماني كلماتٍ لا تشترك مع جاراتها (‏فتنجح قاعدةُ الأقرب بهامشٍ واسع)."""
    return {a: norm(" ".join(word(a, i) for i in range(8))).split() for a in range(1, N + 1)}


TEXTS = texts()


def ref_words(_riw, _s, a):
    return TEXTS[a]


def starts_for():
    return {a: a * 10000 for a in range(1, N + 1)}


def cand_idx(shift=None):
    st = dict(starts_for())
    if shift:
        st[DEV] += shift
    ents = [{"ayahId": f"{S}:{a}", "startMs": v, "endMs": v + 8000, "fileRef": REF} for a, v in st.items()]
    shas = [""] * 114
    shas[S - 1] = SHA
    return {"riwaya": "hafs", "reciterId": "x", "entries": ents, "audioSha256": shas}


def pub_idx():
    p = cand_idx()
    p["entries"] = [dict(e, startMs=e["startMs"] + PUB_SHIFT) for e in p["entries"]]
    return p


def gmap(occ=None, dev_anchor=120000, q=.9, sha=SHA, extra_dev=None):
    """مراسي كلّ الآيات عند بدئها إلا DEV فمِرساتُها بعيدةٌ (‏منحرفةٌ)؛ occ أداءاتُ DEV."""
    anchors = {}
    for a, st in starts_for().items():
        anchors[str(a)] = [[st, st + 900], q, []]
    anchors[str(DEV)] = [[dev_anchor, dev_anchor + 900], q, list(occ if occ is not None else [[70000, 78000, .6]])]
    for a, off in (extra_dev or {}).items():
        anchors[str(a)] = [[starts_for()[a] + off, starts_for()[a] + off + 900], q, []]
    return {"sha256": sha, "fileRef": REF, "anchors": anchors, "engine": "ctc-heardmap-1"}


def wit(ayahs=(DEV,), word_shift=0, win_shift=0, sha=SHA, bad_words=False, window_pad=300, model="medium"):
    """شاهدُ Whisper: الكلماتُ في الصوت عند البدء المنشور + word_shift، والنافذةُ من (البدء + win_shift − window_pad)."""
    out = {"surah": S, "riwaya": "hafs", "fileRef": REF, "sha256": sha, "model": model, "computeType": "float32", "ayahs": {}}
    for a in ayahs:
        st = starts_for()[a]
        words = [{"w": ("خطأ" if bad_words else w), "s": st + word_shift + i * 400, "e": st + word_shift + i * 400 + 300, "p": .9}
                 for i, w in enumerate(TEXTS[a])]
        lo = max(0, st + win_shift - window_pad)
        out["ayahs"][str(a)] = {"windowMs": [lo, st + win_shift + 11000], "words": words}
    return out


def census(ayahs=(DEV,), neighbour=False, start_shift=0, sha=SHA, model="small"):
    """إحصاءُ النوافذ لمدخل الآية: كلماتُ نافذته؛ neighbour ⇒ النافذةُ تحمل نصَّ الآية التالية (‏حتمًا «آية أخرى»)."""
    ents = {}
    for a in ayahs:
        st = starts_for()[a]
        src = TEXTS[a + 1] if neighbour else TEXTS[a]
        ents[str(a)] = {"startMs": st + start_shift, "endMs": st + 8000 + start_shift,
                        "words": [{"w": w, "s": st + i * 400, "p": .9} for i, w in enumerate(src)]}
    return {"surah": S, "riwaya": "hafs", "fileRef": REF, "sha256": sha, "model": model, "computeType": "float32", "entries": ents}


def judge(g, w=None, c=None, cand=None):
    return H.judge(cand or cand_idx(), pub_idx(), CAND_SHA, {S: g},
                   rwit={S: w} if w is not None else None, rcensus={S: c} if c is not None else None,
                   ref_words=ref_words, texts=TEXTS)


class ThreeConditions(unittest.TestCase):
    def test_all_three_pass_and_are_recorded(self):
        j = judge(gmap(), wit(), census())
        self.assertTrue(j["ok"], j["reason"])
        row = next(r for r in j["surahs"][str(S)]["rows"] if r["ayah"] == DEV)
        self.assertEqual(row["status"], H.REPEAT_STATUS)
        ev = j["repeat"][str(S)][str(DEV)]
        self.assertTrue(ev["passed"] and ev["witnessOk"] and ev["censusOk"])
        self.assertEqual(ev["witness"]["diffMs"], 0)
        self.assertEqual(ev["witness"]["heard"], " ".join(TEXTS[DEV]))
        self.assertIn("أدنى ثقة", ev["witness"]["detail"])
        self.assertEqual(ev["census"]["verdict"], "pass")
        self.assertGreaterEqual(ev["census"]["gap"], 0.1)
        self.assertEqual(ev["otherPerformance"]["startMs"], 70000)
        self.assertGreaterEqual(ev["otherPerformance"]["q"], H.REPEAT_OCC_Q)
        self.assertEqual((ev["startMs"], ev["anchorMs"]), (DEV * 10000, 120000))

    def test_truth_table_only_all_three_pass(self):
        """تحوّر: كلُّ شرطٍ وحده لا يكفي، وكلُّ اثنين بلا الثالث لا يكفيان."""
        for has_rep, has_wit, has_cen in itertools.product((True, False), repeat=3):
            with self.subTest(repeat=has_rep, witness=has_wit, census=has_cen):
                g = gmap() if has_rep else gmap(occ=[])
                j = judge(g, wit() if has_wit else None, census() if has_cen else None)
                self.assertEqual(j["ok"], has_rep and has_wit and has_cen, j["reason"])

    def test_without_measured_repeat_never_passes(self):
        for occ in ([], [[70000, 78000, .49]],                      # جودةٌ دون 0.5
                    [[119000, 127000, .9]],                         # داخل مِرساتها لا منفصلةٌ عنها (‏119000 ≥ 120900−1500 ؟ لا ⇒ داخل المدى)
                    [[40000, 48000, .9]]):                          # على مِرساة الآية 4 ⇒ تشابهٌ لا تكرار
            with self.subTest(occ=occ):
                j = judge(gmap(occ=occ), wit(), census())
                self.assertFalse(j["ok"])
                self.assertEqual(j["repeat"], {})

    def test_repeat_quality_boundary_and_after(self):
        self.assertTrue(judge(gmap(occ=[[70000, 78000, .5]]), wit(), census())["ok"])          # 0.5 ⇒ مقيس
        self.assertTrue(judge(gmap(occ=[[130000, 138000, .6]]), wit(), census())["ok"])        # أداءٌ بعدها
        self.assertEqual(H.other_performance(DEV, [120000, 120900], [[130000, 138000, .6]], {})["where"], "after")
        self.assertEqual(H.other_performance(DEV, [120000, 120900], [[70000, 78000, .6]], {})["where"], "before")
        self.assertIsNone(H.other_performance(DEV, [120000, 120900], [[120000, 120900, .9]], {}))   # المِرساةُ نفسُها ليست أداءً آخر

    def test_only_deviating_ayahs_enter(self):
        # آيةٌ غيرُ منحرفة لا تدخل الباب، وغيرُ المقيسة لا تُرفع به
        j = judge(gmap(occ=[]), None, None)
        self.assertFalse(j["ok"])
        g = gmap(q=.3)                                              # كلُّها غيرُ مقيسة
        j = judge(g, wit(), census())
        self.assertEqual(j["repeat"], {})
        clean = {"sha256": SHA, "fileRef": REF, "anchors": {str(a): [[st, st + 900], .9, []] for a, st in starts_for().items()}}
        j = judge(clean)
        self.assertTrue(j["ok"])
        self.assertEqual(j["repeat"], {})

    def test_other_deviation_still_rejects_surah(self):
        j = judge(gmap(extra_dev={3: 30000}), wit(), census())
        self.assertFalse(j["ok"])
        self.assertIn("الآيات 3", j["reason"])
        self.assertNotIn(str(DEV), j["reason"].split("الآيات")[-1])


class WitnessConditions(unittest.TestCase):
    def test_wrong_words_rejected(self):
        self.assertFalse(judge(gmap(), wit(bad_words=True), census())["ok"])

    def test_shifted_start_by_one_second_never_passes(self):
        """البدءُ المزاح ±1ث: الصوتُ عند موضعه والبدءُ المنشور مزاح — شاهدٌ وإحصاءٌ صادقان لا يحسمان."""
        for d in (1000, -1000, 400, -400):
            with self.subTest(shift=d):
                cand = cand_idx(shift=d)
                # نافذةُ الشاهد تُقطع من البدء المزاح كما يفعل سيرُ العمل؛ والكلماتُ في الصوت عند الموضع الأصليّ
                w = wit(win_shift=d)
                c = census(start_shift=d)                          # إحصاءٌ على نافذة مدخل المرشّح المزاح نفسِه
                j = judge(gmap(), w, c, cand=cand)
                self.assertFalse(j["ok"])
                ev = j["repeat"][str(S)][str(DEV)]
                self.assertFalse(ev["witnessOk"])
                self.assertEqual(ev["witness"]["diffMs"], -d)

    def test_shifted_start_with_original_window_rejected_too(self):
        cand = cand_idx(shift=1000)
        j = judge(gmap(), wit(), census(start_shift=1000), cand=cand)          # نافذةٌ أصليّةٌ تُسقط عن البدء المزاح
        self.assertFalse(j["ok"])

    def test_agreement_boundary_is_300ms(self):
        self.assertTrue(judge(gmap(), wit(word_shift=300), census())["ok"])
        self.assertFalse(judge(gmap(), wit(word_shift=301), census())["ok"])
        self.assertFalse(judge(gmap(), wit(word_shift=-301), census())["ok"])

    def test_old_wide_window_is_refused(self):
        # نافذةٌ تبدأ قبل البدء المنشور بـ3000م.ث (‏القديمة) لا تُقبل شاهداً لهذا الباب
        self.assertFalse(judge(gmap(), wit(window_pad=3000), census())["ok"])
        self.assertTrue(judge(gmap(), wit(window_pad=300), census())["ok"])
        self.assertFalse(judge(gmap(), wit(window_pad=0), census())["ok"])      # كلمةٌ ملتصقةٌ ببدء النافذة (‏فرق 0) ⇒ ليست شاهداً

    def test_word_stuck_to_window_start_is_not_a_witness(self):
        """شاهدٌ دائريّ: بدءُ أوّل كلمةٍ = بدءُ النافذة (‏المنشور − 300) يمرّ ≤300 دائماً ⇒ يُرفض (< 50م.ث)."""
        j = judge(gmap(), wit(word_shift=-300), census())            # الكلمةُ عند بدء النافذة تماماً (‏فرقٌ 300 عن المنشور فيوافق ≤300)
        self.assertFalse(j["ok"])
        ev = j["repeat"][str(S)][str(DEV)]
        self.assertTrue(ev["witness"]["stuckToWindow"])
        self.assertEqual(ev["witness"]["wordMinusWindowMs"], 0)
        self.assertFalse(judge(gmap(), wit(word_shift=-251), census())["ok"])    # فرقٌ 49 عن بدء النافذة
        self.assertTrue(judge(gmap(), wit(word_shift=-250), census())["ok"])     # فرقٌ 50 ⇒ يُقبل
        ev = judge(gmap(), wit(), census())["repeat"][str(S)][str(DEV)]
        self.assertEqual(ev["witness"]["wordMinusWindowMs"], 300)                # الصيغةُ العاديّة: كلمةٌ بعد النافذة بـ300
        self.assertFalse(ev["witness"]["stuckToWindow"])

    def test_missing_window_refused(self):
        w = wit()
        del w["ayahs"][str(DEV)]["windowMs"]
        self.assertFalse(judge(gmap(), w, census())["ok"])

    def test_witness_on_other_audio_or_model_rejected(self):
        self.assertFalse(judge(gmap(), wit(sha="bb" * 32), census())["ok"])
        self.assertFalse(judge(gmap(), wit(model="tiny"), census())["ok"])
        w = wit()
        w["computeType"] = "int8"
        self.assertFalse(judge(gmap(), w, census())["ok"])

    def test_witness_for_other_ayah_does_not_help(self):
        self.assertFalse(judge(gmap(), wit(ayahs=(3,)), census())["ok"])

    def test_no_fuzzy(self):
        w = wit()
        w["ayahs"][str(DEV)]["words"][0]["w"] = TEXTS[DEV][0] + "ن"       # حرفٌ زائدٌ في أوّل كلمة: تشابهٌ عالٍ لا تطابق
        self.assertFalse(judge(gmap(), w, census())["ok"])


class CensusConditions(unittest.TestCase):
    def test_neighbour_text_rejected(self):
        j = judge(gmap(), wit(), census(neighbour=True))
        self.assertFalse(j["ok"])
        ev = j["repeat"][str(S)][str(DEV)]
        self.assertFalse(ev["censusOk"])
        self.assertEqual(ev["census"]["reason"], "آية أخرى")

    def test_census_window_must_be_the_published_entry(self):
        self.assertFalse(judge(gmap(), wit(), census(start_shift=500))["ok"])

    def test_census_on_other_audio_or_model_rejected(self):
        self.assertFalse(judge(gmap(), wit(), census(sha="bb" * 32))["ok"])
        self.assertFalse(judge(gmap(), wit(), census(model="tiny"))["ok"])

    def test_census_without_this_ayah_rejected(self):
        self.assertFalse(judge(gmap(), wit(), census(ayahs=(3,)))["ok"])

    def test_missing_reference_text_closes(self):
        with mock.patch("entry_window_census.surah_texts", side_effect=SystemExit("لا نصّ")):
            j = H.judge(cand_idx(), pub_idx(), CAND_SHA, {S: gmap()}, rwit={S: wit()}, rcensus={S: census()}, ref_words=ref_words)
        self.assertFalse(j["ok"])


class Recompute(unittest.TestCase):
    def rep(self, **kw):
        base = {"sha256": CAND_SHA, "maps": {str(S): gmap()}}
        base.update(kw)
        return base

    def test_gate_error_recomputes_from_data(self):
        good = self.rep(repeatWitness={str(S): wit()}, repeatCensus={str(S): census()})
        with mock.patch("entry_window_census.surah_texts", return_value=TEXTS), \
                mock.patch("pin_heard.ref_words_for", side_effect=ref_words):
            self.assertIsNone(H.gate_error(cand_idx(), pub_idx(), CAND_SHA, good))
            # حكمٌ مكتوبٌ يدّعي النجاحَ بلا شاهدٍ وإحصاء ⇒ يُردّ (‏يُعاد الحسابُ ولا يُوثق بالمكتوب)
            forged = self.rep(ok=True, reason=None, repeat={str(S): {str(DEV): {"passed": True}}})
            self.assertIn("بوّابةُ السماع", H.gate_error(cand_idx(), pub_idx(), CAND_SHA, forged))
            only_wit = self.rep(repeatWitness={str(S): wit()}, ok=True)
            self.assertIn("بوّابةُ السماع", H.gate_error(cand_idx(), pub_idx(), CAND_SHA, only_wit))
            only_cen = self.rep(repeatCensus={str(S): census()}, ok=True)
            self.assertIn("بوّابةُ السماع", H.gate_error(cand_idx(), pub_idx(), CAND_SHA, only_cen))
            # شاهدٌ حقيقيٌّ بإزاحة 1ث ⇒ يُردّ
            shifted = self.rep(repeatWitness={str(S): wit(word_shift=1000)}, repeatCensus={str(S): census()})
            self.assertIn("بوّابةُ السماع", H.gate_error(cand_idx(), pub_idx(), CAND_SHA, shifted))

    def test_constants_untouched(self):
        self.assertEqual((H.TOL_MS, H.MIN_Q, H.REPEAT_SIM, H.WIT_PAD_MS), (1500, 0.5, 0.7, 300))
        self.assertEqual(H.REPEAT_OCC_Q, 0.5)

    def test_plan_lists_only_deviating_with_repeat(self):
        self.assertEqual(H.repeat_plan(starts_for(), gmap()), [DEV])
        self.assertEqual(H.repeat_plan(starts_for(), gmap(occ=[])), [])
        self.assertEqual(H.repeat_plan(starts_for(), gmap(extra_dev={3: 30000})), [DEV])      # الآية 3 بلا تكرارٍ مقيس


if __name__ == "__main__":
    unittest.main()
