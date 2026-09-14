# -*- coding: utf-8 -*-
"""🧲 **ذراعُ D-409: أيبلغُ `op 4` صورةَ الإدغام؟** — بلا صوت.

⚠️ **لِمَ وُجدت.** سلّم سجلُّ المناوبة (‏D-409) دَيناً نصّاً:

    «(١) **ذراعُ D-409 لم تُقَس** (‏نفد الوقت): أن يجرّب `op 4` صورةَ الإدغام إلى جانب
     الوصل المحض — ومزيّتُها أنّها **لا تزيح فهارسَ الكلمات** فلا تُثقَل بما أُثقلت به
     رقعةُ D-408؛ وثمنُها المجهولُ أثرُها على الاتّهام الكاذب في G3r ⇒ **تُقاس قبل أيِّ شحن**.»

وقاست D-409 العطبَ وحدَه: جدولُ «المقطوعِ والموصول» **52** موضعاً حفصاً (‏51 للدوريِّ
والسوسيّ)، تسقط منها **28** — وكلُّ ساقطٍ **إدغامٌ** وكلُّ صامدٍ **وصلٌ محض**، والعلّةُ
سطرٌ واحد: `scorer.py:390` يبني المدمَجَ `joined = a + b` فصورةُ «ألّا» (‏«الا» لا «انلا»)
لا يملكها `op 4` بحال. وهذا الملفُّ يقيس **الذراعَ** لا العطب: فائدتَها وثمنَها.

**الذراعان — وكلتاهما سطرٌ واحدٌ يُضاف إلى `joined`:**

    (ض) الضيّقة  — لا تُفتَح صورةُ الإدغام إلّا لزوجٍ **من جدول D-409** (‏عشرةُ أزواجٍ
                   بأسمائها) ⇒ مسُّها محصورٌ في 52 موضعاً معروفاً.
    (و) الواسعة  — تُفتَح لكلِّ زوجٍ عليه علامةُ الإدغام في الرسم (‏شدّةٌ على أوّل الثانية
                   ومخرجٌ يقبلها) ⇒ مدىً 1,780–2,568 موضعاً للرواية.

**والعملةُ عملتان لا واحدة، وهذا لبُّ التقرير:**

    الفائدة = مواضعُ «المقطوعِ والموصول» التي تسقط اليومَ وتخضرُّ بالذراع (‏28 مرشَّحة)
    التكلفة = **الإفلات**: موضعٌ تفتح له الذراعُ صورةً هي **كلمةٌ قائمةٌ في المصحف** ⇒
              فمن قرأ تلك الكلمةَ الواحدةَ مكان الكلمتين **يُبرَّأ وهو مخطئ**. وقد أشارت
              D-409 إلى خطرها بعدِّ الصور (‏«الا» 4,782 · «امن» 234 …) — وهذا الملفُّ
              يعدُّ **المواضعَ** لا الصور، ويثبت الإفلاتَ **بتشغيل المِسطرة عليه** لا بالاستنتاج.

⚠️ **وما لا يُقاس هنا فلا يُدَّعى:** أثرُ الذراع على **الاتّهام الكاذب في G3r** يحتاج صوتاً
(‏الشبكةُ ممنوعةٌ في المناوبة) ⇒ يبقى دَيناً، ولا يُشحن شيءٌ قبلَه.

    python tools/tasmi_bench/merge_idgham_arm.py --control   # 🧪 الضوابطُ الثلاثةُ أوّلاً
    python tools/tasmi_bench/merge_idgham_arm.py             # الفائدةُ والتكلفةُ · الستّ
    python tools/tasmi_bench/merge_idgham_arm.py --riwaya hafs --examples 12

⛔ قياسٌ وتقريرٌ: هذا الملفُّ **لا يمسّ** `scorer.py` ولا `RecitationScorer.kt` ولا إعداداً
   مشحوناً. والمِسطرةُ المستعملةُ هنا نسخةٌ من `scorer.score` بسطرِ الذراع، ويحرسها
   **الضابطُ صفر** (‏التطابقُ التامُّ مع الأصل عند تعطيل الذراع) فلا ينحرف القياسُ صامتاً.
"""
import argparse
import collections
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "tools", "alignment"))
import scorer  # noqa: E402
import detect_score  # noqa: E402
from common import load_text  # noqa: E402
from merge_floor import ORTHOGRAPHIC, SHADDA, _tajwid_idgham  # noqa: E402

SIX = ("hafs", "warsh", "qalun", "shuba", "douri", "sousi")

# 🛡️ حدُّ الحارس الموزون: أقصى **وزنٍ** (‏عددُ مواضع الكلمة الغريبة في المصحف) يُتسامَح فيه.
# وُضع 1 لا اعتباطاً: الوزنُ 1 هو الأدنى غيرُ الصفر، وبه تنفتح «الن» دون «امن» (‏26) و«الا» (‏752).
GUARD_W1_MAX = 1


# ───────────────────────── المِسطرةُ بسطرِ الذراع ─────────────────────────
# نسخةٌ من `scorer.score` لا تفارق الأصلَ إلّا في `op 4`: `joined` يكتسب صوراً
# إضافيةً تأتي من `extra[i]`. و`extra` فارغٌ ⇒ السلوكُ الأصليُّ حرفاً بحرف (الضابط ٠).
def score_arm(ref_words, hyp_text, cfg, extra=None):
    extra = extra or {}
    ref = [scorer._riwaya_forms(scorer.variants(w, cfg), cfg) for w in ref_words]
    hyp = [w for w in (scorer.norm(x, cfg) for x in re.split(r"\s+", hyp_text)) if w]
    R, H = len(ref), len(hyp)
    INF = scorer.INF
    dp = [[INF] * (H + 1) for _ in range(R + 1)]
    back = [[None] * (H + 1) for _ in range(R + 1)]
    dp[0][0] = 0
    for i in range(R + 1):
        for j in range(H + 1):
            d = dp[i][j]
            if d == INF:
                continue

            def relax(ni, nj, cost, op, i=i, j=j, d=d):
                if ni <= R and nj <= H and cost < INF and d + cost < dp[ni][nj]:
                    dp[ni][nj] = d + cost
                    back[ni][nj] = (i, j, op)

            if i < R and j < H:
                relax(i + 1, j + 1,
                      0 if scorer._matches(ref[i], hyp[j], cfg)
                      else (1 if scorer._uncertain(ref[i], hyp[j], cfg) else 2), 0)
            if i < R:
                relax(i + 1, j, 3, 1)
            if j < H:
                cheap = getattr(cfg, "learner_tolerant", False) and (
                    any(scorer._matches(ref[k], hyp[j], cfg) for k in range(max(0, i - 2), i))
                    or any(scorer._matches(ref[k], hyp[j], cfg) for k in range(i, min(R, i + 3)))
                    or (i == 0 and j < 6))
                relax(i, j + 1, 1 if cheap else 3, 2)
            if i < R and j + 1 < H:
                relax(i + 1, j + 2,
                      1 if scorer._matches(ref[i], hyp[j] + hyp[j + 1], cfg) else INF, 3)
            if i + 1 < R and j < H:
                joined = tuple(a + b for a in ref[i] for b in ref[i + 1]) + tuple(extra.get(i, ()))
                relax(i + 2, j + 1, 1 if scorer._matches(joined, hyp[j], cfg) else INF, 4)

    words = [None] * R
    additions = []
    i, j = R, H
    while i > 0 or j > 0:
        b = back[i][j]
        if b is None:
            break
        pi, pj, op = b
        if op == 0:
            words[pi] = (pi, scorer.CORRECT if scorer._matches(ref[pi], hyp[pj], cfg)
                         else (scorer.UNCERTAIN if scorer._uncertain(ref[pi], hyp[pj], cfg)
                               else scorer.SUBSTITUTED), hyp[pj])
        elif op == 1:
            words[pi] = (pi, scorer.MISSED, None)
        elif op == 2:
            additions.insert(0, hyp[pj])
        elif op == 3:
            words[pi] = (pi, scorer.CORRECT, hyp[pj] + " " + hyp[pj + 1])
        elif op == 4:
            words[pi] = (pi, scorer.CORRECT, hyp[pj])
            words[pi + 1] = (pi + 1, scorer.CORRECT, hyp[pj])
        i, j = pi, pj
    for k in range(R):
        if words[k] is None:
            words[k] = (k, scorer.MISSED, None)
    words = scorer._collapse_guard(words, cfg)
    return {"words": words, "additions": additions,
            "correct": sum(1 for w in words if w[1] == scorer.CORRECT), "total": R}


# ───────────────────────── مواضعُ الذراع وصورُها ─────────────────────────
def arm_sites(ref, n, arm, lex=None):
    """يعيد {i: (صورةُ الإدغام, نوعُ الموضع)} للأزواج المتلاحقة (i, i+1) في الآية.

    ⚠️ **لا يُفتَح إلّا للمتجاورِين حقيقةً** (‏لا رمزَ بينهما): الرمزُ المنفصل يجعل
    المرجعَ ثلاثاً و`op 4` لا يتعدّى اثنتين ⇒ سقفُ D-409 ذاك لا تمسُّه الذراع.
    """
    out = {}
    for i in range(len(n) - 1):
        na, nb = n[i], n[i + 1]
        if not na or not nb:
            continue
        if arm in ("narrow", "guarded", "guarded_shadda", "guarded_w1"):
            if (na, nb) in ORTHOGRAPHIC:
                img = ORTHOGRAPHIC[(na, nb)]
                if img != na + nb:                     # الوصلُ المحضُ يبلغه `op 4` أصلاً
                    # 🛡️ **الذراعُ المحروسة:** تُغلَق الصورةُ إن كانت **كلمةً قائمةً بحركاتٍ
                    # أخرى** في المصحف — فالحارسُ يقرأ المصحفَ ولا يُملى عليه سطراً سطراً.
                    w = foreign_hit(lex, img, ref[i], ref[i + 1],
                                    tol_shadda=(arm == "guarded_shadda"))
                    if arm != "narrow" and w > (GUARD_W1_MAX if arm == "guarded_w1" else 0):
                        continue
                    out[i] = (img, "جدول")
        elif arm == "wide":
            if _tajwid_idgham(ref[i + 1], na, nb):
                img = na[:-1] + nb
                if img != na + nb:
                    out[i] = (img, "شدّة")
    return out


def hyp_merged(n, i, img):
    """المسموعُ = تطبيعُ المرجع، إلّا الموضعَ (i, i+1) فصورةٌ واحدةٌ هي `img`."""
    out = []
    for k, x in enumerate(n):
        if not x or k == i + 1:
            continue
        out.append(img if k == i else x)
    return " ".join(out)


def lexicon(cfg, text):
    """معجمُ الصور المفردة: صورةٌ مطبَّعةٌ ⇐ Counter لصورها **الخام** وأعدادها.

    والصورةُ الخامُّ لازمةٌ لا زينة: عليها وحدَها يقوم فرزُ «النفس» من «الغير» أدناه.
    """
    lex = collections.defaultdict(collections.Counter)
    for ayah in text:
        for w in ayah.split():
            x = scorer.norm(w, cfg)
            if x:
                lex[x][w] += 1
    return lex


# 🔑 **فرزُ الإفلات — وهو مفتاحُ القياس كلِّه.** الصورةُ المدمَجةُ قد تصطدم بكلمةٍ قائمةٍ
# هي **الزوجُ نفسُه مكتوباً موصولاً في موضعٍ آخرَ من المصحف** (`أَن لَّن` هنا و`أَلَّن` هناك —
# وهذا **بابُ «المقطوعِ والموصول» بعينِه**)، فالتبرئةُ حينئذٍ **صوابٌ لا إفلات**. وقد تصطدم
# بكلمةٍ **أخرى** (`إِلَّا` · `ءَامَنَ`) فتلك هي التكلفةُ الحقيقيّة. والفارقُ بينهما **الحركاتُ**
# التي يحذفها `norm`: `أَلَّا` فتحةٌ وشدّةٌ وفتحة، و`إِلَّا` كسرةٌ وشدّةٌ وفتحة.
# ⇒ الفرزُ آليٌّ محضٌ لا حَدْسَ فيه: تُقارَن **سلسلةُ العلامات** بترتيبها.
_MARKS = re.compile("[ً-ْٰ]")
SHADDA_CH = "ّ"


def _marks(w, tol_shadda=False):
    m = _MARKS.findall(w)
    return tuple(c for c in m if not (tol_shadda and c == SHADDA_CH))


def foreign_hit(lex, img, wa, wb, tol_shadda=False):
    """أتصطدم الصورةُ بكلمةٍ **أخرى**؟ (‏لا بالزوج نفسِه مكتوباً موصولاً في موضعٍ آخر).

    `tol_shadda` يسأل سؤالَ الدَّين: حارسٌ **يتسامح في الشدّة وحدَها** — أيفتح «الن»
    الأحدَ عشرَ؟ يفتحها، لكنّ التسامحَ **لا يُصيِّر الغريبَ نفساً**: الجوابُ المقيسُ
    أدناه أنّ `أَلَن` (٣:١٢٤) همزةُ استفهامٍ + `لَن`، لا `أَن` + `لَن` موصولَين.
    """
    raws = (lex or {}).get(img)
    if not raws:
        return 0
    want = _marks(_raw_idgham(wa, wb), tol_shadda)
    return sum(c for w, c in raws.items() if _marks(w, tol_shadda) != want)


def _raw_idgham(wa, wb):
    """صورةُ الزوج الخامُّ مدغمةً: يُحذف آخرُ **حرفٍ** من الأولى بعلاماته، ثمّ تُوصَل الثانية."""
    k = len(wa)
    while k > 0 and _MARKS.match(wa[k - 1]):
        k -= 1
    return wa[:max(k - 1, 0)] + wb


# ───────────────────────────── الضوابط ─────────────────────────────
def control_identity(limit):
    """ضابط ٠ — التطابقُ التامّ: الذراعُ معطَّلةً ⇒ كلُّ حكمٍ كما تحكم `scorer.score`."""
    bad = tot = 0
    for riw in SIX:
        cfg = detect_score.cfg_for(riw)
        text = load_text(riw)
        step = max(1, len(text) // limit)
        for ayah in text[::step][:limit]:
            ref = ayah.split()
            if not ref:
                continue
            n = [scorer.norm(w, cfg) for w in ref]
            hyps = [" ".join(x for x in n if x)]
            sites = arm_sites(ref, n, "wide") or arm_sites(ref, n, "narrow")
            for i, (img, _) in list(sites.items())[:1]:
                hyps.append(hyp_merged(n, i, img))
                hyps.append(hyp_merged(n, i, n[i] + n[i + 1]))
            for h in hyps:
                tot += 1
                a = scorer.score(ref, h, cfg)["words"]
                b = score_arm(ref, h, cfg, None)["words"]
                if a != b:
                    bad += 1
    return bad, tot


def control_signs(riwayat):
    """ضابطان — موجبٌ: المواضعُ الساقطةُ (‏إدغامٌ) تخضرُّ بالذراع الضيّقة.
                سالبٌ: المواضعُ الصامدةُ (‏وصلٌ محضٌ) تبقى خضراءَ ولا تنقلب."""
    pos_fix = pos_tot = neg_ok = neg_tot = 0
    for riw in riwayat:
        cfg = detect_score.cfg_for(riw)
        for ayah in load_text(riw):
            ref = ayah.split()
            if not ref:
                continue
            n = [scorer.norm(w, cfg) for w in ref]
            for i in range(len(n) - 1):
                if not n[i] or not n[i + 1] or (n[i], n[i + 1]) not in ORTHOGRAPHIC:
                    continue
                img = ORTHOGRAPHIC[(n[i], n[i + 1])]
                pure = img == n[i] + n[i + 1]
                hyp = hyp_merged(n, i, img)
                extra = {i: (img,)}
                before = all(w[1] == scorer.CORRECT for w in scorer.score(ref, hyp, cfg)["words"])
                after = all(w[1] == scorer.CORRECT for w in score_arm(ref, hyp, cfg, extra)["words"])
                if pure:
                    neg_tot += 1
                    neg_ok += 1 if (before and after) else 0
                else:
                    pos_tot += 1
                    pos_fix += 1 if (not before and after) else 0
    return pos_fix, pos_tot, neg_ok, neg_tot


# ─────────────────────── الفائدةُ والتكلفةُ لرواية ───────────────────────
def measure(riw, arm, examples=0, fast=False, unfixed=0):
    """`fast` يُسقط تشغيلَ المِسطرة (‏فلا `fell`/`fixed`) ويُبقي فرزَ الاصطدام وحدَه —
    وهو ما يحتاجه دَينُ «فرزِ اصطدام الواسعة على الستّ»: الفرزُ معجميٌّ لا يحتاج حكماً.
    `unfixed` يطبع أمثلةَ المواضع التي **سقطت وبقيت ساقطةً** بعد الذراع (‏دَينٌ رابع)."""
    cfg = detect_score.cfg_for(riw)
    text = load_text(riw)
    lex = lexicon(cfg, text)
    sites = fell = fixed = escape = esc_self = esc_foreign = 0
    fixed_pair_only = 0
    esc_weight = esc_self_weight = 0
    esc_kinds = collections.Counter()
    esc_ex = {}
    unfixed_ex = []
    base_collide = base_sites = 0
    for ayah in text:
        ref = ayah.split()
        if not ref:
            continue
        n = [scorer.norm(w, cfg) for w in ref]
        # خطُّ الأساس: كم موضعاً يفتح له `op 4` **اليومَ** صورةَ وصلٍ هي كلمةٌ قائمة؟
        for i in range(len(n) - 1):
            if n[i] and n[i + 1]:
                base_sites += 1
                if lex.get(n[i] + n[i + 1]):
                    base_collide += 1
        for i, (img, kind) in arm_sites(ref, n, arm, lex).items():
            sites += 1
            if not fast:
                hyp = hyp_merged(n, i, img)
                extra = {i: (img,)}
                before = all(w[1] == scorer.CORRECT
                             for w in scorer.score(ref, hyp, cfg)["words"])
                aw = score_arm(ref, hyp, cfg, extra)["words"]
                after = all(w[1] == scorer.CORRECT for w in aw)
                if not before:
                    fell += 1
                    if after:
                        fixed += 1
                    else:
                        # ⚠️ **ومعيارُ «الآيةُ كلُّها خضراء» يظلم الذراعَ:** الرمزُ المنفصل
                        # (`۞` · `ۗ`) تطبيعُه فارغٌ فيُحكَم عليه `MISSED` دائماً ⇒ فالآيةُ
                        # لا تخضرُّ أبداً وإن أخضرَّ **الزوجُ**. فيُعَدُّ المعيارُ الموضعيُّ
                        # إلى جانبه: أخضرَّتِ الكلمتان (i, i+1) أنفسُهما؟
                        if (aw[i][1] == scorer.CORRECT
                                and aw[i + 1][1] == scorer.CORRECT):
                            fixed_pair_only += 1
                        elif len(unfixed_ex) < unfixed:
                            unfixed_ex.append((ref[i], ref[i + 1], img,
                                               " ".join(ref)[:70]))
            # 💸 الإفلات: الصورةُ الجديدةُ **كلمةٌ قائمةٌ في المصحف** ⇒ من قرأها يُبرَّأ.
            raws = lex.get(img)
            if raws:
                escape += 1
                want = _marks(_raw_idgham(ref[i], ref[i + 1]))
                mine = sum(c for w, c in raws.items() if _marks(w) == want)
                other = sum(c for w, c in raws.items() if _marks(w) != want)
                # ⚖️ والوزنُ غيرُ العدد: موضعٌ واحدٌ يصطدم بكلمةٍ وزنُها 752 ليس كموضعٍ
                # يصطدم بوزن 1. والعددُ وحدَه يسوّي بينهما ⇒ يُكتب الوزنُ إلى جانبه.
                esc_weight += other
                esc_self_weight += mine
                if other:
                    esc_foreign += 1
                    top = max(((w, c) for w, c in raws.items() if _marks(w) != want),
                              key=lambda t: t[1])
                    esc_kinds[(img, top[0], other)] += 1
                    esc_ex.setdefault((img, top[0], other), (ref[i], ref[i + 1], mine))
                else:
                    esc_self += 1
    return dict(riwaya=riw, arm=arm, sites=sites, fell=fell, fixed=fixed, fast=fast,
                fixed_pair_only=fixed_pair_only,
                escape=escape, esc_self=esc_self, esc_foreign=esc_foreign,
                esc_weight=esc_weight, esc_self_weight=esc_self_weight,
                kinds=esc_kinds.most_common(examples or 6), ex=esc_ex,
                unfixed_ex=unfixed_ex,
                base_sites=base_sites, base_collide=base_collide)


def selftest():
    """🧪 **حارسُ ذراع الإدغام** (‏D-506) — والضوابطُ الثلاثةُ فيها **ثقيلةٌ** (تجري المِسطرةَ
    على الستّ وعلى المصحف كلِّه في `control_signs`) فلا تُشعَل في كلّ دفعة. وهذا يفحص في
    ثوانٍ الأربعةَ التي يسقط القياسُ كلُّه بسقوطها:

    ⭐⭐ **نسخةُ المِسطرة لم تنحرف عن أصلها** — `score_arm` **نسخةٌ من `scorer.score`**،
      وانحرافُها بسطرٍ يجعل كلَّ فرقٍ نقيسه فرقَ نسختَين لا فرقَ ذراع (ضابطُ ٠ مصغَّراً).
    ⭐ **وسطرُ الذراع يفعل شيئاً أصلاً** — ذراعٌ بلا أثرٍ تعطي «صفرَ تكلفةٍ وصفرَ فائدة»
      فتبدو رخيصةً بلا ثمنٍ ولا نفع (‏وهو عينُ عطبِ D-503 في دفتر الرخص).
    ⭐⭐ **وفرزُ الإفلات يفرّق «النفس» من «الغير»** — وعليه وحدَه تقوم التكلفة: إن عدَّ
      `أَلَّا` إفلاتاً لارتفعت التكلفةُ كذباً، وإن عدَّ `إِلَّا` نفساً **لبُرِّئ مخطئٌ**.
    ⛔ **والحارسُ يضيّق ولا يوسّع** — رتابةٌ مقيسةٌ: `narrow ⊇ guarded_w1 ⊇ guarded`.
    """
    ok = True

    def say(good, line):
        nonlocal ok
        ok &= bool(good)
        print(("✅ " if good else "❌ ") + line)

    cfg = detect_score.cfg_for("hafs")
    text = load_text("hafs")
    lex = lexicon(cfg, text)

    # ①⭐⭐ ضابطُ ٠ مصغَّراً: الذراعُ معطَّلةً ⇒ **حكمٌ بحكم** لا «قريبٌ منه»
    bad = tot = 0
    for ayah in text[:120]:
        ref = ayah.split()
        if not ref:
            continue
        n = [scorer.norm(w, cfg) for w in ref]
        hyp = " ".join(x for x in n if x)
        a = scorer.score(ref, hyp, cfg)
        b = score_arm(ref, hyp, cfg, None)
        tot += 1
        if a["words"] != b["words"] or a["additions"] != b["additions"]:
            bad += 1
    say(tot >= 100 and bad == 0,
        "⭐⭐ النسخةُ تطابق `scorer.score` حرفاً بحرفٍ عند تعطيل الذراع: %d/%d" % (tot - bad, tot))

    # ② وسطرُ الذراع **يغيّر الحكم** حين يُفتح — وإلّا كان القياسُ على لا شيء
    fixed = seen = 0
    for ayah in text:
        ref = ayah.split()
        n = [scorer.norm(w, cfg) for w in ref]
        for i in range(len(n) - 1):
            if not n[i] or not n[i + 1] or (n[i], n[i + 1]) not in ORTHOGRAPHIC:
                continue
            img = ORTHOGRAPHIC[(n[i], n[i + 1])]
            if img == n[i] + n[i + 1]:
                continue                     # وصلٌ محضٌ يبلغه `op 4` أصلاً
            hyp = hyp_merged(n, i, img)
            before = all(w[1] == scorer.CORRECT for w in scorer.score(ref, hyp, cfg)["words"])
            after = all(w[1] == scorer.CORRECT
                        for w in score_arm(ref, hyp, cfg, {i: (img,)})["words"])
            seen += 1
            fixed += 1 if (not before and after) else 0
            if seen >= 12:
                break
        if seen >= 12:
            break
    say(seen >= 5 and fixed == seen,
        "⭐ سطرُ الذراع يقلب الساقطَ أخضرَ في %d من %d موضعَ إدغامٍ جُرِّب" % (fixed, seen))

    # ③⭐⭐ فرزُ الإفلات على **المصحف نفسِه**: `أَلَّا` نفسٌ · و`إِلَّا` غيرٌ
    self_hit = foreign_hit(lex, "الا", "أَن", "لَّا")
    other_hit = foreign_hit(lex, "الا", "إِ", "لَّا")
    say(self_hit > 0 and other_hit >= 0 and foreign_hit(lex, "لاتوجدصورة", "أَن", "لَّا") == 0,
        "فرزُ الإفلات يقرأ المعجمَ: «الا» تصطدم بـ%d صورةٍ خام، وصورةٌ غيرُ موجودةٍ ⇒ 0" % self_hit)
    say(_marks("أَلَّا") != _marks("إِلَّا") and _marks("أَلَّا", tol_shadda=True) !=
        _marks("إِلَّا", tol_shadda=True),
        "⭐⭐ والفارقُ **حركاتٌ بترتيبها**: أَلَّا %s ≠ إِلَّا %s — فلا يُبرَّأ مخطئٌ بحَدْس"
        % ("".join(_marks("أَلَّا")), "".join(_marks("إِلَّا"))))
    say(_raw_idgham("أَن", "لَّا") == "أَلَّا" and _raw_idgham("عَن", "مَّا") == "عَمَّا",
        "وصورةُ الزوج الخامُّ مدغمةً تُبنى بحذف الحرف الأخير بعلاماته: %s · %s"
        % (_raw_idgham("أَن", "لَّا"), _raw_idgham("عَن", "مَّا")))

    # ④⛔ الحارسُ **يضيّق ولا يوسّع** — رتابةٌ مقيسةٌ لا مدَّعاة
    cnt = {}
    for arm in ("narrow", "guarded_w1", "guarded"):
        c = 0
        for ayah in text[:1500]:
            ref = ayah.split()
            n = [scorer.norm(w, cfg) for w in ref]
            c += len(arm_sites(ref, n, arm, lex))
        cnt[arm] = c
    say(cnt["narrow"] >= cnt["guarded_w1"] >= cnt["guarded"] and cnt["narrow"] > cnt["guarded"],
        "⛔ ضيقاً: narrow %d ⊇ guarded_w1 %d ⊇ guarded %d — الحارسُ يقصُّ ولا يفتح"
        % (cnt["narrow"], cnt["guarded_w1"], cnt["guarded"]))
    say(GUARD_W1_MAX == 1, "⛔ وحدُّ الحارس الموزون كما قِيس: %d" % GUARD_W1_MAX)

    # ⑤ المسموعُ المدمَجُ يُسقط الكلمةَ الثانيةَ ويضع الصورةَ مكانَ الأولى — لا أكثر
    n = ["الف", "ان", "لا", "باء"]
    say(hyp_merged(n, 1, "الا") == "الف الا باء",
        "المسموعُ المدمَج: %r" % hyp_merged(n, 1, "الا"))
    say(hyp_merged(["", "ان", "لا"], 1, "الا") == "الا",
        "والرمزُ المطبَّعُ إلى فراغٍ لا يدخل المسموع")

    # ⑥ جدولُ «المقطوعِ والموصول» عشرةُ أزواجٍ بأسمائها — لا يُوسَّع بالسكوت
    say(len(ORTHOGRAPHIC) == 10 and all(len(k) == 2 for k in ORTHOGRAPHIC),
        "جدولُ D-409 عشرةُ أزواج: %d" % len(ORTHOGRAPHIC))

    # ⑦ حارسُ مصدرٍ على أرقام الدَّين التي بُنيت عليها الذراع
    src = io.open(os.path.abspath(__file__), encoding="utf-8").read()
    say(all(k in src for k in ("52", "28", "D-409", "الاتّهام الكاذب في G3r")),
        "حارسُ مصدر: 52 موضعاً · 28 ساقطةً · والدَّينُ الصوتيُّ الباقي مكتوبان")
    say("لا يُشحن شيءٌ قبلَه" in src,
        "⛔ وشرطُ الشحن باقٍ بالنصّ: لا شحنَ قبل قياس الاتّهام الكاذب بالصوت")

    print("\n%s" % ("✅ حارسُ ذراع الإدغام: تمّ" if ok else "❌ حارسُ ذراع الإدغام: أخفق"))
    return 0 if ok else 1


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--riwaya", choices=SIX + ("all",), default="all")
    p.add_argument("--arm", choices=("narrow", "guarded", "guarded_shadda", "guarded_w1",
                                     "wide", "both", "all", "guards"),
                   default="both")
    p.add_argument("--control", action="store_true", help="🧪 الضوابطُ الثلاثةُ وحدَها")
    p.add_argument("--selftest", action="store_true", help="🧪 حارسُ الأداة (ثوانٍ · خفيف)")
    p.add_argument("--identity-limit", type=int, default=400,
                   help="عددُ آياتِ ضابطِ التطابق لكلِّ رواية")
    p.add_argument("--examples", type=int, default=0)
    p.add_argument("--fast", action="store_true",
                   help="فرزُ الاصطدام وحدَه بلا تشغيل المِسطرة (‏للستّ بسرعة)")
    p.add_argument("--unfixed", type=int, default=0,
                   help="اطبع هذا العددَ من المواضع التي سقطت ولم تُصلَح")
    a = p.parse_args()
    if a.selftest:
        return selftest()
    riwayat = SIX if a.riwaya == "all" else (a.riwaya,)
    fail = 0

    if a.control:
        bad, tot = control_identity(a.identity_limit)
        mark = "✅" if bad == 0 else "🚨"
        print(f"{mark} ضابط ٠ · التطابقُ مع `scorer.score` عند تعطيل الذراع: "
              f"{tot - bad}/{tot} حالةً متطابقة")
        fail += bad
        sys.stdout.flush()
        pf, pt, no, nt = control_signs(riwayat)
        m1 = "✅" if (pt and pf == pt) else "🚨"
        m2 = "✅" if (nt and no == nt) else "🚨"
        print(f"{m1} ضابطٌ موجب · المواضعُ المدغَمةُ الساقطةُ تخضرُّ بالذراع: {pf}/{pt}")
        print(f"{m2} ضابطٌ سالب · المواضعُ الوَصليّةُ الخضراءُ تبقى خضراءَ: {no}/{nt}")
        fail += (pt - pf) + (nt - no)
        return 1 if fail else 0

    NAMES = {"narrow": "الضيّقة (جدولُ D-409)",
             "guarded": "🛡️ المحروسة (الجدولُ ناقصاً ما يصطدم)",
             "guarded_shadda": "🛡️ المحروسةُ المتسامحةُ في الشدّة",
             "guarded_w1": f"🛡️ المحروسةُ بوزنٍ ≤ {GUARD_W1_MAX}",
             "wide": "الواسعة (كلُّ مشدَّد)"}
    for riw in riwayat:
        arms = ("narrow", "wide") if a.arm == "both" else (
            ("narrow", "guarded", "wide") if a.arm == "all" else (
                ("guarded", "guarded_shadda", "guarded_w1") if a.arm == "guards"
                else (a.arm,)))
        for arm in arms:
            r = measure(riw, arm, a.examples, fast=a.fast, unfixed=a.unfixed)
            name = NAMES[arm]
            if not r["sites"]:
                print(f"— {riw} · {name}: لا موضعَ ⇒ لا تُقاس")
                continue
            fixed_txt = ("المِسطرةُ لم تُشغَّل (`--fast`) ⇒ لا fell/fixed" if a.fast
                         else f"كانت تسقط {r['fell']} ⇒ **تُصلَح {r['fixed']}**"
                              + (f" (‏و{r['fixed_pair_only']} أخضرَّ فيها **الزوجُ** "
                                 f"وبقيت الآيةُ حمراءَ برمزٍ منفصلٍ لا بالذراع ⇒ "
                                 f"**{r['fixed'] + r['fixed_pair_only']} موضعاً بالمعيار "
                                 f"الموضعيّ**)" if r['fixed_pair_only'] else ""))
            print(f"🧲 {riw} · الذراعُ {name}: مواضعُ {r['sites']} · {fixed_txt} · "
                  f"اصطدامٌ {r['escape']} منه **إفلاتٌ حقيقيٌّ {r['esc_foreign']}** "
                  f"({100 * r['esc_foreign'] / r['sites']:.1f}٪ · وزنُه {r['esc_weight']}) "
                  f"و«اصطدامٌ بالنفس» {r['esc_self']} (‏تبرئةٌ صائبة · وزنُ "
                  f"{r['esc_self_weight']})")
            print(f"     ◦ خطُّ الأساس للمقارنة: صورةُ الوصل المحض تصطدم بكلمةٍ قائمةٍ في "
                  f"{r['base_collide']}/{r['base_sites']} زوجاً "
                  f"({100 * r['base_collide'] / max(r['base_sites'], 1):.2f}٪)")
            for (img, top, c), k in r["kinds"]:
                wi, wj, mine = r["ex"][(img, top, c)]
                print(f"     💸 {img!r} ⇜ كلمةٌ **أخرى** {top!r} ×{c} "
                      f"(‏ومن الزوج نفسِه موصولاً ×{mine}) — في {k} موضعاً: {wi!r} + {wj!r}")
            for wi, wj, img, ctx in r["unfixed_ex"]:
                print(f"     ⛔ سقط ولم يُصلَح: {wi!r} + {wj!r} ⇒ {img!r} — {ctx}")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
