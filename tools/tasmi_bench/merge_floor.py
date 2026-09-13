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
     ⚠️ وهذا الصنفُ **في حفصٍ وحدَه تقريباً**: رموزُ الوسط حفصاً 4,360 وفي الخمس
     الباقية 0–13 (‏نصوصُها بلا علامات وقفٍ وسطيّة) — فلا يُعمَّم رقمُ حفصٍ عليها.
  ٢) `مجاور · أدواتُ الالتحام` — لا رمزَ بينهما، والثانيةُ أداةٌ يُلحمها الإملاءُ
     (`ما · من · لا · لن · لو · هم · ها · ذا · ان · اذ`) ⇒ 6,271–6,275 موضعاً للرواية.
     وهو **سقفُ تعرّضٍ** لا دعوى: ليس كلُّ زوجٍ من هذه يكتبه الإملاءُ ملتحماً
     (`مِن قَبْلُ` لا تُلحَم)، لكنّ كلَّ ما يُلحَم داخلَه. فخضرتُه تُبرّئ ما فوقَها.

    python merge_floor.py                    # الصنفان · الرواياتُ الستّ (‏≈١٦ دقيقة)
    python merge_floor.py --riwaya hafs --klass via-symbol
    python merge_floor.py --sample 300       # فحصٌ سريع
    python merge_floor.py --prove            # ضابطٌ موجب: دمجٌ **ثلاثيّ** ⇒ يجب أن يسقط
"""
import argparse
import collections
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "../alignment")

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


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--riwaya", choices=RIWAYAT + ("all",), default="all")
    p.add_argument("--klass", choices=KLASSES + ("all",), default="all")
    p.add_argument("--sample", type=int, default=0)
    p.add_argument("--prove", action="store_true",
                   help="ضابطٌ موجب: دمجٌ ثلاثيٌّ — أرضيّةٌ خضراءُ هنا **فشلُ الضابط**")
    a = p.parse_args()
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
