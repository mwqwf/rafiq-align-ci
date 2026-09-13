#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""🩻 الرمزُ المنفصلُ في المِسطرة — كلمةٌ مرجعيّةٌ تُطبَّع إلى فراغ، ومَن يحرسها؟ (‏D-412)

**الدَّينُ الذي سلّمته D-411 نصّاً:** «ضعفُ المِسطرة عند الرمز المنفصل (‏٣٦:٥٢) عطبٌ قائمٌ
مستقلٌّ عن الإدغام ⇒ يستحقّ `D-41x` خاصّاً به وقياساً على المصحف كلِّه: كم موضعاً يضيع فيه
`op 4` بسبب رمزٍ مجاور؟ (‏لم يُقَس ⇒ لا يُدَّعى)». وهذا قياسُه.

## الآليّةُ التي يقيسها هذا الملفّ
`scorer.score` يُسقط الفراغَ من **المسموع** (`hyp = [... if w]`) ولا يُسقطه من **المرجع**.
فرمزُ الوقف (`ۚ` · `ۖ` · `ۗ` · `۞`) كلمةٌ مرجعيّةٌ قائمةٌ صورتُها `""`، ولا مسموعَ يطابق
الفراغَ ⇒ **حظُّها الطبيعيُّ `MISSED`**. وإنّما تخضرُّ اليومَ بقاعدة الدمج وحدَها
(`op 4`: مرجعيّتان = مسموعة، `joined = "" + B = B`) — فالرمزُ يركب جارَه.

⚠️ **وهذه خضرةٌ مستعارةٌ لا مملوكة.** `op 4` موردٌ **مُتنازَعٌ عليه**: هو نفسُه القاعدةُ
التي يحتاجها الإملاءُ حين يصل ما يفصله الرسمُ (`أَن لَّا` ⇒ «ألّا» · D-409)، وهو نفسُه
ما يحتاجه القارئُ السريعُ حين يلحم كلمتين. فإن طلبَه الرمزُ والإدغامُ معاً في موضعٍ واحد
سقط أحدُهما. ⇒ **أرضيّةُ `ruler_floor.py` البنيويّةُ الخضراءُ (0.000٪) تقيس حالةَ
«لا منازعَ»، فخضرتُها لا تشهد للرمز بشيءٍ عند المنازعة.**

## ما يُقاس (‏المصحفُ كلُّه · الرواياتُ الستّ · بلا شبكةٍ ولا عتاد)
- `--census`   إحصاءُ الكلمات المرجعيّة الفارغة ومَن يحرسها اليومَ (‏بإثبات أنّ الحارسَ `op 4`).
- `--collide`  المسحُ الشامل: يُلحَم في كلِّ آيةٍ **كلُّ زوجٍ مسموعٍ متجاور** على حدة
               (‏لا اختيارَ ولا عيّنة) ⇒ فيُفرز صنفا الضياع:
                 **أ) الجارُ الفاصل** — الرمزُ **بين** الملحومَين ⇒ `op 4` يطلب `ref[i]`
                    و`ref[i+1]` متجاورَين، والرمزُ يفصلهما ⇒ **الدمجُ مستحيلٌ بالبناء**.
                 **ب) الجارُ المزاحِم** — الرمزُ **يجاور** الملحومَين لا يتوسّطهما ⇒ نزاعٌ
                    على `op 4`، والـDP يشتري الأرخص.
- `--idgham`   الرقمُ الواقعيُّ لا الافتراضيّ: كم من مواضع «المقطوعِ والموصول» العشرة
               (‏جدولُ D-409 — وهي التي **يلحمها التفريغُ دائماً** لا احتمالاً) يجاورها رمزٌ؟
- `--fix`      الدواءُ المقترَح مقيساً: إسقاطُ الكلمات الفارغة من المرجع قبل المحاذاة
               (‏فلا تُحكَم ولا تنازع) مع ضابطَي تماثلٍ وكلفة. ⛔ **يُقاس ولا يُشحن**:
               `scorer.py` مرآةُ `RecitationScorer.kt`، والشحنُ قرارُ الجلسة المحلّية.

- `--denom`   الدَّينُ الثاني (‏D-413): الرمزُ **معدودٌ في المقام** (`total`) و`score.py` يجمع
               جمعاً مصغَّراً ⇒ فكم تنفخ الفارغاتُ الرقمَ الرسميَّ على عيّنة G1 نفسِها؟
- `--shard i/n` قسمةُ `--fix` على فهرس الآية (‏ضرورةٌ زمنيّةٌ لا منهجيّة: حفصٌ وحدَه 47,864
               التحاماً × حكمَين). العدّاداتُ مجاميعُ ⇒ جمعُ الأقسام = المسحُ كاملاً،
               وقد **ضُبط ذلك بشعبةَ**: القسمةُ الرباعيّةُ = الجريةُ الكاملةُ رقماً برقم.

    python blank_symbol_probe.py --census
    python blank_symbol_probe.py --collide --riwaya hafs
    python blank_symbol_probe.py --idgham
    python blank_symbol_probe.py --fix --riwaya hafs --shard 0/4
    python blank_symbol_probe.py --denom
    python blank_symbol_probe.py --all
"""
import argparse
import collections
import sys
import time

sys.path.insert(0, ".")
sys.path.insert(0, "../alignment")

import scorer  # noqa: E402
import detect_score  # noqa: E402
from common import load_text  # noqa: E402

RIWAYAT = ("hafs", "warsh", "qalun", "shuba", "douri", "sousi")

# جدولُ «المقطوعِ والموصول» كما حرّرته D-409: أزواجٌ يصلها الإملاءُ الحديثُ **بإدغام**،
# فصورةُ المسموع ليست `a + b` بل مدغمةٌ («ألّا» لا «انلا») ⇒ `op 4` لا يملكها أصلاً.
# تُكتب هنا بصورتها المطبَّعة (‏بلا تشكيل) كي تُطابَق على أيِّ روايةٍ بلا إعادةِ رسم.
IDGHAM_PAIRS = (
    ("ان", "لا"), ("ان", "لن"), ("ان", "لو"), ("ام", "من"), ("عن", "ما"),
    ("في", "ما"), ("اين", "ما"), ("كل", "ما"), ("ان", "ما"), ("كي", "لا"),
)


def _blank_flags(ref, cfg):
    return [scorer.norm(w, cfg) == "" for w in ref]


def _structural_hyp(ref, cfg):
    """المسموعُ المثاليّ: تطبيعُ المرجع، والفراغاتُ تسقط كما يُسقطها `score` من المسموع."""
    return [x for x in (scorer.norm(w, cfg) for w in ref) if x]


def _ref_index_of_hyp(ref, cfg):
    """خريطةُ «الكلمةُ المسموعةُ رقم k ⇦ الكلمةُ المرجعيّةُ رقم i» في المسموع المثاليّ."""
    return [i for i, w in enumerate(ref) if scorer.norm(w, cfg) != ""]


# ─────────────────────────── ١) الإحصاءُ ومَن يحرس ───────────────────────────

def census(riwayat, verbose=True):
    rows = []
    for riw in riwayat:
        cfg = detect_score.cfg_for(riw)
        text = load_text(riw)
        tok = blank = ayat = 0
        sym = collections.Counter()
        by_arm = collections.Counter()   # بأيِّ قاعدةٍ خضّر الرمزُ؟
        for a in text:
            ref = a.split()
            if not ref:
                continue
            tok += len(ref)
            flags = _blank_flags(ref, cfg)
            nb = sum(flags)
            if not nb:
                continue
            blank += nb
            ayat += 1
            for w, f in zip(ref, flags):
                if f:
                    sym[w] += 1
            s = scorer.score(ref, " ".join(_structural_hyp(ref, cfg)), cfg)
            for i, f in enumerate(flags):
                if not f:
                    continue
                v = s["words"][i]
                if v[1] != scorer.CORRECT:
                    by_arm["أحمر"] += 1
                    continue
                # 🔬 إثباتُ أنّ الحارسَ `op 4` لا غيرُه: القاعدةُ تُسند **نصَّ المسموعِ
                #    نفسَه** إلى الكلمتين i وi+1 (‏سطرا `words[pi] = … ; words[pi+1] = …`).
                nb_ = s["words"][i - 1] if i else None
                nx_ = s["words"][i + 1] if i + 1 < len(ref) else None
                if (nx_ and nx_[1] == scorer.CORRECT and nx_[2] == v[2]) or \
                   (nb_ and nb_[1] == scorer.CORRECT and nb_[2] == v[2]):
                    by_arm["op 4 (‏ركوبُ الجار)"] += 1
                else:
                    by_arm["أخضرُ بغيرِ الدمج"] += 1
        rows.append((riw, tok, blank, ayat, len(text), sym, by_arm))
        if verbose:
            print(f"  {riw:6s} كلماتٌ مرجعيّة {tok:6d} · **فارغةٌ {blank:5d}** "
                  f"({100 * blank / tok:5.2f}٪) في {ayat:5d}/{len(text)} آية "
                  f"({100 * ayat / len(text):4.1f}٪) · الحارس: {dict(by_arm)}")
            if riw == "hafs":
                print(f"         أشهرُها: {sym.most_common(8)}")
    return rows


# ─────────────────── ٢) المسحُ الشامل: أين يضيع `op 4`؟ ───────────────────

def collide(riwayat, limit=0, verbose=True):
    """يلحم **كلَّ زوجٍ مسموعٍ متجاور** في كلِّ آيةٍ فيها رمز، ويفرز الضياع صنفَين.

    الالتحامُ هنا **قدرةٌ مشحونةٌ في المِسطرة لا افتراضٌ خارجيّ**: `op 4` موجودٌ بعينِه
    ليغفر «مرجعيّتان = مسموعة». فإن سقط الرمزُ عند التحامٍ **يملك الحاكمُ غفرانَه**
    فالسقوطُ عطبٌ في المِسطرة لا في القارئ.
    """
    out = {}
    for riw in riwayat:
        cfg = detect_score.cfg_for(riw)
        text = load_text(riw)
        # ⚖️ الضابطُ الصفر: بلا التحامٍ يجب أن يخضرَّ الكلُّ (‏أرضيّةُ `ruler_floor` البنيويّة).
        base_red = 0
        cases = collections.Counter()
        red_blank = collections.Counter()
        red_real = collections.Counter()
        ex = {}
        seen = 0
        for n, a in enumerate(text):
            ref = a.split()
            if not ref:
                continue
            flags = _blank_flags(ref, cfg)
            if not any(flags):
                continue
            seen += 1
            if limit and seen > limit:
                break
            hyp = _structural_hyp(ref, cfg)
            ridx = _ref_index_of_hyp(ref, cfg)
            s0 = scorer.score(ref, " ".join(hyp), cfg)
            base_red += sum(1 for w in s0["words"] if w[1] != scorer.CORRECT)
            for k in range(len(hyp) - 1):
                merged = hyp[:k] + [hyp[k] + hyp[k + 1]] + hyp[k + 2:]
                i0, i1 = ridx[k], ridx[k + 1]
                # صنفُ الموضع: هل بين الملحومَين رمز؟ أم يجاورهما؟
                between = i1 - i0 > 1
                near = (i0 > 0 and flags[i0 - 1]) or (i1 + 1 < len(ref) and flags[i1 + 1])
                kind = "أ) الجارُ الفاصل" if between else ("ب) الجارُ المزاحِم" if near else "ج) بلا جوار")
                cases[kind] += 1
                s = scorer.score(ref, " ".join(merged), cfg)
                rb = [i for i, f in enumerate(flags) if f and s["words"][i][1] != scorer.CORRECT]
                rr = [i for i, f in enumerate(flags)
                      if not f and s["words"][i][1] != scorer.CORRECT]
                if rb:
                    red_blank[kind] += 1
                if rr:
                    red_real[kind] += 1
                if (rb or rr) and kind not in ex:
                    ex[kind] = (n + 1, ref[i0], ref[i1],
                                [ref[i] for i in rb], [ref[i] for i in rr])
        out[riw] = (cases, red_blank, red_real, base_red, ex, seen)
        if verbose:
            print(f"  {riw}: آياتٌ فيها رمز {seen} · **الضابطُ الصفر (‏بلا التحام): "
                  f"{base_red} أحمر** {'✅' if base_red == 0 else '🚨'}")
            for kind in ("أ) الجارُ الفاصل", "ب) الجارُ المزاحِم", "ج) بلا جوار"):
                c = cases[kind]
                if not c:
                    continue
                print(f"     {kind:18s} التحاماتٌ {c:6d} · **يسقط فيها الرمزُ "
                      f"{red_blank[kind]:5d} ({100 * red_blank[kind] / c:5.1f}٪)** · "
                      f"وتسقط كلمةٌ حقيقيّةٌ {red_real[kind]:5d} ({100 * red_real[kind] / c:5.1f}٪)")
            for kind, e in ex.items():
                print(f"     مثالُ {kind}: آيةٌ {e[0]} · «{e[1]} + {e[2]}» ⇒ "
                      f"رمزٌ أحمرُ {e[3]} · كلمةٌ حمراءُ {e[4]}")
    return out


# ───────────── ٣) الرقمُ الواقعيّ: الإدغامُ الذي يلحمه التفريغُ دائماً ─────────────

def idgham(riwayat, verbose=True):
    """كم من مواضع «المقطوعِ والموصول» يجاورها رمزٌ منفصل؟

    فرقُ هذا عن `--collide`: ذاك يقيس **الطاقةَ الكامنة** (‏أيُّ التحامٍ ممكن)، وهذا يقيس
    **الواقعَ المحتوم** — هذه الأزواجُ يصلها كلُّ كاتبٍ وكلُّ نموذجِ تفريغ، فجوارُ الرمز
    لها ليس احتمالاً بل موعدٌ مضروب.
    """
    out = {}
    for riw in riwayat:
        cfg = detect_score.cfg_for(riw)
        text = load_text(riw)
        tot = adj = between_c = 0
        by = collections.Counter()
        ex = []
        for n, a in enumerate(text):
            ref = a.split()
            if len(ref) < 2:
                continue
            flags = _blank_flags(ref, cfg)
            norms = [scorer.norm(w, cfg) for w in ref]
            for i in range(len(ref) - 1):
                if flags[i]:
                    continue
                # الزوجُ قد يفصله رمزٌ في الرسم ⇒ نأخذ التاليَ غيرَ الفارغ
                j = i + 1
                while j < len(ref) and flags[j]:
                    j += 1
                if j >= len(ref):
                    continue
                if (norms[i], norms[j]) not in IDGHAM_PAIRS:
                    continue
                tot += 1
                sep = j - i > 1
                near = (i > 0 and flags[i - 1]) or (j + 1 < len(ref) and flags[j + 1])
                if sep:
                    between_c += 1
                    by["أ) الرمزُ بينهما"] += 1
                elif near:
                    adj += 1
                    by["ب) الرمزُ يجاورهما"] += 1
                else:
                    by["ج) بلا رمز"] += 1
                if (sep or near) and len(ex) < 6:
                    ex.append((riw, n + 1, " ".join(ref[max(0, i - 1):j + 2])))
        out[riw] = (tot, between_c, adj, by, ex)
        if verbose:
            print(f"  {riw:6s} مواضعُ «المقطوعِ والموصول» {tot:4d} · "
                  f"**يجاورها رمزٌ {between_c + adj:3d} ({100 * (between_c + adj) / max(tot, 1):4.1f}٪)** "
                  f"⇦ {dict(by)}")
            for e in ex[:3]:
                print(f"         مثال: آيةٌ {e[1]} · «{e[2]}»")
    return out


# ──────────────── ٤) الدواءُ المقترَح مقيساً (‏ولا يُشحن) ────────────────

def _score_dropblank(ref, hyp_text, cfg):
    """المِسطرةُ نفسُها، إلّا أنّ الكلمةَ المرجعيّةَ الفارغةَ **تُسقَط قبل المحاذاة**.

    فلا تُحكَم (‏إذ لا نطقَ لها يُحاسَب عليه القارئ) ولا تنازع `op 4` على مورده.
    الأحكامُ تُعاد إلى فهارس المرجع الأصليّة، والفارغةُ تُوسَم `CORRECT` بالبناء.
    ⛔ نسخةٌ للقياس وحدَه: الشحنُ يقتضي المرآةَ في `RecitationScorer.kt` حرفاً بحرف.
    """
    keep = [i for i, w in enumerate(ref) if scorer.norm(w, cfg) != ""]
    s = scorer.score([ref[i] for i in keep], hyp_text, cfg)
    words = [None] * len(ref)
    for pos, i in enumerate(keep):
        v = s["words"][pos]
        words[i] = (i,) + tuple(v[1:])
    for i in range(len(ref)):
        if words[i] is None:
            words[i] = (i, scorer.CORRECT, None)
    return {"words": words, "additions": s["additions"],
            "correct": sum(1 for w in words if w[1] == scorer.CORRECT), "total": len(ref)}


def fix(riwayat, limit=0, verbose=True, shard=None, upto=0):
    """`shard=(i, n)` ⇒ لا يُعالَج إلّا ما كان `رقمُ الآية % n == i`.

    القسمةُ على فهرس الآية **لا على العمل**، فهي لا تغيّر حكماً ولا تُسقط حالة:
    كلُّ آيةٍ تُعالَج في قسمٍ واحدٍ لا غير، وجمعُ الأقسام = المسحُ كاملاً حرفاً بحرف
    (‏العدّاداتُ كلُّها مجاميعُ لا نِسَب ⇒ تُجمَع بلا وزن). القسمةُ ضرورةٌ زمنيّةٌ
    لا منهجيّة: حفصٌ وحدَه 47,864 التحاماً × حكمَين، وحدُّ المناوبة خمسون دقيقة.
    """
    for riw in riwayat:
        cfg = detect_score.cfg_for(riw)
        text = load_text(riw)
        par_ok = par_bad = 0          # ضابطُ التماثل: آياتٌ بلا رمزٍ ⇒ حكمٌ واحد
        gain_b = gain_r = loss = 0    # على الملتحمات
        cases = 0
        seen = 0
        for n, a in enumerate(text):
            # `--upto` يقصّ **مدخلَ** المسح لا عملَه ⇒ فهو مدخلٌ واحدٌ بعينه للجريةِ
            #   الكاملةِ ولأقسامها معاً، وبه يُضبَط تكافؤُ القسمة بكلفةٍ يحتملها الوقت.
            if upto and n >= upto:
                break
            if shard and n % shard[1] != shard[0]:
                continue
            ref = a.split()
            if not ref:
                continue
            flags = _blank_flags(ref, cfg)
            hyp = _structural_hyp(ref, cfg)
            if not any(flags):
                # ⚖️ الضابطُ صفر: حيث لا رمزَ، الدواءُ **لا يغيّر شيئاً** بالبناء —
                #    ويُختبر على مسموعٍ ملتحمٍ لا مثاليٍّ كي يمرّ بفروع الدمج فعلاً.
                if len(hyp) > 1:
                    m = [hyp[0] + hyp[1]] + hyp[2:]
                    t = " ".join(m)
                    if [w[1] for w in scorer.score(ref, t, cfg)["words"]] == \
                       [w[1] for w in _score_dropblank(ref, t, cfg)["words"]]:
                        par_ok += 1
                    else:
                        par_bad += 1
                continue
            seen += 1
            if limit and seen > limit:
                break
            for k in range(len(hyp) - 1):
                cases += 1
                t = " ".join(hyp[:k] + [hyp[k] + hyp[k + 1]] + hyp[k + 2:])
                old = scorer.score(ref, t, cfg)["words"]
                new = _score_dropblank(ref, t, cfg)["words"]
                ob = [i for i, f in enumerate(flags) if f and old[i][1] != scorer.CORRECT]
                nb = [i for i, f in enumerate(flags) if f and new[i][1] != scorer.CORRECT]
                orr = [i for i, f in enumerate(flags) if not f and old[i][1] != scorer.CORRECT]
                nr = [i for i, f in enumerate(flags) if not f and new[i][1] != scorer.CORRECT]
                if ob and not nb:
                    gain_b += 1
                if len(orr) > len(nr):
                    gain_r += 1
                if len(nr) > len(orr):
                    loss += 1
        if verbose:
            tot_par = par_ok + par_bad
            print(f"  {riw:6s} ⚖️ ضابطُ التماثل (‏آياتٌ بلا رمز): "
                  f"**{par_ok}/{tot_par}** {'✅' if par_bad == 0 else '🚨 ' + str(par_bad)}")
            print(f"         على {cases} التحاماً في آياتِ الرمز: "
                  f"**يُنقذ رمزاً في {gain_b} ({100 * gain_b / max(cases, 1):.1f}٪)** · "
                  f"ويُنقذ كلمةً حقيقيّةً في {gain_r} · "
                  f"**ويُضيّع في {loss}** {'✅' if loss == 0 else '🚨'}")
            # سطرٌ يُقرأ آليّاً كي تُجمَع الأقسام بلا نقلٍ يدويٍّ للأرقام
            print(f"SHARD\t{riw}\t{par_ok}\t{par_bad}\t{cases}\t{gain_b}\t{gain_r}\t{loss}")


# ───────── ٥) المقامُ المنتفخ: أهي «كلمات» تُقسَم عليها النسبةُ الرسميّة؟ ─────────

def denom(riwayat, verbose=True):
    """الدَّينُ الثاني من D-412: الرمزُ كلمةٌ مرجعيّةٌ **معدودةٌ في المقام** (`total`).

    و`score.py` يجمع جمعاً مصغَّراً (`accuracy = Σcorrect / Σtotal`) ⇒ فالتحويلُ
    **حسابيٌّ مضبوطٌ لا تقديريّ**: إن كانت الفارغاتُ `B` من `N` كلمةً وحُكم منها
    `g` صواباً، فالدقّةُ على **الكلام وحدَه** = `(p·N − g) / (N − B)`.

    ولأنّ عيّنةَ G1 تلاوةٌ متقنةٌ (‏المثاليُّ 100٪ تتبّعاً · `sample.py`) فالفارغاتُ
    تخضرُّ فيها بـ`op 4` حيث لا منازع ⇒ الحالةُ الواقعيّةُ `g = B`، وهي **أسوأُ**
    الحدَّين على الرقم المعلَن. ونحسب الحدَّين معاً فلا يُدَّعى ما لم يُقَس:
      · `g = B` (‏كلُّها خضراء) ⇒ أدنى دقّةٍ ممكنةٍ على الكلام.
      · `g = 0` (‏كلُّها حمراء) ⇒ أعلاها.
    ⛔ ولا يُقاس هنا `g` الفعليُّ: يقتضي ملفَّ `hyps` أي صوتاً ⇒ **ممنوعٌ شبكيّاً**.
    """
    import json
    import os
    ref_acc = {"hafs": 0.9817, "qalun": 0.9471, "warsh": 0.9021}   # المرآة · D-274
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sample.json")
    items = collections.defaultdict(list)
    try:
        for it in json.load(open(path, encoding="utf-8"))["items"]:
            # `refText` نصُّ العيّنة نفسُه لا فهرسٌ يُعاد حلُّه ⇒ لا وسيطَ يُخطئ
            items[it["riwaya"]].append(it["refText"])
    except Exception as e:                                    # noqa: BLE001
        print(f"  ⛔ تعذّرت قراءةُ العيّنة: {e!r}")
        return {}
    out = {}
    for riw in riwayat:
        cfg = detect_score.cfg_for(riw)
        pick = items.get(riw, [])
        n_tok = n_blank = 0
        for a in pick:
            ref = a.split()
            n_tok += len(ref)
            n_blank += sum(_blank_flags(ref, cfg))
        out[riw] = (len(pick), n_tok, n_blank)
        if not verbose:
            continue
        if not pick:
            print(f"  {riw:6s} ليست في عيّنة G1 ⇒ لا رقمَ رسميّاً يُصحَّح")
            continue
        share = 100 * n_blank / max(n_tok, 1)
        print(f"  {riw:6s} عيّنةُ G1: {len(pick):3d} آيةً · {n_tok:5d} كلمةً مرجعيّة · "
              f"**فارغةٌ {n_blank:4d} ({share:.2f}٪ من المقام)**")
        p = ref_acc.get(riw)
        if p is None or n_blank == 0:
            continue
        c = p * n_tok                                  # الصوابُ المعلَن (‏كلماتٍ)
        lo = (c - n_blank) / (n_tok - n_blank)         # g = B ⇒ أدنى دقّةٍ على الكلام
        # 🔬 حدٌّ **سفليٌّ مقيسٌ على `g` نفسِه**، يُستخرج من الرقم المعلَن وحدَه:
        #    الصوابُ على الكلام لا يتجاوز عددَ كلماته ⇒ `g ≥ c − (N − B)`. فإن خرج
        #    موجباً فقد **ثبت بالحساب** أنّ الفارغاتِ خضراءُ في القياس الرسميّ نفسِه،
        #    ولا يُحتاج إلى ملفِّ `hyps` لإثباته (‏وهو المعنى الذي يُنطِق حدَّ `g=0`
        #    بأكثرَ من 100٪ ⇒ فذلك الحدُّ **مستحيلٌ لا حدّ**).
        g_min = c - (n_tok - n_blank)
        hi = min(c, n_tok - n_blank) / (n_tok - n_blank)
        print(f"         الدقّةُ المعلَنة {100 * p:.2f}٪ ⇒ على الكلام وحدَه "
              f"**{100 * lo:.2f}٪** (‏الفارغاتُ خضراء) … {100 * hi:.2f}٪ "
              f"⇒ المدى **{100 * (p - lo):+.2f}** نقطة على الأكثر")
        if g_min > 0:
            print(f"         🔬 ويثبت بالحساب أنّ **{g_min:.0f} فارغةً على الأقلّ من "
                  f"{n_blank}** ({100 * g_min / n_blank:.0f}٪) حُكمت صواباً في القياس "
                  f"الرسميّ ⇒ فالحالةُ الواقعيّةُ هي الحدُّ الأدنى أو ما يقاربه")
        # ⭐ والصورةُ الدقيقةُ ليست «نقطةً تُطرَح» بل **نسبةٌ ثابتةٌ من الخطأ**:
        #    الفرقُ = B(1−p)/(N−B) ⇒ فالخطأُ المعلَن أصغرُ من الحقيقيّ بـ B/(N−B)
        #    **مهما بلغت الدقّة**. فالعيبُ لا يُرى عند 98٪ ويكبر حيث تسوء التلاوة.
        f = n_blank / (n_tok - n_blank)
        print(f"         ⭐ والصورةُ الثابتة: الخطأُ المعلَن أصغرُ من الحقيقيّ بـ"
              f"**{100 * f:.2f}٪ من نفسِه** مهما بلغت الدقّة "
              f"(‏{100 * (1 - p):.2f} ⇐ {100 * (1 - lo):.2f} نقطةَ خطأ) ⇒ "
              f"عند دقّةٍ 50٪ يصير الفرقُ {100 * f * 0.5:.2f} نقطة لا {100 * (p - lo):.2f}")
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--riwaya", default="")
    p.add_argument("--limit", type=int, default=0, help="حدُّ الآيات ذواتِ الرمز (‏للفحص السريع)")
    p.add_argument("--census", action="store_true")
    p.add_argument("--collide", action="store_true")
    p.add_argument("--idgham", action="store_true")
    p.add_argument("--fix", action="store_true")
    p.add_argument("--denom", action="store_true")
    # ⚠️ `%` في نصِّ المساعدة يُفسَّر تنسيقاً في argparse ⇒ يُضاعَف وإلّا سقطت `--help`
    p.add_argument("--shard", default="", help="«i/n» ⇒ قسمٌ من `--fix` (‏آيةٌ %% n == i)")
    p.add_argument("--upto", type=int, default=0, help="اقصر `--fix` على أوّل N آيةً (‏للضبط)")
    p.add_argument("--all", action="store_true")
    a = p.parse_args()
    riwayat = (a.riwaya,) if a.riwaya else RIWAYAT
    shard = None
    if a.shard:
        i, n = (int(x) for x in a.shard.split("/"))
        if not 0 <= i < n:
            p.error("‏--shard: يجب أن يكون 0 ≤ i < n")
        shard = (i, n)
    if not any((a.census, a.collide, a.idgham, a.fix, a.denom, a.all)):
        a.all = True
    t0 = time.time()
    if a.census or a.all:
        print("\n① إحصاءُ الكلمات المرجعيّة الفارغة ومَن يحرسها اليوم")
        census(riwayat)
    if a.collide or a.all:
        print("\n② المسحُ الشامل: كلُّ التحامٍ ممكنٍ في آياتِ الرمز")
        collide(riwayat, a.limit)
    if a.idgham or a.all:
        print("\n③ الرقمُ الواقعيّ: «المقطوعُ والموصول» وجوارُ الرمز")
        idgham(riwayat)
    if a.fix or a.all:
        print("\n④ الدواءُ المقترَح مقيساً (‏يُقاس ولا يُشحن)"
              + (f" · القسم {shard[0]}/{shard[1]}" if shard else ""))
        fix(riwayat, a.limit, shard=shard, upto=a.upto)
    if a.denom or a.all:
        print("\n⑤ المقامُ المنتفخ: كم من «كلمات» العيّنة ليست كلاماً؟")
        denom(riwayat)
    print(f"\n⏱️ {time.time() - t0:.1f} ثانية")


if __name__ == "__main__":
    main()
