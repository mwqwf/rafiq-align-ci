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
                           kwargs.pop("aligned_path", self.aligned_path), kwargs.pop("surah", 42),
                           kwargs.pop("out", self.out), **kwargs)

    def result(self):
        return json.loads(gzip.decompress(self.out.read_bytes()))

    def multi_inputs(self, surahs=(25, 41, 42, 82)):
        """لكل سورة قياس مستقل وبصمة مختلفة؛ يظل الأب الخام واحداً."""
        paths = []
        for s in surahs:
            n = B.splice_surah.COUNTS[s - 1]
            audio_sha = f"{s:064x}"
            self.parent["audioSha256"][s - 1] = audio_sha
            aligned = copy.deepcopy(self.aligned)
            aligned.update(surah=s, fileRef=f"https://example.org/current/{s:03d}.mp3",
                           sha256=audio_sha, totalMs=(n + 2) * 1000,
                           heardMap={str(a + 1): {"anchorMs": [a * 1000 + 100, (a + 1) * 1000],
                                                 "anchorQuality": .9, "heard": True} for a in range(n)},
                           entries=[{"ayahIdx": a, "startMs": a * 1000 + 100,
                                     "endMs": (a + 1) * 1000, "conf": .9, "snapped": True}
                                    for a in range(n)])
            path = self.root / f"aligned-{s}.json"
            path.write_text(json.dumps(aligned), encoding="utf-8")
            paths.append(path)
        self.save()
        return paths

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
        self.assertEqual(report["surah"], 42)
        self.assertEqual(report["alignedSha256"], B.sha256(self.aligned_path.read_bytes()))
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

    def test_multiple_surahs_use_one_splice_and_one_raw_parent(self):
        surahs = [25, 41, 42, 82]
        paths = self.multi_inputs(surahs)
        before = [p.read_bytes() for p in paths]
        with mock.patch.object(B.splice_surah, "main", wraps=B.splice_surah.main) as splice:
            report = self.build(aligned_path=paths, surah=surahs)
        splice.assert_called_once()
        candidate = self.result()
        sources = {s: B.parent_source(self.parent, s) for s in surahs}
        B.check_preserved(self.parent, candidate, surahs, sources)
        self.assertEqual(candidate["transform"]["op"], f"{B.OP}:25,41,42,82")
        self.assertEqual(candidate["transform"]["fromSha256"], self.parent_sha)
        self.assertEqual(candidate["transform"]["movedEntries"], 77 + 54 + 53 + 19)
        self.assertEqual(candidate["transform"]["addedEntries"], 0)
        self.assertEqual(candidate["transform"]["removedEntries"], 0)
        self.assertEqual(candidate["missing"], self.parent["missing"])
        self.assertEqual(candidate["audioSha256"], self.parent["audioSha256"])
        self.assertEqual(candidate["sourceBySurah"], self.parent["sourceBySurah"])
        self.assertEqual(report["surahs"], surahs)
        self.assertEqual(report["qualityChecks"], "pending")
        self.assertEqual(report["heardGate"], "pending")
        self.assertFalse(report["sourceChanged"])
        repairs = candidate["transform"]["sameSourceRepair"]
        self.assertEqual(repairs["surahs"], surahs)
        for s, blob in zip(surahs, before):
            self.assertEqual(repairs["bySurah"][str(s)]["audioSha256"], sources[s]["audio_sha256"])
            self.assertEqual(report["alignedSha256BySurah"][str(s)], B.sha256(blob))
            row = next(e for e in candidate["entries"] if e["ayahId"] == f"{s}:1")
            self.assertEqual((row["startMs"], row["endMs"]), (100, 1000))
        self.assertEqual(self.parent_path.read_bytes(), self.parent_blob)
        self.assertEqual([p.read_bytes() for p in paths], before)

    def test_multiple_alignment_order_count_and_duplicate_surahs_are_rejected(self):
        paths = self.multi_inputs()
        cases = [(paths[::-1], [25, 41, 42, 82]), (paths[:-1], [25, 41, 42, 82]),
                 ([paths[0], paths[0]], [25, 25]), ([], [])]
        for aligned_paths, surahs in cases:
            with self.subTest(surahs=surahs), mock.patch.object(B.splice_surah, "main") as splice:
                with self.assertRaises(ValueError):
                    self.build(aligned_path=aligned_paths, surah=surahs)
                splice.assert_not_called()
        self.assertFalse(self.out.exists())

    def test_wrong_sha_or_incomplete_last_surah_rejects_whole_batch(self):
        paths = self.multi_inputs()
        original = json.loads(paths[-1].read_text())
        for mutation in (lambda a: a.update(sha256="b" * 64),
                         lambda a: a.update(audioSha256="b" * 64),
                         lambda a: a["entries"].pop()):
            aligned = copy.deepcopy(original)
            mutation(aligned)
            paths[-1].write_text(json.dumps(aligned), encoding="utf-8")
            with mock.patch.object(B.splice_surah, "main") as splice:
                with self.assertRaises(ValueError):
                    self.build(aligned_path=paths, surah=[25, 41, 42, 82])
                splice.assert_not_called()
        self.assertFalse(self.out.exists())

    def test_multiple_sources_in_different_folders_are_rejected_explicitly(self):
        paths = self.multi_inputs()
        for row in self.parent["entries"]:
            if row["ayahId"].startswith("82:"):
                row["fileRef"] = "https://example.org/another/082.mp3"
        aligned = json.loads(paths[-1].read_text())
        aligned["fileRef"] = "https://example.org/another/082.mp3"
        paths[-1].write_text(json.dumps(aligned), encoding="utf-8")
        self.save()
        with mock.patch.object(B.splice_surah, "main") as splice:
            with self.assertRaisesRegex(ValueError, "مجلدات مختلفة"):
                self.build(aligned_path=paths, surah=[25, 41, 42, 82])
            splice.assert_not_called()
        self.assertFalse(self.out.exists())

    def test_multiple_surah_merge_rejects_reordered_ids_or_outside_changes(self):
        surahs = [25, 41, 42, 82]
        paths = self.multi_inputs(surahs)
        self.build(aligned_path=paths, surah=surahs)
        original = self.result()
        sources = {s: B.parent_source(self.parent, s) for s in surahs}
        def reorder(candidate):
            rows = candidate["entries"]
            i = next(i for i, e in enumerate(rows) if e["ayahId"] == "25:1")
            rows[i], rows[i + 1] = rows[i + 1], rows[i]
        mutations = [reorder, lambda c: c["entries"][0].update(startMs=900),
                     lambda c: c["audioSha256"].__setitem__(81, "b" * 64),
                     lambda c: c["sourceBySurah"].__setitem__("25", "https://other.org/025.mp3"),
                     lambda c: c["alignmentModelBySurah"].pop("2"),
                     lambda c: c["engineBySurah"].pop("82"),
                     lambda c: c["missing"].update(count=1)]
        for mutate in mutations:
            candidate = copy.deepcopy(original)
            mutate(candidate)
            with self.assertRaises(ValueError):
                B.check_preserved(self.parent, candidate, surahs, sources)

    def test_multiple_surah_history_is_preserved_and_stale_source_reason_removed(self):
        self.parent["transform"] = {
            "op": "declare_gap:25,82", "reasonCode": "SOURCE_CORRUPT", "reasonUser": "تاريخ المصدر",
            "truncatedTail": {"25": {"absentFrom": 50}, "82": {"absentFrom": 17}},
            "dropSurah": [25, 82], "gapAyahs": 4, "droppedEntries": 4,
            "sourceRepair": {"old": "قياس سابق"}, "sameSourceRepair": {"old": "تصحيح سابق"},
            "provenance": {"older": "تاريخ محفوظ"},
        }
        paths = self.multi_inputs()
        self.build(aligned_path=paths, surah=[25, 41, 42, 82])
        transform = self.result()["transform"]
        self.assertEqual(transform["provenance"]["parentTransform"], self.parent["transform"])
        self.assertEqual(transform["provenance"]["parentSha256"], self.parent_sha)
        self.assertEqual(transform["truncatedTail"], {})
        self.assertEqual(transform["dropSurah"], [])
        for field in ("reasonCode", "reasonUser", "gapAyahs", "droppedEntries", "sourceRepair"):
            self.assertNotIn(field, transform)
        self.assertEqual(set(transform["sameSourceRepair"]["bySurah"]), {"25", "41", "42", "82"})

    def test_mutation_of_last_alignment_after_multiple_splice_writes_nothing(self):
        paths = self.multi_inputs()
        actual = B.splice_surah.main
        def mutate():
            actual()
            paths[-1].write_text("{}", encoding="utf-8")
        with mock.patch.object(B.splice_surah, "main", side_effect=mutate):
            with self.assertRaisesRegex(ValueError, "تغيرت مدخلات"):
                self.build(aligned_path=paths, surah=[25, 41, 42, 82])
        self.assertFalse(self.out.exists())

    def test_cli_passes_multiple_measurements_in_explicit_surah_order(self):
        paths = self.multi_inputs()
        argv = [B.__file__, "--parent", str(self.parent_path), "--parent-sha", self.parent_sha,
                "--aligned", *map(str, paths), "--surah", "25,41,42,82", "--out", str(self.out)]
        with mock.patch.object(sys, "argv", argv), mock.patch.object(B, "build") as build, \
                redirect_stdout(io.StringIO()):
            build.return_value = {"qualityChecks": "pending"}
            B.main()
        self.assertEqual(build.call_args.args[2], list(map(str, paths)))
        self.assertEqual(build.call_args.args[3], [25, 41, 42, 82])


if __name__ == "__main__":
    unittest.main()
