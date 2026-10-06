import importlib.util
from pathlib import Path
import unittest


PATH = Path(__file__).with_name("resume_guard.py")
SPEC = importlib.util.spec_from_file_location("resume_guard", PATH)
guard = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(guard)


GOOD = (
    "# مصحفك: نقطة الاستئناف — اختبار\n\n"
    "## متابعة Codex — أ\n\n"
    "- قياس محفوظ.\n"
).encode()


class ResumeGuardTests(unittest.TestCase):
    def test_accepts_byte_exact_append(self):
        stats = guard.require_append_only(
            GOOD + "\n## متابعة Codex — ب\n\n- تقدم جديد.\n".encode(), GOOD
        )
        self.assertEqual(stats["baselineSections"], 1)
        self.assertEqual(stats["candidateSections"], 2)

    def test_rejects_invalid_utf8(self):
        with self.assertRaisesRegex(ValueError, "UTF-8"):
            guard.require_append_only(GOOD + b"\xff\n", GOOD)

    def test_rejects_rewrite_or_truncation(self):
        with self.assertRaisesRegex(ValueError, "لا يحفظ baseline"):
            guard.require_append_only(GOOD.replace(b"Codex", b"CODEX"), GOOD)
        with self.assertRaises(ValueError):
            guard.require_append_only(GOOD[:-1], GOOD)


if __name__ == "__main__":
    unittest.main()
