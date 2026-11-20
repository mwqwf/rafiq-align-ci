#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""اختباراتُ «مطلع الحروف المقطّعة بلا خطّ أساسٍ منشور» (‏`baseline=none`) — سورةٌ غائبةٌ من الحيّ كلِّها.

الحالةُ: فهارسُ a_alshahhat وh_abudalal (‏س20) وkyat (‏س28) تُعلن السورةَ محجوبةً «قيد الإصلاح» (‏لا مداخلَ لها في الحيّ)،
فلا بدءَ منشورَ للآية الأولى يُقاس به تمديدُها فكان الحارسُ يردّ كلَّ مطلعِ حروفٍ مهما اكتمل دليلُه.

القاعدةُ **أشدُّ لا أخفّ** من مسار الخطّ الأساس (‏لا يُرخي شرطاً قائماً ولا يمسّ ما له بدءٌ منشور):
  ١) تُقبل فقط إن كانت السورةُ بلا أيّ مدخلٍ منشور (‏يُقاس من الحيّ لا من المكتوب) **وبادّعاءٍ صريحٍ** `baseline=none`؛
  ٢) كلُّ شاهدٍ يسمع كلمةً قبل مطلع الثانية — (‏في مسار الخطّ الأساس يكفي شاهدٌ واحدٌ فيُقصّ التمديدُ بالمنشور)؛
  ٣) الشاهدان يتّفقان على أبكر كلمةٍ ضمن W_AGREE_MS؛  ٤) مدّةُ الأولى بين OPENER_DUR_MIN_MS وOPENER_DUR_MAX_MS؛
  ٥) سورةٌ لها مدخلٌ منشورٌ تردّ ادّعاءَ «بلا خطّ أساس» (‏فلا يُتحايل بالادّعاء على السقف 3000م.ث).

⚠️ الشاهدان الحقيقيّان للكردي 40 لا يجتازان هذا الشرط (‏الثاني لم يسمع حرفاً قبل المطلع) — وهذا مقصود: يُردّان هنا ويمرّان بالخطّ الأساس.
والزوجُ المقبولُ أدناه **مركّبٌ معلَّم** (‏تعديلٌ واحد: كلمةُ حروفٍ مسموعةٌ في الشاهد الثاني عند 5000) لاختبار القاعدة لا دليلاً.

    python -m unittest tools/index_qa/test_opener_no_baseline.py
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
import test_heard_opener_letters as TG                           # noqa: E402
import test_pin_heard_opener_letters as TP                       # noqa: E402

RUN_A, RUN_B = TG.RUN_A, TG.RUN_B
PIN2 = 6684


def agreed_sources(srcs, b_start=5000):
    """⚠️ مركّب: كلمةُ حروفٍ مسموعةٌ في الشاهد الثاني («حاميم» عند b_start) ليتّفق مع الأول (5119)."""
    s = copy.deepcopy(srcs)
    s[RUN_B]["ayahs"]["1"]["words"].insert(0, {"w": "حاميم", "s": b_start, "e": b_start + 900, "p": 0.6})
    return s


def evidence(srcs, start, baseline="none", pub=None):
    """دليلٌ مكتوبٌ يطابق المحسوبَ من المصادر (‏يُركَّب هنا لحالاتٍ لا يقبلها الباني نفسُه)."""
    head2 = list(P.heard_gate.disputed_ref_words("hafs", 40, 2)[:P.W_K])
    got = {}
    for r in (RUN_A, RUN_B):
        d, why = P._opener_witness(srcs[r], head2, PIN2)
        assert d is not None, why
        got[r] = d
    ev = {"version": P.OPENER_VERSION, "publishedStartMs": pub, "startMs": start, "ayah2PinMs": PIN2,
          "maxExtendMs": None if pub is None else P.OPENER_MAX_EXTEND_MS, "witnesses": got}
    if baseline:
        ev["baseline"] = baseline
    return ev


def case(srcs=None, start=5000, baseline="none", pub_present=False, claim_pub=None, edit=None):
    """(مرشّح، منشور، خريطة، مصادر): السورةُ غائبةٌ من المنشور ما لم يُطلب `pub_present`."""
    srcs = agreed_sources(TG.D["sources"]) if srcs is None else srcs
    cidx, pidx, m, _ = TG.build()
    for e in cidx["entries"]:
        if e["ayahId"] == "40:1":
            e["startMs"], e["endMs"] = start, PIN2
    cidx["transform"]["openerLetters"] = {"40": evidence(srcs, start, baseline, claim_pub)}
    if not pub_present:
        pidx["entries"] = [e for e in pidx["entries"] if not e["ayahId"].startswith("40:")]
        # المقتطفُ فيه 40:54 غيرُ مقيسةٍ كانت معفاةً لأنّها مطابقةٌ للمنشور؛ وفي سورةٍ غائبةٍ كلُّ غير المقيس ممسوسٌ ويلزمه شاهدُه
        # (‏`--witness-run` الموجود) — فتُحذف من المقتطف ليبقى الاختبارُ على مطلع الحروف وحده.
        cidx["entries"] = [e for e in cidx["entries"] if e["ayahId"] != "40:54"]
    if edit:
        edit(cidx, pidx, m, srcs)
    return cidx, pidx, m, srcs


def judge(**kw):
    cidx, pidx, m, srcs = case(**kw)
    return H.judge(cidx, pidx, "c" * 64, {40: m}, dual={}, disputed_src={"40": srcs})


class Gate(unittest.TestCase):
    def test_absent_surah_with_agreeing_witnesses_accepted(self):
        j = judge()
        self.assertTrue(TG.accepted(j), j["reason"])
        ev = j["weak"]["40"]["openerLetters"]["1"]
        self.assertEqual((ev["startMs"], ev["ayah2StartMs"], ev["publishedStartMs"]), (5000, PIN2, None))

    def test_published_surah_rejects_the_no_baseline_claim(self):
        # ⛔ لا يُتحايل على سقف 3000م.ث بادّعاء «بلا خطّ أساس» والسورةُ لها مدخلٌ منشور
        j = judge(pub_present=True)
        TG.refused(self, j, "يُردّ الادّعاء")

    def test_absent_surah_without_the_claim_refused(self):
        j = judge(baseline=None)
        TG.refused(self, j, "لا بدءَ منشورَ")

    def test_absent_surah_claim_with_a_published_start_value_refused(self):
        j = judge(claim_pub=6854)
        TG.refused(self, j, "لا بدءَ منشورَ")

    def test_second_witness_silent_refused(self):
        # الشاهدان الحقيقيّان للكردي 40: الثاني لا يسمع حرفاً قبل المطلع ⇒ يُردّ بلا خطّ أساس
        real = copy.deepcopy(TG.D["sources"])
        j = judge(srcs=real, start=5119)
        TG.refused(self, j, "لم يسمع كلمةً قبل مطلع الثانية")

    def test_witnesses_disagree_beyond_agree_ms_refused(self):
        srcs = agreed_sources(TG.D["sources"], b_start=5119 - P.W_AGREE_MS - 1)
        j = judge(srcs=srcs, start=5119 - P.W_AGREE_MS - 1)
        TG.refused(self, j, "يختلفان في أبكر كلمة")

    def test_witnesses_at_exactly_agree_ms_accepted(self):
        srcs = agreed_sources(TG.D["sources"], b_start=5119 - P.W_AGREE_MS)
        j = judge(srcs=srcs, start=5119 - P.W_AGREE_MS)
        self.assertTrue(TG.accepted(j), j["reason"])

    def test_start_must_be_the_earliest_witnessed(self):
        TG.refused(self, judge(start=5200), "ليس أبكرَ بدءٍ مشهود")

    def test_duration_cap_still_applies(self):
        with mock.patch.object(H, "OPENER_DUR_MAX_MS", 1000):
            TG.refused(self, judge(), "مدّةُ الآية الأولى")

    def test_duration_floor_still_applies(self):
        with mock.patch.object(H, "OPENER_DUR_MIN_MS", 5000):
            TG.refused(self, judge(), "مدّةُ الآية الأولى")

    def test_basmala_check_still_applies(self):
        def inject(cidx, pidx, m, srcs):
            srcs[RUN_B]["ayahs"]["1"]["words"].insert(0, {"w": "الرحمن", "s": 4900, "e": 5400, "p": 0.9})
            cidx["transform"]["openerLetters"]["40"] = evidence(srcs, 5000)
        TG.refused(self, judge(edit=inject), "البسملة")

    def test_the_old_published_baseline_path_is_unchanged(self):
        j = TG.run()                                        # الخطُّ الأساس: الشاهدان الحقيقيّان كما قُبلا
        self.assertTrue(TG.accepted(j), j["reason"])
        self.assertEqual(j["weak"]["40"]["openerLetters"]["1"]["publishedStartMs"], 6854)

    def test_old_missing_published_start_still_refused_for_a_claim_without_none(self):
        cidx, pidx, m, srcs = TG.build()
        cs = H.by_surah(cidx["entries"])[40]
        rows = H.surah_rows({a: v[0] for a, v in cs.items()}, m)
        ok, why = H.opener_letters_verdict(40, 1, cs, {}, rows, m, TG.SHA, cidx, srcs, "hafs")
        self.assertFalse(ok)
        self.assertIn("منشورَ", why)


class Builder(unittest.TestCase):
    def _wits(self, srcs):
        return {r: srcs[r] for r in (RUN_A, RUN_B)}

    def test_builder_none_baseline_accepts_agreeing_pair_and_records_the_claim(self):
        srcs = agreed_sources(TG.D["sources"])
        st, ev = P.opener_letters_start(self._wits(srcs), 40, "hafs", TG.D["map"], TG.SHA, None, PIN2)
        self.assertEqual(st, 5000)
        self.assertEqual((ev["baseline"], ev["publishedStartMs"], ev["maxExtendMs"]), ("none", None, None))

    def test_builder_none_baseline_refuses_the_real_pair(self):
        with self.assertRaises(SystemExit) as cm:
            P.opener_letters_start(self._wits(TG.D["sources"]), 40, "hafs", TG.D["map"], TG.SHA, None, PIN2)
        self.assertIn("لم يسمع كلمةً", str(cm.exception))

    def test_builder_none_baseline_refuses_witnesses_that_disagree(self):
        srcs = agreed_sources(TG.D["sources"], b_start=5119 - P.W_AGREE_MS - 1)
        with self.assertRaises(SystemExit) as cm:
            P.opener_letters_start(self._wits(srcs), 40, "hafs", TG.D["map"], TG.SHA, None, PIN2)
        self.assertIn("يختلفان", str(cm.exception))
        srcs = agreed_sources(TG.D["sources"], b_start=5119 - P.W_AGREE_MS)         # الحدُّ نفسُه يُقبل
        self.assertEqual(P.opener_letters_start(self._wits(srcs), 40, "hafs", TG.D["map"], TG.SHA, None, PIN2)[0], 4819)

    def test_builder_with_a_baseline_is_byte_identical_to_before(self):
        st, ev = P.opener_letters_start(self._wits(TG.D["sources"]), 40, "hafs", TG.D["map"], TG.SHA, 6854, PIN2)
        self.assertEqual(st, 5119)
        self.assertNotIn("baseline", ev)
        self.assertEqual(ev["maxExtendMs"], P.OPENER_MAX_EXTEND_MS)

    def test_builder_duration_cap(self):
        srcs = agreed_sources(TG.D["sources"])
        with mock.patch.object(P.heard_gate, "OPENER_DUR_MAX_MS", 1000):
            with self.assertRaises(SystemExit) as cm:
                P.opener_letters_start(self._wits(srcs), 40, "hafs", TG.D["map"], TG.SHA, None, PIN2)
        self.assertIn("مدّتُه", str(cm.exception))

    def test_pin_ignores_the_stage_base_start_when_no_baseline(self):
        srcs = agreed_sources(TG.D["sources"])
        ev = {}
        out, report, ch = P.pin(TP._idx(TP.K40[0]), 40, TP.K40[1], {2: 6684}, opener_witnesses=self._wits(srcs),
                                opener_evidence=ev, opener_no_baseline=True)
        row = next(e for e in out["entries"] if e["ayahId"] == "40:1")
        self.assertEqual((row["startMs"], row["endMs"]), (5000, 6684))
        self.assertEqual(ev["baseline"], "none")
        self.assertTrue(any("بلا خطّ أساسٍ منشور" in r for r in report))


if __name__ == "__main__":
    unittest.main()
