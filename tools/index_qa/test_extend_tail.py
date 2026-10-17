# -*- coding: utf-8 -*-
import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import extend_tail as x


class DecideTest(unittest.TestCase):
    def test_extends_when_at_header_and_speech(self):
        self.assertTrue(x.decide(4253777, 4253777, 4273716, -17.0)[0])

    def test_refuses_when_end_not_at_header(self):
        self.assertFalse(x.decide(4267554, 4253777, 4273716, -17.0)[0])

    def test_refuses_small_gain(self):
        self.assertFalse(x.decide(1000000, 1000000, 1002000, -17.0)[0])

    def test_refuses_silent_tail(self):
        self.assertFalse(x.decide(1000000, 1000000, 1020000, -50.0)[0])
        self.assertFalse(x.decide(1000000, 1000000, 1020000, None)[0])

    def test_last_entry_per_surah(self):
        es = [{"ayahId": "3:199", "endMs": 5}, {"ayahId": "3:200", "endMs": 9}, {"ayahId": "4:1", "endMs": 1}]
        self.assertEqual(x.last_entries(es, {3})[3]["ayahId"], "3:200")
        self.assertNotIn(4, x.last_entries(es, {3}))


if __name__ == "__main__":
    unittest.main()
