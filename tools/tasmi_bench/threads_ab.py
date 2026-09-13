# -*- coding: utf-8 -*-
"""🧵⏱️ **ذراعا خيوطٍ على البنود عينِها** — أتربح زيادةُ خيوط التفريغ زمناً، وبأيّ ثمنٍ في الزمن الحقيقيّ؟

⛔ **لِمَ وُجدت (‏D-432):** `WhisperCpuConfig` يُخرج **صفراً لا استثناءً** على جهازٍ متساوي ترددات
النوى، فلا يعمل مسارُ المتغيّرات، فيُفرَّغ بـ**خيطَين** لا بعدد النوى. ورفعُ العدد **دعوى أداءٍ**
لا تُشحن بظنّ ⇒ تُقاس بذراعَين على **البنود عينِها**، وبشرطَين مجتمعَين (‏شروطُ القبول المتّفق
عليها قبل الشوط): **كسبُ زمنٍ يقينيٌّ** (الحدُّ الأعلى لمجال 95٪ دون الصفر) **وألّا يتجاوز
ذراعٌ الزمنَ الحقيقيّ** في بندٍ واحد. ⭐ **وزمنٌ يربح ويكسر الزمنَ الحقيقيَّ ليس ربحاً.**

    python threads_ab.py --a a1.json a2.json a3.json --b b1.json b2.json b3.json --md out.md
    python threads_ab.py --selftest        # يختبر الحاكمَ نفسَه على حالاتٍ معلومة

⚠️ **وحدُّ ما يُقاس يُقال معه** (‏ولا يُنقل رقمُه إلى الهاتف): عدّاءُ `arm64` **لينكس/glibc** وأنويةٌ
**متماثلة** لا `big.LITTLE` أندرويد ⇒ المقيسُ هو **اتّجاهُ التوسّع بالخيوط على المعمارية**، لا
زمنُ جهاز المستخدم. ⛔ ومسارا الفكّ **كلاهما مشحون**: `greedy` للتتبّع الحيّ و`guard` (‏beam 5 ·
‏et 1.80) للحكم النهائيّ (`guardScope=FINAL`) ⇒ **حارسُ الزمن الحقيقيّ يلزم كليهما**.
"""
import argparse
import json
import random
import statistics as st
import sys

DECODE = ("greedy", "guard")


def load_arm(paths):
    """يُعيد (عددَ الخيوط، {مسارُ الفكّ: {البند: وسيطُ rtf عبر الإعادات}}، عددَ الإعادات)."""
    threads, per = None, {d: {} for d in DECODE}
    for p in paths:
        j = json.load(open(p, encoding="utf-8"))
        t = int(j.get("threads", 0))
        if threads is None:
            threads = t
        elif t != threads:
            raise SystemExit(f"⛔ إعاداتُ ذراعٍ واحدةٍ بعددَي خيوطٍ مختلفَين: {threads} و{t} في {p}")
        rows = j.get("rows") or {}
        for d in DECODE:
            if d not in rows or not rows[d]:
                raise SystemExit(f"⛔ مسارُ الفكّ {d!r} غائبٌ أو فارغٌ في {p} ⇒ لا يُحكم بعيّنةٍ ناقصة")
            for i, r in rows[d].items():
                per[d].setdefault(i, []).append(float(r["rtf"]))
    return threads, {d: {i: st.median(v) for i, v in per[d].items()} for d in DECODE}, len(paths)


def boot_mean_diff(diffs, seed=7, boot=2000):
    """‏bootstrap على **البنود** لمتوسّط الفرق المزدوج (b − a) ⇒ (الأدنى، الأعلى، احتمالُ الارتفاع)."""
    if not diffs:
        return (0.0, 0.0, 0.0)
    rng = random.Random(seed)
    ms = []
    for _ in range(boot):
        pick = [diffs[rng.randrange(len(diffs))] for _ in range(len(diffs))]
        ms.append(sum(pick) / len(pick))
    ms.sort()
    return (ms[int(0.025 * boot)], ms[int(0.975 * boot) - 1], sum(1 for m in ms if m > 0) / boot)


def compare(a_paths, b_paths, rt=1.0):
    ta, pa, ra = load_arm(a_paths)
    tb, pb, rb = load_arm(b_paths)
    # ⛔ ذراعان بعدد الخيوط نفسِه تُعطيان «لا أثرَ للخيوط» كذباً (درسُ D-303) ⇒ يسقط قبل الحكم.
    if ta == tb:
        raise SystemExit(f"⛔ الذراعان بعدد الخيوط نفسِه ({ta}) ⇒ لا سؤالَ تُجيبانه")
    out = {"threads": (ta, tb), "repeats": (ra, rb), "rt": rt, "by_decode": {}}
    for d in DECODE:
        common = sorted(set(pa[d]) & set(pb[d]))
        if not common:
            raise SystemExit(f"⛔ لا بندَ مشترَكاً في {d} ⇒ المقارنةُ المزدوجةُ مستحيلة")
        diffs = [pb[d][i] - pa[d][i] for i in common]
        lo, hi, pgain = boot_mean_diff(diffs)
        va = [pa[d][i] for i in common]
        vb = [pb[d][i] for i in common]
        out["by_decode"][d] = {
            "n": len(common),
            "dropped": sorted((set(pa[d]) | set(pb[d])) - set(common)),
            "median": (st.median(va), st.median(vb)),
            "max": (max(va), max(vb)),
            "over_rt": (sum(1 for v in va if v > rt), sum(1 for v in vb if v > rt)),
            "diff": sum(diffs) / len(diffs),
            "ci": (lo, hi),
            "p_gain": pgain,
            # ⛔ الشرطان مجتمعان: كسبٌ يقينيٌّ (‏hi < 0) **و**لا بندَ يتجاوز الزمنَ الحقيقيَّ في الذراع الجديدة.
            "gain_certain": hi < 0,
            "rt_safe": max(vb) <= rt,
        }
    out["verdict"] = all(v["gain_certain"] and v["rt_safe"] for v in out["by_decode"].values())
    return out


def render(r):
    ta, tb = r["threads"]
    L = [f"## 🧵 ذراعا الخيوط — `{ta}` مقابل `{tb}` (‏وسيطُ {r['repeats'][0]}/{r['repeats'][1]} إعاداتٍ لكلّ بند)",
         "",
         f"| مسارُ الفكّ | ن | وسيطُ RTF ({ta}) | وسيطُ RTF ({tb}) | الفرقُ المزدوج [95٪] | أقصى RTF ({tb}) | يتجاوز {r['rt']:.2f} |",
         "|---|---:|---:|---:|---|---:|---:|"]
    for d in DECODE:
        v = r["by_decode"][d]
        L.append(f"| `{d}` | {v['n']} | {v['median'][0]:.3f} | **{v['median'][1]:.3f}** | "
                 f"{v['diff']:+.3f} [{v['ci'][0]:+.3f} .. {v['ci'][1]:+.3f}] | {v['max'][1]:.3f} | "
                 f"{v['over_rt'][0]} ⇐ {v['over_rt'][1]} |")
        if v["dropped"]:
            L.append(f"| ⚠️ بنودٌ غيرُ مشترَكةٍ أُسقطت من `{d}` | {len(v['dropped'])} | | | | | |")
    L += ["",
          "⛔ **الحكمُ زوجٌ:** يُقبل رفعُ الخيوط إن **نقص الزمنُ يقيناً** (الحدُّ الأعلى للمجال دون الصفر) "
          f"**ولم يتجاوز** بندٌ الزمنَ الحقيقيَّ ({r['rt']:.2f}) في الذراع الجديدة — **في مسارَي الفكّ كليهما**، "
          "فكلاهما مشحون (`greedy` للتتبّع الحيّ · `guard` للحكم النهائيّ).",
          ""]
    for d in DECODE:
        v = r["by_decode"][d]
        why = []
        if not v["gain_certain"]:
            why.append("الكسبُ غيرُ يقينيّ (المجال يعبر الصفرَ أو يرتفع)")
        if not v["rt_safe"]:
            why.append(f"بندٌ يتجاوز الزمنَ الحقيقيَّ (أقصى {v['max'][1]:.3f})")
        L.append(f"- `{d}`: " + ("✅ الشرطان متحقّقان" if not why else "⛔ " + " · و".join(why)))
    L += ["", ("## ✅ الحكم: **رفعُ الخيوط مقبولٌ بالقياس**" if r["verdict"]
               else "## ⛔ الحكم: **لا يُرفع عددُ الخيوط بهذا الشوط** — والخيطان يبقيان **بقياسٍ لا بعطب**"),
          "",
          f"⚠️ **حدُّ القراءة:** عدّاءُ `arm64` لينكس/glibc بأنويةٍ **متماثلة** لا `big.LITTLE` أندرويد ⇒ "
          "المقيسُ **اتّجاهُ التوسّع بالخيوط**، ولا يُنقل الرقمُ إلى جهاز المستخدم رقماً مطلقاً."]
    return "\n".join(L)


# ⛔ **والحاكمُ يُختبر قبل أن يُستعمل** (‏قاعدةُ المالك) — بحالاتٍ تُعرف أجوبتُها سلفاً.
def _mk(threads, rtfs):
    return {"threads": threads, "rows": {d: {i: {"sec": v, "rtf": v, "segs": 1, "text": ""}
                                            for i, v in rtfs.items()} for d in DECODE}}


def selftest(tmp="/tmp"):
    import os
    cases = [
        ("كسبٌ واضحٌ وآمنٌ من الزمن الحقيقيّ", {f"i{k}": 0.60 for k in range(12)},
         {f"i{k}": 0.40 for k in range(12)}, True),
        ("لا فرقَ البتّة ⇒ لا كسبَ يقينيّاً", {f"i{k}": 0.50 for k in range(12)},
         {f"i{k}": 0.50 for k in range(12)}, False),
        # ⭐ الحالةُ التي وُجد الحاكمُ لها: **يربح في المتوسّط ويكسر الزمنَ الحقيقيّ في بندٍ** ⇒ يُردّ.
        ("يربح ويكسر الزمنَ الحقيقيَّ في بندٍ واحد", {f"i{k}": 0.70 for k in range(12)},
         dict({f"i{k}": 0.40 for k in range(11)}, i11=1.20), False),
        ("يخسر زمناً ⇒ يُردّ", {f"i{k}": 0.40 for k in range(12)},
         {f"i{k}": 0.55 for k in range(12)}, False),
    ]
    bad = 0
    for name, a, b, want in cases:
        pa, pb = os.path.join(tmp, "_ta.json"), os.path.join(tmp, "_tb.json")
        json.dump(_mk(2, a), open(pa, "w", encoding="utf-8"))
        json.dump(_mk(4, b), open(pb, "w", encoding="utf-8"))
        got = compare([pa], [pb])["verdict"]
        ok = got == want
        print(f"  {'✅' if ok else '⛔'} {name}: الحكمُ {got} · المتوقَّع {want}")
        bad += 0 if ok else 1
    # ⛔ وحارسُ «ذراعان متطابقتان» يُختبر أيضاً: عددُ خيوطٍ واحدٌ ⇒ سقوطٌ لا حكم.
    pa = os.path.join(tmp, "_ta.json")
    json.dump(_mk(2, {"i0": 0.5}), open(pa, "w", encoding="utf-8"))
    try:
        compare([pa], [pa])
        print("  ⛔ ذراعان بعدد خيوطٍ واحدٍ لم تُردّا")
        bad += 1
    except SystemExit:
        print("  ✅ ذراعان بعدد خيوطٍ واحدٍ تُردّان قبل الحكم")
    # ⛔ ومسارُ فكٍّ ناقصٌ يُردّ ولا يُحتسب نصفَ عيّنة.
    j = _mk(2, {"i0": 0.5}); del j["rows"]["guard"]
    json.dump(j, open(pa, "w", encoding="utf-8"))
    pb = os.path.join(tmp, "_tb.json")
    json.dump(_mk(4, {"i0": 0.4}), open(pb, "w", encoding="utf-8"))
    try:
        compare([pa], [pb])
        print("  ⛔ مسارُ فكٍّ غائبٌ لم يُردّ")
        bad += 1
    except SystemExit:
        print("  ✅ مسارُ فكٍّ غائبٌ يُردّ")
    print("✅ الحاكمُ سليمٌ على حالاته" if not bad else f"⛔ الحاكمُ نفسُه معطوبٌ في {bad} حالة")
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", nargs="*", default=[], help="‏json الذراع الأولى (‏خيوطُ السياسة الحاليّة)")
    ap.add_argument("--b", nargs="*", default=[], help="‏json الذراع الثانية (‏عددُ الخيوط المرشَّح)")
    ap.add_argument("--rt", type=float, default=1.0, help="حدُّ الزمن الحقيقيّ بـRTF")
    ap.add_argument("--md", default="")
    ap.add_argument("--json", default="")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if not a.a or not a.b:
        raise SystemExit("⛔ لا بدّ من ملفٍّ واحدٍ لكلّ ذراعٍ على الأقلّ (‏--a و--b)")
    r = compare(a.a, a.b, a.rt)
    md = render(r)
    print(md)
    if a.md:
        open(a.md, "w", encoding="utf-8").write(md + "\n")
    if a.json:
        json.dump(r, open(a.json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    # ⛔ رمزُ الخروج **لا يُقرأ حكماً**: الحكمُ نصٌّ يُقرأ، والصفرُ يعني «قِيس وكُتب» لا «رُبح».
    return 0


if __name__ == "__main__":
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    raise SystemExit(main())
