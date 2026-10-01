"""اختبار دمج تصحيح أسماء التسجيلات مع حفظ بقية الفهرس ورفض مصدر غير مثبت."""
import gzip
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.ci_fleet.source_registry import registered_source

ROOT = Path(__file__).resolve().parents[2]


class RegisteredSpliceTest(unittest.TestCase):
    def run_splice(self, corrupt=None):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            inherited = {"ayahId": "1:1", "fileRef": "https://example.test/001.mp3",
                         "startMs": 1000, "endMs": 2000, "conf": .9}
            parent = {"riwaya": "qalun", "reciterId": "akri_qalun",
                      "engineVersion": "align-0.2", "audioSha256": ["0" * 64] * 114,
                      "entries": [inherited], "missing": {"count": 6235}}
            (p / "parent.jz").write_bytes(gzip.compress(json.dumps(parent).encode()))
            files = []
            for s, count in [(106, 4), (107, 7), (108, 3)]:
                source = registered_source("qalun", "akri_qalun", s)
                res = {"sourceUrl": source["url"], "audioSha256": source["audio_sha256"],
                       "entries": [{"startMs": (i + 1) * 4000, "endMs": (i + 2) * 4000,
                                    "conf": .7, "snapped": True} for i in range(count)]}
                if s == 107 and corrupt:
                    res[corrupt] = "https://example.test/wrong.mp3" if corrupt == "sourceUrl" else "b" * 64
                file = p / f"s{s}.json"; file.write_text(json.dumps(res)); files.append(str(file))
            cmd = [sys.executable, str(ROOT / "tools/index_qa/splice_surah.py"),
                   "--index", str(p / "parent.jz"), "--surah", "106,107,108",
                   "--aligned", *files, "--url", "https://example.test/{s:03d}.mp3",
                   "--registered-sources", "--alt-source", "--engine-tag", "ctc-seg-1",
                   "--out", str(p / "candidate.jz")]
            result = subprocess.run(cmd, capture_output=True, text=True)
            out = json.loads(gzip.decompress((p / "candidate.jz").read_bytes())) if result.returncode == 0 else None
            return result, out, inherited

    def test_atomic_cycle_correction_restores_missing_surah_and_preserves_other_entries(self):
        result, out, inherited = self.run_splice()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(out["entries"][0], inherited)
        for s, count in [(106, 4), (107, 7), (108, 3)]:
            source = registered_source("qalun", "akri_qalun", s)
            rows = [e for e in out["entries"] if e["ayahId"].startswith(f"{s}:")]
            self.assertEqual(len(rows), count)
            self.assertEqual({e["fileRef"] for e in rows}, {source["url"]})
            self.assertEqual(out["audioSha256"][s - 1], source["audio_sha256"])
            self.assertEqual(out["sourceBySurah"][str(s)], source["url"])
            self.assertEqual(out["engineBySurah"][str(s)], "ctc-seg-1")

    def test_wrong_url_or_audio_hash_never_writes_candidate(self):
        for field in ["sourceUrl", "audioSha256"]:
            result, out, _ = self.run_splice(field)
            self.assertNotEqual(result.returncode, 0)
            self.assertIsNone(out)
