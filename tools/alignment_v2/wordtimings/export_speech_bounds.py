# -*- coding: utf-8 -*-
"""حدود **كلام** الكلمات (غير ملصوقة) لعيّنة آيات — لجراحة التسميع (rafiq-tasmi).

المنشور الكلمي ملصوق عمداً (`endsPolicy: contiguous`): الكلمة j = [نهاية j-1، نهاية j]
بعلامات DTW المقيسة. الحقيقة المقيسة عندنا هي **علامة نهاية كل كلمة** فقط؛ أما بدء كلام
الكلمة فليس مقيساً بالنموذج، لكنه محصور: يقع بعد نهاية السابقة وبعد أي صمت يليها.
فنُخرج لكل كلمة:
  · `startMs/endMs`  — الحدّ الملصوق كما نُشر.
  · `speechStartMs`  — أول إطار غير صامت داخل مداها (VAD دقيق 20م.ث، صمت ≥60م.ث).
  · `speechEndMs`    — آخر إطار غير صامت داخل مداها.
  · `leadSilenceMs / tailSilenceMs` — الصمت المقصوص من الطرفين (0 = كلمتان موصولتان،
    وحينها الحدّ الملصوق هو الحدّ الحقيقي بقدر دقة علامة DTW).
⚠️ حيث لا صمت بين كلمتين لا يوجد «حدّ كلام» أدقّ من علامة DTW نفسها — فليست هذه
حدوداً أرضية بل حدود مقيسة بأداة، وينبغي أن يُقاس القصّ بها لا أن يُفترض.

python export_speech_bounds.py --file ../out/wordtimings_husary_qalun.jz --surahs 78-114 \\
    --min-words 4 --max-words 14 --limit 200 --audio-base <قالب mp3> --out ../out/speech_bounds_sample_qalun.json
"""
import argparse
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_V2 = os.path.dirname(_HERE)
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(os.path.dirname(_V2), "alignment"))

from common import read_jz, to_wav16k  # noqa: E402
from vad import silences  # noqa: E402

import build_index as B  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def speech_bounds(sil, s, e):
    """أول/آخر كلام داخل [s,e] بحسب فترات الصمت (مرتبة)."""
    ss, ee = s, e
    for a, b in sil:
        if a <= s < b:            # صمت يغطي البداية
            ss = min(b, e)
        if a < e <= b:            # صمت يغطي النهاية
            ee = max(a, ss)
    return ss, ee


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True, help="ملف التوقيتات الكلمية المنشور")
    ap.add_argument("--surahs", default="78-114")
    ap.add_argument("--min-words", type=int, default=4)
    ap.add_argument("--max-words", type=int, default=14)
    ap.add_argument("--limit", type=int, default=200)
    ap.add_argument("--audio-base", required=True, help="قالب صوت السورة {surah:03d}")
    ap.add_argument("--audio-dir", default=os.path.join(_HERE, "work", "audio_bounds"))
    ap.add_argument("--min-silence-ms", type=int, default=60)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    os.makedirs(args.audio_dir, exist_ok=True)

    doc = read_jz(args.file)
    only = B.parse_range(args.surahs)
    picked = {}
    for e in doc["entries"]:
        sn = int(e["ayahId"].split(":")[0])
        if only and sn not in only:
            continue
        if not (args.min_words <= len(e["words"]) <= args.max_words):
            continue
        picked.setdefault(sn, []).append(e)
    total = sum(len(v) for v in picked.values())
    print("مرشّحة: %d آية في %d سورة (الحدّ %d)" % (total, len(picked), args.limit))

    out, n = [], 0
    stats = {"words": 0, "lead>0": 0, "tail>0": 0, "joined": 0}
    for sn in sorted(picked):
        if n >= args.limit:
            break
        mp3 = os.path.join(args.audio_dir, "%03d.mp3" % sn)
        B.fetch_verified(args.audio_base.format(surah=sn), mp3, log=print)
        wav = to_wav16k(mp3)
        sil = silences(wav, min_silence_ms=args.min_silence_ms)
        for e in picked[sn]:
            if n >= args.limit:
                break
            words = []
            for w in e["words"]:
                ss, ee = speech_bounds(sil, w["startMs"], w["endMs"])
                lead, tail = ss - w["startMs"], w["endMs"] - ee
                stats["words"] += 1
                stats["lead>0"] += lead > 0
                stats["tail>0"] += tail > 0
                stats["joined"] += (lead == 0 and tail == 0)
                words.append(dict(w, speechStartMs=ss, speechEndMs=ee,
                                  leadSilenceMs=lead, tailSilenceMs=tail))
            out.append({"ayahId": e["ayahId"], "evidence": e.get("evidence"), "words": words})
            n += 1
        for p in (mp3, wav):
            if os.path.exists(p):
                os.remove(p)
        print("سورة %d: %d آية (الإجمالي %d)" % (sn, len(picked[sn]), n), flush=True)

    res = {"schema": 1, "riwaya": doc["riwaya"], "reciterId": doc["reciterId"],
           "source": os.path.basename(args.file), "generatedAgainst": doc.get("generatedAgainst"),
           "timeBase": doc.get("timeBase", "SURAH_FILE"),
           "method": "published contiguous cuts + fine VAD (20ms frames, min silence %dms) "
                     "inside each word span; speechStart/End are VAD-trimmed, not model-measured"
                     % args.min_silence_ms,
           "stats": stats, "entries": out}
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False)
    print("كُتب %s — %d آية · %d كلمة · صمت أمامي>0: %d · صمت خلفي>0: %d · موصولة: %d"
          % (args.out, len(out), stats["words"], stats["lead>0"], stats["tail>0"], stats["joined"]))


if __name__ == "__main__":
    main()
