# -*- coding: utf-8 -*-
"""م3 — مطلعُ الحروف بالشاهد الزمنيّ (‏`pin_heard --opener-timing`): حفص وحده، ثقةُ QWA ≥0.9، سكتةٌ، |MMS−B|≤150، التثبيتُ المقيس ضمن W_AGREE_MS."""
from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import pin_heard as P                                            # noqa: E402

TD = HERE / "testdata" / "opener_letters" / "kurdi40"
ENTS = json.loads((TD / "entries.json").read_text(encoding="utf-8"))
HMAP = json.loads(next(TD.glob("heard_s*.json")).read_text(encoding="utf-8"))


def _idx(start1=4000):
    idx = {"riwaya": ENTS["riwaya"] or "hafs", "reciterId": ENTS["reciterId"],
           "entries": copy.deepcopy(ENTS["entries"]), "audioSha256": [ENTS["audioSha256"]]}
    for e in idx["entries"]:
        if e["ayahId"] == "40:1":
            e["startMs"] = start1
    return idx


def _tw(**kw):
    a2 = {"mms": 6700, "mmsScore": 0.9, "qwa": 6690, "qwaConf": 0.95, "pause": [6400, 6690]}
    a2.update(kw)
    return {"surah": 40, "riwaya": "hafs", "fileRef": HMAP.get("fileRef"), "sha256": HMAP.get("sha256"),
            "tool": P.TW_TOOL, "ayahs": {"2": a2}}


def _pin(tw, idx=None, pin2=6684):
    ev = {}
    out, report, ch = P.pin(idx or _idx(), 40, HMAP, {2: pin2}, opener_witnesses={}, opener_evidence=ev, timing=tw)
    return {e["ayahId"]: e for e in out["entries"]}, report, ev


class OpenerTiming(unittest.TestCase):
    def test_accepted_without_whisper(self):
        e, report, ev = _pin(_tw())
        self.assertEqual(e["40:1"]["startMs"], 4000)             # لا تمديدَ بلا شاهد Whisper (‏المنشورُ يبقى)
        self.assertEqual(e["40:1"]["endMs"], 6684)
        self.assertEqual(e["40:2"]["startMs"], 6684)
        self.assertEqual(ev["witnesses"], {})
        self.assertEqual(ev["ayah2Timing"]["pauseEndMs"], 6690)
        self.assertTrue(any("حدٌّ بلا قياسٍ للحروف" in r for r in report))

    def _refused(self, tw, why, **kw):
        with self.assertRaises(SystemExit) as cm:
            _pin(tw, **kw)
        self.assertIn(why, str(cm.exception))

    def test_low_confidence_refused(self):
        self._refused(_tw(qwaConf=0.89), "ثقةُ QWA")

    def test_no_pause_refused(self):
        self._refused(_tw(pause=None), "لا سكتةَ")

    def test_mms_far_from_pause_end_refused(self):
        self._refused(_tw(mms=6841), "MMS")

    def test_pin_far_from_pause_end_refused(self):
        self._refused(_tw(pause=[6900, 7100], mms=7100), "التثبيت", pin2=6684)

    def test_only_hafs(self):
        with self.assertRaises(SystemExit) as cm:
            P.opener_timing_b(_tw(), "warsh", 40)
        self.assertIn("لحفص وحده", str(cm.exception))
        with self.assertRaises(SystemExit):
            P.opener_timing_b(_tw(), "qalun", 40)

    def test_wrong_audio_refused(self):
        tw = _tw()
        tw["sha256"] = "0" * 64
        self._refused(tw, "بصمةُ صوت")

    def test_no_baseline_refused(self):
        with self.assertRaises(SystemExit) as cm:
            P.opener_letters_start({}, 40, "hafs", HMAP, ENTS["audioSha256"], None, 6684, timing=_tw())
        self.assertIn("بلا خطّ أساسٍ", str(cm.exception))

    def test_without_timing_still_needs_two_whisper_witnesses(self):
        with self.assertRaises(SystemExit) as cm:
            P.opener_letters_start({}, 40, "hafs", HMAP, ENTS["audioSha256"], 4000, 6684)
        self.assertIn("شاهدان", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
