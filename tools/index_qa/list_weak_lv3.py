#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""جردُ الآيات المقبولة بشاهد large-v3 للمرساة الضعيفة (‏heard-weak-lv3-1) — قارئٌ محض لا يكتب شيئاً.

    python tools/index_qa/list_weak_lv3.py [--json out.json] [--live-only]

يقرأ كلَّ `state-heard/*.json` من الدلو، ويسرد كلَّ آيةٍ في `weak[س].weakWitnessLargeV3`، ويبيّن أيّها في **فهرسٍ منشورٍ
حيّ**: بصمةُ الحالة (‏`sha256` = بصمةُ المرشّح الذي حُكم عليه) = بصمةُ `timings/<riw>/<id>.jz` الآن. فإن ظهر بلاغٌ عن آيةٍ
قُبلت بهذا المسار عُرف موضعُها وشاهداها (‏`witness` و`witnessL` في الحالة نفسِها) فيُعاد فحصُها.
⛔ `state-heard/` أثرٌ دائم: لا يحذفه تنظيفٌ آليّ (‏الحذفُ في المستودع مقصورٌ على `claims/` و`tmp/ui_walk/` و`tmp/e2e/`).

عبر قناة الأوامر: {"action":"tool","tool":"index_qa/list_weak_lv3.py","args":[]}
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                 # noqa: BLE001
        pass

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
PREFIX = "state-heard/"
LV3_KEY = "weakWitnessLargeV3"          # = heard_gate.LV3_KEY (‏يتحقّق منه الاختبار)


def published_key(src: str) -> str | None:
    """`timings-staging/<riw>/<id>.<sha8>.jz` ⇐ `timings/<riw>/<id>.jz` (‏كما يشتقّه heard_gate.yml)؛ وغيرُ ذلك None."""
    parts = str(src or "").split("/")
    if len(parts) != 3 or parts[0] != "timings-staging" or not parts[2]:
        return None
    return f"timings/{parts[1]}/{parts[2].split('.')[0]}.jz"


def collect(states, live_sha):
    """states: [(مفتاح الحالة، المحتوى)] · live_sha(مفتاح المنشور) ⇐ البصمة أو None.
    يُرجع صفّاً لكلّ آيةٍ مقبولةٍ بـlarge-v3: {state, src, sha256, published, live, riwaya, surah, ayah, run, detail}."""
    rows, cache = [], {}
    for key, rep in states:
        if not isinstance(rep, dict):
            continue
        src, sha = rep.get("src"), rep.get("sha256")
        pub = published_key(src)
        for s, ev in sorted((rep.get("weak") or {}).items(), key=lambda x: int(x[0])):
            acc = (ev or {}).get(LV3_KEY) if isinstance(ev, dict) else None
            if not acc:
                continue
            if pub is not None and pub not in cache:
                try:
                    cache[pub] = live_sha(pub)
                except Exception:                     # noqa: BLE001  (‏غيابُ المنشور ⇒ ليس حيّاً)
                    cache[pub] = None
            live = bool(pub and sha and cache.get(pub) == sha)
            det = ((ev.get("largeV3") or {}).get("detail") or {}) if isinstance(ev.get("largeV3"), dict) else {}
            for a in acc:
                rows.append({"state": key, "src": src, "sha256": sha, "published": pub, "live": live,
                             "riwaya": (pub or "//").split("/")[1] or None, "surah": int(s), "ayah": int(a),
                             "run": rep.get("run"), "detail": str(det.get(str(a), ""))[:160]})
    return rows


def bucket_states(cl, bucket):
    for page in cl.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=PREFIX):
        for obj in page.get("Contents", []):
            try:
                yield obj["Key"], json.loads(cl.get_object(Bucket=bucket, Key=obj["Key"])["Body"].read())
            except Exception as ex:                   # noqa: BLE001
                print(f"⚠️ {obj['Key']}: تعذّرت قراءته ({type(ex).__name__})", file=sys.stderr)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--json", help="يكتب الصفوف JSON في هذا المسار")
    ap.add_argument("--live-only", action="store_true", help="المنشورُ الحيّ وحده")
    a = ap.parse_args(argv)
    import promote                                    # noqa: PLC0415
    cl, bucket = promote.s3()

    def live_sha(k):
        return hashlib.sha256(cl.get_object(Bucket=bucket, Key=k)["Body"].read()).hexdigest()

    rows = collect(bucket_states(cl, bucket), live_sha)
    if a.live_only:
        rows = [r for r in rows if r["live"]]
    n_live = sum(r["live"] for r in rows)
    print(f"آياتٌ قُبلت بشاهد large-v3: {len(rows)} · منها في منشورٍ حيّ: {n_live}")
    for r in rows:
        print(f"  {'✅ حيّ' if r['live'] else '· غيرُ حيّ'}  {r['published'] or r['src']}  {r['surah']}:{r['ayah']}"
              f"  (بصمة {str(r['sha256'])[:8]} · تشغيلة {r['run']} · {r['state']})")
    if a.json:
        Path(a.json).write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
