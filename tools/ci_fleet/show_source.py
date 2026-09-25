#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""يطبع **مصدرَ القارئ المسجَّل في الكتالوج** — قراءةٌ محضةٌ تمنع التخمين.

    python tools/ci_fleet/show_source.py sousi/soufi_sousi douri/deban_douri

⛔ **العطبُ الذي وُلد منه (مقيسٌ 2026-09-21):** خمّنتُ قالبَ رابطٍ لـ`soufi_sousi`
من نمط قارئٍ آخر، فأُنفقت **محاذاةُ CTC كاملةً بأربعة أجزاءٍ وسقطت الأربعةُ**
(‏404 على كلّ سورة، وقد تحقّقتُ منه بعدها بنفسي). ⇒ ساعةٌ ونصفٌ من العمل ضاعت
لأنّ المصدرَ خُمّن ولم يُقرأ.
⛔ **وأخطرُ من الهدر:** قالبٌ خاطئٌ يصيب سوراً موجودةً عند قارئٍ آخر **يُنتج
فهرساً يحاذي صوتَ غيره** — وذاك تحريفٌ لا نقص. فالمصدرُ يُقرأ من الكتالوج دائماً.

⚖️ قراءةٌ محضة: تستعمل `catalog_bases()` نفسَها التي تستعملها حلقةُ الاسترجاع،
ولا تكتب في الدلو بايتاً ولا تمسّ حارساً.
"""
from __future__ import annotations
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass

sys.path.insert(0, str(Path(__file__).resolve().parent))
import restore_loop as rl                                            # noqa: E402


def catalog_file_tables(cat: dict) -> set:
    """مفاتيحُ `(الرواية، القارئ)` لكلّ قارئٍ له جدولُ `files` في الكتالوج.

    ⛔ **سببُها مقيسٌ (2026-09-25):** كانت الأداةُ تطبع `{base}{s:03d}.mp3`
    لكلّ قارئ، وقرّاءُ مجلّدات archive.org (‏مثل `warsh/gharbi_warsh`
    وأسماؤه `ar_036_Mustapha_Gharbi_Warsh.mp3`) لا يجمعهم قالبٌ رقميّ —
    فيعطي القالبُ 404 **ويُحكم على مصدرٍ حيٍّ كذباً بأنّه ميت**.
    ⚖️ دالّةٌ محضة على كتالوجٍ مقروء: بلا شبكةٍ ولا دلو، فتُختبر.
    """
    out = set()
    for r in cat.get("riwayat", []):
        riw = r.get("id") or r.get("key")
        for rc in r.get("reciters", []):
            if rc.get("files"):
                out.add((riw, rc.get("id")))
    return out


def fetch_catalog() -> dict:
    """الكتالوجُ نفسُه من الدلو — قراءةٌ محضة بعميل `restore_loop`."""
    import json                                                      # noqa: PLC0415
    cl, b = rl.s3()
    return json.loads(cl.get_object(Bucket=b,
                                    Key="catalog/reciters.json")["Body"].read())


def describe(a: str, bases: dict, folders: set) -> tuple[list[str], int]:
    """أسطرُ المخرَج لقارئٍ واحد ورمزُ الخروج — بلا شبكة، فتُختبر."""
    riwaya, _, rid = a.partition("/")
    base = rl.source_base(bases, riwaya, rid, 1)
    if not base:
        return [f"⛔ {a}\tلا مصدرَ في الكتالوج — ولا يُخمَّن"], 1
    if (riwaya, rid) in folders:
        # مضيفُ مجلّد: الأساسُ وحدَه بلا `{s:03d}`، والأسماءُ من جدول files.
        folder = base.rstrip("/")
        return [f"✅ {a}\t{folder}",
                "   📂 مجلّدٌ لا قالب: أسماءُ الملفّات تُحلّ من جدول `files` في "
                "الكتالوج (‏`resolve_url.py`) — فالقالبُ الرقميُّ 404 لا يعني موتَ المصدر.",
                f"   ⇒ الأداةُ المناسبة `realign_surah.yml` بـ`url_template={folder}` "
                f"و`reciter_id={rid}`؛ ⛔ ولا يصلح `ctc_splice` ولا `whisper_splice` "
                "(‏يشترطان قالباً رقميّاً)."], 0
    return [f"✅ {a}\t{base}{{s:03d}}.mp3"], 0


def main() -> int:
    args = sys.argv[1:]
    bases = rl.catalog_bases()
    if not args:
        print(f"الكتالوجُ فيه {len(bases)} مدخلاً. مرّر <رواية>/<قارئ> لطباعة مصدره.")
        return 0
    folders = catalog_file_tables(fetch_catalog())
    rc = 0
    for a in args:
        lines, code = describe(a, bases, folders)
        print("\n".join(lines))
        rc = rc or code
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
