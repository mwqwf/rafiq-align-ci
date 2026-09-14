#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""يمسح كلَّ فهرسٍ **منشورٍ فعلاً** بحثاً عن بصمتَي صوتٍ متطابقتَين لسورتين
مختلفتَين في الفهرس نفسه — أي أنّ ملفَّ صوتٍ واحداً صار يُخدَم موضعَ سورتين،
فقارئٌ يسمع سورةً بصوت غيرها.

    python tools/index_qa/dup_sha_sweep.py [--only hafs/]

⛔⛔ **هذا الصنفُ من العطب بعينه ما يمنعه البندُ الأوّل في CLAUDE.md** («لا
تحريفَ للقرآن بأيّ وجه») — فأيُّ سطرٍ يطبعه هذا المسحُ يستحقّ توقّفاً فوريّاً
لا تأجيلاً: يُجمَّد المفتاحُ (`promote.py --freeze`) ويُصلَح المصدرُ قبل أيّ
عملٍ آخر.

⭐ والحارسُ نفسُه مبنيٌّ أصلاً في `run.py --struct-only` (فحصٌ فاتٌ عند كلّ
ترقية) — وهذا المسحُ **يُعيد الفحصَ نفسَه على كلّ المنشور فعلاً**، لا على
مرشَّحٍ جديدٍ وحده، كطبقةِ دفاعٍ دوريّةٍ لا تنتظر أن يُعاد فحصُ قارئٍ بعد نشره.
ولذا يستعمل استثناء «الإسقاط المعلَن» **نفسَه حرفاً** (`run.declared_drops`)
لا نسخةً موازيةً قد تنحرف عنه.

⚠️ قراءةٌ من الدلو فحسب — لا يكتب شيئاً ولا يجمّد ولا يمسّ حارساً أو عتبة؛
التجميدُ والإصلاحُ فعلُ من يقرأ الجوابَ لا هذا المسح.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                 # noqa: BLE001
        pass

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run as _run                                                   # noqa: E402


def list_published(cl, bucket, prefix="timings/"):
    out = []
    for page in cl.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=prefix):
        for o in page.get("Contents", []):
            if o["Key"].endswith(".jz"):
                out.append(o["Key"])
    return sorted(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default=None, help="بادئةُ مفتاحٍ لتضييق المسح (مثل hafs/)")
    a = ap.parse_args()

    cl, bucket = _run.s3()
    keys = list_published(cl, bucket)
    if a.only:
        keys = [k for k in keys if a.only in k]

    checked = 0
    hits = 0
    for key in keys:
        try:
            idx, _sha = _run.fetch_index(key)
        except Exception as e:                          # noqa: BLE001
            print(f"⛔ {key}: تعذّرت القراءة — {e}")
            continue
        checked += 1
        sha = idx.get("audioSha256") or []
        served = {int(e["ayahId"].split(":")[0]) for e in idx.get("entries", [])}
        exempt = {s for s in _run.declared_drops(idx) if s not in served}
        live = [(i + 1, x) for i, x in enumerate(sha) if (i + 1) not in exempt and x]
        seen: dict[str, list[int]] = {}
        for surah, digest in live:
            seen.setdefault(digest, []).append(surah)
        dups = {d: ss for d, ss in seen.items() if len(ss) > 1}
        if dups:
            hits += 1
            print(f"🔴 {key}: بصمةٌ واحدةٌ لعدّة سور — تحريفٌ سمعيّ محتمل")
            for digest, surahs in dups.items():
                print(f"    {digest[:16]}…  ⇐  سور {sorted(surahs)}")

    print(f"⇒ فُحص {checked} فهرساً منشوراً · فهارسُ فيها بصمةٌ مكرّرة: {hits}")
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
