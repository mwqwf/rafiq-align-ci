"""المدخل الذي لم يُعد قياسه يحتفظ بوسوم تقريب حدوده؛ لا علامة ثقة منسوخة لقياس متغير."""
import gzip
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent


class InheritedFlagsTest(unittest.TestCase):
    def build(self, corrupt=False):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            rows = [{"ayahId": f"112:{i+1}", "fileRef": "https://example.test/112.mp3",
                     "startMs": (i+1)*2000, "endMs": (i+2)*2000, "conf": .76,
                     "confBand": "HIGH", "startApprox": True, "endApprox": True} for i in range(4)]
            parent = {"riwaya": "hafs", "reciterId": "x", "entries": rows, "missing": {}}
            (p/"parent.jz").write_bytes(gzip.compress(json.dumps(parent).encode()))
            aligned = {"entries": [{"startMs": e["startMs"], "endMs": e["endMs"],
                                    "conf": e["conf"], "snapped": False, "inherited": True} for e in rows]}
            if corrupt:
                aligned["entries"][0]["conf"] = .9
            (p/"s.json").write_text(json.dumps(aligned))
            r = subprocess.run([sys.executable, str(HERE/"splice_surah.py"), "--index", str(p/"parent.jz"),
                                "--surah", "112", "--aligned", str(p/"s.json"), "--url", "https://example.test/{s:03d}.mp3",
                                "--preserve-inherited-entries", "--out", str(p/"out.jz")], capture_output=True, text=True)
            output = json.loads(gzip.decompress((p/"out.jz").read_bytes())) if (p/"out.jz").exists() else None
            return r, rows, output

    def test_preserves_approximation_flags_and_original_confidence_band(self):
        r, original, out = self.build()
        self.assertEqual(r.returncode, 0, r.stdout+r.stderr)
        self.assertEqual(out["entries"], original)

    def test_changed_confidence_cannot_be_claimed_inherited(self):
        r, _, out = self.build(corrupt=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertIsNone(out)


if __name__ == "__main__":
    unittest.main()
