# -*- coding: utf-8 -*-
"""📖 **حجمُ أثر الفكّ الموجَّه بمعجم المصحف (GBNF في whisper-cli)** — الخطوة 2-أ من خطة المستشار 2026-10-05.

يشغّل `whisper-cli` على g3r (‏`g3rn` مضجَّج · `g3rc` نظيف) وg2 (‏`wavn`) بذراعَين أو أكثر **على البنود عينِها**:
* `ref` — بلا نحو (‏المرجع؛ الرايات المشحونة `-l en -bs 1 -et 2.40`).
* `P<n>` — الرايات نفسُها + `--grammar mushaf.gbnf --grammar-rule root --grammar-penalty n`.
  (‏⚠️ whisper-cli يحوّل الاستراتيجيّةَ إلى beam-search حين يُعطى نحوٌ، وبـ`-bs 1` هو greedy بمكافأةٍ — الفرقُ الوحيدُ بين الذراعَين هو النحو.)
ثمّ يحكم بأدوات العدّة نفسِها (‏`v2_gate.judge_arm` · `v2_gate._boot_diff`): Δاتّهام كاذب وΔكشف بـbootstrap عنقوديّ بالبند، ونسبةُ oov
(‏كلماتُ المفكوك المطبَّعةُ **خارجَ** المعجم) والزمنُ الوسيط.

⚖️ **المعيارُ مكتوبٌ قبل القراءة (المستشار):** لذراعٍ ما، **على كلّ مجموعةٍ على حِدة**: الحدُّ الأعلى لـΔاتّهام ≤ 0
**و** (‏على g3r) الحدُّ الأدنى لـΔكشف ≥ 0 **و** الزمنُ ≤ ×1.2 **و** oov ينخفض ≥ 20 نقطةً (‏مجمَّعاً) — وإلا فالمكافأةُ لا تعمل.
مرَّ ذراعٌ ⇒ يُوصى بـJNI (‏2ب)؛ وإلا يُغلق البندُ بسطر.

⚠️ حدُّه يُقال معه: لينكس/glibc لا أندرويد، و`whisper-cli` لا `jni.c`؛ والمقيسُ **أثرُ النحو** لا رقمُ الجهاز.
الزمنُ = `total − load` من `whisper_print_timings` (‏تحليلُ النحو وتحميلُ النموذج خارجَه)، والعمّالُ متوازون (‏`-t 1`) فالنسبةُ مقارِنةٌ لا مطلقة.

    python tools/tasmi_bench/lexbias_bench.py --cli wc/b/bin/whisper-cli --models tiny=a.bin,base=b.bin --grammar mushaf.gbnf --words words.txt --md out.md --json out.json
    python tools/tasmi_bench/lexbias_bench.py --selftest
"""
import argparse
import json
import os
import re
import statistics
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import detect_score as D  # noqa: E402
import scorer  # noqa: E402
import token_conf_auc as T  # noqa: E402
import v2_gate as V  # noqa: E402

WORK = os.path.join(HERE, "work")
FLAGS = T.FLAGS
SETS = {k: T.SETS[k] for k in ("g3rn", "g3rc", "g2")}
CONF = {scorer.MISSED, scorer.SUBSTITUTED}
COLLAPSE = 0.60
TIME_MAX = 1.2          # ⛔ سقفُ الزمن من المستشار
OOV_DROP = 0.20         # ⛔ هبوطُ oov المطلوبُ (‏نقاطٌ مطلقة)
_T = re.compile(r"(load|total)\s+time\s*=\s*([\d.]+)\s*ms")


# ───────────────────────── التشغيل ─────────────────────────

def run_one(cli, model, wav, base, grammar, penalty, threads):
    """يفكّ ملفّاً. يعيد {text, ms (‏total−load), wall}. يُستأنف من `base.json` إن وُجد."""
    jp = base + ".json"
    if os.path.exists(jp) and os.path.getsize(jp) > 0:
        return json.load(open(jp, encoding="utf-8"))
    os.makedirs(os.path.dirname(base), exist_ok=True)
    cmd = [cli, "-m", model, "-t", str(threads), "-otxt", "-of", base] + FLAGS
    if grammar:
        cmd += ["--grammar", os.path.abspath(grammar), "--grammar-rule", "root", "--grammar-penalty", str(penalty)]
    cmd += [wav]
    t0 = time.time()
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    wall = (time.time() - t0) * 1000
    err = (p.stderr or "") + (p.stdout or "")
    if p.returncode == 4 or "failed to parse grammar" in err:
        raise SystemExit(f"⛔ فشل تحليلُ النحو (رمز {p.returncode}):\n{err[-600:]}")
    if "usage:" in err and "error:" in err:
        raise SystemExit(f"⛔ رايةٌ غيرُ مدعومة:\n{err[:400]}")
    tx = base + ".txt"
    if not os.path.exists(tx):
        raise SystemExit(f"⛔ لا مخرجَ لـ{os.path.basename(wav)} (رمز {p.returncode}):\n{err[-500:]}")
    text = " ".join(open(tx, encoding="utf-8", errors="replace").read().split())
    tm = {k: float(v) for k, v in _T.findall(err)}
    ms = (tm["total"] - tm["load"]) if "total" in tm and "load" in tm else None
    rec = {"text": text, "ms": ms, "wall": wall}
    json.dump(rec, open(jp, "w", encoding="utf-8"), ensure_ascii=False)
    return rec


def collect(cli, model_name, model, arms, sets, workdir, threads, workers, limit, grammar):
    """{مجموعة: {ذراع: {id: rec}}} + بنود كلّ مجموعة."""
    out, plans = {}, {}
    for sname in sets:
        folder, plan_name, _ = SETS[sname]
        d = os.path.join(WORK, folder)
        if not os.path.isdir(d):
            raise SystemExit(f"⛔ لا مجلدَ {d} — المجموعةُ {sname} لم تُبنَ")
        items = [it for it in T.load_plan(plan_name) if os.path.exists(os.path.join(d, it["id"] + ".wav"))]
        if limit:
            items = items[:limit]
        if not items:
            raise SystemExit(f"⛔ المجموعةُ {sname} بلا ملفّات")
        plans[sname] = items
        out[sname] = {}
        for arm, pen in arms:
            print(f"▶ {model_name} · {sname} · {arm}: {len(items)} بنداً", flush=True)
            t0 = time.time()

            def one(it):
                return it["id"], run_one(cli, model, os.path.join(d, it["id"] + ".wav"),
                                         os.path.join(workdir, model_name, arm, sname, it["id"]),
                                         grammar if pen is not None else None, pen, threads)

            with ThreadPoolExecutor(max_workers=workers) as ex:
                out[sname][arm] = dict(ex.map(one, items))
            print(f"   ⏱ {time.time() - t0:.0f}ث", flush=True)
    return out, plans


# ───────────────────────── الحساب ─────────────────────────

def hyps_of(recs):
    return {i: {"text": r["text"]} for i, r in recs.items()}


def judge_set(plans, ref_recs, arm_recs, injected):
    """(‏Δاتّهام (قيمة، [lo, hi])، Δكشف (أو None)، اتّهامُ الذراعين، كشفُ الذراعين، عددُ المنهارة بحارس 0.60)."""
    plan = [it for it in plans if it["id"] in ref_recs and it["id"] in arm_recs]
    ha, hb = hyps_of(ref_recs), hyps_of(arm_recs)
    if injected:
        da, fa_a, n, pa = V.judge_arm(plan, ha)
        db, fa_b, _, pb = V.judge_arm(plan, hb)
        keys = [i for i in pa if i in pb]
        lo, hi, _p = V._boot_diff([(pa[i][0], pa[i][1], pb[i][0], pb[i][1]) for i in keys])
        dl, dh, _p = V._boot_diff([(pa[i][2], 1, pb[i][2], 1) for i in keys])
        det = {"diff": db - da, "ci": (dl, dh), "arms": (da, db)}
    else:
        pa, pb = _fa_only(plan, ha), _fa_only(plan, hb)
        keys = [i for i in pa if i in pb]
        lo, hi, _p = V._boot_diff([(pa[i][0], pa[i][1], pb[i][0], pb[i][1]) for i in keys])
        fa_a = sum(pa[i][0] for i in keys) / max(sum(pa[i][1] for i in keys), 1)
        fa_b = sum(pb[i][0] for i in keys) / max(sum(pb[i][1] for i in keys), 1)
        det, n = None, len(keys)
    return {"n": n, "fa": (fa_a, fa_b), "fa_diff": fa_b - fa_a, "fa_ci": (lo, hi), "det": det,
            "collapsed": (_collapsed(plan, ha), _collapsed(plan, hb))}


def _score(it, h):
    if not h or not h.get("text"):
        return None
    return scorer.score(it["refText"].split(), h["text"], D.cfg_for(it.get("riwaya")))


def _fa_only(plan, hyps):
    """g2: تلاواتٌ صحيحةٌ ⇒ كلُّ اتّهامٍ كاذب. (‏اتّهامات، كلمات) لكلّ بند؛ المنهارُ بالحارس (0,0) كما في `judge_arm`."""
    out = {}
    for it in plan:
        s = _score(it, hyps.get(it["id"]))
        if not s:
            continue
        ws = s["words"]
        if sum(1 for w in ws if w[1] in CONF) / max(len(ws), 1) > COLLAPSE:
            out[it["id"]] = (0, 0)
            continue
        out[it["id"]] = (sum(1 for w in ws if w[1] in CONF), len(ws))
    return out


def _collapsed(plan, hyps):
    c = 0
    for it in plan:
        s = _score(it, hyps.get(it["id"]))
        if s and sum(1 for w in s["words"] if w[1] in CONF) / max(len(s["words"]), 1) > COLLAPSE:
            c += 1
    return c


def oov_rate(plan, recs, lex):
    """نسبةُ كلماتِ المفكوك (بعد `scorer.norm` بإعداد الرواية) غيرِ الموجودةِ في `lex`، مجمَّعةً على البنود."""
    tot = bad = 0
    for it in plan:
        r = recs.get(it["id"])
        if not r:
            continue
        cfg = D.cfg_for(it.get("riwaya"))
        for w in r["text"].split():
            n = scorer.norm(w, cfg)
            if n:
                tot += 1
                bad += n not in lex
    return bad / max(tot, 1), tot


def med_ms(recs):
    return [r["ms"] for r in recs.values() if r.get("ms") is not None]


def evaluate(data, plans, arms, lex, lex_strict):
    """يعيد {ذراع: {مجموعة: …, oov, time, pass}} لنموذجٍ واحد."""
    res = {}
    ref = "ref"
    for arm, pen in arms:
        if arm == ref:
            continue
        r = {"sets": {}}
        oa = ob = 0
        for sname in data:
            inj = SETS[sname][2]
            r["sets"][sname] = judge_set(plans[sname], data[sname][ref], data[sname][arm], inj)
        # oov مجمَّعاً (‏مقامُه كلُّ كلمات المفكوك في المجموعات الثلاث)
        for key, L in (("oov", lex), ("oov_strict", lex_strict)):
            a_b = a_t = b_b = b_t = 0
            for sname in data:
                ra, ta = oov_rate(plans[sname], data[sname][ref], L)
                rb, tb = oov_rate(plans[sname], data[sname][arm], L)
                a_b += ra * ta; a_t += ta; b_b += rb * tb; b_t += tb
            r[key] = (a_b / max(a_t, 1), b_b / max(b_t, 1))
        ma = [x for s in data for x in med_ms(data[s][ref])]
        mb = [x for s in data for x in med_ms(data[s][arm])]
        wa = [x["wall"] for s in data for x in data[s][ref].values()]
        wb = [x["wall"] for s in data for x in data[s][arm].values()]
        r["time"] = {"ref_ms": statistics.median(ma) if ma else None, "arm_ms": statistics.median(mb) if mb else None,
                     "ratio": (statistics.median(mb) / statistics.median(ma)) if ma and mb else None,
                     "wall_ratio": statistics.median(wb) / statistics.median(wa) if wa and wb else None}
        r["pass"] = decide(r)
        res[arm] = r
    return res


def decide(r):
    """المعيارُ كما كُتب: على كلّ مجموعة: أعلى Δاتّهام ≤ 0 · وعلى g3r أدنى Δكشف ≥ 0 · والزمن ≤ ×1.2 · وoov ينخفض ≥ 20 نقطة."""
    why = []
    for s, v in r["sets"].items():
        if not v["fa_ci"][1] <= 0:
            why.append(f"{s}: أعلى Δاتّهام {v['fa_ci'][1] * 100:+.2f} > 0")
        if v["det"] and not v["det"]["ci"][0] >= 0:
            why.append(f"{s}: أدنى Δكشف {v['det']['ci'][0] * 100:+.1f} < 0")
    t = r["time"]["ratio"]
    if t is None or t > TIME_MAX:
        why.append(f"الزمن ×{t:.2f} > ×{TIME_MAX}" if t is not None else "لا زمن")
    drop = r["oov"][0] - r["oov"][1]
    if drop < OOV_DROP:
        why.append(f"oov هبط {drop * 100:.1f} نقطةً < {OOV_DROP * 100:.0f}")
    return {"ok": not why, "why": why}


# ───────────────────────── التقرير ─────────────────────────

def pct(x, d=2):
    return "—" if x is None else f"{x * 100:.{d}f}٪"


def ci(lo_hi, d=2, scale=100):
    return f"[{lo_hi[0] * scale:+.{d}f} .. {lo_hi[1] * scale:+.{d}f}]"


def report(allres, arms, n_items, stats):
    md = ["# أثرُ الفكّ الموجَّه بمعجم المصحف (GBNF) — whisper-cli", "",
          "> مولَّد بـ`tools/tasmi_bench/lexbias_bench.py`؛ الخطوة 2-أ من خطة المستشار 2026-10-05. الأرقامُ على `whisper-cli` "
          "(‏whisper.cpp@c4ac001، رايات `greedy` المشحونة، q8) لا `jni.c`. الفواصلُ bootstrap عنقوديّ بالبند (95٪).",
          f"> المعجمُ: {stats.get('words', '?')} صورةً مطبَّعة (‏الروايات الستّ، صورُ الحاكم) في {stats.get('dawg_nodes', '?')} عقدةً DAWG؛ "
          f"oov يُقاس على المعجم نفسِه، و«oov صارم» على `scorer.norm` وحدَه ({stats.get('strict', '?')} كلمة).",
          "> ⚖️ المعيارُ (‏قبل القراءة): لكلّ مجموعةٍ أعلى Δاتّهام ≤ 0 · وعلى g3r أدنى Δكشف ≥ 0 · والزمن ≤ ×1.2 · وoov ينخفض ≥ 20 نقطة.", ""]
    for model, res in allres.items():
        md += [f"## النموذج `{model}`", "",
               "| الذراع | المجموعة | ن | اتّهامٌ كاذب: مرجع ⇒ ذراع | **Δاتّهام [95٪]** (نقاط) | كشف: مرجع ⇒ ذراع | **Δكشف [95٪]** (نقاط) | منهارٌ (مرجع/ذراع) |",
               "|---|---|---:|---|---|---|---|---|"]
        for arm, r in res.items():
            for s, v in r["sets"].items():
                d = v["det"]
                md.append(f"| {arm} | {s} | {v['n']} | {pct(v['fa'][0])} ⇒ {pct(v['fa'][1])} | **{v['fa_diff'] * 100:+.2f}** {ci(v['fa_ci'])} | "
                          + (f"{pct(d['arms'][0], 1)} ⇒ {pct(d['arms'][1], 1)} | **{d['diff'] * 100:+.1f}** {ci(d['ci'], 1)}" if d else "— | —")
                          + f" | {v['collapsed'][0]}/{v['collapsed'][1]} |")
        md += ["", "| الذراع | oov (مرجع ⇒ ذراع) | Δoov (نقاط) | oov صارم (مرجع ⇒ ذراع) | وسيط الزمن مرجع ⇒ ذراع (م.ث) | **نسبة الزمن** | نسبة الجدار (تحليلُ النحو داخلَها) | الحكم |",
               "|---|---|---:|---|---|---:|---:|---|"]
        for arm, r in res.items():
            t = r["time"]
            md.append(f"| {arm} | {pct(r['oov'][0], 1)} ⇒ {pct(r['oov'][1], 1)} | {(r['oov'][1] - r['oov'][0]) * 100:+.1f} | "
                      f"{pct(r['oov_strict'][0], 1)} ⇒ {pct(r['oov_strict'][1], 1)} | {t['ref_ms']:.0f} ⇒ {t['arm_ms']:.0f} | **×{t['ratio']:.2f}** | "
                      f"×{t['wall_ratio']:.2f} | {'✅ يمرّ' if r['pass']['ok'] else '⛔ لا'} |")
        md.append("")
        for arm, r in res.items():
            if not r["pass"]["ok"]:
                md.append(f"- `{arm}` يسقط: " + " · ".join(r["pass"]["why"]))
        md.append("")
    ok = [(m, a) for m, res in allres.items() for a, r in res.items() if r["pass"]["ok"]]
    md += ["## الحكم مقابل المعيار", ""]
    if ok:
        md.append("**مرّ:** " + "، ".join(f"`{m}`/{a}" for m, a in ok) + " ⇒ يُوصى بتنفيذ JNI (‏الخطوة 2ب) لهذه الأذرع.")
    else:
        md.append("**لا ذراعَ يمرّ** ⇒ يُغلق البندُ (‏النحو الكاملُ بالمعجم لا يمرّ المعيار). أسبابُ السقوط أعلاه حرفاً.")
    return "\n".join(md) + "\n"


def jsonable(x):
    if isinstance(x, dict):
        return {str(k): jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [jsonable(v) for v in x]
    return x


# ───────────────────────── اختبارٌ ذاتيّ ─────────────────────────

def selftest():
    import tempfile
    # ① قراءةُ الزمن من سجلّ whisper
    err = "whisper_print_timings:     load time =   120.50 ms\nwhisper_print_timings:    total time =  1500.25 ms\n"
    tm = {k: float(v) for k, v in _T.findall(err)}
    assert tm == {"load": 120.5, "total": 1500.25}, tm
    # ② الاستئنافُ: سجلٌّ مخزَّنٌ يُقرأ بلا تشغيل
    d = tempfile.mkdtemp()
    base = os.path.join(d, "x")
    json.dump({"text": "قول", "ms": 5.0, "wall": 9.0}, open(base + ".json", "w", encoding="utf-8"), ensure_ascii=False)
    assert run_one("/nonexistent", "m", "w", base, None, None, 1)["text"] == "قول"
    # ③ oov: كلمةٌ خارجَ المعجم تُحسب، والتشكيلُ يُطبَّع
    lex = {"الحمد", "لله"}
    plan = [{"id": "a", "riwaya": "hafs"}]
    rate, n = oov_rate(plan, {"a": {"text": "الْحَمْدُ لله سيارة"}}, lex)
    assert n == 3 and abs(rate - 1 / 3) < 1e-9, (rate, n)
    # ④ حكمُ g2: ذراعٌ يزيد الاتّهامَ فيُرفَض، وذراعٌ يخفضه ويمرّ على g2
    ref_t = "الحمد لله رب العالمين الرحمن الرحيم مالك يوم الدين"
    items = [{"id": f"i{k}", "refText": ref_t, "riwaya": "hafs"} for k in range(30)]
    good = {it["id"]: {"text": ref_t, "ms": 10.0, "wall": 12.0} for it in items}
    worse = {it["id"]: {"text": "الحمد لله رب العالمين سيارة كتاب مالك يوم الدين", "ms": 10.0, "wall": 12.0} for it in items}
    v = judge_set(items, good, worse, False)
    assert v["fa_diff"] > 0 and v["fa_ci"][0] > 0, v
    v2 = judge_set(items, worse, good, False)
    assert v2["fa_diff"] < 0 and v2["fa_ci"][1] < 0, v2
    # ⑤ القرارُ: سقوطٌ بالزمن وبoov يُسمّى سببُه
    r = {"sets": {"g2": {"fa_ci": (-0.02, -0.01), "det": None}}, "time": {"ratio": 1.5}, "oov": (0.63, 0.50)}
    p = decide(r)
    assert not p["ok"] and len(p["why"]) == 2, p
    r["time"]["ratio"] = 1.1
    r["oov"] = (0.63, 0.30)
    assert decide(r)["ok"]
    r["sets"]["g2"]["fa_ci"] = (-0.02, 0.001)
    assert not decide(r)["ok"]
    print("✅ lexbias_bench selftest: 5 فحوص نجحت")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--cli")
    ap.add_argument("--models")
    ap.add_argument("--grammar", help="mushaf.gbnf")
    ap.add_argument("--words", help="قائمةُ المعجم (كلمةٌ في السطر) لحساب oov")
    ap.add_argument("--strict-words", default="", help="معجمٌ صارمٌ (‏scorer.norm وحدَه) لـ«oov صارم»؛ وإلا يُشتقّ من المعجم نفسِه")
    ap.add_argument("--penalties", default="2,4,8")
    ap.add_argument("--sets", default="g3rn,g3rc,g2")
    ap.add_argument("--threads", type=int, default=1)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workdir", default=os.path.join(WORK, "lexbias"))
    ap.add_argument("--stats", default="", help="ملفُّ إحصاءات المولّد (json) يُذكر في التقرير")
    ap.add_argument("--md", default="")
    ap.add_argument("--json", default="")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if not (a.cli and a.models and a.grammar and a.words):
        ap.error("--cli و--models و--grammar و--words لازمة")
    lex = {w.strip() for w in open(a.words, encoding="utf-8") if w.strip()}
    strict = ({w.strip() for w in open(a.strict_words, encoding="utf-8") if w.strip()} if a.strict_words else lex)
    arms = [("ref", None)] + [(f"P{p}", float(p)) for p in a.penalties.split(",") if p]
    sets = [s for s in a.sets.split(",") if s]
    allres = {}
    for pair in a.models.split(","):
        name, path = pair.split("=", 1)
        data, plans = collect(a.cli, name, path, arms, sets, a.workdir, a.threads, a.workers, a.limit, a.grammar)
        allres[name] = evaluate(data, plans, arms, lex, strict)
    stats = json.load(open(a.stats, encoding="utf-8")) if a.stats and os.path.exists(a.stats) else {}
    stats["strict"] = len(strict)
    md = report(allres, arms, a.limit, stats)
    print(md)
    if a.md:
        open(a.md, "w", encoding="utf-8").write(md)
    if a.json:
        json.dump(jsonable(allres), open(a.json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
