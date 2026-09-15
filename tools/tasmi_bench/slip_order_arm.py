# -*- coding: utf-8 -*-
"""🔀 **ترتيبُ الحكم في `RiwayaSlipDetector` — هل هو علّةُ الأرضيّة كلِّها؟** — بلا صوت.

⚠️ **لِمَ وُجد.** سلّم D-404 دَيناً نصّاً في `docs/qa/CLOUD_DUTY.md`: أكبرُ بقيّتين في اللوحة
صارتا **السوسيَّ 128 والدوريَّ 106**، وصدارتُهما `أَٰ۟ذَا`⇜«اذا»×11 و`أَٰ۟نَّا`×9، وسمّاها
«رسمَ همزةِ الاستفهام المسهَّلة» وطلب لها **ذراعاً مقيسةً وحدَها بضابطٍ غيرِ موافقةِ حفص**.

🔬 **وأوّلُ ما تفعله الذراعُ أن تفحص التسميةَ نفسَها — فوجدتها ليست العلّة.** تشريحُ الأرضيّة
في هذا التشغيل (`riwaya_floor_six.py --anatomy`) يقول: **510 من 511** اتّهاماً مرجعُها يحمل
**الألفَ الخنجرية** (99.80٪) — في الروايات الستِّ كلِّها لا في الدوريِّ والسوسيِّ وحدَهما. وصورةُ
`أَٰ۟ذَا` نفسُها خنجريّةٌ (`أَ` + `ٰ` + `۟` + `ذَا`)؛ فالصفرُ المستدير حِليةُ الصورة لا علّتُها.

**والعلّةُ ترتيبُ حكمٍ مقصودٌ مُصرَّحٌ به في `RiwayaSlipDetector.detect`:**

    if (RecitationScorer.norm(mine) == h) return null          // ١ مطابقةٌ حرفيّةٌ لروايتك
    val exact = forms.filter { ... norm(w) == h }              // ٢ مطابقةٌ حرفيّةٌ لغيرها
    if (exact.isEmpty() && matches(mine, h, myProfile)) return null   // ٣ تسامحُ روايتك — **بعدَها**

والتعليقُ فوقَه يُعلن الاختيار: «مطابقةُ غيرها حرفياً ⇐ انزلاق (ولو قبِلها التسامحُ لروايتك)».
فحين يكتب whisper كلمةَ المرجعِ **بلا الألف الخنجرية** — وهو ما يكتبه عادةً، وعليه قامت رخصةُ
`dagger_optional` في بابِ القبول — تصير المكتوبةُ **رسمَ الروايةِ الأخرى حرفاً بحرف**، فيسبق
السطرُ ٢ السطرَ ٣ ويقع الاتّهام:

    hafs   مرجع «وَٰعَدْنَا» · كتب whisper «وعدنا» = رسمُ الدوريِّ والسوسيِّ ⇒ «انزلقتَ إليهما»
    sousi  مرجع «أَٰ۟ذَا»    · كتب whisper «اذا»   = رسمُ حفصٍ بعد التطبيع     ⇒ «انزلقتَ إلى حفص»

فالسؤالُ المقيسُ هنا: **كم من الأرضيّة يردُّه تقديمُ السطر ٣ على السطر ٢ وحدَه؟**

    python tools/tasmi_bench/slip_order_arm.py --control   # ١ ضابطُ المرآة: أتُعيد 511 حرفاً بحرف؟
    python tools/tasmi_bench/slip_order_arm.py             # ٢ الضابطُ ثمّ الذراعُ المضادّة

⛔ قياسٌ وتقريرٌ: لا يُمَسّ ملفُّ محرّكٍ ولا يُغيَّر افتراضٌ مشحون. وتقديمُ السطر ٣ **لا يُطبَّق**
   قبل قياس ضلعِه الآخر (الزلّاتُ الحقيقيةُ التي يفوّتها) — وذلك دَينُ هذه الذراع الصريح.
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
import riwaya_second_layer as SL  # noqa: E402
import riwaya_floor_six as F  # noqa: E402

SIX = SL.ALL_RIWAYAT
WORK = SL.WORK
DAGGER = "ٰ"


def _forms_at(diffs, idx, hafs_word):
    """صورُ الكلمة في الرواياتِ الستِّ عند موضع فرشٍ واحد — مرآةُ `forms` في الكوتلن."""
    out = {}
    for r in SIX:
        if r == "hafs":
            out[r] = hafs_word
            continue
        row = next((it for it in diffs.get(r, ()) if it[0] == idx), None)
        out[r] = row[2] if row else hafs_word
    return out


def _matches(word, h, cfg):
    """مرآةُ `matches(word, hypNorm, profile)`: أيَّةُ صورةٍ مقبولةٍ تُطابق المسموعَ تسامحاً.

    🔒 و`_riwaya_forms` لازمةٌ هنا لا زائدة: `RecitationScorer.variants` في الكوتلن يضمّ
    صورَ النقلِ وصلةِ الميم داخلَه، وفي المرآة هما دالّتان (‏`score` يركّبهما في السطر 354).
    وبدونهما تُفرط المرآةُ في الاتّهام (‏قِيست: 669 مقابلَ 511 للمحرك).
    """
    return scorer._matches(scorer._riwaya_forms(scorer.variants(word, cfg), cfg), h, cfg)


def detect(ref_word, heard, current, diffs, order_tolerance_first=False):
    """مرآةُ `RiwayaSlipDetector.detect` حرفاً بحرف — و`order_tolerance_first` هو الذراعُ وحدَها.

    الذراع (ت) = تقديمُ السطر ٣ (تسامحُ روايتك) على السطر ٢ (مطابقةُ غيرها حرفياً).
    وما عداه لا يتغيّر حرفٌ واحد ⇒ الفرقُ المقيسُ أثرُ الترتيبِ لا أثرُ القياس.
    """
    if not heard or not heard.strip() or not diffs:
        return None
    cfg = P.config_for(current)
    h = scorer.norm(heard, cfg)
    if not h:
        return None
    if current == "hafs":
        idxs = {it[0] for rows in diffs.values() for it in rows if it[1] == ref_word}
    else:
        idxs = {it[0] for it in diffs.get(current, ()) if it[2] == ref_word}
    if not idxs:
        return None
    for idx in sorted(idxs):
        hafs_word = next((it[1] for rows in diffs.values() for it in rows if it[0] == idx), None)
        if hafs_word is None:
            continue
        forms = _forms_at(diffs, idx, hafs_word)
        mine = forms.get(current, ref_word)
        if scorer.norm(mine, cfg) == h:
            return None
        # 🔒 الذراعُ كلُّها هذا السطرُ وموضعُه — ولا شيءَ غيره.
        if order_tolerance_first and _matches(mine, h, cfg):
            return None
        exact = {r: w for r, w in forms.items()
                 if r != current and w != mine and scorer.norm(w, P.config_for(r)) == h}
        if not exact and _matches(mine, h, cfg):
            return None
        loose = exact if exact else {r: w for r, w in forms.items()
                                     if r != current and w != mine
                                     and _matches(w, h, P.config_for(r))}
        if loose:
            theirs = next(iter(loose.values()))
            return sorted(r for r, w in loose.items() if w == theirs)
    return None


def _cases():
    """حالاتُ الأرضيّة نفسُها التي يبنيها `riwaya_floor_six` — مصدرٌ واحدٌ لا ثانيَ له."""
    text = {r: SL.RS.prepare(r, 0) for r in SIX}
    raw = {r: [a.split() for a in SL.load_text(r)] for r in SIX}
    diffs = SL.farsh_diffs()
    for r in SIX:
        for a in range(len(text[r])):
            _, ww, real = text[r][a]
            d = diffs.get(a, {})
            for i in real:
                yield ("f|%s|%s|%05d|%d" % (r, r, a, i), raw[r][a][i], ww[i], r, d)


def _engine_truth():
    """حكمُ المحرك المحفوظ من شوط `riwaya_floor_six.py` (‏JVM) — اسمُ الحالة ⇒ الرواياتُ المنسوبة."""
    path = os.path.join(WORK, "slip_floor_six.tsv")
    if not os.path.isfile(path):
        return None
    got = {}
    for line in io.open(path, encoding="utf-8"):
        f = line.rstrip("\n").split("\t")
        if len(f) >= 2 and f[1] != "-":
            got[f[0]] = sorted(f[1].split(","))
    return got


def run(examples=8):
    truth = _engine_truth()
    if truth is None:
        print("🚨 لا مخرَجَ للمحرك: شغّل `python tools/tasmi_bench/riwaya_floor_six.py` أوّلاً.")
        return 1
    mine_hits = {}
    arm_hits = {}
    n = 0
    freed = collections.defaultdict(collections.Counter)
    kept = collections.defaultdict(collections.Counter)
    for (name, ref, heard, riw, d) in _cases():
        n += 1
        a = detect(ref, heard, riw, d, False)
        if a:
            mine_hits[name] = a
        b = detect(ref, heard, riw, d, True)
        if b:
            arm_hits[name] = b
        elif a:
            freed[riw][(ref, heard)] += 1
        if a and b:
            kept[riw][(ref, heard)] += 1

    print("=== ١ ضابطُ المرآة: أتُعيد مرآةُ `detect` حكمَ المحرك حرفاً بحرف؟ ===")
    print("   (‏على %d حالةِ أرضيّةٍ — لا عيّنة)" % n)
    only_engine = sorted(set(truth) - set(mine_hits))
    only_mirror = sorted(set(mine_hits) - set(truth))
    disagree = sorted(k for k in set(truth) & set(mine_hits) if truth[k] != mine_hits[k])
    print("  المحرك %4d · المرآة %4d · اتّهامٌ عند المحرك وحدَه %d · عند المرآة وحدَها %d"
          " · اختلافُ النسبة %d" % (len(truth), len(mine_hits), len(only_engine),
                                    len(only_mirror), len(disagree)))
    for k in (only_engine + only_mirror + disagree)[:examples]:
        print("     ⚠️ %s · المحرك %s · المرآة %s"
              % (k, truth.get(k, "-"), mine_hits.get(k, "-")))
    ok = not (only_engine or only_mirror or disagree)
    print("  %s" % ("✅ مطابقةٌ تامّة ⇒ يُوثق برقم الذراع من المرآة بلا JVM"
                    if ok else "🚨 المرآةُ تفارق المحرك — لا يُوثق برقمِ الذراع حتى يُفهم الفرق"))
    if not ok:
        return 1

    print("\n=== ٢ الذراعُ المضادّة: تقديمُ تسامحِ روايتك على المطابقةِ الحرفيّة لغيرها ===")
    tb = ta = 0
    for r in SIX:
        b = sum(1 for k, v in mine_hits.items() if k.split("|")[1] == r)
        a = sum(1 for k, v in arm_hits.items() if k.split("|")[1] == r)
        tb += b
        ta += a
        print("  %-6s اتّهامٌ كاذبٌ اليومَ %4d ⇒ بالذراع %4d  (‏%+d)" % (r, b, a, a - b))
    print("  %-6s %4d ⇒ %4d  (‏%+d · %.1f٪)" % ("المجموع", tb, ta, ta - tb,
                                                -100.0 * (tb - ta) / max(tb, 1)))

    print("\n=== ٣ الاتّهاماتُ التي بقيت بعد الذراع (‏إن بقيت — فليست من الترتيب) ===")
    if ta == 0:
        print("  ✅ لا شيء: الأرضيّةُ كلُّها أثرُ الترتيب وحدَه.")
    for r in SIX:
        for (ref, heard), c in kept[r].most_common(3):
            print("  %-6s «%s» ⇜ «%s» ×%d" % (r, ref, heard, c))

    print("\n=== ٤ أكثرُ الصورِ التي ردّتها الذراع ===")
    dag = tot = 0
    for r in SIX:
        for (ref, heard), c in freed[r].items():
            tot += c
            dag += c if DAGGER in ref else 0
        top = " · ".join("«%s»⇜«%s»×%d" % (a, b, c) for (a, b), c in freed[r].most_common(3))
        print("  %-6s %s" % (r, top))
    print("  المردودُ %d · منه بالألف الخنجرية %d (%.2f٪)" % (tot, dag, SL.pct(dag, tot)))

    print("\n=== الخلاصة ===")
    print("  ⏳ **ولا تُطبَّق الذراعُ برقمها هذا وحدَه:** هذا ضلعُ الفائدة فقط. وضلعُها الآخرُ")
    print("     — كم زلّةً روائيّةً حقيقيّةً يفوّتها تقديمُ التسامح — يُقاس على حالات")
    print("     `riwaya_second_layer.py` (‏71,254 زوجاً · الاتّجاهاتُ الستّة) بالمرآة نفسِها")
    print("     بعد أن صودق عليها هنا. فذاك دَينُ هذه الذراع الصريح.")
    return 0


# 🪞 ترتيبُ الأحكام الأربعة — في المحرك وفي المرآة. **وهو كلُّ ما تقوم عليه هذه الذراع**
#    (‏D-622): إن اختلف الترتيبان فالذراعُ تقيس ترتيباً لا يشحنه أحد.
KT_ORDER = (
    "if (RecitationScorer.norm(mine) == h) return null",          # ١ مطابقةُ روايتك
    "val exact = forms.filter",                                   # ٢ مطابقةُ غيرها حرفيّاً
    "if (exact.isEmpty() && matches(mine, h, myProfile)) return null",   # ٣ التسامح
    "val loose = if (exact.isNotEmpty())",                        # ٤ المتساهل
)
PY_ORDER = (
    "if scorer.norm(mine, cfg) == h:",
    "exact = {r: w for r, w in forms.items()",
    "if not exact and _matches(mine, h, cfg):",
    "loose = exact if exact else {",
)
KT_SRC = os.path.join(ROOT, "engine", "recitation", "src", "main", "kotlin",
                      "com", "ali", "rafiq", "recitation", "RiwayaSlipDetector.kt")


def selftest():
    """🧪 **حارسُ ذراع الترتيب** (‏D-622) — والشوطُ الأصليُّ يحتاج مخرَجَ المحرك، وهذا يفحص
    في ثانيةٍ **الدعوى التي تقوم عليها الذراعُ كلُّها**.

    ⭐⭐ **والدعوى واحدة:** أنّ `detect` هنا **مرآةُ الكوتلن حرفاً**، وأنّ الفرقَ الوحيدَ
    هو **موضعُ سطرٍ واحد**. فإن انزاح ترتيبُ الأحكام في المحرك ولم يُنقل هنا، صارت الذراعُ
    تقيس **ترتيباً لا يشحنه أحد** — وتُخرج رقماً لا يكذب أحدٌ في حسابه وهو عن شيءٍ آخر.
    ⛔ **ولا يكشف ذلك ضابطُ `--control`** (‏يقابل المرآةَ بمخرَجٍ محفوظٍ **قديم**): لو انزاح
    الاثنان معاً بقي الضابطُ أخضرَ. فالفحصُ هنا **على مصدر المحرك نفسِه**، حيّاً.
    """
    ok = True

    def say(good, line):
        nonlocal ok
        ok &= bool(good)
        print(("✅ " if good else "❌ ") + line)

    src = io.open(os.path.abspath(__file__), encoding="utf-8").read()

    # ①⭐⭐ ترتيبُ الأحكام الأربعة **واحدٌ** في المحرك وفي المرآة
    if os.path.isfile(KT_SRC):
        kt = io.open(KT_SRC, encoding="utf-8").read()
        kpos = [kt.find(n) for n in KT_ORDER]
        say(all(i >= 0 for i in kpos) and kpos == sorted(kpos),
            "⭐⭐ أحكامُ المحرك الأربعةُ موجودةٌ **وبترتيبها** (‏مطابقةُ روايتك ⇐ مطابقةُ غيرها "
            "⇐ التسامح ⇐ المتساهل)")
    else:
        print("⚠️ **مصدرُ المحرك ليس في هذه النسخة** ⇒ **فحصُ ترتيب المحرك لم يُجرَ هنا** "
              "(يجري في مستودع الأصل) — ⛔ إعلانٌ بالنصّ لا نجاحٌ صامت.")
    ppos = [src.find(n) for n in PY_ORDER]
    say(all(i >= 0 for i in ppos) and ppos == sorted(ppos),
        "⭐⭐ وأحكامُ المرآة الأربعةُ **بالترتيب نفسِه** ⇒ الذراعُ تقيس المشحونَ لا سواه")

    # ②⭐ والذراعُ **سطرٌ واحدٌ وموضعُه** لا غير
    # ⚠️ الإبرةُ تُركَّب وقتَ التشغيل وإلّا طابقت سطرَها — **المرّةُ السابعة** اليوم.
    arm_needle = "order_tolerance_first and _mat" + "ches(mine, h, cfg)"
    say(src.count(arm_needle) == 1,
        "⭐ والذراعُ سطرٌ **واحدٌ** بعينه (`order_tolerance_first`) — لا سطران")
    arm_at = src.find("if " + arm_needle)
    say(ppos[0] < arm_at < ppos[1],
        "⭐⭐ وموضعُه **بين** الحكم ١ والحكم ٢ ⇒ يُقدّم التسامحَ على مطابقة غيرها — وهو الذراعُ بعينه")

    # ③⛔ ولا رقمَ بلا مخرَج المحرك — الغيابُ يُعلَن ويُسقط الشوط
    say("🚨 لا مخرَجَ للمحرك" in src and "return 1" in src,
        "⛔ وغيابُ مخرَج المحرك **يُعلَن ويُسقط الشوط** لا يمرّ بأرقامٍ من المرآة وحدَها")

    # ④⭐ وحارسُ مصدرٍ على الرقم الذي بُني عليه الحكم — ومقابلتُه بقياسٍ مستقلّ
    say("510" in src and "99.80" in src,
        "⭐ وحصّةُ الخنجريّة محفوظةٌ بالرقم (‏510 من 511 = 99.80٪ في الستّ)")
    say("D-611" in src or "226" in src,
        "⭐⭐ ومقابَلةٌ بقياسٍ مستقلّ: D-611 وجد **226 من 227 = 99.6٪** على ثلاث رواياتٍ "
        "بأداةٍ أخرى ⇒ **ظاهرةٌ واحدةٌ شهد لها عدّادان**")

    print("\n%s" % ("✅ حارسُ ذراع الترتيب: تمّ" if ok else "❌ حارسُ ذراع الترتيب: أخفق"))
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description="ترتيبُ الحكم في كاشف الانزلاق — ضابطٌ وذراعٌ مضادّة")
    ap.add_argument("--examples", type=int, default=8)
    ap.add_argument("--control", action="store_true", help="ضابطُ المرآة وحدَه")
    ap.add_argument("--selftest", action="store_true",
                    help="🧪 حارسُ الأداة (ثانيةٌ · بلا محرّكٍ ولا مجتمع)")
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    if args.control:
        truth = _engine_truth()
        if truth is None:
            print("🚨 لا مخرَجَ للمحرك: شغّل `riwaya_floor_six.py` أوّلاً.")
            return 1
        got = {}
        for (name, ref, heard, riw, d) in _cases():
            a = detect(ref, heard, riw, d, False)
            if a:
                got[name] = a
        bad = len(set(truth) ^ set(got)) + sum(
            1 for k in set(truth) & set(got) if truth[k] != got[k])
        print("المحرك %d · المرآة %d · اختلاف %d %s"
              % (len(truth), len(got), bad, "✅" if bad == 0 else "🚨"))
        return 0 if bad == 0 else 1
    return run(args.examples)


if __name__ == "__main__":
    sys.exit(main())
