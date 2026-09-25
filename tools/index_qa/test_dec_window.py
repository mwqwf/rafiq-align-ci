#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""عقدُ النافذة الحاسمة (‏D): لا تُبنى حيث لا صوتَ قبل الحدّ، ولا يُبرَّأ بغيابها.

‏وقع 2026-09-25 على إحصاء `a_alhazmi@6e289031`: 87:1 تبدأ عند 0م.ث فبُنيت نافذةٌ
‏0→0 فأخفق `np.interp` («array of sample points is empty») وردّ `census_gate`
‏الإحصاءَ بنافذةٍ «تعذّر تفريغُها» لا صوتَ فيها أصلاً.

‏⛔ النصوصُ هنا كلماتٌ عربيةٌ اصطناعية لا نصٌّ قرآني — الحكمُ يقابل هياكلَ حروفٍ فحسب.
"""
from __future__ import annotations

import gzip
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent))
import run as R  # noqa: E402

REF = "كتب الطالب درسه في دفتر جديد"
PREV = "قرأ المعلم كتابه على الطلاب"
MID = "في دفتر جديد"            # تفريغٌ يبدأ من وسط الآية ⇒ اشتباهُ سقوط المطلع


class DecWindowTest(unittest.TestCase):
    def test_zero_start_builds_no_window(self):
        self.assertIsNone(R.dec_window(0))

    def test_short_positive_start_builds_no_window(self):
        # ‏دون MIN_DEC_MS لا يُسمع شاهدُ كلمة — فلا نافذةَ إلا مبرِّئة، فلا تُبنى
        self.assertIsNone(R.dec_window(1))
        self.assertIsNone(R.dec_window(R.MIN_DEC_MS - 1))

    def test_minimum_window_is_built_exactly(self):
        self.assertEqual(R.dec_window(R.MIN_DEC_MS), (0, R.MIN_DEC_MS))

    def test_normal_start_keeps_the_old_window(self):
        for st in (1000, R.DEC_MS, 10000, 123456):
            self.assertEqual(R.dec_window(st), (max(0, st - R.DEC_MS), st))

    def test_min_is_below_the_decisive_span(self):
        # ‏الحدّ الأدنى لا يجوز أن يأكل النوافذ العاديّة
        self.assertLess(R.MIN_DEC_MS, R.DEC_MS)


class JudgeNoPreTest(unittest.TestCase):
    def test_silent_decisive_window_still_acquits_when_it_existed(self):
        # ‏السلوكُ القديم باقٍ: نافذةٌ سُمعت فكانت صمتاً ⇒ إنذارٌ أول كاذب
        v, kind, _ = R.judge(REF, PREV, MID, "", MID)
        self.assertEqual((v, kind), ("بريء", "بريء"))

    def test_missing_decisive_window_never_acquits(self):
        v, kind, why = R.judge(REF, PREV, MID, "", MID, no_pre=True)
        self.assertEqual(v, "LATE_START")
        self.assertEqual(kind, "جسيم")          # سقطت كلمتان كاملتان
        self.assertIn("لا صوتَ قبل الحدّ", why)

    def test_missing_window_partial_opening_is_minor(self):
        # ‏سقوطُ الكلمة الأولى كاملةً ⇒ جسيم؛ وبعضِها فقط ⇒ طفيف — كنظيره تماماً
        v, kind, _ = R.judge(REF, PREV, "الطالب درسه في دفتر", "", "", no_pre=True)
        self.assertEqual(v, "LATE_START")
        self.assertEqual(kind, "جسيم")
        v, kind, _ = R.judge("استكتب الطالب درسه في دفتر", PREV, "كتب الطالب درسه في دفتر",
                             "", "", no_pre=True)
        self.assertEqual((v, kind), ("LATE_START", "طفيف"))

    def test_no_pre_does_not_touch_forward_verdicts(self):
        # ‏F مطابقٌ للمطلع ⇒ بريءٌ كما كان؛ وF فارغ ⇒ غير حاسم كما كان
        self.assertEqual(R.judge(REF, PREV, REF, "", REF, no_pre=True)[:2], ("بريء", "بريء"))
        self.assertEqual(R.judge(REF, PREV, "", "", "", no_pre=True)[:2],
                         ("غير حاسم", "غير حاسم"))
        # ‏وتسرّبُ السابقة يُحكم بـF وL وحدهما — لا يمسّه غيابُ D
        leak = "على الطلاب " + REF
        self.assertEqual(R.judge(REF, PREV, leak, "", leak, no_pre=True),
                         R.judge(REF, PREV, leak, "", leak))


class AuditJobsTest(unittest.TestCase):
    """‏بناءُ المهامّ في `audit`: لا نافذةَ D لـst=0 ولا للقصير، والعاديُّ كما كان."""

    def _audit(self, starts, heard):
        with tempfile.TemporaryDirectory() as td:
            txt = [f"سطر رقم {i} للاختبار" for i in range(6236)]
            txt[R.flat(87, 1)] = REF
            (Path(td) / "text_test.jz").write_bytes(
                gzip.compress(json.dumps(txt, ensure_ascii=False).encode("utf-8")))
            entries = [{"ayahId": f"87:{a}", "fileRef": "https://example.invalid/087.mp3",
                        "startMs": st, "endMs": st + 3000, "confBand": "HIGH"}
                       for a, st in starts]
            idx = {"reciterId": "t", "riwaya": "test", "entries": entries}
            seen = []

            def runner(jobs, _h=None, _t=None):
                seen.extend(jobs)
                res = {}
                for j in jobs:
                    p, aid = j["id"].split("|")
                    res[j["id"]] = {"text": heard.get((p, aid), ""), "ms": 0}
                return res, {}

            args = SimpleNamespace(struct_only=False, local=False, clusters=1, per_cluster=9,
                                   band=None, long_seg=False, refined=None, batch=24,
                                   host=None, threads=1, allow_unmarked=True, expect_sha=None)
            with mock.patch.object(R, "ASSETS", Path(td)), \
                 mock.patch.object(R, "fetch_index", return_value=(idx, "sha")), \
                 mock.patch.object(R, "structural", return_value=([], [], {})), \
                 mock.patch.object(R, "_src_mtime", return_value=None), \
                 mock.patch.object(R, "sample_boundaries",
                                   return_value=(1, [(87, e) for e in entries])), \
                 mock.patch.object(R, "remote_run", side_effect=runner):
                rep = R.audit("timings-staging/test/t.jz", args)
        return rep, {j["id"]: j for j in seen}

    def test_zero_and_short_starts_have_no_d_and_no_error(self):
        rep, jobs = self._audit([(1, 0), (2, 150), (3, 10000)], {})
        self.assertNotIn("D|87:1", jobs)
        self.assertNotIn("D|87:2", jobs)
        self.assertEqual((jobs["D|87:3"]["startMs"], jobs["D|87:3"]["endMs"]),
                         (10000 - R.DEC_MS, 10000))
        for aid in ("87:1", "87:2", "87:3"):
            self.assertIn(f"F|{aid}", jobs)
            self.assertIn(f"L|{aid}", jobs)
        self.assertEqual(rep["sample"]["errors"], 0)
        self.assertEqual(rep["sample"]["errorWindows"], {})
        rows = {r["aid"]: r for r in rep["sample"]["rows"]}
        self.assertTrue(rows["87:1"].get("noPreAudio"))
        self.assertTrue(rows["87:2"].get("noPreAudio"))
        self.assertNotIn("noPreAudio", rows["87:3"])

    def test_opening_lost_at_file_start_is_counted_not_acquitted(self):
        rep, _ = self._audit([(1, 0)], {("F", "87:1"): MID, ("L", "87:1"): MID})
        row = rep["sample"]["rows"][0]
        self.assertEqual((row["verdict"], row["kind"]), ("LATE_START", "جسيم"))
        self.assertEqual(rep["sample"]["severe"][0], 1)

    def test_rejudge_keeps_the_no_pre_flag(self):
        rep, _ = self._audit([(1, 0)], {("F", "87:1"): MID, ("L", "87:1"): MID})
        with tempfile.TemporaryDirectory() as td:
            txt = [f"سطر رقم {i} للاختبار" for i in range(6236)]
            txt[R.flat(87, 1)] = REF
            (Path(td) / "text_test.jz").write_bytes(
                gzip.compress(json.dumps(txt, ensure_ascii=False).encode("utf-8")))
            key = "timings-staging/test/t.jz"
            (Path(td) / (key.replace("/", "_") + ".json")).write_text(
                json.dumps(rep, ensure_ascii=False), encoding="utf-8")
            with mock.patch.object(R, "ASSETS", Path(td)), mock.patch.object(R, "STATE", Path(td)):
                out = R.rejudge(key, SimpleNamespace())
        row = out["sample"]["rows"][0]
        self.assertEqual((row["verdict"], row["kind"]), ("LATE_START", "جسيم"))


if __name__ == "__main__":
    unittest.main()
