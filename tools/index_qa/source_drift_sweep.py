#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""مسحُ تبدّل المصدر لكلّ المنشور — قارئٌ محض (2026-11-09 · أمر القائد العاجل: 055.mp3 للكردي قُصّ بعد الفهرسة).

    python tools/index_qa/source_drift_sweep.py --out ops/out/source-drift.json [--shard I/N] [--only riw/id,…]

لا يكتب في الدلو ولا يحجب ولا يرقّي؛ يقرأ من العنوان العامّ وحده. لكلّ (قارئ، سورة) في فهرسٍ منشور:
  ١) HEAD إلى المصدر الحيّ (fileRef) ⇒ Content-Length وETag وLast-Modified.
  ٢) أوّل 64ك.ب بطلب مدى ⇒ مدّةٌ مقدَّرة (‏Xing أو CBR كما في duration_sweep).
علاماتُ التبدّل (كلُّ واحدةٍ دليلٌ مستقلّ لا حكمٌ نهائيّ):
  · `modifiedAfterIndex`: Last-Modified أحدثُ من `generatedAt` للفهرس بيومٍ فأكثر.
  · `sizeVsMirror`: حجمُ المصدر الحيّ ≠ `perFile.bytes` في مانيفست المرآة (‏لمن له مرآة وحدَه).
  · `endBeyondFile`: آخرُ endMs في السورة > المدّة المقدَّرة للملفّ الحاليّ + هامش (‏نقصٌ في الملفّ).
  · `probeError`: تعذّر الوصول (‏يُسمّى ولا يُعدّ سليماً).
والترتيبُ بحجم الفرق: max(|فرق الحجم عن المرآة| بالثواني المكافئة، endBeyond بالثواني).
"""
import argparse
import email.utils
import gzip
import json
import os
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from duration_sweep import PUBLIC, UA, first_frame  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = HERE.parents[1]
RIW = ("hafs", "warsh", "qalun", "douri", "shuba", "sousi")
END_MARGIN_S = 3.0          # هامشُ خطأ تقدير المدّة قبل أن يُعدّ آخرُ endMs «بعد نهاية الملفّ»
MOD_MARGIN_S = 86400        # Last-Modified بعد توليد الفهرس بأكثر من يوم


def req(url, method="GET", headers=None, timeout=45):
    r = urllib.request.Request(url, method=method, headers={**UA, **(headers or {})})
    return urllib.request.urlopen(r, timeout=timeout)


def probe(url):
    """{size, etag, lastModified, fileSec, note} أو {error}."""
    out = {"url": url}
    try:
        try:
            with req(url, "HEAD") as r:
                h = r.headers
                out["size"] = int(h["Content-Length"]) if h.get("Content-Length") else None
                out["etag"] = (h.get("ETag") or "").strip('"')
                out["lastModified"] = h.get("Last-Modified")
        except Exception:                                    # noqa: BLE001  بعضُ الخوادم تردّ على HEAD بخطأ
            out["headFailed"] = True
        with req(url, "GET", {"Range": "bytes=0-65535"}) as r:
            buf = r.read()
            h = r.headers
            if out.get("size") is None:
                cr = h.get("Content-Range") or ""
                out["size"] = int(cr.rsplit("/", 1)[1]) if "/" in cr and cr.rsplit("/", 1)[1].isdigit() else None
            out.setdefault("etag", (h.get("ETag") or "").strip('"'))
            out.setdefault("lastModified", h.get("Last-Modified"))
        ff = first_frame(buf)
        if ff and out.get("size"):
            id3, kbps, sr, spf, xing = ff
            if xing:
                out["fileSec"] = round(xing * spf / sr, 1); out["note"] = f"xing {kbps}k"
            else:
                out["fileSec"] = round((out["size"] - id3) * 8 / (kbps * 1000), 1); out["note"] = f"cbr {kbps}k"
            out["kbps"] = kbps
        else:
            out["note"] = "مدّةٌ غيرُ مقدَّرة"
    except Exception as ex:                                  # noqa: BLE001
        out["error"] = f"{type(ex).__name__}: {str(ex)[:80]}"
    return out


def get_json(url, gz=False):
    with req(url, timeout=90) as r:
        b = r.read()
    return json.loads(gzip.decompress(b) if gz else b)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--shard", default="0/1")
    ap.add_argument("--only", default="")
    ap.add_argument("--workers", type=int, default=24)
    ap.add_argument("--budget-sec", type=int, default=19000)
    a = ap.parse_args()
    si, sn = (int(x) for x in a.shard.split("/"))
    t0 = time.time()
    man = get_json(f"{PUBLIC}/timings/manifest.json")
    items = sorted((x["riwaya"], x["reciterId"]) for x in man["indexes"])
    if a.only:
        want = {tuple(x.split("/")) for x in a.only.split(",")}
        items = [i for i in items if i in want]
    items = [it for n, it in enumerate(items) if n % sn == si]
    mirror = {}
    for riw in RIW:
        try:
            mm = get_json(f"{PUBLIC}/audio/{riw}/manifest.json")
            for rc in mm.get("reciters", []):
                for pf in rc.get("perFile", []) or []:
                    mirror[(riw, rc["id"], int(pf["surah"]))] = int(pf["bytes"])
        except Exception as ex:                              # noqa: BLE001
            print(f"⚠️ مانيفست مرآة {riw}: {type(ex).__name__}", flush=True)
    rows, probes, errs = [], {}, []
    for riw, rid in items:
        if time.time() - t0 > a.budget_sec:
            errs.append(f"نفدت الميزانية قبل {riw}/{rid}"); break
        try:
            idx = get_json(f"{PUBLIC}/timings/{riw}/{rid}.jz", gz=True)
        except Exception as ex:                              # noqa: BLE001
            errs.append(f"{riw}/{rid}: فهرسٌ لا يُقرأ {type(ex).__name__}"); continue
        gen = (idx.get("generatedAt") or 0) / 1000
        per = {}
        for e in idx["entries"]:
            s = int(e["ayahId"].split(":")[0])
            d = per.setdefault(s, {"ref": e.get("fileRef"), "end": 0, "n": 0})
            d["end"] = max(d["end"], int(e.get("endMs") or 0)); d["n"] += 1
        urls = sorted({d["ref"] for d in per.values() if d["ref"] and d["ref"] not in probes})
        with ThreadPoolExecutor(max_workers=a.workers) as pool:
            for u, p in zip(urls, pool.map(probe, urls)):
                probes[u] = p
        for s, d in sorted(per.items()):
            p = probes.get(d["ref"]) or {"error": "بلا رابط"}
            row = {"riwaya": riw, "reciter": rid, "surah": s, "ayat": d["n"], "lastEndSec": round(d["end"] / 1000, 1),
                   "ref": d["ref"], "size": p.get("size"), "etag": p.get("etag"), "lastModified": p.get("lastModified"),
                   "fileSec": p.get("fileSec"), "note": p.get("note"), "indexGeneratedAt": int(gen)}
            flags, mag = [], 0.0
            if p.get("error"):
                flags.append("probeError"); row["error"] = p["error"]
            lm = p.get("lastModified")
            if lm and gen:
                try:
                    lts = email.utils.parsedate_to_datetime(lm).timestamp()
                    if lts - gen > MOD_MARGIN_S:
                        flags.append("modifiedAfterIndex"); row["modifiedAfterIndexDays"] = round((lts - gen) / 86400, 1)
                except Exception:                            # noqa: BLE001
                    pass
            mb = mirror.get((riw, rid, s))
            if mb is not None and p.get("size") is not None:
                row["mirrorBytes"] = mb
                if p["size"] != mb:
                    flags.append("sizeVsMirror"); row["sizeDiffBytes"] = p["size"] - mb
                    kb = p.get("kbps") or 64
                    mag = max(mag, abs(p["size"] - mb) * 8 / (kb * 1000))
            if p.get("fileSec") and d["end"] / 1000 > p["fileSec"] + END_MARGIN_S:
                flags.append("endBeyondFile"); row["endBeyondSec"] = round(d["end"] / 1000 - p["fileSec"], 1)
                mag = max(mag, row["endBeyondSec"])
            row["flags"], row["magnitudeSec"] = flags, round(mag, 1)
            rows.append(row)
        nf = sum(1 for r in rows if r["reciter"] == rid and r["flags"])
        print(f"{riw}/{rid}: سور {len(per)} · موسومة {nf} · {time.time() - t0:.0f}ث", flush=True)
    flagged = sorted((r for r in rows if r["flags"]), key=lambda r: (-r["magnitudeSec"], r["reciter"], r["surah"]))
    res = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "shard": a.shard, "reciters": len(items),
           "rows": len(rows), "flaggedCount": len(flagged), "errors": errs, "flagged": flagged,
           "mirrorBaselines": len(mirror)}
    path = ROOT / a.out
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
    print(f"■ shard {a.shard}: {len(rows)} (قارئ،سورة) · موسومة {len(flagged)} · أخطاء {len(errs)}")
    for r in flagged[:60]:
        print(f"  {r['riwaya']}/{r['reciter']} س{r['surah']}: {','.join(r['flags'])} · فرق {r['magnitudeSec']}ث · "
              f"ملفّ {r.get('fileSec')}ث · آخر endMs {r['lastEndSec']}ث · LM {r.get('lastModified')}", flush=True)


if __name__ == "__main__":
    main()
