#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""عذرُ البتر المسجَّل (`missing.byReason.source_truncated`) بعد `splice_surah.py` (‏2026-11-05).

① إعادةُ سورةٍ تامّةٍ لا غائبَ فيها لا تمحو عذرَ سورةٍ أخرى مُسقطةٍ بسببٍ مسجَّل.
② إعادةُ السورة المُسقطة نفسِها بمداخلها كلّها تُسقط عذرَها كاملاً.
③ العذرُ لا يزيد أبداً على ما كان في الأب.
"""
import gzip
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from splice_surah import COUNTS  # noqa: E402

TPL = "https://h.example/r/{s:03d}.mp3"
DROPPED = 22            # مُسقطةٌ كاملةً في الأب بعذرٍ مسجَّل


def _parent():
    ents = []
    for s in range(1, 115):
        if s == DROPPED:
            continue
        for a in range(1, COUNTS[s - 1] + 1):
            st = a * 4000
            ents.append({"ayahId": f"{s}:{a}", "fileRef": TPL.format(s=s), "startMs": st,
                         "endMs": st + 4000, "conf": 0.9, "confBand": "HIGH"})
    n = COUNTS[DROPPED - 1]
    return {"riwaya": "hafs", "reciterId": "x", "engineVersion": "align-0.2", "entries": ents,
            "missing": {"count": n, "ids": [], "byReason": {"source_truncated": n}}}


def _aligned(s):
    rows = [{"ayahIdx": i, "startMs": (i + 1) * 4000, "endMs": (i + 2) * 4000,
             "conf": 0.8, "snapped": True} for i in range(COUNTS[s - 1])]
    return {"fileRef": TPL.format(s=s), "sha256": "c" * 64, "entries": rows}


def _run(tmp: Path, s: int):
    with gzip.open(tmp / "p.jz", "wt", encoding="utf-8") as f:
        json.dump(_parent(), f, ensure_ascii=False)
    (tmp / "s.json").write_text(json.dumps(_aligned(s)), encoding="utf-8")
    r = subprocess.run([sys.executable, str(HERE / "splice_surah.py"), "--index", str(tmp / "p.jz"),
                        "--surah", str(s), "--aligned", str(tmp / "s.json"), "--url", TPL,
                        "--skip-unresolved", "--engine-tag", "ctc-heardmap-1", "--out", str(tmp / "o.jz")],
                       capture_output=True, text=True, encoding="utf-8")
    out = None
    if r.returncode == 0:
        with gzip.open(tmp / "o.jz", "rt", encoding="utf-8") as f:
            out = json.load(f)
    return r, out


class TruncatedExcuse(unittest.TestCase):
    def test_other_surah_keeps_excuse(self):
        with tempfile.TemporaryDirectory() as t:
            r, out = _run(Path(t), 12)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        m = out["missing"]
        self.assertEqual(m["count"], COUNTS[DROPPED - 1])
        self.assertEqual(m["byReason"].get("source_truncated"), COUNTS[DROPPED - 1])

    def test_dropped_surah_returned_clears_excuse(self):
        with tempfile.TemporaryDirectory() as t:
            r, out = _run(Path(t), DROPPED)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(out["missing"]["count"], 0)
        self.assertNotIn("source_truncated", out["missing"]["byReason"])

    def test_excuse_never_exceeds_missing(self):
        with tempfile.TemporaryDirectory() as t:
            r, out = _run(Path(t), 12)
        m = out["missing"]
        self.assertLessEqual(m["byReason"].get("source_truncated", 0), m["count"])


if __name__ == "__main__":
    unittest.main()
