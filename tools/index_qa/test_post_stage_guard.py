"""Pure byte/provenance guards; no clients, credentials, model, or network."""
import copy
import gzip
import hashlib
import json
import unittest

from tools.index_qa import post_stage_guard as G


TARGET = "timings/hafs/peshawa.jz"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def entries_digest(entries):
    return digest(json.dumps(entries, ensure_ascii=False, sort_keys=True,
                             separators=(",", ":")).encode("utf-8"))


def compressed(document, mtime=0):
    return gzip.compress(json.dumps(document, ensure_ascii=False).encode("utf-8"), mtime=mtime)


class PostStageBindingTest(unittest.TestCase):
    def setUp(self):
        self.parent = {"riwaya": "hafs", "reciterId": "peshawa",
                       "entries": [{"ayahId": "63:1", "startMs": 1000, "endMs": 5000},
                                   {"ayahId": "63:2", "startMs": 5000, "endMs": 9000}],
                       "futureMetadata": {"preserved": "نعم"}}
        self.candidate = copy.deepcopy(self.parent)
        self.candidate["entries"][0]["startMs"] = 1200

    def args(self, *, candidate=None, parent=None, mutate_tx=None):
        parent = copy.deepcopy(self.parent if parent is None else parent)
        candidate = copy.deepcopy(self.candidate if candidate is None else candidate)
        parent_blob = compressed(parent)
        parent_sha = digest(parent_blob)
        candidate["transform"] = {
            "op": "ctc_heardmap_splice:63", "fromKey": TARGET, "fromSha256": parent_sha,
            "qaDispatch": {"mode": "manual-free-only", "parentSha256": parent_sha},
            "entriesSha256": entries_digest(candidate["entries"]),
            "parentEntriesSha256": entries_digest(parent["entries"])}
        if mutate_tx:
            mutate_tx(candidate)
        blob = compressed(candidate)
        sha = digest(blob)
        key = f"timings-staging/hafs/peshawa.{sha[:8]}.jz"
        return [key, sha, parent_sha, blob, parent_blob]

    def test_complete_binding_preserves_documents_and_unknown_metadata(self):
        args = self.args()
        candidate, parent = G.validate_binding(*args)
        self.assertEqual(candidate, json.loads(gzip.decompress(args[3])))
        self.assertEqual(parent, self.parent)
        self.assertEqual(candidate["futureMetadata"], self.candidate["futureMetadata"])
        self.assertEqual(G.parent_key(args[0]), TARGET)

    def test_both_hashes_must_be_full_lowercase_sha256(self):
        for position in (1, 2):
            original = self.args()[position]
            for bad in (original[:8], original[:63], original + "0", original.upper(),
                        "g" * 64, "", None):
                with self.subTest(position=position, bad=bad):
                    args = self.args()
                    args[position] = bad
                    with self.assertRaisesRegex(ValueError, "كامل بصمتي"):
                        G.validate_binding(*args)

    def test_matching_prefix_does_not_substitute_for_exact_candidate_sha(self):
        args = self.args()
        args[1] = args[1][:-1] + ("0" if args[1][-1] != "0" else "1")
        with self.assertRaisesRegex(ValueError, "بايتات المرشح"):
            G.validate_binding(*args)

    def test_parent_hash_is_checked_in_full_even_when_prefix_matches(self):
        args = self.args()
        args[2] = args[2][:-1] + ("0" if args[2][-1] != "0" else "1")
        with self.assertRaisesRegex(ValueError, "تغير الأصل"):
            G.validate_binding(*args)

    def test_same_json_recompressed_with_different_gzip_header_is_different_object(self):
        for position in (3, 4):
            with self.subTest(position=position):
                args = self.args()
                original = args[position]
                document = json.loads(gzip.decompress(original))
                args[position] = compressed(document, mtime=123)
                self.assertNotEqual(original, args[position])
                with self.assertRaises(ValueError):
                    G.validate_binding(*args)

    def test_key_requires_staging_namespace_exact_suffix_and_safe_identity(self):
        for key in ("timings/hafs/peshawa.00000000.jz",
                    "timings-staging/hafs/peshawa.0000.jz",
                    "timings-staging/hafs/../peshawa.00000000.jz",
                    "timings-staging/hafs/peshawa.00000000.jz/extra"):
            with self.subTest(key=key):
                args = self.args()
                args[0] = key
                with self.assertRaisesRegex(ValueError, "مفتاح staging"):
                    G.validate_binding(*args)
        args = self.args()
        wrong = "0" if args[1][0] != "0" else "1"
        args[0] = f"timings-staging/hafs/peshawa.{wrong + args[1][1:8]}.jz"
        with self.assertRaisesRegex(ValueError, "لاحقة المفتاح"):
            G.validate_binding(*args)

    def test_candidate_and_parent_identity_must_both_match_key(self):
        for which in ("candidate", "parent"):
            for field, value in (("reciterId", "other"), ("riwaya", "warsh")):
                with self.subTest(which=which, field=field):
                    document = copy.deepcopy(getattr(self, which))
                    document[field] = value
                    with self.assertRaisesRegex(ValueError, "هوية المرشح أو الأصل"):
                        G.validate_binding(*self.args(**{which: document}))

    def test_parent_provenance_must_reference_exact_published_key_and_sha(self):
        for field, value in (("fromKey", "timings/hafs/other.jz"),
                             ("fromKey", "timings-staging/hafs/peshawa.12345678.jz"),
                             ("fromSha256", "f" * 64), ("fromSha256", "12345678")):
            with self.subTest(field=field, value=value):
                with self.assertRaisesRegex(ValueError, "نسب التحويل"):
                    G.validate_binding(*self.args(mutate_tx=lambda doc:
                                                 doc["transform"].update({field: value})))
        for value in (None, "ctc_heardmap_splice:63", []):
            with self.subTest(transform=value), self.assertRaisesRegex(ValueError, "نسب التحويل"):
                G.validate_binding(*self.args(mutate_tx=lambda doc: doc.update(transform=value)))

    def test_manual_dispatch_must_be_explicit_and_bound_to_parent(self):
        values = (None, True, {}, {"mode": "auto", "parentSha256": "f" * 64},
                  {"mode": "manual-free-only"},
                  {"mode": "manual-free-only", "parentSha256": "f" * 64})
        for value in values:
            with self.subTest(policy=value), self.assertRaisesRegex(ValueError, "الفحص اليدوي"):
                G.validate_binding(*self.args(mutate_tx=lambda doc:
                                             doc["transform"].update(qaDispatch=value)))
        def legacy_flag(doc):
            doc["transform"].pop("qaDispatch")
            doc["transform"]["manualQaOnly"] = True
        with self.assertRaisesRegex(ValueError, "الفحص اليدوي"):
            G.validate_binding(*self.args(mutate_tx=legacy_flag))

    def test_both_entry_digests_must_match_measured_documents(self):
        for field in ("entriesSha256", "parentEntriesSha256"):
            for value in (None, "e" * 64):
                with self.subTest(field=field, value=value):
                    with self.assertRaisesRegex(ValueError, "بصمات مداخل"):
                        G.validate_binding(*self.args(mutate_tx=lambda doc:
                                                     doc["transform"].update({field: value})))
        def stale_digest(doc):
            doc["entries"][0]["startMs"] += 1
        with self.assertRaisesRegex(ValueError, "بصمات مداخل"):
            G.validate_binding(*self.args(mutate_tx=stale_digest))

    def test_duplicate_ids_rejected_even_after_all_hashes_are_recomputed(self):
        for which in ("candidate", "parent"):
            with self.subTest(which=which):
                document = copy.deepcopy(getattr(self, which))
                document["entries"].append(copy.deepcopy(document["entries"][0]))
                with self.assertRaisesRegex(ValueError, "معرفات آيات مكررة"):
                    G.validate_binding(*self.args(**{which: document}))

    def test_missing_or_replaced_published_id_rejected_with_valid_hashes(self):
        for replacement in (None, "63:3"):
            with self.subTest(replacement=replacement):
                candidate = copy.deepcopy(self.candidate)
                if replacement is None:
                    candidate["entries"].pop()
                else:
                    candidate["entries"][-1]["ayahId"] = replacement
                with self.assertRaisesRegex(ValueError, "يفقد مداخل منشورة"):
                    G.validate_binding(*self.args(candidate=candidate))

    def test_new_ids_can_be_added_without_losing_published_entries(self):
        candidate = copy.deepcopy(self.candidate)
        candidate["entries"].append({"ayahId": "63:3", "startMs": 9000, "endMs": 12000})
        bound, parent = G.validate_binding(*self.args(candidate=candidate))
        self.assertEqual(len(bound["entries"]), 3)
        self.assertEqual(len(parent["entries"]), 2)


if __name__ == "__main__":
    unittest.main()
