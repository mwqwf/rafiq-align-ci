#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""جدولُ انحراف بدء الآيات عن المسموع لكلّ فهرسٍ منشور — قارئٌ محض (e6 · 2026-10-18).

    python tools/index_qa/heard_sweep_table.py

لكلّ خريطةٍ في state-heard/ على فهرسٍ منشور: السورُ المنحرفة · الآياتُ المنحرفة (status=dev)
· ما فوق 1.5ث · ما فوق 5ث · أقصى انحراف · السورُ التي خريطتها على صوتٍ ≠ صوتِ الفهرس (لا يُحكم عليها)
· أهي خريطةُ بصمةِ الحيّ أم متقادمة. يطبع أسطر TSV تبدأ بـ«R».
لا يكتب شيئاً ولا يمسّ حارساً.
"""
from __future__ import annotations
import gzip, hashlib, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import heard_gate as H  # noqa: E402
from run import s3  # noqa: E402


def row_for(key, idx, live_sha, rep):
    cs = H.by_surah(idx["entries"])
    shas = idx.get("audioSha256")
    present = sorted(cs)
    sha_of = ({s: shas[s - 1] for s in present} if isinstance(shas, list) and len(shas) == 114 else
              dict(zip(present, shas)) if isinstance(shas, list) and len(shas) == len(present) else {})
    maps = {int(k): v for k, v in (rep.get("maps") or {}).items()}
    surahs = dev = g15 = g5 = 0
    worst = (0, "-")
    audio_ne = []
    for s in present:
        m = maps.get(s)
        if not m:
            continue
        if m.get("sha256") != sha_of.get(s):
            audio_ne.append(s); continue
        rows = H.surah_rows({a: v[0] for a, v in cs[s].items()}, m)
        d = [r for r in rows if r["status"] == "dev"]
        if d:
            surahs += 1
        dev += len(d)
        for r in rows:
            if r["devMs"] is None:
                continue
            a = abs(r["devMs"])
            if a > 1500: g15 += 1
            if a > 5000: g5 += 1
            if a > worst[0]: worst = (a, f"{s}:{r['ayah']}")
    live = "حيّ" if rep.get("sha256") == live_sha else f"متقادم({str(rep.get('sha256'))[:8]}≠{live_sha[:8]})"
    return (f"R\t{key}\t{live}\tخرائط={len(maps)}\tسور_منحرفة={surahs}\tآيات_dev={dev}"
            f"\tفوق1.5ث={g15}\tفوق5ث={g5}\tأقصى={worst[0] / 1000:.1f}ث@{worst[1]}"
            f"\tصوت≠={len(audio_ne)}{audio_ne if audio_ne else ''}")


def main():
    cl, b = s3()
    keys = []
    for page in cl.get_paginator("list_objects_v2").paginate(Bucket=b, Prefix=H.STATE_PREFIX):
        keys += [o["Key"] for o in page.get("Contents", []) if o["Key"].endswith(".json")]
    for sk in sorted(keys):
        try:
            rep = json.loads(cl.get_object(Bucket=b, Key=sk)["Body"].read())
            key = rep.get("src") or ""
            if not key.startswith("timings/"):
                continue
            body = cl.get_object(Bucket=b, Key=key)["Body"].read()
            print(row_for(key, json.loads(gzip.decompress(body)), hashlib.sha256(body).hexdigest(), rep), flush=True)
        except Exception as ex:  # noqa: BLE001
            print(f"E\t{sk}\t{type(ex).__name__}: {ex}")


if __name__ == "__main__":
    main()
