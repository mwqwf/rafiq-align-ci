# -*- coding: utf-8 -*-
"""يختم مدخلات المانيفست القائمة بتغطية الفهرس — بقراءة الفهارس وحدها.

لا يلمس الصوت ولا يعيد حساب بصمة: الفهارس كيلوبايتات والصوت جيغابايتات،
فالختم الرجعي يكلّف ثوانيَ لا ساعة. واصفٌ لا مانع — لا يُسقط مدخلاً بحال.
"""
import gzip, json, os, sys, time
import boto3
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
B = os.environ["R2_BUCKET"]
s3 = boto3.client("s3", endpoint_url=os.environ["R2_ENDPOINT"],
                  aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
                  aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
                  region_name="auto")


def guard(key):
    if "_quarantine" in key:
        sys.exit(f"⛔ كتابة ممنوعة تحت مسار محجور: {key}")
    return key


idx_cache = {}
for page in s3.get_paginator("list_objects_v2").paginate(Bucket=B, Prefix="timings/"):
    for o in page.get("Contents", []):
        if o["Key"].endswith(".jz"):
            d = json.loads(gzip.decompress(
                s3.get_object(Bucket=B, Key=o["Key"])["Body"].read()))
            idx_cache[(d["riwaya"], d["reciterId"])] = d

for riwaya in ("qalun", "warsh", "hafs", "shuba", "douri", "sousi"):
    mkey = f"audio/{riwaya}/manifest.json"
    try:
        cur = json.loads(s3.get_object(Bucket=B, Key=mkey)["Body"].read())
    except Exception:
        continue
    changed = 0
    for e in cur.get("reciters", []):
        d = idx_cache.get((riwaya, e["id"]))
        if not d:
            continue
        n = len(d.get("entries") or [])
        cov = round(n / (d.get("ayahCount") or 6236), 3)
        sur = len({x["ayahId"].split(":")[0] for x in (d.get("entries") or [])})
        # جيل المحرّك — والغياب "unknown" لا "none": الأول فهرسٌ سابق للحقل،
        # والثاني وصفةٌ جديدة جرت بلا صقل. وخلطهما ادّعاءُ قياسٍ لم يقع.
        rv = d.get("refineVersion", "unknown")
        rc, mt = d.get("refinedCount"), d.get("medTargeted")
        ev = d.get("engineVersion")
        # ⚠️ شرط التخطي يجب أن يشمل **كل** حقل يكتبه هذا السكربت، وإلا
        # تخطّى مدخلاً ناقصَ حقلٍ جديد لأن القديمة مطابقة — وقع فعلاً:
        # clipsBlockedReason لم يُختم على 39 مدخلاً لهذا السبب.
        same = ((e.get("indexEntries"), e.get("indexCoverage"),
                 e.get("indexSurahs"), e.get("refineVersion"))
                == (n, cov, sur, rv)
                and (e.get("mode") != "surah"
                     or "clipsBlockedReason" in e))
        if same:
            continue
        e["indexEntries"], e["indexCoverage"], e["indexSurahs"] = n, cov, sur
        e["refineVersion"], e["refinedCount"] = rv, rc
        e["medTargeted"], e["engineVersion"] = mt, ev
        # ⛔ ختمٌ رجعي لسبب المنع: المدخلات المنشورة قبل سنّ الحقل كانت تُبقي
        # المستهلك يستنتج السبب — وهو ما رفضه rafiq-packages بحق. والسبب
        # يُشتقّ من بيانات المانيفست نفسها بلا قراءة صوت: ما كان في
        # durationMismatchAtSource فالملف معطوب، وما سواه فمخالفة بصمة
        # (والسورة كاملةً تُشغَّل سليمة فيه).
        dur_bad = {x["surah"] for x in (e.get("durationMismatchAtSource") or [])}
        reason = {}
        for sn in (e.get("clipsBlockedBySurah") or []):
            reason[str(sn)] = ("DURATION_MISMATCH" if sn in dur_bad
                               else "SHA_MISMATCH")
        for sn in dur_bad:
            reason[str(sn)] = "DURATION_MISMATCH"
        if e.get("mode") == "surah":
            e["clipsBlockedReason"] = reason
        changed += 1
        print(f"  {riwaya}/{e['id']}: {n}/6236 ({cov:.0%}) · سور {sur}/114"
              f" · صقل {rv}")
    if changed:
        cur["updated"] = int(time.time())
        s3.put_object(Bucket=B, Key=guard(mkey), ContentType="application/json",
                      Body=json.dumps(cur, ensure_ascii=False, indent=1).encode("utf-8"))
        print(f"✅ {mkey} — {changed} مدخلاً")
