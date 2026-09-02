# -*- coding: utf-8 -*-
"""يُنفَّذ **على خادم الأسطول**: ينزّل صوت كل بند، يحوّله 16ك.هز، يفرّغه، يحذفه.

سبب وجوده هناك لا على جهاز المالك: ثنائي `whisper-cli` المحلي حُذف ولا نسخة له
على R2، ولا مترجم C على الجهاز (درس الأسطول 9). التشغيل بإذن الإشراف:
**عملية واحدة `-t 2`** كي لا تزاحم الفهرسة الجارية.

لا سرّ يُنقل إلى الخادم: روابط R2 **موقّعة مسبقاً** تُولَّد على جهاز المالك.

    python3 remote_whisper.py --job job.json --out hyps_ar.json --lang ar
"""
import argparse
import json
import os
import subprocess
import time
import urllib.request
import wave

HOME = os.path.expanduser("~")
WHISPER = f"{HOME}/QuranRafiq/assets-archive/ggml/bin/Release/whisper-cli.exe"
MODEL = f"{HOME}/QuranRafiq/assets-archive/ggml/ggml-tiny-ar-quran-q8_0.bin"
TMP = "/tmp/tasmi"


def sh(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def prepare(it):
    """يعيد مسار wav 16ك.هز (ينزّل ويقصّ عند الحاجة)."""
    os.makedirs(TMP, exist_ok=True)
    src = os.path.join(TMP, it["id"] + ".src")
    wav = os.path.join(TMP, it["id"] + ".wav")
    for attempt in range(3):
        try:
            urllib.request.urlretrieve(it["url"], src)
            break
        except Exception:
            if attempt == 2:
                raise
            time.sleep(3)
    cmd = ["ffmpeg", "-y", "-v", "error"]
    if it.get("startMs") is not None:
        cmd += ["-ss", f"{it['startMs']/1000:.3f}"]
    cmd += ["-i", src]
    if it.get("endMs") is not None:
        cmd += ["-t", f"{(it['endMs']-it['startMs'])/1000:.3f}"]
    cmd += ["-ar", "16000", "-ac", "1", wav]
    r = subprocess.run(cmd, capture_output=True, text=True)
    os.remove(src)
    if r.returncode:
        raise RuntimeError("ffmpeg: " + r.stderr[-200:])
    return wav


SR = 16000
WINDOW_S, TAIL_FRACTION = 25, 3     # مرآة LongAudioTranscriber: نافذة 25ث


def _read_pcm(path):
    with wave.open(path, "rb") as w:
        n = w.getnframes()
        import array
        a = array.array("h")
        a.frombytes(w.readframes(n))
        return a


def _write_pcm(path, samples):
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(samples.tobytes())


def quietest_cut(a, frm, to):
    """أدنى طاقة بإطارات 100م.ث — منقولة عن LongAudioTranscriber.quietestCut."""
    frame = SR // 10
    best, best_e, i = to - frame, None, frm
    while i + frame <= to:
        e = 0
        for k in range(i, i + frame, 4):        # عيّنة كل 4 (RMS نسبي يكفي للأدنى)
            e += a[k] * a[k]
        if best_e is None or e < best_e:
            best_e, best = e, i
        i += frame // 2
    return min(best + frame // 2, to)


def split_windows(wav, out_prefix):
    """يقسّم wav إلى نوافذ كما يفعل المحرك على الجهاز؛ يعيد قائمة مسارات."""
    a = _read_pcm(wav)
    window = WINDOW_S * SR
    if len(a) <= window + SR:
        return [wav]
    parts, start, k = [], 0, 0
    while start < len(a):
        hard = min(start + window, len(a))
        end = hard if hard == len(a) else quietest_cut(a, start + window * 2 // TAIL_FRACTION, hard)
        p = f"{out_prefix}.w{k}.wav"
        _write_pcm(p, a[start:end])
        parts.append(p); k += 1
        if end == len(a):
            break
        start = end
    return parts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--job", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--lang", default="ar")
    ap.add_argument("--threads", type=int, default=2)
    ap.add_argument("--model", default=MODEL,
                    help="نموذج ggml بديل (لمقارنة tiny/base بجدول كلفة)")
    ap.add_argument("--windowed", action="store_true",
                    help="قطّع الطويل نوافذ 25ث كما يفعل المحرك على الجهاز")
    args = ap.parse_args()

    items = json.load(open(args.job, encoding="utf-8"))["items"]
    done = {}
    if os.path.exists(args.out):
        done = json.load(open(args.out, encoding="utf-8")).get("hyps", {})
    meta = {"lang": args.lang, "threads": args.threads, "windowed": args.windowed,
            "modelPath": args.model, "modelBytes": os.path.getsize(args.model),
            "flags": "-bo 1 -bs 1 -nt -np (مرآة الحاكم: greedy بلا طوابع)",
            "model": os.path.basename(args.model), "host": os.uname().nodename}

    for n, it in enumerate(items, 1):
        if it["id"] in done:
            continue
        rec = {}
        try:
            wav = prepare(it)
            dur = float(sh(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                            "-of", "default=nw=1:nk=1", wav]).stdout.strip() or 0)
            parts = split_windows(wav, wav[:-4]) if args.windowed else [wav]
            t0 = time.time()
            texts, rc = [], 0
            for p in parts:
                r = sh([WHISPER, "-m", args.model, "-f", p, "-l", args.lang,
                        "-t", str(args.threads), "-bo", "1", "-bs", "1", "-nt", "-np"])
                texts.append(" ".join(r.stdout.split()))
                rc = rc or r.returncode
                if p != wav:
                    os.remove(p)
            rec = {"text": " ".join(t for t in texts if t), "ms": int((time.time() - t0) * 1000),
                   "audioMs": int(dur * 1000), "rc": rc, "windows": len(parts)}
            os.remove(wav)
        except Exception as e:                       # لا يسقط التشغيل كله ببند
            rec = {"error": str(e)[:200]}
        done[it["id"]] = rec
        if n % 10 == 0 or n == len(items):
            json.dump({"meta": meta, "hyps": done}, open(args.out, "w", encoding="utf-8"),
                      ensure_ascii=False)
            print(f"{n}/{len(items)}", flush=True)
    json.dump({"meta": meta, "hyps": done}, open(args.out, "w", encoding="utf-8"),
              ensure_ascii=False)
    print("DONE", len(done), flush=True)


if __name__ == "__main__":
    main()
