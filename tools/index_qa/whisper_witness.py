#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""شاهدُ Whisper float32 لنوافذ آياتٍ في ملفِّ سورةٍ واحد — مرشّحٌ للتوقيت لا نصٌّ مرجعيّ (‏2026-11-07).

    python tools/index_qa/whisper_witness.py --url <mp3> --surah 56 --riwaya hafs \\
        --ayahs "68:229000-239000,69:236000-246000" --model small --out out

يكتب `out/whisper_s056.json`: `sha256` الصوت المنزَّل (‏هي `audioSha256` للسورة) ولكلّ آيةٍ كلماتُها بأزمنتها المطلقة
في الملفّ (‏م.ث) واحتمالاتها. ⛔ لا يُكتب منه شيءٌ في الفهارس: `pin_heard --witness-run` يقرؤه ويقابله بنصّ المصحف
وبخريطة CTC، والنافذةُ التي يختارها المُطلِق لا تُقبل بها آيةٌ إلا إذا طابق التفريغُ طرفَي الآية.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SR = 16000


def parse_windows(txt):
    """«68:229000-239000,69:…» ⇐ {68: (229000, 239000)}؛ ويرفض ما لا يُفهم."""
    out = {}
    for part in (txt or "").replace("،", ",").split(","):
        part = part.strip()
        if not part:
            continue
        a, w = part.split(":")
        s, e = w.split("-")
        a, s, e = int(a), int(s), int(e)
        if not (0 <= s < e) or e - s > 120_000:
            raise SystemExit(f"⛔ نافذةُ الآية {a} غيرُ صالحة ({s}-{e}؛ والأقصى 120ث)")
        out[a] = (s, e)
    if not out:
        raise SystemExit("⛔ لا آياتٍ في --ayahs")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--url", required=True)
    ap.add_argument("--surah", type=int, required=True)
    ap.add_argument("--riwaya", default="hafs")
    ap.add_argument("--ayahs", required=True, help="آية:بدء-نهاية بالم.ث، مفصولةً بفواصل")
    ap.add_argument("--model", default="small", choices=("small", "medium", "large-v3"))
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    wins = parse_windows(a.ayahs)
    sys.path.insert(0, str(ROOT / "tools" / "alignment"))
    from common import fetch_retry, to_wav16k                            # noqa: PLC0415
    import numpy as np                                                   # noqa: PLC0415
    import faster_whisper                                                # noqa: PLC0415
    from faster_whisper import WhisperModel                              # noqa: PLC0415

    os.makedirs(a.out, exist_ok=True)
    mp3 = os.path.join(a.out, f"{a.surah:03d}.mp3")
    fetch_retry(a.url, mp3)
    sha = hashlib.sha256(open(mp3, "rb").read()).hexdigest()
    wav = to_wav16k(mp3, os.path.join(tempfile.mkdtemp(), "a.wav"))
    with wave.open(wav, "rb") as w:
        if w.getframerate() != SR or w.getnchannels() != 1:
            raise SystemExit("⛔ الصوتُ المفكوك ليس أحاديَّ 16ك.هز")
        pcm = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768.0
    model = WhisperModel(a.model, device="cpu", compute_type="float32", cpu_threads=os.cpu_count() or 2)
    res = {"surah": a.surah, "riwaya": a.riwaya, "fileRef": a.url, "sha256": sha, "model": a.model,
           "computeType": "float32", "fasterWhisper": getattr(faster_whisper, "__version__", ""),
           "ayahs": {}}
    for ay, (s, e) in sorted(wins.items()):
        seg = pcm[int(s * SR / 1000):int(e * SR / 1000)]
        segs, _info = model.transcribe(seg, language="ar", beam_size=5, word_timestamps=True,
                                       condition_on_previous_text=False, vad_filter=False, temperature=0.0)
        words = [{"w": w.word.strip(), "s": s + int(w.start * 1000), "e": s + int(w.end * 1000),
                  "p": round(float(w.probability), 4)}
                 for sg in segs for w in (sg.words or [])]
        res["ayahs"][str(ay)] = {"windowMs": [s, e], "words": words}
        print(f"{a.surah}:{ay} نافذة {s}-{e} ⇒ {len(words)} كلمة", flush=True)
    out = os.path.join(a.out, f"whisper_s{a.surah:03d}.json")
    with open(out + ".part", "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False)
    os.replace(out + ".part", out)
    os.remove(mp3)
    print("كُتب:", out, "· بصمة الصوت", sha[:12])
    return 0


if __name__ == "__main__":
    sys.exit(main())
