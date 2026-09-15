#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""تشخيصٌ لمرّةٍ واحدة: كلُّ تقارير `state/` لمفتاحٍ بعينه، بأيّ ملفٍّ كُتبت
وماذا يحمل كلُّ تقرير (verdict/fatal/source/ts/sha256/seedSalt) — لفضّ
تناقضٍ بين حكمٍ مقروءٍ في `state/` وفحصٍ بنيويٍّ مباشر (CLAUDE.md: «حين
تتناقض أداتان، الحَكَمُ قياسٌ ثالثٌ من بياناتٍ تملكها»).

    python tools/index_qa/_debug_state_for.py <جزءٌ من المفتاح، مثل hamza.01f734d9>

قراءةٌ فحسب — لا يكتب شيئاً.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                 # noqa: BLE001
        pass

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run import s3  # noqa: E402

STATE_PREFIXES = ("qa-state/", "state/")


def main():
    if len(sys.argv) < 2:
        sys.exit("الاستعمال: _debug_state_for.py <جزءٌ من المفتاح>")
    needle = sys.argv[1]
    cl, bucket = s3()
    found = 0
    for prefix in STATE_PREFIXES:
        for page in cl.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=prefix):
            for o in page.get("Contents", []):
                key = o["Key"]
                if not key.endswith(".json"):
                    continue
                try:
                    data = json.loads(cl.get_object(Bucket=bucket, Key=key)["Body"].read())
                except Exception as ex:                  # noqa: BLE001
                    continue
                for rep in (data if isinstance(data, list) else [data]):
                    if not isinstance(rep, dict):
                        continue
                    if needle not in str(rep.get("key") or ""):
                        continue
                    found += 1
                    print(f"— {key}  (آخرُ تعديل {o['LastModified']:%Y-%m-%dT%H:%M:%SZ})")
                    print(f"    key={rep.get('key')!r}")
                    print(f"    verdict={rep.get('verdict')!r} fatal={rep.get('fatal')!r}")
                    print(f"    source={rep.get('source')!r} ts={rep.get('ts')!r}")
                    print(f"    sha256={str(rep.get('sha256'))[:16]!r} "
                          f"seedSalt={(rep.get('sample') or {}).get('seedSalt')!r}")
    print(f"⇒ {found} تقريراً وُجد فيه المفتاحُ يحوي {needle!r}")


if __name__ == "__main__":
    main()
