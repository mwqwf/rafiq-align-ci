#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""اختبارُ الفحص الشامل بلا شبكة — فهارسُ وهميّةٌ بعطبٍ معلومٍ يجب أن يُلتقط، وسليمةٌ يجب ألّا تُتَّهم."""
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import full_audit as fa                                               # noqa: E402

COUNTS = fa.COUNTS


def make_index(reciter="x", riwaya="hafs", skip=(), drop=(), transform=None, missing=None):
    """فهرسٌ كاملٌ وهميّ: كلُّ آيةٍ 4 ثوانٍ متتالية في ملفّ سورتها."""
    entries, shas = [], []
    for s in range(1, 115):
        shas.append("" if s in drop else f"sha{s:03d}" + "0" * 58)
        if s in drop:
            continue
        t = 5000
        for a in range(1, COUNTS[s - 1] + 1):
            if (s, a) in skip:
                t += 4000
                continue
            entries.append({"ayahId": f"{s}:{a}", "fileRef": f"https://h/{reciter}/{s:03d}.mp3",
                            "startMs": t, "endMs": t + 4000, "confBand": "HIGH"})
            t += 4000
    idx = {"schema": 1, "riwaya": riwaya, "reciterId": reciter, "ayahCounting": "KUFI", "ayahCount": 6236,
           "engineVersion": "test", "refineVersion": "none", "refinedCount": 0, "exactEnds": True,
           "audioSha256": shas, "entries": entries}
    if transform:
        idx["transform"] = transform
    if missing:
        idx["missing"] = missing
    return idx


class StructureTest(unittest.TestCase):
    def test_clean_index_passes(self):
        idx = make_index()
        r = fa.check_structure(idx, "timings/hafs/x.jz")
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["entries"], 6236)
        g = fa.check_gaps(idx)
        self.assertTrue(g["ok"], g)
        self.assertEqual(g["missingTotal"], 0)

    def test_duplicate_and_invalid_and_overlap(self):
        idx = make_index()
        idx["entries"].append(dict(idx["entries"][10]))                      # ayahId مكرّر
        idx["entries"][20]["endMs"] = idx["entries"][20]["startMs"]           # مدّةٌ غير صالحة
        idx["entries"][31]["startMs"] = idx["entries"][30]["startMs"] + 100   # تداخل داخل الملفّ
        r = fa.check_structure(idx, "timings/hafs/x.jz")
        self.assertFalse(r["ok"])
        txt = " ".join(r["errors"])
        self.assertIn("مكرّر", txt)
        self.assertIn("غير صالح", txt)
        self.assertIn("تداخل", txt)

    def test_file_shared_and_mismatch(self):
        idx = make_index()
        for e in idx["entries"]:
            if e["ayahId"].startswith("112:"):
                e["fileRef"] = "https://h/x/113.mp3"                          # سورةٌ بصوت غيرها
        r = fa.check_structure(idx, "timings/hafs/x.jz")
        txt = " ".join(r["errors"])
        self.assertIn("لسورتين", txt)
        self.assertIn("لا يطابق السورة", txt)

    def test_duplicate_audio_sha(self):
        idx = make_index()
        idx["audioSha256"][5] = idx["audioSha256"][4]
        r = fa.check_structure(idx, "timings/hafs/x.jz")
        self.assertIn("بصمةُ صوتٍ واحدةٌ", " ".join(r["errors"]))


class GapsTest(unittest.TestCase):
    def test_internal_gap_is_error(self):
        idx = make_index(skip={(2, 100)})
        g = fa.check_gaps(idx)
        self.assertFalse(g["ok"])
        self.assertEqual(g["internalGaps"][0]["surah"], 2)
        self.assertEqual(g["internalGaps"][0]["missing"], [100])

    def test_undeclared_tail_is_error_and_declared_tail_is_ok(self):
        skip = {(24, a) for a in range(31, 65)}
        idx = make_index(skip=skip)
        g = fa.check_gaps(idx)
        self.assertFalse(g["ok"])
        self.assertEqual(g["tailMissing"][0], {"surah": 24, "range": [31, 64]})
        idx2 = make_index(skip=skip, missing={"count": 34, "byReason": {"source_truncated": 34}})
        g2 = fa.check_gaps(idx2)
        self.assertTrue(g2["ok"], g2["errors"])
        self.assertEqual(g2["missingTotal"], 34)

    def test_declared_ids_cover_edge(self):
        skip = {(37, 1), (37, 2)}
        idx = make_index(skip=skip, missing={"count": 2, "byReason": {"x": 2}, "ids": ["37:1", "37:2"]})
        self.assertTrue(fa.check_gaps(idx)["ok"])
        idx3 = make_index(skip=skip, missing={"count": 2, "byReason": {"x": 2}, "ids": ["37:1"]})
        self.assertFalse(fa.check_gaps(idx3)["ok"])

    def test_dropped_surah_declared(self):
        idx = make_index(drop={38}, transform={"op": "drop_surah:38", "reason": "404"})
        g = fa.check_gaps(idx)
        self.assertTrue(g["ok"], g["errors"])
        self.assertEqual(g["wholeMissing"], [38])
        idx2 = make_index(drop={38})
        self.assertFalse(fa.check_gaps(idx2)["ok"])


class DurationTest(unittest.TestCase):
    def test_outliers_and_gaps(self):
        text = ["ا" * 20] * 6236
        idx = make_index()
        e = next(x for x in idx["entries"] if x["ayahId"] == "2:50")
        e["endMs"] = e["startMs"] + 40000                                      # 10× المتوقَّع
        nxt = next(x for x in idx["entries"] if x["ayahId"] == "2:51")
        nxt["startMs"] = e["endMs"] + 20000                                    # فجوة 20ث
        nxt["endMs"] = nxt["startMs"] + 4000
        d = fa.check_durations(idx, text)
        self.assertEqual(d["durationOutliers"], 1)
        self.assertEqual(d["durationExamples"][0]["aid"], "2:50")
        self.assertEqual(d["silenceGaps"], 1)
        self.assertEqual(d["silenceExamples"][0]["from"], "2:50")

    def test_short_ayahs_not_flagged(self):
        text = ["ا" * 3] * 6236                                                  # دون MIN_CHARS
        d = fa.check_durations(make_index(), text)
        self.assertEqual(d["durationOutliers"], 0)


class AudioTest(unittest.TestCase):
    SHA = "a" * 64

    def _rep(self, salt, m, n, verdict="مقبول", sha=None):
        return ("f", {"key": "timings-staging/hafs/x.aaaaaaaa.jz", "sha256": sha or self.SHA, "source": "ci",
                      "engine": "e", "verdict": verdict, "ts": 1.0,
                      "sample": {"seedSalt": salt, "seed": salt, "rows": [{"aid": "1:1"}],
                                 "severe": [m, n, [m / n, 0.0, 0.05 if m else 0.015]]}})

    def _op(self, **kw):
        d = {"kind": "openers", "key": "k", "sha256": self.SHA, "commit": "9ffb957", "scope": "full",
             "late": [], "swallowed": [], "suspect": [], "tail": [], "at": 2.0}
        d.update(kw)
        return ("o", d)

    def test_four_salts_and_openers_ok(self):
        reps = [self._rep(f"k{i}", 1, 200) for i in range(1, 5)] + [self._op()]
        r = fa.audio_status(self.SHA, "x", reps)
        self.assertTrue(r["ok"], r["errors"])
        self.assertEqual(r["pooled"]["n"], 800)
        self.assertLess(r["severeHi"], 0.05)

    def test_missing_verdicts_and_bad_openers(self):
        r = fa.audio_status(self.SHA, "x", [])
        self.assertFalse(r["ok"])
        self.assertEqual(len(r["errors"]), 2)
        reps = [self._rep(f"k{i}", 0, 200) for i in range(1, 5)] + [self._op(lateConfirmed=[37])]
        r2 = fa.audio_status(self.SHA, "x", reps)
        self.assertIn("مؤكَّد", " ".join(r2["errors"]))
        reps = [self._rep(f"k{i}", 0, 200) for i in range(1, 5)] + [self._op(commit="0000000")]
        self.assertIn("غير موثوقة", " ".join(fa.audio_status(self.SHA, "x", reps)["errors"]))
        r3 = fa.audio_status(self.SHA, "x", [self._rep("k1", 30, 200, verdict="مرفوض (15%)"), self._op()])
        self.assertFalse(r3["ok"])

    def test_other_sha_listed(self):
        reps = [self._rep("k1", 0, 200, sha="b" * 64), self._op()]
        r = fa.audio_status(self.SHA, "x", reps)
        self.assertEqual(r["otherShasWithSamples"], ["bbbbbbbb"])


class IdentityTest(unittest.TestCase):
    def test_identity(self):
        k, sha = "timings/hafs/x.jz", "c" * 64
        man = {k: {"sha256": sha, "entries": 6236}}
        r = fa.check_identity(k, sha, 6236, man, {k: sha}, {k: sha}, sha)
        self.assertTrue(r["ok"])
        r2 = fa.check_identity(k, sha, 6236, man, {k: "d" * 64}, {}, "e" * 64)
        self.assertEqual(len(r2["errors"]), 3)
        r3 = fa.check_identity(k, sha, 6236, man, {k: sha}, {k: sha}, None, check_public=False)
        self.assertTrue(r3["ok"])


if __name__ == "__main__":
    unittest.main()
