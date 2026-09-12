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


def main():
    ap = argparse.ArgumentParser(description="سطحُ الزلّة الروائية على حاكم المحرك")
    ap.add_argument("--limit", type=int, default=0, help="أوّل ن آية فقط (للتجربة)")
    ap.add_argument("--arms", default="abc", help="الأذرعُ المطلوبة من abc")
    ap.add_argument("--examples", type=int, default=6, help="كم زلّةً غيرَ مكشوفةٍ تُطبع")
    ap.add_argument("--control", action="store_true", help="الضابطُ السالب وحدَه")
    ap.add_argument("--why", action="store_true",
                    help="تشريحُ ما فات الطبقةَ الأولى: سببُه · وهل تراه الطبقةُ الثانية")
    args = ap.parse_args()
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
