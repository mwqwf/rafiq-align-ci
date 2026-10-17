# -*- coding: utf-8 -*-
import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import extend_tail as x


class DecideTest(unittest.TestCase):
    def test_extends_when_at_header_and_speech(self):
        self.assertTrue(x.decide(4253777, 4253777, 4273716, -17.0)[0])

    def test_extends_when_slightly_below_header(self):
        # لحوني 37:182 (‏58م.ث دون الترويسة) و42:53 (‏206م.ث) مقصوصتان بالعلّة نفسها
        self.assertTrue(x.decide(1148242, 1148300, 1153700, -26.8)[0])
        self.assertTrue(x.decide(1025094, 1025300, 1030100, -24.6)[0])

    def test_refuses_when_far_below_header(self):
        self.assertFalse(x.decide(4251000, 4253777, 4273716, -17.0)[0])

    def test_31_34_correct_stays(self):
        self.assertFalse(x.decide(643500, 643500, 646000, -17.0)[0])

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
