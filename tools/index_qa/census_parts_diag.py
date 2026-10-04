#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""تشخيصٌ قارئٌ محضٌ لاتحاد الإحصاء المتوازي حين يفشل قبل أن يكتب حكمه (fixT · 2026-10-04).

    python tools/index_qa/census_parts_diag.py <مفتاح timings-staging/...jz> <run_id>

سببُه: سجلُّ التشغيلة لا يُقرأ من خارج GitHub، و`ci_census_parts --collect` يرفع استثناءً
قبل `put_object` فلا يبقى في الدلو أثرٌ لسبب الفشل. هذه الأداة تقرأ الأجزاءَ نفسَها وتعيد
`aggregate` كما هو (‏ببصمات الأداة والنصّ المأخوذة من الأجزاء نفسِها) وتطبع الاستثناءَ
وأخطاءَ النوافذ لكلّ سورة. ⛔ لا تكتب شيئاً في الدلو، ولا تمسّ حارساً ولا عتبة.
"""
import gzip
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "ci_fleet"))

import ci_census_parts as C  # noqa: E402
import promote as P  # noqa: E402
import run as R  # noqa: E402


def main():
    key, run_id = sys.argv[1], sys.argv[2]
    cl, bucket = R.s3()
    idx, sha = R.fetch_index(key, None)
    expected = sorted(map(int, P.census_surahs(idx)))
    print(f"■ {key} ({sha[:8]}) · سورُ الإحصاء {len(expected)} · التشغيلة {run_id}")
    parts, missing = [], []
    for s in expected:
        try:
            parts.append(json.loads(cl.get_object(Bucket=bucket, Key=C.part_key(sha, run_id, s))["Body"].read()))
        except Exception as e:  # noqa: BLE001
            missing.append(f"{s}: {type(e).__name__}")
    if missing:
        print("⛔ أجزاءٌ غائبة:", "; ".join(missing))
    for p in parts:
        sm = p.get("sample") or {}
        rows = sm.get("rows") or []
        bad = [r.get("aid") for r in rows if r.get("verdict") == "تعذّر"]
        ew = sm.get("errorWindows") or {}
        if sm.get("errors") or bad or ew:
            print(f"  س{(p.get('partProvenance') or {}).get('surah')}: errors={sm.get('errors')} "
                  f"تعذّر={bad[:6]} نوافذ={json.dumps(ew, ensure_ascii=False)[:400]}")
    if missing or not parts:
        return
    pv = parts[0].get("partProvenance") or {}
    canonical = R.ASSETS / f"text_{idx['riwaya']}.jz"
    if not canonical.exists():
        canonical.parent.mkdir(parents=True, exist_ok=True)
        cl.download_file(bucket, f"quran-text/text_{idx['riwaya']}.jz", str(canonical))
    text = json.loads(gzip.decompress(canonical.read_bytes()))
    try:
        rep = C.aggregate(idx, sha, key, parts, run_id, pv.get("runSha"), text,
                          pv.get("canonicalSha256"), pv.get("toolSha256"))
    except Exception as e:  # noqa: BLE001
        print(f"⛔ aggregate: {type(e).__name__}: {e}")
        return
    print("✓ aggregate نجح · errors =", (rep.get("sample") or {}).get("errors"))


if __name__ == "__main__":
    main()
