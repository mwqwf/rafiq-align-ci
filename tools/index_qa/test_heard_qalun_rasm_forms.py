#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""قائمةُ رسمٍ مغلقةٌ لرواية قالون في مقارِن الشاهد `heard_gate._witness_eval` (‏قرار القائد 2026-11-10 · على نسق #110).

الحالةُ: Whisper يكتب «وجاوزنا» ونصُّ قالون في 10:90 «وجوزنا». كلُّ زوجٍ هنا مقيسٌ من تفريغٍ حقيقيٍّ في المستودع
ومثبَتٌ بموضعٍ يُقرأ آلياً من `text_qalun.jz`. القائمةُ مفتاحُها الرواية: لا تسري على حفص. ولا قاعدةَ عامّة ولا مسافةَ تحرير."""
import os
import sys
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import heard_gate as H  # noqa: E402
import pin_heard as PH  # noqa: E402

SHA, REF = "b" * 64, "https://x/qalun.mp3"
GMAP = {"sha256": SHA, "fileRef": REF}
START = 1_000_000

# زوجٌ ⇒ موضعٌ مثبَتٌ (‏سورة، آية) من نصّ قالون
PAIRS = {m: (q, H.QALUN_RASM_WITNESS[q]) for m, q in H.RASM_FORMS_BY_RIWAYA["qalun"].items()}


def edge_slice(mushaf, s, a):
    """شريحةٌ من آية قالون الحقيقيّة تقع فيها كلمةُ الزوج في طرفها (‏مقارِنُ الشاهد لا يقابل إلا أوّلَ W_K وآخرَ W_K كلمة؛
    فكلمةٌ في وسط الآية تمرّ بلا قائمة). تُرجع (من، إلى)."""
    q = PH.ref_words_for("qalun", s, a)
    i = q.index(mushaf)
    return (i, min(len(q), i + 6)) if i + 6 <= len(q) else (max(0, i - 5), i + 1)


def witness(riwaya, s, a, repl=None, ref=None, p=0.9):
    """شاهدٌ لآيةٍ واحدةٍ كلماتُه كلماتُ المرجع نفسِه (‏الصحيحُ تماماً) إلا ما في repl {قيمةُ المرجع: ما كتبه Whisper}."""
    ref = ref or PH.ref_words_for(riwaya, s, a)
    repl = repl or {}
    words = [{"w": repl.get(w, w), "s": START + i * 450, "e": START + i * 450 + 350, "p": p} for i, w in enumerate(ref)]
    hi = START + len(ref) * 450 + 3000
    return {"surah": s, "riwaya": riwaya, "fileRef": REF, "sha256": SHA, "model": "medium", "computeType": "float32",
            "ayahs": {str(a): {"windowMs": [START - 3000, hi], "words": words}}}


def sliced(mushaf, s, a):
    lo, hi = edge_slice(mushaf, s, a)
    return lambda riw, ss, aa: PH.ref_words_for(riw, ss, aa)[lo:hi]


def ev(wit, s, a, riwaya, ref_words=None):
    res, bad = H._witness_eval(wit, s, GMAP, SHA, riwaya, {a: START}, [a], ref_words)
    assert bad is None, bad
    return res[a]


def pair_ok(modern, mushaf, s, a, riwaya="qalun"):
    rw = sliced(mushaf, s, a)
    ref = rw(riwaya, s, a)
    return ev(witness(riwaya, s, a, {mushaf: modern}, ref=ref), s, a, riwaya, ref_words=rw)[0]


class TextWitness(unittest.TestCase):
    """الشاهدُ النصّيّ: الشكلُ القالونيّ موجودٌ فعلاً في الموضع المسمّى من ملفّ نصّ قالون."""

    def test_every_pair_has_a_witness_position_in_qalun_text(self):
        self.assertEqual(set(H.QALUN_RASM_WITNESS), set(H.RASM_FORMS_BY_RIWAYA["qalun"].values()))
        for mushaf, (s, a) in H.QALUN_RASM_WITNESS.items():
            self.assertIn(mushaf, PH.ref_words_for("qalun", s, a), f"{mushaf} ليس في قالون {s}:{a}")

    def test_originating_case_10_90(self):
        self.assertEqual(H.QALUN_RASM_WITNESS["وجوزنا"], (10, 90))
        self.assertEqual(PH.ref_words_for("qalun", 10, 90)[0], "وجوزنا")

    def test_modern_key_is_not_the_text_itself(self):
        """المفتاحُ (‏الإملاء الحديث) ليس في موضع الشاهد من النصّ؛ وإلا فالزوجُ بلا معنى."""
        for modern, (mushaf, (s, a)) in PAIRS.items():
            self.assertNotIn(modern, PH.ref_words_for("qalun", s, a))

    def test_eight_pairs_closed(self):
        self.assertEqual(len(PAIRS), 8)
        self.assertEqual(set(H.RASM_FORMS_BY_RIWAYA), {"qalun"})


class EachPairPasses(unittest.TestCase):
    def test_each_pair_passes_with_qalun(self):
        for modern, (mushaf, (s, a)) in PAIRS.items():
            with self.subTest(pair=modern):
                self.assertTrue(pair_ok(modern, mushaf, s, a), modern)

    def test_baseline_without_pairs_each_is_rejected(self):
        """العطبُ الأصل: بلا هذه الأزواج يردّ مقارِنُ الشاهد كلَّ حالة (‏وهذا ما يجعل الاختبارَ أعلاه ذا معنى)."""
        for modern, (mushaf, (s, a)) in PAIRS.items():
            with self.subTest(pair=modern), mock.patch.dict(H.RASM_FORMS_BY_RIWAYA, {"qalun": {}}):
                self.assertFalse(pair_ok(modern, mushaf, s, a))

    def test_true_reading_still_passes(self):
        for _m, (mushaf, (s, a)) in PAIRS.items():
            rw = sliced(mushaf, s, a)
            self.assertTrue(ev(witness("qalun", s, a, ref=rw("qalun", s, a)), s, a, "qalun", ref_words=rw)[0])


class OutsideListAndScope(unittest.TestCase):
    def test_word_outside_list_with_same_difference_rejected(self):
        """«الرحمان» بدل «الرحمن» (‏1:3) فرقُ الألف نفسُه لكنّه خارج القائمة ⇒ لا يمرّ."""
        self.assertNotIn("الرحمان", H.rasm_forms("qalun"))
        self.assertFalse(ev(witness("qalun", 1, 3, {"الرحمن": "الرحمان"}), 1, 3, "qalun")[0])

    def test_one_letter_apart_from_listed_rejected(self):
        self.assertFalse(pair_ok("وجاوزنه", "وجوزنا", 10, 90))
        self.assertFalse(pair_ok("الانساان", "الانسن", 42, 48))

    def test_qalun_pairs_do_not_apply_to_hafs(self):
        """المرجعُ حفصٌ: الشكلُ في 10:90 مشتركٌ في النصّ، لكنّ الزوجَ قالونيٌّ فلا يسري على حفص."""
        self.assertIn("وجوزنا", PH.ref_words_for("hafs", 10, 90))
        self.assertFalse(pair_ok("وجاوزنا", "وجوزنا", 10, 90, riwaya="hafs"))
        self.assertTrue(pair_ok("وجاوزنا", "وجوزنا", 10, 90, riwaya="qalun"))

    def test_other_riwayat_unaffected(self):
        for r in ("hafs", "warsh", "douri", "shuba", "sousi", None):
            self.assertEqual(H.rasm_forms(r), H.RASM_FORMS)

    def test_general_list_unchanged(self):
        self.assertEqual(len(H.RASM_FORMS), 16)
        self.assertEqual(H.RASM_FORMS["الصلاه"], "الصلوه")

    def test_general_forms_still_work_for_qalun(self):
        self.assertIn("الصلاه", H.rasm_forms("qalun"))

    def test_ref_side_explicit_form_still_matches_itself(self):
        """مرجعٌ فيه الشكلُ الحديثُ نفسُه (‏«الكتاب» صريحةُ الألف) والتفريغُ مثله ⇒ يمرّ (‏توحيدُ الطرفين)."""
        ref = ["الكتاب", "ربنا"]
        w = witness("qalun", 2, 2, ref=ref)
        self.assertTrue(ev(w, 2, 2, "qalun", ref_words=lambda *_: ref)[0])

    def test_fragment_token_not_unified(self):
        w = {"surah": 1, "ayahs": {"1": {"words": [{"w": "الكتاب والانسان", "s": 1, "e": 2, "p": 1}]}}}
        self.assertEqual(H.rasm_unify_wit(w, "qalun")["ayahs"]["1"]["words"][0]["w"], "الكتاب والانسان")

    def test_riwaya_defaults_keep_old_signatures(self):
        self.assertEqual(H.rasm_unify_ref(["الصلاه"]), ["الصلوه"])
        self.assertEqual(H.rasm_unify_ref(["الكتاب"]), ["الكتاب"])
        self.assertEqual(H.rasm_unify_ref(["الكتاب"], "qalun"), ["الكتب"])


class Mutations(unittest.TestCase):
    """أزِل كلَّ شرطٍ وحدَه ⇒ يجب أن يموت اختبارٌ بعينه (‏المحاكاةُ تُجري الفحصَ تحت التحوير وتشترط إخفاقَه)."""

    def killed(self, mutant, check):
        with mutant:
            with self.assertRaises(AssertionError):
                check()

    # فحوصٌ (‏تمرّ على الشيفرة الأصلية)
    @staticmethod
    def chk_pairs():
        for modern, (mushaf, (s, a)) in PAIRS.items():
            assert pair_ok(modern, mushaf, s, a), modern

    @staticmethod
    def chk_hafs_scope():
        assert not pair_ok("وجاوزنا", "وجوزنا", 10, 90, riwaya="hafs")

    @staticmethod
    def chk_outside_list():
        assert not ev(witness("qalun", 1, 3, {"الرحمن": "الرحمان"}), 1, 3, "qalun")[0]

    @staticmethod
    def chk_ref_side():
        ref = ["الكتاب", "ربنا"]
        assert ev(witness("qalun", 2, 2, ref=ref), 2, 2, "qalun", ref_words=lambda *_: ref)[0]

    @staticmethod
    def chk_fragment():
        w = {"surah": 1, "ayahs": {"1": {"words": [{"w": "الكتاب والانسان", "s": 1, "e": 2, "p": 1}]}}}
        assert H.rasm_unify_wit(w, "qalun")["ayahs"]["1"]["words"][0]["w"] == "الكتاب والانسان"

    @staticmethod
    def chk_witness_text():
        for mushaf, (s, a) in H.QALUN_RASM_WITNESS.items():
            assert mushaf in PH.ref_words_for("qalun", s, a)
        assert set(H.QALUN_RASM_WITNESS) == set(H.RASM_FORMS_BY_RIWAYA["qalun"].values())

    @staticmethod
    def chk_one_letter():
        assert not pair_ok("وجاوزنه", "وجوزنا", 10, 90)

    def test_checks_pass_on_real_code(self):
        for c in (self.chk_pairs, self.chk_hafs_scope, self.chk_outside_list, self.chk_ref_side, self.chk_fragment,
                  self.chk_witness_text, self.chk_one_letter):
            c()

    def test_m1_drop_riwaya_key_killed(self):
        """شرط: الزوجُ بمفتاح الرواية ⇒ إزالتُه (‏يسري على الجميع) يقتل اختبارَ حفص."""
        allq = {**H.RASM_FORMS, **H.RASM_FORMS_BY_RIWAYA["qalun"]}
        self.killed(mock.patch.object(H, "rasm_forms", lambda r=None: allq), self.chk_hafs_scope)

    def test_m2_empty_table_killed(self):
        self.killed(mock.patch.dict(H.RASM_FORMS_BY_RIWAYA, {"qalun": {}}), self.chk_pairs)

    def test_m3_generic_alef_rule_killed(self):
        """شرط: لا قاعدةَ عامّة ⇒ إضافةُ «احذف كلَّ ألف» تقتل اختبارَ خارج القائمة (‏الرحمان)."""
        class Gen(dict):
            def __contains__(self, k):
                return True

            def __getitem__(self, k):
                return k.replace("ا", "")

            def get(self, k, d=None):
                return k.replace("ا", "") if k != "" else d
        self.killed(mock.patch.object(H, "rasm_forms", lambda r=None: Gen()), self.chk_outside_list)

    def test_m4_fuzzy_distance_killed(self):
        """شرط: لا مسافةَ تحرير ⇒ توحيدُ كلِّ كلمةٍ قريبةٍ (‏حرفٌ واحد) من مفتاحٍ يقتل اختبارَ الحرف الواحد."""
        real = H.rasm_forms

        def fuzzy(r=None):
            base = real(r)

            class F(dict):
                def get(self, k, d=None):
                    for key, v in base.items():
                        if k == key or (abs(len(k) - len(key)) <= 1 and sum(x != y for x, y in zip(k, key)) <= 1):
                            return v
                    return d

                def __contains__(self, k):
                    return self.get(k) is not None

                def __getitem__(self, k):
                    return self.get(k)
            return F(base)
        self.killed(mock.patch.object(H, "rasm_forms", fuzzy), self.chk_one_letter)

    def test_m5_ref_side_not_unified_killed(self):
        self.killed(mock.patch.object(H, "rasm_unify_ref", lambda ref, riwaya=None: ref), self.chk_ref_side)

    def test_m6_fragment_guard_removed_killed(self):
        def loose(wit, riwaya=None):
            forms = H.rasm_forms(riwaya)
            out = dict(wit)
            out["ayahs"] = {a: dict(rec, words=[dict(w, w=" ".join(forms.get(t, t) for t in H._ncommon(w["w"])))
                                               for w in rec["words"]]) for a, rec in wit["ayahs"].items()}
            return out
        self.killed(mock.patch.object(H, "rasm_unify_wit", loose), self.chk_fragment)

    def test_m7_wrong_value_killed(self):
        """شرط: الشكلُ القالونيّ موجودٌ فعلاً في الموضع ⇒ قيمةٌ غلط تقتل اختبارَ الشاهد (‏والتمرير)."""
        bad = dict(H.RASM_FORMS_BY_RIWAYA["qalun"], **{"وجاوزنا": "وجازنا"})
        self.killed(mock.patch.dict(H.RASM_FORMS_BY_RIWAYA, {"qalun": bad}), self.chk_pairs)
        wit = dict(H.QALUN_RASM_WITNESS, **{"وجوزنا": (10, 91)})
        self.killed(mock.patch.object(H, "QALUN_RASM_WITNESS", wit), self.chk_witness_text)

    def test_m8_pair_removed_each_killed(self):
        """كلُّ زوجٍ وحدَه: حذفُه يقتل اختبارَ الأزواج."""
        for modern in list(H.RASM_FORMS_BY_RIWAYA["qalun"]):
            less = {k: v for k, v in H.RASM_FORMS_BY_RIWAYA["qalun"].items() if k != modern}
            with self.subTest(removed=modern):
                self.killed(mock.patch.dict(H.RASM_FORMS_BY_RIWAYA, {"qalun": less}), self.chk_pairs)


if __name__ == "__main__":
    unittest.main()
