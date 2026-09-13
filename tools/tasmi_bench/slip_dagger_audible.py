# -*- coding: utf-8 -*-
"""🗣️ **ثمنُ لافتةِ الخنجرية على الصوت لا على الرسم** — تشريحُ الـ96 كشفاً التي تفوّتها (خ). بلا صوت.

⚠️ **لِمَ وُجد.** سلّم D-406 دَيناً واحداً بين رقمِه وأيِّ شحن: «من الـ96، كم موضعاً يُنطق فيه
الفرقُ الخنجريُّ نطقاً مسموعاً (‏مدُّ الألف) فيكتبه نموذجٌ أفضلُ ولو لم يكتب الخنجريّة؟».
وهذا الملفُّ يجيب الشقَّ الذي **يُقاس بلا صوت**: أهو فرقٌ في المنطوق أصلاً، أم حِليةُ رسمٍ
لا تُسمع؟ فإن كان في الرسم صامتاً فلا نموذجَ يستردّه أبداً، ويسقط الدَّينُ نفسُه.

**الطريقةُ (‏على المحرك · لا مرآة):** تُعاد حالاتُ D-406 حرفاً بحرف عبر `slip_dagger_gate_arm`
نفسِه — الطبقةُ الأولى ⇒ العمياء ⇒ الأذرعُ الثلاثُ على JVM — ثمّ يُلتقط **كلُّ** ما يردّه
المشحونُ وتفوّته (خ) (‏لا عشرون مثالاً كما في الذراع)، وتُشرَّح كلُّ حالةٍ على رسمها:

    صورتي (‏خام) · صورتُهم (‏خام) · أيُّهما يحمل U+0670 · أعليها علامةُ سكوت؟

**والسؤالُ الحاسمُ ليس «أمسموعٌ الفرق؟» بل «أيكتبه الإملاءُ الحديثُ أصلاً؟»** — فنموذجُ
التفريغ لا يكتب رسمَ المصحف، يكتب إملاءً حديثاً بلا تشكيل. فالفرقُ المسموعُ الذي لا صورةَ
له في الإملاء الحديث **لا يستردُّه نموذجٌ مهما جَوُد**. ومن هنا أربعةُ أصناف:

    ١ · ألفُ مدٍّ مفردة   «ارايتم» ⇜ «اريتم»   ⇒ صورةٌ يكتبها الناسُ ⇒ **يستردُّها نموذجٌ أفضل**
    ٢ · ألفٌ مضاعفةٌ أو خنجريّةٌ صامتة «اانتم» ⇜ «انتم» ⇒ لا يكتب «اا» أحدٌ (‏عائلةُ D-275)
    ٣ · فرقُ همزةٍ لا مدّ  «هَٰا۬نتُمْ» ⇜ «هَٰٓأَنتُمْ» ⇒ تسهيلٌ/نقلٌ يمحوه الإملاءُ ⇒ لا تُستردّ
    ٤ · رسمان متطابقان   «اِ۬لرِّيَٰحُ» ⇜ «اِ۬لرِّيَٰحُ»   ⇒ **لا زلّةَ هناك أصلاً** ⇒ ليست كشفاً يُفقد

🔇 وعلامتا السكوت (‏تُجرَّد بهما الخنجريّةُ من النطق): U+06DF الصفرُ المستديرُ · U+06E0 المستطيلُ.

⛔ ولا يُغيَّر افتراضٌ مشحون ولا يُمَسّ ملفُّ محرّك: قياسٌ وتقريرٌ لا قرار.
⚠️ يلزم مخرَجُ الطبقة الأولى `work/engine_riwaya_surface.tsv` (‏`riwaya_surface.py --arms b`).

    python tools/tasmi_bench/slip_dagger_audible.py --control   # 🧪 الضوابطُ أوّلاً
    python tools/tasmi_bench/slip_dagger_audible.py             # المصحف كلُّه
"""
import argparse
import collections
import itertools
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "tools", "alignment"))
import riwaya_second_layer as S      # noqa: E402  (‏مصدرٌ واحدٌ لبناء الحالات)
import riwaya_surface as RS          # noqa: E402
import slip_dagger_gate_arm as G     # noqa: E402  (‏مصدرٌ واحدٌ لتشغيل الأذرع الثلاث)
import scorer                        # noqa: E402
import parity_full as P              # noqa: E402  (‏config_for — مصدرٌ واحدٌ لإعداد الرواية)
from common import load_text         # noqa: E402

DAGGER = "ٰ"        # الألفُ الخنجرية
MUTE = {"۟", "۠"}          # الصفرُ المستديرُ · الصفرُ المستطيلُ القائم

# 🔒 أرقامُ D-406 على المصحف كلِّه — بها تُضبط حيويّةُ هذا التشريح قبل أيِّ تصنيف.
D406 = dict(blind=49140, shipped=351, tol=2, dag=255)


def raw_pairs(limit=0):
    """‏اسمُ الحالة ⇒ (صورتي الخام، صورتُهم الخام) — بناءٌ مطابقٌ لـ`S.build_slips` موضعاً بموضع."""
    text = {r: RS.prepare(r, limit) for r in S.RIWAYAT}
    raw = {r: [a.split() for a in load_text(r)[:limit or None]] for r in S.RIWAYAT}
    out = {}
    for e, s in itertools.permutations(S.RIWAYAT, 2):
        for a in range(len(text[e])):
            _, ww, real_e = text[e][a]
            _, ws, real_s = text[s][a]
            if len(real_e) != len(real_s) or not real_e:
                continue
            for ie, isx in zip(real_e, real_s):
                if ws[isx] == ww[ie]:
                    continue
                out["b|%s|%s|%05d|%d" % (e, s, a, ie)] = (raw[e][a][ie], raw[s][a][isx])
    return out


def dagger_sites(word):
    """مواضعُ U+0670 في الصورة الخام ⇒ [(الفهرس، أعليها علامةُ سكوت؟)]."""
    sites = []
    for i, c in enumerate(word):
        if c != DAGGER:
            continue
        near = set(word[max(0, i - 2):i]) | set(word[i + 1:i + 3])
        sites.append((i, bool(near & MUTE)))
    return sites


KINDS = ("١ · ألفُ مدٍّ مفردة ⇒ يستردُّها نموذجٌ أفضل",
         "٢ · ألفٌ مضاعفة أو خنجريّةٌ صامتة ⇒ لا يكتبها أحد",
         "٣ · فرقُ همزةٍ لا مدّ (تسهيل/نقل)",
         "٤ · رسمان متطابقان ⇒ لا زلّةَ أصلاً")


def classify(mine, theirs, riwaya):
    """تصنيفُ الفرق بين الرسمين إلى أحد `KINDS`. المخرَج: (الصنف، صورتي المطبَّعة، صورتُهم)."""
    cfg = P.config_for(riwaya)
    nm, nt = scorer.norm(mine, cfg), scorer.norm(theirs, cfg)
    if mine == theirs:
        return (KINDS[3], nm, nt)
    if mine.count(DAGGER) == theirs.count(DAGGER):
        return (KINDS[2], nm, nt)               # الخنجريّةُ ذاتُها في الصورتين ⇒ الفرقُ همزةٌ
    live = [s for s in dagger_sites(mine) + dagger_sites(theirs) if not s[1]]
    if not live:
        return (KINDS[1], nm, nt)               # خنجريّةٌ عليها علامةُ سكوت ⇒ لا مدَّ يُسمع
    if "اا" in nm or "اا" in nt:
        return (KINDS[1], nm, nt)
    return (KINDS[0], nm, nt)


def measure(limit=0, examples=12):
    eng = S.layer1()
    if eng is None:
        return 1
    slips = S.build_slips(limit)
    pairs = raw_pairs(limit)
    print("حالاتُ الزلّة: %d (‏منها %d لها صورتان خامّتان)" % (len(slips), len(pairs)))
    det = G.run_arms(slips, os.path.join(S.WORK, "audible_slip.tsv"))

    blind = shipped = tol = dag = 0
    lost = []
    for name, ref, heard, _riw, _enc in slips:
        got = eng.get(name)
        if got is None:
            continue
        verdicts, adds = got
        _arm, _e, _s, _a, i = name.split("|")
        i = int(i)
        v = verdicts[i] if i < len(verdicts) else "?"
        if (v != "C") or bool(adds):
            continue                             # كشفتها الطبقةُ الأولى ⇒ ليست عمياء
        sh, tl, dg = det.get(name, ("-", "-", "-"))
        blind += 1
        shipped += 1 if sh != "-" else 0
        tol += 1 if tl != "-" else 0
        dag += 1 if dg != "-" else 0
        if sh != "-" and dg == "-":
            mine, theirs = pairs.get(name, (ref, heard))
            lost.append((name, mine, theirs, heard, _riw))

    print("\n🧪 الضابطُ الأوّل · حيويّةٌ ومطابقةُ D-406 (‏على المصحف كلِّه):")
    ok = True
    for key, got in (("blind", blind), ("shipped", shipped), ("tol", tol), ("dag", dag)):
        want = D406[key]
        good = (limit != 0) or (got == want)
        ok = ok and good
        print("  %-8s المقيسُ الآن %6d · D-406 %6d %s" % (key, got, want, "✅" if good else "🚨"))
    print("  المفقودُ بذراع (خ): %d (‏D-406: %d) %s"
          % (len(lost), D406["shipped"] - D406["dag"],
             "✅" if limit or len(lost) == D406["shipped"] - D406["dag"] else "🚨"))
    if not ok and not limit:
        print("  🚨 لم تُطابَق أرقامُ D-406 ⇒ لا يُوثق بتصنيفٍ مبنيٍّ عليها.")

    # ═══ 🧪 الضابطُ الثاني: أفرقُ الصورتين بعد التطبيع ألفاتٌ وحدَها؟ ═══
    dagger_pairs = [x for x in lost if x[1] != x[2] and x[1].count(DAGGER) != x[2].count(DAGGER)]
    alif_only = 0
    for _n, mine, theirs, _h, riw in dagger_pairs:
        cfg = P.config_for(riw)
        if scorer.norm(mine, cfg).replace("ا", "") == scorer.norm(theirs, cfg).replace("ا", ""):
            alif_only += 1
    print("\n🧪 الضابطُ الثاني · ما اختلفت فيه الخنجريّاتُ: الفرقُ بعد التطبيع ألفاتٌ وحدَها ⇒ %d من %d %s"
          % (alif_only, len(dagger_pairs), "✅" if alif_only == len(dagger_pairs) else "🚨"))

    # ═══ التشريح ═══
    kinds = collections.Counter()
    shapes = collections.defaultdict(collections.Counter)
    for _name, mine, theirs, heard, riw in lost:
        kind, nm, nt = classify(mine, theirs, riw)
        kinds[kind] += 1
        shapes[kind][(mine, theirs, nm, nt, heard)] += 1

    print("\n=== 🗣️ تشريحُ الكشفِ المفقود (‏%d حالة) — أيكتب الإملاءُ الحديثُ فرقَها؟ ===" % len(lost))
    for kind in KINDS:
        print("  %-42s %4d (%.1f٪)" % (kind, kinds[kind], G.pct(kinds[kind], len(lost))))
    # 🔒 الصنفان ٣ و٤ يتطابقان بعد التطبيع ⇒ لا يفرّق بينهما تفريغٌ بإملاءٍ حديثٍ البتّة.
    same = 0
    for _n, mine, theirs, _h, riw in lost:
        cfg = P.config_for(riw)
        if scorer.norm(mine, cfg) == scorer.norm(theirs, cfg):
            same += 1
    mute_kinds = kinds[KINDS[2]] + kinds[KINDS[3]]
    print("\n🧪 الضابطُ الثالث · الصنفان ٣ و٤ متطابقان بعد التطبيع ⇒ %d من %d %s"
          % (same, mute_kinds, "✅" if same == mute_kinds else "🚨"))
    back, never = kinds[KINDS[0]], kinds[KINDS[1]]
    print("\n  ⇒ **ثمنُ (خ) الحقيقيُّ %d لا %d**: %d منها صورتاها سواءٌ بعد التطبيع ⇒ لا يكشفها"
          " تفريغٌ أصلاً، فليست كشفاً يُفقد بل ضجيجُ عدّادٍ في بناء الحالات."
          % (len(lost) - same, len(lost), same))
    print("  ⇒ ومن الـ%d: **%d (%.1f٪) يستردُّها نموذجٌ يكتب المدَّ ألفاً مفردة** (‏«ارايتم» ⇜ «اريتم»)"
          % (len(lost) - same, back, G.pct(back, len(lost) - same)))
    print("     و**%d لا يستردُّها أحدٌ** لأنّ صورتَها «اا» ولا يكتبها الإملاءُ الحديث ⇒ **الثمنُ الدائمُ %d**."
          % (never, never))

    for kind in KINDS:
        if not shapes[kind]:
            continue
        print("\n=== %s · صورٌ متمايزة %d ===" % (kind, len(shapes[kind])))
        for (mine, theirs, nm, nt, heard), c in shapes[kind].most_common(examples):
            print("  ×%-3d «%s» ⇜ «%s» · مطبَّعاً «%s» ⇜ «%s» · سُمع «%s»"
                  % (c, mine, theirs, nm, nt, heard))
    return 0 if ((ok or limit) and alif_only == len(dagger_pairs) and same == mute_kinds) else 1


def control(limit=600):
    """🧪 الضوابطُ: تصنيفٌ حيٌّ على أمثلةٍ معلومة، وسالبٌ لا يُصنَّف مسموعاً بلا خنجرية."""
    cases = [
        ("مَٰلِكِ", "مَلِكِ", "hafs", KINDS[0]),           # فرشٌ مشهور: ألفُ مدٍّ مفردة
        ("مَلِكِ", "مَٰلِكِ", "hafs", KINDS[0]),           # الاتّجاهُ المعاكس
        ("ءَٰا۬نتُمْ", "ءَأَنتُمْ", "qalun", KINDS[1]),      # «اانتم» لا يكتبها أحد
        ("ءَاٰ۟ذَا", "ءَاذَا", "hafs", KINDS[1]),   # خنجريّةٌ عليها الصفرُ المستدير ⇒ لا مدّ
        ("هَٰا۬نتُمْ", "هَٰٓأَنتُمْ", "qalun", KINDS[2]),    # الخنجريّةُ ذاتُها ⇒ الفرقُ همزة
        ("كِتَٰبٌ", "كِتَٰبٌ", "hafs", KINDS[3]),          # رسمان متطابقان
    ]
    print("\n🧪 ضابطُ التصنيف (‏صورٌ معلومةٌ سلفاً):")
    ok = True
    for mine, theirs, riw, want in cases:
        kind, nm, nt = classify(mine, theirs, riw)
        good = kind == want
        ok = ok and good
        print("  «%s» ⇜ «%s» ⇒ %s — المتوقَّع %s %s" % (mine, theirs, kind, want, "✅" if good else "🚨"))
    # سالبٌ على عيّنةٍ حقيقية: زوجٌ لا خنجريّةَ فيه البتّةَ لا يُصنَّف صنفَ المدّ.
    pairs = raw_pairs(limit)
    bad = 0
    for name, (mine, theirs) in pairs.items():
        if DAGGER not in mine and DAGGER not in theirs:
            if classify(mine, theirs, name.split("|")[1])[0] == KINDS[0]:
                bad += 1
    print("  سالبٌ · أزواجٌ بلا خنجريّةٍ صُنّفت «ألفَ مدّ» ⇒ %d (يجب 0) %s"
          % (bad, "✅" if bad == 0 else "🚨"))
    ok = ok and bad == 0
    print("  %s" % ("✅ المصنِّفُ حيٌّ ولا يفتح بلا سند" if ok else "🚨 ضابطٌ سقط — لا يُوثق برقم"))
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description="تشريحُ الكشفِ الذي تفوّته لافتةُ الخنجرية")
    ap.add_argument("--limit", type=int, default=0, help="أوّل ن آية فقط (للتجربة)")
    ap.add_argument("--examples", type=int, default=12)
    ap.add_argument("--control", action="store_true", help="الضوابطُ وحدَها")
    args = ap.parse_args()
    os.makedirs(S.WORK, exist_ok=True)
    if args.control:
        return control(args.limit or 600)
    return measure(args.limit, args.examples)


if __name__ == "__main__":
    sys.exit(main())
