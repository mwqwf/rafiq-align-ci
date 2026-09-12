# -*- coding: utf-8 -*-
"""🎙️ **مجموعةُ G4 — التلاوةُ الطويلة (عدّةُ آياتٍ في تسجيلٍ واحد)**.

⚠️ **لِمَ وُجدت — وهي أخطرُ ثغرةٍ في القياس كلِّه:** كلُّ مجموعاتنا (‏G1 · G2 · G2b · G3 · G3r)
**آيةٌ واحدةٌ لكلِّ ملفّ**. والمستخدمُ يسجّل **عدّةَ آيات**، وشكواه بنصّها: «أسجّل عدّة آياتٍ
ثم يكتب لي بعضَها كأنّه ناقصُ السمع، وأحياناً في وسط التلاوة نفسِها».

وقياسُ الآية المفردة **لا يرى هذا العطب أصلاً**: نسبةُ ما نُقل إلى ما قُرئ فيها **1.00**
(‏وسيطاً، نظيفاً وضجيجاً). فالضياعُ ليس في التفريغ بل في **مسار الطويل**:
`splitAtSilences` ⇐ `groupUtterances` ⇐ سقفُ المجموعة ⇐ المرساة.

**البناء:** آياتٌ **متتاليةٌ** من السورة نفسِها والقارئ نفسِه، مقطوعةٌ من ملفِّ السورة بحدودها
المقيسة، موصولةٌ بسكتاتٍ واقعيّة. والحقيقةُ الأرضيّة **نصُّها كاملاً بالترتيب** — فالسؤالُ
المقيس: **كم من الكلمات وصلت أصلاً؟** لا كم منها صحّ.

    python tools/tasmi_bench/build_long.py --ayahs 6
"""
import argparse
import gzip
import json
import os
import random
import sys

import numpy as np
import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "tools", "alignment"))

WORK = os.path.join(HERE, "work")
OUT = os.path.join(WORK, "g4")
CACHE = os.path.join(WORK, "g3r_src")
SR = 16_000
SEED = 1446
AUDIO = {
    "warsh": "https://server13.mp3quran.net/husr/Rewayat-Warsh-A-n-Nafi/",
    "qalun": "https://server13.mp3quran.net/husr/Rewayat-Qalon-A-n-Nafi/",
}
# سكتاتٌ واقعيّةٌ بين الآيات — لا صمتٌ مثاليّ: القارئُ يتنفّس ويقف
GAPS_MS = (350, 700, 1200, 1800)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ayahs", type=int, default=6, help="عددُ الآيات في التسجيل الواحد")
    ap.add_argument("--count", type=int, default=30, help="تسجيلاتٌ لكلِّ رواية")
    args = ap.parse_args()

    from common import FFMPEG, load_index, load_text
    import inject_riwaya_local as L

    index = load_index()
    start = {s["n"]: s["start"] for s in index["surahs"]}
    rng = random.Random(SEED)
    os.makedirs(OUT, exist_ok=True)
    items = []

    for riwaya in ("warsh", "qalun"):
        # ⛔ **سقطت ذراعا التلاوة الطويلة في CI بـ`FileNotFoundError: husary_warsh.jz`** (‏2026-09-12):
        # الأداةُ كانت تفترض الطوابعَ موجودةً على القرص، و`inject_riwaya_local.py` لا يُنزّلها
        # (‏الذي يُنزّلها هو `inject_riwaya.py` وهو لا يُشغَّل في مسار المحاكي). فصارت تُنزّلها بنفسها
        # بالدالّة القائمة — أداةٌ لا تكتمل إلا بخطوةٍ في مسارٍ آخرَ تسقط في كلّ مسارٍ سواه.
        import inject_riwaya as IR
        d = IR.load_timings(riwaya, WORK)
        text = load_text(riwaya)
        # فهرسٌ: (سورة، آية) ⇒ حدودُها في ملفِّ السورة، للآيات كاملةِ الشاهد وحدَها
        by = {}
        for e in d["entries"]:
            if not e["evidence"].get("fullEvidence"):
                continue
            s, a = map(int, e["ayahId"].split(":"))
            if s < 78:
                continue
            wb = L.__dict__ and None  # (لا شيء — نستخدم الحدودَ مباشرةً)
            ms = [(w["startMs"], w["endMs"]) for w in e["words"]]
            by[(s, a)] = (min(m[0] for m in ms), max(m[1] for m in ms))

        runs = []
        for (s, a) in sorted(by):
            seq = [(s, a + k) for k in range(args.ayahs)]
            if all(x in by for x in seq):
                runs.append(seq)
        rng.shuffle(runs)

        made = 0
        cache = {}
        for seq in runs:
            if made >= args.count:
                break
            s0 = seq[0][0]
            if s0 not in cache:
                p = L.surah_wav(riwaya, s0, AUDIO[riwaya] + f"{s0:03d}.mp3", FFMPEG)
                cache[s0] = sf.read(p, dtype="float32")[0] if p else None
            full = cache[s0]
            if full is None:
                continue
            parts, ref = [], []
            for i, (s, a) in enumerate(seq):
                a0, b0 = by[(s, a)]
                parts.append(L.sl(full, a0, b0))
                ref += text[start[s] + a - 1].split()
                if i < len(seq) - 1:
                    parts.append(np.zeros(int(rng.choice(GAPS_MS) * SR / 1000), dtype="float32"))
            y = np.concatenate(parts).astype("float32")
            if len(y) < SR:
                continue
            iid = f"long_{riwaya}_{s0:03d}_{seq[0][1]:03d}x{len(seq)}"
            sf.write(os.path.join(OUT, iid + ".wav"), y, SR, subtype="PCM_16")
            items.append({"id": iid, "riwaya": riwaya, "surah": s0,
                          "firstAyah": seq[0][1], "ayahs": len(seq),
                          "refText": " ".join(ref), "wordCount": len(ref),
                          "durationSec": round(len(y) / SR, 1)})
            made += 1

    json.dump({"seed": SEED, "gapsMs": list(GAPS_MS), "items": items},
              open(os.path.join(WORK, "long_plan.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    if items:
        ds = [i["durationSec"] for i in items]
        print(f"✅ {len(items)} تسجيلاً ⇒ {OUT}")
        print(f"   المدّة: وسيط {sorted(ds)[len(ds)//2]:.0f}ث · أقصر {min(ds):.0f}ث · أطول {max(ds):.0f}ث")
        print(f"   الكلمات: وسيط {sorted(i['wordCount'] for i in items)[len(items)//2]}")
    return 0 if items else 1


if __name__ == "__main__":
    raise SystemExit(main())
