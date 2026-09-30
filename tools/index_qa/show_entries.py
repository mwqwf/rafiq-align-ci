#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""طباعةُ مداخل سورٍ من فهرسٍ في الدلو — قارئٌ محض للمقابلة (2026-09-30).

    python tools/index_qa/show_entries.py <مفتاح .jz> <سور بفواصل> [مفتاحٌ ثانٍ للمقابلة]

يطبع لكلّ آية: البدء · النهاية · النطاق · والرابط. ومع مفتاحٍ ثانٍ يطبع الفرقَ
بين الفهرسين آيةً آية (‏ما تغيّر وما لم يتغيّر) — لمعرفة أيّ الحدود أحدثها التحويل.
"""
from __future__ import annotations

import gzip
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run import s3  # noqa: E402


def load(cl, b, key):
    return json.loads(gzip.decompress(cl.get_object(Bucket=b, Key=key)["Body"].read()).decode("utf-8"))


def rows(idx, surahs):
    return {e["ayahId"]: e for e in idx.get("entries") or []
            if int(e["ayahId"].split(":")[0]) in surahs}


def main() -> None:
    if len(sys.argv) < 3:
        sys.exit("الاستعمال: show_entries.py <مفتاح> <سور> [مفتاحٌ ثانٍ]")
    surahs = {int(s) for s in sys.argv[2].split(",") if s.strip()}
    cl, b = s3()
    a = load(cl, b, sys.argv[1])
    ra = rows(a, surahs)
    print(f"{sys.argv[1]} · engineBySurah="
          f"{ {k: v for k, v in (a.get('engineBySurah') or {}).items() if int(k) in surahs} }")
    if len(sys.argv) < 4:
        for aid in sorted(ra, key=lambda x: tuple(map(int, x.split(":")))):
            e = ra[aid]
            print(f"  {aid}\t{e.get('startMs')}\t{e.get('endMs')}\t{e.get('confBand')}\t{e.get('fileRef')}")
        return
    rb = rows(load(cl, b, sys.argv[3]), surahs)
    same = diff = 0
    for aid in sorted(set(ra) | set(rb), key=lambda x: tuple(map(int, x.split(":")))):
        x, y = ra.get(aid) or {}, rb.get(aid) or {}
        k1, k2 = (x.get("startMs"), x.get("endMs")), (y.get("startMs"), y.get("endMs"))
        if k1 == k2:
            same += 1
            continue
        diff += 1
        print(f"  ≠ {aid}\tالأول {k1}\tالثاني {k2}")
    print(f"⇒ متطابقة {same} · مختلفة {diff}")


if __name__ == "__main__":
    main()
