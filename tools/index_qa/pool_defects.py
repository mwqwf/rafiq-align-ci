#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""قائمةُ الآيات المعيبة كاملةً من أملاح مرشّحٍ — قارئٌ محض (pW · 2026-10-12).

    pool_defects.py timings-staging/<riw>/<id>.<sha8>.jz [بادئة اسم الملح، اختياري]

يطبع لكلّ آيةٍ حكمُها EARLY_START/LATE_START/WRONG_AYAH في أيّ ملحٍ: الملحُ والحكمُ والانحراف إن وُجد،
ثمّ ملخّصاً بالسور وعدد الأملاح التي تكرّر فيها العطب. لا يكتب ولا يمسّ حارساً.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import promote as P  # noqa: E402

BAD = ("EARLY_START", "LATE_START", "WRONG_AYAH")


def main() -> int:
    cl, bucket = P.s3()
    key = sys.argv[1]
    want = sys.argv[2] if len(sys.argv) > 2 else ""
    pre = "state/" + key.replace("/", "_") + ".audio-"
    seen = {}
    for page in cl.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=pre):
        for o in page.get("Contents") or []:
            name = o["Key"][len(pre):]
            if want and not name.startswith(want):
                continue
            r = json.loads(cl.get_object(Bucket=bucket, Key=o["Key"])["Body"].read())
            for row in ((r.get("sample") or {}).get("rows") or []):
                if row.get("verdict") in BAD:
                    aid = str(row.get("aid"))
                    seen.setdefault(aid, []).append(name)
                    extra = {k: v for k, v in row.items() if k not in ("aid", "verdict", "text", "heard")}
                    print(f"{aid}\t{row.get('verdict')}\t{name}\t{json.dumps(extra, ensure_ascii=False)[:200]}")
    bys = {}
    for aid, salts in seen.items():
        bys.setdefault(int(aid.split(":")[0]), []).append((int(aid.split(":")[1]), len(salts)))
    print("== ملخّص: سورة: آية×عدد الأملاح")
    for s in sorted(bys, key=lambda s: -sum(n for _, n in bys[s])):
        print(f"س{s}: " + " ".join(f"{a}×{n}" for a, n in sorted(bys[s])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
