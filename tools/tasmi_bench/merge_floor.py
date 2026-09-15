#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""🧲 أرضيّةُ الدمج — الوجهُ المقلوبُ لأرضيّة الفصل (‏D-408).

`ruler_floor.py` يقيس **الفصلَ**: كلمةٌ في الرسم موصولةٌ يكتبها الإملاءُ كلمتين
(‏ياءُ النداء `يَٰقَوْمِ` ⇒ «يا قوم»)، ومقرُّها `op 3` (مسموعتان = مرجعيّة).
وهذا الملفُّ يقيس **الدمجَ**: كلمتان في الرسم مفصولتان يكتبهما الإملاءُ كلمةً واحدة
(`مِن مَّا` ⇒ «مما» · `أَيْنَ مَا` ⇒ «أينما» · `أَن لَّا` ⇒ «ألا»)، ومقرُّها `op 4`
(مرجعيّتان = مسموعة). وهو بابُ البلاء الأرجح، لأنّ نموذجَ التفريغ **يدمج دائماً**:
لا كاتبَ يكتب «من ما»، وبابُ «المقطوع والموصول» في الرسم كلُّه ضدَّ الإملاء.

⚠️ والفرقُ الحاسم عن أرضيّات `ruler_floor.py` الثلاث: هذه الأرضيّةُ **تُقاس موضعاً
موضعاً** لا آيةً آيةً. لأنّ دمجَ عدّةِ مواضعَ في فرضيّةٍ واحدةٍ يُحرّك `_collapse_guard`
(‏نصفُ الكلمات تصير مدمجةً) فيُنتج سقوطاً كاذباً يُنسب إلى `op 4` وليس منه. ⇒ لكلِّ
موضعٍ فرضيّةٌ مستقلّةٌ لا دمجَ فيها غيرُه. وثمنُه أنّ المصحفَ كلَّه بكلِّ أزواجه
(‏≈71 ألف زوجٍ للرواية) يحتاج ≈٣ ساعاتٍ للستّ ⇒ فالمقيسُ صنفان محدودان مذكوران أدناه.

**الأصناف:**
  ١) `عبرَ رمز` — بين الكلمتين **رمزٌ منفصلٌ** يُطبَّع إلى فراغٍ (‏ۖ ۚ ۗ ۞ ۩).
     فثلاثُ كلماتٍ مرجعيّةٍ تقابل مسموعةً واحدة، و`op 4` لا يتعدّى **اثنتين**
     ⇒ يُنتظر سقوطُه. وهو الوجهُ المقلوبُ لعطب D-408 حرفاً بحرف: هناك انكسر
     الابتلاعُ لأنّ الفصلَ جعل المسموعَ اثنتين، وهنا لأنّ الدمجَ جعل المرجعَ ثلاثاً.
     ⚠️ وهذا الصنفُ **في حفصٍ وحدَه تقريباً**: مواضعُه حفصاً **4,361** وفي الخمس
     الباقية **0–13** (‏نصوصُها بلا علامات وقفٍ وسطيّة) — فلا يُعمَّم رقمُ حفصٍ عليها.
     (‏والرقمُ مواضعُ دمجٍ لا عددَ رموز: رمزان متتاليان موضعٌ واحد · جردٌ بـ`--census`.)
  ٢) `مجاور · أدواتُ الالتحام` — لا رمزَ بينهما، والثانيةُ أداةٌ يُلحمها الإملاءُ
     (`ما · من · لا · لن · لو · هم · ها · ذا · ان · اذ`) ⇒ **6,271–6,275 موضعاً في الخمس**،
     ⚠️ **وحفصٌ 5,778 وحدَه** (‏قِيس في D-603): رموزُ الوقف الوسطيّةُ **تقطع الجوار** فتُخرج
     الزوجَ من هذا الصنف إلى صنف «عبرَ رمز» ⇒ −493 موضعاً. فالمدى للخمس لا للستّ.
     وهو **سقفُ تعرّضٍ** لا دعوى: ليس كلُّ زوجٍ من هذه يكتبه الإملاءُ ملتحماً
     (`مِن قَبْلُ` لا تُلحَم)، لكنّ كلَّ ما يُلحَم داخلَه. فخضرتُه تُبرّئ ما فوقَها.

    python merge_floor.py                    # الصنفان · الرواياتُ الستّ (‏≈١٦ دقيقة)
    python merge_floor.py --riwaya hafs --klass via-symbol
    python merge_floor.py --sample 300       # فحصٌ سريع
    python merge_floor.py --prove            # ضابطٌ موجب: دمجٌ **ثلاثيّ** ⇒ يجب أن يسقط
"""
import argparse
import os
import io
import collections
import sys

# ⛔ كان المساران **نسبيَّين** فلا يعمل الملفُّ إلّا إن نودي من داخل مجلّده، وشوطُ
# `bench-selftest` ينادي من **جذر المستودع** (‏وهو عينُ عطب D-507 — ثاني ملفٍّ فيه).
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "tools", "alignment"))

import scorer  # noqa: E402
import detect_score  # noqa: E402
from common import load_text  # noqa: E402

RIWAYAT = ("hafs", "warsh", "qalun", "shuba", "douri", "sousi")

# أدواتٌ يُلحمها الإملاءُ الحديثُ بما قبلَها، بصورتها **بعد التطبيع** (‏بلا تشكيل):
# «مما · عما · أينما · كلما · إنما · ألا · ألن · حيثما · ربما · إذما · لكنما».
PARTICLES = ("ما", "من", "لا", "لن", "لو", "هم", "ها", "ذا", "ان", "اذ")

KLASSES = ("via-symbol", "adjacent-particle", "orthographic", "tajwid-idgham")

SHADDA = "ّ"

# 📖 **بابُ «المقطوعِ والموصول»** — الزوجُ مفصولٌ في رسم المصحف وملتحمٌ في الإملاء الحديث.
# مفتاحُ الجدول صورتا الكلمتين **بعد التطبيع**، وقيمتُه الصورةُ الملتحمةُ **بعد التطبيع** أيضاً.
# وكلُّ سطرٍ له شاهدٌ في نصِّ المستودع، فلا سطرَ بلا موضع (‏الأعدادُ مطبوعةٌ في D-409).
# ⚠️ **وحدُّ التحقّق:** المتحقَّقُ من النصِّ **شقُّ الرسم** وحدَه (‏أنّ الزوجَ مفصولٌ وعددُ
#    مواضعِه). وشقُّ الإملاء — أنّ الكاتبَ المعاصرَ يُلحمه — من البابِ المعروف ولم يُتحقَّق
#    بمصدرٍ (‏المناوبةُ بلا شبكة). وأوهنُها `أن+لو`: الإملاءُ الشائعُ يُبقيها مفصولةً في
#    الغالب ⇒ إن أُسقطت فالسقوطُ 25 لا 28. ومن شكّ في سطرٍ فليحذفه ويُعِدِ القياس: الفرزُ
#    (‏وصلٌ محضٌ يصمد · إدغامٌ يسقط) لا يتعلّق بسطرٍ بعينه.
# ⛔ ولا يُزاد فيه سطرٌ بالحَدْس: ما لم يُعلم أنّ الإملاءَ يُلحمه يُترك لسقف `tajwid-idgham`.
ORTHOGRAPHIC = {
    ("ان", "لا"): "الا",     # `أَن لَّا` ⇒ «ألّا»
    ("ان", "لن"): "الن",     # `أَن لَّن` ⇒ «ألّن»
    ("ان", "لو"): "الو",     # `أَن لَّوْ` ⇒ «ألّو»
    ("عن", "ما"): "عما",     # `عَن مَّا` ⇒ «عمّا»
    ("ام", "من"): "امن",     # `أَم مَّن` ⇒ «أمّن»
    ("اين", "ما"): "اينما",  # `أَيْنَ مَا` ⇒ «أينما»
    ("كل", "ما"): "كلما",    # `كُلَّ مَا` ⇒ «كلّما»
    ("في", "ما"): "فيما",    # `فِى مَا` ⇒ «فيما»
    ("كي", "لا"): "كيلا",    # `كَىْ لَا` ⇒ «كيلا»
    ("ان", "ما"): "انما",    # `إِنَّ مَا` ⇒ «إنّما»
}


def _tajwid_idgham(b_raw, na, nb):
    """أيُدغمُ الزوجُ **في التلاوة**؟ علامتُه في الرسم: شدّةٌ على أوّل الثانية.

    ⚠️ **وهذا صوتٌ لا إملاء** — وهو الفرقُ الذي كاد يُخطئه القياس. `غَفُورٌ رَّحِيمٌ` يُتلى
    مدغماً («غفورحيم») ولا يكتبه كاتبٌ كذلك البتّة. فالصنفُ هذا **سقفُ تعرّضٍ على جانب
    الصوت**: إن كتب نموذجُ التفريغ ما سمعه مدغماً فهذا مداه، وهل يكتبه **سؤالٌ ينتظر
    الصوتَ** ولا يُحسم على المرآة. وبابُ الإملاء المحقَّقُ هو `orthographic` وحدَه.
    """
    if len(na) < 2 or not nb:
        return False
    if SHADDA not in b_raw[:3]:
        return False
    return na[-1] in "نم" or na[-1] == nb[0]


def _sites(ref, n, klass):
    """مواضعُ الدمج: (i, j) فهرسا كلمتين مرجعيّتين متلاحقتين في **تيّار المسموع**."""
    idx = [i for i, x in enumerate(n) if x]
    out = []
    for k in range(len(idx) - 1):
        i, j = idx[k], idx[k + 1]
        gap = j - i - 1
        if klass == "via-symbol":
            if gap > 0:
                out.append((i, j))
        elif klass == "orthographic":
            if gap == 0 and (n[i], n[j]) in ORTHOGRAPHIC:
                out.append((i, j))
        elif klass == "tajwid-idgham":
            if gap == 0 and _tajwid_idgham(ref[j], n[i], n[j]):
                out.append((i, j))
        elif gap == 0 and n[j] in PARTICLES:
            out.append((i, j))
    return out


def _hyp_merge(n, i, j, mode="concat"):
    """المسموعُ = تطبيعُ المرجع، إلّا الموضعَ (i, j) فكلمةٌ واحدةٌ ملتحمة.

    ثلاثُ صورٍ للالتحام، وفرقُها هو بيتُ الدّاء:
      `concat`      — وصلٌ محضٌ `a + b` (وهو **بعينه** ما يجرّبه `op 4`).
      `orthographic`— الصورةُ التي يكتبها الإملاءُ من الجدول (`أن`+`لا` ⇒ «الا» لا «انلا»).
      `idgham`      — يُحذف آخرُ حرفٍ من الأولى كما يُسقطه الإدغامُ في التلاوة.
    والأخيرتان **لا يبلغهما `op 4` بحالٍ**، لأنّ `joined` عنده وصلٌ محضٌ لا إدغامَ فيه
    ولا حذف. فخضرةُ `concat` لا تشهد لهما بشيء.
    """
    if mode == "orthographic":
        merged = ORTHOGRAPHIC[(n[i], n[j])]
    elif mode == "idgham":
        merged = n[i][:-1] + n[j]
    else:
        merged = n[i] + n[j]
    out = []
    for k, x in enumerate(n):
        if not x or k == j:
            continue
        out.append(merged if k == i else x)
    return " ".join(out)


def _hyp_merge3(n, idx3):
    """ضابطٌ موجب: ثلاثُ مسموعاتٍ في واحدة — `op 4` لا يتعدّى اثنتين ⇒ يجب أن يسقط."""
    a, b, c = idx3
    out = []
    for k, x in enumerate(n):
        if not x or k in (b, c):
            continue
        out.append(n[a] + n[b] + n[c] if k == a else x)
    return " ".join(out)


def run(riwaya, klass, sample=0, prove=False):
    cfg = detect_score.cfg_for(riwaya)
    text = load_text(riwaya)
    if sample:
        step = max(1, len(text) // sample)
        text = text[::step][:sample]
    sites = bad = 0
    bad_kinds = collections.Counter()
    ex = {}
    for v, ayah in enumerate(text):
        ref = ayah.split()
        if not ref:
            continue
        n = [scorer.norm(w, cfg) for w in ref]
        if prove:
            nz = [i for i, x in enumerate(n) if x]
            cand = [tuple(nz[k:k + 3]) for k in range(0, len(nz) - 2, 3)][:1]
            hyps = [(t[0], t[-1], _hyp_merge3(n, t)) for t in cand]
        else:
            mode = ("orthographic" if klass == "orthographic"
                    else "idgham" if klass == "tajwid-idgham" else "concat")
            hyps = [(i, j, _hyp_merge(n, i, j, mode)) for i, j in _sites(ref, n, klass)]
        for i, j, hyp in hyps:
            sites += 1
            s = scorer.score(ref, hyp, cfg)
            miss = [w for w in s["words"] if w[1] != scorer.CORRECT]
            if not miss:
                continue
            bad += 1
            # الكلمةُ المتّهمةُ ظلماً: أهي داخلَ موضع الدمج أم جارتُها أم الرمزُ بينهما؟
            for w in miss:
                where = ("داخلَ الدمج" if w[0] in (i, j)
                         else "الرمزُ بينهما" if i < w[0] < j
                         else "جارةٌ خارجَه")
                kind = (where, w[1], scorer.norm(ref[w[0]], cfg) or "«فراغ»")
                bad_kinds[kind] += 1
                ex.setdefault(kind, (v, ref[i], ref[j], n[i] + n[j]))
    return dict(sites=sites, bad=bad, kinds=bad_kinds.most_common(8), ex=ex)


def census():
    """جردُ المواضع لكلِّ رواية — بلا حكمٍ ولا مِسطرة (‏ثوانٍ). يردّ {رواية: (رمز, أداة, جدول)}."""
    import parity_full as P
    from common import load_text
    out = {}
    for riw in RIWAYAT:
        cfg = P.config_for(riw)
        sym = adj = orth = 0
        for a in load_text(riw):
            ref = a.split()
            n = [scorer.norm(w, cfg) for w in ref]
            sym += len(_sites(ref, n, "via-symbol"))
            adj += len(_sites(ref, n, "adjacent-particle"))
            orth += len(_sites(ref, n, "orthographic"))
        out[riw] = (sym, adj, orth)
    return out


def table_witnesses(riwaya="hafs"):
    """شواهدُ كلِّ سطرٍ من جدول «المقطوع والموصول» في النصّ — ⛔ **وسطرٌ بلا شاهدٍ قاعدةٌ
    عن لا شيء**، وهو نصُّ ما يدّعيه متنُ الجدول («كلُّ سطرٍ له شاهدٌ في نصِّ المستودع»)."""
    import parity_full as P
    from common import load_text
    cfg = P.config_for(riwaya)
    per = collections.Counter()
    for a in load_text(riwaya):
        ref = a.split()
        n = [scorer.norm(w, cfg) for w in ref]
        for i, j in _sites(ref, n, "orthographic"):
            per[(n[i], n[j])] += 1
    return per


def selftest():
    """🧪 **حارسُ أرضيّة الدمج** (‏D-603) — والأرضيّةُ نفسُها **ثقيلةٌ** (≈16 دقيقةً للستّ)
    فلا تُشعَل في كلّ دفعة؛ وهذا يفحص في ثوانٍ ما لا يفحصه شوطُها:

    ⭐⭐ **كلُّ سطرٍ في جدول «المقطوعِ والموصول» له شاهدٌ في المصحف** — ادّعاءٌ في متن
      الجدول لم يكن مقيساً. المقيسُ (حفص): **52 موضعاً**، وأقلُّ سطرٍ **1** (‏`عن+ما` ·
      `كي+لا` · `ان+ما`) ⇒ لا سطرَ بلا شاهد. **وقاعدةٌ عن لا شيءٍ أسوأُ من قاعدةٍ خاطئة.**
    ⭐⭐ **وصورةُ الجدول ليست الوصلَ المحض** في أيِّ سطر — ولو كانت، لبلغَها `op 4` أصلاً
      ولم يكن للسطر معنى (‏وهو لبُّ D-409 كلِّه).
    ⚠️ **وحدٌّ في التوثيق صُحّح بالقياس:** «6,271–6,275 موضعاً للرواية» في صنف الجوار
      **لا يشمل حفصاً**: حفصٌ **5,778** — لأنّ رموزَ الوقف الوسطيّة (4,361 فجوةً) **تقطع
      الجوار** فتُخرج الزوجَ من الصنف. ⇒ فالمدى **للخمس**، وحفصٌ أقلُّ بـ497 موضعاً،
      **والسببُ هو الرمزُ نفسُه** الذي قِيس في D-412 وحُرس في D-507.
    """
    ok = True

    def say(good, line):
        nonlocal ok
        ok &= bool(good)
        print(("✅ " if good else "❌ ") + line)

    # ①⭐⭐ لا سطرَ في الجدول بلا شاهدٍ في المصحف
    per = table_witnesses("hafs")
    missing = [k for k in ORTHOGRAPHIC if per[k] == 0]
    say(len(ORTHOGRAPHIC) == 10 and not missing and sum(per.values()) == 52,
        "⭐⭐ جدولُ «المقطوع والموصول» %d أسطر · شواهدُها %d موضعاً · بلا شاهدٍ: %s"
        % (len(ORTHOGRAPHIC), sum(per.values()), missing or "لا شيء"))
    say(min(per[k] for k in ORTHOGRAPHIC) >= 1,
        "وأقلُّ سطرٍ شاهدٌ واحدٌ على الأقلّ (‏الأدنى %d)" % min(per[k] for k in ORTHOGRAPHIC))

    # ②⭐⭐ الجدولُ **صنفان بالبناء**، وهذا نصُّ حكم D-409 لا مصادفة:
    #    صورةٌ = وصلٌ محضٌ (يبلغها `op 4` فتصمد) · وصورةٌ مدغمةٌ (لا يبلغها فتسقط).
    plain = sorted(k for k, v in ORTHOGRAPHIC.items() if v == k[0] + k[1])
    idg = sorted(k for k, v in ORTHOGRAPHIC.items() if v != k[0] + k[1])
    say(len(plain) == 5 and len(idg) == 5,
        "⭐⭐ الجدولُ صنفان: **%d وصلٌ محضٌ** (يصمد) و**%d مدغمٌ** (يسقط) — وهو حكمُ D-409"
        % (len(plain), len(idg)))
    say(all(ORTHOGRAPHIC[k][0] == k[0][0] and len(ORTHOGRAPHIC[k]) < len(k[0] + k[1])
            for k in idg),
        "⭐ والمدغمُ أقصرُ من الوصل بحرفٍ (‏`ان`+`لا` ⇒ «الا» لا «انلا»): %s"
        % [ORTHOGRAPHIC[k] for k in idg])
    say({k[0] for k in idg} <= {"ان", "عن", "ام"},
        "وأوائلُ المدغم نونٌ أو ميمٌ ساكنةٌ في الرسم — لا عشوائيّةَ في الفرز")

    # ③ جردُ المواضع: المدى للخمس، وحفصٌ خارجَه بسبب الرمز
    cen = census()
    five = [cen[r][1] for r in RIWAYAT if r != "hafs"]
    say(cen["hafs"][0] > 4000 and max(cen[r][0] for r in RIWAYAT if r != "hafs") <= 13,
        "رمزٌ وسطيٌّ: حفص %d · وأقصى الخمس %d — فلا يُعمَّم رقمُ حفص"
        % (cen["hafs"][0], max(cen[r][0] for r in RIWAYAT if r != "hafs")))
    say(6271 <= min(five) and max(five) <= 6275 and cen["hafs"][1] < 6000,
        "⚠️ جوارُ الأداة: الخمسُ %d–%d **وحفصٌ %d** (‏الرمزُ يقطع الجوار ⇒ −%d)"
        % (min(five), max(five), cen["hafs"][1], min(five) - cen["hafs"][1]))
    say(all(cen[r][2] in (51, 52) for r in RIWAYAT),
        "والجدولُ 52 حفصاً/ورشاً/قالون و51 للدوريّ والسوسيّ: %s"
        % {r: cen[r][2] for r in RIWAYAT})

    # ④ `_sites` يفرز الأصناف بشرطها لا بالظنّ
    n = ["من", "", "ما", "كل", "ما", "قال"]
    ref = ["مِن", "ۖ", "مَّا", "كُلَّ", "مَا", "قَالَ"]
    say(_sites(ref, n, "via-symbol") == [(0, 2)], "عبرَ رمزٍ: فجوةٌ بين الكلمتين")
    adj = _sites(ref, n, "adjacent-particle")
    say(all(n[j] in PARTICLES and j - i == 1 for i, j in adj),
        "وجوارُ الأداة: لا فجوةَ والثانيةُ أداةٌ من القائمة (‏%s)" % (adj,))
    say(_sites(ref, n, "orthographic") == [(3, 4)],
        "والجدولُ: `كل`+`ما` وحدَها هنا (‏%s)" % (_sites(ref, n, "orthographic"),))

    # ⑤⭐ صورُ الالتحام الثلاث — والفرقُ بينها هو بيتُ الدّاء
    say(_hyp_merge(n, 3, 4, "orthographic") == "من ما كلما قال"
        and _hyp_merge(n, 3, 4, "concat") == "من ما كلما قال",
        "الوصلُ والجدولُ يتّفقان حين تكون الصورةُ نفسَها (‏`كل`+`ما`)")
    say(_hyp_merge(["ان", "لا", "خير"], 0, 1, "orthographic") == "الا خير"
        and _hyp_merge(["ان", "لا", "خير"], 0, 1, "concat") == "انلا خير"
        and _hyp_merge(["ان", "لا", "خير"], 0, 1, "idgham") == "الا خير",
        "⭐⭐ و`أن`+`لا`: الجدولُ «الا» والوصلُ «انلا» — **ولا يبلغ `op 4` الأولى بحال**")
    say(_hyp_merge3(["ا", "ب", "ج", "د"], (0, 1, 2)) == "ابج د",
        "وضابطُ الثلاثيّ يدمج ثلاثاً في واحدة")

    # ⑥ الإدغامُ صوتٌ لا إملاء — بشرطه المكتوب
    say(_tajwid_idgham("رَّحِيمٌ", "غفور", "رحيم"), "إدغامٌ: شدّةٌ على أوّل الثانية")
    say(not _tajwid_idgham("رحيم", "غفور", "رحيم"), "ولا إدغامَ بلا شدّةٍ في الرسم")
    say(not _tajwid_idgham("مَّا", "ا", "ما"), "ولا إدغامَ لأولى من حرفٍ واحد")

    # ⑦ حارسُ مصدرٍ على القاعدتين اللتين تمنعان توسيعَ الجدول بالحَدْس
    src = io.open(os.path.abspath(__file__), encoding="utf-8").read()
    say("ولا يُزاد فيه سطرٌ بالحَدْس" in src and "ومن شكّ في سطرٍ فليحذفه" in src,
        "⛔ وقاعدتا الجدول بالنصّ: لا زيادةَ بالحَدْس · ومَن شكّ فليحذف ويُعِد القياس")
    say("وهذا صوتٌ لا إملاء" in src,
        "⭐ والفرقُ المحفوظ: `tajwid-idgham` **صوتٌ** و`orthographic` **إملاءٌ محقَّق**")

    print("\n%s" % ("✅ حارسُ أرضيّة الدمج: تمّ" if ok else "❌ حارسُ أرضيّة الدمج: أخفق"))
    return 0 if ok else 1


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--selftest", action="store_true", help="🧪 حارسُ الأداة (ثوانٍ · بلا مِسطرة)")
    p.add_argument("--census", action="store_true", help="جردُ المواضع لكلِّ رواية بلا حكم")
    p.add_argument("--riwaya", choices=RIWAYAT + ("all",), default="all")
    p.add_argument("--klass", choices=KLASSES + ("all",), default="all")
    p.add_argument("--sample", type=int, default=0)
    p.add_argument("--prove", action="store_true",
                   help="ضابطٌ موجب: دمجٌ ثلاثيٌّ — أرضيّةٌ خضراءُ هنا **فشلُ الضابط**")
    a = p.parse_args()
    if a.selftest:
        return selftest()
    if a.census:
        for r, (sy, ad, orth) in census().items():
            print('%-7s رمزٌ وسطيّ %5d · جوارُ أداة %5d · جدولٌ %4d' % (r, sy, ad, orth))
        return 0
    riwayat = RIWAYAT if a.riwaya == "all" else (a.riwaya,)
    klasses = KLASSES if a.klass == "all" else (a.klass,)
    fail = 0
    for riw in riwayat:
        for kl in (("prove",) if a.prove else klasses):
            r = run(riw, kl, a.sample, a.prove)
            if not r["sites"]:
                print(f"— {riw} · {kl}: لا موضعَ (‏0) ⇒ لا يُقاس")
                continue
            pct = 100 * r["bad"] / r["sites"]
            mark = "✅" if r["bad"] == 0 else "🚨"
            print(f"{mark} {riw} · دمجٌ {kl}: مواضعُ تسقط {r['bad']}/{r['sites']} = {pct:.2f}٪")
            for k, c in r["kinds"]:
                v, wi, wj, joined = r["ex"][k]
                print(f"     ✗ {k[0]} · {k[1]} · {k[2]!r} ×{c} — الآية {v}: "
                      f"{wi!r} + {wj!r} ⇜ {joined!r}")
            if a.prove:
                if r["bad"] < r["sites"]:
                    print(f"     🚨 الضابطُ الموجب لم يُسقط {r['sites'] - r['bad']} موضعاً "
                          f"⇒ الأرضيّةُ لا تقيس")
                    fail += 1
            else:
                fail += r["bad"]
            sys.stdout.flush()
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
