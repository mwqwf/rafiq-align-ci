#!/usr/bin/env python3
"""اعتماد مشتق محدد بالحراس القائمين، وإعادة التجميد حتى عند فشل الاعتماد.

لا تجاوز ولا استثناء عتبة. المعاينة تزيل التجميد من الذاكرة فقط، بلا كتابة؛
ولا يرفع التجميد الحقيقي إلا بعد قبول كل حراس promote.py على البصمة المحددة.
"""
import argparse
import contextlib
import gzip
import io
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import promote as p


def invoke(key, yes=False):
    argv = sys.argv
    try:
        sys.argv = ["promote.py", "--only", key] + (["--yes"] if yes else [])
        p.main()
    finally:
        sys.argv = argv


def adopt(key, sha, parent_sha, reason):
    if not all(re.fullmatch(r"[0-9a-f]{64}", h) for h in (sha, parent_sha)):
        raise ValueError("يلزم كامل بصمتي المشتق والأصل")
    if not reason.strip():
        raise ValueError("يلزم سبب اعتماد مكتوب")
    if not re.fullmatch(r"timings-staging/[a-z_]+/[a-z0-9_]+\.[0-9a-f]{8}\.jz", key):
        raise ValueError("يلزم مفتاح مشتق مرحلي صريح")
    cl, bucket = p.s3()
    actual, _, body = p.object_sha(cl, bucket, key)
    if actual != sha:
        raise ValueError("بصمة المسرح لا تطابق المطلوب")
    idx = json.loads(gzip.decompress(body))
    target = f"timings/{idx['riwaya']}/{idx['reciterId']}.jz"
    tx = idx.get("transform") or {}
    if (tx.get("fromKey"), tx.get("fromSha256")) != (target, parent_sha):
        raise ValueError("سلسلة نسب المشتق لا تطابق الأصل المطلوب")
    old_sha, _, old_body = p.object_sha(cl, bucket, target)
    if old_sha != parent_sha:
        raise ValueError("تغير المنشور منذ بناء المشتق؛ لا رفع تجميد")
    old_ids = {e["ayahId"] for e in json.loads(gzip.decompress(old_body))["entries"]}
    if not old_ids <= {e["ayahId"] for e in idx["entries"]}:
        raise ValueError("المشتق يفقد مداخل منشورة؛ لا اعتماد")
    frozen, _, _ = p.load_frozen(cl, bucket)
    if frozen.get(target) != parent_sha:
        raise ValueError("يلزم أصل مجمد على كامل بصمته المطلوبة")

    # جميع الأحكام في نطاق اسم المصدر، لا اختيار الأحكام المقبولة وحدها.
    # هذه هي تسمية ci_run/openers_scan الرسمية؛ الحراس يطابقون كامل SHA.
    saved_prefixes, saved_reports = p.STATE_PREFIXES, p.REPORTS_CACHE
    saved_load = p.load_frozen
    try:
        flat = key.replace("/", "_")
        p.STATE_PREFIXES = tuple(prefix + flat for prefix in saved_prefixes)
        p.REPORTS_CACHE = p.bucket_reports(cl, bucket)
        for report_key, report in p.REPORTS_CACHE:
            if report.get("sha256") == sha and (report.get("sample") or {}).get("errors"):
                raise ValueError("شاهد بنوافذ تعذرت؛ لا رفع تجميد قبل إعادة الفحص: " + report_key)
        def preview_frozen(client, bucket_name):
            keys, text, etag = saved_load(client, bucket_name)
            return {k: v for k, v in keys.items() if k != target}, text, etag
        p.load_frozen = preview_frozen
        preview = io.StringIO()
        try:
            with contextlib.redirect_stdout(preview):
                invoke(key)
        finally:
            p.load_frozen = saved_load
        print(preview.getvalue(), end="")
        if f"✅ جاهز: {key} → {target}" not in preview.getvalue():
            raise ValueError("ردت الحراس المعاينة؛ بقي تجميد الأصل دون كتابة")
        # إعادة قراءة الأصل بعد المعاينة، قبل أي تعديل للتجميد.
        if p.object_sha(cl, bucket, target)[0] != parent_sha:
            raise ValueError("تغير الأصل أثناء المعاينة؛ لا رفع تجميد")
        try:
            p.unfreeze(target, reason)
            invoke(key, yes=True)
        finally:
            current = p.object_sha(cl, bucket, target)[0]
            keys, _, _ = saved_load(cl, bucket)
            if keys.get(target) != current:
                p.freeze(cl, bucket, target, current, "إعادة تجميد بعد محاولة اعتماد · " + reason)
                print(f"🧊 أعيد تجميد {target} على بصمته الفعلية {current}")
        current, _, _ = p.object_sha(cl, bucket, target)
        manifest = json.loads(cl.get_object(Bucket=bucket, Key="timings/manifest.json")["Body"].read())
        rows = [r for r in manifest["indexes"]
                if (r.get("riwaya"), r.get("reciterId")) == (idx["riwaya"], idx["reciterId"])]
        keys, _, _ = saved_load(cl, bucket)
        if current != sha or keys.get(target) != sha or len(rows) != 1 or rows[0].get("sha256") != sha:
            raise ValueError("لم تتطابق بصمة المنشور والبيان والتجميد؛ لا إعلان نجاح")
        print(json.dumps({"productionKey": target, "sha256": sha,
                          "entries": len(idx["entries"]), "manifestVerified": True,
                          "frozenVerified": True}, ensure_ascii=False))
    finally:
        p.load_frozen = saved_load
        p.STATE_PREFIXES, p.REPORTS_CACHE = saved_prefixes, saved_reports


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--key", required=True)
    ap.add_argument("--sha", required=True)
    ap.add_argument("--parent-sha", required=True)
    ap.add_argument("--reason", required=True)
    a = ap.parse_args()
    adopt(a.key, a.sha, a.parent_sha, a.reason)


if __name__ == "__main__":
    main()
