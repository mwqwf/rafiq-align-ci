#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""إعادةُ عدٍّ قارئةٍ محضة لإحصاءٍ متوازٍ محفوظ (state-census-parts/<sha>/<run>/NNN.json) — لا تكتب شيئاً ولا تمسّ حارساً.

    python tools/index_qa/census_parts_recount.py <timings-staging/..jz> <sha256 كامل> <run_id> <run_sha>

الغاية: مقارنة عدّ «العطب الجسيم» في المسار المتوازي (parallel_surahs) بالمسار المتسلسل على المفتاح نفسه
قبل اعتماد التوازي (أمر المالك 2026-11-25: إن اختلف العدّ تُرك التوازي). يُعاد بناءُ الاتحاد بالدالّة نفسها
`ci_census_parts.aggregate` (بكلّ تحقّقاتها) ويُطبع سطرُ العدّ بصيغة الإحصاء المتسلسل حرفاً.
"""
from __future__ import annotations
import gzip, hashlib, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ci_census_parts as C  # noqa: E402
import promote as P  # noqa: E402
import run as R  # noqa: E402


def severe_line(rep: dict) -> str:
    hit, n, ci = rep['sample']['severe']
    if not n:
        return '📐 العطب الجسيم (إسقاط كلمة): —'
    c = f" · مجال 95% عنقودي: {ci[1]:.1%} – {ci[2]:.1%}" if ci else ''
    return f"📐 العطب الجسيم (إسقاط كلمة): {hit}/{n} = {hit/n:.1%}{c}"


def main(argv):
    if len(argv) != 4:
        raise SystemExit(__doc__)
    key, sha, run_id, run_sha = argv
    cl, bucket = R.s3()
    idx, got = R.fetch_index(key, sha)
    expected = sorted(map(int, P.census_surahs(idx)))
    parts = [json.loads(cl.get_object(Bucket=bucket, Key=C.part_key(got, run_id, s))['Body'].read())
             for s in expected]
    canon = cl.get_object(Bucket=bucket, Key=f"quran-text/text_{idx['riwaya']}.jz")['Body'].read()
    text = json.loads(gzip.decompress(canon))
    tool_sha = parts[0]['partProvenance']['toolSha256']
    rep = C.aggregate(idx, got, key, parts, run_id, run_sha, text, C.digest(canon), tool_sha)
    print(f"key {key} · run {run_id} · parts {len(parts)} · population {rep['census']['population']}")
    print(severe_line(rep))
    print(f"⇒ الحكم: {rep['verdict'][:200]}")


if __name__ == '__main__':
    main(sys.argv[1:])
