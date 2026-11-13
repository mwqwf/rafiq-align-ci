"""اختباراتُ بقاء إعلان المصدر البديل الموروث عند الدمج (2026-11-13).

    python -m unittest tools.index_qa.test_splice_keep_source_decl -v

الحالة المقيسة: akri_qalun س106–108 — مضيفُ مجلّدٍ يلزمه `--refs-from-parent` الذي لا يجتمع
مع `--alt-source`، فكان `splice_surah.py` يمحو إعلانَ `sourceBySurah` الموروثَ ومداخلُ السورة
ما زالت تُشير إلى المصدر البديل فيردّ حارسُ `stage_transform`.
تُثبت: (أ) الإعلانُ يبقى حرفاً حين تشير المداخلُ إلى الرابط نفسِه؛ (ب) يُمحى حين يتغيّر
المصدرُ الفعليّ؛ (ج) طفرة: لو أُبطل الإصلاحُ لفشل (أ).
"""
from __future__ import annotations

import gzip
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from test_splice_folder_refs import FOLDER, NAME, _aligned, _parent   # noqa: E402

SCRIPT = HERE / "splice_surah.py"
FIX_GUARD = "if got_refs == {want_ref}:"


def _ref(s):
    return FOLDER + NAME.format(s=s)


def _run(tmp: Path, script: Path = SCRIPT, refs_map: str = "", new_url=None, declared=None):
    """يدمج س28 و36 من أبٍ يعلن س28 مصدراً بديلاً (رابطُه رابطُ مداخلها نفسُه)."""
    parent = _parent(FOLDER)
    parent["sourceBySurah"] = {"28": declared or _ref(28)}
    with gzip.open(tmp / "p.jz", "wt", encoding="utf-8") as f:
        json.dump(parent, f, ensure_ascii=False)
    files = []
    for s in (28, 36):
        p = tmp / f"s{s}.json"
        url = new_url if (new_url and s == 28) else _ref(s)
        res = _aligned(s, FOLDER)
        res["fileRef"] = url
        p.write_text(json.dumps(res), encoding="utf-8")
        files.append(str(p))
    cmd = [sys.executable, str(script), "--index", str(tmp / "p.jz"), "--surah", "28,36",
           "--aligned", *files, "--url", FOLDER, "--skip-unresolved",
           "--engine-tag", "ctc-seg-1", "--out", str(tmp / "o.jz")]
    cmd.append("--refs-map" if refs_map else "--refs-from-parent")
    if refs_map:
        cmd.append(refs_map)
    env = dict(os.environ, PYTHONPATH=str(HERE))
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", env=env)
    out = None
    if r.returncode == 0:
        with gzip.open(tmp / "o.jz", "rt", encoding="utf-8") as f:
            out = json.load(f)
    return r, out


class KeepInheritedSourceDecl(unittest.TestCase):
    def test_a_declaration_kept_when_entries_point_to_same_source(self):
        with tempfile.TemporaryDirectory() as t:
            r, out = _run(Path(t))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(out["sourceBySurah"], {"28": _ref(28)})
        got = {e["fileRef"] for e in out["entries"] if e["ayahId"].startswith("28:")}
        self.assertEqual(got, {_ref(28)})

    def test_b_declaration_dropped_when_entries_point_elsewhere(self):
        """الإعلانُ الموروثُ بقالبٍ لا يطابق رابطَ المداخل ⇒ لا يُبقى."""
        with tempfile.TemporaryDirectory() as t:
            r, out = _run(Path(t), declared="https://other.example/{s:03d}.mp3")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn("sourceBySurah", out)

    def test_b2_declaration_dropped_when_actual_source_changes(self):
        new = FOLDER + "ar_028_other_take.mp3"
        with tempfile.TemporaryDirectory() as t:
            r, out = _run(Path(t), refs_map=f"28={new},36={_ref(36)}")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        got = {e["fileRef"] for e in out["entries"] if e["ayahId"].startswith("28:")}
        self.assertEqual(got, {new})
        self.assertNotIn("sourceBySurah", out)

    def test_c_mutation_without_fix_a_fails(self):
        src = SCRIPT.read_text(encoding="utf-8")
        self.assertIn(FIX_GUARD, src)
        with tempfile.TemporaryDirectory() as t:
            mutant = Path(t) / "splice_mutant.py"
            mutant.write_text(src.replace(FIX_GUARD, "if False:"), encoding="utf-8")
            r, out = _run(Path(t), script=mutant)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotEqual(out.get("sourceBySurah"), {"28": _ref(28)})


if __name__ == "__main__":
    unittest.main()
