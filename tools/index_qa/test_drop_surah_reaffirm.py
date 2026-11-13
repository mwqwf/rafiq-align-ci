#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""`drop_surah.py --reaffirm`: إعادةُ كتابة إعلاناتٍ **قائمةٍ** حرفاً بـ`op` صادق، بلا مسّ مدخلٍ ولا إعلانٍ جديد (‏2026-11-13).

    python -m unittest tools.index_qa.test_drop_surah_reaffirm

الحالة (‏akri_qalun.5ab97519): الحيُّ ناتجُ `graft_surahs` فـ`op = graft_surahs:…` والإعلاناتُ (‏4 و10 و37 إسقاطاً و24 ذيلاً)
موروثةٌ في `declarations`/`dropSurah`/`priorOp`؛ و`promote.inherited_drops` لا يورّث حجبَ OTHER إلا عن أصلٍ يبدأ `op` فيه بـ
`drop_surah:` ⇒ كلُّ مرشّحٍ فوقه يُردّ. والعيّنةُ هنا تُبنى من `testdata/akri_qalun.b99e3573.min.jz` (‏المنشور قبل حجب 10 و37)
بحذف مداخل 10 و37 وكتابةِ ترويسةٍ على هيئة ترويسة الحيّ 5ab97519 حرفاً في حقولها الحاكمة، والدليلُ هو ملفُّ المستودع نفسُه
`ops/evidence/tail-drop-akri_qalun-b99e3573.json` الذي استند إليه حجبُ 10 و37.

وفي آخره طفراتٌ: يُعطَّل كلُّ شرطٍ موسومٍ في نسخةٍ من المصدر، فيُثبَت أنّ اختبارَ ردّه يسقط بغيابه.
"""
from __future__ import annotations

import copy
import gzip
import hashlib
import io
import json
import re
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import drop_surah                                                # noqa: E402
import promote                                                   # noqa: E402
import stage_transform as st                                     # noqa: E402
from rename_reciter import entries_sha                           # noqa: E402

FIX = HERE / "testdata" / "akri_qalun.b99e3573.min.jz"
KEY = "timings/qalun/akri_qalun.jz"
EVIDENCE = "ops/evidence/tail-drop-akri_qalun-b99e3573.json"
EVIDENCE_OTHER = "ops/evidence/tail-drop-rakbawi_qalun-3d8dc7c9.json"
# نصّا سجلَّي 10 و37 في الحيّ 5ab97519 حرفاً (‏ومنهما رقما شاهدَي Whisper اللذان في ملفّ الدليل).
USER = "توقيت هذه السورة لهذا القارئ قيد الإصلاح، فحُجبت مؤقّتاً حتى لا تُعرض آياتها على صوت غيرها"
REASON = ("ذيلُ السورة في هذا الفهرس مُزاحٌ بدقائق عن صوته: س10: الآية 109 تُسمع عند 2668ث والفهرس يضعها عند 1862ث "
          "(شاهد Whisper 42756669766)؛ س37: الآية 182 تُسمع عند 1414ث والفهرس يضعها عند 1258ث (شاهد Whisper "
          "42756522605)، وخريطةُ السماع توافق الشاهد. تُحجب مؤقّتاً حتى تُعاد محاذاتها.")


def _remove(idx, surahs):
    pfx = tuple(f"{s}:" for s in surahs)
    gone = [e["ayahId"] for e in idx["entries"] if e["ayahId"].startswith(pfx)]
    idx["entries"] = [e for e in idx["entries"] if not e["ayahId"].startswith(pfx)]
    m = idx["missing"]
    m["count"] += len(gone)
    m["byReason"]["source_truncated"] = m["byReason"].get("source_truncated", 0) + len(gone)
    m["ids"] = sorted(m["ids"] + gone, key=lambda a: tuple(map(int, a.split(":"))))


def live_like(mutate=None):
    """فهرسٌ على هيئة الحيّ 5ab97519: مداخلُ b99e3573 ناقصَ 10 و37، وترويسةُ `graft_surahs` تحمل الإعلانات."""
    idx = json.loads(gzip.decompress(FIX.read_bytes()))
    idx.pop("fixtureNote", None)
    tr0 = idx["transform"]
    _remove(idx, (10, 37))
    old = {f: tr0[f] for f in ("reasonCode", "reasonUser", "reason")}
    new = {"reasonCode": "OTHER", "reasonUser": USER, "reason": REASON}
    idx["transform"] = {
        "truncatedTail": tr0["truncatedTail"],
        "declarations": {"4": {"op": "drop_surah", **old}, "24": {"op": "declare_gap", **old},
                         "10": {"op": "drop_surah", **new}, "37": {"op": "drop_surah", **new}},
        "op": "graft_surahs:1,12,13",
        "fromSha256": "143e13dd932467e0610ab3adbf5f60edc83e3bc3eb977f0076d4a1990ba8107a",
        "fromKey": KEY, "droppedEntries": 291,
        "reason": "مرشّحٌ مركّب فوق الحيّ ويورّث إعلاناته",
        "reasonUser": USER, "reasonCode": "OTHER",
        "dropSurah": [4, 10, 37], "priorOp": "drop_surah:4,10,37|declare_gap:24",
        "entriesSha256": entries_sha(idx["entries"]), "by": "graft_surahs",
        "graft": {"surahs": [1, 12, 13], "by": "graft_surahs"},
    }
    if mutate:
        mutate(idx)
    return idx


def _blob(idx):
    return gzip.compress(json.dumps(idx, ensure_ascii=False, separators=(",", ":")).encode(), 9, mtime=0)


def _sha(idx):
    return hashlib.sha256(_blob(idx)).hexdigest()


def run(mod=None, idx=None, surahs=(10, 37), evidence=EVIDENCE, **kw):
    mod = mod or drop_surah
    idx = idx or live_like()
    return mod.reaffirm(idx, _sha(idx), kw.pop("key", KEY), list(surahs), evidence, **kw)


class _Bucket:
    def __init__(self, body):
        self.store = {KEY: body}

    def get_object(self, Bucket, Key):                           # noqa: N803
        return {"Body": io.BytesIO(self.store[Key])}

    def put_object(self, Bucket, Key, Body, ContentType=None):   # noqa: N803
        self.store[Key] = Body

    def head_object(self, Bucket, Key):                          # noqa: N803
        return {"ContentLength": len(self.store[Key])}


def run_main(extra, mod=None, idx=None, yes=True):
    mod = mod or drop_surah
    body = _blob(idx or live_like())
    b = _Bucket(body)
    argv = ["drop_surah.py", "--key", KEY, "--sha", hashlib.sha256(body).hexdigest()[:8], "--surah", "10,37",
            "--reason", REASON, *extra, *(["--yes"] if yes else [])]
    with mock.patch.object(promote, "s3", return_value=(b, "bk")), mock.patch.object(sys, "argv", argv):
        mod.main()
    return b


TAG = r"\[reaffirm:{}\]"


class Accept(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.live = live_like()
        cls.lsha = _sha(cls.live)
        cls.out = drop_surah.reaffirm(cls.live, cls.lsha, KEY, [10, 37], EVIDENCE,
                                      reason=REASON, reason_code="OTHER", reason_user=USER)
        cls.nsha = _sha(cls.out)

    def test_op_is_truthful_and_provenance_kept(self):
        t = self.out["transform"]
        self.assertEqual(t["op"], "drop_surah:4,10,37|declare_gap:24")
        self.assertEqual(t["by"], "drop_surah --reaffirm")
        self.assertEqual(t["priorOp"], "drop_surah:4,10,37|declare_gap:24")
        self.assertEqual((t["fromKey"], t["fromSha256"]), (KEY, self.lsha))
        self.assertEqual(t["reaffirm"]["replacedOp"], "graft_surahs:1,12,13")
        self.assertEqual(t["reaffirm"]["replacedFrom"]["by"], "graft_surahs")
        self.assertEqual(t["graft"], self.live["transform"]["graft"])
        for f in ("dropSurah", "truncatedTail", "reasonCode", "reasonUser", "reason"):
            self.assertEqual(t[f], self.live["transform"][f], f)

    def test_entries_and_declarations_verbatim(self):
        self.assertEqual(self.out["entries"], self.live["entries"])
        t = self.out["transform"]
        self.assertEqual(t["entriesSha256"], entries_sha(self.live["entries"]))
        self.assertEqual(t["entriesSha256"], t["parentEntriesSha256"])
        self.assertEqual(t["entriesSha256"], self.live["transform"]["entriesSha256"])
        self.assertEqual(t["declarations"], self.live["transform"]["declarations"])
        self.assertEqual({k: v for k, v in self.out.items() if k != "transform"},
                         {k: v for k, v in self.live.items() if k != "transform"})
        self.assertEqual((t["droppedEntries"], t["addedEntries"], t["removedEntries"], t["movedEntries"]), (0, 0, 0, 0))

    def test_evidence_recorded_and_linked(self):
        ev = self.out["transform"]["reaffirm"]["evidence"]
        self.assertEqual(ev["path"], EVIDENCE)
        self.assertEqual(ev["sha256"], hashlib.sha256((drop_surah.REPO / EVIDENCE).read_bytes()).hexdigest())
        self.assertTrue(ev["liveSha256"].startswith("b99e3573"))
        self.assertEqual(ev["link"], {"10": "reason-runId", "37": "reason-runId"})

    def test_index_gate_needs_approval_row(self):
        ap = frozenset({4, 10, 37})
        self.assertIsNone(promote.index_gate(self.out, parent=self.live, parent_sha=self.lsha, coded_approved=ap))
        self.assertIsNotNone(promote.index_gate(self.out, parent=self.live, parent_sha=self.lsha))
        self.assertTrue(promote.declared_truncated_tail(self.out, "24")[0])

    def _candidate(self):
        cand = copy.deepcopy(self.out)
        cand["transform"].update(op="ctc_heardmap_splice:106", fromSha256=self.nsha, fromKey=KEY)
        return cand

    def test_candidate_on_top_inherits_with_row(self):
        rows = {f"timings-staging/qalun/akri_qalun.{self.nsha[:8]}.jz": frozenset({4, 10, 37})}
        own = st.published_owner_approved(self.out, self.nsha, rows)
        self.assertEqual(promote.inherited_drops(self._candidate(), self.out, self.nsha, own), ({"4", "10", "37"}, None))
        self.assertIsNone(promote.index_gate(self._candidate(), parent=self.out, parent_sha=self.nsha,
                                             owner_approved=own, coded_approved=own))

    def test_candidate_on_top_rejected_without_row(self):
        own = st.published_owner_approved(self.out, self.nsha, {})
        got, why = promote.inherited_drops(self._candidate(), self.out, self.nsha, own)
        self.assertEqual(got, set())
        self.assertIsNotNone(why)

    def test_same_candidate_over_graft_live_is_rejected(self):
        """الحالُ قبل الإصلاح: المرشّحُ نفسُه فوق الحيّ المطعَّم يُردّ ولو بصفّ موافقة — وهو سببُ هذا الوضع."""
        cand = self._candidate()
        cand["transform"]["fromSha256"] = self.lsha
        rows = {f"timings-staging/qalun/akri_qalun.{self.lsha[:8]}.jz": frozenset({4, 10, 37})}
        own = st.published_owner_approved(self.live, self.lsha, rows)
        self.assertIsNotNone(promote.inherited_drops(cand, self.live, self.lsha, own)[1])

    def test_main_uploads_only_with_yes(self):
        extra = ["--reaffirm", "--evidence", EVIDENCE, "--reason-code", "OTHER", "--reason-user", USER]
        with mock.patch("builtins.print"):
            b = run_main(extra, yes=False)
            self.assertEqual(list(b.store), [KEY])
            b = run_main(extra)
        keys = [k for k in b.store if k.startswith("timings-staging/qalun/akri_qalun.")]
        self.assertEqual(len(keys), 1)
        got = json.loads(gzip.decompress(b.store[keys[0]]))
        self.assertEqual(got["transform"]["op"], "drop_surah:4,10,37|declare_gap:24")
        self.assertEqual(got["entries"], self.live["entries"])


class Reject(unittest.TestCase):
    """كلُّ ردٍّ برسالةٍ موسومةٍ باسم شرطه — والطفراتُ أدناه تُعطّل الشرطَ نفسَه."""

    def assertTag(self, tag, fn):
        with self.assertRaisesRegex(SystemExit, TAG.format(tag)):
            fn()

    # ── السورُ ──
    def test_undeclared_absent_surah(self):
        self.assertTag("not_declared", S_UNDECLARED)

    def test_declare_gap_surah_not_drop(self):
        self.assertTag("not_drop", S_NOT_DROP)

    def test_surah_with_entries(self):
        self.assertTag("has_entries", S_HAS_ENTRIES)

    def test_live_key_only(self):
        self.assertTag("key_live", S_KEY)

    def test_op_already_drop(self):
        self.assertTag("op_already", S_OP_ALREADY)

    def test_fields_disagree(self):
        self.assertTag("fields_disagree", S_FIELDS)
        self.assertTag("fields_disagree", lambda: run(idx=live_like(lambda i: i["transform"].update(
            priorOp="drop_surah:4,10|declare_gap:24"))))

    # ── النصوص ──
    def test_reason_code_mismatch(self):
        self.assertTag("arg_mismatch", S_CODE)

    def test_reason_user_mismatch(self):
        self.assertTag("arg_mismatch", lambda: run(reason_user=USER + "."))

    def test_reason_mismatch(self):
        self.assertTag("arg_mismatch", lambda: run(reason="سببٌ آخر"))

    # ── الدليل ──
    def test_no_evidence(self):
        self.assertTag("no_evidence", S_NO_EVIDENCE)

    def test_evidence_other_reciter(self):
        self.assertTag("evidence_key", S_EV_KEY)

    def test_evidence_missing_file(self):
        self.assertTag("evidence_file", S_EV_FILE)

    def test_evidence_outside_ops_evidence(self):
        self.assertTag("evidence_outside", S_EV_OUTSIDE)

    def test_evidence_not_covering_surah(self):
        """س4 معلَنةٌ إسقاطاً غائبةُ المداخل، لكنّ دليلَ 10 و37 لا يسمّيها ⇒ لا تُعاد بدليلٍ ليس دليلَها."""
        self.assertTag("evidence_surah", S_EV_SURAH)

    def test_flags(self):
        self.assertTag("flags", S_FLAGS)
        with mock.patch("builtins.print"):
            self.assertTag("flags", lambda: run_main(["--evidence", EVIDENCE, "--reason-code", "OTHER",
                                                      "--reason-user", USER, "--declare-absent"]))


def _no10back(i):
    e = next(x for x in json.loads(gzip.decompress(FIX.read_bytes()))["entries"] if x["ayahId"] == "10:1")
    i["entries"].append(e)
    i["missing"]["count"] -= 1
    i["missing"]["ids"].remove("10:1")


S_UNDECLARED = lambda mod=None: run(mod, idx=live_like(lambda i: _remove(i, (5,))), surahs=(5,))      # noqa: E731
S_NOT_DROP = lambda mod=None: run(mod, surahs=(24,))                                                     # noqa: E731
S_HAS_ENTRIES = lambda mod=None: run(mod, idx=live_like(_no10back))                                      # noqa: E731
S_KEY = lambda mod=None: run(mod, key="timings-staging/qalun/akri_qalun.12345678.jz")                    # noqa: E731
S_OP_ALREADY = lambda mod=None: run(mod, idx=live_like(lambda i: i["transform"].update(                  # noqa: E731
    op="drop_surah:4,10,37|declare_gap:24")))
S_FIELDS = lambda mod=None: run(mod, idx=live_like(lambda i: i["transform"].update(dropSurah=[4, 10])))  # noqa: E731
S_CODE = lambda mod=None: run(mod, reason_code="SOURCE_TRUNCATED")                                       # noqa: E731
S_NO_EVIDENCE = lambda mod=None: run(mod, evidence=None)                                                 # noqa: E731
S_EV_KEY = lambda mod=None: run(mod, evidence=EVIDENCE_OTHER)                                            # noqa: E731
S_EV_FILE = lambda mod=None: run(mod, evidence="ops/evidence/no-such-akri-evidence.json")                # noqa: E731
S_EV_OUTSIDE = lambda mod=None: run(mod, evidence="ops/OWNER_DROP_APPROVALS.json")                       # noqa: E731
S_EV_SURAH = lambda mod=None: run(mod, surahs=(4, 10, 37))                                               # noqa: E731
S_FLAGS = lambda mod=None: run_main(["--evidence", EVIDENCE], mod=mod)                                   # noqa: E731


def mutant(tag):
    """نسخةٌ من `drop_surah` عُطّل فيها كلُّ ردٍّ موسومٍ بـ`tag` (‏الشرطُ يبقى، والردُّ صار لا شيء)."""
    src = (HERE / "drop_surah.py").read_text(encoding="utf-8")
    n = src.count(f'_reject("{tag}"')
    src = src.replace(f'_reject("{tag}"', f'_noop("{tag}"')
    if tag == "flags":
        n = len(re.findall(r'raise SystemExit\("⛔ \[reaffirm:flags\]', src))
        src = re.sub(r'raise SystemExit\(("⛔ \[reaffirm:flags\])', r'_noop(\1', src)
    assert n, tag
    src = src.replace("\ndef _reject(", "\ndef _noop(*a, **k):\n    return None\n\n\ndef _reject(", 1)
    mod = types.ModuleType(f"drop_surah_mut_{tag}")
    mod.__file__ = str(HERE / "drop_surah.py")
    exec(compile(src, mod.__file__, "exec"), mod.__dict__)                # noqa: S102
    return mod


class Mutations(unittest.TestCase):
    """إزالةُ كلّ شرطٍ تُسقط اختبارَ ردّه: السيناريو نفسُه لا يُخرج الوسمَ في النسخة المطفَّرة."""

    CASES = [("not_declared", S_UNDECLARED), ("not_drop", S_NOT_DROP), ("has_entries", S_HAS_ENTRIES),
             ("key_live", S_KEY), ("op_already", S_OP_ALREADY), ("fields_disagree", S_FIELDS),
             ("arg_mismatch", S_CODE), ("no_evidence", S_NO_EVIDENCE), ("evidence_key", S_EV_KEY),
             ("evidence_file", S_EV_FILE), ("evidence_outside", S_EV_OUTSIDE), ("evidence_surah", S_EV_SURAH),
             ("flags", S_FLAGS)]

    def test_each_guard_is_load_bearing(self):
        for tag, scenario in self.CASES:
            with self.subTest(tag=tag):
                with self.assertRaisesRegex(SystemExit, TAG.format(tag)):
                    scenario()                                            # الأصلُ يردّ بالوسم
                mod = mutant(tag)
                try:
                    with mock.patch("builtins.print"):
                        scenario(mod)
                except SystemExit as e:
                    self.assertNotRegex(str(e), TAG.format(tag))
                except Exception:                                         # noqa: BLE001,S110
                    pass                                                  # انهارت بغير الوسم ⇒ اختبارُه يسقط

    def test_evidence_guards_are_layered(self):
        """بلا شرط مفتاح الدليل يبقى شرطُ السور حاجزاً ثانياً (‏دليلُ rakbawi لا يسمّي 10 ولا 37) — طبقتان لا واحدة."""
        mod = mutant("evidence_key")
        with self.assertRaises(SystemExit) as cm:
            S_EV_KEY(mod)
        self.assertRegex(str(cm.exception), TAG.format("evidence_surah"))


if __name__ == "__main__":
    unittest.main()
