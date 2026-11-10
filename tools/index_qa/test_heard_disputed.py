#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""اختباراتُ «المرساة المتنازَع عليها» في `heard_gate.py` (‏قرار القائد 2026-11-10 · سندُه موافقةُ المالك 11-07).

الحالاتُ الحقيقيّة (‏3siri س10 · bc63afc4 · 010.mp3 = 51cf8d7d · خريطة float32 42756633030 · شاهد medium 42756381986):
  10:55 المرساةُ 1531244 على «وأسروا الندامة» (‏من 10:54) والمنشورُ 1546040 على «ألا إن لله» (‏1545744).
  10:50 المرساةُ 1383145 على «فلا يستأخرون ساعة» (‏من 10:49) والمنشورُ 1389500 على «قل أرأيتم» (‏1390005).
  10:70 المرساةُ 1948983 على «أتقولون على الله» (‏من 10:68) والمنشورُ 1963920 على «متاع في الدنيا» (‏1964143).
  10:4  المرساةُ 85557 على تكرار «إليه مرجعكم جميعاً» — نصُّ الآية نفسِها، فليس تنازعاً.
وكلُّ شرطٍ يُحوَّر وحده فيُردّ. والقبولُ يُختبر على زوجٍ **مركّبٍ معلَّم** من الشاهد الحقيقيّ (‏انظر `_pair`).

    python -m unittest tools/index_qa/test_heard_disputed.py
"""
from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import heard_gate as H                                           # noqa: E402
import pin_heard as P                                            # noqa: E402

TD = HERE / "testdata" / "3siri_disputed"
HMAP = json.loads((TD / "heard_s010_part.json").read_text(encoding="utf-8"))
WIT = json.loads((TD / "whisper_s010_42756381986.json").read_text(encoding="utf-8"))
ENTS = json.loads((TD / "entries_s010_bc63afc4.json").read_text(encoding="utf-8"))
CMAP = H.compact_map(HMAP)
SHA = HMAP["sha256"]


def ref(s, a):
    return H.disputed_ref_words("hafs", s, a)


def start(a):
    return [e for e in ENTS["entries"] if e["ayahId"] == f"10:{a}"][0]["startMs"]


def anchor(a):
    return CMAP["anchors"][str(a)][0][0]


def _pair(ayah="55"):
    """⚠️ زوجٌ مركّب: الشاهدُ الحقيقيّ 42756381986 لنافذة 10:55 وحدها، مع تعديلٍ واحدٍ معلَّم: ثقةُ «ألا» 0.50 ⇒ 0.90
    (‏هي على الحدّ في الحقيقيّ فتردّه). والثاني نسخةٌ منه بنموذج small مزاحةٌ +40م.ث. لاختبار القاعدة لا دليلاً."""
    a = copy.deepcopy(WIT)
    a["ayahs"] = {ayah: a["ayahs"][ayah]}
    for w in a["ayahs"][ayah]["words"]:
        if w["w"] in ("ألا",) and w["s"] == 1545744:
            w["p"] = 0.9
    b = copy.deepcopy(a)
    b["model"] = "small"
    for w in b["ayahs"][ayah]["words"]:
        w["s"] += 40
        w["e"] += 40
    return {"run-a": a, "run-b": b}


def _idx(claims=None):
    i = {"riwaya": "hafs", "reciterId": "3siri", "entries": copy.deepcopy(ENTS["entries"]), "audioSha256": [SHA]}
    if claims is not None:
        i["transform"] = {"op": "heard_pin:10", "disputedAnchors": {"10": claims}}
    return i


def _src(claims):
    """مصدرُ الشواهد كما يحمّله `disputed_sources` (‏هنا نسخةٌ مطابقةٌ لما في الادّعاء — لاختبار الشروط ١–٥)."""
    out = {}
    for c in (claims or {}).values():
        for r, w in (c.get("witnesses") or {}).items():
            out[str(r)] = H.disputed_src_rec(copy.deepcopy(w))
    return out


def _verdict(claims, n=None, src="same"):
    i = _idx(claims)
    rows = H.surah_rows({int(e["ayahId"].split(":")[1]): e["startMs"] for e in i["entries"]}, CMAP)
    why, ev = H.disputed_verdict(10, rows, CMAP, SHA, i, ref, n_ayahs=n,
                                 sources=_src(claims) if src == "same" else src)
    return why, ev, {r["ayah"]: r for r in rows}


class RealCases(unittest.TestCase):
    def test_rows_are_dev_before_the_rule(self):
        rows = {r["ayah"]: r for r in H.surah_rows({int(e["ayahId"].split(":")[1]): e["startMs"]
                                                    for e in ENTS["entries"]}, CMAP)}
        for a in (4, 50, 55, 70):
            self.assertEqual(rows[a]["status"], "dev", a)

    def test_real_4_is_its_own_repetition(self):
        why, d = H.disputed_one(WIT, 10, 4, start(4), anchor(4), 3, ref, CMAP, SHA)
        self.assertIsNone(d)
        self.assertIn("تكرار", why)

    def test_real_50_and_70_after_orthography_refused_by_other_conditions(self):
        # بعد التطبيع الإملائيّ يطابق المطلعُ نصَّ المصحف («أرأيتم» = «أرءيتم» · «متاع» = «متٰع»)، ويبقى الردُّ بشرطٍ آخر حرفاً:
        # 10:50 مطلعُ Whisper 1390005 والمنشور 1389500 (‏505 > 300م.ث) · 10:70 «على» عند المرساة ثقتُها 0.39.
        why, d = H.disputed_one(WIT, 10, 50, start(50), anchor(50), 49, ref, CMAP, SHA)
        self.assertIsNone(d)
        self.assertIn("بعيدٌ عن المنشور", why)
        why, d = H.disputed_one(WIT, 10, 70, start(70), anchor(70), 68, ref, CMAP, SHA)
        self.assertIsNone(d)
        self.assertIn("عند المرساة", why)

    def test_real_55_confidence_on_the_edge_refused(self):
        why, d = H.disputed_one(WIT, 10, 55, start(55), anchor(55), 54, ref, CMAP, SHA)
        self.assertIsNone(d)
        self.assertIn("ثقة", why)

    def test_real_single_witness_refused_in_verdict(self):
        why, ev, rows = _verdict({"55": {"otherAyah": 54, "witnesses": {"42756381986": WIT}}})
        self.assertIn("شاهدان", why)
        self.assertEqual(rows[55]["status"], "dev")


class Rule(unittest.TestCase):
    def test_pair_accepted_and_evidence(self):
        why, ev, rows = _verdict({"55": {"otherAyah": 54, "witnesses": _pair()}})
        self.assertIsNone(why)
        self.assertEqual(rows[55]["status"], "disputed")
        acc = ev["accepted"]["55"]
        self.assertEqual(acc["otherAyah"], 54)
        self.assertEqual(sorted(acc["witnesses"]), ["run-a", "run-b"])
        self.assertIn("الندامه", acc["witnesses"]["run-a"]["anchorText"])

    def test_judge_reports_disputed_and_still_judges_the_rest(self):
        cl = {"55": {"otherAyah": 54, "witnesses": _pair()}}
        j = H.judge(_idx(cl), None, "c" * 64, {10: CMAP}, disputed_src={"10": _src(cl)})
        self.assertIn("55", j["disputed"]["10"]["accepted"])
        self.assertNotIn("55,", j["surahs"]["10"]["reason"] + ",")    # ‏55 خرجت من المنحرفة؛ وغيرُها يبقى يردّ
        self.assertIn("50", j["surahs"]["10"]["reason"])

    def test_no_claim_is_unchanged(self):
        base = H.judge(_idx(), None, "c" * 64, {10: CMAP})
        self.assertNotIn("disputed", base)
        self.assertIn("55", base["surahs"]["10"]["reason"])

    def test_c1_one_witness(self):
        w = _pair()
        w.pop("run-b")
        self.assertIsNotNone(_verdict({"55": {"otherAyah": 54, "witnesses": w}})[0])

    def test_c1_other_audio_or_int8_or_other_file(self):
        for k, v in (("sha256", "b" * 64), ("computeType", "int8"), ("fileRef", "https://x/010.mp3"), ("model", "tiny")):
            w = _pair()
            w["run-b"][k] = v
            self.assertIsNotNone(_verdict({"55": {"otherAyah": 54, "witnesses": w}})[0], k)

    def test_c2_head_far_from_published(self):
        w = _pair()
        for x in w["run-b"]["ayahs"]["55"]["words"]:
            if x["s"] >= 1545744:
                x["s"] -= 700
                x["e"] -= 700
        why = _verdict({"55": {"otherAyah": 54, "witnesses": w}})[0]
        self.assertIn("بعيدٌ عن المنشور", why)

    def test_c2_head_low_confidence_or_clamped(self):
        w = _pair()
        w["run-b"]["ayahs"]["55"]["words"][-6]["p"] = 0.3          # «إن»
        self.assertIsNotNone(_verdict({"55": {"otherAyah": 54, "witnesses": w}})[0])
        w = _pair()
        w["run-b"]["ayahs"]["55"]["windowMs"][1] = 1549000          # «لله» تلتصق بنهاية النافذة
        self.assertIsNotNone(_verdict({"55": {"otherAyah": 54, "witnesses": w}})[0])

    def test_c3_wrong_other_ayah_named(self):
        why = _verdict({"55": {"otherAyah": 53, "witnesses": _pair()}})[0]
        self.assertIn("ليس من نصّ 10:53", why)

    def test_c3_same_ayah_named_or_low_conf_at_anchor(self):
        self.assertIsNotNone(_verdict({"55": {"otherAyah": 55, "witnesses": _pair()}})[0])
        w = _pair()
        for x in w["run-a"]["ayahs"]["55"]["words"]:
            if x["w"] == "الندامة":
                x["p"] = 0.2
        self.assertIsNotNone(_verdict({"55": {"otherAyah": 54, "witnesses": w}})[0])

    def test_c3_anchor_window_clamped(self):
        w = _pair()
        w["run-b"]["ayahs"]["55"]["windowMs"][0] = 1530784          # كلُّ ما يغطّي المرساة ملصوقٌ ببدء النافذة
        self.assertIsNotNone(_verdict({"55": {"otherAyah": 54, "witnesses": w}})[0])

    def test_c4_over_ten_percent(self):
        why = _verdict({"55": {"otherAyah": 54, "witnesses": _pair()}}, n=9)[0]
        self.assertIn("10٪", why)
        self.assertIsNone(_verdict({"55": {"otherAyah": 54, "witnesses": _pair()}}, n=10)[0])

    def test_claim_on_non_dev_ayah_refused(self):
        why = _verdict({"6": {"otherAyah": 5, "witnesses": _pair()}})[0]
        self.assertIn("ليست منحرفة", why)

    def test_gate_error_recomputes_from_candidate(self):
        cl = {"55": {"otherAyah": 54, "witnesses": _pair()}}
        i = _idx(cl)
        rep = {"sha256": "c" * 64, "maps": {"10": CMAP}, "disputedSource": {"10": _src(cl)}}
        why = H.gate_error(i, None, "c" * 64, rep)
        self.assertNotIn("الآيات 4,5,14,26,50,51,53,55", why)
        self.assertNotIn("مصدر", why)
        rep.pop("disputedSource")                     # حكمٌ محفوظٌ بلا مصدرٍ محمَّل ⇒ المكتوبُ وحده لا يُصدَّق
        self.assertIn("لا مصدرَ محمَّلٌ", H.gate_error(i, None, "c" * 64, rep))


class Source(unittest.TestCase):
    """⛔ (‏قرار القائد 2026-11-10) الشاهدُ المكتوبُ في المرشّح لا يُصدَّق وحده: يُحمَّل من مخرَج تشغيلته ويطابقه حرفاً."""

    def _cl(self):
        return {"55": {"otherAyah": 54, "witnesses": _pair()}}

    def test_forged_witness_without_source_refused(self):
        cl = self._cl()
        for src in ({}, {"run-a": _src(cl)["run-a"]}, None):
            why, _ev, rows = _verdict(cl, src=src)
            self.assertIn("لا مصدرَ محمَّلٌ", why)
            self.assertEqual(rows[55]["status"], "dev")

    def test_one_word_changed_refused(self):
        cl = self._cl()
        src = _src(cl)
        cl["55"]["witnesses"]["run-b"]["ayahs"]["55"]["words"][0]["w"] += "ـ"     # كلمةٌ واحدةٌ عُدّلت في المكتوب
        why, _ev, rows = _verdict(cl, src=src)
        self.assertIn("يخالف مصدرَه", why)
        self.assertEqual(rows[55]["status"], "dev")

    def test_one_time_or_confidence_changed_refused(self):
        for k, d in (("s", 1), ("p", 0.01)):
            cl = self._cl()
            src = _src(cl)
            cl["55"]["witnesses"]["run-a"]["ayahs"]["55"]["words"][3][k] += d
            self.assertIn("يخالف مصدرَه", _verdict(cl, src=src)[0], k)

    def test_source_load_error_refused(self):
        cl = self._cl()
        src = _src(cl)
        src["run-b"] = {"error": "⛔ شاهدٌ مردود: التشغيلة 1 لم تنجح"}
        self.assertIn("تعذّر تحميلُه", _verdict(cl, src=src)[0])

    def test_judgment_uses_the_loaded_source(self):
        # المكتوبُ يطابق المصدرَ في حقول الدليل ⇒ يُحكم؛ وحقلٌ خارجها لا يدخل الحكم ولا المقارنة
        cl = self._cl()
        src = _src(cl)
        cl["55"]["witnesses"]["run-a"]["note"] = "x"
        self.assertIsNone(_verdict(cl, src=src)[0])

    def test_disputed_sources_loads_every_named_run(self):
        cl = self._cl()
        pair = _pair()
        calls = []

        def loader(r, s):
            calls.append((r, s))
            if r == "run-b":
                raise SystemExit("⛔ لا شاهدَ")
            return pair[r]
        got = H.disputed_sources(_idx(cl), loader)
        self.assertEqual(sorted(calls), [("run-a", 10), ("run-b", 10)])
        self.assertEqual(_canon_eq(got["10"]["run-a"], H.disputed_src_rec(pair["run-a"])), True)
        self.assertIn("لا شاهدَ", got["10"]["run-b"]["error"])
        self.assertEqual(H.disputed_sources(_idx()), {})

    def test_witness_run_must_be_a_successful_whisper_witness_run_on_main(self):
        ok = {"id": 42756381986, "path": ".github/workflows/whisper_witness.yml", "status": "completed",
              "conclusion": "success", "repository": {"full_name": P.REPO}, "head_repository": {"full_name": P.REPO},
              "head_branch": "main", "event": "workflow_dispatch"}
        self.assertIsNone(P.witness_run_error("42756381986", ok))
        for k, v in (("path", ".github/workflows/heard_gate.yml"), ("conclusion", "failure"), ("status", "in_progress"),
                     ("head_repository", {"full_name": "x/fork"}), ("head_branch", "wk"), ("event", "push"),
                     ("id", 1)):
            self.assertIsNotNone(P.witness_run_error("42756381986", dict(ok, **{k: v})), k)
        for bad in ("run-a", "../x", "", "1"):
            self.assertIsNotNone(P.witness_run_error(bad, ok), bad)


def _canon_eq(a, b):
    return json.dumps(a, sort_keys=True, ensure_ascii=False) == json.dumps(b, sort_keys=True, ensure_ascii=False)


class PinHeardWrites(unittest.TestCase):
    def test_disputed_claims_embeds_and_prechecks(self):
        rec = P.disputed_claims(_idx(), 10, HMAP, {55: 54}, "", wits=_pair())
        self.assertEqual(rec["10"]["55"]["otherAyah"], 54)
        self.assertEqual(sorted(rec["10"]["55"]["witnesses"]), ["run-a", "run-b"])
        with self.assertRaises(SystemExit):
            P.disputed_claims(_idx(), 10, HMAP, {55: 53}, "", wits=_pair())
        with self.assertRaises(SystemExit):
            P.disputed_claims(_idx(), 10, HMAP, {55: 54}, "1")             # تشغيلةٌ واحدة


class Orthography(unittest.TestCase):
    """التطبيعُ الإملائيّ الضيّق لهذا الباب وحده: ٰ ← ا · ء ← ا · ٱ ← ا، ولا حذف."""

    def test_equal_pairs(self):
        for a, b in (("أرأيتم", "أَرَءَيْتُمْ"), ("متاع", "مَتَٰعٌ"), ("الكتاب", "ٱلْكِتَٰبُ")):
            self.assertEqual(H.disputed_norm_words(a), H.disputed_norm_words(b), (a, b))

    def test_a_missing_real_alif_is_not_made(self):
        for a, b in (("قال", "قُلْ"), ("ملك", "مَٰلِكِ"), ("كتب", "ٱلْكِتَٰبُ"), ("كتب", "كتاب")):
            self.assertNotEqual(H.disputed_norm_words(a), H.disputed_norm_words(b), (a, b))

    def test_word_count_unchanged_on_the_mushaf(self):
        for s, a in ((10, 50), (10, 70), (10, 55), (9, 93), (2, 255), (1, 4)):
            self.assertEqual(len(H.disputed_ref_words("hafs", s, a)), len(P.ref_words_for("hafs", s, a)), (s, a))

    def test_hamza_alif_merges_only_when_made_by_the_three(self):
        # (‏#104) «ءا» = «آ»: ألفان متتاليتان تُدمجان إذا نتجت إحداهما عن التحويل؛ والألفُ الأصليّةُ المكرّرة لا تُمسّ
        self.assertEqual(H.disputed_norm_words("ءَايَٰت"), ["ايات"])
        self.assertEqual(H.disputed_norm_words("ءَايَٰتُ"), H.disputed_norm_words("آيات"))
        self.assertEqual(H.disputed_norm_words("ءَامَنُوا۟"), H.disputed_norm_words("آمنوا"))
        self.assertEqual(H.disputed_ref_words("hafs", 28, 2)[:3], H.disputed_norm_words("تلك آيات الكتاب"))
        self.assertEqual(H.disputed_norm_words("جاا"), ["جاا"])          # ألفان أصليّتان: لا دمج
        self.assertEqual(H.disputed_norm_words("أرأيتم"), ["ارايتم"])    # ألفٌ ناتجةٌ وحدها لا تُدمج بغير ألف

    def test_alif_madda_is_normalised_by_common_norm(self):
        sys.path.insert(0, str(P._REPO_ROOT / "tools" / "alignment"))
        from common import norm
        self.assertEqual(norm("آمنوا"), "امنوا")

    def test_merge_makes_no_missing_alif(self):
        for a, b in (("قال", "قُلْ"), ("مالك", "مَلِكِ"), ("كتب", "كتاب"), ("كتب", "كِتَٰبٌ")):
            self.assertNotEqual(H.disputed_norm_words(a), H.disputed_norm_words(b), (a, b))

    def test_mark_char_in_input_is_not_trusted(self):
        # الحارسُ ػ في نصٍّ داخلٍ لا يُصنع منه دمج (‏يُحذف قبل التعليم)
        self.assertEqual(H.disputed_norm_words("ا\u063bا"), ["اا"])

    def test_common_norm_untouched(self):
        self.assertEqual(P.ref_words_for("hafs", 10, 50)[:2], ["قل", "اريتم"])
        self.assertEqual(H.disputed_ref_words("hafs", 10, 50)[:2], ["قل", "ارايتم"])


if __name__ == "__main__":
    unittest.main()
