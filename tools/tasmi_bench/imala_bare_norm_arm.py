# -*- coding: utf-8 -*-
"""📐 **الصورةُ الخامسة: الياءُ الممالةُ المجرّدةُ `يٰ` في المِسطرة** — بلا صوت.

⚠️ **لِمَ وُجد.** سلّم D-403 دَيناً نصّاً في `docs/qa/CLOUD_DUTY.md`:

    «**الصورةُ الخامسةُ** `يٰ` **مجرّدةً** (بلا `ۭ` ولا `۪`) — قالون **335** · ورش **25** ·
     و**صفرٌ** في حفصٍ وشعبةَ والدوريِّ والسوسيّ. وصدارةُ اتّهامات قالونَ الباقية (‏302 —
     أكبرُ بقيّةٍ في اللوحة) هي `أَدْرَيٰكَ`⇜«ادريك»×13 و`أَتَيٰكَ`×6 أي هذه الصورةُ بعينِها.
     ⚠️ ولا تُطبَّق بلا ذراعٍ مقيسةٍ وحدَها: رقمُ قالون (302) آخرُ أرقام D-288 الثلاثة الباقي
     بلا حركة، ومسُّه يمسُّه — ويُبنى لها ذراعٌ على منوال `imala_stop_norm_arm.py`.»

وهذا الملفُّ **هو تلك الذراع**، على المنوال المطلوب حرفاً بحرف: (أ) الإحصاءُ والحصر ·
(ب) موافقةُ حفصٍ ضابطاً · (ج) الاتّساعُ والاصطدامُ **الجديدُ** وحدَه تكلفةً. والفائدةُ
(الاتّهاماتُ المردودة) تُؤخذ من `riwaya_floor_six.py` على الكاشف المشحون قبلَ القاعدة وبعدَها.

**الصورةُ بعينِها.** ياءٌ صريحةٌ يعلوها ألفٌ خنجريّةٌ **مباشرةً** ولا علامةَ إمالةٍ تحتها:

    qalun: `أَدْرَيٰكَ`  ⇜ اليومَ «ادرياك» · والصوابُ «ادريك»  (‏حفصٌ `أَدۡرَىٰكَ` ⇜ «ادريك»)
    warsh: `بَنَيٰهَا`   ⇜ اليومَ «بنياها» · والصوابُ «بنيها»  (‏حفصٌ `بَنَىٰهَا` ⇜ «بنيها»)

    الذراع (ت) = في `norm`، بجوار قواعد D-274/402/403:   `يٰ` ⇒ `ي`  (‏تُسقَط الخنجرية)
    والذراع (ق) = الشحنُ نفسُه وهذه القاعدةُ وحدَها معطَّلةٌ في الذاكرة — انظر `rule_off`.

🔒 **الفرقُ عن D-402 وD-403 الذي يوجب ذراعاً ثالثةً مستقلّة:** تانك محصورتان بعلامةٍ تحت
الحرف (`ۭ` · `۪`) تُعيّن الروايةَ وتُثبّت الموضع. وهذه **مجرّدةٌ**: لا علامةَ تحصرها، ومسُّها
يمسُّ **قالون** في 335 موضعاً — ورقمُ قالون (302) هو آخرُ أرقام D-288 الثلاثة الباقي بلا حركة.
فلا يجوز تطبيقُها إلّا برقمٍ يُبيّن أنّ الحركةَ **ردُّ اتّهامٍ كاذبٍ لا فقدُ إصابة**.

    python tools/tasmi_bench/imala_bare_norm_arm.py            # ١ الإحصاء ٢ موافقةُ حفص ٣ التكلفة
    python tools/tasmi_bench/imala_bare_norm_arm.py --examples 12

⛔ قياسٌ وتقريرٌ: هذا الملفُّ لا يكتب في ملفِّ محرّكٍ ولا مرآة.
"""
import argparse
import collections
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "tools", "alignment"))
import scorer  # noqa: E402
import parity_full as P  # noqa: E402
from common import load_text  # noqa: E402

SIX = ("hafs", "warsh", "qalun", "shuba", "douri", "sousi")
DAGGER = "ٰ"                 # U+0670 ALEF SUPERSCRIPT — الخنجرية
MARKS = "ۭ۪"                  # U+06ED (ميمٌ صغيرة · D-402) · U+06EA (وقفٌ أسفل · D-403)
# **المجرّدةُ وحدَها:** ياءٌ + خنجريّةٌ ملتصقتان، ولا علامةَ من علامتي الإمالة قبلَ الياء.
BARE = re.compile("(?<![%s])ي%s" % (MARKS, DAGGER))
SKIP = "۞"                   # علامةُ الرُّبع: كلمةٌ مستقلّةٌ في بعض الرسوم لا في حفص
# الرواياتُ التي تقع فيها الصورةُ المجرّدة؛ وما عداها يجب أن يكون **صفراً** (الضابط أ).
BARE_RIWAYAT = ("warsh", "qalun")
CLEAN_RIWAYAT = ("hafs", "shuba", "douri", "sousi")


class rule_off(object):
    """الذراع (ق) — سلوكُ المِسطرة **قبلَ** القاعدة: الشحنُ نفسُه و**القاعدةُ وحدَها معطَّلة**.

    🔒 **ولِمَ هكذا لا بنصٍّ مكتوب؟** لأنّ «قبلَ» ليس تطبيعَ الكلمة وحدَه بل **بابُ القبول
    كلُّه**: `variants` يفتح عند `dagger_optional` صورةً ثانيةً شرطُها `"ٰ" in word`. فلو
    كُتب القديمُ نصّاً (‏`يٰ` ⇜ `يا`) لسقطت الخنجريّةُ من الكلمة الخام فانطفأ ذلك الشرطُ،
    فقاست الذراعُ باباً أضيقَ ممّا كان فعلاً وأوهمت أنّ القاعدةَ **توسّعه**. وبتعطيل القاعدة
    وحدَها يبقى كلُّ ما عداها على حاله ⇒ الفرقُ المقيسُ هو أثرُ القاعدة لا أثرُ القياس.
    """

    def __enter__(self):
        assert hasattr(scorer, "_BARE_IMALA"), "القاعدةُ غيرُ مشحونةٍ في المرآة"
        self.saved = scorer._BARE_IMALA
        scorer._BARE_IMALA = re.compile("(?!)")      # لا يطابق شيئاً ⇒ القاعدةُ معطَّلة
        return self

    def __exit__(self, *a):
        scorer._BARE_IMALA = self.saved
        return False


def norm_old(word, cfg):
    with rule_off():
        return scorer.norm(word, cfg)


def variants_old(word, cfg):
    with rule_off():
        return scorer.variants(word, cfg)


def census(examples=8):
    """١ · **الإحصاء والضابط (أ):** أين تقع الصورةُ المجرّدة، وكم موضعاً يتغيّر تطبيعُه؟"""
    print("=== ١ إحصاءُ الصورة المجرّدة `يٰ` · المصحف كلُّه · الرواياتُ الستّ ===")
    print("   (‏الملتصقُ وحدَه ولا علامةَ إمالةٍ قبلَه؛ فـ`يَٰٓأَيُّهَا` خارجَها لأنّ بين الحرفين حركة)")
    hits = {}
    for r in SIX:
        cfg = P.config_for(r)
        occ = collections.Counter()
        changed = collections.Counter()
        for ayah in load_text(r):
            for w in ayah.split():
                if not BARE.search(w):
                    continue
                occ[w] += 1
                if scorer.norm(w, cfg) != norm_old(w, cfg):
                    changed[w] += 1
        hits[r] = (occ, changed)
        print("  %-6s مواضعُ الصورة %5d (فريدة %4d) · يتغيّر تطبيعُها %5d (فريدة %4d)"
              % (r, sum(occ.values()), len(occ), sum(changed.values()), len(changed)))
    print("\n🧪 **الضابطُ (أ) — أين تقع القاعدةُ فعلاً:** الصورةُ المجرّدةُ رسمُ قالونَ وورشٍ")
    print("   وحدَهما؛ والدوريُّ والسوسيُّ يكتبان علامةَ الإمالة تحت الياء دائماً (‏D-402/403).")
    ok = True
    for r in CLEAN_RIWAYAT:
        n = sum(hits[r][1].values())
        ok = ok and n == 0
        print("   %-6s %5d  %s" % (r, n, "✅" if n == 0 else "⚠️ خارجَ المتوقَّع — يُفهم قبل التطبيق"))
    for r in BARE_RIWAYAT:
        print("   %-6s %5d  (‏المقصودُ بالقاعدة)" % (r, sum(hits[r][1].values())))
    print("   %s" % ("✅ القاعدةُ لا تمسّ حفصاً ولا شعبةَ ولا الدوريَّ ولا السوسيَّ بحرفٍ واحد"
                     if ok else "🚨 لا تُطبَّق القاعدةُ حتى يُفهم التعدّي"))
    print("\n=== أكثرُ الصورِ تكراراً · قبلَ ⇜ بعدَ ===")
    for r in BARE_RIWAYAT:
        cfg = P.config_for(r)
        for w, n in hits[r][1].most_common(examples):
            print("  %-6s «%s» ×%-4d  «%s» ⇜ «%s»  (‏whisper: «%s»)"
                  % (r, w, n, norm_old(w, cfg), scorer.norm(w, cfg),
                     P.whisper_forms(w, cfg)[-1]))
    return ok, hits


def hafs_agreement(examples=8):
    """٢ · **ضابطُ موافقة حفص** — ضابطُ هذه الذراع، لأنّ الصورةَ ليست محصورةً بعلامة.

    الكلمةُ في قالونَ أو ورشٍ هي **الكلمةُ نفسُها** في حفصٍ مرسومةً `ىٰ` (‏ألفٌ مقصورةٌ +
    خنجريّة)، وقاعدةُ D-274 تُطبِّعها في حفصٍ إلى `ى`⇜`ي`. فإن كانت المِسطرةُ بعدَ القاعدة
    تُعطي **ما تعطيه في حفصٍ بعينِه**، فالقاعدةُ ليست اجتهاداً جديداً بل **إلحاقُ صورةٍ خامسةٍ
    بقاعدةٍ قائمةٍ مقيسة**؛ وإن باعدت بينهما فهي ريبة.

    المقارنةُ بفهرس الكلمة داخل الآية، وتُتخطّى الآياتُ التي يختلف فيها عددُ الكلمات
    (‏فرشٌ يزيد كلمةً أو ينقصها) فلا يُوثَق بالمحاذاة فيها.
    """
    print("\n=== ٢ ضابطُ موافقة حفص (‏الكلمةُ نفسُها · نفسُ الآية ونفسُ الفهرس) ===")
    hafs = [[x for x in a.split() if x != SKIP] for a in load_text("hafs")]
    hcfg = P.config_for("hafs")
    tot = collections.Counter()
    ex = collections.defaultdict(list)
    for r in BARE_RIWAYAT:
        cfg = P.config_for(r)
        for ai, ayah in enumerate(load_text(r)):
            ws = [x for x in ayah.split() if x != SKIP]
            if ai >= len(hafs) or len(ws) != len(hafs[ai]):
                continue          # محاذاةٌ غيرُ موثوقة — تُتخطّى ولا تُحسب
            for i, w in enumerate(ws):
                if not BARE.search(w):
                    continue
                h = scorer.norm(hafs[ai][i], hcfg)
                before = norm_old(w, cfg)
                after = scorer.norm(w, cfg)
                tot[(r, "n")] += 1
                tot[(r, "before")] += 1 if before == h else 0
                tot[(r, "after")] += 1 if after == h else 0
                if after != h and len(ex[r]) < examples:
                    ex[r].append((ai + 1, w, before, after, h))
    for r in BARE_RIWAYAT:
        n = tot[(r, "n")]
        if not n:
            print("  %-6s لا موضعَ محاذًى" % r)
            continue
        print("  %-6s مواضعُ مقارَنةٍ %4d · توافق حفصاً قبلَ القاعدة %4d (%.1f٪) · بعدَها %4d (%.1f٪)"
              % (r, n, tot[(r, "before")], 100.0 * tot[(r, "before")] / n,
                 tot[(r, "after")], 100.0 * tot[(r, "after")] / n))
    print("\n=== مواضعُ لم توافق حفصاً بعد القاعدة (‏إن وُجدت — فرشٌ أو صورةٌ أخرى) ===")
    any_ex = False
    for r in BARE_RIWAYAT:
        for (ay, w, b, a, h) in ex[r][:4]:
            any_ex = True
            print("  %-6s آية %4d · «%s» · «%s» ⇜ «%s» · وحفصٌ «%s»" % (r, ay, w, b, a, h))
    if not any_ex:
        print("  ✅ لا شيء: كلُّ موضعٍ مُحاذًى وافق تطبيعَ حفصٍ بعد القاعدة")
    return tot


def cost(hits, examples=8):
    """٣ · **التكلفة:** أيَعمى بابُ القبول عن خطأ تلاوةٍ حقيقيٍّ بعد القاعدة؟

    بالضلعين نفسِهما اللذين قاست بهما D-402 وD-403:
      (ب) **الاتّساع:** صورٌ يقبلها المحركُ بعد القاعدة ولم يكن يقبلها قبلَها.
      (ج) **الاصطدام:** أتساوي صورةٌ **جديدةٌ** مقبولةٌ صورةَ كلمةٍ قرآنيةٍ **أخرى** (رسمٌ مختلف)
          في الرواية نفسِها؟ فذاك إبدالٌ حقيقيٌّ يعمى عنه.
    """
    print("\n=== ٣ تكلفةُ القاعدة في بابِ القبول (‏المصحف كلُّه) ===")
    widened = collections.Counter()
    narrowed = collections.Counter()
    new_forms = collections.defaultdict(collections.Counter)
    for r in BARE_RIWAYAT:
        cfg = P.config_for(r)
        for w, n in hits[r][1].items():
            before = set(variants_old(w, cfg))
            after = set(scorer.variants(w, cfg))
            for f in after - before:
                widened[r] += n
                new_forms[r][(w, f)] += n
            if before - after:
                narrowed[r] += n
    for r in BARE_RIWAYAT:
        print("  %-6s صورةٌ مقبولةٌ جديدةٌ في %4d موضعاً · صورةٌ مقبولةٌ سقطت في %4d موضعاً"
              % (r, widened[r], narrowed[r]))
    for r in BARE_RIWAYAT:
        for (w, f), n in new_forms[r].most_common(3):
            print("     %-6s «%s» ×%-3d صورةٌ جديدةٌ «%s»" % (r, w, n, f))
    print("\n=== ٤ اصطدامُ الصورةِ الجديدةِ بكلمةٍ قرآنيةٍ **أخرى** (‏عمًى عن إبدالٍ حقيقيّ) ===")
    print("   «أخرى» = كلمةٌ يختلف تطبيعُها بعدَ رفع الإمالة عن هذه؛ فاختلافُ رسمِ الإمالة")
    print("   وحدَه (‏`أَدۡرَىٰكَ` ⇄ `أَدْرَيٰكَ`) **كلمةٌ واحدةٌ** لا اصطدام.")
    total = 0
    for r in BARE_RIWAYAT:
        cfg = P.config_for(r)
        by_form = collections.defaultdict(set)
        for ayah in load_text(r):
            for w in ayah.split():
                for f in variants_old(w, cfg):
                    if f:
                        by_form[f].add(w)
        clash = collections.Counter()
        ex = []
        for w, n in hits[r][1].items():
            before = set(variants_old(w, cfg))
            mine = scorer.norm(w, cfg)
            for f in set(scorer.variants(w, cfg)) - before:
                real = set()
                for o in by_form.get(f, set()) - {w}:
                    if scorer.norm(o, cfg) == mine:
                        continue          # الكلمةُ نفسُها برسمِ إمالةٍ مختلف — لا اصطدام
                    # 🔒 والاصطدامُ **الجديدُ** وحدَه يُحسب: إن كانت الكلمتان تشتركان في
                    # صورةٍ مقبولةٍ **قبلَ** القاعدة فالعمى قائمٌ أصلاً وليس من صنعها.
                    if before & set(variants_old(o, cfg)):
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


# 📊 إحصاءُ الصورة المجرّدة على المصحف كلِّه (‏قِيس 2026-09-15 · D-618) — وهو عينُ ما نصّ عليه
#    دَينُ D-403: «قالون 335 · ورش 25 · وصفرٌ في حفصٍ وشعبةَ والدوريِّ والسوسيّ».
BARE_CENSUS = {"hafs": 0, "warsh": 25, "qalun": 335, "shuba": 0, "douri": 0, "sousi": 0}

# 🩻 وما كان يقع **لو رُفع النظرُ الخلفيُّ** من `BARE` — مقيسٌ لا مظنون (‏D-618):
#    فالنظرُ الخلفيُّ هو **وحدَه** ما يُبقي الدوريَّ والسوسيَّ خارجَ هذه الصورة.
NO_LOOKBEHIND = {"hafs": 0, "warsh": 335, "qalun": 335, "shuba": 0, "douri": 605, "sousi": 572}


def selftest():
    """🧪 **حارسُ الصورة الخامسة** (‏D-618) — والشوطُ الأصليُّ ثقيلٌ (إحصاءٌ وضابطٌ وتكلفة)،
    وهذا يفحص في ثانيةٍ **حدَّ القاعدة** الذي عليه مدارُ الإذن بها.

    ⭐⭐ **ولِمَ هو أخطرُ ما في الملفّ:** دَينُ D-403 يشترط أن تكون هذه الصورةُ **محصورةً**
    في ورشٍ وقالون، «وصفرٌ في حفصٍ وشعبةَ والدوريِّ والسوسيّ». **والحاصرُ حرفٌ واحدٌ في
    التعبير النمطيّ: النظرُ الخلفيُّ `(?<![ۭ۪])`.** ولو سقط لصار الدوريُّ **605** والسوسيُّ
    **572** بدل الصفر ⇒ **قاعدةٌ أُذن بها لروايتين تمسّ أربعاً**، وذلك عطبٌ صامتٌ تماماً:
    الأرقامُ تكبر ولا شيءَ يصرخ. ⇒ فيُثبَّت الإحصاءُ **ونقيضُه** معاً.
    """
    ok = True

    def say(good, line):
        nonlocal ok
        ok &= bool(good)
        print(("✅ " if good else "❌ ") + line)

    got = {r: sum(len(BARE.findall(w)) for a in load_text(r) for w in a.split())
           for r in SIX}
    say(got == BARE_CENSUS,
        "⭐⭐ الإحصاءُ كما نصّ دَينُ D-403: قالون %d · ورش %d · وصفرٌ في الأربع"
        % (got["qalun"], got["warsh"]))
    say(all(got[r] == 0 for r in CLEAN_RIWAYAT) and set(BARE_RIWAYAT) == {"warsh", "qalun"},
        "⛔ والقاعدةُ **محصورةٌ** في ورشٍ وقالون: الأربعُ الأخرى صفرٌ")

    # ⭐⭐ والحاصرُ هو النظرُ الخلفيُّ — يُقاس نقيضُه لا يُفترَض
    no_look = re.compile("ي%s" % DAGGER)
    got2 = {r: sum(len(no_look.findall(w)) for a in load_text(r) for w in a.split())
            for r in SIX}
    say(got2 == NO_LOOKBEHIND,
        "🩻 ولو رُفع النظرُ الخلفيُّ: دوري **%d** وسوسي **%d** وورش **%d** بدل الصفر والـ25"
        % (got2["douri"], got2["sousi"], got2["warsh"]))
    say(got2["douri"] > 0 and got["douri"] == 0 and got2["sousi"] > 0 and got["sousi"] == 0,
        "⭐⭐ ⇒ **النظرُ الخلفيُّ حاملٌ لا زينة**: هو وحدَه ما يُخرج الدوريَّ والسوسيَّ من الباب")

    # ⛔ وعلامتا الحصر هما المنصوصتان في D-402/D-403 لا غيرُهما
    say(MARKS == "ۭ۪" and DAGGER == "ٰ",
        "⛔ وعلامتا الحصر `U+06ED` (D-402) و`U+06EA` (D-403) والخنجريّةُ `U+0670` كما هي")
    say("(?<![" in BARE.pattern and BARE.pattern.endswith(DAGGER),
        "⛔ والتعبيرُ يحصر بالنظر الخلفيّ ويشترط الخنجريّةَ **مباشرةً** بعد الياء")

    print("\n%s" % ("✅ حارسُ الصورة الخامسة: تمّ" if ok else "❌ حارسُ الصورة الخامسة: أخفق"))
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description="الصورةُ المجرّدة `يٰ` في المِسطرة — إحصاءٌ وضابطٌ وتكلفة")
    ap.add_argument("--examples", type=int, default=8)
    ap.add_argument("--selftest", action="store_true",
                    help="🧪 حارسُ حدِّ القاعدة (ثانيةٌ · بلا ضابطٍ ولا تكلفة)")
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    ok, hits = census(args.examples)
    agree = hafs_agreement(args.examples)
    blind = cost(hits, args.examples)
    print("\n=== الخلاصة ===")
    print("  القاعدةُ لا تتعدّى إلى الروايات الأربع الأخرى: %s" % ("✅" if ok else "🚨"))
    miss = sum(agree[(r, "n")] - agree[(r, "after")] for r in BARE_RIWAYAT)
    print("  مواضعُ لم توافق حفصاً بعد القاعدة: %d %s" % (miss, "✅" if miss == 0 else "⚠️"))
    print("  عمًى جديدٌ عن خطأ تلاوة: %d موضعاً %s" % (blind, "✅" if blind == 0 else "🚨"))
    print("  الفائدةُ المقيسةُ تُؤخذ من `riwaya_floor_six.py` قبلَ القاعدة وبعدَها (‏مرجع D-403: 730).")
    return 0 if (ok and blind == 0) else 1


if __name__ == "__main__":
    sys.exit(main())
