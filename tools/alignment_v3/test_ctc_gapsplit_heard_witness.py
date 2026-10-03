# -*- coding: utf-8 -*-
"""اختباراتُ شاهد السماع لحدّ المدّة الأعلى في ctc_gapsplit (fixS2 · 2026-10-03):
يُقبل ما فوق 2× **فقط** بمِرساةٍ قويّةٍ منفردةٍ يوافقها الحدّان بفرقٍ مقيس، وما سواه يُردّ."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ctc_gapsplit as G  # noqa: E402

# 55:64 عند العفاسي: مسموعةٌ 551526–558571 (خريطة 37105... · fixS2) والمتوقَّع بالحروف 3190م.ث
H = {"heardMap": {"64": {"anchorMs": [551526, 558571], "anchorQuality": 0.875, "heard": True,
                         "occurrences": [[551526, 558571, 0.875]]}}}
EXP = 3190


class Witness(unittest.TestCase):
    def test_accepts_agreeing_bounds(self):
        ok, why = G.heard_witness_ok(H, 64, 551900, 558900, EXP)
        self.assertTrue(ok, why)

    def test_no_heard_map(self):
        self.assertFalse(G.heard_witness_ok(None, 64, 551526, 558571, EXP)[0])

    def test_unknown_ayah(self):
        self.assertFalse(G.heard_witness_ok(H, 65, 551526, 558571, EXP)[0])

    def test_weak_anchor(self):
        h = {"heardMap": {"64": dict(H["heardMap"]["64"], anchorQuality=0.84)}}
        self.assertFalse(G.heard_witness_ok(h, 64, 551526, 558571, EXP)[0])

    def test_not_heard(self):
        h = {"heardMap": {"64": dict(H["heardMap"]["64"], heard=False)}}
        self.assertFalse(G.heard_witness_ok(h, 64, 551526, 558571, EXP)[0])

    def test_repeated_performance(self):
        h = {"heardMap": {"64": dict(H["heardMap"]["64"],
                                      occurrences=[[551526, 558571, 0.875], [600000, 607000, 0.72]])}}
        self.assertFalse(G.heard_witness_ok(h, 64, 551526, 558571, EXP)[0])

    def test_weak_second_occurrence_ignored(self):
        h = {"heardMap": {"64": dict(H["heardMap"]["64"],
                                      occurrences=[[551526, 558571, 0.875], [82134, 91040, 0.6]])}}
        self.assertTrue(G.heard_witness_ok(h, 64, 551526, 558571, EXP)[0])

    def test_start_off(self):
        self.assertFalse(G.heard_witness_ok(H, 64, 551526 + 701, 558571, EXP)[0])
        self.assertFalse(G.heard_witness_ok(H, 64, 551526 - 701, 558571, EXP)[0])

    def test_end_off(self):
        self.assertFalse(G.heard_witness_ok(H, 64, 551526, 558571 + 1001, EXP)[0])

    def test_tolerance_edges_inclusive(self):
        self.assertTrue(G.heard_witness_ok(H, 64, 551526 + 700, 558571 - 1000, EXP)[0])

    def test_absolute_cap(self):
        h = {"heardMap": {"64": dict(H["heardMap"]["64"], anchorMs=[0, 20000])}}
        self.assertFalse(G.heard_witness_ok(h, 64, 0, 20000, 3000)[0])

    def test_constants_not_loosened(self):
        # ⛔ الشاهدُ لا يمسّ سائرَ الحرّاس
        self.assertEqual((G.MIN_CONF, G.DUR_LO, G.DUR_HI, G.NEIGH_LO), (0.45, 0.5, 2.0, 0.5))
        self.assertLessEqual(G.HW_START_TOL, 700)
        self.assertLessEqual(G.HW_END_TOL, 1000)
        self.assertGreaterEqual(G.HW_MIN_Q, 0.85)


if __name__ == "__main__":
    unittest.main()
