#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""مُطالبة موزَّعة على R2: من سبق مَلَك القارئ. رمز 0 = مَلَكتَه، 1 = لغيرك.

    python tools/cloud/claim.py --take a_turki --owner 47.206   # مطالبة
    python tools/cloud/claim.py --release a_turki               # عند الرفع أو الرفض

⚠️ لماذا لزمت: حصرُ كل خادم بشريحته منع تكرار `akri_qalun` (عُمل ثلاث مرات
وأهدر ساعات)، **لكنه يعطّل الخادم إذا نفدت شريحته** ولو كان في شرائح غيره
عشرات الأحرار — وقع فعلاً على 47.206 (حمل 2.1 وشريحته خالية). والجمع بين
منع التكرار ومنع التعطّل يحتاج مُطالبةً يراها الخمسة، ولا نظام ملفات بينهم:
فالدلو هو المكان الوحيد المشترك.

⛔ والذرّية شرطٌ لا تحسين: `head` ثم `put` سباقٌ يملكه اثنان معاً. فالكتابة
بـ`If-None-Match: *` — يرفضها الخادم إن وُجد المفتاح، فيَملك واحدٌ حتماً.

⚠️ وانتهاء الصلاحية ليس زينة: خادمٌ يموت وهو مالك يحجز القارئ للأبد. فمطالبةٌ
أقدم من TTL تُعدّ متروكة وتُنتزع — والقيمة الافتراضية ست ساعات، أطول من أطول
فهرسة قِستها (~2.5 ساعة) بهامشٍ واسع.
"""
import argparse
import json
import os
import pathlib
import sys
import time

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

ROOT = pathlib.Path(__file__).resolve().parents[2]
SECURE = ROOT / "secure" / "r2_credentials.json"
TTL_S = int(os.environ.get("CLAIM_TTL_S", str(6 * 3600)))
PREFIX = "claims/"


def _s3():
    import boto3  # noqa: PLC0415
    c = json.loads(SECURE.read_text(encoding="utf-8"))
    return boto3.client("s3", endpoint_url=c["endpoint"],
                        aws_access_key_id=c["accessKeyId"],
                        aws_secret_access_key=c["secretAccessKey"],
                        region_name="auto"), c["bucket"]


def take(rid, owner):
    s3, bucket = _s3()
    key = f"{PREFIX}{rid}"
    body = json.dumps({"owner": owner, "ts": int(time.time())}).encode()
    try:
        s3.put_object(Bucket=bucket, Key=key, Body=body,
                      ContentType="application/json", IfNoneMatch="*")
        print(f"  ✅ {rid} مملوك لـ{owner}")
        return 0
    except Exception:
        pass
    # موجودة: أمتروكة هي؟
    try:
        cur = json.loads(s3.get_object(Bucket=bucket, Key=key)["Body"].read())
        age = int(time.time()) - int(cur.get("ts", 0))
        if cur.get("owner") == owner:
            print(f"  ✅ {rid} مملوك لك أصلاً")
            return 0
        if age > TTL_S:
            s3.put_object(Bucket=bucket, Key=key, Body=body, ContentType="application/json")
            print(f"  ♻️ {rid} انتُزع من {cur.get('owner')} (متروك منذ {age//60}د)")
            return 0
        print(f"  ⛔ {rid} مملوك لـ{cur.get('owner')} منذ {age//60}د")
        return 1
    except Exception as ex:
        print(f"  ⛔ تعذّر فحص مطالبة {rid} ({ex}) — لا تُؤخذ")
        return 1


def release(rid):
    s3, bucket = _s3()
    try:
        s3.delete_object(Bucket=bucket, Key=f"{PREFIX}{rid}")
        print(f"  🔓 {rid} أُطلق")
    except Exception as ex:
        print(f"  ⚠️ تعذّر إطلاق {rid} ({ex})")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--take")
    ap.add_argument("--release")
    ap.add_argument("--owner", default=os.environ.get("CLAIM_OWNER", "unknown"))
    a = ap.parse_args()
    if a.take:
        return take(a.take, a.owner)
    if a.release:
        return release(a.release)
    ap.error("‏--take أو --release")


if __name__ == "__main__":
    sys.exit(main())
