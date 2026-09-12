# -*- coding: utf-8 -*-
"""🧮 النصفُ **الرابع** من ميزان «رخصة الكلمة القصيرة» — الذراعُ على **المحرك نفسِه**، المصحفُ كلُّه (‏D-285).

⚠️ **لِمَ وُجد.** ذراعُ `short_cap=2` هو المرشَّحُ الوحيدُ الباقي على طاولة المالك (‏D-282 · D-283
· D-284). وقد قِيس ثلاثَ مرّاتٍ **وكلُّها على المرآة البايثونية**:

    D-277 · التعرُّض  34–39٪ من المصحف (مرآة)
    D-282 · الفائدة   12 إنذاراً كاذباً يزول، على 60 تفريغاً حقيقياً (مرآة)
    D-284 · التتبّع    لا يُكسَر، على 360 آية (مرآة)

🚨 **وأثمنُ رقمٍ في اللوحة لم يُمَسّ بالذراع قطّ:** أرضيّةُ الاتّهام الكاذب **صفرٌ مطلق**
(‏0/77,429 في ورشٍ و0/77,429 في قالون — D-281 على **المحرك**). ذلك الصفرُ هو الضمانةُ التي
يقوم عليها المنتجُ كلُّه: مَن تلا صحيحاً بروايته **لا يُتَّهم أبداً**. فإن كانت الرخصةُ هي
ما يحفظه، فقصُّها يشتري 0.31 نقطةٍ بثمنٍ **ليس في الميزان أصلاً**.

**وهذا يُقاس بلا صوتٍ وبلا شبكة، على المحرك لا على مرآته:** `build_and_run.sh` يقبل
`SHORT_CAP=<n>` فيبني الحاكمَ من **نسخةٍ مرقَّعةٍ في `work/`** غُيِّر فيها حرفٌ واحدٌ
(‏`n <= 3` ⇐ `n <= 2` في `matches`) ⇒ ⛔ **لا يُمَسّ ملفُّ المحرك على القرص**، والترقيعُ يفشل
صراحةً إن لم يجد الموضعَ مرّةً واحدةً بالضبط.

الأذرعُ (بناءُ الحالات من `riwaya_surface.py` نفسِه — مصدرٌ واحدٌ للقاعدة، وأرقامُه مُصادَقةٌ
في D-280 و D-281):

    أ · نظيف · مرجعُ الرواية + تلاوتُها تامّةً + ملفُّها ⇒ **أرضيّةُ الاتّهام الكاذب**
    ب · زلّة · مرجعُ E + كلمةٌ واحدةٌ بصورة S + ملفُّ E ⇒ **سقفُ كشف الزلّة الروائية**

ويُقارن الحكمُ **حالةً بحالة** بين السقفين، فيُقال بالعدد: كم كلمةً صحيحةً صارت متَّهمة،
وكم زلّةً فائتةً صارت مكشوفة.

⚠️ **حدُّ الرقم:** المسموعُ هنا **صورةُ whisper الحتميّة** (`parity_full.whisper_forms`) لا
تعرُّفٌ حقيقيّ ⇒ أرقامُ الذراع (أ) **حدٌّ أدنى** للكلفة (تعرُّفٌ حقيقيٌّ يخطئ أكثرَ من الرسم)،
وأرقامُ (ب) نصٌّ إلى نصّ ⇒ مطلقةٌ صحيحة.

🧪 **الضابطُ** (‏قاعدةُ D-279): `--control` يشغّل ثلاثةَ سقوف: `3` (‏المشحون ⇒ يجب أن يعيد
أرقامَ D-281 حرفاً بحرف) · `3` مرّةً أخرى بمصنّفاتٍ أخرى (‏فرقٌ **0** = ضابطٌ سالب) · `9`
(‏رخصةٌ موسَّعة ⇒ **يجب** أن تتحرّك الأرقام، وإلا فالعدّادُ أخرس).

    python tools/tasmi_bench/short_word_engine_arms.py --arms a          # الأرضيّة (الأهمّ)
    python tools/tasmi_bench/short_word_engine_arms.py --arms ab
    python tools/tasmi_bench/short_word_engine_arms.py --control --limit 800
"""
import argparse
import collections
import io
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "tools", "alignment"))

import parity_full as P  # noqa: E402
import riwaya_surface as R  # noqa: E402
import scorer  # noqa: E402

WORK = R.WORK
SHIPPED_CAP = 3


def run_cap(cases, cap, tag):
    """يبني حاكمَ المحرك بسقفٍ بعينه ويشغّله ⇒ {اسمُ الحالة: (الأحكام, الزوائد)}."""
    os.makedirs(WORK, exist_ok=True)
    src = os.path.join(WORK, "cases_short_engine_%s.tsv" % tag)
    out = os.path.join(WORK, "engine_short_arms_%s.tsv" % tag)
    with io.open(src, "w", encoding="utf-8") as f:
        for name, ref, hyp, riw in cases:
            f.write("\t".join((name, ref, hyp, riw)) + "\n")
    env = dict(os.environ, SHORT_CAP=str(cap))
    subprocess.run(["bash", os.path.join(HERE, "engine_judge", "build_and_run.sh"), src, out],
                   check=True, env=env)
    got = {}
    for line in io.open(out, encoding="utf-8"):
        if not line.strip():
            continue
        f = line.rstrip("\n").split("\t")
        got[f[0]] = (f[1], (f[2] if len(f) > 2 else "").split())
    return got


def tally(cases, eng):
    """عدّاداتٌ لكلِّ (ذراع, E, S) — بالمنطق نفسِه الذي صادقته D-280/D-281."""
    acc = {}
    per_case = {}
    for name, ref, hyp, riw in cases:
        got = eng.get(name)
        if got is None:
            continue
        verdicts, adds = got
        arm, e, s, _a, i = name.split("|")
        i = int(i)
        toks = ref.split()
        cfg = P.config_for(e)
        real = [j for j, t in enumerate(toks) if scorer.norm(t, cfg)]
        k = acc.setdefault((arm, e, s), dict(n=0, words=0, accused=0, det=0, cases=0))
        k["n"] += 1
        if arm in ("a", "c"):
            bad = sum(1 for j in real if j < len(verdicts) and verdicts[j] != "C")
            k["words"] += len(real)
            k["accused"] += bad + len(adds)
            per_case[name] = bad + len(adds)
        else:
            hit = (i < len(verdicts) and verdicts[i] != "C") or bool(adds)
            k["cases"] += 1
            k["det"] += 1 if hit else 0
            per_case[name] = 1 if hit else 0
    return acc, per_case


def pct(a, b):
    return 100.0 * a / b if b else 0.0


def report(cases, base, arm_eng, cap_base, cap_arm, examples=8):
    a_acc, a_per = tally(cases, base)
    b_acc, b_per = tally(cases, arm_eng)
    print("\n" + "=" * 78)
    print("⚖️  سقفُ الرخصة %d (المشحون)  ⇐⇒  سقفُ الرخصة %d (الذراع)" % (cap_base, cap_arm))
    print("=" * 78)

    keys = sorted(set(a_acc) | set(b_acc))
    print("\n— الذراع (أ) · أرضيّةُ الاتّهام الكاذب على تلاوةٍ تامّةِ الصحّة —")
    hdr = False
    for k in keys:
        if k[0] != "a":
            continue
        if not hdr:
            print("%-8s %10s %14s %14s %10s" % ("الرواية", "كلمات", "متّهمة (%d)" % cap_base,
                                                "متّهمة (%d)" % cap_arm, "الفرق"))
            hdr = True
        x, y = a_acc.get(k, {}), b_acc.get(k, {})
        w = x.get("words", 0) or y.get("words", 0)
        print("%-8s %10d %14s %14s %10s" % (
            k[1], w,
            "%d (%.3f%%)" % (x.get("accused", 0), pct(x.get("accused", 0), w)),
            "%d (%.3f%%)" % (y.get("accused", 0), pct(y.get("accused", 0), w)),
            "%+d" % (y.get("accused", 0) - x.get("accused", 0))))

    print("\n— الذراع (ب) · سقفُ كشف الزلّة الروائية —")
    hdr = False
    for k in keys:
        if k[0] != "b":
            continue
        if not hdr:
            print("%-16s %10s %14s %14s %10s" % ("المرجع ⇜ المنزلَق", "حالات",
                                                 "كُشف (%d)" % cap_base, "كُشف (%d)" % cap_arm, "الفرق"))
            hdr = True
        x, y = a_acc.get(k, {}), b_acc.get(k, {})
        n = x.get("cases", 0) or y.get("cases", 0)
        print("%-16s %10d %14s %14s %10s" % (
            "%s ⇜ %s" % (k[1], k[2]), n,
            "%d (%.2f%%)" % (x.get("det", 0), pct(x.get("det", 0), n)),
            "%d (%.2f%%)" % (y.get("det", 0), pct(y.get("det", 0), n)),
            "%+d" % (y.get("det", 0) - x.get("det", 0))))

    # أمثلةٌ بالعين. ⚠️ اتّجاهُ «الأفضل» يختلف بين الذراعين: في (أ) العدّادُ اتّهامٌ كاذب
    # (‏الزيادةُ **سوء**)، وفي (ب) العدّادُ كشفُ زلّة (‏الزيادةُ **حَسَن**).
    a_worse = [n for n, v in b_per.items() if n.startswith("a|") and v > a_per.get(n, 0)]
    a_better = [n for n, v in b_per.items() if n.startswith("a|") and v < a_per.get(n, 0)]
    b_gain = [n for n, v in b_per.items() if n.startswith("b|") and v > a_per.get(n, 0)]
    b_lost = [n for n, v in b_per.items() if n.startswith("b|") and v < a_per.get(n, 0)]
    print("\n— ما تغيّر بالذراع —")
    print("  (أ) اتّهاماتٌ كاذبةٌ **جديدة**: %d · زالت: %d" % (len(a_worse), len(a_better)))
    print("  (ب) زلّاتٌ صارت **مكشوفة**: %d · زلّاتٌ **ضاعت**: %d" % (len(b_gain), len(b_lost)))
    idx = {c[0]: c for c in cases}

    def show(label, names):
        if not names:
            return
        print("  %s:" % label)
        for n in names[:examples]:
            _, ref, hyp, _riw = idx[n]
            _arm, _e, _s, _ay, i = n.split("|")
            i = int(i)
            rt, ht = ref.split(), hyp.split()
            pair = "%s ⇜ %s" % (rt[i] if i < len(rt) else "?", ht[i] if i < len(ht) else "?")
            print("    %-26s %s" % (n, pair))

    show("🚨 اتُّهمت بالذراع وهي تلاوةٌ صحيحة", a_worse)
    show("✅ زلّةٌ روائيةٌ كان يبتلعها السقفُ 3 فصارت تُكشف", b_gain)
    show("⛔ زلّةٌ كانت تُكشف فضاعت بالذراع", b_lost)
    return a_acc, b_acc, a_worse, b_gain


def b_eng_verdicts(eng, name):
    return eng.get(name, ("", []))[0]


def control(limit=800):
    """🧪 ضابطُ D-279: موجَبٌ (المشحون يعيد نفسَه) وسالبٌ (رخصةٌ موسَّعةٌ يجب أن تحرّك الأرقام)."""
    cases = R.build(limit=limit, arms="ab")
    print("الضابط: %d حالة (‏limit=%d)" % (len(cases), limit))
    e3 = run_cap(cases, 3, "c3")
    e3b = run_cap(cases, 3, "c3b")
    e9 = run_cap(cases, 9, "c9")
    same = sum(1 for n in e3 if e3.get(n) != e3b.get(n))
    moved9 = sum(1 for n in e3 if e3.get(n) != e9.get(n))
    print("✅ ضابطٌ سالب: سقفٌ مطابقٌ (3⇐3) ⇒ اختلفت %d حالة (يجب 0)" % same)
    print("✅ عدّادٌ حيّ: رخصةٌ موسَّعة (3⇐9) ⇒ اختلفت %d حالة (يجب > 0)" % moved9)
    return same == 0 and moved9 > 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", default="a")
    ap.add_argument("--cap", type=int, default=2, help="سقفُ الذراع المقيس")
    ap.add_argument("--limit", type=int, default=0, help="عددُ الآيات لكلِّ رواية (0 = المصحف كلُّه)")
    ap.add_argument("--control", action="store_true")
    ap.add_argument("--examples", type=int, default=8)
    args = ap.parse_args()

    if args.control:
        ok = control(limit=args.limit or 800)
        sys.exit(0 if ok else 1)

    cases = R.build(limit=args.limit, arms=args.arms)
    print("الحالات: %d (‏أذرع=%s · limit=%s)" % (len(cases), args.arms, args.limit or "المصحف كلُّه"))
    base = run_cap(cases, SHIPPED_CAP, "cap%d_%s" % (SHIPPED_CAP, args.arms))
    arm = run_cap(cases, args.cap, "cap%d_%s" % (args.cap, args.arms))
    report(cases, base, arm, SHIPPED_CAP, args.cap, examples=args.examples)


if __name__ == "__main__":
    main()
