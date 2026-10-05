"""حراس المرشح المحلي باستعمال الدمج الحقيقي ومدخلات مقيسة مصغرة."""
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
import build_registered_candidate as B

SHA = "b" * 64
URL = "https://example.org/registered/063.mp3"


class CandidateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.root_patch = mock.patch.object(B, "ROOT", self.root)
        self.root_patch.start()
        self.registry = [{"riwaya": "hafs", "reciter": "example", "surah": 63,
                          "url": URL, "audio_sha256": SHA, "evidence": "قياس مستقل محدد"}]
        self.registry_path = self.root / "registry.json"
        self.registry_path.write_text(json.dumps(self.registry), encoding="utf-8")
        self.registry_patch = mock.patch.object(B.source_registry, "REGISTRY", self.registry_path)
        self.registry_patch.start()
        self.parent = {"riwaya": "hafs", "reciterId": "example", "engineVersion": "ctc-seg-1",
                       "refineVersion": "refined-1", "ayahCount": 6236,
                       "audioSha256": ["a" * 64] * 114,
                       "engineBySurah": {"2": "existing-engine"},
                       "sourceBySurah": {"2": "https://example.org/old/{s:03d}.mp3"},
                       "alignmentModelBySurah": {"2": {"id": "existing-model"}},
                       "transform": {"op": "earlier", "truncatedTail": {}},
                       "missing": {"count": 0, "ids": [], "byReason": {}},
                       "entries": [{"ayahId": f"{s}:{a}", "fileRef": f"https://example.org/old/{s:03d}.mp3",
                                    "startMs": a * 1000, "endMs": (a + 1) * 1000,
                                    "conf": .9, "confBand": "HIGH"}
                                   for s, n in enumerate(B.splice_surah.COUNTS, 1)
                                   for a in range(1, n + 1)]}
        self.aligned = {"surah": 63, "riwaya": "hafs", "engine": B.ENGINE,
                        "fileRef": URL, "sha256": SHA, "totalMs": 13000,
                        "heardMap": {str(i + 1): {"anchorMs": [i * 1000 + 100, (i + 1) * 1000],
                                                    "anchorQuality": .9, "heard": True}
                                     for i in range(11)},
                        "entries": [{"ayahIdx": i, "startMs": i * 1000 + 100,
                                     "endMs": (i + 1) * 1000, "conf": .9, "snapped": True}
                                    for i in range(11)]}
        self.parent_path = self.root / "parent.jz"
        self.aligned_path = self.root / "aligned.json"
        self.out = self.root / "ops/source-repair/candidates/test.jz"
        self.save_inputs()

    def tearDown(self):
        self.registry_patch.stop()
        self.root_patch.stop()
        self.tmp.cleanup()

    def save_inputs(self):
        self.parent_blob = gzip.compress(json.dumps(self.parent).encode(), mtime=0)
        self.parent_path.write_bytes(self.parent_blob)
        self.parent_sha = B.sha256(self.parent_blob)
        self.aligned_path.write_text(json.dumps(self.aligned), encoding="utf-8")

    def build(self, **kwargs):
        # أي اتصال عرضي في المسار المحلي يفشل الاختبار بدلاً من جلب بيانات حقيقية.
        with mock.patch.object(socket, "socket", side_effect=AssertionError("لا شبكة")), \
                mock.patch.object(B.stage_transform.promote, "s3", side_effect=AssertionError("لا دلو")), \
                redirect_stdout(io.StringIO()):
            return B.build(self.parent_path, kwargs.pop("parent_sha", self.parent_sha),
                           self.aligned_path, kwargs.pop("surah", 63), kwargs.pop("out", self.out), **kwargs)

    def test_actual_splice_preserves_other_surahs_and_marks_pending_quality(self):
        with mock.patch.object(B.time, "time", return_value=1234):
            report = self.build()
        blob = self.out.read_bytes()
        result = json.loads(gzip.decompress(blob))
        B.check_preserved(self.parent, result, 63, self.registry[0])
        self.assertEqual(report["sha256"], B.sha256(blob))
        self.assertTrue(report["unpublishedLocalCandidate"])
        self.assertEqual(report["qualityChecks"], "pending")
        self.assertEqual(report["heardGate"], "pending")
        transform = result["transform"]
        self.assertEqual(transform["op"], "ctc_heardmap_splice:63")
        self.assertEqual(transform["fromKey"], "timings/hafs/example.jz")
        self.assertEqual(transform["fromSha256"], self.parent_sha)
        self.assertEqual(transform["entriesSha256"], B.stage_transform.entries_sha(result["entries"]))
        self.assertEqual(transform["movedEntries"], 11)
        self.assertEqual(transform["addedEntries"], 0)
        self.assertEqual(transform["removedEntries"], 0)
        self.assertEqual(result["sourceBySurah"]["63"], URL)
        self.assertEqual(result["audioSha256"][62], SHA)
        self.assertNotIn("lowCount", result)
        self.assertEqual(self.parent_path.read_bytes(), self.parent_blob)
        self.assertEqual(json.loads(self.aligned_path.read_text()), self.aligned)
        self.assertFalse(list(self.out.parent.glob(".candidate-*")))

    def test_full_parent_sha_is_required_and_checked_before_splice(self):
        for sha in (self.parent_sha[:8], "f" * 64):
            with self.subTest(sha=sha), mock.patch.object(B.splice_surah, "main") as splice:
                with self.assertRaisesRegex(ValueError, "بصمة"):
                    self.build(parent_sha=sha)
                splice.assert_not_called()
        self.assertFalse(self.out.exists())

    def test_rejects_wrong_source_sha_or_url_without_writing(self):
        for field, value in (("sha256", "c" * 64), ("fileRef", "https://other.org/063.mp3"),
                             ("sourceUrl", "https://other.org/063.mp3"), ("audioSha256", "c" * 64)):
            with self.subTest(field=field):
                original = copy.deepcopy(self.aligned)
                self.aligned[field] = value
                self.save_inputs()
                with self.assertRaises(ValueError):
                    self.build()
                self.aligned = original
        self.assertFalse(self.out.exists())

    def test_rejects_probe_reordered_missing_overlapping_or_unbounded_entries(self):
        mutations = [lambda a: a.update(entries=[]),
                     lambda a: a["entries"][0].update(ayahIdx=1),
                     lambda a: a["entries"][0].update(startMs=None),
                     lambda a: a["entries"][1].update(startMs=500),
                     lambda a: a["entries"][-1].update(endMs=20000),
                     lambda a: a["entries"][0].update(conf=float("nan")),
                     lambda a: a.update(heardMap={}),
                     lambda a: a.update(surah=64),
                     lambda a: a.update(riwaya="warsh")]
        for mutate in mutations:
            original = copy.deepcopy(self.aligned)
            mutate(self.aligned)
            self.save_inputs()
            with self.assertRaises(ValueError):
                self.build()
            self.aligned = original
        self.assertFalse(self.out.exists())

    def test_rejects_missing_registry_pin_or_duplicate_registration(self):
        for rows in ([{k: v for k, v in self.registry[0].items() if k != "audio_sha256"}],
                     self.registry * 2, []):
            self.registry_path.write_text(json.dumps(rows))
            with self.assertRaises(ValueError):
                self.build()
        self.assertFalse(self.out.exists())

    def test_rejects_parent_without_all_114_source_slots(self):
        self.parent["audioSha256"].pop()
        self.save_inputs()
        with self.assertRaisesRegex(ValueError, "114"):
            self.build()

    def test_existing_output_is_never_replaced(self):
        self.out.parent.mkdir(parents=True)
        self.out.write_bytes(b"existing evidence")
        with self.assertRaisesRegex(ValueError, "موجود"):
            self.build()
        self.assertEqual(self.out.read_bytes(), b"existing evidence")

    def test_output_must_be_direct_child_and_not_symlink(self):
        for path in (self.root / "elsewhere.jz", self.out.parent / "sub" / "test.jz"):
            with self.assertRaises(ValueError):
                self.build(out=path)
        self.out.parent.parent.mkdir(parents=True)
        other = self.root / "other"
        other.mkdir()
        self.out.parent.symlink_to(other, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "رمزية"):
            self.build()
        self.assertFalse(list(other.iterdir()))

    def test_staged_parent_key_must_match_full_parent_fingerprint(self):
        good = f"timings-staging/hafs/example.{self.parent_sha[:8]}.jz"
        self.build(parent_key=good)
        self.assertEqual(json.loads(gzip.decompress(self.out.read_bytes()))["transform"]["fromKey"], good)
        for bad in ("timings/hafs/other.jz", "timings-staging/hafs/example.12345678.jz"):
            with self.assertRaises(ValueError):
                B.checked_parent_key(self.parent, self.parent_sha, bad)

    def test_post_splice_guard_rejects_changed_outside_entry_sha_and_declarations(self):
        self.build()
        candidate = json.loads(gzip.decompress(self.out.read_bytes()))
        mutations = [lambda c: c["entries"][0].update(startMs=999999),
                     lambda c: c["audioSha256"].__setitem__(0, "e" * 64),
                     lambda c: c["sourceBySurah"].__setitem__("2", "https://other.org/002.mp3"),
                     lambda c: c["engineBySurah"].pop("2"),
                     lambda c: c["alignmentModelBySurah"]["2"].update(id="changed")]
        for mutate in mutations:
            altered = copy.deepcopy(candidate)
            mutate(altered)
            with self.assertRaisesRegex(ValueError, "خارج"):
                B.check_preserved(self.parent, altered, 63, self.registry[0])

    def test_structural_gate_failure_leaves_no_candidate(self):
        self.parent.pop("refineVersion")
        self.save_inputs()
        with self.assertRaisesRegex(ValueError, "حارس بنية"):
            self.build()
        self.assertFalse(self.out.exists())

    def test_input_mutation_during_splice_is_rejected(self):
        original_splice = B.splice_surah.main
        def mutate():
            original_splice()
            self.aligned_path.write_text("{}")
        with mock.patch.object(B.splice_surah, "main", side_effect=mutate):
            with self.assertRaisesRegex(ValueError, "تغيرت مدخلات"):
                self.build()
        self.assertFalse(self.out.exists())

    def test_splice_cannot_reduce_unrelated_truncation_explanation(self):
        self.parent["missing"]["byReason"] = {"source_truncated": 20}
        self.save_inputs()
        with self.assertRaisesRegex(ValueError, "تفسير غياب"):
            self.build()
        self.assertFalse(self.out.exists())

    def test_repaired_tail_declaration_removed_only_for_selected_surah(self):
        self.parent["transform"]["truncatedTail"] = {"63": {"absentFrom": 10},
                                                    "70": {"absentFrom": 40}}
        self.save_inputs()
        self.build()
        result = json.loads(gzip.decompress(self.out.read_bytes()))
        self.assertEqual(result["transform"]["truncatedTail"], {"70": {"absentFrom": 40}})

    def test_restored_tail_has_no_current_gap_claim_and_keeps_exact_parent_history(self):
        self.parent["entries"] = [e for e in self.parent["entries"]
                                  if e["ayahId"] not in ("63:10", "63:11")]
        self.parent["missing"] = {"count": 2, "ids": ["63:10", "63:11"],
                                  "byReason": {"source_truncated": 2}}
        self.parent["transform"] = {
            "op": "declare_gap:63", "reasonCode": "SOURCE_TRUNCATED",
            "reasonUser": "تسجيل هذه السورة ينتهي قبل آخر آيتين.",
            "reason": "شاهد المصدر السابق", "note": "حدود المصدر السابق",
            "droppedEntries": 2, "gapAyahs": 2, "at": 123,
            "truncatedTail": {"63": {"published": 9, "absentFrom": 10, "absentTo": 11,
                                      "reason": "source_truncated"}},
            "provenance": {"olderSurahHistory": {"70": {"source": "earlier"}}},
        }
        self.save_inputs()
        self.build()
        result = json.loads(gzip.decompress(self.out.read_bytes()))
        transform = result["transform"]
        self.assertEqual(result["missing"], {"count": 0, "ids": [], "byReason": {}})
        for field in ("reasonCode", "reasonUser", "droppedEntries", "gapAyahs"):
            self.assertNotIn(field, transform)
        self.assertEqual(transform["truncatedTail"], {})
        self.assertEqual(transform["addedEntries"], 2)
        self.assertEqual(transform["removedEntries"], 0)
        self.assertEqual(transform["provenance"], {
            "kind": "historical-parent-transform", "parentSha256": self.parent_sha,
            "parentKey": "timings/hafs/example.jz", "parentTransform": self.parent["transform"],
        })
        self.assertEqual(self.parent_path.read_bytes(), self.parent_blob)

    def test_other_surah_declarations_and_history_survive_metadata_repair(self):
        self.parent["transform"] = {
            "op": "declare_gap:63,70", "reasonCode": "SOURCE_TRUNCATED",
            "reasonUser": "نقص معلن في التسجيلات السابقة.", "droppedEntries": 7, "gapAyahs": 7,
            "truncatedTail": {"63": {"absentFrom": 10}, "70": {"absentFrom": 40}},
            "dropSurah": [110], "customBySurah": {"80": {"evidence": "سجل قديم"}},
        }
        candidate = copy.deepcopy(self.parent)
        before = copy.deepcopy(self.parent)
        transform = B.repaired_transform(self.parent, candidate, 63, self.parent_sha,
                                         "timings/hafs/example.jz")
        self.assertEqual(transform["truncatedTail"], {"70": {"absentFrom": 40}})
        for field in ("reasonCode", "reasonUser", "dropSurah", "customBySurah"):
            self.assertEqual(transform[field], self.parent["transform"][field])
        self.assertEqual(transform["provenance"]["parentTransform"], self.parent["transform"])
        for field in ("droppedEntries", "gapAyahs"):
            self.assertNotIn(field, transform)
        transform["provenance"]["parentTransform"]["customBySurah"]["80"]["evidence"] = "تغيير الاختبار"
        transform["truncatedTail"]["70"]["absentFrom"] = 42
        self.assertEqual(self.parent, before)
        self.assertEqual(candidate, before)

    def test_unrelated_reason_is_not_removed_with_repaired_tail(self):
        self.parent["transform"].update(reasonCode="OTHER_REASON", reasonUser="بيان آخر")
        candidate = copy.deepcopy(self.parent)
        transform = B.repaired_transform(self.parent, candidate, 63, self.parent_sha,
                                         "timings/hafs/example.jz")
        self.assertEqual(transform["reasonCode"], "OTHER_REASON")
        self.assertEqual(transform["reasonUser"], "بيان آخر")

    def test_low_count_recomputed_without_changing_low_confidence_or_approximate_starts(self):
        self.parent["lowCount"] = 0
        for row, conf in ((self.aligned["entries"][0], .3), (self.aligned["entries"][-1], .4)):
            row.update(conf=conf, snapped=False)
        self.save_inputs()
        self.build()
        result = json.loads(gzip.decompress(self.out.read_bytes()))
        self.assertEqual(result["lowCount"], 2)
        low = [e for e in result["entries"] if e["confBand"] == "LOW"]
        self.assertEqual([(e["ayahId"], e["conf"], e["startApprox"]) for e in low],
                         [("63:1", .3, True), ("63:11", .4, True)])

    def test_low_count_keeps_other_surah_low_entries_unchanged(self):
        self.parent["lowCount"] = 1
        self.parent["entries"][0].update(conf=.4, confBand="LOW", startApprox=True)
        self.aligned["entries"][0].update(conf=.3, snapped=False)
        self.save_inputs()
        self.build()
        result = json.loads(gzip.decompress(self.out.read_bytes()))
        self.assertEqual(result["lowCount"], 2)
        self.assertEqual(result["entries"][0], self.parent["entries"][0])


if __name__ == "__main__":
    unittest.main()
