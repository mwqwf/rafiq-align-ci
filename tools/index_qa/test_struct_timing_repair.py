"""إعفاءُ الفحص البنيويّ من عتبة الغياب 2% للحجب المؤقّت TIMING_UNDER_REPAIR وحدَه — بلا شبكةٍ ولا دلو.

الأصلُ: فهرسٌ سورتُه 2 (286 آيةً ≈ 4.6%) مُسقطةٌ بإعلان. يُعفى بالشروط كلِّها، ويُردّ بنقص أيٍّ منها.
(المحمِّلُ والنصُّ المرجعيّ يُحقنان؛ ولا يُتصل بـGitHub.)"""
import copy
import unittest

from tools.index_qa import run as R
from tools.index_qa import timing_repair as T

C = R.COUNTS
S = 2                                    # السورةُ المُسقطة: 286 آيةً > 2% من 6236 (124)
KEY = "timings-staging/hafs/x_hafs.abcdef12.jz"
RUN_A, RUN_B = "1234567", "7654321"
SHA = [f"{i:064x}" for i in range(1, 115)]
LETTERS = "بتجحخدذرزسشصضطظعغفقكلمنهو"


def _w(a, i):
    n = a * 31 + i * 7
    return LETTERS[n % 25] + LETTERS[(n // 25 + 3) % 25] + LETTERS[(n // 7 + 11) % 25]


def ref_words(_riwaya, _s, a):
    return [_w(a, i) for i in range(8)]


def witness(sha=None, heard=7, at=5000, surah=S, own=False, p=0.95, compute="float32"):
    """شاهدٌ يسمع عند 5000م.ث نصَّ الآية heard (‏أو نصَّ الآية 3 نفسِها إن own)."""
    a = 3 if own else heard
    words = [{"w": _w(a, i), "s": at - 200 + i * 400, "e": at - 200 + i * 400 + 380, "p": p} for i in range(4)]
    return {"surah": surah, "riwaya": "hafs", "fileRef": "https://e.org/002.mp3", "sha256": sha or SHA[surah - 1],
            "model": "small", "computeType": compute,
            "ayahs": {"1": {"windowMs": [0, 20000], "words": words}}}


def record(runs=(RUN_A, RUN_B), probe=None, **wkw):
    """سجلُّ الدليل المكتوب في الترويسة — يُبنى من الشاهد نفسِه الذي يعيده المحمِّل (‏وإلا ردّه تطابقُ المصدر لا المضمون)."""
    keys = ("surah", "riwaya", "fileRef", "sha256", "model", "computeType", "ayahs")
    return {"probes": [probe or {"ayah": 3, "startMs": 5000, "heardAyah": 7}],
            "witnesses": {r: {k: witness(**wkw)[k] for k in keys} for r in runs}}


def loader_for(**wkw):
    return lambda run, surah: witness(**wkw)


def make_idx(code="TIMING_UNDER_REPAIR", rec=None, drop=(S,), by_reason=None, extra_tr=None, recs=None):
    E, ms = [], 0
    for s in range(1, 115):
        if s in drop:
            continue
        for a in range(1, C[s - 1] + 1):
            E.append({"ayahId": f"{s}:{a}", "startMs": ms, "endMs": ms + 1000,
                      "fileRef": f"https://example.org/q/{s:03d}.mp3"})
            ms += 1000
    ids = [f"{s}:{a}" for s in drop for a in range(1, C[s - 1] + 1)]
    n = len(ids)
    tr = {"op": "drop_surah:" + ",".join(map(str, drop)), "reason": "r", "reasonUser": "u", "reasonCode": code,
          "declarations": {str(s): {"op": "drop_surah", "reasonCode": code, "reasonUser": "u", "reason": "r"}
                           for s in drop}}
    if recs is not None:
        tr["timingRepair"] = {str(k): v for k, v in recs.items()}
    elif rec is not None:
        tr["timingRepair"] = {str(S): rec}
    tr.update(extra_tr or {})
    key = {"timing_under_repair": "timing_under_repair"}
    reasons = by_reason if by_reason is not None else {key.get("timing_under_repair"): n}
    return {"ayahCounting": "KUFI", "ayahCount": 6236, "entries": E, "audioSha256": list(SHA),
            "riwaya": "hafs", "reciterId": "x_hafs", "refineVersion": 1, "refinedCount": 0,
            "missing": {"count": n, "ids": ids, "byReason": reasons}, "transform": tr}


def loader_ok(run, surah):
    return witness(surah=surah)


def tag(idx, approvals, loader=loader_ok, rw=ref_words):
    f, w, info = R.structural(idx, KEY, allow_unmarked=True,
                              timing_ctx={"approvals": approvals, "loader": loader, "ref_words": rw})[:3]
    return f, w, info


def gap_fatal(f):
    return [x for x in f if "مداخل ناقصة" in x]


GOOD_ROW = {KEY: frozenset({S})}


class StructTimingRepair(unittest.TestCase):
    def test_00_control_all_conditions_met_is_excused(self):
        f, w, info = tag(make_idx(rec=record()), GOOD_ROW)
        self.assertEqual(gap_fatal(f), [], f)
        self.assertEqual(info["timingRepairExcused"], {"count": C[S - 1], "surahs": [S]})
        self.assertTrue(any("TIMING_UNDER_REPAIR" in x and str(C[S - 1]) in x for x in w))   # (د) يُطبع العدد والسور

    def test_01_missing_row_rejected(self):
        f, _w, info = tag(make_idx(rec=record()), {})
        self.assertTrue(gap_fatal(f))
        self.assertEqual(info["timingRepairExcused"]["count"], 0)

    def test_02_row_for_other_key_rejected(self):
        f, _w, _i = tag(make_idx(rec=record()), {"timings-staging/hafs/other.abcdef12.jz": frozenset({S})})
        self.assertTrue(gap_fatal(f))

    def test_03_row_partial_rejected(self):
        # المعلَن {2، 112} وكلاهما بدليلٍ سويّ، والصفُّ يسمّي 2 وحدَها ⇒ يُردّ بالصفّ وحدَه.
        idx = make_idx(drop=(S, 112), recs={S: record(), 112: record(surah=112)},
                       by_reason={"timing_under_repair": C[S - 1] + C[111]})
        f, _w, info = tag(idx, {KEY: frozenset({S})})
        self.assertTrue(gap_fatal(f))
        self.assertEqual(info["timingRepairExcused"]["count"], 0)

    def test_04_row_superset_rejected(self):
        f, _w, _i = tag(make_idx(rec=record()), {KEY: frozenset({S, 5})})
        self.assertTrue(gap_fatal(f))

    def test_05_other_code_not_excused(self):
        f, _w, _i = tag(make_idx(code="OTHER", rec=record(), by_reason={"other": C[S - 1]}), GOOD_ROW)
        self.assertTrue(gap_fatal(f))

    def test_06_source_truncated_code_not_excused_by_this_path(self):
        f, _w, info = tag(make_idx(code="SOURCE_TRUNCATED", rec=record(), by_reason={"timing_under_repair": C[S - 1]}),
                          GOOD_ROW)
        self.assertEqual(info["timingRepairExcused"]["count"], 0)

    def test_07_single_witness_rejected(self):
        f, _w, _i = tag(make_idx(rec=record(runs=(RUN_A,))), GOOD_ROW)
        self.assertTrue(gap_fatal(f))

    def test_08_same_run_twice_rejected(self):
        f, _w, _i = tag(make_idx(rec=record(runs=(RUN_A, "0" + RUN_A))), GOOD_ROW)
        self.assertTrue(gap_fatal(f))

    def test_09_wrong_audio_fingerprint_rejected(self):
        # المكتوبُ والمحمَّلُ متّفقان على بصمةٍ ليست audioSha256 للسورة ⇒ يردّه تطابقُ البصمة وحدَه.
        f, _w, _i = tag(make_idx(rec=record(sha="f" * 64)), GOOD_ROW, loader=loader_for(sha="f" * 64))
        self.assertTrue(gap_fatal(f))

    def test_10_written_differs_from_source_rejected(self):
        rec = record()
        rec["witnesses"][RUN_B]["fileRef"] = "https://e.org/other.mp3"
        f, _w, _i = tag(make_idx(rec=rec), GOOD_ROW)
        self.assertTrue(gap_fatal(f))

    def test_11_witness_does_not_hear_other_ayah_rejected(self):
        f, _w, _i = tag(make_idx(rec=record(own=True)), GOOD_ROW, loader=loader_for(own=True))   # يسمع نصَّ الآية نفسِها
        self.assertTrue(gap_fatal(f))

    def test_12_low_confidence_witness_rejected(self):
        f, _w, _i = tag(make_idx(rec=record(p=0.2)), GOOD_ROW, loader=loader_for(p=0.2))
        self.assertTrue(gap_fatal(f))

    def test_11b_witness_hears_a_different_ayah_than_claimed_rejected(self):
        # المسبارُ يدّعي سماعَ نصّ الآية 7، والشاهدُ يسمع نصَّ الآية 9 ⇒ ادّعاءٌ لم يُثبته الشاهد.
        f, _w, _i = tag(make_idx(rec=record(heard=9)), GOOD_ROW, loader=loader_for(heard=9))
        self.assertTrue(gap_fatal(f))

    def test_13_no_evidence_record_rejected(self):
        f, _w, _i = tag(make_idx(rec=None), GOOD_ROW)
        self.assertTrue(gap_fatal(f))

    def test_14_loader_failure_rejected(self):
        def boom(r, s):
            raise SystemExit("لا شاهد")
        f, _w, _i = tag(make_idx(rec=record()), GOOD_ROW, loader=boom)
        self.assertTrue(gap_fatal(f))

    def test_15_inherited_outside_declared_rejected(self):
        f, _w, _i = tag(make_idx(rec=record(), extra_tr={"dropSurah": [S, 9]}), GOOD_ROW)
        self.assertTrue(gap_fatal(f))

    def test_16_by_reason_not_counting_rejected(self):
        f, _w, info = tag(make_idx(rec=record(), by_reason={"unknown": C[S - 1]}), GOOD_ROW)
        self.assertEqual(info["timingRepairExcused"]["count"], 0)
        self.assertTrue(gap_fatal(f))

    def _drop_partial(self, idx, s, n):
        gone = {f"{s}:{a}" for a in range(1, n + 1)}
        idx["entries"] = [e for e in idx["entries"] if e["ayahId"] not in gone]
        idx["missing"]["count"] += n
        idx["missing"]["ids"] += sorted(gone)
        return idx

    def test_17_unexcused_absence_after_subtraction_still_over_2pct(self):
        # سورة 2 معفاة، وغيابٌ آخر غيرُ معلَن (‏150 آيةً من سورة 3) فوق 2% بعد الطرح ⇒ يبقى قاتلاً.
        f, _w, info = tag(self._drop_partial(make_idx(rec=record()), 3, 150), GOOD_ROW)
        self.assertTrue(gap_fatal(f), f)
        self.assertEqual(info["missingUnexcused"], 150)

    def test_18_small_unexcused_absence_below_2pct_passes_after_subtraction(self):
        f, _w, info = tag(self._drop_partial(make_idx(rec=record()), 3, 100), GOOD_ROW)
        self.assertEqual(gap_fatal(f), [], f)
        self.assertEqual(info["missingUnexcused"], 100)


    def test_19_repeated_text_is_not_drift(self):
        # آيتان نصُّهما واحد (‏تكرار): الشاهدُ يسمع نصَّ الآية الأخرى وهو نصُّها هي ⇒ لا انحراف.
        f, _w, _i = tag(make_idx(rec=record(own=True)), GOOD_ROW, loader=loader_for(own=True),
                        rw=lambda r, s, a: ref_words(r, s, 3 if a in (3, 7) else a))
        self.assertTrue(gap_fatal(f))

    def test_20_witness_of_another_surah_rejected(self):
        # المكتوبُ والمحمَّلُ متّفقان على أنّ الشاهد لسورة 3 (‏وبصمتُه بصمةُ السورة 2 كي لا تردّه البصمة).
        w = dict(surah=3, sha=SHA[S - 1])
        f, _w, _i = tag(make_idx(rec=record(**w)), GOOD_ROW, loader=loader_for(**w))
        self.assertTrue(gap_fatal(f))

    def test_21_witness_not_float32_rejected(self):
        f, _w, _i = tag(make_idx(rec=record(compute="int8")), GOOD_ROW, loader=loader_for(compute="int8"))
        self.assertTrue(gap_fatal(f))

    def test_22_no_probes_rejected(self):
        rec = record()
        rec["probes"] = []
        f, _w, _i = tag(make_idx(rec=rec), GOOD_ROW)
        self.assertTrue(gap_fatal(f))

    def test_23_witness_hears_nothing_at_probe_time_rejected(self):
        f, _w, _i = tag(make_idx(rec=record(probe={"ayah": 3, "startMs": 90000, "heardAyah": 7})), GOOD_ROW)
        self.assertTrue(gap_fatal(f))


class DropSurahAcceptsCode(unittest.TestCase):
    """drop_surah يقبل الرمزَ بشرط (ج) نفسِه، ويخرج فهرسٌ يُعفيه الفحصُ البنيويّ (‏ذهابٌ وإياب)."""

    def _run(self, args, ev=None):
        import gzip, hashlib, json, os, sys, tempfile
        from unittest import mock
        from tools.index_qa import drop_surah as D
        import timing_repair as T2          # الوحدةُ كما يستوردها drop_surah (‏مسارُ tools/index_qa)، لا نسخةُ الحزمة
        idx = make_idx(drop=())
        idx["missing"] = {"count": 0, "ids": [], "byReason": {"unknown": 0}}
        body = gzip.compress(json.dumps(idx, ensure_ascii=False).encode("utf-8"))
        sha = hashlib.sha256(body).hexdigest()
        put = {}

        class CL:
            def get_object(self, **kw):
                import io
                return {"Body": io.BytesIO(body)}

            def put_object(self, **kw):
                put.update(kw)

            def head_object(self, **kw):
                return {"ContentLength": len(put["Body"])}

        argv = ["drop_surah.py", "--key", "timings/hafs/x_hafs.jz", "--sha", sha, "--surah", str(S),
                "--reason", "قياس", "--reason-user", "توقيتها قيد الإصلاح",
                "--reason-code", "TIMING_UNDER_REPAIR", "--yes"] + args
        with tempfile.TemporaryDirectory() as d, mock.patch.object(D.promote, "s3", lambda: (CL(), "b")), \
                mock.patch.object(T2, "_default_loader", lambda: loader_ok), \
                mock.patch.object(T2, "_default_ref_words", lambda: ref_words), mock.patch.object(sys, "argv", argv):
            if ev is not None:
                f = os.path.join(d, "ev.json")
                with open(f, "w", encoding="utf-8") as fh:
                    fh.write(json.dumps(ev))
                argv += ["--timing-evidence", f]
            D.main()
        return json.loads(gzip.decompress(put["Body"]).decode("utf-8")) if put else None

    def test_accepts_with_valid_evidence_and_struct_excuses_output(self):
        out = self._run([], {str(S): record()})
        self.assertEqual(out["transform"]["declarations"][str(S)]["reasonCode"], "TIMING_UNDER_REPAIR")
        f, _w, info = tag(out, GOOD_ROW)
        self.assertEqual(gap_fatal(f), [], f)
        self.assertEqual(info["timingRepairExcused"]["surahs"], [S])

    def test_rejects_without_evidence(self):
        with self.assertRaises(SystemExit):
            self._run([])

    def test_rejects_single_witness(self):
        with self.assertRaises(SystemExit):
            self._run([], {str(S): record(runs=(RUN_A,))})

    def test_rejects_wrong_fingerprint(self):
        rec = record()
        for w in rec["witnesses"].values():
            w["sha256"] = "e" * 64
        with self.assertRaises(SystemExit):
            self._run([], {str(S): rec})


if __name__ == "__main__":
    unittest.main()
