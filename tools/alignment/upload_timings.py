# -*- coding: utf-8 -*-
"""رفع فهرس توقيتات مكتمل إلى R2 بمساره القانوني timings/{riwaya}/{reciterId}.jz.

python upload_timings.py --index work/timings_qalun_husary_qalun.jz
يقرأ الميتاداتا من الفهرس نفسه فيشتق المفتاح، ويتحقق بعد الرفع بالقراءة العامة.
"""
import argparse
import json
import os
import urllib.request

import boto3

from common import ROOT, read_jz

SECURE = os.path.join(ROOT, "secure", "r2_credentials.json")

# ⛔ درس 2026-09-02: كانت كل الحُرّاس في `run_fleet.py` **مُستدعي** هذا الملف،
# وهذا الملف نفسه بلا حارسٍ واحد. فأيُّ استدعاءٍ مباشر — جولة رفع يدوية،
# سكربتٌ عابر، أو حتى التلميح في تحذير `fleet_status.py` — يتجاوز الحُرّاس
# كلها ويكتب في مسار الإنتاج. **الحارس يكون عند عنق الزجاجة لا عند أحد
# الداخلين إليه**؛ حارسٌ في المُستدعي يحمي مساراً واحداً ويترك الباب مفتوحاً.
# ولا راية `--force` هنا عمداً: بابٌ للطوارئ يصير الباب المعتاد.
def _guards(index_path, riwaya, reciter_id):
    """يرجع None عند السماح أو نصّ المنع. يفشل مغلقاً عند أي تعذّر."""
    import subprocess
    import sys
    guard = os.path.join(ROOT, "tools", "cloud", "coverage_guard.py")
    if os.path.exists(guard):
        r = subprocess.run([sys.executable, guard, "--index", index_path],
                           capture_output=True, text=True)
        if r.returncode != 0:
            return f"تغطية: {(r.stdout or r.stderr).strip()}"
    else:
        return f"حارس التغطية مفقود ({guard}) — لا رفع"
    frozen = os.path.join(ROOT, "tools", "index_qa", "frozen.txt")
    key = f"timings/{riwaya}/{reciter_id}.jz"
    try:
        with open(frozen, encoding="utf-8") as f:
            for line in f:
                line = line.split("#", 1)[0].strip()
                parts = line.split()
                if len(parts) >= 2 and parts[0] == key:
                    return f"FROZEN {key} — مجمّد، لا يُكتب فوقه"
    except FileNotFoundError:
        return f"قائمة التجميد غائبة ({frozen}) — لا رفع حتى تصل"
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", required=True)
    args = ap.parse_args()
    ti = read_jz(args.index)
    key = f"timings/{ti['riwaya']}/{ti['reciterId']}.jz"
    # ⛔ عقد الوجهات (github-f4): كل كاتبٍ يكتب في وجهته وحدها فلا يبقى باب.
    # هذا الرافع للإنتاج `timings/` فقط؛ وstaging لسكربت 3a وحده.
    if not key.startswith("timings/") or key.startswith("timings-"):
        print(f"⛔ بادئة غير مسموحة: {key} — هذا الرافع لا يكتب إلا في timings/", flush=True)
        raise SystemExit(4)
    blocked = _guards(args.index, ti["riwaya"], ti["reciterId"])
    if blocked:
        print(f"⛔ رُفض الرفع — {blocked}", flush=True)
        raise SystemExit(3)
    c = json.load(open(SECURE))
    s3 = boto3.client("s3", endpoint_url=c["endpoint"],
                      aws_access_key_id=c["accessKeyId"],
                      aws_secret_access_key=c["secretAccessKey"], region_name="auto")
    s3.upload_file(args.index, c["bucket"], key,
                   ExtraArgs={"ContentType": "application/gzip"})
    size = os.path.getsize(args.index)
    print(f"رُفع {key} ({size//1024}ك.ب، {len(ti['entries'])} آية)")

    # تحديث manifest الفهارس (اتفاق مع مستهلك التطبيق 2026-08-31): يغني عن الجس
    import time
    mkey = "timings/manifest.json"
    try:
        cur = json.loads(s3.get_object(Bucket=c["bucket"], Key=mkey)["Body"].read())
    except Exception:
        cur = {"version": 1, "indexes": []}
    row = {"riwaya": ti["riwaya"], "reciterId": ti["reciterId"],
           "entries": len(ti["entries"]), "updatedTs": int(time.time() * 1000)}
    cur["indexes"] = [x for x in cur["indexes"]
                      if not (x["riwaya"] == row["riwaya"] and x["reciterId"] == row["reciterId"])]
    cur["indexes"].append(row)
    cur["updated"] = row["updatedTs"]
    s3.put_object(Bucket=c["bucket"], Key=mkey,
                  Body=json.dumps(cur, ensure_ascii=False).encode(),
                  ContentType="application/json")
    print(f"مانيفست محدث: {len(cur['indexes'])} فهرساً")
    pub = c.get("publicBase") or "https://pub-2c2e1dcd92e84a2898820dd38d3e09e6.r2.dev"
    if pub:
        # r2.dev يحجب وكيل بايثون الافتراضي (403) — وكيل متصفح يلزم
        req = urllib.request.Request(f"{pub.rstrip('/')}/{key}",
                                     headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req) as r:
            ok = len(r.read()) == size
        print("تحقق القراءة العامة:", "✅" if ok else "❌ حجم مختلف")


if __name__ == "__main__":
    main()
