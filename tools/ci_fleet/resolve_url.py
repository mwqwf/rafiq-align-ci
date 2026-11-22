#!/usr/bin/env python3
"""عنوانُ سورةٍ من قالبٍ **أو** من جدول أسماء الكتالوج.

⛔ **سببُ وجوده مقيسٌ بثمنه (2026-09-11):** قرّاءٌ على archive.org أساسُهم
**مجلَّدٌ** لا قالبَ فيه `{s:03d}`، وأسماءُ ملفّاتهم مكتوبةٌ في جدول `files`
بالكتالوج — يقرؤها `batch_run` و`QuranRepository.kt` في التطبيق. وكان
`realign_surah` يشترط القالبَ، فتعذّر **إصلاحُ سورةٍ واحدة** عندهم فيُردُّ
مصحفٌ كاملٌ لعلّةٍ في سورتين (‏`janaini_qalun`: ابتلاعٌ في س33 و38 آيةً
غائبةً في س37، وتغطيتُه 98.8%).

⛔ ولا تخمينَ هنا: إمّا قالبٌ يُنسَّق، وإمّا اسمٌ **مقروءٌ** من الجدول. وما لم
يُوجد له اسمٌ يُوقِف التنزيلَ برسالةٍ ناطقة — فعنوانٌ مخمَّنٌ يُخرج 404 في كلّ
سورة، **وذاك عطبٌ صامتٌ أسوأُ من توقّفٍ ناطق**.
"""
import os
import sys
from urllib.parse import quote, unquote


def href_filename(name: str) -> str:
    """يرمّز اسم الملف للمسار **مرة واحدة**.

    جدول `files` في الكتالوج قد يُكتب مرمّزاً سلفاً (`add_surah_reciter.py`).
    `quote` على اسمٍ مرمّز يحيل `%` إلى `%25` فيسقط التنزيل — قيس 2026-11-22
    على `shaykhna_qalun` س29: الاسم كان `029%20…العنكبوت.mp3` فصار
    `029%2520%25D8…`، وffmpeg قرأ ملفّاً ليس MP3 (`Invalid argument`).
    `unquote` ثم `quote` يعيد الترميز الصحيح للاسم الخام والمرمّز معاً.
    """
    return quote(unquote(name), safe="")


def resolve_surah_url(tpl: str, surah: int, names: dict | None = None) -> str:
    """يبني عنوان السورة: قالب `{s:03d}` أو `أساس/اسم` من الجدول."""
    if "{s" in tpl:
        return tpl.format(s=surah)
    if not names or surah not in names:
        raise SystemExit(f"⛔ لا اسمَ لسورة {surah} في جدول الكتالوج — لا تنزيلَ بتخمين")
    return tpl.rstrip("/") + "/" + href_filename(names[surah])


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit("الاستعمال: resolve_url.py <رقم السورة>")
    surah = int(sys.argv[1])
    tpl = os.environ["URLT"]
    names = None
    if "{s" not in tpl:
        root = os.environ.get("GITHUB_WORKSPACE") or os.getcwd()
        sys.path.insert(0, os.path.join(root, "tools", "alignment"))
        from batch_run import catalog_files  # noqa: PLC0415
        names = catalog_files(os.environ["RID"])
    print(resolve_surah_url(tpl, surah, names))


if __name__ == "__main__":
    main()
