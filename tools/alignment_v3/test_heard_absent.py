#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""اختباراتُ `heard_absent` وبابِ `--absent-ayahs` في `ctc_heard_map` (‏ctc_splice mode=heard · أمر القائد 2026-11-07):
المنطقُ المحضُ، ثمّ **اختبارُ تحوّرٍ** يثبت أنّ كلَّ حالةٍ مرفوضةٍ تُردّ، ثمّ `run()` بنموذجٍ مُزيَّفٍ حتميّ، ثمّ التقاءُ
المخرَج بـ`drop_ayahs(already_absent=True)` وبوّابة `promote.declared_truncated_gaps`.

    python -m unittest tools/alignment_v3/test_heard_absent.py
"""
import copy
import os
import random
import sys
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "alignment"))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "index_qa"))

import heard_absent as HA  # noqa: E402
import ctc_heard_map as H  # noqa: E402

E = HA.HeardAbsentError


def cand(start, end, q=0.9, solo=True):
    """خريطةُ آيةٍ واحدة: مِرساةٌ عامّةٌ وأداءٌ منفرد."""
    h = {"anchorMs": [start, end], "anchorQuality": q, "heardMs": [start, end] if solo else None,
         "score": q if solo else None, "occurrences": []}
    return h


def maps(n=30, absent=(12, 13, 14), dg=None, dr=None):
    """خريطتان متّفقتان: الآيةُ k تبدأ k*10000؛ والمسمّاةُ بلا شيء. ‏dg/dr: تعديلاتٌ لكلّ آيةٍ في خريطةٍ واحدة."""
    gm, rm = {}, {}
    for k in range(1, n + 1):
        if k in absent:
            gm[str(k)] = {"anchorMs": [1, 2], "anchorQuality": 0.1, "heardMs": None, "score": None, "occurrences": []}
            rm[str(k)] = copy.deepcopy(gm[str(k)])
        else:
            gm[str(k)] = cand(k * 10000, k * 10000 + 8000)
            rm[str(k)] = cand(k * 10000 + 100, k * 10000 + 8200)
    for k, v in (dg or {}).items():
        gm[str(k)] = v
    for k, v in (dr or {}).items():
        rm[str(k)] = v
    return gm, rm


class Spec(unittest.TestCase):
    def test_expand(self):
        self.assertEqual(HA.expand_spec("6:74-94", 6), list(range(74, 95)))
        self.assertEqual(HA.expand_spec("6:74,6:80 82", 6), [74, 80, 82])
        self.assertEqual(HA.expand_spec("74-76", 6), [74, 75, 76])

    def test_expand_rejects(self):
        for bad in ("7:74", "6:74-6:73", "6:74,6:74", "", "abc", "6:74-7:80"):
            with self.assertRaises(E, msg=bad):
                HA.expand_spec(bad, 6)

    def test_named_guards(self):
        HA.check_named(165, list(range(74, 95)))                   # 21 ≤ ربع 165
        with self.assertRaises(E):
            HA.check_named(165, [1, 5])                           # الأولى
        with self.assertRaises(E):
            HA.check_named(165, [5, 165])                         # الأخيرة
        with self.assertRaises(E):
            HA.check_named(165, list(range(20, 62)))              # 42 > ربع 165
        with self.assertRaises(E):
            HA.check_named(165, [170])                            # خارج السورة
        HA.check_named(165, list(range(20, 61)))                  # 41 = حدٌّ مقبول (41×4=164 ≤ 165)


class Agreement(unittest.TestCase):
    def test_accepts_and_masks_absent(self):
        gm, rm = maps()
        out, notes = HA.agreed_anchors(gm, rm, 30, [12, 13, 14])
        self.assertEqual([k + 1 for k, a in enumerate(out) if a is None], [12, 13, 14])
        self.assertEqual(out[0], (10000, 18000))                  # بدءُ العامّة ونهايةُ الأدنى
        self.assertEqual(out[10], (110000, 118000))
        self.assertEqual(notes["disputed"], [])

    # ── اختبارُ التحوّر: كلُّ حالةٍ ترفضها الأداة ─────────────────────────────────────────
    def test_mutation_unnamed_absent(self):
        # آيةٌ غيرُ مسمّاةٍ لا شيءَ لها في الخريطتين ⇒ غائبٌ غيرُ مسمّى
        gm, rm = maps()
        for m in (gm, rm):
            m["20"] = {"anchorMs": [1, 2], "anchorQuality": 0.05, "heardMs": None, "score": None, "occurrences": []}
        with self.assertRaisesRegex(E, "غائبٌ غيرُ مسمّى"):
            HA.agreed_anchors(gm, rm, 30, [12, 13, 14])

    def test_mutation_named_absent_but_heard_in_one_map(self):
        for which in ("g", "r"):
            gm, rm = maps()
            (gm if which == "g" else rm)["13"] = cand(130000, 138000)
            with self.assertRaisesRegex(E, "مسمّاةٌ غائبةٌ لكنّها مسموعةٌ"):
                HA.agreed_anchors(gm, rm, 30, [12, 13, 14])

    def test_mutation_named_absent_heard_as_solo_only(self):
        gm, rm = maps()
        gm["13"] = {"anchorMs": [1, 2], "anchorQuality": 0.1, "heardMs": [130000, 138000], "score": 0.86, "occurrences": []}
        with self.assertRaisesRegex(E, "مسمّاةٌ غائبةٌ لكنّها مسموعةٌ"):
            HA.agreed_anchors(gm, rm, 30, [12, 13, 14])

    def test_mutation_named_absent_with_strong_match_elsewhere(self):
        gm, rm = maps()
        rm["13"]["occurrences"] = [[500000, 508000, 0.82]]
        with self.assertRaisesRegex(E, "مطابقةٌ قويّة"):
            HA.agreed_anchors(gm, rm, 30, [12, 13, 14])
        # دون العتبة (‏مطابقةٌ عرَضيّةٌ كالمقيسة 0.55–0.63 في ناصر الماجد) لا تردّ
        gm, rm = maps()
        rm["13"]["occurrences"] = [[500000, 508000, 0.63]]
        HA.agreed_anchors(gm, rm, 30, [12, 13, 14])

    def test_mutation_heard_without_anchor_nor_solo(self):
        # مسموعةٌ في خريطة (‏العامّة) وفي الأخرى لا مِرساةَ ولا أداءَ منفرداً ≥0.5 (‏0.45)
        gm, rm = maps()
        rm["20"] = {"anchorMs": [200000, 208000], "anchorQuality": 0.12, "heardMs": [200000, 208000], "score": 0.45,
                    "occurrences": []}
        with self.assertRaisesRegex(E, "خريطةٍ واحدةٍ"):
            HA.agreed_anchors(gm, rm, 30, [12, 13, 14])

    def test_solo_at_threshold_is_accepted(self):
        gm, rm = maps()
        for m in (gm, rm):
            m["20"] = {"anchorMs": [200000, 208000], "anchorQuality": 0.12, "heardMs": [200000, 208000], "score": 0.5,
                       "occurrences": []}
        out, _ = HA.agreed_anchors(gm, rm, 30, [12, 13, 14])
        self.assertEqual(out[19], (200000, 208000))

    def test_mutation_first_last_quarter(self):
        gm, rm = maps()
        for bad in ([1, 5], [5, 30], list(range(5, 14))):         # الأولى · الأخيرة · 9 > ربع 30
            with self.assertRaises(E):
                HA.agreed_anchors(gm, rm, 30, bad)

    def test_disputed_start_is_not_anchored_but_named(self):
        gm, rm = maps()
        rm["20"] = cand(205000, 213000)                           # يخالف العامّة بـ5ث
        out, notes = HA.agreed_anchors(gm, rm, 30, [12, 13, 14])
        self.assertIsNone(out[19])
        self.assertEqual(notes["disputed"], [20])

    def test_solo_pair_rescues_disagreeing_globals(self):
        # كالآية 6:95: المِرساتان العامّتان تختلفان 1.7ث والأداءان المنفردان متّفقان
        gm, rm = maps()
        gm["20"] = {"anchorMs": [201700, 209000], "anchorQuality": 0.8, "heardMs": [200000, 208000], "score": 0.9, "occurrences": []}
        rm["20"] = {"anchorMs": [200000, 208500], "anchorQuality": 0.9, "heardMs": [200020, 208500], "score": 1.0, "occurrences": []}
        out, notes = HA.agreed_anchors(gm, rm, 30, [12, 13, 14])
        self.assertEqual(out[19][0], 200000)
        self.assertEqual(notes["kinds"][20], "solo/solo")


class Built(unittest.TestCase):
    def entries(self, n=30, absent=(12, 13, 14), ends=None):
        out = []
        for k in range(n):
            if (k + 1) in absent:
                out.append({"ayahIdx": k, "startMs": None, "endMs": None})
            else:
                out.append({"ayahIdx": k, "startMs": (k + 1) * 10000 + 50, "endMs": (k + 1) * 10000 + 8000})
        for k, v in (ends or {}).items():
            out[k - 1]["endMs"] = v
        return out

    def anchors(self):
        gm, rm = maps()
        return HA.agreed_anchors(gm, rm, 30, [12, 13, 14])[0]

    def test_valid(self):
        e = self.entries(ends={11: 110000 + 8000 + 600})
        HA.validate_built(e, self.anchors(), [12, 13, 14], 30)

    def test_mutation_extension_covers_the_gap(self):
        # مدخلُ 11 يُمدّ إلى بدء 15 ليغطّيَ فجوة 12–14 ⇒ يُردّ
        e = self.entries(ends={11: 150000})
        with self.assertRaisesRegex(E, "تغطّي فجوة"):
            HA.validate_built(e, self.anchors(), [12, 13, 14], 30)
        # حتى بمقدار صغيرٍ فوق الذيل
        e = self.entries(ends={11: 118000 + HA.TAIL_MS + 1})
        with self.assertRaises(E):
            HA.validate_built(e, self.anchors(), [12, 13, 14], 30)

    def test_mutation_absent_with_bounds(self):
        e = self.entries()
        e[12]["startMs"], e[12]["endMs"] = 125000, 126000
        with self.assertRaisesRegex(E, "ولها حدود"):
            HA.validate_built(e, self.anchors(), [12, 13, 14], 30)

    def test_mutation_unnamed_without_bounds(self):
        e = self.entries()
        e[19]["startMs"] = e[19]["endMs"] = None
        with self.assertRaisesRegex(E, "بلا حدود"):
            HA.validate_built(e, self.anchors(), [12, 13, 14], 30)

    def test_mutation_non_ascending(self):
        e = self.entries()
        e[20]["startMs"] = 5000
        with self.assertRaises(E):
            HA.validate_built(e, self.anchors(), [12, 13, 14], 30)

    def test_end_before_gap(self):
        a = self.anchors()
        self.assertEqual(HA.end_before_gap(10, 110050, 150000, a), 118000 + HA.TAIL_MS)
        self.assertEqual(HA.end_before_gap(10, 110050, 118300, a), 118300)          # مسقوفةٌ ببدء التالية
        with self.assertRaises(E):
            HA.end_before_gap(10, 119000, 150000, a)                                 # نهايةٌ ≤ بدء
        a[10] = None
        with self.assertRaises(E):
            HA.end_before_gap(10, 110050, 150000, a)                                 # بلا مِرساة

    def test_support(self):
        gm, rm = maps()
        e = self.entries()
        HA.check_support(e, gm, rm, [12, 13, 14])
        e[20]["startMs"] = 210000 + 5000                                              # 5ث عن كلّ قياس
        with self.assertRaisesRegex(E, "لا يسنده"):
            HA.check_support(e, gm, rm, [12, 13, 14])

    def test_plan_groups_never_cross_absent(self):
        anchors = self.anchors()
        wins = HA.plan_groups(anchors, 30, {11, 12, 13}, H.plan_windows)
        for i, j in wins:
            self.assertFalse(any(k in (11, 12, 13) for k in range(i, j + 1)), (i, j))
        self.assertEqual(sorted(k for i, j in wins for k in range(i, j + 1)),
                         [k for k in range(30) if k not in (11, 12, 13)])
        self.assertEqual(wins[0][0], 0)
        self.assertTrue(any(i == 14 for i, _ in wins))

    def test_clusters(self):
        self.assertEqual(HA.clusters([5, 6, 7, 12]), [(4, 8, [5, 6, 7]), (11, 13, [12])])


class Evidence(unittest.TestCase):
    N = 30

    def setUp(self):
        self.txt = {k: "ا" * 40 for k in range(1, self.N + 1)}
        self.ents = {11: {"startMs": 110050, "endMs": 118800}, 15: {"startMs": 150050, "endMs": 158000}}
        self.scan = {str(k): {"bestScore": 0.55, "bestAtMs": 3000} for k in (12, 13, 14)}

    def align(self, conf=0.2, dur=1500):
        def f(ws, we, texts):
            # 11 ثمّ 12–14 مضغوطةٌ في الفجوة ثمّ 15 — كما يفعل CTC على نصٍّ غيرِ موجود
            gap0, gap1 = 118800, 150050
            step = (gap1 - gap0) // 3
            return [(ws, gap0, 0.9)] + [(gap0 + i * step, gap0 + i * step + dur, conf) for i in range(3)] + [(gap1, we, 0.9)]
        return f

    def build(self, **kw):
        a = dict(surah=6, absent=[12, 13, 14], ents=self.ents, t_of=lambda k: self.txt[k], rate=200.0,
                 align=self.align(), scan_g=self.scan, scan_r=self.scan)
        a.update(kw)
        return HA.build_evidence(**a)

    def test_evidence_shape(self):
        ev = self.build()
        self.assertEqual(sorted(ev), ["6:12", "6:13", "6:14"])
        for v in ev.values():
            self.assertEqual(v["method"], "ctc_window")
            self.assertIn("وعلى الملفّ كلِّه", v["detail"])
            self.assertIn("0.55", v["detail"])

    def test_mutation_absent_passes_alignment_guards(self):
        # ثقةٌ عالية ومدّةٌ معقولةٌ للآية 13 ⇒ هي مسموعةٌ لا غائبة
        def f(ws, we, texts):
            return [(ws, 118800, 0.9), (118800, 122800, 0.2), (122800, 130800, 0.9), (130800, 131800, 0.2), (150050, we, 0.9)]
        with self.assertRaisesRegex(E, "اجتازت حرّاسَ المحاذاة"):
            self.build(align=f)

    def test_mutation_whole_file_match(self):
        scan = dict(self.scan)
        scan["13"] = {"bestScore": 0.74, "bestAtMs": 777000}
        with self.assertRaisesRegex(E, "مسموعةٌ لا غائبة"):
            self.build(scan_r=scan)
        with self.assertRaisesRegex(E, "مسموعةٌ لا غائبة"):
            self.build(scan_g=scan)

    def test_mutation_missing_scan(self):
        scan = dict(self.scan)
        del scan["13"]
        with self.assertRaisesRegex(E, "لا مسحَ ملفٍّ كاملٍ"):
            self.build(scan_r=scan)
        with self.assertRaisesRegex(E, "لا مسحَ ملفٍّ كاملٍ"):
            self.build(scan_g={})

    def test_mutation_missing_neighbour(self):
        ents = {11: self.ents[11]}
        with self.assertRaisesRegex(E, "جارةُ النافذة"):
            self.build(ents=ents)


# ───────────────────────── run() بنموذجٍ مُزيَّفٍ حتميّ ─────────────────────────
ALPHA = "ابتثجحخدذرزسشصضطظعغفقكلمنهوي"
BASM = "بسم الله الرحمن الرحيم"
N_RUN, ABSENT_RUN = 14, [6, 7, 8]
TOTAL_MS = 130000


def layout():
    """‏k ⇒ (بدء، نهاية) م.ث: 1–5 ثمّ بسملةٌ بين 47000–52000 ثمّ 9–14 (‏6–8 غائبة)."""
    t, spans = {}, {}
    for k in range(1, N_RUN + 1):
        if k <= 5:
            s = 2000 + (k - 1) * 9000
        elif k >= 9:
            s = 55000 + (k - 9) * 9000
        else:
            continue
        spans[k] = (s, s + 8000)
    return spans


def texts():
    rng = random.Random(7)
    return ["".join(rng.choice(ALPHA) for _ in range(40)) for _ in range(N_RUN)]


class FakeClip:
    def __init__(self, off_ms):
        self.off = off_ms


class RunWithFakes(unittest.TestCase):
    """يشغّل `ctc_heard_map.run` بحقنٍ حتميّ: مسموعٌ نظيفٌ مطابقٌ للنصّ للمسموعات وبسملةٌ في الفجوة، والغائباتُ لا أثرَ لها."""

    def setUp(self):
        import numpy as np
        self.np = np
        self.texts = texts()
        self.spans = layout()
        vocab = {"<pad>": 0, "|": 1}
        for ch in (chr(c) for c in range(0x621, 0x64B)):
            vocab[ch] = len(vocab)
        self.vocab = vocab
        import common
        import ctc_seg
        import validate
        import vad

        norm = common.norm
        truth = {norm(self.texts[k - 1]): v for k, v in self.spans.items()}
        truth[norm(BASM)] = (47000, 52000)
        full_len = TOTAL_MS * 16

        def em(clip):
            if len(clip) == full_len:
                T = TOTAL_MS // 20
                lpz = np.full((T, len(vocab)), -10.0, dtype=np.float32)
                lpz[:, 0] = 0.0
                seq = [(norm(BASM), 47000, 52000)] + [(self.texts[k - 1], s, e) for k, (s, e) in self.spans.items()]
                for text, s, e in sorted(seq, key=lambda x: x[1]):
                    text = text.replace(" ", "")
                    step = (e - s - 200) / len(text)
                    for i, ch in enumerate(text):
                        f = int((s + i * step) // 20)
                        lpz[f, 0] = -10.0
                        lpz[f, vocab[ch]] = 0.0
                return lpz
            return FakeClip(clip[0] / 16.0 if len(clip) else 0.0)

        def seg(emis, n, tx):
            off, out, prev_end = emis.off, [], None
            known = [truth.get(t) for t in tx]
            for i, t in enumerate(tx):
                if known[i] is not None:
                    st, en = known[i]
                    out.append(((st - off) / 1000.0, (en - off) / 1000.0, -0.3))
                    prev_end = en
                else:                                    # نصٌّ غيرُ موجود: يُعصر في الفجوة بثقةٍ منخفضة
                    nxt = next((known[j] for j in range(i + 1, len(tx)) if known[j] is not None), None)
                    g0 = prev_end if prev_end is not None else off
                    g1 = nxt[0] if nxt else g0 + 1000
                    run = sum(1 for j in range(i, len(tx)) if known[j] is None)
                    s = g0 + (g1 - g0) * 0 / max(1, run)
                    out.append(((s - off) / 1000.0, (s + 1200 - off) / 1000.0, -4.0))
                    prev_end = s + 1200
            return out

        class Tok:
            pad_token_id = 0
            word_delimiter_token = "|"

            @staticmethod
            def get_vocab():
                return dict(vocab)

        self.patches = [
            mock.patch.object(common, "load_index", lambda: {}),
            mock.patch.object(common, "load_text", lambda riwaya: list(self.texts)),
            mock.patch.object(common, "surah_slice", lambda index, s: (0, N_RUN, {})),
            mock.patch.object(common, "ffprobe_duration_ms", lambda p: TOTAL_MS),
            mock.patch.object(common, "to_wav16k", lambda p: "wav"),
            mock.patch.object(vad, "read_wav", lambda w: np.arange(full_len, dtype=np.float32)),
            mock.patch.object(vad, "silences", lambda w: []),
            mock.patch.object(vad, "snap_to_silence", lambda t, sil, tolerance_ms=0: (t, False)),
            mock.patch.object(ctc_seg, "_emissions", em),
            mock.patch.object(ctc_seg, "_segment", seg),
            mock.patch.object(ctc_seg, "_conf", lambda sc: 0.9 if sc > -1 else 0.2),
            mock.patch.object(ctc_seg, "BASMALA", BASM),
            mock.patch.object(ctc_seg, "_model", lambda: {"proc": mock.Mock(tokenizer=Tok)}),
        ]
        for p in self.patches:
            p.start()
        self.addCleanup(lambda: [p.stop() for p in reversed(self.patches)])

    def probe(self):
        res, _rep = H.run("x.mp3", 5, "hafs", log=lambda *_: None, probe=True, absent=ABSENT_RUN)
        res.update(sha256="s" * 64, quranModel={"id": "m"})
        return res

    def build(self, peer=None, absent=ABSENT_RUN, **kw):
        return H.run("x.mp3", 5, "hafs", log=lambda *_: None, strict_tol_ms=1000, absent=absent,
                     peer=peer if peer is not None else self.probe(), **kw)

    def test_probe_scans_absent_over_whole_file(self):
        res = self.probe()
        self.assertEqual(sorted(res["absentScan"]), ["6", "7", "8"])
        for v in res["absentScan"].values():
            self.assertLess(v["bestScore"], HA.ABSENT_BEST_MAX)
        self.assertEqual(res["absent"], ABSENT_RUN)

    def test_build_leaves_absent_and_does_not_extend_over_gap(self):
        res, _ = self.build()
        ent = {e["ayahIdx"] + 1: e for e in res["entries"]}
        for k in ABSENT_RUN:
            self.assertIsNone(ent[k]["startMs"])
            self.assertIsNone(ent[k]["endMs"])
        for k, (s, e) in self.spans.items():
            self.assertLessEqual(abs(ent[k]["startMs"] - s), 1000, k)
        # ⛔ آخرُ مسموعةٍ قبل الفجوة لا تمتدّ إلى بدء 9 (55000)
        self.assertLessEqual(ent[5]["endMs"], self.spans[5][1] + 2000)
        self.assertLess(ent[5]["endMs"], 47000 + 200)             # بدءُ البسملة المقيس
        self.assertGreaterEqual(ent[9]["startMs"], self.spans[9][0] - 1000)
        self.assertEqual(sorted(res["absentEvidence"]), ["5:6", "5:7", "5:8"])
        for v in res["absentEvidence"].values():
            self.assertEqual(v["method"], "ctc_window")

    def test_build_requires_peer(self):
        with self.assertRaises(E):
            H.run("x.mp3", 5, "hafs", log=lambda *_: None, strict_tol_ms=1000, absent=ABSENT_RUN, peer=None)

    def test_mutation_named_absent_heard_in_peer(self):
        peer = self.probe()
        k = self.spans[3]
        peer["heardMap"]["7"] = cand(*k)
        with self.assertRaisesRegex(E, "مسموعةٌ"):
            self.build(peer=peer)

    def test_mutation_unnamed_absent(self):
        # نُسمّي 6 و7 فقط وتبقى 8 بلا صوتٍ ولا تسمية ⇒ غائبٌ غيرُ مسمّى
        peer = self.probe()
        with self.assertRaisesRegex(E, "غائبٌ غيرُ مسمّى"):
            self.build(peer=peer, absent=[6, 7])

    def test_mutation_first_and_last_and_quarter(self):
        for bad in ([1, 6], [6, N_RUN], [5, 6, 7, 8]):
            with self.assertRaises(E):
                self.build(absent=bad)

    def test_default_mode_untouched(self):
        # بلا absent: يمشي المسارُ الأصليّ (‏يُبنى كلُّ شيءٍ بلا أيّ إعلان) ولا يلزمه نظير
        res, _ = H.run("x.mp3", 5, "hafs", log=lambda *_: None, strict_tol_ms=1000)
        self.assertNotIn("absentEvidence", res)
        self.assertNotIn("absent", res)


# ───────────────────────── التقاؤه بـdrop_ayahs وبوّابة الترقية ─────────────────────────
class WithDrop(unittest.TestCase):
    S, N = 6, 165
    ABSENT = list(range(74, 95))

    def setUp(self):
        import drop_ayahs
        import promote
        self.drop, self.promote = drop_ayahs, promote

    def idx(self, absent=None, extra_missing=()):
        absent = self.ABSENT if absent is None else absent
        gone = set(absent) | set(extra_missing)
        ents = [{"ayahId": f"{self.S}:{a}", "startMs": a * 1000, "endMs": a * 1000 + 900, "fileRef": "f", "confBand": "HIGH"}
                for a in range(1, self.N + 1) if a not in gone]
        ids = [f"{self.S}:{a}" for a in sorted(gone)]
        return {"riwaya": "hafs", "reciterId": "x", "entries": ents, "ayahCount": 6236,
                "engineBySurah": {"6": "ctc-heardmap-1"},
                "missing": {"count": 6236 - len(ents), "byReason": {"source_truncated": len(gone)}, "ids": ids}}

    def ev(self, absent=None):
        return {f"{self.S}:{a}": {"method": "ctc_window", "detail": "نافذة الجارتين: لا صوتَ للآية، ثقة 0.1"}
                for a in (self.ABSENT if absent is None else absent)}

    def go(self, idx=None, absent=None, evidence=None, already=True):
        absent = self.ABSENT if absent is None else absent
        return self.drop.drop_ayahs(
            idx if idx is not None else self.idx(absent), {self.S: sorted(absent)},
            evidence if evidence is not None else self.ev(absent),
            reason="قياس CTC", reason_user="هذه الآيات غير موجودة في تسجيل القارئ المتاح",
            reason_code="SOURCE_TRUNCATED", from_sha="a" * 64, from_key="timings-staging/hafs/x.aaaaaaaa.jz",
            already_absent=already)

    def test_accepted_without_touching_entries(self):
        src = self.idx()
        out = self.go(idx=src)
        ok, why = self.promote.declared_truncated_gaps(out, self.S)
        self.assertTrue(ok, why)
        self.assertEqual(out["entries"], src["entries"])             # لا مدخلَ يُحذف ولا يتحرّك
        self.assertEqual(out["missing"], src["missing"])             # ولا عدَّ مزدوج
        self.assertEqual(out["transform"]["droppedEntries"], 0)
        self.assertEqual(out["transform"]["gapAyahs"], 21)
        self.assertEqual(out["transform"]["reasonCode"], "SOURCE_TRUNCATED")
        self.assertEqual(out["engineBySurah"]["6"], "ctc-heardmap-1")
        self.assertIn("6", self.promote.census_surahs(out))          # ⇒ يلزمه الإحصاءُ الشامل

    def test_default_mode_still_rejects_incomplete_surah(self):
        with self.assertRaises(SystemExit):
            self.go(already=False)

    def test_mutation_unnamed_absent_in_entries(self):
        # آيةٌ إضافيّةٌ غائبةٌ غيرُ مسمّاة (‏80 هنا ليست في absent) ⇒ يُردّ
        absent = [a for a in self.ABSENT if a != 80]
        with self.assertRaises(SystemExit):
            self.go(idx=self.idx(self.ABSENT), absent=absent, evidence=self.ev(absent))

    def test_mutation_named_absent_present_in_entries(self):
        # مسمّاةٌ غائبةٌ لكنّ لها مدخلاً في الفهرس ⇒ يُردّ
        idx = self.idx([a for a in self.ABSENT if a != 80], )
        with self.assertRaises(SystemExit):
            self.go(idx=idx)

    def test_mutation_first_last_quarter(self):
        for bad in ([1, 74], [74, 165], list(range(20, 62))):
            with self.assertRaises(SystemExit):
                self.go(idx=self.idx(bad), absent=bad, evidence=self.ev(bad))

    def test_mutation_no_evidence_for_one_ayah(self):
        ev = self.ev()
        del ev["6:80"]
        with self.assertRaises(SystemExit):
            self.go(evidence=ev)

    def test_mutation_absent_not_declared_in_missing(self):
        idx = self.idx()
        idx["missing"]["ids"] = idx["missing"]["ids"][:-1]
        with self.assertRaises(SystemExit):
            self.go(idx=idx)
        idx = self.idx()
        idx["missing"]["byReason"] = {"source_truncated": 5}
        with self.assertRaises(SystemExit):
            self.go(idx=idx)

    def test_reason_user_and_code_guards_unchanged(self):
        with self.assertRaises(SystemExit):
            self.drop.drop_ayahs(self.idx(), {self.S: self.ABSENT}, self.ev(), reason="x", reason_user="",
                                 reason_code="SOURCE_TRUNCATED", from_sha="a" * 64, from_key="k", already_absent=True)
        with self.assertRaises(SystemExit):
            self.drop.drop_ayahs(self.idx(), {self.S: self.ABSENT}, self.ev(), reason="x", reason_user="ك",
                                 reason_code="SOURCE_CORRUPT", from_sha="a" * 64, from_key="k", already_absent=True)


if __name__ == "__main__":
    unittest.main()
