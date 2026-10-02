"""اختباراتُ دمج CTC من مضيف مجلَّدٍ بلا `{s:03d}` (2026-09-28).

    python -m pytest -q tools/index_qa/test_splice_folder_refs.py

تُثبت: (1) مجلَّدٌ مع أبٍ فيه رابطٌ واحدٌ للسورة ⇒ يُؤخذ `fileRef` منه حرفاً؛
(2) أبٌ بلا مدخلٍ للسورة أو بروابطَ مختلفة ⇒ ردٌّ صريح؛ (3) القالبُ المرقَّمُ
القديمُ يعمل كما هو؛ (4) مجلَّدٌ بلا `--refs-from-parent` يُردّ ولا يُكتب
المجلَّدُ مرجعاً لكلّ آية؛ (5) السيرُ يمرّر العَلَمَ ويطابق الروابطَ بالكتالوج.
"""
from __future__ import annotations

import gzip
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))

from splice_surah import COUNTS                                  # noqa: E402

FOLDER = "https://archive.org/download/gharbi_warsh/"
NAME = "ar_{s:03d}_Mustapha_Gharbi_Warsh.mp3"
TPL = "https://h.example/r/{s:03d}.mp3"
GAP = {28: [5, 6], 36: [9]}


def _ref(s, url):
    return url.format(s=s) if "{s" in url else url + NAME.format(s=s)


def _parent(url, drop=(), odd=None):
    ents = []
    for s in range(1, 115):
        if s in drop:
            continue
        for a in range(1, COUNTS[s - 1] + 1):
            if a in GAP.get(s, []):
                continue
            ref = _ref(s, url)
            if odd and odd == (s, a):
                ref = url + "other.mp3"
            st = a * 4000
            ents.append({"ayahId": f"{s}:{a}", "fileRef": ref, "startMs": st,
                         "endMs": st + 3500, "conf": 0.9, "confBand": "HIGH"})
    return {"riwaya": "warsh", "reciterId": "gharbi_warsh", "engineVersion": "align-0.2",
            "entries": ents, "missing": {"count": 3, "ids": [], "byReason": {}}}


def _aligned(s, url):
    rows = [{"ayahIdx": i, "startMs": (i + 1) * 5000, "endMs": (i + 1) * 5000 + 4000,
             "conf": 0.85, "snapped": True} for i in range(COUNTS[s - 1])]
    return {"fileRef": _ref(s, url), "sha256": "b" * 64, "entries": rows}


def _run(tmp: Path, parent: dict, url: str, refs: bool, surahs=(28, 36), refs_map: str = ""):
    with gzip.open(tmp / "p.jz", "wt", encoding="utf-8") as f:
        json.dump(parent, f, ensure_ascii=False)
    files = []
    for s in surahs:
        p = tmp / f"s{s}.json"
        p.write_text(json.dumps(_aligned(s, url)), encoding="utf-8")
        files.append(str(p))
    cmd = [sys.executable, str(HERE / "splice_surah.py"), "--index", str(tmp / "p.jz"),
           "--surah", ",".join(map(str, surahs)), "--aligned", *files, "--url", url,
           "--skip-unresolved", "--engine-tag", "ctc-seg-1", "--out", str(tmp / "o.jz")]
    if refs:
        cmd.append("--refs-from-parent")
    if refs_map:
        cmd += ["--refs-map", refs_map]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    out = None
    if r.returncode == 0:
        with gzip.open(tmp / "o.jz", "rt", encoding="utf-8") as f:
            out = json.load(f)
    return r, out


class FolderRefs(unittest.TestCase):
    def test_folder_takes_ref_from_parent_verbatim(self):
        with tempfile.TemporaryDirectory() as t:
            r, out = _run(Path(t), _parent(FOLDER), FOLDER, refs=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        for s in (28, 36):
            got = {e["fileRef"] for e in out["entries"] if e["ayahId"].startswith(f"{s}:")}
            self.assertEqual(got, {FOLDER + NAME.format(s=s)})
        self.assertEqual(len(out["entries"]), 6236)
        self.assertEqual(out["engineBySurah"], {"28": "ctc-seg-1", "36": "ctc-seg-1"})
        self.assertNotIn("sourceBySurah", out)

    def test_folder_surah_absent_from_parent_refused(self):
        with tempfile.TemporaryDirectory() as t:
            r, _ = _run(Path(t), _parent(FOLDER, drop=(36,)), FOLDER, refs=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("لا مدخلَ لها في الأب", r.stdout + r.stderr)

    def test_folder_mixed_refs_refused(self):
        with tempfile.TemporaryDirectory() as t:
            r, _ = _run(Path(t), _parent(FOLDER, odd=(28, 1)), FOLDER, refs=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("بروابطَ مختلفة", r.stdout + r.stderr)

    def test_folder_ref_outside_folder_refused(self):
        with tempfile.TemporaryDirectory() as t:
            r, _ = _run(Path(t), _parent("https://evil.example/x/"), FOLDER, refs=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("خارجَ المجلَّد", r.stdout + r.stderr)

    def test_folder_without_flag_refused_not_written(self):
        with tempfile.TemporaryDirectory() as t:
            r, _ = _run(Path(t), _parent(FOLDER), FOLDER, refs=False)
            self.assertFalse((Path(t) / "o.jz").exists())
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("بلا {s:03d}", r.stdout + r.stderr)

    def test_refs_flag_with_template_refused(self):
        with tempfile.TemporaryDirectory() as t:
            r, _ = _run(Path(t), _parent(TPL), TPL, refs=True)
        self.assertNotEqual(r.returncode, 0)

    def test_numbered_template_unchanged(self):
        with tempfile.TemporaryDirectory() as t:
            r, out = _run(Path(t), _parent(TPL), TPL, refs=False)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        for s in (28, 36):
            got = {e["fileRef"] for e in out["entries"] if e["ayahId"].startswith(f"{s}:")}
            self.assertEqual(got, {TPL.format(s=s)})
        self.assertEqual(len(out["entries"]), 6236)


class FolderRefGuard(unittest.TestCase):
    """⛔ (2026-10-02) الأبُ الذي يحمل المجلّدَ مرجعاً (‏وقع ونُشر عند الركباوي والغربي) لا يُورَّث؛
    والبديلُ `--refs-map` بروابطَ محلولةٍ من جدول الكتالوج، بحرّاسٍ: داخل المجلّد وباسم ملفٍّ صوتيّ."""

    def _folder_parent(self):
        p = _parent(FOLDER)
        for e in p["entries"]:
            if e["ayahId"].split(":")[0] in ("28", "36"):
                e["fileRef"] = FOLDER.rstrip("/")             # المجلّدُ نفسُه بلا اسم ملفّ
        return p

    def test_parent_folder_ref_refused(self):
        with tempfile.TemporaryDirectory() as t:
            r, _ = _run(Path(t), self._folder_parent(), FOLDER, refs=True)
            self.assertFalse((Path(t) / "o.jz").exists())
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("مجلّدٌ لا ملفٌّ صوتيّ", r.stdout + r.stderr)

    def test_refs_map_writes_resolved_names(self):
        m = ",".join(f"{s}={FOLDER + NAME.format(s=s)}" for s in (28, 36))
        with tempfile.TemporaryDirectory() as t:
            r, out = _run(Path(t), self._folder_parent(), FOLDER, refs=False, refs_map=m)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        for s in (28, 36):
            got = {e["fileRef"] for e in out["entries"] if e["ayahId"].startswith(f"{s}:")}
            self.assertEqual(got, {FOLDER + NAME.format(s=s)})
        self.assertEqual(len(out["entries"]), 6236)

    def test_refs_map_folder_value_refused(self):
        m = f"28={FOLDER}sub/,36={FOLDER + NAME.format(s=36)}"
        with tempfile.TemporaryDirectory() as t:
            r, _ = _run(Path(t), self._folder_parent(), FOLDER, refs=False, refs_map=m)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("مجلّدٌ لا ملفٌّ صوتيّ", r.stdout + r.stderr)

    def test_refs_map_outside_folder_refused(self):
        m = f"28=https://evil.example/028.mp3,36={FOLDER + NAME.format(s=36)}"
        with tempfile.TemporaryDirectory() as t:
            r, _ = _run(Path(t), self._folder_parent(), FOLDER, refs=False, refs_map=m)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("خارجَ المجلَّد", r.stdout + r.stderr)

    def test_refs_map_missing_surah_refused(self):
        m = f"28={FOLDER + NAME.format(s=28)}"
        with tempfile.TemporaryDirectory() as t:
            r, _ = _run(Path(t), self._folder_parent(), FOLDER, refs=False, refs_map=m)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("بلا رابطٍ للسور [36]", r.stdout + r.stderr)

    def test_refs_map_with_numbered_template_refused(self):
        m = f"28={TPL.format(s=28)},36={TPL.format(s=36)}"
        with tempfile.TemporaryDirectory() as t:
            r, _ = _run(Path(t), _parent(TPL), TPL, refs=False, refs_map=m)
        self.assertNotEqual(r.returncode, 0)

    def test_structural_guard_flags_folder_ref(self):
        import run as _run_mod
        idx = self._folder_parent()
        idx.update({"ayahCounting": "KUFI", "ayahCount": 6236, "audioSha256": ["a" * 64] * 114,
                    "refineVersion": "x", "refinedCount": 0})
        fatal, _w, info = _run_mod.structural(idx, "timings/warsh/gharbi_warsh.jz", allow_unmarked=True)
        self.assertTrue(any("مجلّدٌ لا ملفّ" in f for f in fatal), fatal)
        self.assertEqual(info.get("folderFileRef"), [28, 36])
        for e in idx["entries"]:
            if e["ayahId"].split(":")[0] in ("28", "36"):
                e["fileRef"] = FOLDER + NAME.format(s=int(e["ayahId"].split(":")[0]))
        fatal, _w, info = _run_mod.structural(idx, "timings/warsh/gharbi_warsh.jz", allow_unmarked=True)
        self.assertFalse(any("مجلّدٌ لا ملفّ" in f for f in fatal), fatal)


class WorkflowContract(unittest.TestCase):
    def test_ctc_splice_folder_path(self):
        y = (ROOT / ".github/workflows/ctc_splice.yml").read_text(encoding="utf-8")
        self.assertIn("--refs-from-parent", y)
        self.assertIn("parent_refs(idx[\"entries\"], todo)", y)
        self.assertIn("r != urlt + files[s - 1]", y)       # الأبُ = الكتالوجُ + الجدول
        self.assertNotIn("غيرُ مدعومٍ في هذا المسار", y)
        # حارسُ مطابقة المنزَّل بالمدموج والإحصاءُ باقيان
        self.assertIn("fileRef المدموج", y)
        # ‏(2026-09-30) الوسمُ متغيّرٌ: ctc-seg-1 للوضع الكامل، وctc-gapsplit-1 لوضع النافذة وحده.
        self.assertIn('ETAG="ctc-seg-1"', y)
        self.assertIn('--engine-tag "$ETAG"', y)
        self.assertIn('if [ "$MODE" = "window" ]; then ALTF="$ALTF --keep-parent-gaps"; ETAG="ctc-gapsplit-1"; fi', y)
        self.assertIn("steps.plan.outputs.urlt", y)

    def test_realign_surah_folder_uses_resolved_refs_map(self):
        # ⛔ (2026-10-02) لا يُؤخذ الرابطُ من الأب (‏يورّث المجلّدَ المنشور) بل من الجدول المحلول.
        y = (ROOT / ".github/workflows/realign_surah.yml").read_text(encoding="utf-8")
        self.assertNotIn('REFS="--refs-from-parent"', y)
        self.assertIn('REFS="--refs-map ${REFMAP#,}"', y)
        self.assertIn('REFMAP="$REFMAP,$S=$URL"', y)


if __name__ == "__main__":
    unittest.main()
