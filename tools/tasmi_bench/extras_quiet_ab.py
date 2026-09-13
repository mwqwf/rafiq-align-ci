# -*- coding: utf-8 -*-
"""🤫 **تهدئةُ الزوائد: ثمنٌ بثمن** — كم تُخفِض كلُّ قاعدةٍ من الضجّة، وكم تُفقد من الحقيقيّ؟ (‏D-369)

⛔ **السبب مقيس:** على تلاوةٍ **صحيحةٍ نظيفةٍ** تُعرَض زائدةٌ كاذبةٌ في **7.0٪** من الآيات
(‏D-369) — بينما اتّهامُ الكلمات الكاذبُ 7.69٪ على عيّنته ⇒ **عرضُ الزوائد خاماً يكاد يُضاعف
الإنذارَ الكاذب.** ⇒ فلا تُعرَض حتى تُهدَّأ، **ولا تُختار تهدئةٌ بالهوى**.

⭐ **والقاعدةُ لا تُقاس بنصف ميزان:** كلُّ تهدئةٍ تُقاس **مرّتين على الفرضيّات عينِها**:
1. **الضجّةُ** على `g1` النظيفة (‏آياتٌ صحيحةٌ: كلُّ زائدةٍ غريبةٍ وهمٌ)، و
2. **الإمساكُ** على `g3r` المحقونة (‏بنودُ `INSERT`: أتبقى الزائدةُ الحقيقيّةُ معروضةً؟).
⇒ **فتهدئةٌ تُسكت الوهمَ وتُسكت الحقيقةَ معه ليست تهدئةً بل عمى.**

    python tools/tasmi_bench/extras_quiet_ab.py --dirs work: --arm shipped-B
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import scorer  # noqa: E402
import judge_cfg_probe as J  # noqa: E402
import restore_probe as R  # noqa: E402
import v2_gate as G  # noqa: E402
from detect_anatomy import boot  # noqa: E402

# 🤫 التهدئاتُ المرشَّحة — كلُّ واحدةٍ شرطٌ **يُسكت** زائدةً؛ والاسمُ يُطبع كما هو في القرار.
#    (‏`extras` قائمةُ (نصٌّ، موضعٌ) لآيةٍ واحدة · و`sc` حكمُ المسطرة عليها)
RULES = {
    "كما هو (بلا تهدئة)": lambda e, sc: True,
    "لا تُعرَض عند انهيار التعرّف": lambda e, sc: not sc.get("collapsed"),
    "طولُ الزائدة ≥ 4 أحرف": lambda e, sc: len(e[0]) >= 4,
    "زائدتان متجاورتان": None,            # تُحسب على مستوى الآية لا الزائدة
    # 🆕 **شاهدٌ ثانٍ: جارةٌ متّهمة** — الدخيلةُ الحقيقيّةُ تُحدث ضرراً جانبيّاً في جارتها غالباً
    # (وهو أصلُ تعريف «الكشف الضيّق» · D-351)، والوهمُ يجيء في آيةٍ **كلُّ كلماتها صحيحة**.
    # ⇒ فلا تُعرَض زائدةٌ إلّا إن كان في جوارها (‏±1) حكمُ خطإٍ مؤكَّد.
    "جارةٌ متّهمةٌ (‏±1)": None,
    "المجّانيّةُ + جارةٌ متّهمة": None,
    "الثلاثُ مجتمعةً": None,
    # 🆕🕋 **حزامٌ ثالثٌ: حكمُ الآية نفسِها** (‏أُضيف 2026-09-13 بعد D-375): قاعدةُ الانهيار
    # مجّانيّةٌ لكنّها **لا تُطلق إلّا في الكارثة** (‏حارسُ التعرّف · 14/201 مقابل 15) ⇒ فيُجرَّب
    # نظيرُها **الأخفُّ وهو مشحونٌ أصلاً**: `AyahVerdict.Band.WEAK` («تحتاج مراجعة»). والحدسُ
    # المقيسُ اتّجاهاً: الوهمُ يجيء في آيةٍ **مهلهَلةِ التفريغ**، والدخيلةُ الحقيقيّةُ تجيء في
    # آيةٍ سليمةٍ سواها. ⛔ **ولا تُشحن قاعدةٌ لأنّها أعقل** (‏درسُ D-367) — تُقاس أوّلاً.
    "لا تُعرَض في آيةٍ «تحتاج مراجعة»": lambda e, sc: not weak_ayah(sc),
    "المجّانيّةُ + لا في آيةٍ «تحتاج مراجعة»":
        lambda e, sc: (not sc.get("collapsed")) and not weak_ayah(sc),
    # 🆕 ومنحنى الطول عند نقطةٍ أوسطَ: «≥ 4» أفقد **58٪** من الإمساك (D-375) ⇒ أفي «≥ 3» وسطٌ؟
    "طولُ الزائدة ≥ 3 أحرف": lambda e, sc: len(e[0]) >= 3,
}

BAD = ("MISSED", "SUBSTITUTED")


def weak_ayah(sc):
    """أحكمُ الآية «تحتاج مراجعة»؟ — **بتعريف المحرك حرفاً** (`LongTasmiMapper.AyahVerdict.band`):
    خطآن فأقلّ **و**الخطأُ لا يبلغ ثلثَ الكلمات = تعثّر؛ وما فوقه = تحتاج مراجعة.
    ⛔ ولا يُعاد تعريفُه هنا بالتقريب: قاعدةٌ تفوز بتعريفٍ غيرِ المشحون **لا تُنفَّذ كما قِيست**."""
    ws = [w for w in sc.get("words", []) if w]
    if not ws:
        return False
    errs = sum(1 for w in ws if w[1] in BAD)
    return not (errs <= 2 and errs * 3 <= len(ws))


def has_bad_neighbor(e, sc):
    """أفي جوار الزائدة (‏±1) كلمةٌ حُكم عليها بخطإٍ **مؤكَّد**؟ — شاهدٌ ثانٍ لا تساهل."""
    at = e[1]
    return any(w[1] in BAD and abs(w[0] - at) <= 1 for w in sc["words"] if w)


def adjacent_pairs(extras):
    """مواضعُ الزوائد التي لها جارةٌ في الموضع نفسِه أو الذي يليه — «زائدتان متجاورتان»."""
    pos = sorted(at for _, at in extras)
    keep = set()
    for i, p in enumerate(pos):
        for q in pos[i + 1:]:
            if q - p <= 1:
                keep.add(p); keep.add(q)
    return keep


def shown(extras, sc, rule):
    """الزوائدُ التي **تُعرَض** بعد تطبيق [rule]."""
    if rule == "زائدتان متجاورتان":
        k = adjacent_pairs(extras)
        return [e for e in extras if e[1] in k]
    if rule == "جارةٌ متّهمةٌ (‏±1)":
        return [e for e in extras if has_bad_neighbor(e, sc)]
    if rule == "المجّانيّةُ + جارةٌ متّهمة":
        if sc.get("collapsed"):
            return []
        return [e for e in extras if has_bad_neighbor(e, sc)]
    if rule == "الثلاثُ مجتمعةً":
        if sc.get("collapsed"):
            return []
        k = adjacent_pairs(extras)
        return [e for e in extras if e[1] in k and len(e[0]) >= 4]
    f = RULES[rule]
    return [e for e in extras if f(e, sc)]


def foreign_extras(it, hyp):
    """(‏الزوائدُ الغريبةُ وموضعُها، حكمُ المسطرة) — بقاعدة D-267 عينِها وصورِ الحاكم نفسِه."""
    c = J.cfg(it.get("riwaya"), True)
    ref = it["refText"].split()
    sc = scorer.score(ref, hyp["text"], c)
    forms = [scorer._riwaya_forms(scorer.variants(x, c), c) for x in ref]
    out = [(t, at) for t, at in sc.get("located", [])
           if not any(scorer._matches(f, t, c) for f in forms)]
    return out, sc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dirs", nargs="+", required=True)
    ap.add_argument("--arm", required=True, help="ذراعٌ واحدةٌ — فالمقارنةُ بين قواعدِ عرضٍ لا بين نموذجَين")
    a = ap.parse_args()

    clean = R.load(a.dirs, prefix="hyps_emu_g1").get(a.arm, {})
    inj = R.load(a.dirs, prefix="hyps_emu_g3r").get(a.arm, {})
    if not clean or not inj:
        raise SystemExit(f"⛔ يحتاج الأمرُ فرضيّاتِ `g1` **و**`g3r` للذراع {a.arm!r} — "
                         f"الموجود: نظيفةٌ {len(clean)} · محقونةٌ {len(inj)}. ⇒ راجِع `results/HYPS_INVENTORY.md`")

    pool = {it["id"]: it for it in G.pool_items()}
    plan = {it["id"]: it for it in json.load(open(J.PLAN, encoding="utf-8"))["items"]}
    cl = [(pool[k.split("/", 1)[1]], clean[k]) for k in sorted(clean) if k.split("/", 1)[1] in pool]
    ij = [(plan[k.split("/", 1)[1]], inj[k]) for k in sorted(inj)
          if k.split("/", 1)[1] in plan and plan[k.split("/", 1)[1]]["op"] == "INSERT"]
    # ⛔ **ولا يُقرأ الصفرُ نتيجةً:** تُسمّى العيّنتان قبل أيّ رقم.
    if len(cl) < 50 or len(ij) < 30:
        raise SystemExit(f"⛔ عيّنةٌ لا يُحكم بها: نظيفةٌ {len(cl)} · إقحامٌ {len(ij)}")

    # نُحسب مرّةً واحدةً ثمّ تُطبَّق القواعدُ على المحسوب — فالمسطرةُ واحدةٌ لكلّ القواعد.
    cl_ex = [(it, *foreign_extras(it, h)) for it, h in cl]
    ij_ex = []
    for it, h in ij:
        ex, sc = foreign_extras(it, h)
        c = J.cfg(it.get("riwaya"), True)
        dw = scorer.norm((it.get("donor") or {}).get("word", ""), c)
        w = int(it["wordIndex"])
        # الزائدةُ **الحقيقيّة**: كلمةُ المانحِ بعينها في موضع الحقن (‏±1) — وهي التي لا يجوز إسكاتُها.
        true_ex = [e for e in ex if scorer.norm(e[0], c) == dw and abs(e[1] - w) <= 1]
        ij_ex.append((it, ex, sc, true_ex))

    print(f"# 🤫 تهدئةُ الزوائد — الذراعُ `{a.arm}`\n")
    print(f"**العيّنتان:** نظيفةٌ `g1` **{len(cl)}** آيةً (‏كلُّ زائدةٍ غريبةٍ وهم) · "
          f"ومحقونةٌ `g3r` **{len(ij)}** بندَ إقحامٍ (‏الزائدةُ الحقيقيّةُ معلومةٌ بعينها).\n")
    print("| قاعدةُ العرض | ضجّةٌ: آياتٌ نظيفةٌ فيها زائدةٌ مَعروضة | إمساكٌ: إقحامٌ حقيقيٌّ يُعرَض | الحكم |")
    print("|---|---:|---:|---|")
    base_noise = base_hold = None
    for rule in RULES:
        noise = sum(1 for _, ex, sc in cl_ex if shown(ex, sc, rule))
        hold = sum(1 for _, ex, sc, tr in ij_ex if [e for e in shown(ex, sc, rule) if e in tr])
        pn, ph = noise / len(cl_ex) * 100, hold / len(ij_ex) * 100
        if base_noise is None:
            base_noise, base_hold = pn, ph
            verd = "خطُّ الأساس"
        else:
            dn, dh = pn - base_noise, ph - base_hold
            # ⛔ **و«لا أثر» تُسمّى ولا تُلبَس حكماً:** صفرٌ مقابل صفرٍ كان يُطبع «تُسكت الحقيقةَ
            # أكثرَ من الوهم» (لأنّ ‎0 ≤ 0) — حكمٌ على قاعدةٍ **لم تفعل شيئاً**، وكذبٌ صريح.
            if abs(dn) < 0.05 and abs(dh) < 0.05:
                verd = "⚪ لا أثرَ على هذه العيّنة"
            elif dn >= -0.05:
                verd = "⛔ لا تُخفِض ضجّةً"
            elif dh >= -0.05:
                verd = "✅ **تُسكت الوهمَ بلا ثمن**"
            elif dh <= dn:
                verd = "⛔ الثمنُ أكبرُ من المكسب"
            else:
                verd = f"⚖️ {dn:+.1f} ضجّةً مقابل {dh:+.1f} إمساكاً"
        print(f"| {rule} | **{pn:.1f}٪** ({noise}/{len(cl_ex)}) | **{ph:.1f}٪** ({hold}/{len(ij_ex)}) | {verd} |")

    print("\n⛔ **وما لا يُقرأ من هذا الجدول:** أنّ القاعدةَ الفائزةَ «تُشحن» — فالعرضُ قرارُ جلسة "
          "التطبيق، والمسطرةُ هنا بايثونيّةٌ (وهي مسطرةُ أرقام اللوحة). وما يُقرأ: **أيُّ تهدئةٍ "
          "تشتري هدوءاً بثمنٍ مقبولٍ وأيُّها عمى.**")
    return 0


if __name__ == "__main__":
    sys.exit(main())
