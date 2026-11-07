#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""قياسُ الباب الثالث (‏آيةٌ مكرّرةٌ مشهودة) لسورةٍ واحدة بعد أن قِيست خريطةُ العامّة فيها.

    python tools/index_qa/heard_repeat_probe.py --url <mp3> --surah 67 --riwaya qalun --dir hg/x --cand cand.json

`--dir` فيه `heard_sNNN.json` (‏خريطةُ العامّة) و`NNN.mp3` (‏الصوتُ نفسُه الذي قِيست عليه الخريطة). `cand.json`: {"sha": بصمةُ المرشّح،
"ends": {"آية": [بدء، نهاية]}}. يحسب من الخريطة الآياتِ المنحرفةَ ذواتِ التكرار المقيس (‏`heard_gate.repeat_plan` — لا من المُطلِق)،
فإن وُجدت كتب:
  rw/whisper_sNNN.json  شاهدُ Whisper (‏medium float32) لنوافذها: من البدء المنشور − WIT_PAD_MS (‏`witness_windows` نفسُها)
  rc/census_sNNN.json   كلماتُ Whisper (‏small float32) لنافذة مدخل كلٍّ منها [startMs, endMs] — مادّةُ إحصاء النوافذ، والحكمُ يُعاد منها
وإلا لا شيء. ⛔ لا رفعَ ولا كتابةَ في دلو ولا state؛ والحكمُ يُعاد في `heard_gate.judge` ولا يُقرأ من هذين الملفّين حكمٌ."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
import heard_gate as H  # noqa: E402

SR = 16000


def census_words(model, pcm, st: int, en: int) -> list[dict]:
    """كلماتُ Whisper لنافذة المدخل [st, en] بمعاملات `entry_window_census.cmd_run` نفسِها (‏beam 5 · temperature 0 · بلا VAD)."""
    seg = pcm[int(st * SR / 1000):int(int(en) * SR / 1000)]
    segs, _i = model.transcribe(seg, language="ar", beam_size=5, word_timestamps=True,
                                condition_on_previous_text=False, vad_filter=False, temperature=0.0)
    return [{"w": x.word.strip(), "s": st + int(x.start * 1000), "p": round(float(x.probability), 4)}
            for sg in segs for x in (sg.words or [])]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--url", required=True)
    ap.add_argument("--surah", type=int, required=True)
    ap.add_argument("--riwaya", required=True)
    ap.add_argument("--dir", required=True)
    ap.add_argument("--cand", required=True, help="ملفُّ JSON: sha وends")
    ap.add_argument("--witness-model", default="medium", choices=("small", "medium"))
    ap.add_argument("--census-model", default="small", choices=("small", "medium"))
    a = ap.parse_args()
    d = Path(a.dir)
    s3 = f"{a.surah:03d}"
    gp = d / f"heard_s{s3}.json"
    if not gp.exists():
        print(f"⚠️ س{a.surah}: لا خريطةَ عامّةٍ في {d} — لا باب ثالث")
        return 0
    cand = json.load(open(a.cand, encoding="utf-8"))
    ends = {int(k): v for k, v in cand["ends"].items()}
    starts = {k: v[0] for k, v in ends.items()}
    gm = H.compact_map(json.load(open(gp, encoding="utf-8")))
    plan = H.repeat_plan(starts, gm)
    if not plan:
        print(f"✓ س{a.surah}: لا آيةَ منحرفةً ذاتَ تكرارٍ مقيس — لا شاهدَ ولا إحصاء")
        return 0
    print(f"✓ س{a.surah}: آياتٌ منحرفةٌ ذاتُ تكرارٍ مقيس {len(plan)}: {plan[:40]}")
    dw, dc = d / "rw", d / "rc"
    dw.mkdir(parents=True, exist_ok=True)
    dc.mkdir(parents=True, exist_ok=True)
    rc = subprocess.run([sys.executable, str(HERE / "whisper_witness.py"), "--url", a.url, "--surah", str(a.surah),
                         "--riwaya", a.riwaya, "--ayahs", H.witness_windows(ends, plan), "--model", a.witness_model,
                         "--out", str(dw)], stdin=subprocess.DEVNULL,
                        stdout=subprocess.DEVNULL, stderr=open(dw / f"err_{a.surah}.txt", "w", encoding="utf-8")).returncode
    if rc:
        print(f"⚠️ س{a.surah}: شاهدُ Whisper أخفق ({rc}) — يُحكم بلا شاهد (‏الآياتُ تُردّ)")
    mp3 = d / f"{s3}.mp3"
    if not mp3.exists():
        print(f"⚠️ س{a.surah}: لا ملفَّ صوتٍ ({mp3}) للإحصاء — يُحكم بلا إحصاء (‏الآياتُ تُردّ)")
        return 0
    sha = hashlib.sha256(mp3.read_bytes()).hexdigest()
    sys.path.insert(0, str(ROOT / "tools" / "alignment"))
    from common import to_wav16k  # noqa: PLC0415
    import numpy as np  # noqa: PLC0415
    from faster_whisper import WhisperModel  # noqa: PLC0415
    wav = to_wav16k(str(mp3), os.path.join(tempfile.mkdtemp(), "a.wav"))
    with wave.open(wav, "rb") as w:
        if w.getframerate() != SR or w.getnchannels() != 1:
            raise SystemExit("⛔ الصوتُ المفكوك ليس أحاديَّ 16ك.هز")
        pcm = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768.0
    os.remove(wav)
    model = WhisperModel(a.census_model, device="cpu", compute_type="float32", cpu_threads=os.cpu_count() or 2)
    ents = {}
    for ay in plan:
        st, en = int(ends[ay][0]), ends[ay][1]
        if en is None or int(en) <= st:
            continue                                            # مدخلٌ بلا نهايةٍ صالحة ⇒ لا إحصاءَ له (‏يُردّ)
        ents[str(ay)] = {"startMs": st, "endMs": int(en), "words": census_words(model, pcm, st, int(en))}
        print(f"  إحصاءٌ {a.surah}:{ay} [{st}-{en}] ⇒ {len(ents[str(ay)]['words'])} كلمة", flush=True)
    out = dc / f"census_s{s3}.json"
    res = {"surah": a.surah, "riwaya": a.riwaya, "fileRef": a.url, "sha256": sha, "model": a.census_model,
           "computeType": "float32", "entries": ents}
    with open(str(out) + ".part", "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False)
    os.replace(str(out) + ".part", out)
    print(f"كُتب: {out} · بصمة الصوت {sha[:12]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
