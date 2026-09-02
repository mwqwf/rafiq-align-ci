# -*- coding: utf-8 -*-
"""هل لهذا القارئ فهرسٌ **كامل** على الدلو؟ يخرج 0 إن كان (فيُتخطّى).

⛔ سببه أن الجبهتين (‏CI وCloud Run) تعملان على القائمة نفسها من طرفيها
(أمر github-f4: هذه من الذيل وتلك من الرأس، فتلتقيان في الوسط). فالسؤال قبل
كل قارئ ليس «هل بدأتُه؟» بل **«هل أنجزه أحدٌ سلفاً؟»** — والجواب من الدلو
لا من قائمةٍ محلية، لأن القائمة لقطةٌ والدلو حالة.

⛔ و«كامل» تعني **بلا لاحقة `partial`**: الجزئي عملٌ محفوظ لا فهرسٌ منجَز،
وتخطّي قارئٍ لأجل لقطةٍ جزئية يترك العمل ناقصاً عند الطرفين معاً.

    python already_done.py <riwaya> <reciterId>     ⇒ 0 موجود · 1 غير موجود
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def main():
    riwaya, rid = sys.argv[1], sys.argv[2]
    try:
        import boto3
        c = json.load(open(os.path.join(ROOT, "secure", "r2_credentials.json")))
        s3 = boto3.client("s3", endpoint_url=c["endpoint"],
                          aws_access_key_id=c["accessKeyId"],
                          aws_secret_access_key=c["secretAccessKey"], region_name="auto")
        found = []
        for page in s3.get_paginator("list_objects_v2").paginate(
                Bucket=c["bucket"], Prefix=f"timings-staging/{riwaya}/{rid}."):
            for o in page.get("Contents", []):
                k = o["Key"]
                if k.endswith(".jz") and ".partial" not in k:
                    found.append((k, o["LastModified"]))
    except Exception as ex:
        # ⛔ فشلٌ **مفتوح** هنا عمداً، على عكس حرّاس الرفع: تعذّرُ السؤال
        #    يعني «لا أعلم»، والعمل عند الشكّ **أرخص من تركه**. (وحارس الرفع
        #    يمنع التكرار على الدلو لاحقاً، فالبصمة تُسقط المكرَّر.)
        print(f"⚠️ تعذّر السؤال عن {rid} ({ex}) — يُعمل عند الشكّ")
        return 1
    if found:
        k, t = sorted(found, key=lambda x: x[1])[-1]
        print(f"⏭ {rid}: فهرسٌ كامل موجودٌ سلفاً — {k} ({t:%H:%M}Z)")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
