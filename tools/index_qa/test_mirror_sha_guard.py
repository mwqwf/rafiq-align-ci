# -*- coding: utf-8 -*-
"""اختبار mirror_sha_guard بلا شبكة: عدمُ ابتلاع الخطأ (فهرسٌ معطوب ⇒ «غيرُ قابلٍ للتحقّق» لا «لا مخالفة»)،
وقبولُ صيغتَي audioSha256، ومسحُ المرآة غير المسجَّلة (report فقط)."""
import copy
import gzip
import io
import json
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mirror_sha_guard as G  # noqa: E402
from index_fields import IndexFieldError  # noqa: E402

IDX = [f"{n:064x}" for n in range(1, 115)]


def _entry(rid, shas, **kw):
    e = {"id": rid, "mode": "surah", "complete": True,
         "perFile": [{"surah": n, "name": f"{n:03d}.mp3", "bytes": 1000 + n, "sha256": shas[n - 1], "clipsOk": True}
                     for n in range(1, 115)],
         "clipsOkBySurah": list(range(1, 115)), "clipsBlockedBySurah": [], "clipsBlockedReason": {},
         "timingIndexShaMatch": "MATCH", "usableForClips": True}
    e.update(kw)
    return e


class FakeSrc:
    """يحاكي Src.get على مفاتيح الدلو."""

    def __init__(self, objs):
        self.objs = objs
        self.public = True

    def get(self, key):
        if key not in self.objs:
            raise KeyError(key)
        v = self.objs[key]
        return v if isinstance(v, bytes) else json.dumps(v).encode()


def _jz(**hdr):
    return gzip.compress(json.dumps(dict(hdr, entries=[])).encode())


def _world(index_headers):
    """مانيفست hafs بقارئين a وb، وفهارسهما بالترويسات المعطاة."""
    bad = copy.deepcopy(IDX)
    bad[6] = "f" * 64
    man = {"reciters": [_entry("a", IDX), _entry("b", bad)]}
    objs = {"timings/manifest.json": {"indexes": [{"riwaya": "hafs", "reciterId": r} for r in ("a", "b")]},
            "audio/hafs/manifest.json": man}
    for rid, hdr in index_headers.items():
        if hdr is not None:
            objs[f"timings/hafs/{rid}.jz"] = _jz(**hdr)
    return FakeSrc(objs)


class ScanDoesNotSwallow(unittest.TestCase):
    def test_list_and_text_forms_give_same_verdict(self):
        for form in (IDX, json.dumps(IDX), repr(IDX)):
            res = G.scan(_world({"a": {"audioSha256": form}, "b": {"audioSha256": form}}), ("hafs",), set(), False, False)
            _man, rows, unver = res["hafs"]
            self.assertEqual(unver, {}, msg=type(form).__name__)
            self.assertEqual(rows["a"][2], {})
            self.assertEqual(rows["b"][2], {7: "SHA_MISMATCH"})          # مخالفة س7 تُكشف بالصيغتين

    def test_unreadable_index_is_unverifiable_not_clean(self):
        # a: ترويسةٌ بلا audioSha256 · b: الفهرسُ غائب (خطأ شبكة/404)
        res = G.scan(_world({"a": {}, "b": None}), ("hafs",), set(), False, False)
        _man, rows, unver = res["hafs"]
        self.assertEqual(rows, {})                                        # لا يُحسب أيٌّ منهما «نظيفاً»
        self.assertEqual(sorted(unver), ["a", "b"])
        self.assertIn("audioSha256", unver["a"])                          # السببُ مسمّى
        self.assertIn("KeyError", unver["b"])

    def test_malformed_text_is_unverifiable(self):
        res = G.scan(_world({"a": {"audioSha256": "[oops"}, "b": {"audioSha256": IDX}}), ("hafs",), set(), False, False)
        _man, rows, unver = res["hafs"]
        self.assertIn("a", unver)
        self.assertIn("b", rows)

    def test_report_exit_code_flags_unverifiable(self):
        src = _world({"a": {}, "b": {"audioSha256": IDX}})
        orig = G.Src
        G.Src = lambda public: src
        try:
            ns = type("A", (), dict(public=True, riwaya=["hafs"], only=None, verify_size=False, rehash=False))()
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = G.cmd_report(ns)
        finally:
            G.Src = orig
        out = buf.getvalue()
        self.assertEqual(rc, 3)                                           # b: س7 مخالفةٌ غيرُ محجوبة تغلب
        self.assertIn("غيرُ قابلٍ للتحقّق", out)

    def test_report_unverifiable_alone_is_nonzero(self):
        src = _world({"a": {}, "b": {"audioSha256": IDX}})
        # b نظيفٌ هنا (نُصلح مانيفستَه) ⇒ يبقى a وحدَه غيرَ قابلٍ للتحقّق ⇒ 6
        src.objs["audio/hafs/manifest.json"]["reciters"][1] = _entry("b", IDX)
        orig = G.Src
        G.Src = lambda public: src
        try:
            ns = type("A", (), dict(public=True, riwaya=["hafs"], only=None, verify_size=False, rehash=False))()
            with redirect_stdout(io.StringIO()):
                rc = G.cmd_report(ns)
        finally:
            G.Src = orig
        self.assertEqual(rc, 6)


class FindMismatchesStrict(unittest.TestCase):
    def test_invalid_index_sha_raises(self):
        e = _entry("x", IDX)
        for bad in (None, "[]", IDX[:100], {}):
            with self.assertRaises(IndexFieldError):
                G.find_mismatches(e, bad)


class Unregistered(unittest.TestCase):
    def test_find_unregistered_only_published_unregistered_mp3(self):
        keys = ["audio/hafs/qasm/002.mp3", "audio/hafs/a_klb/002.mp3", "audio/hafs/ghost/001.mp3",
                "audio/hafs/manifest.json", "audio/_manifest_backups/hafs/manifest.1.json",
                "audio/hafs/qasm/x.mp3", "audio/hafs/qasm/115.mp3", "audio/hafs/qasm/0002.mp3.part"]
        got = G.find_unregistered(keys, {("hafs", "a_klb")}, {("hafs", "qasm"), ("hafs", "a_klb")})
        self.assertEqual({k: sorted(v) for k, v in got.items()}, {("hafs", "qasm"): [2]})

    def test_compare_files(self):
        idx = list(IDX)
        idx[2] = None
        got = G.compare_files({1: IDX[0], 2: "e" * 64, 3: "d" * 64}, idx)
        self.assertEqual(got, {2: "SHA_MISMATCH", 3: "NO_INDEX_SHA"})
        with self.assertRaises(IndexFieldError):
            G.compare_files({1: IDX[0]}, IDX[:3])

    def test_cmd_is_report_only(self):
        """الأمرُ لا يستعمل أيَّ كتابةٍ إلى الدلو: لا put_object/upload_file/copy_object/delete في مساره."""
        import inspect
        src = inspect.getsource(G.cmd_unregistered)
        for w in ("put_object", "upload_file", "copy_object", "delete_object", "delete_objects"):
            self.assertNotIn(w, src)


class Selftest(unittest.TestCase):
    def test_builtin_selftest(self):
        with redirect_stdout(io.StringIO()):
            self.assertEqual(G.selftest(), 0)


if __name__ == "__main__":
    unittest.main()
