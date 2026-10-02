# -*- coding: utf-8 -*-
"""اختباراتُ الدوالّ المحضة في `ctc_heard_map.py` — بلا نموذجٍ ولا شبكة."""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "alignment"))

import ctc_heard_map as H  # noqa: E402

A1 = "صوالقرانذيالذكر"
A2 = "بلالذينكفروافيعزهوشقاق"
A3 = "كماهلكنامنقبلهممنقرنفنادواولاتحينمناص"
A4 = "وعجبواانجاهممنذرمنهموقالالكافرونهذاساحركذاب"


def _heard(parts):
    """هيكلٌ مسموعٌ مصطنع: كلُّ حرفٍ 80م.ث، والأجزاءُ تفصلها «ضجّةٌ» لا تشبه شيئاً."""
    s = "".join(parts)
    return s, [i * 80 for i in range(len(s))]


class Pure(unittest.TestCase):
    def test_skeleton_maps_like_norm(self):
        chars = [("ب", 0), ("س", 10), ("م", 20), (" ", 30), ("ٱ", 40), ("ل", 50), ("ل", 60), ("ه", 70),
                 ("ء", 80), ("ة", 90), ("1", 100)]
        sk, ts = H.skeleton(chars)
        self.assertEqual(sk, "بسماللهه")
        self.assertEqual(ts, [0, 10, 20, 40, 50, 60, 70, 90])

    def test_greedy_decode_collapses_repeats_and_blank(self):
        import numpy as np
        # الرموز: 0 فراغ · 1 «ب» · 2 «|» · 3 «س»
        lpz = np.log(np.array([[.9, .1, 0, 0], [.1, .9, 0, 0], [.1, .9, 0, 0], [.9, .1, 0, 0],
                               [0, 0, .9, .1], [.1, .9, 0, 0], [0, 0, 0, 1.]]) + 1e-9)
        got = H.greedy_decode(lpz, 20.0, [None, "ب", "|", "س"], 0)
        self.assertEqual(got, [("ب", 20), (" ", 80), ("ب", 100), ("س", 120)])

    def test_occurrences_finds_repeated_performance(self):
        heard, _ = _heard([A1, A2, "ههههههه", A2, A3])
        occ = H.occurrences(A2, heard)
        self.assertEqual(len(occ), 2, occ)
        self.assertLess(occ[0][0], occ[1][0])
        self.assertTrue(all(o[2] >= H.MIN_OCC for o in occ))
        self.assertEqual(H.occurrences("صو", heard), [])          # أقصرُ من ثلاثة حروف

    def test_occurrences_tolerates_noise(self):
        noisy = A3[:10] + "ق" + A3[12:]                            # حرفٌ مبدَّلٌ وحرفٌ محذوف
        heard, _ = _heard([A1, noisy, A4])
        occ = H.occurrences(A3, heard)
        self.assertEqual(len(occ), 1)
        self.assertGreaterEqual(occ[0][2], 0.85)

    def test_choose_chain_prefers_last_connected_performance(self):
        heard, times = _heard([A1, A2, A3, "ههههههه", A2, A3, A4])
        occ = [H.occurrences(a, heard) for a in (A1, A2, A3, A4)]
        chosen = H.choose_chain(occ)
        self.assertTrue(all(chosen))
        # الثانيةُ والثالثةُ من الأداء الثاني (‏المتّصل بالرابعة)، والأولى من موضعها الوحيد
        self.assertEqual(chosen[0][0], 0)
        self.assertGreater(chosen[1][0], len(A1) + len(A2) + len(A3))
        self.assertLess(chosen[1][1], chosen[2][0] + 6)
        self.assertLess(chosen[2][1], chosen[3][0] + 6)
        # ورتابةٌ تامّة
        self.assertTrue(all(chosen[k][1] <= chosen[k + 1][0] + 6 for k in range(3)))

    def test_choose_chain_leaves_unheard_none(self):
        heard, _ = _heard([A1, "ههههههههههههههههههههه", A3])
        chosen = H.choose_chain([H.occurrences(a, heard) for a in (A1, A2, A3)])
        self.assertIsNotNone(chosen[0]); self.assertIsNone(chosen[1]); self.assertIsNotNone(chosen[2])

    def test_plan_windows_caps_and_splits_on_gap(self):
        ms = [(k * 1000, k * 1000 + 900) for k in range(30)]
        self.assertEqual(H.plan_windows(ms, 30, max_ayat=12), [(0, 11), (12, 23), (24, 29)])
        ms[10] = (60000, 60900)                                      # فجوةٌ كبيرةٌ قبل الحادية عشرة
        for k in range(11, 30):
            ms[k] = (60000 + (k - 10) * 1000, 60900 + (k - 10) * 1000)
        self.assertEqual(H.plan_windows(ms, 30, max_ayat=12)[0], (0, 9))
        ms[5] = None                                                 # غيرُ مسموعةٍ لا تقطع
        self.assertEqual(H.plan_windows(ms, 30, max_ayat=12)[0], (0, 9))

    def test_chunk_map_names_nearest_ayah(self):
        heard, times = _heard([A1, A2, A3, A4])
        chunks = H.chunk_map(heard, times, [A1, A2, A3, A4], chunk_ms=len(A1) * 80)
        self.assertEqual(chunks[0][2], 0)
        self.assertGreaterEqual(chunks[0][3], 0.9)


class Wiring(unittest.TestCase):
    """المحرّكُ معلَنٌ في سجلّ الحُرّاس الواحد وفي سير الدمج — فلا يتسلّل دمجٌ بلا إحصاء."""
    ROOT = os.path.dirname(os.path.dirname(HERE))

    def test_splice_ops_declares_engine(self):
        sys.path.insert(0, os.path.join(self.ROOT, "tools", "index_qa"))
        import promote
        self.assertEqual(promote.SPLICE_OPS["ctc_heardmap_splice"], H.ENGINE)

    def test_ctc_splice_workflow_heard_mode(self):
        y = open(os.path.join(self.ROOT, ".github/workflows/ctc_splice.yml"), encoding="utf-8").read()
        self.assertIn('if [ "$MODE" = "heard" ]; then ETAG="ctc-heardmap-1"; fi', y)
        self.assertIn('OPN="ctc_heardmap_splice"', y)
        self.assertIn("tools/alignment_v3/ctc_heard_map.py --url", y)
        self.assertIn("rapidfuzz", y)


if __name__ == "__main__":
    unittest.main()
