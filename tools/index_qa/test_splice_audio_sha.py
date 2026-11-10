#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""`splice_audio_sha.py` — البصمةُ المقيسة تُكتب للسورة المعاد محاذاتُها كلِّها وحدَها (‏2026-11-10 · الكردي س55).

  ① قائمةٌ ثابتةٌ من 114 وسورةٌ محجوبةٌ (‏113 حاضرة) + heard بـrewindow 55:1-78 ⇒ تُكتب بصمةُ س55 في موضعها 54.
  ② heard بمدىً جزئيّ (55:41-75) ⇒ لا تُمسّ.
  ③ وضعُ window ولو بصفوفٍ تامّة ⇒ لا تُمسّ؛ وdualfix بدليل أساسٍ على الملفّ نفسِه ⇒ تُكتب، وبلا دليل ⇒ لا.
  ④ مدخلٌ موروثٌ من الأب لم يأتِ من المحاذاة ⇒ لا تُمسّ.
  ⑤ قائمةٌ مضغوطةٌ على الحاضرة ⇒ موضعُ السورة بين الحاضرة.
  ⑥ fileRef مخالف ⇒ ردّ.
  ⑦ عبر سطر الأوامر على ملفٍّ حقيقيّ مضغوط.
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
import splice_audio_sha as M  # noqa: E402
from splice_surah import COUNTS  # noqa: E402

TPL = "https://h.example/r/{s:03d}.mp3"
OLD, NEW = "a" * 64, "b" * 64


def _rows(s, shift=0):
    return [{"startMs": 1000 * i + shift, "endMs": 1000 * i + 900 + shift} for i in range(COUNTS[s - 1])]


def _idx(drop=(4,), shas=114, s55_rows=None):
    ents = []
    for s in range(1, 115):
        if s in drop:
            continue
        rows = s55_rows if (s == 55 and s55_rows is not None) else _rows(s, 7)
        for i, r in enumerate(rows):
            ents.append({"ayahId": f"{s}:{i + 1}", "fileRef": TPL.format(s=s), **r})
    present = [s for s in range(1, 115) if s not in drop]
    lst = [f"{s:064x}" for s in range(1, 115)] if shas == 114 else [f"{s:064x}" for s in present]
    if shas == 114:
        lst[54] = OLD
    else:
        lst[present.index(55)] = OLD
    return {"entries": ents, "audioSha256": lst}


def _rec(rows=None):
    return {"fileRef": TPL.format(s=55), "sha256": NEW, "entries": rows or _rows(55)}


class T(unittest.TestCase):
    def test_whole_heard_114_written(self):
        idx = _idx(s55_rows=_rows(55))
        r = M.apply(idx, [55], {55: _rec()}, "heard", "55:1-78", log=lambda *_: None)
        self.assertEqual(r[55], "written")
        self.assertEqual(idx["audioSha256"][54], NEW)
        self.assertEqual(idx["audioSha256"][3], f"{4:064x}")      # موضعُ النساء المحجوبة باقٍ

    def test_partial_rewindow_kept(self):
        idx = _idx(s55_rows=_rows(55))
        r = M.apply(idx, [55], {55: _rec()}, "heard", "55:41-75", log=lambda *_: None)
        self.assertTrue(r[55].startswith("partial:"))
        self.assertEqual(idx["audioSha256"][54], OLD)

    def test_window_mode_kept(self):
        idx = _idx(s55_rows=_rows(55))
        r = M.apply(idx, [55], {55: _rec()}, "window", "55:1-78", log=lambda *_: None)
        self.assertTrue(r[55].startswith("partial:"))
        self.assertEqual(idx["audioSha256"][54], OLD)

    def test_dualfix_with_evidence_written(self):
        idx = _idx(s55_rows=_rows(55))
        rec = _rec()
        rec.update(engine="ctc-dualfix-1",
                   dualFixEvidence={"baseKey": "timings-staging/hafs/x.11111111.jz", "sourceSha256": NEW})
        r = M.apply(idx, [55], {55: rec}, "dualfix", "55:5-7,55:36-38", log=lambda *_: None)
        self.assertEqual(r[55], "written")
        self.assertEqual(idx["audioSha256"][54], NEW)

    def test_dualfix_without_evidence_kept(self):
        for ev in ({}, {"baseKey": "k", "sourceSha256": OLD}):
            idx = _idx(s55_rows=_rows(55))
            rec = _rec()
            rec.update(engine="ctc-dualfix-1", dualFixEvidence=ev)
            r = M.apply(idx, [55], {55: rec}, "dualfix", "", log=lambda *_: None)
            self.assertTrue(r[55].startswith("partial:"), ev)
            self.assertEqual(idx["audioSha256"][54], OLD)

    def test_inherited_entry_kept(self):
        rows = _rows(55)
        merged = [dict(x) for x in rows]
        merged[10] = {"startMs": 10007, "endMs": 10907}                 # مدخلٌ من الأب لا من المحاذاة
        idx = _idx(s55_rows=merged)
        r = M.apply(idx, [55], {55: _rec(rows)}, "heard", "", log=lambda *_: None)
        self.assertIn("ليست من هذه المحاذاة", r[55])
        self.assertEqual(idx["audioSha256"][54], OLD)

    def test_unbounded_row_kept(self):
        rows = _rows(55)
        rows[5] = {"startMs": None, "endMs": None}
        idx = _idx(s55_rows=_rows(55))
        r = M.apply(idx, [55], {55: _rec(rows)}, "full", "", log=lambda *_: None)
        self.assertTrue(r[55].startswith("partial:"))
        self.assertEqual(idx["audioSha256"][54], OLD)

    def test_truncated_or_absent_kept(self):
        for kw in ({"truncated": True}, {"absent": True}):
            idx = _idx(s55_rows=_rows(55))
            r = M.apply(idx, [55], {55: _rec()}, "heard", "", log=lambda *_: None, **kw)
            self.assertTrue(r[55].startswith("partial:"), kw)
            self.assertEqual(idx["audioSha256"][54], OLD)

    def test_compact_list_position(self):
        idx = _idx(shas="compact", s55_rows=_rows(55))
        r = M.apply(idx, [55], {55: _rec()}, "full", "", log=lambda *_: None)
        self.assertEqual(r[55], "written")
        self.assertEqual(idx["audioSha256"][53], NEW)                  # 113 حاضرة: س55 عند 53

    def test_fileref_mismatch_refused(self):
        idx = _idx(s55_rows=_rows(55))
        rec = _rec()
        rec["fileRef"] = "https://other/055.mp3"
        with self.assertRaises(SystemExit):
            M.apply(idx, [55], {55: rec}, "heard", "55:1-78", log=lambda *_: None)

    def test_cli_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            p = d / "patched.jz"
            p.write_bytes(gzip.compress(json.dumps(_idx(s55_rows=_rows(55))).encode()))
            Path(str(p) + ".taken").write_text("55")
            (d / "b").mkdir()
            (d / "b" / "s055.json").write_text(json.dumps(_rec()))
            subprocess.run([sys.executable, str(HERE / "splice_audio_sha.py"), "--index", str(p),
                            "--batch-dir", str(d / "b"), "--mode", "heard", "--rewindow", "55:1-78"],
                           check=True, capture_output=True)
            got = json.loads(gzip.decompress(p.read_bytes()))
            self.assertEqual(got["audioSha256"][54], NEW)


if __name__ == "__main__":
    unittest.main()
