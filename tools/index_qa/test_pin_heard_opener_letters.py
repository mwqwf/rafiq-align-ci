#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""اختباراتُ «حدٌّ بلا قياسٍ للحروف» في `pin_heard.py` (‏قرار القائد 2026-11-10 · خيار أ · `opener-letters-1`).

البياناتُ الحقيقيّة في `testdata/opener_letters/` (‏كلُّ شاهدٍ float32 بمعرّف تشغيلته، والخرائطُ ctc_heard_probe float32،
والمداخلُ من المنشور: الكردي b7fe6778 · a_ahmed 774603c1 · mhsny 14c13705 · darweez 51d9615e):
  الكردي 40: «حميم»@5119 (medium) و«حاميم»@4120 (small) — Whisper لا يكتب «حم»، والشاهدان يختلفان 1000م.ث في بدئها؛
            ومطلعُ 40:2 «تنزيل الكتاب من» عند 6520/6720 ومرساتُه 6684 (‏0.893)؛ والمنشورُ 40:1 = 6854–7054 بعد مطلع الثانية.
  الكردي 28 · 43 · a_ahmed 26 · mhsny 2 · darweez 40: حالاتٌ حقيقيّةٌ تُردّ اليوم بشروطٍ لا تُرخى (‏انظر RealCases).

    python -m pytest -q tools/index_qa/test_pin_heard_opener_letters.py
"""
from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import pin_heard as P                                            # noqa: E402

TD = HERE / "testdata" / "opener_letters"
HAFS = [2, 3, 7, 19, 20, 26, 28, 29, 30, 31, 32, 36, 40, 41, 43, 44, 45, 46]


def _case(name):
    d = TD / name
    ents = json.loads((d / "entries.json").read_text(encoding="utf-8"))
    maps = list(d.glob("heard_s*.json"))
    hmap = json.loads(maps[0].read_text(encoding="utf-8")) if maps else None
    wits = {p.stem.split("_", 1)[1]: json.loads(p.read_text(encoding="utf-8")) for p in sorted(d.glob("whisper_*.json"))}
    return ents, hmap, wits


def _idx(ents):
    return {"riwaya": ents["riwaya"] or "hafs", "reciterId": ents["reciterId"],
            "entries": copy.deepcopy(ents["entries"]), "audioSha256": [ents["audioSha256"]]}


K40 = _case("kurdi40")


def _k40_pair():
    """⚠️ زوجٌ **مركّبٌ معلَّم** من شاهدَي الكردي 40 الحقيقيَّين: تعديلٌ واحد — ثقةُ «من» في small 0.39 ⇒ 0.90
    (‏هي التي تردّه حقيقةً). لاختبار القاعدة لا دليلاً."""
    w = copy.deepcopy(K40[2])
    for x in w["42757072643"]["ayahs"]["1"]["words"]:
        if x["w"] == "من" and x["s"] == 9220:
            x["p"] = 0.9
    return w


def _pin40(wits, ents=None, pin2=6684, pins=None):
    ents = ents or K40[0]
    ev = {}
    out, report, ch = P.pin(_idx(ents), 40, K40[1], pins or {2: pin2}, opener_witnesses=wits, opener_evidence=ev)
    return {e["ayahId"]: e for e in out["entries"]}, report, ch, ev


class DerivedList(unittest.TestCase):
    """١) القائمةُ مشتقّةٌ من نصّ المصحف الموثَّق لكلّ رواية، و٢) تُستثنى سورةٌ آيتُها الثانية حروف."""

    def test_three_riwayat(self):
        for riw in ("hafs", "warsh", "qalun"):
            self.assertEqual(P.letters_opener_surahs(riw), HAFS, riw)

    def test_42_excluded_second_ayah_is_letters(self):
        self.assertNotIn(42, P.letters_opener_surahs("hafs"))
        self.assertTrue(P.is_letters_ayah("عٓسٓقٓ"))

    def test_words_of_the_same_letters_are_not_openers(self):
        # الرحمن · الحاقّة · القارعة: كلمةٌ واحدةٌ من حروف الفواتح وليست حروفاً مقطّعة
        for raw in ("ٱلرَّحْمَٰنُ", "ٱلْحَآقَّةُ", "ٱلْقَارِعَةُ", "مَا", "لَمْ", "صٓ ۚ وَٱلْقُرْءَانِ ذِى ٱلذِّكْرِ"):
            self.assertFalse(P.is_letters_ayah(raw), raw)
        for raw in ("الٓمٓ", "حمٓ", "طسٓمٓ", "طه", "كٓهيعٓصٓ", "يسٓ", "أَلَٓمِّٓۖ", "ح۪مِٓۖ", "طَهَۖ"):
            self.assertTrue(P.is_letters_ayah(raw), raw)

    def test_surah_outside_the_list_refused(self):
        with self.assertRaises(SystemExit) as cm:
            P.opener_letters_start(_k40_pair(), 42, "hafs", K40[1], K40[0]["audioSha256"], 6854, 6684, ["تنزيل"])
        self.assertIn("ليست في قائمة", str(cm.exception))


class Rule(unittest.TestCase):
    def test_accepted_extends_backwards_only_and_records_evidence(self):
        e, report, ch, ev = _pin40(_k40_pair())
        self.assertEqual(e["40:1"]["startMs"], 4120)            # أبكرُ كلمةٍ قبل مطلع الثانية («حاميم» small)
        self.assertEqual(e["40:1"]["endMs"], 6684)
        self.assertEqual(e["40:2"]["startMs"], 6684)
        self.assertEqual(ev["version"], P.OPENER_VERSION)
        self.assertEqual(ev["publishedStartMs"], 6854)
        self.assertEqual(sorted(ev["witnesses"]), ["42756948718", "42757072643"])
        self.assertTrue(any("حدٌّ بلا قياسٍ للحروف" in r for r in report))
        self.assertEqual(ch, [1, 2])
        for a in (3, 4):
            self.assertEqual(e[f"40:{a}"], [x for x in K40[0]["entries"] if x["ayahId"] == f"40:{a}"][0])

    def test_published_earlier_is_kept(self):
        ents = copy.deepcopy(K40[0])
        ents["entries"][0]["startMs"] = 3500
        e, *_ = _pin40(_k40_pair(), ents)
        self.assertEqual(e["40:1"]["startMs"], 3500)

    def test_c3_more_than_3000_before_published_refused(self):
        ents = copy.deepcopy(K40[0])
        ents["entries"][0]["startMs"] = 7121              # 7121 − 4120 = 3001
        ents["entries"][0]["endMs"] = 7200
        with self.assertRaises(SystemExit) as cm:
            _pin40(_k40_pair(), ents)
        self.assertIn("3000", str(cm.exception))

    def test_c3_before_file_start_refused(self):
        w = _k40_pair()
        w["42757072643"]["ayahs"]["1"]["windowMs"][0] = -1000      # ⚠️ نافذةٌ مصطنعةٌ قبل الملفّ لاختبار الحدّ وحده
        w["42757072643"]["ayahs"]["1"]["words"][1]["s"] = -40      # «حاميم» قبل بدء الملفّ
        with self.assertRaises(SystemExit) as cm:
            _pin40(w)
        self.assertIn("قبل بدء الملفّ", str(cm.exception))

    def test_one_witness_refused(self):
        w = _k40_pair()
        w.pop("42757072643")
        with self.assertRaises(SystemExit) as cm:
            _pin40(w)
        self.assertIn("شاهدان", str(cm.exception))

    def test_other_audio_or_int8_refused(self):
        for k, v in (("sha256", "b" * 64), ("computeType", "int8"), ("fileRef", "https://x/040.mp3")):
            w = _k40_pair()
            w["42757072643"][k] = v
            with self.assertRaises(SystemExit):
                _pin40(w)

    def test_head_far_from_pin_refused(self):
        w = _k40_pair()
        for x in w["42756948718"]["ayahs"]["1"]["words"][1:]:
            x["s"] += 500                                   # «تنزيل» 7020: 336م.ث من التثبيت 6684
            x["e"] += 500
        with self.assertRaises(SystemExit) as cm:
            _pin40(w)
        self.assertIn("بعيدٌ عن التثبيت", str(cm.exception))

    def test_head_word_changed_refused(self):
        # «حم» عند موضع «تنزيل»: مطلعُ الثانية يجب أن يُسمع كلمةً بكلمة
        w = _k40_pair()
        w["42756948718"]["ayahs"]["1"]["words"][1]["w"] = "حم"
        with self.assertRaises(SystemExit):
            _pin40(w)

    def test_head_clamped_to_window_refused(self):
        w = _k40_pair()
        w["42756948718"]["ayahs"]["1"]["windowMs"][0] = 6520
        with self.assertRaises(SystemExit) as cm:
            _pin40(w)
        self.assertIn("ملصوقٌ ببدء النافذة", str(cm.exception))

    def test_letters_word_clamped_to_window_start_is_not_a_measurement(self):
        w = _k40_pair()
        w["42757072643"]["ayahs"]["1"]["windowMs"][0] = 4120       # «حاميم» ملصوقةٌ ببدء النافذة ⇒ لا تُعدّ
        e, *_ = _pin40(w)
        self.assertEqual(e["40:1"]["startMs"], 5119)

    def test_basmala_words_do_not_extend(self):
        w = _k40_pair()
        words = w["42756948718"]["ayahs"]["1"]["words"]
        words[:0] = [{"w": "بسم", "s": 1100, "e": 1600, "p": 0.99}, {"w": "الله", "s": 1600, "e": 2100, "p": 0.99},
                     {"w": "الرحمن", "s": 2100, "e": 2900, "p": 0.99}, {"w": "الرحيم", "s": 2900, "e": 3900, "p": 0.99}]
        e, *_ = _pin40(w)
        self.assertEqual(e["40:1"]["startMs"], 4120)

    def test_ayah1_pinned_or_ayah2_not_pinned_refused(self):
        for pins in ({1: 6684}, {3: 14729}):
            with self.assertRaises(SystemExit):
                _pin40(_k40_pair(), pins=pins)

    def test_pin2_must_be_measured(self):
        with self.assertRaises(SystemExit) as cm:
            _pin40(_k40_pair(), pin2=6400)
        self.assertIn("لا يقع على أداءٍ مقيس", str(cm.exception))

    def test_without_opener_path_old_behaviour_refuses(self):
        # بلا المسار: تثبيتُ 40:2 على 6684 يجعل 40:1 (‏6854) بعد الثانية ⇒ حدودٌ غيرُ صاعدة كما كان
        with self.assertRaises(SystemExit) as cm:
            P.pin(_idx(K40[0]), 40, K40[1], {2: 6684})
        self.assertIn("غيرُ صاعدة", str(cm.exception))


class RealCases(unittest.TestCase):
    """الحالاتُ الحقيقيّة كما هي اليوم: كلُّها تُردّ بسببٍ مسمّى (‏لا يُرخى شرطٌ لتمرّ)."""

    def test_kurdi40_small_low_confidence(self):
        with self.assertRaises(SystemExit) as cm:
            _pin40(dict(K40[2]))
        self.assertIn("0.39", str(cm.exception))

    def test_kurdi28_head_not_heard(self):
        ents, hmap, wits = _case("kurdi28")
        with self.assertRaises(SystemExit) as cm:
            P.pin(_idx(ents), 28, hmap, {2: 9786}, opener_witnesses=wits, opener_evidence={})
        self.assertIn("مطلعُ الآية الثانية", str(cm.exception))

    def test_kurdi43_extension_beyond_3000(self):
        # لا خريطةَ float32 لس43 بعد: مطلعُ «والكتاب» عند Whisper 5780/6380، و«حامين» 4380/4980، والمنشورُ 43:1 = 8415.
        ents, _h, wits = _case("kurdi43")
        hm = {"sha256": ents["audioSha256"], "fileRef": ents["entries"][0]["fileRef"], "surah": 43}
        with self.assertRaises(SystemExit):
            P.opener_letters_start(wits, 43, "hafs", hm, ents["audioSha256"], 8415, 6380)

    def test_a_ahmed26_and_mhsny2_no_measured_second_ayah(self):
        for name, s in (("a_ahmed26", 26), ("mhsny2", 2)):
            ents, hmap, wits = _case(name)
            self.assertEqual(P.measured_starts(hmap, 2), [], name)

    def test_darweez40_head_misheard(self):
        ents, hmap, wits = _case("darweez40")
        with self.assertRaises(SystemExit) as cm:
            P.pin(_idx(ents), 40, hmap, {2: 5023}, opener_witnesses=wits, opener_evidence={})
        self.assertIn("مطلعُ الآية الثانية", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
