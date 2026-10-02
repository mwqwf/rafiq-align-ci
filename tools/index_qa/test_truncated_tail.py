#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""اختباراتُ «الذيل المبتور» (أمر المالك 2026-10-02): بادئةٌ متّصلة 1..N تُقبل، فجوةٌ
وسطيّةٌ تُردّ، وN غيرُ مطابقةٍ تُردّ — في `stage_transform` و`splice_surah` و`promote`.

    python -m unittest tools/index_qa/test_truncated_tail.py

⛔ وتُثبت أنّ الحارسَ الأصل (`realigned_coverage_error`) ما زال يردّ الناقصَ بلا الخيار.
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
sys.path.insert(0, str(HERE.parent / "alignment_v3"))

import promote                                                   # noqa: E402
import stage_transform                                           # noqa: E402
from stage_transform import (AYAH_COUNTS, realigned_coverage_error,  # noqa: E402
                             truncated_header_error, truncated_tail_error)
from splice_surah import COUNTS                                  # noqa: E402
import quran_ctc_model as Q                                      # noqa: E402

S, N = 24, 30                     # النورُ عند العكري: 64 آية، البادئةُ 1..30
URL = "https://h.example/r/{s:03d}.mp3"
EV = {"id": Q.MODEL_ID, "revision": Q.REVISION, "weightsSha256": Q.WEIGHTS_SHA256,
      "license": "Apache-2.0", "canonicalTextChanged": False}


def _ids(s, ayahs):
    return {f"{s}:{a}" for a in ayahs}


FULL = _ids(S, range(1, 65))
PREFIX = _ids(S, range(1, N + 1))


class PureGuard(unittest.TestCase):
    def test_contiguous_prefix_accepted(self):
        self.assertIsNone(truncated_tail_error(set(), PREFIX, [S], {S: N}))

    def test_original_guard_still_refuses_partial(self):
        self.assertIn("لا يُرفع ناقص", realigned_coverage_error(set(), PREFIX, [S]))
        self.assertIn("لم تزد", realigned_coverage_error(PREFIX, PREFIX, [S], allow_inherited=True))

    def test_mid_gap_refused(self):
        self.assertIn("فجوةٌ وسطيّة", truncated_tail_error(set(), PREFIX - {f"{S}:15"}, [S], {S: N}))

    def test_n_mismatch_refused(self):
        self.assertIn("بعد N", truncated_tail_error(set(), PREFIX | {f"{S}:31"}, [S], {S: N}))
        self.assertIn("[30]", truncated_tail_error(set(), PREFIX - {f"{S}:30"}, [S], {S: N}))
        self.assertIn("فجوةٌ وسطيّة", truncated_tail_error(set(), PREFIX, [S], {S: 31}))

    def test_loss_and_no_gain_refused(self):
        self.assertIn("غابت", truncated_tail_error(_ids(S, [1, 31]), PREFIX, [S], {S: N}))
        self.assertIn("لم تزد", truncated_tail_error(PREFIX, PREFIX, [S], {S: N}))

    def test_tail_surah_must_be_realigned_and_others_complete(self):
        self.assertIn("ليست من السور", truncated_tail_error(set(), PREFIX, [23], {S: N}))
        full23 = _ids(23, range(1, 119))
        self.assertIsNone(truncated_tail_error(set(), PREFIX | full23, [23, S], {S: N}))
        self.assertIn("لا يُرفع ناقص", truncated_tail_error(set(), PREFIX | (full23 - {"23:7"}), [23, S], {S: N}))

    def test_header_must_declare_tail(self):
        tail = sorted(FULL - PREFIX, key=lambda x: int(x.split(":")[1]))
        idx = {"transform": {"truncatedTail": {"24": {"published": N, "absentFrom": N + 1,
                                                       "absentTo": 64, "reason": "source_truncated"}}},
               "missing": {"ids": tail, "byReason": {"source_truncated": 34}}}
        self.assertIsNone(truncated_header_error(idx, {S: N}))
        bad = json.loads(json.dumps(idx)); bad["transform"]["truncatedTail"]["24"]["published"] = 31
        self.assertIn("لا تُعلن", truncated_header_error(bad, {S: N}))
        bad = json.loads(json.dumps(idx)); bad["missing"]["ids"] = tail[:-1]
        self.assertIn("وسمُ الاكتمال", truncated_header_error(bad, {S: N}))
        bad = json.loads(json.dumps(idx)); bad["missing"]["byReason"] = {"source_truncated": 3}
        self.assertIn("byReason", truncated_header_error(bad, {S: N}))


# ═══ splice_surah --truncated-tail ═══
def _entries(skip_surah=None):
    out = []
    for s in range(1, 115):
        if s == skip_surah:
            continue
        for a in range(1, COUNTS[s - 1] + 1):
            st = a * 4000
            out.append({"ayahId": f"{s}:{a}", "fileRef": URL.format(s=s),
                        "startMs": st, "endMs": st + 3500, "conf": 0.9, "confBand": "HIGH"})
    return out


def _parent():
    ents = _entries(skip_surah=S)
    gone = [f"{S}:{a}" for a in range(1, 65)]
    return {"riwaya": "qalun", "reciterId": "zz", "engineVersion": "align-0.2",
            "refineVersion": "r1", "ayahCount": 6236, "ayahCounting": "KUFI",
            "entries": ents, "audioSha256": ["a" * 64] * 114,
            "missing": {"count": 64, "ids": gone, "byReason": {"no-align": 47, "source_truncated": 0}},
            "transform": {"op": "ctc_surah_splice:106", "dropSurah": [S],
                          "reasonCode": "SOURCE_TRUNCATED", "reasonUser": "تسجيلُ السورة ناقص."}}


def _aligned(keep=N, declared=None, hole=None, beyond=None):
    rows = []
    for i in range(64):
        st = 7000 + i * 20000
        bounded = i < keep
        if hole is not None and i + 1 == hole:
            bounded = False
        if beyond is not None and i + 1 == beyond:
            bounded = True
        rows.append({"ayahIdx": i, "startMs": st if bounded else None,
                     "endMs": st + 20000 if bounded else None,
                     "conf": 0.7 if bounded else 0.0, "snapped": True})
    return {"fileRef": URL.format(s=S), "sha256": "b" * 64, "surah": S, "totalMs": 766902,
            "engine": "ctc-quran-surah-1", "alignmentModel": EV,
            "truncatedTail": {"keep": keep if declared is None else declared},
            "entries": rows}


def _write(p, d):
    with gzip.open(p, "wt", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False)


def _load(p):
    with gzip.open(p, "rt", encoding="utf-8") as f:
        return json.load(f)


class SpliceTruncated(unittest.TestCase):
    def _run(self, aligned, flag=f"{S}:{N}", extra=()):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            _write(tmp / "p.jz", _parent())
            (tmp / "s024.json").write_text(json.dumps(aligned), encoding="utf-8")
            cmd = [sys.executable, str(HERE / "splice_surah.py"), "--index", str(tmp / "p.jz"),
                   "--surah", str(S), "--aligned", str(tmp / "s024.json"), "--url", URL,
                   "--skip-unresolved", "--engine-tag", "ctc-quran-surah-1",
                   "--truncated-tail", flag, "--out", str(tmp / "o.jz"), *extra]
            r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
            out = _load(tmp / "o.jz") if r.returncode == 0 else None
            return r, out

    def test_prefix_spliced_and_tail_declared(self):
        r, out = self._run(_aligned())
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        got = sorted(int(e["ayahId"].split(":")[1]) for e in out["entries"] if e["ayahId"].startswith("24:"))
        self.assertEqual(got, list(range(1, N + 1)))
        self.assertEqual(out["missing"]["count"], 34)
        self.assertEqual(out["missing"]["byReason"], {"source_truncated": 34})
        self.assertEqual(out["transform"]["truncatedTail"]["24"]["published"], N)
        self.assertEqual(out["transform"]["truncatedTail"]["24"]["absentTo"], 64)
        self.assertNotIn("dropSurah", out["transform"])
        self.assertEqual(out["engineBySurah"], {"24": "ctc-quran-surah-1"})
        self.assertEqual(out["alignmentModelBySurah"]["24"], EV)
        self.assertEqual((Path(r.args[r.args.index("--out") + 1]).name), "o.jz")

    def test_declared_keep_mismatch_refused(self):
        r, _ = self._run(_aligned(declared=31))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("لا يُدمج ما لم تتّفق", r.stdout + r.stderr)
        r, _ = self._run(_aligned(), flag=f"{S}:31")
        self.assertNotEqual(r.returncode, 0)

    def test_mid_gap_refused(self):
        r, _ = self._run(_aligned(hole=15))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("15 بلا حدود", r.stdout + r.stderr)

    def test_entry_beyond_tail_refused(self):
        r, _ = self._run(_aligned(beyond=33))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("بعد البتر", r.stdout + r.stderr)

    def test_requires_engine_tag_and_no_parent_gaps(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            _write(tmp / "p.jz", _parent())
            (tmp / "s024.json").write_text(json.dumps(_aligned()), encoding="utf-8")
            base = [sys.executable, str(HERE / "splice_surah.py"), "--index", str(tmp / "p.jz"),
                    "--surah", str(S), "--aligned", str(tmp / "s024.json"), "--url", URL,
                    "--truncated-tail", f"{S}:{N}", "--out", str(tmp / "o.jz")]
            r = subprocess.run(base, capture_output=True, text=True, encoding="utf-8")
            self.assertNotEqual(r.returncode, 0)
            r = subprocess.run(base + ["--engine-tag", "ctc-quran-surah-1", "--keep-parent-gaps"],
                               capture_output=True, text=True, encoding="utf-8")
            self.assertNotEqual(r.returncode, 0)


# ═══ stage_transform --owner-truncated-tail (دلوٌ في الذاكرة) ═══
class _S3:
    def __init__(self, objs):
        self.objs = objs

    def get_object(self, Bucket, Key):                          # noqa: N803
        return {"Body": io.BytesIO(self.objs[Key])}

    def put_object(self, **kw):
        self.objs[kw["Key"]] = kw["Body"]

    def head_object(self, Bucket, Key):                         # noqa: N803
        return {"ContentLength": len(self.objs[Key])}


def _child(n=N, hole=None):
    d = _parent()
    rows = []
    for a in range(1, n + 1):
        if a == hole:
            continue
        st = 7000 + a * 20000
        rows.append({"ayahId": f"{S}:{a}", "fileRef": URL.format(s=S), "startMs": st,
                     "endMs": st + 20000, "conf": 0.7, "confBand": "MED"})
    d["entries"] = sorted(d["entries"] + rows, key=lambda e: tuple(map(int, e["ayahId"].split(":"))))
    have = {e["ayahId"] for e in d["entries"]}
    gone = [f"{S}:{a}" for a in range(1, 65) if f"{S}:{a}" not in have]
    d["missing"] = {"count": len(gone), "ids": gone, "byReason": {"source_truncated": 64 - n}}
    d["engineBySurah"] = {"24": "ctc-quran-surah-1"}
    d["alignmentModelBySurah"] = {"24": EV}
    d["transform"] = {"op": "ctc_surah_splice:106", "reasonCode": "SOURCE_TRUNCATED",
                      "reasonUser": "تسجيلُ السورة ناقص.",
                      "truncatedTail": {"24": {"published": n, "absentFrom": n + 1, "absentTo": 64,
                                               "reason": "source_truncated"}}}
    return d


class StageTruncated(unittest.TestCase):
    def _stage(self, child, extra=()):
        pbody = gzip.compress(json.dumps(_parent()).encode())
        s3 = _S3({"timings/qalun/zz.jz": pbody})
        with tempfile.TemporaryDirectory() as t:
            f = Path(t) / "c.jz"
            f.write_bytes(gzip.compress(json.dumps(child).encode()))
            argv = ["x", "--file", str(f), "--parent", "timings/qalun/zz.jz", "--parent-sha", "",
                    "--op", "ctc_quran_surah_splice:24", "--reason", "اختبار", *extra]
            with mock.patch.object(promote, "s3", return_value=(s3, "b")), \
                 mock.patch.object(promote, "catalog", return_value={}), \
                 mock.patch.object(sys, "argv", argv):
                try:
                    stage_transform.main()
                    return None
                except SystemExit as e:
                    return str(e)

    def test_refused_without_option(self):
        self.assertIn("لا يُرفع ناقص", self._stage(_child()))

    def test_accepted_with_named_n(self):
        self.assertIsNone(self._stage(_child(), ["--owner-truncated-tail", "24:30"]))

    def test_wrong_n_refused(self):
        self.assertIsNotNone(self._stage(_child(), ["--owner-truncated-tail", "24:31"]))
        self.assertIsNotNone(self._stage(_child(), ["--owner-truncated-tail", "24:29"]))

    def test_mid_gap_refused(self):
        self.assertIn("فجوةٌ وسطيّة", self._stage(_child(hole=12), ["--owner-truncated-tail", "24:30"]))

    def test_header_without_declaration_refused(self):
        c = _child()
        c["transform"].pop("truncatedTail")
        self.assertIn("لا تُعلن", self._stage(c, ["--owner-truncated-tail", "24:30"]))


# ═══ promote.declared_truncated_tail ═══
def _final(n=N, op="declare_gap:24", hole=None, code="SOURCE_TRUNCATED", user="تسجيلٌ ناقص."):
    d = _child(n, hole)
    d["transform"].update({"op": op, "reasonCode": code, "reasonUser": user})
    return d


class PromoteTruncated(unittest.TestCase):
    def test_declared_prefix_accepted(self):
        ok, why = promote.declared_truncated_tail(_final(), 24)
        self.assertTrue(ok, why)
        self.assertIn("1..30", why)

    def test_mid_gap_refused(self):
        ok, why = promote.declared_truncated_tail(_final(hole=9), 24)
        self.assertFalse(ok); self.assertIn("متّصلة", why)

    def test_wrong_n_in_header_refused(self):
        d = _final(); d["transform"]["truncatedTail"]["24"]["published"] = 31
        self.assertFalse(promote.declared_truncated_tail(d, 24)[0])

    def test_user_declaration_required(self):
        self.assertFalse(promote.declared_truncated_tail(_final(op="ctc_quran_surah_splice:24"), 24)[0])
        self.assertFalse(promote.declared_truncated_tail(_final(code="OTHER"), 24)[0])
        self.assertFalse(promote.declared_truncated_tail(_final(user=""), 24)[0])

    def test_missing_ids_must_cover_tail(self):
        d = _final(); d["missing"]["ids"] = d["missing"]["ids"][:-1]
        self.assertFalse(promote.declared_truncated_tail(d, 24)[0])

    def test_other_surah_not_excused(self):
        self.assertFalse(promote.declared_truncated_tail(_final(), 107)[0])


if __name__ == "__main__":
    unittest.main()
