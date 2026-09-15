# -*- coding: utf-8 -*-
"""🔢 **ترتيبُ المواضع** في كاشف الانزلاق — هل يحجب موضعٌ سابقٌ دليلاً أقوى في موضعٍ لاحق؟

**من أين جاء السؤال (‏D-448):** في تشخيص اختلاف المحرك والمرآة تبيّن أنّ كلمةَ `يَكُن` تقع
في آيةٍ واحدةٍ في **موضعَي فرشٍ** (‏7 و14)، وأنّ `detect` تمرّ على الفهارس **مرتّبةً** ثمّ
**تنصرف من أوّل موضعٍ يحكم**. فانصرف الحكمُ عند الموضع 7 (‏بتسامح روايتك) ولم يُنظر إلى
الموضع 14 أصلاً — **وفيه مطابقةٌ حرفيّةٌ لصورة ورشٍ وقالون**، وهي دليلٌ أقوى.

⚠️ **وهذا سؤالُ ترتيبٍ من نوعٍ آخرَ غير الذي درسه `slip_order_arm`:** ذاك يقارن ترتيبَ
**السطور داخل الموضع الواحد** (‏التسامحُ قبل المطابقة الحرفيّة أو بعدها). وهذا يسأل عن
**الترتيب بين المواضع** — ولم يُقَس قطّ.

والذراعان المقيسان هنا:
- **(أ)** لا تنصرف عند «تسامحُ روايتك»، بل جرّب بقيّةَ المواضع — فإن حكم أحدُها بانزلاقٍ فهو الحكم.
- **(ب)** لا تنصرف عند أيِّ «لا انزلاق» (‏بما فيه مطابقةُ روايتك حرفيّاً) حتى تُستنفد المواضع.

  python tools/tasmi_bench/slip_index_order.py [--limit N] [--strict]

⛔ **قياسٌ لا اقتراحَ شحن:** الترتيبُ الحاليُّ قد يكون مقصوداً (‏«أوّلُ موضعٍ يحكم» قاعدةٌ
بسيطةٌ يفهمها القارئ). والغرضُ أن يُعرف **حجمُ ما يُحجب**، فإن كان صفراً فالسؤالُ مغلق.
⚠️ والأرقامُ من المرآة (`slip_order_arm.detect` مرآةُ المحرك حرفاً) — للمقارنة النسبيّة.
"""
import argparse
import copy
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "tools", "alignment"))

import scorer  # noqa: E402
import slip_order_arm as SOA  # noqa: E402
import slip_guard_equivalence as G  # noqa: E402

P = SOA.P


def detect(ref_word, heard, current, diffs, keep_going_on_tolerance=False,
           keep_going_on_any_null=False):
    """`detect` مع إمكان **متابعة المواضع** بدل الانصراف من أوّلِ حكمٍ سالب."""
    if not heard or not heard.strip() or not diffs:
        return None
    cfg = P.config_for(current)
    h = scorer.norm(heard, cfg)
    if not h:
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
            if keep_going_on_any_null:
                continue
            return None
        exact = {r: w for r, w in forms.items()
                 if r != current and w != mine and scorer.norm(w, P.config_for(r)) == h}
        if not exact and SOA._matches(mine, h, cfg):
            if keep_going_on_tolerance or keep_going_on_any_null:
                continue
            return None
        loose = exact if exact else {r: w for r, w in forms.items()
                                     if r != current and w != mine
                                     and SOA._matches(w, h, P.config_for(r))}
        if loose:
            theirs = next(iter(loose.values()))
            return sorted(r for r, w in loose.items() if w == theirs)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--strict", action="store_true",
                    help="بإعداد المحرك المشحون (‏criticalPairsUncertain=true)")
    args = ap.parse_args()

    if args.strict:
        tbl = {}
        for r in SOA.SIX:
            c = copy.copy(P.config_for(r))
            c.strict_short = True
            tbl[r] = c
        P.config_for = lambda r, _t=tbl: _t[r]

    cases = list(G.build_cases(args.limit))
    multi = a_diff = b_diff = 0
    examples = []
    for name, heard, ref, cur, d in cases:
        idxs = ({it[0] for rows in d.values() for it in rows if it[1] == ref} if cur == "hafs"
                else {it[0] for it in d.get(cur, ()) if it[2] == ref})
        if len(idxs) > 1:
            multi += 1
        base = detect(ref, heard, cur, d)
        va = detect(ref, heard, cur, d, keep_going_on_tolerance=True)
        vb = detect(ref, heard, cur, d, keep_going_on_any_null=True)
        if va != base:
            a_diff += 1
            if len(examples) < 5:
                examples.append((name, base, va, vb))
        if vb != base:
            b_diff += 1

    print(f"# الإعداد: {'المحرك (strict_short=True)' if args.strict else 'المرآة كما هي'}")
    print(f"# حالاتٌ فُحصت: {len(cases)} · منها **متعدّدةُ المواضع**: {multi} "
          f"({100*multi/max(len(cases),1):.1f}٪)")
    print(f"# (أ) متابعةٌ بعد «تسامحُ روايتك»     ⇒ تغيّر الحكم في {a_diff} موضعاً")
    print(f"# (ب) متابعةٌ بعد أيِّ «لا انزلاق»    ⇒ تغيّر الحكم في {b_diff} موضعاً")
    for name, base, va, vb in examples:
        print(f"   مثال {name}: الحالي={base} · (أ)={va} · (ب)={vb}")
    if not a_diff and not b_diff:
        print("# ✅ لا يُحجب شيء: الانصرافُ من أوّل موضعٍ لا يُخفي حكماً في موضعٍ لاحق.")


if __name__ == "__main__":
    main()
