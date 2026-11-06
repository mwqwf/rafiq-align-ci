#!/usr/bin/env python3
"""تنظيفُ بادئةٍ مؤقّتةٍ من الدلو — مقيَّدٌ بـ`tmp/ui_walk/` وحدها (أمان 2026-11-06).

لماذا: كانت جولةُ الواجهة ترفع APK التطبيق التصحيحيّ وسجلّاتَها إلى الدلو العامّ `rafiq-media`
فصارت قابلةً للتنزيل من r2.dev بلا مصادقة. السكربتاتُ أُصلحت (#65) وهذه الأداةُ تُزيل ما بقي.

حُرّاسُها (لا تُرخى):
- البادئةُ يجب أن تبدأ بإحدى ALLOWED_PREFIXES، بلا `..` ولا بدايةٍ بـ`/`، وليست البادئةَ الأمَّ `tmp/`.
- بلا `--yes` تكون تجربةً جافّة: جردٌ فقط.
- تطبع كلَّ مفتاحٍ تحذفه، ثمّ تُعيد الجردَ وتُفشل (rc=1) إن بقي شيء.

الاستعمالُ عبر قناة الأوامر:
  {"action":"tool","tool":"ci_fleet/r2_tmp_purge.py","args":["--prefix","tmp/ui_walk/","--yes","--reason","…"]}
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
SECURE = ROOT / "secure" / "r2_credentials.json"
ALLOWED_PREFIXES = ("tmp/ui_walk/",)


def check_prefix(prefix: str) -> str | None:
    """None إن كانت البادئةُ مسموحة، وإلا نصُّ الرفض."""
    if not prefix or not isinstance(prefix, str):
        return "⛔ بادئةٌ فارغة"
    if prefix.startswith("/") or ".." in prefix.split("/") or "\\" in prefix:
        return f"⛔ بادئةٌ مرفوضة الشكل: {prefix!r}"
    if not prefix.endswith("/"):
        return f"⛔ البادئةُ يجب أن تنتهي بـ'/' لتُحذف مجلّداً لا مفتاحاً جزئياً: {prefix!r}"
    if not any(prefix.startswith(a) for a in ALLOWED_PREFIXES):
        return f"⛔ خارجَ البادئات المسموحة {ALLOWED_PREFIXES}: {prefix!r}"
    return None


def _s3():
    import boto3  # noqa: PLC0415

    c = json.loads(SECURE.read_text(encoding="utf-8"))
    return boto3.client("s3", endpoint_url=c["endpoint"], aws_access_key_id=c["accessKeyId"],
                        aws_secret_access_key=c["secretAccessKey"], region_name="auto"), c["bucket"]


def list_keys(s3, bucket: str, prefix: str) -> list[tuple[str, int]]:
    out: list[tuple[str, int]] = []
    token = None
    while True:
        kw = {"Bucket": bucket, "Prefix": prefix, "MaxKeys": 1000}
        if token:
            kw["ContinuationToken"] = token
        r = s3.list_objects_v2(**kw)
        out.extend((o["Key"], int(o.get("Size", 0))) for o in r.get("Contents", []) or [])
        if not r.get("IsTruncated"):
            return out
        token = r.get("NextContinuationToken")


def purge(s3, bucket: str, keys: list[str]) -> int:
    n = 0
    for i in range(0, len(keys), 1000):
        chunk = keys[i:i + 1000]
        r = s3.delete_objects(Bucket=bucket, Delete={"Objects": [{"Key": k} for k in chunk], "Quiet": False})
        for d in r.get("Deleted", []) or []:
            n += 1
            print(f"🗑 {d.get('Key')}")
        for e in r.get("Errors", []) or []:
            print(f"⚠ لم يُحذف {e.get('Key')}: {e.get('Code')} {e.get('Message')}")
    return n


def main(argv=None, s3_factory=_s3) -> int:
    ap = argparse.ArgumentParser(description="تنظيف tmp/ui_walk/ من الدلو (جردٌ بلا --yes)")
    ap.add_argument("--prefix", required=True)
    ap.add_argument("--yes", action="store_true", help="احذف فعلاً (وإلا جردٌ فقط)")
    ap.add_argument("--reason", default="", help="سببٌ يُطبع في الجواب")
    a = ap.parse_args(argv)
    bad = check_prefix(a.prefix)
    if bad:
        print(bad)
        return 2
    s3, bucket = s3_factory()
    objs = list_keys(s3, bucket, a.prefix)
    total = sum(sz for _, sz in objs)
    print(f"📦 الدلو {bucket} · البادئة {a.prefix} · {len(objs)} كائناً · {total/1024/1024:.1f} م.ب")
    for k, sz in objs:
        print(f"   {sz:>12} {k}")
    if a.reason:
        print(f"📝 السبب: {a.reason}")
    if not a.yes:
        print("ℹ️ تجربةٌ جافّة — لا حذفَ بلا --yes")
        return 0
    if not objs:
        print("✅ لا شيءَ يُحذف")
        return 0
    n = purge(s3, bucket, [k for k, _ in objs])
    left = list_keys(s3, bucket, a.prefix)
    print(f"✅ حُذف {n} · باقٍ تحت البادئة: {len(left)}")
    return 0 if not left else 1


if __name__ == "__main__":
    sys.exit(main())
