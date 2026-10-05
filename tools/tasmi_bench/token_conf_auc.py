# -*- coding: utf-8 -*-
"""🎯 **أتفصل ثقةُ الرموز `p` الاتّهامَ الصادقَ عن الكاذب؟** — خطوة 1 من خطة المستشار 2026-10-05 (توصية 2-ج).

المشكلة: الحكمُ كلُّه نصّيّ (مسافةُ تحرير)، وثقةُ النموذج في كلّ رمزٍ (`whisper_token_data.p`) تُحسب وتُصدَّر ثم تُرمى.
فهل **كلمةٌ متّهمةٌ برمزٍ ضعيفِ الثقة** أقربُ إلى «اتّهامٍ كاذب» (النموذجُ لم يتبيّن) منها إلى «خطأٍ حقيقيّ» (سمع ما قيل)؟

الطريقة (بأدوات العدّة نفسِها لا بمحاذاةٍ جديدة):
1. `whisper-cli -ojf` (JSON كاملٌ بـ`p` لكلّ رمز) على بنود:
   - **g3r** (‏`g3rn` مضجَّج · `g3rc` نظيف · خطأٌ **مصنوعٌ معلومُ الموضع** من `inject_plan_riwaya.json`) — فيه الاتّهامُ الصادقُ والكاذب.
   - **g1** (‏`wav` نظيف) و**g2** (‏`wavn` = `noise-fan-5`) من `sample.json` — تلاواتٌ صحيحةٌ بالافتراض ⇒ **كلُّ اتّهامٍ فيها كاذب**.
   بالرايات المشحونة (‏`-l en -bs 1 -et 2.40`، مرآةُ ذراع `greedy` في `cli_time.py`).
2. كلماتُ المفكوك = الرموزُ بين بدايتَي كلمةٍ (‏رمزٌ يبدأ بمسافة)، و`p` الكلمة = **متوسّطُ `p` لرموزها** (‏ويُحسب الأدنى للاستئناس).
3. المحاذاةُ والحكم: `scorer.score` نفسُه بـ`detect_score.cfg_for` (‏كما يفعل `v2_gate.judge_arm`: بندٌ يُطلق حارسَ الانهيار 0.60 لا يُحسب).
   المتّهَمُ = `MISSED` أو `SUBSTITUTED`. **صادقٌ** = داخل نطاق الحقن ±1 (‏`detect_score.zone`)، **كاذبٌ** = خارجَه (‏وكلُّ اتّهامٍ في g1/g2).
4. AUC لمتوسّط `p` (‏**عالٍ ⇒ صادق**) على الكلمات المتّهمة **ذاتِ الكلمة المسموعة** (‏`SUBSTITUTED`)، بمجال 95٪ **bootstrap عنقوديّ بالبند**.
   ⛔ `MISSED` لا كلمةَ مسموعةً فيها فلا `p` لها — **تُعَدّ ولا تُحسب في AUC** وتُقال نسبتُها.
5. **τ = المئين العاشر لـ`p` على الكلمات الصحيحة** (‏`CORRECT`)، ومعه أثرُه: كم صادقاً يُفقد وكم كاذباً يُزال لو صار «p<τ ⇒ غير متبيَّن».

⚖️ **معيار القرار (المستشار):** AUC ≥ 0.75 ⇒ يُوصى بالخطوة 1ب (`ReciteFollower` بالكلمات الموقوتة و`UNCERTAIN`)؛ وإلا يُغلق البند.
⛔ لا عتبةَ حاكمٍ تُمسّ هنا ولا نصَّ قرآنٍ يُولَّد: أداةُ قياسٍ فقط.

    python tools/tasmi_bench/token_conf_auc.py --cli wc/b/bin/whisper-cli --models tiny=work_tiny.bin,base=work_base.bin --md out.md --json out.json
    python tools/tasmi_bench/token_conf_auc.py --selftest
"""
import argparse
import json
import os
import random
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import detect_score as D  # noqa: E402
import scorer  # noqa: E402

WORK = os.path.join(HERE, "work")
CONF = {scorer.MISSED, scorer.SUBSTITUTED}
COLLAPSE = 0.60
FLAGS = ["-l", "en", "-bs", "1", "-et", "2.40"]   # ⛔ مرآةُ ذراع `greedy` المشحون في cli_time.py
# المجموعةُ ← (مجلد الصوت، ملفُّ الخطّة، هل فيها خطأٌ محقون؟)
SETS = {
    "g3rn": ("g3rn", "inject_plan_riwaya.json", True),
    "g3rc": ("g3rc", "inject_plan_riwaya.json", True),
    "g1": ("wav", "sample.json", False),
    "g2": ("wavn", "sample.json", False),
}


# ───────────────────────── JSON ⇒ كلماتٌ بـ`p` ─────────────────────────

def parse_words(js):
    """يعيد قائمةً من `{"w": نصُّ الكلمة, "p": متوسّطُ p, "pmin": أدناه, "n": عددُ الرموز}` من JSON `-ojf`.

    الرمزُ الخاصّ (‏`[_BEG_]` · `[_TT_…]` · `<|…|>`) يُتخطّى؛ والكلمةُ تبدأ برمزٍ أوّلُه مسافةٌ أو أوّلَ المقطع.
    """
    words = []
    for seg in js.get("transcription", []):
        cur = None
        for tok in seg.get("tokens", []):
            t = tok.get("text", "")
            if t.startswith("[_") or t.startswith("<|"):
                continue
            p = float(tok.get("p", 0.0))
            if t.startswith(" ") or cur is None:
                if cur is not None:
                    words.append(cur)
                cur = None
                body = t.strip()
                if not body:
                    continue
                cur = {"w": body, "ps": [p]}
            else:
                cur["w"] += t
                cur["ps"].append(p)
        if cur is not None:
            words.append(cur)
    out = []
    for c in words:
        w = re.sub(r"\s+", "", c["w"])
        if w:
            out.append({"w": w, "p": sum(c["ps"]) / len(c["ps"]), "pmin": min(c["ps"]), "n": len(c["ps"])})
    return out


def judge_item(it, words, cfg):
    """يحاذي كلماتِ المفكوك بالمرجع **بـ`scorer.score`** ويعيد سجلَّ كلّ كلمةٍ مرجعيّة: الحكمُ والكلمةُ المسموعةُ و`p`.

    ⛔ بندٌ يُطلق حارسَ الانهيار (‏>0.60 اتّهاماً) يُعاد `None` — كما يفعل `v2_gate.judge_arm`: لا اتّهامَ يُعرض ولا يُحسب.
    """
    hyp_text = " ".join(w["w"] for w in words)
    ref = it["refText"].split()
    s = scorer.score(ref, hyp_text, cfg)
    ws = s["words"]
    if sum(1 for w in ws if w[1] in CONF) / max(len(ws), 1) > COLLAPSE:
        return None
    # فهرسُ الكلمة المسموعة بعد مصفاة `norm` (‏كما تصنعها `scorer.score`) ← فهرسِها في قائمتي
    kept = [k for k, w in enumerate(words) if scorer.norm(w["w"], cfg)]
    out = []
    for k, (idx, state, heard) in enumerate(ws):
        h = s["hyp_idx"][k]
        hw = words[kept[h]] if h is not None and h < len(kept) else None
        out.append({"k": k, "state": state, "heard": heard, "p": hw["p"] if hw else None,
                    "pmin": hw["pmin"] if hw else None})
    return out


# ───────────────────────── AUC وbootstrap ─────────────────────────

def auc(pos, neg):
    """AUC بالرُّتَب (‏تعادلٌ = نصف). `None` إن غاب صنفٌ."""
    if not pos or not neg:
        return None
    allv = sorted([(v, 1) for v in pos] + [(v, 0) for v in neg])
    ranks = {}
    i = 0
    n = len(allv)
    while i < n:
        j = i
        while j + 1 < n and allv[j + 1][0] == allv[i][0]:
            j += 1
        ranks[allv[i][0]] = (i + j) / 2 + 1
        i = j + 1
    rp = sum(ranks[v] for v in pos)
    return (rp - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg))


def boot_auc(by_item, n_boot=2000, seed=7):
    """`by_item`: بندٌ ← (قائمةُ p الصادقة، قائمةُ p الكاذبة). مجال 95٪ بإعادة سحب **البنود**."""
    ids = list(by_item)
    rnd = random.Random(seed)
    vals = []
    for _ in range(n_boot):
        pos, neg = [], []
        for _ in ids:
            a, b = by_item[ids[rnd.randrange(len(ids))]]
            pos += a
            neg += b
        v = auc(pos, neg)
        if v is not None:
            vals.append(v)
    if len(vals) < 50:
        return None
    vals.sort()
    return vals[int(0.025 * len(vals))], vals[int(0.975 * len(vals)) - 1]


def percentile(xs, q):
    xs = sorted(xs)
    if not xs:
        return None
    k = (len(xs) - 1) * q
    f = int(k)
    c = min(f + 1, len(xs) - 1)
    return xs[f] + (xs[c] - xs[f]) * (k - f)


# ───────────────────────── تشغيل whisper-cli ─────────────────────────

def run_cli(cli, model, wav, out_base, threads):
    jp = out_base + ".json"
    if os.path.exists(jp) and os.path.getsize(jp) > 0:
        return jp   # استئناف
    os.makedirs(os.path.dirname(out_base), exist_ok=True)
    cmd = [cli, "-m", model, "-t", str(threads), "-ojf", "-of", out_base, "-np"] + FLAGS + [wav]
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = (p.stdout or "") + (p.stderr or "")
    if "usage:" in out and "error:" in out:
        raise SystemExit(f"⛔ الأداةُ ردّت الاستعمالَ لا نتيجةً (رايةٌ غيرُ مدعومة): {out[:300]}")
    if not os.path.exists(jp):
        raise SystemExit(f"⛔ لا JSON لـ{os.path.basename(wav)} (رمز {p.returncode}):\n{out[-400:]}")
    return jp


def load_plan(name):
    return json.load(open(os.path.join(HERE, name), encoding="utf-8"))["items"]


def collect(cli, model_name, model, sets, workdir, threads, workers, limit):
    """يفكّ كلَّ بنود المجموعات ويعيد سجلّاتِ الكلمات: قائمةً من dict (مجموعة، بند، حكم، p…)."""
    recs = []
    skipped = {}
    for sname in sets:
        folder, plan_name, injected = SETS[sname]
        d = os.path.join(WORK, folder)
        if not os.path.isdir(d):
            raise SystemExit(f"⛔ لا مجلدَ {d} — المجموعةُ {sname} لم تُبنَ (‏ولا يُقاس على فراغ)")
        items = [it for it in load_plan(plan_name) if os.path.exists(os.path.join(d, it["id"] + ".wav"))]
        if limit:
            items = items[:limit]
        if not items:
            raise SystemExit(f"⛔ المجموعةُ {sname} بلا ملفّات")
        print(f"▶ {model_name} · {sname}: {len(items)} بنداً", flush=True)

        def one(it):
            jp = run_cli(cli, model, os.path.join(d, it["id"] + ".wav"),
                         os.path.join(workdir, model_name, sname, it["id"]), threads)
            return it, json.load(open(jp, encoding="utf-8", errors="replace"))

        with ThreadPoolExecutor(max_workers=workers) as ex:
            results = list(ex.map(one, items))
        for it, js in results:
            words = parse_words(js)
            cfg = D.cfg_for(it.get("riwaya"))
            j = judge_item(it, words, cfg) if words else None
            if j is None:
                skipped[sname] = skipped.get(sname, 0) + 1
                continue
            lo, hi = D.zone(it) if injected else (None, None)
            for r in j:
                zone = injected and lo <= r["k"] <= hi
                recs.append({"set": sname, "item": it["id"], "k": r["k"], "state": r["state"], "p": r["p"], "pmin": r["pmin"],
                             "kind": ("honest" if zone else "false") if r["state"] in CONF else None,
                             "op": it.get("op")})
    return recs, skipped


# ───────────────────────── التلخيص ─────────────────────────

def summarize(recs, key="p", n_boot=2000):
    """سطرٌ ملخِّصٌ لمجموعةٍ من السجلّات: AUC صادقٌ-مقابل-كاذبٍ على المتّهمات ذواتِ الكلمة المسموعة."""
    by_item = {}
    n_h = n_f = n_h_miss = n_f_miss = 0
    for r in recs:
        if r["kind"] is None:
            continue
        if r["state"] == scorer.MISSED or r[key] is None:
            if r["kind"] == "honest":
                n_h_miss += 1
            else:
                n_f_miss += 1
            continue
        pos, neg = by_item.setdefault(r["item"], ([], []))
        (pos if r["kind"] == "honest" else neg).append(r[key])
        if r["kind"] == "honest":
            n_h += 1
        else:
            n_f += 1
    pos = [v for a, _ in by_item.values() for v in a]
    neg = [v for _, b in by_item.values() for v in b]
    a = auc(pos, neg)
    return {"auc": a, "ci": boot_auc(by_item, n_boot) if a is not None else None,
            "n_honest": n_h, "n_false": n_f, "n_honest_missed": n_h_miss, "n_false_missed": n_f_miss,
            "med_honest": percentile(pos, .5), "med_false": percentile(neg, .5)}


def tau_effect(recs):
    """τ = المئين العاشر لـ`p` على الكلمات الصحيحة ⇒ كم صادقاً يُفقد وكم كاذباً يُزال بـ«p<τ ⇒ غير متبيَّن»."""
    ok = [r["p"] for r in recs if r["state"] == scorer.CORRECT and r["p"] is not None]
    tau = percentile(ok, .10)
    if tau is None:
        return None
    sub = [r for r in recs if r["state"] == scorer.SUBSTITUTED and r["p"] is not None]
    h = [r for r in sub if r["kind"] == "honest"]
    f = [r for r in sub if r["kind"] == "false"]
    return {"tau": tau, "n_correct": len(ok),
            "honest_lost": sum(1 for r in h if r["p"] < tau), "honest_n": len(h),
            "false_removed": sum(1 for r in f if r["p"] < tau), "false_n": len(f)}


def _f3(x):
    return "—" if x is None else f"{x:.3f}"


def fmt_auc(s):
    if s["auc"] is None:
        return "—"
    ci = f" [{s['ci'][0]:.3f}, {s['ci'][1]:.3f}]" if s["ci"] else " [—]"
    return f"{s['auc']:.3f}{ci}"


def report(all_recs, skipped, n_boot=2000):
    """يعيد (نصَّ markdown، dict النتائج)."""
    groups = [("g3r مضجَّج", ["g3rn"], True), ("g3r نظيف", ["g3rc"], True), ("g3r كلُّه", ["g3rn", "g3rc"], True),
              ("g3r كلُّه + سلبيّات g1/g2 (كلُّ اتّهامٍ فيها كاذب)", ["g3rn", "g3rc", "g1", "g2"], True)]
    md = ["# AUC ثقة الرموز `p` في فصل الاتّهام الصادق عن الكاذب", "",
          "> مولَّد بـ`tools/tasmi_bench/token_conf_auc.py` (‏خطوة 1 من خطة المستشار 2026-10-05). **عالي `p` ⇒ صادق.**",
          "> الأرقامُ على `whisper-cli` (‏whisper.cpp@c4ac001، رايات `greedy` المشحونة، `-ojf`) لا على محرك الهاتف؛ والمجالُ bootstrap عنقوديّ بالبند.", ""]
    res = {}
    for model, recs in all_recs.items():
        md += [f"## النموذج `{model}`", "",
               "| المجموعة | AUC لمتوسّط p [95٪] | AUC لأدنى p [95٪] | صادقٌ (له كلمةٌ مسموعة) | كاذبٌ (له كلمةٌ مسموعة) | صادقٌ بلا كلمة (MISSED) | كاذبٌ بلا كلمة (MISSED) | وسيط p صادق/كاذب |",
               "|---|---|---|---:|---:|---:|---:|---|"]
        res[model] = {"groups": {}, "skipped": skipped.get(model, {})}
        for label, sets, _ in groups:
            sub = [r for r in recs if r["set"] in sets]
            if not sub:
                continue
            sm = summarize(sub, "p", n_boot)
            sn = summarize(sub, "pmin", n_boot)
            md.append(f"| {label} | **{fmt_auc(sm)}** | {fmt_auc(sn)} | {sm['n_honest']} | {sm['n_false']} | {sm['n_honest_missed']} | {sm['n_false_missed']} | "
                      f"{_f3(sm['med_honest'])} / {_f3(sm['med_false'])} |")
            res[model]["groups"][label] = {"mean_p": sm, "min_p": sn}
        # التفصيلُ بنوع الحقن (‏على g3r كلِّه)
        g3 = [r for r in recs if r["set"] in ("g3rn", "g3rc")]
        ops = sorted({r["op"] for r in g3 if r["op"]})
        if ops:
            md += ["", "صادقٌ بنوع الحقن (‏كلمةٌ مسموعةٌ فقط، g3r كلُّه): " + " · ".join(
                f"{op}: {sum(1 for r in g3 if r['op'] == op and r['kind'] == 'honest' and r['state'] == scorer.SUBSTITUTED and r['p'] is not None)}" for op in ops)]
        te = tau_effect(recs)
        md += [""]
        if te:
            md += [f"**τ (المئين العاشر لـp على الكلمات الصحيحة، ن={te['n_correct']}) = {te['tau']:.4f}** — "
                   f"لو صار «p<τ ⇒ غير متبيَّن»: يُفقد {te['honest_lost']}/{te['honest_n']} من الصادقة ويُزال {te['false_removed']}/{te['false_n']} من الكاذبة "
                   "(‏المتّهماتُ ذواتُ الكلمة المسموعة فقط).", ""]
            res[model]["tau"] = te
        if skipped.get(model):
            md += [f"بنودٌ لم تُحسب (‏حارسُ الانهيار 0.60 أو تفريغٌ فارغ): {skipped[model]}", ""]
    return "\n".join(md) + "\n", res


def verdict(res):
    """معيارُ المستشار: AUC لمتوسّط p على «g3r كلِّه» ≥ 0.75 ⇒ 1ب؛ وإلا يُغلق (‏يُقرأ **حدُّه الأدنى** أيضاً)."""
    lines = ["## الحكم مقابل المعيار (AUC ≥ 0.75)", ""]
    for model, r in res.items():
        g = r["groups"].get("g3r كلُّه")
        if not g or g["mean_p"]["auc"] is None:
            lines.append(f"- `{model}`: لا قياسَ كافياً (صنفٌ فارغ) ⇒ لا حكم.")
            continue
        a, ci = g["mean_p"]["auc"], g["mean_p"]["ci"]
        if a >= 0.75 and ci and ci[0] >= 0.75:
            v = "**يُوصى بالخطوة 1ب** (‏الحدُّ الأدنى للمجال ≥ 0.75 أيضاً)"
        elif a >= 0.75:
            v = "**يُوصى بالخطوة 1ب بتحفّظ**: النقطةُ ≥ 0.75 لكنّ المجالَ يعبر 0.75"
        else:
            v = "**يُغلق البند** (‏AUC دون 0.75)"
        lines.append(f"- `{model}`: AUC = {a:.3f}" + (f" [{ci[0]:.3f}, {ci[1]:.3f}]" if ci else "") + f" ⇒ {v}")
    return "\n".join(lines) + "\n"


# ───────────────────────── اختبارٌ ذاتيّ (بلا whisper ولا شبكة) ─────────────────────────

def _tok(text, p):
    return {"text": text, "id": 100, "p": p, "t_dtw": -1}


def selftest():
    # ① تحليلُ الكلمات: الرمزُ الخاصّ يُتخطّى، والرمزُ بلا مسافةٍ يُلصق، والمتوسّطُ والأدنى صحيحان
    js = {"transcription": [{"tokens": [_tok("[_BEG_]", 0.9), _tok(" كتاب", 0.8), _tok("ٌ", 0.4), _tok(" قلم", 0.6), _tok("[_TT_5]", 0.1)]},
                             {"tokens": [_tok("باب", 0.5)]}]}
    w = parse_words(js)
    assert [x["w"] for x in w] == ["كتابٌ", "قلم", "باب"], w
    assert abs(w[0]["p"] - 0.6) < 1e-9 and w[0]["pmin"] == 0.4 and w[0]["n"] == 2, w[0]
    # ② AUC: فصلٌ تامّ = 1 · لا فصلَ = 0.5 · عكسٌ = 0 · تعادلٌ = نصف
    assert auc([.9, .8], [.1, .2]) == 1.0
    assert auc([.5, .5], [.5, .5]) == 0.5
    assert auc([.1], [.9]) == 0.0
    assert abs(auc([.9, .5], [.5, .1]) - 0.875) < 1e-9
    assert auc([], [.1]) is None
    # ③ المئين
    assert abs(percentile([1, 2, 3, 4, 5], .10) - 1.4) < 1e-9
    # ④ تعيينُ p على الكلمة المسموعة عبر `scorer.score` — مع زيادةٍ في المفكوك تُزيح الفهارس
    ref = ["الْكِتَابُ", "الْقَلَمُ", "الْبَابُ", "الْبَيْتُ", "الشَّمْسُ", "الْقَمَرُ"]
    words = [{"w": "الكتاب", "p": 0.9, "pmin": 0.9, "n": 1}, {"w": "زيادة", "p": 0.11, "pmin": 0.11, "n": 1},
             {"w": "سيارة", "p": 0.2, "pmin": 0.2, "n": 1}, {"w": "الباب", "p": 0.7, "pmin": 0.7, "n": 1},
             {"w": "البيت", "p": 0.6, "pmin": 0.6, "n": 1}, {"w": "الشمس", "p": 0.5, "pmin": 0.5, "n": 1},
             {"w": "القمر", "p": 0.4, "pmin": 0.4, "n": 1}]
    cfg = D.cfg_for("hafs")
    s = scorer.score(ref, " ".join(x["w"] for x in words), cfg)
    j = judge_item({"refText": " ".join(ref)}, words, cfg)
    assert j is not None, s["words"]
    # «سيارة» تُحاذى بـ«القلم» إبدالاً و«زيادة» زائدةٌ تُزيح الفهارس — يجب أن يحمل الإبدالُ p الكلمةِ المسموعة لا جارتِها
    sub = [r for r in j if r["state"] == scorer.SUBSTITUTED]
    assert [r["p"] for r in sub] == [0.2], (s["words"], j)
    assert [r["p"] for r in j if r["state"] == scorer.CORRECT] == [0.9, 0.7, 0.6, 0.5, 0.4], j
    # ⑤ bootstrap: فصلٌ تامٌّ ⇒ المجالُ كلُّه 1 · ولا فصلَ ⇒ يحيط بـ0.5
    perfect = {f"i{n}": ([0.9], [0.1]) for n in range(30)}
    lo, hi = boot_auc(perfect, 200)
    assert lo == hi == 1.0
    rnd = random.Random(3)
    flat = {f"i{n}": ([rnd.random()], [rnd.random()]) for n in range(80)}
    lo, hi = boot_auc(flat, 300)
    assert lo < 0.5 < hi, (lo, hi)
    # ⑥ summarize + tau_effect على سجلّاتٍ مصنوعة (‏MISSED لا يدخل AUC ويُعَدّ)
    recs = []
    for n in range(40):
        recs.append({"set": "g3rn", "item": f"a{n}", "k": 0, "state": scorer.SUBSTITUTED, "p": 0.8, "pmin": 0.8, "kind": "honest", "op": "SUBSTITUTE"})
        recs.append({"set": "g3rn", "item": f"a{n}", "k": 1, "state": scorer.SUBSTITUTED, "p": 0.2, "pmin": 0.2, "kind": "false", "op": "SUBSTITUTE"})
        recs.append({"set": "g3rn", "item": f"a{n}", "k": 2, "state": scorer.MISSED, "p": None, "pmin": None, "kind": "false", "op": "SUBSTITUTE"})
        recs.append({"set": "g3rn", "item": f"a{n}", "k": 3, "state": scorer.CORRECT, "p": 0.5 + n / 100, "pmin": 0.5, "kind": None, "op": "SUBSTITUTE"})
    sm = summarize(recs, "p", 200)
    assert sm["auc"] == 1.0 and sm["n_false_missed"] == 40 and sm["n_honest"] == 40, sm
    te = tau_effect(recs)
    assert te["honest_lost"] == 0 and te["false_removed"] == 40, te
    md, res = report({"tiny": recs}, {}, 100)
    assert "AUC" in md and "يُوصى" in verdict(res)
    # ⑦ الإضافةُ `hyp_idx` في المحاذي لم تغيّر الأحكام: نتيجةٌ بدونها مطابقةٌ حرفاً لما كانت
    assert len(s["hyp_idx"]) == 6 and s["words"][0][1] == scorer.CORRECT
    print("✅ token_conf_auc selftest: 7 فحوص نجحت")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--cli")
    ap.add_argument("--models", help="‏اسم=مسار، مفصولةً بفواصل (tiny=…,base=…)")
    ap.add_argument("--sets", default="g3rn,g3rc,g1,g2")
    ap.add_argument("--threads", type=int, default=1)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--limit", type=int, default=0, help="‏حدُّ البنود لكلّ مجموعة (0 = الكلّ)")
    ap.add_argument("--boot", type=int, default=2000)
    ap.add_argument("--workdir", default=os.path.join(WORK, "conf"))
    ap.add_argument("--md", default="")
    ap.add_argument("--json", default="")
    ap.add_argument("--words", default="", help="‏يُكتب سجلُّ كلماتِ كلّ نموذجٍ (‏p والحكم) لمن يريد إعادةَ الحساب")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if not a.cli or not a.models:
        ap.error("--cli و--models لازمان")
    sets = [s for s in a.sets.split(",") if s]
    for s in sets:
        if s not in SETS:
            ap.error(f"مجموعةٌ مجهولة: {s}")
    all_recs, skipped = {}, {}
    for pair in a.models.split(","):
        name, path = pair.split("=", 1)
        if not os.path.exists(path):
            raise SystemExit(f"⛔ لا نموذجَ في {path}")
        all_recs[name], skipped[name] = collect(a.cli, name, path, sets, a.workdir, a.threads, a.workers, a.limit)
    md, res = report(all_recs, skipped, a.boot)
    md += "\n" + verdict(res)
    print(md)
    if a.md:
        with open(a.md, "w", encoding="utf-8") as f:
            f.write(md)
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump(res, f, ensure_ascii=False, indent=1)
    if a.words:
        with open(a.words, "w", encoding="utf-8") as f:
            json.dump(all_recs, f, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
