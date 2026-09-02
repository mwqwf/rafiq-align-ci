# -*- coding: utf-8 -*-
"""مرشِّح بنيوي محلي لكل الوارد — بلا ثنائي ولا خادم ولا مال.

⛔ **ما هو، وما ليس هو** (يُقرأ قبل أي حكم يُبنى عليه):
- **هو** تشغيلٌ متوازٍ لـ`tools/index_qa/run.py --struct-only` على كل مفاتيح
  `timings/` و`timings-staging/`. الحكم البنيوي حكمُ تلك الأداة لا حكمي.
- **وليس** بديلاً عن التدقيق الصوتي. البنيوي **يرفض ولا يقبل**: يلتقط الفهرس
  المعطوب هيكلياً (لا أثر صقل · مداخل ناقصة · بصمات غائبة · مدد شاذة)، ولا
  يرى الإزاحة الزمنية أصلاً — وهي أخطر عيبٍ في فهرس توقيتات.

**لماذا يستحق أن يسبق الصوتي** (قسمة github-f4، 2026-09-02): التدقيق الصوتي
يمرّ بعملية whisper واحدة على خادمٍ واحد (~10 دقائق للفهرس بالعيّنة الممثِّلة،
~35 بالمطبَّقة)، فهو **العنق**. والبنيوي ثوانٍ لكل فهرس ويتوازى هنا بلا حدّ —
فكل فهرسٍ يرفضه بنيوياً هو **عشر دقائق من عنق الزجاجة وُفِّرت**. وقد أثبت
جدواه ليلتَه: التقط عطب «لا أثر صقل» الذي أقلقنا، بلا صوتٍ ولا خادم.

الاستعمال:
    python tools/ci_fleet/struct_triage.py                 # الاثنان
    python tools/ci_fleet/struct_triage.py --prefix timings-staging/
    python tools/ci_fleet/struct_triage.py --jobs 6 --json out.json
"""
import argparse
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

try:  # طرفية ويندوز الافتراضية cp1256 لا تحتمل الرسم ولا العربية معاً
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RUN = os.path.join(ROOT, "tools", "index_qa", "run.py")
CREDS = os.path.join(ROOT, "secure", "r2_credentials.json")


def keys(prefixes):
    import boto3
    c = json.load(open(CREDS))
    s3 = boto3.client("s3", endpoint_url=c["endpoint"],
                      aws_access_key_id=c["accessKeyId"],
                      aws_secret_access_key=c["secretAccessKey"], region_name="auto")
    out = []
    for p in prefixes:
        for page in s3.get_paginator("list_objects_v2").paginate(Bucket=c["bucket"], Prefix=p):
            for o in page.get("Contents", []):
                if o["Key"].endswith(".jz"):
                    out.append((o["Key"], o["LastModified"]))
    # ⛔ الترتيب `LastModified` تصاعدياً — نفس ترتيب المدقّقين الصوتيين
    #    (اتفاق 7e)، فلا يختلف ترتيبان بين مرحلتين من الطابور نفسه.
    out.sort(key=lambda x: x[1])
    return [k for k, _ in out]


def classify(d):
    """تفريقٌ ثلاثي (قرار github-f4، 2026-09-02) — ولا يُختزل إلى «مرفوض».

    ⛔ سببه قياسٌ لا رأي: حقل `refineVersion` **أُضيف يوم 2026-09-02** في
    `866cfb7`. فكلّ فهرسٍ أُنتج قبله يفتقده **بحكم تاريخه لا بعطبٍ فيه**،
    وعدُّه «جيلاً أول» حكمٌ يوجب إعادة إنتاج، بينما الصواب أنه **غير مصنَّف**
    وحالُه توجب القياس. والخلط بينهما رفض أربعين فهرساً بلا بيّنة وأفرغ طابور
    التدقيق الصوتي من العمل — وهو خطأ وقعتُ فيه أنا في أول تشغيل.

    - **غير مصنَّف:** لا حقل أصلاً ⇒ أولوية دنيا (وكلها ستُعاد بالوصفة الجديدة
      على كل حال، فلا يُنفق عليها صوتٌ إلا إن فرغ الطابور).
    - **مرفوض قطعاً:** الحقل موجودٌ ويقول `none`/`medTargeted=0` **مع وجود
      MED** ⇒ الصقل لم يعمل، والوسم يشهد على نفسه.
    - **مصنَّف:** وسمٌ سليم ⇒ أولوية عادية.
    """
    has = "refineVersion" in d
    mt = d.get("medTargeted", 0) or 0
    med = sum(1 for e in d.get("entries", []) if e.get("confBand") == "MED")
    if not has:
        return "غير مصنَّف", "لا وسم جيل (أُنتج قبل 866cfb7) — أولوية دنيا"
    if mt == 0 and med > 0:
        return "مرفوض", f"الصقل لم يعمل: medTargeted=0 مع MED={med}"
    return "مصنَّف", f"medTargeted={mt} · refineVersion={d.get('refineVersion')}"


def header(key):
    """ترويسة الفهرس من R2 — تنزيلٌ صغير واحد لا يكرّر ما تنزّله الأداة."""
    import gzip
    import io as _io

    import boto3
    c = json.load(open(CREDS))
    s3 = boto3.client("s3", endpoint_url=c["endpoint"],
                      aws_access_key_id=c["accessKeyId"],
                      aws_secret_access_key=c["secretAccessKey"], region_name="auto")
    body = s3.get_object(Bucket=c["bucket"], Key=key)["Body"].read()
    return json.load(gzip.open(_io.BytesIO(body), "rt", encoding="utf-8"))


def judge(key):
    r = subprocess.run([sys.executable, RUN, key, "--struct-only"],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", cwd=ROOT,
                       env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    out = (r.stdout or "") + (r.stderr or "")
    verdict = "مجهول"
    for line in out.splitlines():
        if "⇒ الحكم:" in line:
            verdict = line.split("⇒ الحكم:", 1)[1].strip()
    try:
        cls, why = classify(header(key))
    except Exception as ex:
        cls, why = "مجهول", f"تعذّرت قراءة الترويسة: {ex}"
    return {"key": key, "verdict": verdict, "class": cls, "why": why,
            "rc": r.returncode, "out": out}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prefix", action="append", default=None)
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--json", default=None)
    a = ap.parse_args()
    prefixes = a.prefix or ["timings/", "timings-staging/"]

    ks = keys(prefixes)
    print(f"مفاتيح للفحص البنيوي: {len(ks)} · توازٍ {a.jobs}", flush=True)
    with ThreadPoolExecutor(max_workers=a.jobs) as ex:
        results = list(ex.map(judge, ks))

    # ⛔ التصنيف لا يقبل شيئاً: «ناجٍ» تعني «لم يُرفض بنيوياً» فيستحق وقت
    #    الخادم الصوتي — لا تعني «سليم». القبول للصوت وحده (7e/7d).
    # ⛔ ثلاثة أصناف لا صنفان (قرار github-f4): «غير مصنَّف» ليس «مرفوضاً».
    rejected     = [r for r in results if r["class"] == "مرفوض"]
    unclassified = [r for r in results if r["class"] == "غير مصنَّف"]
    ready        = [r for r in results if r["class"] not in ("مرفوض", "غير مصنَّف")]
    print("")
    print("──────── حصيلة الترشيح البنيوي ────────")
    print(f"مرفوض قطعاً: {len(rejected)} · غير مصنَّف (أولوية دنيا): "
          f"{len(unclassified)} · مصنَّف (أولوية عادية): {len(ready)}")
    for r in rejected:
        print(f"  🔴 {r['key']}")
        print(f"     {r['why']}")
    if ready:
        print("")
        print("  ✅ طابور الصوت — أولوية عادية (‏LastModified تصاعدياً):")
        for r in ready:
            print(f"     {r['key']}  ·  {r['why']}")
    if unclassified:
        print("")
        print(f"  ⏳ أولوية دنيا — {len(unclassified)} بلا وسم جيل (أُنتجت قبل "
              "866cfb7). ⛔ لا يُنفق عليها صوتٌ إلا إن فرغ الطابور:")
        for r in unclassified:
            print(f"     {r['key']}")
    print("")
    print(f"⏱ وُفِّر من العنق الصوتي ≈ {len(rejected) * 10} دقيقة "
          f"({len(rejected)} مرفوضاً قطعاً × ~10د). ⛔ وغير المصنَّف لا يُحتسب "
          "توفيراً: أُجِّل ولم يُرفض.")
    if a.json:
        json.dump(results, open(a.json, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        print(f"التقرير الخام: {a.json}")


if __name__ == "__main__":
    main()
