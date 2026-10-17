#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""جردُ «القصّ عند الترويسة» لكلّ المنشور — قارئٌ محض (e5 · 2026-10-17).

    python tools/index_qa/header_clip.py --out ops/out/header_clip.json [--keys k1,k2] [--workers 24]

العلّة: مدّةُ ترويسة mp3 تقصر عن الصوت الحقيقيّ بنحو 0.5% في ملفّات mp3quran الطويلة (‏لحوني س3: 4253.8 مقابل
4273.7ث)، وكانت المحاذاةُ تقصّ الصوتَ عندها فتنتهي آخر آيةٍ عند الترويسة. هذه الأداة، لكلّ سورة، تقدّر
المدّة الحقيقية من الحجم ومتوسّط طول الإطار في أوّل 256ك.ب (‏CBR مع الحشو)، وتقارنها بنهاية آخر آية endMs
وبمدّة الترويسة المقدَّرة، وتعلّم السورة إن كان **endMs عند الترويسة (±0.7ث) والصوتُ الحقيقيّ أطولَ بأكثر من 3ث**.
ثم، للمعلَّم، تقيس طاقة الصوت في الذيل (‏بين endMs والنهاية المقدَّرة) بـffmpeg على مدى بايتات الذيل وحده.
تقديرٌ لا حكم: لا يُنزَّل ملفّ كامل ولا يُكتب في الدلو.
"""
import argparse, gzip, json, os, struct, subprocess, sys, tempfile, time, urllib.request
from concurrent.futures import ThreadPoolExecutor

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PUBLIC = os.environ.get("R2_PUBLIC", "https://pub-2c2e1dcd92e84a2898820dd38d3e09e6.r2.dev")
UA = {"User-Agent": "Mozilla/5.0 (QuranRafiq tools)"}
BR3 = [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320]
BR2 = [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160]
SR = {3: [44100, 48000, 32000], 2: [22050, 24000, 16000], 0: [11025, 12000, 8000]}


def fetch(url, headers=None, method="GET", timeout=60):
    rq = urllib.request.Request(url, method=method, headers={**UA, **(headers or {})})
    return urllib.request.urlopen(rq, timeout=timeout)


def frames(buf):
    """(id3، قائمة (bytes، samples/إطار، sr، kbps)) لإطارات متتالية من buf."""
    i = 0
    if buf[:3] == b"ID3":
        i = 10 + ((buf[6] & 0x7F) << 21 | (buf[7] & 0x7F) << 14 | (buf[8] & 0x7F) << 7 | (buf[9] & 0x7F))
    out = []
    n = len(buf)
    j = i
    while j + 4 < n and len(out) < 4000:
        if buf[j] == 0xFF and (buf[j + 1] & 0xE0) == 0xE0:
            h = struct.unpack(">I", buf[j:j + 4])[0]
            ver, layer = (h >> 19) & 3, (h >> 17) & 3
            bri, sri, pad = (h >> 12) & 15, (h >> 10) & 3, (h >> 9) & 1
            if ver != 1 and layer == 1 and bri not in (0, 15) and sri != 3:
                kbps = BR3[bri] if ver == 3 else BR2[bri]
                sr = SR[ver][sri]
                spf = 1152 if ver == 3 else 576
                ln = int(spf // 8 * kbps * 1000 / sr) + pad
                out.append((ln, spf, sr, kbps))
                j += ln
                continue
        j += 1
    return i, out


def est(url):
    with fetch(url, method="HEAD") as r:
        size = int(r.headers.get("Content-Length") or 0)
    if not size:
        return None
    with fetch(url, headers={"Range": "bytes=0-262143"}) as r:
        buf = r.read()
    id3, fr = frames(buf)
    if len(fr) < 50:
        return None
    kb = {f[3] for f in fr}
    avg = sum(f[0] for f in fr) / len(fr)
    spf, sr, kbps = fr[0][1], fr[0][2], fr[0][3]
    true = (size - id3) / avg * spf / sr
    hdr = (size - id3) * 8 / (kbps * 1000)
    return dict(size=size, id3=id3, true=true, hdr=hdr, vbr=len(kb) > 1, kbps=kbps)


def tail_rms(url, info, end_s):
    """طاقة الذيل (‏dB) بين end_s والنهاية المقدَّرة، بمدى بايتات يقابل آخر 40ث."""
    span = min(40.0, info["true"])
    byts = int(span * info["size"] / info["true"])
    start = max(0, info["size"] - byts)
    with fetch(url, headers={"Range": f"bytes={start}-"}) as r:
        data = r.read()
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as t:
        t.write(data); p = t.name
    try:
        out = subprocess.run(["ffmpeg", "-nostats", "-i", p, "-vn", "-af", "volumedetect", "-f", "null", "-"],
                             capture_output=True, text=True, errors="replace").stderr
        for line in out.splitlines():
            if "mean_volume" in line:
                return float(line.split("mean_volume:")[1].split("dB")[0])
    finally:
        os.unlink(p)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--keys", default="")
    ap.add_argument("--workers", type=int, default=24)
    a = ap.parse_args()
    with fetch(f"{PUBLIC}/timings/manifest.json") as r:
        man = json.loads(r.read())
    keys = [f"timings/{x['riwaya']}/{x['reciterId']}.jz" for x in man["indexes"]]
    if a.keys:
        w = set(a.keys.split(",")); keys = [k for k in keys if k in w]
    res = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "keys": {}}
    cache = {}

    def probe(u):
        if u not in cache:
            try: cache[u] = est(u)
            except Exception as ex: cache[u] = {"err": type(ex).__name__}
        return cache[u]

    t0 = time.time()
    for key in keys:
        with fetch(f"{PUBLIC}/{key}") as r:
            idx = json.loads(gzip.decompress(r.read()))
        per = {}
        for e in idx["entries"]:
            s = int(e["ayahId"].split(":")[0])
            d = per.setdefault(s, {"ref": e.get("fileRef"), "end": 0})
            d["end"] = max(d["end"], e.get("endMs") or 0)
        urls = sorted({d["ref"] for d in per.values() if d["ref"]})
        with ThreadPoolExecutor(max_workers=a.workers) as pool:
            list(pool.map(probe, urls))
        rows = []
        for s, d in sorted(per.items()):
            i = probe(d["ref"]) if d["ref"] else None
            if not i or "err" in i:
                rows.append({"s": s, "err": (i or {}).get("err", "لا رابط")}); continue
            end = d["end"] / 1000
            row = {"s": s, "endS": round(end, 1), "hdrS": round(i["hdr"], 1), "trueS": round(i["true"], 1), "vbr": i["vbr"]}
            if not i["vbr"] and abs(i["hdr"] - end) <= 0.7 and i["true"] - end > 3:
                row["flag"] = True
                try: row["tailDb"] = tail_rms(d["ref"], i, end)
                except Exception as ex: row["tailErr"] = type(ex).__name__
            rows.append(row)
        res["keys"][key] = rows
        print(f"{key}: علّم {sum(1 for r in rows if r.get('flag'))} من {len(rows)} · {time.time()-t0:.0f}ث", flush=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False)
    print("كُتب", a.out)


if __name__ == "__main__":
    main()
