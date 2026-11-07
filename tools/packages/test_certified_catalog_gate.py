#!/usr/bin/env python3
from __future__ import annotations
import unittest
from tools.packages.certified_catalog_gate import certified_only
from tools.packages.certified_catalog_gate import id_diff
from tools.packages.certified_catalog_gate import declared_removal
import gzip
import hashlib
import json

SHA = "a" * 64


def pkg(name="ok", certified=True, coverage=0.99, sha=SHA, sha8="aaaaaaaa"):
    return {"id": "timings.hafs." + name, "kind": "timing_index",
            "files": [{"key": "timings/hafs/" + name + ".jz", "sha256": sha}],
            "quality": {"ayahCertified": certified, "ayahCoverage": coverage,
                        "sha8": sha8}}


def snapshot(*names, coverage=0.99, sha=SHA, rejected=False):
    return {"schema": 1, "certifier": "certify_catalog-1.2",
            "catalogSha256": "c" * 64, "indexes": {
        "hafs/" + name: {"sha256": sha, "coverage": coverage,
                          "rejected": rejected} for name in names
    }}


class GateTest(unittest.TestCase):
    def test_keeps_only_certified_timing_and_preserves_extras(self):
        doc = {"packages": [pkg(), pkg("no", False),
                            {"id": "model.x", "kind": "model", "files": []}],
               "failures": [], "rejected": []}
        out, stat = certified_only(doc, 1, snapshot("ok"))
        self.assertEqual([p["id"] for p in out["packages"]],
                         ["timings.hafs.ok", "model.x"])
        self.assertEqual(stat["timingCertified"], 1)
        self.assertEqual(stat["timingDroppedUncertified"], 1)
        self.assertEqual(out["rejected"][-1]["reason"],
                         "NOT_IN_CERTIFICATE_SNAPSHOT")

    def test_transient_build_failure_blocks_whole_catalog(self):
        with self.assertRaisesRegex(ValueError, "فشلاً"):
            certified_only({"packages": [pkg()], "failures": [{"key": "x"}]},
                           certificate_snapshot=snapshot("ok"))

    def test_certified_sha_mismatch_is_tool_failure_not_quality_rejection(self):
        with self.assertRaisesRegex(ValueError, "sha8"):
            certified_only({"packages": [pkg(sha8="bbbbbbbb")], "failures": []},
                           certificate_snapshot=snapshot("ok"))

    def test_conservative_floor_blocks_regression(self):
        with self.assertRaisesRegex(ValueError, "الحد المحافظ"):
            certified_only({"packages": [pkg()], "failures": []}, 2, snapshot("ok"))

    def test_coverage_rejects_bool_nan_inf_and_out_of_range(self):
        for value in (True, False, float("nan"), float("inf"),
                      float("-inf"), 0.8999, 1.0001):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "تغطية"):
                certified_only({"packages": [pkg(coverage=value)], "failures": []},
                               certificate_snapshot=snapshot("ok", coverage=value))

    def test_full_sha_certificate_is_required(self):
        with self.assertRaisesRegex(ValueError, "SHA-256 الكاملة"):
            certified_only({"packages": [pkg()], "failures": []},
                           certificate_snapshot=snapshot("ok", sha="b" * 64))

    def test_snapshot_must_name_certifier_and_catalog_full_sha(self):
        bad = snapshot("ok")
        bad["catalogSha256"] = "c" * 8
        with self.assertRaisesRegex(ValueError, "بصمة كتالوج"):
            certified_only({"packages": [pkg()], "failures": []},
                           certificate_snapshot=bad)

    def test_rejected_certificate_is_blocked(self):
        with self.assertRaisesRegex(ValueError, "rejected=false"):
            certified_only({"packages": [pkg()], "failures": []},
                           certificate_snapshot=snapshot("ok", rejected=True))

    def test_snapshot_member_missing_from_candidate_blocks_whole_catalog(self):
        with self.assertRaisesRegex(ValueError, "أسقط"):
            certified_only({"packages": [pkg()], "failures": []},
                           certificate_snapshot=snapshot("ok", "missing"))

    def test_id_diff_lists_ids_and_blocks_removal(self):
        before = {"packages": [pkg("old"), pkg("uncert", False)]}
        after = {"packages": [pkg("old"), pkg("new")]}
        report = id_diff(before, after)
        self.assertEqual(report["beforeCertified"], ["hafs/old"])
        self.assertEqual(report["afterCertified"], ["hafs/new", "hafs/old"])
        self.assertEqual(report["added"], ["hafs/new"])
        self.assertEqual(report["removed"], [])
        with self.assertRaisesRegex(ValueError, "أسقط قارئاً"):
            id_diff(before, {"packages": [pkg("new")]})


DROPPED = [12, 22]
REASON_USER = "توقيتُ هذه السورة لهذا القارئ قيد الإصلاح، فحُجب مؤقّتاً."


def index_doc(drop=DROPPED, present_extra=(), code="OTHER", user=REASON_USER, op=None, rid="old"):
    present = [s for s in range(1, 115) if s not in drop] + list(present_extra)
    tr = {"op": op if op is not None else "drop_surah:" + ",".join(map(str, drop))}
    if code is not None:
        tr["reasonCode"] = code
    if user is not None:
        tr["reasonUser"] = user
    return {"reciterId": rid, "riwaya": "hafs", "transform": tr,
            "entries": [{"ayahId": f"{s}:1"} for s in present]}


def blob(doc):
    return gzip.compress(json.dumps(doc, ensure_ascii=False).encode("utf-8"), mtime=0)


def approvals_for(b, surahs=DROPPED, rid="old"):
    sha8 = hashlib.sha256(b).hexdigest()[:8]
    return [{"key": f"timings-staging/hafs/{rid}.{sha8}.jz", "surahs": list(surahs)}]


class DeclaredRemovalTest(unittest.TestCase):
    """باب الإسقاط المعلن (‏إذن المالك 2026-11-07 11:09Z): الشروط الثلاثة مجتمعة، وغيابُ أيّها يُبقي الردّ."""

    before = {"packages": [pkg("old"), pkg("keep")]}
    after = {"packages": [pkg("keep")]}

    def ok(self, doc=None):
        b = blob(doc or index_doc())
        return b, declared_removal("hafs/old", b, approvals_for(b))

    def test_declared_and_approved_removal_passes_and_is_recorded(self):
        b, rec = self.ok()
        self.assertEqual(rec["declaredSurahs"], DROPPED)
        self.assertEqual(rec["sha256"], hashlib.sha256(b).hexdigest())
        report = id_diff(self.before, self.after, {"hafs/old": rec})
        self.assertEqual(report["removed"], ["hafs/old"])
        self.assertEqual(report["removedDeclared"], [rec])

    def test_without_declaration_removal_still_blocked(self):
        with self.assertRaisesRegex(ValueError, "أسقط قارئاً"):
            id_diff(self.before, self.after)
        with self.assertRaisesRegex(ValueError, "أسقط قارئاً"):
            id_diff(self.before, {"packages": []}, {"hafs/old": self.ok()[1]})  # keep لم يُعلن

    def test_declaration_for_reciter_not_removed_refused(self):
        with self.assertRaisesRegex(ValueError, "لم يُسقَط"):
            id_diff(self.before, self.before, {"hafs/old": self.ok()[1]})

    def test_missing_approval_row_refused(self):
        b = blob(index_doc())
        with self.assertRaisesRegex(ValueError, "لا صفَّ موافقة"):
            declared_removal("hafs/old", b, [])

    def test_approval_for_other_sha_refused(self):
        b = blob(index_doc())
        other = blob(index_doc(user=REASON_USER + "!"))
        with self.assertRaisesRegex(ValueError, "لا صفَّ موافقة"):
            declared_removal("hafs/old", b, approvals_for(other))

    def test_approval_for_other_reciter_refused(self):
        b = blob(index_doc())
        with self.assertRaisesRegex(ValueError, "لا صفَّ موافقة"):
            declared_removal("hafs/old", b, approvals_for(b, rid="keep"))

    def test_approval_surahs_mismatch_refused(self):
        b = blob(index_doc())
        for surahs in ([12], [12, 22, 40], []):
            with self.assertRaisesRegex(ValueError, "لا يطابق"):
                declared_removal("hafs/old", b, approvals_for(b, surahs))

    def test_missing_reason_code_or_user_refused(self):
        for kw in ({"code": None}, {"code": "  "}, {"user": None}, {"user": ""}):
            b = blob(index_doc(**kw))
            with self.assertRaisesRegex(ValueError, "بلا reason"):
                declared_removal("hafs/old", b, approvals_for(b))

    def test_without_drop_surah_op_refused(self):
        for op in ("", "ctc_splice:12,22", "drop_surah:", "x drop_surah:12,22"):
            b = blob(index_doc(op=op))
            with self.assertRaisesRegex(ValueError, "لا إعلانَ drop_surah"):
                declared_removal("hafs/old", b, approvals_for(b))

    def test_silent_absent_surah_refused(self):
        doc = index_doc()
        doc["entries"] = [e for e in doc["entries"] if e["ayahId"] != "40:1"]
        b = blob(doc)
        with self.assertRaisesRegex(ValueError, "بلا إعلان"):
            declared_removal("hafs/old", b, approvals_for(b))

    def test_declared_but_present_surah_refused(self):
        b = blob(index_doc(present_extra=(22,)))
        with self.assertRaisesRegex(ValueError, "وهي حاضرة"):
            declared_removal("hafs/old", b, approvals_for(b))

    def test_index_of_other_reciter_or_unreadable_refused(self):
        b = blob(index_doc(rid="keep"))
        with self.assertRaisesRegex(ValueError, "قارئاً آخر"):
            declared_removal("hafs/old", b, approvals_for(b))
        with self.assertRaisesRegex(ValueError, "لا يُقرأ"):
            declared_removal("hafs/old", b"not gzip", [])
        with self.assertRaisesRegex(ValueError, "غير صالح"):
            declared_removal("../old", blob(index_doc()), [])

    def test_certified_only_unchanged_by_door(self):
        """الباب لا يُدخل الفهرس المعلن في الحزم ولا يمسّ أرضيّة التغطية."""
        doc = {"packages": [pkg("old", False, 0.87), pkg("keep")], "failures": [], "rejected": []}
        out, stat = certified_only(doc, 1, snapshot("keep"))
        self.assertEqual([p["id"] for p in out["packages"]], ["timings.hafs.keep"])
        with self.assertRaisesRegex(ValueError, "خارج"):
            certified_only({"packages": [pkg("old", True, 0.87)], "failures": []}, 0,
                           snapshot("old", coverage=0.87))


if __name__ == "__main__":
    unittest.main()
