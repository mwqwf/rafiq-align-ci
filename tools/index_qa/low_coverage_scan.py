#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""يمسح كلَّ فهرسٍ **منشورٍ فعلاً** بحثاً عن سورةٍ حاضرةٍ لكن ناقصة التغطية —
أخطرُ من الغائبة الكاملة: التطبيقُ يعرضها "موجودة" بينما بعضُ آياتها بلا
توقيت، وقد يختفي هذا النقصُ خلف حكم البنية الإجماليّ (نسبةُ فقدٍ على 6236
آيةً كلِّها) حين يتوسّط 113 سورةً كاملة.

    python tools/index_qa/low_coverage_scan.py [--min-ratio 0.98] [--only hafs/]

⚠️ قراءةٌ من الدلو فحسب — لا يكتب شيئاً ولا يمسّ حارساً ولا عتبة.
⛔ سورةٌ صفرُ مداخلها **لا تُحسب هنا**: تلك «غائبةٌ كليّاً» ومحلُّها فحصُ البنية
   (`run.py --struct-only`) الذي يفرّق الإسقاطَ المعلَن عن الغياب السهو. وهذا
   المسحُ لصنفٍ آخر بعينه: سورةٌ **حاضرة** (مدخلٌ واحدٌ فأكثر) لكنّ عددَ مداخلها
   دون عدد آياتها الحقيقيّ.
"""
from __future__ import annotations

import argparse
import gzip
import json
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

ROOT = HERE.parent.parent
ASSETS = ROOT / "core" / "quran" / "src" / "main" / "assets" / "quran"


def canonical_ayahs() -> dict[int, int]:
    """عددُ آيات كلّ سورةٍ حقّاً — من `index.jz` المرجعيّ لا من تخمين."""
    idx = json.loads(gzip.decompress((ASSETS / "index.jz").read_bytes()).decode("utf-8"))
    return {s["n"]: s["ayahs"] for s in idx["surahs"]}


def list_published(cl, bucket, prefix="timings/"):
    out = []
    for page in cl.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=prefix):
        for o in page.get("Contents", []):
            if o["Key"].endswith(".jz"):
                out.append(o["Key"])
    return sorted(out)


def surah_counts(entries):
    per: dict[int, int] = {}
    for e in entries:
        s = int(e["ayahId"].split(":")[0])
        per[s] = per.get(s, 0) + 1
    return per


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-ratio", type=float, default=0.98,
                    help="نسبةُ تغطيةٍ دون هذا الحدّ لسورةٍ حاضرةٍ تُعدّ ناقصة")
    ap.add_argument("--only", default=None, help="بادئةُ مفتاحٍ لتضييق المسح (مثل hafs/)")
    a = ap.parse_args()

    ayahs = canonical_ayahs()
    cl, bucket = _run.s3()
    keys = list_published(cl, bucket)
    if a.only:
        keys = [k for k in keys if a.only in k]

    checked = 0
    total_flags = 0
    for key in keys:
        try:
            idx, _sha = _run.fetch_index(key)
        except Exception as e:                          # noqa: BLE001
            print(f"⛔ {key}: تعذّرت القراءة — {e}")
            continue
        checked += 1
        per = surah_counts(idx.get("entries", []))
        dropped = set(_run.declared_drops(idx))
        flags = []
        for s, want in ayahs.items():
            have = per.get(s, 0)
            if have == 0 or s in dropped or want <= 0:
                continue
            ratio = have / want
            if ratio < a.min_ratio:
                flags.append((s, have, want, ratio))
        if flags:
            total_flags += len(flags)
            flags.sort(key=lambda x: x[3])
            print(f"⚠️ {key}: {len(flags)} سورةً حاضرةً ناقصة")
            for s, have, want, ratio in flags[:6]:
                print(f"    سورة {s}: {have}/{want} ({ratio:.0%})")

    print(f"⇒ فُحص {checked} فهرساً منشوراً · سورٌ حاضرةٌ ناقصة: {total_flags}")
    return 1 if total_flags else 0


if __name__ == "__main__":
    sys.exit(main())
