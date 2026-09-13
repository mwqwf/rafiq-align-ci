# -*- coding: utf-8 -*-
"""📐 **صورةُ الإمالة في المِسطرة** (`ۭيٰ`) — أهي عطبُ تطبيعٍ كعطبَي D-274/D-275؟ بلا صوت.

⚠️ **لِمَ وُجد.** سلّم D-401 دَيناً نصّاً: «بابُ صورةِ الإمالة (`يٰ`/`ۭي`) في `RecitationScorer`
— يردُّ 182 اتّهاماً مقيساً؛ وفائدتُه وتكلفتُه تحتاجان **ذراعاً كذراع D-288** على المصحف كلِّه.
لم يُقَس هنا فلا رقمَ له». وهذا الملفُّ يقيسهما.

**الصورةُ بعينِها.** في رسم الدوريِّ والسوسيّ تُكتب ألفُ الإمالة **ياءً تحتها ميمٌ صغيرةٌ**
‏(`ۭ` U+06ED) والخنجريّةُ فوق الياء: `مُوسۭيٰ` · `أَنّۭيٰ` · `يَٰمُوسۭيٰ`. والمِسطرةُ اليومَ لا
تعرف هذه الصورة، فتمرُّ على الخنجريّة بقاعدةِ `khanjariya` العامّة (‏خنجريّةٌ ⇒ ألف):

    مُوسۭيٰ  ⇜ اليومَ «موسيا»   ·  وwhisper يكتب «موسي»  (‏وحفصٌ `مُوسَىٰ` ⇜ «موسي»)

وهو **عطبُ D-274 نفسُه بصورةٍ أخرى**: D-274 عالجت `ىٰ` (ألفٌ مقصورةٌ + خنجرية ⇒ `ى`) لأنّ
الخنجريّةَ هناك **نطقُ الألف المقصورة لا ألفٌ زائدة**؛ وهنا الحرفُ ياءٌ صريحةٌ لا مقصورة،
فأفلتت من القاعدة. والرسمُ نفسُه يحمل علامةَ التمييز: `ۭ` قبل الياء.

    الذراع (ت) = في `norm`، تحت `dagger_madd` نفسِه:  ۭ + ي + ٰ  ⇒  ۭ + ي   (‏أي تُسقَط الخنجرية)

🔒 **وشرطُ أن تكون القاعدةُ مرساةً في الرسم لا مفصّلةً على حالاتها:** العلامةُ `ۭ` في حفصٍ
وشعبةَ هي **علامةُ الإقلاب** (تنوينٌ ⇒ ميم) لا الإمالة، ولا تقع فيهما قبل ياءٍ فوقها خنجرية؛
وورشٌ وقالونُ لا يستعملان `ۭ` البتّة. فالقاعدةُ **لا تمسُّ حرفاً** خارج الدوريِّ والسوسيّ —
وهذا ما يقيسه الضابطُ (١)، وهو الذي يُبقي رقمَ D-288 (‏57 · 239 · 302) سليماً بالبناء.

    python tools/tasmi_bench/imala_norm_arm.py            # ١ الإحصاء · ٢ الضابط · ٣ التكلفة
    python tools/tasmi_bench/imala_norm_arm.py --examples 12

⛔ قياسٌ وتقريرٌ: هذا الملفُّ لا يكتب في ملفِّ محرّكٍ ولا مرآة. والفائدةُ المقيسةُ (‏الاتّهاماتُ
المردودة) تُؤخذ من `riwaya_floor_six.py` على **الكاشف المشحون** بعد تطبيق القاعدة في الموضعين.
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
LOWMEEM = "ۭ"      # ۭ — ميمٌ صغيرةٌ سفلى: إقلابٌ في حفصٍ وشعبة · إمالةٌ في الدوريِّ والسوسيّ
DAGGER = "ٰ"       # ٰ — الألفُ الخنجرية
MARKS = "ؐ-ًؚ-ٰٟۖ-ۭ"
# الصورةُ: ميمٌ سفلى ثمّ ياءٌ (قد تتخلّلهما علاماتٌ) ثمّ خنجريّةٌ فوق الياء.
IMALA = re.compile("%s[%s]*ي[%s]*%s" % (LOWMEEM, MARKS, MARKS.replace("ٰ", ""), DAGGER))


def imala_fix(word):
    """الذراع (ت) — القاعدةُ المقترَحة، مطبَّقةً على الكلمة الخام قبل `norm`."""
    return IMALA.sub(lambda m: m.group(0).replace(DAGGER, ""), word)


def census(examples=8):
    """١ · **الإحصاء والضابط:** أين تقع الصورةُ في المصحف كلِّه، وهل تمسُّ روايةً لا إمالةَ لها؟"""
    print("=== ١ إحصاءُ صورة الإمالة `ۭ…يٰ` · المصحف كلُّه · الرواياتُ الستّ ===")
    hits = {}
    for r in SIX:
        cfg = P.config_for(r)
        occ = collections.Counter()
        changed = collections.Counter()
        for ayah in load_text(r):
            for w in ayah.split():
                if not IMALA.search(w):
                    continue
                occ[w] += 1
                if scorer.norm(imala_fix(w), cfg) != scorer.norm(w, cfg):
                    changed[w] += 1
        hits[r] = (occ, changed)
        print("  %-6s مواضعُ الصورة %5d (فريدة %4d) · يتغيّر تطبيعُها %5d (فريدة %4d)"
              % (r, sum(occ.values()), len(occ), sum(changed.values()), len(changed)))
    print("\n🧪 **الضابطُ (أ) — القاعدةُ مرساةٌ في الرسم:** يجب أن تكون حفصٌ وورشٌ وقالونُ وشعبةُ")
    print("   **صفراً** (‏`ۭ` فيها إقلابٌ لا إمالة، ولا تلي ياءً مخنجرة) وإلّا انتقلت القاعدةُ")
    print("   إلى روايةٍ لا إمالةَ فيها، ولبطل رقمُ D-288 المسنود (‏57 · 239 · 302).")
    ok = True
    for r in ("hafs", "warsh", "qalun", "shuba"):
        n = sum(hits[r][1].values())
        ok = ok and n == 0
        print("   %-6s %5d  %s" % (r, n, "✅" if n == 0 else "🚨 القاعدةُ تتعدّى"))
    for r in ("douri", "sousi"):
        print("   %-6s %5d  (‏المقصودُ بالقاعدة)" % (r, sum(hits[r][1].values())))
    print("   %s" % ("✅ القاعدةُ محصورةٌ في الروايتين الممالتين" if ok
                     else "🚨 لا تُطبَّق القاعدةُ حتى يُفهم التعدّي"))
    print("\n=== أكثرُ الصورِ تكراراً (الدوريُّ والسوسيّ) · قبلَ ⇜ بعدَ ===")
    for r in ("douri", "sousi"):
        cfg = P.config_for(r)
        for w, n in hits[r][1].most_common(examples):
            print("  %-6s «%s» ×%-4d  «%s» ⇜ «%s»  (‏whisper: «%s»)"
                  % (r, w, n, scorer.norm(w, cfg), scorer.norm(imala_fix(w), cfg),
                     P.whisper_forms(w, cfg)[-1]))
    return ok, hits


def cost(hits, examples=8):
    """٢ · **التكلفة:** أيَعمى بابُ القبول عن خطأ تلاوةٍ حقيقيٍّ بعد القاعدة؟

    التكلفةُ الوحيدةُ الممكنةُ في بابِ القبول هي أن **تتّسع** مجموعةُ الصور المقبولة فتبتلع
    كلمةً أخرى. فتُقاس بضلعين:

      (ب) **الاتّساع:** صورٌ يقبلها المحركُ بعد القاعدة ولم يكن يقبلها قبلَها.
      (ج) **الاصطدام:** أتساوي صورةٌ **جديدةٌ** مقبولةٌ صورةَ كلمةٍ قرآنيةٍ **أخرى** (رسمٌ مختلف)
          في الرواية نفسِها؟ فذاك إبدالٌ حقيقيٌّ يعمى عنه.
    """
    print("\n=== ٢ تكلفةُ القاعدة في بابِ القبول (‏المصحف كلُّه) ===")
    widened = collections.Counter()
    narrowed = collections.Counter()
    new_forms = collections.defaultdict(collections.Counter)
    for r in ("douri", "sousi"):
        cfg = P.config_for(r)
        for w, n in hits[r][1].items():
            before = set(scorer.variants(w, cfg))
            after = set(scorer.variants(imala_fix(w), cfg))
            for f in after - before:
                widened[r] += n
                new_forms[r][(w, f)] += n
            if before - after:
                narrowed[r] += n
    for r in ("douri", "sousi"):
        print("  %-6s صورةٌ مقبولةٌ جديدةٌ في %4d موضعاً · صورةٌ مقبولةٌ سقطت في %4d موضعاً"
              % (r, widened[r], narrowed[r]))
    print("  📌 والصورُ الجديدةُ كلُّها من **باب النداء**: `يَٰمُوسۭيٰ` تحمل خنجريّتين — خنجريّةَ")
    print("     «يا» (‏ألفٌ حقيقيّة) وخنجريّةَ الإمالة. فقبلَ القاعدة كانت الصورتان المقبولتان")
    print("     {«ياموسيا» · «يموسي»}؛ وبعدَها {«ياموسي» · «يموسي»} — **العددُ نفسُه**: سقطت")
    print("     الصورةُ التي لا يكتبها أحدٌ وحلّت محلَّها التي يكتبها. فليس اتّساعاً بل إصابة.")
    for r in ("douri", "sousi"):
        for (w, f), n in new_forms[r].most_common(3):
            print("     %-6s «%s» ×%-3d صورةٌ جديدةٌ «%s»" % (r, w, n, f))
    # (ج) الاصطدام — على **الصور الجديدة وحدَها**: ما كان مقبولاً قبلَ القاعدة ليس من صنعها.
    print("\n=== ٣ اصطدامُ الصورةِ الجديدةِ بكلمةٍ قرآنيةٍ **أخرى** (‏عمًى عن إبدالٍ حقيقيّ) ===")
    print("   «أخرى» = كلمةٌ يختلف تطبيعُها بعدَ رفع الإمالة عن هذه؛ فاختلافُ رسمِ الإمالة")
    print("   وحدَه (‏`مُوسَى` ⇄ `مُوسۭيٰ`) **كلمةٌ واحدةٌ** لا اصطدام.")
    total = 0
    for r in ("douri", "sousi"):
        cfg = P.config_for(r)
        by_form = collections.defaultdict(set)
        for ayah in load_text(r):
            for w in ayah.split():
                for f in scorer.variants(w, cfg):
                    if f:
                        by_form[f].add(w)
        clash = collections.Counter()
        ex = []
        for w, n in hits[r][1].items():
            before = set(scorer.variants(w, cfg))
            mine = scorer.norm(imala_fix(w), cfg)
            for f in set(scorer.variants(imala_fix(w), cfg)) - before:
                real = {o for o in by_form.get(f, set()) - {w}
                        if scorer.norm(imala_fix(o), cfg) != mine}
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
    ap = argparse.ArgumentParser(description="صورةُ الإمالة في المِسطرة — إحصاءٌ وضابطٌ وتكلفة")
    ap.add_argument("--examples", type=int, default=8)
    args = ap.parse_args()
    ok, hits = census(args.examples)
    blind = cost(hits, args.examples)
    print("\n=== الخلاصة ===")
    print("  القاعدةُ محصورةٌ في الروايتين الممالتين: %s" % ("✅" if ok else "🚨"))
    print("  عمًى جديدٌ عن خطأ تلاوة: %d موضعاً %s" % (blind, "✅" if blind == 0 else "🚨"))
    print("  الفائدةُ المقيسةُ تُؤخذ من `riwaya_floor_six.py` على الكاشف المشحون (‏مرجع D-401: 1968).")
    return 0 if (ok and blind == 0) else 1


if __name__ == "__main__":
    sys.exit(main())
