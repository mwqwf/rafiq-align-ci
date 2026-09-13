# -*- coding: utf-8 -*-
"""📐 **علامةُ الإمالة الثانية `۪` في المِسطرة** (`۪يٰ`) — صورةٌ رابعةٌ لعطب D-274؟ بلا صوت.

⚠️ **لِمَ وُجد.** سلّم D-402 دَيناً نصّاً في `docs/qa/CLOUD_DUTY.md`:

    «علامةُ إمالةٍ ثانيةٌ `۪` (U+06EA) بالصورة نفسِها ظهرت في مخرَج الشوط ولم تُعالَج:
     `اِ۪فۡتَر۪يٰ` ⇜ «افتريا» والصوابُ «افتري». إحصاؤها: الدوري 159 · السوسي 159 · **ورش 310**.
     ⚠️ ومسُّها يمسُّ **ورشاً** ورقمُه (239) ضابطٌ مسنودٌ ⇒ لا تُطبَّق بلا ذراعٍ مقيسةٍ وحدَها.»

وهذا الملفُّ **هو تلك الذراع**: يقيس الصورةَ وضابطَها وتكلفتَها. وفائدتُها (الاتّهاماتُ
المردودة) تُؤخذ من `riwaya_floor_six.py` على الكاشف المشحون قبلَ القاعدة وبعدَها.

**الصورةُ بعينِها.** `۪` (U+06EA · ARABIC EMPTY CENTRE LOW STOP) علامةُ **الإمالة والتقليل**
في رسم ورشٍ والدوريِّ والسوسيّ، وتوضع تحت الحرف الممال؛ فتُكتب ألفُ الإمالة ياءً تحتها هذه
العلامةُ وفوقها الخنجريّة:

    douri/sousi: `اِ۪فۡتَر۪يٰ` ⇜ اليومَ «افتريا»  ·  والصوابُ «افتري»  (‏حفصٌ `اِفۡتَرَىٰ` ⇜ «افتري»)
    warsh:       `أَدۡر۪يٰكَ`  ⇜ اليومَ «ادرياك» ·  والصوابُ «ادريك»  (‏حفصٌ `أَدۡرَىٰكَ` ⇜ «ادريك»)

    الذراع (ت) = في `norm`، بجوار قاعدة D-402 نفسِها:  `۪يٰ` ⇒ `۪ي`  (‏تُسقَط الخنجرية)

🔒 **الفرقُ عن D-402 الذي يوجب ذراعاً مستقلّة:** قاعدةُ D-402 (`ۭيٰ`) كانت **محصورةً بالبناء**
في الدوريِّ والسوسيّ ⇒ رقمُ D-288 المسنود (‏حفص 57 · ورش 239 · قالون 302) سليمٌ بلا قياس.
وهذه القاعدةُ **تمسُّ ورشاً في 310 مواضع** ⇒ الضابطُ المسنودُ نفسُه يتحرّك، فلا يجوز تطبيقُها
إلّا برقمٍ يُبيّن أنّ الحركةَ **ردُّ اتّهامٍ كاذبٍ لا فقدُ إصابة**. وضابطُ هذه الذراع بديلٌ
وأقوى: **موافقةُ حفص** — أتُطابق المِسطرةُ بعد القاعدة تطبيعَ حفصٍ لنفس الكلمة في نفس الموضع؟

    python tools/tasmi_bench/imala_stop_norm_arm.py            # ١ الإحصاء ٢ موافقةُ حفص ٣ التكلفة
    python tools/tasmi_bench/imala_stop_norm_arm.py --examples 12

⛔ قياسٌ وتقريرٌ: هذا الملفُّ لا يكتب في ملفِّ محرّكٍ ولا مرآة.
"""
import argparse
import collections
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "tools", "alignment"))
import scorer  # noqa: E402
import parity_full as P  # noqa: E402
from common import load_text  # noqa: E402

SIX = ("hafs", "warsh", "qalun", "shuba", "douri", "sousi")
TRIPLE = "۪يٰ"        # ۪ (U+06EA) + ي + الخنجرية — الصورةُ الملتصقةُ وحدَها
FIXED = "۪ي"          # الذراع (ت) — ما تقترحه هذه الذراع
OLD = "۪يا"           # الذراع (ق) — ما كانت المِسطرةُ تفعله (خنجريّةٌ ⇒ ألف)
SKIP = "۞"            # علامةُ الرُّبع: كلمةٌ مستقلّةٌ في بعض الرسوم لا في حفص ⇒ تُسقَط عند المحاذاة
# الرواياتُ الممالةُ بهذه العلامة؛ وما عداها يجب أن يكون **صفراً** (الضابط أ).
IMALA_RIWAYAT = ("warsh", "douri", "sousi")
CLEAN_RIWAYAT = ("hafs", "qalun", "shuba")


def stop_fix(word):
    """الذراع (ت) — القاعدةُ المقترَحة، مطبَّقةً على الكلمة الخام قبل `norm`."""
    return word.replace(TRIPLE, FIXED)


def stop_old(word):
    """الذراع (ق) — سلوكُ المِسطرة **قبلَ** القاعدة، مكتوباً نصّاً لا مقروءاً من القرص.

    🔒 **ولِمَ نصّاً؟** لأنّ القاعدةَ متى شُحنت في `scorer.norm` صار `norm(w)` هو «بعدَ»،
    فتقيس الذراعُ صفراً وتكذب. والسلوكُ القديمُ معروفٌ بعينِه: الخنجريّةُ تصير ألفاً
    (`۪يٰ` ⇜ `۪يا` ⇜ «…يا»). فبكتابته نصّاً تعطي الذراعُ **الرقمَ نفسَه قبلَ الشحن وبعدَه**.
    """
    return word.replace(TRIPLE, OLD)


def census(examples=8):
    """١ · **الإحصاء والضابط (أ):** أين تقع الصورةُ، وهل تمسُّ روايةً لا إمالةَ لها بهذه العلامة؟"""
    print("=== ١ إحصاءُ صورة الإمالة `۪يٰ` · المصحف كلُّه · الرواياتُ الستّ ===")
    print("   (‏الملتصقُ وحدَه؛ ولا موضعَ في المصحف تفصل فيه علامةٌ بين الأحرف الثلاثة)")
    hits = {}
    for r in SIX:
        cfg = P.config_for(r)
        occ = collections.Counter()
        changed = collections.Counter()
        for ayah in load_text(r):
            for w in ayah.split():
                if TRIPLE not in w:
                    continue
                occ[w] += 1
                if scorer.norm(stop_fix(w), cfg) != scorer.norm(stop_old(w), cfg):
                    changed[w] += 1
        hits[r] = (occ, changed)
        print("  %-6s مواضعُ الصورة %5d (فريدة %4d) · يتغيّر تطبيعُها %5d (فريدة %4d)"
              % (r, sum(occ.values()), len(occ), sum(changed.values()), len(changed)))
    print("\n🧪 **الضابطُ (أ) — القاعدةُ مرساةٌ في الرسم:** `۪` علامةُ إمالةٍ وتقليلٍ لا تقع إلّا")
    print("   في ورشٍ والدوريِّ والسوسيّ؛ فحفصٌ وقالونُ وشعبةُ يجب أن تكون **صفراً**.")
    ok = True
    for r in CLEAN_RIWAYAT:
        n = sum(hits[r][1].values())
        ok = ok and n == 0
        print("   %-6s %5d  %s" % (r, n, "✅" if n == 0 else "🚨 القاعدةُ تتعدّى"))
    for r in IMALA_RIWAYAT:
        print("   %-6s %5d  (‏المقصودُ بالقاعدة)" % (r, sum(hits[r][1].values())))
    print("   %s" % ("✅ القاعدةُ محصورةٌ في الروايات الثلاث الممالة بهذه العلامة" if ok
                     else "🚨 لا تُطبَّق القاعدةُ حتى يُفهم التعدّي"))
    print("\n=== أكثرُ الصورِ تكراراً · قبلَ ⇜ بعدَ ===")
    for r in IMALA_RIWAYAT:
        cfg = P.config_for(r)
        for w, n in hits[r][1].most_common(examples):
            print("  %-6s «%s» ×%-4d  «%s» ⇜ «%s»  (‏whisper: «%s»)"
                  % (r, w, n, scorer.norm(stop_old(w), cfg), scorer.norm(stop_fix(w), cfg),
                     P.whisper_forms(stop_old(w), cfg)[-1]))
    return ok, hits


def hafs_agreement(examples=8):
    """٢ · **ضابطُ موافقة حفص** — وهو ضابطُ هذه الذراع الأقوى، لأنّ ورشاً ليس محصوراً بالبناء.

    الكلمةُ الممالةُ في ورشٍ أو الدوريِّ أو السوسيِّ هي **الكلمةُ نفسُها** في حفصٍ مرسومةً
    `ىٰ` (‏ألفٌ مقصورةٌ + خنجرية)، وقاعدةُ D-274 تُطبِّعها في حفصٍ إلى `ي`. فإن كانت المِسطرةُ
    بعدَ القاعدة تُعطي في الروايةِ الممالةِ **ما تعطيه في حفصٍ بعينِه**، فالقاعدةُ ليست اجتهاداً
    جديداً بل **إلحاقُ صورةٍ رابعةٍ بقاعدةٍ قائمةٍ مقيسة**؛ وإن باعدت بينهما فهي ريبة.

    المقارنةُ بفهرس الكلمة داخل الآية، وتُتخطّى الآياتُ التي يختلف فيها عددُ الكلمات
    (‏فرشٌ يزيد كلمةً أو ينقصها) فلا يُوثَق بالمحاذاة فيها.
    """
    print("\n=== ٢ ضابطُ موافقة حفص (‏الكلمةُ نفسُها · نفسُ الآية ونفسُ الفهرس) ===")
    hafs = [[x for x in a.split() if x != SKIP] for a in load_text("hafs")]
    hcfg = P.config_for("hafs")
    tot = collections.Counter()
    ex = collections.defaultdict(list)
    for r in IMALA_RIWAYAT:
        cfg = P.config_for(r)
        for ai, ayah in enumerate(load_text(r)):
            ws = [x for x in ayah.split() if x != SKIP]
            if ai >= len(hafs) or len(ws) != len(hafs[ai]):
                continue          # محاذاةٌ غيرُ موثوقة — تُتخطّى ولا تُحسب
            for i, w in enumerate(ws):
                if TRIPLE not in w:
                    continue
                h = scorer.norm(hafs[ai][i], hcfg)
                before = scorer.norm(stop_old(w), cfg)
                after = scorer.norm(stop_fix(w), cfg)
                tot[(r, "n")] += 1
                tot[(r, "before")] += 1 if before == h else 0
                tot[(r, "after")] += 1 if after == h else 0
                if after != h and len(ex[r]) < examples:
                    ex[r].append((ai + 1, w, before, after, h))
    for r in IMALA_RIWAYAT:
        n = tot[(r, "n")]
        if not n:
            print("  %-6s لا موضعَ محاذًى" % r)
            continue
        print("  %-6s مواضعُ مقارَنةٍ %4d · توافق حفصاً قبلَ القاعدة %4d (%.1f٪) · بعدَها %4d (%.1f٪)"
              % (r, n, tot[(r, "before")], 100.0 * tot[(r, "before")] / n,
                 tot[(r, "after")], 100.0 * tot[(r, "after")] / n))
    print("\n=== مواضعُ لم توافق حفصاً بعد القاعدة (‏إن وُجدت — فرشٌ أو صورةٌ أخرى) ===")
    any_ex = False
    for r in IMALA_RIWAYAT:
        for (ay, w, b, a, h) in ex[r][:3]:
            any_ex = True
            print("  %-6s آية %4d · «%s» · «%s» ⇜ «%s» · وحفصٌ «%s»" % (r, ay, w, b, a, h))
    if not any_ex:
        print("  ✅ لا شيء: كلُّ موضعٍ مُحاذًى وافق تطبيعَ حفصٍ بعد القاعدة")
    return tot


def cost(hits, examples=8):
    """٣ · **التكلفة:** أيَعمى بابُ القبول عن خطأ تلاوةٍ حقيقيٍّ بعد القاعدة؟

    بالضلعين نفسِهما اللذين قاست بهما D-402:
      (ب) **الاتّساع:** صورٌ يقبلها المحركُ بعد القاعدة ولم يكن يقبلها قبلَها.
      (ج) **الاصطدام:** أتساوي صورةٌ **جديدةٌ** مقبولةٌ صورةَ كلمةٍ قرآنيةٍ **أخرى** (رسمٌ مختلف)
          في الرواية نفسِها؟ فذاك إبدالٌ حقيقيٌّ يعمى عنه.
    """
    print("\n=== ٣ تكلفةُ القاعدة في بابِ القبول (‏المصحف كلُّه) ===")
    widened = collections.Counter()
    narrowed = collections.Counter()
    new_forms = collections.defaultdict(collections.Counter)
    for r in IMALA_RIWAYAT:
        cfg = P.config_for(r)
        for w, n in hits[r][1].items():
            before = set(scorer.variants(stop_old(w), cfg))
            after = set(scorer.variants(stop_fix(w), cfg))
            for f in after - before:
                widened[r] += n
                new_forms[r][(w, f)] += n
            if before - after:
                narrowed[r] += n
    for r in IMALA_RIWAYAT:
        print("  %-6s صورةٌ مقبولةٌ جديدةٌ في %4d موضعاً · صورةٌ مقبولةٌ سقطت في %4d موضعاً"
              % (r, widened[r], narrowed[r]))
    for r in IMALA_RIWAYAT:
        for (w, f), n in new_forms[r].most_common(3):
            print("     %-6s «%s» ×%-3d صورةٌ جديدةٌ «%s»" % (r, w, n, f))
    print("\n=== ٤ اصطدامُ الصورةِ الجديدةِ بكلمةٍ قرآنيةٍ **أخرى** (‏عمًى عن إبدالٍ حقيقيّ) ===")
    print("   «أخرى» = كلمةٌ يختلف تطبيعُها بعدَ رفع الإمالة عن هذه؛ فاختلافُ رسمِ الإمالة")
    print("   وحدَه (‏`أَدۡرَىٰكَ` ⇄ `أَدۡر۪يٰكَ`) **كلمةٌ واحدةٌ** لا اصطدام.")
    total = 0
    for r in IMALA_RIWAYAT:
        cfg = P.config_for(r)
        by_form = collections.defaultdict(set)
        for ayah in load_text(r):
            for w in ayah.split():
                for f in scorer.variants(stop_old(w), cfg):
                    if f:
                        by_form[f].add(w)
        clash = collections.Counter()
        ex = []
        for w, n in hits[r][1].items():
            before = set(scorer.variants(stop_old(w), cfg))
            mine = scorer.norm(stop_fix(w), cfg)
            for f in set(scorer.variants(stop_fix(w), cfg)) - before:
                real = set()
                for o in by_form.get(f, set()) - {w}:
                    if scorer.norm(stop_fix(o), cfg) == mine:
                        continue          # الكلمةُ نفسُها برسمِ إمالةٍ مختلف — لا اصطدام
                    # 🔒 والاصطدامُ **الجديدُ** وحدَه يُحسب: إن كانت الكلمتان تشتركان في
                    # صورةٍ مقبولةٍ **قبلَ** القاعدة فالعمى قائمٌ أصلاً وليس من صنعها.
                    if before & set(scorer.variants(stop_old(o), cfg)):
                        continue
                    real.add(o)
                if real:
                    clash[r] += n
                    if len(ex) < examples:
                        ex.append((w, f, sorted(real)[:3]))
        total += clash[r]
        print("  %-6s مواضعُ العمى الجديدة: %d" % (r, clash[r]))
        for (w, f, o) in ex[:3]:
            print("     «%s» ⇜ «%s» يصطدم بـ %s" % (w, f, " · ".join("«%s»" % x for x in o)))
    print("  ⇒ %s" % ("✅ **صفر**: لا صورةَ جديدةً تبتلع كلمةً أخرى ⇒ لا خطأ تلاوةٍ يعمى عنه "
                      "البابُ بسبب القاعدة." if total == 0 else
                      "🚨 ثمّةُ عمًى جديدٌ — لا تُطبَّق القاعدةُ حتى يُوزن."))
    return total


def main():
    ap = argparse.ArgumentParser(description="علامةُ الإمالة `۪` في المِسطرة — إحصاءٌ وضابطٌ وتكلفة")
    ap.add_argument("--examples", type=int, default=8)
    args = ap.parse_args()
    ok, hits = census(args.examples)
    agree = hafs_agreement(args.examples)
    blind = cost(hits, args.examples)
    print("\n=== الخلاصة ===")
    print("  القاعدةُ محصورةٌ في الروايات الممالة: %s" % ("✅" if ok else "🚨"))
    miss = sum(agree[(r, "n")] - agree[(r, "after")] for r in IMALA_RIWAYAT)
    print("  مواضعُ لم توافق حفصاً بعد القاعدة: %d %s" % (miss, "✅" if miss == 0 else "⚠️"))
    print("  عمًى جديدٌ عن خطأ تلاوة: %d موضعاً %s" % (blind, "✅" if blind == 0 else "🚨"))
    print("  الفائدةُ المقيسةُ تُؤخذ من `riwaya_floor_six.py` قبلَ القاعدة وبعدَها (‏مرجع D-402: 1162).")
    return 0 if (ok and blind == 0) else 1


if __name__ == "__main__":
    sys.exit(main())
