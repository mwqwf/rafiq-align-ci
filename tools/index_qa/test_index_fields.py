# -*- coding: utf-8 -*-
"""اختبار index_fields: `audioSha256` و`timingWarnings` تُقبل بالصيغتين (قائمة / نصُّ قائمة) ولا يُبتلع المعطوب.

السياق: في 180/180 فهرساً منشوراً `audioSha256` قائمةٌ حقيقية، و`timingWarnings` قائمةُ قواميس في 28 فهرس توقيت ناشر.
`ast.literal_eval(list)` يرفع ValueError فكان `except: []` يُسقط الفحصَ صامتاً."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import index_fields as F  # noqa: E402

SHAS = [f"{n:064x}" for n in range(1, 115)]


class AudioShasTest(unittest.TestCase):
    def test_real_list_accepted(self):
        self.assertEqual(F.audio_shas({"audioSha256": SHAS}), SHAS)

    def test_text_forms_accepted(self):
        self.assertEqual(F.audio_shas({"audioSha256": json.dumps(SHAS)}), SHAS)
        self.assertEqual(F.audio_shas({"audioSha256": repr(SHAS)}), SHAS)       # repr بايثون بنقطتي اقتباس مفردتين

    def test_absent_is_empty_not_error(self):
        self.assertEqual(F.audio_shas({}), [])
        self.assertEqual(F.audio_shas({"audioSha256": None}), [])
        self.assertEqual(F.audio_shas({"audioSha256": "  "}), [])

    def test_malformed_raises_never_swallowed(self):
        for bad in ("[not a list", "{'a': 1}", "123", 7, {"a": 1}, [1, 2]):
            with self.assertRaises(F.IndexFieldError, msg=repr(bad)):
                F.audio_shas({"audioSha256": bad})
        with self.assertRaises(F.IndexFieldError):
            F.audio_shas(None)

    def test_none_slots_preserved_empty_strings_normalised(self):
        got = F.audio_shas({"audioSha256": [None, "a" * 64, ""]})
        self.assertEqual(got, [None, "a" * 64, None])

    def test_does_not_execute_code(self):
        with self.assertRaises(F.IndexFieldError):
            F.audio_shas({"audioSha256": "__import__('os').system('true')"})

    def test_full_shas_requires_114(self):
        self.assertEqual(F.full_shas({"audioSha256": SHAS}), SHAS)
        for bad in ({}, {"audioSha256": SHAS[:100]}, {"audioSha256": "[]"}):
            with self.assertRaises(F.IndexFieldError):
                F.full_shas(bad)


class ShaBySurahTest(unittest.TestCase):
    def test_full_slots_with_dropped_surah(self):
        present = [s for s in range(1, 115) if s != 9]
        got = F.sha_by_surah({"audioSha256": SHAS}, present)
        self.assertEqual(got[10], SHAS[9])
        self.assertNotIn(9, got)

    def test_compact_form(self):
        got = F.sha_by_surah({"audioSha256": ["x" * 64, "y" * 64]}, [5, 2])
        self.assertEqual(got, {2: "x" * 64, 5: "y" * 64})

    def test_uncovered_raises(self):
        for idx in ({}, {"audioSha256": SHAS[:50]}, {"audioSha256": "[]"}):
            with self.assertRaises(F.IndexFieldError):
                F.sha_by_surah(idx, [1, 2, 3])


class TimingWarningsTest(unittest.TestCase):
    W = [{"surah": 1, "ratio": 0.954, "note": "x"}, {"surah": "7", "ratio": 1.2}]

    def test_list_accepted_and_warned_surahs(self):
        self.assertEqual(F.warned_surahs({"timingWarnings": self.W}), {1, 7})

    def test_text_forms_accepted(self):
        self.assertEqual(F.warned_surahs({"timingWarnings": json.dumps(self.W)}), {1, 7})
        self.assertEqual(F.warned_surahs({"timingWarnings": repr(self.W)}), {1, 7})

    def test_absent_is_empty(self):
        self.assertEqual(F.timing_warnings({}), [])
        self.assertEqual(F.warned_surahs({"timingWarnings": None}), set())

    def test_malformed_raises(self):
        for bad in ("[oops", [1, 2], [{"note": "no surah"}], [{"surah": "abc"}], 5):
            with self.assertRaises(F.IndexFieldError, msg=repr(bad)):
                F.timing_warnings({"timingWarnings": bad})

    def test_old_pattern_was_silently_wrong(self):
        """يُثبت العطب الأصلي: literal_eval على القائمة الحقيقية يرفع، فكان الابتلاع يُفرغ التحذيرات."""
        import ast
        with self.assertRaises(ValueError):
            ast.literal_eval(self.W)
        self.assertEqual(F.warned_surahs({"timingWarnings": self.W}), {1, 7})


if __name__ == "__main__":
    unittest.main()
