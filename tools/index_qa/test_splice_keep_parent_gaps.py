#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""`splice_surah.py --keep-parent-gaps` (‏ctc_gapsplit · 2026-09-29).

يثبت أنّ الخيارَ **لا يُرخي حارساً**:
  ① آيةٌ بلا حدودٍ غائبةٌ في الأب أصلاً ⇒ تُقبل السورةُ وتبقى الآيةُ غائبةً، ويُضاف المقسوم.
  ② آيةٌ بلا حدودٍ كانت **حاضرةً** في الأب ⇒ تُردّ السورةُ كما قبل الخيار.
  ③ بلا الخيار ⇒ السلوكُ القديمُ نفسُه (تُردّ السورة).
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
S = 55                  # غائبتان في الأب: 5 و20
PARENT_GAPS = {5, 20}


def _parent():
    ents = []
    for s in range(1, 115):
        for a in range(1, COUNTS[s - 1] + 1):
            if s == S and a in PARENT_GAPS:
                continue
            st = a * 4000
            ents.append({"ayahId": f"{s}:{a}", "fileRef": TPL.format(s=s), "startMs": st,
                         "endMs": st + 4000, "conf": 0.9, "confBand": "HIGH"})
    return {"riwaya": "warsh", "reciterId": "x_warsh", "engineVersion": "align-0.2",
            "entries": ents, "missing": {"count": 2, "ids": [], "byReason": {}}}


def _aligned(null_ayat):
    rows = []
    for i in range(COUNTS[S - 1]):
        if (i + 1) in null_ayat:
            rows.append({"ayahIdx": i, "startMs": None, "endMs": None, "conf": 0.0})
        else:
            st = (i + 1) * 4000
            rows.append({"ayahIdx": i, "startMs": st, "endMs": st + 4000,
                         "conf": 0.6, "snapped": True})
    return {"fileRef": TPL.format(s=S), "sha256": "c" * 64, "entries": rows}


def _run(tmp: Path, null_ayat, keep: bool):
    with gzip.open(tmp / "p.jz", "wt", encoding="utf-8") as f:
        json.dump(_parent(), f, ensure_ascii=False)
    (tmp / "s.json").write_text(json.dumps(_aligned(null_ayat)), encoding="utf-8")
    cmd = [sys.executable, str(HERE / "splice_surah.py"), "--index", str(tmp / "p.jz"),
           "--surah", str(S), "--aligned", str(tmp / "s.json"), "--url", TPL,
           "--skip-unresolved", "--engine-tag", "ctc-seg-1", "--out", str(tmp / "o.jz")]
    if keep:
        cmd.append("--keep-parent-gaps")
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    out = None
    if r.returncode == 0:
        with gzip.open(tmp / "o.jz", "rt", encoding="utf-8") as f:
            out = json.load(f)
    return r, out


class KeepParentGaps(unittest.TestCase):
    def test_inherited_gap_kept_and_split_added(self):
        # 5 قُسمت (لها حدود الآن) · 20 بقيت غائبةً كما في الأب
        with tempfile.TemporaryDirectory() as t:
            r, out = _run(Path(t), {20}, keep=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        ids = {e["ayahId"] for e in out["entries"]}
        self.assertIn(f"{S}:5", ids)
        self.assertNotIn(f"{S}:20", ids)
        self.assertEqual(len(out["entries"]), 6236 - 1)

    def test_present_in_parent_then_null_refused(self):
        # 7 حاضرةٌ في الأب ⇒ غيابُها في المخرَج نقضٌ يُردّ
        with tempfile.TemporaryDirectory() as t:
            r, _ = _run(Path(t), {7, 20}, keep=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("بلا حدود", r.stdout + r.stderr)

    def test_without_flag_old_behaviour(self):
        with tempfile.TemporaryDirectory() as t:
            r, _ = _run(Path(t), {20}, keep=False)
        self.assertNotEqual(r.returncode, 0)


if __name__ == "__main__":
    unittest.main()
