# -*- coding: utf-8 -*-
"""🧭 النصفُ **الثالث** من ميزان «رخصة الكلمة القصيرة» — أثرُها على **التتبّع** لا على الحكم (‏D-284).

`short_word_exposure.py` (‏D-277) قاس **التكلفة** (34–39٪ تعرُّضاً)، و`short_word_benefit.py`
(‏D-282) قاس **الفائدة** على حاكم الكلمات (‏+0.31 نقطة إنذارٍ كاذب لذراع ≤2)، و`D-283` ردَّ
البديلَ الصوتيّ. وبقي ذراعُ (ب) `short_cap=2` **المرشَّحَ الوحيد** المعروضَ على المالك.

⚠️ **لكنّ الميزانَ كلَّه قِيس على نصفِ الرخصة.** الرخصةُ `(_n <= 3 and _d <= 1)` ليست في
حاكم الكلمات وحدَه: هي في `RecitationScorer.looseMatch` — و`looseMatch` يستعملها **محدّدُ
الموضع** (`QuranLocator.strip_preamble`) و**كاشفُ الانزلاق الروائيّ** (`RiwayaSlipDetector`)،
وتستعملها حلقةُ **المحاذاة** (`anchoredPerAyah`) عبر `score` في كلِّ نافذةٍ تجرّبها.

🔑 **وهذا ليس تفصيلاً جانبياً: الرخصةُ أُضيفت لأجل التتبّع أصلاً.** نصُّ تعليق المحرك
(2026-09-05): «التتبّع 96.78→97.16٪ والكشف 94.3→92.5٪ والإنذار الكاذب 0.9→0.7٪». فقياسُ
ذراعِ (ب) على الحكم وحدَه **قياسٌ للنصف الذي لم تُضَف الرخصةُ لأجله**. وإن كان الذراعُ
يشتري 0.31 نقطةً بكسرِ المحاذاة فالصفقةُ غيرُ التي عُرضت.

**والمقيسُ هنا:** على النصِّ الحقيقيِّ المودَع (`long_anchor_fixture.tsv` — 60 تفريغاً
حقيقيّاً من `hyps_shipped_g4.json`، كلُّ تفريغٍ مع آياته مفصولةً بـ`|`) تُعاد المحاذاةُ
بكلِّ ذراعٍ ويُقارن:

    • آياتٌ ضاعت نافذتُها  — الآيةُ تُبلَّغ «لم تُسمَع» وهي مسموعة  ⇐ العطبُ الأفدح
    • تغطيةُ الكلمات       — Σ correct / Σ n
    • انزياحُ النافذة      — كم آيةً تغيّر حدُّها (بدايةً أو نهاية)

الأذرع: **أ) 3 = المشحون** · **ب) 2 = ذراعُ D-277** · **ج) 0 = بلا رخصة**.

✅ **ضابطُ التصديق:** الذراعُ (أ) يعيد إنتاجَ أحكامِ `parity_fixture.tsv` (‏212 حالةً
**مصدَّقةً على المحرك**) حرفاً بحرف ⇒ المقيسُ هو المشحون لا تقريبُه.
🧪 **والضابطُ السالب** (‏قاعدةُ D-279: حارسٌ لا يسقط على عطبٍ مزروعٍ لا يُصدَّق أخضرُه):
ذراعٌ مطابقٌ للمشحون ⇒ فرقٌ **0**؛ ورخصةٌ موسَّعةٌ `≤9` ⇒ **يجب** أن تحرّك المحاذاة.

    python tools/tasmi_bench/short_word_tracking.py
    python tools/tasmi_bench/short_word_tracking.py --control --examples 20
"""
import argparse
import csv
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "tools", "alignment"))

import locator  # noqa: E402
import scorer  # noqa: E402
import short_word_benefit as B  # noqa: E402  (‏حزمةُ التماثل وضابطُها — مصدرٌ واحدٌ للقاعدة)

FIXTURES = os.path.join(ROOT, "engine", "recitation", "src", "test", "resources")
ANCHOR_TSV = os.path.join(FIXTURES, "long_anchor_fixture.tsv")

SHIPPED_CAP = 3


def config_for(riwaya, short_cap=SHIPPED_CAP):
    """الإعدادُ المشحون لكلِّ رواية — هو نفسُه الذي يبني به `make_parity_fixture` حزمةَ التماثل."""
    return scorer.Config(naql=(riwaya == "warsh"), sila=(riwaya in ("warsh", "qalun")),
                         short_cap=short_cap)


def _rows(path):
    with open(path, encoding="utf-8") as f:
        for row in csv.reader(f, delimiter="\t"):
            if row and not row[0].startswith("#"):
                yield row


def load_anchor():
    """(المعرّف، الرواية، التفريغُ المسموع، قائمةُ آياتِ المرجع)."""
    out = []
    for row in _rows(ANCHOR_TSV):
        if len(row) < 4:
            continue
        name, riwaya, hyp, refs = row[0], row[1], row[2], row[3]
        ayat = [a for a in refs.split("|") if a.strip()]
        if ayat:
            out.append((name, riwaya, hyp, ayat))
    return out


# ── ضابطُ التصديق: الذراعُ المشحون يطابق الحزمةَ المصدَّقةَ على المحرك ─────────────────────
def verify_parity(short_cap=SHIPPED_CAP):
    """يُستدعى ضابطُ D-282 نفسُه — لا يُعاد بناؤه هنا فيختلف عنه صمتاً."""
    rows = B.load_fixture()
    return B.validate(rows, B.judge(rows, short_cap))


# ── القياس ────────────────────────────────────────────────────────────────────────────
def run_arm(rows, short_cap):
    """المحاذاةُ بذراعٍ واحد ⇒ عدّاداتٌ + بصمةُ نوافذَ للمقارنة الحالةَ بالحالة."""
    acc = dict(ayat=0, heard=0, correct=0, words=0, texts=len(rows))
    per = {}
    for name, riwaya, hyp, ayat in rows:
        cfg = config_for(riwaya, short_cap)
        res = locator.anchored_per_ayah([a.split() for a in ayat], hyp, cfg)
        for a in res:
            acc["ayat"] += 1
            acc["words"] += a["n"]
            acc["correct"] += a["correct"]
            if a["window"] is not None:
                acc["heard"] += 1
            per[(name, a["i"])] = (a["window"], a["correct"], a["n"])
    return acc, per


def compare(base, arm):
    """(ضاعت نافذتُها، ظهرت نافذتُها، انزاحت نافذتُها، تغيّر عددُ صحيحِها)."""
    lost = gained = moved = recount = 0
    rows = []
    for k, (w0, c0, n) in base.items():
        w1, c1, _ = arm.get(k, (None, 0, n))
        if w0 is not None and w1 is None:
            lost += 1
        elif w0 is None and w1 is not None:
            gained += 1
        elif w0 != w1:
            moved += 1
        if c0 != c1:
            recount += 1
        if (w0, c0) != (w1, c1):
            rows.append((k, w0, c0, w1, c1, n))
    return dict(lost=lost, gained=gained, moved=moved, recount=recount), rows


def pct(a, b):
    return 100.0 * a / b if b else 0.0


ARMS = (("أ) المشحون ≤3", 3), ("ب) ذراعُ D-277 ≤2", 2), ("ج) بلا رخصة", 0))


def report(rows, examples):
    base, base_per = run_arm(rows, SHIPPED_CAP)
    print("\nالنصُّ الحقيقيُّ المودَع: %d تفريغاً · %d آيةً · %d كلمةً مرجعية"
          % (base["texts"], base["ayat"], base["words"]))
    print("\n=== المحاذاةُ بالذراع ===")
    print("  %-20s %8s %10s %8s %8s %8s" % ("الذراع", "مسموعة", "تغطية", "ضاعت", "انزاحت", "تغيّر عدّها"))
    out = {}
    for label, cap in ARMS:
        acc, per = (base, base_per) if cap == SHIPPED_CAP else run_arm(rows, cap)
        d, ex = compare(base_per, per)
        out[cap] = (acc, d, ex)
        print("  %-20s %5d/%-4d %8.2f٪ %8d %8d %8d"
              % (label, acc["heard"], acc["ayat"], pct(acc["correct"], acc["words"]),
                 d["lost"], d["moved"], d["recount"]))
    for cap in (2, 0):
        _acc, _d, ex = out[cap]
        if not ex:
            continue
        print("\n  — أمثلةُ ما تغيّر في الذراع ≤%d (%d حالة):" % (cap, len(ex)))
        for (name, i), w0, c0, w1, c1, n in ex[:examples]:
            print("    %-28s آية %2d · نافذة %s ⇐ %s · صحيح %d/%d ⇐ %d/%d"
                  % (name, i, w0, w1, c0, n, c1, n))
    return out


def control(examples):
    """🧪 الضابطُ السالب — انظر ترويسةَ الملفّ."""
    rows = load_anchor()
    total, diff = verify_parity(SHIPPED_CAP)
    ok_parity = total > 0 and diff == 0
    print("ضابطُ التصديق: الذراعُ المشحون ⇐ %d/%d حالةً من حزمة التماثل (انحراف %d) %s"
          % (total - diff, total, diff, "✅" if ok_parity else "🚨"))

    _b, base_per = run_arm(rows, SHIPPED_CAP)
    _s, same_per = run_arm(rows, SHIPPED_CAP)
    d_same, _ = compare(base_per, same_per)
    ok_same = sum(d_same.values()) == 0
    print("الضابطُ السالب (أ): ذراعٌ مطابقٌ ⇒ فرقٌ %d %s"
          % (sum(d_same.values()), "✅" if ok_same else "🚨"))

    _w, wide_per = run_arm(rows, 9)
    d_wide, ex = compare(base_per, wide_per)
    moved = d_wide["lost"] + d_wide["gained"] + d_wide["moved"] + d_wide["recount"]
    ok_wide = moved > 0
    print("الضابطُ السالب (ب): رخصةٌ موسَّعةٌ ≤9 ⇒ تغيّر %d %s"
          % (moved, "✅ العدّادُ حيّ" if ok_wide else "🚨 العدّادُ أخرس — لا يُوثق برقمٍ منه"))
    for (name, i), w0, c0, w1, c1, n in ex[:examples]:
        print("    %-28s آية %2d · نافذة %s ⇐ %s · صحيح %d/%d ⇐ %d/%d"
              % (name, i, w0, w1, c0, n, c1, n))
    return 0 if (ok_parity and ok_same and ok_wide) else 1


def main():
    ap = argparse.ArgumentParser(description="أثرُ رخصة الكلمة القصيرة على التتبّع لا على الحكم")
    ap.add_argument("--examples", type=int, default=10, help="كم حالةً متغيّرةً تُطبع")
    ap.add_argument("--control", action="store_true", help="الضوابطُ وحدَها")
    args = ap.parse_args()
    if args.control:
        return control(args.examples)
    total, diff = verify_parity(SHIPPED_CAP)
    print("ضابطُ التصديق: الذراعُ المشحون ⇐ %d/%d حالةً من حزمة التماثل (انحراف %d) %s"
          % (total - diff, total, diff, "✅" if diff == 0 else "🚨"))
    if diff:
        print("🚨 المشحونُ لا يُعاد إنتاجُه ⇒ لا يُقرأ ما بعده.")
        return 1
    report(load_anchor(), args.examples)
    return 0


if __name__ == "__main__":
    sys.exit(main())
