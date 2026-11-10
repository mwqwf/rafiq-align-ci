#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""اختباراتُ حدّ `--trim` من شاهدَي Whisper في `pin_heard.py` (‏2026-11-10 · مسودّة لا تُدمج).

الحالةُ الحقيقيّة: الكردي 55:29/30 (‏بصمة 055.mp3 = 60b66c8b). خريطةُ السماع (‏ctc_heard_probe 42746663915):
أداءُ 29 السماعيّ [176500، 183585] ومرساتُها القسريّة [175839، 187988]، وتثبيتُ 30 على أدائها الثاني 191830.
والشواهدُ الحقيقيّة الثلاثة في `testdata/kurdi_55_29_30/`:
  42742400575 (‏نافذة 183000–200500): «وفي@183000» ملصوقةٌ ببدء النافذة · «شأنٍ@183820» · «فبأي@187160».
  42748189731 (‏نافذة 172000–192500): «هو@182840 في@183380 شأن@183880» · «فبأي@185160» · «ربكم» لا «ربكما».
  42749137847 (‏نافذة 178000–196000): «هو@182840 (0.41)» · «شأن@183880» · «فبأي@184760» · «ربكم».
⇒ بدءُ «شأنٍ» ثابتٌ في الثلاثة (‏183820–183880)، وبدءُ «فبأي» يتفرّق 2400م.ث (‏184760 · 185160 · 187160).
والقياسُ الصوتيّ (‏055.raw · عبورُ الصفر لكلّ 50م.ث) يضع احتكاكَ الشين عند 183750–183850 واحتكاكَ الفاء عند
≈187030، وبينهما صوتٌ مجهورٌ متّصلٌ بلا احتكاك (‏غنّةُ الإخفاء في «شأنٍ فـ») ⇒ 184760/185160 أثرُ تقطيعٍ عند Whisper.

    python -m pytest -q tools/index_qa/test_pin_heard_trim_witness.py
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

TD = HERE / "testdata" / "kurdi_55_29_30"
HMAP = json.loads((TD / "heard_s055_28_31.json").read_text(encoding="utf-8"))
W = {r: json.loads((TD / f"whisper_{r}.json").read_text(encoding="utf-8"))
     for r in ("42742400575", "42748189731", "42749137847")}
SHA, URL = HMAP["sha256"], HMAP["fileRef"]
REF = {29: ["يساله", "من", "في", "السماوات", "والارض", "كل", "يوم", "هو", "في", "شان"],
       30: ["فباي", "الا", "ربكما", "تكذبان"]}


def ref_words(_s, a):
    return REF[a]


def _idx():
    ents = [{"ayahId": "55:28", "startMs": 168234, "endMs": 175139, "fileRef": URL},
            {"ayahId": "55:29", "startMs": 175839, "endMs": 187988, "fileRef": URL},
            {"ayahId": "55:30", "startMs": 187988, "endMs": 199135, "fileRef": URL},
            {"ayahId": "55:31", "startMs": 199856, "endMs": 204499, "fileRef": URL}]
    return {"entries": ents, "audioSha256": [SHA], "engineVersion": "align-0.2"}


def _composite():
    """⚠️ زوجٌ **مركّبٌ** لاختبار القاعدة لا دليلٌ: لا شاهدَ حقيقيٌّ واحدٌ يجمع خاتمةَ 29 ومطلعَ 30 كاملين.
    التوقيتاتُ منقولةٌ من الشواهد الحقيقيّة: الخاتمةُ من 42748189731 والمطلعُ من 42742400575 (‏فبأي@187160)."""
    words = [{"w": "هو", "s": 182840, "e": 183380, "p": 0.58},
             {"w": "في", "s": 183380, "e": 183880, "p": 0.9982},
             {"w": "شأنٍ", "s": 183880, "e": 187160, "p": 0.9368},
             {"w": "فبأي", "s": 187160, "e": 188320, "p": 0.7891},
             {"w": "آلاء", "s": 188320, "e": 189800, "p": 0.9492},
             {"w": "ربكما", "s": 189800, "e": 191460, "p": 0.8006}]
    base = {k: W["42742400575"][k] for k in ("surah", "riwaya", "fileRef", "sha256", "model", "computeType")}
    a = dict(base, ayahs={"30": {"windowMs": [178000, 196000], "words": words}})
    b = dict(copy.deepcopy(a), model="small")
    for w in b["ayahs"]["30"]["words"]:
        w["s"] += 60
    return {"syn-a": a, "syn-b": b}


def _run(trim, wits):
    return P.pin(_idx(), 55, HMAP, {30: 191830}, {29: trim}, ref_words=ref_words, trim_witnesses=wits,
                 trim_evidence={})


class RealWitnesses(unittest.TestCase):
    def test_reference_is_the_mushaf_text(self):
        self.assertEqual(P.ref_words_for("hafs", 55, 29)[-3:], REF[29][-3:])
        self.assertEqual(P.ref_words_for("hafs", 55, 30)[:3], REF[30][:3])

    def test_sha_of_every_witness_is_the_map_sha(self):
        for w in W.values():
            self.assertEqual(w["sha256"], SHA)

    def test_window_start_clamp_is_not_a_measurement(self):
        b, why = P._junction(W["42742400575"], REF[29], REF[30])
        self.assertIsNone(b)

    def test_truncated_head_word_refused(self):
        for r in ("42748189731", "42749137847"):
            b, _why = P._junction(W[r], REF[29], REF[30])
            self.assertIsNone(b, r)

    def test_real_witnesses_cannot_certify_any_trim(self):
        for t in (183585, 184760, 185160, 187160, 187988):
            with self.assertRaises(SystemExit):
                _run(t, dict(W))

    def test_one_witness_is_not_enough(self):
        with self.assertRaises(SystemExit) as cm:
            _run(187160, {"syn-a": _composite()["syn-a"]})
        self.assertIn("شاهدان", str(cm.exception))

    def test_trim_without_witness_refused(self):
        """⛔ (‏#99 · قرار القائد) `--trim` بلا شاهدَين مردودٌ أيّاً كانت قيمتُه."""
        for t in (183585, 187160, 187988):
            with self.assertRaises(SystemExit) as cm:
                P.pin(_idx(), 55, HMAP, {30: 191830}, {29: t})
            self.assertIn("بلا شاهدَي Whisper", str(cm.exception))

    def test_wrong_ctc_bounds_183585_and_187988_refused(self):
        """الحدّان المقيسان بـCTC اللذان كانا يُقبلان قبل #99 (‏183585 يقطع «شأنٍ» · 187988 يُدخل «فبأي»)
        يُردّان الآن بلا شاهد، وبالشواهد الحقيقيّة، وبالزوج المركّب الذي يقبل 187160."""
        for t in (183585, 187988):
            for wits in (None, dict(W), _composite()):
                with self.assertRaises(SystemExit):
                    P.pin(_idx(), 55, HMAP, {30: 191830}, {29: t}, ref_words=ref_words,
                          trim_witnesses=wits, trim_evidence={})

class RuleOnComposite(unittest.TestCase):
    def test_187160_accepted_and_evidence_recorded(self):
        ev = {}
        out, report, _ch = P.pin(_idx(), 55, HMAP, {30: 191830}, {29: 187160}, ref_words=ref_words,
                                 trim_witnesses=_composite(), trim_evidence=ev)
        e = {x["ayahId"]: x for x in out["entries"]}
        self.assertEqual(e["55:29"]["endMs"], 187160)
        self.assertEqual(e["55:30"]["startMs"], 191830)
        self.assertEqual(sorted(ev[29]["witnesses"]), ["syn-a", "syn-b"])
        self.assertEqual(ev[29]["prevHeardEndMs"], 183585)
        self.assertTrue(any("شاهدَي Whisper" in r for r in report))

    def test_boundary_cutting_shan_refused(self):
        for t in (183585, 183880, 184760, 185160):
            with self.assertRaises(SystemExit):
                _run(t, _composite())

    def test_boundary_putting_fabi_into_29_refused(self):
        with self.assertRaises(SystemExit):
            _run(187988, _composite())

    def test_witnesses_disagreeing_refused(self):
        w = _composite()
        for x in w["syn-b"]["ayahs"]["30"]["words"][3:]:
            x["s"] -= 2400                      # بدءُ «فبأي» عند 184820 كما في 42749137847
        w["syn-b"]["ayahs"]["30"]["words"][2]["e"] -= 2400
        with self.assertRaises(SystemExit) as cm:
            _run(187160, w)
        self.assertIn("يختلفان", str(cm.exception))

    def test_other_audio_refused(self):
        w = _composite()
        w["syn-b"]["sha256"] = "b" * 64
        with self.assertRaises(SystemExit):
            _run(187160, w)

    def test_low_confidence_refused(self):
        w = _composite()
        w["syn-b"]["ayahs"]["30"]["words"][0]["p"] = 0.41      # «هو» كما في 42749137847
        with self.assertRaises(SystemExit):
            _run(187160, w)

    def test_boundary_not_before_next_pin(self):
        with self.assertRaises(SystemExit):
            P.trim_from_witnesses(_composite(), HMAP, 55, 29, 187160, REF[29], REF[30], 187000, SHA)

if __name__ == "__main__":
    unittest.main()
