# -*- coding: utf-8 -*-
"""مسبار: هل تعطي whisper-cli طوابع رمزية مفيدة على مقطع قصير (<10ث)؟"""
import json, os, subprocess, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "alignment"))
from common import FFMPEG, MODEL_Q8, WHISPER_CLI, WORK, norm  # noqa

HERE = os.path.dirname(os.path.abspath(__file__))
W2 = os.path.join(HERE, "work")

def run(wav, start_ms, dur_ms, tag, dtw=None):
    os.makedirs(W2, exist_ok=True)
    base = os.path.join(W2, tag)
    clip = base + ".clip.wav"
    subprocess.run([FFMPEG, "-y", "-v", "error", "-i", wav, "-ss", f"{start_ms/1000:.3f}",
                    "-t", f"{dur_ms/1000:.3f}", "-ar", "16000", "-ac", "1", clip], check=True, timeout=60)
    cmd = [WHISPER_CLI, "-m", MODEL_Q8, "-f", clip, "-l", "ar", "-oj", "-ojf",
           "-of", base, "--no-prints", "-ml", "1", "-sow"]
    if dtw:
        cmd += ["-dtw", dtw]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        return {"error": r.stderr[-500:]}
    with open(base + ".json", encoding="utf-8") as f:
        return json.load(f)

if __name__ == "__main__":
    wav, s, d, dtw = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), (sys.argv[4] if len(sys.argv) > 4 else None)
    data = run(wav, s, d, "probe", dtw)
    if "error" in data:
        print(data["error"]); sys.exit(1)
    for seg in data.get("transcription", []):
        off = seg["offsets"]
        toks = seg.get("tokens", [])
        tw = " | ".join(f"{t['text']}@{t['offsets']['from']}-{t['offsets']['to']}" for t in toks) if toks else ""
        print(f"[{off['from']}-{off['to']}] {seg['text'].strip()}   TOKENS: {tw}")
