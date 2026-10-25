#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""عقدُ إعادة استعمال أحكام الإحصاء على مستوى السورة (‏`census_cache.py` + `run.audit`).

كلُّ شيءٍ هنا بمحاكاةٍ: دلوٌ في الذاكرة، وتفريغٌ مزيَّف يعدّ ما سُمع، ونصٌّ اصطناعيٌّ ليس قرآناً.
⛔ المحاكاةُ تكشف *من سُمع ومن لم يُسمع*؛ أمّا الحكمُ فيمرّ على `R.judge` و`promote.census_gate`
الحقيقيّتين بلا أيّ استبدال.
"""
from __future__ import annotations

import copy
import gzip
import hashlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent))
import census_cache as CC  # noqa: E402
import promote as P  # noqa: E402
import run as R  # noqa: E402

KEY = "timings-staging/hafs/tst.abcd1234.jz"
SHA = "a" * 64
SURAHS = {2: 4, 3: 3}                       # سورة ⇒ عدد الآيات الموضوعة في الفهرس
_AR = "ابتثجحخدذرزسشصضطظعغفقكلمنهوي"


def word(n: int) -> str:
    """كلمةٌ اصطناعيةٌ عربيةُ الحروف من العدد — تختلف هياكلُها فلا يلتبس مرجعٌ بسابقته."""
    out, n = "", n + 1
    while n:
        out += _AR[n % len(_AR)]
        n //= len(_AR)
    return (out * 3)[:6]


def make_text():
    return [" ".join(word(i * 5 + k) for k in range(4)) for i in range(6236)]


class FakeS3:
    """دلوٌ في الذاكرة بواجهة boto3 التي يستعملها الكاش و`census_gate`."""

    def __init__(self):
        self.objs = {}
        self.gets = []
        self.puts = []

    def get_object(self, Bucket, Key):                          # noqa: N803
        self.gets.append(Key)
        if Key not in self.objs:
            raise KeyError(Key)
        return {"Body": io.BytesIO(self.objs[Key])}

    def put_object(self, Bucket, Key, Body, **kw):              # noqa: N803
        self.puts.append(Key)
        self.objs[Key] = Body


def static(**over):
    s = {"codeSha": "code-1", "modelSha": "model-1",
         "facts": {"ffmpeg": "ffmpeg 6", "pywhispercpp": "1.0", "numpy": "2", "soundfile": "0.12"},
         "env": {"QA_NO_RANGE": None}}
    s.update(over)
    return s


class Base(unittest.TestCase):
    def setUp(self):
        self.text = make_text()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.assets = Path(self.tmp.name)
        (self.assets / "text_hafs.jz").write_bytes(
            gzip.compress(json.dumps(self.text, ensure_ascii=False).encode("utf-8")))
        self.s3 = FakeS3()
        self.heard_jobs = []            # ‏كلُّ مهمّة سُمعت عبر كلّ التشغيلات
        self.sever = set()              # ‏آياتٌ يُسمع فيها مطلعٌ ساقط (‏جسيم)
        self.failing = set()               # ‏معرّفاتُ نوافذ تفشل (‏مثل "F|2:1")
        self.mute = set()               # ‏آياتٌ يُسمع فيها غيرُ ما يُطابق (‏غير حاسم)
        self.idx = self.build_index()

    # ── الفهرس
    def build_index(self):
        entries, st = [], 1000
        for s, n in SURAHS.items():
            for a in range(1, n + 1):
                entries.append({"ayahId": f"{s}:{a}", "startMs": st, "endMs": st + 4000,
                                "fileRef": f"https://example.org/{s:03d}.mp3",
                                "confBand": "HIGH", "startApprox": False})
                st += 4000
            st = 1000
        return {"riwaya": "hafs", "reciterId": "tst", "engineVersion": "whisper",
                "engineBySurah": {"2": "ctc", "3": "ctc"},
                "audioSha256": [f"{i:064x}" for i in range(114)], "entries": entries}

    # ── محاكاة التفريغ: تعدّ ما يُسمع وتردّ نصَّ الآية (‏أو ما يُراد)
    def fake_local_run(self, jobs, _h=None, _t=None):
        res, errs = {}, {}
        for j in jobs:
            self.heard_jobs.append(j["id"])
            kind, _, aid = j["id"].partition("|")
            if j["id"] in self.failing:
                errs[j["id"]] = "RuntimeError: محاكاة"
                continue
            s, a = map(int, aid.split(":")) if ":" in aid else (0, 0)
            ref = self.text[R.flat(s, a)] if s else ""
            if aid in self.mute:
                res[j["id"]] = {"text": "كلامٌ لا يطابق شيئاً مطلقاً", "ms": 0}
            elif aid in self.sever:
                w = ref.split()
                # ‏الأمامية تسقط كلمتين من المطلع، والحاسمة (‏D) تحمل ما سقط ⇒ جسيم
                res[j["id"]] = {"text": " ".join(w[2:]) if kind in "FL" else ref, "ms": 0}
            else:
                res[j["id"]] = {"text": "" if kind == "D" else ref, "ms": 0}
        return res, errs

    # ── تشغيل audit بمحاكاة الدلو والفهرس
    def run_audit(self, idx=None, cache="default", **env):
        idx = self.idx if idx is None else idx
        if cache == "default":
            cache = CC.CensusCache(self.s3, "b", static(), write_ok=True, run_id="111")
        args = SimpleNamespace(struct_only=False, allow_unmarked=True, local=True, rejudge=False,
                               clusters=20, per_cluster=10, band=None, refined=None, long_seg=False,
                               batch=48, threads=1, host=None, expect_sha=None)
        with mock.patch.object(R, "fetch_index", lambda k, w=None: (copy.deepcopy(idx), SHA)), \
                mock.patch.object(R, "structural", lambda *a, **k: ([], [], {})), \
                mock.patch.object(R, "_src_mtime", lambda k: None), \
                mock.patch.object(R, "ASSETS", self.assets), \
                mock.patch.object(R, "local_run", self.fake_local_run), \
                mock.patch.object(R, "CENSUS_CACHE", cache), \
                mock.patch.dict(os.environ, {"QA_CENSUS_SURAHS": ",".join(map(str, SURAHS)),
                                             "QA_SEED_SALT": "census", **env}):
            rep = R.audit(KEY, args)
        return rep, cache

    def audit_and_flush(self, **kw):
        rep, cache = self.run_audit(**kw)
        if cache is not None:
            cache.flush(index_key=KEY, index_sha=SHA)
        return rep, cache

    def n_heard(self, surah):
        return sum(1 for i in self.heard_jobs if i.partition("|")[2].startswith(f"{surah}:"))

    def strip(self, rep):
        """التقريرُ بلا علامات الإعادة وبلا الزمن — للمقارنة بالسماع الكامل."""
        r = copy.deepcopy(rep)
        r.pop("censusReuse", None)
        r.pop("ts", None)
        for row in r["sample"]["rows"]:
            row.pop("reusedFrom", None)
        return r


class ReuseTest(Base):
    def test_identical_surahs_are_reused_and_not_heard(self):
        rep1, _ = self.audit_and_flush()
        first = len(self.heard_jobs)
        self.assertGreater(first, 0)
        self.assertEqual(len(self.s3.puts), len(SURAHS))            # كاشٌ لكلّ سورةٍ سليمة
        self.assertTrue(all(k.startswith("state-census-cache/hafs/tst/") for k in self.s3.puts))
        rep2, _ = self.audit_and_flush()
        self.assertEqual(len(self.heard_jobs), first)               # ‏لم يُسمع شيءٌ في الثانية
        self.assertEqual(rep2["censusReuse"]["reusedSurahs"], [2, 3])
        # ‏الصفوفُ والإحصاءاتُ الناتجة هي ما أعطاه السماعُ الكامل نفسُه
        self.assertEqual(self.strip(rep1), self.strip(rep2))
        for row in rep2["sample"]["rows"]:
            mark = row["reusedFrom"]
            self.assertEqual(mark["runId"], "111")
            self.assertEqual(len(mark["cacheKey"]), 64)
            self.assertIn(mark["cacheKey"], mark["object"])

    def test_change_in_one_surah_hears_only_that_surah(self):
        self.audit_and_flush()
        before = (self.n_heard(2), self.n_heard(3))
        idx = copy.deepcopy(self.idx)
        next(e for e in idx["entries"] if e["ayahId"] == "3:2")["endMs"] += 1
        rep, _ = self.run_audit(idx=idx)
        self.assertEqual(rep["censusReuse"]["reusedSurahs"], [2])
        self.assertEqual(self.n_heard(2), before[0])               # ‏2 لم تُسمع ثانيةً
        self.assertGreater(self.n_heard(3), before[1])             # ‏3 سُمعت كاملةً

    def test_any_entry_field_change_invalidates(self):
        self.audit_and_flush()
        for field, val in (("startMs", 1001), ("endMs", 5001), ("fileRef", "https://example.org/x.mp3"),
                           ("confBand", "MED"), ("startApprox", True), ("extra", 1)):
            with self.subTest(field=field):
                idx = copy.deepcopy(self.idx)
                next(e for e in idx["entries"] if e["ayahId"] == "2:3")[field] = val
                rep, _ = self.run_audit(idx=idx)
                self.assertNotIn(2, rep["censusReuse"]["reusedSurahs"])
                self.assertIn(3, rep["censusReuse"]["reusedSurahs"])

    def test_audio_sha_change_invalidates_only_its_surah(self):
        self.audit_and_flush()
        idx = copy.deepcopy(self.idx)
        idx["audioSha256"][1] = "f" * 64                           # سورة 2
        rep, _ = self.run_audit(idx=idx)
        self.assertEqual(rep["censusReuse"]["reusedSurahs"], [3])

    def test_missing_audio_sha_is_never_cached(self):
        idx = copy.deepcopy(self.idx)
        idx["audioSha256"][1] = None
        self.audit_and_flush(idx=idx)
        self.assertEqual(len(self.s3.puts), 1)                     # ‏سورة 3 وحدها
        rep, _ = self.run_audit(idx=idx)
        self.assertEqual(rep["censusReuse"]["reusedSurahs"], [3])
        self.assertIn("2", rep["censusReuse"]["notReused"])

    def test_shared_file_end_change_invalidates(self):
        # ‏آخرُ مدخلٍ في الملفّ يُدخل نهايتَه في حشو النافذة، وقد يأتي من سورةٍ أخرى تشاركه
        idx = copy.deepcopy(self.idx)
        for e in idx["entries"]:
            e["fileRef"] = "https://example.org/shared.mp3"
        self.audit_and_flush(idx=idx)
        idx2 = copy.deepcopy(idx)
        last = max((e for e in idx2["entries"]), key=lambda e: e["startMs"])
        last["endMs"] += 50
        rep, _ = self.run_audit(idx=idx2)
        self.assertEqual(rep["censusReuse"]["reusedSurahs"], [])   # ‏التغيّر مسَّ نهايةَ الملفّ لكليهما

    def test_header_fields_that_name_the_source_invalidate(self):
        self.audit_and_flush()
        for k, v in (("sourceBySurah", {"2": "mirror-2"}), ("sourceTimingBySurah", {"2": "official"}),
                     ("engineVersion", "other")):
            with self.subTest(k=k):
                idx = copy.deepcopy(self.idx)
                idx[k] = v
                rep, _ = self.run_audit(idx=idx)
                self.assertNotIn(2, rep["censusReuse"]["reusedSurahs"])

    def test_text_change_invalidates(self):
        self.audit_and_flush()
        self.text[R.flat(3, 1)] = self.text[R.flat(3, 1)] + " زيادة"
        (self.assets / "text_hafs.jz").write_bytes(
            gzip.compress(json.dumps(self.text, ensure_ascii=False).encode("utf-8")))
        rep, _ = self.run_audit()
        self.assertEqual(rep["censusReuse"]["reusedSurahs"], [])

    def test_shared_module_model_runtime_and_env_changes_invalidate(self):
        self.audit_and_flush()
        for name, st in (("code", static(codeSha="code-2")), ("model", static(modelSha="model-2")),
                         ("ffmpeg", static(facts={"ffmpeg": "ffmpeg 7"})),
                         ("env", static(env={"QA_NO_RANGE": "1"}))):
            with self.subTest(name=name):
                cache = CC.CensusCache(self.s3, "b", st, write_ok=False, run_id="222")
                rep, _ = self.run_audit(cache=cache)
                self.assertEqual(rep["censusReuse"]["reusedSurahs"], [])

    def test_judge_constants_and_no_range_enter_the_key(self):
        self.audit_and_flush()
        with mock.patch.object(R, "LONG_MS", R.LONG_MS + 1):
            rep, _ = self.run_audit()
        self.assertEqual(rep["censusReuse"]["reusedSurahs"], [])
        with mock.patch.object(R, "_NO_RANGE", not R._NO_RANGE):
            rep, _ = self.run_audit()
        self.assertEqual(rep["censusReuse"]["reusedSurahs"], [])


class EligibilityTest(Base):
    def test_severe_surah_is_neither_stored_nor_reused(self):
        self.sever = {"3:2"}
        rep1, _ = self.audit_and_flush()
        self.assertEqual({r["kind"] for r in rep1["sample"]["rows"] if r["aid"] == "3:2"}, {"جسيم"})
        self.assertEqual(len(self.s3.puts), 1)                     # ‏سورة 2 وحدها
        self.sever = set()
        before = self.n_heard(3)
        rep2, _ = self.run_audit()
        self.assertEqual(rep2["censusReuse"]["reusedSurahs"], [2])
        self.assertGreater(self.n_heard(3), before)                # ‏أُعيد سماعُ 3

    def test_unavailable_row_or_error_window_is_neither_stored_nor_reused(self):
        self.failing = {"F|2:1", "L|2:1", "D|2:1"}                                      # ‏صفٌّ «تعذّر»
        rep1, _ = self.audit_and_flush()
        self.assertEqual(next(r for r in rep1["sample"]["rows"] if r["aid"] == "2:1")["verdict"], "تعذّر")
        self.assertEqual(len(self.s3.puts), 1)
        self.failing = {"D|3:2"}                                      # ‏نافذةُ خطأٍ دون صفّ تعذّر
        self.s3.objs.clear()
        self.s3.puts.clear()
        rep2, _ = self.audit_and_flush()
        self.assertEqual(rep2["sample"]["errors"], 1)
        self.assertEqual(len(self.s3.puts), 1)                     # ‏سورة 2 وحدها
        self.assertIn("3", rep2["censusReuse"]["notReused"])

    def test_inconclusive_surah_is_neither_stored_nor_reused(self):
        self.mute = {"2:2"}
        rep1, _ = self.audit_and_flush()
        self.assertEqual(next(r for r in rep1["sample"]["rows"] if r["aid"] == "2:2")["kind"], "غير حاسم")
        self.assertEqual(len(self.s3.puts), 1)

    def test_tampered_or_foreign_entries_are_rejected(self):
        self.audit_and_flush()
        key = next(k for k in self.s3.objs if "/002/" in k)
        good = json.loads(self.s3.objs[key])
        cases = {}
        d = copy.deepcopy(good); d["rows"][0]["kind"] = "جسيم"; cases["جسيم"] = d
        d = copy.deepcopy(good); d["rows"][0]["kind"] = "غير حاسم"; cases["غير حاسم"] = d
        d = copy.deepcopy(good); d["rows"] = d["rows"][:-1]; cases["ناقص"] = d
        d = copy.deepcopy(good); d["rows"][0]["independentSpokenCtc"] = {}; cases["دخيل"] = d
        d = copy.deepcopy(good); d["source"] = "local"; cases["محلي"] = d
        d = copy.deepcopy(good); d["runId"] = "abc"; cases["بلا تشغيلة"] = d
        d = copy.deepcopy(good); d["material"]["modelSha"] = "x"; cases["مادّة"] = d
        for name, doc in cases.items():
            with self.subTest(name=name):
                self.s3.objs[key] = json.dumps(doc, ensure_ascii=False).encode("utf-8")
                rep, _ = self.run_audit()
                self.assertEqual(rep["censusReuse"]["reusedSurahs"], [3])
        self.s3.objs[key] = b"not json"
        rep, _ = self.run_audit()
        self.assertEqual(rep["censusReuse"]["reusedSurahs"], [3])


class WriteAuthorityTest(unittest.TestCase):
    def test_only_ci_with_numeric_run_and_actions_env_may_write(self):
        ok = {"GITHUB_ACTIONS": "true"}
        self.assertTrue(CC.ci_may_write("ci", "123", ok))
        for source, run_id, env in (("local", "123", ok), ("cloud-build", "123", ok), ("ci", None, ok),
                                    ("ci", "abc", ok), ("ci", "123", {}), ("ci", "123", {"GITHUB_ACTIONS": "false"})):
            self.assertFalse(CC.ci_may_write(source, run_id, env), (source, run_id, env))

    def test_non_ci_cache_reads_but_never_writes(self):
        t = ReuseTest("test_identical_surahs_are_reused_and_not_heard")
        t.setUp()
        cache = CC.CensusCache(t.s3, "b", static(), write_ok=False, run_id="1")
        t.run_audit(cache=cache)
        self.assertEqual(cache.flush(), [])
        self.assertEqual(t.s3.puts, [])
        t.tmp.cleanup()


class KillSwitchTest(Base):
    def test_env_switch_disables_everything(self):
        for v in ("1", "true", "yes"):
            self.assertTrue(CC.disabled({CC.OFF_ENV: v}))
        for v in ("", "0", "false", "no"):
            self.assertFalse(CC.disabled({CC.OFF_ENV: v}))
        self.assertFalse(CC.disabled({}))

    def test_for_run_returns_none_when_off_or_unkeyable(self):
        model = Path(self.tmp.name) / "m.bin"
        model.write_bytes(b"\0" * 1_000_001)
        kw = dict(cl=self.s3, bucket="b", source="ci", run_id="9", code_roots=("tools/index_qa/census_cache.py",))
        self.assertIsNotNone(CC.for_run(model, env={"GITHUB_ACTIONS": "true"}, **kw))
        self.assertIsNone(CC.for_run(model, env={CC.OFF_ENV: "1", "GITHUB_ACTIONS": "true"}, **kw))
        self.assertIsNone(CC.for_run(Path(self.tmp.name) / "absent.bin", env={}, **kw))   # ‏الشكُّ ⇒ لا كاش

    def test_off_restores_the_old_behaviour_exactly(self):
        self.audit_and_flush()
        self.s3.gets.clear()
        n0, p0 = len(self.heard_jobs), len(self.s3.puts)
        rep_old, _ = self.audit_and_flush(cache=None)              # ‏CENSUS_CACHE=None كما يضعه الإطفاء
        self.assertEqual(self.s3.gets, [])                          # ‏لا قراءةَ كاش
        self.assertEqual(len(self.s3.puts), p0)                     # ‏ولا كتابة
        self.assertNotIn("censusReuse", rep_old)
        self.assertTrue(all("reusedFrom" not in r for r in rep_old["sample"]["rows"]))
        # ‏سُمع كلُّ شيء: ما سُمع في التشغيلة الأولى (‏لا مطالعَ هنا) يُسمع ثانيةً بعدده
        self.assertEqual(len(self.heard_jobs) - n0, n0)

    def test_cache_is_inert_outside_census_mode(self):
        cache = CC.CensusCache(self.s3, "b", static(), write_ok=True, run_id="1")
        args = SimpleNamespace(struct_only=False, allow_unmarked=True, local=True, rejudge=False,
                               clusters=20, per_cluster=10, band=None, refined=None, long_seg=False,
                               batch=48, threads=1, host=None, expect_sha=None)
        env = {k: v for k, v in os.environ.items() if k != "QA_CENSUS_SURAHS"}
        with mock.patch.object(R, "fetch_index", lambda k, w=None: (copy.deepcopy(self.idx), SHA)), \
                mock.patch.object(R, "structural", lambda *a, **k: ([], [], {})), \
                mock.patch.object(R, "_src_mtime", lambda k: None), \
                mock.patch.object(R, "ASSETS", self.assets), \
                mock.patch.object(R, "local_run", self.fake_local_run), \
                mock.patch.object(R, "CENSUS_CACHE", cache), \
                mock.patch.dict(os.environ, env, clear=True):
            R.audit(KEY, args)
        self.assertEqual(self.s3.gets, [])
        self.assertEqual(cache.keys, {})


class GateTest(Base):
    """التقريرُ المركّب يمرّ على `promote.census_gate` الحقيقية بشروط التقرير الكامل نفسِها."""

    def gate(self, rep, idx=None):
        idx = self.idx if idx is None else idx
        cl = FakeS3()
        cl.objs[P.CENSUS_PREFIX + KEY.replace("/", "_") + ".json"] = json.dumps(
            rep, ensure_ascii=False).encode("utf-8")
        return P.census_gate(cl, "b", KEY, SHA, idx)

    def roundtrip(self, rep):
        return json.loads(json.dumps(rep, ensure_ascii=False))

    def test_composed_report_is_accepted_like_the_full_one(self):
        full, _ = self.run_audit(cache=None)
        self.assertIsNone(self.gate(self.roundtrip(full)))
        self.audit_and_flush()
        mixed = copy.deepcopy(self.idx)
        next(e for e in mixed["entries"] if e["ayahId"] == "3:1")["endMs"] += 1     # ‏3 تُسمع و2 تُعاد
        composed, _ = self.run_audit(idx=mixed)
        self.assertEqual(composed["censusReuse"]["reusedSurahs"], [2])
        marked = [r for r in composed["sample"]["rows"] if "reusedFrom" in r]
        self.assertEqual({r["cluster"] for r in marked}, {2})
        self.assertIsNone(self.gate(self.roundtrip(composed), idx=mixed))
        allreused, _ = self.run_audit()
        self.assertEqual(allreused["censusReuse"]["reusedSurahs"], [2, 3])
        self.assertIsNone(self.gate(self.roundtrip(allreused)))

    def test_composed_report_is_rejected_like_the_full_one(self):
        # ‏سورةٌ جديدةٌ جسيمةٌ فوق 5% ⇒ يردّها الحارسُ بالسبب نفسِه في التقرير الكامل والمركّب
        self.audit_and_flush()
        mixed = copy.deepcopy(self.idx)
        next(e for e in mixed["entries"] if e["ayahId"] == "3:1")["endMs"] += 1
        self.sever = {"3:1", "3:2", "3:3"}
        composed, _ = self.run_audit(idx=mixed)
        self.assertEqual(composed["censusReuse"]["reusedSurahs"], [2])
        full, _ = self.run_audit(idx=mixed, cache=None)
        why_composed, why_full = self.gate(self.roundtrip(composed), mixed), self.gate(self.roundtrip(full), mixed)
        self.assertIsNotNone(why_full)
        self.assertEqual(why_composed, why_full)
        self.assertIn("> 5%", why_full)

    def test_gate_still_requires_every_ayah_of_a_reused_surah(self):
        self.audit_and_flush()
        rep, _ = self.run_audit()
        rep = self.roundtrip(rep)
        rep["sample"]["rows"] = rep["sample"]["rows"][:-1]          # ‏آيةٌ ناقصةٌ من صفوف مُعادة
        self.assertIn("لا يُقبل ناقص", self.gate(rep))


class ClosureTest(unittest.TestCase):
    def test_module_text_change_changes_the_digest(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "a.py").write_text("import b\nx = 1\n", encoding="utf-8")
            (d / "b.py").write_text("def f():\n    import c\n", encoding="utf-8")   # ‏استيرادٌ داخل دالّة
            (d / "c.py").write_text("y = 2\n", encoding="utf-8")
            (d / "unrelated.py").write_text("z = 3\n", encoding="utf-8")
            base = CC.code_digest(("a.py",), (d,), d)
            self.assertEqual(sorted(CC.code_closure(("a.py",), (d,), d)), ["a.py", "b.py", "c.py"])
            (d / "unrelated.py").write_text("z = 4\n", encoding="utf-8")
            self.assertEqual(CC.code_digest(("a.py",), (d,), d), base)           # ‏غيرُ المشارك لا يبطل
            for name in ("a.py", "b.py", "c.py"):                                # ‏المشاركُ ولو بعيداً يبطل
                old = (d / name).read_text(encoding="utf-8")
                (d / name).write_text(old + "# تعديل\n", encoding="utf-8")
                self.assertNotEqual(CC.code_digest(("a.py",), (d,), d), base, name)
                (d / name).write_text(old, encoding="utf-8")
                self.assertEqual(CC.code_digest(("a.py",), (d,), d), base)

    def test_real_closure_contains_the_judging_modules(self):
        files = set(CC.code_closure(CC.CODE_ROOTS))
        for must in ("tools/index_qa/run.py", "tools/index_qa/ci_run.py", "tools/index_qa/census_cache.py",
                     "tools/index_qa/promote.py", "tools/index_qa/mp3_resync.py",
                     "tools/alignment/channel_mix.py",
                     "tools/alignment_v3/spoken_census_witness.py",
                     "tools/alignment_v3/tail_census_witness.py",
                     "tools/alignment_v3/window_census_witness.py"):
            self.assertIn(must, files)

    def test_no_dynamic_imports_hide_from_the_closure(self):
        # ‏الإغلاقُ سكونيٌّ: وجودُ استيرادٍ ديناميكيٍّ في وحدةٍ مشاركة يُخفيها عنه، فيُمنع هنا
        for rel in CC.code_closure(CC.CODE_ROOTS):
            text = (CC.ROOT / rel).read_text(encoding="utf-8", errors="replace")
            for needle in ("importlib.import_module(", "__import__("):
                self.assertNotIn(needle, text, f"{rel}: {needle}")


if __name__ == "__main__":
    unittest.main()


def test_only_innocent_rows_are_reusable():
    """شُدّد: «طفيف» حكمُ عطبٍ فيُسمع من جديد؛ لا يُعاد إلا «بريء»."""
    import census_cache
    assert census_cache.REUSABLE_KINDS == ("بريء",)
