"""‏`skip_for` — خريطةُ التخطّي لكلّ سورة (2026-09-30).  python -m unittest tools/ci_fleet/test_skip_for.py"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from skip_for import skip_for  # noqa: E402


class SkipFor(unittest.TestCase):
    def test_single_value_unchanged(self):
        self.assertEqual(skip_for("7840", 6), 7840)
        self.assertEqual(skip_for("0", 2), 0)
        self.assertEqual(skip_for("", 2), 0)

    def test_map_per_surah(self):
        self.assertEqual(skip_for("95:8030,97:6903", 97), 6903)
        self.assertEqual(skip_for("95:8030,97:6903", 95), 8030)

    def test_surah_missing_from_map_refused(self):
        with self.assertRaises(ValueError):
            skip_for("95:8030,97:6903", 99)

    def test_garbage_and_duplicates_refused(self):
        for bad in ("95=8030", "95:80a", "95:1,95:2", "-5", "95:"):
            with self.assertRaises(ValueError):
                skip_for(bad, 95)


if __name__ == "__main__":
    unittest.main()
