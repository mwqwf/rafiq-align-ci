#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""إسقاطُ سورةٍ لا يمحو إعلانَ ذيلٍ مبتورٍ لسورةٍ أخرى (fixV · 2026-10-05 · akri_qalun س4 وس24).

    python -m unittest tools/index_qa/test_drop_surah_carry_tail.py

يُشغَّل `drop_surah.main` على دلوٍ في الذاكرة: الأصلُ يُعلن ذيلَ س24 (بادئة 1..30)، ثمّ تُسقط س4.
⛔ بدون الحمل يخرج فهرسٌ بلا `truncatedTail` فيردّه `promote.declared_truncated_tail` (‏الاختبارُ الأوّل).
"""
from __future__ import annotations

import gzip
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import drop_surah                                                # noqa: E402
import promote                                                   # noqa: E402

URL = "https://h.example/r/{s:03d}.mp3"
N = 30


def _parent(op="declare_gap:24"):
    ents, ids = [], []
    for s, n in enumerate(drop_surah.SURAH_AYAHS, start=1):
        for a in range(1, n + 1):
            if s == 24 and a > N:
                ids.append(f"24:{a}")
                continue
            ents.append({"ayahId": f"{s}:{a}", "startMs": a * 1000, "endMs": a * 1000 + 1000,
                         "fileRef": URL.format(s=s), "confBand": "MED"})
    return {"riwaya": "qalun", "reciterId": "x", "ayahCounting": "KUFI", "refineVersion": "r",
            "entries": ents,
            "missing": {"count": len(ids), "byReason": {"source_truncated": len(ids)}, "ids": ids},
            "transform": {"op": op, "reasonCode": "SOURCE_TRUNCATED", "reasonUser": "النور ناقصة.",
                          "truncatedTail": {"24": {"published": N, "absentFrom": N + 1, "absentTo": 64,
                                                   "reason": "source_truncated"}}}}


class _Bucket:
    def __init__(self, obj):
        self.store = {"timings/qalun/x.jz": gzip.compress(json.dumps(obj).encode())}

    def get_object(self, Bucket, Key):                           # noqa: N803
        import io
        return {"Body": io.BytesIO(self.store[Key])}

    def put_object(self, Bucket, Key, Body, ContentType=None):   # noqa: N803
        self.store[Key] = Body

    def head_object(self, Bucket, Key):                          # noqa: N803
        return {"ContentLength": len(self.store[Key])}


def _drop(parent, *extra):
    import hashlib
    b = _Bucket(parent)
    sha = hashlib.sha256(b.store["timings/qalun/x.jz"]).hexdigest()[:8]
    argv = ["drop_surah.py", "--key", "timings/qalun/x.jz", "--sha", sha, "--surah", "4",
            "--reason", "4:140 غير متلوّة في الملفّ", "--yes", *extra]
    with mock.patch.object(promote, "s3", return_value=(b, "bk")), mock.patch.object(sys, "argv", argv):
        drop_surah.main()
    keys = [k for k in b.store if k.startswith("timings-staging/")]
    return json.loads(gzip.decompress(b.store[keys[0]]))


OK = ("--reason-code", "SOURCE_TRUNCATED", "--reason-user", "تسجيلُ النساء تنقصه آية، والنور ينقطع.")


class CarryTail(unittest.TestCase):
    def test_drop_keeps_declared_tail_of_other_surah(self):
        out = _drop(_parent(), *OK)
        ok, why = promote.declared_truncated_tail(out, 24)
        self.assertTrue(ok, why)
        self.assertEqual(out["transform"]["op"], "drop_surah:4|declare_gap:24")
        self.assertIsNone(promote.index_gate(out))
        self.assertFalse(any(e["ayahId"].startswith("4:") for e in out["entries"]))

    def test_refuses_when_drop_would_erase_user_declaration(self):
        with self.assertRaises(SystemExit):
            _drop(_parent())                                      # بلا SOURCE_TRUNCATED/reasonUser
        with self.assertRaises(SystemExit):
            _drop(_parent(), "--reason-code", "OTHER", "--reason-user", "x")

    def test_undeclared_tail_not_carried(self):
        out = _drop(_parent(op="ctc_quran_surah_splice:24"), *OK)
        self.assertNotIn("truncatedTail", out["transform"])
        self.assertEqual(out["transform"]["op"], "drop_surah:4")

    def test_dropping_the_declared_surah_itself_carries_nothing(self):
        b = _parent()
        out = drop_surah.carried_declared_tails(b, b["entries"], [24], "SOURCE_TRUNCATED", "x")
        self.assertEqual(out, ({}, []))

    def test_prefix_mismatch_refused(self):
        b = _parent()
        kept = [e for e in b["entries"] if e["ayahId"] != "24:7"]
        with self.assertRaises(SystemExit):
            drop_surah.carried_declared_tails(b, kept, [4], "SOURCE_TRUNCATED", "x")


if __name__ == "__main__":
    unittest.main()
