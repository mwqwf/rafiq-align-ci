"""اختبارات الدمج المحلي الفعلي لصوت ثابت، مع منع الشبكة والسجل البديل."""
from __future__ import annotations

import copy
import gzip
import io
import json
import socket
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_same_source_candidate as B

URL = "https://example.org/current/042.mp3"
SHA = "a" * 64


class SameSourceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.root_patch = mock.patch.object(B.shared, "ROOT", self.root)
        self.root_patch.start()
        self.parent = {
            "riwaya": "hafs", "reciterId": "example", "engineVersion": "ctc-seg-1",
            "refineVersion": "refined-1", "ayahCount": 6236, "audioSha256": [SHA] * 114,
            "engineBySurah": {"2": "existing-engine"},
            "sourceBySurah": {"2": "https://example.org/other/{s:03d}.mp3", "42": URL},
            "alignmentModelBySurah": {"2": {"id": "existing-model"}},
            "missing": {"count": 0, "ids": [], "byReason": {}},
            "transform": {"op": "earlier", "truncatedTail": {}}, "lowCount": 0,
            "entries": [{"ayahId": f"{s}:{a}", "fileRef": f"https://example.org/current/{s:03d}.mp3",
                         "startMs": a * 1000, "endMs": (a + 1) * 1000,
                         "conf": .9, "confBand": "HIGH"}
                        for s, count in enumerate(B.splice_surah.COUNTS, 1)
                        for a in range(1, count + 1)],
        }
        self.aligned = {
            "surah": 42, "riwaya": "hafs", "engine": B.ENGINE,
            "fileRef": URL, "sha256": SHA, "totalMs": 55000,
            "heardMap": {str(a + 1): {"anchorMs": [a * 1000 + 100, (a + 1) * 1000],
                                      "anchorQuality": .9, "heard": True} for a in range(53)},
            "entries": [{"ayahIdx": a, "startMs": a * 1000 + 100,
                         "endMs": (a + 1) * 1000, "conf": .9, "snapped": True}
                        for a in range(53)],
        }
        self.parent_path, self.aligned_path = self.root / "parent.jz", self.root / "aligned.json"
        self.out = self.root / "ops/source-repair/candidates/same-source.jz"
        self.save()

    def tearDown(self):
        self.root_patch.stop()
        self.tmp.cleanup()

    def save(self):
        self.parent_blob = gzip.compress(json.dumps(self.parent).encode(), mtime=0)
        self.parent_path.write_bytes(self.parent_blob)
        self.parent_sha = B.sha256(self.parent_blob)
        self.aligned_path.write_text(json.dumps(self.aligned), encoding="utf-8")

    def build(self, **kwargs):
        with mock.patch.object(socket, "socket", side_effect=AssertionError("لا شبكة")), \
                mock.patch.object(B.stage_transform.promote, "s3", side_effect=AssertionError("لا دلو")), \
                mock.patch.object(B.shared.source_registry, "registered_source", side_effect=AssertionError("لا سجل بديل")), \
                redirect_stdout(io.StringIO()):
            return B.build(self.parent_path, kwargs.pop("parent_sha", self.parent_sha),
                           self.aligned_path, kwargs.pop("surah", 42), kwargs.pop("out", self.out), **kwargs)

    def result(self):
        return json.loads(gzip.decompress(self.out.read_bytes()))

    def test_real_splice_keeps_all_6236_ids_sources_and_nonselected_entries(self):
        report = self.build()
        candidate = self.result()
        B.check_preserved(self.parent, candidate, 42, B.parent_source(self.parent, 42))
        self.assertEqual(len(candidate["entries"]), 6236)
        self.assertEqual(candidate["sourceBySurah"], self.parent["sourceBySurah"])
        self.assertEqual(candidate["audioSha256"], self.parent["audioSha256"])
        self.assertEqual(candidate["transform"]["movedEntries"], 53)
        self.assertEqual(candidate["transform"]["addedEntries"], 0)
        self.assertEqual(candidate["transform"]["removedEntries"], 0)
        self.assertTrue(report["unpublishedLocalCandidate"])
        self.assertFalse(report["sourceChanged"])
        self.assertEqual(report["qualityChecks"], "pending")
        self.assertEqual(report["heardGate"], "pending")
        self.assertEqual(report["sha256"], B.sha256(self.out.read_bytes()))
        self.assertEqual(self.parent_path.read_bytes(), self.parent_blob)
        self.assertEqual(json.loads(self.aligned_path.read_text()), self.aligned)
        self.assertFalse(list(self.out.parent.glob(".candidate-*")))

    def test_original_catalog_source_never_gets_alternate_source_declaration(self):
        self.parent.pop("sourceBySurah")
        self.save()
        self.build()
        self.assertNotIn("sourceBySurah", self.result())

    def test_preserves_historical_transform_and_recounts_low_band(self):
        self.parent["transform"] = {
            "op": "declare_gap:42", "reasonCode": "SOURCE_TRUNCATED", "reasonUser": "سبب قديم",
            "gapAyahs": 4, "droppedEntries": 4, "truncatedTail": {"42": {"absentFrom": 50}},
            "sourceRepair": {"old": "قياس تاريخي"}, "provenance": {"older": "أقدم"},
        }
        self.parent["lowCount"] = 7
        self.aligned["entries"][0]["conf"] = .4
        self.save()
        self.build()
        candidate = self.result()
        self.assertEqual(candidate["lowCount"], 1)
        transform = candidate["transform"]
        self.assertEqual(transform["provenance"]["parentTransform"], self.parent["transform"])
        for field in ("reasonCode", "reasonUser", "gapAyahs", "droppedEntries", "sourceRepair"):
            self.assertNotIn(field, transform)
        self.assertEqual(transform["truncatedTail"], {})
        self.assertEqual(transform["sameSourceRepair"]["audioSha256"], SHA)

    def test_bad_parent_pin_or_identity_rejected_before_splice(self):
        for args in ({"parent_sha": "b" * 64}, {"parent_sha": self.parent_sha[:8]},
                     {"parent_key": "timings/hafs/another.jz"}):
            with self.subTest(args=args), mock.patch.object(B.splice_surah, "main") as splice:
                with self.assertRaises(ValueError):
                    self.build(**args)
                splice.assert_not_called()
        self.assertFalse(self.out.exists())

    def test_mismatched_audio_url_and_conflicting_aliases_rejected(self):
        for field, value in (("sha256", "b" * 64), ("fileRef", "https://other.org/042.mp3"),
                             ("sourceUrl", "https://other.org/042.mp3"), ("audioSha256", "b" * 64)):
            original = copy.deepcopy(self.aligned)
            self.aligned[field] = value
            self.save()
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.build()
            self.aligned = original
        self.assertFalse(self.out.exists())

    def test_matching_aliases_are_names_only(self):
        self.aligned.update(sourceUrl=URL, audioSha256=SHA)
        self.save()
        self.build()
        self.assertEqual(json.loads(self.aligned_path.read_text()), self.aligned)
        row = next(e for e in self.result()["entries"] if e["ayahId"] == "42:53")
        measured = self.aligned["entries"][52]
        self.assertEqual((row["startMs"], row["endMs"]), (measured["startMs"], measured["endMs"]))

    def test_incomplete_parent_or_source_sha_list_rejected(self):
        original = copy.deepcopy(self.parent)
        mutations = [lambda p: p["entries"].remove(next(e for e in p["entries"] if e["ayahId"] == "42:53")),
                     lambda p: p["audioSha256"].pop(),
                     lambda p: p["audioSha256"].__setitem__(41, ""),
                     lambda p: next(e for e in p["entries"] if e["ayahId"] == "42:53").update(fileRef="https://other.org/042.mp3")]
        for mutate in mutations:
            self.parent = copy.deepcopy(original)
            mutate(self.parent)
            self.save()
            with self.assertRaises((ValueError, SystemExit)):
                self.build()
        self.assertFalse(self.out.exists())

    def test_incomplete_or_invalid_measurement_rejected(self):
        original = copy.deepcopy(self.aligned)
        mutations = [lambda a: a["entries"].pop(), lambda a: a.update(heardMap={}),
                     lambda a: a["entries"][0].update(ayahIdx=1),
                     lambda a: a["entries"][-1].update(endMs=56000),
                     lambda a: a["entries"][1].update(startMs=200),
                     lambda a: a["entries"][0].update(startMs=None),
                     lambda a: a.update(surah=43), lambda a: a.update(riwaya="qalun")]
        for mutate in mutations:
            self.aligned = copy.deepcopy(original)
            mutate(self.aligned)
            self.save()
            with self.assertRaises(ValueError):
                self.build()
        self.assertFalse(self.out.exists())

    def test_post_splice_rejects_corrupted_sources_entries_counts_or_other_metadata(self):
        self.build()
        original = self.result()
        mutations = [lambda c: c["entries"][0].update(startMs=900),
                     lambda c: c["audioSha256"].__setitem__(41, "b" * 64),
                     lambda c: c["sourceBySurah"].__setitem__("42", "https://other.org/042.mp3"),
                     lambda c: c["engineBySurah"].pop("2"),
                     lambda c: c.update(ayahCount=1),
                     lambda c: c["missing"].update(count=1),
                     lambda c: next(e for e in c["entries"] if e["ayahId"] == "42:53").update(fileRef="https://other.org/042.mp3")]
        for mutate in mutations:
            candidate = copy.deepcopy(original)
            mutate(candidate)
            with self.assertRaises(ValueError):
                B.check_preserved(self.parent, candidate, 42, B.parent_source(self.parent, 42))

    def test_unrelated_missing_reason_cannot_be_erased_by_splice(self):
        self.parent["missing"]["byReason"] = {"source_truncated": 12}
        self.save()
        with self.assertRaisesRegex(ValueError, "missing"):
            self.build()
        self.assertFalse(self.out.exists())

    def test_input_mutation_or_structural_failure_writes_nothing(self):
        actual = B.splice_surah.main
        def mutate():
            actual()
            self.aligned_path.write_text("{}")
        with mock.patch.object(B.splice_surah, "main", side_effect=mutate):
            with self.assertRaisesRegex(ValueError, "تغيرت مدخلات"):
                self.build()
        self.save()
        self.parent.pop("refineVersion")
        self.save()
        with self.assertRaisesRegex(ValueError, "حارس بنية"):
            self.build()
        self.assertFalse(self.out.exists())

    def test_existing_candidate_is_never_overwritten(self):
        self.out.parent.mkdir(parents=True)
        self.out.write_bytes(b"prior evidence")
        with self.assertRaisesRegex(ValueError, "موجود"):
            self.build()
        self.assertEqual(self.out.read_bytes(), b"prior evidence")


if __name__ == "__main__":
    unittest.main()
