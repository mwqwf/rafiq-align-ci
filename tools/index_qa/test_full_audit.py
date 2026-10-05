#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""اختبارُ الفحص الشامل بلا شبكة — فهارسُ وهميّةٌ بعطبٍ معلومٍ يجب أن يُلتقط، وسليمةٌ يجب ألّا تُتَّهم."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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

    def test_folder_fileref_is_error(self):
        idx = make_index()
        for e in idx["entries"]:
            if e["ayahId"].startswith("63:"):
                e["fileRef"] = "https://archive.org/download/some-item"                 # مجلّدٌ لا ملفّ
        r = fa.check_structure(idx, "timings/hafs/x.jz")
        self.assertIn("بلا اسم ملفٍّ صوتيّ", " ".join(r["errors"]))
        self.assertEqual(list(r["examples"]["folderFileRef"]), ["63"])

    def test_duplicate_audio_sha(self):
        idx = make_index()
        idx["audioSha256"][5] = idx["audioSha256"][4]
        r = fa.check_structure(idx, "timings/hafs/x.jz")
        self.assertIn("بصمةُ صوتٍ واحدةٌ", " ".join(r["errors"]))


class FileNumberTest(unittest.TestCase):
    def test_explicit_numbers_and_unparsed_names(self):
        for name, expected in {
            "001.mp3": {1}, "002 - البقرة.mp3": {2},
            "016_النحل.ogg": {16}, "surah-114.opus": {114},
            "سورة%20003.m4a": {3}, "115.mp3": {115},
            "surah017.mp3": {17}, "سورة٠١٨.mp3": {18},
            "kurdi-nahl-c82dee87.mp3": set(), "nahl-128kbps.mp3": set(),
            "recording_2026_10_05.mp3": set(), "1435.mp3": set(),
            "%D8%A9.mp3": set(), "016dead87.mp3": set(),
            "item/": set(),
        }.items():
            with self.subTest(name=name):
                self.assertEqual(fa._file_nos("https://h/" + name), expected)
        self.assertEqual(fa._file_nos("https://h/016.mp3?name=099.mp3"), {16})
        self.assertEqual(fa._file_nos("https://h/nahl.mp3?name=099.mp3"), set())

    def test_hash_name_does_not_accuse_clean_index(self):
        idx = make_index()
        for e in idx["entries"]:
            if e["ayahId"].startswith("16:"):
                e["fileRef"] = "https://h/kurdi-nahl-c82dee87.mp3"
        result = fa.check_structure(idx, "timings/hafs/x.jz")
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["fileNoUnparsed"], 1)

    def test_explicit_wrong_number_without_shared_file_still_fails(self):
        idx = make_index()
        for entry in idx["entries"]:
            if entry["ayahId"].startswith("16:"):
                entry["fileRef"] = "https://other.example/surah017.mp3"
        result = fa.check_structure(idx, "timings/hafs/x.jz")
        self.assertFalse(result["ok"])
        self.assertIn("16", result["examples"].get("fileNoMismatch", {}))
        self.assertNotIn("sharedFiles", result["examples"])
        self.assertEqual(result["registeredFileNoMappings"], {})

    def _registered_index(self):
        # السجل الحقيقي المقيس، مع توقيت وهمي؛ الاختبار لا يحتاج صوتاً ولا شبكة.
        rows = json.loads(fa._p.SOURCE_OVERRIDES.read_text(encoding="utf-8"))
        rows = [r for r in rows if r.get("riwaya") == "qalun"
                and r.get("reciter") == "akri_qalun" and r.get("surah") in (106, 107, 108)]
        self.assertEqual(len(rows), 3)
        idx = make_index(reciter="akri_qalun", riwaya="qalun")
        for row in rows:
            surah = row["surah"]
            idx["audioSha256"][surah - 1] = row["audio_sha256"]
            for entry in idx["entries"]:
                if entry["ayahId"].startswith(f"{surah}:"):
                    entry["fileRef"] = row["url"]
        return idx, rows

    def test_registered_mapping_requires_full_identity_and_bytes(self):
        idx, _rows = self._registered_index()
        for key in ("timings/qalun/akri_qalun.jz",
                    "timings-staging/qalun/akri_qalun.12345678.jz"):
            with self.subTest(key=key):
                result = fa.check_structure(idx, key)
                self.assertTrue(result["ok"], result)
                self.assertEqual(set(result["registeredFileNoMappings"]), {"106", "107", "108"})
        for kind in ("sha", "url", "missing", "key", "riwaya", "reciter"):
            altered = copy.deepcopy(idx)
            key = "timings/qalun/akri_qalun.jz"
            if kind == "sha":
                altered["audioSha256"][105] = "f" * 64
            elif kind == "url":
                for entry in altered["entries"]:
                    if entry["ayahId"].startswith("106:"):
                        entry["fileRef"] = "https://other.example/108.mp3"
            elif kind == "missing":
                altered["entries"] = [e for e in altered["entries"] if e["ayahId"] != "106:4"]
            elif kind == "key":
                key = "timings/qalun/someone_else.jz"
            elif kind == "riwaya":
                altered["riwaya"] = "hafs"
            else:
                altered["reciterId"] = "someone_else"
            with self.subTest(kind=kind):
                result = fa.check_structure(altered, key)
                self.assertIn("106", result["examples"].get("fileNoMismatch", {}))

    def test_missing_or_invalid_registry_keeps_mismatch(self):
        idx, rows = self._registered_index()
        key = "timings/qalun/akri_qalun.jz"
        without_evidence = copy.deepcopy(rows)
        without_evidence[0]["evidence"] = ""
        with tempfile.TemporaryDirectory() as directory:
            registry = Path(directory) / "sources.json"
            with patch.object(fa._p, "SOURCE_OVERRIDES", registry):
                for payload in (None, "{", json.dumps(rows + [rows[0]]),
                                json.dumps(without_evidence)):
                    if payload is not None:
                        registry.write_text(payload, encoding="utf-8")
                    with self.subTest(payload=payload):
                        result = fa.check_structure(idx, key)
                        self.assertIn("106", result["examples"].get("fileNoMismatch", {}))


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
        tiny = next(x for x in idx["entries"] if x["ayahId"] == "3:200")
        tiny["endMs"] = tiny["startMs"] + 67                                   # 67م.ث — لا تلاوة
        d = fa.check_durations(idx, text)
        self.assertEqual(d["durationOutliers"], 2)
        self.assertEqual([o["aid"] for o in d["impossibleShort"]], ["3:200"])
        mid = next(x for x in idx["entries"] if x["ayahId"] == "3:100")
        mid["endMs"] = mid["startMs"] + 700                                    # 0.7ث من 4ث ⇒ قصيرةٌ جدّاً لا مستحيلة
        d2 = fa.check_durations(idx, text)
        self.assertEqual([o["aid"] for o in d2["veryShort"]], ["3:100"])
        self.assertEqual([o["aid"] for o in d2["impossibleShort"]], ["3:200"])
        self.assertEqual([o["aid"] for o in d["extremeLong"]], ["2:50"])
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
        self.assertEqual(len(r2["errors"]), 2)
        self.assertTrue(r2["mirrorStale"])
        r3 = fa.check_identity(k, sha, 6236, man, {k: sha}, {k: sha}, None, check_public=False)
        self.assertTrue(r3["ok"])


if __name__ == "__main__":
    unittest.main()
