# -*- coding: utf-8 -*-
"""🪞 **حارسُ المرآة** — أيُّ ملفٍّ في `rafiq-align-ci` تخلّف عن أصله في `QuranRafiq`؟

⛔ **لِمَ وُجد:** أدواتُ المقعد تعيش في مستودعَين — الأصلُ في `QuranRafiq/tools/tasmi_bench`
والمرآةُ هنا حيث تعمل مسارات GitHub. **وانحرافُ المرآة لا يصرخ: يعطي رقماً معقولاً وخاطئاً.**
وقد كلّف هذا ليلةَ 2026-09-12/13 ثلاثَ مرّات:

1. مفتاحُ نموذجٍ أُضيف في الأصل ولم يُنسخ ⇒ مُرِّر الاسمُ حرفاً إلى `whisper-cli` فمات الشوطُ
   كلُّه بـ«failed to initialize whisper context» — **وكلُّ بندٍ فيه خطأ**.
2. `cli_time.py` أُصلح في الأصل ولم يُنسخ ⇒ شوطان على `arm64`.
3. **وأخطرُها صامت:** `scorer.py` — **الحاكمُ نفسُه** — تخلّف عن ثلاث قواعدِ إمالةٍ
   (‏D-402/403/404) و`snr_probe.py` بقي على عتبتَي 8/15 وقد صارتا 14/18 (‏D-344)
   ⇒ **مرآةٌ تحكم بغير ما يحكم به المحرك، وتطبع نسبةً لا تنقصها إلّا الصحّة.**

    python tools/tasmi_bench/mirror_check.py            # يطبع ويخرج بـ1 إن وُجد انحراف
    python tools/tasmi_bench/mirror_check.py --sync     # ينسخ الأصلَ فوق المرآة
"""
import argparse
import filecmp
import os
import shutil
import sys

# ⛔ **ثالثةُ ثلاثٍ في ليلةٍ:** أداةٌ تُشغَّل بلا بيئةٍ مضبوطةٍ تسقط بـ`UnicodeEncodeError`
# على رسالةِ **نجاحها** فيُظنّ العطبُ في المفحوص لا في الفاحص. ⇒ تفرض ترميزها بنفسها.
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.normpath(os.path.join(HERE, "..", "..", "..", "QuranRafiq", "tools", "tasmi_bench"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=SRC)
    ap.add_argument("--sync", action="store_true", help="انسخ الأصلَ فوق المرآة (لا يحذف ولا يضيف)")
    a = ap.parse_args()
    if not os.path.isdir(a.src):
        raise SystemExit(f"⛔ لا مجلدَ أصلٍ في {a.src} — لا يُقرأ «لا انحراف» من غياب المقارَن به")

    drift, missing = [], []
    for f in sorted(os.listdir(HERE)):
        # ⛔⛔ **ولا `.py` وحدَها — ثغرةٌ وُجدت 2026-09-13 (D-374 وما بعده):** جسمُ **كلِّ** شوط
        # محاكٍ هو `ci_emu_run.sh` (‏وهو الذي يُنشئ الأذرعَ ويثبّت لغتَها)، وخُطَطُ الحقن
        # `inject_plan*.json` هي **المدخَلُ المقيسُ** الذي تُحسب عليه أرقامُ الحقن. فكان
        # الحارسُ يقرأ `.py` فقط ⇒ **انحرافُ سطرٍ في صدفةٍ أو بندٍ في خطّةٍ يمرّ صامتاً**
        # ويعطي أرقاماً معقولةً لعيّنةٍ غيرِ العيّنة. وعلّةُ وجودِ الحارس عينُها تُوجِب توسيعَه.
        # ⭐ (‏وفُحص يومَ التوسيع فلم يكن هناك انحرافٌ — فالتوسيعُ **منعٌ** لا إصلاح.)
        if not f.endswith((".py", ".sh", ".json")):
            continue
        o = os.path.join(a.src, f)
        if not os.path.exists(o):
            missing.append(f)
        elif not filecmp.cmp(os.path.join(HERE, f), o, shallow=False):
            drift.append(f)

    # ⛔⛔ **وثغرةٌ ثالثةٌ سُدّت 2026-09-13 — وقعت في اليوم نفسِه:** الحلقةُ تمشي على **المرآة**،
    # فملفٌّ **في الأصل ولا نسخةَ له هنا** كان **لا يُرى البتّة**: أُضيف `hyps_time_ab.py` إلى
    # `QuranRafiq` وأُشير إليه في خطوةِ مسارٍ، فقال الحارسُ «لا انحراف» **وكان المسارُ سيسقط**
    # بـ«لا ملفّ» في العدّاء. ⇒ يُسرد الأصلُ أيضاً، والغائبُ عن المرآة **انحرافٌ يُنسخ بـ`--sync`**.
    absent = []
    for f in sorted(os.listdir(a.src)):
        if not f.endswith((".py", ".sh", ".json")):
            continue
        if not os.path.exists(os.path.join(HERE, f)):
            absent.append(f)

    if absent:
        print("⛔ **في الأصل ولا نسخةَ لها في المرآة** (‏وهذه تُسقط المساراتَ التي تناديها): "
              + " · ".join(absent))
        if a.sync:
            for f in absent:
                shutil.copyfile(os.path.join(a.src, f), os.path.join(HERE, f))
            print("↻ نُسخت الغائبةُ — أودِعها بمسارٍ صريح.")
        else:
            drift = drift + absent   # كي لا يخرج بـ0 والمرآةُ ناقصة

    if missing:
        # ⚠️ ملفٌّ هنا وليس في الأصل: **ليس انحرافاً** بالضرورة (قد يكون أداةَ مسارٍ خاصّةً
        # بالمستودع العامّ) — يُذكر ولا يُعالَج تلقائيّاً.
        print("ℹ️ هنا ولا أصلَ لها (تُراجَع بالعين): " + " · ".join(missing))
    if not drift:
        print("✅ لا انحراف: كلُّ ملفٍّ له أصلٌ مطابقٌ بايتاً ببايت.")
        return 0
    print("⛔ **انحرافُ مرآة** في " + str(len(drift)) + " ملفّاً:")
    for f in drift:
        print("   ≠ " + f)
    if a.sync:
        for f in drift:
            shutil.copyfile(os.path.join(a.src, f), os.path.join(HERE, f))
        print("↻ نُسخ الأصلُ فوق المرآة — راجع `git diff` قبل الإيداع.")
        return 0
    print("⇒ `python tools/tasmi_bench/mirror_check.py --sync` ثمّ أودِع بمسارات صريحة.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
