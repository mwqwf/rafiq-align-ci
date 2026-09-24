"""اختباراتُ مسار «سور النقص بـCTC مدموجةً في فهرس Whisper» وحُرّاسه (2026-09-24).

    python -m unittest tools/index_qa/test_ctc_splice.py

تُثبت أنّ الحُرّاس الجديدة **تردّ** ما يجب ردُّه لا أنّها تقبل السليم وحده:
دمجٌ بلا إعلانٍ لكلّ سورة · إحصاءٌ غائب · إحصاءٌ على بصمةٍ أخرى · إحصاءٌ ناقص ·
آيةٌ تعذّر سماعُها · عطبٌ فوق 5% · وسجلُّ محرّكاتٍ يزيد سوراً لم يمسّها التحويل.
"""
from __future__ import annotations

import gzip
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import promote                                                   # noqa: E402
import stage_transform                                           # noqa: E402
from splice_surah import COUNTS                                  # noqa: E402

URL = "https://h.example/r/{s:03d}.mp3"
GAP = {112: [2, 3], 113: [4]}               # السورة → الآياتُ الغائبة في الأصل


def _entries(missing):
    out = []
    for s in range(1, 115):
        for a in range(1, COUNTS[s - 1] + 1):
            if a in missing.get(s, []):
                continue
            st = a * 4000
            out.append({"ayahId": f"{s}:{a}", "fileRef": URL.format(s=s),
                        "startMs": st, "endMs": st + 3500, "conf": 0.9,
                        "confBand": "HIGH"})
    return out


def _parent():
    ents = _entries(GAP)
    gone = [f"{s}:{a}" for s, v in GAP.items() for a in v]
    return {"riwaya": "hafs", "reciterId": "zz", "engineVersion": "align-0.2",
            "refineVersion": "r1", "ayahCount": 6236, "entries": ents,
            "audioSha256": ["a" * 64] * 114,
            "missing": {"count": len(gone), "ids": gone, "byReason": {}}}


def _write(p: Path, d: dict) -> None:
    with gzip.open(p, "wt", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False)


def _load(p: Path) -> dict:
    with gzip.open(p, "rt", encoding="utf-8") as f:
        return json.load(f)


def _aligned(s, bad_at=None):
    rows = []
    for i in range(COUNTS[s - 1]):
        st = (i + 1) * 5000
        rows.append({"ayahIdx": i, "startMs": None if i == bad_at else st,
                     "endMs": st + 4000, "conf": 0.85, "snapped": True})
    return {"fileRef": URL.format(s=s), "sha256": "b" * 64, "entries": rows}


class SpliceHeader(unittest.TestCase):
    def _run(self, tmp, tag, bad=None):
        par = tmp / "p.jz"
        _write(par, _parent())
        files = []
        for s in (112, 113):
            f = tmp / f"s{s}.json"
            f.write_text(json.dumps(_aligned(s, bad if s == 113 else None)), encoding="utf-8")
            files.append(str(f))
        cmd = [sys.executable, str(HERE / "splice_surah.py"), "--index", str(par),
               "--surah", "112,113", "--aligned", *files, "--url", URL,
               "--skip-unresolved", "--out", str(tmp / "o.jz")]
        if tag:
            cmd += ["--engine-tag", tag]
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return _load(tmp / "o.jz"), (tmp / "o.jz.taken").read_text()

    def test_tag_names_every_taken_surah(self):
        with tempfile.TemporaryDirectory() as t:
            out, taken = self._run(Path(t), "ctc-seg-1")
        self.assertEqual(taken, "112,113")
        self.assertEqual(out["engineBySurah"], {"112": "ctc-seg-1", "113": "ctc-seg-1"})
        self.assertEqual(len(out["entries"]), 6236)
        self.assertEqual(out["missing"]["count"], 0)

    def test_unresolved_surah_is_not_tagged(self):
        with tempfile.TemporaryDirectory() as t:
            out, taken = self._run(Path(t), "ctc-seg-1", bad=2)
        self.assertEqual(taken, "112")
        self.assertEqual(out["engineBySurah"], {"112": "ctc-seg-1"})
        self.assertEqual(out["missing"]["count"], 1)       # س113 بقيت كما هي

    def test_same_engine_realign_clears_tag(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            p = _parent()
            p["engineBySurah"] = {"112": "ctc-seg-1", "5": "ctc-seg-1"}
            _write(tmp / "p.jz", p)
            f = tmp / "s112.json"
            f.write_text(json.dumps(_aligned(112)), encoding="utf-8")
            subprocess.run([sys.executable, str(HERE / "splice_surah.py"), "--index",
                            str(tmp / "p.jz"), "--surah", "112", "--aligned", str(f),
                            "--url", URL, "--out", str(tmp / "o.jz")], check=True,
                           capture_output=True)
            self.assertEqual(_load(tmp / "o.jz")["engineBySurah"], {"5": "ctc-seg-1"})


class _S3:
    """دلوٌ في الذاكرة يكفي `census_gate` و`stage_transform`."""

    def __init__(self, objs):
        self.objs = objs

    def get_object(self, Bucket, Key):                          # noqa: N803
        if Key not in self.objs:
            raise KeyError(Key)
        return {"Body": io.BytesIO(self.objs[Key])}

    def put_object(self, **kw):
        self.objs[kw["Key"]] = kw["Body"]

    def head_object(self, Bucket, Key):                         # noqa: N803
        return {"ContentLength": len(self.objs[Key])}


def _spliced():
    d = _parent()
    d["entries"] = _entries({})
    d["missing"] = {"count": 0, "ids": [], "byReason": {}}
    d["engineBySurah"] = {"112": "ctc-seg-1", "113": "ctc-seg-1"}
    d["transform"] = {"op": "ctc_surah_splice:112,113"}
    return d


def _census(sha, surahs=(112, 113), severe=0, fail=0, drop=0):
    rows = []
    for s in surahs:
        for a in range(1, COUNTS[s - 1] + 1):
            rows.append({"aid": f"{s}:{a}", "cluster": s, "verdict": "سليم",
                         "kind": "سليم"})
    rows = rows[drop:]
    for r in rows[:severe]:
        r["kind"] = "جسيم"
    for r in rows[severe:severe + fail]:
        r["verdict"], r["kind"] = "تعذّر", "غير حاسم"
    return {"sha256": sha, "fatal": [], "census": {"surahs": list(surahs)},
            "sample": {"rows": rows, "errors": fail}}


class CensusGate(unittest.TestCase):
    SRC = "timings-staging/hafs/zz.12345678.jz"
    KEY = "state-census/" + SRC.replace("/", "_") + ".json"

    def gate(self, rep, idx=None, sha="S"):
        objs = {} if rep is None else {self.KEY: json.dumps(rep).encode()}
        return promote.census_gate(_S3(objs), "b", self.SRC, sha, idx or _spliced())

    def test_full_clean_census_passes(self):
        self.assertIsNone(self.gate(_census("S")))

    def test_no_mixing_needs_no_census(self):
        d = _parent()
        self.assertIsNone(self.gate(None, d))

    def test_splice_op_without_header_refused(self):
        d = _spliced()
        d.pop("engineBySurah")
        self.assertIn("بلا سجلّ", self.gate(_census("S"), d))

    def test_missing_census_refused(self):
        self.assertIn("بلا إحصاء", self.gate(None))

    def test_other_sha_refused(self):
        self.assertIn("بصمةٍ أخرى", self.gate(_census("X")))

    def test_census_of_fewer_surahs_refused(self):
        self.assertIn("غطّى", self.gate(_census("S", surahs=(112,))))

    def test_partial_census_refused(self):
        self.assertIn("لا يُقبل ناقص", self.gate(_census("S", drop=1)))

    def test_unheard_ayah_refused(self):
        self.assertIn("تعذّر", self.gate(_census("S", fail=1)))

    def test_window_error_alone_refused(self):
        rep = _census("S")
        rep["sample"]["errors"] = 1
        self.assertIn("1 نافذةً", self.gate(rep))

    def test_severe_over_five_percent_refused(self):
        # س112+س113 = 4+5 = 9 آيات ⇒ آيةٌ جسيمةٌ واحدة 11% > 5%
        self.assertIn("عطبٌ جسيم", self.gate(_census("S", severe=1)))

    def test_header_mixing_without_splice_op_still_needs_census(self):
        d = _spliced()
        d["transform"] = {"op": "realign_surah:5"}
        self.assertIn("بلا إحصاء", self.gate(None, d))


class StageGuard(unittest.TestCase):
    def _stage(self, child, op):
        parent = _parent()
        pbody = gzip.compress(json.dumps(parent).encode())
        s3 = _S3({"timings/hafs/zz.jz": pbody})
        with tempfile.TemporaryDirectory() as t:
            f = Path(t) / "c.jz"
            f.write_bytes(gzip.compress(json.dumps(child).encode()))
            argv = ["x", "--file", str(f), "--parent", "timings/hafs/zz.jz",
                    "--parent-sha", "", "--op", op, "--reason", "اختبار"]
            with mock.patch.object(promote, "s3", return_value=(s3, "b")), \
                 mock.patch.object(promote, "catalog", return_value={}), \
                 mock.patch.object(sys, "argv", argv):
                try:
                    stage_transform.main()
                    return None
                except SystemExit as e:
                    return str(e)

    def test_declared_splice_accepted(self):
        self.assertIsNone(self._stage(_spliced(), "ctc_surah_splice:112,113"))

    def test_undeclared_surah_refused(self):
        d = _spliced()
        d["engineBySurah"] = {"112": "ctc-seg-1"}
        self.assertIn("بلا إعلانٍ", self._stage(d, "ctc_surah_splice:112,113"))

    def test_extra_declared_surah_refused(self):
        d = _spliced()
        d["engineBySurah"]["5"] = "ctc-seg-1"
        self.assertIn("لم يمسّها", self._stage(d, "ctc_surah_splice:112,113"))

    def test_header_growth_under_plain_realign_refused(self):
        self.assertIn("سجلُّ المحرّكات", self._stage(_spliced(), "realign_surah:112,113"))

    def test_outside_entries_untouched(self):
        d = _spliced()
        d["entries"] = [e for e in d["entries"] if e["ayahId"] != "1:1"]
        d["missing"] = {"count": 1, "ids": ["1:1"], "byReason": {}}
        self.assertIn("خارج السور", self._stage(d, "ctc_surah_splice:112,113"))


if __name__ == "__main__":
    unittest.main()
