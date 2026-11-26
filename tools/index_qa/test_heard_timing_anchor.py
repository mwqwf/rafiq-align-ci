#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""م3ب: مرساةُ الآية 2 من الشاهد الزمنيّ في بوّابة السماع — الاستبدالُ بالشروط كلِّها، وكلُّ ما عداه كما كان."""
import copy
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import heard_gate as H  # noqa: E402

SHA = "13" * 32
REF = "https://h/045.mp3"


def tw(sha=SHA, surah=45, conf=0.998, pause=(9700, 9970), mms=9947, riw="hafs"):
    a2 = {"mms": mms, "mmsScore": 0.8, "qwa": 9920, "qwaConf": conf}
    if pause:
        a2["pause"] = list(pause)
    return {"surah": surah, "riwaya": riw, "sha256": sha, "tool": "mms_fa+qwa", "ayahs": {"2": a2}}


def src(**k):
    return {"run": "123456789", "tw": H.timing_src_rec(tw(**k))}


def cmap(a2=(5023, 0.893), occ=((9966, 0.83),), sha=SHA):
    return {"sha256": sha, "fileRef": REF, "surah": 45,
            "anchors": {"1": [[4263, 5000], 0.9, []],
                        "2": [[a2[0], 16090], a2[1], [[o[0], o[0] + 900, o[1]] for o in occ]],
                        "3": [[16731, 17500], 0.9, []]}}


def rows(c, st2=9966):
    return H.surah_rows({1: 3820, 2: st2, 3: 16731}, c)


class Override(unittest.TestCase):
    def test_before_dev_after_ok(self):
        self.assertEqual(rows(cmap())[1]["status"], "dev")
        c2, ev = H.timing_override(45, cmap(), src(), SHA, "hafs")
        self.assertEqual(ev["replaced"]["to"], 9966)
        self.assertEqual(ev["replaced"]["B"], 9970)
        self.assertEqual(rows(c2)[1]["status"], "ok")
        self.assertIsNone(H.surah_verdict(rows(c2)))

    def test_original_untouched(self):
        c = cmap()
        before = copy.deepcopy(c)
        H.timing_override(45, c, src(), SHA, "hafs")
        self.assertEqual(c, before)

    def _same(self, s, riw="hafs", want=SHA, c=None, surah=45):
        c = c or cmap()
        c2, ev = H.timing_override(surah, c, s, want, riw)
        self.assertIs(c2, c)
        self.assertIsNone(ev["replaced"])
        return ev

    def test_low_qwa_conf_unchanged(self):
        self.assertIn("ثقةُ QWA", self._same(src(conf=0.89))["reason"])

    def test_no_pause_unchanged(self):
        self.assertIn("لا سكتةَ", self._same(src(pause=None))["reason"])

    def test_mms_far_from_b_unchanged(self):
        self.assertIn("MMS", self._same(src(mms=9970 + 151))["reason"])

    def test_mms_150_boundary_ok(self):
        c2, ev = H.timing_override(45, cmap(), src(mms=9970 + 150), SHA, "hafs")
        self.assertIsNotNone(ev["replaced"])

    def test_ctc_start_far_from_b_unchanged(self):
        ev = self._same(src(pause=(9700, 10300), mms=10300))
        self.assertIn("300", ev["reason"])

    def test_ctc_boundary_300_ok(self):
        c2, ev = H.timing_override(45, cmap(occ=((9970 - 300, 0.83),)), src(), SHA, "hafs")
        self.assertEqual(ev["replaced"]["to"], 9670)

    def test_unmeasured_ayah2_unchanged(self):
        self._same(src(), c=cmap(a2=(5023, 0.3), occ=((9966, 0.4),)))

    def test_other_audio_unchanged(self):
        self.assertIn("صوتٍ", self._same(src(sha="aa" * 32))["reason"])

    def test_other_surah_unchanged(self):
        self.assertIn("سورةٍ", self._same(src(surah=44))["reason"])

    def test_not_letters_surah_unchanged(self):
        s = src()
        s["tw"]["surah"] = 55
        self.assertIn("الحروف", self._same(s, surah=55)["reason"])

    def test_other_riwaya_unchanged(self):
        self.assertIn("حفصاً", self._same(src(), riw="warsh")["reason"])

    def test_no_witness_or_error_unchanged(self):
        self._same(None)
        self._same({"run": "1", "tw": {"error": "x"}})

    def test_threshold_1500_kept(self):
        c2, _ = H.timing_override(45, cmap(), src(), SHA, "hafs")
        self.assertEqual(rows(c2, st2=9966 + 1500)[1]["status"], "ok")
        self.assertEqual(rows(c2, st2=9966 + 1501)[1]["status"], "dev")

    def test_anchor_already_ok_status_same(self):
        c = cmap(a2=(9800, 0.9), occ=())
        c2, ev = H.timing_override(45, c, src(), SHA, "hafs")
        self.assertEqual(ev["replaced"]["to"], 9800)
        self.assertEqual([r["status"] for r in rows(c)], [r["status"] for r in rows(c2)])


class JudgeInt(unittest.TestCase):
    def setUp(self):
        def ent(a, st, en):
            return {"ayahId": f"45:{a}", "startMs": st, "endMs": en, "fileRef": REF}
        self.pub = {"entries": [ent(1, 3820, 5023), ent(2, 5023, 16731), ent(3, 16731, 20000)]}
        self.cand = {"riwaya": "hafs", "audioSha256": [None] * 44 + [SHA] + [None] * 69,
                     "entries": [ent(1, 3820, 9966), ent(2, 9966, 16731), ent(3, 16731, 20000)]}

    def test_rejected_without_and_passes_with(self):
        m = {45: cmap()}
        j0 = H.judge(self.cand, self.pub, "x" * 64, m)
        self.assertFalse(j0["ok"])
        self.assertIn("أقصاها الآية 2", j0["reason"])
        j1 = H.judge(self.cand, self.pub, "x" * 64, m, timing_src={"45": src()})
        self.assertTrue(j1["ok"], j1["reason"])
        self.assertEqual(j1["timing"]["45"]["replaced"]["to"], 9966)

    def test_timing_not_applied_to_unmodified_sample(self):
        j = H.judge(self.cand, self.cand, "x" * 64, {45: cmap()}, timing_src={"45": src()})
        self.assertNotIn("timing", j)

    def test_timing_sources_loader(self):
        c = {"transform": {"op": "heard_pin:45", "timingWitnessRun": "123456789"}}
        got = H.timing_sources(c, loader=lambda r, s: tw())
        self.assertEqual(got["45"]["run"], "123456789")
        self.assertEqual(H.timing_sources({"transform": {"op": "heard_pin:45"}}, loader=lambda r, s: tw()), {})
        err = H.timing_sources(c, loader=lambda r, s: (_ for _ in ()).throw(SystemExit("x")))
        self.assertIn("error", err["45"]["tw"])


if __name__ == "__main__":
    unittest.main()
