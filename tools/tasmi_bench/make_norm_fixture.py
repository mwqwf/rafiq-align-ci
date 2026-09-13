# -*- coding: utf-8 -*-
"""يولّد **بصمةَ تماثلٍ للتطبيع وحدَه** من نصّ المصحف — بلا صوتٍ ولا شبكة.

لماذا ملفٌّ ثانٍ بجوار `make_parity_fixture.py`؟ لأنّ الأولى تُولَّد من **مخرَج
whisper** على عيّنة G1 (`work/hyps_ar.json`)، فما لم تنطق به العيّنةُ لا يدخلها.
وقياسُ 2026-09-12 (‏D-320) كشف أنّ حالاتِها الـ214 فيها `ىٰ` 57 و`ے` 60 و`ٱ` 123
و`اٰ` **صفراً** ⇒ حذفُ قاعدة D-275 من `RecitationScorer.norm` **يمرّ خضراءَ**.
أي أنّ حارسَ التماثل يحمي بعضَ قواعد المِسطرة ويترك بعضَها مكشوفاً — والمكشوفُ
لا يُعرف إلا بالعدّ. وهذه الأداةُ تسدُّ الثغرة: مصدرُها نصُّ المصحف كلُّه
(‏18,708 آيةً في ثلاث روايات) فتصل إلى كلِّ قاعدةٍ في `norm`/`variants`.

**وكلُّ حالةٍ هنا حمّالة:** لا تُقبل كلمةٌ لقاعدةٍ إلا إذا كان **إلغاءُ تلك
القاعدة وحدَها يغيّر مخرَجَها** (‏`ablate` أدناه). فالبصمةُ ليست شاهدةً على أنّ
القاعدة موجودة بل على أنّها **عاملة**: من حذفها سقط اختبارُه.

    python tools/tasmi_bench/make_norm_fixture.py

المخرَج: `engine/recitation/src/test/resources/norm_fixture.tsv`
ويقرؤه `RecitationNormParityTest` فيعيد تشغيل `RecitationScorer.norm`/`variants`
الحقيقيَّين عليه ويطابق حرفاً بحرف، **ويسقط كذلك إن غابت قاعدةٌ مطلوبة** عن
البصمة (‏حارسُ التغطية) فلا تُفرَّغ البصمةُ من قاعدةٍ بلا صياح.
"""
import collections
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "tools", "alignment"))
import scorer  # noqa: E402
from common import load_text  # noqa: E402

OUT = os.path.join(ROOT, "engine", "recitation", "src", "test", "resources", "norm_fixture.tsv")
# 📐 **D-402 — البصمةُ على الرواياتِ الستّ لا الثلاث.** كانت ثلاثاً، فلمّا أُضيفت قاعدةُ
# صورةِ الإمالة (`ۭيٰ ⇒ ۭي`) — ومواضعُها كلُّها في الدوريِّ والسوسيّ — لم يكن لها **شاهدٌ واحدٌ**
# في البصمة: قاعدةٌ حيّةٌ في المِسطرة يمرُّ حذفُها أخضرَ. والستُّ لها نصٌّ كاملٌ في أصول
# المستودع، فالحدُّ كان حدَّ أداةٍ لا بيانات (وهو درسُ D-401 بعينِه).
RIWAYAT = ("hafs", "warsh", "qalun", "shuba", "douri", "sousi")
PER_BUCKET = 6  # حدُّ الحالات لكلِّ (قاعدة × رواية) — البصمةُ شاهدةٌ لا مستودع

# إعدادُ المرآة = **المشحون حرفاً بحرف** (كما في make_parity_fixture.py).
CFG = {r: scorer.Config(strip_yeh_barree=True, dagger_optional=True, naql=r == "warsh",
                        sila=r in ("warsh", "qalun"), mark_sila=True) for r in RIWAYAT}


def norm_ablated(word, off=None):
    """`scorer.norm` نفسُها خطوةً خطوة مع إمكان **إطفاء قاعدةٍ واحدة**.

    `off=None` ⇒ المشحون بالضبط (‏يُتحقَّق منه في `main` على كلِّ كلمةٍ تُفحَص:
    لو انحرفت هذه النسخةُ عن `scorer.norm` لخرج المولّدُ صارخاً، فلا تُبنى
    البصمةُ على مِسطرةٍ ثانيةٍ تتسلّل).
    """
    w = word
    if off != "dagger_yeh":
        w = w.replace("ىٰ", "ى")
    if off != "dagger_alif":
        w = w.replace("اٰ", "ا")
    if off != "dagger_imala":
        w = w.replace("ۭيٰ", "ۭي")
    if off != "dagger_imala_stop":
        w = w.replace("۪يٰ", "۪ي")
    if off != "dagger_imala_bare":
        w = scorer._BARE_IMALA.sub("ي", w)
    if off != "khanjariya":
        w = w.replace("ٰ", "ا")
    if off != "strip":
        w = scorer._STRIP.sub("", w)
    for a, b in scorer._SUBS + [("ے", "ي")]:
        if off == "sub:" + a:
            continue
        w = w.replace(a, b)
    if off != "non_arabic":
        w = scorer._NON_ARABIC.sub("", w)
    return w


# قواعدُ التطبيع — لكلٍّ اسمُها وإطفاؤها. الكلمةُ لا تدخل بُقعةَ قاعدةٍ إلا إن
# غيّر إطفاءُ تلك القاعدة وحدَها مخرَجَها.
NORM_RULES = [
    ("dagger_yeh", "dagger_yeh"),      # D-274: ىٰ ⇒ ى قبل ى⇒ي
    ("dagger_alif", "dagger_alif"),    # D-275: اٰ ⇒ ا (مدٌّ لا ألفٌ ثانية)
    ("dagger_imala", "dagger_imala"),  # D-402: ۭيٰ ⇒ ۭي (ألفُ الإمالة — الدوريُّ والسوسيّ)
    # D-403: ۪يٰ ⇒ ۪ي (علامةُ الإمالة الثانية — **ورشٌ** والدوريُّ والسوسيّ)
    ("dagger_imala_stop", "dagger_imala_stop"),
    # D-404: `يٰ` مجرّدةً (نظرةٌ خلفيّةٌ سالبةٌ على ۭ و۪) — **قالونُ وورش**
    ("dagger_imala_bare", "dagger_imala_bare"),
    ("khanjariya", "khanjariya"),      # الخنجريةُ ألفٌ تُنطق لا حركةٌ تُحذف
    ("strip_marks", "strip"),          # الحركاتُ وعلاماتُ الوقف والتطويل
    ("sub_wasla", "sub:ٱ"),
    ("sub_hamza_above", "sub:أ"),
    ("sub_hamza_below", "sub:إ"),
    ("sub_madda", "sub:آ"),
    ("sub_waw_hamza", "sub:ؤ"),
    ("sub_yeh_hamza", "sub:ئ"),
    ("sub_alif_maqsura", "sub:ى"),
    ("sub_teh_marbuta", "sub:ة"),
    ("sub_hamza", "sub:ء"),
    ("sub_yeh_barree", "sub:ے"),
    ("non_arabic", "non_arabic"),      # ما بقي خارج ء-ي بعد ما سبق
]

def forms(word, cfg):
    """صورُ الكلمة **كما يبنيها المحرك**.

    ⚠️ فرقٌ بنيويٌّ بين الطرفَين لا بدّ من ردمه هنا: الكوتلن يبني الصورَ كلَّها في
    `computeVariants` واحدةً (‏النقلُ وصلةُ الميم داخلَها)، وبايثون تقسمها
    `variants` ثم `_riwaya_forms` (تُنادى في `score`). فمقارنةُ `scorer.variants`
    وحدَها بـ`RecitationScorer.variants` تقارن نصفاً بكلٍّ — وتترك النقلَ وصلةَ
    الميم بلا حارسٍ أصلاً. الترتيبُ في الطرفَين واحد: [المطبَّع، بلا خنجرية،
    صلةُ ۦ، صلةُ ۥ] ثم لكلِّ صورةٍ نقلُها فصلةُ ميمها، ثم إسقاطُ المكرَّر.
    """
    return tuple(scorer._riwaya_forms(scorer.variants(word, cfg), cfg))


# ✍️ حالاتٌ مصنوعةٌ لقاعدةٍ **لا يبلغها رسمُ المصحف**: `NON_ARABIC` تُنقّي ما بقي
# خارج ء-ي، ولا يبقى في المصحف شيءٌ بعد `STRIP` (‏قُيس: صفرُ موضعٍ في 237,729 كلمة).
# لكنّها تعمل على **مخرَج whisper** (أرقامٌ لاتينيةٌ وحروفٌ أعجمية) ⇒ تُغطَّى صناعةً
# كي لا تبقى قاعدةٌ في المِسطرة بلا حارس.
SYNTH = [
    ("non_arabic", "hafs", "ابراهيم42"),
    ("non_arabic", "hafs", "قُلْ ok".replace(" ", "")),
    ("non_arabic", "warsh", "اَ۬لْحَمْدُ7"),
]

# قواعدُ الصور (‏variants) — تُكشف بأثرها لا بإطفائها: الصورةُ الزائدةُ دليلُها.
VAR_RULES = [
    # (‏الاسم، شرطٌ على (الكلمة، الصور، المطبَّع))
    ("var_dagger_optional", lambda w, v, n: "ٰ" in w and len(v) > 1 and v[1] != n),
    ("var_sila_yeh", lambda w, v, n: "ۦ" in w and (n + "ي") in v),
    ("var_sila_waw", lambda w, v, n: "ۥ" in w and (n + "و") in v),
    ("var_naql", lambda w, v, n: any(f == n[1:] for f in v) and n.startswith("ال") and len(n) > 3),
    ("var_naql_hamza_seat", lambda w, v, n: n.startswith("الا") and len(n) > 4 and ("ل" + n[3:]) in v),
    ("var_sila_meem", lambda w, v, n: n.endswith(("هم", "كم", "تم")) and (n + "وا") in v),
]


def main():
    buckets = collections.defaultdict(collections.Counter)   # (قاعدة، رواية) ⇒ عدّادُ الكلمات
    totals = collections.Counter()                           # (قاعدة، رواية) ⇒ مواضعُها كلُّها
    checked = 0
    for riw in RIWAYAT:
        cfg = CFG[riw]
        for ayah in load_text(riw):
            for word in ayah.split():
                n = norm_ablated(word)
                checked += 1
                # ⛔ ضبطٌ على المولّد نفسِه: نسختُه من المِسطرة = المِسطرةُ أو نتوقّف.
                if n != scorer.norm(word, cfg):
                    raise SystemExit(
                        "🚨 انحرفت نسخةُ المولّد عن scorer.norm عند «%s»: %r ≠ %r"
                        % (word, n, scorer.norm(word, cfg)))
                for name, off in NORM_RULES:
                    if norm_ablated(word, off) != n:
                        buckets[(name, riw)][word] += 1
                        totals[(name, riw)] += 1
                v = list(forms(word, cfg))
                for name, cond in VAR_RULES:
                    if cond(word, v, n):
                        buckets[(name, riw)][word] += 1
                        totals[(name, riw)] += 1

    rows = [(n, r, w, norm_ablated(w), " ".join(forms(w, CFG[r]))) for n, r, w in SYNTH]
    for name, _ in NORM_RULES + [(n, None) for n, _ in VAR_RULES]:
        for riw in RIWAYAT:
            words = buckets.get((name, riw))
            if not words:
                continue
            # اختيارٌ حتميّ: الأكثرُ وروداً، وعند التساوي ترتيبُ الحرف.
            for word, _c in sorted(words.items(), key=lambda kv: (-kv[1], kv[0]))[:PER_BUCKET]:
                rows.append((name, riw, word, norm_ablated(word),
                             " ".join(forms(word, CFG[riw]))))

    nl, tab = chr(10), chr(9)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline=nl) as f:
        f.write("# مولّد: tools/tasmi_bench/make_norm_fixture.py — لا يُحرَّر يدوياً" + nl)
        f.write("# مصدرُه نصُّ المصحف كلُّه (6,236 آية × 6 روايات)، لا مخرَجُ whisper." + nl)
        f.write("# كلُّ حالةٍ حمّالة: إطفاءُ قاعدتِها وحدَها يغيّر مخرَجَها." + nl)
        for name, _ in NORM_RULES + [(n, None) for n, _ in VAR_RULES]:
            per = " · ".join("%s %d" % (r, totals.get((name, r), 0)) for r in RIWAYAT)
            f.write("# مواضعُ %s: %s%s" % (name, per, nl))
        f.write(tab.join(["# rule", "riwaya", "word", "norm", "variants"]) + nl)
        for r in rows:
            f.write(tab.join(r) + nl)
    print("✅ %d حالة · %d قاعدة → %s (فُحصت %d كلمة)"
          % (len(rows), len({r[0] for r in rows}), OUT, checked))
    for name, _ in NORM_RULES + [(n, None) for n, _ in VAR_RULES]:
        per = {r: totals.get((name, r), 0) for r in RIWAYAT}
        mark = "⛔ لا حالةَ لها" if not sum(per.values()) else ""
        print("   %-22s %s %s" % (name, " · ".join("%s %5d" % (r, per[r]) for r in RIWAYAT), mark))


if __name__ == "__main__":
    main()
