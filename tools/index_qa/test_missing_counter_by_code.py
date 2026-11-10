#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""عدّادُ الغياب برمزه، وبابُ الصفّ للحجب بغير البتر (‏تشديدٌ بأمر القائد 2026-11-10).

    python -m unittest tools/index_qa/test_missing_counter_by_code.py

① `drop_surah` لا يعدّ في `byReason.source_truncated` إلا ما رمزُه SOURCE_TRUNCATED، وما سواه في عدّاد رمزه.
② لا يُعفي من عتبة `index_gate` ولا يُحسب في `certify_catalog.declared_absent` إلا البتر — ولو كان العدّادُ
   القديمُ في فهرسٍ منشورٍ قد ضمّ رموزاً أخرى (‏عيّنة kurdi المنشورة: drop_surah:4,55 برمز OTHER عُدّت 254 بتراً).
③ الحجبُ الجديدُ برمزٍ آخر لا يمرّ إلا بصفٍّ في OWNER_DROP_APPROVALS (‏`coded_drop_gate`)، وصفُّه يعفيه من العتبة.
"""
from __future__ import annotations

import gzip
import hashlib
import io
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import certify_catalog                                           # noqa: E402
import drop_surah                                                # noqa: E402
import promote                                                   # noqa: E402

KURDI = HERE / "testdata" / "kurdi.published.min.jz"
URL = "https://h.example/r/{s:03d}.mp3"


def _full():
    ents = [{"ayahId": f"{s}:{a}", "startMs": a * 1000, "endMs": a * 1000 + 900, "fileRef": URL.format(s=s),
             "confBand": "MED"}
            for s, n in enumerate(drop_surah.SURAH_AYAHS, start=1) for a in range(1, n + 1)]
    return {"riwaya": "hafs", "reciterId": "x", "ayahCounting": "KUFI", "refineVersion": "r", "entries": ents,
            "missing": {"count": 0, "byReason": {}, "ids": []}}


class _Bucket:
    def __init__(self, body):
        self.store = {"timings/hafs/x.jz": body}

    def get_object(self, Bucket, Key):                           # noqa: N803
        return {"Body": io.BytesIO(self.store[Key])}

    def put_object(self, Bucket, Key, Body, ContentType=None):   # noqa: N803
        self.store[Key] = Body

    def head_object(self, Bucket, Key):                          # noqa: N803
        return {"ContentLength": len(self.store[Key])}


def _drop(idx, surahs, code):
    body = gzip.compress(json.dumps(idx).encode(), 9, mtime=0)
    b = _Bucket(body)
    argv = ["drop_surah.py", "--key", "timings/hafs/x.jz", "--sha", hashlib.sha256(body).hexdigest()[:8],
            "--surah", surahs, "--reason", "سجلّ", "--reason-code", code, "--reason-user", "نصٌّ للمستخدم", "--yes"]
    with mock.patch.object(promote, "s3", return_value=(b, "bk")), mock.patch.object(sys, "argv", argv):
        drop_surah.main()
    k = [k for k in b.store if k.startswith("timings-staging/")][0]
    return json.loads(gzip.decompress(b.store[k]))


class CounterByCode(unittest.TestCase):
    def test_other_counted_under_other(self):
        out = _drop(_full(), "6", "OTHER")
        self.assertEqual({k: v for k, v in out["missing"]["byReason"].items() if v}, {"other": 165})
        self.assertEqual(promote.truncation_excused(out), 0)

    def test_truncated_counted_under_source_truncated(self):
        out = _drop(_full(), "6", "SOURCE_TRUNCATED")
        self.assertEqual({k: v for k, v in out["missing"]["byReason"].items() if v}, {"source_truncated": 165})
        self.assertEqual(promote.truncation_excused(out), 165)
        self.assertIsNone(promote.index_gate(out))

    def test_corrupt_not_excused(self):
        out = _drop(_full(), "6", "SOURCE_CORRUPT")
        self.assertEqual({k: v for k, v in out["missing"]["byReason"].items() if v}, {"source_corrupt": 165})
        self.assertIn("غيابٌ غير معلَّل", promote.index_gate(out))


class RowDoor(unittest.TestCase):
    def setUp(self):
        self.out = _drop(_full(), "6", "OTHER")

    def test_other_without_row_refused(self):
        self.assertIn("بلا صفّ موافقة", promote.coded_drop_gate(self.out, _full(), frozenset()))
        self.assertIn("بلا صفّ موافقة", promote.coded_drop_gate(self.out, None, frozenset({7})))
        self.assertIn("غيابٌ غير معلَّل", promote.index_gate(self.out))

    def test_other_with_row_accepted(self):
        self.assertIsNone(promote.coded_drop_gate(self.out, _full(), frozenset({6})))
        self.assertIsNone(promote.index_gate(self.out, coded_approved=frozenset({6})))

    def test_inherited_declaration_needs_no_new_row(self):
        # الإعلانُ نفسُه برمزه في المنشور لا يُطلب له صفٌّ ثانٍ؛ والجديدُ فوقه يُطلب.
        self.assertIsNone(promote.coded_drop_gate(self.out, self.out, frozenset()))
        more = _drop(self.out, "7", "OTHER")
        self.assertIn("[7]", promote.coded_drop_gate(more, self.out, frozenset()))
        self.assertIsNone(promote.coded_drop_gate(more, self.out, frozenset({7})))

    def test_truncated_needs_no_row(self):
        out = _drop(_full(), "6", "SOURCE_TRUNCATED")
        self.assertIsNone(promote.coded_drop_gate(out, _full(), frozenset()))

    def test_code_change_on_same_surah_needs_row(self):
        tr = json.loads(json.dumps(self.out))
        tr["transform"]["declarations"]["6"]["reasonCode"] = "SOURCE_CORRUPT"
        self.assertIn("[6]", promote.coded_drop_gate(tr, self.out, frozenset()))


class OldPublishedCounter(unittest.TestCase):
    """⚠️ تغيّرُ حكمٍ معلَن: kurdi المنشور (drop_surah:4,55 · OTHER) كان عدّادُه source_truncated = 254 فيُعفى
    كلُّه؛ والآن لا يُعفى منه شيء ⇒ index_gate يردّه (4.1% > 2%) ما لم يسمِّ صفٌّ سورتيه، وdeclared_absent = 0."""

    @classmethod
    def setUpClass(cls):
        cls.k = json.loads(gzip.decompress(KURDI.read_bytes()))

    def test_fixture_is_mixed_counter(self):
        self.assertEqual(self.k["transform"]["op"], "drop_surah:4,55")
        self.assertEqual(self.k["transform"]["reasonCode"], "OTHER")
        self.assertEqual(self.k["missing"]["byReason"]["source_truncated"], 254)

    def test_verdict_changes_and_is_stated(self):
        self.assertEqual(promote.truncation_excused(self.k), 0)
        self.assertIn("غيابٌ غير معلَّل 254/6236", promote.index_gate(self.k, inherited={}))
        self.assertIsNone(promote.index_gate(self.k, coded_approved=frozenset({4, 55}), inherited={}))
        self.assertEqual(certify_catalog.declared_absent(self.k, inherited={}), 0)


ROW = {"title": "موروث قبل #103", "date": "2026-11-10", "key": "timings/hafs/kurdi.jz", "sha8": "b7fe6778",
       "surahs": {"4": "OTHER", "55": "OTHER"}, "basis": ["أمر المالك 2026-10-12 للكردي والعكري"]}


class InheritedRow(unittest.TestCase):
    """البند ١ و٢ من حكم القائد: الصفُّ الموروث يُبقي حكمَ المنشور كما كان، ويحمي سورَه برموزها فقط."""

    @classmethod
    def setUpClass(cls):
        cls.k = json.loads(gzip.decompress(KURDI.read_bytes()))

    def _rows(self, row=ROW):
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump([row], f, ensure_ascii=False)
        return promote.load_inherited_declarations(f.name)

    def test_row_keeps_published_verdict(self):
        rows = self._rows()
        self.assertIsNone(promote.index_gate(self.k, inherited=rows))
        self.assertEqual(certify_catalog.declared_absent(self.k, inherited=rows), 254)

    def test_row_protects_only_its_surahs_and_codes(self):
        k2 = json.loads(json.dumps(self.k))
        k2["transform"]["reasonCode"] = "SOURCE_CORRUPT"                       # رمزٌ آخر للسورتين نفسيهما
        self.assertIn("غيابٌ غير معلَّل", promote.index_gate(k2, inherited=self._rows()))
        only4 = self._rows({**ROW, "surahs": {"4": "OTHER"}})                 # الصفُّ لا يسمّي س55
        self.assertEqual(promote.inherited_protected(self.k, only4), {4})
        self.assertEqual(certify_catalog.declared_absent(self.k, inherited=only4), 176)

    def test_new_drop_after_row_needs_new_row(self):
        more = _drop(self.k, "7", "OTHER")
        rows = self._rows()
        self.assertEqual(promote.inherited_protected(more, rows), {4, 55})
        self.assertIn("غيابٌ غير معلَّل", promote.index_gate(more, inherited=rows))
        self.assertIsNone(promote.index_gate(more, inherited=rows, coded_approved=frozenset({7})))

    def test_row_never_excuses_more_than_old_counter(self):
        k2 = json.loads(json.dumps(self.k))
        k2["missing"]["byReason"]["source_truncated"] = 100                    # العدّادُ القديم عدّ 100 فقط
        self.assertEqual(promote.gate_excused(k2, inherited=self._rows()), 100)

    def test_malformed_rows_ignored(self):
        for bad in ({**ROW, "title": "x"}, {**ROW, "sha8": "zz"}, {**ROW, "basis": []}, {**ROW, "surahs": {}},
                    {**ROW, "date": ""}, {**ROW, "key": "timings-staging/hafs/kurdi.1.jz"}):
            self.assertEqual(self._rows(bad), {})


if __name__ == "__main__":
    unittest.main()
