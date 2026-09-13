# -*- coding: utf-8 -*-
"""🔀 **أرضيّةُ الاتّهام الكاذب للباب الثاني على الرواياتِ الستِّ كلِّها** — بلا صوت.

⚠️ **لِمَ وُجد.** أغلقت D-287 وD-288 البابَ الثاني (`RiwayaSlipDetector`) برقمِ أرضيّةٍ
‏**598** اتّهاماً كاذباً على مَن تلا صحيحاً بروايته، وختمت D-288 بحدٍّ صريحٍ على رقمها:

    «(٣) الأرضيّةُ على ثلاث رواياتٍ لها نصٌّ كامل والكاشفُ يعرف ستّاً ⇒ أرقامُ الاتّهام **حدٌّ أدنى**»

وهذا الحدُّ **ليس حدَّ بيانات بل حدَّ أداة**: `riwaya_surface.RIWAYAT = ("hafs","warsh","qalun")`
ثلاثةٌ بالاختيار، وفي أصول المستودع `core/quran/.../text_{shuba,douri,sousi}.jz` — **6236 آيةً
مشكولةً كاملةً لكلٍّ منها** كما لحفصٍ وورشٍ وقالون. فالحدُّ يُرفع بإضافة ثلاثِ رواياتٍ إلى
الحلقة لا أكثر. وهذا الملفُّ يفعله: يحوّل «حدّاً أدنى» إلى **رقمٍ تامٍّ على الرواياتِ الستّ**.

    الأرضيّة = انزلاقٌ يُتَّهم به مَن تلا **صحيحاً بروايته** (‏الرواياتُ الستُّ · 464,576 موضعاً)

🔒 **وشرطُ أن يكون للرقم معنى — ملفُّ الرواية:** `RiwayaProfile` يعطي شعبةَ والدوريَّ والسوسيَّ
‏`naql=false · silaMeem=false` أي **سلوكَ حفصٍ بعينِه**، و`parity_full.config_for` يعطيها ذلك
تلقائياً (‏النقلُ لورشٍ وحدَه، والصلةُ لورشٍ وقالون) ⇒ فالمرآةُ مطابقةٌ للمحرك في الستّ بلا تعديل.

    python tools/tasmi_bench/riwaya_floor_six.py --anchor    # ١ فحصُ الإرساء (بلا JVM)
    python tools/tasmi_bench/riwaya_floor_six.py --control   # ٢ إعادةُ رقمِ D-288 بالثلاث
    python tools/tasmi_bench/riwaya_floor_six.py             # ٣ الستُّ كلُّها

⛔ لا يُمَسّ ملفُّ محرّكٍ على القرص، ولا يُغيَّر افتراضٌ مشحون: قياسٌ وتقريرٌ لا غير.
"""
import argparse
import collections
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "tools", "alignment"))
import riwaya_surface as RS  # noqa: E402
import riwaya_second_layer as SL  # noqa: E402
from common import load_text  # noqa: E402

SIX = SL.ALL_RIWAYAT                     # الستُّ التي يعرفها الكاشف — وللستِّ نصٌّ كامل
THREE = RS.RIWAYAT                       # الثلاثُ التي قِيست في D-287/D-288
WORK = SL.WORK


def anchor_check():
    """١ · **فحصُ الإرساء** (بلا JVM): أيجد الكاشفُ موضعَ الفرش للرواياتِ الستّ أصلاً؟

    `detect` يُرسي الموضعَ **بنصّ الكلمة** لا بفهرسها (‏لأنّ عددَ الكلمات يختلف بين الروايات):
    لغيرِ حفصٍ `diffs[current].filter { otherWord == refWord }`. فإن لم تكن كلمةُ الرواية في
    صفِّ الفرش هي الكلمةَ نفسَها في نصِّ الرواية، فالبابُ **مغلقٌ بالبناء** هناك لا بالحكم.
    """
    diffs = SL.farsh_diffs()
    txt = {r: [a.split() for a in load_text(r)] for r in SIX}
    cnt = collections.Counter()
    ex = collections.defaultdict(list)
    for a, per in diffs.items():
        for r, rows in per.items():
            for (i, hw, ow) in rows:
                cnt[(r, "n")] += 1
                if hw not in txt["hafs"][a]:
                    cnt[(r, "hafs")] += 1
                if ow not in txt[r][a]:
                    cnt[(r, "other")] += 1
                    if len(ex[r]) < 3:
                        ex[r].append((a + 1, i, hw, ow))
    print("آياتٌ فيها فرش: %d" % len(diffs))
    print("\n=== ١ إرساءُ صفوف الفرش في نصوص الروايات ===")
    for r in SIX:
        if r == "hafs":
            continue
        n = cnt[(r, "n")]
        print("  %-6s صفوف %5d · كلمةُ حفصٍ غائبةٌ عن نصّ حفص %4d · كلمةُ الرواية غائبةٌ عن نصّها"
              " %5d (%.2f٪)" % (r, n, cnt[(r, "hafs")], cnt[(r, "other")],
                                SL.pct(cnt[(r, "other")], n)))
    for r in SIX:
        for (ayah, i, hw, ow) in ex[r]:
            print("     مثالٌ غيرُ مُرسًى · %s · آية %d · فهرس %d · حفص «%s» ⇐ «%s»" % (r, ayah, i, hw, ow))
    return 0


def build_floor(riwayat, limit=0):
    """ذراعُ الأرضيّة لأيِّ مجموعةِ رواياتٍ — بناءُ `riwaya_second_layer.build_floor` بعينِه."""
    text = {r: RS.prepare(r, limit) for r in riwayat}
    raw = {r: [a.split() for a in load_text(r)[:limit or None]] for r in riwayat}
    diffs = SL.farsh_diffs()
    cases = []
    for r in riwayat:
        for a in range(len(text[r])):
            _, ww, real = text[r][a]
            enc = SL.encode(diffs.get(a, {}))
            for i in real:
                cases.append(("f|%s|%s|%05d|%d" % (r, r, a, i), raw[r][a][i], ww[i], r, enc))
    return cases


def measure(riwayat, limit=0, examples=8, tag="floor_six"):
    cases = build_floor(riwayat, limit)
    print("حالاتُ الأرضيّة (تلاوةٌ صحيحةٌ تامّةٌ بروايتها): %d" % len(cases))
    got = SL.run_detector(cases, os.path.join(WORK, "slip_%s.tsv" % tag))
    fa = collections.Counter()
    ex = collections.defaultdict(list)
    for name, ref, heard, riw, _enc in cases:
        fa[(riw, "n")] += 1
        if got.get(name, "-") != "-":
            fa[riw] += 1
            if len(ex[riw]) < examples:
                ex[riw].append((name, ref, heard, got[name]))
    print("\n=== أرضيّةُ الاتّهام الكاذب للباب الثاني (‏مَن تلا صحيحاً بروايته) ===")
    tn = tb = 0
    for r in riwayat:
        n = fa[(r, "n")]
        tn += n
        tb += fa[r]
        print("  %-6s  مواضع %7d · اتُّهم بانزلاق %5d (%.3f٪)" % (r, n, fa[r], SL.pct(fa[r], n)))
    print("  %-6s  مواضع %7d · اتُّهم بانزلاق %5d (%.3f٪)" % ("المجموع", tn, tb, SL.pct(tb, tn)))
    print("\n=== أمثلةٌ · اتّهامٌ كاذبٌ أرضيّ (‏واحدٌ لكلِّ رواية) ===")
    for r in riwayat:
        for (name, ref, heard, ids) in ex[r][:1]:
            print("  %s · مرجع «%s» · سُمع «%s» ⇒ نُسب إلى %s" % (name, ref, heard, ids))
    return fa


def control(limit=0):
    """٢ · **ضابطُ الإسناد:** الثلاثُ وحدَها بهذه الأداة ⇒ يجب أن تُعيد رقمَ D-288 بعينِه.

    المرجعُ المحفوظ: حفص 57 · ورش 239 · قالون 302 ⇒ 598 من 232,288 موضعاً.
    """
    ref = {"hafs": 57, "warsh": 239, "qalun": 302}
    fa = measure(THREE, limit, tag="floor_three")
    ok = True
    print("\n🧪 ضابطُ الإسناد (‏مقابلَ D-288):")
    for r in THREE:
        good = fa[r] == ref[r]
        ok = ok and good
        print("  %-6s هنا %4d · D-288 %4d  %s" % (r, fa[r], ref[r], "✅" if good else "🚨 اختلاف"))
    print("  %s" % ("✅ الأداةُ تُعيد رقمَ D-288 حرفاً بحرف ⇒ توسيعُها إلى الستِّ مسنود"
                    if ok else "🚨 لا يُوثق برقمٍ من هذه الأداة حتى يُفهم الاختلاف"))
    return 0 if ok else 1


DAGGER = "ٰ"                        # الألفُ الخنجرية — صورةُ D-288 بعينِها


def anatomy(tag="floor_six"):
    """٤ · **تشريحُ الاتّهامات:** أصورةُ الخنجريةِ نفسُها (‏D-288) أم صورةٌ أخرى في الثلاثِ الجديدة؟

    يُقرأ من مخرَج الشوط (`work/slip_<tag>.tsv`) فلا يُعاد بناءُ JVM.
    """
    import io
    path = os.path.join(WORK, "slip_%s.tsv" % tag)
    if not os.path.isfile(path):
        print("🚨 لا مخرَجَ للشوط: شغّل الأداةَ بلا معلَمٍ أوّلاً (%s)." % path)
        return 1
    cases = {c[0]: c for c in build_floor(SIX)}
    per = collections.defaultdict(collections.Counter)
    attrib = collections.defaultdict(collections.Counter)
    forms = collections.defaultdict(collections.Counter)
    for line in io.open(path, encoding="utf-8"):
        f = line.rstrip("\n").split("\t")
        if len(f) < 2 or f[1] == "-" or f[0] not in cases:
            continue
        r = f[0].split("|")[1]
        ref, heard = cases[f[0]][1], cases[f[0]][2]
        per[r]["n"] += 1
        per[r]["dagger"] += 1 if DAGGER in ref else 0
        for x in f[1].split(","):
            attrib[r][x] += 1
        forms[r][(ref, heard)] += 1
    print("\n=== ٤ تشريحُ الاتّهامات ===")
    tn = td = 0
    for r in SIX:
        k = per[r]
        tn += k["n"]
        td += k["dagger"]
        print("  %-6s اتّهامات %4d · مرجعُه يحمل الألفَ الخنجرية %4d (%.0f٪) · نُسب إلى: %s"
              % (r, k["n"], k["dagger"], SL.pct(k["dagger"], k["n"]),
                 " ".join("%s=%d" % kv for kv in attrib[r].most_common())))
    print("  المجموع %d · بالخنجرية %d (%.2f٪)" % (tn, td, SL.pct(td, tn)))
    print("\n=== أكثرُ الصورِ تكراراً لكلِّ رواية ===")
    for r in SIX:
        top = " · ".join("«%s»⇜«%s»×%d" % (a, b, c) for (a, b), c in forms[r].most_common(4))
        print("  %-6s %s" % (r, top))
    return 0


def main():
    ap = argparse.ArgumentParser(description="أرضيّةُ الباب الثاني على الرواياتِ الستّ")
    ap.add_argument("--limit", type=int, default=0, help="أوّل ن آية فقط (للتجربة)")
    ap.add_argument("--examples", type=int, default=8)
    ap.add_argument("--anchor", action="store_true", help="فحصُ الإرساء وحدَه (بلا JVM)")
    ap.add_argument("--control", action="store_true", help="ضابطُ الإسناد (الثلاثُ وحدَها)")
    ap.add_argument("--anatomy", action="store_true", help="تشريحُ مخرَجِ شوطٍ سابق (بلا JVM)")
    args = ap.parse_args()
    os.makedirs(WORK, exist_ok=True)
    if args.anchor:
        return anchor_check()
    if args.control:
        return control(args.limit)
    if args.anatomy:
        return anatomy()
    measure(SIX, args.limit, args.examples)
    return anatomy()


if __name__ == "__main__":
    sys.exit(main())
