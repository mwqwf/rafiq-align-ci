"""اختباراتُ عقدِ مُدخَل `quran_model` في `ctc_splice.yml` (محاذاةُ سورةٍ كاملةً بنموذج التلاوة).

    python -m unittest tools/index_qa/test_ctc_splice_quran_model_input.py

تُثبت: (1) المُدخَل مطفأٌ افتراضاً · (2) لا يجتمع مع الذيل المبتور ولا الغائبات ولا غيرِ full ·
(3) استثناءُ «الأصلُ منشورٌ بـCTC نفسِه» مشروطٌ به وحدَه · (4) العَلَمُ يصل إلى batch_run والمحرّكُ المعلَن
`ctc-quran-surah-1` وتحويلُه `ctc_quran_surah_splice` يلزمهما الإحصاءُ الشامل · (5) سلوكُ batch_run:
العَلَمُ يلزمه ALIGN_ENGINE=ctc ويكتب نسبَ النموذج في ملف السورة.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import unittest
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))

import promote  # noqa: E402

WF = ROOT / ".github/workflows/ctc_splice.yml"


class WorkflowContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.y = WF.read_text(encoding="utf-8")
        cls.doc = yaml.safe_load(cls.y)

    def _inputs(self):
        on = self.doc.get("on") or self.doc.get(True)
        return on["workflow_dispatch"]["inputs"]

    def test_input_off_by_default(self):
        inp = self._inputs()["quran_model"]
        self.assertEqual(inp["default"], "false")
        self.assertFalse(inp.get("required", False))

    def test_input_is_full_mode_only_and_excludes_tail_and_absent(self):
        self.assertIn('if qm not in ("true", "float32", "false")', self.y)
        self.assertRegex(self.y, r'qm != "false" and \(os\.environ\.get\("MODE", "full"\) != "full"')
        self.assertIn('os.environ.get("TRUNC", "").strip()', self.y)
        self.assertIn('os.environ.get("ABSENT", "").strip() or not os.environ.get("WANT", "").strip()', self.y)

    def test_parent_ctc_refusal_exception_is_conditional_on_input_alone(self):
        m = re.search(r'if idx\.get\("engineVersion"\) == "ctc-seg-1"[^\n]*', self.y)
        self.assertIsNotNone(m)
        line = m.group(0)
        self.assertIn('qm == "false"', line)
        # الأوضاعُ القائمة كما هي (لم يُوسَّع الاستثناءُ لغير المُدخَل)
        self.assertIn('not in ("window", "heard", "dualfix")', line)
        self.assertIn("not alt", line)

    def test_flag_reaches_aligner_only_when_true(self):
        self.assertIn('QMF=""; [ "$QM" != "false" ] && QMF="--quran-model"', self.y)
        self.assertIn('[ "$QM" = "float32" ] && export CTC_INT8=0 CTC_THREADS=2', self.y)
        self.assertIn('--base "$BASE" --surahs "$SURAHS" $QMF', self.y)

    def test_engine_declared_with_distinct_name(self):
        self.assertIn('if [ "$QM" != "false" ]; then ETAG="ctc-quran-surah-1"; fi', self.y)
        self.assertIn('if [ "$QM" != "false" ]; then OPN="ctc_quran_surah_splice"; fi', self.y)

        # الاسمُ مُعلَنٌ في السجلّ الموحَّد فيلزمه الإحصاءُ الشامل، ومحرّكُه غيرُ ctc-seg-1
        self.assertEqual(promote.SPLICE_OPS["ctc_quran_surah_splice"], Q_ENGINE)
        self.assertNotEqual(Q_ENGINE, promote.SPLICE_OPS["ctc_surah_splice"])
        self.assertNotIn("--owner-truncated-tail", re.search(
            r'if \[ "\$QM" != "false" \]; then OPN[^\n]*', self.y).group(0))

    def test_no_input_interpolated_inside_run(self):
        # 🔒 (المراجعة الأمنية 2026-11-14) لا ${{ inputs.* }} داخل run: في سيرٍ يحمل سرَّ R2 — المدخلاتُ عبر env وحدها
        import re
        for block in re.findall(r"run: \|\n((?:          .*\n|\s*\n)+)", self.y):
            self.assertNotRegex(block, r"\$\{\{\s*(github\.event\.)?inputs\.")

    def test_existing_modes_and_guards_untouched(self):
        for needle in ('ETAG="ctc-seg-1"', 'ETAG="ctc-gapsplit-1"', 'ETAG="ctc-heardmap-1"', 'ETAG="ctc-dualfix-1"',
                       'ETAG="ctc-quran-surah-1"', "--skip-unresolved", "stage_transform.py"):
            self.assertIn(needle, self.y)
        # (#95 · 5a230b751a) حارسُ «fileRef المدموج» انتقل من سطر السير المضمَّن إلى splice_audio_sha.py (مختبَر في
        # test_splice_audio_sha)؛ فيلزم أن يستدعيه السيرُ وأن يبقى الحارسُ في الأداة.
        self.assertIn("python tools/index_qa/splice_audio_sha.py", self.y)
        self.assertIn("fileRef المدموج", (Path(__file__).resolve().parent / "splice_audio_sha.py").read_text(encoding="utf-8"))

    def test_concurrency_group_splits_by_surahs_only_for_quran_model(self):
        g = self.doc["concurrency"]["group"]
        self.assertIn("inputs.quran_model != 'false'", g)
        self.assertTrue(g.startswith("${{ inputs.parent }}") or g.startswith("rafiq-ctc-splice-${{ inputs.parent }}"))


Q_ENGINE = "ctc-quran-surah-1"


class BatchRunBehaviour(unittest.TestCase):
    def test_flag_requires_ctc_engine(self):
        env = {k: v for k, v in os.environ.items() if k != "ALIGN_ENGINE"}
        r = subprocess.run([sys.executable, str(ROOT / "tools/alignment/batch_run.py"), "--reciter", "x",
                            "--riwaya", "hafs", "--base", "https://h.example/{surah:03d}.mp3", "--quran-model"],
                           cwd=ROOT / "tools/alignment", env=env, capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("ALIGN_ENGINE=ctc", r.stdout + r.stderr)

    def test_source_wires_pinned_evidence_only_with_flag(self):
        src = (ROOT / "tools/alignment/batch_run.py").read_text(encoding="utf-8")
        self.assertIn('quran_model=True', src)
        self.assertIn('rec["engine"] = result["engine"]', src)
        self.assertIn('rec["alignmentModel"] = result["alignmentModel"]', src)
        self.assertIn("if args.quran_model:", src)


if __name__ == "__main__":
    unittest.main()
