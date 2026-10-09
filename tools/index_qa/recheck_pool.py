#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""قراءةٌ محضة: أحكامُ الصوت المحمولة على بصمةٍ بعينها (الملح · المحرّك · العيّنة · fatal) — pR 2026-10-09.

    python tools/index_qa/recheck_pool.py <بصمة8> [<بصمة8> ...]
"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import promote as P  # noqa: E402

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass


def main():
    want = sys.argv[1:]
    cl, bucket = P.s3()
    ev = list(P.reports()) + P.bucket_reports(cl, bucket)
    print(f"أحكامٌ: {len(ev)} · تعذّرت: {P.READ_FAILED}")
    for w in want:
        reps = [(n, r) for n, r in ev if str(r.get("sha256", "")).startswith(w)]
        print(f"\n## {w}: {len(reps)} حكماً")
        for n, r in sorted(reps, key=lambda x: str((x[1].get("sample") or {}).get("seedSalt"))):
            sp = r.get("sample") or {}
            print(json.dumps({"name": str(n)[:60], "key": r.get("key"), "salt": sp.get("seedSalt"),
                              "seed": sp.get("seed"), "engine": r.get("engine"), "source": P.source_of(r),
                              "verdict": r.get("verdict"), "severe": sp.get("severe"),
                              "fatal": r.get("fatal"), "ts": r.get("ts")}, ensure_ascii=False)[:900])
        pz = P.pooled_samples([r for _n, r in reps if (r.get("sample") or {}).get("severe")])
        print("pooled_samples =>", json.dumps(pz, ensure_ascii=False)[:500] if pz else None)


if __name__ == "__main__":
    main()
