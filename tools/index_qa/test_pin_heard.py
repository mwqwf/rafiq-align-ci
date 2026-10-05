#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""اختباراتُ `pin_heard.py` (fixV · 2026-10-05): التثبيتُ على أداءٍ مقيسٍ يُقبل ويُرضي حكمَ السماع،
وبدءٌ غيرُ مقيسٍ يُردّ، وصوتٌ غيرُ صوت الفهرس يُردّ، ولا يتغيّر بدءُ آيةٍ لم تُثبَّت.

    python -m unittest tools/index_qa/test_pin_heard.py
"""
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import heard_gate                                                # noqa: E402
from pin_heard import pin                                        # noqa: E402

URL = "https://h.example/r/077.mp3"
# تسجيلٌ يعيد 2–3: الأداءُ الأوّل 10–30ث، ثمّ تكرارٌ 30–50ث، ثمّ 4 عند 50ث.
HMAP = {"surah": 77, "fileRef": URL, "sha256": "a" * 64, "heardMap": {
    "1": {"anchorMs": [0, 10000], "anchorQuality": 0.9, "occurrences": [[0, 10000, 0.9]]},
    "2": {"anchorMs": [10000, 20000], "anchorQuality": 0.9, "occurrences": [[10000, 20000, 0.9], [30000, 40000, 0.85]]},
    "3": {"anchorMs": [40000, 50000], "anchorQuality": 0.8, "occurrences": [[20000, 30000, 0.6], [40000, 50000, 0.8]]},
    "4": {"anchorMs": [50000, 60000], "anchorQuality": 0.9, "occurrences": [[50000, 60000, 0.9]]}}}


def _idx():
    ents = [{"ayahId": "77:1", "startMs": 0, "endMs": 10000, "fileRef": URL, "confBand": "MED"},
            {"ayahId": "77:2", "startMs": 10000, "endMs": 39800, "fileRef": URL, "confBand": "MED"},
            {"ayahId": "77:3", "startMs": 39800, "endMs": 40000, "fileRef": URL, "confBand": "LOW"},
            {"ayahId": "77:4", "startMs": 40000, "endMs": 60000, "fileRef": URL, "confBand": "MED"},
            {"ayahId": "78:1", "startMs": 0, "endMs": 5000, "fileRef": "x", "confBand": "MED"}]
    return {"entries": ents, "audioSha256": ["a" * 64, "b" * 64], "engineVersion": "align-0.2"}


class PinHeard(unittest.TestCase):
    def test_published_shape_is_refused_by_heard_gate(self):
        rows = heard_gate.surah_rows({1: 0, 2: 10000, 3: 39800, 4: 40000}, heard_gate.compact_map(HMAP))
        self.assertIsNotNone(heard_gate.surah_verdict(rows))

    def test_pin_second_performance(self):
        out, rep, changed = pin(_idx(), 77, copy.deepcopy(HMAP), {2: 30000, 3: 40000, 4: 50000}, {1: 10000})
        e = {x["ayahId"]: (x["startMs"], x["endMs"]) for x in out["entries"]}
        self.assertEqual(e["77:1"], (0, 10000))
        self.assertEqual(e["77:2"], (30000, 40000))
        self.assertEqual(e["77:3"], (40000, 50000))
        self.assertEqual(e["77:4"], (50000, 60000))
        self.assertEqual(e["78:1"], (0, 5000))
        self.assertEqual(out["engineBySurah"]["77"], "heard-pin-1")
        self.assertEqual(changed, [2, 3, 4])
        out2, _, _ = pin(_idx(), 77, copy.deepcopy(HMAP), {2: 30000, 3: 40000, 4: 50000})
        self.assertEqual([x for x in out2["entries"] if x["ayahId"] == "77:1"][0]["endMs"], 30000)  # بلا قصّ يبقى متّصلاً

    def test_trim_must_be_measured(self):
        out, _, _ = pin(_idx(), 77, copy.deepcopy(HMAP), {2: 30000, 3: 40000, 4: 50000})
        with self.assertRaises(SystemExit):
            pin(_idx(), 77, copy.deepcopy(HMAP), {3: 40000, 4: 50000}, {2: 23456})
        out, _, _ = pin(_idx(), 77, copy.deepcopy(HMAP), {3: 40000, 4: 50000}, {2: 20000})
        self.assertEqual([x for x in out["entries"] if x["ayahId"] == "77:2"][0]["endMs"], 20000)
        with self.assertRaises(SystemExit):                            # لا قصَّ لآيةٍ لا يليها تثبيت
            pin(_idx(), 77, copy.deepcopy(HMAP), {2: 30000, 3: 40000}, {4: 60000})

    def test_contiguous_neighbour_stays_contiguous(self):
        out, _, _ = pin(_idx(), 77, copy.deepcopy(HMAP), {2: 10000, 3: 40000, 4: 50000})
        e = {x["ayahId"]: (x["startMs"], x["endMs"]) for x in out["entries"]}
        self.assertEqual(e["77:1"], (0, 10000))
        self.assertEqual(e["77:2"], (10000, 40000))

    def test_pinned_ayah_trimmed_to_its_measured_end(self):
        out, _, _ = pin(_idx(), 77, copy.deepcopy(HMAP), {2: 10000, 3: 40000, 4: 50000}, {2: 20000})
        e = {x["ayahId"]: (x["startMs"], x["endMs"]) for x in out["entries"]}
        self.assertEqual(e["77:2"], (10000, 20000))                   # التكرارُ 20–40ث بلا مدخل
        self.assertEqual(e["77:3"], (40000, 50000))

    def test_unmeasured_start_refused(self):
        with self.assertRaises(SystemExit):
            pin(_idx(), 77, copy.deepcopy(HMAP), {3: 20000})          # أداءٌ بتشابه 0.6 < 0.7
        with self.assertRaises(SystemExit):
            pin(_idx(), 77, copy.deepcopy(HMAP), {3: 44000})

    def test_other_audio_refused(self):
        h = copy.deepcopy(HMAP); h["sha256"] = "c" * 64
        with self.assertRaises(SystemExit):
            pin(_idx(), 77, h, {2: 30000, 3: 40000, 4: 50000})
        h = copy.deepcopy(HMAP); h["fileRef"] = "https://other/077.mp3"
        with self.assertRaises(SystemExit):
            pin(_idx(), 77, h, {2: 30000, 3: 40000, 4: 50000})

    def test_result_must_satisfy_heard_gate(self):
        with self.assertRaises(SystemExit):                            # 4 تبقى منحرفة 10ث
            pin(_idx(), 77, copy.deepcopy(HMAP), {2: 30000})

    def test_drop_declaration_parent_refused(self):
        i = _idx(); i["transform"] = {"op": "drop_surah:9"}
        with self.assertRaises(SystemExit):
            pin(i, 77, copy.deepcopy(HMAP), {2: 30000, 3: 40000, 4: 50000})


if __name__ == "__main__":
    unittest.main()
