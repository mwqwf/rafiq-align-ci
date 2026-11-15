#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""`drop_surah.py --reclassify-source-truncated`: تصحيحُ رمز إعلانِ سورةٍ محجوبةٍ كلِّها من TIMING_UNDER_REPAIR إلى SOURCE_TRUNCATED
بدليل سماعٍ يُثبت أنّ الملفَّ نفسَه ناقص (‏2026-11-15 · benkirane_warsh.45e17a08 س13).

    python -m unittest tools.index_qa.test_drop_surah_reclassify

الفهرسُ هنا اصطناعيٌّ صغير: مداخلُ `testdata/akri_qalun.b99e3573.min.jz` بترويسةٍ على هيئة الحيّ 45e17a08 (‏رواية warsh · س13
معلَنةٌ TIMING_UNDER_REPAIR · س4 وس24 معلَنتان بترَ مصدر · `op` من نوع drop_ayahs لا يبدأ بـdrop_surah). والشاهدان هما مخرَجا
التشغيلتين الحقيقيّتين 43775192310 (small) و43775192404 (medium) لسورة 13 في `testdata/benkirane_s13_witnesses/`،
ونصوصُ الآيات من المصحف الموثَّق في المستودع (‏`heard_gate.disputed_ref_words`) لا من تفريغٍ.

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
import pin_heard                                                 # noqa: E402
import promote                                                   # noqa: E402
from rename_reciter import entries_sha                           # noqa: E402

FIX = HERE / "testdata" / "akri_qalun.b99e3573.min.jz"
WIT = HERE / "testdata" / "benkirane_s13_witnesses"
KEY = "timings/warsh/benkirane_warsh.jz"
RUNS = ["43775192310", "43775192404"]
GAP = (14, 24)
AUDIO_SHA = "a06c67fed009fa3d6190244d573cb7747c1357798e682cc2c65aabba692aed95"
OLD_USER = "توقيت هذه السورة لهذا القارئ قيد الإصلاح، فحُجبت مؤقّتاً حتى لا تُعرض آياتها على صوت غيرها"
OLD_REASON = "توقيت س13 يُسمع على صوت غيره؛ حُجبت مؤقّتاً حتى يُصلح."
USER = "ملفّ تسجيل هذه السورة عند الناشر ناقص: ينتقل من الآية 13 إلى الآية 25 مباشرةً."
REASON = ("ملفّ المصدر نفسُه ناقص: شاهدا Whisper (small 43775192310 وmedium 43775192404) يسمعان «وهم يجادلون في الله» "
          "(‏13:13) ثمّ «أولئك لهم اللعنة» (‏13:25) متتاليتين بعد نحو خمس ثوانٍ، فلا آياتِ 14–24 في الملفّ.")


def _w(name):
    return json.loads((WIT / f"{name}.json").read_text(encoding="utf-8"))


def witnesses():
    return {r: _w(r) for r in RUNS}


def loader_of(wits):
    def load(run, surah):
        if run not in wits:
            raise SystemExit(f"⛔ لا شاهدَ {run}")
        return copy.deepcopy(wits[run])
    return load


def live_like(mutate=None):
    """فهرسٌ على هيئة الحيّ 45e17a08: س13 غائبةٌ كلُّها معلَنةٌ TIMING_UNDER_REPAIR فوق إعلاني س4 وس24 (‏بتر مصدر)."""
    idx = json.loads(gzip.decompress(FIX.read_bytes()))
    idx.pop("fixtureNote", None)
    idx.update(riwaya="warsh", reciterId="benkirane_warsh")
    idx["audioSha256"] = list(idx["audioSha256"])
    idx["audioSha256"][12] = AUDIO_SHA
    tr0 = idx["transform"]
    gone = [e["ayahId"] for e in idx["entries"] if e["ayahId"].startswith("13:")]
    idx["entries"] = [e for e in idx["entries"] if not e["ayahId"].startswith("13:")]
    m = idx["missing"]
    m["count"] += len(gone)
    m["byReason"]["timing_under_repair"] = len(gone)
    m["ids"] = sorted(m["ids"] + gone, key=lambda a: tuple(map(int, a.split(":"))))
    st = {f: tr0[f] for f in ("reasonCode", "reasonUser", "reason")}
    tur = {"reasonCode": "TIMING_UNDER_REPAIR", "reasonUser": OLD_USER, "reason": OLD_REASON}
    idx["transform"] = {
        "truncatedTail": tr0["truncatedTail"],
        "declarations": {"4": {"op": "drop_surah", **st}, "24": {"op": "declare_gap", **st},
                         "13": {"op": "drop_surah", **tur}},
        "op": "declare_gap:24",
        "fromSha256": "143e13dd932467e0610ab3adbf5f60edc83e3bc3eb977f0076d4a1990ba8107a",
        "fromKey": KEY, "droppedEntries": 0, "by": "drop_ayahs",
        **tur,
        "dropSurah": [4, 13],
        "timingRepair": {"13": {"probes": [{"ayah": 14, "startMs": 1, "heardAyah": 25}], "witnesses": {}}},
        "entriesSha256": entries_sha(idx["entries"]),
    }
    if mutate:
        mutate(idx)
    return idx


def _blob(idx):
    return gzip.compress(json.dumps(idx, ensure_ascii=False, separators=(",", ":")).encode(), 9, mtime=0)


def _sha(idx):
    return hashlib.sha256(_blob(idx)).hexdigest()


def run(mod=None, idx=None, surah=13, gap=GAP, runs=None, wits=None, key=KEY, **kw):
    mod = mod or drop_surah
    idx = idx or live_like()
    kw.setdefault("reason", REASON)
    kw.setdefault("reason_user", USER)
    kw.setdefault("loader", loader_of(wits if wits is not None else witnesses()))
    return mod.reclassify_source_truncated(idx, _sha(idx), key, surah, gap, RUNS if runs is None else runs, **kw)


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
    argv = ["drop_surah.py", "--key", KEY, "--sha", hashlib.sha256(body).hexdigest()[:8], "--surah", "13",
            "--reason", REASON, *extra, *(["--yes"] if yes else [])]
    wits = witnesses()
    with mock.patch.object(promote, "s3", return_value=(b, "bk")), mock.patch.object(sys, "argv", argv), \
            mock.patch.object(pin_heard, "load_witness", side_effect=loader_of(wits)):
        mod.main()
    return b


TAG = r"\[reclassify:{}\]"
GOOD_FLAGS = ["--reclassify-source-truncated", "--witness-runs", ",".join(RUNS), "--gap", "14-24", "--reason-user", USER]


class Accept(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.live = live_like()
        cls.lsha = _sha(cls.live)
        cls.out = drop_surah.reclassify_source_truncated(cls.live, cls.lsha, KEY, 13, GAP, RUNS, reason=REASON,
                                                         reason_user=USER, loader=loader_of(witnesses()))
        cls.nsha = _sha(cls.out)

    def test_only_the_code_of_the_named_surah_changes(self):
        t, t0 = self.out["transform"], self.live["transform"]
        self.assertEqual(t["declarations"]["13"], {"op": "drop_surah", "reasonCode": "SOURCE_TRUNCATED",
                                                    "reasonUser": USER, "reason": REASON})
        for s in ("4", "24"):
            self.assertEqual(t["declarations"][s], t0["declarations"][s])
        self.assertEqual(promote.declared_surah_codes(t),
                         {**promote.declared_surah_codes(t0), 13: "SOURCE_TRUNCATED"})
        self.assertEqual(t["dropSurah"], [4, 13])
        self.assertEqual(t["truncatedTail"], t0["truncatedTail"])
        # الرمزُ العلويّ كان يصف س13 وحدها فيتبعها
        self.assertEqual((t["reasonCode"], t["reasonUser"], t["reason"]), ("SOURCE_TRUNCATED", USER, REASON))
        self.assertNotIn("timingRepair", t)
        self.assertEqual(t["reclassify"]["13"]["replacedTimingRepair"], t0["timingRepair"]["13"])
        self.assertEqual(t["reclassify"]["13"]["replacedRecord"], t0["declarations"]["13"])

    def test_entries_and_everything_else_byte_identical(self):
        self.assertEqual(self.out["entries"], self.live["entries"])
        self.assertEqual(json.dumps(self.out["entries"], sort_keys=True), json.dumps(self.live["entries"], sort_keys=True))
        keys = lambda d: {k: v for k, v in d.items() if k not in ("transform", "missing")}      # noqa: E731
        self.assertEqual(keys(self.out), keys(self.live))
        t = self.out["transform"]
        self.assertEqual(t["entriesSha256"], entries_sha(self.live["entries"]))
        self.assertEqual(t["entriesSha256"], t["parentEntriesSha256"])
        self.assertEqual((t["droppedEntries"], t["addedEntries"], t["removedEntries"], t["movedEntries"]), (0, 0, 0, 0))
        self.assertEqual((t["fromKey"], t["fromSha256"]), (KEY, self.lsha))

    def test_counters_move_exactly_the_surah_ayahs(self):
        mo, ml = self.out["missing"], self.live["missing"]
        self.assertEqual((mo["ids"], mo["count"]), (ml["ids"], ml["count"]))
        self.assertEqual(ml["byReason"]["timing_under_repair"], 43)
        self.assertNotIn("timing_under_repair", mo["byReason"])
        self.assertEqual(mo["byReason"]["source_truncated"], ml["byReason"]["source_truncated"] + 43)
        self.assertEqual(promote.truncation_excused(self.out) - promote.truncation_excused(self.live), 43)

    def test_op_leads_with_drop_surah_so_the_candidate_is_gated_as_a_declared_drop(self):
        self.assertEqual(self.out["transform"]["op"], "drop_surah:4,13|declare_gap:24")
        self.assertEqual(self.out["transform"]["reclassify"]["13"]["replacedOp"], "declare_gap:24")

    def test_evidence_recorded(self):
        r = self.out["transform"]["reclassify"]["13"]
        self.assertEqual((r["from"], r["to"], r["gap"], r["movedAyahs"]), ("TIMING_UNDER_REPAIR", "SOURCE_TRUNCATED", [14, 24], 43))
        self.assertEqual(sorted(r["witnesses"]), RUNS)
        for run, h in r["heard"].items():
            self.assertLessEqual(h["gapMs"], drop_surah.RECLASSIFY_MAX_GAP_MS, run)
            self.assertTrue(h["prevGram"] and h["nextGram"], run)
        self.assertEqual({w["model"] for w in r["witnesses"].values()}, {"small", "medium"})

    def test_every_consumer_of_the_code_accepts_the_result(self):
        """index_gate بلا صفّ موافقة (‏الرمزُ بترٌ لا حجبٌ مؤقّت) · إعلانُ الذيل · وحارسُ الأصل."""
        self.assertIsNone(promote.index_gate(self.out, parent=self.live, parent_sha=self.lsha))
        self.assertTrue(promote.declared_truncated_tail(self.out, "24")[0])
        self.assertIsNone(promote.coded_drop_gate(self.out, self.live, frozenset()))

    def test_candidate_on_top_inherits_where_it_was_rejected_before(self):
        """مرشّحٌ فوق الناتج يرث إعلانَ الغياب (‏بيانُ ST مقبولٌ بلا صفّ)، وفوق الحيّ القديم يُردّ ببيان TIMING_UNDER_REPAIR."""
        def cand(parent_sha):
            c = copy.deepcopy(self.out)
            c["transform"] = {"op": "ctc_heardmap_splice:106", "fromKey": KEY, "fromSha256": parent_sha,
                              "dropSurah": [4, 13], "reasonCode": self.out["transform"]["reasonCode"],
                              "reasonUser": self.out["transform"]["reasonUser"]}
            return c
        got, why = promote.inherited_drops(cand(self.nsha), self.out, self.nsha, frozenset())
        self.assertEqual((got, why), ({"4", "13"}, None))
        old = copy.deepcopy(cand(self.lsha))
        old["transform"].update(reasonCode="TIMING_UNDER_REPAIR", reasonUser=OLD_USER)
        got, why = promote.inherited_drops(old, self.live, self.lsha, frozenset())
        self.assertEqual(got, set())
        self.assertIsNotNone(why)

    def test_top_code_kept_when_another_surah_keeps_the_old_code(self):
        def keep23(i):
            i["transform"]["declarations"]["23"] = {"op": "declare_gap", "reasonCode": "TIMING_UNDER_REPAIR",
                                                    "reasonUser": OLD_USER, "reason": OLD_REASON}
        out = run(idx=live_like(keep23))
        self.assertEqual(out["transform"]["reasonCode"], "TIMING_UNDER_REPAIR")
        self.assertEqual(out["transform"]["declarations"]["23"]["reasonCode"], "TIMING_UNDER_REPAIR")
        self.assertEqual(out["transform"]["declarations"]["13"]["reasonCode"], "SOURCE_TRUNCATED")

    def test_main_prints_then_uploads_only_with_yes(self):
        with mock.patch("builtins.print"):
            b = run_main([*GOOD_FLAGS], yes=False)
            self.assertEqual(list(b.store), [KEY])
            b = run_main([*GOOD_FLAGS])
        keys = [k for k in b.store if k.startswith("timings-staging/warsh/benkirane_warsh.")]
        self.assertEqual(len(keys), 1)
        got = json.loads(gzip.decompress(b.store[keys[0]]))
        self.assertEqual(got["transform"]["declarations"]["13"]["reasonCode"], "SOURCE_TRUNCATED")
        self.assertEqual(got["entries"], self.live["entries"])
        self.assertIn(hashlib.sha256(b.store[keys[0]]).hexdigest()[:8], keys[0])


# ── سيناريوهات الردّ: كلٌّ منها يخالف شرطاً واحداً فقط ─────────────────────────────────────────────────────────────

def _edit_wits(fn):
    w = witnesses()
    fn(w)
    return w


def _words(w, run="43775192310", ayah="13"):
    return w[run]["ayahs"][ayah]["words"]


def _find(words, token):
    return next(i for i, x in enumerate(words) if x["w"] == token)


def _drop_prev(w):                       # لا يُسمع شيءٌ من نصّ 13:13 عند الشاهد الأوّل
    for rec in w["43775192310"]["ayahs"].values():
        rec["words"] = [x for x in rec["words"] if x["w"] not in ("وهم", "يجادلون", "في", "الله", "ويسبح", "الرعب", "بحمده",
                                                                  "والملائكة", "من", "خيفته", "ويرسل", "الصواعق", "فيصيب",
                                                                  "بها", "يشاء")]


def _drop_next(w):                       # لا يُسمع شيءٌ من نصّ 13:25 عند الشاهد الأوّل (‏يُقطع تفريغُه بعد 13:13)
    for rec in w["43775192310"]["ayahs"].values():
        rec["words"] = [x for x in rec["words"] if x["s"] < 311000]


def _next_first(w):                      # مقطعُ 13:25 يُسمع قبل مقطع 13:13 زمنيّاً لا بعده (‏لا ترتيبَ صحيح)
    for run in RUNS:
        rec = w[run]["ayahs"]["25"]
        rec["windowMs"] = [280000, rec["windowMs"][1]]
        rec["words"] = [{"w": t, "s": 286000 + n * 500, "e": 286400 + n * 500, "p": 0.97}
                        for n, t in enumerate(("لهم", "اللعنة", "ولهم"))]


def _far(w):                             # يُبعَد مقطعُ 13:25 عن 13:13 ≥ 13ث في الشاهدَين
    for run in RUNS:
        for rec in w[run]["ayahs"].values():
            ws = rec["words"]
            cut = next((i for i, x in enumerate(ws) if x["w"] in ("أولئك", "أولائك") and x["s"] > 313000), None)
            if cut is None:
                continue
            for x in ws[cut:]:
                x["s"] += 13000
                x["e"] += 13000
            rec["windowMs"] = [rec["windowMs"][0], rec["windowMs"][1] + 13000]


def _between(w):                         # يُسمع بين الآيتين نصٌّ من 13:14 («له دعوة الحق») بثقة عالية
    for run in RUNS:
        ws = _words(w, run)
        i = next(n for n, x in enumerate(ws) if x["s"] > 313000)
        s = ws[i]["s"] - 1500
        ws[i:i] = [{"w": t, "s": s + n * 400, "e": s + n * 400 + 380, "p": 0.97} for n, t in enumerate(("له", "دعوة", "الحق"))]


def _drop_second(w):
    w.pop(RUNS[1])


S_KEY = lambda mod=None: run(mod, key="timings-staging/warsh/benkirane_warsh.12345678.jz")                  # noqa: E731
def _no5(i):                             # س5 غائبةٌ كلُّها لكنّها غيرُ معلَنة
    i["entries"] = [e for e in i["entries"] if not e["ayahId"].startswith("5:")]


S_UNDECLARED = lambda mod=None: run(mod, idx=live_like(_no5), surah=5)                                       # noqa: E731
S_REASON_REQ = lambda mod=None: run(mod, reason_user="  ")                                                   # noqa: E731
S_BANNED = lambda mod=None: run(mod, reason="سببٌ عرضه المشرف على القارئ")                                    # noqa: E731
S_NOT_DROP = lambda mod=None: run(mod, idx=live_like(lambda i: i["transform"]["declarations"]["13"].update(  # noqa: E731
    op="declare_gap")))
S_CODE = lambda mod=None: run(mod, idx=live_like(lambda i: i["transform"]["declarations"]["13"].update(     # noqa: E731
    reasonCode="OTHER")))


def _with_entries(i):
    e = next(x for x in json.loads(gzip.decompress(FIX.read_bytes()))["entries"] if x["ayahId"] == "13:1")
    i["entries"].append(e)
    i["missing"]["count"] -= 1
    i["missing"]["ids"].remove("13:1")


S_HAS_ENTRIES = lambda mod=None: run(mod, idx=live_like(_with_entries))                                      # noqa: E731
S_GAP_FORM = lambda mod=None: run(mod, gap=(14, 99))                                                         # noqa: E731
S_GAP_EDGE = lambda mod=None: run(mod, gap=(1, 24))                                                          # noqa: E731
S_GAP_SMALL = lambda mod=None: run(mod, gap=(14, 20))                                                        # noqa: E731
S_RUNS = lambda mod=None: run(mod, runs=[RUNS[0]])                                                           # noqa: E731
S_LOAD = lambda mod=None: run(mod, wits={RUNS[0]: _w(RUNS[0])})                                              # noqa: E731
S_W_SURAH = lambda mod=None: run(mod, wits=_edit_wits(lambda w: w[RUNS[0]].update(surah=14)))                # noqa: E731
S_W_SHA = lambda mod=None: run(mod, wits=_edit_wits(lambda w: w[RUNS[0]].update(sha256="0" * 64)))           # noqa: E731
S_W_MODEL = lambda mod=None: run(mod, wits=_edit_wits(lambda w: w[RUNS[0]].update(model="tiny")))            # noqa: E731
S_W_DIFF = lambda mod=None: run(mod, wits={RUNS[0]: _w(RUNS[0]), RUNS[1]: _w(RUNS[0])})                      # noqa: E731
S_PREV = lambda mod=None: run(mod, wits=_edit_wits(_drop_prev))                                              # noqa: E731
S_NEXT = lambda mod=None: run(mod, wits=_edit_wits(_drop_next))                                              # noqa: E731
S_ORDER = lambda mod=None: run(mod, wits=_edit_wits(_next_first))                                            # noqa: E731
S_FAR = lambda mod=None: run(mod, wits=_edit_wits(_far))                                                     # noqa: E731
S_BETWEEN = lambda mod=None: run(mod, wits=_edit_wits(_between))                                             # noqa: E731
S_COUNTS = lambda mod=None: run(mod, idx=live_like(lambda i: i["missing"]["byReason"].pop(                   # noqa: E731
    "timing_under_repair")))
S_FLAGS = lambda mod=None: run_main(["--reclassify-source-truncated", "--witness-runs", ",".join(RUNS), "--gap", "14-24",  # noqa: E731
                                     "--reason-user", USER, "--reaffirm"], mod=mod)


class Reject(unittest.TestCase):
    def assertTag(self, tag, fn):
        with self.assertRaisesRegex(SystemExit, TAG.format(tag)):
            fn()

    def test_each_scenario_is_rejected_with_its_tag(self):
        for tag, fn in Mutations.CASES:
            with self.subTest(tag=tag):
                if tag == "flags":
                    with mock.patch("builtins.print"):
                        self.assertTag(tag, fn)
                else:
                    self.assertTag(tag, fn)

    def test_gap_boundaries(self):
        run(gap=(14, 24))                                 # 11 آيةً من 43 ⇒ أكثرُ من الربع
        self.assertTag("gap_small", lambda: run(gap=(14, 23)))           # 10×4 = 40 ≤ 43
        self.assertTag("gap_edge", lambda: run(gap=(14, 43)))

    def test_single_witness_run_id_forms(self):
        self.assertTag("witness_runs", lambda: run(runs=[RUNS[0], RUNS[0]]))
        self.assertTag("witness_runs", lambda: run(runs=[RUNS[0], "0" + RUNS[1]]))
        self.assertTag("witness_runs", lambda: run(runs=[RUNS[0], "abc"]))

    def test_live_not_mutated(self):
        live = live_like()
        before = json.dumps(live, sort_keys=True)
        run(idx=live)
        self.assertEqual(json.dumps(live, sort_keys=True), before)

    def test_flag_forms(self):
        for extra in (["--witness-runs", "1", "--gap", "14-24"],                                     # بلا الوضع
                      [*GOOD_FLAGS, "--declare-absent"], [*GOOD_FLAGS, "--timing-evidence", "x.json"],
                      [*GOOD_FLAGS, "--evidence", "ops/evidence/x.json"], [*GOOD_FLAGS, "--reason-code", "OTHER"],
                      ["--reclassify-source-truncated", "--reason-user", USER, "--gap", "14-24"],     # بلا --witness-runs
                      ["--reclassify-source-truncated", "--witness-runs", ",".join(RUNS), "--reason-user", USER]):   # بلا --gap
            with self.subTest(extra=extra), mock.patch("builtins.print"):
                with self.assertRaisesRegex(SystemExit, r"\[(reclassify|reaffirm):flags\]"):
                    run_main(extra)
        with mock.patch("builtins.print"), self.assertRaisesRegex(SystemExit, r"\[reclassify:flags\]"):
            drop_surah_main_two_surahs()
        with self.assertRaisesRegex(SystemExit, r"\[reclassify:gap_form\]"):
            drop_surah.parse_gap("14..24")


def drop_surah_main_two_surahs():
    body = _blob(live_like())
    b = _Bucket(body)
    argv = ["drop_surah.py", "--key", KEY, "--sha", hashlib.sha256(body).hexdigest()[:8], "--surah", "13,24",
            "--reason", REASON, *GOOD_FLAGS]
    with mock.patch.object(promote, "s3", return_value=(b, "bk")), mock.patch.object(sys, "argv", argv):
        drop_surah.main()


def mutant(tag):
    """نسخةٌ من `drop_surah` عُطّل فيها كلُّ ردٍّ موسومٍ بـ`tag` (‏الشرطُ يبقى، والردُّ صار لا شيء)."""
    src = (HERE / "drop_surah.py").read_text(encoding="utf-8")
    n = src.count(f'_reclass_reject("{tag}"')
    src = src.replace(f'_reclass_reject("{tag}"', f'_noop("{tag}"')
    if tag == "flags":
        n = len(re.findall(r'raise SystemExit\("⛔ \[reclassify:flags\]', src))
        src = re.sub(r'raise SystemExit\(("⛔ \[reclassify:flags\])', r'_noop(\1', src)
    assert n, tag
    src = src.replace("\ndef _reclass_reject(", "\ndef _noop(*a, **k):\n    return None\n\n\ndef _reclass_reject(", 1)
    mod = types.ModuleType(f"drop_surah_mut_{tag}")
    mod.__file__ = str(HERE / "drop_surah.py")
    exec(compile(src, mod.__file__, "exec"), mod.__dict__)                # noqa: S102
    return mod


class Mutations(unittest.TestCase):
    """إزالةُ كلّ شرطٍ تُسقط اختبارَ ردّه: السيناريو نفسُه لا يُخرج الوسمَ في النسخة المطفَّرة. وتُسجَّل نتيجةُ كلّ طفرةٍ:
    «قُبل» (‏لا حاجزَ غيرُه) أو «ردّه حاجزٌ آخر <وسمُه>» (‏طبقتان) أو «انهار»."""

    CASES = [("key_live", S_KEY), ("not_declared", S_UNDECLARED), ("reason_required", S_REASON_REQ), ("banned", S_BANNED),
             ("not_drop", S_NOT_DROP), ("code", S_CODE), ("has_entries", S_HAS_ENTRIES), ("gap_form", S_GAP_FORM),
             ("gap_edge", S_GAP_EDGE), ("gap_small", S_GAP_SMALL), ("witness_runs", S_RUNS), ("witness_load", S_LOAD),
             ("witness_surah", S_W_SURAH), ("witness_sha", S_W_SHA), ("witness_model", S_W_MODEL), ("witness_diff", S_W_DIFF),
             ("heard_prev", S_PREV), ("heard_next", S_NEXT), ("heard_order", S_ORDER), ("heard_gap", S_FAR),
             ("heard_between", S_BETWEEN), ("counts", S_COUNTS), ("flags", S_FLAGS)]
    outcomes: dict = {}

    def test_each_guard_is_load_bearing(self):
        for tag, scenario in self.CASES:
            with self.subTest(tag=tag):
                with mock.patch("builtins.print"):
                    with self.assertRaisesRegex(SystemExit, TAG.format(tag)):
                        scenario()                                        # الأصلُ يردّ بالوسم
                mod = mutant(tag)
                try:
                    with mock.patch("builtins.print"):
                        scenario(mod)
                    verdict = "قُبل"
                except SystemExit as e:
                    self.assertNotRegex(str(e), TAG.format(tag))
                    m = re.search(r"\[reclassify:(\w+)\]", str(e))
                    verdict = f"ردّه حاجزٌ آخر {m.group(1) if m else '(غيرُ موسوم)'}"
                except Exception as e:                                    # noqa: BLE001
                    verdict = f"انهار ({type(e).__name__})"
                Mutations.outcomes[tag] = verdict
        print("\nنتيجة الطفرات:\n" + "\n".join(f"  {t:16} ← {v}" for t, v in Mutations.outcomes.items()))

    def test_heard_mutants_accept_when_guard_is_the_only_barrier(self):
        """الحاجزان الأخيران (‏المسافةُ والتداخل) مستقلّان: بإزالة أيٍّ منهما يُقبل السيناريو الذي لا يخالف غيرَه."""
        for tag, scenario in ((("heard_between", S_BETWEEN)),):
            with self.subTest(tag=tag), mock.patch("builtins.print"):
                scenario(mutant(tag))


if __name__ == "__main__":
    unittest.main()
