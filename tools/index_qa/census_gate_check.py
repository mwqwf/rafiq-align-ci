#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""يحكم حارسَ الإحصاء الشامل في `promote.census_gate` على مرشّحٍ في المسرح **قراءةً محضة**،
ويطبع عدَّ الأصناف (جسيم · غير حاسم · تعذّر) — fixS1 · 2026-10-03.

    python tools/index_qa/census_gate_check.py timings-staging/qalun/kshidan_qalun.4ac42a49.jz [...]

⭐ سببُه: حكمُ ملفّ الإحصاء قد يقول «حدّي (الحدّ الأعلى 8.8%)» بمجال ثقةٍ لا يستعمله
الحارس (‏الإحصاءُ مجتمعٌ كامل لا عيّنة)، فلا يُعرف من الحكم وحده أيمرّ المرشّح أم يُردّ.
⚖️ لا يكتب بايتاً، ولا يغيّر حارساً: يستدعي `census_gate` نفسَه كما تستدعيه الترقية.
"""
from __future__ import annotations
import gzip
import hashlib
import json
import sys
from pathlib import Path
for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass
sys.path.insert(0, str(Path(__file__).resolve().parent))
import promote as P  # noqa: E402


def main() -> int:
    cl, bucket = P.s3()
    for src in sys.argv[1:]:
        body = cl.get_object(Bucket=bucket, Key=src)["Body"].read()
        sha = hashlib.sha256(body).hexdigest()
        idx = json.loads(gzip.decompress(body))
        why = P.census_gate(cl, bucket, src, sha, idx)
        counts = {}
        try:
            rep = json.loads(cl.get_object(Bucket=bucket, Key=P.CENSUS_PREFIX + src.replace("/", "_") + ".json")["Body"].read())
            for r in (rep.get("sample") or {}).get("rows") or []:
                k = r.get("kind") or r.get("verdict")
                counts[k] = counts.get(k, 0) + 1
            sev = [r.get("aid") for r in (rep.get("sample") or {}).get("rows") or [] if r.get("kind") == "جسيم"]
        except Exception as ex:                        # noqa: BLE001
            sev = []; counts = {"⛔": str(ex)[:80]}
        print(f"■ {src} ({sha[:8]}) · {counts} · جسيم: {sev[:20]}")
        print(f"   ⇒ حارسُ الإحصاء: {'✅ يمرّ' if why is None else '⛔ ' + why}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
