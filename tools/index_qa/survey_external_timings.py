#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""يجرد مصادر التوقيت الخارجية لقرّاء محدَّدين: mp3quran ayat_timing + مقارنة مدّة الملف.

    python tools/index_qa/survey_external_timings.py \
        --list tools/index_qa/mp3quran_reads.tsv \
        --only afs,deban,m_qari --surahs 16,40 --out ops/out/timing-survey.json

قارئٌ محض: لا يكتب في الدلو ولا يرقّي. الطلبات خفيفة (JSON وHEAD/64ك.ب).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
UA = {"User-Agent": "Mozilla/5.0 (QuranRafiq timing survey)"}
API = "https://www.mp3quran.net/api/v3/ayat_timing?surah={s}&read={r}"
BR_L3_V1 = [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320]
BR_L3_V2 = [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160]


def fetch(url, headers=None, method="GET", timeout=30):
    rq = urllib.request.Request(url, method=method, headers={**UA, **(headers or {})})
    return urllib.request.urlopen(rq, timeout=timeout)


def estimate_duration(url: str) -> dict:
    out = {"url": url}
    try:
        with fetch(url, {"Range": "bytes=0-65535"}, timeout=25) as r:
            buf = r.read()
            cr = r.headers.get("Content-Range") or ""
            if "/" in cr:
                try:
                    out["size"] = int(cr.split("/")[-1])
                except ValueError:
                    pass
            out["etag"] = (r.headers.get("ETag") or "").strip('"')
        off = 0
        if buf[:3] == b"ID3" and len(buf) >= 10:
            off = 10 + ((buf[6] & 0x7F) << 21 | (buf[7] & 0x7F) << 14 |
                        (buf[8] & 0x7F) << 7 | (buf[9] & 0x7F))
        i = off
        while i + 4 < len(buf) and not (buf[i] == 0xFF and (buf[i + 1] & 0xE0) == 0xE0):
            i += 1
        if i + 4 >= len(buf):
            out["error"] = "no_frame"
            return out
        b1, b2 = buf[i + 1], buf[i + 2]
        ver = {3: 1, 2: 2, 0: 2.5}.get((b1 >> 3) & 3)
        layer = 4 - ((b1 >> 1) & 3)
        br_i = (b2 >> 4) & 0xF
        if ver == 1 and layer == 3 and 0 < br_i < len(BR_L3_V1):
            br = BR_L3_V1[br_i]
        elif ver != 1 and layer == 3 and 0 < br_i < len(BR_L3_V2):
            br = BR_L3_V2[br_i]
        else:
            out["error"] = f"hdr ver={ver} layer={layer}"
            return out
        out["bitrate_kbps"] = br
        size = out.get("size") or 0
        if br and size:
            out["file_sec"] = round((size - off) * 8 / (br * 1000), 1)
        return out
    except Exception as e:  # noqa: BLE001
        out["error"] = str(e)[:200]
        return out


def timing_span(read: int, surah: int) -> dict:
    url = API.format(s=surah, r=read)
    try:
        with fetch(url, timeout=25) as r:
            rows = json.load(r)
        if not isinstance(rows, list) or not rows:
            return {"n": 0, "empty": True}
        body = [x for x in rows if isinstance(x.get("ayah"), int) and x["ayah"] >= 1]
        body.sort(key=lambda x: x["ayah"])
        st, en = body[0]["start_time"], body[-1]["end_time"]
        return {
            "n": len(body),
            "first_ayah": body[0]["ayah"],
            "start_ms": st,
            "end_ms": en,
            "span_sec": round((en - st) / 1000, 1),
            "end_sec": round(en / 1000, 1),
            "has_ayah0": any(x.get("ayah") == 0 for x in rows),
        }
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)[:200]}


def load_tsv(path: Path, only: set[str] | None):
    rows = []
    for ln in path.read_text(encoding="utf-8").splitlines():
        if not ln.strip() or ln.startswith("#"):
            continue
        parts = ln.split("\t")
        if len(parts) < 4:
            continue
        rid, riw, read, url = parts[0], parts[1], parts[2], parts[3]
        if only and rid not in only:
            continue
        rows.append({"rid": rid, "riw": riw, "read": int(read), "url": url})
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", default="tools/index_qa/mp3quran_reads.tsv")
    ap.add_argument("--only", default="", help="معرّفات بفواصل")
    ap.add_argument("--surahs", default="1", help="سور بفواصل")
    ap.add_argument("--out", default="")
    args = ap.parse_args(argv)
    only = {x for x in args.only.replace(",", " ").split() if x}
    surahs = [int(x) for x in args.surahs.replace(",", " ").split() if x]
    rows = load_tsv(Path(args.list), only or None)
    out = []
    for row in rows:
        for s in surahs:
            url = row["url"].replace("{s:03d}", f"{s:03d}").replace("{surah:03d}", f"{s:03d}")
            span = timing_span(row["read"], s)
            dur = estimate_duration(url)
            rec = {
                "reciter": row["rid"],
                "riwaya": row["riw"],
                "read": row["read"],
                "surah": s,
                "timing": span,
                "audio": {k: dur.get(k) for k in ("file_sec", "size", "etag", "bitrate_kbps", "error")},
            }
            if dur.get("file_sec") and span.get("end_sec"):
                rec["ours_vs_timing_end"] = round(dur["file_sec"] / max(1e-3, span["end_sec"]), 3)
            if dur.get("file_sec") and span.get("span_sec"):
                rec["ours_vs_span"] = round(dur["file_sec"] / max(1e-3, span["span_sec"]), 3)
            if span.get("start_ms") and dur.get("file_sec"):
                rec["start_frac"] = round((span["start_ms"] / 1000) / max(1e-3, dur["file_sec"]), 3)
            out.append(rec)
            print(f"{row['rid']} s{s} read={row['read']} timing_n={span.get('n')} "
                  f"file={dur.get('file_sec')}s ratio={rec.get('ours_vs_timing_end')} "
                  f"start_frac={rec.get('start_frac')} err={span.get('error') or dur.get('error') or ''}",
                  flush=True)
            time.sleep(0.05)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
