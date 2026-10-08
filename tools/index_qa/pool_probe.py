#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""مسبارُ التجميع (‏fixW · 2026-10-08): ما حكمُ `promote.pooled_samples` على أملاح مرشّحٍ قبل الترقية؟

    pool_probe.py timings-staging/<riw>/<id>.<sha8>.jz [...]

⚖️ قارئٌ محض: يقرأ `state/<المفتاح مسطّحاً>.audio-*.json` من الدلو ويستدعي دالّةَ الترقية نفسَها
(‏لا نسخةً منها)، ويطبع لكلّ ملحٍ حكمَه وعطبَه، ثمّ المجمَّعَ وحدَّه الأعلى والرافضين والتناثر.
لا يكتب بايتاً ولا يمسّ حارساً ولا عتبة. سببُه: العرضُ التجريبيّ لـpromote يقف عند حارس التجميد
فلا يُظهر حكمَ التجميع لمرشّحٍ حدّيّ أُضيفت له أملاحٌ أخرى.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import promote as P  # noqa: E402


def main() -> int:
    cl, bucket = P.s3()
    for key in sys.argv[1:]:
        pre = "state/" + key.replace("/", "_") + ".audio-"
        reps = []
        for page in cl.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=pre):
            for o in page.get("Contents") or []:
                r = json.loads(cl.get_object(Bucket=bucket, Key=o["Key"])["Body"].read())
                reps.append(r)
                sv = (r.get("sample") or {}).get("severe")
                print(f"  {o['Key'][len(pre):]:<22} {str(r.get('verdict'))[:48]:<48} severe={sv[:2] if isinstance(sv, list) else sv} sha={str(r.get('sha256'))[:8]}")
        pooled = P.pooled_samples(reps)
        if pooled is None:
            print(f"■ {key}: لا تجميع (رافضان · محرّكان · عيّنةٌ دون الحدّ · أو تكتّلٌ يمنعه)")
        else:
            v = "مقبول" if pooled["hi"] < P.SEVERE_CEILING else "غير مقبول"
            print(f"■ {key}: مجمَّع {pooled['rate']:.2%} · الحدّ الأعلى {pooled['hi']:.2%} ⇒ {v} · "
                  f"بذور {pooled['seeds']} · القاعدة {pooled['rule']} · رافضون {pooled.get('dissent')} · تناثر {pooled.get('scatter')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
