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
    def test_snap_cannot_push_accepted_boundary_beyond_strict_tol(self):
        # qeryo_qalun 3:164: مقبولٌ عند −1.4ث ثمّ دفعه الالتقاطُ إلى −1.9ث فردّته البوّابة.
        self.assertEqual(H.keep_snap_within_tol(4798300, 4797800, True, 4799700, 1500), (4798300, False))
        # التقاطٌ يبقى داخل التسامح يُقبل كما هو
        self.assertEqual(H.keep_snap_within_tol(4798300, 4798800, True, 4799700, 1500), (4798800, True))
        # بلا strict_ms (‏وضع heard في ctc_splice) لا يتغيّر شيء
        self.assertEqual(H.keep_snap_within_tol(4798300, 4797800, True, 4799700, 0), (4797800, True))
        # بلا مِرساة لا يتغيّر شيء
        self.assertEqual(H.keep_snap_within_tol(100, 700, True, None, 1500), (700, True))

    def test_anchor_tol_default_and_strict(self):
        # الافتراضُ كما كان: max(3ث، نصفُ مدّة المِرساة)؛ والصارمُ ثابتٌ يُعطى (الدفعةُ السماعيّة 1500)
        self.assertEqual(H.anchor_tol((0, 2000)), 3000)
        self.assertEqual(H.anchor_tol((0, 20000)), 10000)
        self.assertEqual(H.anchor_tol((0, 20000), 1500), 1500)

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

    def test_choose_chain_survives_spurious_early_match(self):
        # مطابقةٌ زائفةٌ مبكّرةٌ للرابعة لا تجرّ الأُوَل إلى «لم تُسمع»
        occ = [[(0, 10, 0.9)], [(12, 22, 0.9)], [(24, 34, 0.9)], [(3, 8, 0.6), (36, 46, 0.9)]]
        chosen = H.choose_chain(occ)
        self.assertEqual([c[0] for c in chosen], [0, 12, 24, 36])
        # وتُتخطّى آيةٌ بلا أداءٍ دون كسر السلسلة
        occ[1] = []
        self.assertEqual([c[0] if c else None for c in H.choose_chain(occ)], [0, None, 24, 36])

    def test_choose_chain_leaves_unheard_none(self):
        heard, _ = _heard([A1, "ههههههههههههههههههههه", A3])
        chosen = H.choose_chain([H.occurrences(a, heard) for a in (A1, A2, A3)])
        self.assertIsNotNone(chosen[0]); self.assertIsNone(chosen[1]); self.assertIsNotNone(chosen[2])

    def test_global_anchors_monotone_with_noise_extra_and_repeat(self):
        # دعاءٌ زائد · الآيات بأخطاءٍ متناثرة · إعادةُ الثانية · ذيلٌ زائد
        noisy2 = A2[:5] + "ق" + A2[6:15] + A2[16:]
        heard, times = _heard(["هههههههههههههههههه", A1, noisy2, A2, A3[:12] + "ك" + A3[13:], A4, "هههههه"])
        anc = H.global_anchors(heard, times, [A1, A2, A3, A4], frame_ms=80)
        self.assertTrue(all(anc))
        self.assertTrue(all(anc[k][1] <= anc[k + 1][0] + 80 for k in range(3)))
        self.assertGreaterEqual(anc[0][0], 18 * 80)                 # لا تُنسب الزيادةُ إلى الأولى
        self.assertTrue(all(a[2] >= 0.8 for a in anc), anc)
        self.assertLess(anc[1][0], times[len("هههههههههههههههههه") + len(A1) + len(noisy2)])

    def test_global_anchors_low_quality_when_unrelated(self):
        heard, times = _heard(["ههقكمصهههقكمصهههقكمصهههقكمصهههقكمصههه"])
        anc = H.global_anchors(heard, times, [A1, A2], frame_ms=80)
        self.assertTrue(all(a is None or a[2] < 0.5 for a in anc))

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
