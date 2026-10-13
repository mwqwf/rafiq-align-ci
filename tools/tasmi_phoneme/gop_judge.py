#!/usr/bin/env python3
"""⚖️🔤 **الحَكَمُ الفونيميّ — «جودةُ النطق» لكلّ كلمة (GOP) مقارَناً بـ`whisper` على كلمات المتعلّمين عينِها** ([[D-756]]).

**السؤالُ الذي وُجد له** ([[D-754]]): «النموذجُ الجامع» لا يُغني عن `whisper` إلّا إن **حَكَم على التسميع**
مثلَه أو أحسن. و`whisper` يُخرج نصّاً يُحكم عليه بمحرّك التطبيق؛ والنموذجُ الفونيميُّ يُخرج **احتمالات أصوات** ⇒
فالحَكَمُ هنا: يُحاذى النصُّ المتوقَّع (`QuranG2P` بالرواية) قسراً، ولكلّ رمزٍ في كلّ كلمة:

    GOP(رمز) = متوسّطُ الإطاراتِ التي احتلّها [ log p(الرمزِ المتوقَّع) − max log p(أيِّ رمز) ]   ≤ 0

وGOP الكلمة = **متوسّطُ** رموزها (ويُحفظ الأدنى أيضاً). والكلمةُ **تُتّهم** إن نزل GOP عن عتبةٍ θ.

⛔ **ولا تُضبط θ على ما يُقاس** — وهذا شرطُ المقارنة العادلة:
- θ تُشتقّ **من الكلمات السليمة وحدَها** (تسجيلاتٌ `سالب` مراجَعةٌ بلا خطأ) لتطابق نسبةَ اتّهام `whisper` الكاذب
  (11.56٪ المشحون · 6.91٪ الأكبر — [[D-734]]) ثمّ **يُقاس الكشفُ على كلمات الخطأ وحدَها** (`human_error`).
  ⇒ المجموعتان منفصلتان، فالكشفُ لم يَرَه اختيارُ العتبة.
- وعيّنةُ الخطأ صغيرةٌ (‏[[D-735]]: 70 كلمةً موسومة) ⇒ **مجالُ ويلسون يُطبع مع كلّ نسبة**، ولا يُعلن فرقٌ لا يفصله.

    python gop_judge.py --model <مجلّد torch> [--onnx <ملف>] --labels g2p_labels.jsonl --index index.jz \
        --judge docs/qa/tasmi_2026-09-20/learner_judge.json --wav-dir work/tasmi/learner_wav --out gop.json
"""
from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from ctc_align import align                     # noqa: E402  — المسطرةُ نفسُها التي قِيس بها الهدهد
from ctc_train import surah_starts              # noqa: E402

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:                          # noqa: BLE001
        pass

WHISPER_POINTS = {"whisper-tiny (المشحون)": (11.56, 25.5), "whisper-base (الأكبر)": (6.91, 15.7)}   # [[D-734]]


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (100 * (c - h), 100 * (c + h))


def load_audio(path: str) -> np.ndarray:
    """ffmpeg ⇐ 16 ك.هـ أحاديّ float32 — أيًّا كانت صيغةُ المصدر (مجموعةُ المتعلّمين ليست كلُّها 16 ك.هـ)."""
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-f", "f32le", "-ac", "1", "-ar", "16000", "-"],
                       capture_output=True, check=True)
    return np.frombuffer(r.stdout, dtype=np.float32).copy()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", help="مجلّدُ torch (المفرداتُ والإعدادُ منه) — أو `--vocab` مع `--onnx` بلا torch")
    ap.add_argument("--vocab", help="vocab.json لتشغيل ONNX وحده بلا torch (الفراغ = `--blank`)")
    ap.add_argument("--blank", type=int, default=0)
    ap.add_argument("--onnx", help="تُؤخذ المخرَجاتُ من ONNX بدل torch")
    ap.add_argument("--labels", required=True)
    ap.add_argument("--index", required=True)
    ap.add_argument("--judge", required=True, help="learner_judge.json — الصفوفُ وحكمُ الإنسان لكلّ كلمة")
    ap.add_argument("--wav-dir", required=True, help="مجلّدُ learner_fetch.py (فيه manifest.json)")
    ap.add_argument("--label", default="phoneme")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    model, blank = None, a.blank
    if a.model:
        import torch
        from transformers import Wav2Vec2ForCTC
        model = Wav2Vec2ForCTC.from_pretrained(a.model).eval()
        vocab = json.load(open(os.path.join(a.model, "vocab.json"), encoding="utf-8"))
        blank = model.config.pad_token_id or 0
    elif a.onnx and a.vocab:
        vocab = json.load(open(a.vocab, encoding="utf-8"))
    else:
        ap.error("--model أو (--onnx و--vocab)")
    sess = None
    if a.onnx:
        import onnxruntime as ort
        sess = ort.InferenceSession(a.onnx, providers=["CPUExecutionProvider"])

    starts = surah_starts(a.index)
    g2p = {}
    for line in open(a.labels, encoding="utf-8"):
        d = json.loads(line)
        g2p[(d["r"], d["flat"])] = d["words"]

    man = json.load(open(os.path.join(a.wav_dir, "manifest.json"), encoding="utf-8"))
    wav_of = {(it["recording_id"], it["ref"]): os.path.join(a.wav_dir, it["wav"]) for it in man["items"]}
    judge = json.load(open(a.judge, encoding="utf-8"))

    out_rows, skipped = [], {}
    for r in judge["rows"]:
        key = (r["rec"], r["ref"])
        path = wav_of.get(key)
        why = None
        s, ay = (int(x) for x in r["ref"].split(":"))
        words = g2p.get((r.get("riwaya") or "hafs", starts[s - 1] + ay - 1))
        if path is None or not os.path.isfile(path):
            why = "no audio"
        elif not words or len(words) != r["n_ref"]:
            why = "word count"
        target, owner = [], []
        if not why:
            for wi, w in enumerate(words):
                for ph in w:
                    if ph not in vocab:
                        why = "phoneme not in vocab"
                        break
                    target.append(vocab[ph]); owner.append(wi)
                if why:
                    break
        if why:
            skipped[why] = skipped.get(why, 0) + 1
            continue
        wav = load_audio(path)
        if sess is not None:
            logits = sess.run(None, {sess.get_inputs()[0].name: wav[None, :]})[0][0]
            x = logits.astype(np.float64)
            lp = x - (x.max(-1, keepdims=True) + np.log(np.exp(x - x.max(-1, keepdims=True)).sum(-1, keepdims=True)))
        else:
            with torch.no_grad():
                lp = torch.log_softmax(model(torch.from_numpy(wav)[None]).logits[0].double(), -1).numpy()
        try:
            spans, _ = align(lp, target, blank=blank)
        except ValueError as e:
            skipped[f"align: {e}"] = skipped.get(f"align: {e}", 0) + 1
            continue
        best = lp.max(axis=1)
        per_word = [[] for _ in words]
        for sp, wi in zip(spans, owner):
            fr = slice(sp.start_frame, sp.end_frame)
            per_word[wi].append(float(np.mean(lp[fr, sp.token_id] - best[fr])))
        gops = [{"w": wi, "gop_mean": float(np.mean(g)), "gop_min": float(np.min(g)),
                 "ph": [round(x, 4) for x in g], "ph_sym": [w_ph for w_ph in words[wi]],
                 "human_error": bool(r["words"][wi]["human_error"]) if wi < len(r["words"]) else None,
                 "whisper_status": r["words"][wi]["status"] if wi < len(r["words"]) else None}
                for wi, g in enumerate(per_word)]
        out_rows.append({"rec": r["rec"], "ref": r["ref"], "kind": r.get("kind"), "words": gops})
        print(f"{r['ref']:>8} {r.get('kind')}: " + " ".join(f"{g['gop_mean']:.2f}" for g in gops), flush=True)

    # ⚖️ المجموعتان المنفصلتان — و`whisper` يُحسب **على الصفوف نفسِها** لا من أرقامه المنشورة:
    #    فإن أُسقطت صفوفٌ هنا (صوتٌ مفقود · محاذاةٌ مستحيلة) لم تُقارَن عيّنتان مختلفتان.
    ACCUSE = {"MISSED", "SUBSTITUTED"}
    cw = [w for row in out_rows if row["kind"] == "سالب" for w in row["words"] if w["human_error"] is False]
    ew = [w for row in out_rows for w in row["words"] if w["human_error"] is True]
    clean = [w["gop_mean"] for w in cw]
    errs = [w["gop_mean"] for w in ew]
    res = {"label": a.label, "rows": len(out_rows), "skipped": skipped,
           "clean_words": len(clean), "error_words": len(errs), "points": {}}
    print(f"\n⚖️ {a.label}: {len(out_rows)} صفّاً · كلماتٌ سليمة {len(clean)} · كلماتُ خطأ {len(errs)} · مُسقَط {skipped}")
    if clean and errs:
        w_fa = 100 * sum(1 for w in cw if w["whisper_status"] in ACCUSE) / len(cw)
        w_det_k = sum(1 for w in ew if w["whisper_status"] in ACCUSE)
        wl, wh = wilson(w_det_k, len(ew))
        res["whisperSameRows"] = {"falseAccusePct": round(w_fa, 2), "detectPct": round(100 * w_det_k / len(ew), 1),
                                  "detectWilson95": [round(wl, 1), round(wh, 1)]}
        print(f"  ⚙️ ضابط — whisper على الصفوف نفسِها: اتّهامٌ كاذبٌ {w_fa:.2f}٪ · كشفٌ {100*w_det_k/len(ew):.1f}٪ "
              f"[{wl:.1f}..{wh:.1f}] (المنشورُ في D-734: 11.56٪ · 25.5٪)")
        cs = np.sort(np.array(clean))
        for name, fa in (("مثل whisper على هذه الصفوف", w_fa), *((n, v[0]) for n, v in WHISPER_POINTS.items())):
            k = max(0, min(len(cs) - 1, int(math.floor(fa / 100 * len(cs)))))
            theta = float(cs[k])                     # يتّهم ما دونها ⇒ نسبةُ الاتّهام على السليم ≈ fa
            fa_got = sum(1 for g in clean if g < theta)
            det = sum(1 for g in errs if g < theta)
            lo, hi = wilson(det, len(errs))
            res["points"][name] = {"targetFalseAccusePct": round(fa, 2), "theta": theta,
                                   "falseAccusePct": round(100 * fa_got / len(clean), 2),
                                   "detectPct": round(100 * det / len(errs), 1), "detectWilson95": [round(lo, 1), round(hi, 1)]}
            print(f"  عند اتّهامٍ كاذبٍ ≈ {fa:.2f}٪ ({name}): θ={theta:.3f} · فعليّ {100*fa_got/len(clean):.2f}٪ · "
                  f"**كشفٌ {100*det/len(errs):.1f}٪** [{lo:.1f}..{hi:.1f}]")
    else:
        print("⛔ لا مقارنة: إحدى المجموعتَين فارغة — لا يُعلن رقمٌ")
    res["rowsDetail"] = out_rows
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    json.dump(res, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("⇒", a.out)
    print("⛔ الحكمُ البشريُّ هنا مراجِعٌ واحدٌ في 95.7٪ من الصفوف (D-729) · وكلماتُ الخطأ قليلة (D-735) — فالفرقُ لا يُعلن ما لم يفصله مجالُ ويلسون")
    return 0


if __name__ == "__main__":
    sys.exit(main())
