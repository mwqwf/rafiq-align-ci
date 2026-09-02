#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""لقطةٌ مرحلية لقارئٍ لم يكتمل — تحفظ العمل إن ماتت المهمة أو زال الخادم.

    python tools/cloud/partial_snapshot.py --reciter deban_douri --riwaya douri
    python tools/cloud/partial_snapshot.py --reciter X --riwaya Y --every 20 --loop

⛔ **السبب مقيسٌ بثمنه**: ليلة 2026-09-02 عُلّق أسطول Hetzner فجأةً (حساب
محجوب)، فنجا **14 فهرساً مرفوعاً** بلا خدش وضاع **خمسة قرّاء غير مكتملين**
أحدهم عند **95/114** — لا لعيبٍ فيه بل لأن **الاكتمال شرط الرفع**. الحقيقة
نجت لأنها على الدلو، والعمل ضاع لأنه على الخادم.

⇒ فاللقطة المرحلية ترفع ما أُنجز إلى `timings-staging/` كل عشرين سورة:
**مفتاحٌ يحمل بصمته** (`<id>.partial.<sha8>.jz`) فلا تُخلط نسختان، وميتاداتا
`partial=true` وعدد السور، **ولا تمسّ المانيفست بحال** — فالمانيفست عقدٌ مع
التطبيق ولا يُذكر فيه ناقص.

⚠️ وليست بديلاً عن الفهرس الكامل: لا تُرقّى ولا تُدقَّق ولا تُحسب في العدّ.
هي **تأمينٌ على العمل** لا مخرَجٌ للإنتاج.
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tools", "alignment"))
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

WORK = os.environ.get("ALIGN_WORK", os.path.join(ROOT, "tools", "alignment", "work"))
PREFIX = os.environ.get("STAGING_PREFIX", "timings-staging")
SECURE = os.path.join(ROOT, "secure", "r2_credentials.json")


def build(reciter, riwaya, counting="KUFI"):
    """يبني فهرساً من السور المنجزة وحدها. يرجع (ti, عدد السور)."""
    from validate import make_timing_index  # noqa: PLC0415
    d = os.path.join(WORK, f"batch_{reciter}")
    per = {}
    for f in sorted(glob.glob(os.path.join(d, "s*.json"))):
        try:
            per[int(os.path.basename(f)[1:4])] = json.load(open(f, encoding="utf-8"))
        except Exception:
            continue
    if not per:
        return None, 0
    rels = sorted(v["vadRel"] for v in per.values() if v.get("vadRel") is not None)
    med = rels[len(rels) // 2] if rels else None
    ti = make_timing_index(riwaya, reciter, "SURAH_FILES", counting, per, vad_rel=med)
    return ti, len(per)


def upload(ti, n, reciter, riwaya):
    import gzip  # noqa: PLC0415
    import io  # noqa: PLC0415

    import boto3  # noqa: PLC0415
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb", mtime=0) as g:
        g.write(json.dumps(ti, ensure_ascii=False).encode("utf-8"))
    body = buf.getvalue()
    sha = hashlib.sha256(body).hexdigest()
    key = f"{PREFIX}/{riwaya}/{reciter}.partial.{sha[:8]}.jz"
    c = json.load(open(SECURE, encoding="utf-8"))
    s3 = boto3.client("s3", endpoint_url=c["endpoint"],
                      aws_access_key_id=c["accessKeyId"],
                      aws_secret_access_key=c["secretAccessKey"], region_name="auto")
    s3.put_object(Bucket=c["bucket"], Key=key, Body=body,
                  ContentType="application/gzip",
                  Metadata={"partial": "true", "surahs": str(n),
                            "entries": str(len(ti["entries"])),
                            "ts": str(int(time.time()))})
    return key, sha, len(body)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reciter", required=True)
    ap.add_argument("--riwaya", required=True)
    ap.add_argument("--counting", default="KUFI")
    ap.add_argument("--every", type=int, default=20, help="لقطة كل كذا سورة جديدة")
    ap.add_argument("--loop", action="store_true", help="يراقب حتى الاكتمال")
    ap.add_argument("--interval", type=int, default=120)
    a = ap.parse_args()
    last = 0
    while True:
        ti, n = build(a.reciter, a.riwaya, a.counting)
        if n >= 114:
            print(f"  ✅ {a.reciter} اكتمل ({n}) — لا لقطة، المسار الكامل يتولاه", flush=True)
            return 0
        if ti and n - last >= a.every:
            try:
                key, sha, size = upload(ti, n, a.reciter, a.riwaya)
                last = n
                print(f"  📸 {a.reciter} {n}/114 · {len(ti['entries'])} مدخلاً · "
                      f"{size//1024}ك.ب · {key}", flush=True)
            except Exception as ex:  # اللقطة تُخفق ولا تُسقط الفهرسة
                print(f"  ⚠️ تعذّرت اللقطة ({ex}) — الفهرسة تمضي", flush=True)
        if not a.loop:
            return 0
        time.sleep(a.interval)


if __name__ == "__main__":
    sys.exit(main())
