#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""اختباراتُ قاعدة «المرساة المزاحة داخل نصّ الآية نفسِها» في `heard_gate.py` (‏#107 · قرار القائد 2026-11-10).

الحالةُ الحقيقيّة (‏3siri س10 · الحيّ bc63afc4 · خريطة float32 الحقيقيّة 42756633030): 10:51 المنشورُ 1406900 ينتهي 1435020،
ومرساتُها في الخريطة [1409362، 1431497] جودة 0.632 (‏متأخّرةٌ 2462م.ث على «إذا ما وقع») فتُحكم «dev» والفهرسُ صواب.
وشاهدا Whisper الحقيقيّان لهذه الآية (‏مطلعُ «أثم» عند 1407500 و1407880) **لم يُحفظا في المستودع**، فالقبولُ يُختبر على
**زوجٍ مركّبٍ معلَّم** (‏`_pair`): مطلعُ «أثم إذا ما» عند المنشور + 100م.ث و+160م.ث بثقة 0.9. ويُسجَّل هنا صراحةً أنّ مطلعَيْ
الشاهدين الحقيقيّين (‏+600 و+980م.ث) **خارجُ 300م.ث** فيردّهما الشرطُ كما هو (‏`test_real_witness_heads_outside_300ms`).
كلُّ شرطٍ يُحوَّر وحده فيُردّ، وكلُّ اختبارٍ يفشل إن أُسقط شرطُه (‏انظر وصفَ الطلب).

    python -m unittest tools.index_qa.test_heard_owntext
"""
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import heard_gate as H                                           # noqa: E402
import pin_heard as P                                            # noqa: E402
import test_heard_disputed as T                                  # noqa: E402

A = 51
CMAP = T.CMAP
SHA = T.SHA
WIN = [1403900, 1438020]          # ‏النافذةُ = المنشورُ ± 3000م.ث


def ref(s, a):
    return H.disputed_ref_words("hafs", s, a)


def _wit(model="medium", head_delta=100, ayah=A, start=None, p=0.9, text=None):
    """⚠️ شاهدٌ مركّب: ستُّ كلماتٍ من مطلع الآية بثقة p، أُولاها عند (‏المنشور + head_delta)."""
    st = T.start(ayah) if start is None else start
    words = (text or ref(10, ayah))[:6]
    t0 = st + head_delta
    return {"surah": 10, "riwaya": "hafs", "fileRef": T.HMAP["fileRef"], "sha256": SHA, "model": model,
            "computeType": "float32",
            "ayahs": {str(ayah): {"windowMs": list(WIN),
                                  "words": [{"w": w, "s": t0 + i * 350, "e": t0 + i * 350 + 300, "p": p}
                                            for i, w in enumerate(words)]}}}


def _pair(**kw):
    return {"run-c": _wit("medium", 100, **kw), "run-d": _wit("small", 160, **kw)}


def _claims(wits=None, ayah=A):
    return {str(ayah): {"witnesses": wits or _pair()}}


def _idx(own=None, disputed=None, end_none=False):
    i = {"riwaya": "hafs", "reciterId": "3siri", "entries": copy.deepcopy(T.ENTS["entries"]), "audioSha256": [SHA]}
    tr = {"op": "heard_pin:10"}
    if own is not None:
        tr["ownTextAnchors"] = {"10": own}
    if disputed is not None:
        tr["disputedAnchors"] = {"10": disputed}
    i["transform"] = tr
    if end_none:
        for e in i["entries"]:
            if e["ayahId"] == f"10:{A}":
                e["endMs"] = None
    return i


def _src(*claim_sets):
    out = {}
    for cl in claim_sets:
        out.update(T._src(cl))
    return out


def _rows(idx, cmap=CMAP):
    return H.surah_rows({int(e["ayahId"].split(":")[1]): e["startMs"] for e in idx["entries"]}, cmap)


def _verdict(own, cmap=CMAP, n=None, src="same", already=0, end_none=False):
    i = _idx(own, end_none=end_none)
    rows = _rows(i, cmap)
    why, ev = H.own_text_verdict(10, rows, cmap, SHA, i, ref, n_ayahs=n,
                                 sources=_src(own) if src == "same" else src, already=already)
    return why, ev, {r["ayah"]: r for r in rows}


def _cmap_with(anchor51=None, extra=None):
    m = copy.deepcopy(CMAP)
    if anchor51 is not None:
        m["anchors"]["51"] = anchor51
    for k, v in (extra or {}).items():
        m["anchors"][str(k)] = v
    return m


class RealCase(unittest.TestCase):
    def test_real_51_is_dev_before_the_rule(self):
        row = {r["ayah"]: r for r in _rows(_idx())}[A]
        self.assertEqual(row["status"], "dev")
        self.assertEqual(row["devMs"], 1406900 - 1409362)

    def test_real_witness_heads_outside_300ms(self):
        # مطلعُ «أثم» الحقيقيّ عند 1407500 (‏medium) و1407880 (‏small) والمنشور 1406900: +600 و+980 > 300م.ث ⇒ يردّها الشرط حرفاً.
        wits = {"run-c": _wit("medium", 600), "run-d": _wit("small", 980)}
        why, _ev, rows = _verdict(_claims(wits))
        self.assertIn("بعيدٌ عن المنشور", why)
        self.assertEqual(rows[A]["status"], "dev")

    def test_issue_101_still_refuses_this_case(self):
        # #101 لا يُضعَف: ادّعاءُ «تنازع» على هذه الآية (‏المرساةُ لا تسمع آيةً أخرى) يُردّ كما كان.
        cl = {str(A): {"otherAyah": 50, "witnesses": _pair()}}
        i = _idx(None, disputed=cl)
        rows = _rows(i)
        why, _ev = H.disputed_verdict(10, rows, CMAP, SHA, i, ref, sources=_src(cl))
        self.assertIsNotNone(why)
        self.assertEqual({r["ayah"]: r for r in rows}[A]["status"], "dev")


class Accept(unittest.TestCase):
    def test_pair_accepted_with_evidence(self):
        why, ev, rows = _verdict(_claims())
        self.assertIsNone(why)
        self.assertEqual(rows[A]["status"], "owntext")
        acc = ev["accepted"][str(A)]
        self.assertEqual(ev["version"], "heard-owntext-1")
        self.assertEqual(acc["map"]["mapSpanMs"], [1409362, 1431497])
        self.assertEqual(acc["map"]["shiftMs"], 1409362 - 1406900)
        self.assertEqual(sorted(acc["witnesses"]), ["run-c", "run-d"])
        self.assertEqual(acc["witnesses"]["run-c"]["headMs"], 1406900 + 100)

    def test_judge_reports_ownText_and_still_judges_the_rest(self):
        cl = _claims()
        j = H.judge(_idx(cl), None, "c" * 64, {10: CMAP}, disputed_src={"10": _src(cl)})
        self.assertIn("51", j["ownText"]["10"]["accepted"])
        reason = j["surahs"]["10"]["reason"]
        self.assertNotIn("51,", reason + ",")
        self.assertIn("50", reason)                       # غيرُها من المنحرفة يبقى يردّ
        self.assertNotIn("disputed", j)                   # ولا يدخل في أيّ عتبةٍ أخرى ولا في دليل #101

    def test_no_claim_is_unchanged(self):
        base = H.judge(_idx(), None, "c" * 64, {10: CMAP})
        self.assertNotIn("ownText", base)
        self.assertIn("51", base["surahs"]["10"]["reason"])

    def test_distinct_status_name(self):
        why, ev, rows = _verdict(_claims())
        self.assertEqual(rows[A]["status"], "owntext")
        self.assertNotEqual(rows[A]["status"], "disputed")

    def test_head_exactly_300ms_accepted_301_refused(self):
        self.assertIsNone(_verdict(_claims({"run-c": _wit("medium", 300), "run-d": _wit("small", 160)}))[0])
        why = _verdict(_claims({"run-c": _wit("medium", 301), "run-d": _wit("small", 160)}))[0]
        self.assertIn("بعيدٌ عن المنشور", why)


class C1Witnesses(unittest.TestCase):
    """١) شاهدان من تشغيلتين، يُحمَّلان من المصدر ويطابقان المكتوبَ حرفاً، float32، بصمةٌ واحدة."""

    def test_one_witness_refused(self):
        w = _pair()
        w.pop("run-d")
        why, _ev, rows = _verdict(_claims(w))
        self.assertIn("شاهدان", why)
        self.assertEqual(rows[A]["status"], "dev")

    def test_other_audio_int8_other_file_other_model(self):
        for k, v in (("sha256", "b" * 64), ("computeType", "int8"), ("fileRef", "https://x/010.mp3"), ("model", "tiny")):
            w = _pair()
            w["run-d"][k] = v
            self.assertIsNotNone(_verdict(_claims(w))[0], k)

    def test_forged_witness_without_source_refused(self):
        for src in ({}, {"run-c": _src(_claims())["run-c"]}, None):
            why, _ev, rows = _verdict(_claims(), src=src)
            self.assertIn("لا مصدرَ محمَّلٌ", why)
            self.assertEqual(rows[A]["status"], "dev")

    def test_one_word_changed_vs_source_refused(self):
        cl = _claims()
        src = _src(cl)
        cl[str(A)]["witnesses"]["run-d"]["ayahs"][str(A)]["words"][0]["w"] += "ـ"
        why, _ev, rows = _verdict(cl, src=src)
        self.assertIn("يخالف مصدرَه", why)
        self.assertEqual(rows[A]["status"], "dev")

    def test_load_error_refused(self):
        cl = _claims()
        src = _src(cl)
        src["run-d"] = {"error": "⛔ شاهدٌ مردود: التشغيلة 1 لم تنجح"}
        self.assertIn("تعذّر تحميلُه", _verdict(cl, src=src)[0])

    def test_each_witness_is_judged_not_only_the_first(self):
        w = _pair()
        w["run-c"]["ayahs"][str(A)]["words"][0]["p"] = 0.3        # ‏الأولُ سيّئٌ والثاني سليم
        self.assertIn("run-c", _verdict(_claims(w))[0])
        w = _pair()
        w["run-d"]["ayahs"][str(A)]["words"][0]["p"] = 0.3        # ‏الأولُ سليمٌ والثاني سيّئ
        self.assertIn("run-d", _verdict(_claims(w))[0])

    def test_disputed_sources_loads_ownText_runs_too(self):
        cl = _claims()
        pair = _pair()
        calls = []

        def loader(r, s):
            calls.append((r, s))
            return pair[r]
        got = H.disputed_sources(_idx(cl), loader)
        self.assertEqual(sorted(calls), [("run-c", 10), ("run-d", 10)])
        self.assertEqual(sorted(got["10"]), ["run-c", "run-d"])
        self.assertEqual(H.disputed_sources(_idx()), {})

    def test_gate_error_recomputes_from_loaded_source(self):
        cl = _claims()
        i = _idx(cl)
        rep = {"sha256": "c" * 64, "maps": {"10": CMAP}, "disputedSource": {"10": _src(cl)}}
        why = H.gate_error(i, None, "c" * 64, rep)
        self.assertNotIn("الآيات 4,5,14,26,50,51", why)
        self.assertNotIn("مصدر", why)
        rep.pop("disputedSource")                      # بلا مصدرٍ محمَّل ⇒ المكتوبُ وحدَه لا يُصدَّق
        self.assertIn("لا مصدرَ محمَّلٌ", H.gate_error(i, None, "c" * 64, rep))


class C2Head(unittest.TestCase):
    """٢) كلُّ شاهدٍ يسمع مطلعَ الآية نفسِها ضمن 300م.ث من المنشور، بثقةٍ ودون التصاق."""

    def test_head_far_from_published(self):
        w = _pair()
        w["run-d"] = _wit("small", -700)
        self.assertIn("بعيدٌ عن المنشور", _verdict(_claims(w))[0])

    def test_head_low_confidence_or_clamped(self):
        w = _pair()
        w["run-d"]["ayahs"][str(A)]["words"][1]["p"] = 0.3
        self.assertIn("ثقة", _verdict(_claims(w))[0])
        w = _pair()
        w["run-d"]["ayahs"][str(A)]["windowMs"][0] = T.start(A) + 160      # ‏أُولى الكلمات ملصوقةٌ ببدء النافذة
        self.assertIn("ملصوقة", _verdict(_claims(w))[0])

    def test_head_is_not_the_ayah_text(self):
        w = _pair()
        w["run-d"] = _wit("small", 160, text=ref(10, 50))                   # ‏يسمع مطلعَ آيةٍ أخرى لا مطلعَ هذه
        self.assertIn("لا يُسمع مطلعُ الآية", _verdict(_claims(w))[0])


class C3Map(unittest.TestCase):
    """٣) المرساةُ المزاحةُ داخل مدى الآية نفسِها **من الخريطة** لا في آيةٍ أخرى."""

    def test_anchor_not_later_than_start(self):
        st = T.start(A)
        m = _cmap_with([[st - 3000, st - 500], 0.7, []])                    # ‏مرساةٌ **أبكرُ** من البدء (‏صنفُ #101) لا متأخّرة
        why, _ev, rows = _verdict(_claims(), cmap=m)
        self.assertEqual(rows[A]["status"], "dev")
        self.assertIn("ليست متأخّرةً", why)

    def test_anchor_span_leaves_the_published_window(self):
        m = _cmap_with([[1409362, 1436000], 0.632, []])                     # ‏النهايةُ بعد نهاية المنشور 1435020
        why, _ev, rows = _verdict(_claims(), cmap=m)
        self.assertEqual(rows[A]["status"], "dev")
        self.assertIn("يخرج من نافذة", why)

    def test_anchor_span_overlaps_another_ayah_in_the_map(self):
        m = _cmap_with(extra={52: [[1420000, 1425000], 0.8, []]})           # ‏آيةٌ أخرى تُغطّي الموضعَ نفسَه في الخريطة
        why, _ev, rows = _verdict(_claims(), cmap=m)
        self.assertEqual(rows[A]["status"], "dev")
        self.assertIn("يتقاطع", why)
        self.assertIn("52", why)

    def test_touching_neighbour_span_is_not_overlap(self):
        # ‏الحقيقيّة: 10:50 تنتهي 1409142 قبل بدء 51 (‏1409362) — لا تقاطع.
        self.assertIsNone(_verdict(_claims())[0])

    def test_no_published_end_refused(self):
        why, _ev, rows = _verdict(_claims(), end_none=True)
        self.assertEqual(rows[A]["status"], "dev")
        self.assertIsNotNone(why)

    def test_partial_map_refused_as_in_101(self):
        part = copy.deepcopy(T.HMAP)
        part[H.PARTIAL_KEY] = 1400000
        with self.assertRaises(ValueError):
            H.compact_map(part)
        with self.assertRaises(SystemExit):
            P.own_text_claims(_idx(), 10, part, [A], "", wits=_pair())


class C4SharedCap(unittest.TestCase):
    """٤) السقفُ 10٪ مشتركٌ مع #101."""

    def test_over_ten_percent_alone(self):
        why = _verdict(_claims(), n=9)[0]
        self.assertIn("10٪", why)
        self.assertIsNone(_verdict(_claims(), n=10)[0])

    def test_cap_is_shared_with_disputed(self):
        self.assertIsNone(_verdict(_claims(), n=10, already=0)[0])
        why = _verdict(_claims(), n=10, already=1)[0]                       # ‏1 متنازَع + 1 مزاحة = 2 > 10٪ من 10
        self.assertIn("10٪", why)
        self.assertIsNone(_verdict(_claims(), n=20, already=1)[0])

    def test_shared_cap_through_judge_with_both_rules(self):
        d_claims = {"55": {"otherAyah": 54, "witnesses": T._pair()}}
        o_claims = _claims()
        i = _idx(o_claims, disputed=d_claims)
        src = {"10": _src(d_claims, o_claims)}
        with mock.patch.object(P, "heard_gate_n_ayahs", return_value=19):    # ‏1 + 1 = 2 من 19 = 10.5٪
            j = H.judge(i, None, "c" * 64, {10: CMAP}, disputed_src=src)
        self.assertIn("55", j["disputed"]["10"]["accepted"])                 # ‏كلٌّ وحدَه ≤ 10٪ (‏5.3٪)
        self.assertIn("المتنازَعُ عليه (1)", j["surahs"]["10"]["reason"])
        with mock.patch.object(P, "heard_gate_n_ayahs", return_value=109):
            j = H.judge(i, None, "c" * 64, {10: CMAP}, disputed_src=src)
        self.assertEqual(sorted(j["ownText"]["10"]["accepted"]), ["51"])
        self.assertNotIn("المتنازَعُ عليه", j["surahs"]["10"]["reason"])


class C5Separate(unittest.TestCase):
    def test_claim_on_non_dev_ayah_refused(self):
        why = _verdict(_claims(ayah=6))[0]
        self.assertIn("ليست منحرفة", why)

    def test_ayah_claimed_by_both_rules_is_not_double_counted(self):
        # ‏آيةٌ قبلها #101 تصير «disputed» فلا تُدّعى بالقاعدة الثانية (‏ليست «dev»)؛ والمعكوسُ: المدّعى هنا لا يدخل #101.
        d_claims = {"55": {"otherAyah": 54, "witnesses": T._pair()}}
        o_claims = _claims(ayah=55)
        i = _idx(o_claims, disputed=d_claims)
        j = H.judge(i, None, "c" * 64, {10: CMAP}, disputed_src={"10": _src(d_claims, o_claims)})
        self.assertIn("ليست منحرفة", j["surahs"]["10"]["reason"])

    def test_evidence_written_under_its_own_name(self):
        self.assertEqual(H.OWNTEXT_KEY, "ownTextAnchors")
        self.assertEqual(H.OWNTEXT_VERSION, "heard-owntext-1")
        self.assertNotEqual(H.OWNTEXT_VERSION, H.DISPUTED_VERSION)


if __name__ == "__main__":
    unittest.main()
