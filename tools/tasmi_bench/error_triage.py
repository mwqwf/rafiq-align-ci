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
    print("| كلمةُ المرجع | ما سُمع | الصنف | البابُ الذي يغفره | كلمةٌ أخرى؟ | تكراراً | تفصيل |")
    print("|---|---|---|---|:---:|---:|---|")
    kinds = collections.Counter()
    others = collections.Counter()
    for ref, heard, _riw, _item, c, kind, det, other, _head in rows:
        kinds[kind] += c
        if other:
            others[kind] += c
        print(f"| `{ref}` | `{heard}` | {kind} | {DOOR.get(kind, '—')} | "
              f"{'⛔ نعم' if other else '—'} | {c} | {det} |")
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


def from_pairs(path):
    data = json.load(open(path, encoding="utf-8"))
    out = []
    for d in data:
        out.append((d["ref"], d.get("heard"), d.get("riwaya", "warsh"),
                    d.get("item", ""), int(d.get("count", 1))))
    return out


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
    ap.add_argument("--riwayat", default="warsh qalun")
    ap.add_argument("--heads", default="", help="صدورٌ ساقطةٌ يُقاس سعرُ بابِ كلٍّ منها وحدَه")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if a.pairs:
        rows = annotate(from_pairs(a.pairs))
        table(rows, f"تصنيفُ {sum(r[4] for r in rows)} خطأً — من `{os.path.basename(a.pairs)}`")
    if a.dirs:
        lex_cache = {}
        dirs = [d.split(":", 1)[0] for d in a.dirs.split() if d] or ["work"]
        dirs = [d if os.path.isabs(d) else os.path.join(HERE, d) for d in dirs]
        found = 0
        for st, arm, pairs in from_dirs(dirs, a.arms.split(), a.sets.split()):
            found += 1
            rows = annotate(pairs[:a.top], lex_cache=lex_cache)
            table(rows, f"تصنيفُ أخطاء `{st}` · `{arm}`")
        # ⛔ **ولا خروجَ صامتٌ:** جدولٌ فارغٌ يُقرأ «لم يُقَس» لا «لا خطأ» ⇒ يُنطق بسببه
        #    ويسقط بالرمز، فلا تُعدّ خطوةٌ فارغةٌ نجاحاً (‏درسُ الشوط `34795058366`).
        if not found:
            print(f"⛔ لا فرضيّاتٍ قُرئت في {dirs} للذراعَين `{a.arms}` والمجموعات `{a.sets}` "
                  f"⇒ **لا تصنيفَ** (وهذا «لم يُقَس» لا «لا أخطاء»).")
            return 3
    if a.cost:
        cost_report(a.riwayat.split(), a.heads.split())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
