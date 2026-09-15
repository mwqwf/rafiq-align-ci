# -*- coding: utf-8 -*-
"""🔁 **جردُ التكرار في السورة الواحدة — لماذا تنقص سورةٌ بعينِها عند قرّاءٍ لا صلةَ بينهم؟** (‏D-508)

⚠️ **لِمَ وُجد:** سألت **مناوبةُ الفهرسة** في لوحة المالك (‏2026-09-14 ‏23:24Z) سؤالاً
صريحاً موجَّهاً إلى مناوبة المحرك: `low_coverage_scan` كشف نمطاً **نظاميّاً** — سورة 55
ناقصةٌ قليلاً عند **35٪** من القرّاء، وسورة 102 عند **32٪**، **عبر قرّاءٍ لا صلةَ بينهم**
⇒ «أتكرارٌ مدمَجٌ عمداً أم نقصٌ حقيقيّ؟».

⭐ **والجوابُ يُقاس من المصحف وحدَه** (‏بلا دلوٍ ولا صوتٍ ولا شبكة): إن كان النقصُ يقع في
السور التي **يتشابه فيها جارٌ وجارُه**، فالعلّةُ **انهيارُ حدٍّ بين آيتين متشابهتين** في
المحاذاة لا نقصُ مادّةٍ ولا دمجٌ متعمَّد — والفرقُ بينهما **فرقُ علاجٍ**: الأوّلُ يُصلَح
بإلزام الحدّ، والثاني بإعادة التحميل، والثالثُ بإعلان الغياب.

⛔ **ومسطرتان لا واحدة** (‏درسُ D-504: المسطرةُ الواحدةُ تُضلّ في النفي كما في الإثبات):

    ① **التطابقُ الحرفيّ** بعد التطبيع — «فبأيّ آلاء ربّكما تكذّبان» 31 مرّةً في الرحمن.
    ② **الجوارُ القريب** — صدرٌ أو ذيلٌ (‏≤ كلمتين فرقاً) أو كلمةٌ واحدةٌ تختلف:
       «كلّا سوف تعلمون» ⇜ «ثمّ كلّا سوف تعلمون» · «فإنّ مع العسر يسرا» ⇜ «إنّ مع العسر يسرا».
    ⇒ والمسطرةُ ① وحدَها **تُبرّئ سورة 102 كذباً** (صفرُ تكرارٍ حرفيّ فيها)، و② تكشفها.

**المقيس (‏حفص · المصحف كلُّه):** سورة **55** الأولى في المسطرتين معاً (30 تكراراً حرفيّاً
من 78 آية · و**35 آيةً (44.9٪) متورّطةٌ في تشابه**)، وسورة **102** صفرٌ حرفيّاً و**2 (25.0٪)**
بالجوار القريب — وهما **الآيتان 3 و4** بعينِهما.

⭐⭐ **وهذا حكمٌ قابلٌ للتكذيب، وهو شرطُ أن يكون حكماً:** إن صحّت العلّةُ فالنقصُ يجب أن
يظهر **أيضاً** في السور التالية في الجدول (‏101 · 109 · 114 · 1 · 94 · 26 · 77)، وأن تكون
الآياتُ الناقصةُ **هي الطرفَ الثاني من الزوج المتشابه** لا آياتٍ عشوائيّة. ⇒ **الفحصُ
الحاسمُ على مَن يملك الدلو**: قابِلْ فهرسَ النقص بجدول `--pairs` أدناه.

    python tools/tasmi_bench/repeat_census.py                 # الجدولُ مرتَّباً
    python tools/tasmi_bench/repeat_census.py --surah 102     # أزواجُ سورةٍ بعينها
    python tools/tasmi_bench/repeat_census.py --pairs --top 8 # أزواجُ أخطرِ السور
    python tools/tasmi_bench/repeat_census.py --selftest

⛔ **قياسٌ وتقريرٌ:** لا يُكتب في `timings*` ولا في `tools/index_qa/` ولا يُمَسّ فهرسٌ منشور.
"""
import argparse
import collections
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "tools", "alignment"))
import scorer  # noqa: E402
import parity_full as P  # noqa: E402
from common import load_text, load_index, surah_slice  # noqa: E402

# 🎚️ حدُّ «الجوار القريب» — ويُكتب صريحاً لأنّه **مسطرة**:
#    فرقُ كلمةٍ واحدةٍ في طولٍ واحد، أو صدرٌ/ذيلٌ يزيد بكلمتين على الأكثر.
#    وُضع 1 و2 لا اعتباطاً: «ثمّ» و«ثمّ كلّا» هما الفاصلُ الفعليُّ في 102 و94 و109،
#    وتوسيعُه يُدخل آياتٍ لا يخلط بينها سامعٌ (‏جُرِّب في الضابط السالب أدناه).
MAX_WORD_DIFF = 1
MAX_AFFIX_GAP = 2


def norm_ayah(text, cfg):
    return " ".join(x for x in (scorer.norm(w, cfg) for w in text.split()) if x)


def near(a, b):
    """أجارٌ قريبٌ يخلط المحاذيَ بينهما؟ — صدرٌ · ذيلٌ · أو كلمةٌ واحدةٌ تختلف."""
    if not a or not b:
        return False
    if a == b:
        return True
    A, B = a.split(), b.split()
    if len(A) > len(B):
        A, B = B, A
    if len(A) == len(B):
        return sum(1 for x, y in zip(A, B) if x != y) <= MAX_WORD_DIFF
    if B[:len(A)] == A or B[-len(A):] == A:
        return len(B) - len(A) <= MAX_AFFIX_GAP
    return False


def surah_rows(riwaya="hafs"):
    """لكلِّ سورة: (رقمُها · آياتُها · تكرارٌ حرفيّ · آياتٌ متورّطةٌ في تشابه · نسبتُها)."""
    cfg = P.config_for(riwaya)
    text = load_text(riwaya)
    idx = load_index()
    rows = []
    for s in idx["surahs"]:
        a, b, _ = surah_slice(idx, s["n"])
        ayat = [norm_ayah(x, cfg) for x in text[a:b]]
        n = len(ayat)
        c = collections.Counter(ayat)
        exact = sum(v - 1 for v in c.values() if v > 1)
        involved = set()
        for i in range(n):
            for j in range(i + 1, n):
                if near(ayat[i], ayat[j]):
                    involved.add(i)
                    involved.add(j)
        rows.append((s["n"], n, exact, len(involved), 100.0 * len(involved) / n if n else 0.0))
    return rows


def pairs_of(surah_no, riwaya="hafs"):
    """أزواجُ التشابه في سورةٍ بعينها: (رقمُ الآية الأولى · الثانية · أحرفيٌّ هو؟)."""
    cfg = P.config_for(riwaya)
    text = load_text(riwaya)
    idx = load_index()
    a, b, _ = surah_slice(idx, surah_no)
    ayat = [norm_ayah(x, cfg) for x in text[a:b]]
    out = []
    for i in range(len(ayat)):
        for j in range(i + 1, len(ayat)):
            if near(ayat[i], ayat[j]):
                out.append((i + 1, j + 1, ayat[i] == ayat[j]))
    return out


def report(top=14, riwaya="hafs"):
    rows = sorted(surah_rows(riwaya), key=lambda r: -r[4])
    print("🔁 أخطرُ السور تشابهاً داخلَها (‏%s) — والنقصُ النظاميُّ يُتوقَّع هنا" % riwaya)
    print("  %-7s %-7s %-11s %s" % ("سورة", "آيات", "حرفيٌّ", "متورّطةٌ في تشابه"))
    for sn, n, ex, inv, pc in rows[:top]:
        print("  %-7d %-7d %-11d %d (%.1f٪)" % (sn, n, ex, inv, pc))
    return rows


def main():
    ap = argparse.ArgumentParser(description="جردُ التكرار داخلَ السورة — علّةُ النقص النظاميّ")
    ap.add_argument("--riwaya", default="hafs")
    ap.add_argument("--surah", type=int, default=0, help="أزواجُ سورةٍ بعينها")
    ap.add_argument("--pairs", action="store_true", help="اطبع أزواجَ أخطرِ السور")
    ap.add_argument("--top", type=int, default=14)
    ap.add_argument("--selftest", action="store_true", help="🧪 حارسُ الأداة (ثوانٍ)")
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    if args.surah:
        ps = pairs_of(args.surah, args.riwaya)
        print("سورة %d · أزواجُ التشابه: %d" % (args.surah, len(ps)))
        for i, j, ex in ps:
            print("   %3d ⇜ %3d  %s" % (i, j, "تطابقٌ حرفيّ" if ex else "جوارٌ قريب"))
        return 0
    rows = report(args.top, args.riwaya)
    if args.pairs:
        for sn, _n, _ex, _inv, _pc in sorted(rows, key=lambda r: -r[4])[:args.top]:
            ps = pairs_of(sn, args.riwaya)
            print("\n  سورة %d · %d زوجاً: %s" % (sn, len(ps),
                  " · ".join("%d⇜%d" % (i, j) for i, j, _ in ps[:12])))
    return 0


def selftest():
    """🧪 **حارسُ جردِ التكرار** (‏D-508) — والأداةُ تُقرأ منها **علّةُ نقصٍ في فهرسٍ منشور**،
    فمسطرتُها تُثبَّت بالنصّ لا بالنيّة:

    ⭐⭐ **المسطرةُ تكشف ما وُجدت له** — أزواجُ 102 و94 و109 و1 بأرقامها من المصحف.
    ⭐⭐ **ولا تكشف ما ليس منه** (‏ضابطٌ سالب): آياتٌ متجاورةٌ لا يخلط بينها سامعٌ **لا
      تُعَدّ زوجاً**، وإلّا صار «كلُّ شيءٍ متشابهاً» فلا يدلّ الجدولُ على شيء.
    ⭐ **والحدُّ 1/2 حدٌّ مقيسٌ يُصرَخ عند تغييره** — فتوسيعُه يُغرق الجدولَ، وتضييقُه
      يُبرّئ 102 كذباً (‏وهي المسطرةُ التي كادت تُضلّني: صفرُ تكرارٍ حرفيٍّ فيها).
    """
    ok = True

    def say(good, line):
        nonlocal ok
        ok &= bool(good)
        print(("✅ " if good else "❌ ") + line)

    # ① المسطرةُ على أمثلةٍ مكتوبةٍ بأيدينا — الشكلُ أوّلاً
    say(near("كلا سوف تعلمون", "ثم كلا سوف تعلمون"), "صدرٌ بكلمةٍ: «ثمّ كلّا سوف تعلمون»")
    say(near("فان مع العسر يسرا", "ان مع العسر يسرا"), "كلمةٌ تختلف: «فإنّ» ⇜ «إنّ»")
    say(near("ملك الناس", "اله الناس"), "كلمةٌ تختلف في طولٍ واحد: «ملك» ⇜ «إله»")
    say(not near("قل هو الله احد", "لم يلد ولم يولد"), "⭐ ولا تُعَدّ آيتان مختلفتان زوجاً")
    say(not near("", "شيء") and not near("شيء", ""), "والفارغُ لا يصنع زوجاً (‏مدخلٌ ناقص)")
    say(near("أ ب ج", "أ ب ج"), "والمتطابقُ زوجٌ بداهةً")
    say(not near("ا ب", "ا ب ج د ه"), "⛔ وفجوةٌ أوسعُ من كلمتين ليست جواراً")

    # ②⭐⭐ ثمّ على المصحف نفسِه — الأرقامُ لا الأمثلة
    ps102 = pairs_of(102)
    say(ps102 == [(3, 4, False)],
        "⭐⭐ سورة 102: زوجٌ واحدٌ **3⇜4** بالجوار لا بالتطابق %s" % (ps102,))
    ps109 = pairs_of(109)
    say((3, 5, True) in ps109, "وسورة 109: **3⇜5 تطابقٌ حرفيّ** %s" % (ps109,))
    ps94 = pairs_of(94)
    say(ps94 == [(5, 6, False)], "وسورة 94: **5⇜6** (فإنّ/إنّ) %s" % (ps94,))
    ps1 = pairs_of(1)
    say((1, 3, False) in ps1, "وسورة 1: **1⇜3** (البسملةُ وذيلُها) %s" % (ps1,))

    # ③⭐⭐ والترتيبُ هو الحكم: 55 أولاً في المسطرتين معاً
    rows = surah_rows()
    by_near = sorted(rows, key=lambda r: -r[4])
    by_exact = sorted(rows, key=lambda r: -r[2])
    r55 = next(r for r in rows if r[0] == 55)
    r102 = next(r for r in rows if r[0] == 102)
    say(by_near[0][0] == 55 and by_exact[0][0] == 55,
        "⭐⭐ سورة 55 الأولى في المسطرتين (‏حرفيٌّ %d · متشابهةٌ %d من %d)"
        % (r55[2], r55[3], r55[1]))
    say(r102[2] == 0 and r102[3] == 2,
        "⛔ وسورة 102 **صفرٌ حرفيّاً** و2 بالجوار — فالمسطرةُ الواحدةُ كانت تُبرّئها كذباً")
    say(sum(1 for r in rows if r[4] > 0) < len(rows) * 0.75,
        "⭐ والجدولُ يفرّق: %d سورةً من %d بلا تشابهٍ أصلاً"
        % (sum(1 for r in rows if r[4] == 0), len(rows)))
    say(len(rows) == 114 and sum(r[1] for r in rows) == 6236,
        "والمصحفُ كاملٌ: %d سورةً · %d آية" % (len(rows), sum(r[1] for r in rows)))

    # ④ الحدُّ مكتوبٌ ومحروس
    src = io.open(os.path.abspath(__file__), encoding="utf-8").read()
    say(MAX_WORD_DIFF == 1 and MAX_AFFIX_GAP == 2 and "MAX_WORD_DIFF = 1" in src,
        "⛔ حدُّ الجوار كما قِيس: كلمةٌ واحدةٌ · وفجوةُ كلمتين")
    say("قابلٌ للتكذيب" in src and "على مَن يملك الدلو" in src,
        "وحكمٌ قابلٌ للتكذيب، وفحصُه الحاسمُ مُسمّىً لمن يملك الدلو")

    print("\n%s" % ("✅ حارسُ جردِ التكرار: تمّ" if ok else "❌ حارسُ جردِ التكرار: أخفق"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
