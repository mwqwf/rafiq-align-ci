#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""اختباراتُ مسار «مطلع الحروف المقطّعة» في بوّابة السماع (‏`heard_gate.opener_letters_verdict` · قرار القائد 2026-11-10).

الحالةُ الحقيقيّة: الكردي س40 (‏المرشّح timings-staging/hafs/kurdi.cd85eecc.jz · التشغيلة 42807865400): حدُّ 40:1 «حم» بُني بنصّ
`opener-letters-1` (‏5119→6684، شاهدان medium float32: 42756948718 و42767019946) وWhisper لا يفرّغ الحروف فردّته البوّابةُ
«أوّلُ كلماتِ الآية لا يطابق تفريغَ النافذة». المقتطفُ في `testdata/heard_opener_letters_kurdi_s40.json` (‏المداخلُ والخريطةُ
والشاهدان كما حُمّلا من مصدرهما). وكلُّ شرطٍ يُحوَّر وحده فيُردّ، ويسقط اختبارٌ إن أُسقط شرطُه.

    python -m unittest tools.index_qa.test_heard_opener_letters
"""
from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import heard_gate as H                                           # noqa: E402
import pin_heard as P                                            # noqa: E402

D = json.loads((HERE / "testdata" / "heard_opener_letters_kurdi_s40.json").read_text(encoding="utf-8"))
RUN_A, RUN_B = "42756948718", "42767019946"
SHA = D["audioSha256"]
REFUSED = "مطلعُ الحروف 40:1 مردود"
EXPECTED_SURAHS = (2, 3, 7, 10, 11, 12, 13, 14, 15, 19, 20, 26, 27, 28, 29, 30, 31, 32, 36, 38,
                   40, 41, 42, 43, 44, 45, 46, 50, 68)


def _entry(e, a):
    return next(x for x in e if x["ayahId"] == f"40:{a}")


def build(cand=None, pub=None, transform=None, sources=None, cmap=None, with_claim=True, with_sources=True):
    """(مرشّح، منشور، حكم، مصادر، خريطة) من المقتطف الحقيقيّ، وكلُّ معامل دالّةٌ تحوّر نسخةً منه."""
    shas = [""] * 114
    shas[39] = SHA
    c_ent, p_ent = copy.deepcopy(D["candEntries"]), copy.deepcopy(D["pubEntries"])
    tr = {"op": "heard_pin:40"}
    if with_claim:
        tr["openerLetters"] = {"40": copy.deepcopy(D["transform"]["openerLetters"]["40"])}
    srcs = copy.deepcopy(D["sources"]) if with_sources else {}
    m = copy.deepcopy(D["map"])
    for fn, obj in ((cand, c_ent), (pub, p_ent)):
        if fn:
            fn(obj)
    if transform:
        transform(tr)
    if sources:
        sources(srcs)
    if cmap:
        cmap(m)
    cidx = {"riwaya": "hafs", "reciterId": "kurdi", "entries": c_ent, "audioSha256": shas, "transform": tr}
    pidx = {"riwaya": "hafs", "reciterId": "kurdi", "entries": p_ent, "audioSha256": shas}
    return cidx, pidx, m, srcs


def run(**kw):
    cidx, pidx, m, srcs = build(**kw)
    return H.judge(cidx, pidx, "c" * 64, {40: m}, dual={}, disputed_src={"40": srcs} if srcs else {})


def accepted(j):
    return j["ok"] and j["weak"]["40"].get("openerAccepted") == [1]


def refused(test, j, why=None):
    test.assertFalse(j["ok"], j["reason"])
    test.assertIn(REFUSED, j["reason"])
    if why:
        test.assertIn(why, j["reason"])


def words_of(srcs, run_id, ayah="1"):
    return srcs[run_id]["ayahs"][ayah]["words"]


class RealCandidate(unittest.TestCase):
    def test_passes(self):
        j = run()
        self.assertTrue(accepted(j), j["reason"])
        ev = j["weak"]["40"]["openerLetters"]["1"]
        self.assertEqual((ev["startMs"], ev["ayah2StartMs"], ev["durationMs"], ev["agreeMs"]), (5119, 6684, 1565, P.W_AGREE_MS))
        self.assertEqual(ev["runs"], [RUN_A, RUN_B])
        self.assertEqual(j["weak"]["40"]["missing"], [])

    def test_gate_error_recomputes_from_state(self):
        cidx, pidx, m, srcs = build()
        rep = {"sha256": "c" * 64, "maps": {"40": m}, "disputedSource": {"40": srcs}, "ok": False, "reason": "مكتوبٌ كاذب"}
        self.assertIsNone(H.gate_error(cidx, pidx, "c" * 64, rep))      # الحكمُ يُعاد حسابُه لا يُقرأ
        rep["disputedSource"] = {}
        self.assertIn("مطلعُ الحروف", H.gate_error(cidx, pidx, "c" * 64, rep))

    def test_old_behaviour_without_claim_is_byte_identical(self):
        j = run(with_claim=False)
        self.assertFalse(j["ok"])
        self.assertNotIn("مطلعُ الحروف", j["reason"])
        self.assertNotIn("openerRefused", j["weak"]["40"])
        self.assertEqual(j["weak"]["40"]["missing"], [1])

    def test_weak_verdict_without_new_params_is_old(self):
        cidx, pidx, m, _s = build()
        cs, ps = H.by_surah(cidx["entries"])[40], H.by_surah(pidx["entries"])[40]
        rows = H.surah_rows({a: v[0] for a, v in cs.items()}, m)
        why, ev = H.weak_verdict(40, cs, ps, rows, m, None, SHA, "hafs")
        self.assertIn("الآيات 1", why)
        self.assertNotIn("openerAccepted", ev)


class ListOfSurahs(unittest.TestCase):
    def test_exactly_29_closed_named_list(self):
        self.assertIsInstance(H.OPENER_LETTER_SURAHS, frozenset)
        self.assertEqual(len(H.OPENER_LETTER_SURAHS), 29)
        self.assertEqual(tuple(sorted(H.OPENER_LETTER_SURAHS)), EXPECTED_SURAHS)

    def test_covers_everything_the_builder_derives(self):
        self.assertLessEqual(set(P.letters_opener_surahs("hafs")), set(H.OPENER_LETTER_SURAHS))

    def test_surah_outside_list_refused(self):
        with mock.patch.object(H, "OPENER_LETTER_SURAHS", frozenset(H.OPENER_LETTER_SURAHS - {40})):
            refused(self, run(), "قائمة سور الحروف")
        ok, why = H.opener_letters_verdict(39, 1, {}, {}, [], {}, SHA, {}, {}, "hafs")
        self.assertFalse(ok)
        self.assertIn("قائمة سور الحروف", why)

    def test_second_ayah_instead_of_first_refused(self):
        cidx, pidx, m, srcs = build()
        cs, ps = H.by_surah(cidx["entries"])[40], H.by_surah(pidx["entries"])[40]
        rows = H.surah_rows({a: v[0] for a, v in cs.items()}, m)
        self.assertTrue(H.opener_letters_verdict(40, 1, cs, ps, rows, m, SHA, cidx, srcs, "hafs")[0])
        ok, why = H.opener_letters_verdict(40, 2, cs, ps, rows, m, SHA, cidx, srcs, "hafs")
        self.assertFalse(ok)
        self.assertIn("الأولى وحدها", why)

    def test_unmeasured_second_ayah_is_not_excused_and_refuses_the_first(self):
        def weaken(m):
            m["anchors"]["2"][1] = 0.1
        j = run(cmap=weaken, cand=lambda e: _entry(e, 2).update(startMs=6684))
        refused(self, j, "غيرُ مقيس")
        self.assertIn(2, j["weak"]["40"]["missing"])

    def test_other_weak_ayah_still_requires_its_own_witness(self):
        def weaken(m):
            m["anchors"]["3"][1] = 0.1
        j = run(cmap=weaken, cand=lambda e: _entry(e, 3).update(startMs=14261),
                pub=lambda e: _entry(e, 3).update(startMs=14260))
        self.assertFalse(j["ok"])
        self.assertEqual(j["weak"]["40"]["openerAccepted"], [1])
        self.assertEqual(j["weak"]["40"]["missing"], [3])
        self.assertIn("الآيات 3", j["reason"])


class LettersOnlyShape(unittest.TestCase):
    """٧) الآيةُ الأولى في نصّ الرواية نفسِها حروفٌ مقطّعةٌ وحدها (‏مراجعة القائد 2026-11-10)."""

    def _direct(self, s, riwaya):
        ok, why = H.opener_letters_verdict(s, 1, {}, {}, [], {}, SHA, {}, {}, riwaya)
        return ok, why

    def test_hafs_with_speech_after_letters_refused(self):
        for s in (38, 68, 10, 11, 12, 13, 14, 15, 27, 50):
            ok, why = self._direct(s, "hafs")
            self.assertFalse(ok, s)
            self.assertIn("ليست حروفاً مقطّعةً وحدها", why, s)

    def test_hafs_40_passes_the_shape(self):
        ok, why = self._direct(40, "hafs")
        self.assertNotIn("ليست حروفاً", why)            # ‏يتجاوز الشكلَ ثمّ يقف عند غياب الادّعاء في هذا الاستدعاء المجرَّد

    def test_judge_accepts_40_in_hafs(self):
        self.assertTrue(accepted(run()))

    def test_gate_list_is_the_builders_function(self):
        for s in sorted(H.OPENER_LETTER_SURAHS):
            ok, why = self._direct(s, "hafs")
            self.assertEqual("ليست حروفاً" in why, s not in P.letters_opener_surahs("hafs"), s)

    def test_exactly_the_ten_with_speech_and_42_are_excluded_in_hafs(self):
        self.assertEqual(sorted(H.OPENER_LETTER_SURAHS - set(P.letters_opener_surahs("hafs"))),
                         [10, 11, 12, 13, 14, 15, 27, 38, 42, 50, 68])

    def test_only_hafs_is_allowed(self):
        self.assertEqual(H.OPENER_RIWAYAT, frozenset({"hafs"}))

    def test_warsh_and_qalun_refused_even_for_2_1_and_40_1(self):
        # ‏فهارسُ ورش وقالون بعدٍّ كوفيٍّ موحَّد وصوتُ 2:1 عندهم يمتدّ بعد الحروف؛ والمسارُ لحفص وحده حتى يوجد نصٌّ مدنيّ.
        for riw in ("warsh", "qalun"):
            for s in (2, 40):
                ok, why = self._direct(s, riw)
                self.assertFalse(ok, (riw, s))
                self.assertIn("OPENER_RIWAYAT", why)

    def test_shape_function_alone_still_accepts_kufi_text_of_madani_riwayat(self):
        # ‏للدالّة المشتركة وحدها (‏لا للبوّابة): نصُّ ورش وقالون كوفيّ الفهرسة فالدالّة تقبل 2:1 — ولهذا شرطُ الرواية أعلاه.
        for riw in ("warsh", "qalun"):
            self.assertIn(2, P.letters_opener_surahs(riw))

    def test_warsh_candidate_refused_in_judge(self):
        cidx, pidx, m, srcs = build()
        cidx["riwaya"] = pidx["riwaya"] = "warsh"
        j = H.judge(cidx, pidx, "c" * 64, {40: m}, dual={}, disputed_src={"40": srcs})
        refused(self, j, "OPENER_RIWAYAT")

    def test_riwaya_is_passed_to_the_builders_function(self):
        with mock.patch.object(H, "OPENER_RIWAYAT", frozenset({"hafs", "warsh"})):
            with mock.patch.object(P, "letters_opener_surahs", return_value=[2]) as m:
                self._direct(2, "warsh")
            m.assert_called_once_with("warsh")

    def test_missing_riwaya_defaults_to_hafs(self):
        ok, why = self._direct(2, None)
        self.assertNotIn("OPENER_RIWAYAT", why)

    def test_surah_outside_builders_list_refused(self):
        with mock.patch.object(P, "letters_opener_surahs", return_value=[3]):
            ok, why = self._direct(2, "hafs")
        self.assertFalse(ok)
        self.assertIn("ليست حروفاً مقطّعةً وحدها", why)
        with mock.patch.object(P, "letters_opener_surahs", side_effect=SystemExit("x")):
            self.assertFalse(self._direct(2, "hafs")[0])


class BasmalaBoundary(unittest.TestCase):
    """٨) بدءُ الآية الأولى لا يقع داخل البسملة المسموعة."""

    def _garbled_basmala(self):
        head2 = H.disputed_ref_words("hafs", 40, 2)[:3]

        def src(s):
            ws = words_of(s, RUN_A)
            pre = [{"w": "بسم", "s": 3000, "e": 3400, "p": 0.9}, {"w": "الله", "s": 3400, "e": 3900, "p": 0.9},
                   {"w": "الرحمن", "s": 3900, "e": 4700, "p": 0.9}, {"w": "الرحم", "s": 4800, "e": 5100, "p": 0.6}]
            s[RUN_A]["ayahs"]["1"]["words"] = pre + ws
        cidx, _p, _m, srcs = build(sources=src)
        d, why = P._opener_witness(srcs[RUN_A], head2, 6684)
        self.assertIsNone(why)
        self.assertEqual(d["earliestMs"], 4800)           # ‏الباني وحدَه يبدأ من «الرحم» داخل البسملة

        def tr(t):
            t["openerLetters"]["40"]["witnesses"][RUN_A] = d
            t["openerLetters"]["40"]["startMs"] = 4800
        return src, tr

    def test_garbled_basmala_word_refused(self):
        src, tr = self._garbled_basmala()
        refused(self, run(sources=src, transform=tr, cand=lambda e: _entry(e, 1).update(startMs=4800)), "داخل البسملة")

    def test_real_candidate_has_no_basmala_word_after_start(self):
        _c, _p, _m, srcs = build()
        for r in (RUN_A, RUN_B):
            self.assertIsNone(H._basmala_inside(srcs[r], 5119, 6684))

    def test_basmala_ending_before_start_is_fine(self):
        src = {"ayahs": {"1": {"words": [{"w": "الرحيم", "s": 4000, "e": 5000, "p": 0.9}]}}}
        self.assertIsNone(H._basmala_inside(src, 5119, 6684))
        self.assertIsNotNone(H._basmala_inside(src, 4500, 6684))


class DirectCalls(unittest.TestCase):
    def _args(self, **kw):
        cidx, pidx, m, srcs = build(**kw)
        cs, ps = H.by_surah(cidx["entries"])[40], H.by_surah(pidx["entries"])[40]
        return cs, ps, H.surah_rows({a: v[0] for a, v in cs.items()}, m), m, cidx, srcs

    def test_no_claim_refused_directly(self):
        cs, ps, rows, m, cidx, srcs = self._args(with_claim=False)
        ok, why = H.opener_letters_verdict(40, 1, cs, ps, rows, m, SHA, cidx, srcs, "hafs")
        self.assertFalse(ok)
        self.assertIn("لا transform.openerLetters", why)

    def test_missing_second_ayah_refused_directly(self):
        cs, ps, rows, m, cidx, srcs = self._args()
        ok, why = H.opener_letters_verdict(40, 1, {1: cs[1]}, ps, rows, m, SHA, cidx, srcs, "hafs")
        self.assertFalse(ok)
        self.assertIn("غيرُ حاضرتين", why)

    def test_claim_ignored_when_first_ayah_is_not_weak(self):
        # ‏الأولى مقيسةٌ جيّداً (‏جودة 0.9 عند بدئها) فليست ضعيفةً؛ وتبقى الثالثةُ الضعيفةُ وحدها مطلوبةَ الشاهد، ولا يُسجَّل دليلُ مطلعٍ
        def good(m):
            m["anchors"]["1"] = [[5119, 6684], 0.9, []]
            m["anchors"]["3"][1] = 0.1
        j = run(cmap=good, cand=lambda e: _entry(e, 3).update(startMs=14261),
                pub=lambda e: _entry(e, 3).update(startMs=14260))
        self.assertEqual(j["weak"]["40"]["weak"], [3])
        self.assertNotIn("openerAccepted", j["weak"]["40"])
        self.assertNotIn("openerLetters", j["weak"]["40"])


class Witnesses(unittest.TestCase):
    def test_no_sources_loaded(self):
        refused(self, run(with_sources=False), "لم يُحمَّل")

    def test_source_load_error(self):
        refused(self, run(sources=lambda s: s.__setitem__(RUN_A, {"error": "boom"})), "لم يُحمَّل")

    def test_single_witness_refused(self):
        def one(tr):
            del tr["openerLetters"]["40"]["witnesses"][RUN_B]
        refused(self, run(transform=one), "شاهدان")

    def test_same_run_twice_refused(self):
        def dup(tr):
            w = tr["openerLetters"]["40"]["witnesses"]
            w["0" + RUN_A] = copy.deepcopy(w[RUN_A])
            del w[RUN_B]

        def src(s):
            s["0" + RUN_A] = copy.deepcopy(s[RUN_A])
            del s[RUN_B]
        refused(self, run(transform=dup, sources=src), "المعرّف نفسه")

    def test_non_numeric_run_id_refused(self):
        def bad(tr):
            w = tr["openerLetters"]["40"]["witnesses"]
            w["abc"] = w.pop(RUN_B)
        refused(self, run(transform=bad), "ليس رقماً")

    def test_witnesses_disagree_on_second_ayah_refused(self):
        def shift(s):
            for w in words_of(s, RUN_B):
                w["s"] += 350
                w["e"] += 350
        refused(self, run(sources=shift), "بعيدٌ عن التثبيت")

    def test_audio_fingerprint_mismatch_refused(self):
        refused(self, run(sources=lambda s: s[RUN_B].update(sha256="0" * 64)), "بصمةُ صوت")

    def test_not_float32_refused(self):
        refused(self, run(sources=lambda s: s[RUN_A].update(computeType="int8")), "float32")

    def test_second_ayah_without_witness_refused(self):
        def cut(s):
            s[RUN_A]["ayahs"]["1"]["words"] = words_of(s, RUN_A)[:2]
        refused(self, run(sources=cut), "بلا شاهد في موضعها")

    def test_low_confidence_second_ayah_refused(self):
        def low(s):
            for w in words_of(s, RUN_B)[1:4]:
                w["p"] = 0.3
        refused(self, run(sources=low), "ثقةُ")

    def test_written_evidence_must_match_loaded_source(self):
        def tamper(tr):
            tr["openerLetters"]["40"]["witnesses"][RUN_A]["minP"] = 0.99
        refused(self, run(transform=tamper), "لا يطابق المحسوبَ")


class Geometry(unittest.TestCase):
    def test_no_claim_for_surah(self):
        j = run(with_claim=False)
        self.assertNotIn("openerRefused", j["weak"]["40"])

    def test_claim_version_mismatch(self):
        refused(self, run(transform=lambda t: t["openerLetters"]["40"].update(version="opener-letters-0")), "نسخةُ الدليل")

    def test_start_must_be_earliest_heard(self):
        def early(e):
            _entry(e, 1)["startMs"] = 4800
        refused(self, run(cand=early, transform=lambda t: t["openerLetters"]["40"].update(startMs=4800)), "أبكرَ بدءٍ")

        def late(e):
            _entry(e, 1)["startMs"] = 6000
        refused(self, run(cand=late, transform=lambda t: t["openerLetters"]["40"].update(startMs=6000)), "أبكرَ بدءٍ")

    def test_extension_beyond_cap_refused(self):
        refused(self, run(pub=lambda e: _entry(e, 1).update(startMs=9000, endMs=9200),
                          transform=lambda t: t["openerLetters"]["40"].update(publishedStartMs=9000)), "تمديدُ")

    def test_start_before_file_refused(self):
        def neg(e):
            _entry(e, 1)["startMs"] = -5

        def src(s):                                   # ‏لا كلمةَ مسموعةً قبل المطلع فتبقى أبكرَ نقطةٍ بدؤها المنشور
            for r in (RUN_A, RUN_B):
                s[r]["ayahs"]["1"]["words"] = [w for w in words_of(s, r) if w["w"] != "حميم"]

        def tr(t):
            t["openerLetters"]["40"]["witnesses"][RUN_A].update(lettersWords=[], earliestMs=None)
            t["openerLetters"]["40"].update(startMs=-5, publishedStartMs=-5)
        refused(self, run(cand=neg, pub=lambda e: _entry(e, 1).update(startMs=-5), sources=src, transform=tr), "قبل بدء الملفّ")

    def test_first_ayah_end_must_be_second_start(self):
        refused(self, run(cand=lambda e: _entry(e, 1).update(endMs=6600)), "ليست بدءَ الثانية")

    def test_two_files_refused(self):
        refused(self, run(cand=lambda e: _entry(e, 1).update(fileRef="https://x/other.mp3")), "ملفّين")

    def test_duration_below_min_refused(self):
        def src(s):                                   # ‏بلا كلمةٍ مسموعةٍ قبل المطلع: البدءُ هو المنشور 6000 ⇒ مدّةٌ 684م.ث
            for r in (RUN_A, RUN_B):
                s[r]["ayahs"]["1"]["words"] = [w for w in words_of(s, r) if w["w"] != "حميم"]

        def tr(t):
            t["openerLetters"]["40"]["witnesses"][RUN_A].update(lettersWords=[], earliestMs=None)
            t["openerLetters"]["40"].update(startMs=6000, publishedStartMs=6000)
        refused(self, run(cand=lambda e: _entry(e, 1).update(startMs=6000),
                          pub=lambda e: _entry(e, 1).update(startMs=6000, endMs=6100), sources=src, transform=tr), "مدّةُ الآية الأولى")

    def test_duration_above_max_refused(self):
        with mock.patch.object(H, "OPENER_DUR_MAX_MS", 1500):
            refused(self, run(), "مدّةُ الآية الأولى")

    def test_duration_bounds_are_the_documented_constants(self):
        self.assertEqual((H.OPENER_DUR_MIN_MS, H.OPENER_DUR_MAX_MS), (1000, 8000))

    def test_written_start_pin_and_published_must_match(self):
        for k, v in (("startMs", 5000), ("ayah2PinMs", 6000), ("publishedStartMs", 6000)):
            refused(self, run(transform=lambda t, k=k, v=v: t["openerLetters"]["40"].update({k: v})), "يخالف المحسوب")

    def test_missing_published_start_refused(self):
        cidx, pidx, m, srcs = build()
        cs = H.by_surah(cidx["entries"])[40]
        rows = H.surah_rows({a: v[0] for a, v in cs.items()}, m)
        ok, why = H.opener_letters_verdict(40, 1, cs, {}, rows, m, SHA, cidx, srcs, "hafs")
        self.assertFalse(ok)
        self.assertIn("منشورَ", why)


class Sources(unittest.TestCase):
    def test_disputed_sources_loads_opener_runs(self):
        cidx, _p, _m, _s = build()
        seen = []

        def loader(r, s):
            seen.append((r, s))
            return {"surah": s}
        out = H.disputed_sources(cidx, loader=loader)
        self.assertEqual(sorted(seen), [(RUN_A, 40), (RUN_B, 40)])
        self.assertEqual(sorted(out["40"]), [RUN_A, RUN_B])

    def test_disputed_sources_unchanged_without_claim(self):
        cidx, _p, _m, _s = build(with_claim=False)
        self.assertEqual(H.disputed_sources(cidx, loader=lambda r, s: self.fail("لا تحميل")), {})


if __name__ == "__main__":
    unittest.main()
