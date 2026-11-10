#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""اختباراتُ قاعدة المِرساة الضعيفة في بوّابة السماع (‏تشديد 2026-11-10 · `heard_gate.weak_verdict`).

القاعدة: في سورةٍ معدّلة، كلُّ آيةٍ تخالف حدودُها المنشورَ وجودةُ مرساتها في خريطة السماع < 0.5 تردّ السورة،
إلا أن يشهد لها شاهدُ Whisper بنصّها في موضعها (‏شروطُ `pin_heard._whisper_check`).

الحالاتُ الحقيقيّة في `testdata/heard_weak_cases.json` (‏مقتطفاتٌ من الدلو: مداخلُ السورة المعدّلة وخريطتُها كما حفظتها
heard_gate وبصمةُ صوتها): `kurdi.e8a49589` و`kurdi.1c0c20e6` مرّا بالبوّابة القديمة ومدخلُ 4:127 فيهما صوتُ آيتين أخريين؛
و`rashad.f2f1cb34` و`muftah_sultany.d1cc43bf` ترقيتان سليمتان سابقتان."""
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import heard_gate as H  # noqa: E402

DATA = json.load(open(os.path.join(HERE, "testdata", "heard_weak_cases.json"), encoding="utf-8"))
BASE = ["الحمد", "لله", "رب", "العالمين", "الرحمن", "الرحيم", "مالك", "يوم"]


def ref_words(_riw, _s, _a):
    return list(BASE)


def real(case):
    c = DATA["cases"][case]
    shas = [""] * 114
    shas[c["surah"] - 1] = c["audioSha256"]
    cand = {"riwaya": c["riwaya"], "reciterId": c["reciterId"], "entries": c["cand"], "audioSha256": shas}
    pub = {"riwaya": c["riwaya"], "reciterId": c["reciterId"], "entries": c["pub"], "audioSha256": shas}
    return c, cand, pub


class RealCases(unittest.TestCase):
    def test_e8a49589_rejected_for_4_125_127(self):
        c, cand, pub = real("kurdi.e8a49589")
        j = H.judge(cand, pub, c["candSha256"], {4: c["map"]}, dual={})
        self.assertFalse(j["ok"])
        self.assertEqual(j["modified"], [4])
        self.assertEqual(j["weak"]["4"]["weak"], [125, 126, 127])
        self.assertEqual(j["weak"]["4"]["missing"], [125, 126, 127])
        self.assertIn("الآيات 125,126,127", j["reason"])
        self.assertIn("مسّها التحويل", j["reason"])

    def test_old_rule_was_blind_to_it(self):
        # الثغرة نفسُها: القاعدةُ القديمة (‏انحرافٌ · نصفٌ · ذيل) لا تردّ السورة لأنّ الثلاثَ «غيرُ مقيسة»
        c, cand, _pub = real("kurdi.e8a49589")
        cs = H.by_surah(cand["entries"])[4]
        rows = H.surah_rows({a: v[0] for a, v in cs.items()}, c["map"])
        self.assertIsNone(H.surah_verdict(rows))
        self.assertEqual([r["ayah"] for r in rows if r["status"] == "unmeasured"], [125, 126, 127])

    def test_real_whisper_witness_does_not_rescue_127(self):
        # شاهدُ التشغيلة 42734080787 على 4115000..4170000 سمع 125 ثمّ 126 ثمّ 128 — فلا يشهد لـ127 في مدخلها
        c, cand, pub = real("kurdi.e8a49589")
        w = DATA["witness_42734080787"]
        self.assertEqual(w["sha256"], c["audioSha256"])
        j = H.judge(cand, pub, c["candSha256"], {4: c["map"]}, witness={4: w}, dual={})
        self.assertFalse(j["ok"])
        self.assertIn(127, j["weak"]["4"]["missing"])
        self.assertNotIn(127, j["weak"]["4"]["witnessed"])

    def test_1c0c20e6_rejected_too(self):
        c, cand, pub = real("kurdi.1c0c20e6")
        j = H.judge(cand, pub, c["candSha256"], {4: c["map"]}, dual={})
        self.assertFalse(j["ok"])
        self.assertIn("الآيات 125,126,127", j["reason"])

    def test_gate_error_recomputes_from_state(self):
        c, cand, pub = real("kurdi.e8a49589")
        rep = {"sha256": c["candSha256"], "maps": {"4": c["map"]}, "ok": True, "reason": None}
        why = H.gate_error(cand, pub, c["candSha256"], rep)       # الحكمُ المكتوب «ok» لا يُصدَّق
        self.assertIsNotNone(why)
        self.assertIn("125,126,127", why)

    def test_known_good_promotions_still_pass(self):
        for case in ("rashad.f2f1cb34", "muftah_sultany.d1cc43bf"):
            with self.subTest(case=case):
                c, cand, pub = real(case)
                j = H.judge(cand, pub, c["candSha256"], {c["surah"]: c["map"]}, dual={})
                self.assertEqual(j["modified"], [c["surah"]])
                self.assertTrue(j["ok"], j["reason"])
                self.assertEqual(j["weak"][str(c["surah"])]["weak"], [])


S, REF, SHA = 9, "https://h/009.mp3", "ab" * 32


def ent(a, st, en):
    return {"ayahId": f"{S}:{a}", "startMs": st, "endMs": en, "fileRef": REF}


def idx(ents):
    shas = [""] * 114
    shas[S - 1] = SHA
    return {"riwaya": "hafs", "reciterId": "x", "entries": ents, "audioSha256": shas}


def cmap(q):
    """{آية: جودة}؛ المِرساةُ عند بدء المرشّح."""
    return {"sha256": SHA, "fileRef": REF, "anchors": {str(a): [[a * 10000, a * 10000 + 9000], v, []] for a, v in q.items()}}


def wit(ayahs, sha=SHA, words=BASE, shift=0):
    out = {"surah": S, "riwaya": "hafs", "fileRef": REF, "sha256": sha, "model": "medium", "computeType": "float32", "ayahs": {}}
    for a in ayahs:
        st = a * 10000 + shift
        out["ayahs"][str(a)] = {"windowMs": [st - 3000, st + 9000],
                                "words": [{"w": w, "s": st + i * 400, "e": st + i * 400 + 300, "p": .9} for i, w in enumerate(words)]}
    return out


N = 10
CAND = [ent(a, a * 10000, a * 10000 + 9000) for a in range(1, N + 1)]
Q_ALL = {a: .9 for a in range(1, N + 1)}


def judge(pub_ents, q, w=None):
    return H.judge(idx(CAND), idx(pub_ents), "c" * 64, {S: cmap(q)}, witness={S: w} if w else None, dual={},
                   ref_words=ref_words)


class Synthetic(unittest.TestCase):
    def test_touched_weak_needs_witness(self):
        pub = [dict(e, startMs=e["startMs"] + 1) if e["ayahId"] == f"{S}:5" else e for e in CAND]
        j = judge(pub, {**Q_ALL, 5: .3})
        self.assertFalse(j["ok"])
        self.assertIn("الآيات 5", j["reason"])

    def test_untouched_weak_is_not_asked(self):
        # آيةٌ ضعيفةُ المِرساة لم يمسّ التحويلُ حدودَها (‏تطابق المنشور) ⇒ لا تُسأل؛ والمعدّلةُ سواها مقيسة
        pub = [dict(e, startMs=e["startMs"] + 1) if e["ayahId"] == f"{S}:2" else e for e in CAND]
        j = judge(pub, {**Q_ALL, 5: .3})
        self.assertTrue(j["ok"], j["reason"])
        self.assertEqual(j["weak"][str(S)]["weak"], [])

    def test_missing_anchor_counts_as_weak(self):
        q = dict(Q_ALL)
        del q[7]
        j = judge([], q)                                   # السورةُ غائبةٌ من المنشور ⇒ كلُّ آياتها ممسوسة
        self.assertFalse(j["ok"])
        self.assertIn("الآيات 7", j["reason"])

    def test_boundary_quality(self):
        self.assertTrue(judge([], {**Q_ALL, 4: .5})["ok"])          # 0.5 مقيسة
        self.assertFalse(judge([], {**Q_ALL, 4: .499})["ok"])

    def test_conclusive_witness_in_place_passes(self):
        j = judge([], {**Q_ALL, 4: .2, 6: .1}, wit([4, 6]))
        self.assertTrue(j["ok"], j["reason"])
        self.assertEqual(j["weak"][str(S)]["witnessed"], [4, 6])

    def test_witness_far_from_candidate_start_rejected(self):
        j = judge([], {**Q_ALL, 4: .2}, wit([4], shift=5000))     # سُمعت الآيةُ بعد بدء مدخلها بـ5ث
        self.assertFalse(j["ok"])

    def test_witness_of_other_text_rejected(self):
        j = judge([], {**Q_ALL, 4: .2}, wit([4], words=["قل", "هو", "الله", "احد", "الله", "الصمد", "لم", "يلد"]))
        self.assertFalse(j["ok"])
        self.assertEqual(j["weak"][str(S)]["missing"], [4])

    def test_witness_of_other_audio_rejected(self):
        j = judge([], {**Q_ALL, 4: .2}, wit([4], sha="cd" * 32))
        self.assertFalse(j["ok"])

    def test_partial_witness_rejected(self):
        j = judge([], {**Q_ALL, 4: .2, 6: .1}, wit([4]))
        self.assertFalse(j["ok"])
        self.assertEqual(j["weak"][str(S)]["missing"], [6])

    def test_sample_surah_not_affected(self):
        # العيّنةُ (‏غيرُ المعدّلة) للتقرير وحده كما كانت: لا تُسأل عن مراسٍ ضعيفة
        pub = list(CAND)
        j = H.judge(idx(CAND), idx(pub), "c" * 64, {S: cmap({**Q_ALL, 4: .2})}, dual={})
        self.assertEqual(j["modified"], [])
        self.assertTrue(j["ok"])

    def test_weak_plan_matches_judge(self):
        cand_ends = {a: [a * 10000, a * 10000 + 9000] for a in range(1, N + 1)}
        pub_ends = {**cand_ends, 3: [30001, 39000]}
        q = {**Q_ALL, 3: .2, 8: .2}
        self.assertEqual(H.weak_plan(cand_ends, pub_ends, cmap(q)), [3])
        self.assertEqual(H.weak_plan(cand_ends, None, cmap(q)), [3, 8])


if __name__ == "__main__":
    unittest.main()
