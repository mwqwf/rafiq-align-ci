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

🚨🚨 **وحكمُ 2026-09-15 (‏D-609): الذراعُ ميتةٌ على هذا الحاكم، وكانت تطبع أصفاراً كأنّها نتيجة.**
المقيس: السقوفُ **2 و3 و9** تعطي مخرَجاً **متطابقاً بايتاً بايت** على 89,958 حالة
(‏`md5` واحد) — والترقيعُ **يقع فعلاً** (النسخةُ في `work/kt/src_cap9` تحمل `n <= 9`).
والسببُ مقروءٌ من المصدر لا مظنون:

    matches(ref, hyp, strictShort = criticalPairsUncertain)   // والمشحونُ `true` (D-231)
    return d * 5 <= n || (!strictShort && n <= 3 && d <= 1)   // ⇒ الشقُّ الثاني **ميّتٌ**

⇒ الرخصةُ لا تُبلَغ إلّا عبر `looseMatch` (‏`strictShort = false`)، ومستدعياه
`RiwayaSlipDetector` و`QuranLocator` — و**`EngineJudge` لا يترجمهما أصلاً** (‏ثلاثةُ ملفّاتٍ لا غير).
⛔ **فلا يُقاس سقفُ الرخصة بهذا الحاكم**، ومكانُه `SlipArmJudge` / `SlipDaggerArmJudge`.
⇒ **ورمزُ الخروج صار يفرّق:** 0 قيسَ · 1 ضابطٌ أخفق · **2 جرى ولم يَقِسْ شيئاً**.

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


def dead_arm_note(cap_base, cap_arm):
    """🚨 تشخيصُ «جرى ولم يَقِسْ شيئاً» — يُطبع مكانَ الجدول لا تحته (‏D-609)."""
    return (
        "\n🚨🚨 **الذراعُ لم تحرّك حكماً واحداً — وهذا ليس نتيجةً بل عدّادٌ أخرس.**\n"
        "   سقفُ %s وسقفُ %s أعطيا المخرَجَ **نفسَه بايتاً بايت**.\n"
        "   والترقيعُ **يقع** (‏سيرُ البناء يخرج بخطإٍ لو لم يجد المرساةَ مرّةً واحدة)،\n"
        "   لكنّ الشرطَ المرقَّعَ **ميّتٌ على هذا الحاكم**:\n"
        "     `matches(ref, hyp, strictShort = criticalPairsUncertain)` والمشحونُ `true` (D-231)\n"
        "     ⇒ `(!strictShort && n <= N && d <= 1)` لا يُبلَغ أبداً من `score()`.\n"
        "   والرخصةُ حيّةٌ عبر `looseMatch` وحدَه ⇒ `RiwayaSlipDetector` و`QuranLocator`،\n"
        "   و`EngineJudge` **لا يترجمهما**. ⛔ فمكانُ هذا القياس `SlipArmJudge`/`SlipDaggerArmJudge`.\n"
        % (cap_base, cap_arm))


def control(limit=800):
    """🧪 ضابطُ D-279: موجَبٌ (المشحون يعيد نفسَه) وسالبٌ (رخصةٌ موسَّعةٌ يجب أن تحرّك الأرقام).

    ⛔⛔ **وعلامةُ الصحّة تتبع الشرطَ لا تسبقه** (‏D-609): كان السطران يُطبعان بـ«✅» **ثابتةً**
    فبقي «يجب > 0» مكتوباً فوق صفرٍ، والقارئُ يقرأ نجاحاً حيث الإخفاق. ⇒ العلامةُ تُحسب الآن.
    """
    cases = R.build(limit=limit, arms="ab")
    print("الضابط: %d حالة (‏limit=%d)" % (len(cases), limit))
    e3 = run_cap(cases, 3, "c3")
    e3b = run_cap(cases, 3, "c3b")
    e9 = run_cap(cases, 9, "c9")
    same = sum(1 for n in e3 if e3.get(n) != e3b.get(n))
    moved9 = sum(1 for n in e3 if e3.get(n) != e9.get(n))
    print("%s ضابطٌ سالب: سقفٌ مطابقٌ (3⇐3) ⇒ اختلفت %d حالة (يجب 0)"
          % ("✅" if same == 0 else "❌", same))
    print("%s عدّادٌ حيّ: رخصةٌ موسَّعة (3⇐9) ⇒ اختلفت %d حالة (يجب > 0)"
          % ("✅" if moved9 > 0 else "🚨", moved9))
    if moved9 == 0:
        print(dead_arm_note(3, 9))
    return same == 0 and moved9 > 0


PATCH_ANCHOR = "n <= 3 && d <= 1"          # جسمُ الشرط — بلا قوسٍ فاتحٍ عمداً (‏درسُ 09-12)
OLD_ANCHOR = "(n <= 3 && d <= 1)"          # المرساةُ القديمةُ التي ماتت بصمت
KT_SCORER = os.path.join(ROOT, "engine", "recitation", "src", "main", "kotlin",
                         "com", "ali", "rafiq", "recitation", "RecitationScorer.kt")
BUILD_SH = os.path.join(HERE, "engine_judge", "build_and_run.sh")


def selftest():
    """🧪 **حارسُ الذراع على المحرك** (‏D-602) — والذراعُ تُقاس بـ**ترقيع نسخةٍ من مصدر
    المحرك**، فإن ضاعت المرساةُ **ماتت الذراعُ صامتةً** وقِيس المشحونُ على نفسِه.

    ⛔⛔ **وقد وقع هذا فعلاً** (‏09-12): أُدخل حارسُ الأزواج الحرجة فصار الشرطُ
    `(!strictShort && n <= 3 && d <= 1)` ⇒ المرساةُ القديمةُ `(n <= 3 && d <= 1)` **صفرٌ**،
    و«كلُّ ذراعٍ على المحرك كانت تموت». فالمرساةُ اليومَ **جسمُ الشرط بلا قوس**، وهذا
    الحارسُ يقيس **أنّها لا تزال فريدةً في الملفّ** — في ثوانٍ وبلا بناءِ كوتلن.

    ⭐ **والفرقُ عن الضابط الموجود:** `--control` يبني الحاكمَ ثلاثَ مرّاتٍ (دقائق)، وهذا
    يفحص **شرطَ صحّة الترقيع نفسَه** الذي لولاه لصار الضابطُ يقارن المشحونَ بالمشحون.
    """
    ok = True

    def say(good, line):
        nonlocal ok
        ok &= bool(good)
        print(("✅ " if good else "❌ ") + line)

    # ①⭐⭐ المرساةُ فريدةٌ في مصدر المحرك — لا صفرٌ ولا اثنتان
    if os.path.isfile(KT_SCORER):
        kt = io.open(KT_SCORER, encoding="utf-8").read()
        n = kt.count(PATCH_ANCHOR)
        say(n == 1, "⭐⭐ مرساةُ الترقيع في `RecitationScorer.kt` **مرّةً واحدةً بالضبط**: %d" % n)
        say(kt.count(OLD_ANCHOR) == 0 and "strictShort" in kt,
            "⛔ والمرساةُ القديمةُ بالقوس **صفرٌ** كما قِيس يومَ ماتت (‏والحارسُ `strictShort` قائم)")
    else:
        print("⚠️ **مصدرُ المحرك ليس في هذه النسخة** ⇒ **فحصا المرساة لم يُجرَيا هنا** "
              "(يجريان في مستودع الأصل) — ⛔ إعلانٌ بالنصّ لا نجاحٌ صامت.")

    # ② وسيرُ البناء يرفض الترقيعَ غيرَ الفريد صراحةً — لا يمرّ صامتاً
    if os.path.isfile(BUILD_SH):
        sh = io.open(BUILD_SH, encoding="utf-8").read()
        say('if t.count(old) != 1:' in sh and "sys.exit(" in sh,
            "⛔ وسيرُ البناء **يخرج بخطإٍ** إن لم تكن المرساةُ فريدة")
        say('SHORT_CAP="${SHORT_CAP:-3}"' in sh and 'if [ "$SHORT_CAP" != "3" ]' in sh,
            "والافتراضُ **3 = المشحون** ⇒ المسارُ القديمُ بحذافيره حين لا تُطلب ذراع")
        say('old, new = "n <= 3 && d <= 1"' in sh,
            "والمرساةُ في السيرِ هي عينُها المفحوصةُ هنا (‏مصدرٌ واحد)")
    else:
        print("⚠️ **سيرُ البناء غيرُ موجود** ⇒ ثلاثةُ فحوصٍ لم تُجرَ — ⛔ إعلانٌ لا صمت.")

    # ③ بناءُ الحالات من مصدرٍ واحد: `riwaya_surface` — لا نسخةَ بناءٍ هنا
    src = io.open(os.path.abspath(__file__), encoding="utf-8").read()
    say("\ndef build(" not in src and "R.build(" in src,
        "⛔ ولا بناءَ حالاتٍ في هذا الملفّ: يُستورَد من `riwaya_surface`")

    # ④ عتبةُ الضابط لم تُليَّن: مطابقٌ ⇒ **صفرٌ**، وموسَّعٌ ⇒ **أكثرُ من صفر**
    say("return same == 0 and moved9 > 0" in src,
        "⛔ عتبةُ الضابط كما هي: `same == 0 and moved9 > 0`")

    # ⑤ حارسُ مصدرٍ على الرقم الذي تقوم عليه الضمانة
    say("0/77,429" in src and "صفرٌ مطلق" in src,
        "حارسُ مصدر: أرضيّةُ الاتّهام الكاذب **صفرٌ مطلقٌ** (0/77,429) محفوظةٌ في المتن")

    # ⑥⭐⭐ والذراعُ ميتةٌ على هذا الحاكم — يُثبَّت **سببُها** لا خبرُها (‏D-609)
    if os.path.isfile(KT_SCORER):
        kt = io.open(KT_SCORER, encoding="utf-8").read()
        gate = "criticalPairsUncertain" + ": Boolean = true"
        say(gate in kt,
            "⭐⭐ المشحونُ `criticalPairsUncertain = true` (D-231) ⇒ `strictShort` صادقٌ افتراضاً")
        say("!strictShort && " + PATCH_ANCHOR in kt,
            "⭐⭐ والمرساةُ **داخلَ** شقِّ `!strictShort` ⇒ ميتةٌ على مسار `score()`")
        say(kt.count("strictShort = false") == 1 and "fun looseMatch" in kt,
            "⭐ ولا يفتحها إلّا `looseMatch` (‏موضعٌ واحدٌ يمرّر `strictShort = false`)")
    else:
        print("⚠️ **مصدرُ المحرك ليس في هذه النسخة** ⇒ **ثلاثةُ فحوصِ الموت لم تُجرَ هنا** "
              "(تجري في مستودع الأصل) — ⛔ إعلانٌ بالنصّ لا نجاحٌ صامت.")

    judge = os.path.join(HERE, "engine_judge", "EngineJudge.kt")
    if os.path.isfile(judge):
        say("looseMatch" not in io.open(judge, encoding="utf-8").read(),
            "⛔ و`EngineJudge` لا يستدعي `looseMatch` ولا يترجم مستدعيَيه ⇒ لا مَنفذَ للرخصة")
    else:
        print("⚠️ **`EngineJudge.kt` غيرُ موجود** ⇒ فحصُ المنفذ لم يُجرَ — ⛔ إعلانٌ لا صمت.")

    # ⑦⛔ ورمزُ الخروج يفرّق «قِيس» عن «جرى ولم يَقِسْ» — وإلّا قُرئ الصمتُ نجاحاً
    say("return 2" in src and "\ndef dead_arm_note(" in src,
        "⛔ ورمزُ الخروج **2** لذراعٍ لم تحرّك حكماً — لا 0")
    say("if moved == 0:" in src and "ولا يُطبع الجدولُ" in src,
        "⛔ ولا يُطبع جدولُ الأصفار أصلاً: التشخيصُ مكانَه لا تحتَه")
    say('("✅" if moved9 > 0 else "🚨")' in src,
        "⛔ وعلامةُ الصحّة **تتبع الشرطَ**: كانت ✅ ثابتةً فوق صفرٍ يقول «يجب > 0»")

    print("\n%s" % ("✅ حارسُ الذراع على المحرك: تمّ" if ok else "❌ حارسُ الذراع: أخفق"))
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true", help="🧪 حارسُ الأداة (ثوانٍ · بلا كوتلن)")
    ap.add_argument("--arms", default="a")
    ap.add_argument("--cap", type=int, default=2, help="سقفُ الذراع المقيس")
    ap.add_argument("--limit", type=int, default=0, help="عددُ الآيات لكلِّ رواية (0 = المصحف كلُّه)")
    ap.add_argument("--control", action="store_true")
    ap.add_argument("--examples", type=int, default=8)
    args = ap.parse_args()
    if args.selftest:
        sys.exit(selftest())

    if args.control:
        ok = control(limit=args.limit or 800)
        return 0 if ok else 1

    cases = R.build(limit=args.limit, arms=args.arms)
    print("الحالات: %d (‏أذرع=%s · limit=%s)" % (len(cases), args.arms, args.limit or "المصحف كلُّه"))
    base = run_cap(cases, SHIPPED_CAP, "cap%d_%s" % (SHIPPED_CAP, args.arms))
    arm = run_cap(cases, args.cap, "cap%d_%s" % (args.cap, args.arms))

    # ⛔⛔ الضابطُ **قبل** الجدول لا بعدَه (‏D-609): جدولُ أصفارٍ من ذراعٍ ميتةٍ يُقرأ «لا فرق»
    #    وهو في الحقيقة «لم يُقَس». ⇒ يُطبع التشخيصُ ويُعاد **2** لا **0**.
    moved = sum(1 for n in base if base.get(n) != arm.get(n))
    if moved == 0:
        print(dead_arm_note(SHIPPED_CAP, args.cap))
        print("⛔ ولا يُطبع الجدولُ: أصفارُه أثرُ عدّادٍ أخرسَ لا أثرُ تساوي السقفين.")
        return 2

    print("✅ الذراعُ حيّة: حرّكت %d حكماً ⇒ الجدولُ أدناه يُقرأ" % moved)
    report(cases, base, arm, SHIPPED_CAP, args.cap, examples=args.examples)
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
