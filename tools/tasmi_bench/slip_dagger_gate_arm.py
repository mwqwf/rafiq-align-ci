# -*- coding: utf-8 -*-
"""🔀 **أتفصل لافتةُ الخنجرية ما قالت D-288 إنّه لا ينفصل؟** — الذراعُ الثالثةُ في الباب الثاني. بلا صوت.

⚠️ **لِمَ وُجدت.** قاست D-288 ذراعَ «أسبقيّةِ التسامح» (‏ت) على المحرك فوجدتها **تُلغي كلَّ**
الاتّهام الكاذب و**تُطفئ معه 99.7٪** من الكشف، وخلصت إلى أنّ «الفائدةَ والتكلفةَ تُنتجهما
العبارةُ نفسُها ⇒ لا شرطَ يفصل بينهما». ثم سلّم سجلُّ المناوبة (‏دَينُ D-405) الصيغةَ التي لم
تُجرَّب بعد: **«يُقدَّم التسامحُ إن كان الفرقُ بين الرسمين الخنجريّةَ وحدَها، ويبقى المشحونُ
فيما عداها»** — وهي دعوى D-288 مُختبَرةً لا مُعادة، لأنّ:

    الاتّهامُ الكاذب  ⇜ مرجعُه خنجريٌّ في 226 من 227 (‏99.6٪ · D-405)
    الكشفُ الحقيقيّ   ⇜ `تَعْمَلُونَ`⇜«يعملون» · `يَبْغُونَ`⇜«تبغون» — تاءٌ وياءٌ لا خنجرية

فإن كانت اللافتةُ تفصل، فالثمنُ الذي دفعته (ت) كلَّه ليس لازماً.

**ذراعُ (خ) = سطرٌ واحدٌ يتغيّر** في `SlipDaggerArmJudge.kt` (لا في المحرك):

    daggerOnly = exact ليست خالية وكلُّ صورةٍ فيها لا تفارق صورتَك إلّا بالألف الخنجرية
    if ((exact.isEmpty() || daggerOnly) && matches(mine, h, myProfile)) return null

والعملةُ عملةُ D-286/D-287/D-288 نفسُها فتُقارن الأرقامُ مباشرةً:

    الفائدة = زلّةٌ روائيةٌ حقيقيةٌ عمِيَ عنها بابُ القبول ⇒ يردّها البابُ الثاني
              (‏المصحف كلُّه · الاتّجاهاتُ الستّة · 71,250 زوجاً)
    التكلفة = انزلاقٌ يُتَّهم به مَن تلا **صحيحاً بروايته** (‏232,288 موضعاً · ثلاثُ روايات)

    python tools/tasmi_bench/slip_dagger_gate_arm.py --control   # 🧪 الضوابطُ أوّلاً
    python tools/tasmi_bench/slip_dagger_gate_arm.py             # المصحف كلُّه

⚠️ يلزم مخرَجُ الطبقة الأولى `work/engine_riwaya_surface.tsv` (‏`riwaya_surface.py --arms b`)،
   ويلزم للضابط الرابع مخرَجُ `riwaya_gate_arms.py` (‏`work/arms_floor.tsv` · `work/arms_slip.tsv`).
⛔ لا يُمَسّ ملفُّ محرّكٍ على القرص، ولا يُغيَّر افتراضٌ مشحون: قياسٌ وتقريرٌ لا قرار.
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
DAGGER = "ٰ"


def run_arms(cases, out_tsv):
    """يبني حاكمَ الأذرع الثلاثة ويشغّله. المخرَج: name ⇒ (المشحون، ذراعُ ت، ذراعُ خ)."""
    src = os.path.join(WORK, "cases_dagger_arm.tsv")
    os.makedirs(WORK, exist_ok=True)
    with io.open(src, "w", encoding="utf-8") as f:
        for row in cases:
            f.write("\t".join(row) + "\n")
    subprocess.run(["bash", os.path.join(HERE, "engine_judge", "build_and_run_dagger.sh"),
                    src, out_tsv], check=True)
    got = {}
    for line in io.open(out_tsv, encoding="utf-8"):
        if not line.strip():
            continue
        f = line.rstrip("\n").split("\t")
        got[f[0]] = (f[1], f[2], f[3])
    return got


def _prev(path):
    """مخرَجُ `riwaya_gate_arms.py` السابق (‏name ⇒ (المشحون، ذراعُ ت)) — للضابط الرابع."""
    p = os.path.join(WORK, path)
    if not os.path.isfile(p):
        return None
    out = {}
    for line in io.open(p, encoding="utf-8"):
        if not line.strip():
            continue
        f = line.rstrip("\n").split("\t")
        out[f[0]] = (f[1], f[2])
    return out


def _parity(got, prev, label):
    """الضابطُ الرابع: عمودا المشحونِ و(ت) هنا = عمودا `SlipArmJudge` حالةً حالةً."""
    if prev is None:
        print("  ⚠️ %s: لا مخرَجَ سابقٌ للمقارنة (شغّل `riwaya_gate_arms.py`) ⇒ الضابطُ لم يُشغَّل" % label)
        return None
    bad = sum(1 for k, v in got.items() if prev.get(k, ("?", "?"))[:2] != v[:2])
    print("  %s: اختلافُ عمودَي المشحون و(ت) عن `SlipArmJudge` ⇒ %d من %d %s"
          % (label, bad, len(got), "✅" if bad == 0 else "🚨"))
    return bad


def pct(a, b):
    return 100.0 * a / b if b else 0.0


def measure(limit=0, examples=8):
    eng = S.layer1()
    if eng is None:
        return 1

    # ═══ ١ · الثمن: أرضيّةُ الاتّهام الكاذب (تلاوةٌ صحيحةٌ تامّةٌ بروايتها) ═══
    floor = S.build_floor(limit)
    print("حالاتُ الأرضيّة (تلاوةٌ صحيحة): %d" % len(floor))
    fd = run_arms(floor, os.path.join(WORK, "dagger_floor.tsv"))
    p_floor = _parity(fd, _prev("arms_floor.tsv"), "ضابطُ الأرضيّة")
    fa = collections.Counter()
    kept = []                                   # ما بقي متّهَماً في ذراع (خ)
    for name, ref, heard, riw, _enc in floor:
        sh, tol, dag = fd.get(name, ("-", "-", "-"))
        fa[(riw, "n")] += 1
        fa[(riw, "sh")] += 1 if sh != "-" else 0
        fa[(riw, "tol")] += 1 if tol != "-" else 0
        if dag != "-":
            fa[(riw, "dag")] += 1
            if len(kept) < 20:
                kept.append((name, ref, heard, dag))

    print("\n=== ١ · الثمن: أرضيّةُ الاتّهام الكاذب — المشحونُ · ذراعُ(ت) · ذراعُ(خ) ===")
    tn = tsh = ttol = tdag = 0
    for r in RIWAYAT:
        n, sh, tol, dag = (fa[(r, "n")], fa[(r, "sh")], fa[(r, "tol")], fa[(r, "dag")])
        tn, tsh, ttol, tdag = tn + n, tsh + sh, ttol + tol, tdag + dag
        print("  %-6s  مواضع %7d · المشحون %4d (%.3f٪) · ذراعُ(ت) %4d · ذراعُ(خ) %4d (%.3f٪)"
              % (r, n, sh, pct(sh, n), tol, dag, pct(dag, n)))
    print("  %-6s  مواضع %7d · المشحون %4d (%.3f٪) · ذراعُ(ت) %4d · ذراعُ(خ) %4d (%.3f٪)"
          % ("المجموع", tn, tsh, pct(tsh, tn), ttol, tdag, pct(tdag, tn)))
    print("  ⇒ يُلغي ذراعُ(خ) %d اتّهاماً كاذباً من %d (%.1f٪)"
          % (tsh - tdag, tsh, pct(tsh - tdag, tsh)))

    # ═══ ٢ · الفائدة: ما يردّه البابُ الثاني من عمى بابِ القبول ═══
    slips = S.build_slips(limit)
    print("\nحالاتُ الزلّة: %d" % len(slips))
    det = run_arms(slips, os.path.join(WORK, "dagger_slip.tsv"))
    p_slip = _parity(det, _prev("arms_slip.tsv"), "ضابطُ الزلّة")
    acc = collections.defaultdict(lambda: dict(n=0, blind=0, sh=0, tol=0, dag=0))
    lost = []                                   # زلّةٌ يردّها المشحونُ ويفوّتها ذراعُ (خ)
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
        sh, tol, dag = det.get(name, ("-", "-", "-"))
        k = acc[(e, s)]
        k["blind"] += 1
        k["sh"] += 1 if sh != "-" else 0
        k["tol"] += 1 if tol != "-" else 0
        k["dag"] += 1 if dag != "-" else 0
        if sh != "-" and dag == "-" and len(lost) < 20:
            lost.append((name, ref, heard, sh))

    print("\n=== ٢ · الفائدة: ما يردّه البابُ الثاني من العمى — الأذرعُ الثلاثة ===")
    t = collections.Counter()
    for (e, s) in sorted(acc):
        k = acc[(e, s)]
        for key in ("blind", "sh", "tol", "dag"):
            t[key] += k[key]
        print("  %-6s ⇜ %-6s  عمياء %6d · المشحون %4d · ذراعُ(ت) %4d · ذراعُ(خ) %4d"
              % (e, s, k["blind"], k["sh"], k["tol"], k["dag"]))
    print("  %-15s عمياء %6d · المشحون %4d · ذراعُ(ت) %4d · ذراعُ(خ) %4d"
          % ("المجموع", t["blind"], t["sh"], t["tol"], t["dag"]))

    print("\n=== ⚖️ الصفقةُ الثلاثيّة (‏لو رُفعت مصفاةُ `RiwayaSlips.forAyah`) ===")
    print("  المشحون  : +%d زلّة · %d اتّهاماً كاذباً" % (t["sh"], tsh))
    print("  ذراعُ (ت): +%d زلّة · %d اتّهاماً كاذباً ⇒ فُقد %d من %d كشفاً (%.1f٪)"
          % (t["tol"], ttol, t["sh"] - t["tol"], t["sh"], pct(t["sh"] - t["tol"], t["sh"])))
    print("  ذراعُ (خ): +%d زلّة · %d اتّهاماً كاذباً ⇒ فُقد %d من %d كشفاً (%.1f٪)"
          % (t["dag"], tdag, t["sh"] - t["dag"], t["sh"], pct(t["sh"] - t["dag"], t["sh"])))
    print("  🔑 فاللافتةُ الخنجريّةُ %s"
          % ("**تفصل**: تردُّ الاتّهامَ الكاذبَ وتُبقي الكشف"
             if (tsh - tdag) > 0 and (t["sh"] - t["dag"]) * 2 < (t["sh"] - t["tol"])
             else "**لا تفصل** فصلاً يغيّر حكمَ D-288"))

    if kept:
        print("\n=== أمثلةٌ · اتّهامٌ كاذبٌ بقي بعد ذراعِ (خ) ===")
        for name, ref, heard, ids in kept[:examples]:
            print("  %s · مرجع «%s» · سُمع «%s» ⇒ نُسب إلى %s%s"
                  % (name, ref, heard, ids, " 🧬خنجريّ" if DAGGER in ref else ""))
    if lost:
        print("\n=== أمثلةٌ · زلّةٌ يردّها المشحونُ ويفوّتها ذراعُ (خ) ===")
        for name, ref, heard, ids in lost[:examples]:
            print("  %s · مرجع «%s» · سُمع «%s» ⇒ كان يُنسب إلى %s" % (name, ref, heard, ids))
    return 0 if (p_floor in (0, None) and p_slip in (0, None)) else 1


def six(limit=0, examples=8):
    """أرضيّةُ الرواياتِ **الستّ** (‏بناءُ `riwaya_floor_six`) بالأذرع الثلاثة — لا الثلاثُ وحدَها.

    🔒 ولِمَ تُعاد على الستّ: أرضيّةُ D-404/D-405 المعلَنةُ (‏511) ستّيّةٌ لا ثلاثيّة، وأكبرُ
    بقيّتيها (‏الدوريُّ 106 · السوسيُّ 128) لا تظهر في الثلاث أصلاً ⇒ فبالستِّ وحدَها يُعرف
    أتردُّ اللافتةُ الخنجريّةُ الأرضيّةَ المعلَنةَ كلَّها أم طرفَها المقيسَ في الثلاث.
    """
    import riwaya_floor_six as F                # noqa: E402  (‏مصدرٌ واحدٌ لبناء حالات الستّ)
    cases = F.build_floor(S.ALL_RIWAYAT if hasattr(S, "ALL_RIWAYAT") else RIWAYAT, limit)
    print("حالاتُ أرضيّةِ الستّ (تلاوةٌ صحيحة): %d" % len(cases))
    got = run_arms(cases, os.path.join(WORK, "dagger_floor_six.tsv"))
    fa = collections.Counter()
    kept = []
    for name, ref, heard, riw, _enc in cases:
        sh, tol, dag = got.get(name, ("-", "-", "-"))
        fa[(riw, "n")] += 1
        fa[(riw, "sh")] += 1 if sh != "-" else 0
        fa[(riw, "tol")] += 1 if tol != "-" else 0
        if dag != "-":
            fa[(riw, "dag")] += 1
            if len(kept) < 20:
                kept.append((name, ref, heard, dag))
    print("\n=== أرضيّةُ الاتّهام الكاذب على الستّ — المشحونُ · ذراعُ(ت) · ذراعُ(خ) ===")
    tn = tsh = ttol = tdag = 0
    for r in S.ALL_RIWAYAT:
        n, sh, tol, dag = (fa[(r, "n")], fa[(r, "sh")], fa[(r, "tol")], fa[(r, "dag")])
        tn, tsh, ttol, tdag = tn + n, tsh + sh, ttol + tol, tdag + dag
        print("  %-6s  مواضع %7d · المشحون %4d (%.3f٪) · ذراعُ(ت) %4d · ذراعُ(خ) %4d (%.3f٪)"
              % (r, n, sh, pct(sh, n), tol, dag, pct(dag, n)))
    print("  %-6s  مواضع %7d · المشحون %4d (%.3f٪) · ذراعُ(ت) %4d · ذراعُ(خ) %4d (%.3f٪)"
          % ("المجموع", tn, tsh, pct(tsh, tn), ttol, tdag, pct(tdag, tn)))
    print("  ⇒ يُلغي ذراعُ(خ) %d اتّهاماً كاذباً من %d (%.1f٪)"
          % (tsh - tdag, tsh, pct(tsh - tdag, tsh)))
    if kept:
        print("\n=== أمثلةٌ · اتّهامٌ كاذبٌ بقي بعد ذراعِ (خ) ===")
        for name, ref, heard, ids in kept[:examples]:
            print("  %s · مرجع «%s» · سُمع «%s» ⇒ نُسب إلى %s%s"
                  % (name, ref, heard, ids, " 🧬خنجريّ" if DAGGER in ref else ""))
    return 0


def control(limit=600):
    """🧪 الضوابطُ (‏قاعدةُ D-279): حيويّةٌ · سالبان · ومطابقةُ عمودَي المشحون و(ت) لسابقهما."""
    a = S.build_slips(limit)
    b = S.build_slips(limit, blind_diffs=True)
    c = S.build_slips(limit, foreign=True)
    ra = run_arms(a, os.path.join(WORK, "ctl_dag_a.tsv"))
    rb = run_arms(b, os.path.join(WORK, "ctl_dag_b.tsv"))
    rc = run_arms(c, os.path.join(WORK, "ctl_dag_c.tsv"))
    n = lambda d, i: sum(1 for v in d.values() if v[i] != "-")  # noqa: E731
    print("\n🧪 الضوابط (‏أوّلُ %d آية · %d حالة):" % (limit, len(a)))
    print("  ١ حيويّة  · زلّةٌ حقيقية   ⇒ المشحون %5d · ذراعُ(ت) %5d · ذراعُ(خ) %5d"
          % (n(ra, 0), n(ra, 1), n(ra, 2)))
    print("  ٢ سالب    · بلا فروقِ فرش ⇒ %d · %d · %d (يجب 0)" % (n(rb, 0), n(rb, 1), n(rb, 2)))
    print("  ٣ سالب    · كلمةٌ غريبة   ⇒ %d · %d · %d (يجب 0)" % (n(rc, 0), n(rc, 1), n(rc, 2)))
    ok = (n(ra, 0) >= 20 and n(ra, 2) >= 20
          and n(rb, 0) == n(rb, 1) == n(rb, 2) == 0
          and n(rc, 0) == n(rc, 1) == n(rc, 2) == 0)
    print("  %s" % ("✅ الأذرعُ حيّةٌ ولا تفتح بلا سند" if ok else "🚨 ضابطٌ سقط — لا يُوثق برقم"))
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description="ذراعُ لافتةِ الخنجرية في كاشف الانزلاق الروائيّ")
    ap.add_argument("--limit", type=int, default=0, help="أوّل ن آية فقط (للتجربة)")
    ap.add_argument("--examples", type=int, default=8)
    ap.add_argument("--control", action="store_true", help="الضوابطُ وحدَها")
    ap.add_argument("--six", action="store_true", help="أرضيّةُ الرواياتِ الستِّ وحدَها")
    args = ap.parse_args()
    os.makedirs(WORK, exist_ok=True)
    if args.control:
        return control(args.limit or 600)
    if args.six:
        return six(args.limit, args.examples)
    return measure(args.limit, args.examples)


if __name__ == "__main__":
    sys.exit(main())
