# -*- coding: utf-8 -*-
"""🔀 **سطحُ الزلّة الروائية على المحرك نفسِه** — سقفُ الكشف وأرضيّةُ الاتّهام الكاذب، بلا صوت.

⚠️ **لِمَ وُجد:** مهمّةُ المناوبة `T=2` تقيس بوّابةَ الاتّهام الكاذب في ورشٍ وقالون **بصوتٍ
محقون** (`inject_riwaya.py` ⇐ `local_whisper.py`). وحين تُمنع الشبكةُ فلا نموذجَ ولا صوت،
تبقى في المسألة طبقةٌ **لا صوتَ فيها أصلاً** ولم تُقَس قطّ:

    إن كان المحركُ يقبل صورةَ ورشٍ حكماً صحيحاً وهو يُسمِّع حفصاً، فزلّةُ الرواية عندئذٍ
    **غيرُ قابلةٍ للكشف مهما بلغ النموذجُ الصوتيّ جودةً** — سقفٌ فوق كلِّ رقمِ كشفٍ يُقاس بالصوت.

وعكسُها: إن اتّهم المحركُ كلمةً في تلاوةٍ **تامّةِ الصحّة** بروايتها، فذلك اتّهامٌ كاذبٌ
**أرضيٌّ** لا يرفعه تحسينُ الصوت. الطبقتان تُقاسان بالرسم والمقياس وحدَهما ⇒ أرقامُهما
**مطلقةٌ صحيحة**، لا تحتمل تحفّظَ «المرآة» ولا «للمقارنة النسبية فقط».

⭐ **والأرقامُ هنا من حاكم المحرك الحقيقيّ** (‏`engine_judge/` — كوتلن على JVM، ‏D-279)
لا من المرآة البايثونية.

الأذرعُ الثلاثة:

    أ · نظيف   · مرجعُ الرواية + تلاوتُها تامّةً + ملفُّها      ⇒ أرضيّةُ الاتّهام الكاذب
    ب · زلّة   · مرجعُ E + كلمةٌ واحدةٌ بصورة S + ملفُّ E        ⇒ سقفُ الكشف + ضررُه الجانبيّ
    ج · ملفٌّ خطأ · مرجعُ R + تلاوتُه تامّةً + ملفُّ رواية أخرى   ⇒ كلفةُ اختيار الرواية خطأً

    python tools/tasmi_bench/riwaya_surface.py --control   # 🧪 الضابطُ السالب أوّلاً
    python tools/tasmi_bench/riwaya_surface.py             # المصحف كلُّه، الأذرعُ الثلاثة
    python tools/tasmi_bench/riwaya_surface.py --limit 300 --arms ab

🧪 **الضابطُ السالب** (‏قاعدةُ D-279: حارسٌ لا يسقط على عطبٍ مزروعٍ لا يُصدَّق أخضرُه):
عدّادُ الكشف كلُّه معلّقٌ بصحّة **موضع** الكلمة في سلسلة الأحكام؛ فلو انزاح الموضعُ حرفاً
لصار «لا كشفَ» وصمتَ القياس. فالضابطُ يزرع كلمةً غريبةً (`الحاسوب`) مكان الكلمة — يجب أن
يُكشف قرابةَ 100٪ — ثمّ يعيد العدَّ **بموضعٍ منزاحٍ واحداً**: إن لم ينهرِ الرقمُ فالعدّادُ أخرس.
"""
import argparse
import io
import itertools
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "tools", "alignment"))
import scorer  # noqa: E402
import parity_full as P  # noqa: E402  (‏whisper_forms + config_for — مصدرٌ واحدٌ للقاعدة)
from common import load_text  # noqa: E402

RIWAYAT = ("hafs", "warsh", "qalun")
WORK = os.path.join(HERE, "work")
FOREIGN = P.FOREIGN


def prepare(riwaya, limit=0):
    """لكلِّ آية: رموزُها الخام · صورةُ whisper لكلِّ رمز · مواضعُ الكلمات الحقيقية.

    ⚠️ علاماتُ الوقف رموزٌ مستقلّةٌ تُطبَّع إلى فراغ، وتبقى في المرجع كما يمرّرها التطبيق
    (‏قاعدةُ `parity_full`)، فتُستثنى من العدّ لا من المرجع.
    """
    cfg = P.config_for(riwaya)
    ayat = load_text(riwaya)
    if limit:
        ayat = ayat[:limit]
    out = []
    for ayah in ayat:
        toks = ayah.split()
        nw = [scorer.norm(x, cfg) for x in toks]
        # الصورةُ الأبعدُ عن الرسم — أقربُ ما يكتبه whisper فعلاً (‏D-279).
        ww = [P.whisper_forms(x, cfg)[-1] if n else "" for x, n in zip(toks, nw)]
        real = [i for i, x in enumerate(nw) if x]
        out.append((ayah, ww, real))
    return out


def build(limit=0, arms="abc", foreign=False):
    """يبني حالاتِ الأذرع. `foreign=True` يجعل ذراعَ (ب) تزرع كلمةً غريبةً — للضابط."""
    text = {r: prepare(r, limit) for r in RIWAYAT}
    cases = []
    if "a" in arms:
        for r in RIWAYAT:
            for a, (ayah, ww, real) in enumerate(text[r]):
                if not real:
                    continue
                cases.append(("a|%s|%s|%05d|0" % (r, r, a), ayah, " ".join(ww), r))
    if "c" in arms:
        for r in RIWAYAT:
            for other in RIWAYAT:
                if other == r:
                    continue
                for a, (ayah, ww, real) in enumerate(text[r]):
                    if not real:
                        continue
                    cases.append(("c|%s|%s|%05d|0" % (r, other, a), ayah, " ".join(ww), other))
    if "b" in arms:
        for e, s in itertools.permutations(RIWAYAT, 2):
            for a in range(len(text[e])):
                ayah, ww, real_e = text[e][a]
                _, ws, real_s = text[s][a]
                # ⛔ آيةٌ اختلف فيها عددُ الكلمات الحقيقية بين الروايتين لا تُحاذى كلمةً بكلمة.
                if len(real_e) != len(real_s) or not real_e:
                    continue
                for k, (ie, isx) in enumerate(zip(real_e, real_s)):
                    alt = FOREIGN if foreign else ws[isx]
                    if alt == ww[ie]:
                        continue           # لا زلّةَ: الروايتان تتّفقان في هذه الكلمة
                    hyp = ww[:ie] + [alt] + ww[ie + 1:]
                    cases.append(("b|%s|%s|%05d|%d" % (e, s, a, ie), ayah, " ".join(hyp), e))
    return cases


def run_engine(cases, out_tsv):
    """يبني حاكمَ المحرك (‏Kotlin) ويشغّله — عمودُ الرواية لكلِّ حالةٍ على حدة."""
    src = os.path.join(WORK, "cases_riwaya_surface.tsv")
    os.makedirs(WORK, exist_ok=True)
    with io.open(src, "w", encoding="utf-8") as f:
        for name, ref, hyp, riw in cases:
            f.write("\t".join((name, ref, hyp, riw)) + "\n")
    subprocess.run(["bash", os.path.join(HERE, "engine_judge", "build_and_run.sh"),
                    src, out_tsv], check=True)
    got = {}
    for line in io.open(out_tsv, encoding="utf-8"):
        if not line.strip():
            continue
        f = line.rstrip("\n").split("\t")
        got[f[0]] = (f[1], (f[2] if len(f) > 2 else "").split())
    return got


def analyse(cases, eng, skew=0):
    """`skew` يزيح موضعَ الكلمة المزلولة — للضابط السالب وحدَه (يجب أن ينهار الكشف)."""
    acc = {}          # (ذراع, E, S) ⇒ عدّادات
    misses = []       # أمثلةُ زلّةٍ لم تُكشف
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
        k = acc.setdefault((arm, e, s), dict(n=0, words=0, accused=0, ayat_bad=0,
                                             det=0, coll=0, coll_tot=0))
        k["n"] += 1
        if arm in ("a", "c"):
            bad = sum(1 for j in real if j < len(verdicts) and verdicts[j] != "C")
            k["words"] += len(real)
            k["accused"] += bad + len(adds)
            if bad or adds:
                k["ayat_bad"] += 1
        else:
            j = i + skew
            hit = (j < len(verdicts) and verdicts[j] != "C") or bool(adds)
            k["det"] += 1 if hit else 0
            other = [x for x in real if x != i and x < len(verdicts)]
            k["coll"] += sum(1 for x in other if verdicts[x] != "C")
            k["coll_tot"] += len(other)
            if not hit and len(misses) < 400:
                misses.append((name, ref, hyp))
    return acc, misses


def pct(a, b):
    return 100.0 * a / b if b else 0.0


def report(acc, misses, examples=6):
    for arm, title in (("a", "أ · نظيف — أرضيّةُ الاتّهام الكاذب"),
                       ("c", "ج · ملفُّ روايةٍ خطأ — كلفةُ الاختيار"),
                       ("b", "ب · زلّةٌ روائيةٌ بكلمةٍ واحدة — سقفُ الكشف")):
        rows = sorted((k, v) for k, v in acc.items() if k[0] == arm)
        if not rows:
            continue
        print("\n=== %s ===" % title)
        for (_, e, s, ), v in rows:
            if arm == "b":
                print("  %-6s ⇜ %-6s  زلّات %6d · كُشف %6d (%5.1f٪) · فات %5d"
                      "  ·  اتّهامٌ جانبيّ %6d من %7d (%.2f٪)"
                      % (e, s, v["det"] + (v["n"] - v["det"]), v["det"], pct(v["det"], v["n"]),
                         v["n"] - v["det"], v["coll"], v["coll_tot"], pct(v["coll"], v["coll_tot"])))
            else:
                lbl = e if arm == "a" else "%s بملفّ %s" % (e, s)
                print("  %-18s آيات %5d · كلمات %7d · متّهَمة %6d (%.3f٪) · آياتٌ فيها اتّهام %5d (%.2f٪)"
                      % (lbl, v["n"], v["words"], v["accused"], pct(v["accused"], v["words"]),
                         v["ayat_bad"], pct(v["ayat_bad"], v["n"])))
    for name, ref, hyp in misses[:examples]:
        print("  ⚠️ زلّةٌ لم تُكشف · %s\n     مرجع : %s\n     مسموع: %s" % (name, ref, hyp))


def control(limit=400):
    """🧪 الضابطُ السالب — انظر ترويسةَ الملفّ."""
    cases = build(limit=limit, arms="b", foreign=True)
    eng = run_engine(cases, os.path.join(WORK, "engine_riwaya_control.tsv"))
    good, _ = analyse(cases, eng, skew=0)
    skewed, _ = analyse(cases, eng, skew=1)
    d0 = sum(v["det"] for v in good.values()) if good else 0
    n0 = sum(v["n"] for v in good.values()) if good else 0
    d1 = sum(v["det"] for v in skewed.values()) if skewed else 0
    print("\nالضابط: كلمةٌ غريبةٌ مزروعة — كُشف %d من %d (%.1f٪) · وبموضعٍ منزاحٍ واحداً %.1f٪"
          % (d0, n0, pct(d0, n0), pct(d1, n0)))
    ok = n0 >= 100 and pct(d0, n0) >= 99.0 and pct(d0, n0) - pct(d1, n0) >= 20.0
    print("الضابط: %s" % ("✅ العدّادُ حيٌّ ويسقط بالإزاحة"
                          if ok else "🚨 العدّادُ لا يميّز الموضعَ — لا يُوثق برقمِ كشفٍ منه"))
    return 0 if ok else 1


FARSH_DIR = os.path.join(ROOT, "tools", "quraat", "farsh", "out")
ALL_RIWAYAT = ("hafs", "warsh", "qalun", "shuba", "douri", "sousi")


def farsh_positions():
    """مواضعُ الفرش لكلِّ آية من `farsh_<riwaya>.jz` — بفهرس كلمة **حفص** الحقيقية."""
    import collections
    import gzip
    import json
    per = {}
    for r in ALL_RIWAYAT:
        if r == "hafs":
            continue
        path = os.path.join(FARSH_DIR, "farsh_%s.jz" % r)
        if not os.path.isfile(path):
            continue
        d = json.loads(gzip.open(path, "rt", encoding="utf-8").read())
        m = collections.defaultdict(set)
        diffs = d["diffs"]
        if isinstance(diffs, dict):
            for a, lst in diffs.items():
                for it in lst:
                    m[int(a)].add(int(it[0] if isinstance(it, list) else it["hafsWordIdx"]))
        else:
            for it in diffs:
                m[int(it["ayah"])].add(int(it["hafsWordIdx"]))
        per[r] = m
    any_ = collections.defaultdict(set)
    for m in per.values():
        for a, s in m.items():
            any_[a] |= s
    return per, any_


def why(limit=0):
    """تشريحُ الزلّات التي **لم تُكشف** في الطبقة الأولى (‏`RecitationScorer`):

    1. **السبب:** أصورةٌ يقبلها ملفُّ الرواية حرفياً (‏`variants`) أم تسامحُ المسافة (‏≤⅕)؟
       الأوّلُ قرارُ تصميمٍ في الملفّ، والثاني رخصةُ المسافة (مِلَفُّ D-277).
    2. **هل تراها الطبقةُ الثانية؟** `RiwayaSlipDetector` (‏D-248) لا يعمل إلا على **مواضع
       الفرش**؛ فما وقع في **الأصول** (النقلُ والصلةُ ورسمُ المدّ) **لا تراه طبقةٌ البتّة**.
       وكونُ الموضع فرشاً شرطٌ **لازمٌ لا كافٍ** ⇒ العمودُ سقفُ تغطيةٍ لا تغطية.

    يقرأ مخرَجَ الذراع (ب) من `work/engine_riwaya_surface.tsv` — فشغّل القياسَ أوّلاً.
    """
    import collections
    out_tsv = os.path.join(WORK, "engine_riwaya_surface.tsv")
    if not os.path.isfile(out_tsv):
        print("🚨 لا مخرَجَ للذراع (ب): شغّل القياسَ أوّلاً.")
        return 1
    eng = {}
    for line in io.open(out_tsv, encoding="utf-8"):
        f = line.rstrip("\n").split("\t")
        if f and f[0].startswith("b|"):
            eng[f[0]] = f[1]
    text = {r: prepare(r, limit) for r in RIWAYAT}
    raw = {r: [a.split() for a in load_text(r)[:limit or None]] for r in RIWAYAT}
    per_farsh, any_farsh = farsh_positions()
    cause = collections.Counter()
    cover = collections.Counter()
    for e, s in itertools.permutations(RIWAYAT, 2):
        cfg_e = P.config_for(e)
        for a in range(len(text[e])):
            _, ww, real_e = text[e][a]
            _, ws, real_s = text[s][a]
            if len(real_e) != len(real_s) or not real_e:
                continue
            pos = any_farsh.get(a, set()) if e == "hafs" else per_farsh.get(e, {}).get(a, set())
            for k, (ie, isx) in enumerate(zip(real_e, real_s)):
                if ws[isx] == ww[ie]:
                    continue
                v = eng.get("b|%s|%s|%05d|%d" % (e, s, a, ie))
                if v is None or (ie < len(v) and v[ie] != "C"):
                    continue        # كُشفت — ليست موضعَ التشريح
                forms = set(P.whisper_forms(raw[e][a][ie], cfg_e))
                forms.add(scorer.norm(raw[e][a][ie], cfg_e))
                cause[(e, s, "صورةٌ يقبلها الملفّ" if ws[isx] in forms else "تسامحُ المسافة")] += 1
                cover[(e, s, "فرشٌ (قد تراه الطبقة ٢)" if k in pos else "أصولٌ (لا تراه طبقة)")] += 1
    print("\n=== سببُ الفوات ===")
    for k in sorted(cause):
        print("  %-6s ⇜ %-6s  %-22s %6d" % (k[0], k[1], k[2], cause[k]))
    print("\n=== هل تراه الطبقةُ الثانية (‏فرشٌ أم أصول)؟ ===")
    for k in sorted(cover):
        print("  %-6s ⇜ %-6s  %-24s %6d" % (k[0], k[1], k[2], cover[k]))
    return 0


# ⛔ حركاتٌ تقطع بأنّ الميمَ **ليست ميمَ جمع**: ميمُ الجمع لا تُفتح ولا تُكسر ولا تُنوَّن
# البتّة (هُمْ · هُمُ · كُمْ · كُمُ · تُمْ · تُمُ)، فالمفتوحةُ والمكسورةُ والمنوَّنةُ حرفُ أصلٍ
# في الكلمة (خَتَمَ · لِيَحْكُمَ · بُكْمٌ). مِسطرةٌ من الرسم المشكول نفسِه لا من صرفٍ خارجيّ.
_FAT, _KAS, _DAM, _SUK = "َ", "ِ", "ُ", "ْ"
_TANWEEN = ("ً", "ٌ", "ٍ")
_NOT_MIM_JAM = (_FAT, _KAS) + _TANWEEN


def _mim_mark(word):
    """حركةُ آخرِ ميمٍ في الكلمة المشكولة — و`""` إن لم تُكتب لها حركة."""
    i = word.rfind("م")
    if i < 0:
        return None
    for ch in word[i + 1:]:
        if ch in (_FAT, _KAS, _DAM, _SUK) or ch in _TANWEEN:
            return ch
    return ""


def population_audit(limit=0):
    """⭐⭐ **أزلّةٌ حقّاً ما تولّده الذراع (ب)، أم صورةٌ مشروعةٌ للأصل؟** (‏D-504)

    السؤالُ وارثُ درسِ D-503 (‏`license_ledger.population_b`): هناك كان **41.9٪** من «الزلّات»
    ليس زلّةً أصلاً، فصارت القاعدةُ أن يُسأل كلُّ مولِّدِ مجتمعٍ السؤالَ نفسَه قبل أن يُصدَّق رقمُه.
    وهنا **الجوابُ مختلفٌ، وقد قيس على المصحف كلِّه (71,250 حالةَ ذراعٍ (ب)):**

    ① 55.02٪ من الحالات **الكلمةُ فيها واحدةٌ حرفاً بحرف** في مصحفَي الروايتين
       (‏`عَلَيْهِمْ` · `ٱلَّذِينَ`) — ومع ذلك **هي زلّةٌ حقيقيّة**: الفرقُ في **النطق** لا الرسم
       (صلةُ ميم الجمع «عليهمو» · النقلُ «لذين»)، وهو ما يكتبه whisper مختلفاً فعلاً.
       ⛔ فـ«اتّحادُ الرسم» **ليس** دليلَ بطلانٍ هنا — ومَن ردَّ به لأسقط زلّاتِ ورشٍ الحقيقيّة.
    ② 98.9٪ منها يتساوى طرفاها تحت `norm` بكلّ مسطرةٍ من الثلاث — للسبب نفسِه: `norm` تُسقط
       الشكلَ الذي يحمل النقلَ والصلة، فالتساوي بعدها **أثرُ مسطرةٍ لا نفيُ زلّة**.
    ③ **والباطلُ المقيسُ ضئيل: 112 حالةً من 71,250 (0.16٪)** — ومصدرُها بابٌ واحدٌ بعينه:
       رخصةُ صلةِ ميم الجمع تُطبَّق بـ`endsWith("هم"/"كم"/"تم")` **في المحرك نفسِه**
       (`RecitationScorer.kt`: `profile.silaMeem && (f.endsWith("هم") || …)`)، فتنال كلماتٍ
       ميمُها حرفُ أصل: **خَتَمَ ⇒ «ختموا»** · بُكْمٌ · كَتَمَ · لِيَحْكُمَ · ٱللَّهُمَّ.
       المقيسُ في المصحف: **54 ظهوراً في ورشٍ (30 صورة) و40 في قالون (27 صورة)**، أي
       **0.77٪** من 7,008 ظهورٍ تنالها الرخصة.

    ⇒ **الحكم:** مجتمعُ الذراع (ب) **سليمٌ عند 0.16٪**، فأرقامُ سقف الكشف المنشورة (D-280)
      تبقى كما هي ولا تُراجَع. وهذا **حكمٌ مقيسٌ لا انطباع**: السؤالُ نفسُه أسقط `license_ledger`.

    ⚠️ وتبقى **الرخصةُ المشحونةُ عيباً قائماً في المحرك** (لا في هذه الأداة): تلاوةُ ورشٍ
    «ختموا» مكان «خَتَمَ» **لا تُصحَّح**. ⛔ ولم تُمَسّ هنا: `RecitationScorer.kt` مشغولٌ بفرعٍ
    غيرِ مدموج، وتضييقُ رخصةٍ مشحونةٍ يُحرّك بصماتِ التماثل كلَّها ⇒ يُسعَّر أوّلاً ثمّ يُقرَّر.

    يردّ: (‏كلُّ الحالات · الباطلةُ منها · أمثلة).
    """
    text = {r: prepare(r, limit) for r in RIWAYAT}
    raw = {r: [a.split() for a in load_text(r)[:limit or None]] for r in RIWAYAT}
    total = 0
    bogus = 0
    examples = []
    for e, s in itertools.permutations(RIWAYAT, 2):
        for a in range(len(text[e])):
            _, ww, real_e = text[e][a]
            _, ws, real_s = text[s][a]
            if len(real_e) != len(real_s) or not real_e:
                continue
            for ie, isx in zip(real_e, real_s):
                if ws[isx] == ww[ie]:
                    continue
                total += 1
                we, wx = raw[e][a][ie], raw[s][a][isx]
                if we != wx or _mim_mark(we) not in _NOT_MIM_JAM:
                    continue
                lo, hi = sorted((ww[ie], ws[isx]), key=len)
                if hi.startswith(lo) and hi[len(lo):] in ("و", "وا"):
                    bogus += 1
                    if len(examples) < 8:
                        examples.append((e, s, we, ww[ie], ws[isx]))
    return total, bogus, examples


def selftest():
    """🧪 **حارسُ سطح الزلّة الروائية** (‏D-504) — الأداةُ التي تُنتج أخطرَ جدولٍ في اللوحة
    (‏«طالبُ ورشٍ ينزلق إلى حفص فلا يُنبَّه في 99.7٪») لم يكن لها حارسٌ البتّة.

    يفحص أربعةَ أشياءَ لا يفحصها الضابطُ السالب (‏وهو ثقيلٌ: يبني الحاكمَ ويجري المصحف):
    ① **بناءُ الحالات** — أذرعٌ ثلاثةٌ لكلٍّ عقدُه: موضعُ الزلّة واحدٌ، والباقي تلاوةٌ صحيحة.
    ② **العدّادُ يميّز الموضع** — `analyse` بـ`skew` ينهار، بحاكمٍ مصطنعٍ في الذاكرة.
    ③ **عتبةُ الضابط لم تُليَّن** — 99٪ كشفاً و20 نقطةً انهياراً، وهو الحارسُ على الحارس.
    ④ ⭐⭐ **مجتمعُ الذراع (ب) ليس دائريّاً** — سؤالُ D-503 مطبَّقاً هنا، ورقمُه محفوظٌ بالنصّ.
    """
    ok = True

    def say(good, line):
        nonlocal ok
        ok &= bool(good)
        print(("✅ " if good else "❌ ") + line)

    # ① الأذرعُ الثلاثة: لكلِّ ذراعٍ عقدُه المكتوب
    ca = build(limit=12, arms="a")
    say(ca and all(c[0].startswith("a|") and c[3] == c[0].split("|")[1] for c in ca)
        and all(c[1].split() and c[2].split() for c in ca),
        "أ · كلُّ حالةٍ بروايتها ومرجعِها وتلاوتِها (‏%d حالة)" % len(ca))
    cc = build(limit=12, arms="c")
    say(cc and all(c[0].startswith("c|") and c[3] != c[0].split("|")[1] for c in cc),
        "ج · النصُّ نصُّ الرواية والملفُّ **ملفُّ غيرِها** (‏%d حالة)" % len(cc))

    cb = build(limit=12, arms="b")
    bad = []
    for name, ref, hyp, riw in cb:
        arm, e, s, _a, i = name.split("|")
        i = int(i)
        cfg = P.config_for(e)
        toks = ref.split()
        base = [P.whisper_forms(x, cfg)[-1] if scorer.norm(x, cfg) else "" for x in toks]
        # ⚠️ علاماتُ الوقف تُطبَّع إلى فراغٍ فتسقط عند `" ".join` — فالموضعُ يُنقل إلى
        # ترقيمِ ما نُطق فعلاً، وإلّا قارنّا قائمتين مختلفتَي الطول.
        spoken = " ".join(base).split()
        got = hyp.split()
        at = sum(1 for x in base[:i] if x)
        diff = [j for j in range(min(len(spoken), len(got))) if spoken[j] != got[j]]
        if riw != e or len(spoken) != len(got) or diff != [at]:
            bad.append(name)
    say(cb and not bad,
        "ب · **كلمةٌ واحدةٌ بالضبط** هي المزلولة وموضعُها هو المعلَن (‏%d حالة · شواذ %d)"
        % (len(cb), len(bad)))

    # ②⭐ الضابطُ يزرع كلمةً **غريبةً عن المصحف** — لا صورةَ روايةٍ أخرى
    cf = build(limit=12, arms="b", foreign=True)
    say(cf and all(FOREIGN in c[2].split() for c in cf)
        and all(FOREIGN not in a for a in load_text("hafs")[:200]),
        "🧪 الضابطُ يزرع «%s» وهي **ليست في المصحف رسماً**" % FOREIGN)

    # ③ الآيةُ التي اختلف عددُ كلماتها بين الروايتين **تُطرح** ولا تُحاذى كلمةً بكلمة
    tx = {r: prepare(r, 12) for r in RIWAYAT}
    skipped = sum(1 for e, s in itertools.permutations(RIWAYAT, 2)
                  for a in range(len(tx[e]))
                  if len(tx[e][a][2]) != len(tx[s][a][2]))
    say(all(int(c[0].split("|")[3]) < len(tx[c[0].split("|")[1]]) for c in cb),
        "الحالاتُ كلُّها داخلَ المدى (‏وآياتٌ مطروحةٌ لاختلاف العدّ: %d)" % skipped)

    # ④⭐ العدّادُ معلّقٌ بالموضع: حاكمٌ مصطنعٌ يكشف في الموضع المعلَن وحدَه
    pick = cb[:40]
    eng = {}
    for name, ref, hyp, riw in pick:
        i = int(name.split("|")[4])
        v = ["C"] * len(ref.split())
        v[i] = "S"
        eng[name] = (v, [])
    good, _ = analyse(pick, eng, skew=0)
    skew1, _ = analyse(pick, eng, skew=1)
    d0 = sum(v["det"] for v in good.values())
    d1 = sum(v["det"] for v in skew1.values())
    n0 = sum(v["n"] for v in good.values())
    say(n0 == len(pick) and d0 == n0 and d1 < n0 * 0.35,
        "⭐ الكشفُ %d/%d وبإزاحةِ الموضعِ واحداً %d — العدّادُ يميّز الموضع" % (d0, n0, d1))

    # ⑤ الزيادةُ (‏`A`) كشفٌ ولو كان الموضعُ سليماً — وإلّا عُدّت الزلّةُ المسموعةُ فواتاً
    add = {pick[0][0]: (["C"] * len(pick[0][1].split()), ["دخيلة"])}
    acc_add, _ = analyse(pick[:1], add)
    say(sum(v["det"] for v in acc_add.values()) == 1,
        "الزيادةُ في المسموع كشفٌ (‏`adds`) لا فوات")

    # ⑥ حالةٌ لا جوابَ لها من الحاكم **تُطرح ولا تُعدّ فواتاً** — وإلّا هبط الرقمُ بصمتٍ
    acc_gap, _ = analyse(pick, {})
    say(not acc_gap, "ما لم يجب عنه الحاكمُ لا يدخل العدَّ البتّة")

    # ⑦ عتبةُ الضابط السالب لم تُليَّن (‏⛔ درسُ الدستور: العلاجُ عيّنةٌ أكبر لا عتبةٌ أصغر)
    src = io.open(os.path.abspath(__file__), encoding="utf-8").read()
    say('pct(d0, n0) >= 99.0 and pct(d0, n0) - pct(d1, n0) >= 20.0' in src,
        "⛔ عتبةُ الضابط كما هي: كشفٌ ≥99٪ وانهيارٌ ≥20 نقطة")
    say("if not hit and len(misses) < 400" in src, "وأمثلةُ الفوات محفوظةٌ للتشريح")

    # ⑧⭐⭐ المجتمعُ ليس دائريّاً — ورقمُه مقيسٌ على عيّنتين
    t1, b1, ex = population_audit(limit=60)
    t2, b2, _ = population_audit(limit=180)
    r1 = 100.0 * b1 / t1 if t1 else 0.0
    r2 = 100.0 * b2 / t2 if t2 else 0.0
    say(t1 > 400 and r1 <= 1.0 and r2 <= 1.0,
        "⭐⭐ باطلُ المجتمع %d/%d (%.2f٪) و%d/%d (%.2f٪) — دون 1٪ في العيّنتين"
        % (b1, t1, r1, b2, t2, r2))
    say(all(_mim_mark(w) in _NOT_MIM_JAM for _, _, w, _, _ in ex) if ex else True,
        "وكلُّ ما عُدّ باطلاً ميمُه مفتوحةٌ أو مكسورةٌ أو منوَّنة (‏%d مثال)" % len(ex))

    # ⑨ المِسطرةُ نفسُها تُختبر على كلماتٍ من المصحف — لا على مصنوعاتٍ تشهد لنفسها
    say(_mim_mark("خَتَمَ") == _FAT and _mim_mark("بُكْمٌ") in _TANWEEN
        and _mim_mark("عَلَيْهِمْ") == _SUK and _mim_mark("لَهُم") == ""
        and _mim_mark("قَالَ") is None,
        "مِسطرةُ ميم الجمع: خَتَمَ فتحٌ · بُكْمٌ تنوينٌ · عَلَيْهِمْ سكونٌ · لَهُم بلا حركة")
    say(_NOT_MIM_JAM == (_FAT, _KAS) + _TANWEEN and _DAM not in _NOT_MIM_JAM
        and _SUK not in _NOT_MIM_JAM,
        "⛔ والمضمومةُ والساكنةُ **لا تُعَدّان باطلتين** — فميمُ الجمع تكون بهما")

    # ⑩ حارسُ مصدرٍ: رقمُ المجتمع وبابُه لا يُمحيان بصمتٍ من التوثيق
    doc = population_audit.__doc__
    say(all(k in doc for k in ("0.16", "112", "71,250", "خَتَمَ", "RecitationScorer.kt", "0.77")),
        "حارسُ مصدر: رقمُ الباطل وبابُه ومثالُه في التوثيق")
    say("⛔ فـ«اتّحادُ الرسم» **ليس** دليلَ بطلانٍ هنا" in doc,
        "⛔ والدرسُ المضادُّ محفوظ: اتّحادُ الرسم لا يُبطل زلّةَ النطق")

    print("\n%s" % ("✅ حارسُ سطح الزلّة الروائية: تمّ" if ok else "❌ حارسُ سطح الزلّة: أخفق"))
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description="سطحُ الزلّة الروائية على حاكم المحرك")
    ap.add_argument("--limit", type=int, default=0, help="أوّل ن آية فقط (للتجربة)")
    ap.add_argument("--arms", default="abc", help="الأذرعُ المطلوبة من abc")
    ap.add_argument("--examples", type=int, default=6, help="كم زلّةً غيرَ مكشوفةٍ تُطبع")
    ap.add_argument("--control", action="store_true", help="الضابطُ السالب وحدَه")
    ap.add_argument("--why", action="store_true",
                    help="تشريحُ ما فات الطبقةَ الأولى: سببُه · وهل تراه الطبقةُ الثانية")
    ap.add_argument("--audit-population", action="store_true",
                    help="أزلّةٌ حقّاً ما تولّده الذراع (ب)؟ — جردُ الباطل بلا حاكم")
    ap.add_argument("--selftest", action="store_true", help="🧪 حارسُ الأداة (ثوانٍ · بلا حاكم)")
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    if args.audit_population:
        t, b, ex = population_audit(args.limit)
        print("حالاتُ (ب) %d · باطلةٌ %d (%.2f٪)" % (t, b, 100.0 * b / t if t else 0.0))
        for e, s, w, fe, fs in ex:
            print("   %s ⇜ %s  %s : %s / %s" % (e, s, w, fe, fs))
        return 0
    os.makedirs(WORK, exist_ok=True)
    if args.control:
        return control(args.limit or 400)
    if args.why:
        return why(args.limit)
    cases = build(args.limit, args.arms)
    print("حالات: %d" % len(cases))
    eng = run_engine(cases, os.path.join(WORK, "engine_riwaya_surface.tsv"))
    acc, misses = analyse(cases, eng)
    report(acc, misses, args.examples)
    return 0


if __name__ == "__main__":
    sys.exit(main())
