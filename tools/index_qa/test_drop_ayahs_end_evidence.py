#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""دليلُ «نهاية المدخل» (‏kind="end") لحجب آيةٍ بـ`drop_ayahs` برمز TIMING_UNDER_REPAIR — بلا شبكةٍ ولا دلو.

شروطُ القائد (2026-11-10) حرفاً، ولكلّ شرطٍ اختبارٌ يسقط إن أُزيل أو أُرخي:
  ١) شاهدان مستقلّان (‏تشغيلتان متمايزتان قانونيّتان، وبصمةُ الصوت = audioSha256 للسورة) عند **نهاية** المدخل يسمعان نصّاً ليس من الآية.
  ٢) التحقّقُ بدوالّ البوّابة (‏`disputed_ref_words` · `_span_ok` · `W_K`) على المصدر المحمَّل، لا بحكمٍ مكتوب.
  ٥) الحجبُ للآية وحدها بحدّ الربع، لا الأولى ولا الأخيرة، وreasonUser، ودليلٌ لكلّ آية.
(المحمِّلُ والنصُّ المرجعيّ يُحقنان؛ ولا يُتصل بـGitHub.)

    PYTHONPATH=tools/index_qa:tools/ci_fleet python -m unittest tools.index_qa.test_drop_ayahs_end_evidence
"""
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import drop_ayahs                                                # noqa: E402
import promote                                                   # noqa: E402
import timing_repair as T                                        # noqa: E402

S, N = 78, 40                       # النبأ: 40 آية، الربعُ = 10
TUR = "TIMING_UNDER_REPAIR"
RUN_A, RUN_B = "1234567", "7654321"
SHA = [f"{i:064x}" for i in range(1, 115)]
LETTERS = "بتجحخدذرزسشصضطظعغفقكلمنهو"


def _w(a, i):
    n = a * 31 + i * 7
    return LETTERS[n % 25] + LETTERS[(n // 25 + 3) % 25] + LETTERS[(n // 7 + 11) % 25]


def ref_words(_riwaya, _s, a):
    return [_w(a, i) for i in range(8)]


def _end(a):
    return a * 10000 + 9000          # نهايةُ مدخل الآية a المنشور


def _idx():
    ents = [{"ayahId": f"{S}:{a}", "startMs": a * 10000, "endMs": _end(a), "fileRef": "f", "confBand": "HIGH"}
            for a in range(1, N + 1)]
    return {"riwaya": "hafs", "reciterId": "x", "entries": ents, "ayahCount": 6236, "audioSha256": list(SHA),
            "missing": {"count": 6236 - N, "byReason": {"unknown": 6236 - N},
                        "ids": [f"{s}:{a}" for s in range(1, 115) if s != S
                                for a in range(1, promote._AYAH_COUNTS[s - 1] + 1)]}}


def _words(a, at, p=0.95, first=0, n=4):
    """أربعُ كلماتٍ متّصلةٍ من نصّ الآية a تغطّي اللحظةَ at (‏الثانيةُ تبدأ قبلها بـ200م.ث)."""
    return [{"w": _w(a, first + k), "s": at - 600 + k * 400, "e": at - 600 + k * 400 + 380, "p": p} for k in range(n)]


def witness(probes, heard=None, own=False, p=0.95, sha=None, surah=S, compute="float32", model="small",
            shift=0, extra=None, win=None, words_fn=None):
    """شاهدٌ يسمع عند نهاية كلّ مدخلٍ مسبورٍ نصَّ heardAyah (‏أو heard، أو نصَّ الآية نفسِها إن own)."""
    ayahs = {}
    for i, (a, o) in enumerate(probes):
        h = a if own else (heard if heard is not None else o)
        at = _end(a) + shift
        words = words_fn(h, at) if words_fn else _words(h, at, p)
        ayahs[str(a)] = {"windowMs": list(win(at)) if win else [at - 3000, at + 3000], "words": words}
    for k, v in (extra or {}).items():
        ayahs[k] = v
    return {"surah": surah, "riwaya": "hafs", "fileRef": "https://e.org/078.mp3", "sha256": sha or SHA[surah - 1],
            "model": model, "computeType": compute, "ayahs": ayahs}


PROBES = [(15, 16), (20, 21)]
KEYS = ("surah", "riwaya", "fileRef", "sha256", "model", "computeType", "ayahs")


def end_rec(a, o, runs=(RUN_A, RUN_B), per_run=None, end_ms=None, **wkw):
    wits = {r: {k: witness(PROBES, **{**wkw, **(per_run or {}).get(r, {})})[k] for k in KEYS} for r in runs}
    return {"method": "whisper", "detail": f"شاهدان عند نهاية {S}:{a} سمعا {S}:{o}", "kind": "end",
            "heard": {"witness": "whisper_witness.yml small float32", "runId": int(runs[0]), "text": "نصّ"},
            "probe": {"ayah": a, "heardAyah": o, "endMs": _end(a) if end_ms is None else end_ms},
            "witnesses": wits}


def loader_for(per_run=None, **wkw):
    return lambda run, surah: witness(PROBES, surah=surah, **{**wkw, **(per_run or {}).get(str(run), {})})


def ev_all(**kw):
    return {f"{S}:{a}": end_rec(a, o, **kw) for a, o in PROBES}


def make(evidence=None, ayahs=None, loader=None, reason_user="توقيتُ هذه الآيات قيد الإصلاح فحُجبت مؤقّتاً.",
         code=TUR, idx=None, **kw):
    return drop_ayahs.drop_ayahs(idx or _idx(), {S: ayahs or [a for a, _ in PROBES]},
                                 evidence if evidence is not None else ev_all(),
                                 reason="قياس شاهدَين عند نهاية المدخل", reason_user=reason_user, reason_code=code,
                                 from_sha="a" * 64, from_key="timings/hafs/x.jz",
                                 end_loader=loader or loader_for(), end_ref_words=ref_words, **kw)


def gate(out):
    return promote.declared_truncated_gaps(out, S, end_ref_words=ref_words)


class Accept(unittest.TestCase):
    def test_00_control_end_evidence_accepted_and_gate_reverifies(self):
        out = make()
        ok, why = gate(out)
        self.assertTrue(ok, why)
        rec = out["transform"]["truncatedGaps"][str(S)]
        self.assertEqual(rec["absent"], [15, 20])
        self.assertEqual(out["missing"]["byReason"]["timing_under_repair"], 2)
        e = rec["evidence"][f"{S}:15"]
        self.assertEqual(e["kind"], "end")
        self.assertEqual(sorted(e["witnesses"]), sorted([RUN_A, RUN_B]))
        self.assertEqual(e["probe"], {"ayah": 15, "heardAyah": 16, "endMs": _end(15)})
        src = {x["ayahId"]: x for x in _idx()["entries"]}
        for x in out["entries"]:
            self.assertEqual(x, src[x["ayahId"]])                       # حدودُ الباقي لم تُمسّ

    def test_01_start_evidence_path_unchanged(self):
        """دليلٌ بلا kind يبقى على حكمه القديم حرفاً (‏heard وحده) — لا يُخلط بدليل النهاية."""
        ev = {f"{S}:15": {"method": "whisper", "detail": "بدء",
                          "heard": {"witness": "w", "runId": 42, "text": "نصّ"}}}
        out = make(evidence=ev, ayahs=[15])
        self.assertTrue(gate(out)[0])
        self.assertNotIn("kind", out["transform"]["truncatedGaps"][str(S)]["evidence"][f"{S}:15"])


class Condition1TwoIndependentWitnesses(unittest.TestCase):
    def test_one_witness_rejected(self):
        ev = ev_all(runs=(RUN_A,))
        with self.assertRaisesRegex(SystemExit, "شاهدان"):
            make(evidence=ev)

    def test_same_run_two_spellings_rejected(self):
        ev = ev_all(runs=(RUN_A, "0" + RUN_A))
        with self.assertRaisesRegex(SystemExit, "قانونياً"):
            make(evidence=ev)

    def test_audio_sha_mismatch_rejected(self):
        bad = {RUN_B: {"sha": "f" * 64}}
        with self.assertRaisesRegex(SystemExit, "بصمةُ الصوت"):
            make(evidence=ev_all(per_run=bad), loader=loader_for(per_run=bad))

    def test_witness_of_other_surah_rejected(self):
        bad = {RUN_B: {"surah": 77}}
        with self.assertRaisesRegex(SystemExit, "لسورة"):
            make(evidence=ev_all(per_run=bad), loader=loader_for(per_run=bad))

    def test_model_or_compute_rejected(self):
        bad = {RUN_B: {"compute": "float16"}}
        with self.assertRaisesRegex(SystemExit, "النموذج"):
            make(evidence=ev_all(per_run=bad), loader=loader_for(per_run=bad))

    def test_own_text_at_end_rejected(self):
        """الشاهدُ يسمع عند النهاية نصَّ الآية نفسِها ⇒ لا عطب."""
        bad = {RUN_B: {"own": True}}
        with self.assertRaisesRegex(SystemExit, "نفسِها"):
            make(evidence=ev_all(per_run=bad), loader=loader_for(per_run=bad))

    def test_own_text_heard_alongside_other_rejected(self):
        """نافذةٌ أخرى تسمع في اللحظة نفسِها نصَّ الآية ⇒ يُردّ ولو سُمع معها غيرُها (‏أشدّ من البدء)."""
        extra = {"x": {"windowMs": [_end(15) - 3000, _end(15) + 3000], "words": _words(15, _end(15))}}
        bad = {RUN_B: {"extra": extra}}
        with self.assertRaisesRegex(SystemExit, "نفسِها"):
            make(evidence=ev_all(per_run=bad), loader=loader_for(per_run=bad))

    def test_third_ayah_text_rejected(self):
        """يُسمع نصُّ آيةٍ ثالثةٍ غيرِ المسمّاة ⇒ ليس من نصّ heardAyah."""
        bad = {RUN_B: {"heard": 33}}
        with self.assertRaisesRegex(SystemExit, "ليس من نصّ"):
            make(evidence=ev_all(per_run=bad), loader=loader_for(per_run=bad))

    def test_heard_ayah_equal_to_ayah_rejected(self):
        ev = ev_all()
        ev[f"{S}:15"]["probe"]["heardAyah"] = 15
        with self.assertRaisesRegex(SystemExit, "نفسُها"):
            make(evidence=ev)

    def test_other_text_not_at_end_rejected(self):
        """نصُّ الآية الأخرى مسموعٌ لكن بعد نهاية المدخل لا عندها (‏مُزاحٌ 1500م.ث)."""
        bad = {RUN_B: {"shift": 1500}}
        with self.assertRaisesRegex(SystemExit, "لا يُسمع عند نهاية المدخل"):
            make(evidence=ev_all(per_run=bad), loader=loader_for(per_run=bad))

    def test_other_text_before_end_window_only_rejected(self):
        """نصُّ الآية الأخرى ينتهي قبل نهاية المدخل بـ1500م.ث ⇒ ليس عند النهاية."""
        bad = {RUN_B: {"shift": -1500}}
        with self.assertRaisesRegex(SystemExit, "لا يُسمع عند نهاية المدخل"):
            make(evidence=ev_all(per_run=bad), loader=loader_for(per_run=bad))

    def test_end_ms_must_equal_published_end(self):
        ev = ev_all()
        ev[f"{S}:15"]["probe"]["endMs"] = _end(15) + 1
        with self.assertRaisesRegex(SystemExit, "endMs"):
            make(evidence=ev)


class Condition2GateFunctions(unittest.TestCase):
    def test_low_confidence_rejected_by_span_ok(self):
        bad = {RUN_B: {"p": 0.45}}
        with self.assertRaisesRegex(SystemExit, "ثقةٌ دون العتبة"):
            make(evidence=ev_all(per_run=bad), loader=loader_for(per_run=bad))

    def test_mean_confidence_rejected_by_span_ok(self):
        bad = {RUN_B: {"p": 0.6}}                                      # فوق الأدنى 0.5 ودون المتوسّط 0.7
        with self.assertRaisesRegex(SystemExit, "ثقةٌ دون العتبة"):
            make(evidence=ev_all(per_run=bad), loader=loader_for(per_run=bad))

    def test_word_glued_to_window_edge_rejected(self):
        bad = {RUN_B: {"win": lambda at: (at - 3000, at + 100)}}       # نهايةُ النافذة داخل المقطع
        with self.assertRaisesRegex(SystemExit, "ملصوقةٌ"):
            make(evidence=ev_all(per_run=bad), loader=loader_for(per_run=bad))

    def test_fewer_than_w_k_words_rejected(self):
        """كلمتان فقط من الآية الأخرى متّصلتان عند النهاية (‏والثالثةُ من غيرها) ⇒ دون W_K."""
        def two(h, at):
            ws = _words(h, at, n=2, first=0)
            return ws + [{"w": _w(39, 5), "s": at + 200, "e": at + 580, "p": 0.95},
                         {"w": _w(38, 6), "s": at + 600, "e": at + 980, "p": 0.95}]
        bad = {RUN_B: {"words_fn": two}}
        with self.assertRaises(SystemExit):
            make(evidence=ev_all(per_run=bad), loader=loader_for(per_run=bad))

    def test_written_differs_from_source_rejected(self):
        """المكتوبُ يسمع الأخرى والمصدرُ المحمَّل يسمع الآيةَ نفسَها ⇒ الحكمُ على المحمَّل."""
        with self.assertRaisesRegex(SystemExit, "يخالف مصدرَه"):
            make(loader=loader_for(per_run={RUN_B: {"own": True}}))

    def test_loader_failure_rejected(self):
        def boom(run, surah):
            raise SystemExit("لا مخرَج")
        with self.assertRaisesRegex(SystemExit, "تعذّر تحميلُه"):
            make(loader=boom)

    def test_gate_reverifies_written_witness(self):
        """promote يعيد الحكمَ بدالّته على الشاهدين المكتوبين: تبديلُ تفريغ أحدهما بنصّ الآية نفسِها يُردّ."""
        out = make()
        bad = copy.deepcopy(out)
        e = bad["transform"]["truncatedGaps"][str(S)]["evidence"][f"{S}:15"]
        e["witnesses"][RUN_B] = {k: witness(PROBES, own=True)[k] for k in KEYS}
        ok, why = gate(bad)
        self.assertFalse(ok)
        self.assertIn("نفسِها", why)

    def test_gate_rejects_candidate_sha_mismatch(self):
        out = make()
        bad = copy.deepcopy(out)
        bad["audioSha256"][S - 1] = "e" * 64
        ok, why = gate(bad)
        self.assertFalse(ok)
        self.assertIn("بصمةُ الصوت", why)

    def test_gate_rejects_single_written_witness(self):
        out = make()
        bad = copy.deepcopy(out)
        bad["transform"]["truncatedGaps"][str(S)]["evidence"][f"{S}:20"]["witnesses"].pop(RUN_A)
        self.assertFalse(gate(bad)[0])

    def test_gate_rejects_unknown_kind(self):
        out = make()
        bad = copy.deepcopy(out)
        bad["transform"]["truncatedGaps"][str(S)]["evidence"][f"{S}:20"]["kind"] = "start"
        self.assertFalse(gate(bad)[0])

    def test_gate_rejects_probe_of_other_ayah(self):
        out = make()
        bad = copy.deepcopy(out)
        bad["transform"]["truncatedGaps"][str(S)]["evidence"][f"{S}:20"]["probe"]["ayah"] = 15
        self.assertFalse(gate(bad)[0])


class ExplicitKind(unittest.TestCase):
    def test_unknown_kind_rejected(self):
        ev = ev_all()
        ev[f"{S}:15"]["kind"] = "start"
        with self.assertRaisesRegex(SystemExit, "kind|نوع"):
            make(evidence=ev)

    def test_kind_with_source_truncated_rejected(self):
        ev = ev_all()
        for v in ev.values():
            v["method"] = "whisper"
        with self.assertRaisesRegex(SystemExit, "TIMING_UNDER_REPAIR"):
            make(evidence=ev, code="SOURCE_TRUNCATED")

    def test_gate_rejects_kind_under_source_truncated(self):
        """مرشّحٌ SOURCE_TRUNCATED يحمل سجلَّ نهايةٍ سليماً في دليله ⇒ promote يردّه (‏النوعُ لـTIMING_UNDER_REPAIR وحدَه)."""
        ev = {f"{S}:{a}": {"method": "whisper", "detail": "بتر"} for a, _ in PROBES}
        out = make(evidence=ev, code="SOURCE_TRUNCATED")
        self.assertTrue(gate(out)[0])
        good = make()["transform"]["truncatedGaps"][str(S)]["evidence"]
        out["transform"]["truncatedGaps"][str(S)]["evidence"] = copy.deepcopy(good)
        ok, why = gate(out)
        self.assertFalse(ok)
        self.assertIn("TIMING_UNDER_REPAIR", why)

    def test_method_must_be_whisper(self):
        ev = ev_all()
        ev[f"{S}:15"]["method"] = "ctc_window"
        with self.assertRaisesRegex(SystemExit, "method=whisper"):
            make(evidence=ev)

    def test_probe_must_name_dropped_ayah(self):
        ev = ev_all()
        ev[f"{S}:15"] = end_rec(20, 21)
        with self.assertRaisesRegex(SystemExit, "المسبارُ لا يسمّي"):
            make(evidence=ev)

    def test_heard_run_must_be_a_witness(self):
        ev = ev_all()
        ev[f"{S}:15"]["heard"]["runId"] = 999999999
        with self.assertRaisesRegex(SystemExit, "heard.runId"):
            make(evidence=ev)

    def test_heard_still_required(self):
        ev = ev_all()
        ev[f"{S}:15"].pop("heard")
        with self.assertRaisesRegex(SystemExit, "دليلَ سماعٍ"):
            make(evidence=ev)

    def test_already_absent_rejected(self):
        idx = _idx()
        idx["entries"] = [e for e in idx["entries"] if e["ayahId"] not in (f"{S}:15", f"{S}:20")]
        idx["missing"]["ids"] += [f"{S}:15", f"{S}:20"]
        idx["missing"]["count"] += 2
        idx["missing"]["byReason"]["source_truncated"] = 2
        with self.assertRaisesRegex(SystemExit, "already-absent"):
            make(idx=idx, already_absent=True)


class Condition5DropAyahsLimits(unittest.TestCase):
    def _many(self, pairs):
        prs = list(pairs)
        lo = lambda run, surah: witness(prs, surah=surah)            # noqa: E731
        ev = {}
        for a, o in prs:
            r = end_rec(a, o)
            r["witnesses"] = {k: {kk: witness(prs)[kk] for kk in KEYS} for k in (RUN_A, RUN_B)}
            ev[f"{S}:{a}"] = r
        return ev, lo, [a for a, _ in prs]

    def test_first_ayah_rejected(self):
        ev, lo, ays = self._many([(1, 2)])
        with self.assertRaisesRegex(SystemExit, "أولُ السورة"):
            make(evidence=ev, ayahs=ays, loader=lo)

    def test_last_ayah_rejected(self):
        ev, lo, ays = self._many([(N, N - 1)])
        with self.assertRaisesRegex(SystemExit, "آخرُها"):
            make(evidence=ev, ayahs=ays, loader=lo)

    def test_quarter_limit(self):
        ev, lo, ays = self._many([(a, a + 1) for a in range(3, 3 + 2 * 11, 2)])    # 11 > 10
        with self.assertRaisesRegex(SystemExit, "ربع"):
            make(evidence=ev, ayahs=ays, loader=lo)

    def test_quarter_exact_accepted(self):
        ev, lo, ays = self._many([(a, a + 1) for a in range(3, 3 + 2 * 10, 2)])    # 10 = الربع
        out = make(evidence=ev, ayahs=ays, loader=lo)
        self.assertTrue(gate(out)[0])

    def test_reason_user_required(self):
        with self.assertRaisesRegex(SystemExit, "reason-user"):
            make(reason_user="  ")

    def test_evidence_for_each_ayah(self):
        ev = ev_all()
        ev.pop(f"{S}:20")
        with self.assertRaisesRegex(SystemExit, "لا دليلَ قياسٍ للآية"):
            make(evidence=ev)


class RealText(unittest.TestCase):
    """بالنصّ الموثَّق ودالّة البوّابة الافتراضيّة (‏`heard_gate.disputed_ref_words`): 78:24 ونهايتُها في صوت 78:25."""
    def _wit(self, text):
        at = 249000
        ws = [{"w": w, "s": at - 600 + k * 400, "e": at - 600 + k * 400 + 380, "p": 0.95} for k, w in enumerate(text.split())]
        return {"surah": S, "riwaya": "hafs", "fileRef": "f", "sha256": SHA[S - 1], "model": "small",
                "computeType": "float32", "ayahs": {"24": {"windowMs": [at - 3000, at + 3000], "words": ws}}}

    def test_default_ref_words(self):
        idx = _idx()
        for e in idx["entries"]:
            if e["ayahId"] == f"{S}:24":
                e["endMs"] = 249000
        good = self._wit("إلا حميما وغساقا")
        rec = {"method": "whisper", "detail": "d", "kind": "end",
               "heard": {"witness": "w", "runId": int(RUN_A), "text": "إلا حميما وغساقا"},
               "probe": {"ayah": 24, "heardAyah": 25, "endMs": 249000},
               "witnesses": {RUN_A: good, RUN_B: good}}
        self.assertIsNone(T.end_evidence_error(idx, S, 24, rec, lambda r, s: good))
        own = self._wit("فيها بردا ولا شرابا")
        rec2 = dict(rec, witnesses={RUN_A: good, RUN_B: own})
        self.assertIn("نفسِها", T.end_record_error(idx, S, 24, rec2))


if __name__ == "__main__":
    unittest.main()
