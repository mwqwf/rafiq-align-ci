# -*- coding: utf-8 -*-
"""يقسم السور 114 إلى `n` حزمٍ متوازنة **بمجموع الآي** — لا بعددها.

⛔ سبب وجوده (عيبٌ قاتل كشفه github-f4، 2026-09-02): `batch_run.py` **تسلسليّ
بلا توازٍ داخلي** (فحصتُه: صفر `Thread`/`Pool`/`multiprocessing`)، و`JOBS`
كان يُطبَع ولا يُستعمل. ⇒ عدّاءٌ بأربع أنوية كان يعمل **بنواةٍ واحدة**،
والقارئ يحتاج 5–6 ساعات فيقتله سقف الست ساعات ⇒ **صفر قارئ مكتمل**.

⛔ والقسمة **بمجموع الآي لا بعدد السور**: البقرة وحدها 286 آية بينما الكوثر 3،
فقسمةٌ بالعدد تعطي حزمةً تنتهي في دقائق وأخرى تلتهم المهلة كلها — وأبطأ حزمة
هي زمن الشريحة كله. والقسمة الجشعة (الأكبر أولاً إلى أخفّ حزمة) تقارب المثالي
هنا وتكفي.

    python tools/ci_fleet/make_bins.py 4          # أربع حزم مفصولة بمسافة
    python tools/ci_fleet/make_bins.py 4 --show   # مع مجموع الآي لكل حزمة
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "alignment"))
from common import load_index  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def ayah_counts():
    ix = load_index()
    out = {}
    for s in ix["surahs"]:
        n = s.get("n") or s.get("number") or s.get("index")
        c = s.get("ayahs") or s.get("ayahCount") or s.get("count")
        if n and c:
            out[int(n)] = int(c)
    if len(out) != 114:
        raise SystemExit(f"⛔ فهرس السور غير مكتمل: {len(out)}/114")
    return out


def bins(n):
    counts = ayah_counts()
    order = sorted(counts, key=lambda s: -counts[s])     # الأكبر أولاً
    packs = [[] for _ in range(n)]
    load = [0] * n
    for s in order:
        i = load.index(min(load))                        # إلى أخفّ حزمة
        packs[i].append(s)
        load[i] += counts[s]
    return [sorted(p) for p in packs], load


def fmt(surahs):
    """يضغط القائمة إلى مدياتٍ مفهومة: 1-3,7,90-114."""
    out, i = [], 0
    while i < len(surahs):
        j = i
        while j + 1 < len(surahs) and surahs[j + 1] == surahs[j] + 1:
            j += 1
        out.append(str(surahs[i]) if i == j else f"{surahs[i]}-{surahs[j]}")
        i = j + 1
    return ",".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("n", type=int)
    ap.add_argument("--show", action="store_true")
    a = ap.parse_args()
    packs, load = bins(max(1, a.n))
    if a.show:
        for p, l in zip(packs, load):
            print(f"{l:>5} آية · {len(p):>3} سورة · {fmt(p)}")
        print(f"أثقل حزمة {max(load)} · أخفّ {min(load)} · "
              f"الفرق {max(load) - min(load)} آية")
    else:
        print(" ".join(fmt(p) for p in packs))


if __name__ == "__main__":
    main()
