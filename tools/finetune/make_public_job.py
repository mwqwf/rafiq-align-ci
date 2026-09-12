#!/usr/bin/env python3
"""يبني work/job.json لعيّنة G1 بروابط **عامة** (الدلو مقروء للعموم) — بديل make_job.py الذي يوقّع بمفتاح المالك."""
import json, sys
PUB = "https://pub-2c2e1dcd92e84a2898820dd38d3e09e6.r2.dev"
s = json.load(open(sys.argv[1], encoding="utf-8"))
items = []
for it in s["items"]:
    src = it["source"]; job = {"id": it["id"]}
    if src["kind"] == "ayah_file":
        job["url"] = src["url"]
    else:
        job["url"] = f"{PUB}/{src['r2Key']}"
        job["startMs"], job["endMs"] = src["startMs"], src["endMs"]  # مرآة make_job.py: بلا حشو
    items.append(job)
json.dump({"items": items}, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False)
print(len(items), "items")
