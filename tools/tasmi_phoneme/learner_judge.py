#!/usr/bin/env python3
"""⚖️🚨 **الحاكمُ المشحونُ على متعلّمين حقيقيّين** — أوّلُ قياسٍ للاتّهام الكاذب بحكم التطبيق نفسِه.

[[D-724]] قاس **إشارةً فونيميّةً خاماً** (‏GOP) لا حكمَ التطبيق. وهذا يقيس **المسارَ المشحونَ كما هو**:
`local_whisper` (مرآةُ `LongAudioTranscriber`) ⇒ `scorer.score` (مرآةُ `RecitationScorer` المحروسةُ
بالتماثل) — على مادّةِ [[D-722]] بعد تفتيشِ [[D-723]]:

- **194 تلاوةً حكم إنسانٌ بسلامتها** ⇒ كلُّ كلمةٍ يسمّيها الحاكمُ `MISSED`/`SUBSTITUTED`/`ADDED`
  **اتّهامٌ كاذبٌ بشهادة إنسان** — وهي شكوى المالك الأولى، ولم تُقَس قطُّ على متعلّمين حقيقيّين.
- **53 تلاوةً فيها كلمةٌ وسمها إنسانٌ بالخطأ** ⇒ أيكشفها الحاكمُ في موضعها؟

⛔ **ما لا يثبته:** ليس المحاكيَ ولا JNI (يبقى فرقُ الجسر)؛ وهو مرآةُ المحرك المحروسةُ بالتماثل
(`RecitationScorerParityTest`) لا المحرّكَ نفسَه على أندرويد.

    python learner_judge.py --wav work/learner_wav --model shipped --out work/learner_judge.json
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections import Counter

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "tools", "tasmi_bench"))

from learner_check import load_text, skeleton  # noqa: E402
from detect_score import cfg_for               # noqa: E402

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:                        # noqa: BLE001
        pass

SR = 16000
# ⛔ الاتّهامُ حكمٌ على كلمةٍ مرجعيّة: `UNCERTAIN` ليس اتّهاماً (المحرّكُ يقول «غيرُ متبيَّن»)
ACCUSE = {"MISSED", "SUBSTITUTED"}


def read_any(path: str) -> np.ndarray:
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-f", "f32le", "-ac", "1",
                        "-ar", str(SR), "-"], capture_output=True)
    return np.frombuffer(r.stdout, dtype="<f4").astype(np.float32)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--wav", default="tools/tasmi_phoneme/work/learner_wav")
    ap.add_argument("--check", default="tools/tasmi_phoneme/work/learner_check.json")
    ap.add_argument("--model", default="shipped")
    ap.add_argument("--out", default="tools/tasmi_phoneme/work/learner_judge.json")
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--limit", type=int, default=0)
    # 🧱 (نسخةُ المستودع العامّ 2026-10-13) مرآةُ المحرك على CI كما في `tasmi-gate.yml`: `--backend cli` مع
    #    `whisper-cli` والنموذجِ q8 المشحون بعينه — فلا HF ولا torch على العدّاء المجّانيّ.
    ap.add_argument("--backend", default="hf", choices=["hf", "cli"])
    ap.add_argument("--cli", default=os.environ.get("WHISPER_CLI", ""), help="مسارُ whisper-cli مع --backend cli")
    ap.add_argument("--lang", default="en", help="رمزُ لغة الفكّ مع --backend cli (en = ما يفعله المحرك اليوم)")
    a = ap.parse_args()

    import local_whisper as lw
    import scorer as sc

    path = lw.MODELS.get(a.model, a.model)
    tr = lw.Transcriber(path, threads=a.threads, backend=a.backend, cli=a.cli or None, lang=a.lang)

    chk = {(u["recording_id"], u["ref"]): u
           for u in json.load(open(a.check, encoding="utf-8"))["anchored"]}
    man = json.load(open(os.path.join(a.wav, "manifest.json"), encoding="utf-8"))
    items = [it for it in man["items"] if (it["recording_id"], it["ref"]) in chk]
    if a.limit:
        items = items[:a.limit]

    texts, rows, skipped = {}, [], Counter()
    for n, it in enumerate(items, 1):
        u = chk[(it["recording_id"], it["ref"])]
        r, flat = u["riwaya"], u["flat"]
        if r not in texts:
            texts[r] = load_text(r)
        ref_words = texts[r][flat].split()
        audio = read_any(os.path.join(a.wav, it["wav"]))
        if len(audio) < SR // 4:
            skipped["صوتٌ أقصرُ من رُبع ثانية"] += 1
            continue
        hyp = tr.transcribe(audio)
        hyp = hyp[0] if isinstance(hyp, tuple) else hyp
        # ⚠️ [[D-728]]: كان هنا `sc.score(ref_words, hyp)` بالإعداد الافتراضيّ ⇒ **قالونُ يُحاكَم
        # بمسطرة حفص** (لا صلةَ ميمٍ) أشدَّ ممّا يُشحن. والصوابُ ملفُّ الرواية كما في المحرك.
        res = sc.score(ref_words, hyp, cfg_for(r))
        marked = {skeleton(e["word"]) for e in u["errors"]}
        per_word = []
        for wi, tup in enumerate(res["words"]):
            st = tup[1] if isinstance(tup, (list, tuple)) else str(tup)
            per_word.append({"w": wi, "status": st,
                             "human_error": (wi < len(ref_words)
                                             and skeleton(ref_words[wi]) in marked)})
        rows.append({"rec": it["recording_id"], "ref": it["ref"], "riwaya": r,
                     "kind": u["kind"], "n_ref": len(ref_words), "hyp": hyp,
                     "additions": len(res.get("additions") or []), "words": per_word})
        if n % 20 == 0:
            print(f"  {n}/{len(items)}", flush=True)

    # ⛔ الاتّهامُ الكاذبُ يُحسب على **الصفوف السليمة وحدَها** — جاراتُ الكلمةِ المخطوءة لم
    # يحكم بسلامتها إنسان، فلا تُعدّ سالباً.
    clean = [r for r in rows if r["kind"] == "سالب"]
    dirty = [r for r in rows if r["kind"] == "موجب"]
    fa_words = sum(1 for r in clean for w in r["words"] if w["status"] in ACCUSE)
    tot_words = sum(len(r["words"]) for r in clean)
    fa_recs = sum(1 for r in clean if any(w["status"] in ACCUSE for w in r["words"]))
    hit = sum(1 for r in dirty for w in r["words"] if w["human_error"] and w["status"] in ACCUSE)
    hit_tot = sum(1 for r in dirty for w in r["words"] if w["human_error"])
    rec_hit = sum(1 for r in dirty if any(w["human_error"] and w["status"] in ACCUSE for w in r["words"]))
    status_mix = Counter(w["status"] for r in clean for w in r["words"])
    adds_clean = sum(r.get("additions", 0) for r in clean)

    res = {
        "model": a.model, "recordings": len(rows),
        "clean_recordings": len(clean), "clean_words": tot_words,
        "false_accused_words": fa_words,
        "false_accusation_word_pct": round(100.0 * fa_words / max(1, tot_words), 2),
        "clean_recordings_with_any_accusation": fa_recs,
        "false_accusation_recording_pct": round(100.0 * fa_recs / max(1, len(clean)), 1),
        "status_mix_on_clean": dict(status_mix), "additions_on_clean": adds_clean,
        "marked_recordings": len(dirty), "marked_words": hit_tot,
        "detected_words": hit,
        "detection_word_pct": round(100.0 * hit / max(1, hit_tot), 1),
        "detection_recording_pct": round(100.0 * rec_hit / max(1, len(dirty)), 1),
        "skipped": dict(skipped), "rows": rows,
    }
    json.dump(res, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    print(f"\nتسجيلاتٌ {len(rows)} (سليمٌ {len(clean)} · موسومٌ بخطأ {len(dirty)})")
    print(f"🚨 **الاتّهامُ الكاذب**: {fa_words} من {tot_words} كلمةً = "
          f"**{res['false_accusation_word_pct']}٪** · وتسجيلاتٌ سليمةٌ اتُّهم فيها شيءٌ: "
          f"{fa_recs}/{len(clean)} = {res['false_accusation_recording_pct']}٪")
    print(f"   توزيعُ الأحكام على السليم: {dict(status_mix)}")
    print(f"✅ **الكشف**: {hit}/{hit_tot} كلمةً = {res['detection_word_pct']}٪ "
          f"· وتسجيلاتٌ كُشف فيها الخطأ: {res['detection_recording_pct']}٪")
    if skipped:
        print("مُسقَطات:", dict(skipped))
    print("⛔ مرآةُ المحرك المحروسةُ بالتماثل — لا المحاكي ولا JNI")
    return 0


if __name__ == "__main__":
    sys.exit(main())
