import datetime as dt
import email.message
from pathlib import Path
import types
import unittest
from unittest import mock

from tools.ci_fleet import restore_loop as loop


def _idx(n):
    return {"entries": [{"ayahId": f"1:{i + 1}", "endMs": 1000 + i}
                        for i in range(n)],
            "refineVersion": "test"}


class _Paginator:
    def paginate(self, **_kwargs):
        return [{"Contents": [
            {"Key": "timings-staging/hafs/nufais.old.jz",
             "LastModified": dt.datetime(2026, 9, 17, 0, 0)},
            {"Key": "timings-staging/hafs/nufais.new.jz",
             "LastModified": dt.datetime(2026, 9, 17, 1, 0)},
        ]}]


class _S3:
    def get_paginator(self, _name):
        return _Paginator()


class _Response:
    def __init__(self, headers):
        self.headers = email.message.Message()
        for key, value in headers.items():
            self.headers[key] = value

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class RestoreLoopTests(unittest.TestCase):
    def test_head_len_uses_one_byte_range_when_head_is_unsupported(self):
        responses = [OSError("HEAD unsupported"),
                     _Response({"Content-Range": "bytes 0-0/57088047"})]

        def open_side_effect(request, **_kwargs):
            response = responses.pop(0)
            if isinstance(response, Exception):
                raise response
            self.assertEqual(request.get_header("Range"), "bytes=0-0")
            return response

        with mock.patch.object(loop.urllib.request, "urlopen",
                               side_effect=open_side_effect):
            self.assertEqual(loop.head_len("https://audio/009.mp3"), 57_088_047)

    def test_source_override_is_scoped_to_exact_reciter_and_surah(self):
        bases = {("hafs", "3siri"): "https://catalog/3siri/"}
        self.assertEqual(
            loop.source_base(bases, "hafs", "3siri", 9),
            "https://media.way2quran.com/ibrahim-al-asiri/hafs-an-asim/",
        )
        self.assertEqual(loop.source_base(bases, "hafs", "3siri", 8),
                         "https://catalog/3siri/")
        self.assertIsNone(loop.source_base({}, "hafs", "missing", 9))

    def test_realign_guard_reads_same_surah_scoped_override_file(self):
        body = (Path(__file__).resolve().parents[2] / ".github" / "workflows" /
                "realign_surah.yml").read_text(encoding="utf-8")
        self.assertIn("SURAHS: ${{ github.event.inputs.surahs }}", body)
        self.assertIn('tools/ci_fleet/source_overrides.json', body)
        self.assertIn('len(selected) == len(surahs)', body)
        self.assertIn('got not in (want, mirror, override)', body)

    def test_effective_indexes_chains_latest_staged_gain(self):
        indexes = {
            "timings/hafs/nufais.jz": _idx(10),
            "timings-staging/hafs/nufais.old.jz": _idx(11),
            "timings-staging/hafs/nufais.new.jz": _idx(12),
        }
        with mock.patch.object(loop, "s3", return_value=(_S3(), "bucket")), \
             mock.patch.object(loop, "list_indexes",
                               return_value=[{"key": "timings/hafs/nufais.jz"}]), \
             mock.patch.object(loop, "fetch_index",
                               side_effect=lambda key: (indexes[key], None)):
            got = loop.effective_indexes()
        self.assertEqual(got[0]["key"], "timings-staging/hafs/nufais.new.jz")
        self.assertEqual(got[0]["liveKey"], "timings/hafs/nufais.jz")
        self.assertEqual(len(got[0]["index"]["entries"]), 12)

    def test_candidates_does_not_repeat_surah_repaired_in_staging(self):
        staged = {"entries": [{"ayahId": f"{s}:1", "endMs": s * 1000}
                              for s in range(1, 115) if s != 46],
                  "refineVersion": "test"}
        expected = [1] * 114
        expected[45] = 35
        with mock.patch.object(loop, "effective_indexes", return_value=[{
                 "key": "timings-staging/hafs/nufais.new.jz",
                 "liveKey": "timings/hafs/nufais.jz", "index": staged}]), \
             mock.patch.object(loop, "SURAH_AYAHS_OF", return_value=expected):
            got = loop.candidates()
        self.assertEqual([(r["surah"], r["key"]) for r in got], [
            (46, "timings-staging/hafs/nufais.new.jz")])

    def test_candidates_skips_non_kufi_index_without_stopping_fleet(self):
        bad = {"entries": [{"ayahId": "1:1"}], "ayahCounting": "qalun"}
        good = {"entries": [{"ayahId": "1:1"}], "refineVersion": "test"}
        expected = [1] * 114
        expected[1] = 4
        with mock.patch.object(loop, "effective_indexes", return_value=[
                 {"key": "timings/qalun/non_kufi.jz", "liveKey": "bad", "index": bad},
                 {"key": "timings/hafs/good.jz", "liveKey": "good", "index": good},
             ]), mock.patch.object(
                 loop, "SURAH_AYAHS_OF",
                 side_effect=[SystemExit("⛔ عدٌّ غير كوفيّ"), expected]):
            got = loop.candidates()
        self.assertEqual([(r["reciter"], r["surah"], r["gap"]) for r in got],
                         [("good", 2, 4)])

    def test_scan_passes_staged_parent_to_realign(self):
        row = {"riwaya": "hafs", "reciter": "nufais", "surah": 46,
               "have": 0, "expected": 35, "gap": 35,
               "key": "timings-staging/hafs/nufais.new.jz",
               "liveKey": "timings/hafs/nufais.jz"}
        calls = []

        def fake_gh(*args):
            calls.append(args)
            return "run-url"

        with mock.patch.object(loop, "catalog_bases",
                               return_value={("hafs", "nufais"): "https://audio/"}), \
             mock.patch.object(loop, "fetch_index", return_value=(_idx(12), None)), \
             mock.patch.object(loop, "surah_ends", return_value={46: 10_000}), \
             mock.patch.object(loop, "inflight_reciters", return_value=set()), \
             mock.patch.object(loop, "candidates", return_value=[row]), \
             mock.patch.object(loop, "source_ratio", return_value=1.0), \
             mock.patch.object(loop, "measured_skip", return_value=7340), \
             mock.patch.object(loop, "gh", side_effect=fake_gh):
            loop.cmd_scan(types.SimpleNamespace(limit=1))

        flat = calls[-1]
        self.assertIn("parent=timings-staging/hafs/nufais.new.jz", flat)
        self.assertIn("surahs=46", flat)


if __name__ == "__main__":
    unittest.main()
