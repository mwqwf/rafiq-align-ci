#!/usr/bin/env python3
"""☁️ رفعُ سجلّ private-ci الكامل إلى بادئةٍ خاصّة في R2 — بمكتبة بايثون القياسيّة وحدها (توقيعُ SigV4 يدويّ).

لماذا بلا boto3: كلُّ حزمةٍ تُثبَّت من PyPI في شوطٍ يحمل بيانةَ R2 بابُ سلسلةِ توريد؛ والتوقيعُ ستّون سطراً.

الوضعان:
  private — البيانةُ من PCI_R2_JSON (‏سرُّ البيئة private-ci)، والدلوُ يجب أن يكون في PRIVATE_BUCKETS وليس في
            PUBLIC_BUCKETS، والبادئة ci/private-ci/. وبعد الرفع **يُسأل النطاقُ العامّ r2.dev عن المفتاح نفسِه**:
            إن ردّ 200 فالدلوُ علنيٌّ ⇒ يُحذف الكائنُ فوراً ويفشل الشوط (رمز 4). ويُكتب رابطٌ موقَّعٌ لسبعة أيّام
            في ملفٍّ بأذونات 600 (‏لا يُطبع) لتحمله حالةُ الإيداع في المستودع الخاص وحدَه.
  dryrun  — البيانةُ الموجودة R2_CREDENTIALS_JSON والدلوُ العامّ، والبادئة tmp/private-ci-dryrun/ — لأنّ ما يُرفع
            في التجربة سجلُّ المستودع العام نفسِه؛ ويُسأل النطاقُ العامّ أيضاً فيُتوقَّع 200 (‏برهانُ أنّ المسبار يعمل).

⛔ لا يطبع بيانةً ولا رابطاً موقَّعاً ولا مسارَ ملفٍّ محلّيّ: المطبوعُ عددُ الكائنات وأحجامُها ونتيجةُ المسبار فقط.
"""
import argparse
import datetime
import gzip
import hashlib
import hmac
import json
import os
import sys
import tarfile
import urllib.error
import urllib.parse
import urllib.request

PRIVATE_BUCKETS = {"mushafak-private"}
PUBLIC_BUCKETS = {"rafiq-media"}
PUBLIC_ORIGIN = "https://pub-2c2e1dcd92e84a2898820dd38d3e09e6.r2.dev"
PRIVATE_PREFIX = "ci/private-ci/"
DRYRUN_PREFIX = "tmp/private-ci-dryrun/"
PRESIGN_SECONDS = 7 * 24 * 3600
EXIT_OK, EXIT_FAIL, EXIT_PUBLIC_BUCKET = 0, 1, 4


# ───── SigV4 (S3) — مطابقٌ لمثال وثائق AWS للرابط الموقَّع (يُختبر في test_upload_r2.py) ─────
def _h(key, msg):
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def _signing_key(secret, date, region, service):
    k = _h(("AWS4" + secret).encode("utf-8"), date)
    k = _h(k, region)
    k = _h(k, service)
    return _h(k, "aws4_request")


def _uri_encode(s, keep_slash):
    return urllib.parse.quote(s, safe="/~" if keep_slash else "~")


def presign_get(host, path, access_key, secret, now, expires, region="auto", service="s3"):
    """رابطٌ موقَّعٌ لـGET (‏path يبدأ بـ/ ويُرمَّز هنا)."""
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    date = amz_date[:8]
    scope = f"{date}/{region}/{service}/aws4_request"
    q = {
        "X-Amz-Algorithm": "AWS4-HMAC-SHA256",
        "X-Amz-Credential": f"{access_key}/{scope}",
        "X-Amz-Date": amz_date,
        "X-Amz-Expires": str(int(expires)),
        "X-Amz-SignedHeaders": "host",
    }
    cq = "&".join(f"{_uri_encode(k, False)}={_uri_encode(v, False)}" for k, v in sorted(q.items()))
    canonical = "\n".join(["GET", _uri_encode(path, True), cq, f"host:{host}\n", "host", "UNSIGNED-PAYLOAD"])
    sts = "\n".join(["AWS4-HMAC-SHA256", amz_date, scope, hashlib.sha256(canonical.encode()).hexdigest()])
    sig = hmac.new(_signing_key(secret, date, region, service), sts.encode(), hashlib.sha256).hexdigest()
    return f"https://{host}{_uri_encode(path, True)}?{cq}&X-Amz-Signature={sig}"


def signed_request(method, host, path, access_key, secret, now, body=b"", content_type=None,
                   region="auto", service="s3"):
    """يُعيد (url, headers) لطلبٍ موقَّعٍ في الترويسة."""
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    date = amz_date[:8]
    payload_hash = hashlib.sha256(body).hexdigest()
    headers = {"host": host, "x-amz-content-sha256": payload_hash, "x-amz-date": amz_date}
    if content_type:
        headers["content-type"] = content_type
    signed = ";".join(sorted(headers))
    canon_headers = "".join(f"{k}:{headers[k].strip()}\n" for k in sorted(headers))
    canonical = "\n".join([method, _uri_encode(path, True), "", canon_headers, signed, payload_hash])
    scope = f"{date}/{region}/{service}/aws4_request"
    sts = "\n".join(["AWS4-HMAC-SHA256", amz_date, scope, hashlib.sha256(canonical.encode()).hexdigest()])
    sig = hmac.new(_signing_key(secret, date, region, service), sts.encode(), hashlib.sha256).hexdigest()
    headers["authorization"] = (f"AWS4-HMAC-SHA256 Credential={access_key}/{scope}, "
                                f"SignedHeaders={signed}, Signature={sig}")
    headers.pop("host")
    return f"https://{host}{_uri_encode(path, True)}", headers


# ───── الرفع ─────
def load_creds(env_name):
    raw = os.environ.get(env_name, "")
    if not raw:
        return None
    c = json.loads(raw)
    need = ("endpoint", "accessKeyId", "secretAccessKey", "bucket")
    if not all(isinstance(c.get(k), str) and c.get(k) for k in need):
        raise ValueError("بيانةٌ ناقصة")
    host = urllib.parse.urlparse(c["endpoint"]).netloc or c["endpoint"]
    if not host.endswith(".r2.cloudflarestorage.com"):
        raise ValueError("نقطةُ نهايةٍ ليست R2")
    return {"host": host, "key": c["accessKeyId"], "secret": c["secretAccessKey"], "bucket": c["bucket"]}


def check_bucket(mode, bucket):
    if mode == "private":
        if bucket in PUBLIC_BUCKETS or bucket not in PRIVATE_BUCKETS:
            raise ValueError("⛔ الدلوُ ليس في قائمة الدلاء الخاصّة — لا رفعَ لسجلٍّ خاص")
    elif mode == "dryrun":
        if bucket in PRIVATE_BUCKETS:
            raise ValueError("⛔ التجربةُ لا تكتب في الدلو الخاص")


def put_object(creds, key, body, content_type, opener=urllib.request.urlopen):
    now = datetime.datetime.now(datetime.timezone.utc)
    url, headers = signed_request("PUT", creds["host"], f"/{creds['bucket']}/{key}", creds["key"],
                                  creds["secret"], now, body, content_type)
    req = urllib.request.Request(url, data=body, method="PUT", headers=headers)
    with opener(req, timeout=120) as r:
        if r.status not in (200, 201):
            raise RuntimeError(f"PUT {r.status}")


def delete_object(creds, key, opener=urllib.request.urlopen):
    now = datetime.datetime.now(datetime.timezone.utc)
    url, headers = signed_request("DELETE", creds["host"], f"/{creds['bucket']}/{key}", creds["key"],
                                  creds["secret"], now)
    with opener(urllib.request.Request(url, method="DELETE", headers=headers), timeout=60):
        pass


def public_probe(key, opener=urllib.request.urlopen):
    """رمزُ ردّ النطاق العامّ لهذا المفتاح (0 عند تعذّر الاتصال)."""
    req = urllib.request.Request(f"{PUBLIC_ORIGIN}/{urllib.parse.quote(key)}", method="HEAD",
                                 headers={"User-Agent": "private-ci-probe"})
    try:
        with opener(req, timeout=30) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except (urllib.error.URLError, OSError):
        return 0


def build_bundle(out_dir, extra_dirs, dest):
    """يجمع المجلّدات الإضافيّة (لقطات · نتائج الاختبار) في tar.gz واحد؛ يُتخطّى ما غاب."""
    n = 0
    with tarfile.open(dest, "w:gz") as t:
        for d in extra_dirs:
            if d and os.path.isdir(d):
                t.add(d, arcname=os.path.basename(d.rstrip("/")))
                n += 1
    return n


def run(a):
    creds = load_creds(a.creds_env)
    if creds is None:
        print("الرفع: ⛔ لا بيانةَ R2 في هذا الشوط")
        return EXIT_FAIL
    check_bucket(a.mode, creds["bucket"])
    base = (PRIVATE_PREFIX if a.mode == "private" else DRYRUN_PREFIX) + f"{a.sha}/{a.run_id}-{a.attempt}/{a.leg}/"
    objects = []
    log = os.path.join(a.out, "log.txt")
    if os.path.isfile(log):
        with open(log, "rb") as f:
            objects.append(("log.txt.gz", gzip.compress(f.read(), 6), "application/gzip"))
    for name, ct in (("counts.json", "application/json"), ("summary.md", "text/markdown; charset=utf-8"),
                     ("guard_private.json", "application/json")):
        p = os.path.join(a.out, name)
        if os.path.isfile(p):
            with open(p, "rb") as f:
                objects.append((name, f.read(), ct))
    if a.extra:
        tgz = os.path.join(a.state, "bundle.tgz")
        if build_bundle(a.out, a.extra, tgz):
            with open(tgz, "rb") as f:
                objects.append(("bundle.tgz", f.read(), "application/gzip"))
    if not objects:
        print("الرفع: ⛔ لا شيءَ يُرفع")
        return EXIT_FAIL
    total = 0
    for name, body, ct in objects:
        put_object(creds, base + name, body, ct)
        total += len(body)
    probe = public_probe(base + objects[0][0])
    if a.mode == "private" and probe == 200:
        for name, _b, _c in objects:
            try:
                delete_object(creds, base + name)
            except Exception:  # noqa: BLE001 — الحذفُ أفضلُ جهد، والفشلُ يُعلن أدناه
                pass
        print("الرفع: ⛔ الكائنُ مقروءٌ من النطاق العامّ ⇒ الدلوُ علنيّ؛ حُذف ما رُفع")
        return EXIT_PUBLIC_BUCKET
    if a.mode == "private":
        link = presign_get(creds["host"], f"/{creds['bucket']}/{base}log.txt.gz", creds["key"], creds["secret"],
                           datetime.datetime.now(datetime.timezone.utc), PRESIGN_SECONDS)
        fd = os.open(os.path.join(a.state, "link.txt"), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(link)
    expect = "403/404" if a.mode == "private" else "200"
    print(f"الرفع: ✅ {len(objects)} كائنات · {total // 1024} ك.ب · مسبارُ النطاق العامّ {probe} (المتوقَّع {expect})")
    if a.mode == "dryrun" and probe != 200:
        print("الرفع: ⚠ المسبارُ لم يرَ الكائنَ العامّ — قد لا يكشف دلواً علنيّاً؛ يُراجع قبل التفعيل")
    return EXIT_OK


def main(argv=None):
    ap = argparse.ArgumentParser(description="رفع سجلّ private-ci إلى R2")
    ap.add_argument("--mode", choices=("private", "dryrun"), required=True)
    ap.add_argument("--creds-env", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--state", required=True)
    ap.add_argument("--sha", required=True)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--attempt", default="1")
    ap.add_argument("--leg", required=True)
    ap.add_argument("--extra", nargs="*", default=[])
    a = ap.parse_args(argv)
    try:
        return run(a)
    except ValueError as e:
        print(f"الرفع: {e}" if str(e).startswith("⛔") else "الرفع: ⛔ بيانةٌ أو دلوٌ غيرُ مقبول")
        return EXIT_FAIL
    except Exception as e:  # noqa: BLE001 — لا يُطبع نصُّ الاستثناء: قد يحمل رابطاً أو ترويسة
        print(f"الرفع: ⛔ تعذّر ({type(e).__name__})")
        return EXIT_FAIL


if __name__ == "__main__":
    sys.exit(main())
