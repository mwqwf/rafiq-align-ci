#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""قراءةٌ محضةٌ: صفوفُ تقرير الإحصاء التي خلا فيها تفريغُ نافذةٍ (fwd أو dec أو long)، مع بدء الآية وانتهائها من المرشّح.

    python tools/index_qa/census_empty_rows.py <مفتاح timings-staging/...jz>

سببُه: التقريرُ يحفظ عدَّ «نوافذ تعذّر تفريغها» بلا تسميتها، وجوابُ dump_state يُقصّ عند 200000 حرف.
لا يكتب شيئاً في الدلو ولا يمسّ حارساً.
"""
import gzip, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import promote as P  # noqa: E402
import run as R  # noqa: E402


def main():
    key = sys.argv[1]
    cl, bucket = R.s3()
    rep = json.loads(cl.get_object(Bucket=bucket, Key=P.CENSUS_PREFIX + key.replace("/", "_") + ".json")["Body"].read())
    idx = json.loads(gzip.decompress(cl.get_object(Bucket=bucket, Key=key)["Body"].read()))
    ent = {e["ayahId"]: e for e in idx["entries"]}
    rows = (rep.get("sample") or {}).get("rows") or []
    print(f"صفوف {len(rows)} · errors={(rep.get('sample') or {}).get('errors')}")
    for r in rows:
        h = r.get("heard") or {}
        empt = [k for k in ("fwd", "dec", "long") if not (h.get(k) or "").strip()]
        e = ent.get(r.get("aid")) or {}
        if empt:
            print(r.get("aid"), "فارغ:", empt, "start", e.get("startMs"), "end", e.get("endMs"),
                  "verdict", r.get("verdict"), "why", (r.get("why") or "")[:60], "fileRef", e.get("fileRef"))
    print("sha", idx.get("audioSha256") if not isinstance(idx.get("audioSha256"), list) else "list")


if __name__ == "__main__":
    main()
