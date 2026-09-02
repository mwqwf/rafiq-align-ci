# -*- coding: utf-8 -*-
"""مسبار البسملة: يقصّ 12ث من مطلع الآية الأولى ويفرّغها **بطوابع كلمية**،
فيُعرف موضع نهاية البسملة برهاناً لا تقديراً.

يُنفَّذ على الخادم. لكل بند: {reciter, surah, url, startMs}
المخرج: نهاية آخر كلمة من البسملة، وبداية أول كلمةٍ بعدها، وثقة المطابقة.
"""
import json, os, subprocess, sys, urllib.request
sys.path.insert(0, "/root/QuranRafiq/tools/alignment")
from common import FFMPEG, MODEL_Q8, WHISPER_CLI, norm

W = "/root/basmala"; os.makedirs(W, exist_ok=True)
WIN_MS = 12_000
BAS = norm("بسم الله الرحمن الرحيم").split()


def words_of_clip(mp3, start_ms, tag):
    wav = f"{W}/{tag}.wav"
    subprocess.run([FFMPEG, "-y", "-v", "error", "-ss", f"{start_ms/1000:.3f}",
                    "-i", mp3, "-t", f"{WIN_MS/1000:.3f}", "-ar", "16000",
                    "-ac", "1", wav], check=True)
    base = f"{W}/{tag}"
    r = subprocess.run([WHISPER_CLI, "-m", MODEL_Q8, "-f", wav, "-l", "ar",
                        "-oj", "-ojf", "-ml", "1", "-sow", "-nfa", "-dtw", "tiny",
                        "-of", base, "--no-prints", "-t", "1"],
                       capture_output=True, text=True, timeout=900)
    out = []
    if os.path.exists(base + ".json"):
        d = json.load(open(base + ".json", encoding="utf-8"))
        for seg in d.get("transcription", []):
            w = norm(seg.get("text", ""))
            ts = [t["t_dtw"] for t in seg.get("tokens", []) if t.get("t_dtw", -1) >= 0]
            if w and ts:
                out.append({"w": w, "s": min(ts) * 10, "e": max(ts) * 10})
        os.remove(base + ".json")
    for p in (wav,):
        if os.path.exists(p):
            os.remove(p)
    return out


def main():
    plan = json.load(open(sys.argv[1], encoding="utf-8"))
    res = []
    for it in plan:
        tag = f"{it['reciter']}_{it['surah']:03d}"
        mp3 = f"{W}/{tag}.mp3"
        try:
            if not os.path.exists(mp3):
                urllib.request.urlretrieve(it["url"], mp3)
            ws = words_of_clip(mp3, it["startMs"], tag)
            hit = [i for i, x in enumerate(ws) if x["w"] in BAS]
            row = {"reciter": it["reciter"], "surah": it["surah"],
                   "startMs": it["startMs"],
                   "heard": " ".join(x["w"] for x in ws[:8]),
                   "basmalaWords": len(hit)}
            if len(hit) >= 3 and max(hit) + 1 < len(ws):
                last = ws[max(hit)]
                nxt = ws[max(hit) + 1]
                row["basmalaEndMs"] = it["startMs"] + int(last["e"])
                row["nextWordMs"] = it["startMs"] + int(nxt["s"])
                row["nextWord"] = nxt["w"]
            res.append(row)
            print(json.dumps(row, ensure_ascii=False), flush=True)
        except Exception as e:
            print(json.dumps({"reciter": it["reciter"], "surah": it["surah"],
                              "error": str(e)[:80]}, ensure_ascii=False), flush=True)
        finally:
            if os.path.exists(mp3):
                os.remove(mp3)
    json.dump(res, open(f"{W}/probe_result.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
