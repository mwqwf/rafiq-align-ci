# -*- coding: utf-8 -*-
"""🔀 **هل يُفتح البابُ الثاني بثمنٍ صفريّ؟** — ذراعُ أسبقيّةِ التسامح. بلا صوت.

⚠️ **لِمَ وُجد.** أغلقت D-287 البابَ الثاني (`RiwayaSlipDetector`) بصفقةٍ لا تُشترى:
**+705** زلّةً عمياء مقابل **−598** اتّهاماً كاذباً على مَن تلا صحيحاً بروايته (1.18 : 1)،
على أثمنِ رقمٍ في اللوحة (أرضيّةُ الطبقة الأولى **0** من 232,288). ولاحظت في نتيجتها الرابعة
أنّ أمثلةَ الاتّهام الكاذب **كلَّها صورةُ تطبيعٍ واحدة** (‏`مَٰلِكِ`⇜«ملك» · `قَٰتَلَ`⇜«قتل»).
وبقي ما يليه بلا سؤال: **أهي صورةٌ عارضةٌ أم سطرٌ بعينِه؟ وإن كان سطراً، فكم يكلّف نقلُه؟**

**والجواب سطرٌ بعينِه** في `RiwayaSlipDetector.detect`:

    val exact = forms.filter { r != current && w != mine && norm(w) == h }
    if (exact.isEmpty() && matches(mine, h, myProfile)) return null   // ⇜ الشرطُ هنا

أي **المطابقةُ الحرفيّةُ لروايةٍ أخرى تسبق تسامحَ روايتك**: فحفصٌ تلا `مَٰلِكِ` صحيحاً، وصورتُه
المسموعة «ملك» يقبلها بابُ القبول لحفص (‏الخنجريّةُ الاختيارية · D-276)، لكنّها تطابق حرفيّاً
كلمةَ ورشٍ وقالون `مَلِكِ` ⇒ فيُتَّهم. والتعليقُ في المحرك **يقصد** هذا الترتيب ويذكره صراحةً،
فالسؤالُ ليس «أعطبٌ هو؟» بل **«كم ثمنُه وكم فائدتُه؟»** — ولم يُقَسا قطّ.

**الذراعُ المقيس (ت):** يُقدَّم التسامحُ على المطابقة الحرفيّة — مكانُ سطرٍ واحدٍ يتغيّر.
يُقاس بعملة D-286/D-287 نفسِها فتُقارن الأرقامُ مباشرةً:

    الفائدة = زلّةٌ روائيةٌ حقيقيةٌ عمِيَ عنها بابُ القبول ⇒ يردّها البابُ الثاني
              (‏المصحف كلُّه · الاتّجاهاتُ الستّة · 71,254 زوجاً)
    التكلفة = انزلاقٌ يُتَّهم به مَن تلا **صحيحاً بروايته** (‏232,288 موضعاً · ثلاثُ روايات)

    python tools/tasmi_bench/riwaya_gate_arms.py --control   # 🧪 الضوابطُ أوّلاً
    python tools/tasmi_bench/riwaya_gate_arms.py             # المصحف كلُّه

⚠️ يلزم مخرَجُ الطبقة الأولى `work/engine_riwaya_surface.tsv` (‏`riwaya_surface.py --arms b`).
⛔ لا يُمَسّ ملفُّ محرّكٍ على القرص، ولا يُغيَّر افتراضٌ مشحون: الذراعُ في
`engine_judge/SlipArmJudge.kt` وحدَه. قياسٌ وتقريرٌ لا قرار.
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
import riwaya_second_layer as S  # noqa: E402  (‏مصدرٌ واحدٌ لبناء الحالات — لا نسخَ ثانٍ)

RIWAYAT = S.RIWAYAT
WORK = S.WORK
DAGGER = "ٰ"                    # الألفُ الخنجرية — الصورةُ التي أسندت إليها D-281/D-287


def run_arms(cases, out_tsv):
    """يبني حاكمَ الذراعين ويشغّله. المخرَج: name ⇒ (المشحون، ذراعُ ت)."""
    src = os.path.join(WORK, "cases_gate_arms.tsv")
    os.makedirs(WORK, exist_ok=True)
    with io.open(src, "w", encoding="utf-8") as f:
        for row in cases:
            f.write("\t".join(row) + "\n")
    subprocess.run(["bash", os.path.join(HERE, "engine_judge", "build_and_run_arm.sh"),
                    src, out_tsv], check=True)
    got = {}
    for line in io.open(out_tsv, encoding="utf-8"):
        if not line.strip():
            continue
        f = line.rstrip("\n").split("\t")
        got[f[0]] = (f[1], f[2])
    return got


def pct(a, b):
    return 100.0 * a / b if b else 0.0


def measure(limit=0, examples=6):
    eng = S.layer1()
    if eng is None:
        return 1

    # ═══ ١ · الثمن: أرضيّةُ الاتّهام الكاذب (تلاوةٌ صحيحةٌ تامّةٌ بروايتها) ═══
    floor = S.build_floor(limit)
    print("حالاتُ الأرضيّة (تلاوةٌ صحيحة): %d" % len(floor))
    fd = run_arms(floor, os.path.join(WORK, "arms_floor.tsv"))
    fa = collections.Counter()
    kept = []                                   # ما بقي متّهَماً في ذراع (ت)
    for name, ref, heard, riw, _enc in floor:
        sh, ar = fd.get(name, ("-", "-"))
        fa[(riw, "n")] += 1
        if sh != "-":
            fa[(riw, "sh")] += 1
            fa[("dagger", "sh")] += 1 if DAGGER in ref else 0
        if ar != "-":
            fa[(riw, "ar")] += 1
            if len(kept) < 20:
                kept.append((name, ref, heard, ar))

    print("\n=== أرضيّةُ الاتّهام الكاذب — المشحونُ مقابلَ ذراعِ (ت) ===")
    tn = tsh = tar = 0
    for r in RIWAYAT:
        n, sh, ar = fa[(r, "n")], fa[(r, "sh")], fa[(r, "ar")]
        tn += n
        tsh += sh
        tar += ar
        print("  %-6s  مواضع %7d · المشحون %5d (%.3f٪) · ذراعُ(ت) %5d (%.3f٪)"
              % (r, n, sh, pct(sh, n), ar, pct(ar, n)))
    print("  %-6s  مواضع %7d · المشحون %5d (%.3f٪) · ذراعُ(ت) %5d (%.3f٪)"
          % ("المجموع", tn, tsh, pct(tsh, tn), tar, pct(tar, tn)))
    print("  ⇒ يُلغي الذراعُ %d اتّهاماً كاذباً من %d (%.1f٪)%s"
          % (tsh - tar, tsh, pct(tsh - tar, tsh),
             " ⇒ **أرضيّةٌ صفرٌ**" if tar == 0 else ""))
    print("  🧬 ومن اتّهامات المشحون ما مرجعُه خنجريّ: %d من %d (%.1f٪)"
          % (fa[("dagger", "sh")], tsh, pct(fa[("dagger", "sh")], tsh)))

    # ═══ ٢ · الفائدة: ما يردّه البابُ الثاني من عمى بابِ القبول ═══
    slips = S.build_slips(limit)
    print("\nحالاتُ الزلّة: %d" % len(slips))
    det = run_arms(slips, os.path.join(WORK, "arms_slip.tsv"))
    acc = collections.defaultdict(lambda: dict(n=0, blind=0, sh=0, ar=0))
    lost = []                                   # زلّةٌ يردّها المشحونُ ويفوّتها الذراع
    for name, ref, heard, riw, _enc in slips:
        got = eng.get(name)
        if got is None:
            continue
        verdicts, adds = got
        _arm, e, s, _a, i = name.split("|")
        i = int(i)
        v = verdicts[i] if i < len(verdicts) else "?"
        if (v != "C") or bool(adds):
            continue                            # كشفتها الطبقةُ الأولى ⇒ ليست عمياء
        sh, ar = det.get(name, ("-", "-"))
        k = acc[(e, s)]
        k["blind"] += 1
        k["sh"] += 1 if sh != "-" else 0
        k["ar"] += 1 if ar != "-" else 0
        if sh != "-" and ar == "-" and len(lost) < 20:
            lost.append((name, ref, heard, sh))

    print("\n=== ما يردّه البابُ الثاني من العمى — المشحونُ مقابلَ ذراعِ (ت) ===")
    tb = tsh2 = tar2 = 0
    for (e, s) in sorted(acc):
        k = acc[(e, s)]
        tb += k["blind"]
        tsh2 += k["sh"]
        tar2 += k["ar"]
        print("  %-6s ⇜ %-6s  عمياء %5d · المشحون %4d · ذراعُ(ت) %4d"
              % (e, s, k["blind"], k["sh"], k["ar"]))
    print("  %-15s عمياء %5d · المشحون %4d (%.1f٪) · ذراعُ(ت) %4d (%.1f٪)"
          % ("المجموع", tb, tsh2, pct(tsh2, tb), tar2, pct(tar2, tb)))

    # ═══ ٣ · الصفقة ═══
    print("\n=== ⚖️ الصفقة ===")
    print("  المشحونُ لو رُفعت المصفاة : +%d زلّة · −%d اتّهاماً كاذباً" % (tsh2, tsh))
    print("  ذراعُ (ت) لو رُفعت المصفاة: +%d زلّة · −%d اتّهاماً كاذباً" % (tar2, tar))
    print("  ثمنُ الذراع: %d زلّةً فُقدت من %d (%.1f٪) · وفائدتُه: %d اتّهاماً كاذباً أُلغي"
          % (tsh2 - tar2, tsh2, pct(tsh2 - tar2, tsh2 or 1), tsh - tar))

    if lost:
        print("\n=== أمثلةٌ · زلّةٌ يردّها المشحونُ ويفوّتها الذراع ===")
        for name, ref, heard, ids in lost[:examples]:
            print("  %s · مرجع «%s» · سُمع «%s» ⇒ كان يُنسب إلى %s" % (name, ref, heard, ids))
    if kept:
        print("\n=== أمثلةٌ · اتّهامٌ كاذبٌ بقي في الذراع ===")
        for name, ref, heard, ids in kept[:examples]:
            print("  %s · مرجع «%s» · سُمع «%s» ⇒ نُسب إلى %s" % (name, ref, heard, ids))
    return 0


def control(limit=600):
    """🧪 الضوابطُ (‏قاعدةُ D-279) — على الذراعين معاً، فالذراعُ لا يُصدَّق أخضرُه بلا عدّادٍ حيّ.

    ١ · **حيويّة:** زلّةٌ حقيقيةٌ في مواضع الفرش ⇒ يجب أن يفتح الذراعُ كثيراً (وإلا فهو أخرس).
    ٢ · **سالبٌ · بلا فرش:** الفروقُ مُفرَغة ⇒ يجب **0** في الذراعين (لا تخمينَ بلا فرش).
    ٣ · **سالبٌ · كلمةٌ غريبة:** «الحاسوب» مكانَ المسموع ⇒ يجب **0**: الغريبةُ خطأٌ لا انزلاق.
    ٤ · **مطابقةُ المشحون:** عمودُ المشحون في هذا الحاكم يجب أن يطابق `SlipJudge` حرفاً بحرف.
    """
    a = S.build_slips(limit)
    b = S.build_slips(limit, blind_diffs=True)
    c = S.build_slips(limit, foreign=True)
    ra = run_arms(a, os.path.join(WORK, "ctl_arms_a.tsv"))
    rb = run_arms(b, os.path.join(WORK, "ctl_arms_b.tsv"))
    rc = run_arms(c, os.path.join(WORK, "ctl_arms_c.tsv"))
    n1s = sum(1 for v in ra.values() if v[0] != "-")
    n1a = sum(1 for v in ra.values() if v[1] != "-")
    n2 = sum(1 for v in rb.values() if v[0] != "-" or v[1] != "-")
    n3 = sum(1 for v in rc.values() if v[0] != "-" or v[1] != "-")

    # ٤ · المشحونُ هنا = المشحونُ في SlipJudge (حاكمٌ آخرُ · مسارُ بناءٍ آخر)
    ref = S.run_detector(a, os.path.join(WORK, "ctl_arms_ref.tsv"))
    mism = sum(1 for k, v in ref.items() if (ra.get(k, ("?", "?"))[0] != v))

    print("\n🧪 الضوابط (‏أوّلُ %d آية · %d حالة):" % (limit, len(a)))
    print("  ١ حيويّة  · زلّةٌ حقيقية      ⇒ المشحون %5d · ذراعُ(ت) %5d" % (n1s, n1a))
    print("  ٢ سالب    · بلا فروقِ فرش    ⇒ فتح %5d (يجب 0)" % n2)
    print("  ٣ سالب    · كلمةٌ غريبة      ⇒ فتح %5d (يجب 0)" % n3)
    print("  ٤ مطابقة  · المشحون = SlipJudge ⇒ اختلاف %5d من %d (يجب 0)" % (mism, len(ref)))
    ok = n1s >= 20 and n1a >= 20 and n2 == 0 and n3 == 0 and mism == 0
    print("  %s" % ("✅ العدّادان حيّان · لا فتحَ بلا سند · والمشحونُ مطابق" if ok
                    else "🚨 ضابطٌ سقط — لا يُوثق برقمٍ من هذا العدّاد"))
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description="ذراعُ أسبقيّة التسامح في الباب الثاني")
    ap.add_argument("--limit", type=int, default=0, help="أوّل ن آية فقط (للتجربة)")
    ap.add_argument("--examples", type=int, default=6)
    ap.add_argument("--control", action="store_true", help="الضوابطُ وحدَها")
    args = ap.parse_args()
    os.makedirs(WORK, exist_ok=True)
    if args.control:
        return control(args.limit or 600)
    return measure(args.limit, args.examples)


if __name__ == "__main__":
    sys.exit(main())
