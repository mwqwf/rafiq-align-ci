# -*- coding: utf-8 -*-
"""يُنفَّذ على خادم الأسطول: يجري **الجراحة الصوتية** على خطة الحقن ثم يفرّغ.

لكل بند: تلاوةٌ صحيحة تُقطَّع عند حدود كلمةٍ مقيسة، ويُعاد تركيبها ناقصةً
أو مُبدَلة أو مبدَّلة الترتيب أو مزيدة — فالحقيقة الأرضية **معلومة بالبناء**
لا مستنبطة. ثم يمرّ الناتج بمسار المحرك نفسه (نوافذ 25ث + whisper q8).

    python3 remote_inject.py --plan inject_plan.json --out inj_hyps.json
"""
import argparse
import json
import os
import subprocess
import time
import urllib.request

from remote_whisper import MODEL, TMP, WHISPER, sh, split_windows

SR = 16000


def fetch_wav(url, dst, trim=None):
    """ينزّل ويحوّل 16ك.هز؛ و[trim] (بالمللي، مطلقاً في الملف) يقتطع الآية من
    ملف السورة أولاً — فتصير إزاحات الجراحة نسبيةً إلى بداية الآية."""
    src = dst + ".src"
    for a in range(3):
        try:
            urllib.request.urlretrieve(url, src)
            break
        except Exception:
            if a == 2:
                raise
            time.sleep(3)
    cmd = ["ffmpeg", "-y", "-v", "error"]
    if trim:
        cmd += ["-ss", f"{trim[0]/1000:.3f}"]
    cmd += ["-i", src]
    if trim:
        cmd += ["-t", f"{(trim[1]-trim[0])/1000:.3f}"]
    r = sh(cmd + ["-ar", str(SR), "-ac", "1", dst])
    os.remove(src)
    if r.returncode:
        raise RuntimeError("ffmpeg: " + r.stderr[-200:])
    return dst


def pcm(path):
    import wave
    with wave.open(path, "rb") as w:
        import array
        a = array.array("h")
        a.frombytes(w.readframes(w.getnframes()))
        return a


def write(path, samples):
    import wave
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(samples.tobytes())


def idx(ms):
    return max(0, int(ms * SR / 1000))


def operate(it, base_wav, donor_wav):
    """يعيد عيّنات الصوت بعد الجراحة."""
    a = pcm(base_wav)
    s, e = (idx(x) for x in it["cutMs"])
    e = min(e, len(a))
    if it["op"] == "OMIT":
        return a[:s] + a[e:]
    if it["op"] == "SUBSTITUTE":
        d = pcm(donor_wav)
        ds, de = (idx(x) for x in it["donor"]["cutMs"])
        return a[:s] + d[ds:min(de, len(d))] + a[e:]
    if it["op"] == "INSERT":
        d = pcm(donor_wav)
        ds, de = (idx(x) for x in it["donor"]["cutMs"])
        return a[:s] + d[ds:min(de, len(d))] + a[s:]     # إقحامٌ بلا حذف
    if it["op"] == "SWAP":
        s2, e2 = (idx(x) for x in it["swapMs"])
        e2 = min(e2, len(a))
        return a[:s] + a[s2:e2] + a[e:s2] + a[s:e] + a[e2:]
    raise ValueError(it["op"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--lang", default="ar")
    ap.add_argument("--threads", type=int, default=2)
    ap.add_argument("--clean", action="store_true",
                    help="فرّغ الأصل السليم بدل المحقون (خط الأساس للإنذار الكاذب)")
    args = ap.parse_args()
    os.makedirs(TMP, exist_ok=True)
    items = json.load(open(args.plan, encoding="utf-8"))["items"]
    done = {}
    if os.path.exists(args.out):
        done = json.load(open(args.out, encoding="utf-8")).get("hyps", {})
    for n, it in enumerate(items, 1):
        if it["id"] in done:
            continue
        rec = {}
        try:
            base = fetch_wav(it["url"], os.path.join(TMP, it["id"] + ".base.wav"),
                             it.get("trimMs"))
            donor = None
            if it.get("donor") and not args.clean:
                donor = fetch_wav(it["donor"]["url"], os.path.join(TMP, it["id"] + ".don.wav"))
            target = os.path.join(TMP, it["id"] + ".wav")
            if args.clean:
                os.replace(base, target)
            else:
                write(target, operate(it, base, donor))
                os.remove(base)
            if donor:
                os.remove(donor)
            parts = split_windows(target, target[:-4])
            t0 = time.time()
            texts, rc = [], 0
            for p in parts:
                r = sh([WHISPER, "-m", MODEL, "-f", p, "-l", args.lang,
                        "-t", str(args.threads), "-bo", "1", "-bs", "1", "-nt", "-np"])
                texts.append(" ".join(r.stdout.split()))
                rc = rc or r.returncode
                if p != target:
                    os.remove(p)
            rec = {"text": " ".join(t for t in texts if t), "ms": int((time.time() - t0) * 1000),
                   "rc": rc, "windows": len(parts)}
            os.remove(target)
        except Exception as e:
            rec = {"error": str(e)[:200]}
        done[it["id"]] = rec
        if n % 10 == 0 or n == len(items):
            json.dump({"clean": args.clean, "hyps": done},
                      open(args.out, "w", encoding="utf-8"), ensure_ascii=False)
            print(f"{n}/{len(items)}", flush=True)
    json.dump({"clean": args.clean, "hyps": done},
              open(args.out, "w", encoding="utf-8"), ensure_ascii=False)
    print("DONE", len(done), flush=True)


if __name__ == "__main__":
    main()
