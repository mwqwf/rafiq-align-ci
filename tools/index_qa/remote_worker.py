#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""عامل القصّ والتفريغ — يعمل **على خادم الفهرسة** لا على جهاز المالك.

يقرأ خطة نوافذ من stdin (JSON) ويطبع تفريغ كل نافذة (JSON) على stdout.
⛔ لا يكتب شيئاً خارج `WORK`، ولا يلمس دفعات الأسطول ولا `/root/done`.

سبب وجوده على الخادم: الثنائي `whisper-cli` والنموذج q8 مبنيّان هناك
(‏Release/GGML_NATIVE) والصوت يُنزَّل بخط الخادم لا بخط المالك. وهو
**عملية whisper واحدة متسلسلة بخيوط محدودة** احتراماً لدرس العدة §8
(«عملية whisper واحدة لكل جهة») كي لا يزاحم دفعات الفهرسة الجارية.

الخطة:
  {"threads": 2,
   "jobs": [{"id": "...", "url": "...", "startMs": 0, "endMs": 4200}, ...]}
المخرج:
  {"ok": true, "results": {"<id>": {"text": "...", "ms": 123}, ...},
   "errors": {"<id>": "..."}}
"""
import json, os, subprocess, sys, hashlib, time

ROOT    = "/root/QuranRafiq"
WHISPER = f"{ROOT}/assets-archive/ggml/bin/Release/whisper-cli.exe"
MODEL   = f"{ROOT}/assets-archive/ggml/ggml-tiny-ar-quran-q8_0.bin"
WORK    = "/root/qa_work"
AUDIO   = f"{WORK}/audio"
WIN     = f"{WORK}/win"

def sh(cmd, timeout):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                          stdin=subprocess.DEVNULL, errors="replace")

def fetch(url):
    """ينزّل ملف السورة مرة واحدة ويحتفظ به لبقية نوافذ السورة نفسها."""
    p = os.path.join(AUDIO, hashlib.sha256(url.encode()).hexdigest()[:16] + ".mp3")
    if os.path.exists(p) and os.path.getsize(p) > 10_000:
        return p
    r = sh(["curl", "-sS", "-L", "--max-time", "300", "-o", p, url], 330)
    if not os.path.exists(p) or os.path.getsize(p) < 10_000:
        raise RuntimeError(f"تنزيل فاشل ({r.stderr.strip()[:120]})")
    return p

def cut(mp3, start_ms, end_ms, out):
    # القصّ بـffmpeg مباشرة إلى PCM16 أحادي 16ك — لا نعتمد soundfile (غير مثبّت على الخادم).
    dur = max(0.2, (end_ms - start_ms) / 1000.0)
    r = sh(["ffmpeg", "-y", "-v", "error", "-ss", f"{max(0,start_ms)/1000:.3f}",
            "-t", f"{dur:.3f}", "-i", mp3, "-ac", "1", "-ar", "16000",
            "-c:a", "pcm_s16le", out], 120)
    if not os.path.exists(out) or os.path.getsize(out) < 2000:
        raise RuntimeError(f"قصّ فاشل ({r.stderr.strip()[:120]})")

def transcribe(wav, threads):
    r = sh([WHISPER, "-m", MODEL, "-f", wav, "-l", "ar", "-t", str(threads),
            "-nt", "-np", "--no-fallback"], 300)
    if r.returncode != 0:
        raise RuntimeError(f"whisper rc={r.returncode} {r.stderr.strip()[:120]}")
    return " ".join(r.stdout.split())

def main():
    plan = json.load(sys.stdin)
    threads = int(plan.get("threads", 2))
    os.makedirs(AUDIO, exist_ok=True); os.makedirs(WIN, exist_ok=True)
    for b in (WHISPER, MODEL):
        if not os.path.exists(b):
            print(json.dumps({"ok": False, "error": f"مفقود: {b}"}, ensure_ascii=False)); return
    results, errors = {}, {}
    for j in plan["jobs"]:
        t0 = time.time()
        wav = os.path.join(WIN, j["id"].replace(":", "_").replace("/", "_") + ".wav")
        try:
            cut(fetch(j["url"]), j["startMs"], j["endMs"], wav)
            results[j["id"]] = {"text": transcribe(wav, threads),
                                "ms": int((time.time() - t0) * 1000)}
        except Exception as ex:
            errors[j["id"]] = str(ex)[:200]
        finally:
            if os.path.exists(wav):
                os.remove(wav)   # النوافذ لا تُخزَّن — القرص للأسطول لا لنا
    print(json.dumps({"ok": True, "results": results, "errors": errors}, ensure_ascii=False))

if __name__ == "__main__":
    main()
