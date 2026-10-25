#!/usr/bin/env python3
"""منحةُ روابط R2 لشوط تقطير «المُنصِت» على Vertex (تعمل على المشغّل لا على الجهاز).

    r2_distill_grant.py --out grant.json --expect-step 13500

الحالةُ كلُّها على R2 تحت `models/mushafak1/stage-distill-gcp/` (لا يُمسّ `stage/` ولا `stage-distill/` ولا `stage-out/`):
  ckpt/last.pt (نقطةُ البدء = نسخةُ الخطوة 13500؛ ثمّ يكتبها الشوطُ كلَّ 10 دقائق) · ckpt/best.pt · status.json · train.log · spans.jsonl ·
  out/*.onnx · code.zip + code_manifest.json (الشيفرةُ ببصمتها) · ckpt_manifest.json (خطوةُ البدء وsha256).
يُقرأ من R2 بروابط GET موقّعة (7 أيام): المعلّمُ `stage-out/140121/best.pt` وملفّاتُ `stage/d2delta/` (الجزء 16)؛ وتُكتب النتائجُ بروابط PUT موقّعة.
الاعتمادُ من secure/r2_credentials.json (يكتبه السير من السرّ). ⛔ لا تُطبع روابطُ ولا مفاتيح: أعدادٌ وأحجامٌ فقط، وتُقنَّع التواقيع في سجلّ Actions.
"""
import argparse
import json
import sys
import time
import urllib.parse

import boto3
from botocore.config import Config

PFX = "models/mushafak1/stage-distill-gcp/"
STAGE_MAN = "models/mushafak1/stage/manifest.json"
TEACHER_KEY = "models/mushafak1/stage-out/140121/best.pt"
TEACHER_SHA = "3c061c7c5a5214f66f76af3b5a1ee98da9a3e6a3e384881be802951415777978"
G2P_URL = "https://pub-2c2e1dcd92e84a2898820dd38d3e09e6.r2.dev/tasmi/g2p_labels_2026-09-20.jsonl.gz"
PUT_NAMES = {"last": "ckpt/last.pt", "best": "ckpt/best.pt", "status": "status.json", "log": "train.log", "spans": "spans.jsonl",
             "onnx_best": "out/best.model.int8.onnx", "onnx_best_meta": "out/best.export.json",
             "onnx_last": "out/last.model.int8.onnx", "onnx_last_meta": "out/last.export.json"}
DAYS = 7


def die(msg):
    sys.exit(f"::error::{msg}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--creds", default="secure/r2_credentials.json")
    ap.add_argument("--out", required=True)
    ap.add_argument("--expect-step", type=int, required=True)
    a = ap.parse_args()
    cr = json.load(open(a.creds, encoding="utf-8"))
    s3 = boto3.client("s3", endpoint_url=cr["endpoint"], aws_access_key_id=cr["accessKeyId"], aws_secret_access_key=cr["secretAccessKey"],
                      region_name="auto", config=Config(signature_version="s3v4", retries={"max_attempts": 5}))
    bucket, ttl = cr["bucket"], DAYS * 86400 - 600

    def sign(op, key):
        u = s3.generate_presigned_url(op, Params={"Bucket": bucket, "Key": key}, ExpiresIn=ttl)
        q = urllib.parse.parse_qs(urllib.parse.urlparse(u).query)
        for k in ("X-Amz-Signature", "X-Amz-Credential"):
            for v in q.get(k, []):
                print(f"::add-mask::{v}")
        return u

    def head(key):
        try:
            return int(s3.head_object(Bucket=bucket, Key=key)["ContentLength"])
        except Exception as e:  # noqa: BLE001
            die(f"غاب {key} عن R2 ({type(e).__name__})")

    def jget(key):
        return json.loads(s3.get_object(Bucket=bucket, Key=key)["Body"].read())

    cm = jget(PFX + "ckpt_manifest.json")
    if int(cm["step"]) < a.expect_step:
        die(f"نقطةُ البدء {cm['step']} دون expect_step={a.expect_step}")
    if head(PFX + "ckpt/last.pt") != int(cm["size"]):
        # قد تكون الحملةُ مستأنفةً (last.pt كتبها شوطٌ سابق): نقبل أيَّ حجمٍ ما دام الملفّ قائماً، والخطوةُ تُتحقَّق داخل الجهاز
        print("last.pt حجمُه يخالف ckpt_manifest (شوطٌ سابقٌ كتبه؟) — تُتحقَّق الخطوة داخل الجهاز")
    head(PFX + "spans.jsonl")
    codem = jget(PFX + "code_manifest.json")
    if head(PFX + "code.zip") != int(codem["size"]):
        die("حجمُ code.zip يخالف code_manifest")
    head(TEACHER_KEY)
    man = jget(STAGE_MAN)
    data = []
    for f in man.get("files", []):
        key = f["key"]
        full = key if key.startswith("models/mushafak1/stage/") else "models/mushafak1/stage/" + key.lstrip("/")
        rel = full[len("models/mushafak1/stage/"):]
        if not rel.startswith("d2delta/"):
            continue
        size = int(f.get("size", f.get("bytes")))
        if head(full) != size or not f.get("sha256"):
            die(f"ملفّ d2delta غير متّسق: {rel}")
        data.append({"rel": rel.split("/", 1)[1], "size": size, "sha256": f["sha256"], "url": sign("get_object", full)})
    if not any(d["rel"] == "part_16.tar" for d in data) or not any(d["rel"] == "eligible.json" for d in data):
        die("d2delta ناقصة (part_16.tar/eligible.json)")
    exp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + ttl))
    g = {"expires": exp, "note": "distill-gcp",
         "teacher": {"get": sign("get_object", TEACHER_KEY), "sha": TEACHER_SHA}, "g2p": G2P_URL,
         "get": {"last": sign("get_object", PFX + "ckpt/last.pt"), "spans": sign("get_object", PFX + "spans.jsonl")},
         "put": {k: sign("put_object", PFX + v) for k, v in PUT_NAMES.items()},
         "code": {"get": sign("get_object", PFX + "code.zip"), "sha256": codem["sha256"], "size": int(codem["size"]), "commit": codem.get("commit")},
         "data": data}
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(g, fh, separators=(",", ":"))
    print(f"grant: start_step={cm['step']} code={str(codem.get('commit'))[:10]} data_files={len(data)} puts={len(g['put'])} expires={exp}")


if __name__ == "__main__":
    main()
