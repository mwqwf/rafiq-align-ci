#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""أيُّ فهرسٍ **منشور** بلا شاهدِ مطالعٍ موثوقٍ على بصمته الحاليّة؟ — قارئٌ محض.

⛔ **سببُه مقيسٌ 2026-09-29:** فهرسُ `hafs/nufais` المنشور كان فيه بسملةٌ مبتلعةٌ
في 37:1 (بدء 1820م.ث)، ولم يكشفها إلا ملوحُ مرشّحٍ لاحق. وشرطُ المطالع في
`promote.py` لا يمنع إن غاب الشاهد («غيابُ الحقل لا يمنع») ⇒ فالمنشورُ قبل
هذا الشرط، أو بشاهدٍ من أداةٍ غير موثوقة، لم يُفحص مطلعُه قطّ.

يطبع لكلّ فهرسٍ في `timings/**.jz`: بصمته، وهل له شاهدُ مطالع **بالبصمة نفسها**
صادرٌ عن أداةٍ موثوقة (`promote.openers_tool_ok`)، وفواتلُه إن وُجدت. ثمّ سطراً
أخيراً `UNCOVERED=<مفاتيح بفاصلة>` يُمرَّر إلى `openers.yml` (‏`only`).

    python tools/index_qa/openers_coverage.py

⚖️ لا يكتب بايتاً ولا يحكم: الحكمُ لـ`openers.yml` ثمّ لـ`promote.py` كما هما.
"""
import gzip
import hashlib
import io
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run import s3  # noqa: E402
from promote import openers_tool_ok  # noqa: E402

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                  # noqa: BLE001
        pass


def _list(cl, bucket, prefix):
    out = []
    for pg in cl.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=prefix):
        out += [o["Key"] for o in pg.get("Contents", [])]
    return out


def main() -> int:
    cl, bucket = s3()
    pub = [k for k in _list(cl, bucket, "timings/")
           if k.endswith(".jz") and k.count("/") == 2]
    ops = [k for k in _list(cl, bucket, "state/") if k.endswith(".openers.json")]
    print(f"فهارسُ منشورة: {len(pub)} · شواهدُ مطالع في state/: {len(ops)}")

    def _get(k):
        for _ in range(3):
            try:
                return k, cl.get_object(Bucket=bucket, Key=k)["Body"].read()
            except Exception:                          # noqa: BLE001
                continue
        return k, None

    with ThreadPoolExecutor(max_workers=16) as pool:
        op_raw = dict(pool.map(_get, ops))
        pub_raw = dict(pool.map(_get, pub))

    # أحدثُ شاهدٍ موثوقٍ لكلّ بصمة — بالمقياس نفسِه الذي يحكم به الحارس.
    by_sha = {}
    for k, raw in op_raw.items():
        if raw is None:
            continue
        try:
            rep = json.loads(raw.decode("utf-8"))
        except Exception:                              # noqa: BLE001
            continue
        for r in (rep if isinstance(rep, list) else [rep]):
            if not isinstance(r, dict) or not r.get("sha256"):
                continue
            if not openers_tool_ok(r):
                continue
            t = float(r.get("ts") or r.get("at") or 0)
            cur = by_sha.get(r["sha256"])
            if cur is None or t > cur[0]:
                by_sha[r["sha256"]] = (t, k, r)

    uncovered, flagged, unread = [], [], []
    for k in sorted(pub):
        raw = pub_raw.get(k)
        if raw is None:
            unread.append(k)
            continue
        sha = hashlib.sha256(raw).hexdigest()
        hit = by_sha.get(sha)
        if not hit:
            uncovered.append(k)
            continue
        fat = hit[2].get("fatal") or []
        if fat:
            flagged.append((k, fat))

    print(f"\n✅ مغطّاةٌ بشاهدٍ موثوقٍ على بصمتها: {len(pub) - len(uncovered) - len(unread)}")
    print(f"⛔ بشاهدٍ فيه فواتل: {len(flagged)}")
    for k, fat in flagged:
        print(f"   {k}: " + " · ".join(str(f)[:110] for f in fat[:4]))
    print(f"⚠️ بلا شاهدٍ موثوقٍ على بصمتها الحاليّة: {len(uncovered)}")
    if unread:
        print(f"⚠️ تعذّرت قراءتُها (لا يُحكم عليها): {len(unread)} — {', '.join(unread)}")
    print("UNCOVERED=" + ",".join(uncovered))
    return 0


if __name__ == "__main__":
    sys.exit(main())
