#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""اختباراتُ `truncate_tail.py`: ذيلٌ غيرُ متلوٍّ في الملفّ يُحذف ويُعلَن فيجتاز
`promote.declared_truncated_tail`، والأصلُ بلا الأداة لا يجتازه، وحُرّاسُها تردّ ما ليس حالتَها.

    python -m unittest tools/index_qa/test_truncate_tail_tool.py
"""
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import promote                                                   # noqa: E402
from drop_surah import SURAH_AYAHS                               # noqa: E402
from truncate_tail import truncate_tail                          # noqa: E402

URL = "https://h.example/r/{s:03d}.mp3"


def _index():
    ents = []
    for s, n in enumerate(SURAH_AYAHS, start=1):
        for a in range(1, n + 1):
            ents.append({"ayahId": f"{s}:{a}", "startMs": a * 1000, "endMs": a * 1000 + 1000,
                         "fileRef": URL.format(s=s), "confBand": "MED"})
    return {"riwaya": "hafs", "reciterId": "x", "ayahCounting": "KUFI", "refineVersion": "r",
            "entries": ents, "missing": {"count": 0, "byReason": {}, "ids": []}}


def _run(idx, **kw):
    args = dict(surah=63, keep=9, absorb=True, reason="الملفّ ينتهي بعد 63:9 (قياس السماع)",
                reason_user="تسجيلُ هذه السورة ينقطع قبل آخر آيتين.",
                reason_code="SOURCE_TRUNCATED", from_sha="0" * 64, from_key="timings/hafs/x.jz")
    args.update(kw)
    return truncate_tail(copy.deepcopy(idx), **args)


class TruncateTail(unittest.TestCase):
    def test_without_tool_promote_refuses(self):
        ok, _ = promote.declared_truncated_tail(_index(), 63)
        self.assertFalse(ok)

    def test_tool_output_passes_promote_and_index_gate(self):
        out = _run(_index())
        ok, why = promote.declared_truncated_tail(out, 63)
        self.assertTrue(ok, why)
        self.assertIsNone(promote.index_gate(out))
        self.assertEqual(len(out["entries"]), 6234)
        self.assertEqual(out["missing"]["byReason"], {"source_truncated": 2})
        self.assertEqual(out["missing"]["ids"], ["63:10", "63:11"])

    def test_only_last_end_changes(self):
        src = _index()
        out = _run(src)
        old = {e["ayahId"]: e for e in src["entries"]}
        diff = [e["ayahId"] for e in out["entries"] if e != old[e["ayahId"]]]
        self.assertEqual(diff, ["63:9"])
        e9 = next(e for e in out["entries"] if e["ayahId"] == "63:9")
        self.assertEqual((e9["startMs"], e9["endMs"]), (9000, 12000))
        out2 = _run(src, absorb=False)
        self.assertEqual([e for e in out2["entries"] if e["ayahId"] == "63:9"][0]["endMs"], 10000)

    def test_refuses_incomplete_surah(self):
        src = _index()
        src["entries"] = [e for e in src["entries"] if e["ayahId"] != "63:5"]
        src["missing"] = {"count": 1, "byReason": {"unknown": 1}, "ids": ["63:5"]}
        with self.assertRaises(SystemExit):
            _run(src)

    def test_refuses_bad_keep_and_code(self):
        for kw in ({"keep": 11}, {"keep": 0}, {"reason_code": "OTHER"}, {"reason_user": ""},
                   {"reason": "بأمر المالك"}):
            with self.assertRaises(SystemExit):
                _run(_index(), **kw)

    def test_absorb_refuses_other_file(self):
        src = _index()
        for e in src["entries"]:
            if e["ayahId"] == "63:11":
                e["fileRef"] = URL.format(s=64)
        with self.assertRaises(SystemExit):
            _run(src)


if __name__ == "__main__":
    unittest.main()
