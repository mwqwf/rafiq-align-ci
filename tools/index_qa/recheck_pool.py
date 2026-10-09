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


def guards(src):
    """حرّاسُ المصدر المرشَّح بعد الحكم، كما في main (عرضاً): الإحصاء · السماع · البنية · الهويّة · البتر."""
    import gzip
    cl, bucket = P.s3()
    sha, size, body = P.object_sha(cl, bucket, src)
    idx = json.loads(gzip.decompress(body).decode("utf-8"))
    published = "timings/%s/%s.jz" % (idx.get("riwaya"), idx.get("reciterId"))
    out = {"src": src, "sha": sha[:12], "entries": len(idx.get("entries", []))}
    out["census_gate"] = P.census_gate(cl, bucket, src, sha, idx)
    out["heard_gate"] = P.heard_gate_check(cl, bucket, src, sha, idx, published)
    try:
        out["index_gate"] = P.index_gate(idx)
        out["catalog_gate"] = P.catalog_gate(idx, P.catalog(cl, bucket))
    except SystemExit as ex:
        out["catalog_exit"] = str(ex)
    petag = cl.head_object(Bucket=bucket, Key=published).get("ETag")
    cut, st = P.truncation(cl, bucket, idx.get("riwaya"), idx.get("reciterId"), None)
    out["truncation"] = {"state": st, "cut": [r.get("surah") for r in cut]}
    print(json.dumps(out, ensure_ascii=False))


def main():
    if sys.argv[1:2] == ["--guards"]:
        for k in sys.argv[2:]:
            guards(k)
        return
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
