#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""اختباراتُ انتقاء الدفعة السماعيّة (heard_batch_select.decide)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from heard_batch_select import decide  # noqa: E402

REF = "https://h/001.mp3"


def parent(starts):
    return {"entries": [{"ayahId": f"1:{a}", "startMs": st, "endMs": st + 500, "fileRef": REF}
                        for a, st in starts.items()], "audioSha256": ["aa"]}


def res(anchors, built, sha="aa", ref=REF):
    return {"sha256": sha, "fileRef": ref, "engine": "ctc-heardmap-1",
            "heardMap": {str(a): {"anchorMs": [v[0], v[0] + 900], "anchorQuality": v[1], "heard": v[1] >= .3,
                                  "occurrences": []} for a, v in anchors.items()},
            "entries": [{"ayahIdx": a - 1, "startMs": st, "endMs": (st + 900) if st is not None else None}
                        for a, st in built.items()]}


AN = {1: (0, .9), 2: (10000, .9), 3: (40000, .9), 4: (80000, .9)}


class Decide(unittest.TestCase):
    def test_takes_damaged_fixed(self):
        d = decide(1, parent({1: 0, 2: 10000, 3: 12000, 4: 14000}), res(AN, {1: 100, 2: 10100, 3: 40200, 4: 80300}))
        self.assertTrue(d["take"], d["why"])
        self.assertEqual(d["publishedDev"], [3, 4])

    def test_sound_published_untouched(self):
        d = decide(1, parent({1: 0, 2: 10000, 3: 40000, 4: 80000}), res(AN, {1: 0, 2: 10000, 3: 40000, 4: 80000}))
        self.assertFalse(d["take"])
        self.assertIn("لم يُمسّ", d["why"])

    def test_rebuilt_still_deviating_rejected(self):
        d = decide(1, parent({1: 0, 2: 10000, 3: 12000, 4: 14000}), res(AN, {1: 0, 2: 10000, 3: 40000, 4: 70000}))
        self.assertFalse(d["take"])
        self.assertIn("المبنيُّ يُردّ", d["why"])

    def test_unresolved_rejected(self):
        d = decide(1, parent({1: 0, 2: 10000, 3: 12000, 4: 14000}), res(AN, {1: 0, 2: 10000, 3: 40000, 4: None}))
        self.assertFalse(d["take"])
        self.assertIn("بلا حدود", d["why"])

    def test_audio_changed_rejected(self):
        d = decide(1, parent({1: 0, 2: 10000, 3: 12000, 4: 14000}), res(AN, {1: 0, 2: 10000, 3: 40000, 4: 80000}, sha="zz"))
        self.assertFalse(d["take"])
        self.assertIn("تبدّل", d["why"])

    def test_other_file_rejected(self):
        d = decide(1, parent({1: 0, 2: 10000, 3: 12000, 4: 14000}),
                   res(AN, {1: 0, 2: 10000, 3: 40000, 4: 80000}, ref="https://x/001.mp3"))
        self.assertFalse(d["take"])

    def test_missing_output(self):
        self.assertFalse(decide(1, parent({1: 0}), None)["take"])


if __name__ == "__main__":
    unittest.main()
