# -*- coding: utf-8 -*-
"""سائقُ خطّ CTC السحابيّ (أمر المالك 2026-09-19: «انقل كلّ عملك إلى السحابة»).

يعمل في `ctc_driver.yml` مجدولاً، ويحلّ محلّ ما كان يجري على جهاز المالك:
  ١. كلُّ فهرسٍ في المسرح محرّكُه `ctc-seg-1` ولم يُحكم عليه ⇒ يُطلق عليه
     `openers.yml` + `audio_qa.yml` بأربعة ملوح (k1…k4) — مرّةً واحدة (وسمٌ في state/).
  ٢. ما اكتملت ملوحُه الأربعة كلُّها «مقبول» ⇒ `promote.py --only <key> --yes`
     (الحرّاسُ كلّهم داخل promote.py كما هي؛ لا يُخفَّض شيء).
  ٣. إن رُقّي شيء ⇒ `certify_catalog.py --yes` فيصل إلى التطبيق.
⛔ لا يُطلق محاذاةً ولا يكتب في timings/ إلا عبر promote.py.
"""
import gzip
import json
import os
import subprocess
import sys
from pathlib import Path

import boto3

ROOT = Path(__file__).resolve().parents[2]
REPO = os.environ.get("GITHUB_REPOSITORY", "mwqwf/rafiq-align-ci")
SALTS = ("k1", "k2", "k3", "k4")
SINCE = "2026-09-19"          # فهارسُ CTC كلُّها بعد هذا اليوم

c = json.load(open(ROOT / "secure" / "r2_credentials.json"))
s3 = boto3.client("s3", endpoint_url=c["endpoint"], aws_access_key_id=c["accessKeyId"],
                  aws_secret_access_key=c["secretAccessKey"], region_name="auto")
B = c["bucket"]


def ls(prefix):
    out = []
    for p in s3.get_paginator("list_objects_v2").paginate(Bucket=B, Prefix=prefix):
        out += p.get("Contents", [])
    return out


def get(key):
    return s3.get_object(Bucket=B, Key=key)["Body"].read()


def sh(*a):
    print("$", " ".join(a), flush=True)
    return subprocess.run(a, cwd=ROOT).returncode


state = {o["Key"] for o in ls("state/timings-staging_")}
frozen = get("timings/frozen.txt").decode("utf-8")
promoted = 0
# الأحدثُ لكلّ قارئ وحدَه: بصمةٌ قديمةٌ ناقصةٌ لا تُبوَّب ولا تُرقّى فوق خليفتها.
latest = {}
for o in ls("timings-staging/"):
    k = o["Key"]
    if not k.endswith(".jz") or o["LastModified"].isoformat() < SINCE:
        continue
    rid = k.split("/")[-1].split(".")[0]
    if rid not in latest or o["LastModified"] > latest[rid]["LastModified"]:
        latest[rid] = o
runs = json.loads(subprocess.run(
    ["gh", "run", "list", "-R", REPO, "-w", "ctc_align.yml", "-L", "60",
     "--json", "displayTitle,status"], capture_output=True, text=True).stdout or "[]")
busy = {r["displayTitle"].split()[1].split("/")[0] for r in runs if r["status"] != "completed"}
for rid, o in latest.items():
    k = o["Key"]
    if rid in busy:                              # فهرسةٌ أحدثُ جارية: لا بوابةَ ولا ترقيةَ لما قبلها
        print(f"⏳ {k}: فهرسةٌ أحدث جارية لـ{rid}")
        continue
    sha8 = k.rsplit(".", 2)[-2]
    if sha8 in frozen:                          # رُقّي سلفاً
        continue
    try:
        hdr = json.loads(gzip.decompress(get(k)))
    except Exception as e:                      # noqa: BLE001
        print(f"⚠️ {k}: {e}")
        continue
    if hdr.get("engineVersion") != "ctc-seg-1":
        continue
    flat = "state/" + k.replace("/", "_")
    salts = [f"{flat}.audio-{s}.json" for s in SALTS]
    if all(x in state for x in salts):
        verdicts = [json.loads(get(x)).get("verdict") for x in salts]
        if all(v == "مقبول" for v in verdicts) and f"{flat}.openers.json" in state:
            print(f"▶ ترقية {k}")
            if sh(sys.executable, "tools/index_qa/promote.py", "--only", k, "--yes") == 0:
                promoted += 1
        else:
            print(f"⛔ {k}: أحكام {verdicts} — لا ترقية")
        continue
    mark = f"{flat}.ctc-gate-dispatched"
    if mark in state or any(x in state for x in salts):
        print(f"⏳ {k}: البوابة جارية")
        continue
    print(f"▶ بوابة {k}")
    sh("gh", "workflow", "run", "openers.yml", "-R", REPO, "-f", f"only={k}", "-f", "limit=1")
    for s in SALTS:
        sh("gh", "workflow", "run", "audio_qa.yml", "-R", REPO, "-f", f"only={k}", "-f", f"seed_salt={s}")
    s3.put_object(Bucket=B, Key=mark, Body=b"1")

if promoted:
    sh(sys.executable, "tools/index_qa/certify_catalog.py", "--yes")
print(f"رُقّي في هذه الدورة: {promoted}")
