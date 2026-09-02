# -*- coding: utf-8 -*-
"""إعادة تصنيف الحدود المصقولة بعتبةِ صمتٍ مرفوعة — بلا خادم وبلا استبدال.

**السياق:** ‏`adaptive-1/2` قبل إصلاح `f1ea508` كانتا تُطبّقان التكيّف على **كل**
نداء `silences()`، ومنها نداء «الصمت الدقيق» في الصقل (‏`rel=0.06`). فالحدّ الذي
رُقّي إلى HIGH بعد أن «التُقط على صمت» ربما التُقط على **طاقةٍ منخفضة داخل
الكلام** لا على صمتٍ حقيقي ⇒ **ترقيتُه غير مُبرهنة**.

**ما تفعله الأداة:** تُنزل كل مدخلٍ `refined` وHIGH في السور المشبوهة إلى MED
بوسم `reclassified` وسببه، **وتكتب ملفاً جديداً ببصمةٍ جديدة ولا تلمس القديم**.

⛔ **ما لا تفعله:** لا تحذف حدّاً ولا تغيّر توقيتاً — **الزمن يبقى كما هو**؛
إنما تُسحب **الشهادة** لا القيمة. فالحدّ قد يكون صحيحاً، وإنما سقط برهانه.

⛔ **ولا تخمّن السور المشبوهة:** تُمرَّر صراحةً (`--surahs` أو `--all`)، لأن
الفهرس لا يحمل — في نسخه الأولى — ختمَ النسخة التي بنت كل سورة.

    python tools/tasmi_bench/reclassify_refined.py --index a.jz --surahs 1-9,36 --out b.jz
    python tools/tasmi_bench/reclassify_refined.py --index a.jz --all --dry-run
"""
import argparse
import collections
import hashlib
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "tools", "alignment"))
from common import read_jz, write_jz  # noqa: E402

REASON = ("صُقل بعتبة صمتٍ مرفوعة (تسرّب التكيّف إلى نداء الصقل قبل f1ea508) "
          "⇒ الالتقاط غير مُبرهن؛ الزمن كما هو والشهادة مسحوبة")


def parse_surahs(spec):
    out = set()
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-")
            out.update(range(int(a), int(b) + 1))
        elif part:
            out.add(int(part))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", required=True)
    ap.add_argument("--out")
    ap.add_argument("--surahs", help="مثال: 1-9,36,78")
    ap.add_argument("--all", action="store_true", help="كل السور مشبوهة")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    if not args.all and not args.surahs:
        sys.exit("⛔ حدّد السور المشبوهة (`--surahs`) أو `--all` — الأداة لا تخمّن")
    target = None if args.all else parse_surahs(args.surahs)

    ti = read_jz(args.index)
    before = collections.Counter(e.get("confBand") or "?" for e in ti["entries"])
    touched = 0
    for e in ti["entries"]:
        s = int(e["ayahId"].split(":")[0])
        if target is not None and s not in target:
            continue
        if not e.get("refined") or e.get("confBand") != "HIGH":
            continue
        e["confBand"] = "MED"
        e["conf"] = min(float(e.get("conf", 0.6)), 0.79)   # دون عتبة HIGH
        e["reclassified"] = "refined-on-raised-vad"
        e["reclassifiedReason"] = REASON
        touched += 1
    after = collections.Counter(e.get("confBand") or "?" for e in ti["entries"])

    print(f"مدخلات: {len(ti['entries'])} · سور مشبوهة: "
          f"{'كلها' if target is None else len(target)}")
    print(f"  نُزّلت من HIGH إلى MED: **{touched}**")
    print(f"  قبل: {dict(before)}")
    print(f"  بعد: {dict(after)}")
    if args.dry_run:
        print("(تجربة جافّة — لم يُكتب شيء)")
        return
    if not args.out:
        sys.exit("⛔ حدّد `--out`: الأداة لا تكتب فوق الفهرس القديم بحال")
    if os.path.abspath(args.out) == os.path.abspath(args.index):
        sys.exit("⛔ المخرج هو المدخل — المقابلة تحتاج النسختين معاً")
    ti["reclassify"] = {"tool": "reclassify_refined.py", "at": int(time.time()),
                        "count": touched, "reason": REASON,
                        "scope": "all" if target is None else sorted(target),
                        "sourceIndex": os.path.basename(args.index)}
    write_jz(args.out, ti)
    sha = hashlib.sha256(open(args.out, "rb").read()).hexdigest()
    print(f"✅ كُتب {args.out} · sha256 {sha[:16]}… (الأصل لم يُمَس)")


if __name__ == "__main__":
    main()
