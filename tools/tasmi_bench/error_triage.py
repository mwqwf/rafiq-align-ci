# -*- coding: utf-8 -*-
"""🔖 **تصنيفُ الأخطاء الباقية على التلاوة النظيفة** — ومعه **سعرُ كلِّ بابٍ** يُقترح لفتحه.

## السؤالُ ومن أين جاء
D-389 قاست تقاطعَ مواضع الخطأ بين ذراعَين على النظيف فأعطت **×13.31** [×10.14..×18.64]
(‏32 موضعاً ملحوظاً مقابل 2.4 بالمصادفة) ⇒ **الأخطاءُ الباقيةُ على النظيف مادّةٌ ثابتةٌ
بعينها** لا عمليّةٌ عشوائيّة. و«32 خطأً» **نسبةٌ مجهولةٌ** ما لم تُقرأ كلمةً كلمة:
أهي **بترُ كلمةٍ** سمعها الفكُّ ناقصةً؟ أم **كلمةٌ قرآنيّةٌ أخرى** سُمعت مكانَها؟ أم
**التباسُ حرفٍ من مخرجه**؟ فلكلِّ صنفٍ علاجٌ مختلف، وأحدُها **لا يُعالَج بحال**.

## المِسطرة — شكلُ العلاقة لا الانطباع
لكلِّ زوجٍ (‏مرجعٌ · ما سُمع) تُحسب صورُ المرجع المقبولةُ **بإعداد الحاكم المشحون**
(`score.config_for("proposed", riwaya)` ثمّ `variants` ثمّ `_riwaya_forms`) ويُطبَّع
المسموعُ بالتطبيع نفسِه، ثمّ يُسأل **سؤالٌ شكليٌّ واحدٌ قابلٌ للفحص**:

    صفرُ سمع     · لا نصَّ البتّة (‏`MISSED`) ⇒ العلاجُ في الفكّ/التقطيع لا في الحاكم
    بترُ صدر     · المسموعُ **ذَنَبُ** صورةٍ (‏«تراث» من «التراث») ⇒ سقط صدرُ الكلمة
    بترُ عجز     · المسموعُ **صدرُ** صورةٍ (‏«تله» من «تلهى»)
    بترٌ داخليّ  · المسموعُ داخلَ صورةٍ بلا طرفَيها
    التصاقٌ      · صورةُ المرجع **داخلَ** المسموع (‏«وكذب» في «واسوكذب») ⇒ جارةٌ لُصِقت
    مخرجٌ واحد   · طولٌ واحدٌ وموضعُ اختلافٍ واحدٌ من المخرج نفسِه (‏جدولُ D-283)
                   ⭐ **ومنطقةُ هذا البابِ كلماتُ أربعةِ حروفٍ وحدَها** — بحسابٍ لا بعيّنة:
                   خطأُ حرفٍ في كلمةٍ طولُها ≥5 يقبله **الخُمسُ** أصلاً (1×5 ≤ 5)، وفي
                   كلمةٍ طولُها ≤3 تقبله **رخصةُ القصيرة** (`short_cap=3`) ⇒ فما بقي إلا 4.
    مخرجٌ مجاور  · كذلك من مخرجٍ مجاور
    صورةٌ بعيدة  · لا علاقةَ شكليّةً ⇒ العلاجُ في السمع

⛔ **وعلامةٌ مستقلّةٌ عن الصنف — ولها الأولويّةُ في القرار:** أيوافق المسموعُ **صورةَ كلمةٍ
قرآنيّةٍ أخرى** موافقةً تامّة؟ (‏بحثٌ في نصِّ الرواية كلِّه). فإن كان **فكلُّ بابٍ يغفر هذا
الموضعَ يغفر معه زلّةً حقيقيّةً** — ويبقى الصنفُ وصفاً للشكل لا إذناً بالغفران. والموافقةُ
تُطلب **تامّةً** (صورةٌ مقبولةٌ = المسموعُ حرفاً بحرف) لا بعتبة الخُمس، كي لا يُنتفخ العدّ.

## وسعرُ كلِّ باب — بعملة `license_ledger` نفسِها
`--cost` يقيس على **نصِّ الرواية كلِّه**: كم **موضعاً** (‏بتكرار الكلمة لا بالكلمات الفريدة)
يصير مقبولاً فيه **نطقُ كلمةٍ قرآنيّةٍ أخرى** لو فُتح البابُ؟ فبابٌ يكسب ثلاثةَ مواضعَ
في عيّنتنا ويعمي عن ألفٍ في المصحف **بابٌ خاسرٌ بالرقم** لا بالرأي.

⛔ **وهذا كشفٌ لا شحنٌ**: لا يُغيَّر به حكمٌ ولا تُخفَّض عتبةٌ ولا يُفتح بابٌ — المخرَجُ
جدولٌ يُقرأ، وأيُّ فتحٍ بابٍ **بندُ قرارٍ** له ذراعٌ تُقاس قبلَه وبعدَه.

    python error_triage.py --pairs pairs.json           # أزواجٌ تُصنَّف (‏مرجع · ما سُمع · رواية)
    python error_triage.py --dirs "work:" --arms "shipped-P nogate-P" --sets "g4"
    python error_triage.py --cost --riwayat "warsh qalun"
    python error_triage.py --selftest
"""
import argparse
import collections
import json
import os
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

HERE = os.path.dirname(os.path.abspath(__file__))
MISS = "صفرُ سمع"
HEAD = "بترُ صدر"
TAIL = "بترُ عجز"
MIDL = "بترٌ داخليّ"
GLUE = "التصاقٌ"
PHON1 = "مخرجٌ واحد"
PHON2 = "مخرجٌ مجاور"
MADD = "مدٌّ ساقط"
FAR = "صورةٌ بعيدة"
_MADD_CHARS = "اوي"
ACCEPTED = "⚠️ يقبله الحاكمُ أصلاً"

# باب الحاكم الذي يغفر الصنف لو فُتح — أو لا بابَ له (‏فالعلاجُ خارجَ الحاكم).
DOOR = {
    MISS: "— (‏فكٌّ/تقطيع)",
    HEAD: "بابُ الذَنَب",
    TAIL: "بابُ الصدر",
    MIDL: "بابُ الاحتواء",
    GLUE: "بابُ الاحتواء المقلوب",
    PHON1: "`phon=same`",
    PHON2: "`phon=adj`",
    MADD: "بابُ المدّ",
    FAR: "— (‏سمع)",
}
_SEP = "ـ"  # لا يُستعمل — يُبقى صريحاً أنّ المقارنةَ على الحروف بعد التطبيع


def _mods():
    sys.path.insert(0, HERE)
    sys.path.insert(0, os.path.join(os.path.dirname(HERE), "alignment"))
    import scorer as SCR
    import score as SC
    return SCR, SC


def forms_of(word, cfg, SCR):
    """صورُ المرجع المقبولةُ كما يبنيها الحاكمُ نفسُه (‏variants ثمّ صورُ الرواية)."""
    return SCR._riwaya_forms(SCR.variants(word, cfg), cfg)


def classify(ref_raw, heard, riwaya, SCR=None, SC=None, lexicon=None, min_part=2):
    """صنفُ الزوج · وبابُه · وأتوافق المسموعُ كلمةً قرآنيّةً أخرى تماماً؟

    ترجع (‏الصنف · تفصيلٌ يُطبع · أهي كلمةٌ أخرى). و`lexicon` مجموعةُ الصور المقبولة
    لكلِّ كلمات الرواية (‏تُبنى مرّةً بـ`lexicon_of`) — وغيابُها يعني «لم يُبحَث» لا «لا».
    """
    if SCR is None or SC is None:
        SCR, SC = _mods()
    cfg = SC.config_for("proposed", riwaya)
    forms = forms_of(ref_raw, cfg, SCR)
    if heard is None or heard in ("—", ""):
        return MISS, f"صفرُ نصٍّ مقابلَ `{forms[0]}`", False, ""
    h = SCR.norm(heard, cfg)
    other = bool(lexicon) and h in lexicon and h not in forms
    if SCR._matches(forms, h, cfg):
        return ACCEPTED, f"`{h}` مقبولٌ لـ`{forms[0]}` ⇒ العطبُ في خطِّ القراءة لا في الزوج", other, ""
    if len(h) >= min_part:
        for f in forms:
            if h == f:
                continue
            if f.endswith(h):
                return HEAD, f"سقط صدرُ `{f}` (`{f[:len(f) - len(h)]}`)", other, f[:len(f) - len(h)]
            if f.startswith(h):
                return TAIL, f"سقط عجزُ `{f}` (`{f[len(h):]}`)", other, ""
        for f in forms:
            if h != f and h in f:
                return MIDL, f"`{h}` داخلَ `{f}`", other, ""
    for f in forms:
        if f and f != h and f in h:
            return GLUE, f"`{f}` داخلَ المسموع `{h}` (‏زيادةُ {len(h) - len(f)} حرفاً)", other, ""
    for name, mode in ((PHON1, "same"), (PHON2, "adj")):
        c2 = SC.config_for("proposed", riwaya)
        c2.phon, c2.phon_cap = mode, 99
        for f in forms:
            if SCR._phon_ok(f, h, c2):
                d = [(a, b) for a, b in zip(f, h) if a != b][0]
                return name, f"`{f}` ⇄ `{h}` (`{d[0]}`⇄`{d[1]}`)", other, ""
    for f in forms:
        if madd_drop(f, h):
            return MADD, f"`{f}` ⇒ `{h}` (‏حُذف من حروف المدّ {len(f) - len(h)})", other, ""
    f0 = forms[0]
    return FAR, f"`{f0}` ⇄ `{h}` (‏مسافةٌ {SCR._edit(f0, h)}/{max(len(f0), len(h))})", other, ""


def madd_drop(f, h):
    """أيُنال `h` من `f` **بحذف حروف المدّ وحدَها** (‏ا · و · ي) بلا إبدالٍ ولا زيادة؟

    شرطٌ صارمٌ: `h` متتاليةٌ جزئيّةٌ من `f` وكلُّ محذوفٍ حرفُ مدّ. فـ`بالافق`⇒`بلفق` نعم،
    و`وحقت`⇒`وحك` لا (‏حُذف حرفٌ صحيحٌ وأُبدل آخر).
    """
    if not h or len(h) >= len(f):
        return False
    i = 0
    dropped = 0
    for ch in f:
        if i < len(h) and ch == h[i]:
            i += 1
        elif ch in _MADD_CHARS:
            dropped += 1
        else:
            return False
    return i == len(h) and dropped > 0


def lexicon_of(riwaya, cfg, SCR, load_text):
    """كلُّ صورةٍ مقبولةٍ لكلِّ كلمةٍ في نصِّ الرواية — للسؤال «أهي كلمةٌ أخرى؟»."""
    lex = set()
    for ayah in load_text(riwaya):
        for w in ayah.split():
            lex.update(forms_of(w, cfg, SCR))
    lex.discard("")
    return lex


def counts_of(riwaya, cfg, SCR, load_text):
    """(‏صورةٌ أولى ⇒ عددُ المواضع) و(صورةٌ أولى ⇒ صورُها كلُّها) لكلمات الرواية."""
    occ = collections.Counter()
    forms = {}
    for ayah in load_text(riwaya):
        for w in ayah.split():
            fs = forms_of(w, cfg, SCR)
            if not fs or not fs[0]:
                continue
            occ[fs[0]] += 1
            forms.setdefault(fs[0], set()).update(fs)
    return occ, forms


def head_cost(riwaya, heads, SCR, SC, load_text):
    """سعرُ **بابٍ ضيّقٍ** لكلِّ صدرٍ بعينه: «اغفرْ سقوطَ الصدر `hh`».

    الثمنُ بالعملة نفسِها: كم موضعاً يصير فيه نطقُ **كلمةٍ قرآنيّةٍ أخرى** مقبولاً؟
    (‏«والصبح» لو غُفر سقوطُ «و» قَبِلت «الصبح» — وهي كلمةٌ أخرى ⇒ سقوطُ الواو زلّةٌ تُبتلَع.)
    """
    cfg = SC.config_for("proposed", riwaya)
    occ, forms = counts_of(riwaya, cfg, SCR, load_text)
    by_form = collections.defaultdict(set)
    for k, fs in forms.items():
        for f in fs:
            by_form[f].add(k)
    cost = collections.Counter()
    reach = collections.Counter()
    for k, fs in forms.items():
        n = occ[k]
        for hh in heads:
            hit = paid = False
            for f in fs:
                if not f.startswith(hh) or len(f) - len(hh) < 2:
                    continue
                hit = True
                if by_form.get(f[len(hh):], set()) - {k}:
                    paid = True
            if hit:
                reach[hh] += n
            if paid:
                cost[hh] += n
    return cost, reach, sum(occ.values())


def naql_cost(riwaya, SCR, SC, load_text):
    """سعرُ **بابِ النقل** بشكله الصحيح: `ال…` ⇒ `ل…` (‏تسقط ألفُ الوصل نطقاً لا اللامُ معها).

    ولِمَ وحدَه؟ لأنّه **مفتوحٌ في ورشٍ مشحوناً ومغلقٌ في قالون** (`_riwaya_forms`: `naql`)،
    وسقوطُ ألفِ الوصل في الوصل **ظاهرةٌ عربيّةٌ عامّةٌ لا خاصّةَ ورشٍ** ⇒ فالسؤالُ مقيسٌ:
    كم موضعاً يبلغه البابُ؟ وكم موضعاً **يعمى** عن كلمةٍ قرآنيّةٍ أخرى لو فُتح؟
    (‏وفي ورشٍ هذا ثمنٌ **مدفوعٌ اليومَ** لا مقترَح.)
    """
    cfg = SC.config_for("proposed", riwaya)
    occ, forms = counts_of(riwaya, cfg, SCR, load_text)
    by_form = collections.defaultdict(set)
    for k, fs in forms.items():
        for f in fs:
            by_form[f].add(k)
    reach = cost = 0
    for k, fs in forms.items():
        n = occ[k]
        hit = paid = False
        for f in fs:
            if f.startswith("ال") and len(f) > 3:
                hit = True
                if by_form.get("ل" + f[2:], set()) - {k}:
                    paid = True
        if hit:
            reach += n
        if paid:
            cost += n
    return reach, cost, sum(occ.values()), cfg.naql


def door_cost(riwaya, SCR, SC, load_text, min_part=2):
    """سعرُ كلِّ بابٍ على نصِّ الرواية كلِّه — بعملة `license_ledger`(ب): **مواضعُ عمًى**.

    لكلِّ كلمةٍ (‏بتكرارها) نسأل: هل توجد كلمةٌ قرآنيّةٌ **أخرى** صورتُها تدخل البابَ مع
    هذه الكلمة؟ فإن وُجدت فنطقُ الأخرى مكانَ هذه **يُقبل** لو فُتح البابُ ⇒ زلّةٌ تُبتلَع.
    ⛔ **وهذا سقفُ الثمن لا وسطُه**: المحاذاةُ وحارسُ الانهيار طبقتان فوقَه (‏قيدُ
    `license_ledger` نفسُه) — يُخفيان أثرَه ولا يُنشئانه.
    """
    cfg = SC.config_for("proposed", riwaya)
    occ, forms = counts_of(riwaya, cfg, SCR, load_text)
    all_forms = set()
    for fs in forms.values():
        all_forms.update(fs)
    by_form = collections.defaultdict(set)     # صورةٌ ⇒ مفاتيحُ الكلمات التي تملكها
    for k, fs in forms.items():
        for f in fs:
            by_form[f].add(k)
    out = collections.Counter()
    uniq = collections.Counter()
    tot_pos = sum(occ.values())
    for k, fs in forms.items():
        n = occ[k]
        hit = set()
        for f in fs:
            for i in range(len(f) - min_part + 1):
                for j in range(i + min_part, len(f) + 1):
                    part = f[i:j]
                    if part == f or len(part) < min_part:
                        continue
                    if part not in by_form:
                        continue
                    if not (by_form[part] - {k}):
                        continue
                    if f.endswith(part):
                        hit.add(HEAD)
                    elif f.startswith(part):
                        hit.add(TAIL)
                    else:
                        hit.add(MIDL)
        for d in hit:
            out[d] += n
            uniq[d] += 1
    # بابُ المدّ: حذفُ حروف مدٍّ من الكلمة يعطي **كلمةً قرآنيّةً أخرى**
    import itertools
    for k, fs in forms.items():
        n = occ[k]
        paid = False
        for f in fs:
            pos = [i for i, c in enumerate(f) if c in _MADD_CHARS]
            if not pos or len(pos) > 8:
                continue
            for r in range(1, len(pos) + 1):
                for comb in itertools.combinations(pos, r):
                    cand = "".join(c for i, c in enumerate(f) if i not in comb)
                    if len(cand) < min_part:
                        continue
                    if by_form.get(cand, set()) - {k}:
                        paid = True
                        break
                if paid:
                    break
            if paid:
                break
        if paid:
            out[MADD] += n
            uniq[MADD] += 1
    # بابا المخرج: زوجُ كلمتَين مختلفتَين بحرفٍ واحدٍ من المخرج نفسِه (أو المجاور)
    for name, mode in ((PHON1, "same"), (PHON2, "adj")):
        c2 = SC.config_for("proposed", riwaya)
        c2.phon, c2.phon_cap = mode, 99
        by_len = collections.defaultdict(list)
        for f in all_forms:
            by_len[len(f)].append(f)
        acc = {}
        for L, fs in by_len.items():
            for a in fs:
                for b in fs:
                    if a >= b:
                        continue
                    if SCR._phon_ok(a, b, c2):
                        acc.setdefault(a, set()).add(b)
                        acc.setdefault(b, set()).add(a)
        for k, fs in forms.items():
            n = occ[k]
            hit = False
            for f in fs:
                for g in acc.get(f, ()):
                    if by_form.get(g, set()) - {k}:
                        hit = True
                        break
                if hit:
                    break
            if hit:
                out[name] += n
                uniq[name] += 1
    return out, uniq, tot_pos, len(forms)


def table(rows, title):
    """rows = [(مرجع · مسموع · رواية · بند · تكرار · صنف · تفصيل · كلمةٌ أخرى)]"""
    print(f"\n### 🔖 {title}\n")
    print("| كلمةُ المرجع | ما سُمع | الصنف | البابُ الذي يغفره | كلمةٌ أخرى؟ | تكراراً | مثالُ بند | تفصيل |")
    print("|---|---|---|---|:---:|---:|---|---|")
    kinds = collections.Counter()
    others = collections.Counter()
    for ref, heard, _riw, _item, c, kind, det, other, _head in rows:
        kinds[kind] += c
        if other:
            others[kind] += c
        print(f"| `{ref}` | `{heard}` | {kind} | {DOOR.get(kind, '—')} | "
              f"{'⛔ نعم' if other else '—'} | {c} | `{_item or '—'}` | {det} |")
    heads = collections.Counter()
    for r in rows:
        if r[5] == HEAD and len(r) > 8 and r[8]:
            heads[r[8]] += r[4]
    print(f"\n**الحصيلة** ({sum(kinds.values())} خطأً):\n")
    print("| الصنف | خطأً | منها كلمةٌ قرآنيّةٌ أخرى | البابُ |")
    print("|---|---:|---:|---|")
    for kind, n in kinds.most_common():
        print(f"| {kind} | {n} | {others.get(kind, 0)} | {DOOR.get(kind, '—')} |")
    if heads:
        print("\n**وصدورُ البتر** (‏ما سقط من أوّل الكلمة) — كلُّ صدرٍ **بابٌ ضيّقٌ** سعرُه يُقاس وحده:\n")
        print("| الصدرُ الساقط | خطأً |")
        print("|---|---:|")
        for hh, n in heads.most_common():
            print(f"| `{hh}` | {n} |")
    return kinds, others, heads


def parse_item(iid):
    """`long_<رواية>_<سورة>_<أوّلُ آية>x<عدد>` ⇒ (‏رواية · سورة · أوّل آيةٍ · عدد) — أو None.

    (‏وهي صيغةُ `build_long.py` حرفاً بحرف: آياتٌ **متتاليةٌ** من سورةٍ واحدة.)
    """
    try:
        parts = iid.split("_")
        if len(parts) < 4 or parts[0] != "long":
            return None
        riw = parts[1]
        surah = int(parts[2])
        tail = parts[3]
        first, n = tail.split("x")
        return riw, surah, int(first), int(n)
    except Exception:
        return None


def item_words(iid, load_text, index):
    """كلماتُ مرجعِ البند كما بناه `build_long.py` — من المصحف لا من الفرضيّات."""
    got = parse_item(iid)
    if not got:
        return None, None
    riw, surah, first, n = got
    start = {x["n"]: x["start"] for x in index["surahs"]}
    if surah not in start:
        return None, None
    text = load_text(riw)
    words = []
    for a in range(first, first + n):
        j = start[surah] + a - 1
        if j >= len(text):
            return None, None
        words += text[j].split()
    return riw, words


def where_stats(rows, SCR=None, SC=None):
    """🧭 **الكلمةُ التي سُمعت مكانَ غيرها: أمِن البند نفسِه أم من خارجه؟**

    فإن كانت **من كلمات البند** (‏وقريبةً من موضع المرجع) فالشبهةُ **محاذاةٌ أو تكرارُ
    كلمةٍ**، وإن لم تكن فيه البتّة فهي **سمعٌ** أتى بكلمةٍ من مكانٍ آخرَ من المصحف.
    ⚠️ **وهذا مُرجِّحٌ لا برهان**: وجودُها في البند قد يكون مصادفةً في كلماتٍ شائعة
    (`قل` · `ان`) ⇒ **تُقرأ المسافةُ مع الوجود**، والشائعُ يُسمّى.
    """
    if SCR is None or SC is None:
        SCR, SC = _mods()
    from common import load_text, load_index
    index = load_index()
    # ⛔⛔ **وضابطُ المصادفة — سُئل بعد قياس 11:21Z ولم يكن مسؤولاً قبلَه:** «في البند» وحدَها
    #     لا تُقرأ محاذاةً، فكلمةٌ شائعةٌ (`من` · `ان` · `وما`) توجد في **معظم** البنود
    #     بالمصادفة. ⇒ يُقاس لكلّ مسموعٍ **أيوجد في بندٍ آخرَ من الرواية نفسِها** (دورانٌ
    #     بخطوةٍ واحدةٍ على ترتيبٍ مُرتَّبٍ ⇒ **ثابتٌ يُعاد حرفاً**) — فإن تساوى العددان
    #     فـ«في البند» **مصادفةٌ لا محاذاة**، وإن زاد كثيراً فهو أثرٌ حقيقيٌّ يُعالَج بالإرساء.
    #     ⭐ **ورقمٌ بلا أرضيّةِ مصادفةٍ يُقرأ أكبرَ من حقّه** — وهذا بابُ خطإٍ مذكورٌ في دفترنا.
    all_items = sorted({r[3] for r in rows if r[3]})
    bygrp = {}
    for it in all_items:
        g = parse_item(it)
        if g:
            bygrp.setdefault(g[0], []).append(it)
    nxt = {}
    for _g, lst in bygrp.items():
        for i, it in enumerate(lst):
            nxt[it] = lst[(i + 1) % len(lst)] if len(lst) > 1 else None
    wcache = {}

    def _words(it):
        if it not in wcache:
            wcache[it] = item_words(it, load_text, index)
        return wcache[it]
    out = []
    for ref, heard, riw, item, c, kind, det, other, _head in rows:
        if heard in (None, "—", "") or not item:
            continue
        riw2, words = _words(item)
        if not words:
            out.append((ref, heard, item, "؟ بندٌ لم يُبنَ", None, c, None))
            continue
        cfg = SC.config_for("proposed", riw2 or riw)
        h = SCR.norm(heard, cfg)
        hits = [i for i, w in enumerate(words) if h in forms_of(w, cfg, SCR)]
        refs = [i for i, w in enumerate(words) if w == ref]
        # أرضيّةُ المصادفة: أيوجد المسموعُ في **بندٍ آخر**؟ (‏`None` = لا بندَ ثانيَ للرواية)
        alt = nxt.get(item)
        chance = None
        if alt:
            _r3, aw = _words(alt)
            chance = bool(aw) and any(h in forms_of(w, cfg, SCR) for w in aw)
        # ⛔⛔ **ضابطٌ سالبٌ يسبق كلَّ حكم:** إن لم تُوجد **كلمةُ المرجع نفسُها** في البند
        #     المُعادِ بناؤه فالبناءُ خاطئٌ (‏رواية/سورة/نافذة) ⇒ **«لم يُقَس»** لا «من خارجه»،
        #     وإلّا صار «صفرُ التقاطع» أثرَ عطبٍ في الأداة لا حكماً على البيانات.
        if not refs:
            out.append((ref, heard, item, "؟ المرجعُ ليس في البند (‏لا يُحكم)", None, c, chance))
            continue
        if not hits:
            out.append((ref, heard, item, "من خارج البند", None, c, chance))
            continue
        d = min(abs(i - j) for i in hits for j in refs)
        out.append((ref, heard, item, "**في البند**", d, c, chance))
    return out


def where_table(rows, SCR=None, SC=None):
    res = where_stats(rows, SCR, SC)
    print("\n### 🧭 الكلمةُ المسموعةُ — أمِن البند نفسِه أم من خارجه؟\n")
    print("| كلمةُ المرجع | ما سُمع | البند | أين وُجدت | مسافةُ كلماتٍ عن المرجع | تكراراً |")
    print("|---|---|---|---|---:|---:|")
    tally = collections.Counter()
    chance_n = chance_hit = 0
    for ref, heard, item, where, d, c, chance in res:
        tally[where] += c
        if not where.startswith("؟") and chance is not None:
            chance_n += c
            chance_hit += c if chance else 0
        print(f"| `{ref}` | `{heard}` | `{item}` | {where} | "
              f"{'—' if d is None else d} | {c} |")
    print("\n**الحصيلة:**\n")
    print("| أين | خطأً |")
    print("|---|---:|")
    for k, v in tally.most_common():
        print(f"| {k} | {v} |")
    unchecked = sum(v for k, v in tally.items() if k.startswith("؟"))
    total = sum(tally.values())
    judged = total - unchecked
    inside = tally.get("**في البند**", 0)
    if chance_n:
        print(f"\n🎲 **أرضيّةُ المصادفة** (‏المسموعُ في **بندٍ آخرَ** من الرواية نفسِها · دورانٌ "
              f"بخطوةٍ واحدةٍ ثابتة): **{chance_hit} من {chance_n}** "
              f"({100.0 * chance_hit / chance_n:.1f}٪) مقابل **في البند** "
              f"{inside} من {judged} ({100.0 * inside / judged if judged else 0:.1f}٪). "
              "⇒ فإن تقاربا فـ«في البند» **مصادفةٌ لا محاذاة**، وإن زاد الثاني كثيراً فهو "
              "أثرٌ يُعالَج بالإرساء. ⭐ **ورقمٌ بلا أرضيّةِ مصادفةٍ يُقرأ أكبرَ من حقّه.**")
    else:
        print("\n⚠️ **ولا أرضيّةَ مصادفةٍ في هذه القراءة** (‏بندٌ واحدٌ للرواية أو لم تُبنَ "
              "البنودُ) ⇒ «في البند» **تُقرأ سقفاً لا وسطاً**.")
    print(f"\n🧪 **الضابطُ السالب:** وُجدت كلمةُ المرجع نفسُها في البند المُعادِ بنائه في "
          f"**{total - unchecked} من {total}** ⇒ البناءُ سليمٌ فيها، **وما لم يُوجَد فيه المرجعُ "
          f"لا يُحكم عليه**. (‏ولولا هذا الضابطُ لقُرئ «صفرُ تقاطعٍ» حكماً وهو قد يكون عطبَ بناءٍ.)")
    return res, tally


def from_pairs(path):
    data = json.load(open(path, encoding="utf-8"))
    out = []
    for d in data:
        out.append((d["ref"], d.get("heard"), d.get("riwaya", "warsh"),
                    d.get("item", ""), int(d.get("count", 1))))
    return out


def floor_positions(dirs, arms, sets):
    """🧱 **مواضعُ الأرضيّة بأعيانها** — (بندٌ · ترتيبُ الكلمة · المرجعُ · ما سُمع) لكلِّ ذراع.

    ⭐ **لِمَ موضعٌ لا نسبة؟** D-392 أرت أنّ الفرقَ المجملَ (+0.14) **يُخفي انقساماً**
    (‏قالونُ يرتفع وورشٌ يهبط). والموضعُ لا يُخفي شيئاً: ذراعٌ جديدةٌ تُقاس بـ«كم موضعاً
    من الأرضيّة أصلحتْ وكم موضعاً جديداً أحدثتْ» — **فلا يختبئ كسرٌ خلف إصلاح**.
    """
    SCR, SC = _mods()
    import v2_gate as G
    out = {}
    for d in dirs:
        G.WORK = d
        pool = G.pool_items()
        for st in sets:
            key = st if st.startswith(("g1", "g4")) else st.replace("-", ":", 1)
            for arm in arms:
                hyps = G.load_hyps(key, arm)
                if not hyps:
                    continue
                rows = []
                seen_items = []
                for it in [x for x in pool if x["id"] in hyps]:
                    h = hyps.get(it["id"]) or {}
                    if h.get("text") is None or "error" in h:
                        continue
                    riw = it.get("riwaya")
                    ref = it["refText"].split()
                    seen_items.append(it["id"])       # 🧾 **التغطيةُ تُسجَّل ولو بلا خطأ**
                    sc = SCR.score(ref, h["text"], SC.config_for("proposed", riw))
                    for w in sc.get("words", []):
                        if not w or w[1] not in (SCR.MISSED, SCR.SUBSTITUTED):
                            continue
                        rows.append({"item": it["id"], "idx": w[0], "riwaya": riw,
                                     "ref": ref[w[0]] if w[0] < len(ref) else "?",
                                     "heard": w[2], "status": w[1]})
                if seen_items:
                    out[(st, arm)] = {"rows": rows, "items": sorted(seen_items)}
    return out


def floor_compare(base_rows, arm_rows, shared=None):
    """(‏مثبَّتٌ · مُصلَحٌ · جديدٌ) بمقارنة **المواضع** لا الأعداد.

    ⛔⛔ **وعلى البنود المشتركة وحدَها متى عُرفت** (`shared`): بندٌ لم تقرأه الذراعُ أصلاً
    **ليس بنداً أصلحتْه** — ولولا هذا القيدُ لقرأنا نقصَ التغطية «إصلاحاً»، وهو أخطرُ
    ما في هذا الجدول لأنّه يكذب في الاتّجاه المُرضي.
    """
    b = {(r["item"], r["idx"]) for r in base_rows}
    a = {(r["item"], r["idx"]) for r in arm_rows}
    if shared is not None:
        sh = set(shared)
        b = {x for x in b if x[0] in sh}
        a = {x for x in a if x[0] in sh}
    return sorted(b & a), sorted(b - a), sorted(a - b)


def floor_table(floor, arm_rows, arm_name, base_name, floor_items=None, arm_items=None):
    """جدولُ المقابلة — ومعه **تغطيةُ البنود** صراحةً (‏وبلا تغطيةٍ يُقال «لم تُعرَف»)."""
    base_items = set(floor_items) if floor_items else {r["item"] for r in floor}
    a_items = set(arm_items) if arm_items is not None else {r["item"] for r in arm_rows}
    shared = base_items & a_items
    kept, fixed, new = floor_compare(floor, arm_rows, shared)
    print(f"\n### 🧱 مقابلةُ الأرضيّة — `{arm_name}` في مواجهة أرضيّة `{base_name}`\n")
    print("| | عددٌ |")
    print("|---|---:|")
    print(f"| بنودُ الأرضيّة {'(‏تغطيةٌ مسجَّلة)' if floor_items else '**(‏من بنود الخطأ وحدَها — التغطيةُ لم تُسجَّل)**'} | {len(base_items)} |")
    print(f"| بنودُ الذراع | {len(a_items)} |")
    print(f"| **بنودٌ مشتركةٌ** (‏وعليها وحدَها يُحكم) | **{len(shared)}** |")
    print(f"| مواضعُ الأرضيّة في المشترك | {len(kept) + len(fixed)} |")
    print(f"| **مثبَّتٌ** (‏بقي خطأً) | {len(kept)} |")
    print(f"| **مُصلَحٌ** | {len(fixed)} |")
    print(f"| **جديدٌ** (‏كسرٌ أحدثتْه) | {len(new)} |")
    if not shared:
        print("\n⛔ **لا بندَ مشتركاً ⇒ لا حكمَ** (‏والصفرُ أعلاه «لم يُقَس» لا «لا خطأ»).")
        return kept, fixed, new
    if len(shared) < len(base_items):
        print(f"\n⚠️ **والذراعُ لم تقرأ {len(base_items) - len(shared)} بنداً من الأرضيّة** — "
              f"وقد أُخرجت من الحساب كي لا يُقرأ نقصُ التغطية «إصلاحاً».")
    if not floor_items:
        print("\n⚠️ **وتغطيةُ الأرضيّة نفسِها غيرُ مسجَّلة** (‏ملفٌّ كُتب قبل تسجيلها) ⇒ بنودُها "
              "هنا **بنودُ خطئها** لا كلُّ ما قرأتْه؛ ويزول هذا القيدُ بأوّل أرضيّةٍ تُكتب بعد اليومَ.")
    net = len(fixed) - len(new)
    print(f"\n**المحصّلة:** {'+' if net > 0 else ''}{net} موضعاً. ⛔ **ولا يُقرأ «أصلحَ» وحدَه**: "
          f"ذراعٌ تُصلح {len(fixed)} وتكسر {len(new)} ليست أفضلَ بـ{len(fixed)} (‏درسُ D-392).")
    return kept, fixed, new


def from_dirs(dirs, arms, sets):
    """الأزواجُ من الفرضيّات المحفوظة — بالحاكم نفسِه الذي يحكم به الشوط.

    ⛔ **وصيغةُ `--dirs` هي صيغةُ التشريح نفسُها** (`work:`) ⇒ يُقطع ما بعد النقطتَين
    ويُجعل المسارُ مطلقاً كما في `drift_probe` حرفاً بحرف. **وقد وقع العطبُ فعلاً:**
    مُرِّر `work:` كما هو فصار المجلَّدُ `work:/…` فلا فرضيّةً وُجدت، **وخرجت الخطوةُ
    بصفرِ ثانيةٍ «ناجحةً»** وجدولُها فارغ (الشوط `34795058366`).
    """
    SCR, SC = _mods()
    import v2_gate as G
    out = []
    for d in dirs:
        G.WORK = d
        pool = G.pool_items()
        for st in sets:
            key = st if st.startswith(("g1", "g4")) else st.replace("-", ":", 1)
            for arm in arms:
                hyps = G.load_hyps(key, arm)
                if not hyps:
                    continue
                items = [it for it in pool if it["id"] in hyps]
                cnt = collections.Counter()
                ex = {}
                for it in items:
                    h = hyps.get(it["id"]) or {}
                    if h.get("text") is None or "error" in h:
                        continue
                    riw = it.get("riwaya")
                    ref = it["refText"].split()
                    sc = SCR.score(ref, h["text"], SC.config_for("proposed", riw))
                    for w in sc.get("words", []):
                        if not w or w[1] not in (SCR.MISSED, SCR.SUBSTITUTED):
                            continue
                        k = (ref[w[0]] if w[0] < len(ref) else "?", w[2], riw)
                        cnt[k] += 1
                        ex.setdefault(k, it["id"])
                if cnt:
                    out.append((st, arm, [(r, hd, riw, ex[(r, hd, riw)], c)
                                          for (r, hd, riw), c in cnt.most_common()]))
    return out


def annotate(pairs, SCR=None, SC=None, lex_cache=None):
    if SCR is None or SC is None:
        SCR, SC = _mods()
    from common import load_text
    lex_cache = {} if lex_cache is None else lex_cache
    rows = []
    for ref, heard, riw, item, c in pairs:
        if riw not in lex_cache:
            try:
                lex_cache[riw] = lexicon_of(riw, SC.config_for("proposed", riw), SCR, load_text)
            except Exception as e:                    # نصُّ الرواية غائبٌ ⇒ «لم يُبحَث»
                print(f"⚠️ لم يُبنَ معجمُ `{riw}` ({e}) ⇒ عمودُ «كلمةٌ أخرى» **لم يُبحَث** لا «لا»",
                      file=sys.stderr)
                lex_cache[riw] = set()
        kind, det, other, head = classify(ref, heard, riw, SCR, SC, lex_cache[riw])
        rows.append((ref, heard if heard else "—", riw, item, c, kind, det, other, head))
    return rows


def pair_cost(rows, SCR, SC, load_text):
    """💠 **سعرُ بابٍ مقفَل**: «اغفرْ هذه الأزواجَ بعينها (‏مرجعٌ ⇒ مسموعٌ) ولا شيءَ غيرَها».

    ⭐ **ولِمَ يُقاس هذا البابُ بعد أن سقطت الأبوابُ الثلاثة؟** لأنّ D-390 قاست **أبواباً
    عامّةً** (صنفٌ كاملٌ من الشبه) فكان ثمنُها 44٪–84٪ من مواضع المصحف ⇒ **ردٌّ بالثمن**.
    وهذا بابٌ من جنسٍ آخر: **قائمةٌ مقفلةٌ** لا قاعدة — ثمنُها **محصورٌ ببنائه** في مواضع
    الكلمة المرجعيّة وحدَها، فيُقاس ولا يُظنّ. (‏وD-389: أخطاءُ النظيف **ثابتةُ الموضع**
    ×13.3 ⇒ قائمةٌ مقفلةٌ هي الشكلُ الذي يناسبها، لا رخصةٌ عامّة.)

    ⇒ يُعيد لكلّ رواية: الأزواجَ الفريدةَ · و**مواضعَ يبلغها البابُ** (‏تكرارُ المرجع في
    النصّ: عند كلِّ واحدٍ منها يصير المسموعُ مقبولاً) · و**مواضعَ عمًى** منها: ما يكون
    المسموعُ فيه **صورةَ كلمةٍ قرآنيّةٍ أخرى** ⇒ زلّةٌ حقيقيّةٌ تُبتلَع.

    ⛔ **وحدُّه يُقال:** غفرانُ لا-كلمةٍ ثمنُه **صفرٌ بهذه العملة** ولا يعني «بلا ثمنٍ
    البتّة»: يبقى احتمالُ أن يُخرج فكُّ ترميزٍ **لتلاوةٍ خاطئةٍ** الرمزَ نفسَه — وذلك
    **لا يُقاس من نصٍّ** بل بذراعٍ على صوتٍ مُحقَن، وضابطُه أدناه (`plan_collisions`).
    """
    out = {}
    for riw in sorted({r["riwaya"] for r in rows}):
        cfg = SC.config_for("proposed", riw)
        occ, forms = counts_of(riw, cfg, SCR, load_text)
        by_form = collections.defaultdict(set)
        for k, fs in forms.items():
            for f in fs:
                by_form[f].add(k)
        pairs, seen = [], set()
        mute = accepted = 0
        for r in rows:
            if r["riwaya"] != riw:
                continue
            heard = (r.get("heard") or "").strip()
            if heard in ("", "—"):
                mute += 1                      # صفرُ نصٍّ: لا زوجَ يُغفر — البابُ لا يبلغه
                continue
            fsr = forms_of(r["ref"], cfg, SCR)
            k, h = fsr[0], SCR.norm(heard, cfg)
            if SCR._matches(fsr, h, cfg):
                accepted += 1                  # مقبولٌ أصلاً ⇒ العطبُ في خطِّ القراءة
                continue
            if (k, h) in seen:
                continue
            seen.add((k, h))
            others = by_form.get(h, set()) - {k}
            pairs.append((k, h, occ.get(k, 0), sorted(others)[:2]))
        out[riw] = {
            "pairs": pairs,
            "reach": sum(p[2] for p in pairs),
            "blind": sum(p[2] for p in pairs if p[3]),
            "total": sum(occ.values()),
            "mute": mute,
            "accepted": accepted,
        }
    return out


def pair_generalize(rows, SCR, SC, load_text):
    """⛔⛔ **أتُعمَّم القائمةُ أم تحفظ عيّنتَها؟ — والفرقُ بينهما قياسٌ لا رأي.**

    قائمةٌ مقفلةٌ **مبنيّةٌ من العيّنة التي تُقاس عليها** تكسب دائماً (‏تغفر ما رأته) ⇒ **والرقمُ
    كذبٌ**. فالسؤالُ: لو بُنيت من **نصفِ البنود** كم تغفر من أخطاء **النصف الآخر**؟ والقسمةُ
    **ثابتةٌ لا عشوائيّة** (‏بالتناوب على ترتيبٍ مُرتَّب) كي يُعاد الرقمُ حرفاً.

    ويُقاس شكلان: **بالزوج** (مرجعٌ ⇒ مسموعٌ بعينه) و**بالمرجع** (اغفرْ لهذه الكلمةِ أيَّ
    سماع) — فإن كان الأوّلُ صفراً والثانيُ أكبرَ منه فالمتكرّرُ **الكلمةُ** لا **السماعُ**،
    ⇒ والشكلُ الذي يُعمَّم هو الأغلى، ⛔ فلا يُقترح قبل أن يُسعَّر بدوره.
    """
    cfgs, keyed = {}, []
    for r in rows:
        riw = r["riwaya"]
        if riw not in cfgs:
            cfgs[riw] = SC.config_for("proposed", riw)
        heard = (r.get("heard") or "").strip()
        if heard in ("", "—"):
            continue
        fs = forms_of(r["ref"], cfgs[riw], SCR)
        h = SCR.norm(heard, cfgs[riw])
        if SCR._matches(fs, h, cfgs[riw]):
            continue
        keyed.append((r.get("item", ""), riw, fs[0], h))
    items = sorted({k[0] for k in keyed})
    halves = (set(items[0::2]), set(items[1::2]))
    out = []
    for i, build in enumerate(halves):
        test = [k for k in keyed if k[0] not in build]
        pairs = {(k[1], k[2], k[3]) for k in keyed if k[0] in build}
        refs = {(k[1], k[2]) for k in keyed if k[0] in build}
        out.append({
            "name": f"النصفُ {i + 1}",
            "built": len(pairs),
            "n": len(test),
            "by_pair": sum(1 for k in test if (k[1], k[2], k[3]) in pairs),
            "by_ref": sum(1 for k in test if (k[1], k[2]) in refs),
        })
    uniq_refs = len({(k[1], k[2]) for k in keyed})
    return out, len(keyed), uniq_refs


def abstain_stats(rows, SCR, SC, load_text, plans=()):
    """🤫 **«غيرُ متبيَّن» بدل «أخطأت» — أرخصُ صورةٍ للامتناع، وتُقاس بلا احتمالاتٍ أصلاً.**

    D-444 قاست أنّ أخطاءَ الضجيج **سمعٌ من خارج البند**، وأكثرُها في العين **ليست كلمةً
    عربيّةً** (`سسنسا` · `رفهثا` · `جسهيد`). وأغلى رافعةٍ باقيةٍ هي **الامتناع**: أن يقول
    المحركُ «لم أتبيّن» لا «أخطأت». وثقةُ الرموز تحتاج مسباراً في التطبيق **لم يُطبع بعد**،
    ⇒ فهذه **وكيلٌ نصّيٌّ لا يحتاج احتمالاً**: *أهو كلمةٌ من المصحف أصلاً؟*

    ويُعيد لكلّ رواية: `no_word` (‏المسموعُ **ليس** صورةَ أيّ كلمةٍ في نصّ الرواية ⇒ يصلح
    للامتناع) · `word` (‏كلمةٌ قرآنيّةٌ قائمةٌ ⇒ **لا يُمتنع عنه**: خطأٌ يُقال) · `mute`.

    ⛔⛔ **وثمنُه يُقاس ولا يُظنّ:** لو امتنع المحركُ عن كلّ لا-كلمةٍ، **فأيُّ خطإٍ حقيقيٍّ
    يُكتَم؟** وضابطُنا المتاح: `SUBSTITUTE` في خطط الحقن **يُبدل كلمةً بكلمةٍ قرآنيّةٍ أخرى
    بصوت القارئ** ⇒ إن كان مانحُها **كلمةً** فالامتناعُ لا يكتمها. ⚠️ **وهذا لا يقيس نطقاً
    خاطئاً من طالبٍ حقيقيّ** (‏لا مادّةَ لنا فيه) — وذلك **أخطرُ ما يُقال في هذا الباب**:
    نطقٌ فاسدٌ قد يُفرَّغ لا-كلمةً فيُكتَم عن صاحبه. ⇒ **لا يُشحن بهذا وحدَه.**
    """
    out = {}
    for riw in sorted({r["riwaya"] for r in rows}):
        cfg = SC.config_for("proposed", riw)
        lex = lexicon_of(riw, cfg, SCR, load_text)
        d = {"n": 0, "no_word": 0, "word": 0, "mute": 0, "examples": []}
        for r in rows:
            if r["riwaya"] != riw:
                continue
            heard = (r.get("heard") or "").strip()
            if heard in ("", "—"):
                d["mute"] += 1
                continue
            d["n"] += 1
            h = SCR.norm(heard, cfg)
            if h in lex:
                d["word"] += 1
            else:
                d["no_word"] += 1
                if len(d["examples"]) < 6:
                    d["examples"].append(h)
        out[riw] = d
    # 🧪 الضابط: مانحُ كلِّ إبدالٍ مصنوعٍ — أهو كلمةٌ (‏فلا يُكتَم) أم لا؟
    ctrl = {"n": 0, "word": 0, "no_word": 0}
    lexc = {}
    for p in plans:
        try:
            items = json.load(open(p, encoding="utf-8")).get("items", [])
        except Exception:
            continue
        for it in items:
            if it.get("op") != "SUBSTITUTE":
                continue
            dw = (it.get("donor") or {}).get("word") or ""
            if not dw:
                continue
            riw = it.get("riwaya", "hafs")
            if riw not in lexc:
                cfg = SC.config_for("proposed", riw)
                try:
                    lexc[riw] = (cfg, lexicon_of(riw, cfg, SCR, load_text))
                except Exception:
                    lexc[riw] = (cfg, set())
            cfg, lex = lexc[riw]
            ctrl["n"] += 1
            if SCR.norm(dw, cfg) in lex:
                ctrl["word"] += 1
            else:
                ctrl["no_word"] += 1
    return out, ctrl


def abstain_report(rows, plans=()):
    """يطبع جدولَ الامتناع النصّيّ وضابطَه — **كشفٌ لا شحنٌ**."""
    SCR, SC = _mods()
    from common import load_text
    out, ctrl = abstain_stats(rows, SCR, SC, load_text, plans)
    print("\n#### 🤫 **وكيلُ الامتناع النصّيّ** — أهو كلمةٌ من المصحف أصلاً؟ (‏بلا احتمالاتٍ)\n")
    print("| الرواية | أخطاءٌ فيها نصٌّ | **ليست كلمةً** ⇒ يصلح للامتناع | كلمةٌ قرآنيّةٌ ⇒ خطأٌ يُقال | صفرُ نصٍّ | أمثلة |")
    print("|---|---:|---:|---:|---:|---|")
    tn = tnw = 0
    for riw, d in out.items():
        pct = 100.0 * d["no_word"] / d["n"] if d["n"] else 0.0
        tn += d["n"]; tnw += d["no_word"]
        print(f"| `{riw}` | {d['n']} | **{d['no_word']}** ({pct:.1f}٪) | {d['word']} | {d['mute']} | "
              + " · ".join(f"`{x}`" for x in d["examples"]) + " |")
    if tn:
        print(f"\n⇒ **الحصيلة: {tnw} من {tn} ({100.0 * tnw / tn:.1f}٪)** من الاتّهامات يصلح "
              "أن يصير «لم أتبيّن» بلا احتمالٍ ولا عتبةٍ جديدة.")
    if ctrl["n"]:
        print(f"\n🧪 **الضابطُ (ثمنُ الامتناع على عطبٍ مصنوع):** مانحو **{ctrl['n']}** إبدالاً: "
              f"**{ctrl['word']}** كلماتٌ قرآنيّةٌ (‏**لا تُكتَم**) · {ctrl['no_word']} ليست. "
              f"⇒ الامتناعُ يكتم **{100.0 * ctrl['no_word'] / ctrl['n']:.1f}٪** من الإبدالات المصنوعة.")
    else:
        print("\n⛔ **ولا ضابطَ في هذه القراءة** (‏لم تُقرأ خطّةٌ) ⇒ الثمنُ **لم يُقَس**.")
    print("\n⚠️⚠️ **وأخطرُ ما يُقال في هذا الباب:** الإبدالُ المصنوعُ **صوتٌ صحيحٌ لكلمةٍ أخرى**، "
          "أمّا **نطقُ طالبٍ فاسدٌ** فقد يُفرَّغ **لا-كلمةً** فيُكتَم عن صاحبه — **ولا مادّةَ "
          "عندنا تقيسه**. ⇒ **لا يُشحن الامتناعُ بهذا وحدَه**، ويبقى قياسُ الثقة (`RafiqConf`) "
          "هو الحكم.")
    return out, ctrl


def pair_against(rows, other, SCR, SC, load_text):
    """🎯 **قائمةٌ من أرضيّةٍ تُقاس على أرضيّةٍ أخرى** — الخطوةُ التي سمّتها D-443 بنصّها.

    القسمةُ الداخليّةُ (`pair_generalize`) تحجب **البناءَ** ولا تحجب **الصوتَ والنموذج**:
    بنودُ النصفَين من المجموعة والذراع نفسِهما. وهذه تحجب المجموعةَ كلَّها (‏`g4` ⇒ `g4n`
    المضجَّجة · أو ملحٌ آخر) ⇒ **فهي الشهادةُ التي يُبنى عليها شحنٌ، لا القسمة.**

    ⛔ **ولا يُقرأ صفرُ تغطيةٍ «ثمناً»**: هو خبرٌ عن **الكسب** وحدَه (‏القائمةُ لا تغفر أخطاءَ
    هذه الأرضيّة) — والثمنُ مصحفيٌّ قِيس في `pair_cost` ولا يتغيّر بأرضيّة.
    """
    def keys(rs):
        cfgs, out = {}, []
        for r in rs:
            riw = r.get("riwaya", "")
            if riw not in cfgs:
                cfgs[riw] = SC.config_for("proposed", riw)
            heard = (r.get("heard") or "").strip()
            if heard in ("", "—"):
                continue
            fs = forms_of(r["ref"], cfgs[riw], SCR)
            h = SCR.norm(heard, cfgs[riw])
            if SCR._matches(fs, h, cfgs[riw]):
                continue
            out.append((riw, fs[0], h))
        return out
    built = set(keys(rows))
    refs = {(a, b) for a, b, _ in built}
    tgt = keys(other)
    return {
        "built": len(built),
        "n": len(tgt),
        "by_pair": sum(1 for k in tgt if k in built),
        "by_ref": sum(1 for k in tgt if (k[0], k[1]) in refs),
        "mute": sum(1 for r in other if (r.get("heard") or "").strip() in ("", "—")),
    }


def plan_collisions(pair_out, SCR, SC, plans):
    """⛔⛔ **الضابطُ السالبُ للبابِ المقفل — ولا يُقترح بابٌ بلا هذا السؤال:**

    أيغفر هذا البابُ **عطباً مصنوعاً في خططنا** (‏`SUBSTITUTE`: كلمةٌ أُبدلت بكلمةِ آيةٍ
    أخرى بصوت القارئ نفسِه)؟ فإن وافق زوجٌ من القائمة زوجَ حقنٍ ⇒ **القائمةُ تعمي عن خطإٍ
    مكتوبٍ في حقيقتنا الأرضيّة**، وذلك ردٌّ لا نقاش فيه.

    ⇒ `(عددُ الإبدالات المفحوصة، قائمةُ التوافقات)`. والمقابلةُ **باتّحاد الأزواج عبر
    الروايات** (أقسى قراءةٍ) لا برواية كلِّ خطّةٍ وحدَها.
    """
    allow = set()
    for d in pair_out.values():
        for k, h, _n, _o in d["pairs"]:
            allow.add((k, h))
    hits, checked = [], 0
    for p in plans:
        try:
            items = json.load(open(p, encoding="utf-8")).get("items", [])
        except Exception as e:
            hits.append(("⛔ لم تُقرأ الخطّة", os.path.basename(p), str(e)))
            continue
        for it in items:
            if it.get("op") != "SUBSTITUTE":
                continue
            dw = (it.get("donor") or {}).get("word") or ""
            tw = it.get("targetWord") or ""
            if not dw or not tw:
                continue
            checked += 1
            cfg = SC.config_for("proposed", it.get("riwaya", "hafs"))
            k = forms_of(tw, cfg, SCR)[0]
            h = SCR.norm(dw, cfg)
            if (k, h) in allow:
                hits.append((it.get("id", "?"), k, h))
    return checked, hits


def pair_report(rows, plans=(), items=(), against=None, against_name=""):
    """يطبع جدولَ البابِ المقفل وضابطَه السالب — ولا يُشحن منه شيء."""
    SCR, SC = _mods()
    from common import load_text
    out = pair_cost(rows, SCR, SC, load_text)
    print("\n### 💠 سعرُ **بابٍ مقفَل** — «اغفرْ هذه الأزواجَ بعينها ولا شيءَ غيرَها»\n")
    print("| الرواية | أزواجٌ فريدة | مواضعُ يبلغها البابُ | **مواضعُ عمًى** | من النصّ | "
          "لا يبلغها (صفرُ نصٍّ · مقبولٌ أصلاً) |")
    print("|---|---:|---:|---:|---:|---:|")
    for riw, d in out.items():
        pct = 100.0 * d["blind"] / d["total"] if d["total"] else 0.0
        print(f"| `{riw}` | {len(d['pairs'])} | {d['reach']} | **{d['blind']}** | {pct:.3f}٪ | "
              f"{d['mute']} · {d['accepted']} |")
    for riw, d in out.items():
        risky = [p for p in d["pairs"] if p[3]]
        if risky:
            print(f"\n⛔ **وأزواجُ `{riw}` التي المسموعُ فيها كلمةٌ قرآنيّةٌ أخرى** "
                  "(‏هذه وحدَها ثمنُ الباب):")
            for k, h, n, o in risky:
                print(f"   ⛔ `{k}` ⇒ `{h}` — و`{h}` صورةُ {' · '.join(f'`{x}`' for x in o)} "
                      f"· مواضعُ `{k}`: {n}")
    # ⭐⭐ **والثمنُ ليس خاصّيّةَ «القائمةِ المقفلة» بل خاصّيّةُ تكرارِ مرجعها:** زوجٌ واحدٌ
    #    مرجعُه كلمةٌ عاليةُ التكرار يكلّف أكثرَ من كلِّ ما سواه مجتمعاً ⇒ يُقاس السعرُ
    #    **بسقوفِ تكرارٍ** لا برقمٍ واحد، فيُرى الحدُّ الذي يصير عنده البابُ رخيصاً.
    caps = [0, 100, 20, 5]
    print("\n#### 📉 والسعرُ بسقفِ تكرارِ المرجع (‏0 = بلا سقف) — **زوجٌ واحدٌ ثمنُه أكثرُ من الباقي**\n")
    print("| الرواية | السقف | أزواجٌ باقية | مواضعُ يبلغها | **مواضعُ عمًى** | من النصّ |")
    print("|---|---:|---:|---:|---:|---:|")
    for riw, d in out.items():
        for c in caps:
            keep = [p for p in d["pairs"] if not c or p[2] <= c]
            blind = sum(p[2] for p in keep if p[3])
            pct = 100.0 * blind / d["total"] if d["total"] else 0.0
            print(f"| `{riw}` | {'—' if not c else c} | {len(keep)} | "
                  f"{sum(p[2] for p in keep)} | **{blind}** | {pct:.4f}٪ |")
    gen, n_keyed, uniq_refs = pair_generalize(rows, SCR, SC, load_text)
    print("\n#### 🔍 **أتُعمَّم أم تحفظ؟** — تُبنى القائمةُ من نصفِ البنود وتُقاس على النصف الآخر\n")
    print("| بُنيت من | أزواجٌ فيها | أخطاءُ النصف الآخر | يغفرها **بالزوج** | يغفرها **بالمرجع** |")
    print("|---|---:|---:|---:|---:|")
    for g in gen:
        print(f"| {g['name']} | {g['built']} | {g['n']} | **{g['by_pair']}** | **{g['by_ref']}** |")
    print(f"\n⭐ **وبنيةُ العيّنة:** {n_keyed} خطأً يقبل الغفرانَ · **{uniq_refs}** مرجعاً "
          "فريداً ⇒ فكلُّ مرجعٍ يُخطأ فيه مرّةً أو مرّتَين. **والصفرُ في عمود «بالزوج» يعني "
          "حفظاً لا تعلُّماً** — ولا يُشحن ما هذا برهانُه.")
    if against:
        g = pair_against(rows, against, SCR, SC, load_text)
        print(f"\n#### 🎯 **وعلى أرضيّةٍ أخرى محجوبةٍ بتمامها** — `{against_name}`\n")
        print("| القائمةُ من | أزواجٌ فيها | أخطاءُ الأرضيّة الأخرى | يغفرها **بالزوج** | "
              "بالمرجع | صفرُ نصٍّ فيها |")
        print("|---|---:|---:|---:|---:|---:|")
        pct = 100.0 * g["by_pair"] / g["n"] if g["n"] else 0.0
        print(f"| الأرضيّةُ الأولى | {g['built']} | {g['n']} | **{g['by_pair']}** ({pct:.1f}٪) | "
              f"{g['by_ref']} | {g['mute']} |")
        if not g["n"]:
            print("⛔ **صفرُ أخطاءٍ في الأرضيّة الأخرى ⇒ لم يُقَس** (ولا يُقرأ هذا تعميماً).")
        print("⛔ **ولا يُقرأ صفرُ تغطيةٍ ثمناً**: هو خبرٌ عن الكسب وحدَه — والثمنُ مصحفيٌّ "
              "قِيس أعلاه ولا يتغيّر بأرضيّة.")
    checked, hits = plan_collisions(out, SCR, SC, plans)
    print(f"\n🧪 **الضابطُ السالبُ:** قوبلت القائمةُ بـ**{checked}** إبدالاً مصنوعاً في "
          f"خطط الحقن ⇒ **توافقات: {len(hits)}**"
          + ("" if not hits else " ⛔ " + " · ".join(str(h) for h in hits[:5])))
    if not checked:
        print("⛔ **ولا يُقرأ صفرُ توافقٍ سلامةً**: صفرُ إبدالاتٍ مفحوصةٍ يعني أنّ الخططَ "
              "لم تُقرأ — لا أنّ القائمةَ نظيفة.")
    if items:
        nw = 0
        try:
            from common import load_index
            index = load_index()
            for iid in items:
                _riw, ws = item_words(iid, load_text, index)
                nw += len(ws or [])
        except Exception as e:
            print(f"⚠️ لم تُبنَ كلماتُ البنود ({e}) ⇒ **سقفُ الكسب لم يُحسب**")
            nw = 0
        forg = sum(len(d["pairs"]) for d in out.values())
        if nw:
            print(f"\n📐 **وسقفُ الكسب حسابيٌّ لا مقيسٌ على محرّك**: {forg} خطأً يغفرها البابُ "
                  f"من **{nw}** كلمةً في {len(items)} بنداً ⇒ **{100.0 * forg / nw:.2f}** نقطةً "
                  "سقفاً (‏وكلُّ زوجٍ يُغفر مرّةً واحدةً في موضعه، فالسقفُ لا يُبلغ إلّا إن "
                  "تكرّر السماعُ نفسُه). ⛔ **ولا يدخل لوحةَ النتائج رقمٌ لم يُقَس على المحرك.**")
    return out


def cost_report(riwayat, heads=()):
    SCR, SC = _mods()
    from common import load_text
    print("\n### 🔓 بابُ النقل (`ال…` ⇒ `ل…`) — مفتوحٌ في ورشٍ مغلقٌ في قالون\n")
    print("| الرواية | البابُ اليومَ | مواضعُ يبلغها | **مواضعُ عمًى** | من النصّ |")
    print("|---|:---:|---:|---:|---:|")
    for riw in riwayat:
        reach, cost, tot, open_ = naql_cost(riw, SCR, SC, load_text)
        print(f"| `{riw}` | {'مفتوحٌ (مشحون)' if open_ else 'مغلق'} | {reach} | **{cost}** | "
              f"{100.0 * cost / tot:.2f}٪ |")
    if heads:
        print("\n### 🎯 سعرُ **بابٍ ضيّقٍ** لكلِّ صدرٍ ساقطٍ — على نصِّ الرواية كلِّه\n")
        print("| الرواية | الصدرُ | مواضعُ يبلغها البابُ | **مواضعُ عمًى** | من النصّ |")
        print("|---|---|---:|---:|---:|")
        for riw in heads and riwayat:
            cost, reach, tot = head_cost(riw, list(heads), SCR, SC, load_text)
            for hh in heads:
                n = cost.get(hh, 0)
                print(f"| `{riw}` | `{hh}` | {reach.get(hh, 0)} | **{n}** | {100.0 * n / tot:.2f}٪ |")
        print("\n⭐ «مواضعُ يبلغها البابُ» = مواضعُ كلماتٍ تبدأ بهذا الصدر (‏سقفُ ما يمكن أن "
              "يكسبه) · و«مواضعُ عمًى» منها ما يصير فيه المتبقّي **كلمةً قرآنيّةً أخرى**.")
    print("\n### 💰 سعرُ كلِّ بابٍ لو فُتح — على نصِّ الرواية كلِّه (‏عملةُ `license_ledger`(ب))\n")
    print("| الرواية | مواضعُ النصّ | البابُ | مواضعُ عمًى | من النصّ | كلماتٌ فريدة |")
    print("|---|---:|---|---:|---:|---:|")
    for riw in riwayat:
        out, uniq, tot, nu = door_cost(riw, SCR, SC, load_text)
        for d in (HEAD, TAIL, MIDL, MADD, PHON1, PHON2):
            n = out.get(d, 0)
            print(f"| `{riw}` | {tot} | {d} | **{n}** | {100.0 * n / tot:.2f}٪ | {uniq.get(d, 0)}/{nu} |")
    print("\n⭐ **كيف يُقرأ:** «مواضعُ عمًى» = مواضعُ المصحف التي يصير فيها نطقُ **كلمةٍ قرآنيّةٍ "
          "أخرى** مقبولاً لو فُتح البابُ ⇒ **زلّةٌ حقيقيّةٌ تُبتلَع**. وهو **سقفُ الثمن** "
          "(‏المحاذاةُ وحارسُ الانهيار فوقَه يُخفيان أثرَه ولا يُنشئانه — قيدُ `license_ledger`).")


def selftest():
    SCR, SC = _mods()
    ok = True
    # معجمٌ صناعيٌّ صريحٌ كي لا يعتمد الضابطُ على وجود أصول المصحف
    lex = {"الخير", "علي", "قل"}
    cases = [
        # (مرجع, مسموع, رواية, الصنف المنتظر, كلمةٌ أخرى منتظرة)
        ("تَلَهّ۪ىٰ", "تله", "warsh", TAIL, False),          # سقط عجزُ الكلمة
        ("اَ۬لتُّرَاثَ", "تراث", "qalun", HEAD, False),        # سقط صدرُها
        ("وَكَذَّبَ", "واسوكذب", "qalun", GLUE, False),        # جارةٌ لُصقت
        ("اَ۬لْغَيْبِ", "الخير", "warsh", FAR, True),          # كلمةٌ قرآنيّةٌ أخرى تماماً
        ("إِنْ", "قل", "warsh", FAR, True),                    # قصيرةٌ وكلمةٌ أخرى
        ("تَلَهّ۪ىٰ", "دلهي", "warsh", PHON1, False),           # ت⇄د مخرجٌ واحد · وطولُ 4 هو منطقةُ البابِ كلُّها
        ("قَدَّرَ", "قدل", "warsh", ACCEPTED, False),           # ثلاثيّةٌ ⇒ رخصةُ القصيرة تقبلها أصلاً
        ("بِالُافُقِ", "بلفق", "warsh", MADD, False),          # حُذفت ألفان مدّاً لا حرفاً صحيحاً
        ("وَحُقَّتْۖ", "وحك", "qalun", FAR, False),              # حُذف صحيحٌ وأُبدل ⇒ ليس مدّاً ساقطاً
        ("يُسْقَوْنَ", "رول", "warsh", FAR, False),            # لا علاقةَ شكليّة
        ("وَاسْتَغْنَىٰ", None, "qalun", MISS, False),         # صفرُ سمع
        ("ذَٰلِكَ", "ذلك", "warsh", ACCEPTED, False),          # يقبله الحاكمُ ⇒ حارسُ خطِّ القراءة
        ("اَ۬لْكُبْرَىٰ", "لكبرا", "qalun", None, False),      # النقلُ صورةٌ مقبولةٌ في الرواية
    ]
    for ref, heard, riw, want, want_other in cases:
        kind, det, other, _hd = classify(ref, heard, riw, SCR, SC, lex)
        if want is None:                                   # «أيّاً كان الصنف» — يُفحص العمودُ وحدَه
            print(f"ℹ️ `{ref}`⇄`{heard}` ⇒ {kind} · {det}")
        elif kind != want:
            print(f"⛔ `{ref}`⇄`{heard}`: انتُظر {want} فجاء {kind} ({det})")
            ok = False
        if other != want_other:
            print(f"⛔ `{ref}`⇄`{heard}`: عمودُ «كلمةٌ أخرى» انتُظر {want_other} فجاء {other}")
            ok = False
    # ضوابطُ مقابلةِ الأرضيّة — بجوابٍ معلومٍ سلفاً
    base = [{"item": "i1", "idx": 3}, {"item": "i1", "idx": 9}, {"item": "i2", "idx": 0}]
    arm = [{"item": "i1", "idx": 3}, {"item": "i3", "idx": 5}]
    kept, fixed, new = floor_compare(base, arm)
    if (len(kept), len(fixed), len(new)) != (1, 2, 1):
        print(f"⛔ floor_compare: انتُظر (1 · 2 · 1) فجاء ({len(kept)} · {len(fixed)} · {len(new)})")
        ok = False
    if floor_compare(base, base) != (sorted({("i1", 3), ("i1", 9), ("i2", 0)}), [], []):
        print("⛔ floor_compare: ذراعٌ مطابقةٌ يجب أن تعطي صفرَ إصلاحٍ وصفرَ كسر")
        ok = False
    # ⛔ والموضعُ يُميَّز بـ(بندٍ · ترتيب) لا بالكلمة: كلمتان متشابهتان في بندَين موضعان
    if len(floor_compare([{"item": "i1", "idx": 3}], [{"item": "i2", "idx": 3}])[0]) != 0:
        print("⛔ floor_compare: خلط موضعَين مختلفَي البند")
        ok = False
    # ⛔ وضابطُ التغطية: بندٌ لم تقرأه الذراعُ ليس بنداً أصلحتْه
    b2 = [{"item": "i1", "idx": 1}, {"item": "i2", "idx": 2}]
    a2 = [{"item": "i1", "idx": 1}]
    k2, f2, n2 = floor_compare(b2, a2, shared={"i1"})
    if (len(k2), len(f2), len(n2)) != (1, 0, 0):
        print(f"⛔ التغطية: بندٌ غائبٌ عُدّ إصلاحاً — جاء ({len(k2)} · {len(f2)} · {len(n2)})")
        ok = False
    k3, f3, n3 = floor_compare(b2, a2)      # بلا قيدٍ ⇒ يُقرأ «أصلح» كذباً (‏وهو ما نمنعه)
    if len(f3) != 1:
        print("⛔ الضابطُ نفسُه فاسدٌ: بلا قيد التغطية كان يجب أن يظهر «إصلاحٌ» كاذب")
        ok = False
    # ضوابطُ `parse_item` و`where_stats` على نصٍّ صناعيٍّ معلومِ الجواب
    if T_parse := parse_item("long_qalun_092_005x6"):
        if T_parse != ("qalun", 92, 5, 6):
            print(f"⛔ parse_item: جاء {T_parse}")
            ok = False
    else:
        print("⛔ parse_item ردّ None على معرِّفٍ صحيح")
        ok = False
    if parse_item("threads_x") is not None:
        print("⛔ parse_item قبِل معرِّفاً ليس من `build_long`")
        ok = False
    # ⛔ والضابطُ السالبُ: بندٌ لا مرجعَ فيه **لا يُحكم عليه**
    import types
    fake_mod = types.SimpleNamespace()

    def _fake_words(iid, _lt, _ix):
        return "qalun", ["الف", "باء", "جيم"]
    _real = globals()["item_words"]
    globals()["item_words"] = _fake_words
    try:
        rows_in = [("باء", "جيم", "qalun", "long_qalun_001_001x1", 1, FAR, "", False, ""),
                   ("دال", "جيم", "qalun", "long_qalun_001_001x1", 1, FAR, "", False, "")]
        got = where_stats(rows_in, SCR, SC)
        if got[0][3] != "**في البند**" or got[0][4] != 1:
            print(f"⛔ where_stats: انتُظر «في البند» بمسافة 1 فجاء {got[0][3:5]}")
            ok = False
        if not got[1][3].startswith("؟"):
            print(f"⛔ where_stats: بندٌ لا مرجعَ فيه يجب ألّا يُحكم عليه — جاء {got[1][3]}")
            ok = False
        # 🎲 وضابطُ أرضيّة المصادفة: **ببندٍ واحدٍ لا أرضيّةَ** (‏None) · وببندَين تُقاس
        if got[0][6] is not None:
            print(f"⛔ بندٌ واحدٌ للرواية ⇒ لا أرضيّةَ مصادفةٍ ممكنة، فجاء {got[0][6]}")
            ok = False
        rows_2 = [("باء", "جيم", "qalun", "long_qalun_001_001x1", 1, FAR, "", False, ""),
                  ("باء", "جيم", "qalun", "long_qalun_002_001x1", 1, FAR, "", False, "")]
        g2 = where_stats(rows_2, SCR, SC)
        # المُرقِّعُ يُعيد الكلماتِ عينَها لكلّ بند ⇒ المسموعُ في البند **وفي غيره** ⇒ مصادفة
        if g2[0][6] is not True or g2[0][3] != "**في البند**":
            print(f"⛔ أرضيّةُ المصادفة: انتُظر (‏في البند · ووُجد في غيره) فجاء {g2[0][3:]}")
            ok = False
    finally:
        globals()["item_words"] = _real
    del fake_mod
    # ضابطُ `naql_cost` على معجمٍ صناعيٍّ معلومِ الجواب: «الارض» يقابلها «لارض» كلمةً أخرى
    def lt2(_r):
        return ["الارض لارض", "الكبري"]
    r_, c_, t_, _o = naql_cost("qalun", SCR, SC, lt2)
    if (r_, c_, t_) != (2, 1, 3):
        print(f"⛔ naql_cost صناعيّاً: انتُظر (‏يبلغ 2 · يعمى 1 · المواضع 3) فجاء ({r_} · {c_} · {t_})")
        ok = False
    # ضابطا `madd_drop` مباشرةً — حدُّها أنّها **حذفٌ فقط** لا إبدال
    if not madd_drop("بالافق", "بلفق") or madd_drop("وحقت", "وحك") or madd_drop("تله", "تله"):
        print("⛔ madd_drop: حدُّها «حذفُ مدٍّ فقط» لم يُحفَظ")
        ok = False
    # ضابطٌ سالبٌ: بلا معجمٍ لا يُقال «لا» بل «لم يُبحَث» ⇒ العمودُ صفرٌ دائماً
    _k, _d, o, _h = classify("اَ۬لْغَيْبِ", "الخير", "warsh", SCR, SC, None)
    if o:
        print("⛔ بلا معجمٍ يجب أن يبقى عمودُ «كلمةٌ أخرى» فارغاً (‏لم يُبحَث)")
        ok = False
    # ضابطٌ: البترُ الذي يوافق كلمةً أخرى **يُعلَن** ولا يُغطّى بالصنف
    k2, _d2, o2, h2 = classify("اَ۬لتُّرَاثَ", "تراث", "qalun", SCR, SC, {"تراث"})
    if k2 != HEAD or not o2:
        print(f"⛔ بترٌ يوافق كلمةً أخرى: انتُظر ({HEAD}, True) فجاء ({k2}, {o2})")
        ok = False
    # ضابطٌ: سعرُ البابِ يتحرّك على معجمٍ صناعيٍّ معلومِ الجواب
    fake = {"warsh": ["الخير خير", "قل"]}

    def lt(r):
        return fake[r]
    try:
        out, uniq, tot, nu = door_cost("warsh", SCR, SC, lt)
    except Exception:
        out = None
    if out is None:
        print("⛔ door_cost سقط على معجمٍ صناعيّ")
        ok = False
    else:
        # «خير» ذَنَبُ «الخير» وكلمةٌ أخرى ⇒ بابُ الذَنَب يعمى عن موضعَي «الخير»
        if out.get(HEAD, 0) != 1 or out.get(TAIL, 0) != 0:
            print(f"⛔ سعرٌ صناعيّ: انتُظر (‏الذَنَب 1 · الصدر 0) فجاء "
                  f"({out.get(HEAD, 0)} · {out.get(TAIL, 0)}) · المواضع {tot} · الفريدة {nu}")
            ok = False
    # 💠 **وضوابطُ البابِ المقفل — على نصٍّ صناعيٍّ معلومِ الجواب** (‏وفيه ضابطٌ سالب)
    def lt3(_r):
        return ["قل خير", "قل", "قل", "الغيب"]     # «قل» ثلاثُ مواضعَ · «الغيب» موضعٌ
    rows_p = [
        {"riwaya": "warsh", "ref": "قل", "heard": "خير"},      # المسموعُ كلمةٌ أخرى ⇒ يُدفع 3
        {"riwaya": "warsh", "ref": "الغيب", "heard": "زقزق"},  # ليس كلمةً ⇒ يبلغ 1 ويُدفع 0
        {"riwaya": "warsh", "ref": "الغيب", "heard": ""},      # صفرُ نصٍّ ⇒ لا زوجَ
        {"riwaya": "warsh", "ref": "قل", "heard": "خير"},      # مكرَّرٌ ⇒ لا يُحسب مرّتَين
    ]
    d = pair_cost(rows_p, SCR, SC, lt3)["warsh"]
    if (len(d["pairs"]), d["reach"], d["blind"], d["mute"]) != (2, 4, 3, 1):
        print(f"⛔ pair_cost صناعيّاً: انتُظر (‏زوجان · يبلغ 4 · يعمى 3 · صامتٌ 1) فجاء "
              f"({len(d['pairs'])} · {d['reach']} · {d['blind']} · {d['mute']})")
        ok = False
    # 🔍 وضابطُ التعميم: زوجٌ يتكرّر في بندَين **يُغفر** في المحجوب، وفريدٌ **لا يُغفر**
    rows_g = [
        {"riwaya": "warsh", "ref": "قل", "heard": "خير", "item": "long_warsh_001_001x1"},
        {"riwaya": "warsh", "ref": "قل", "heard": "خير", "item": "long_warsh_002_001x1"},
        {"riwaya": "warsh", "ref": "الغيب", "heard": "زقزق", "item": "long_warsh_002_001x1"},
    ]
    gen, nk, ur = pair_generalize(rows_g, SCR, SC, lt3)
    g1 = [g for g in gen if g["name"].endswith("1")][0]
    if (nk, ur, g1["by_pair"], g1["n"]) != (3, 2, 1, 2):
        print(f"⛔ pair_generalize صناعيّاً: انتُظر (3 · مرجعان · يغفر 1 من 2) فجاء "
              f"({nk} · {ur} · {g1['by_pair']} من {g1['n']})")
        ok = False
    # ⛔ وضابطٌ سالبٌ: أزواجٌ لا تتكرّر بين البنود ⇒ **صفرُ غفرانٍ** في المحجوب (‏حفظٌ لا تعميم)
    rows_u = [
        {"riwaya": "warsh", "ref": "قل", "heard": "خير", "item": "long_warsh_001_001x1"},
        {"riwaya": "warsh", "ref": "الغيب", "heard": "زقزق", "item": "long_warsh_002_001x1"},
    ]
    gu = pair_generalize(rows_u, SCR, SC, lt3)[0]
    if any(g["by_pair"] for g in gu):
        print(f"⛔ pair_generalize: أزواجٌ فريدةٌ يجب أن تُعطي صفرَ غفرانٍ فجاء {gu}")
        ok = False
    # 🤫 وضابطُ وكيل الامتناع: لا-كلمةٍ تُعدّ · وكلمةٌ قرآنيّةٌ لا تُعدّ · وصفرُ نصٍّ يُفرَز
    import tempfile
    rows_a = [
        {"riwaya": "warsh", "ref": "قل", "heard": "زقزق"},     # ليست كلمةً ⇒ يصلح للامتناع
        {"riwaya": "warsh", "ref": "قل", "heard": "خير"},      # كلمةٌ قرآنيّةٌ ⇒ خطأٌ يُقال
        {"riwaya": "warsh", "ref": "قل", "heard": ""},         # صفرُ نصّ
    ]
    with tempfile.TemporaryDirectory() as td2:
        pl = os.path.join(td2, "p.json")
        json.dump({"items": [
            {"op": "SUBSTITUTE", "riwaya": "warsh", "targetWord": "قل", "donor": {"word": "خير"}},
            {"op": "SUBSTITUTE", "riwaya": "warsh", "targetWord": "قل", "donor": {"word": "زقزق"}},
        ]}, open(pl, "w", encoding="utf-8"), ensure_ascii=False)
        ab, ct = abstain_stats(rows_a, SCR, SC, lt3, [pl])
        da = ab["warsh"]
        if (da["n"], da["no_word"], da["word"], da["mute"]) != (2, 1, 1, 1):
            print(f"⛔ abstain_stats: انتُظر (‏نصّان · لا-كلمةٌ 1 · كلمةٌ 1 · صامتٌ 1) فجاء {da}")
            ok = False
        # ⛔ والضابطُ يَعدّ المانحَ كلمةً لا لا-كلمةً — وإلّا قِيس ثمنُ الامتناع خطأً
        if (ct["n"], ct["word"], ct["no_word"]) != (2, 1, 1):
            print(f"⛔ ضابطُ الامتناع: انتُظر (2 · كلمةٌ 1 · لا-كلمةٌ 1) فجاء {ct}")
            ok = False
    # 🎯 وضابطُ الأرضيّة الأخرى: زوجٌ مشتركٌ يُغفر · ومختلفٌ لا · وأرضيّةٌ فارغةٌ «لم تُقَس»
    g_self = pair_against(rows_g, rows_g, SCR, SC, lt3)
    # ⭐ ومرجعٌ من القائمة بسماعٍ آخر: **بالزوج صفرٌ وبالمرجع واحدٌ** — وهذا معنى العمودَين
    g_off = pair_against(rows_g, [{"riwaya": "warsh", "ref": "الغيب", "heard": "خير",
                                   "item": "x"}], SCR, SC, lt3)
    # ومرجعٌ ليس فيها البتّة ⇒ صفرٌ في العمودَين
    g_new = pair_against(rows_g, [{"riwaya": "warsh", "ref": "خير", "heard": "زقزق",
                                   "item": "x"}], SCR, SC, lt3)
    g_nil = pair_against(rows_g, [], SCR, SC, lt3)
    if (g_self["by_pair"] != g_self["n"] or (g_off["by_pair"], g_off["by_ref"]) != (0, 1)
            or (g_new["by_pair"], g_new["by_ref"]) != (0, 0) or g_nil["n"]):
        print(f"⛔ pair_against: انتُظر (‏نفسُها كلُّها · مرجعٌ بسماعٍ آخرَ 0/1 · غريبٌ 0/0 · "
              f"فارغةٌ 0) فجاء ({g_self} · {g_off} · {g_new} · {g_nil})")
        ok = False
    # ⛔⛔ **والضابطُ الذي لا يُستغنى عنه:** قائمةٌ فيها زوجُ حقنٍ مصنوعٍ **تُكشف**
    with tempfile.TemporaryDirectory() as td:
        plan = os.path.join(td, "p.json")
        json.dump({"items": [
            {"id": "inj_x", "op": "SUBSTITUTE", "riwaya": "warsh", "targetWord": "قل",
             "donor": {"word": "خير"}},
            {"id": "inj_y", "op": "OMIT", "riwaya": "warsh", "targetWord": "قل"},
        ]}, open(plan, "w", encoding="utf-8"), ensure_ascii=False)
        checked, hits = plan_collisions({"warsh": d}, SCR, SC, [plan])
        if checked != 1 or len(hits) != 1:
            print(f"⛔ plan_collisions: انتُظر (‏فُحص 1 · توافقٌ 1) فجاء ({checked} · {len(hits)})")
            ok = False
        # وخطّةٌ لا تُقرأ **تُعلَن** ولا تُقرأ «صفرَ توافق»
        c2, h2s = plan_collisions({"warsh": d}, SCR, SC, [os.path.join(td, "لا-وجود.json")])
        if c2 != 0 or not h2s:
            print(f"⛔ خطّةٌ غائبةٌ يجب أن تُعلَن لا أن تمرّ: ({c2} · {h2s})")
            ok = False
    print("✅ الضوابطُ كلُّها مرّت." if ok else "⛔ سقط ضابطٌ — لا يُقرأ من هذه الأداة رقمٌ.")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs")
    ap.add_argument("--dirs", default="")
    ap.add_argument("--arms", default="")
    ap.add_argument("--sets", default="")
    ap.add_argument("--top", type=int, default=60)
    ap.add_argument("--cost", action="store_true")
    ap.add_argument("--floor-out", default="", help="🧱 يكتب مواضعَ أرضيّة الذراع الأولى ملفَّ JSON")
    ap.add_argument("--floor", default="", help="🧱 يقابل الأذرعَ بأرضيّةٍ مكتوبةٍ سلفاً")
    ap.add_argument("--where", action="store_true",
                    help="🧭 أمِن البند نفسِه جاءت الكلمةُ المسموعةُ أم من خارجه؟")
    ap.add_argument("--riwayat", default="warsh qalun")
    ap.add_argument("--heads", default="", help="صدورٌ ساقطةٌ يُقاس سعرُ بابِ كلٍّ منها وحدَه")
    ap.add_argument("--pair-door", default="", help="💠 يُسعّر بابَ قائمةٍ مقفلةٍ من أرضيّةٍ مكتوبة")
    ap.add_argument("--plans", default="inject_plan.json inject_plan_qalun.json inject_plan_riwaya.json",
                    help="⛔ خططُ الحقن التي تُقابَل بها القائمةُ (الضابطُ السالب)")
    ap.add_argument("--against", default="",
                    help="🎯 أرضيّةٌ أخرى (‏مجموعةٌ محجوبةٌ بتمامها) تُقاس عليها القائمةُ")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if a.pairs:
        rows = annotate(from_pairs(a.pairs))
        table(rows, f"تصنيفُ {sum(r[4] for r in rows)} خطأً — من `{os.path.basename(a.pairs)}`")
        if a.where:
            where_table(rows)
    if a.dirs:
        lex_cache = {}
        dirs = [d.split(":", 1)[0] for d in a.dirs.split() if d] or ["work"]
        dirs = [d if os.path.isabs(d) else os.path.join(HERE, d) for d in dirs]
        found = 0
        for st, arm, pairs in from_dirs(dirs, a.arms.split(), a.sets.split()):
            found += 1
            rows = annotate(pairs[:a.top], lex_cache=lex_cache)
            table(rows, f"تصنيفُ أخطاء `{st}` · `{arm}`")
            if a.where:
                where_table(rows)
        if a.floor_out or a.floor:
            pos = floor_positions(dirs, a.arms.split(), a.sets.split())
            if not pos:
                print("⛔ لا فرضيّاتٍ للأرضيّة ⇒ **لم تُقَس** (ولا تُكتب أرضيّةٌ فارغة).")
                return 3
            order = [k for k in pos]
            if a.floor_out:
                st0, arm0 = order[0]
                d = pos[(st0, arm0)]
                json.dump({"set": st0, "arm": arm0, "n": len(d["rows"]),
                           "items": d["items"], "rows": d["rows"]},
                          open(a.floor_out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
                print(f"\n🧱 كُتبت أرضيّةُ `{st0}` · `{arm0}`: **{len(d['rows'])}** موضعاً في "
                      f"**{len(d['items'])}** بنداً ⇒ `{os.path.basename(a.floor_out)}` "
                      f"(‏تُقابَل بها أذرعٌ قادمة).")
            if a.floor:
                d0 = json.load(open(a.floor, encoding="utf-8"))
                for (st, arm), d in pos.items():
                    if arm == d0.get("arm") and st == d0.get("set"):
                        continue
                    floor_table(d0["rows"], d["rows"], arm, f"{d0.get('arm')}",
                                d0.get("items"), d["items"])
        # ⛔ **ولا خروجَ صامتٌ:** جدولٌ فارغٌ يُقرأ «لم يُقَس» لا «لا خطأ» ⇒ يُنطق بسببه
        #    ويسقط بالرمز، فلا تُعدّ خطوةٌ فارغةٌ نجاحاً (‏درسُ الشوط `34795058366`).
        if not found:
            print(f"⛔ لا فرضيّاتٍ قُرئت في {dirs} للذراعَين `{a.arms}` والمجموعات `{a.sets}` "
                  f"⇒ **لا تصنيفَ** (وهذا «لم يُقَس» لا «لا أخطاء»).")
            return 3
    if a.pair_door:
        d0 = json.load(open(a.pair_door, encoding="utf-8"))
        rows = d0.get("rows") or []
        if not rows:
            print(f"⛔ لا مواضعَ في `{os.path.basename(a.pair_door)}` ⇒ **لا يُسعَّر بابٌ على "
                  "فراغ** (وهذا «لم يُقَس» لا «صفرُ ثمن»).")
            return 3
        print(f"\n## 💠 بابٌ مقفَلٌ على أرضيّةِ `{d0.get('set')}` · `{d0.get('arm')}` — "
              f"**{len(rows)}** موضعاً في **{len(d0.get('items') or [])}** بنداً")
        plans = [p if os.path.isabs(p) else os.path.join(HERE, p) for p in a.plans.split()]
        other, oname = None, ""
        if a.against:
            d1 = json.load(open(a.against, encoding="utf-8"))
            other = d1.get("rows") or []
            oname = f"{d1.get('set')} · {d1.get('arm')}"
            if not other:
                print(f"⛔ لا مواضعَ في `{os.path.basename(a.against)}` ⇒ **الأرضيّةُ الأخرى "
                      "لم تُقَس** (ولا تُقرأ فراغاً).")
                return 3
        pair_report(rows, plans, d0.get("items") or (), other, oname)
        # 🤫 والامتناعُ يُقاس على **الأرضيّة المحجوبة** إن وُجدت (‏وهي الضجيجُ في العادة)
        #    وإلّا فعلى أرضيّة القائمة — والعنوانُ يقول أيّهما كي لا يلتبس رقمان.
        src = other if other else rows
        print(f"\n#### (‏الامتناعُ مقيسٌ على: **{oname or (str(d0.get('set')) + ' · ' + str(d0.get('arm')))}**)")
        abstain_report(src, plans)
    if a.cost:
        cost_report(a.riwayat.split(), a.heads.split())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
