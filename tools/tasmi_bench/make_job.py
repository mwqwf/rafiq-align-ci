# -*- coding: utf-8 -*-
"""يحوّل sample.json إلى job.json للخادم — بروابط **موقّعة مسبقاً** لأصول R2.

⛔ لا مفتاح ولا سرّ يغادر جهاز المالك: التوقيع هنا، والخادم يرى روابط مؤقتة فقط.

    python tools/tasmi_bench/make_job.py [--expires 86400]
"""
import argparse
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--expires", type=int, default=86400)
    ap.add_argument("--out", default=os.path.join(HERE, "work", "job.json"))
    ap.add_argument("--plan", help="خطة حقن (r2Key ⇒ رابط موقّع، للبند والمانح)")
    args = ap.parse_args()
    import boto3
    c = json.load(open(os.path.join(ROOT, "secure", "r2_credentials.json")))
    s3 = boto3.client("s3", endpoint_url=c["endpoint"], aws_access_key_id=c["accessKeyId"],
                      aws_secret_access_key=c["secretAccessKey"], region_name="auto")
    def sign(key):
        return s3.generate_presigned_url("get_object",
                                         Params={"Bucket": c["bucket"], "Key": key},
                                         ExpiresIn=args.expires)

    if args.plan:                       # وضع خطة الحقن: نُبقي البنية ونوقّع المفاتيح
        plan = json.load(open(args.plan, encoding="utf-8"))
        for it in plan["items"]:
            if "r2Key" in it:
                it["url"] = sign(it.pop("r2Key"))
            if it.get("donor", {}).get("r2Key"):
                it["donor"]["url"] = sign(it["donor"].pop("r2Key"))
        os.makedirs(os.path.dirname(args.out), exist_ok=True)
        json.dump(plan, open(args.out, "w", encoding="utf-8"), ensure_ascii=False)
        print(f"✅ خطة موقّعة: {len(plan['items'])} بنداً → {args.out}")
        return

    data = json.load(open(os.path.join(HERE, "sample.json"), encoding="utf-8"))
    items = []
    for it in data["items"]:
        src = it["source"]
        job = {"id": it["id"]}
        if src["kind"] == "ayah_file":
            url = src["url"]
            if ".r2.dev/" in url:                       # مرآتنا: رابط موقّع بدل العام
                key = url.split(".r2.dev/", 1)[1]
                url = s3.generate_presigned_url("get_object",
                                                Params={"Bucket": c["bucket"], "Key": key},
                                                ExpiresIn=args.expires)
            job["url"] = url
        else:
            job["url"] = s3.generate_presigned_url(
                "get_object", Params={"Bucket": c["bucket"], "Key": src["r2Key"]},
                ExpiresIn=args.expires)
            job["startMs"], job["endMs"] = src["startMs"], src["endMs"]
        items.append(job)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    json.dump({"items": items}, open(args.out, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"✅ {len(items)} بنداً → {args.out} (صلاحية {args.expires}ث)")


if __name__ == "__main__":
    main()
