#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""يجمع شرائح `source_drift_sweep` في تقريرٍ واحد ويفرز الجديد عمّا عُرف — قارئ محض لا يحجب شيئاً.

    python tools/index_qa/source_drift_report.py --known ops/source_drift_known.json.gz \\
        --out report.md shard0.json shard1.json …

«الجديد» = صفٌّ موسومٌ مفتاحُه riw/reciter/surah غيرُ معروفٍ أو ETagه (أوّل 12 حرفاً) غيرُ المعروف.
والموسومُ المعروفُ بالETag نفسه لا يُنبَّه عليه ثانيةً (يمنع ضجيج الإنذارات الكاذبة المزمنة: تقدير VBR ورفعٌ جماعيّ).
يطبع `NEW=<عدد>` في آخر سطر ويكتب Markdown عربياً؛ والسير يفتح بنداً (issue) إن كان العدد > 0.
"""
from __future__ import annotations

import argparse
import gzip
import json
import sys
from pathlib import Path


def load_known(path):
    p = Path(path)
    if not p.exists():
        return {}
    raw = p.read_bytes()
    if p.suffix == ".gz":
        raw = gzip.decompress(raw)
    return json.loads(raw.decode("utf-8")).get("known", {})


def split_new(rows, known):
    new, old = [], 0
    for r in rows:
        key = f"{r['riwaya']}/{r['reciter']}/{r['surah']}"
        if known.get(key) == (r.get("etag") or "")[:12] and key in known:
            old += 1
        else:
            new.append(r)
    return sorted(new, key=lambda r: (-r.get("magnitudeSec", 0), r["reciter"], r["surah"])), old


def render(new, old, shards, errors):
    L = [f"# مسح تبدّل المصدر الأسبوعيّ", "",
         f"- شرائح مقروءة: {shards} · موسومٌ جديد: **{len(new)}** · موسومٌ معروفٌ بلا تغيّر: {old}",
         "- هذا تقريرٌ فقط: لا حجبَ ولا ترقية آليّاً. القرارُ للقائد بعد قياس الإزاحة بـ`ctc_heard_probe build=true`.", ""]
    if new:
        L += ["| القارئ | السورة | العلامات | الفرق (ث) | ملفّ (ث) | آخر endMs (ث) | Last-Modified |", "|---|---|---|---|---|---|---|"]
        for r in new[:80]:
            L.append(f"| {r['riwaya']}/{r['reciter']} | {r['surah']} | {', '.join(r['flags'])} | {r.get('magnitudeSec')} | "
                     f"{r.get('fileSec')} | {r.get('lastEndSec')} | {r.get('lastModified')} |")
        if len(new) > 80:
            L.append(f"\n… و{len(new) - 80} صفّاً آخر في أثر الشرائح.")
    if errors:
        L += ["", "## أخطاء المسح", *[f"- {e}" for e in errors[:30]]]
    return "\n".join(L) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--known", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("shards", nargs="+")
    a = ap.parse_args(argv)
    rows, errors, n = [], [], 0
    for s in a.shards:
        d = json.loads(Path(s).read_text(encoding="utf-8"))
        rows += d.get("flagged", []); errors += d.get("errors", []); n += 1
    new, old = split_new(rows, load_known(a.known))
    Path(a.out).write_text(render(new, old, n, errors), encoding="utf-8")
    print(f"NEW={len(new)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
