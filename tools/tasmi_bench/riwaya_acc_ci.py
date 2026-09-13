# -*- coding: utf-8 -*-
"""🕌📏 **دقّةُ التتبّع روايةً روايةً — بمجالِ ثقةٍ لا بفرقٍ عارٍ.**

⛔ **لِمَ وُجدت — بسببٍ مقيسٍ لا مفترَض** (‏D-418/D-419): جدولُ البوّابة يطبع الدقّةَ بالرواية
**فرقاً عارياً** (`hafs 99.3⇐97.4 · qalun 95.2⇐94.4 · warsh 94.0⇐91.9`) — بلا مجالٍ ولا احتمال.
والمجالُ المنشورُ **مضمومٌ على الروايات الثلاث**. ⇒ فمن أراد أن يحكم على نموذجٍ **شُحن لورشٍ
وقالون بعينهما** لم يجد رقماً يحكم به: قد يكون هبوطُ الروايتَين ضجيجَ عيّنةٍ صغيرةٍ (‏71 ورشاً
و60 قالوناً)، وقد يكون حقيقةً. ⭐ **وفرقٌ بلا مجالٍ يُقرأ على هوى قارئه** (‏درسُ D-351 نفسُه في
صفِّ الكشف: مَن أراد القبولَ سمّاه ضجيجاً ومَن أراد الردَّ سمّاه انحداراً).

**فهذه الأداةُ تُعطي كلَّ مجموعةِ رواياتٍ مجالَها** — و`warsh+qalun` مضمومتَين لأنّهما **موضعُ
القرار** (‏`Variant.forRiwaya`) — بـ**المسطرة عينِها**: `score.run(..., "proposed")` و`_boot_diff`
المستوردَين من `v2_gate` **لا نسخةً منهما** (فلا تنحرف مسطرةٌ عن مسطرة).

    python riwaya_acc_ci.py --arms shipped tinyv2-ar --sets g1 g2-noise-fan-5
    python riwaya_acc_ci.py --work work_anatomy --arms A B --sets g1

⛔ **ولا تقرأ الفرضيّاتَ من جهازك:** ملفّاتُ `hyps_emu_<مجموعة>_cap_<ذراع>.json` تُنزَّل في
العدّاء (R2 محجوبٌ عن صندوق الوكيل بـ403) ⇒ تُشغَّل هناك، ومخرَجُها ملفٌّ في `results/`.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import score  # noqa: E402
import v2_gate as G  # noqa: E402  — للمسطرة نفسِها: `_boot_diff` و`pool_items`

# 🎯 مجموعاتُ الرواياتِ التي تُطبع، وأوّلُها موضعُ القرار.
GROUPS = (("warsh+qalun", ("warsh", "qalun")), ("warsh", ("warsh",)),
          ("qalun", ("qalun",)), ("hafs", ("hafs",)), ("الثلاث", ("warsh", "qalun", "hafs")))


def load_hyps(work, set_tag, arm):
    p = os.path.join(work, f"hyps_emu_{set_tag}_cap_{arm}.json")
    if not os.path.exists(p):
        return None
    h = json.load(open(p, encoding="utf-8")).get("hyps", {})
    return {k: v for k, v in h.items() if v.get("text") is not None and "error" not in v}


def measure(items, ha, hb):
    """(دقّةُ أ، دقّةُ ب، الفرق، المجال، احتمالُ الكسب، ن) — بالمسطرة المعتمدة `proposed`."""
    ra, rb = score.run(items, ha, "proposed"), score.run(items, hb, "proposed")
    aa, ab = score.aggregate(ra), score.aggregate(rb)
    pairs = [(x["correct"], x["total"], y["correct"], y["total"])
             for x, y in zip(ra, rb) if x["ok"] and y["ok"]]
    lo, hi, p = G._boot_diff(pairs)
    return aa["accuracy"], ab["accuracy"], ab["accuracy"] - aa["accuracy"], (lo, hi), p, len(pairs)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", default=os.path.join(HERE, "work"))
    ap.add_argument("--arms", nargs=2, required=True, metavar=("A", "B"))
    ap.add_argument("--sets", nargs="+", default=["g1", "g2-noise-fan-5"],
                    help="بأسماء الملفّات (‏g1 · g2-noise-fan-5) لا بأسماء البوّابة")
    a = ap.parse_args()

    pool = G.pool_items()
    print(f"‏الذراعان: `{a.arms[0]}` ⇒ `{a.arms[1]}` · المرجعُ {len(pool)} بنداً\n")
    any_row = False
    for st in a.sets:
        ha, hb = load_hyps(a.work, st, a.arms[0]), load_hyps(a.work, st, a.arms[1])
        if ha is None or hb is None:
            # ⛔ الغائبُ يُسمّى بملفّه: «لا صفوف» تُقرأ عطباً في الأداة وهي فرضيّاتٌ غائبة.
            print(f"⛔ `{st}`: فرضيّاتٌ غائبةٌ لذراعٍ أو لذراعَين "
                  f"(‏{a.arms[0]}: {'✅' if ha else '⛔'} · {a.arms[1]}: {'✅' if hb else '⛔'})\n")
            continue
        common = set(ha) & set(hb)
        print(f"### `{st}` — {len(common)} بنداً في الذراعَين\n")
        print("| مجموعةُ الرواية | ن | " + a.arms[0] + " | **" + a.arms[1] + "** | الفرق | مجال 95٪ | احتمالُ الكسب |")
        print("|---|---:|---:|---:|---:|---|---:|")
        for name, riws in GROUPS:
            items = [it for it in pool if it["id"] in common and it.get("riwaya") in riws]
            if not items:
                continue
            x, y, d, (lo, hi), p, n = measure(items, ha, hb)
            any_row = True
            star = " ⚠️" if hi < 0 else (" ✅" if lo > 0 else "")
            print(f"| {name} | {n} | {x*100:.2f}٪ | **{y*100:.2f}٪** | **{d*100:+.2f}**{star} | "
                  f"[{lo*100:+.2f} .. {hi*100:+.2f}] | {p*100:.0f}٪ |")
        print()
    if not any_row:
        # ⛔ **ولا يُقرأ صفرُ صفوفٍ نجاحاً** (‏درسُ «لا يفشل صامتاً»): يسقط برمزٍ غيرِ صفر.
        raise SystemExit("⛔ لا صفَّ واحداً حُسب — راجِعْ الوسمَ والأذرعَ وأسماءَ المجموعات")
    print("⛔ **وحدٌّ يُقال:** الرقمُ هنا **قراءةٌ لفرضيّاتٍ مقيسةٍ على المحرك** لا قياسٌ جديد ⇒ "
          "المسطرةُ والمجموعةُ والذراعان كما كانت في شوطها، والمجالُ **عنقوديٌّ بالآية** (‏2000 سحبة).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
