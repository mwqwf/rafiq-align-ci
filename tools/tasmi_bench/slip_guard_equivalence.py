# -*- coding: utf-8 -*-
"""🔬 هل حارسا `RiwayaSlipDetector` **قابلان للحراسة أصلاً**؟ — سؤالٌ سبق كتابةَ الاختبار.

**السياق (‏D-446):** نجت طفرتان من زرع الطفرات في كاشف الانزلاق:
- `slip:noBlankGuard` — نزعُ `if (h.isEmpty()) return null`
- `slip:noTolerance` — نزعُ `if (exact.isEmpty() && matches(mine, h, myProfile)) return null`

وسُجّلتا «🚨 بلا حارس». **لكنّ «نجت» احتمالان لا واحد:**
1. **ثغرةُ تغطية** — السلوكُ يتغيّر ولا اختبارَ يراه ⇒ يُكتب الاختبار.
2. **طفرةٌ مكافئة** — السلوكُ **لا يتغيّر البتّة** ⇒ لا اختبارَ يقتلها، وكتابةُ اختبارٍ لها
   عبثٌ يوهم بالحراسة. والحارسُ حينئذٍ **قِصَرُ طريقٍ ووضوحٌ** لا شرطٌ للصحّة.

وقبل أن يُكتب اختبارٌ يجب أن يُعرف أيُّهما — وهذه الأداةُ تُجيب **بالقياس على المصحف كلِّه**:
تُعيد بناءَ منطق `detect` ثلاثَ مرّات (سليماً · بلا حارسِ الفارغ · بلا التسامح) وتُحصي
المواضعَ التي يختلف فيها الحكم.

  python tools/tasmi_bench/slip_guard_equivalence.py [--limit N]

⚠️ القياسُ على **المرآة** (`slip_order_arm.detect` مرآةُ المحرك حرفاً) — والحكمُ نسبيٌّ كعادته.
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "tools", "alignment"))

import scorer  # noqa: E402
import slip_order_arm as SOA  # noqa: E402

P = SOA.P


def detect(ref_word, heard, current, diffs, no_blank_guard=False, no_tolerance=False):
    """`RiwayaSlipDetector.detect` مع إمكان نزع أحد الحارسَين — وما عداه حرفٌ بحرف."""
    if not heard or not heard.strip() or not diffs:
        return None
    cfg = P.config_for(current)
    h = scorer.norm(heard, cfg)
    if not h and not no_blank_guard:          # ← الحارسُ الأوّل
        return None
    if current == "hafs":
        idxs = {it[0] for rows in diffs.values() for it in rows if it[1] == ref_word}
    else:
        idxs = {it[0] for it in diffs.get(current, ()) if it[2] == ref_word}
    if not idxs:
        return None
    for idx in sorted(idxs):
        hafs_word = next((it[1] for rows in diffs.values() for it in rows if it[0] == idx), None)
        if hafs_word is None:
            continue
        forms = SOA._forms_at(diffs, idx, hafs_word)
        mine = forms.get(current, ref_word)
        if scorer.norm(mine, cfg) == h:
            return None
        exact = {r: w for r, w in forms.items()
                 if r != current and w != mine and scorer.norm(w, P.config_for(r)) == h}
        if not exact and SOA._matches(mine, h, cfg) and not no_tolerance:   # ← الحارسُ الثاني
            return None
        loose = exact if exact else {r: w for r, w in forms.items()
                                     if r != current and w != mine
                                     and SOA._matches(w, h, P.config_for(r))}
        if loose:
            theirs = next(iter(loose.values()))
            return sorted(r for r, w in loose.items() if w == theirs)
    return None


def build_cases(limit=0):
    """⚠️ **حالاتُ انزلاقٍ حقيقيّة** — ولمَ لا تكفي حالاتُ `slip_order_arm._cases`؟

    لأنّها تُطعم القارئَ **كلمةَ روايته هو**، فيردّ السطرُ الأوّل (`norm(mine) == h`) بـ`None`
    فوراً ⇒ مسارُ الانزلاق **لا يُدخَل أصلاً**. وقياسٌ على 464 ألف حالةٍ كلُّها تنصرف من أوّل
    سطرٍ **لا يشهد بشيء** (‏وقد قِيس فعلاً فخرج صفراً — وكان صفراً فارغَ المعنى).

    فالحالةُ الصحيحة **تقاطُعيّة**: يُطعَم قارئُ الرواية `current` صورةَ الكلمة كما في روايةٍ
    **أخرى** — وهو عينُ ما يحرسه الكاشف.
    """
    diffs_by_ayah = SOA.SL.farsh_diffs()
    n = 0
    for ayah, d in diffs_by_ayah.items():
        if not d:
            continue
        idxs = {it[0] for rows in d.values() for it in rows}
        for idx in idxs:
            hafs_word = next((it[1] for rows in d.values() for it in rows if it[0] == idx), None)
            if hafs_word is None:
                continue
            forms = SOA._forms_at(d, idx, hafs_word)
            for current in SOA.SIX:
                mine = forms.get(current, hafs_word)
                for other, their in forms.items():
                    if other == current or their == mine:
                        continue
                    yield (f"x|{current}←{other}|{ayah:05d}|{idx}", their, mine, current, d)
                    n += 1
                    if limit and n >= limit:
                        return


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    cases = list(build_cases(args.limit))

    diff_blank, diff_tol, n = [], [], 0
    for name, heard, ref_word, current, d in cases:
        n += 1
        base = detect(ref_word, heard, current, d)
        if detect(ref_word, heard, current, d, no_blank_guard=True) != base:
            diff_blank.append(name)
        if detect(ref_word, heard, current, d, no_tolerance=True) != base:
            diff_tol.append(name)

    print(f"# حالاتٌ فُحصت (‏المصحفُ كلُّه × 6): {n}")
    print(f"# 🔀 نزعُ حارس **المسموع الفارغ** غيّر الحكمَ في: {len(diff_blank)} موضعاً")
    print(f"# 🔀 نزعُ **تسامحِ روايتك**   غيّر الحكمَ في: {len(diff_tol)} موضعاً")
    for x in diff_tol[:5]:
        print(f"     مثالٌ للتسامح: {x}")

    # 🧪 والفارغُ لا يقع في المصحف (‏كلُّ كلمةٍ تُطبَّع إلى شيء) ⇒ يُجرَّب صراحةً
    print("\n# 🧪 مسموعٌ تشكيلٌ محضٌ (‏يُطبَّع إلى فراغ) — وهو المدخلُ الوحيدُ الذي يُفعّل الحارس:")
    probe = [c for c in cases[:400] if c[4]][:3]
    for name, _, ref_word, current, d in probe:
        a = detect(ref_word, "ًٌٍَُِّْ", current, d)
        b = detect(ref_word, "ًٌٍَُِّْ", current, d, no_blank_guard=True)
        print(f"   {name}: بالحارس={a} · بلا الحارس={b} · "
              f"{'مطابق ⇒ مكافئة' if a == b else '🚨 مختلف ⇒ ثغرةُ تغطية'}")


if __name__ == "__main__":
    main()
