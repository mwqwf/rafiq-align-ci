# -*- coding: utf-8 -*-
"""🎛️ **أثرُ قاعدةِ التعادل على الأرقام** — ذراعان من **مسطرتَين** على فرضيّاتٍ واحدة (‏D-366).

⛔ **لِمَ وُجدت:** قاعدةُ المحاذاة عند تعادل الكلفة تقرأ الإقحامَ **إبدالاً** فتتّهم كلمةً صحيحة
(`PREFER_INSERT_ON_TIE` في `scorer.py` · `preferInsertOnTie` في المحرك). وتغييرُ قاعدةٍ مشحونةٍ
**لا يُشحن بحجّة أنّه أصوب**: يُقاس أثرُه على **الاتّهام الكاذب** و**الكشف** أوّلاً.

⭐ **وهذا يُقاس بلا شوطِ محاكٍ:** القاعدةُ في **المسطرة** لا في التفريغ، والفرضيّاتُ محفوظةٌ من
أشواطٍ مضت ⇒ تُقرأ مرّةً ويُحكم بها **مرّتين** (مطفأةً ومُشعلة). وهو نظيرُ ما صار إليه
`gate-anatomy`: **ما نقص قراءةً لا يُعالَج بشوطٍ جديد** (‏D-365).

⚠️ **وحدُّه:** المسطرةُ بايثونيّةٌ — وهي مسطرةُ كلِّ أرقام اللوحة أصلاً (‏`v2_gate`) — **لكنّ
العرضَ في التطبيق يجري بالمحرك**، فتأكيدُ المحرك يحتاج ربطَ المفتاح بالمسبار في `MainActivity`.

    python tools/tasmi_bench/tie_rule_ab.py --dirs work: --arm shipped-T
"""
import argparse
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
import restore_probe as R  # noqa: E402
import judge_cfg_probe as J  # noqa: E402
import v2_gate as G  # noqa: E402
from detect_anatomy import donor_heard, donor_located, boot, OPS  # noqa: E402


def judge_with(plan, hyps, rule):
    """حكمُ الذراع بمسطرةٍ مفتاحُها [rule] — ويُعيد المفتاحَ دائماً (حالةٌ عامّةٌ لا تُترك مُشعلة)."""
    old = scorer.PREFER_INSERT_ON_TIE
    try:
        scorer.PREFER_INSERT_ON_TIE = rule
        det, fa, n, per = G.judge_arm(plan, hyps)
        loc = {it["id"]: (donor_heard(it, hyps[it["id"]]), donor_located(it, hyps[it["id"]], 0))
               for it in plan if it["op"] == "INSERT" and it["id"] in hyps}
        return det, fa, n, per, loc
    finally:
        scorer.PREFER_INSERT_ON_TIE = old


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dirs", nargs="+", required=True)
    ap.add_argument("--arm", required=True, help="ذراعٌ واحدة — فالمقارنةُ بين مسطرتَين لا بين نموذجَين")
    a = ap.parse_args()

    plan_all = {it["id"]: it for it in J.load_plan()["items"]} if hasattr(J, "load_plan") else \
        {it["id"]: it for it in __import__("json").load(open(J.PLAN, encoding="utf-8"))["items"]}
    acc = R.load(a.dirs)
    (h,) = R.arms_or_die(acc, [a.arm])
    plan = [{**plan_all[k.split("/", 1)[1]], "id": k} for k in sorted(h) if k.split("/", 1)[1] in plan_all]
    # ⛔ **ولا يُقرأ الصفرُ نتيجةً** (قاعدةُ «لا خضرةَ بلا شهادة»): تُسمّى العيّنةُ قبل أيّ رقم.
    if len(plan) < 50:
        raise SystemExit(f"⛔ {len(plan)} بنداً فقط في {a.arm} — لا يُحكم بعيّنةٍ كهذه")

    dA, faA, n, perA, locA = judge_with(plan, h, False)
    dB, faB, _, perB, locB = judge_with(plan, h, True)

    print(f"# 🎛️ أثرُ قاعدةِ التعادل — الذراعُ `{a.arm}` · ن = **{len(plan)}**\n")
    print("**المقارنةُ بين مسطرتَين على الفرضيّات عينِها**: القاعدةُ الحالية ⇐ "
          "«عند التساوي لا تُتَّهم كلمةٌ صحيحة».\n")

    pairs = [(perA[i][0], perA[i][1], perB[i][0], perB[i][1]) for i in perA if i in perB]
    lo, hi, p = G._boot_diff(pairs)
    det_pairs = [(perA[i][2], 1, perB[i][2], 1) for i in perA if i in perB]
    d_lo, d_hi, d_p = G._boot_diff(det_pairs)
    print("| المقياس | القاعدةُ الحالية | **القاعدةُ المرشَّحة** | الفرق [95٪] | احتمالُ السوء |")
    print("|---|---:|---:|---|---:|")
    print(f"| اتّهامٌ كاذب | {faA*100:.2f}٪ | **{faB*100:.2f}٪** | {(faB-faA)*100:+.2f} "
          f"[{lo*100:+.2f} .. {hi*100:+.2f}] | {p*100:.0f}٪ |")
    print(f"| كشفٌ ضيّق | {dA*100:.1f}٪ | **{dB*100:.1f}٪** | {(dB-dA)*100:+.1f} "
          f"[{d_lo*100:+.1f} .. {d_hi*100:+.1f}] | {d_p*100:.0f}٪ |")

    # 📍 وصنفُ الإقحام خاصّةً: أتُقرأ الزيادةُ زيادةً، وفي موضعها؟
    ids = sorted(locA)
    if ids:
        hp = [(locA[i][0], locB[i][0]) for i in ids]
        lp = [(locA[i][1], locB[i][1]) for i in ids]
        h_lo, h_hi = boot(hp)
        l_lo, l_hi = boot(lp)
        HA = sum(x[0] for x in hp) / len(hp) * 100
        HB = sum(x[1] for x in hp) / len(hp) * 100
        LA = sum(x[0] for x in lp) / len(lp) * 100
        LB = sum(x[1] for x in lp) / len(lp) * 100
        print(f"\n## 📍 صنفُ `INSERT` وحدَه (‏ن = **{len(ids)}**)\n")
        print("| المقياس | القاعدةُ الحالية | **المرشَّحة** | الفرق | مجال 95٪ |")
        print("|---|---:|---:|---:|---:|")
        print(f"| تُقرأ الدخيلةُ زيادةً | {HA:.1f}٪ | **{HB:.1f}٪** | **{HB-HA:+.1f}** | [{h_lo:+.1f} .. {h_hi:+.1f}] |")
        print(f"| وفي موضعها بالضبط | {LA:.1f}٪ | **{LB:.1f}٪** | **{LB-LA:+.1f}** | [{l_lo:+.1f} .. {l_hi:+.1f}] |")

    # 🧾 وجردُ ما تبدّل بنداً بنداً — فالرقمُ المضموم يخفي مَن تغيّر ومَن لم يتغيّر.
    moved = [i for i in perA if i in perB and perA[i] != perB[i]]
    print(f"\n## 🧾 ما تبدّل حكمُه: **{len(moved)}** بنداً من {len(perA)}")
    if moved:
        print("\n| البند | الحالية (اتّهام/مجموع/كشف) | المرشَّحة |")
        print("|---|---|---|")
        for i in moved[:15]:
            print(f"| `{i}` | {perA[i]} | **{perB[i]}** |")
        if len(moved) > 15:
            print(f"\n<sub>وبقيةُ المتبدّلين {len(moved)-15} بنداً لم تُطبع.</sub>")
    print("\n⛔ **ولا يُشحن من هذا الجدول:** القاعدةُ تمسّ كلَّ حكمٍ في التطبيق، والمسطرةُ هنا "
          "بايثونيّةٌ — فالتأكيدُ على المحرك يحتاج ربطَ `preferInsertOnTie` بالمسبار ثمّ شوطَ بوّابة.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
