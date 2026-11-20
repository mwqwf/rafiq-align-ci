"""توصيلُ مدخل `explicit_gap` في ctc_splice.yml (فحصٌ نصّيٌّ للـYAML، بلا تشغيل).

    python -m pytest -q tools/index_qa/test_splice_explicit_gap_wiring.py

يُثبت: المدخلُ موجود · يُرفض في غير window ومع rewindow وabsent_ayahs وtruncated_tail ·
نمطُه صارم وسورُه ضمن surahs · يُمرَّر إلى `--explicit-gap` بعد تطبيع «س:أ» إلى «س:أ-أ» ·
ولا يتغيّر وسمُ المحرّك ولا حارسٌ في الأداة.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
YML = (ROOT / ".github/workflows/ctc_splice.yml").read_text(encoding="utf-8")
GAPSPLIT = (ROOT / "tools/alignment_v3/ctc_gapsplit.py").read_text(encoding="utf-8")


class ExplicitGapWiring(unittest.TestCase):
    def test_input_declared_with_empty_default(self):
        self.assertRegex(YML, r'explicit_gap: \{description: "[^"]*window[^"]*", default: ""\}')

    def test_env_in_plan_and_run_steps(self):
        self.assertEqual(YML.count("XGAP: ${{ github.event.inputs.explicit_gap }}"), 2)

    def test_refused_outside_window_and_with_other_doors(self):
        self.assertIn('if os.environ.get("MODE", "full") != "window":\n                  sys.exit("⛔ explicit_gap لوضع window وحده")', YML)
        m = re.search(r'if os\.environ\.get\("REWIN", ""\)\.strip\(\) or absent or os\.environ\.get\("TRUNC", ""\)\.strip\(\):\n\s+sys\.exit\("⛔ explicit_gap لا يجتمع مع rewindow ولا absent_ayahs', YML)
        self.assertIsNotNone(m)

    def test_strict_pattern_accepts_and_rejects(self):
        m = re.search(r're\.fullmatch\(r"([^"]+)", xgap\)', YML)
        self.assertIsNotNone(m)
        pat = m.group(1)
        for ok in ("5:12", "5:12,5:20", "23:105-106", "23:89,23:105-106,25:66"):
            self.assertTrue(re.fullmatch(pat, ok), ok)
        for bad in ("", "5", "5:", "5:12-", "5:12;5:20", "5:12 5:20", "5:12,", "a:1", "5:12-13-14", "5:1234"):
            self.assertFalse(re.fullmatch(pat, bad), bad)

    def test_surahs_must_be_named(self):
        self.assertIn("يجب أن تُسمّى في surahs", YML)

    def test_passed_to_tool_with_normalised_ranges(self):
        self.assertIn('${XGAP:+--explicit-gap "$XG"}', YML)
        self.assertIn("test_explicit_gap.py", YML)
        norm = re.search(r'XG="\$\(printf .*?python -c "([^"]+)"\)"', YML)
        self.assertIsNotNone(norm)
        code = norm.group(1)
        for src, want in (("5:12,5:20", "5:12-12,5:20-20"), ("23:105-106", "23:105-106")):
            import io, sys
            old, sys.stdin = sys.stdin, io.StringIO(src)
            out = io.StringIO(); o2, sys.stdout = sys.stdout, out
            try:
                exec(code)
            finally:
                sys.stdin, sys.stdout = old, o2
            self.assertEqual(out.getvalue().strip(), want)

    def test_engine_tag_and_guards_unchanged(self):
        self.assertIn('ETAG="ctc-gapsplit-1"', YML)
        for g in ("MIN_CONF", "NEIGH_LO", "DUR_LO", "DUR_HI"):
            self.assertIn(g, GAPSPLIT)
        self.assertRegex(GAPSPLIT, r"MIN_CONF\s*=\s*0\.45")


if __name__ == "__main__":
    unittest.main()
