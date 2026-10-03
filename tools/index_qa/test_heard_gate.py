#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""اختباراتُ بوّابة السماع (‏heard_gate) — تُشغَّل قبل كلّ استعمال في heard_gate.yml وctc_splice heard_batch."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import heard_gate as H  # noqa: E402


def ent(s, a, st, en=None, ref="https://h/001.mp3"):
    return {"ayahId": f"{s}:{a}", "startMs": st, "endMs": en if en is not None else st + 1000, "fileRef": ref}


def cmap(anchors, sha="aa", ref="https://h/001.mp3"):
    """anchors: {آية: (بدء، جودة، [أداءاتٌ أخرى (بدء، تشابه)])}"""
    return {"sha256": sha, "fileRef": ref,
            "anchors": {str(a): [[v[0], v[0] + 900], v[1], [[o[0], o[0] + 900, o[1]] for o in (v[2] if len(v) > 2 else [])]]
                        for a, v in anchors.items()}}


class Rows(unittest.TestCase):
    def test_exact_passes(self):
        rows = H.surah_rows({1: 1000, 2: 5000, 3: 9000}, cmap({1: (1100, .9), 2: (5200, .8), 3: (9000, .7)}))
        self.assertIsNone(H.surah_verdict(rows))

    def test_boundary_1500_ok_1501_dev(self):
        rows = H.surah_rows({1: 1000, 2: 6501}, cmap({1: (2500, .9), 2: (5000, .9)}))
        self.assertEqual([r["status"] for r in rows], ["ok", "dev"])
        self.assertIn("الآية 2", H.surah_verdict(rows))

    def test_compressed_tail_rejected(self):
        # ذيلٌ مكبوس: الآياتُ 4–6 منشورةٌ قبل موضعها المسموع بعشرات الثواني
        st = {1: 0, 2: 10000, 3: 20000, 4: 22000, 5: 23000, 6: 24000}
        an = {1: (100, .9), 2: (10100, .9), 3: (20100, .9), 4: (60000, .9), 5: (90000, .9), 6: (120000, .9)}
        why = H.surah_verdict(H.surah_rows(st, cmap(an)))
        self.assertIn("3 آيةً تنحرف", why)

    def test_repeat_exception(self):
        # البدءُ المنشور على أداءٍ آخرَ مسموعٍ للآية نفسِها (تشابه ≥0.7 وقُربٌ ≤2ث) ⇒ تكرار لا انحراف
        rows = H.surah_rows({1: 50000}, cmap({1: (10000, .9, [(49000, .8)])}))
        self.assertEqual(rows[0]["status"], "repeat")
        self.assertIsNone(H.surah_verdict(rows))

    def test_weak_repeat_not_excused(self):
        rows = H.surah_rows({1: 50000}, cmap({1: (10000, .9, [(49000, .6)])}))
        self.assertEqual(rows[0]["status"], "dev")
        rows = H.surah_rows({1: 50000}, cmap({1: (10000, .9, [(47000, .9)])}))
        self.assertEqual(rows[0]["status"], "dev")

    def test_low_quality_unmeasured_and_majority_rule(self):
        rows = H.surah_rows({1: 0, 2: 1000, 3: 2000, 4: 3000}, cmap({1: (0, .9), 2: (1000, .4), 3: (2000, .3), 4: (3000, .9)}))
        self.assertEqual(sum(r["status"] == "unmeasured" for r in rows), 2)
        self.assertIsNone(H.surah_verdict(rows))          # نصفٌ مقيس يكفي
        rows = H.surah_rows({1: 0, 2: 1000, 3: 2000}, cmap({1: (0, .9), 2: (1000, .4), 3: (2000, .3)}))
        self.assertIn("أقلُّ من النصف", H.surah_verdict(rows))

    def test_unheard_tail_rejected(self):
        st = {a: a * 1000 for a in range(1, 11)}
        an = {a: (a * 1000, .9) for a in range(1, 8)}
        an.update({8: (8000, .2), 9: (9000, .1), 10: (10000, .1)})
        self.assertIn("ذيلٌ غيرُ مقيس", H.surah_verdict(H.surah_rows(st, cmap(an))))
        an[8] = (8000, .9)                                 # آيتان فقط غيرُ مقيستين ⇒ يمرّ
        self.assertIsNone(H.surah_verdict(H.surah_rows(st, cmap(an))))

    def test_missing_anchor_record_unmeasured(self):
        rows = H.surah_rows({1: 0, 2: 1000}, {"anchors": {"1": [[0, 500], .9, []]}})
        self.assertEqual(rows[1]["status"], "unmeasured")


class Judge(unittest.TestCase):
    def setUp(self):
        self.pub = {"entries": [ent(1, 1, 0), ent(1, 2, 5000), ent(2, 1, 0, ref="https://h/002.mp3"),
                                ent(2, 2, 4000, ref="https://h/002.mp3")]}
        self.cand = {"entries": [ent(1, 1, 0), ent(1, 2, 9000), ent(2, 1, 0, ref="https://h/002.mp3"),
                                 ent(2, 2, 4000, ref="https://h/002.mp3")],
                     "audioSha256": ["aa", "bb"]}
        self.good = {1: cmap({1: (0, .9), 2: (9000, .9)}),
                     2: cmap({1: (0, .9), 2: (4000, .9)}, sha="bb", ref="https://h/002.mp3")}

    def test_modified_and_sample(self):
        self.assertEqual(H.modified_surahs(self.cand["entries"], self.pub["entries"]), [1])
        j = H.judge(self.cand, self.pub, "x" * 64, self.good)
        self.assertEqual(j["modified"], [1])
        self.assertEqual(j["sample"], [2])
        self.assertTrue(j["ok"], j["reason"])

    def test_sample_deterministic_by_sha(self):
        pool = list(range(1, 115))
        self.assertEqual(H.sample_surahs("ab" * 32, pool), H.sample_surahs("ab" * 32, pool))
        self.assertNotEqual(H.sample_surahs("ab" * 32, pool), H.sample_surahs("cd" * 32, pool))
        self.assertEqual(len(H.sample_surahs("ab" * 32, pool)), H.SAMPLE_K)

    def test_missing_map_rejects(self):
        j = H.judge(self.cand, self.pub, "x" * 64, {1: self.good[1]})
        self.assertFalse(j["ok"])
        self.assertIn("لا خريطةَ سماع", j["reason"])

    def test_wrong_audio_sha_rejects(self):
        bad = dict(self.good)
        bad[1] = dict(self.good[1], sha256="zz")
        j = H.judge(self.cand, self.pub, "x" * 64, bad)
        self.assertFalse(j["ok"])
        self.assertIn("غيرُ صوت المرشّح", j["reason"])

    def test_wrong_file_rejects(self):
        bad = dict(self.good)
        bad[1] = dict(self.good[1], fileRef="https://other/001.mp3")
        self.assertFalse(H.judge(self.cand, self.pub, "x" * 64, bad)["ok"])

    def test_sampled_unmodified_deviation_rejects(self):
        bad = dict(self.good)
        bad[2] = cmap({1: (0, .9), 2: (30000, .9)}, sha="bb", ref="https://h/002.mp3")
        j = H.judge(self.cand, self.pub, "x" * 64, bad)
        self.assertFalse(j["ok"])
        self.assertIn("(عيّنة)", j["reason"])

    def test_gate_error_recomputes_not_trusts(self):
        sha = "x" * 64
        forged = {"sha256": sha, "ok": True, "verdict": "مقبول",
                  "maps": {"1": cmap({1: (0, .9), 2: (40000, .9)}), "2": self.good[2]}}
        self.assertIn("بوّابةُ السماع", H.gate_error(self.cand, self.pub, sha, forged))
        good = {"sha256": sha, "maps": {str(k): v for k, v in self.good.items()}}
        self.assertIsNone(H.gate_error(self.cand, self.pub, sha, good))
        self.assertIn("بصمةٍ أخرى", H.gate_error(self.cand, self.pub, "y" * 64, good))
        self.assertIn("لا حكمَ سماع", H.gate_error(self.cand, self.pub, sha, None))

    def test_report_parser(self):
        txt = ("# خريطةُ السماع س1 · 100م.ث\n# آية\n"
               "1:1\t1.0\t2.0\t0.9\t1.0\t2.0\t0.9\t50–52s(0.8)\n"
               "1:2\t—\t—\t—\t—\t—\t—\t\n")
        m = H.map_from_report(txt)
        self.assertEqual(m["anchors"]["1"][0], [1000, 2000])
        self.assertEqual(m["anchors"]["1"][2][-1], [50000, 52000, 0.8])
        self.assertIsNone(m["anchors"]["2"][0])


class PromoteHook(unittest.TestCase):
    """promote.heard_gate_check: الغيابُ ردٌّ متى خالف المرشّحُ المنشور، ولا شيءَ يلزم الإسقاطَ المحض."""
    def _cl(self, objs):
        import gzip
        import io
        import json

        class C:
            def get_object(self, Bucket, Key):
                if Key not in objs:
                    raise KeyError(Key)
                v = objs[Key]
                b = gzip.compress(json.dumps(v).encode()) if Key.endswith(".jz") else json.dumps(v).encode()
                return {"Body": io.BytesIO(b)}
        return C()

    def test_hook(self):
        import promote as P
        j = Judge()
        j.setUp()
        src, pubk, sha = "timings-staging/hafs/x.12345678.jz", "timings/hafs/x.jz", "x" * 64
        cl = self._cl({pubk: j.pub})
        self.assertIn("لا حكمَ سماع", P.heard_gate_check(cl, "b", src, sha, j.cand, pubk))
        self.assertIsNone(P.heard_gate_check(cl, "b", src, sha, j.pub, pubk))   # لا سورةَ معدّلة
        good = {"sha256": sha, "maps": {str(k): v for k, v in j.good.items()}}
        cl = self._cl({pubk: j.pub, H.state_key(src): good})
        self.assertIsNone(P.heard_gate_check(cl, "b", src, sha, j.cand, pubk))


if __name__ == "__main__":
    unittest.main()
