# -*- coding: utf-8 -*-
"""مقارنة الجيلين من المانيفست — الوسيط المتحرك بلا تجميل.

يقيس أثر الوصفة الجديدة على **التغطية** قارئاً قارئاً، ويحفظ قياس كل جولة
كي يُرى الاتجاه لا اللقطة. والحكم يبقى «مؤشراً» حتى تكفي العيّنة — والعدد
مطبوع مع الوسيط دائماً كي لا يُقرأ رقمٌ بلا سنده.

    python3 generation_report.py
"""
import collections
import json
import os
import sys
import time

import boto3

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
B = os.environ["R2_BUCKET"]
s3 = boto3.client("s3", endpoint_url=os.environ["R2_ENDPOINT"],
                  aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
                  aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
                  region_name="auto")


def med(v):
    v = sorted(v)
    return v[len(v) // 2] if v else None


rows = []
for r in ("qalun", "warsh", "hafs", "shuba", "douri", "sousi"):
    try:
        m = json.loads(s3.get_object(
            Bucket=B, Key="audio/{}/manifest.json".format(r))["Body"].read())
    except Exception:
        continue
    for e in m.get("reciters", []):
        if e.get("mode") != "surah":
            continue
        rows.append((r, e["id"], e.get("refineVersion", "غائب"),
                     e.get("indexCoverage"), e.get("indexEntries"),
                     e.get("medTargeted"), e.get("refinedCount")))

gen2 = [x for x in rows if x[2] not in ("unknown", "none", "غائب")]
gen1 = [x for x in rows if x[2] == "unknown"]
none_ = [x for x in rows if x[2] == "none"]

print("=== مقارنة الجيلين — {} ===".format(time.strftime("%Y-%m-%d %H:%M")))
print("الوصفة الجديدة: {} قارئاً · الجيل الأول: {} · وصفة بصقل صفر: {}".format(
    len(gen2), len(gen1), len(none_)))
c1 = [x[3] for x in gen1 if x[3] is not None]
c2 = [x[3] for x in gen2 if x[3] is not None]
if c1:
    print("  الجيل الأول  — الوسيط {:.1%} · الأدنى {:.0%} · الأعلى {:.0%} "
          "(ن={})".format(med(c1), min(c1), max(c1), len(c1)))
if c2:
    print("  الوصفة الجديدة — الوسيط {:.1%} · الأدنى {:.0%} · الأعلى {:.0%} "
          "(ن={})".format(med(c2), min(c2), max(c2), len(c2)))
if c2 and len(c2) < 5:
    print("  ⚠️ العيّنة أصغر من أن تُعمَّم — مؤشر لا إثبات.")

if gen2:
    print("\n=== قراء الوصفة الجديدة ===")
    print("| الرواية | القارئ | التغطية | مداخل | أهداف الصقل | صُقل |")
    print("|---|---|---:|---:|---:|---:|")
    for r, i, rv, cov, ent, mt, rc in sorted(gen2, key=lambda x: -(x[3] or 0)):
        print("| {} | `{}` | {} | {} | {} | {} |".format(
            r, i, "{:.1%}".format(cov) if cov is not None else "—",
            ent, mt, rc))

worst = sorted([x for x in gen1 if x[3] is not None], key=lambda x: x[3])[:8]
if worst:
    print("\n=== أحوج القراء إلى الإعادة (جيل أول، الأدنى تغطية) ===")
    for r, i, rv, cov, ent, mt, rc in worst:
        print("  {:.0%}  {}/{}  ({} مدخلة)".format(cov, r, i, ent))

hist = "/root/generation_history.jsonl"
try:
    with open(hist, "a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": int(time.time()), "gen2": len(gen2),
                            "gen1": len(gen1),
                            "medGen2": med(c2), "medGen1": med(c1)},
                           ensure_ascii=False) + chr(10))
    print("\n(القياس محفوظ في {} — الاتجاه لا اللقطة)".format(hist))
except Exception:
    pass
