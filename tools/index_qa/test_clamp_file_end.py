"""‏`clamp_file_end.plan` — يُقصّ التجاوزُ الصغير لآخر مدخلٍ وحده، والكبيرُ يُردّ (2026-09-30)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from clamp_file_end import plan  # noqa: E402

U = "https://h/093.mp3"


def ents(last_end):
    return [{"ayahId": "93:10", "fileRef": U, "startMs": 43870, "endMs": 49050},
            {"ayahId": "93:11", "fileRef": U, "startMs": 49050, "endMs": last_end}]


class Clamp(unittest.TestCase):
    def test_small_overrun_of_last_entry_clamped(self):
        cuts, refused = plan(ents(53916), {93}, lambda u: 53869)
        self.assertEqual(cuts, [("93:11", 53916, 53869)])
        self.assertEqual(refused, [])

    def test_large_overrun_refused_not_clamped(self):
        cuts, refused = plan(ents(60000), {93}, lambda u: 53869)
        self.assertEqual(cuts, [])
        self.assertEqual(len(refused), 1)

    def test_inside_file_untouched(self):
        self.assertEqual(plan(ents(53800), {93}, lambda u: 53869), ([], []))

    def test_only_named_surahs(self):
        self.assertEqual(plan(ents(53916), {94}, lambda u: 53869), ([], []))

    def test_file_end_before_start_refused(self):
        cuts, refused = plan(ents(49300), {93}, lambda u: 49000)
        self.assertEqual(cuts, [])
        self.assertEqual(len(refused), 1)


if __name__ == "__main__":
    unittest.main()
