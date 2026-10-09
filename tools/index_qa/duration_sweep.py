#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""مسحٌ رخيص لكلّ المنشور: مدّةُ الملفّ الصوتيّ الفعليّة مقابل نهاية آخر مدخل في الفهرس لكلّ سورة.

    python tools/index_qa/duration_sweep.py --out ops/out/duration-sweep.json [--keys k1,k2] [--budget-sec 1380]

قارئٌ محض (proofZ · 2026-10-09): الفهارس من العنوان العامّ، والصوتُ بـ`HEAD` ثمّ طلب مدى لأوّل 64ك.ب
(‏ترويسة ID3 وأوّل إطار ومعدّل البِتّ)، ولا يُنزَّل ملفٌّ ولا يُكتب في الدلو. المدّة المقدَّرة =
(الحجم − ID3) ÷ معدّل البِتّ، أو عدّ إطارات Xing إن وُجد. تقديرٌ لا حكم: الفرق الكبير (‏آخر مدخل
أقصر من الملفّ بأكثر من 20% و30ث) مرشّحٌ للكبس يُثبَّت بالخرائط المسموعة.
"""
import argparse, gzip, json, os, struct, sys, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PUBLIC = os.environ.get("R2_PUBLIC", "https://pub-2c2e1dcd92e84a2898820dd38d3e09e6.r2.dev")
UA = {"User-Agent": "Mozilla/5.0 (QuranRafiq tools)"}
ROOT = Path(__file__).resolve().parents[2]
BR = {1: [0, 32, 64, 96, 128, 160, 192, 224, 256, 288, 320, 352, 384, 416, 448],
      2: [0, 32, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 384],
      3: [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320]}
BR2 = {1: [0, 32, 48, 56, 64, 80, 96, 112, 128, 144, 160, 176, 192, 224, 256],
       2: [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160]}
SR = {3: [44100, 48000, 32000], 2: [22050, 24000, 16000], 0: [11025, 12000, 8000]}


def fetch(url, headers=None, method="GET", timeout=60):
    rq = urllib.request.Request(url, method=method, headers={**UA, **(headers or {})})
    return urllib.request.urlopen(rq, timeout=timeout)


def head_size(url):
    with fetch(url, method="HEAD") as r:
        n = r.headers.get("Content-Length")
        return int(n) if n else None


def first_frame(buf):
    """(‏id3، bitrate kbps، sample_rate، samples/frame، نصّ Xing أو None‏) من أوّل 64ك.ب."""
    i = 0
    if buf[:3] == b"ID3":
        i = 10 + ((buf[6] & 0x7F) << 21 | (buf[7] & 0x7F) << 14 | (buf[8] & 0x7F) << 7 | (buf[9] & 0x7F))
    for j in range(i, min(len(buf) - 4, i + 20000)):
        if buf[j] == 0xFF and (buf[j + 1] & 0xE0) == 0xE0:
            h = struct.unpack(">I", buf[j:j + 4])[0]
            ver, layer = (h >> 19) & 3, (h >> 17) & 3
            bri, sri = (h >> 12) & 15, (h >> 10) & 3
            if ver == 1 or layer != 1 or bri in (0, 15) or sri == 3:   # layer 3 فقط
                continue
            kbps = BR[3][bri] if ver == 3 else BR2[2][bri]
            sr = SR[ver][sri]
            spf = 1152 if ver == 3 else 576
            xing = None
            mono = (h >> 6) & 3 == 3
            side = (17 if mono else 32) if ver == 3 else (9 if mono else 17)
            crc = 2 if (h >> 16) & 1 == 0 else 0
            p = j + 4 + crc + side
            tag = buf[p:p + 4]
            if tag in (b"Xing", b"Info"):
                flags = struct.unpack(">I", buf[p + 4:p + 8])[0]
                if flags & 1:
                    xing = struct.unpack(">I", buf[p + 8:p + 12])[0]
            return i, kbps, sr, spf, xing
    return None


def est_duration(url):
    size = head_size(url)
    if not size:
        return None, "لا Content-Length"
    with fetch(url, headers={"Range": "bytes=0-65535"}) as r:
        buf = r.read()
    ff = first_frame(buf)
    if not ff:
        return None, "ليس mp3 قابلاً للقراءة"
    id3, kbps, sr, spf, xing = ff
    if xing:
        return xing * spf / sr, f"xing {kbps}k"
    return (size - id3) * 8 / (kbps * 1000), f"cbr {kbps}k"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--keys", default="")
    ap.add_argument("--budget-sec", type=int, default=1380)
    a = ap.parse_args()
    t0 = time.time()
    with fetch(f"{PUBLIC}/timings/manifest.json") as r:
        man = json.loads(r.read())
    keys = [f"timings/{x['riwaya']}/{x['reciterId']}.jz" for x in man["indexes"]]
    if a.keys:
        want = set(a.keys.split(","))
        keys = [k for k in keys if k in want]
    out = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "keys": {}}
    cache = {}

    def probe(url):
        if url not in cache:
            try:
                cache[url] = est_duration(url)
            except Exception as ex:                       # noqa: BLE001
                cache[url] = (None, f"{type(ex).__name__}")
        return cache[url]

    for key in keys:
        if time.time() - t0 > a.budget_sec:
            out["stoppedAt"] = key
            break
        with fetch(f"{PUBLIC}/{key}") as r:
            idx = json.loads(gzip.decompress(r.read()))
        per = {}
        for e in idx["entries"]:
            s = int(e["ayahId"].split(":")[0])
            d = per.setdefault(s, {"ref": e.get("fileRef"), "end": 0, "n": 0})
            d["end"] = max(d["end"], e.get("endMs") or 0)
            d["n"] += 1
        urls = sorted({d["ref"] for d in per.values() if d["ref"]})
        with ThreadPoolExecutor(max_workers=24) as pool:
            list(pool.map(probe, urls))
        rows = []
        for s, d in sorted(per.items()):
            dur, note = probe(d["ref"]) if d["ref"] else (None, "بلا رابط")
            row = {"s": s, "n": d["n"], "endMs": d["end"], "fileSec": round(dur, 1) if dur else None, "note": note}
            if dur:
                row["gapSec"] = round(dur - d["end"] / 1000, 1)
                row["ratio"] = round(dur * 1000 / d["end"], 3) if d["end"] else None
            rows.append(row)
        out["keys"][key] = rows
        flagged = [r for r in rows if r.get("ratio") and r["ratio"] > 1.2 and r["gapSec"] > 30]
        print(f"{key}: سور {len(rows)} · مرشّحة للكبس {len(flagged)} · {time.time() - t0:.0f}ث", flush=True)
    path = ROOT / a.out
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    print("كُتب", a.out)


if __name__ == "__main__":
    main()
