#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""اختباراتُ التسامح الأوسع داخل مسار «المرساة المتنازَع عليها» (‏قرار القائد 2026-11-11 · سندُه موافقةُ المالك 11-07).

الشواهدُ كلُّها **مصنوعةٌ على هيئة** الحالات الثلاث التي ردّها المسارُ مع صحّتها بشهادة شاهدَين (‏لا تُحمَّل من GitHub):
  habdan 3:199: مطلعُ الشاهدَين 3850307 والمنشورُ 3850614 (‏307م.ث > 300).
  nufais 20:106: «فيذرها قاع صفصفاه» والمصحفُ «فيذرها قاعا صفصفا» والآيةُ تنتهي بوقف.
  a_abdl 23:22: نافذةُ المرساة «ومنها تاكلون وعليها» تعبر من آخر 23:21 إلى أوّل 23:22.
وما يُثبت: الردُّ في شاهدٍ واحد · شاهدَين متباعدَين > 400م.ث · نافذةٍ تعبر الحدّ · تطبيعٍ خارج الصيغتين أو على غير آخر كلمة ·
شاهدٍ يتجاوز 1500م.ث؛ والقبولُ في الثلاث، وبقاءُ القاعدة القديمة (‏كلُّ شاهدٍ ضمن 300م.ث) مقبولةً بلا شرط الاتّفاق.

    python -m unittest tools/index_qa/test_heard_disputed_wide.py
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import heard_gate as H                                           # noqa: E402
import pin_heard as P                                            # noqa: E402

SHA = "a" * 64
GMAP = {"sha256": SHA, "fileRef": "f.mp3"}


def _wit(surah, tokens):
    """شاهدٌ مصنوع: tokens = [(كلمة، بدء، نهاية)] بثقة 0.95 ونافذةٍ واسعة تلتصق بها كلمةٌ لا."""
    return {"surah": surah, "riwaya": "hafs", "fileRef": "f.mp3", "sha256": SHA, "model": "medium",
            "computeType": "float32",
            "ayahs": {"1": {"windowMs": [0, 10 ** 9], "words": [{"w": w, "s": s, "e": e, "p": 0.95} for w, s, e in tokens]}}}


def _seq(words, start, step=300):
    return [(w, start + i * step, start + (i + 1) * step) for i, w in enumerate(words)]


class World:
    """آيةٌ منحرفةٌ `ayah` (‏نصُّها own) والآيةُ الأخرى `other` (‏نصُّها oth) ومرساةٌ في ذيل الأخرى والبدءُ المنشور S."""

    def __init__(self, surah, ayah, other, own, oth, S, A, raw_last=None):
        self.surah, self.ayah, self.other, self.own, self.oth, self.S, self.A = surah, ayah, other, own, oth, S, A
        self.raw_last = raw_last

    def ref(self, s, a):
        return list({self.ayah: self.own, self.other: self.oth}[a])

    def witness(self, head_ms, head_words=None, anchor_tokens=None):
        """رمزُ الشاهد: ذيلُ الآية الأخرى مغطّياً المرساة، ثمّ مطلعُ الآية عند head_ms."""
        tail = anchor_tokens if anchor_tokens is not None else _seq(self.oth[-4:], self.A - 700)
        head = _seq(head_words if head_words is not None else self.own[:3], head_ms)
        return _wit(self.surah, tail + head)

    def verdict(self, wits, n=200, raw_last="same"):
        rows = [{"ayah": self.ayah, "status": "dev", "startMs": self.S, "anchorMs": self.A}]
        src = {r: H.disputed_src_rec(w) for r, w in wits.items()}
        idx = {"riwaya": "hafs", "transform": {"disputedAnchors": {str(self.surah): {
            str(self.ayah): {"otherAyah": self.other, "witnesses": wits}}}}}
        rl = self.raw_last if raw_last == "same" else raw_last
        why, ev = H.disputed_verdict(self.surah, rows, GMAP, SHA, idx, self.ref, n_ayahs=n, sources=src,
                                     raw_last=(lambda s, a: rl))
        return why, ev, rows[0]["status"]

    def one(self, wit, head_tol=H.TOL_MS):
        return H.disputed_one(wit, self.surah, self.ayah, self.S, self.A, self.other, self.ref, GMAP, SHA,
                              head_tol=head_tol, raw_last=self.raw_last)


# ‏habdan 3:199 — المنشور 3850614
HAB = World(3, 199, 198, ["وان", "من", "اهل", "الكتاب", "لمن", "يؤمن"], ["ان", "الله", "سريع", "الحساب", "يا", "ايها"],
            S=3850614, A=3830000)


def _pair(w, ha, hb, **kw):
    return {"run-a": w.witness(ha, **kw), "run-b": w.witness(hb, **kw)}


class Accepted(unittest.TestCase):
    def test_habdan_3_199_head_307_off_with_agreeing_witnesses(self):
        # ‏3850307 بعيدٌ عن المنشور 3850614 بـ307م.ث (>300)، والشاهدان متّفقان (‏3850307 و3850330: 23م.ث ≤ 400)
        why, ev, st = HAB.verdict(_pair(HAB, 3850307, 3850330))
        self.assertIsNone(why)
        self.assertEqual(st, "disputed")
        w = ev["accepted"]["199"]["witnesses"]
        self.assertEqual((w["run-a"]["headMs"], w["run-b"]["headMs"]), (3850307, 3850330))
        self.assertEqual(ev["accepted"]["199"]["otherAyah"], 198)

    def test_agreement_exactly_at_400_accepted_and_up_to_1500_off(self):
        why, _ev, st = HAB.verdict(_pair(HAB, HAB.S - 1100, HAB.S - 1500))        # ‏1500 = TOL_MS تُقبل؛ والفرقُ 400
        self.assertIsNone(why)
        self.assertEqual(st, "disputed")

    def test_old_rule_still_accepted_without_agreement_condition(self):
        # ‏كلُّ شاهدٍ ضمن 300م.ث من المنشور (‏-250 و+290: بينهما 540 > 400) ⇒ مقبولٌ كما كان
        why, _ev, st = HAB.verdict(_pair(HAB, HAB.S - 250, HAB.S + 290))
        self.assertIsNone(why)
        self.assertEqual(st, "disputed")

    def test_old_rule_exactly_300_both(self):
        self.assertIsNone(HAB.verdict(_pair(HAB, HAB.S - 300, HAB.S + 300))[0])

    def test_nufais_20_106_last_word_hā_sakt_accepted_as_a_stop_form(self):
        # ‏آيةٌ من ثلاث كلماتٍ تنتهي بوقف: «فيذرها قاعا صفصفا»؛ ويُسمع آخرُها «صفصفاه» (‏هاء السكت) ⇒ يُثبَت مطلعُها بالآية كلِّها
        n = World(20, 106, 105, ["فيذرها", "قاعا", "صفصفا"], ["ويسالونك", "عن", "الجبال", "فقل", "ينسفها", "ربي"],
                  S=2000000, A=1980000, raw_last="صَفْصَفًا")
        why, _ev, st = n.verdict(_pair(n, 2000500, 2000540, head_words=["فيذرها", "قاعا", "صفصفاه"]))
        self.assertIsNone(why)
        self.assertEqual(st, "disputed")

    def test_nufais_20_106_as_heard_stays_refused_because_of_qa3(self):
        # ‏«فيذرها قاع صفصفاه»: «قاع» ليست آخرَ كلمةٍ فلا تُطبَّع، فتبقى مردودةً (‏وهو الصواب)
        n = World(20, 106, 105, ["فيذرها", "قاعا", "صفصفا"], ["ويسالونك", "عن", "الجبال", "فقل", "ينسفها", "ربي"],
                  S=2000000, A=1980000, raw_last="صَفْصَفًا")
        why, ev, st = n.verdict(_pair(n, 2000500, 2000540, head_words=["فيذرها", "قاع", "صفصفاه"]))
        self.assertIn("لا يُسمع مطلعُ الآية كلمةً بكلمة", why)
        self.assertEqual(st, "dev")

    def test_a_abdl_23_22_three_words_of_other_ayah_alone_cover_the_anchor(self):
        # ‏آخرُ 23:21 «ولكم فيها منافع كثيرة ومنها تاكلون» وأوّلُ 23:22 «وعليها وعلى الفلك تحملون»؛ المرساةُ داخل «تاكلون».
        a = World(23, 22, 21, ["وعليها", "وعلي", "الفلك", "تحملون"],
                  ["ولكم", "فيها", "منافع", "كثيره", "ومنها", "تاكلون"], S=900000, A=880000)
        toks = _seq(["منافع", "كثيره", "ومنها", "تاكلون", "وعليها"], 880000 - 900)   # ‏المرساةُ عند «ومنها»؛ وفيها نافذةٌ خالصةٌ من 23:21
        why, ev, st = a.verdict(_pair(a, 900100, 900140, anchor_tokens=toks))
        self.assertIsNone(why)
        self.assertEqual(st, "disputed")
        self.assertIn("ومنها", ev["accepted"]["22"]["witnesses"]["run-a"]["anchorText"])


class ShortAyahs(unittest.TestCase):
    def test_short_ayah_proved_by_the_whole_ayah_and_short_other_ayah_by_itself(self):
        # ‏آيةٌ من كلمتين تُثبَت بنصّها كلِّه، والآيةُ الأخرى كلمتان (‏أقصرُ من W_K) تُسمعان عند المرساة
        w = World(69, 2, 1, ["ما", "الحاقه"], ["الحاقه", "ما"], S=500000, A=480000)
        toks = _seq(["الحاقه", "ما"], 480000 - 200)
        why, _ev, st = w.verdict(_pair(w, 500200, 500240, head_words=["ما", "الحاقه"], anchor_tokens=toks))
        self.assertIsNone(why)
        self.assertEqual(st, "disputed")

    def test_short_ayah_not_proved_by_a_prefix_only(self):
        w = World(69, 2, 1, ["ما", "الحاقه"], ["الحاقه", "ما"], S=500000, A=480000)
        toks = _seq(["الحاقه", "ما"], 480000 - 200)
        why, _ev, st = w.verdict(_pair(w, 500200, 500240, head_words=["ما", "غيرها"], anchor_tokens=toks))
        self.assertIsNotNone(why)
        self.assertEqual(st, "dev")


class Refused(unittest.TestCase):
    def test_single_witness(self):
        why, _ev, st = HAB.verdict({"run-a": HAB.witness(3850307)})
        self.assertIn("شاهدان", why)
        self.assertEqual(st, "dev")

    def test_two_witnesses_more_than_400_apart(self):
        why, _ev, st = HAB.verdict(_pair(HAB, HAB.S - 700, HAB.S - 1200))          # ‏بينهما 500
        self.assertIn("بعيدٌ عن المنشور", why)
        self.assertIn("400", why)
        self.assertEqual(st, "dev")

    def test_one_far_one_near_apart_more_than_400(self):
        # ‏شاهدٌ ضمن 300 وآخرُ على 700: بينهما 700 > 400 والثاني تجاوز 300 ⇒ يلزم الاتّفاق ولا اتّفاق
        why, _ev, st = HAB.verdict(_pair(HAB, HAB.S - 50, HAB.S - 700))
        self.assertIn("400", why)
        self.assertEqual(st, "dev")

    def test_witness_beyond_1500(self):
        why, _ev, st = HAB.verdict(_pair(HAB, HAB.S - 1600, HAB.S - 1620))         # ‏متّفقان لكنْ فوق TOL_MS
        self.assertIn("(>1500م.ث)", why)
        self.assertEqual(st, "dev")

    def test_window_crossing_the_boundary_is_not_counted(self):
        # ‏23:22: لا نافذةَ خالصةً من 23:21 تغطّي المرساة؛ والتي تغطّيها «ومنها تاكلون وعليها» تعبر إلى 23:22 ⇒ تُردّ
        a = World(23, 22, 21, ["وعليها", "وعلي", "الفلك", "تحملون"],
                  ["ولكم", "فيها", "منافع", "كثيره", "ومنها", "تاكلون"], S=900000, A=880000)
        toks = _seq(["ومنها", "تاكلون", "وعليها"], 879000)                        # ‏المرساةُ عند «وعليها» (‏879900+...)
        toks = [("ومنها", 879000, 879300), ("تاكلون", 879300, 879600), ("وعليها", 879600, 880400)]
        why, _ev, st = a.verdict(_pair(a, 900100, 900140, anchor_tokens=toks))
        self.assertIn("ليس من نصّ 23:21", why)
        self.assertEqual(st, "dev")

    def test_normalisation_not_on_the_last_word(self):
        # ‏آيةٌ طويلةٌ (‏آخرُ كلمةٍ منها ليس في المطلع): لا تطبيعَ حتى لو جاءت الكلمةُ الثالثةُ بهاء السكت
        why, _ev, st = HAB.verdict(_pair(HAB, 3850307, 3850330, head_words=["وان", "من", "اههل"]))
        self.assertIn("لا يُسمع مطلعُ الآية كلمةً بكلمة", why)
        self.assertEqual(st, "dev")
        why, _ev, _ = HAB.verdict(_pair(HAB, 3850307, 3850330, head_words=["وان", "من", "اهله"]))   # ‏هاءٌ على غير آخر كلمة
        self.assertIsNotNone(why)

    def test_hā_sakt_on_a_middle_word_of_a_whole_ayah_refused(self):
        # ‏آيةٌ من ثلاث كلماتٍ: الهاءُ على الكلمة الوسطى (‏لا آخرِها) لا تُطبَّع ولو كان آخرُها سليماً
        n = World(20, 106, 105, ["فيذرها", "قاعا", "صفصفا"], ["ويسالونك", "عن", "الجبال", "فقل", "ينسفها", "ربي"],
                  S=2000000, A=1980000, raw_last="صَفْصَفًا")
        for heard in (["فيذرها", "قاعاه", "صفصفا"], ["فيذرهاه", "قاعا", "صفصفاه"]):
            why, _ev, st = n.verdict(_pair(n, 2000500, 2000540, head_words=heard))
            self.assertIn("لا يُسمع مطلعُ الآية كلمةً بكلمة", why)
            self.assertEqual(st, "dev")

    def test_normalisation_other_forms_refused_on_the_last_word(self):
        n = World(20, 106, 105, ["فيذرها", "قاعا", "صفصفا"], ["ويسالونك", "عن", "الجبال", "فقل", "ينسفها", "ربي"],
                  S=2000000, A=1980000, raw_last="صَفْصَفًا")
        for heard in ("صفصفي", "صفصفاك", "صفصف", "صفصفاهه", "صفصفاها", "صفصفاا"):                 # ‏لا صيغةَ ثالثة
            why, _ev, st = n.verdict(_pair(n, 2000500, 2000540, head_words=["فيذرها", "قاعا", heard]))
            self.assertIsNotNone(why, heard)
            self.assertEqual(st, "dev", heard)

    def test_tanween_form_needs_a_fathatan_in_the_mushaf_word(self):
        base = dict(S=2000000, A=1980000)
        oth = ["ويسالونك", "عن", "الجبال", "فقل", "ينسفها", "ربي"]
        ok = World(20, 106, 105, ["فيذرها", "قاعا", "كتب"], oth, raw_last="كُتُبًۭ", **base)           # ‏فتحتان بلا ألف
        self.assertIsNone(ok.verdict(_pair(ok, 2000500, 2000540, head_words=["فيذرها", "قاعا", "كتبا"]))[0])
        no = World(20, 106, 105, ["فيذرها", "قاعا", "كتب"], oth, raw_last="كُتُبٌ", **base)            # ‏تنوينُ ضمٍّ ليس نصباً
        self.assertIsNotNone(no.verdict(_pair(no, 2000500, 2000540, head_words=["فيذرها", "قاعا", "كتبا"]))[0])
        self.assertIsNotNone(ok.verdict(_pair(ok, 2000500, 2000540, head_words=["فيذرها", "قاعا", "كتبا"]),
                                        raw_last=None)[0])

    def test_one_alone_cannot_pass_through_disputed_one_beyond_old_tol_by_default(self):
        # ‏السلوكُ الافتراضيّ لـ`disputed_one` بلا head_tol يبقى 300م.ث (‏لا يُرخى مسارٌ يستدعيه مباشرةً)
        why, d = HAB.one(HAB.witness(3850307), head_tol=None)
        self.assertIsNone(d)
        self.assertIn("(>300م.ث)", why)


class Constants(unittest.TestCase):
    def test_constants_unchanged_and_new_one_named(self):
        self.assertEqual(H.TOL_MS, 1500)
        self.assertEqual(P.W_AGREE_MS, 300)
        self.assertEqual(P.W_K, 3)
        self.assertEqual(H.DISPUTED_AGREE_MS, 400)
        self.assertEqual(H.DISPUTED_MAX_PCT, 10)
        self.assertEqual(H.DISPUTED_MIN_WITNESSES, 2)


if __name__ == "__main__":
    unittest.main()
