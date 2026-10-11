import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))
import split_open_tafsirs as m


class T(unittest.TestCase):
    def test_key(self):
        self.assertEqual(m.chunk_key("tabari", 2, 255), "ai-tafsir/v1/tabari/2/12.json")
        self.assertEqual(m.chunk_key("x", 1, 1), "ai-tafsir/v1/x/1/0.json")
        self.assertEqual(m.chunk_key("x", 1, 20), "ai-tafsir/v1/x/1/0.json")
        self.assertEqual(m.chunk_key("x", 1, 21), "ai-tafsir/v1/x/1/1.json")

    def test_excerpt(self):
        self.assertEqual(m.excerpt("بِسْمِ  اللَّهِ\n الرَّحْمَٰنِ"), "بسم الله الرحمن")
        long = ("كلمة " * 1000)
        e = m.excerpt(long)
        self.assertTrue(e.endswith(" …"))
        self.assertLessEqual(len(e), m.MAX_CHARS + 2)
        self.assertFalse(m.excerpt("قصير").endswith("…"))

    def test_build(self):
        out = m.build_surah("t", 2, {"2:255": "نصٌّ", "2:1": "أ", "3:1": "ب"})
        self.assertEqual(set(out), {"ai-tafsir/v1/t/2/12.json", "ai-tafsir/v1/t/2/0.json"})
        self.assertEqual(json.loads(out["ai-tafsir/v1/t/2/12.json"]),
                         {"id": "t", "s": 2, "t": {"255": "نص"}})


if __name__ == "__main__":
    unittest.main()
