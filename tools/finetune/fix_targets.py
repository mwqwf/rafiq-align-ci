#!/usr/bin/env python3
"""يعيد كتابة target_text في manifest.jsonl بعد تصحيح ٞ (ضمّتان لا فتحتان) — بلا إعادة قصّ الصوت."""
import json, sys
sys.path.insert(0, "/content")
from prep import target_text
p = "/content/data/manifest.jsonl"
rows = [json.loads(l) for l in open(p, encoding="utf-8")]
n = 0
for r in rows:
    t = target_text(r["ref_text"])
    if t != r["target_text"]:
        n += 1
        r["target_text"] = t
with open(p, "w", encoding="utf-8") as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
print("rewritten", n, "of", len(rows))
