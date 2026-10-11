#!/usr/bin/env python3
"""تقطيع التفاسير المفتوحة إلى مقتطفات صغيرة يقرؤها خادم المساعد الذكي مباشرةً.

المفتاح:  ai-tafsir/v1/<id>/<s>/<k>.json   حيث k = (a-1)//20
المحتوى:  {"id":"<id>","s":<s>,"t":{"<a>":"<مقتطف>"}}   (JSON خام مضغوط، UTF-8)
الفهرس:   ai-tafsir/v1/index.json

⛔ الرفع لا يحذف شيئاً ولا يكتب خارج البادئة ai-tafsir/v1/، ولا يبدأ قبل
   التحقق من أن الدلو هو دلو الخادم (وجود ai-src/v1/catalog.json).
"""
import argparse
import datetime
import gzip
import hashlib
import json
import os
import re
import sys
import unicodedata
import urllib.request

PUB = "https://pub-2c2e1dcd92e84a2898820dd38d3e09e6.r2.dev"
CATALOG_URL = PUB + "/packages/tafsir/open/catalog.json"
UA = "curl/8.5.0"
PREFIX = "ai-tafsir/v1/"
SENTINEL = "ai-src/v1/catalog.json"
CHUNK = 20
MAX_CHARS = 2500

_DIAC = re.compile("[ً-ٰٟۖ-ۭ]")
_WS = re.compile(r"\s+")


def excerpt(text, limit=MAX_CHARS):
    """NFKC ثم نزع الحركات ثم طي الفراغات ثم القص عند آخر فراغ."""
    t = unicodedata.normalize("NFKC", text or "")
    t = _DIAC.sub("", t)
    t = _WS.sub(" ", t).strip()
    if len(t) <= limit:
        return t
    cut = t[:limit]
    sp = cut.rfind(" ")
    if sp > 0:
        cut = cut[:sp]
    return cut.rstrip() + " …"


def chunk_key(tid, s, a):
    return f"{PREFIX}{tid}/{s}/{(a - 1) // CHUNK}.json"


def dumps(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def build_surah(tid, s, texts):
    """texts: {"s:a": نص} ⇒ {مفتاح: بايتات} للسورة s."""
    chunks = {}
    for ref, txt in texts.items():
        try:
            ss, aa = ref.split(":")
            ss, aa = int(ss), int(aa)
        except ValueError:
            continue
        if ss != s or aa < 1:
            continue
        ex = excerpt(txt)
        if not ex:
            continue
        chunks.setdefault(chunk_key(tid, s, aa), {})[str(aa)] = ex
    out = {}
    for key, t in chunks.items():
        t = dict(sorted(t.items(), key=lambda kv: int(kv[0])))
        out[key] = dumps({"id": tid, "s": s, "t": t})
    return out


def r2_client():
    import boto3
    need = ("R2_ENDPOINT", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET")
    miss = [k for k in need if not os.environ.get(k)]
    if miss:
        sys.exit(f"⛔ متغيرات R2 ناقصة: {miss}")
    s3 = boto3.client("s3", endpoint_url=os.environ["R2_ENDPOINT"],
                      aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
                      aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
                      region_name="auto")
    return s3, os.environ["R2_BUCKET"]


def verify_bucket(s3, bucket):
    from botocore.exceptions import ClientError
    try:
        s3.head_object(Bucket=bucket, Key=SENTINEL)
    except ClientError as e:
        sys.exit(f"⛔ الدلو ليس دلو الخادم: لا يوجد {SENTINEL} ({e}). لم يُكتب شيء.")


def remote_etags(s3, bucket):
    etags = {}
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=PREFIX):
        for o in page.get("Contents", []):
            etags[o["Key"]] = o["ETag"].strip('"')
    return etags


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="out_ai_tafsir", help="المجلد المحلي")
    ap.add_argument("--upload", action="store_true", help="رفع ما تغيّر إلى R2")
    ap.add_argument("--only", default="", help="معرّفات مفصولة بفواصل")
    ap.add_argument("--limit-surahs", type=int, default=0)
    args = ap.parse_args()

    only = {x.strip() for x in args.only.split(",") if x.strip()}
    cat = json.loads(fetch(CATALOG_URL))
    s3 = bucket = None
    if args.upload:
        s3, bucket = r2_client()
        verify_bucket(s3, bucket)  # قبل أي كتابة

    files = {}  # مفتاح ⇒ بايتات
    written, skipped = [], []
    for tf in cat["tafsirs"]:
        tid = tf["id"]
        if only and tid not in only:
            continue
        if tf.get("numbering") != "kufi":
            skipped.append(f"{tid} (numbering={tf.get('numbering')})")
            continue
        shards = sorted(tf["shards"], key=lambda x: int(x["surah"]))
        if args.limit_surahs:
            shards = shards[:args.limit_surahs]
        n = 0
        for sh in shards:
            raw = fetch(f"{PUB}/{tf['prefix'].strip('/')}/{sh['file']}")
            if sh.get("sha256") and hashlib.sha256(raw).hexdigest() != sh["sha256"]:
                sys.exit(f"⛔ sha256 مخالف: {tid}/{sh['file']}")
            data = json.loads(gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw)
            files.update(build_surah(tid, int(sh["surah"]), data.get("text", {})))
            n += 1
        written.append(tf)
        print(f"{tid}: {n} سورة", flush=True)

    index = {"version": 1,
             "updated": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
             "chunk": CHUNK,
             "tafsirs": [{k: t.get(k) for k in ("id", "name", "author", "died_h", "group", "filled")}
                         for t in written]}
    index_key = PREFIX + "index.json"

    total = 0
    for key, body in files.items():
        p = os.path.join(args.out, key)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as f:
            f.write(body)
        total += len(body)
    ib = dumps(index)
    os.makedirs(os.path.join(args.out, PREFIX), exist_ok=True)
    with open(os.path.join(args.out, index_key), "wb") as f:
        f.write(ib)

    uploaded = 0
    if args.upload:
        etags = remote_etags(s3, bucket)
        for key, body in list(files.items()) + [(index_key, ib)]:
            assert key.startswith(PREFIX)
            if etags.get(key) == hashlib.md5(body).hexdigest():
                continue
            s3.put_object(Bucket=bucket, Key=key, Body=body,
                          ContentType="application/json; charset=utf-8")
            uploaded += 1

    print(f"الملخص: تفاسير={len(written)} ملفات={len(files) + 1} "
          f"مرفوع={uploaded} متخطّى={len(skipped)} الحجم={total / 1e6:.2f} م.ب")
    for s in skipped:
        print("  تخطّي:", s)


if __name__ == "__main__":
    main()
