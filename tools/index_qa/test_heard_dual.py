#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""اختباراتُ الباب الثاني في بوّابة السماع (‏المرجع المزدوج G+R · قرار القائد 1 · 2026-11-07).

الحالاتُ الخمس في البند 7 من القرار + حدودُ «يُغلق عند الشكّ»:
 ١ ما ردّه القديمُ بانحرافٍ مقيسٍ يبقى مردوداً ما لم يحسمه الشاهدُ الثالث (‏ولا يحسمه إن انحرفت كلُّ خريطةٍ قاستْه).
 ٢ التنازعُ بلا شاهدٍ مردود.   ٣ التغطيةُ دون 90٪ مع عامّةٍ دون النصف مردودة.
 ٤ خلافُ عيّنة الاستقلال (‏أو غيابُ شاهدٍ حاسمٍ لها) يردّ السورة.   ٥ قارئٌ خارج القائمة مطابقٌ للقديم حرفاً.
 ٦ المزدوجُ لا يمرّر آيةً لم يشهد لها الصوتُ."""
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "alignment"))
import heard_gate as H  # noqa: E402
from common import norm  # noqa: E402

S, N = 5, 20                                   # السورةُ المختبَرة وعددُ آياتها
SHA = "aa" * 32
REF = "https://h/005.mp3"
CAND_SHA = "c" * 64
BASE = ["الحمد", "لله", "رب", "العالمين", "الرحمن", "الرحيم", "مالك", "يوم"]
DUAL = {"hafs/saad": {S}}


def ref_words(_riw, _s, _a):
    return norm(" ".join(BASE)).split()


def starts_for():
    return {a: a * 10000 for a in range(1, N + 1)}


def cand_idx(rec="saad", moved=True):
    ents = [{"ayahId": f"{S}:{a}", "startMs": st, "endMs": st + 8000, "fileRef": REF} for a, st in starts_for().items()]
    shas = [""] * 114
    shas[S - 1] = SHA
    return {"riwaya": "hafs", "reciterId": rec, "entries": ents, "audioSha256": shas}


def pub_idx(rec="saad"):
    p = cand_idx(rec)
    p["entries"] = [dict(e, startMs=e["startMs"] + 1) for e in p["entries"]]     # يخالفه في كلّ مدخل ⇒ السورة معدّلة
    return p


def cmap(measured, dev=(), sha=SHA, quality=.9, model=False):
    """measured: آياتٌ لها مِرساة؛ dev: {آية: انحرافٌ بالم.ث}؛ ما عداها غيرُ مقيس."""
    dev = dict(dev)
    anchors = {}
    for a in range(1, N + 1):
        if a in measured:
            st = starts_for()[a] - dev.get(a, 0)
            anchors[str(a)] = [[st, st + 900], quality, []]
        else:
            anchors[str(a)] = [None, None, []]
    m = {"sha256": sha, "fileRef": REF, "anchors": anchors, "engine": "ctc-heardmap-1"}
    if model:
        m["quranModel"] = H.pinned_quran_model()
    return m


def G(measured, dev=()):
    return cmap(measured, dev)


def R(measured, dev=()):
    return cmap(measured, dev, model=True)


def witness(ayahs, shift=0, sha=SHA, model="small", bad_words=False):
    """شاهدُ Whisper حاسمٌ للآيات المعطاة (‏يطابق الطرفين بثقة 0.9) يبدأ عند البدء المنشور + shift."""
    out = {"surah": S, "riwaya": "hafs", "fileRef": REF, "sha256": sha, "model": model, "computeType": "float32", "ayahs": {}}
    for a in ayahs:
        st = starts_for()[a] + shift
        words = [{"w": ("خطأ" if bad_words else w), "s": st + i * 400, "e": st + i * 400 + 300, "p": .9} for i, w in enumerate(BASE)]
        out["ayahs"][str(a)] = {"windowMs": [st - 3000, st + 6000], "words": words}
    return out


def judge(cand, maps_g, maps_r, wit=None, dual=DUAL, pub=None):
    return H.judge(cand, pub if pub is not None else pub_idx(cand["reciterId"]), CAND_SHA,
                   {S: maps_g}, {S: maps_r} if maps_r is not None else None,
                   {S: wit} if wit is not None else None, dual=dual, ref_words=ref_words)


def full_wit(g, r, **kw):
    """شاهدٌ حاسمٌ لكلّ ما تطلبه الخريطتان (‏كما يفعل سيرُ العمل)."""
    return witness(H.dual_witness_plan(starts_for(), g, r, CAND_SHA, S), **kw)


class Contest(unittest.TestCase):
    """١–٢: القديمُ يردّ بانحرافٍ مقيس؛ المزدوجُ يحسمه الشاهدُ في التنازع وحده."""

    def setUp(self):
        self.everyone = set(range(1, N + 1))

    def test_old_rejects_measured_deviation(self):
        g = G(self.everyone, {7: 30000})
        j = H.judge(cand_idx(), pub_idx(), CAND_SHA, {S: g})                  # بلا قائمةٍ ⇒ القديم
        self.assertFalse(j["ok"])
        self.assertIn("الآية 7", j["reason"])

    def test_contested_without_witness_rejected(self):
        g, r = G(self.everyone, {7: 30000}), R(self.everyone)
        j = judge(cand_idx(), g, r)
        self.assertFalse(j["ok"])
        self.assertIn("متنازَعةٌ", j["reason"])
        self.assertIn("الآية 7", j["reason"])

    def test_contested_with_conclusive_witness_passes_and_is_recorded(self):
        g, r = G(self.everyone, {7: 30000}), R(self.everyone)
        j = judge(cand_idx(), g, r, full_wit(g, r))
        self.assertTrue(j["ok"], j["reason"])
        ev = j["dual"][str(S)]
        self.assertEqual(ev["contested"], [7])
        self.assertEqual(ev["contestedResolved"], [7])
        self.assertEqual((ev["gMeasured"], ev["rMeasured"], ev["n"]), (N, N, N))

    def test_deviation_on_every_measuring_map_is_not_rescued_by_witness(self):
        g, r = G(self.everyone, {7: 30000}), R(self.everyone, {7: 29000})
        j = judge(cand_idx(), g, r, witness(range(1, N + 1)))
        self.assertFalse(j["ok"])
        self.assertIn("الآية 7", j["reason"])

    def test_deviation_on_only_measuring_map_stays_rejected(self):
        # ما ردّه القديم بانحرافٍ مقيس والتلاوةُ لم تقِس الآية ⇒ يبقى مردوداً ولو جاء شاهد
        r_meas = self.everyone - {7}
        g, r = G(self.everyone, {7: 30000}), R(r_meas)
        j = judge(cand_idx(), g, r, witness(range(1, N + 1)))
        self.assertFalse(j["ok"])

    def test_zero_tolerance_boundary_is_the_old_one(self):
        g, r = G(self.everyone, {7: 1500}), R(self.everyone)
        self.assertTrue(judge(cand_idx(), g, r)["ok"])                         # 1500 ⇒ ok
        g = G(self.everyone, {7: 1501})
        self.assertFalse(judge(cand_idx(), g, r)["ok"])                        # 1501 ⇒ تنازعٌ بلا شاهد

    def test_witness_must_agree_with_published_start(self):
        g, r = G(self.everyone, {7: 30000}), R(self.everyone)
        for shift in (400, 5000, -5000):
            with self.subTest(shift=shift):
                j = judge(cand_idx(), g, r, full_wit(g, r, shift=shift))
                self.assertFalse(j["ok"])

    def test_witness_text_mismatch_does_not_decide(self):
        g, r = G(self.everyone, {7: 30000}), R(self.everyone)
        j = judge(cand_idx(), g, r, full_wit(g, r, bad_words=True))
        self.assertFalse(j["ok"])

    def test_witness_of_other_audio_or_model_is_ignored(self):
        g, r = G(self.everyone, {7: 30000}), R(self.everyone)
        plan = H.dual_witness_plan(starts_for(), g, r, CAND_SHA, S)
        self.assertFalse(judge(cand_idx(), g, r, witness(plan, sha="bb" * 32))["ok"])
        self.assertFalse(judge(cand_idx(), g, r, witness(plan, model="tiny"))["ok"])
        w = witness(plan)
        w["computeType"] = "int8"
        self.assertFalse(judge(cand_idx(), g, r, w)["ok"])


class Coverage(unittest.TestCase):
    """٣: عامّةٌ دون النصف ⇒ يلزم 90٪ بالخريطتين أو بالشاهد؛ وقاعدةُ النصف كما هي حين تبلغه العامّة."""

    def setUp(self):
        # عامّ 5/20 (دون النصف) · تلاوة 1–16 و20 = 17/20 = 85٪ · غيرُ المقيسة 17–19 (‏ليست ذيلاً لأنّ 20 مقيسة)
        self.g, self.r = G(set(range(1, 6))), R(set(range(1, 17)) | {20})

    def test_below_ninety_with_general_below_half_rejected(self):
        j = judge(cand_idx(), self.g, self.r, witness([a for a in H.dual_witness_plan(starts_for(), self.g, self.r, CAND_SHA, S)
                                                       if a not in (17, 18, 19)]))
        self.assertFalse(j["ok"])
        self.assertIn("التغطيةُ 17/20 دون 90٪", j["reason"])

    def test_no_witness_at_all_is_rejected(self):
        self.assertFalse(judge(cand_idx(), self.g, self.r)["ok"])

    def test_witness_completes_coverage_for_named_ayahs(self):
        j = judge(cand_idx(), self.g, self.r, full_wit(self.g, self.r))
        self.assertTrue(j["ok"], j["reason"])
        self.assertEqual(j["dual"][str(S)]["coverWitnessed"], [17, 18, 19])
        self.assertEqual(j["dual"][str(S)]["covered"], N)

    def test_partial_witness_that_reaches_ninety_percent_passes_coverage(self):
        # 17 + شاهدٌ لآيةٍ واحدة = 18/20 = 90٪ بالضبط ⇒ تُقبل التغطية (‏≥ 90٪ لا > 90٪)
        plan = H.dual_witness_plan(starts_for(), self.g, self.r, CAND_SHA, S)
        j = judge(cand_idx(), self.g, self.r, witness([a for a in plan if a not in (18, 19)]))
        self.assertEqual(j["dual"][str(S)]["covered"], 18)
        # ⛔ (2026-11-10 · تشديد) التغطيةُ 90٪ لا تُعفي الآيتين الممسوستين اللتين لم تقسهما خريطةٌ ولا شاهد
        self.assertFalse(j["ok"])
        self.assertIn("الآيات 18,19", j["reason"])
        self.assertIn("مسّها التحويل", j["reason"])
        j2 = judge(cand_idx(), self.g, self.r, witness(plan))
        self.assertTrue(j2["ok"], j2["reason"])

    def test_half_rule_unchanged_when_general_reaches_half(self):
        g, r = G(set(range(1, 11))), R(set())                                   # عامّ 10/20 = النصف بالضبط
        j = judge(cand_idx(), g, r)
        self.assertFalse(j["ok"])                                               # 11–20 بلا خريطتين ⇒ ذيلٌ غيرُ مقيس (‏كالقديم)
        self.assertIn("ذيلٌ غيرُ مقيسٍ بالخريطتين", j["reason"])
        g2, r2 = G(set(range(1, 11)) | {20}), R(set(range(11, 19)))
        j2 = judge(cand_idx(), g2, r2, full_wit(g2, r2))
        self.assertTrue(j2["ok"], j2["reason"])                                 # لا تغطيةَ 90٪ لازمة: العامّةُ بلغت النصف
        self.assertEqual(j2["dual"][str(S)]["coverWitnessed"], [])

    def test_tail_unmeasured_by_both_is_not_filled_by_witness(self):
        g, r = G(set(range(1, 6))), R(set(range(1, 17)))                         # 17–20 ذيلٌ من 4 آيات
        j = judge(cand_idx(), g, r, full_wit(g, r))
        self.assertFalse(j["ok"])                                               # يُسدّ تغطيةً بالشاهد ولا يُسدّ ذيلاً
        self.assertIn("ذيلٌ غيرُ مقيسٍ بالخريطتين", j["reason"])


class Independence(unittest.TestCase):
    """٤: عيّنةُ الاستقلال — 4 آياتٍ من المقيس بالتلاوة وحدها يحسمها الشاهد."""

    def setUp(self):
        self.g, self.r = G(set(range(1, 6)) | {19, 20, 18}), R(set(range(1, 21)))    # R-only: 6..17 (12 آية)
        self.plan = H.dual_witness_plan(starts_for(), self.g, self.r, CAND_SHA, S)

    def test_sample_is_four_from_r_only_and_deterministic(self):
        nd = H.dual_needs(H.dual_classify(starts_for(), self.g, self.r), CAND_SHA, S)
        self.assertEqual(len(nd["sample"]), H.DUAL_SAMPLE_K)
        self.assertTrue(all(6 <= a <= 17 for a in nd["sample"]))
        self.assertEqual(nd["sample"], H.dual_sample(CAND_SHA, S, range(6, 18)))
        self.assertNotEqual(nd["sample"], H.dual_sample("d" * 64, S, range(6, 18)))

    def test_conclusive_sample_passes(self):
        j = judge(cand_idx(), self.g, self.r, witness(self.plan))
        self.assertTrue(j["ok"], j["reason"])
        self.assertEqual(j["dual"][str(S)]["sampleOk"], j["dual"][str(S)]["sample"])

    def test_sample_disagreement_over_1500_rejects_surah(self):
        samp = H.dual_sample(CAND_SHA, S, range(6, 18))
        w = witness(self.plan)
        bad = witness([samp[0]], shift=2000)                                     # الشاهدُ يخالف المنشورَ بـ2ث
        w["ayahs"][str(samp[0])] = bad["ayahs"][str(samp[0])]
        j = judge(cand_idx(), self.g, self.r, w)
        self.assertFalse(j["ok"])
        self.assertIn("عيّنةُ الاستقلال", j["reason"])
        self.assertIn(str(samp[0]), j["reason"])

    def test_sample_without_witness_rejects(self):
        j = judge(cand_idx(), self.g, self.r, None)
        self.assertFalse(j["ok"])
        self.assertIn("عيّنةُ الاستقلال", j["reason"])

    def test_one_missing_sample_ayah_rejects(self):
        samp = H.dual_sample(CAND_SHA, S, range(6, 18))
        w = witness([a for a in self.plan if a != samp[1]])
        self.assertFalse(judge(cand_idx(), self.g, self.r, w)["ok"])

    def test_sample_seed_is_the_candidate_fingerprint(self):
        j1 = H.judge(cand_idx(), pub_idx(), CAND_SHA, {S: self.g}, {S: self.r}, {S: witness(self.plan)},
                     dual=DUAL, ref_words=ref_words)
        other = "d" * 64
        j2 = H.judge(cand_idx(), pub_idx(), other, {S: self.g}, {S: self.r}, {S: witness(self.plan)},
                     dual=DUAL, ref_words=ref_words)
        self.assertEqual(j1["dual"][str(S)]["sample"], H.dual_sample(CAND_SHA, S, range(6, 18)))
        self.assertEqual(j2["dual"][str(S)]["sample"], H.dual_sample(other, S, range(6, 18)))


class OutsideList(unittest.TestCase):
    """٥: من خارج القائمة حكمُه القديمُ حرفاً."""

    def _same(self, cand, g, r):
        # (2026-11-10) الشاهدُ يُقرأ الآن لقاعدة المِرساة الضعيفة في كلّ سورةٍ معدّلة ⇒ يُعطى للقديم أيضاً؛ والمقصودُ باقٍ:
        #    الباب المزدوج (‏maps_r والقائمة) لا يغيّر شيئاً لقارئٍ خارجها.
        old = H.judge(cand, pub_idx(cand["reciterId"]), CAND_SHA, {S: g}, None, {S: witness(range(1, N + 1))},
                      ref_words=ref_words)
        new = H.judge(cand, pub_idx(cand["reciterId"]), CAND_SHA, {S: g}, {S: r}, {S: witness(range(1, N + 1))},
                      dual=DUAL, ref_words=ref_words)
        for k in ("ok", "reason", "required", "modified", "sample", "surahs", "sampleFindings", "version"):
            self.assertEqual(old[k], new[k], k)
        self.assertEqual(new["dual"], {})

    def test_other_reader_identical_to_old(self):
        everyone = set(range(1, N + 1))
        for g in (G(everyone), G(everyone, {3: 40000}), G(set(range(1, 6)))):
            with self.subTest(g=sorted(g["anchors"])[:1]):
                self._same(cand_idx("somebody"), g, R(everyone))

    def test_listed_reader_other_surah_identical_to_old(self):
        everyone = set(range(1, N + 1))
        old = H.judge(cand_idx(), pub_idx(), CAND_SHA, {S: G(set(range(1, 6)))})
        new = H.judge(cand_idx(), pub_idx(), CAND_SHA, {S: G(set(range(1, 6)))}, {S: R(everyone)},
                      dual={"hafs/saad": {S + 1}}, ref_words=ref_words)
        self.assertEqual((old["ok"], old["reason"]), (new["ok"], new["reason"]))

    def test_candidate_without_identity_is_old(self):
        c = cand_idx()
        c.pop("reciterId")
        self.assertEqual(H.dual_surahs(c, DUAL), set())

    def test_unmodified_surah_of_listed_reader_stays_old_report_only(self):
        c = cand_idx()
        j = H.judge(c, c, CAND_SHA, {S: G(set(range(1, 21)), {5: 40000})}, dual=DUAL, ref_words=ref_words)
        self.assertEqual(j["dual"], {})                                          # لا باب ثانٍ لسورةٍ غيرِ معدّلة
        self.assertTrue(j["ok"])


class NotHeard(unittest.TestCase):
    """٦: المزدوجُ لا يمرّر ما لم يشهد له الصوت، ولا يقبل خريطةً غيرَ مثبَّتة النسب."""

    def setUp(self):
        self.everyone = set(range(1, N + 1))
        self.g, self.r = G(self.everyone), R(self.everyone)

    def test_baseline_passes(self):
        self.assertTrue(judge(cand_idx(), self.g, self.r)["ok"])

    def test_missing_r_map_rejects(self):
        j = judge(cand_idx(), self.g, None)
        self.assertFalse(j["ok"])
        self.assertIn("لا خريطةَ سماعٍ بنموذج التلاوة", j["reason"])

    def test_r_map_on_other_audio_rejects(self):
        j = judge(cand_idx(), self.g, dict(self.r, sha256="bb" * 32))
        self.assertFalse(j["ok"])
        self.assertIn("صوتٍ آخر", j["reason"])

    def test_r_map_without_pinned_model_rejects(self):
        for bad in (None, {}, dict(H.pinned_quran_model(), revision="0" * 40), dict(H.pinned_quran_model(), weightsSha256="x")):
            with self.subTest(bad=bad):
                r = dict(self.r)
                if bad is None:
                    r.pop("quranModel")
                else:
                    r["quranModel"] = bad
                j = judge(cand_idx(), self.g, r)
                self.assertFalse(j["ok"])
                self.assertIn("بلا نسبِ النموذج المثبَّت", j["reason"])

    def test_general_map_carrying_quran_model_rejects(self):
        j = judge(cand_idx(), dict(self.g, quranModel=H.pinned_quran_model()), self.r)
        self.assertFalse(j["ok"])

    def test_maps_from_different_files_reject(self):
        j = judge(cand_idx(), self.g, dict(self.r, fileRef="https://other/005.mp3"))
        self.assertFalse(j["ok"])

    def test_wrong_general_audio_rejects_like_old(self):
        j = judge(cand_idx(), dict(self.g, sha256="bb" * 32), self.r)
        self.assertFalse(j["ok"])
        self.assertIn("غيرُ صوت المرشّح", j["reason"])

    def test_ayah_unheard_by_both_and_unwitnessed_is_not_passed_below_coverage(self):
        g, r = G(set(range(1, 4))), R(set(range(1, 14)))                         # 13/20 = 65٪
        self.assertFalse(judge(cand_idx(), g, r)["ok"])

    def test_gate_error_recomputes_and_ignores_forged_verdict(self):
        g, r = G(self.everyone, {7: 30000}), R(self.everyone)
        forged = {"sha256": CAND_SHA, "ok": True, "verdict": "مقبول", "maps": {str(S): g}, "mapsR": {str(S): r}, "witness": {}}
        old = H.DUAL_FILE
        try:
            with tempfile.TemporaryDirectory() as td:
                f = os.path.join(td, "d.txt")
                with open(f, "w", encoding="utf-8") as fh:
                    fh.write("hafs/saad 5 | قياس: عامّ 20/20 | سبب: اختبار\n")
                H.DUAL_FILE = H.Path(f)
                self.assertIn("بوّابةُ السماع", H.gate_error(cand_idx(), pub_idx(), CAND_SHA, forged))
                good = dict(forged, maps={str(S): G(self.everyone)})
                self.assertIsNone(H.gate_error(cand_idx(), pub_idx(), CAND_SHA, good))
                # حكمٌ قديمٌ بلا mapsR لقارئٍ في القائمة ⇒ يُردّ (‏يُغلق)
                legacy = {"sha256": CAND_SHA, "maps": {str(S): G(self.everyone)}}
                self.assertIn("لا خريطةَ سماعٍ بنموذج التلاوة", H.gate_error(cand_idx(), pub_idx(), CAND_SHA, legacy))
        finally:
            H.DUAL_FILE = old


class ListFile(unittest.TestCase):
    def test_real_list_loads_and_has_saad_and_named_surahs(self):
        d = H.load_dual()
        self.assertTrue({38, 39, 40, 29, 45, 12} <= d["hafs/saad"])
        # قرار القائد 20:30Z: مقيسُ العامّة في 36 و53 ليس دون النصف فتمضيان بالحكم القديم،
        # والثلاثُ لم تستوفِ (٣)/(٤) فلا تعود إلا بقاعدة «الشهادة الكاملة».
        self.assertFalse({36, 53} & d["hafs/saad"])
        for k in ("hafs/3siri", "warsh/gharbi_warsh", "hafs/m_qari"):
            self.assertNotIn(k, d)
        self.assertNotIn("qalun/maroush_qalun", d)

    def test_every_line_has_evidence_and_reason(self):
        with open(H.DUAL_FILE, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
        for raw in lines:
            ln = raw.strip()
            if ln and not ln.startswith("#"):
                parts = [x.strip() for x in ln.split("|")]
                self.assertEqual(len(parts), 3, ln)
                self.assertRegex(parts[1], r"\d")

    def test_malformed_list_raises(self):
        with tempfile.TemporaryDirectory() as td:
            for i, bad in enumerate(("hafs/saad 36 | | سبب", "hafs/saad 36 | قياس بلا رقم | سبب", "hafs/saad 36 | قياس 1/2",
                                     "hafs/saad 0 | قياس 1/2 | سبب", "saad 36 | قياس 1/2 | سبب",
                                     "hafs/saad 36 | قياس 1/2 | سبب\nhafs/saad 36 | قياس 1/2 | سبب")):
                f = os.path.join(td, f"{i}.txt")
                with open(f, "w", encoding="utf-8") as fh:
                    fh.write(bad + "\n")
                with self.subTest(bad=bad), self.assertRaises(ValueError):
                    H.load_dual(f)

    def test_constants_are_in_code(self):
        self.assertEqual((H.TOL_MS, H.MIN_Q, H.REPEAT_SIM, H.REPEAT_NEAR_MS, H.TAIL_UNMEASURED, H.SAMPLE_K),
                         (1500, 0.5, 0.7, 2000, 3, 4))
        self.assertEqual((H.DUAL_COVER_PCT, H.DUAL_SAMPLE_K), (90, 4))

    def test_witness_windows_format_and_cap(self):
        self.assertEqual(H.witness_windows({3: (5000, 9000)}, [3]), "3:2000-12000")
        self.assertEqual(H.witness_windows({1: (1000, 400000)}, [1]), "1:0-120000")
        self.assertEqual(H.witness_windows({2: (500, None)}, [2]), "2:0-23500")


if __name__ == "__main__":
    unittest.main()
