#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""اختباراتُ م1 — الشاهدُ الزمنيّ MMS∧QWA في مسار شاهد Whisper (‏`pin_heard --timing-witness-run`، 2026-11-25).

الموجب: Whisper يسمع طرفَي الآية بثقةٍ لكنّ طابعَه الزمنيّ يخالف CTC (>300)، والمحاذيان يتّفقان ≤150 ويوافقان CTC ≤300
⇒ يُعتمد بدءُ CTC كما هو. والسوالبُ إلزاميّة: محاذٍ واحد · محاذيان مختلفان · بدءٌ زمنيٌّ يخالف CTC · رأسُ Whisper بعيد ·
سماعٌ فاشل أو ثقةٌ دون العتبة مهما صحّ التوقيت · بصمةٌ أو مصدرٌ أو أداةٌ مختلفة · وبلا شاهدٍ زمنيٍّ يبقى القديمُ حرفاً.

    python -m pytest -q tools/index_qa/test_pin_heard_timing_witness.py
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from pin_heard import (pin, timing_onset, witness_run_error, TIMING_WORKFLOW, WITNESS_WORKFLOW,  # noqa: E402
                       TW_CONS_MS, TW_LOCATE_MS, W_AGREE_MS, REPO)
from test_pin_heard_witness import _hmap, _idx, _words, _wit, ref_words, URL, SHA      # noqa: E402

LATE = 12850          # طابعُ Whisper متأخّرٌ 750م.ث عن مرساة CTC (12100) ⇒ المسارُ القديم يردّ


def _tw(mms=12090, qwa=12130, sha=SHA, url=URL, tool="mms_fa+qwa", surah=56):
    return {"surah": surah, "riwaya": "hafs", "fileRef": url, "sha256": sha, "tool": tool,
            "ayahs": {"3": {"mms": mms, "mmsScore": 0.9, "qwa": qwa, "qwaConf": 0.9}}}


def _run(wit, tw=None, ev=None, exp=8000):
    return pin(_idx(), 56, _hmap(), {3: 12100}, witness=wit, ref_words=ref_words,
               expected={3: exp}, evidence=ev, timing=tw)


class TimingPositive(unittest.TestCase):
    def test_old_path_refuses_late_whisper(self):
        with self.assertRaises(SystemExit) as c:
            _run(_wit(_words(3, LATE)))
        self.assertIn("يتعارضان", str(c.exception))

    def test_timing_rescues_late_whisper_and_pins_ctc(self):
        ev = {}
        out, rep, _c = _run(_wit(_words(3, LATE)), _tw(), ev=ev)
        e = {x["ayahId"]: x["startMs"] for x in out["entries"]}
        self.assertEqual(e["56:3"], 12100)                       # بدءُ CTC نفسُه لا البدءُ الزمنيّ
        self.assertEqual(ev, {3: "ctc+whisper+timing"})
        self.assertTrue(any("mms∧qwa" in r for r in rep))

    def test_old_path_first_when_whisper_agrees(self):
        ev = {}
        _run(_wit(), _tw(mms=None), ev=ev)                         # الشاهدُ الزمنيُّ الفاسد لا يُستشار
        self.assertEqual(ev, {3: "ctc+whisper"})

    def test_edges_accepted(self):
        _run(_wit(_words(3, LATE)), _tw(mms=12100 + W_AGREE_MS - TW_CONS_MS, qwa=12100 + W_AGREE_MS))
        self.assertEqual(timing_onset(_tw(mms=1000, qwa=1000 + TW_CONS_MS), 3), 1000 + TW_CONS_MS / 2)


class TimingNegative(unittest.TestCase):
    def refused(self, wit, tw, msg=None):
        with self.assertRaises(SystemExit) as c:
            _run(wit, tw)
        if msg:
            self.assertIn(msg, str(c.exception))

    def test_single_aligner_refused(self):
        self.refused(_wit(_words(3, LATE)), _tw(qwa=None), "لا بدءَ زمنيَّ")
        self.refused(_wit(_words(3, LATE)), _tw(mms=None), "لا بدءَ زمنيَّ")

    def test_aligners_disagree_refused(self):
        self.refused(_wit(_words(3, LATE)), _tw(mms=12100, qwa=12100 + TW_CONS_MS + 1), "لا بدءَ زمنيَّ")

    def test_timing_against_ctc_refused(self):
        self.refused(_wit(_words(3, LATE)), _tw(mms=12450, qwa=12460), "يخالف أقربَ CTC")
        self.refused(_wit(_words(3, LATE)), _tw(mms=11740, qwa=11760), "يخالف أقربَ CTC")

    def test_whisper_head_far_from_timing_refused(self):
        self.refused(_wit(_words(3, 12110 + TW_LOCATE_MS + 300)), _tw(), "بعيدٌ عن البدء الزمنيّ")

    def test_hearing_still_required(self):
        self.refused(_wit(_words(1, LATE)), _tw(), "أوّلُ كلماتِ الآية")
        w = _words(3, LATE)
        w[-1]["w"] = "الغفور"
        self.refused(_wit(w), _tw(), "آخرُ كلماتِ")
        w = _words(3, LATE)
        w[1]["p"] = 0.4
        self.refused(_wit(w), _tw(), "ثقةُ")

    def test_duration_guard_unchanged(self):
        with self.assertRaises(SystemExit) as c:
            _run(_wit(_words(3, LATE)), _tw(), exp=3000)
        self.assertIn("خارج", str(c.exception))

    def test_provenance_refused(self):
        self.refused(_wit(_words(3, LATE)), _tw(sha="b" * 64), "بصمةُ صوت الشاهد الزمنيّ")
        self.refused(_wit(_words(3, LATE)), _tw(url="https://h.example/x.mp3"), "الشاهدُ الزمنيّ من")
        self.refused(_wit(_words(3, LATE)), _tw(tool="mms_fa"), "يلزمه mms_fa+qwa")
        self.refused(_wit(_words(3, LATE)), _tw(surah=57), "لسورة 57")

    def test_run_must_come_from_timing_workflow(self):
        run = {"id": 1234567, "path": WITNESS_WORKFLOW, "status": "completed", "conclusion": "success",
               "repository": {"full_name": REPO}, "head_repository": {"full_name": REPO},
               "head_branch": "main", "event": "workflow_dispatch"}
        self.assertIn(TIMING_WORKFLOW, witness_run_error(1234567, run, workflow=TIMING_WORKFLOW))
        self.assertIsNone(witness_run_error(1234567, dict(run, path=TIMING_WORKFLOW), workflow=TIMING_WORKFLOW))
        self.assertIsNone(witness_run_error(1234567, run))          # الافتراضيُّ القديمُ كما هو


if __name__ == "__main__":
    unittest.main()
