#!/usr/bin/env python3
"""⬇️ جلبُ صوتِ الصفوفِ الصالحةِ وحدَها من مجموعة المتعلّمين ([[D-723]]).

⛔ **لا تُنزَّل المجموعةُ كلُّها**: 1042 مقطعاً × 343 ك.ب ≈ 350 م.ب، والمفيدُ منها **247** صفّاً
(‏مثبَّتٌ بنصّه ومراجَعٌ بشريّاً) ≈ 85 م.ب. قاعدةُ «الشبكةُ موردٌ شحيح» تُطبَّق بالاختيار لا بالأمل.

- ملفٌّ ملفاً باستئناف: الموجودُ كاملاً لا يُعاد، والانقطاعُ يكلّف مقطعاً واحداً.
- المصدرُ `metadata.jsonl` من المستودع نفسِه (فيه `file_name`)، والمختارُ من `learner_check.json`.

    python learner_fetch.py --check work/learner_check.json --meta work/ds_metadata.jsonl --out work/learner_wav
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request

BASE = "https://huggingface.co/datasets/sobolev210/quran-recitation-errors/resolve/main/"
UA = {"User-Agent": "Mozilla/5.0 (QuranRafiq learner-fetch)"}

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:                        # noqa: BLE001
        pass


def get(url: str, dst: str, tries: int = 6) -> int:
    if os.path.exists(dst) and os.path.getsize(dst) > 1024:
        return os.path.getsize(dst)
    last = None
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
                data = r.read()
            if len(data) < 1024:
                raise RuntimeError(f"ملفٌّ قصيرٌ ({len(data)} بايتاً)")
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with open(dst, "wb") as f:
                f.write(data)
            return len(data)
        except Exception as e:                # noqa: BLE001
            last = e
            time.sleep(min(2 * (i + 1), 12))
    print(f"  ⛔ {os.path.basename(dst)}: {last}", flush=True)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", default="tools/tasmi_phoneme/work/learner_check.json")
    ap.add_argument("--meta", default="tools/tasmi_phoneme/work/ds_metadata.jsonl")
    ap.add_argument("--rows", default="tools/tasmi_phoneme/work/learner_rows.jsonl")
    ap.add_argument("--out", default="tools/tasmi_phoneme/work/learner_wav")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()

    # 🗂️ `recording_id` قد يتكرّر لعدّة آياتٍ ⇒ المفتاحُ (id, surah, ayah) كما في `metadata.jsonl`
    paths = {}
    for line in open(a.meta, encoding="utf-8"):
        d = json.loads(line)
        paths.setdefault((d["recording_id"], str(d.get("surah")), str(d.get("ayah"))), d["file_name"])

    chk = json.load(open(a.check, encoding="utf-8"))
    want = {}
    for u in chk["usable"]:
        s, ay = u["ref"].split(":")
        want[(u["recording_id"], s, ay)] = {"kind": "موجب", **u}
    # والسوالبُ الموثوقة: مثبَّتٌ ومراجَعٌ بلا خطأ — تُلتقط من الصفوف مباشرةً
    usable_ids = set(want)
    for line in open(a.rows, encoding="utf-8"):
        x = json.loads(line)
        rid = (x.get("reviewer_id") or "").strip()
        if rid in ("", "not reviewed"):
            continue
        if {w: v for w, v in (x.get("errors") or {}).items() if v}:
            continue
        k = (x.get("recording_id"), str(x.get("surah")), str(x.get("ayah")))
        if k in usable_ids or k not in paths:
            continue
        want[k] = {"kind": "سالب", "recording_id": k[0], "ref": f"{k[1]}:{k[2]}",
                   "riwaya": x.get("riwayah"), "reviewer": rid}

    items = list(want.items())
    if a.limit:
        items = items[:a.limit]
    print(f"مطلوبٌ {len(items)} مقطعاً (موجبٌ {sum(1 for _k, v in items if v['kind']=='موجب')} "
          f"· سالبٌ {sum(1 for _k, v in items if v['kind']=='سالب')})", flush=True)

    got, miss, bytes_ = [], 0, 0
    t0 = time.time()
    for n, (k, v) in enumerate(items, 1):
        fn = paths.get(k)
        if not fn:
            miss += 1
            continue
        dst = os.path.join(a.out, fn.replace("/", os.sep))
        size = get(BASE + fn, dst)
        if not size:
            miss += 1
            continue
        bytes_ += size
        got.append({**v, "wav": os.path.relpath(dst, a.out).replace(os.sep, "/")})
        if n % 10 == 0 or n == len(items):
            r = bytes_ / max(time.time() - t0, 1e-6) / 1024
            print(f"  {n}/{len(items)} · {bytes_/1024/1024:.0f} م.ب · {r:.0f} ك.ب/ث", flush=True)

    man = os.path.join(a.out, "manifest.json")
    json.dump({"dataset": "sobolev210/quran-recitation-errors", "license": "mit",
               "note": "صوتٌ للقياس المحليّ فقط — لا يُشحن",
               "fetched": len(got), "missing": miss, "items": got},
              open(man, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"✅ {len(got)} مقطعاً ({bytes_/1024/1024:.1f} م.ب) · مفقودٌ {miss} ⇒ {man}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
