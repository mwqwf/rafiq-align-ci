# -*- coding: utf-8 -*-
"""اختباراتُ دمج الحدود بما اتّفق عليه النموذجان: الاتّفاقُ يؤخذ، والخلافُ والضعفُ يُبقيان حدَّ المرشّح،
والمدّةُ الشاذّةُ تُردّ، والرتابةُ والاتّصالُ محفوظان، والتوصيلُ بسير العمل وpromote والدمج قائم."""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import ctc_dualfix as F
import window_census_witness as X

RATE = 100
CHARS = [40, 50, 60, 45, 55]


def base_bounds():
    out, t = [], 1000
    for c in CHARS:
        out.append([t, t + RATE * c]); t += RATE * c
    return out


def meas_for(bounds, conf=0.8, shift=0, dq=(0, 0)):
    """قياسُ النموذجين لآيةٍ واحدة: العامُّ عند الحدود المزاحة والقرآنيُّ بفرق dq عنه."""
    s, e = bounds[0] + shift, bounds[1] + shift
    return {"generic": (s, e, conf), "quran": (s + dq[0], e + dq[1], conf)}


class FuseTest(unittest.TestCase):
    def setUp(self):
        self.base = base_bounds()

    def test_no_measurement_keeps_candidate_contiguous(self):
        b, src, d = F.fuse(self.base, [None] * 5, CHARS, RATE)
        self.assertEqual(b, self.base); self.assertEqual(set(src), {"base"})

    def test_agreed_shift_is_taken_and_neighbours_follow_the_boundary(self):
        m = [None, None, meas_for(self.base[2], shift=1500), None, None]
        b, src, d = F.fuse(self.base, m, CHARS, RATE)
        self.assertEqual(b[2], [self.base[2][0] + 1500, self.base[2][1] + 1500])
        self.assertEqual(b[1][1], b[2][0]); self.assertEqual(b[3][0], b[2][1])   # متّصل
        self.assertEqual(src[2], "agreed-start"); self.assertEqual(src[3], "agreed-end")
        self.assertEqual(b[0], self.base[0]); self.assertEqual(b[4], self.base[4])
        self.assertTrue(all(b[k][1] > b[k][0] for k in range(5)))

    def test_disagreeing_or_weak_models_keep_candidate(self):
        for m in [meas_for(self.base[2], shift=1500, dq=(X.START_TOL + 1, 0)),
                  meas_for(self.base[2], shift=1500, dq=(0, X.END_TOL + 1)),
                  meas_for(self.base[2], shift=1500, conf=X.TARGET_CONF - 0.01),
                  {"generic": (1, 2, .9)}]:
            b, src, d = F.fuse(self.base, [None, None, m, None, None], CHARS, RATE)
            self.assertEqual(b, self.base, m); self.assertIsNone(d[2]["agreed"])

    def test_conflicting_neighbours_keep_candidate_boundary(self):
        # نهايةُ 2 المقيسة +1500 وبدايةُ 3 المقيسة −1500: خلافٌ على الحدّ نفسِه ⇒ حدُّ المرشّح
        m = [None, meas_for(self.base[1], shift=0), meas_for(self.base[2], shift=0), None, None]
        m[1] = {"generic": (self.base[1][0], self.base[1][1] + 1500, .8), "quran": (self.base[1][0], self.base[1][1] + 1500, .8)}
        m[2] = {"generic": (self.base[2][0] - 1500, self.base[2][1], .8), "quran": (self.base[2][0] - 1500, self.base[2][1], .8)}
        b, src, d = F.fuse(self.base, m, CHARS, RATE)
        self.assertEqual(src[2], "conflict-base"); self.assertEqual(b[1][1], self.base[1][1])
        # واتّفاقُهما يؤخذ وسطاً
        m[2] = {"generic": (self.base[2][0] + 1300, self.base[2][1], .8), "quran": (self.base[2][0] + 1300, self.base[2][1], .8)}
        b, src, d = F.fuse(self.base, m, CHARS, RATE)
        self.assertEqual(src[2], "agreed-both"); self.assertEqual(b[1][1], self.base[1][1] + 1400)

    def test_measured_duration_outside_bounds_is_reverted(self):
        # قياسٌ متّفقٌ يجعل الآية 3 ثلاثةَ أضعاف المتوقَّع ⇒ تُردّ حدودُها إلى المرشّح
        m = [None, None, {"generic": (self.base[2][0], self.base[2][0] + 3 * RATE * CHARS[2], .9),
                          "quran": (self.base[2][0], self.base[2][0] + 3 * RATE * CHARS[2], .9)}, None, None]
        b, src, d = F.fuse(self.base, m, CHARS, RATE)
        self.assertEqual(b, self.base); self.assertTrue(d[2]["reverted"])
        # وقياسٌ يبتلع الجارة (‏يجعلها سالبةً أو صفراً) لا يمرّ
        m = [None, None, {"generic": (self.base[2][0], self.base[3][1] + 10, .9),
                          "quran": (self.base[2][0], self.base[3][1] + 10, .9)}, None, None]
        b, src, d = F.fuse(self.base, m, CHARS, RATE)
        self.assertTrue(all(b[k][1] > b[k][0] for k in range(5)))

    def test_candidate_shifted_by_one_ayah_is_corrected_where_models_agree(self):
        """المرشّحُ المكبوس: الآيةُ 3 تحمل حدودَ الآية 2؛ النموذجان يسمعانها في موضعها الحقيقيّ."""
        true = self.base
        mid = (true[1][0] + true[1][1]) // 2
        wrong = [list(x) for x in true]
        wrong[1] = [true[1][0], mid]; wrong[2] = [mid, true[1][1]]; wrong[3] = [true[1][1], true[3][1]]
        # الحدودُ متّصلةٌ غيرُ متداخلةٍ لكنّها خطأ؛ القياسُ الحقيقيُّ للآيتين 2 و3
        m = [None, meas_for(true[1]), meas_for(true[2]), None, None]
        b, src, d = F.fuse(wrong, m, CHARS, RATE)
        self.assertEqual(b[1], true[1]); self.assertEqual(b[2], true[2])

    def test_wiring(self):
        root = pathlib.Path(F.__file__).parents[2]
        promote = (root / "tools" / "index_qa" / "promote.py").read_text(encoding="utf-8")
        self.assertIn('"ctc_dualfix_splice": "ctc-dualfix-1"', promote)
        splice = (root / "tools" / "index_qa" / "splice_surah.py").read_text(encoding="utf-8")
        self.assertIn("dualFixEvidenceBySurah", splice)
        wf = (root / ".github" / "workflows" / "ctc_splice.yml").read_text(encoding="utf-8")
        self.assertIn('if [ "$MODE" = "dualfix" ]; then ETAG="ctc-dualfix-1"; fi', wf)
        self.assertIn('OPN="ctc_dualfix_splice"', wf)
        self.assertIn("CTC_INT8=0 CTC_THREADS=2 python tools/alignment_v3/ctc_dualfix.py", wf)
        self.assertEqual(F.ENGINE, "ctc-dualfix-1")


if __name__ == "__main__":
    unittest.main()
