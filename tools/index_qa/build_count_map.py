#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""يبني **خريطةَ عدٍّ** من ترقيم رواية المجمَّع إلى خانات حفص الـ6236.

    python tools/index_qa/build_count_map.py warsh > tools/index_qa/countmap_warsh.json

## لماذا (‏قرار المشرف، 2026-09-05)

`mp3quran` يعطي توقيتَ الآية **بعدّ الرواية** (المدنيّ لورش/قالون/الدوري/
السوسي)، وفهرسُنا كلُّه **بعدّ حفص الكوفيّ** — وهو شرطُ المزامنة في البنية
كلِّها (‏`flatAyah` مفتاحُ الصوت والحفظ والتوقيتات). فبلا خريطةٍ يسقط 59.3%
من التوقيتات على حارس الغياب، وهو ما وقع مقيساً على ستّة قرّاء.

## المصدرُ والمنهج — ولا اجتهادَ فيه

الخريطةُ تُشتقّ من **حزم المجمَّع نفسِها** (‏`assets-archive/qurancomplex/`)
مقابلَ نصِّ الرواية **المُعاد ترقيمُه** في أصول التطبيق (`text_<riwaya>.jz`)
— وكلاهما **الكلماتُ نفسُها بالترتيب نفسِه**، والفارقُ موضعُ الفواصل وحده.
⇒ المطابقةُ **بعدِّ الكلمات التراكميّ**: نهايةُ آية المصدر عند الكلمة رقم `W`،
فيُنظر في أيّ خانةِ حفصٍ تقع `W`. **لا محاذاةَ احتمالية ولا تخمين.**

⛔ **وحارسٌ يردّ الخريطةَ كلَّها:** إن لم يتطابق **مجموعُ كلمات الرواية**
بالضبط بين المصدر والنصّ المُعاد ترقيمُه في سورةٍ ما، فالسورةُ **لا تُخرَّط**
وتُسمَّى — لأن اختلافَ الكلمات يعني أنّ أحدَ النصّين ليس الآخر، وخريطةٌ
مبنيّةٌ على ذلك تُزيح آياتٍ في مصحفٍ كامل.

## المخرَج

`{"<سورة>": {"<آية المصدر>": [أوّلُ خانةِ حفص، آخرُها]}}` — والمدى يتّسع حين
تقابل آيةُ المصدر أكثرَ من خانةِ حفص، ويتكرّر حين تقابل عدّةُ آياتٍ خانةً
واحدة (‏وحينها يُدمج التوقيت: من بداية الأولى إلى نهاية الأخيرة).
"""
from __future__ import annotations

import gzip
import json
import os
import re
import sys
import unicodedata
import zipfile

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:                                     # noqa: BLE001
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ASSETS = os.path.join(ROOT, "core", "quran", "src", "main", "assets", "quran")
ZIPS = os.path.join(ROOT, "assets-archive", "qurancomplex")
PKG = {"warsh": "UthmanicWarsh_v2-1.zip", "qalun": "UthmanicQaloun_v2-1.zip",
       "douri": "UthmanicDouri_v2-0.zip", "sousi": "UthmanicSousi_v2-0.zip",
       "shuba": "UthmanicShuba_v2-0.zip", "hafs": "UthmanicHafs_v2-0.zip"}
END_MARK = re.compile(r"\s*[﴾-﷿ﹰ-﻿۝-۞]+\s*$")


def norm(w: str) -> str:
    out = []
    for ch in unicodedata.normalize("NFC", w):
        o = ord(ch)
        if 0x064B <= o <= 0x065F or o == 0x0670 or 0x06D6 <= o <= 0x06ED or o == 0x0640:
            continue
        ch = {"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ٲ": "ا", "ٳ": "ا",
              "ؤ": "و", "ئ": "ي", "ء": "", "ى": "ي", "ة": "ه"}.get(ch, ch)
        out.append(ch)
    return "".join(out)


def _arabic(w: str) -> bool:
    """كلمةٌ فيها حرفٌ عربيٌّ أصليّ — تُسقط رموزَ ترقيم الآي (‏ﰀ) والفواصل.

    ⛔ سببُه مقيس: رمزُ رقم الآية في حزم المجمَّع يسبقه **مسافةٌ غيرُ فاصلة**
    (‏U+00A0) فلا يلتقطه حذفُ آخرِ السطر، فيُعدّ كلمةً — فتزيد كلماتُ الحزمة
    على كلماتِنا بمقدارِ عددِ الآيات (‏قِيس: 2926 مقابل 2804 في سورة 5).
    """
    return any("ء" <= ch <= "ي" for ch in w)


def words(t: str) -> list:
    return [n for n in (norm(w) for w in END_MARK.sub("", t).split())
            if n and _arabic(n)]


def main() -> None:
    riwaya = sys.argv[1] if len(sys.argv) > 1 else "warsh"
    if riwaya not in PKG:
        sys.exit(f"⛔ روايةٌ غيرُ معروفة: {riwaya}")
    idx = json.loads(gzip.open(os.path.join(ASSETS, "index.jz")).read().decode("utf-8"))
    txt = json.loads(gzip.open(os.path.join(ASSETS, f"text_{riwaya}.jz")).read().decode("utf-8"))
    z = zipfile.ZipFile(os.path.join(ZIPS, PKG[riwaya]))
    member = next(n for n in z.namelist() if n.endswith(".json"))
    rows = json.loads(z.read(member).decode("utf-8-sig"))

    src = {}
    for r in rows:
        s = int(r.get("sura_no") or r.get("surah") or r.get("sura"))
        a = int(r.get("aya_no") or r.get("ayah") or r.get("aya"))
        t = r.get("aya_text") or r.get("text") or r.get("aya_text_emlaey") or ""
        src.setdefault(s, {})[a] = words(t)

    out, skipped = {}, []
    for meta in idx["surahs"]:
        s, start, n = meta["n"], meta["start"], meta["ayahs"]
        hafs_slots = [words(txt[start + i]) for i in range(n)]
        srcs = src.get(s) or {}
        if not srcs:
            skipped.append((s, "لا سورةَ في الحزمة")); continue
        # ⛔ الحارس: مجموعُ الكلمات يجب أن يتطابق حرفاً.
        a_all = [w for i in sorted(srcs) for w in srcs[i]]
        b_all = [w for slot in hafs_slots for w in slot]
        if a_all != b_all:
            skipped.append((s, f"الكلماتُ تختلف ({len(a_all)} مقابل {len(b_all)})"))
            continue
        bounds, acc = [], 0
        for slot in hafs_slots:
            acc += len(slot)
            bounds.append(acc)                    # نهايةُ كلِّ خانةِ حفصٍ تراكمياً
        cur, m = 0, {}
        for a in sorted(srcs):
            cur += len(srcs[a])
            first = next(i for i, e in enumerate(bounds) if e >= cur - len(srcs[a]) + 1)
            last = next(i for i, e in enumerate(bounds) if e >= cur)
            m[str(a)] = [first + 1, last + 1]
        out[str(s)] = m
    json.dump({"riwaya": riwaya, "map": out,
               "skipped": [{"surah": s, "why": w} for s, w in skipped]},
              sys.stdout, ensure_ascii=False)
    print(file=sys.stderr)
    print(f"{riwaya}: خُرِّطت {len(out)} سورة · تُركت {len(skipped)}", file=sys.stderr)
    for s, w in skipped[:8]:
        print(f"  ⛔ س{s}: {w}", file=sys.stderr)


if __name__ == "__main__":
    main()
