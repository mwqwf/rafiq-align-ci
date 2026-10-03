#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""تصديرُ المنشور للتدقيق المستقلّ — قارئٌ محضٌ لا يكتب في الدلو بايتاً (‏تدقيقُ الجولة الثانية 2026-10-03).

    python tools/index_qa/audit_export.py --part index      # الفهارسُ المنشورةُ مضغوطةً + manifest + التجميد + الكتالوج + البصمةُ العامّة
    python tools/index_qa/audit_export.py --part state      # خلاصةُ كلِّ حكمٍ في state/ (‏حقولُ الحكم بلا عيّناتها الكبيرة)
    python tools/index_qa/audit_export.py --part durations --shard 0/4   # طولُ كلّ ملفٍّ صوتيٍّ منشور (‏ترويسةُ MP3 بطلبِ مدى)

**سببُه:** المدقّقُ المستقلّ لا يصل الدلوَ ولا الصوتَ من بيئته، والتدقيقُ «كأنّه أوّلَ مرّة» لا يصحّ إن بُني
على خلاصاتِ أدواتٍ سابقة. فيُصدَّر **الخامُ** (‏مداخلُ كلّ فهرسٍ وحقولُ الأحكام) ويُحلَّل خارجاً بشيفرةٍ مستقلّة.
⚖️ لا يمسّ فهرساً ولا حارساً ولا عتبةً ولا تجميداً؛ يكتب في `ops/out/audit-r2/` وحدَه.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import struct
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
OUT = ROOT / "ops" / "out" / "audit-r2"
ONLY = ""

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                                 # noqa: BLE001
        pass


def _published(cl, b):
    keys = []
    for pg in cl.get_paginator("list_objects_v2").paginate(Bucket=b, Prefix="timings/"):
        for o in pg.get("Contents", []):
            k = o["Key"]
            if k.endswith(".jz") and k.count("/") == 2:
                keys.append(k)
    return sorted(keys)


def _get(cl, b, k):
    err = None
    for i in range(4):
        try:
            return cl.get_object(Bucket=b, Key=k)["Body"].read()
        except Exception as ex:                                       # noqa: BLE001
            err = ex
            time.sleep(1.5 * (i + 1))
    raise RuntimeError(f"{k}: {err}")


def _public_sha(key):
    import promote as _p
    req = urllib.request.Request(_p.PUBLIC.rstrip("/") + "/" + key, headers={"User-Agent": "rafiq-audit-r2/1"})
    for i in range(3):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return hashlib.sha256(r.read()).hexdigest()
        except Exception:                                             # noqa: BLE001
            time.sleep(2 * (i + 1))
    return None


def part_index(cl, b):
    keys = _published(cl, b)
    with ThreadPoolExecutor(max_workers=12) as pool:
        raws = dict(zip(keys, pool.map(lambda k: _get(cl, b, k), keys)))
        pubs = dict(zip(keys, pool.map(_public_sha, keys)))
    out = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "indexes": {}}
    for k in keys:
        raw = raws[k]
        idx = json.loads(gzip.decompress(raw).decode("utf-8"))
        E = idx.pop("entries", []) or []
        files, fpos, rows, extra_keys = [], {}, [], set()
        for e in E:
            f = e.get("fileRef")
            if f not in fpos:
                fpos[f] = len(files)
                files.append(f)
            aid = str(e.get("ayahId"))
            try:
                s, a = (int(x) for x in aid.split(":"))
            except Exception:                                         # noqa: BLE001
                s, a = -1, -1
            rows.append([s, a, e.get("startMs"), e.get("endMs"), fpos[f]])
            extra_keys.update(x for x in e if x not in ("ayahId", "startMs", "endMs", "fileRef"))
        out["indexes"][k] = {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw),
                             "publicSha": pubs.get(k), "header": idx, "files": files, "rows": rows,
                             "entryExtraKeys": sorted(extra_keys)}
    side = {}
    for key in ("timings/manifest.json", "timings/frozen.txt", "catalog/reciters.json"):
        try:
            side[key] = _get(cl, b, key).decode("utf-8")
        except Exception as ex:                                       # noqa: BLE001
            side[key] = f"ERROR {ex}"
    out["side"] = side
    OUT.mkdir(parents=True, exist_ok=True)
    data = json.dumps(out, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    p = OUT / "index.json.gz"
    p.write_bytes(gzip.compress(data, 9))
    print(f"فهارس {len(keys)} · مداخل {sum(len(v['rows']) for v in out['indexes'].values())} · "
          f"{p.relative_to(ROOT)} {p.stat().st_size} بايت")
    print("بصمةٌ عامّةٌ متعذّرة:", [k for k in keys if not pubs.get(k)])


def part_state(cl, b):
    import promote as _p
    reps = _p.bucket_reports(cl, b)
    rows = []
    for name, r in reps:
        smp = r.get("sample") if isinstance(r.get("sample"), dict) else {}
        op = r.get("openers") if isinstance(r.get("openers"), dict) else {}
        try:
            tool_ok = _p.openers_tool_ok(r) if str(r.get("kind") or "").lower() == "openers" else None
        except Exception as ex:                                       # noqa: BLE001
            tool_ok = f"ERR {ex}"
        row = {"name": name, "kind": r.get("kind"), "key": r.get("key"), "sha256": r.get("sha256"),
               "verdict": r.get("verdict"), "source": r.get("source"), "engine": r.get("engine"),
               "band": r.get("band"), "ts": r.get("ts") or r.get("at"), "verdictFile": r.get("verdict_file"),
               "hasAudioSample": _p.has_audio_sample(r),
               "severe": smp.get("severe"), "seedSalt": smp.get("seedSalt"),
               "sampleKeys": sorted(smp)[:40],
               "fatal": [str(x)[:200] for x in (r.get("fatal") or [])][:8], "fatalN": len(r.get("fatal") or []),
               "severeRate": r.get("severeRate")}
        if str(r.get("kind") or "").lower() == "openers":
            row.update({"toolOk": tool_ok, "scope": r.get("scope"), "checked": r.get("checked"),
                        "hasLate": "late" in r, "late": r.get("late"), "lateCtcRule": r.get("lateCtcRule"),
                        "lateConfirmed": r.get("lateConfirmed"), "swallowed": r.get("swallowed"),
                        "suspect": r.get("suspect"), "tail": r.get("tail"), "unknown": r.get("unknown"),
                        "defects": op.get("defects"), "commit": r.get("commit"),
                        "openersVerdict": r.get("openersVerdict")})
        rows.append(row)
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / "state.json.gz"
    p.write_bytes(gzip.compress(json.dumps(rows, ensure_ascii=False, separators=(",", ":"),
                                           default=str).encode("utf-8"), 9))
    print(f"أحكام {len(rows)} · {p.relative_to(ROOT)} {p.stat().st_size} بايت")


# ───────── طولُ ملفّ MP3 من ترويسته (‏طلبُ مدى، بلا تنزيل الملفّ) ─────────
_BR = {  # (MPEG1, MPEG2/2.5) لطبقة III
    1: [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320],
    2: [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160]}
_SR = {3: [44100, 48000, 32000], 2: [22050, 24000, 16000], 0: [11025, 12000, 8000]}


def _range(url, a, z):
    req = urllib.request.Request(url, headers={"Range": f"bytes={a}-{z}", "User-Agent": "Mozilla/5.0 rafiq-audit"})
    with urllib.request.urlopen(req, timeout=60) as r:
        body = r.read(z - a + 1)
        cr = r.headers.get("Content-Range") or ""
        total = int(cr.split("/")[-1]) if "/" in cr and cr.split("/")[-1].isdigit() else None
        if total is None and r.status == 200:
            total = int(r.headers.get("Content-Length") or 0) or None
        return body, total, r.geturl()


def mp3_duration(url):
    head, total, final = _range(url, 0, 9)
    off = 0
    if head[:3] == b"ID3":
        sz = (head[6] << 21) | (head[7] << 14) | (head[8] << 7) | head[9]
        off = 10 + sz + (10 if head[5] & 0x10 else 0)
    buf, total2, _ = _range(final, off, off + 16383)
    total = total or total2
    i = 0
    while i + 4 <= len(buf):
        if buf[i] == 0xFF and (buf[i + 1] & 0xE0) == 0xE0:
            h = struct.unpack(">I", buf[i:i + 4])[0]
            ver = (h >> 19) & 3
            layer = (h >> 17) & 3
            bri = (h >> 12) & 15
            sri = (h >> 10) & 3
            if ver != 1 and layer == 1 and 0 < bri < 15 and sri < 3:
                br = _BR[1 if ver == 3 else 2][bri] * 1000
                sr = _SR[ver][sri]
                pad = (h >> 9) & 1
                mono = ((h >> 6) & 3) == 3
                spf = 1152 if ver == 3 else 576
                flen = (144 if ver == 3 else 72) * br // sr + pad
                # Xing/Info
                side = (17 if mono else 32) if ver == 3 else (9 if mono else 17)
                x = i + 4 + side
                tag = buf[x:x + 4]
                if tag in (b"Xing", b"Info") and x + 12 <= len(buf):
                    flags = struct.unpack(">I", buf[x + 4:x + 8])[0]
                    if flags & 1:
                        frames = struct.unpack(">I", buf[x + 8:x + 12])[0]
                        return {"ms": int(frames * spf * 1000 / sr), "how": "xing", "bytes": total, "br": br, "sr": sr}
                v = i + 36
                if buf[v:v + 4] == b"VBRI" and v + 18 <= len(buf):
                    frames = struct.unpack(">I", buf[v + 14:v + 18])[0]
                    return {"ms": int(frames * spf * 1000 / sr), "how": "vbri", "bytes": total, "br": br, "sr": sr}
                # تحقّقٌ من الإطار التالي قبل الاعتماد (‏لئلّا يُقرأ إطارٌ كاذب)
                j = i + flen
                if j + 2 <= len(buf) and not (buf[j] == 0xFF and (buf[j + 1] & 0xE0) == 0xE0):
                    i += 1
                    continue
                if total:
                    return {"ms": int((total - off - i) * 8 * 1000 / br), "how": "cbr", "bytes": total, "br": br, "sr": sr}
                return {"ms": None, "how": "nolen", "br": br, "sr": sr}
        i += 1
    return {"ms": None, "how": "noframe", "bytes": total, "off": off}


def part_durations(cl, b, shard):
    k, n = (int(x) for x in shard.split("/"))
    raw = gzip.decompress((OUT / "index.json.gz").read_bytes()) if (OUT / "index.json.gz").exists() else None
    if raw is None:
        sys.exit("⛔ يلزم index.json.gz أوّلاً (‏--part index)")
    data = json.loads(raw)
    urls = sorted({f for v in data["indexes"].values() for f in v["files"] if f})
    mine = [u for u in urls if int(hashlib.md5(u.encode()).hexdigest(), 16) % n == k]
    if ONLY:
        mine = [u for u in urls if ONLY in u]
    print(f"روابطُ فريدة {len(urls)} · هذه الشريحة {len(mine)}")
    t0 = time.time()

    def one(u):
        for i in range(2):
            try:
                return u, mp3_duration(u)
            except Exception as ex:                                   # noqa: BLE001
                err = str(ex)[:160]
                time.sleep(1 + i)
        return u, {"ms": None, "how": "error", "err": err}

    res = {}
    with ThreadPoolExecutor(max_workers=32) as pool:
        for u, r in pool.map(one, mine):
            res[u] = r
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / (f"durations-{k}of{n}.json.gz" if not ONLY else f"recheck-{hashlib.md5(ONLY.encode()).hexdigest()[:8]}-{time.strftime('%H%M', time.gmtime())}.json.gz")
    p.write_bytes(gzip.compress(json.dumps(res, ensure_ascii=False, separators=(",", ":")).encode("utf-8"), 9))
    from collections import Counter
    print(f"{p.relative_to(ROOT)} · {dict(Counter(r['how'] for r in res.values()))} · {time.time() - t0:.0f}ث")


def part_livesha(cl, b, shard):
    """بصمةُ الصوت الحيّ الآن عند الناشر لعيّنةٍ (‏بذرةٌ 20261003 · ثلاثُ سورٍ من 78–114 لكلّ فهرس) مقابلَ
    `audioSha256` في الفهرس — يكشف استبدالَ الناشر للملفّ بعد الفهرسة (‏التوقيتُ مقيسٌ على تسجيلٍ بعينه)."""
    import random
    k, n = (int(x) for x in shard.split("/"))
    data = json.loads(gzip.decompress((OUT / "index.json.gz").read_bytes()))
    rng = random.Random(20261003)
    jobs = []
    for key in sorted(data["indexes"]):
        v = data["indexes"][key]
        per = {}
        for s, a, st, en, fi in v["rows"]:
            per.setdefault(s, v["files"][fi])
        ash = v["header"].get("audioSha256") or []
        cands = sorted(s for s in per if s >= 78 and len(ash) >= s and ash[s - 1])
        for s in rng.sample(cands, min(3, len(cands))):
            jobs.append((key, s, per[s], ash[s - 1]))
    mine = [j for i, j in enumerate(jobs) if i % n == k]
    print(f"عيّنة {len(jobs)} · هذه الشريحة {len(mine)}")

    def one(j):
        key, s, u, want = j
        for i in range(3):
            try:
                req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0 rafiq-audit"})
                with urllib.request.urlopen(req, timeout=180) as r:
                    body = r.read()
                return {"key": key, "surah": s, "url": u, "want": want,
                        "got": hashlib.sha256(body).hexdigest(), "bytes": len(body)}
            except Exception as ex:                                   # noqa: BLE001
                err = str(ex)[:160]
                time.sleep(2 + 2 * i)
        return {"key": key, "surah": s, "url": u, "want": want, "got": None, "err": err}

    with ThreadPoolExecutor(max_workers=16) as pool:
        res = list(pool.map(one, mine))
    p = OUT / f"livesha-{k}of{n}.json"
    p.write_text(json.dumps(res, ensure_ascii=False, indent=0), encoding="utf-8")
    bad = [r for r in res if r.get("got") and r["got"] != r["want"]]
    print(f"{p.relative_to(ROOT)} · مطابق {sum(1 for r in res if r.get('got') == r['want'])} · "
          f"مختلف {len(bad)} · متعذّر {sum(1 for r in res if not r.get('got'))}")
    for r in bad:
        print("  ≠", r["key"], r["surah"], r["url"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--part", choices=["index", "state", "durations", "livesha"], required=True)
    ap.add_argument("--shard", default="0/1")
    ap.add_argument("--only", default="", help="durations: روابطُ تحوي هذا النصّ وحدها (‏إعادةُ فحصٍ للوصول)")
    a = ap.parse_args()
    global ONLY
    ONLY = a.only
    from run import s3
    cl, b = s3()
    {"index": lambda: part_index(cl, b), "state": lambda: part_state(cl, b),
     "durations": lambda: part_durations(cl, b, a.shard),
     "livesha": lambda: part_livesha(cl, b, a.shard)}[a.part]()


if __name__ == "__main__":
    main()
