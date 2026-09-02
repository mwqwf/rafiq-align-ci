# -*- coding: utf-8 -*-
"""قياس إنتاجية whisper على خادم الفهرسة: أي توزيعٍ للأنوية يعطي أكثر عملاً؟

يُنفَّذ **على الخادم**. الحمل واحدٌ بالضبط في كل حالة (نفس الملفات بنفس
الترتيب)، والزمن الكلي هو الحكم — لا متوسط الملف الواحد (يخدع: زيادة الخيوط
تسرّع الملف وتبطئ المجموع).

    python3 throughput.py --wav DIR --combos 4x4,8x2,16x1
    python3 throughput.py --wav DIR --combos 4x4 --flags "" --tag noac

⛔ لا يُشغَّل على خادمٍ فيه سائق فهرسة: القياس تحت حملٍ مجهول ليس قياساً.
"""
import argparse
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

HOME = os.path.expanduser("~")
WHISPER = f"{HOME}/QuranRafiq/assets-archive/ggml/bin/Release/whisper-cli.exe"
MODEL = f"{HOME}/QuranRafiq/assets-archive/ggml/ggml-tiny-ar-quran-q8_0.bin"
BASE_FLAGS = "-bo 1 -bs 1 -nf -ac 512"      # الوصفة الحالية في transcribe.py


def run_one(path, threads, flags, lang="ar"):
    cmd = [WHISPER, "-m", MODEL, "-f", path, "-l", lang, "-t", str(threads),
           "-nt", "-np"] + flags.split()
    t0 = time.time()
    r = subprocess.run(cmd, capture_output=True, text=True)
    return {"file": os.path.basename(path), "ms": int((time.time() - t0) * 1000),
            "rc": r.returncode, "text": " ".join(r.stdout.split())}


def sweep(files, jobs, threads, flags):
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=jobs) as ex:
        out = list(ex.map(lambda f: run_one(f, threads, flags), files))
    return int((time.time() - t0) * 1000), out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wav", required=True)
    ap.add_argument("--combos", default="4x4,8x2,16x1")
    ap.add_argument("--flags", default=BASE_FLAGS)
    ap.add_argument("--tag", default="")
    ap.add_argument("--out", default="throughput.json")
    args = ap.parse_args()
    files = sorted(os.path.join(args.wav, f) for f in os.listdir(args.wav)
                   if f.endswith(".wav"))
    if not files:
        sys.exit("لا ملفات wav")
    audio_ms = 0
    for f in files:
        p = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                            "-of", "default=nw=1:nk=1", f], capture_output=True, text=True)
        audio_ms += int(float(p.stdout.strip() or 0) * 1000)
    print(f"الحمل: {len(files)} ملفاً · {audio_ms/1000:.0f}ث صوتاً · الأعلام: {args.flags!r}")

    results = {}
    for combo in args.combos.split(","):
        j, t = (int(x) for x in combo.lower().split("x"))
        wall, out = sweep(files, j, t, args.flags)
        bad = [o for o in out if o["rc"]]
        thr = audio_ms / wall                      # ثانية صوت لكل ثانية جدار
        results[combo] = {"wallMs": wall, "audioMs": audio_ms, "speedup": thr,
                          "failed": len(bad),
                          "texts": {o["file"]: o["text"] for o in out}}
        print(f"  {combo:6s} ⇒ {wall/1000:7.1f}ث جداراً · ×{thr:.1f} أسرع من الزمن الحقيقي"
              f" · إخفاقات {len(bad)}", flush=True)

    best = max(results, key=lambda k: results[k]["speedup"])
    ref = results.get("4x4") or results[list(results)[0]]
    print(f"الأفضل: {best} (‏{results[best]['speedup']/ref['speedup']*100-100:+.1f}% "
          f"عن 4x4)")
    # تطابق النصّ بين التوزيعات — توزيعُ الأنوية يجب ألّا يغيّر مخرجاً
    keys = list(results)
    if len(keys) > 1:
        a = results[keys[0]]["texts"]
        for k in keys[1:]:
            same = sum(1 for f in a if a[f] == results[k]["texts"].get(f))
            print(f"  تطابق النصّ {keys[0]} ↔ {k}: {same}/{len(a)}")
    meta = {"flags": args.flags, "tag": args.tag, "files": len(files),
            "audioMs": audio_ms,
            "results": {k: {kk: vv for kk, vv in v.items() if kk != "texts"}
                        for k, v in results.items()},
            "texts": {k: v["texts"] for k, v in results.items()}}
    json.dump(meta, open(args.out, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"→ {args.out}")


if __name__ == "__main__":
    main()
