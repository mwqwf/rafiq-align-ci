#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""📏 كم نقطةً تنفخ مرآةُ اللوحةِ الرقمَ الرسميَّ؟ — الانحرافُ بعُملة اللوحة لا بعدد الحالات (‏D-417)

**الدَّينُ الذي سلّمته D-416 نصّاً:** «الانحرافُ قِيس على **حالاتٍ مصنوعة** ⇒ **أثرُه على
الأرقام الرسميّة لم يُقَس بعدُ**». وهذا قضاؤه بالقدر الذي تسمح به سحابةٌ بلا صوت.

## لماذا «7,521 حالة» ليست جواباً
D-416 عدَّت **سلاسلَ الأحكام المنحرفة**، والمالكُ لا يقرأ سلاسل: يقرأ **«حفص 98.17٪»**.
وبين العددين تحويلٌ ليس بديهيّاً — الحالةُ المنحرفةُ تختلف في **كلمةٍ واحدةٍ غالباً** من آيةٍ
فيها عشرون، فـ4.80٪ من الحالات لا تعني 4.80 نقطةٍ ولا 0.048. ⇒ **يُحسب لا يُقدَّر.**

## الطريقةُ — عدّةُ اللوحة نفسُها
- الحالاتُ **هي حالاتُ `parity_full.make_cases` حرفاً** (‏تسعةُ أبوابٍ حتميّةٍ على كلِّ آيةٍ من
  كلِّ رواية · بلا صوتٍ ولا نموذج)، ويُجرى عليها الحاكمان: **المحركُ** (‏`RecitationScorer.kt`
  على JVM) و**مرآةُ اللوحة** (`config_for` كما هي، بلا `strict_short`).
- والدقّةُ تُجمع **جمعاً مصغَّراً** (`Σcorrect / Σtotal`) — وهي طريقةُ `score.py` بعينِها
  (‏D-413)، لا متوسّطَ نِسَبٍ. فالرقمُ المطبوعُ هنا يُقارَن بأرقام اللوحة بلا تحويل.
- و**الفجوةُ = دقّةُ المرآة − دقّةُ المحرك** بالنقاط: موجبةٌ ⇒ **اللوحةُ تُعلن دقّةً أعلى ممّا
  يحكم به التطبيقُ في يد القارئ**.

## ⚖️ الحدُّ يُقال أوّلاً (‏وهو حدُّ تمثيلٍ لا حدُّ حساب)
الاضطرابُ هنا **مصنوعٌ وواحدٌ في كلِّ آية** (‏تصحيفُ حرفٍ · حذفُ كلمةٍ · إبدالُها …) ⇒ توزيعُه
**ليس توزيعَ أخطاء قارئٍ حقيقيّ**، ولا توزيعَ أخطاء `whisper` على صوت. فالفجوةُ المطبوعةُ
**تصف هذه المجموعةَ بعينِها**، وتصلح لتقدير **الاتّجاه والحجم** لا لتصحيح رقمٍ منشور.
⛔ والقياسُ على العيّنات الرسميّة (‏G1 · G3r) يقتضي `hyps` أي صوتاً — وهو ممنوعٌ في السحابة.

    python mirror_accuracy_gap.py --riwaya hafs --limit 300
    python mirror_accuracy_gap.py --all
"""
import argparse
import collections
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import parity_full as P  # noqa: E402


def gap_for(riwaya, limit=0, jobs=0):
    cases = P.make_cases(riwaya, limit)
    eng = P.run_engine(cases, riwaya, os.path.join(P.WORK, "engine_%s.tsv" % riwaya))
    mir = P.run_mirror(cases, riwaya, jobs)
    # لكلِّ باب: [حالات · كلماتٌ · صوابُ المرآة · صوابُ المحرك]
    doors = collections.defaultdict(lambda: [0, 0, 0, 0])
    flips = collections.Counter()          # (حرفُ المرآة ⇒ حرفُ المحرك)
    for name, ref, hyp in cases:
        door = name.rsplit("_", 1)[1]
        e, m = eng.get(name), mir[name]
        if e is None or len(e[0]) != len(m[0]):
            continue
        d = doors[door]
        d[0] += 1
        d[1] += len(m[0])
        d[2] += m[0].count("C")
        d[3] += e[0].count("C")
        if e[0] != m[0]:
            for cm, ce in zip(m[0], e[0]):
                if cm != ce:
                    flips[(cm, ce)] += 1
    return doors, flips


def show(riwaya, doors, flips):
    tw = tm = te = tc = 0
    print(f"\n=== {riwaya} ===")
    print(f"  {'الباب':<10} {'حالات':>7} {'كلمات':>8} {'المرآة٪':>9} {'المحرك٪':>9} {'الفجوة':>8}")
    for door in sorted(doors):
        c, w, m, e = doors[door]
        tc += c; tw += w; tm += m; te += e
        pm, pe = 100.0 * m / max(w, 1), 100.0 * e / max(w, 1)
        mark = "🚨" if abs(pm - pe) >= 0.005 else "  "
        print(f"  {mark}{door:<9} {c:>7} {w:>8} {pm:>8.3f} {pe:>8.3f} {pm - pe:>+8.3f}")
    pm, pe = 100.0 * tm / max(tw, 1), 100.0 * te / max(tw, 1)
    print(f"  {'—' * 52}")
    print(f"  **المجموع** {tc:>6} {tw:>8} {pm:>8.3f} {pe:>8.3f} {pm - pe:>+8.3f}")
    print(f"GAP\t{riwaya}\t{tc}\t{tw}\t{tm}\t{te}\t{pm - pe:.4f}")
    if flips:
        tot = sum(flips.values())
        det = " · ".join(f"{a}⇒{b} {n}" for (a, b), n in flips.most_common(6))
        print(f"  🔀 كلماتٌ اختلف حكمُها: **{tot}** ({det})")
    return tw, tm, te


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--riwaya", choices=P.RIWAYAT)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--jobs", type=int, default=0)
    args = ap.parse_args()

    riwayat = P.RIWAYAT if (args.all or not args.riwaya) else (args.riwaya,)
    os.makedirs(P.WORK, exist_ok=True)
    TW = TM = TE = 0
    for riw in riwayat:
        t0 = time.time()
        doors, flips = gap_for(riw, args.limit, args.jobs)
        w, m, e = show(riw, doors, flips)
        TW += w; TM += m; TE += e
        print(f"  (‏زمنُ الرواية {time.time() - t0:.0f}ث)")
    if len(riwayat) > 1:
        pm, pe = 100.0 * TM / max(TW, 1), 100.0 * TE / max(TW, 1)
        print(f"\n**الثلاثُ مجموعةً** · كلماتٌ {TW} · المرآة {pm:.3f}٪ · المحرك {pe:.3f}٪ "
              f"· **الفجوة {pm - pe:+.3f} نقطة**")


if __name__ == "__main__":
    main()
