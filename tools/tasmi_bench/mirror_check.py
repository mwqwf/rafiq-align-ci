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
import re
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
# مجلداتٌ مولَّدةٌ أو مؤقّتةٌ لا يُسأل عن مرآتها
IGNORED_DIRS = {"__pycache__", "work", "requests", "patches", ".pytest_cache"}


def check_pair(HERE, src, sync, label):
    """يفحص مجلدَ مرآةٍ واحداً ضدّ أصله ويطبع، ويُعيد عددَ الانحرافات الباقية بعد العلاج.

    ⛔⛔ **خامسةُ الثغرات (2026-09-13) — والحارسُ كان يفحص مجلداً واحداً:** الفحصُ كان على
    `tools/tasmi_bench` وحدَه، **و`tools/finetune/` مُمرأًى أيضاً** وتناديه المساراتُ في كلّ
    شوط (`r2_put.py` في `emu-gate` و`tasmi-gate` و`arm-time` · و`prep.py` في `finetune-prep`).
    فوُجد فيه انحرافٌ قائمٌ **لم يكشفه أحد**: `target_audit.py` في المرآة هو **نسخةُ ما قبل
    D-316** (‏التي كانت تُسقط الآيةَ كلَّها فتعمى عن 3,582 آيةً — تغطيةُ 71.2٪ لا غير)، وتعليقُ
    `prep.py` باقٍ على الرقم المنسوخ. ⇒ **مرآةٌ تُخبر برقمٍ عُلم خطؤه** لو شُغِّلت.
    """
    if not os.path.isdir(src):
        print(f"⛔ لا مجلدَ أصلٍ لـ{label} في {src} — لا يُقرأ «لا انحراف» من غياب المقارَن به")
        return 1
    if not os.path.isdir(HERE):
        print(f"ℹ️ لا مجلدَ مرآةٍ لـ{label} هنا — لا يُفحَص")
        return 0
    print(f"— 🪞 **{label}**")
    a = argparse.Namespace(src=src, sync=sync)
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

    # ⛔⛔ **ورابعةٌ — والحارسُ نفسُه كان أعمى عنها (2026-09-13):** الحلقتان تمشيان على
    # **الملفّات المسطَّحة** وحدَها، والأصلُ فيه مجلدُ `engine_judge/` (‏حاكمُ المحرك بالكوتلن)
    # **لا وجودَ له في المرآة البتّة** — فقال الحارسُ «لا انحراف» وفي المرآة **تسعُ أدواتٍ
    # تناديه بالاسم** (`parity_full` · `riwaya_surface` · `locator_parity` …). فمتى نادى
    # مسارٌ إحداها **سقط بـ«لا ملفّ»**، وذلك أوّلُ ما وُجد الحارسُ ليمنعه.
    # ⭐⭐ **ولا يُعالَج بنسخٍ تلقائيّ:** `QuranRafiq` **خاصّ**، و`engine_judge/` **مصدرُ محرّكٍ
    # بالكوتلن** — ونسخُه إلى المستودع العامّ **نشرٌ لا مزامنة**. ⇒ الغيابُ هنا **قرارٌ** لا
    # سهو، وواجبُ الحارس أن يقول **مَن سيسقط به** لا أن يملأه.
    danger = []
    for d in sorted(os.listdir(a.src)):
        if not os.path.isdir(os.path.join(a.src, d)) or d in IGNORED_DIRS:
            continue
        if os.path.isdir(os.path.join(HERE, d)):
            continue          # مُمرأًى فعلاً — وفحصُ داخله بابٌ آخرُ يُفتح حين يُمرأى شيء
        callers = []
        # ⛔ **والنداءُ يُعرَف بصورته لا بذكرِ الاسم**: مِن مسارٍ (`engine_judge/…`) أو من اسمٍ
        #    مقتبَسٍ في `os.path.join` — ولولا ذلك لعُدَّ **كلُّ ملفٍّ يشرح المجلدَ في تعليقه**
        #    نادياً له. ⭐ وهذا الحارسُ نفسُه يذكره في شرحه ⇒ **لا يعدّ نفسَه**.
        pat = re.compile(r'%s/|["\']%s["\']' % (re.escape(d), re.escape(d)))
        for f in sorted(os.listdir(HERE)):
            if not f.endswith((".py", ".sh")) or f == os.path.basename(__file__):
                continue
            try:
                if pat.search(open(os.path.join(HERE, f), encoding="utf-8", errors="replace").read()):
                    callers.append(f)
            except OSError:
                continue
        if callers:
            danger.append((d, callers))
    for d, callers in danger:
        print(f"⛔ **مجلدُ `{d}/` في الأصل ولا وجودَ له في المرآة، و{len(callers)} أداةً هنا "
              f"تناديه** ⇒ أيُّ مسارٍ يشغّلها يسقط بـ«لا ملفّ»: " + " · ".join(callers[:6])
              + (" …" if len(callers) > 6 else ""))
    if danger:
        print("⭐ **وليس علاجُه نسخاً**: قد يكون الغيابُ مقصوداً (‏مصدرُ محرّكٍ لا يُنشر في "
              "مستودعٍ عامّ) ⇒ فإمّا أن يُمرأى بقرارٍ صريح، وإمّا **ألّا يُنادى من المرآة**.")

    if missing:
        # ⚠️ ملفٌّ هنا وليس في الأصل: **ليس انحرافاً** بالضرورة (قد يكون أداةَ مسارٍ خاصّةً
        # بالمستودع العامّ) — يُذكر ولا يُعالَج تلقائيّاً.
        print("ℹ️ هنا ولا أصلَ لها (تُراجَع بالعين): " + " · ".join(missing))
    if not drift:
        # ⛔ ولا تُقال «✅» مجرّدةً وفوقَها تنبيهٌ — فالعينُ تقرأ آخرَ سطرٍ وتمضي.
        print("✅ لا انحرافَ في الملفّات: كلُّ ملفٍّ له أصلٌ مطابقٌ بايتاً ببايت."
              + (" ⚠️ **لكن فوقَه ما يُنظر فيه.**" if danger else ""))
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=SRC, help="أصلُ tasmi_bench (‏وأخواتُه تُشتقّ منه)")
    ap.add_argument("--sync", action="store_true", help="انسخ الأصلَ فوق المرآة (لا يحذف ولا يضيف)")
    ap.add_argument("--only", default="", help="اسمُ مجلدٍ مُمرأًى واحدٍ يُفحَص وحدَه (‏للاختبار)")
    a = ap.parse_args()
    # 🪞 **كلُّ مجلدٍ مُمرأًى يُفحَص** — والقائمةُ هنا **مصدرٌ واحدٌ للحقيقة**: ما يُضاف إلى
    # المرآة يُضاف إليها، ⛔ **وإلّا فانحرافُه لا يراه أحدٌ حتى يُعطي رقماً خاطئاً**.
    pairs = [("tasmi_bench", os.path.dirname(os.path.abspath(__file__)), a.src)]
    tools_mir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    tools_src = os.path.dirname(a.src)
    for d in ("finetune",):
        pairs.append((d, os.path.join(tools_mir, d), os.path.join(tools_src, d)))
    rc = 0
    for label, mir, src in pairs:
        if a.only and a.only != label:
            continue
        rc = max(rc, check_pair(mir, src, a.sync, label))
    return rc


if __name__ == "__main__":
    sys.exit(main())
