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

    def test_failed_realign_is_blocked_only_for_same_source_and_engine(self):
        old = "https://server6.mp3quran.net/kurdi/"
        self.assertTrue(loop.blocked_realign("hafs", "kurdi", 93, old))
        self.assertFalse(loop.blocked_realign(
            "hafs", "kurdi", 93, "https://verified-alternate.example/kurdi/"))
        self.assertFalse(loop.blocked_realign("hafs", "kurdi", 92, old))

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
             mock.patch.object(loop, "gh", side_effect=fake_gh), \
             mock.patch.dict(loop.os.environ, {"GITHUB_REF_NAME": "feature"}):
            loop.cmd_scan(types.SimpleNamespace(limit=1))

        flat = calls[-1]
        self.assertIn("parent=timings-staging/hafs/nufais.new.jz", flat)
        self.assertIn("surahs=46", flat)
        self.assertIn("--ref", flat)
        self.assertIn("feature", flat)

    def test_scan_does_not_repeat_tool_failure_on_unchanged_source(self):
        row = {"riwaya": "hafs", "reciter": "kurdi", "surah": 93,
               "have": 0, "expected": 11, "gap": 11,
               "key": "timings/hafs/kurdi.jz",
               "liveKey": "timings/hafs/kurdi.jz"}
        calls = []
        with mock.patch.object(loop, "catalog_bases", return_value={
                 ("hafs", "kurdi"): "https://server6.mp3quran.net/kurdi/"}), \
             mock.patch.object(loop, "fetch_index", return_value=(_idx(12), None)), \
             mock.patch.object(loop, "surah_ends", return_value={93: 10_000}), \
             mock.patch.object(loop, "inflight_reciters", return_value=set()), \
             mock.patch.object(loop, "candidates", return_value=[row]), \
             mock.patch.object(loop, "source_ratio", return_value=1.0), \
             mock.patch.object(loop, "measured_skip", return_value=3580), \
             mock.patch.object(loop, "gh", side_effect=lambda *a: calls.append(a)):
            loop.cmd_scan(types.SimpleNamespace(limit=1))
        self.assertEqual(calls, [])



# ───── الإحصاءُ الشامل والتشخيصُ الآليّ (‏عطبان مقيسان 2026-09-24) ─────
def _spliced_idx(op="ctc_surah_splice:45,46"):
    return {"entries": [], "engineVersion": "align-0.2",
            "engineBySurah": {"45": "ctc-seg-1", "46": "ctc-seg-1"},
            "transform": {"op": op}}


class CensusDispatchTests(unittest.TestCase):
    def test_spliced_without_census_needs_it(self):
        self.assertTrue(loop.needs_census(_spliced_idx(), "S", None))

    def test_census_on_same_sha_is_not_repeated(self):
        self.assertFalse(loop.needs_census(_spliced_idx(), "S", {"sha256": "S"}))

    def test_census_on_other_sha_is_redone(self):
        self.assertTrue(loop.needs_census(_spliced_idx(), "S", {"sha256": "X"}))

    def test_whisper_splice_also_needs_census(self):
        d = _spliced_idx("whisper_surah_splice:45")
        d["engineVersion"] = "ctc-seg-1"
        d["engineBySurah"] = {"45": "align-0.2"}
        self.assertTrue(loop.needs_census(d, "S", None))

    def test_unspliced_index_needs_no_census(self):
        self.assertFalse(loop.needs_census(_idx(3), "S", None))
        d = _spliced_idx("drop_surah:93")
        self.assertFalse(loop.needs_census(d, "S", None))

    def test_splice_op_without_foreign_engine_needs_no_census(self):
        d = _spliced_idx()
        d["engineBySurah"] = {"45": "align-0.2"}
        self.assertFalse(loop.needs_census(d, "S", None))

    def test_fully_salted_candidate_gets_census(self):
        # ⭐ حالةُ a_alhazmi: أربعةُ ملوحٍ مكتملة فلا يدخل الدفعة، وإحصاؤه غائب
        imp = [{"key": "timings-staging/hafs/a_alhazmi.6e289031.jz"},
               {"key": "timings-staging/hafs/lhdan.04f3d6be.jz"},
               {"key": "timings-staging/hafs/clean.aaaa.jz"},
               {"key": "timings-staging/hafs/waiting.bbbb.jz"},
               {"key": "timings-staging/hafs/busy.cccc.jz"}]
        salts = {"timings-staging/hafs/a_alhazmi.6e289031.jz": 4,
                 "timings-staging/hafs/lhdan.04f3d6be.jz": 1,
                 "timings-staging/hafs/clean.aaaa.jz": 4,
                 "timings-staging/hafs/waiting.bbbb.jz": 0,
                 "timings-staging/hafs/busy.cccc.jz": 4}
        due = {"timings-staging/hafs/a_alhazmi.6e289031.jz": True,
               "timings-staging/hafs/lhdan.04f3d6be.jz": True,
               "timings-staging/hafs/clean.aaaa.jz": False,
               "timings-staging/hafs/waiting.bbbb.jz": True,
               "timings-staging/hafs/busy.cccc.jz": True}
        asked = []

        def _due(k):
            asked.append(k)
            return due[k]
        got = loop.census_keys(imp, ["timings-staging/hafs/lhdan.04f3d6be.jz"],
                               # عنوانُ تشغيلةٍ جارية (‏إحصاءٌ على المفتاح نفسِه)
                               {"census timings-staging/hafs/busy.cccc.jz"},
                               salts.get, _due)
        self.assertEqual(got, ["timings-staging/hafs/a_alhazmi.6e289031.jz",
                               "timings-staging/hafs/lhdan.04f3d6be.jz"])
        # ما ينتظر دورَه في دفعةٍ لاحقة وما يُحاذى الآن لا يُقرأ ولا يُحصى
        self.assertNotIn("timings-staging/hafs/waiting.bbbb.jz", asked)
        self.assertNotIn("timings-staging/hafs/busy.cccc.jz", asked)

    def test_gate_dispatches_census_even_with_empty_batch(self):
        k = "timings-staging/hafs/a_alhazmi.6e289031.jz"
        calls = []
        with mock.patch.object(loop, "inflight_reciters", return_value=set()), \
             mock.patch.object(loop, "_staged_improvements",
                               return_value=[{"key": k, "gain": 5, "reciter": "a_alhazmi"}]), \
             mock.patch.object(loop, "_salt_count", return_value=4), \
             mock.patch.object(loop, "_census_due", return_value=True), \
             mock.patch.object(loop, "gh", side_effect=lambda *x: calls.append(x) or ""):
            loop.cmd_gate(types.SimpleNamespace(limit=6))
        self.assertEqual(len(calls), 1)
        self.assertIn("splice_census.yml", calls[0])
        self.assertIn(f"only={k}", calls[0])

    def test_gate_skips_census_when_already_counted(self):
        calls = []
        with mock.patch.object(loop, "inflight_reciters", return_value=set()), \
             mock.patch.object(loop, "_staged_improvements",
                               return_value=[{"key": "timings-staging/hafs/x.1.jz",
                                              "gain": 5, "reciter": "x"}]), \
             mock.patch.object(loop, "_salt_count", return_value=4), \
             mock.patch.object(loop, "_census_due", return_value=False), \
             mock.patch.object(loop, "gh", side_effect=lambda *x: calls.append(x) or ""):
            loop.cmd_gate(types.SimpleNamespace(limit=6))
        self.assertEqual(calls, [])


class DiagnosisDispatchTests(unittest.TestCase):
    STALE = ("  ⏳ timings-staging/hafs/lhdan.04f3d6be.jz: تشخيص الكتالوج يصف "
             "فهرساً آخر (بصمةٌ مخالفة) — يُنتظر ولا يُرقّى\n")

    def _promote(self, dry_out, real_out=""):
        calls = []

        def run(cmd, **_kw):
            if "--unfreeze" in cmd or "refreeze.py" in " ".join(map(str, cmd)):
                return types.SimpleNamespace(stdout="", returncode=0)
            out = real_out if "--yes" in cmd else dry_out
            return types.SimpleNamespace(stdout=out, returncode=0)
        imp = [{"key": "timings-staging/hafs/lhdan.04f3d6be.jz", "gain": 3,
                "reciter": "lhdan", "live": "timings/hafs/lhdan.jz"}]
        with mock.patch.object(loop, "_staged_improvements", return_value=imp), \
             mock.patch.object(loop, "_salt_count", return_value=4), \
             mock.patch.object(loop.subprocess, "run", side_effect=run), \
             mock.patch.object(loop, "gh", side_effect=lambda *x: calls.append(x) or ""):
            loop.cmd_promote(types.SimpleNamespace())
        return calls

    def test_waiting_branch_dispatches_diagnosis(self):
        # ⭐ حالةُ lhdan: التجربةُ الجافّةُ تردّه فيقع في «⏸️ لم يمرّ بعدُ»
        calls = self._promote(self.STALE)
        self.assertEqual(len(calls), 1)
        self.assertIn("diagnosis.yml", calls[0])
        self.assertIn("only=hafs/lhdan", calls[0])

    def test_failed_promotion_branch_still_dispatches(self):
        calls = self._promote("✅ جاهز\n", self.STALE)
        self.assertEqual([c for c in calls if "diagnosis.yml" in c].__len__(), 1)

    def test_other_waiting_reason_dispatches_nothing(self):
        self.assertEqual(self._promote("  🔴 سورٌ مبتورةٌ في المصدر (24)\n"), [])

    def test_once_per_reciter_per_round(self):
        fired = set()
        with mock.patch.object(loop, "gh", return_value="") as g:
            self.assertTrue(loop.maybe_diagnose(
                "timings-staging/hafs/lhdan.04f3d6be.jz", self.STALE, fired))
            self.assertFalse(loop.maybe_diagnose(
                "timings-staging/hafs/lhdan.99999999.jz", self.STALE, fired))
            self.assertTrue(loop.maybe_diagnose(
                "timings-staging/hafs/a_alhazmi.6e289031.jz", self.STALE, fired))
        self.assertEqual(g.call_count, 2)


if __name__ == "__main__":
    unittest.main()
