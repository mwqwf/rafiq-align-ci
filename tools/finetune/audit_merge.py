#!/usr/bin/env python3
"""🧩 دمجُ شرائح تدقيق العناوين (‏label_audit.py --shard i/k) في ملفٍّ واحدٍ للجزء — بلا تكرارٍ بالمفتاح، مع ملخّصٍ محسوبٍ من جديد.

    python tools/finetune/audit_merge.py g0.audit.json g0.s0.audit.json g0.s1.audit.json …
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from label_audit import summarize

def main():
    out, srcs = sys.argv[1], sys.argv[2:]
    items, partial = {}, False
    for f in srcs:
        if not os.path.exists(f): print(f"⚠️ غائب: {f}"); continue
        d = json.load(open(f, encoding="utf-8"))
        partial = partial or bool(d.get("partial"))
        for it in d.get("items", []):
            k = it.get("key") or it["id"]
            items[k] = it
        print(f"  {os.path.basename(f)}: {len(d.get('items', []))} {'(ناقص)' if d.get('partial') else ''}")
    res = list(items.values())
    if not res: sys.exit("⛔ لا بنودَ للدمج")
    body = {"summary": summarize(res), "worst": sorted(res, key=lambda r: r["match"])[:25], "items": res, "shards": len(srcs)}
    if partial: body["partial"] = True
    json.dump(body, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    s = body["summary"]
    print(f"✅ {out}: {s['n']} مقطعاً · متوسّط {s['mean']:.3f} · دون 0.85: {s['below_0.85']*100:.1f}٪ · دون 0.9: {s['below_0.9']*100:.1f}٪ · بالرواية {s['dropped_at_0.85_by_riwaya']}")

if __name__ == "__main__":
    main()
