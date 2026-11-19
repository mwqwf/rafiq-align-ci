#!/usr/bin/env python3
"""جرد شواهد state-ci بتوازٍ محدود وكاش محلي، دون قرارات ترقية أو كتابة للدلو."""
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from dataclasses import dataclass, field
import json
from pathlib import Path

if __package__:
    from .verdict_cache import cached, store
else:
    from verdict_cache import cached, store


CACHE_DIR = Path(__file__).resolve().parent / "work" / "verdict_cache"
CREDS = Path(__file__).resolve().parents[2] / "secure" / "r2_credentials.json"
MAX_WORKERS = 16


def classify(report):
    """تصنيف الجرد القديم: القبول بالبادئة، وأولوية البنيوي ثم الجسيم ثم الحدّي."""
    verdict = str(report.get("verdict") or "")
    if verdict.startswith("مقبول"):
        return None
    return ("خلل بنيوي" if "بنيوي" in verdict else
            "عطبٌ جسيم" if "جسيم" in verdict else
            "حدّي" if "حدّي" in verdict else
            "موقوف" if "موقوف" in verdict else "آخر")


@dataclass
class Inventory:
    per: Counter = field(default_factory=Counter)
    seen: int = 0
    read: int = 0
    hits: int = 0
    failed: int = 0
    list_failed: bool = False

    @property
    def partial(self):
        return bool(self.failed or self.list_failed)


def inventory(client, bucket, cache_dir=CACHE_DIR):
    """كائن واحد = شاهد واحد، بلا ترشيح امتداد أو اشتراط حقل key في التقرير.

    طلب GET واحد لكل كائن غير مخزّن، بلا إعادة محاولات إضافية. يبقى نطاق
    السرد state-ci حرفياً (بلا /)، ويُعاد السرد حتى عند دفء الذاكرة.
    """
    result = Inventory()
    cache_dir = Path(cache_dir)
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass  # تعطل الذاكرة المحلية لا يمنع القراءة من المصدر.

    def one(obj):
        try:
            key = obj["Key"]
            etag = obj.get("ETag")
            etag = etag.strip('"') if isinstance(etag, str) else ""
            report = None
            if etag:  # لا تُوثق ذاكرة بلا ETag من السرد الحالي.
                try:
                    report = cached(cache_dir, key, etag)
                except OSError:
                    pass
            if isinstance(report, dict):
                return report, True
            response = client.get_object(Bucket=bucket, Key=key)
            with closing(response["Body"]) as body:
                report = json.loads(body.read())
            if not isinstance(report, dict):
                raise ValueError("الحكم ليس كائن JSON")
            response_etag = response.get("ETag")
            response_etag = response_etag.strip('"') if isinstance(response_etag, str) else ""
            # قد يتغير الكائن بين السرد وGET؛ لا يُنسب محتوى جديد إلى ETag قديم.
            if etag and response_etag == etag:
                store(cache_dir, key, etag, report)
            return report, False
        except Exception:  # noqa: BLE001 — فشل ملف لا يخفي بقية الشواهد.
            return None, False

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        try:
            pages = client.get_paginator("list_objects_v2").paginate(
                Bucket=bucket, Prefix="state-ci")
            for page in pages:
                objects = page.get("Contents", [])
                result.seen += len(objects)
                # map يحفظ ترتيب السرد وتعادل عدّادات most_common في المسار القديم.
                for report, hit in pool.map(one, objects):
                    if report is None:
                        result.failed += 1
                        continue
                    result.read += 1
                    result.hits += int(hit)
                    kind = classify(report)
                    if kind is not None:
                        result.per[kind] += 1
        except Exception:  # noqa: BLE001 — يشمل فشل صفحة لاحقة بعد عدّ صفحات سابقة.
            result.list_failed = True
    return result


def print_summary(result):
    print("## ⚡ ما ينتظر قراراً")
    if result.partial:
        print("⚠️ جرد جزئي: الأعداد أدناه حد أدنى، وليست حصيلة كاملة.")
    for kind, count in result.per.most_common():
        print(f"- {kind}: {count} شاهداً")
    print(f"- قُرئ {result.read} من {result.seen} كائناً مسروداً؛ "
          f"من الذاكرة {result.hits}؛ تعذّر {result.failed}.")
    if result.list_failed:
        print("⚠️ تعذّر إكمال السرد؛ عدد الكائنات الكلي غير معلوم.")


def main():
    try:
        import boto3
        with CREDS.open(encoding="utf-8") as stream:
            credentials = json.load(stream)
        client = boto3.client(
            "s3", endpoint_url=credentials["endpoint"],
            aws_access_key_id=credentials["accessKeyId"],
            aws_secret_access_key=credentials["secretAccessKey"],
            region_name="auto")
        result = inventory(client, credentials["bucket"])
    except Exception:  # noqa: BLE001 — غياب الاعتماد أو فشل العميل ليس جرداً فارغاً ناجحاً.
        result = Inventory(list_failed=True)
    print_summary(result)
    return 1 if result.partial else 0


if __name__ == "__main__":
    raise SystemExit(main())
