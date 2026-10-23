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
        j = H.judge(self.cand, self.pub, "x" * 64, {2: self.good[2]})
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

    def test_sample_is_report_only(self):
        # قرارُ المنسّق: العيّنةُ مطابقةٌ للمنشور حرفاً ⇒ انحرافُها يُسجَّل ولا يردّ
        bad = dict(self.good)
        bad[2] = cmap({1: (0, .9), 2: (30000, .9)}, sha="bb", ref="https://h/002.mp3")
        j = H.judge(self.cand, self.pub, "x" * 64, bad)
        self.assertTrue(j["ok"], j["reason"])
        self.assertTrue(any("(عيّنة)" in f for f in j["sampleFindings"]))
        j = H.judge(self.cand, self.pub, "x" * 64, {1: self.good[1]})     # عيّنةٌ بلا خريطة ⇒ تُسجَّل
        self.assertTrue(j["ok"])
        self.assertIn("لا خريطةَ سماع", j["sampleFindings"][0])

    def test_modified_deviation_rejects(self):
        bad = dict(self.good)
        bad[1] = cmap({1: (0, .9), 2: (30000, .9)})
        j = H.judge(self.cand, self.pub, "x" * 64, bad)
        self.assertFalse(j["ok"])
        self.assertIn("س1", j["reason"])

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


class AudioShaAfterDrop(unittest.TestCase):
    def _index(self, compact=False):
        # حذف السابعة يزيح ترتيب الحاضر دون أن يغيّر موضع الثامنة في القائمة الثابتة.
        present = [s for s in range(1, 115) if s != 7]
        shas = [f"{s:064x}" if s != 7 else "" for s in range(1, 115)]
        idx = {"entries": [ent(s, 1, 1000, ref=f"https://h/{s:03d}.mp3") for s in present],
               "audioSha256": [shas[s - 1] for s in present] if compact else shas}
        maps = {s: cmap({1: (1000, .9)}, sha=shas[s - 1], ref=f"https://h/{s:03d}.mp3")
                for s in present}
        return idx, maps

    def test_fixed_and_compact_lists_match_after_drop(self):
        for compact in (False, True):
            with self.subTest(compact=compact):
                idx, maps = self._index(compact)
                verdict = H.judge(idx, None, "x" * 64, maps)
                self.assertTrue(verdict["ok"], verdict["reason"])
                self.assertIn("8", verdict["surahs"])
                self.assertNotIn(7, verdict["required"])

    def test_wrong_heard_sha_rejects_after_drop(self):
        for compact in (False, True):
            with self.subTest(compact=compact):
                idx, maps = self._index(compact)
                maps[8]["sha256"] = "f" * 64
                verdict = H.judge(idx, None, "x" * 64, maps)
                self.assertFalse(verdict["ok"])
                self.assertIn("س8: الصوتُ المسموع", verdict["reason"])
                self.assertIn("غيرُ صوت المرشّح", verdict["reason"])
                self.assertNotIn("8", verdict["surahs"])

    def test_missing_or_invalid_candidate_sha_rejects_after_drop(self):
        for compact in (False, True):
            for missing in (None, "", "   ", 0, []):
                with self.subTest(compact=compact, missing=missing):
                    idx, maps = self._index(compact)
                    idx["audioSha256"][6 if compact else 7] = missing
                    verdict = H.judge(idx, None, "x" * 64, maps)
                    self.assertFalse(verdict["ok"])
                    self.assertIn("س8: لا بصمةَ صوتٍ صالحة", verdict["reason"])

    def test_absent_or_invalid_sha_list_rejects(self):
        for malformed in (None, "a" * 64, {}, [], ["a" * 64] * 112, ["a" * 64] * 115):
            with self.subTest(malformed=malformed):
                idx, maps = self._index()
                if malformed is None:
                    del idx["audioSha256"]
                else:
                    idx["audioSha256"] = malformed
                verdict = H.judge(idx, None, "x" * 64, maps)
                self.assertFalse(verdict["ok"])
                self.assertIn("لا بصمةَ صوتٍ صالحة", verdict["reason"])

    def test_missing_heard_sha_rejects_after_drop(self):
        for compact in (False, True):
            for missing in (None, ""):
                with self.subTest(compact=compact, missing=missing):
                    idx, maps = self._index(compact)
                    if missing is None:
                        del maps[8]["sha256"]
                    else:
                        maps[8]["sha256"] = missing
                    verdict = H.judge(idx, None, "x" * 64, maps)
                    self.assertFalse(verdict["ok"])
                    self.assertIn("س8: الصوتُ المسموع", verdict["reason"])

    def test_gate_recomputes_wrong_sha_after_drop(self):
        idx, maps = self._index()
        pub = {"entries": [dict(e) for e in idx["entries"]]}
        pub["entries"][6]["startMs"] = 0
        maps[8]["sha256"] = "f" * 64
        forged = {"sha256": "x" * 64, "ok": True, "maps": maps}
        self.assertIn("غيرُ صوت المرشّح", H.gate_error(idx, pub, "x" * 64, forged))
        # العيّنة غير المعدّلة تظل للتقرير وحده، لكن بصمتها الخاطئة تُسجّل.
        verdict = H.judge(idx, {"entries": idx["entries"]}, "x" * 64,
                          {s: dict(m, sha256="f" * 64) for s, m in maps.items()})
        self.assertTrue(verdict["ok"], verdict["reason"])
        self.assertEqual(len(verdict["sampleFindings"]), H.SAMPLE_K)
        self.assertTrue(all("غيرُ صوت المرشّح" in finding for finding in verdict["sampleFindings"]))


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


# ⭐ تشديد 2026-10-23: «الأداءُ البديل» لا يكون داخلَ مدى المِرساة. حالاتٌ حقيقيةٌ من تحقّقٍ مستقلّ
# (‏S/vf/results2.jsonl): (آية، بدءٌ منشور، مِرساة [بدء، نهاية]، أداءٌ [بدء، نهاية، تشابه]، |الإزاحة المسموعة| بالثواني).
LATE_INSIDE_ANCHOR = [
    ("9:1", 4500, [620, 15009], [4683, 15009, .949], 1.9),
    ("14:17", 355140, [352013, 370125], [355395, 369144, .933], 3.42),
    ("68:7", 34180, [29760, 44731], [35104, 44731, .949], 4.74),
    ("2:185", 3473620, [3466100, 3519916], [3475286, 3515313, .891], 8.0),
    ("3:45", 1004350, [998907, 1023564], [1004571, 1022143, .921], 5.52),
    ("14:40", 779280, [773658, 790069], [780983, 789949, .767], 10.64),
    ("26:59", 585800, [573748, 592300], [586576, 590419, .718], 12.06),
    # سليمةٌ فعلاً (‏إزاحة <1ث) لكنّ مِرساتها واسعة: تُردّ أيضاً — ثمنُ التشديد المقبول (~30٪)،
    # وطريقُ قبولها لاحقاً شاهدٌ ثانٍ (‏ctc_opener_probe) لا إرخاءُ هذا الحارس.
    ("11:1", 8135, [3302, 16871], [8285, 16871, .912], .95),
    ("20:15", 138480, [128144, 152900], [139031, 148317, .897], .4),
    ("38:86", 794844, [776966, 801863], [794438, 801863, .943], .36),
]


def row_for(start, anchor, occ, q=.95):
    return H.surah_rows({1: start}, {"anchors": {"1": [anchor, q, [occ]]}})[0]


class TightenedRepeat(unittest.TestCase):
    def test_known_inside_anchor_cases_rejected(self):
        for ayah, st, anchor, occ, _shift in LATE_INSIDE_ANCHOR:
            with self.subTest(ayah=ayah):
                r = row_for(st, anchor, occ)
                self.assertEqual(r["status"], "dev", ayah)
                self.assertIsNotNone(H.surah_verdict([r]), ayah)

    def test_genuine_repeat_after_anchor_end_accepted(self):
        # أداءٌ ثانٍ منفصلٌ بعد نهاية المِرساة والبدءُ المنشور عليه
        r = row_for(50000, [10000, 14000], [49500, 53000, .85])
        self.assertEqual(r["status"], "repeat")
        # عند حدّ النهاية − TOL تماماً يُقبل، وقبلها بميلّي ثانية يُرفض
        self.assertEqual(row_for(13000, [10000, 14500], [13000, 16000, .9])["status"], "repeat")
        self.assertEqual(row_for(13000, [10000, 14501], [13000, 16000, .9])["status"], "dev")

    def test_earlier_separate_performance_accepted(self):
        # أداءٌ سابقٌ يبعد عن بدء المِرساة أكثر من TOL
        self.assertEqual(row_for(4000, [20000, 24000], [3500, 7000, .9])["status"], "repeat")

    def test_occurrence_equal_to_anchor_start_is_not_a_repeat(self):
        # أداءٌ يطابق بدءَ المِرساة نفسَها هو المِرساةُ لا تكرار؛ فبدءٌ منحرفٌ 1.5–2ث لا يُعذَر به
        r = row_for(11800, [10000, 14000], [10000, 14000, .95])
        self.assertEqual(r["status"], "dev")
        r = row_for(8200, [10000, 14000], [10000, 14000, .95])
        self.assertEqual(r["status"], "dev")

    def test_anchor_without_valid_end_treats_all_as_inside(self):
        for am in ([10000, 10000], [10000, 9000], [10000, None]):
            r = H.surah_rows({1: 50000}, {"anchors": {"1": [am, .9, [[49500, 53000, .9]]]}})[0]
            self.assertEqual(r["status"], "dev", am)

    def test_weak_or_far_occurrence_still_rejected(self):
        self.assertEqual(row_for(50000, [10000, 14000], [49500, 53000, .6])["status"], "dev")
        self.assertEqual(row_for(50000, [10000, 14000], [47000, 53000, .9])["status"], "dev")

    def test_judge_rejects_surah_with_inside_anchor_start(self):
        idx = {"entries": [ent(2, 1, 1000), ent(2, 2, 5000), ent(2, 3, 9000)], "audioSha256": ["x"] * 114}
        m = cmap({1: (1000, .9), 2: (5000, .9), 3: (9000, .9)}, sha="x")
        m["anchors"]["3"] = [[2000, 14000], .95, [[9300, 13000, .93]]]   # بدءٌ منشورٌ 9000 وسط المِرساة
        j = H.judge(idx, None, "c" * 64, {2: m})
        self.assertFalse(j["ok"])


if __name__ == "__main__":
    unittest.main()
