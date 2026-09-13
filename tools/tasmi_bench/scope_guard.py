# -*- coding: utf-8 -*-
"""🚧 **حاجزُ النطاق** — يمنع إيداعَ ملفٍّ خارج نطاق جلسة محرّك التسميع.

⛔ **لِمَ حاجزٌ لا تذكير:** كُنس دفترُ جلسة الفهرسة (`docs/qa/PROMOTIONS.md`) **مرّتين في
ليلةٍ واحدة** بـ`git add docs/qa/` — والثانيةُ **بعد ساعةٍ من كتابة القاعدة بنصّها في إيداع**.
⇒ التذكيرُ ثبت فشلُه تجريبيّاً؛ والذي يُوقف الخطأ **ما يخرج بـ1 قبل الإيداع** لا ما يُكتب.

    python tools/tasmi_bench/scope_guard.py <مسارات> && git commit -F - -- <المسارات نفسُها>
    python tools/tasmi_bench/scope_guard.py --selftest      # يختبر الحاجزَ نفسَه

⭐ **والإيداعُ بقائمة مسارات** (`git commit -- <paths>`) هو العلاجُ لا إلغاءُ الترحيل: إلغاؤه
يحتاج أوامرَ يمنعها حارسُ الشجرة المشتركة، **والإيداعُ المقيَّد بمسارات يودِع ما سُمّي وحدَه**
مهما كان في المرحَّل — فلا يُكنس عملُ جلسةٍ أخرى ولو رُحِّل خطأً.

والنطاقُ نصُّ المالك حرفاً: `engine/recitation/` · `tools/tasmi_bench/` · `tools/finetune/` ·
`docs/qa/TASMI_SCOREBOARD.md`. وأُضيف تسليمُ الصباح ومساراتُ الحوسبة لأنّهما تكليفُ الليلة.
⛔ وما عداه — `app/` و`feature/` والترجمات (جلسةُ الواجهة) · `tools/alignment*` و
`timings-staging/` و`docs/qa/PROMOTIONS.md` (جلسةُ الفهرسة) — **لا يُودَع من هنا**.
"""
import posixpath
import subprocess
import sys

# ⛔ **الحاجزُ لا يعتمد على بيئةٍ يُنسى ضبطُها:** سقط أوّلَ استعمالٍ جدّيٍّ بـ`UnicodeEncodeError`
# على رسالة **نجاحه** لأنّ `PYTHONIOENCODING` لم تُصدَّر في ذلك الأمر — فمنع إيداعاً سليماً
# وأوهم أنّ العطبَ في العمل لا في الحارس. ⇒ يفرض الترميزَ على مخرَجه بنفسه.
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ALLOW = (
    "engine/recitation/",
    "tools/tasmi_bench/",
    "tools/finetune/",
    "docs/qa/TASMI_SCOREBOARD.md",
    "docs/qa/HANDOFF_2026-09-13.md",
    "docs/qa/CLOUD_ENGINE.md",
    "docs/ops/CLOUD_ENGINE_DUTY.md",
    "docs/ops/CLOUD_ENGINE_LAUNCH.md",
    ".github/workflows/",
)


def canon(p):
    """يُعيد المسارَ بصورةٍ واحدةٍ للمقارنة، أو `None` إن كان **خارجاً بالبناء**.

    ⛔⛔ **والحاجزُ كان يُخدَع بمسارٍ صحيحٍ نحويّاً (2026-09-13):** المقارنةُ كانت
    `p.startswith("tools/tasmi_bench/")` على النصّ الخامّ ⇒
    **`tools/tasmi_bench/../../app/MainActivity.kt` يجتازه** وهو يكتب في `app/`!
    وكذلك `./tools/tasmi_bench/x.py` **يُرفض** وهو داخلُ النطاق (‏إنذارٌ كاذبٌ يُعلّم تخطّي
    الحارس). ⇒ يُطبَّع المسارُ أوّلاً (‏شرطةُ وندوز · `./` · `..`)، **والمطلقُ وما يخرج
    بـ`..` يُرفضان بلا نظرٍ في القائمة**.
    ⭐ وقاعدةُ المالك: تعديلُ حارسٍ يجعله **أصعبَ خداعاً** لا أوسعَ قبولاً.
    """
    q = (p or "").strip().replace("\\", "/")
    if not q:
        return None
    if q.startswith("/") or (len(q) > 1 and q[1] == ":"):
        return None                      # مطلقٌ: لا يُقاس بنطاقٍ نسبيّ
    q = posixpath.normpath(q)
    if q == ".." or q.startswith("../"):
        return None                      # خرج من الشجرة
    return q


def outside(paths):
    bad = []
    for p in paths:
        q = canon(p)
        if q is None or not any(q.startswith(a) for a in ALLOW):
            bad.append(p)
    return bad


def selftest():
    """⛔ حارسٌ يُختبر قبل أن يُستعمل (قاعدةُ المالك) — وفيه حالتا الخداع اللتان كان يقع فيهما."""
    ok = ["tools/tasmi_bench/x.py", "./tools/tasmi_bench/x.py", "tools\\tasmi_bench\\x.py",
          "engine/recitation/src/main/kotlin/A.kt", "docs/qa/TASMI_SCOREBOARD.md",
          ".github/workflows/emu-gate.yml", "tools/tasmi_bench/./sub/../y.py"]
    bad = ["app/MainActivity.kt", "tools/tasmi_bench/../../app/MainActivity.kt",
           "tools/tasmi_bench/../index_qa/promote.py", "/etc/passwd", "C:/tmp/x",
           "tools/tasmi_benchX/y.py", "docs/qa/PROMOTIONS.md", "../outside.py", "",
           "tools/alignment/common.py"]
    f1 = outside(ok)
    f2 = [p for p in bad if p not in outside(bad)]
    if f1 or f2:
        print("⛔ فشلَ الاختبارُ الذاتيّ — رُفض داخلٌ: " + str(f1) + " · واجتاز خارجٌ: " + str(f2))
        return 1
    print(f"✅ اختبارٌ ذاتيّ: {len(ok)} داخلاً قُبلت و{len(bad)} خارجاً رُدَّت "
          "(ومنها `tools/tasmi_bench/../../app/…` — الخداعُ الذي كان يجتاز).")
    return 0


def main():
    args = [a for a in sys.argv[1:] if a.strip()]
    if args == ["--selftest"]:
        return selftest()
    if args:
        # 🎯 الوضعُ المفضَّل: تُفحص **المسارات المنويّة** قبل بنائها أمرَ إيداعٍ مقيَّد بها.
        bad = outside(args)
        what = "المسارات المطلوبة"
        checked = args
    else:
        r = subprocess.run(["git", "diff", "--cached", "--name-only"], capture_output=True, text=True)
        if r.returncode:
            raise SystemExit("⛔ تعذّر قراءةُ المرحَّل: " + r.stderr.strip())
        checked = [p.strip() for p in r.stdout.splitlines() if p.strip()]
        if not checked:
            raise SystemExit("⛔ لا شيءَ مرحَّلٌ — إيداعٌ فارغٌ ليس إيداعاً")
        bad = outside(checked)
        what = "المرحَّل"
    if bad:
        print("⛔ **خارجَ نطاق هذه الجلسة في " + what + ":**")
        for p in bad:
            print("   ⛔ " + p)
        print("⇒ أودِع **بقائمة مسارات**: `git commit -F - -- <ملفّاتك وحدَها>`")
        print("   فيُودَع ما سُمّي وحدَه ولو بقي غيرُه مرحَّلاً. ولا تُلغِ الترحيل بأوامرَ يمنعها الحارس.")
        print("   (‏وسببُ الوقوع دائماً واحد: `git add <مجلّد>` — وهو `git add -A` مصغَّراً.)")
        return 1
    print("✅ " + what + ": " + str(len(checked)) + " ملفّاً كلُّها داخلَ النطاق.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
