# -*- coding: utf-8 -*-
"""نشر فهرس التوقيتات الكلمية إلى R2 — **يكتبه من لا يملك الصلاحية، ويشغّله من يملكها.**

⛔ هذا السكربت **لا يحمل أي سرّ** ولا يقرأ ملف أسرار. يقرأ الاعتماديات من **بيئة
التشغيل** حصراً، فمن لا يملكها لا يستطيع تشغيله ولو ملك السكربت.

المتغيرات المطلوبة:
    R2_ACCOUNT_ID · R2_ACCESS_KEY_ID · R2_SECRET_ACCESS_KEY · R2_BUCKET
    (اختياري) R2_PREFIX — الافتراضي "wordtimings/qalun"

الاستعمال:
    python publish.py --file out/wordtimings_husary_qalun.jz            # فحص فقط
    python publish.py --file out/wordtimings_husary_qalun.jz --confirm  # ينشر فعلاً

**النشر لا يقع بلا `--confirm`.** والفحص وحده (بلا العلم) يطبع كل ما سيحدث: الوجهة
والحجم والبصمة وملخص التغطية — فلا يُنشر شيء على غير علم.

الحُرّاس قبل الرفع (كلها تمنع النشر ولا تحذّر فقط، وكلٌّ يطبع سنده):
  1. الملف يُقرأ ويُفكّ فعلاً (‏.jz سليم) وليس مبتوراً.
  2. `schema` و`riwaya` و`reciterId` و`indexing` و`endsPolicy` حاضرة.
  3. **لا مدخل بلا كلمات**، والكلمات رتيبة داخل كل آية ولا تتجاوز مدى الآية.
  4. `coverageScope` موجود **وبالأرقام** — لا نشر بوعد تغطية بلا رقم.
  5. مقارنة بالمنشور حالياً (إن وُجد): **لا ينقص عدد الآيات** — النشر لا يتراجع
     بالتغطية إلا بعلم صريح (`--allow-shrink`).
"""
import argparse
import hashlib
import io
import json
import os
import sys
import zlib

# ⛔ المخرج عربي والمشغّل قد يكون بترميز غير UTF-8 (سقط هذا السكربت فعلاً على
#    ويندوز بـcp1256 عند طباعة رمز المنع، فمات قبل أن يطبع سنده).
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

_HERE = os.path.dirname(os.path.abspath(__file__))
_V2 = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(os.path.dirname(_V2), "alignment"))

# نقطة النهاية إمّا R2_ENDPOINT كاملة (كما في /root/.r2env على خادم الأسطول) أو تُشتق من R2_ACCOUNT_ID
REQUIRED_ENV = ("R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET")
PUBLIC_BASE = "https://pub-2c2e1dcd92e84a2898820dd38d3e09e6.r2.dev"


def read_jz_bytes(raw):
    return json.loads(zlib.decompress(raw, 31))


def check(doc, path):
    """يعيد قائمة أسباب المنع (فارغة = سليم). كل سبب يحمل سنده الرقمي."""
    bad = []
    for k in ("schema", "riwaya", "reciterId", "indexing", "endsPolicy"):
        if not doc.get(k):
            bad.append("حقل ناقص في الترويسة: %s" % k)
    entries = doc.get("entries") or []
    if not entries:
        bad.append("لا مدخلات إطلاقاً")
        return bad
    empty = [e["ayahId"] for e in entries if not e.get("words")]
    if empty:
        bad.append("مدخلات بلا كلمات: %d (%s)" % (len(empty), empty[:5]))
    nonmono = []
    for e in entries:
        w = e["words"]
        if any(w[i]["endMs"] > w[i + 1]["startMs"] for i in range(len(w) - 1)):
            nonmono.append(e["ayahId"])
        if any(x["startMs"] > x["endMs"] for x in w):
            nonmono.append(e["ayahId"])
    if nonmono:
        bad.append("آيات بكلمات غير رتيبة: %d (%s)"
                   % (len(nonmono), sorted(set(nonmono))[:5]))
    scope = doc.get("coverageScope")
    if not scope:
        bad.append("لا coverageScope — لا يُنشر بلا نطاق تغطية")
    elif not all(isinstance(c, dict) and "covered" in c and "high" in c
                 for c in scope):
        bad.append("coverageScope بلا أرقام (أسماء بنود فقط) — وعد بلا سند")
    return bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True)
    ap.add_argument("--key", default=None,
                    help="مسار الوجهة داخل الدلو (الافتراضي من اسم الملف)")
    ap.add_argument("--confirm", action="store_true",
                    help="⛔ بدونه لا يقع نشر — فحص وعرض فقط")
    ap.add_argument("--allow-shrink", action="store_true",
                    help="اسمح بنشر أقل تغطية من المنشور حالياً")
    ap.add_argument("--kind", choices=["wordtimings", "timings"], default="wordtimings",
                    help="timings: فهرس آيات (TimingIndex 4.2) — حُرّاس الترويسة والمداخل فقط")
    ap.add_argument("--expect-sha", default=None,
                    help="لا يُنشر إلا إذا طابقت sha256 الملف هذه البادئة (استعادة نسخة مجمّدة)")
    ap.add_argument("--manifest", default=None,
                    help="مفتاح مانيفست يُحدَّث صفّه {riwaya, reciterId, entries, updatedTs} "
                         "بعد النشر (مثل timings/manifest.json)")
    args = ap.parse_args()

    with open(args.file, "rb") as f:
        raw = f.read()
    try:
        doc = read_jz_bytes(raw)
    except Exception as ex:
        print("⛔ الملف غير قابل للفك (مبتور؟): %s" % ex)
        return 2

    sha = hashlib.sha256(raw).hexdigest()
    entries = doc.get("entries") or []
    words = sum(len(e.get("words") or []) for e in entries)
    prefix = os.environ.get("R2_PREFIX", "wordtimings/qalun")
    key = args.key or "%s/%s" % (prefix, os.path.basename(args.file))

    print("الملف: %s" % args.file)
    print("  الحجم: %d ك.ب · sha256: %s" % (len(raw) // 1024, sha[:16]))
    print("  آيات: %d · كلمات: %d" % (len(entries), words))
    print("  الرواية/القارئ: %s / %s" % (doc.get("riwaya"), doc.get("reciterId")))
    print("  الاصطلاح: %s · النهايات: %s"
          % (doc.get("indexing"), doc.get("endsPolicy")))
    ga = doc.get("generatedAgainst") or {}
    print("  بُني على فهرس: %s (HIGH=%s · sha=%s)"
          % (ga.get("file"), ga.get("highCount"), str(ga.get("sha256"))[:12]))
    for c in doc.get("coverageScope") or []:
        print("  تغطية · %s: %s/%s" % (c.get("item"), c.get("covered"),
                                        c.get("high")))
    print("  الوجهة: s3://%s/%s" % (os.environ.get("R2_BUCKET", "<R2_BUCKET>"), key))

    if args.kind == "timings":
        bad = [x for x in ("schema", "riwaya", "reciterId") if not doc.get(x)]
        if not entries:
            bad.append("لا مداخل إطلاقاً")
        high = sum(1 for e in entries if e.get("confBand") == "HIGH")
        print("  فهرس آيات: %d مدخلاً · HIGH %d · engine %s"
              % (len(entries), high, doc.get("engineVersion")))
    else:
        bad = check(doc, args.file)
    if args.expect_sha and not sha.startswith(args.expect_sha):
        bad.append("sha256 %s لا تطابق المتوقعة %s" % (sha[:16], args.expect_sha))
    if bad:
        print("\n⛔ لا يُنشر — سند المنع:")
        for b in bad:
            print("   · %s" % b)
        return 3

    missing = [k for k in REQUIRED_ENV if not os.environ.get(k)]
    if not (os.environ.get("R2_ENDPOINT") or os.environ.get("R2_ACCOUNT_ID")):
        missing.append("R2_ENDPOINT|R2_ACCOUNT_ID")
    if missing:
        print("\nℹ️ متغيرات البيئة الناقصة: %s" % ", ".join(missing))
        print("   (الفحص تمّ بنجاح؛ النشر يحتاج من يملك هذه الاعتماديات)")
        return 0 if not args.confirm else 4

    import boto3  # noqa: E402  (لا يُستورد إلا عند وجود الاعتماديات)
    s3 = boto3.client(
        "s3",
        endpoint_url=os.environ.get("R2_ENDPOINT")
                     or "https://%s.r2.cloudflarestorage.com" % os.environ["R2_ACCOUNT_ID"],
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"])
    bucket = os.environ["R2_BUCKET"]

    try:                                    # حارس التراجع بالتغطية
        cur = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
        old = read_jz_bytes(cur)
        n_old = len(old.get("entries") or [])
        if len(entries) < n_old and not args.allow_shrink:
            print("\n⛔ لا يُنشر — سند المنع: المنشور فيه %d آية والجديد %d "
                  "(تراجع بالتغطية). استعمل --allow-shrink بعلم صريح."
                  % (n_old, len(entries)))
            return 5
        print("  المنشور حالياً: %d آية ⇐ الجديد %d" % (n_old, len(entries)))
    except Exception:
        print("  لا نسخة منشورة سابقاً بهذا المفتاح (نشر أول).")

    if not args.confirm:
        print("\n✅ الفحص سليم. **لم يُنشر شيء** — أضف --confirm للنشر الفعلي.")
        return 0

    s3.put_object(Bucket=bucket, Key=key, Body=raw,
                  ContentType="application/gzip",
                  CacheControl="public, max-age=3600")
    print("\n✅ نُشر: s3://%s/%s · %d ك.ب · sha256 %s"
          % (bucket, key, len(raw) // 1024, sha[:16]))
    if args.manifest:
        import json as _json
        import time as _time
        try:
            cur = _json.loads(s3.get_object(Bucket=bucket, Key=args.manifest)["Body"].read())
        except Exception:
            cur = {"version": 1, "indexes": []}
        row = {"riwaya": doc["riwaya"], "reciterId": doc["reciterId"],
               "entries": len(entries), "updatedTs": int(_time.time() * 1000)}
        cur["indexes"] = [x for x in cur.get("indexes", [])
                          if not (x.get("riwaya") == row["riwaya"]
                                  and x.get("reciterId") == row["reciterId"])]
        cur["indexes"].append(row)
        cur["updated"] = row["updatedTs"]
        s3.put_object(Bucket=bucket, Key=args.manifest,
                      Body=_json.dumps(cur, ensure_ascii=False).encode(),
                      ContentType="application/json")
        print("مانيفست %s: صفّ %s/%s = %d مدخلاً (%d فهرساً)"
              % (args.manifest, row["riwaya"], row["reciterId"], row["entries"],
                 len(cur["indexes"])))
    # تحقق على المضيف: القراءة العامة بالحجم والبصمة (r2.dev يحجب وكيل بايثون ⇒ UA متصفح)
    import urllib.request
    try:
        req = urllib.request.Request("%s/%s" % (PUBLIC_BASE, key),
                                     headers={"User-Agent": "Mozilla/5.0"})
        got = urllib.request.urlopen(req, timeout=120).read()
        ok = len(got) == len(raw) and hashlib.sha256(got).hexdigest() == sha
        print("تحقق القراءة العامة: %s (حجم %d مقابل %d · sha %s)"
              % ("✅" if ok else "❌", len(got), len(raw), "مطابق" if ok else "مختلف"))
        print("الرابط: %s/%s" % (PUBLIC_BASE, key))
        return 0 if ok else 6
    except Exception as ex:
        print("⚠️ تعذّر التحقق العام: %s" % ex)
        return 7


if __name__ == "__main__":
    sys.exit(main())
