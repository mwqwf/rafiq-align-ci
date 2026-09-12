# -*- coding: utf-8 -*-
"""🔪 **بناءُ صوت G3 لورشٍ وقالون** — نظيرُ `inject_local.py` الحفصيّ.

الفرقُ الجوهريّ عن الحفصيّ: توقيتاتُ الروايتين **داخل ملفِّ السورة** (`timeBase: SURAH_FILE`)
لا في ملفِّ آية. فيُنزَّل ملفُّ السورة مرّةً واحدةً ويُقصّ منه مدى الآية ثم تُجرى الجراحة.

⛔ **بلا حشوةٍ عند القطع** — نهاياتُ الفهرس ملصوقةٌ عمداً (`endsPolicy: contiguous`)،
والحشوةُ تسحب ذيلَ الجارة فتصنع إنذاراً كاذباً سببُه السكّينُ لا النموذج.

    python tools/tasmi_bench/inject_riwaya_local.py
"""
import argparse
import json
import os
import sys

import numpy as np
import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "tools", "alignment"))
from decode import run_decode  # noqa: E402

WORK = os.path.join(HERE, "work")
G3 = os.path.join(WORK, "g3r")
CACHE = os.path.join(WORK, "g3r_src")
SR = 16_000


def surah_wav(riwaya, surah, url, ffmpeg):
    """ملفُّ السورة wav 16ك.هز — تنزيلةٌ واحدةٌ في العمر (شبكةُ المالك شحيحة)."""
    dst = os.path.join(CACHE, f"{riwaya}_{surah:03d}.wav")
    if os.path.exists(dst):
        return dst
    from common import fetch_retry
    mp3 = dst + ".mp3"
    try:
        fetch_retry(url, mp3)
        run_decode([ffmpeg, "-y", "-v", "error", "-i", mp3, "-vn",
                    "-ar", str(SR), "-ac", "1", dst], mp3, dst)
        return dst
    except Exception as e:
        print(f"  ⚠️ تعذّر {riwaya} س{surah}: {str(e)[:70]}", flush=True)
        return None
    finally:
        if os.path.exists(mp3):
            os.remove(mp3)


def sl(x, a_ms, b_ms):
    a, b = int(a_ms * SR / 1000), int(b_ms * SR / 1000)
    a = max(0, min(a, len(x)))
    b = max(a, min(b, len(x)))
    return x[a:b]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", default=os.path.join(HERE, "inject_plan_riwaya.json"))
    ap.add_argument("--snr", type=float, default=10.0)
    args = ap.parse_args()

    from common import FFMPEG
    import augment as ag

    items = json.load(open(args.plan, encoding="utf-8"))["items"]
    for d in (CACHE, os.path.join(G3, "clean"), os.path.join(G3, "noisy")):
        os.makedirs(d, exist_ok=True)

    cache = {}
    ok = fail = 0
    print(f"▶ {len(items)} بنداً · {len({(i['riwaya'], i['surah']) for i in items})} ملفَّ سورة", flush=True)
    for n, it in enumerate(items, 1):
        key = (it["riwaya"], it["surah"])
        if key not in cache:
            p = surah_wav(it["riwaya"], it["surah"], it["url"], FFMPEG)
            cache[key] = sf.read(p, dtype="float32")[0] if p else None
        full = cache[key]
        if full is None:
            fail += 1
            continue

        a0, b0 = it["ayahMs"]
        base = sl(full, a0, b0)                      # الآيةُ كاملةً
        ca, cb = it["cutMs"][0] - a0, it["cutMs"][1] - a0   # الحدود بإحداثيّات الآية
        ia, ib = int(ca * SR / 1000), int(cb * SR / 1000)
        ia = max(0, min(ia, len(base)))
        ib = max(ia, min(ib, len(base)))

        op = it["op"]
        y = None
        if op == "OMIT":
            y = np.concatenate([base[:ia], base[ib:]])
        elif op in ("SUBSTITUTE", "INSERT"):
            d = it.get("donor")
            dk = (it["riwaya"], int(d["ayah"].split(":")[0])) if d else None
            if dk and dk not in cache:
                p = surah_wav(dk[0], dk[1], d["url"], FFMPEG)
                cache[dk] = sf.read(p, dtype="float32")[0] if p else None
            dw = sl(cache[dk], *d["cutMs"]) if dk and cache.get(dk) is not None else None
            if dw is not None and len(dw):
                lvl = max(np.abs(base).max(), 1e-6) / max(np.abs(dw).max(), 1e-6)
                dw = (dw * lvl).astype(np.float32)
                y = (np.concatenate([base[:ia], dw, base[ib:]]) if op == "SUBSTITUTE"
                     else np.concatenate([base[:ia], dw, base[ia:]]))
        elif op == "SWAP":
            sa, sb = it["swapMs"][0] - a0, it["swapMs"][1] - a0
            ja, jb = int(sa * SR / 1000), int(sb * SR / 1000)
            if ib <= ja <= jb <= len(base):
                y = np.concatenate([base[:ia], base[ja:jb], base[ib:ja], base[ia:ib], base[jb:]])

        if y is None or len(y) < SR // 4:
            fail += 1
            continue
        y = y.astype(np.float32)
        sf.write(os.path.join(G3, "clean", it["id"] + ".wav"), y, SR, subtype="PCM_16")
        noisy = ag.transform(y, "noise-fan-10", it["id"], [], FFMPEG)
        sf.write(os.path.join(G3, "noisy", it["id"] + ".wav"), noisy, SR, subtype="PCM_16")
        ok += 1
        if n % 20 == 0:
            print(f"    … {n}/{len(items)} (نجح {ok} · أخفق {fail})", flush=True)

    print(f"✅ نجح {ok} · أخفق {fail} ⇒ {G3}")
    meta = {"plan": os.path.basename(args.plan), "snr": args.snr, "pad": 0,
            "note": "⛔ بلا حشوة — endsPolicy: contiguous"}
    json.dump(meta, open(os.path.join(G3, "meta.json"), "w", encoding="utf-8"), ensure_ascii=False)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
