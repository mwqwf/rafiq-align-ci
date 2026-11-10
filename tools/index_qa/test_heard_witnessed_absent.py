#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""اختباراتُ قاعدة «مسمّاةٌ غائبةٌ لكنّها مسموعةٌ في خريطة العامّة» (‏ctc-absent-witnessed-1 · قرار القائد 2026-11-10) في `heard_gate.py`.

الحالةُ الحقيقيّة (‏الكردي 004.mp3 · س4 · 4:127): الخريطةُ تضعها عند [4133566، 4163246] بجودة 0.3، وشاهدا float32 (‏medium 42772750710 ·
small 42772755657) فرّغا 4125–4170ث: 4:125 ثمّ 4:126 حتى ≈4162ث ثمّ 4:128 «وإن امرأة خافت» ≈4165ث، ولا «ويستفتونك في النساء».
⚠️ الشاهدان الحقيقيّان **لم يُحفظا في المستودع**، فالقبولُ يُختبر على **زوجٍ مركّبٍ معلَّم** (‏`_wit`) بنصٍّ مصطنعٍ حتميٍّ على
الأزمنة الحقيقيّة نفسِها (‏السابقةُ تنتهي 4162000 واللاحقةُ تبدأ 4165000 · النافذةُ 4125000–4172000).
وكلُّ شرطٍ يُحوَّر وحده فيُردّ (‏وانظر جدولَ التحوّر في وصف الطلب: تعطيلُ الشرط في الشيفرة يُفشل اختبارَه).

    python -m unittest tools.index_qa.test_heard_witnessed_absent
"""
from __future__ import annotations

import copy
import random
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "alignment_v3"))

import heard_gate as H                                           # noqa: E402
import pin_heard as P                                            # noqa: E402

S, A, N = 4, 127, 176          # النساء: 176 آية؛ الغائبةُ 127 وجارتاها 126 و128
SHA = "d" * 64
URL = "https://example.invalid/kurdi/004.mp3"
META = {"sha256": SHA, "fileRef": URL}
CLAIM = [4133566, 4163246]
EXPECTED = 8000.0              # ⇒ نصفُها 4000م.ث؛ والفجوةُ في المركّب 3000
WIN = [4125000, 4172000]
PREV_END, NEXT_START = 4162000, 4165000

VOCAB = ["قال", "ربك", "الارض", "السماء", "علم", "نور", "حكيم", "عزيز", "رحمة", "كتاب", "يوم", "عظيم", "جنة", "نار", "هدى",
         "صراط", "مستقيم", "ناس", "ملك", "فضل", "ايمان", "عمل", "صالح", "خير", "شر", "حق", "باطل", "ظلم", "عدل", "امر",
         "صبر", "شكر", "ذكر", "فجر", "ليل", "نهار", "بحر", "جبل", "سمع", "بصر"]


def text(a):
    """نصٌّ مصطنعٌ حتميٌّ لكلّ آية: اثنتا عشرةَ كلمةً بمطلعٍ ومختَمٍ فريدين بين الآيات المجاورة."""
    r = random.Random(1000 + a)
    ws = r.sample(VOCAB, 12)
    return " ".join(ws)


def ref(s, a):
    return H.disputed_norm_words(text(a))


for _a in (124, 125, 126, 127, 128, 129):                         # حارسٌ على الحتميّة: لا يتشابه مطلعٌ ولا مختَمٌ بين الجوار
    assert ref(S, _a)[:3] != ref(S, 127)[:3] or _a == 127
    assert ref(S, _a)[-3:] != ref(S, 126)[-3:] or _a == 126


def _words(a, start, step=400, p=0.9):
    return [{"w": w, "s": start + i * step, "e": start + i * step + 300, "p": p} for i, w in enumerate(text(a).split())]


def _wit(model="medium", gap=NEXT_START - PREV_END, window=None, prev=True, nxt=True, own_head=False, p=0.9,
         comp="float32", sha=SHA, file_ref=URL, order_swap=False):
    """شاهدٌ مركّب: ‏4:125 قبلها · 4:126 تنتهي PREV_END · 4:128 تبدأ PREV_END+gap (‏ما لم تُسقَط) · ومطلعُ 4:127 اختياريّاً."""
    win = list(window or WIN)
    words = _words(125, 4126000, p=p)
    if prev:
        words += _words(126, PREV_END - 11 * 400 - 300, p=p)
    nstart = PREV_END + gap
    if nxt:
        words += _words(128, nstart, p=p)
    if own_head:
        words += _words(127, 4150000, p=0.9)[:5]
    if order_swap:
        words = sorted(words, key=lambda w: -w["s"])
    return {"surah": S, "riwaya": "hafs", "fileRef": file_ref, "sha256": sha, "model": model, "computeType": comp,
            "ayahs": {"126": {"windowMs": win, "words": words}}}


def _pair(**kw):
    return {"run-a": _wit("medium", **kw), "run-b": _wit("small", **kw)}


def _src(wits):
    return {str(r): H.disputed_src_rec(copy.deepcopy(w)) for r, w in wits.items()}


G_REC = {"anchorMs": list(CLAIM), "anchorQuality": 0.3, "heardMs": None, "score": None,
         "occurrences": [[5527000, 5540000, 0.514]]}


def one(wits=None, src="same", g=G_REC, r=None, ayah=A, n=N, expected=EXPECTED, meta=META, want=SHA):
    wits = _pair() if wits is None else wits
    return H.witnessed_absent_one(S, ayah, n, g, r, wits, _src(wits) if src == "same" else src, ref, meta, want, expected)


class RealCase(unittest.TestCase):
    def test_old_rule_still_refuses_this_case_without_witnesses(self):
        # بلا الاستثناء: الردُّ القديم حرفاً (‏مسمّاةٌ غائبةٌ لكنّها مسموعةٌ).
        import heard_absent as HA
        gm = {str(k): {"anchorMs": [k * 10000, k * 10000 + 8000], "anchorQuality": 0.9, "heardMs": None, "score": None,
                       "occurrences": []} for k in range(1, 31) if k != 13}
        gm["13"] = {"anchorMs": [130000, 138000], "anchorQuality": 0.3, "heardMs": None, "score": None, "occurrences": []}
        with self.assertRaisesRegex(HA.HeardAbsentError, "مسمّاةٌ غائبةٌ لكنّها مسموعةٌ"):
            HA.agreed_anchors(gm, gm, 30, [13])

    def test_synthetic_pair_has_the_real_timeline(self):
        w = _wit()
        toks = H._wtoks(w["ayahs"]["126"])
        self.assertGreater(len(toks), 30)
        self.assertEqual(w["ayahs"]["126"]["windowMs"], WIN)


class Accept(unittest.TestCase):
    def test_pair_accepted_with_evidence(self):
        why, ev = one()
        self.assertIsNone(why)
        self.assertEqual(ev["claimMs"], CLAIM)
        self.assertEqual(ev["mapQuality"], 0.3)
        self.assertEqual(sorted(ev["witnesses"]), ["run-a", "run-b"])
        for d in ev["witnesses"].values():
            self.assertEqual(d["gapMs"], NEXT_START - PREV_END)
            self.assertEqual(d["computeType"], "float32")

    def test_quality_just_below_half_accepted(self):
        g = dict(G_REC, anchorQuality=0.49)
        self.assertIsNone(one(g=g)[0])

    def test_gap_just_below_half_expected_accepted(self):
        self.assertIsNone(one(wits=_pair(gap=3999))[0])


class Mutations(unittest.TestCase):
    """كلُّ شرطٍ يُسقَط وحده ⇒ ردّ. (‏الأسماءُ مرقَّمةٌ بشروط القائد.)"""

    # ١) شاهدان float32 من تشغيلتين متمايزتين، يُعاد تحميلهما ويطابقان المكتوبَ حرفاً
    def test_c1_single_witness(self):
        why, _ = one(wits={"run-a": _wit("medium")})
        self.assertIn("شاهدان", why)

    def test_c1_no_source(self):
        why, _ = one(src={})
        self.assertIn("لا مصدرَ محمَّلٌ", why)

    def test_c1_source_error(self):
        wits = _pair()
        why, _ = one(wits, src={"run-a": {"error": "x"}, "run-b": _src(wits)["run-b"]})
        self.assertIn("تعذّر تحميلُه", why)

    def test_c1_written_differs_from_source_literally(self):
        wits = _pair()
        src = _src(wits)
        wits2 = copy.deepcopy(wits)
        wits2["run-b"]["ayahs"]["126"]["words"][0]["w"] = "غيرها"            # كلمةٌ مضمَّنةٌ تخالف المصدر
        why, _ = one(wits2, src=src)
        self.assertIn("يخالف مصدرَه", why)

    def test_c1_not_float32(self):
        why, _ = one(_pair(comp="int8"))
        self.assertIn("float32", why)

    def test_c1_model_not_allowed(self):
        wits = {"run-a": _wit("medium"), "run-b": _wit("tiny")}
        why, _ = one(wits)
        self.assertIn("float32", why)

    def test_c1_sha_differs(self):
        why, _ = one(_pair(sha="e" * 64))
        self.assertIn("بصمةُ صوت الشاهد", why)

    def test_c1_want_sha_differs(self):
        why, _ = one(want="e" * 64)
        self.assertIn("بصمةُ صوت الشاهد", why)

    def test_c1_file_differs(self):
        why, _ = one(_pair(file_ref="https://example.invalid/other.mp3"))
        self.assertIn("سُمع من", why)

    # ٢) كلاهما يفرّغ النافذة المدّعاة كاملةً ويسمع الجارتين بلفظهما
    def test_c2_window_does_not_cover_claim(self):
        why, _ = one(_pair(window=[4125000, 4150000]))
        self.assertIn("كاملةً", why)

    def test_c2_window_covers_only_start_of_claim(self):
        why, _ = one(_pair(window=[4140000, 4172000]))
        self.assertIn("كاملةً", why)

    def test_c2_second_witness_window_short(self):
        wits = {"run-a": _wit("medium"), "run-b": _wit("small", window=[4125000, 4150000])}
        why, _ = one(wits)
        self.assertIn("run-b", why)
        self.assertIn("كاملةً", why)

    def test_c2_previous_neighbour_not_heard(self):
        why, _ = one(_pair(prev=False))
        self.assertIn("السابقةَ", why)

    def test_c2_next_neighbour_not_heard(self):
        why, _ = one(_pair(nxt=False))
        self.assertIn("اللاحقةَ", why)

    def test_c2_neighbour_low_confidence(self):
        why, _ = one(_pair(p=0.3))
        self.assertIn("السابقةَ", why)

    def test_c2_next_before_previous(self):
        why, _ = one(_pair(gap=-9000))                     # اللاحقةُ تبدأ قبل نهاية السابقة بكثير ⇒ قبل بدء السابقة
        self.assertIn("اللاحقةُ لا تأتي بعد السابقة", why)

    def test_c2_second_witness_missing_next(self):
        wits = {"run-a": _wit("medium"), "run-b": _wit("small", nxt=False)}
        why, _ = one(wits)
        self.assertIn("run-b", why)
        self.assertIn("اللاحقةَ", why)

    # ٣) لا يسمع أيٌّ منهما أوّل W_K كلماتٍ من الغائبة
    def test_c3_first_witness_hears_head(self):
        wits = {"run-a": _wit("medium", own_head=True), "run-b": _wit("small")}
        why, _ = one(wits)
        self.assertIn("أوّلَ 3 كلماتٍ من الآية الغائبة", why)
        self.assertIn("run-a", why)

    def test_c3_second_witness_hears_head(self):
        wits = {"run-a": _wit("medium"), "run-b": _wit("small", own_head=True)}
        why, _ = one(wits)
        self.assertIn("أوّلَ 3 كلماتٍ من الآية الغائبة", why)
        self.assertIn("run-b", why)

    def test_c3_head_heard_even_with_low_confidence(self):
        wits = _pair()
        for w in wits["run-b"]["ayahs"]["126"]["words"]:
            pass
        extra = _words(127, 4150000, p=0.05)[:4]
        wits["run-b"]["ayahs"]["126"]["words"] += extra
        why, _ = one(wits)
        self.assertIn("الآية الغائبة", why)

    # ٤) جودة الخريطة دون 0.5
    def test_c4_quality_half_refused(self):
        why, _ = one(g=dict(G_REC, anchorQuality=0.5))
        self.assertIn("الردُّ القديمُ باقٍ", why)

    def test_c4_quality_high_refused(self):
        why, _ = one(g=dict(G_REC, anchorQuality=0.8))
        self.assertIn("الردُّ القديمُ باقٍ", why)

    def test_c4_solo_performance_in_other_map_refused(self):
        r = {"anchorMs": None, "anchorQuality": None, "heardMs": [4133000, 4160000], "score": 0.55, "occurrences": []}
        why, _ = one(r=r)
        self.assertIn("الردُّ القديمُ باقٍ", why)

    def test_c4_second_map_global_low_ok_but_union_claim_is_covered(self):
        r = {"anchorMs": [4131000, 4164000], "anchorQuality": 0.31, "heardMs": None, "score": None, "occurrences": []}
        self.assertIsNone(one(r=r)[0])                       # النافذةُ تغطّي اتّحادَ المدّعَيَين
        why, _ = one(wits=_pair(window=[4132000, 4172000]), r=r)
        self.assertIn("كاملةً", why)

    # ٥) لا متّسعَ للآية: الفجوةُ < نصف المدّة المتوقَّعة عند الشاهدين
    def test_c5_gap_at_half_expected_refused(self):
        why, _ = one(_pair(gap=4000))
        self.assertIn("فيها متّسعٌ للآية", why)

    def test_c5_gap_large_refused(self):
        why, _ = one(_pair(gap=20000, window=[4125000, 4210000]))
        self.assertIn("فيها متّسعٌ للآية", why)

    def test_c5_only_second_witness_gap_large(self):
        wits = {"run-a": _wit("medium"), "run-b": _wit("small", gap=9000, window=[4125000, 4210000])}
        why, _ = one(wits)
        self.assertIn("run-b", why)
        self.assertIn("متّسعٌ", why)

    def test_c5_no_expected_duration(self):
        why, _ = one(expected=None)
        self.assertIn("لا مدّةَ متوقَّعةً", why)
        why, _ = one(expected=0)
        self.assertIn("لا مدّةَ متوقَّعةً", why)

    # ٦) لا الأولى ولا الأخيرة
    def test_c6_first_ayah(self):
        why, _ = one(ayah=1)
        self.assertIn("الأولى ولا الأخيرة", why)

    def test_c6_last_ayah(self):
        why, _ = one(ayah=N)
        self.assertIn("الأولى ولا الأخيرة", why)

    def test_c6_second_and_penultimate_pass_the_position_guard(self):
        for a in (2, N - 1):
            why, _ = one(ayah=a)
            self.assertNotIn("الأولى ولا الأخيرة", why or "")


def _wit2(prev_ends=(), next_starts=(), window=(4125000, 4210000), model="medium"):
    """شاهدٌ مركّب بمواضعَ حرّة: كلُّ prev_end ذيلُ 4:126 ينتهي عنده، وكلُّ next_start مطلعُ 4:128 يبدأ عنده."""
    words = _words(125, 4126000)
    for e in prev_ends:
        words += _words(126, e - 11 * 400 - 300)
    for st in next_starts:
        words += _words(128, st)
    words.sort(key=lambda w: w["s"])
    return {"surah": S, "riwaya": "hafs", "fileRef": URL, "sha256": SHA, "model": model, "computeType": "float32",
            "ayahs": {"126": {"windowMs": list(window), "words": words}}}


def _pair2(**kw):
    return {"run-a": _wit2(model="medium", **kw), "run-b": _wit2(model="small", **kw)}


class MeetingLocation(unittest.TestCase):
    """⛔ (‏مراجعةُ القائد #108) الملتقى في الموضع المدّعى لا في موضعٍ آخر يتكرّر فيه اللفظ."""

    # (أ) مع claim: [نهاية السابقة، بدء اللاحقة] تتقاطع مع نافذة الخريطة المدّعاة
    def test_a_meeting_outside_claim_refused(self):
        why, _ = one(_pair2(prev_ends=[4200000], next_starts=[4201000]))
        self.assertIn("لا يقع في الموضع المدّعى", why)

    def test_a_meeting_inside_claim_accepted(self):
        self.assertIsNone(one(_pair2(prev_ends=[4162000], next_starts=[4165000]))[0])

    def test_a_meeting_before_claim_refused(self):
        g = dict(G_REC, anchorMs=[4150000, 4160000])
        why, _ = one(_pair2(prev_ends=[4140000], next_starts=[4141000]), g=g)
        self.assertIn("لا يقع في الموضع المدّعى", why)

    def test_a_repeated_tail_far_away_cannot_prove_absence(self):
        # ذيلُ السابقة يتكرّر عند 4200000 ومطلعُ اللاحقة بعده بثانية: كان «آخرُ ظهورٍ + أوّلُ ظهورٍ بعده» يُثبت فجوةَ ثانيةٍ في غير مكانها.
        # والموضعُ الحقيقيّ (‏السابقة 4162000) لا لاحقةَ بعده إلا البعيدة ⇒ فجوةٌ واسعة ⇒ ردّ.
        why, _ = one(_pair2(prev_ends=[4162000, 4200000], next_starts=[4201000]))
        self.assertIn("متّسعٌ", why)

    def test_a_repeated_pair_far_away_while_real_place_has_room(self):
        # في الموضع الحقيقيّ فجوةٌ واسعةٌ (‏9000) وفي موضعٍ بعيدٍ زوجٌ متلاصق: لا يُنتخب البعيدُ.
        why, _ = one(_pair2(prev_ends=[4162000, 4200000], next_starts=[4171000, 4201000]))
        self.assertIn("متّسعٌ", why)

    # (ب) في البوّابة وبلا claim: الملتقى بين نهاية مدخل a−1 وبدء مدخل a+1 ضمن TOL_MS
    NOCLAIM = {"anchorMs": None, "anchorQuality": None, "heardMs": None, "score": None, "occurrences": []}

    def test_b_no_claim_and_no_bounds_refused(self):
        why, _ = one(_pair2(prev_ends=[4162000], next_starts=[4165000]), g=self.NOCLAIM)
        self.assertIn("لا موضعَ يقيّد", why)

    def test_b_no_claim_with_bounds_accepted(self):
        wits = _pair2(prev_ends=[4162000], next_starts=[4165000])
        why, _ = H.witnessed_absent_one(S, A, N, self.NOCLAIM, None, wits, _src(wits), ref, META, SHA, EXPECTED,
                                        bounds=(PREV_END, NEXT_START))
        self.assertIsNone(why)

    def test_b_meeting_outside_bounds_refused(self):
        wits = _pair2(prev_ends=[4162000], next_starts=[4165000])
        for b in ((PREV_END + 5000, NEXT_START + 9000), (PREV_END - 20000, NEXT_START - 9000)):
            why, _ = H.witnessed_absent_one(S, A, N, self.NOCLAIM, None, wits, _src(wits), ref, META, SHA, EXPECTED, bounds=b)
            self.assertIn("لا يقع في الموضع المدّعى", why)

    def test_b_bounds_tolerance_is_tol_ms(self):
        wits = _pair2(prev_ends=[4162000], next_starts=[4165000])
        ok, _ = H.witnessed_absent_one(S, A, N, self.NOCLAIM, None, wits, _src(wits), ref, META, SHA, EXPECTED,
                                       bounds=(PREV_END + H.TOL_MS, NEXT_START))
        self.assertIsNone(ok)
        bad, _ = H.witnessed_absent_one(S, A, N, self.NOCLAIM, None, wits, _src(wits), ref, META, SHA, EXPECTED,
                                        bounds=(PREV_END + H.TOL_MS + 1, NEXT_START))
        self.assertIn("لا يقع في الموضع المدّعى", bad)

    def test_b_gate_refuses_when_neighbour_entries_elsewhere(self):
        idx = _idx()
        for e in idx["entries"]:
            if e["ayahId"] == f"{S}:{A - 1}":
                e["startMs"], e["endMs"] = 1000000, 1008000
        why, _ = _verdict(idx, cmap=_cmap())
        self.assertIn("لا يقع في الموضع المدّعى", why)

    def test_b_gate_refuses_when_neighbour_entry_missing(self):
        idx = _idx()
        idx["entries"] = [e for e in idx["entries"] if e["ayahId"] != f"{S}:{A + 1}"]
        why, _ = _verdict(idx)
        self.assertIn("لا مدخلَ للجارة", why)

    def test_b_gate_without_claim_in_map_still_bounded(self):
        # خريطةٌ لا تسمع الغائبةَ (‏بلا claim): القيدُ المكانيّ على مداخل المرشّح وحدَه ⇒ يقبل الملتقى الصحيح ويردّ البعيد.
        cm = _cmap()
        cm["anchors"][str(A)] = [None, None, []]
        self.assertIsNone(_verdict(cmap=cm)[0])
        idx = _idx()
        for e in idx["entries"]:
            if e["ayahId"] == f"{S}:{A + 1}":
                e["startMs"], e["endMs"] = 9000000, 9008000
        why, _ = _verdict(idx, cmap=cm)
        self.assertIn("لا يقع في الموضع المدّعى", why)


class ExpectedFromPeers(unittest.TestCase):
    def chars(self, a):
        return sum(len(w) for w in ref(S, a))

    def test_median_rate_times_chars(self):
        durs = {a: (a * 10000, a * 10000 + 100 * self.chars(a)) for a in (120, 121, 122, 123)}
        self.assertAlmostEqual(H.witnessed_expected_ms(durs, 127, self.chars), 100 * self.chars(127), places=3)

    def test_too_few_peers(self):
        durs = {a: (a * 10000, a * 10000 + 8000) for a in (120, 121)}
        self.assertIsNone(H.witnessed_expected_ms(durs, 127, self.chars))

    def test_the_absent_ayah_is_not_its_own_peer(self):
        durs = {a: (a * 10000, a * 10000 + 8000) for a in (120, 121, 127)}
        self.assertIsNone(H.witnessed_expected_ms(durs, 127, self.chars))


# ───────────── البوّابةُ: يُعاد الحكمُ من المصدر والمرشّح ─────────────
def _span(a):
    """مدى مدخل الآية في المرشّح: 126 تنتهي PREV_END و128 تبدأ NEXT_START (‏ملتقاهما = ما سمعه الشاهدان)، وغيرُهما a*10000."""
    if a == A - 1:
        return PREV_END - 8000, PREV_END
    if a == A + 1:
        return NEXT_START, NEXT_START + 8000
    return a * 10000, a * 10000 + 8000


def _entries():
    return [{"ayahId": f"{S}:{a}", "startMs": _span(a)[0], "endMs": _span(a)[1], "fileRef": URL, "conf": 0.9,
             "confBand": "HIGH"} for a in range(1, N + 1) if a != A]


def _cmap(q=0.3):
    anc = {str(a): [list(_span(a)), 0.9, []] for a in range(1, N + 1) if a != A}
    anc[str(A)] = [list(CLAIM), q, [[5527000, 5540000, 0.514]]]
    return {"surah": S, "sha256": SHA, "fileRef": URL, "totalMs": 9_000_000, "engine": "ctc", "anchors": anc}


def _idx(wits=None, absent=(A,), claim=True):
    tr = {"op": f"declare_gap:{S}", "reasonCode": "SOURCE_TRUNCATED", "reasonUser": "تسجيلُ هذه السورة ينقصه بعضُ آياتها.",
          "truncatedGaps": {str(S): {"absent": list(absent), "reason": "source_truncated"}}}
    if claim:
        tr["witnessedAbsent"] = {str(S): {str(A): {"witnesses": copy.deepcopy(_pair() if wits is None else wits)}}}
        tr["witnessedAbsentVersion"] = "ctc-absent-witnessed-1"
    return {"riwaya": "hafs", "reciterId": "kurdi", "entries": _entries(), "audioSha256": [SHA], "transform": tr}


def _verdict(idx=None, cmap=None, src="same", n=N):
    idx = idx or _idx()
    claims = idx["transform"]["witnessedAbsent"][str(S)]
    if src == "same":
        src = {}
        for c in claims.values():
            src.update(_src(c["witnesses"]))
    return H.witnessed_absent_verdict(S, cmap or _cmap(), SHA, idx, ref, n_ayahs=n, sources=src)


class Gate(unittest.TestCase):
    def test_verdict_accepts_and_names_version(self):
        why, ev = _verdict()
        self.assertIsNone(why, why)
        self.assertEqual(ev["version"], "ctc-absent-witnessed-1")
        self.assertIn(str(A), ev["accepted"])

    def test_no_claim_changes_nothing(self):
        self.assertEqual(H.witnessed_absent_verdict(S, _cmap(), SHA, _idx(claim=False), ref, n_ayahs=N), (None, None))

    def test_verdict_refuses_when_map_quality_reaches_half(self):
        why, ev = _verdict(cmap=_cmap(q=0.5))
        self.assertIn("الردُّ القديمُ باقٍ", why)
        self.assertEqual(ev["accepted"], {})

    def test_verdict_refuses_when_source_differs(self):
        idx = _idx()
        src = _src(_pair())
        src["run-a"]["ayahs"]["126"]["words"][3]["w"] = "اخرى"
        why, _ = _verdict(idx, src=src)
        self.assertIn("يخالف مصدرَه", why)

    def test_verdict_refuses_without_loaded_source(self):
        why, _ = _verdict(src={})
        self.assertIn("لا مصدرَ محمَّلٌ", why)

    def test_verdict_refuses_ayah_not_declared_in_truncated_gaps(self):
        why, _ = _verdict(_idx(absent=(100,)))
        self.assertIn("لم يُعلَن حجبُها", why)

    def test_verdict_refuses_ayah_that_has_an_entry(self):
        idx = _idx()
        idx["entries"].append({"ayahId": f"{S}:{A}", "startMs": 1, "endMs": 2, "fileRef": URL})
        why, _ = _verdict(idx)
        self.assertIn("لها مدخلٌ في المرشّح", why)

    def test_verdict_refuses_over_quarter(self):
        idx = _idx()
        idx["transform"]["witnessedAbsent"][str(S)] = {str(a): {"witnesses": _pair()} for a in range(60, 105)}
        idx["transform"]["truncatedGaps"][str(S)]["absent"] = list(range(60, 105))
        why, _ = _verdict(idx)
        self.assertIn("ربع آيات السورة", why)

    def test_verdict_uses_candidate_entries_for_expected_duration(self):
        # مداخلُ الأقران تُطوَّل ×20 ⇒ المتوقَّعُ ضخمٌ فتتّسع الفجوةُ نسبيّاً (‏يقبل)، وتُقصَّر ⇒ المتوقَّعُ صغيرٌ فتردّ.
        idx = _idx()
        for e in idx["entries"]:
            if e["ayahId"] not in (f"{S}:{A - 1}", f"{S}:{A + 1}"):
                e["endMs"] = e["startMs"] + 50
        why, _ = _verdict(idx)
        self.assertIn("متّسعٌ", why)

    def test_judge_recomputes_and_reports(self):
        idx = _idx()
        src = {}
        for c in idx["transform"]["witnessedAbsent"][str(S)].values():
            src.update(_src(c["witnesses"]))
        j = H.judge(idx, None, "c" * 64, {S: _cmap()}, disputed_src={str(S): src}, ref_words=ref)
        self.assertTrue(j["ok"], j["reason"])
        self.assertIn(str(A), j["witnessedAbsent"][str(S)]["accepted"])

    def test_judge_refuses_surah_on_bad_claim(self):
        idx = _idx()
        j = H.judge(idx, None, "c" * 64, {S: _cmap()}, disputed_src={str(S): {}}, ref_words=ref)
        self.assertFalse(j["ok"])
        self.assertIn("لا مصدرَ محمَّلٌ", j["reason"])

    def test_judge_without_claim_unchanged(self):
        j = H.judge(_idx(claim=False), None, "c" * 64, {S: _cmap()}, ref_words=ref)
        self.assertTrue(j["ok"], j["reason"])
        self.assertNotIn("witnessedAbsent", j)

    def test_disputed_sources_loads_witnessed_runs_from_source(self):
        seen = []

        def loader(run, surah):
            seen.append((run, surah))
            return _pair()[run]
        out = H.disputed_sources(_idx(), loader=loader)
        self.assertEqual(sorted(seen), [("run-a", S), ("run-b", S)])
        self.assertEqual(sorted(out[str(S)]), ["run-a", "run-b"])

    def test_gate_error_recomputes_from_stored_source(self):
        idx = _idx()
        src = {}
        for c in idx["transform"]["witnessedAbsent"][str(S)].values():
            src.update(_src(c["witnesses"]))
        rep = {"sha256": "c" * 64, "maps": {str(S): _cmap()}, "disputedSource": {str(S): src}}
        from unittest import mock
        with mock.patch.object(H, "disputed_ref_words", lambda r_, s_, a_: ref(s_, a_)):
            self.assertIsNone(H.gate_error(idx, None, "c" * 64, rep))
            rep["disputedSource"] = {str(S): {}}
            self.assertIn("لا مصدرَ محمَّلٌ", H.gate_error(idx, None, "c" * 64, rep))


if __name__ == "__main__":
    unittest.main()
