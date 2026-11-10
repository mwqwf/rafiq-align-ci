#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""إسقاطٌ جديدٌ يورِّث كلَّ إعلانٍ سابقٍ حرفاً برمزه ونصّه في حقله (‏قرار القائد 2026-11-10 · akri_qalun.b99e3573).

    python -m unittest tools/index_qa/test_drop_surah_declarations.py

العيّنة `testdata/akri_qalun.b99e3573.min.jz` هي الفهرسُ المنشور نفسُه (‏المداخلُ بحقولها الخمسة والترويسةُ كما هي):
`op = drop_surah:4|declare_gap:24` و`reasonCode = SOURCE_TRUNCATED` وذيلُ س24 من 31 إلى 64 معلَن.
والحالة: إسقاطُ س10 وس37 بـ`OTHER` (‏ذيلٌ مُزاحٌ عن صوته) — فكان الأصلُ إمّا أن يُمحى إعلانُه وإمّا أن يُكتب
للسور الأربع رمزٌ واحد. والمطلوب: `drop_surah:4,10,37|declare_gap:24`، ولكلّ سورةٍ رمزُها في سجلّها.
"""
from __future__ import annotations

import gzip
import hashlib
import io
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import drop_surah                                                # noqa: E402
import promote                                                   # noqa: E402

FIX = HERE / "testdata" / "akri_qalun.b99e3573.min.jz"
KEY = "timings/qalun/akri_qalun.jz"
NEW_USER = "توقيت هذه السورة لهذا القارئ قيد الإصلاح، فحُجبت مؤقّتاً حتى لا تُعرض آياتها على صوت غيرها"


class _Bucket:
    def __init__(self, body):
        self.store = {KEY: body}

    def get_object(self, Bucket, Key):                           # noqa: N803
        return {"Body": io.BytesIO(self.store[Key])}

    def put_object(self, Bucket, Key, Body, ContentType=None):   # noqa: N803
        self.store[Key] = Body

    def head_object(self, Bucket, Key):                          # noqa: N803
        return {"ContentLength": len(self.store[Key])}


def _body(mutate=None):
    raw = gzip.decompress(FIX.read_bytes())
    if mutate is None:
        return gzip.compress(raw, 9, mtime=0)
    idx = json.loads(raw)
    mutate(idx)
    return gzip.compress(json.dumps(idx, ensure_ascii=False).encode(), 9, mtime=0)


def _drop(body, surahs="10,37", *extra):
    b = _Bucket(body)
    sha = hashlib.sha256(body).hexdigest()[:8]
    argv = ["drop_surah.py", "--key", KEY, "--sha", sha, "--surah", surahs,
            "--reason", "ذيلُ السورة مُزاحٌ عن صوته (شاهدا Whisper)", "--yes", *extra]
    with mock.patch.object(promote, "s3", return_value=(b, "bk")), mock.patch.object(sys, "argv", argv):
        drop_surah.main()
    keys = [k for k in b.store if k.startswith("timings-staging/")]
    return json.loads(gzip.decompress(b.store[keys[0]]))


OTHER = ("--reason-code", "OTHER", "--reason-user", NEW_USER)


class B99e3573(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parent = json.loads(gzip.decompress(FIX.read_bytes()))
        cls.out = _drop(_body(), "10,37", *OTHER)

    def test_fixture_is_the_published_case(self):
        tr = self.parent["transform"]
        self.assertEqual(tr["op"], "drop_surah:4|declare_gap:24")
        self.assertEqual(tr["reasonCode"], "SOURCE_TRUNCATED")
        self.assertEqual(self.parent["missing"]["count"], 210)

    def test_op_merges_old_and_new(self):
        self.assertEqual(self.out["transform"]["op"], "drop_surah:4,10,37|declare_gap:24")

    def test_every_prior_declaration_inherited_verbatim(self):
        ptr, d = self.parent["transform"], self.out["transform"]["declarations"]
        for s, op in (("4", "drop_surah"), ("24", "declare_gap")):
            self.assertEqual(d[s], {"op": op, "reasonCode": ptr["reasonCode"],
                                    "reasonUser": ptr["reasonUser"], "reason": ptr["reason"]})
        self.assertEqual(self.out["transform"]["truncatedTail"], ptr["truncatedTail"])

    def test_new_drop_takes_its_own_code_one_code_per_field(self):
        tr = self.out["transform"]
        for s in ("10", "37"):
            self.assertEqual(tr["declarations"][s]["reasonCode"], "OTHER")
            self.assertEqual(tr["declarations"][s]["reasonUser"], NEW_USER)
        self.assertEqual(tr["reasonCode"], "OTHER")
        self.assertEqual(tr["truncatedTail"]["24"]["reason"], "source_truncated")
        for rec in tr["declarations"].values():
            self.assertIsInstance(rec["reasonCode"], str)
            self.assertNotIn(",", rec["reasonCode"])
            self.assertNotIn("|", rec["reasonCode"])

    def test_guards_accept_the_output(self):
        ok, why = promote.declared_truncated_tail(self.out, 24)
        self.assertTrue(ok, why)
        self.assertIsNone(promote.index_gate(self.out))
        present = {e["ayahId"].split(":")[0] for e in self.out["entries"]}
        self.assertFalse({"4", "10", "37"} & present)
        self.assertEqual(len(self.out["entries"]) + self.out["missing"]["count"], 6236)
        self.assertEqual(self.out["missing"]["count"], 210 + 109 + 182)

    def test_tail_record_cannot_borrow_the_top_code(self):
        # ⛔ سجلُّ الذيل وحده يعفيه: لو كان رمزُه OTHER لما أعفاه رمزٌ أعلى SOURCE_TRUNCATED.
        bad = json.loads(json.dumps(self.out))
        bad["transform"]["declarations"]["24"]["reasonCode"] = "OTHER"
        bad["transform"]["reasonCode"] = "SOURCE_TRUNCATED"
        self.assertFalse(promote.declared_truncated_tail(bad, 24)[0])
        gone = json.loads(json.dumps(self.out))
        del gone["transform"]["declarations"]["24"]
        self.assertFalse(promote.declared_truncated_tail(gone, 24)[0])


class NoPriorDeclarationDeleted(unittest.TestCase):
    def test_redeclaring_a_dropped_surah_refused(self):
        with self.assertRaises(SystemExit) as cm:
            _drop(_body(), "4,10", *OTHER)
        self.assertIn("معلَنةٌ سلفاً", str(cm.exception))

    def test_redeclaring_the_declared_tail_refused(self):
        with self.assertRaises(SystemExit) as cm:
            _drop(_body(), "24", *OTHER)
        self.assertIn("معلَنةٌ سلفاً", str(cm.exception))

    def test_declare_gap_mode_cannot_erase_either(self):
        with self.assertRaises(SystemExit):
            _drop(_body(), "24", "--declare-gap", *OTHER)

    def test_new_drop_without_code_refused(self):
        with self.assertRaises(SystemExit):
            _drop(_body(), "10")

    def test_tail_whose_record_is_not_source_truncated_refused(self):
        def m(idx):
            idx["transform"]["declarations"] = {
                "4": {"op": "drop_surah", "reasonCode": "SOURCE_TRUNCATED", "reasonUser": "x", "reason": "x"},
                "24": {"op": "declare_gap", "reasonCode": "OTHER", "reasonUser": "x", "reason": "x"}}
        with self.assertRaises(SystemExit):
            _drop(_body(m), "10", *OTHER)

    def test_existing_declarations_field_carried_verbatim(self):
        recs = {"4": {"op": "drop_surah", "reasonCode": "SOURCE_TRUNCATED", "reasonUser": "النساء ناقصة.",
                      "reason": "سجلّ س4"},
                "24": {"op": "declare_gap", "reasonCode": "SOURCE_TRUNCATED", "reasonUser": "النور ناقصة.",
                       "reason": "سجلّ س24"}}

        def m(idx):
            idx["transform"]["declarations"] = recs
        out = _drop(_body(m), "10", *OTHER)
        for s, rec in recs.items():
            self.assertEqual(out["transform"]["declarations"][s], rec)
        self.assertEqual(out["transform"]["op"], "drop_surah:4,10|declare_gap:24")

    def test_second_generation_keeps_all(self):
        # إسقاطٌ ثالثٌ فوق مخرَج الأوّل لا يمحو شيئاً منه.
        first = _drop(_body(), "10", *OTHER)
        body = gzip.compress(json.dumps(first, ensure_ascii=False).encode(), 9, mtime=0)
        second = _drop(body, "37", "--reason-code", "SOURCE_CORRUPT", "--reason-user", "ملفّ السورة تالف.")
        d = second["transform"]["declarations"]
        self.assertEqual(second["transform"]["op"], "drop_surah:4,10,37|declare_gap:24")
        self.assertEqual(d["10"], first["transform"]["declarations"]["10"])
        self.assertEqual(d["37"]["reasonCode"], "SOURCE_CORRUPT")
        self.assertEqual(d["24"]["reasonCode"], "SOURCE_TRUNCATED")
        self.assertTrue(promote.declared_truncated_tail(second, 24)[0])


if __name__ == "__main__":
    unittest.main()
