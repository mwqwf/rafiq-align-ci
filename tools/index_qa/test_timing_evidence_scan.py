"""أداةُ مسح دليل TIMING_UNDER_REPAIR: التصنيفُ وقاعدةُ المسابير الثابتة والشرطُ (٤) — بلا شبكةٍ ولا دلو ولا سرّ.
(المرجعُ يُحقن؛ والشواهدُ مصطنعةٌ تُبنى بالنصّ المسموع عند البدء المنشور.)"""
import unittest

from tools.index_qa import timing_evidence_scan as S

SURAH, N = 2, 24
SHA = f"{7:064x}"
LETTERS = "بتجحخدذرزسشصضطظعغفقكلمنهو"
RA, RB = "1234567", "7654321"


def _w(a, i):
    n = a * 31 + i * 7
    return LETTERS[n % 25] + LETTERS[(n // 25 + 3) % 25] + LETTERS[(n // 7 + 11) % 25]


def ref_words(_riwaya, _s, a):
    return [_w(a, i) for i in range(8)]


STARTS = {a: a * 10000 for a in range(1, N + 1)}


def wit(heard, covered=None, p=0.95):
    """شاهدٌ يسمع عند بدء كلّ آيةٍ منشورةٍ نصَّ heard[a] (‏وهو a نفسُها إن لم تُذكر)."""
    ayahs = {}
    for a in (covered if covered is not None else STARTS):
        o = heard.get(a, a)
        t = STARTS[a]
        words = [{"w": _w(o, k), "s": t - 200 + k * 400, "e": t - 200 + k * 400 + 380, "p": p} for k in range(8)]
        ayahs[str(a)] = {"windowMs": [t - 2000, t + 5000], "words": words}
    return {"surah": SURAH, "riwaya": "hafs", "fileRef": "https://e.org/002.mp3", "sha256": SHA,
            "model": "small", "computeType": "float32", "ayahs": ayahs}


def cls(a_heard, b_heard=None, **kw):
    b_heard = a_heard if b_heard is None else b_heard
    return S.classify([wit(a_heard, **kw), wit(b_heard, **kw)], SURAH, STARTS, "hafs", ref_words, N, SHA)


class Classification(unittest.TestCase):
    def test_in_place(self):
        self.assertEqual(cls({})[5], (S.IN_PLACE, None))

    def test_proven_deviant(self):
        self.assertEqual(cls({5: 9})[5], (S.PROVEN, 9))

    def test_witnesses_disagree_is_undecided(self):
        self.assertEqual(cls({5: 9}, {5: 11})[5][0], S.UNDECIDED)

    def test_one_witness_deviant_other_in_place_is_undecided(self):
        self.assertEqual(cls({5: 9}, {})[5][0], S.UNDECIDED)

    def test_low_confidence_is_not_proven(self):
        r = S.classify([wit({5: 9}, p=0.2), wit({5: 9}, p=0.2)], SURAH, STARTS, "hafs", ref_words, N, SHA)
        self.assertNotEqual(r[5][0], S.PROVEN)

    def test_uncovered_by_either_witness_is_skipped(self):
        r = S.classify([wit({}, covered=[1, 2]), wit({}, covered=[1, 2, 3])], SURAH, STARTS, "hafs", ref_words, N, SHA)
        self.assertEqual(sorted(r), [1, 2])

    def test_wrong_sha_proves_nothing(self):
        bad = dict(wit({5: 9}), sha256=f"{8:064x}")
        r = S.classify([bad, bad], SURAH, STARTS, "hafs", ref_words, N, SHA)
        self.assertNotIn(S.PROVEN, [c for c, _ in r.values()])


class Duplicates(unittest.TestCase):
    def test_text_shared_by_two_ayahs_is_undecided(self):
        def rw(r, s, a):
            return ref_words(r, s, 9 if a == 12 else a)        # نصُّ 12 هو نصُّ 9 (تكرار)
        w = wit({5: 9})
        r = S.classify([w, w], SURAH, STARTS, "hafs", rw, N, SHA)
        self.assertEqual(r[5][0], S.UNDECIDED)


class FixedRule(unittest.TestCase):
    def test_first_middle_last(self):
        self.assertEqual(S.pick_probes([2, 4, 6, 8, 10, 12, 14]), [2, 8, 14])

    def test_order_independent(self):
        self.assertEqual(S.pick_probes([14, 2, 8, 4, 12, 6, 10]), [2, 8, 14])

    def test_non_adjacent(self):
        p = S.pick_probes([3, 4, 5, 6, 7])
        self.assertEqual(len(p), 3)
        self.assertTrue(all(b - a >= 2 for a, b in zip(p, p[1:])))

    def test_too_few(self):
        self.assertIsNone(S.pick_probes([3, 4, 5]))
        self.assertIsNone(S.pick_probes([3, 9]))

    def test_deterministic(self):
        s = [2, 5, 9, 11, 17]
        self.assertEqual(S.pick_probes(s), S.pick_probes(list(s)))


def build(a_heard, b_heard=None, runs=(RA, RB)):
    b_heard = a_heard if b_heard is None else b_heard
    return S.build([wit(a_heard), wit(b_heard)], list(runs), SURAH, STARTS, "hafs", ref_words, N, SHA)


class Condition4(unittest.TestCase):
    DEV = {a: a + 12 for a in (2, 5, 8, 11)}          # 4 منحرفة ⇒ ≥ 3 مسابير؛ وفي الموضع 20

    def test_more_in_place_refuses_whole_surah(self):
        rec, rep, code = build(self.DEV)
        self.assertEqual((rec, code), (None, 3))
        self.assertGreater(rep["counts"][S.IN_PLACE], rep["counts"][S.PROVEN])
        self.assertIn("drop_ayahs", rep["verdict"])

    def test_majority_deviant_builds(self):
        dev = {a: (a + 7 if a + 7 <= N else a - 7) for a in range(1, 18)}
        rec, rep, code = build(dev)
        self.assertEqual(code, 0, rep)
        self.assertEqual(len(rec["probes"]), 3)
        self.assertEqual([p["ayah"] for p in rec["probes"]], rep["probes"])
        self.assertTrue(all(rep["counts"][S.PROVEN] > rep["counts"][S.IN_PLACE] for _ in [0]))
        self.assertEqual(sorted(rec["witnesses"]), sorted((RA, RB)))

    def test_equal_counts_is_not_refused_by_rule_4(self):
        dev = {a: (a + 12) for a in range(1, 13)}      # 12 منحرفة و12 في الموضع
        rec, rep, code = build(dev)
        self.assertEqual(rep["counts"][S.PROVEN], rep["counts"][S.IN_PLACE])
        self.assertNotEqual(code, 3)

    def test_counts_reported(self):
        _r, rep, _c = build(self.DEV)
        self.assertEqual(rep["counts"], {S.PROVEN: 4, S.IN_PLACE: N - 4, S.UNDECIDED: 0})

    def test_runs_must_be_distinct_canonical(self):
        with self.assertRaises(SystemExit):
            build({}, runs=(RA, RA))
        with self.assertRaises(SystemExit):
            build({}, runs=(RA, "abc"))


class Coverage(unittest.TestCase):
    """حجبُ السورة كاملةً يلزمه تغطيةُ الشاهدين معاً لثلاثة أرباع آياتها (‏N=24 ⇒ 18)."""
    DEV = {a: (a + 7 if a + 7 <= N else a - 7) for a in range(1, 18)}

    def _b(self, covered_a, covered_b=None):
        cb = covered_a if covered_b is None else covered_b
        return S.build([wit(self.DEV, covered=covered_a), wit(self.DEV, covered=cb)], [RA, RB],
                       SURAH, STARTS, "hafs", ref_words, N, SHA)

    def test_below_three_quarters_refused(self):
        rec, rep, code = self._b(list(range(1, 18)))               # 17 < 18
        self.assertEqual((rec, code), (None, 5))
        self.assertIn("drop_ayahs", rep["verdict"])
        self.assertEqual(rep["coverage"], {"covered": 17, "ayahs": N, "need": 18})

    def test_exactly_three_quarters_builds(self):
        rec, rep, code = self._b(list(range(1, 19)))               # 18 = 18
        self.assertEqual(code, 0, rep)
        self.assertIsNotNone(rec)

    def test_coverage_is_joint_not_either(self):
        rec, _rep, code = self._b(list(range(1, 25)), list(range(1, 18)))   # أحدهما كامل والآخر 17
        self.assertEqual((rec, code), (None, 5))

    def test_need_rounds_up(self):
        cov = list(range(1, 19))                                    # 18 من 25 ⇒ يلزم ceil(18.75)=19
        rec, rep, code = S.build([wit(self.DEV, covered=cov), wit(self.DEV, covered=cov)], [RA, RB],
                                 SURAH, STARTS, "hafs", ref_words, 25, SHA)
        self.assertEqual((rec, code), (None, 5))
        self.assertEqual(rep["coverage"]["need"], 19)


class GateRefWordsTest(unittest.TestCase):
    """المسحُ يختار المسابيرَ بدالّة النصّ نفسِها التي تتحقّق بها البوّابة (‏timing_repair) — لا بدالّةٍ أخرى."""

    def test_same_function_as_gate(self):
        import heard_gate as HG          # الاسمُ نفسُه الذي تستورده timing_repair (‏مسارُ tools/index_qa)
        import timing_repair as TR
        self.assertIs(S.gate_ref_words(), TR._default_ref_words())
        self.assertIs(S.gate_ref_words(), HG.disputed_ref_words)

    def test_main_passes_gate_function(self):
        import json
        import tempfile
        from pathlib import Path
        from unittest import mock
        seen = {}

        def fake_build(srcs, runs, surah, starts, riwaya, ref_words, n, sha):
            seen["ref_words"] = ref_words
            return None, {"counts": {}, "probes": [], "verdict": "x"}, 4

        sentinel = object()
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(S, "build", fake_build), \
                mock.patch.object(S, "load_artifact", lambda p: {}), \
                mock.patch.object(S, "load_starts", lambda p, s: {}), \
                mock.patch.object(S, "gate_ref_words", lambda: sentinel):
            rc = S.main(["--surah", "2", "--riwaya", "hafs", "--audio-sha", SHA, "--runs", "1,2",
                         "--witness-artifacts", "a,b", "--entries", "e",
                         "--out", str(Path(d) / "o.json"), "--report", str(Path(d) / "r.json")])
            self.assertEqual(rc, 4)
            self.assertEqual(json.loads((Path(d) / "r.json").read_text(encoding="utf-8"))["2"]["verdict"], "x")
        self.assertIs(seen["ref_words"], sentinel)


if __name__ == "__main__":
    unittest.main()
