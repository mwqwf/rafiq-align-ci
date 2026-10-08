# -*- coding: utf-8 -*-
"""🎯 **المحاذاةُ القسريّة بالاحتمالات حكماً على كلمات المتعلّم** — الخطوة 2-ب/2ج من خطة المستشار 2026-10-05 (البند 6).

الفكرة: يُرمَّز الصوتُ مرّةً، ثمّ يُفكّ **قسراً** تسلسلُ رموز النصّ المتوقَّع (`rafiq_forced.cpp` فوق `whisper_decode`)
فيُؤخذ لكلّ رمزٍ `lp` (لوغاريتمُ احتمال المتوقَّع) و`top` (أقوى رمزٍ نصّيّ مسموع) و`alt` (أقوى بديلٍ غيرِ المتوقَّع).
ودرجةُ الكلمة (‏كلّها متوسّطُ رموزها):
- **gap = متوسّط (top − lp)**: لوغاريتمُ نسبةِ احتمال «المسموع» إلى «المتوقَّع» (‏0 حين المتوقَّعُ هو الأقوى) — **الإحصاءُ الأوّل المعلَن**.
- **margin = متوسّط (alt − lp)**: النسخةُ المتّصلة منه (‏لا تعادلَ عند الصفر) — للاستئناس.
- **nlp = متوسّط (−lp)**: سالبُ لوغاريتم احتمال المتوقَّع وحدَه.
- ومعها صورُ «الأسوأ رمزاً» (‏max بدل المتوسط).
**عالي الدرجة ⇒ أرجح أنّ الكلمةَ خاطئة.** هذا يختلف عن GOP الفونيميّ المرفوض سابقاً (‏لا مصفوفةَ فونيمات هنا؛ احتمالاتُ رموز النموذج نفسِه).

## التسمية (‏مكتوبةٌ قبل القراءة)
على g3r (‏خطأٌ مصنوعٌ معلومُ الموضع من `inject_plan_riwaya.json`):
- **موجَب** (‏الكلمةُ خاطئةٌ فعلاً): OMIT/SUBSTITUTE: `wordIndex` · SWAP: `wordIndex` و`+1` · INSERT: النطاقُ كلُّه ±1 (‏لا كلمةَ مرجعيّةَ بعينها خاطئة).
- **سالب**: كلُّ كلمةٍ **خارجَ** نطاق الحقن ±1 (`detect_score.zone`)؛ وجارةُ الخطأ غيرُ الخاطئة تُستبعد من الأوّل ولا تدخل الثاني.
- AUC ثانٍ «النطاق»: موجَبُه النطاقُ كلُّه.

## النصُّ المُفكَّك قسراً (‏ثلاثُ صور، تُقاس كلُّها ويُعلَن الأساسُ قبل القراءة)
النموذجُ المشحون يكتب **بالتشكيل** (‏«وَلَا أَنَا عَابِدٌ») فتشكيلُ المرجع الخام (رسمُ ورش/قالون) قد يكون بعيداً عن أسلوبه:
- `plain`: المطبَّع (`scorer.norm`) بلا تشكيل — أبعدُها عن أسلوب النموذج.
- `raw`: النصُّ المرجعيُّ الخام كما هو.
- `tash`: تشكيلٌ خفيفٌ — حذفُ علامات الوقف والأحرف الصغيرة والخنجريّة، وتوحيدُ التنوين.
**الأساس المعلَن = `tash`** (‏اختير على عيّنةٍ تطويريّة صغيرة بمتوسّط lp للكلمات السالبة فقط، لا بالتمييز).

## المعيار (‏قبل القراءة)
**AUC ≥ 0.80** لإحصاء gap في الصورة الأساس على **g3r المضجَّج** (‏موجَبٌ مقابل سالب)، ويُقرأ **حدُّ المجال الأدنى** أيضاً؛ وإلا يُغلق البند بأرقامه.
المجالُ 95٪ bootstrap عنقوديّ بالبند (‏يُعاد سحبُ البنود لا الكلمات).

⛔ أداةُ قياسٍ فقط: لا عتبةَ حاكمٍ تُمسّ ولا نصَّ قرآنٍ يُولَّد. ‏`rafiq_forced` لا يُشحن.

    python tools/tasmi_bench/forced_auc.py --bin wc/rafiq_forced --models tiny=m.bin,base=m2.bin --md o.md --json o.json
    python tools/tasmi_bench/forced_auc.py --selftest
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import detect_score as D  # noqa: E402
import scorer  # noqa: E402
import token_conf_auc as T  # noqa: E402

WORK = os.path.join(HERE, "work")
SETS = {"g3rn": "g3rn", "g3rc": "g3rc"}
VARIANTS = ["plain", "raw", "tash"]
PRIMARY_VARIANT = "tash"
STATS = ["gap", "margin", "nlp", "gap_max", "nlp_max"]
PRIMARY_STAT = "gap"
BAR = 0.80

# ───────────────────────── صورُ النصّ ─────────────────────────

_DROP = re.compile("[ـۖ-ۜ۟-۪ۨ-ٰۭٕ࣓ٔ-ࣿ]")


def tash(word):
    """تشكيلٌ خفيفٌ على أسلوب النموذج: يحذف الوقفَ والأحرفَ الصغيرة والخنجريّة، ويوحّد التنوين وياءَ ورش."""
    w = word.replace("ٞ", "ٌ").replace("ٗ", "ٌ").replace("ٖ", "ٍ")
    w = w.replace("ے", "ي")
    return _DROP.sub("", w)


def text_forms(refw, cfg):
    return {"plain": scorer.norm(refw, cfg), "raw": refw, "tash": tash(refw)}


# ───────────────────────── تشغيل الأداة ─────────────────────────

def run_forced(binp, model, wav, forms, threads, ts, free):
    """يشغّل `rafiq_forced` على صوتٍ واحد بصورِ النصّ الثلاث ويعيد JSON."""
    with tempfile.TemporaryDirectory() as td:
        args = [binp, "-m", model, "-f", wav, "-t", str(threads)]
        for v in VARIANTS:
            p = os.path.join(td, v + ".txt")
            with open(p, "w", encoding="utf-8") as f:
                f.write("\n".join(forms[v]) + "\n")
            args += ["-w", p]
        if ts:
            args.append("--ts")
        if free:
            args.append("--free")
        p = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if p.returncode != 0 or not p.stdout.strip():
            raise SystemExit(f"⛔ rafiq_forced سقط على {os.path.basename(wav)} (رمز {p.returncode}):\n{(p.stderr or '')[-400:]}")
        return json.loads(p.stdout)


def word_scores(w):
    """درجاتُ كلمةٍ من سجلّ رموزها."""
    n = max(len(w["lp"]), 1)
    gaps = [t - l for t, l in zip(w["top"], w["lp"])]
    marg = [a - l for a, l in zip(w["alt"], w["lp"])]
    nlp = [-l for l in w["lp"]]
    return {"gap": sum(gaps) / n, "margin": sum(marg) / n, "nlp": sum(nlp) / n,
            "gap_max": max(gaps), "nlp_max": max(nlp)}


def label_of(it, k):
    """«pos» (‏خاطئةٌ فعلاً) · «neg» (‏خارج النطاق) · «near» (‏جارةٌ في النطاق) ⇒ ويُعاد معه «zone» منطقيّاً."""
    lo, hi = D.zone(it)
    in_zone = lo <= k <= hi
    wi, op = it["wordIndex"], it["op"]
    if op in ("OMIT", "SUBSTITUTE"):
        exact = k == wi
    elif op == "SWAP":
        exact = k in (wi, wi + 1)
    else:   # INSERT: لا كلمةَ مرجعيّةَ بعينها ⇒ النطاقُ كلُّه
        exact = in_zone
    return ("pos" if exact else "near") if in_zone else "neg", in_zone


def collect(binp, model_name, model, sets, threads, workers, limit, ts, free, plan="inject_plan_riwaya.json", ops=None):
    recs, times = [], []
    for sname in sets:
        folder = SETS[sname]
        d = os.path.join(WORK, folder)
        if not os.path.isdir(d):
            raise SystemExit(f"⛔ لا مجلدَ {d} — المجموعةُ {sname} لم تُبنَ")
        items = [it for it in T.load_plan(plan) if (not ops or it["op"] in ops) and os.path.exists(os.path.join(d, it["id"] + ".wav"))]
        if limit:
            items = items[:limit]
        if not items:
            raise SystemExit(f"⛔ المجموعةُ {sname} بلا ملفّات")
        print(f"▶ {model_name} · {sname}: {len(items)} بنداً", flush=True)

        def one(it):
            cfg = D.cfg_for(it.get("riwaya"))
            ref = it["refText"].split()
            forms = {v: [] for v in VARIANTS}
            keep = []
            for k, rw in enumerate(ref):
                f = text_forms(rw, cfg)
                if all(f[v] for v in VARIANTS):
                    keep.append(k)
                    for v in VARIANTS:
                        forms[v].append(f[v])
            return it, keep, run_forced(binp, model, os.path.join(d, it["id"] + ".wav"), forms, threads, ts, free)

        with ThreadPoolExecutor(max_workers=workers) as ex:
            res = list(ex.map(one, items))
        for it, keep, js in res:
            times.append({"set": sname, "enc_ms": js["enc_ms"], "mel_ms": js["mel_ms"], "forced_ms": js["forced_ms"] / len(VARIANTS),
                          "free_ms": js["free_ms"], "n_samples": js["n_samples"]})
            vs = dict(zip(VARIANTS, js["variants"]))
            # سجلُّ بندٍ (لا كلمة): التفريغُ الحرّ والأزمنة — يقرؤه `forced_veto.py`؛ والتلخيصُ يتجاهله (‏label=meta)
            recs.append({"set": sname, "item": it["id"], "k": -1, "op": it["op"], "label": "meta", "zone": False, "sc": {},
                         "free_text": js.get("free_text", ""), "free_ms": js["free_ms"], "enc_ms": js["enc_ms"],
                         "forced_ms": js["forced_ms"] / len(VARIANTS), "n_samples": js["n_samples"]})
            for pos, k in enumerate(keep):
                lab, in_zone = label_of(it, k)
                rec = {"set": sname, "item": it["id"], "k": k, "op": it["op"], "label": lab, "zone": in_zone, "sc": {}}
                for v in VARIANTS:
                    rec["sc"][v] = word_scores(vs[v]["words"][pos])
                recs.append(rec)
    return recs, times


# ───────────────────────── التلخيص ─────────────────────────

def summarize(recs, variant, stat, mode="exact", n_boot=2000):
    """AUC (‏عالٍ ⇒ خاطئ). mode=exact: موجَبٌ بعينه مقابل سالب · zone: النطاقُ كلُّه مقابل سالب."""
    by_item = {}
    for r in recs:
        if mode == "zone":
            if not r["zone"] and r["label"] != "neg":
                continue
            lab = "pos" if r["zone"] else "neg"
        else:
            if r["label"] not in ("pos", "neg"):
                continue
            lab = r["label"]
        pos, neg = by_item.setdefault(r["item"], ([], []))
        (pos if lab == "pos" else neg).append(r["sc"][variant][stat])
    pos = [v for a, _ in by_item.values() for v in a]
    neg = [v for _, b in by_item.values() for v in b]
    a = T.auc(pos, neg)
    return {"auc": a, "ci": T.boot_auc(by_item, n_boot) if a is not None else None,
            "n_pos": len(pos), "n_neg": len(neg),
            "med_pos": T.percentile(pos, .5), "med_neg": T.percentile(neg, .5)}


def by_op(recs, variant, stat, n_boot=500):
    out = {}
    for op in ("OMIT", "SUBSTITUTE", "SWAP", "INSERT"):
        sub = [r for r in recs if r["op"] == op]
        if sub:
            out[op] = summarize(sub, variant, stat, "exact", n_boot)
    return out


def timing(times):
    if not times:
        return None
    n = len(times)
    avg = lambda key: sum(t[key] for t in times) / n
    free = [t["free_ms"] for t in times if t["free_ms"] >= 0]
    return {"n": n, "mel_ms": avg("mel_ms"), "enc_ms": avg("enc_ms"), "forced_ms": avg("forced_ms"),
            "free_ms": (sum(free) / len(free)) if free else None, "secs": avg("n_samples") / 16000}


def fmt(s):
    if s["auc"] is None:
        return "—"
    ci = f" [{s['ci'][0]:.3f}, {s['ci'][1]:.3f}]" if s["ci"] else " [—]"
    return f"{s['auc']:.3f}{ci}"


def report(allrecs, alltimes, n_boot=2000, mode_note=""):
    groups = [("g3r مضجَّج", ["g3rn"]), ("g3r نظيف", ["g3rc"]), ("g3r كلُّه", ["g3rn", "g3rc"])]
    md = ["# المحاذاةُ القسريّة بالاحتمالات — AUC تمييز الكلمات الخاطئة فعلاً", "",
          "> مولَّد بـ`tools/tasmi_bench/forced_auc.py` + `rafiq_forced.cpp` (‏خطوة 2-ب/2ج من خطة المستشار 2026-10-05). **عالي الدرجة ⇒ كلمةٌ خاطئة.**",
          "> الإحصاءُ الأساس **gap** = متوسّط (أقوى رمزٍ مسموع − المتوقَّع) بلوغاريتم الاحتمال؛ الصورةُ الأساس **tash**؛ المجالُ bootstrap عنقوديّ بالبند.",
          "> الأرقامُ على whisper.cpp@c4ac001 (‏CPU بلا أندرويد) لا على محرك الهاتف. " + mode_note, ""]
    res = {}
    for model, recs in allrecs.items():
        res[model] = {"primary": {}, "variants": {}, "ops": {}}
        md += [f"## النموذج `{model}`", "",
               f"### الأساس: صورة `{PRIMARY_VARIANT}` · إحصاء `{PRIMARY_STAT}`", "",
               "| المجموعة | AUC (موجَبٌ بعينه) [95٪] | AUC (النطاق كلُّه) [95٪] | موجَب | سالب | وسيط الدرجة موجَب/سالب |",
               "|---|---|---|---:|---:|---|"]
        for label, sets in groups:
            sub = [r for r in recs if r["set"] in sets]
            if not sub:
                continue
            s1 = summarize(sub, PRIMARY_VARIANT, PRIMARY_STAT, "exact", n_boot)
            s2 = summarize(sub, PRIMARY_VARIANT, PRIMARY_STAT, "zone", n_boot)
            md.append(f"| {label} | **{fmt(s1)}** | {fmt(s2)} | {s1['n_pos']} | {s1['n_neg']} | "
                      f"{T._f3(s1['med_pos'])} / {T._f3(s1['med_neg'])} |")
            res[model]["primary"][label] = {"exact": s1, "zone": s2}
        # كلُّ الصور × كلُّ الإحصاءات على المضجَّج (للاستئناس)
        noisy = [r for r in recs if r["set"] == "g3rn"]
        if noisy:
            md += ["", "#### كلُّ الصور والإحصاءات على g3r المضجَّج (‏موجَبٌ بعينه)", "",
                   "| الصورة | " + " | ".join(STATS) + " |", "|---|" + "---|" * len(STATS)]
            for v in VARIANTS:
                cells = []
                for st in STATS:
                    s = summarize(noisy, v, st, "exact", 500)
                    cells.append(fmt(s))
                    res[model]["variants"].setdefault(v, {})[st] = s
                md.append(f"| {v} | " + " | ".join(cells) + " |")
            ops = by_op(noisy, PRIMARY_VARIANT, PRIMARY_STAT)
            res[model]["ops"] = ops
            md += ["", f"#### بحسب نوع الحقن (‏مضجَّج · `{PRIMARY_VARIANT}`/`{PRIMARY_STAT}`)", "",
                   "| النوع | AUC [95٪] | موجَب | سالب |", "|---|---|---:|---:|"]
            for op, s in ops.items():
                md.append(f"| {op} | {fmt(s)} | {s['n_pos']} | {s['n_neg']} |")
        tm = timing(alltimes.get(model, []))
        if tm:
            res[model]["timing"] = tm
            extra = f" · الحرّ كاملاً (‏mel+ترميز+فكّ) {tm['free_ms']:.0f} م.ث" if tm["free_ms"] is not None else ""
            md += ["", f"**الزمن** (‏متوسّط بند، {tm['secs']:.1f} ث صوتاً، ن={tm['n']}): mel {tm['mel_ms']:.0f} م.ث · ترميز {tm['enc_ms']:.0f} م.ث · "
                   f"**الفكّ القسريّ (‏صورةٌ واحدة) {tm['forced_ms']:.0f} م.ث**{extra}.", ""]
    return "\n".join(md) + "\n", res


def verdict(res):
    lines = [f"## الحكم مقابل المعيار (AUC ≥ {BAR:.2f} على g3r المضجَّج · `{PRIMARY_VARIANT}`/`{PRIMARY_STAT}`)", ""]
    for model, r in res.items():
        g = r["primary"].get("g3r مضجَّج")
        if not g or g["exact"]["auc"] is None:
            lines.append(f"- `{model}`: لا قياسَ كافياً ⇒ لا حكم.")
            continue
        a, ci = g["exact"]["auc"], g["exact"]["ci"]
        if a >= BAR and ci and ci[0] >= BAR:
            v = "**يُوصى بالمتابعة** (‏الحدُّ الأدنى للمجال ≥ المعيار أيضاً)"
        elif a >= BAR:
            v = "**يُوصى بتحفّظ**: النقطةُ ≥ المعيار لكنّ المجالَ يعبره"
        else:
            v = f"**يُغلق البند** (‏AUC دون {BAR:.2f})"
        lines.append(f"- `{model}`: AUC = {a:.3f}" + (f" [{ci[0]:.3f}, {ci[1]:.3f}]" if ci else "") + f" ⇒ {v}")
    return "\n".join(lines) + "\n"


# ───────────────────────── اختبارٌ ذاتيّ (بلا أداة ولا شبكة) ─────────────────────────

def selftest():
    # ① tash: يحذف علامات الوقف والخنجريّة ويوحّد التنوين
    assert tash("عَابِدٞ") == "عَابِدٌ", tash("عَابِدٞ")
    assert tash("لَّٰ") == "لَّ" or "ٰ" not in tash("لَّٰ")
    assert "ۖ" not in tash("ءَامَنُواْۖ")
    # ② word_scores
    w = {"lp": [-1.0, -3.0], "alt": [-0.5, -0.1], "top": [-0.5, -0.1]}
    s = word_scores(w)
    assert abs(s["gap"] - 1.7) < 1e-9 and abs(s["nlp"] - 2.0) < 1e-9 and abs(s["nlp_max"] - 3.0) < 1e-9, s
    w2 = {"lp": [-0.2], "alt": [-5.0], "top": [-0.2]}
    assert word_scores(w2)["gap"] == 0 and word_scores(w2)["margin"] < 0   # المتوقَّعُ هو الأقوى
    # ③ التسمية
    base = {"wordIndex": 3, "op": "OMIT"}
    assert label_of(base, 3)[0] == "pos" and label_of(base, 2)[0] == "near" and label_of(base, 5)[0] == "neg"
    sw = {"wordIndex": 3, "op": "SWAP"}
    assert [label_of(sw, k)[0] for k in (1, 2, 3, 4, 5, 6)] == ["neg", "near", "pos", "pos", "near", "neg"], [label_of(sw, k) for k in range(1, 7)]
    ins = {"wordIndex": 3, "op": "INSERT"}
    assert [label_of(ins, k)[0] for k in (1, 2, 3, 4, 5)] == ["neg", "pos", "pos", "pos", "neg"]
    # ④ summarize: فصلٌ تامٌّ ⇒ 1 · الجارةُ تُستبعد من الأساس وتدخل «النطاق»
    recs = []
    for n in range(30):
        for k, lab, z, g in ((0, "neg", False, 0.1), (1, "near", True, 0.2), (2, "pos", True, 5.0)):
            recs.append({"set": "g3rn", "item": f"i{n}", "k": k, "op": "OMIT", "label": lab, "zone": z,
                         "sc": {v: {st: g for st in STATS} for v in VARIANTS}})
    s1 = summarize(recs, "tash", "gap", "exact", 100)
    assert s1["auc"] == 1.0 and s1["n_pos"] == 30 and s1["n_neg"] == 30, s1
    s2 = summarize(recs, "tash", "gap", "zone", 100)
    assert s2["n_pos"] == 60 and s2["auc"] == 1.0, s2
    md, res = report({"tiny": recs}, {"tiny": [{"set": "g3rn", "enc_ms": 800, "mel_ms": 20, "forced_ms": 240, "free_ms": 900, "n_samples": 160000}]}, 100)
    assert "AUC" in md and "يُوصى" in verdict(res), verdict(res)
    # ⑤ قارئ wav: يُختبر مع الأداة في السير (‏هنا لا ثنائيّ)
    print("✅ forced_auc selftest: 5 فحوص نجحت")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--bin")
    ap.add_argument("--models", help="اسم=مسار، مفصولةً بفواصل")
    ap.add_argument("--sets", default="g3rn,g3rc")
    ap.add_argument("--threads", type=int, default=1)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--boot", type=int, default=2000)
    ap.add_argument("--ts", action="store_true", help="مطالعُ الزمن <|0.00|> بدل notimestamps")
    ap.add_argument("--free", action="store_true", help="يقيس الفكَّ الحرَّ أيضاً (‏للزمن)")
    ap.add_argument("--plan", default="inject_plan_riwaya.json", help="خطةُ الحقن (‏في مجلد الأداة)")
    ap.add_argument("--ops", default="", help="‏يقصر البنود على هذه الأنواع (‏OMIT,SUBSTITUTE)")
    ap.add_argument("--variants", default="", help="‏يقصر صورَ النصّ (‏tash) لتوفير الزمن؛ الافتراضُ الثلاث")
    ap.add_argument("--md", default="")
    ap.add_argument("--json", default="")
    ap.add_argument("--words", default="")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if not a.bin or not a.models:
        ap.error("--bin و--models لازمان")
    sets = [s for s in a.sets.split(",") if s]
    if a.variants:
        global VARIANTS
        VARIANTS = [v for v in a.variants.split(",") if v in ("plain", "raw", "tash")]
    allrecs, alltimes = {}, {}
    for pair in a.models.split(","):
        name, path = pair.split("=", 1)
        if not os.path.exists(path):
            raise SystemExit(f"⛔ لا نموذجَ في {path}")
        allrecs[name], alltimes[name] = collect(a.bin, name, path, sets, a.threads, a.workers, a.limit, a.ts, a.free,
                                                     a.plan, set(x for x in a.ops.split(',') if x))
    md, res = report(allrecs, alltimes, a.boot, "مطالعُ الزمن." if a.ts else "مطالعُ notimestamps.")
    md += "\n" + verdict(res)
    print(md)
    if a.md:
        open(a.md, "w", encoding="utf-8").write(md)
    if a.json:
        json.dump(res, open(a.json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if a.words:
        json.dump(allrecs, open(a.words, "w", encoding="utf-8"), ensure_ascii=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
