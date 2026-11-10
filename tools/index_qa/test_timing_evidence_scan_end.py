#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""`timing_evidence_scan --kind end`: يبني دليلَ «نهاية المدخل» لـdrop_ayahs بدالّة البوّابة نفسِها (‏`timing_repair.end_drift_error`
ثمّ `end_record_error`)، وما يبنيه تقبله `drop_ayahs` و`promote.declared_truncated_gaps` كما هو — بلا شبكةٍ ولا دلو.

    PYTHONPATH=tools/index_qa:tools/ci_fleet python -m unittest tools.index_qa.test_timing_evidence_scan_end
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import timing_evidence_scan as TES                              # noqa: E402
from test_drop_ayahs_end_evidence import (                       # noqa: E402
    N, PROBES, RUN_A, RUN_B, S, SHA, _end, _idx, gate, make, ref_words, witness)

ENDS = {a: _end(a) for a in range(1, N + 1)}
META = {"riwaya": "hafs", "audioSha256": list(SHA)}


def build(srcs, ayahs=(15, 20, 25), runs=(RUN_A, RUN_B)):
    return TES.build_end(srcs, list(runs), S, ENDS, list(ayahs), "hafs", ref_words, N, SHA[S - 1], META)


class ScanEnd(unittest.TestCase):
    def test_00_builds_only_what_both_witnesses_prove_and_gate_accepts_it(self):
        srcs = [witness(PROBES), witness(PROBES)]
        ev, rep, code = build(srcs)
        self.assertEqual(code, 0)
        self.assertEqual(sorted(ev), [f"{S}:15", f"{S}:20"])
        self.assertIn("25", rep["unproven"])                          # لا يغطّيها الشاهدان ⇒ لا دليل
        self.assertEqual(ev[f"{S}:15"]["probe"], {"ayah": 15, "heardAyah": 16, "endMs": _end(15)})
        out = make(evidence=ev, loader=lambda r, s: witness(PROBES, surah=s))
        self.assertTrue(gate(out)[0])

    def test_disagreeing_witnesses_not_proven(self):
        srcs = [witness(PROBES), witness(PROBES, heard=33)]
        ev, rep, code = build(srcs)
        self.assertEqual(ev, {})
        self.assertEqual(code, 4)

    def test_own_text_not_proven(self):
        ev, _rep, code = build([witness(PROBES), witness(PROBES, own=True)])
        self.assertEqual((ev, code), ({}, 4))

    def test_sha_mismatch_not_proven(self):
        ev, rep, _c = build([witness(PROBES), witness(PROBES, sha="f" * 64)])
        self.assertEqual(ev, {})
        self.assertIn("invalid", rep["unproven"]["15"])

    def test_witness_of_other_surah_not_proven(self):
        """تفريغٌ يُعلن سورةً أخرى ببصمة السورة نفسِها: لا تكشفه حالةُ الشاهد، ويردّه فحصُ البوّابة قبل الكتابة."""
        bad = witness(PROBES)
        bad["surah"] = 77
        ev, rep, _c = build([witness(PROBES), bad])
        self.assertEqual(ev, {})
        self.assertIn("end_record_error", rep["unproven"]["15"])

    def test_low_confidence_not_proven(self):
        ev, _rep, _c = build([witness(PROBES), witness(PROBES, p=0.45)])
        self.assertEqual(ev, {})

    def test_runs_must_be_distinct_canonical(self):
        with self.assertRaises(SystemExit):
            build([witness(PROBES), witness(PROBES)], runs=(RUN_A, RUN_A))
        with self.assertRaises(SystemExit):
            build([witness(PROBES), witness(PROBES)], runs=(RUN_A, "0" + RUN_A))

    def test_cli_with_real_text(self):
        """الواجهةُ بالنصّ الموثَّق ودالّة البوّابة `disputed_ref_words`: 78:24 ونهايتُها في صوت 78:25."""
        at = 249000
        def art(text):
            ws = [{"w": w, "s": at - 600 + k * 400, "e": at - 600 + k * 400 + 380, "p": 0.95}
                  for k, w in enumerate(text.split())]
            return {"surah": S, "riwaya": "hafs", "fileRef": "f", "sha256": SHA[S - 1], "model": "small",
                    "computeType": "float32", "ayahs": {"24": {"windowMs": [at - 3000, at + 3000], "words": ws}}}
        with tempfile.TemporaryDirectory() as d:
            dp = Path(d)
            (dp / "a.json").write_text(json.dumps(art("إلا حميما وغساقا")), encoding="utf-8")
            (dp / "b.json").write_text(json.dumps(art("إلا حميما وغساقا")), encoding="utf-8")
            (dp / "e.txt").write_text(f"{S}:23\t230000\t239000\n{S}:24\t240000\t{at}\n", encoding="utf-8")
            argv = ["--surah", str(S), "--riwaya", "hafs", "--audio-sha", SHA[S - 1], "--runs", f"{RUN_A},{RUN_B}",
                    "--witness-artifacts", f"{dp / 'a.json'},{dp / 'b.json'}", "--entries", str(dp / "e.txt"),
                    "--out", str(dp / "ev.json"), "--report", str(dp / "rep.json"), "--kind", "end", "--ayahs", "23,24"]
            self.assertEqual(TES.main(argv), 0)
            ev = json.loads((dp / "ev.json").read_text(encoding="utf-8"))
            self.assertEqual(sorted(ev), [f"{S}:24"])
            self.assertEqual(ev[f"{S}:24"]["kind"], "end")
            self.assertEqual(ev[f"{S}:24"]["probe"]["heardAyah"], 25)
            (dp / "b.json").write_text(json.dumps(art("فيها بردا ولا شرابا")), encoding="utf-8")
            (dp / "ev2.json").write_text("{}", encoding="utf-8")
            argv[argv.index(str(dp / "ev.json"))] = str(dp / "ev2.json")
            self.assertEqual(TES.main(argv), 4)                       # شاهدٌ يسمع نصَّ الآية نفسِها ⇒ لا دليل
            self.assertEqual(json.loads((dp / "ev2.json").read_text(encoding="utf-8")), {})


if __name__ == "__main__":
    unittest.main()
