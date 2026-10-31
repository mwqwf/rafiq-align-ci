#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""اختباراتُ وضع `--absent-ayahs` (أمر المالك 2026-10-31): منطقُ النافذة والحرّاس والدليل بمحاذٍ مُحقَن
(بلا نموذج ولا صوت)، ثمّ التقاؤه بـ`drop_ayahs` و`promote.declared_truncated_gaps`.

    python -m unittest tools/alignment_v3/test_ctc_gapsplit_absent.py
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "index_qa"))
import ctc_gapsplit as G  # noqa: E402
import drop_ayahs  # noqa: E402
import promote  # noqa: E402

S, N = 79, 46
# نصوصٌ مصطنعة: كلُّ آيةٍ 40 حرفاً ⇒ المتوقَّع 4000م.ث عند معدّل 100م.ث/حرف
TXT = {k: "ا" * 40 for k in range(1, N + 1)}
t_of = lambda k: TXT[k]  # noqa: E731


def ents0():
    # حدودٌ «معصورة» كالمحاذي القديم: 14 طويلة، والغائبات 15/17/18 قصيرات، 19 طويلة
    b = {14: (47600, 50700), 15: (50700, 51200), 16: (51200, 53700), 17: (53700, 54700),
         18: (54700, 55500), 19: (55500, 57700), 20: (57700, 61400)}
    out = {}
    for k in range(1, N + 1):
        out[k] = {"ayahId": f"{S}:{k}", "fileRef": "f", "confBand": "HIGH", "conf": 0.9,
                  "startMs": b.get(k, (k * 3000, k * 3000 + 900) if k < 14 else (61400 + k * 1000, 62300 + k * 1000))[0],
                  "endMs": b.get(k, (k * 3000, k * 3000 + 900) if k < 14 else (61400 + k * 1000, 62300 + k * 1000))[1]}
    return out


def fake_align(good, full_conf, pts=(None, 50700, 51200, 53700, 54700, 55500, None)):
    """good: حدودُ الحاضرات {14,16,19} بنصوصها وحدها؛ full_conf: ثقةُ كلّ آيةٍ في المحاذاة الكاملة؛ pts: حدودُها."""
    def align(ws, we, texts):
        if len(texts) == 3:
            return [(ws, good[0], 0.9), (good[0], good[1], 0.8), (good[1], we, 0.8)]
        # كاملةٌ: 14 | 15 | 16 | 17 | 18 | 19
        p = [ws if v is None and i == 0 else we if v is None else v for i, v in enumerate(pts)]
        return [(p[i], p[i + 1], full_conf[i]) for i in range(6)]
    return align


class Clusters(unittest.TestCase):
    def test_one_window_and_bounds(self):
        c = G.absent_clusters([15, 17, 18], N, ents0())
        self.assertEqual(c, [(14, 19, [15, 17, 18])])

    def test_far_apart_two_windows(self):
        c = G.absent_clusters([5, 30], N, ents0())
        self.assertEqual([(lo, hi) for lo, hi, _ in c], [(4, 6), (29, 31)])

    def test_first_last_refused(self):
        for bad in ([1, 5], [5, N]):
            with self.assertRaises(ValueError):
                G.absent_clusters(bad, N, ents0())

    def test_parse(self):
        self.assertEqual(G.parse_absent_spec("79:15, 79:17,79:18"), {79: [15, 17, 18]})
        with self.assertRaises(ValueError):
            G.parse_absent_spec("79:15,79:15")


class Window(unittest.TestCase):
    def run_win(self, good, full_conf, pts=(None, 50700, 51200, 53700, 54700, 55500, None)):
        ents = ents0()
        return G.align_absent_window(None, S, 14, 19, [15, 17, 18], ents, t_of, 100.0,
                                     align=fake_align(good, full_conf, pts))

    def test_accept_neighbours_retimed_and_evidence(self):
        # 14: 47600–50700 · 16: 50800–54600 (3.8ث) · 19: 54600–57700 (آخرُها من الأب)
        r, ev, why = self.run_win((50700, 54600), [0.9, 0.2, 0.8, 0.2, 0.2, 0.8])
        self.assertIsNone(why, why)
        self.assertEqual(r["79:14"]["startMs"], 47600)          # بدءُ النافذة من الأب
        self.assertEqual((r["79:16"]["startMs"], r["79:16"]["endMs"]), (50700, 54600))
        self.assertEqual((r["79:19"]["startMs"], r["79:19"]["endMs"]), (54600, 57700))
        self.assertEqual(sorted(ev), ["79:15", "79:17", "79:18"])
        for e in ev.values():
            self.assertEqual(e["method"], "ctc_window")
            self.assertIn("ثقة", e["detail"])

    def test_absent_that_passes_guards_is_heard_not_absent(self):
        # الغائبةُ 15 نالت ثقةً 0.9 ومدّةً 3500م.ث (ضمن 0.5–2×) ⇒ مسموعة ⇒ ترفض السورة
        r, ev, why = self.run_win((50700, 54600), [0.9, 0.9, 0.8, 0.2, 0.2, 0.8],
                                  pts=(None, 50700, 54200, 54300, 54400, 54600, None))
        self.assertIsNone(r)
        self.assertIn("79:15", why)
        self.assertIn("مسموعةٌ", why)

    def test_neighbours_alone_rejected(self):
        # 16 بثقة 0.3 بنصّها وحدها ⇒ ردٌّ بحارس الثقة، لا تخفيف
        def align(ws, we, texts):
            return [(ws, 50700, 0.9), (50700, 54600, 0.3), (54600, we, 0.8)]
        r, ev, why = G.align_absent_window(None, S, 14, 19, [15, 17, 18], ents0(), t_of, 100.0, align=align)
        self.assertIsNone(r)
        self.assertIn("ثقةُ CTC", why)

    def test_neighbour_shrink_guard(self):
        # 19 تنكمش دون 0.5× بنصّها وحدها
        r, ev, why = self.run_win((50700, 56000), [0.9, 0.2, 0.8, 0.2, 0.2, 0.8])
        self.assertIsNone(r)
        self.assertIn("تنكمش", why)


class WithDrop(unittest.TestCase):
    """التقاءُ المخرَج بـdrop_ayahs وبوّابة الترقية."""

    def idx(self):
        ents = ents0()
        return {"riwaya": "hafs", "reciterId": "x", "ayahCount": 6236, "engineVersion": "align-0.2",
                "entries": list(ents.values()),
                "missing": {"count": 6236 - N, "byReason": {"unknown": 6236 - N},
                            "ids": [f"{s}:{a}" for s in range(1, 115) if s != S
                                    for a in range(1, promote._AYAH_COUNTS[s - 1] + 1)]}}

    def make(self, retimed=None):
        r, ev, why = G.align_absent_window(None, S, 14, 19, [15, 17, 18], ents0(), t_of, 100.0,
                                           align=fake_align((50700, 54600), [0.9, 0.2, 0.8, 0.2, 0.2, 0.8]))
        self.assertIsNone(why)
        return drop_ayahs.drop_ayahs(
            self.idx(), {S: [15, 17, 18]}, ev, reason="قياس CTC", reason_user="تسجيلُ هذه السورة ينقصه بعضُ آياتها.",
            reason_code="SOURCE_TRUNCATED", from_sha="a" * 64, from_key="timings/hafs/x.jz",
            retimed=retimed if retimed is not None else r)

    def test_end_to_end_passes_promote_gate(self):
        out = self.make()
        ok, why = promote.declared_truncated_gaps(out, S)
        self.assertTrue(ok, why)
        byid = {e["ayahId"]: e for e in out["entries"]}
        self.assertEqual((byid["79:16"]["startMs"], byid["79:16"]["endMs"]), (50700, 54600))
        self.assertEqual(byid["79:19"]["startMs"], 54600)
        self.assertEqual(byid["79:19"]["endMs"], 57700)          # نهايةُ النافذة لم تتحرّك
        self.assertEqual(byid["79:20"]["startMs"], 57700)        # ما خارج النافذة لم يُمسّ
        self.assertEqual(out["engineBySurah"]["79"], "ctc-gapsplit-1")
        self.assertIn("79", promote.census_surahs(out))          # ⇒ يلزمه الإحصاءُ الشامل
        self.assertEqual(out["transform"]["retimedNeighbours"], ["79:14", "79:16", "79:19"])
        self.assertEqual(len(out["entries"]) + out["missing"]["count"], 6236)

    def test_without_retimed_boundaries_untouched(self):
        out = self.make(retimed={})
        self.assertNotIn("retimedNeighbours", out["transform"])
        self.assertNotIn("engineBySurah", out)

    def test_refuses_retiming_outside_window_or_absent(self):
        for key in ("79:20", "79:15", "79:30"):
            with self.assertRaises(SystemExit):
                self.make(retimed={key: {"startMs": 1, "endMs": 5}})

    def test_refuses_window_edge_move(self):
        with self.assertRaises(SystemExit):
            self.make(retimed={"79:14": {"startMs": 47000, "endMs": 50700},
                               "79:16": {"startMs": 50700, "endMs": 54600},
                               "79:19": {"startMs": 54600, "endMs": 57700}})
        with self.assertRaises(SystemExit):
            self.make(retimed={"79:19": {"startMs": 54600, "endMs": 58000}})

    def test_refuses_overlap(self):
        with self.assertRaises(SystemExit):
            self.make(retimed={"79:16": {"startMs": 50700, "endMs": 54600},
                               "79:19": {"startMs": 54000, "endMs": 57700}})


if __name__ == "__main__":
    unittest.main()
