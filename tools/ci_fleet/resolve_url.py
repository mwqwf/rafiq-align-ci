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
from urllib.parse import quote


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit("الاستعمال: resolve_url.py <رقم السورة>")
    surah = int(sys.argv[1])
    tpl = os.environ["URLT"]
    if "{s" in tpl:
        print(tpl.format(s=surah))
        return
    root = os.environ.get("GITHUB_WORKSPACE") or os.getcwd()
    sys.path.insert(0, os.path.join(root, "tools", "alignment"))
    from batch_run import catalog_files  # noqa: PLC0415
    names = catalog_files(os.environ["RID"])
    if not names or surah not in names:
        sys.exit(f"⛔ لا اسمَ لسورة {surah} في جدول الكتالوج — لا تنزيلَ بتخمين")
    print(tpl.rstrip("/") + "/" + quote(names[surah]))


if __name__ == "__main__":
    main()
