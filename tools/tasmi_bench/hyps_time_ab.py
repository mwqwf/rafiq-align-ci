# -*- coding: utf-8 -*-
"""⏱️ **ثمنُ الزمن بين ذراعَين — من الفرضيّات المحفوظة نفسِها** (‏لا شوطَ جديدٌ ولا جهاز).

⛔ **لِمَ وُجد (‏2026-09-13 · بعد D-377):** كلُّ قرارِ مفتاحٍ في هذا الباب **ميزانُ دقّةٍ وزمن**:
حرسُ الفكّ يشتري كشفاً **ويكلّف بحثَ حزمة** (‏×1.73 على `arm64` · D-328)، والتتبّعُ الحيُّ
يسقط إن تجاوز الزمنَ الحقيقيَّ (‏D-355). وكان الزمنُ يُقاس **بشوطٍ خاصٍّ** (`arm-time.yml`)
بينما `emu_sweep` **يحفظ `ms` لكلِّ بندٍ في الفرضيّات أصلاً** ⇒ فالثمنُ مقروءٌ بدقيقةٍ مع
الدقّة، بلا إشعال شيء. ⭐ **ورقمٌ بلا ثمنِه نصفُ قرار.**

⚠️ **وحدُّه يُقال:** هذا زمنُ **محاكي العدّاء** لا زمنُ هاتف المستعمِل — يُقرأ **نسبةً** بين
ذراعَين على البنود عينِها (والنسبةُ تنتقل)، ولا يُقرأ عدداً مطلقاً لجهازٍ.

    python tools/tasmi_bench/hyps_time_ab.py --dirs "work:" --arms shipped-E guardon-E --sets g1
"""
import argparse
import glob
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def load(dirs, arm, sets=None, seen_sets=None):
    """{مُعرِّفُ البند: مللي ثانية} لكلِّ مجموعةٍ مطلوبة — من `hyps_emu_*_<arm>.json`.

    ⚠️ و[seen_sets] تُجمع فيها **أسماءُ المجموعات التي قُرئت فعلاً**: فالجدولُ يقرأ كلَّ ما في
    `work/` لا ما في الطلب (‏`g1` تُنزَّل تلقائيّاً لقناة الضجّة) ⇒ **رقمٌ بلا عيّنته نصفُ رقم**،
    وقد قرأتُ 466 بنداً وفي الطلب مجموعةٌ واحدةٌ فظننتُها هي (‏2026-09-13).
    """
    out = {}
    for d in dirs:
        base, _, suf = d.partition(":")
        for p in sorted(glob.glob(os.path.join(base, f"hyps_emu_*_{arm}{suf}.json"))):
            name = os.path.basename(p)
            if sets and not any(f"hyps_emu_{s}_" in name for s in sets):
                continue
            try:
                h = (json.load(io.open(p, encoding="utf-8")) or {}).get("hyps") or {}
            except Exception as e:
                print(f"⛔ لا يُقرأ {p}: {e}")   # يُقال ولا يُكتَم
                continue
            got = 0
            for k, v in h.items():
                if isinstance(v, dict) and isinstance(v.get("ms"), (int, float)):
                    out[k] = float(v["ms"])
                    got += 1
            if got and seen_sets is not None:
                # اسمُ المجموعة من اسم الملفّ: hyps_emu_<المجموعة>_<السلسلة>_<الذراع>.json
                body = name[len("hyps_emu_"):].rsplit(".json", 1)[0]
                seen_sets.add(body.rsplit("_", 2)[0] if body.count("_") >= 2 else body)
    return out


def pct(xs, q):
    """مئينٌ بلا numpy (‏العدّاءُ قد لا يملكها في هذه الخطوة) — **وبلا استيفاء**: يعيد **عنصراً
    من العيّنة** لا متوسّطَ عنصرَين. ⚠️ ويُقال كي لا يُظَنّ رقمُه أدقَّ مما هو (‏عيّنةٌ زوجيّةٌ
    تعطي العنصرَ الأدنى)، وأثرُه مهملٌ عند مئاتِ البنود ومحسوسٌ عند بندَين."""
    if not xs:
        return 0.0
    ys = sorted(xs)
    i = max(0, min(len(ys) - 1, int(round(q * (len(ys) - 1)))))
    return ys[i]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dirs", default="work:", help="مجلدٌ[:لاحقة] مفصولةٌ بفواصل")
    ap.add_argument("--arms", nargs=2, required=True)
    ap.add_argument("--sets", nargs="*", default=None, help="مجموعاتٌ بأسمائها في الملفّ (g1 · g3r-noisy)")
    a = ap.parse_args()
    dirs = a.dirs.split(",")
    seen = set()
    ta, tb = load(dirs, a.arms[0], a.sets, seen), load(dirs, a.arms[1], a.sets, seen)
    common = sorted(set(ta) & set(tb))
    if not common:
        # ⛔ **ولا صمتَ عند الصفر:** «لا زمنَ» قد تعني فرضيّاتٍ بلا `ms` (شوطٌ قديم) لا تساوياً.
        print(f"⛔ لا بندَ فيه زمنٌ للذراعَين ({len(ta)} · {len(tb)}) — "
              f"إمّا الفرضيّاتُ بلا `ms` وإمّا المجموعاتُ لا تتقاطع. **ولا يُقرأ هذا «لا فرق».**")
        return 1
    da = [ta[k] for k in common]
    db = [tb[k] for k in common]
    ratio = [tb[k] / ta[k] for k in common if ta[k] > 0]
    slower = sum(1 for k in common if tb[k] > ta[k])
    # ⛔ **والعيّنةُ تُسمّى مع الرقم:** المجموعاتُ التي قُرئت فعلاً لا التي في الطلب.
    names = " · ".join(sorted(seen)) or "?"
    print(f"# ⏱️ ثمنُ الزمن — `{a.arms[0]}` ⇒ `{a.arms[1]}` (‏{len(common)} بنداً مشتركاً "
          f"من **{names}** · محاكي العدّاء)\n")
    print("| المقياس | `%s` | `%s` | النسبة |" % (a.arms[0], a.arms[1]))
    print("|---|---:|---:|---:|")
    for name, q in (("الوسيط", 0.5), ("المئينُ 90", 0.9), ("الأقصى", 1.0)):
        pa, pb = pct(da, q), pct(db, q)
        print(f"| {name} (م.ث) | {pa:.0f} | **{pb:.0f}** | ×{(pb / pa if pa else 0):.2f} |")
    print(f"| المجموع (ث) | {sum(da)/1000:.1f} | **{sum(db)/1000:.1f}** | "
          f"×{(sum(db)/sum(da) if sum(da) else 0):.2f} |")
    print(f"\n**ووسيطُ نسبةِ البند إلى نظيره** ×{pct(ratio, 0.5):.2f} · "
          f"وأبطأُ في **{slower}/{len(common)}** بنداً.")
    print("\n⚠️ زمنُ **المحاكي** لا زمنُ هاتفٍ — تُقرأ النسبةُ لا العددُ المطلق (‏وأرقامُ `arm64` "
          "في `arm-time.yml`). ⭐ ورقمُ دقّةٍ بلا ثمنِه نصفُ قرار.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
