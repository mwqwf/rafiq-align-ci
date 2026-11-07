#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""اختباراتُ مسار شاهد Whisper الإضافيّ في `pin_heard.py` (‏2026-11-07).

الحالةُ المقيسة: آيةٌ مدموجةٌ في سابقتها ومرساتُها في خريطة CTC دون شرط الجودة (‏3siri س56: 68 و69).
الموجبُ: شاهدٌ يطابق الطرفين بثقةٍ ويتّفق مع CTC ضمن 300م.ث. والسوالبُ إلزاميّة: نافذةٌ خاطئة · تعارضُ شاهدين ·
ثقةٌ دون العتبة · مدّةٌ خارج 0.5–2× · جارةٌ تنكمش · بصمةُ صوتٍ مختلفة · بلا شاهدٍ يبقى القديمُ حرفاً.

    python -m pytest -q tools/index_qa/test_pin_heard_witness.py
"""
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from pin_heard import pin, expected_from_peers                   # noqa: E402

URL = "https://h.example/r/056.mp3"
SHA = "a" * 64
REF = {1: ["قل", "هو", "الله", "احد", "الله", "الصمد"],
       2: ["لم", "يلد", "ولم", "يولد", "ولم", "يكن"],
       3: ["الحمد", "لله", "رب", "العالمين", "الرحمن", "الرحيم"],
       4: ["مالك", "يوم", "الدين", "اياك", "نعبد", "واياك"]}


def ref_words(_s, a):
    return REF[a]


def _hmap(q3=0.3, a3=12100):
    """الآية 3 مرساتُها دون 0.5 ⇒ يردّها مسارُ CTC الحاليّ."""
    return {"surah": 56, "fileRef": URL, "sha256": SHA, "heardMap": {
        "1": {"anchorMs": [0, 5000], "anchorQuality": 0.9, "occurrences": []},
        "2": {"anchorMs": [5000, 12000], "anchorQuality": 0.9, "occurrences": []},
        "3": {"anchorMs": [a3, 20000], "anchorQuality": q3, "occurrences": []},
        "4": {"anchorMs": [20000, 30000], "anchorQuality": 0.9, "occurrences": []}}}


def _idx():
    ents = [{"ayahId": "56:1", "startMs": 0, "endMs": 5000, "fileRef": URL, "confBand": "MED"},
            {"ayahId": "56:2", "startMs": 5000, "endMs": 18000, "fileRef": URL, "confBand": "MED"},
            {"ayahId": "56:3", "startMs": 18000, "endMs": 20000, "fileRef": URL, "confBand": "LOW"},
            {"ayahId": "56:4", "startMs": 20000, "endMs": 30000, "fileRef": URL, "confBand": "MED"}]
    return {"entries": ents, "audioSha256": [SHA], "engineVersion": "align-0.2"}


def _words(ayah, start, p=0.9, step=1000):
    return [{"w": w, "s": start + i * step, "e": start + i * step + 800, "p": p}
            for i, w in enumerate(REF[ayah])]


def _wit(words=None, sha=SHA, model="small", ct="float32", url=URL):
    # «والله» الزائدةُ قبل المطلع: ذيلُ الآية السابقة داخل النافذة
    w = words if words is not None else [{"w": "ولم", "s": 11500, "e": 11900, "p": 0.9}] + _words(3, 12150)
    return {"surah": 56, "sha256": sha, "fileRef": url, "model": model, "computeType": model and ct,
            "ayahs": {"3": {"windowMs": [9000, 23000], "words": w}}}


def _run(wit, exp=8000, hmap=None, idx=None, pins=None, ev=None):
    return pin(idx or _idx(), 56, hmap or _hmap(), pins or {3: 12100}, witness=wit, ref_words=ref_words,
               expected={3: exp} if exp else {}, evidence=ev)


class WitnessPositive(unittest.TestCase):
    def test_ctc_alone_still_refuses_low_quality_anchor(self):
        with self.assertRaises(SystemExit) as c:
            pin(_idx(), 56, _hmap(), {3: 12100})
        self.assertIn("لا يقع على أداءٍ مقيس", str(c.exception))

    def test_witness_accepts_and_records_evidence(self):
        ev = {}
        out, rep, changed = _run(_wit(), ev=ev)
        e = {x["ayahId"]: (x["startMs"], x["endMs"]) for x in out["entries"]}
        self.assertEqual(e["56:3"], (12100, 20000))
        self.assertEqual(e["56:2"], (5000, 12100))
        self.assertEqual(ev, {3: "ctc+whisper"})
        self.assertEqual(out["engineBySurah"]["56"], "heard-pin-1")
        self.assertTrue(any("Whisper" in r for r in rep))
        self.assertEqual(changed, [2, 3])

    def test_ctc_path_untouched_when_witness_present(self):
        """آيةٌ تجتاز CTC بعتباته لا يُستشار الشاهدُ لها (‏حتى لو كان شاهدُها فاسداً) والدليلُ «ctc»."""
        ev = {}
        out, _r, _c = pin(_idx(), 56, _hmap(q3=0.9), {3: 12100}, witness=_wit(sha="b" * 64),
                          ref_words=ref_words, expected={}, evidence=ev)
        self.assertEqual(ev, {3: "ctc"})
        self.assertEqual([x["startMs"] for x in out["entries"] if x["ayahId"] == "56:3"], [12100])

    def test_agreement_with_occurrence_any_quality(self):
        h = _hmap(a3=9000)                                       # المرساةُ بعيدة، وأحدُ الأداءات يوافق Whisper
        h["heardMap"]["3"]["occurrences"] = [[12050, 20000, 0.2]]
        out, _r, _c = _run(_wit(), hmap=h, pins={3: 12050})
        self.assertEqual([x["startMs"] for x in out["entries"] if x["ayahId"] == "56:3"], [12050])


class WitnessNegative(unittest.TestCase):
    def refused(self, wit, msg=None, **kw):
        with self.assertRaises(SystemExit) as c:
            _run(wit, **kw)
        if msg:
            self.assertIn(msg, str(c.exception))

    def test_wrong_window_refused(self):
        self.refused(_wit(_words(1, 12150)), "أوّلُ كلماتِ الآية")          # يبدأ بكلمات آيةٍ أخرى
        self.refused(_wit(_words(4, 12150)), "أوّلُ كلماتِ الآية")

    def test_wrong_tail_refused(self):
        w = _words(3, 12150)
        w[-1]["w"] = "الغفور"
        self.refused(_wit(w), "آخرُ كلماتِ")

    def test_conflicting_witnesses_refused(self):
        self.refused(_wit(_words(3, 12500)), "يتعارضان")               # 400م.ث > 300
        self.refused(_wit(_words(3, 11700)), "يتعارضان")

    def test_agreement_edge_accepted(self):
        _run(_wit(_words(3, 12350)))                              # 250م.ث ≤ 300

    def test_low_confidence_refused(self):
        w = _words(3, 12150)
        w[1]["p"] = 0.4                                           # كلمةٌ طرفيّةٌ دون الأدنى
        self.refused(_wit(w), "ثقةُ")
        w = _words(3, 12150, p=0.6)                               # كلُّها فوق الأدنى والمتوسّطُ دون 0.7
        self.refused(_wit(w), "ثقةُ")

    def test_duration_outside_band_refused(self):
        self.refused(_wit(), "خارج", exp=3000)                    # 7900 > 2×3000
        self.refused(_wit(), "خارج", exp=20000)                   # 7900 < 0.5×20000
        _run(_wit(), exp=4000)                                    # الحدّ الأعلى 2× مقبول (7900 ≤ 8000)
        _run(_wit(), exp=15800)                                   # الحدّ الأدنى 0.5× مقبول

    def test_no_expected_refused(self):
        self.refused(_wit(), "مدّةَ متوقَّعةَ", exp=None)

    def test_neighbour_shrinking_below_half_refused(self):
        h = _hmap(a3=7000)                                        # الجارة 2: 13000م.ث ← 2000م.ث
        w = [{"w": "ولم", "s": 6500, "e": 6900, "p": 0.9}] + _words(3, 7050)
        self.refused(_wit(w), "تنكمش", hmap=h, pins={3: 7000}, exp=13000)

    def test_other_audio_sha_refused(self):
        self.refused(_wit(sha="b" * 64), "بصمةُ صوت الشاهد")
        i = _idx(); i["audioSha256"] = ["b" * 64]
        self.refused(_wit(sha=SHA), "بصمة", idx=i)                # الشاهدُ يوافق الخريطةَ لا الفهرس
        self.refused(_wit(url="https://other/056.mp3"), "سُمع من")

    def test_model_must_be_float32_small_or_medium(self):
        self.refused(_wit(ct="int8"), "float32")
        self.refused(_wit(model="tiny"), "float32")

    def test_witness_for_other_surah_refused(self):
        w = _wit(); w["surah"] = 55
        self.refused(w, "لسورة")

    def test_missing_ayah_in_witness_refused(self):
        w = _wit(); w["ayahs"] = {}
        self.refused(w, "لا تفريغَ")


class Expected(unittest.TestCase):
    def test_pace_scaling(self):
        own = {1: 10000, 2: 20000, 3: 30000, 4: 99999}
        peer = {1: 5000, 2: 10000, 3: 15000, 4: 5000, 5: 8000}
        e = expected_from_peers(own, peer, skip={4})
        self.assertAlmostEqual(e[4], 10000.0)                     # الوتيرة 2.0
        self.assertAlmostEqual(e[5], 16000.0)
        self.assertEqual(expected_from_peers({}, peer), {})


if __name__ == "__main__":
    unittest.main()
