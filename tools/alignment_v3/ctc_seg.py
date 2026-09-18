# -*- coding: utf-8 -*-
"""محرّك `ctc-seg-1`: محاذاةٌ قسريّةٌ للسورة كاملةً إلى نصّ الرواية — **بلا مِرساة**.

لماذا (خطة 2026-09-18 · `QuranRafiq/docs/ops/PLAN_INDEXING_FAST_2026-09-18.md`):
الثمانيةَ عشرَ الباقون رُدّوا كلُّهم بعَرَضٍ واحدٍ مكتوبٍ في أحكامهم: «الغيابُ منحازٌ
إلى القصار» و«بسملاتٌ مبتلعة». وهذا عيبُ «فرِّغ ثمّ طابِق» (Whisper) بطبيعته.
هنا لا تفريغ: كلُّ آيةٍ من النصّ الذي نملكه **مفروضةٌ** في المسار، فلا تُبتلع.

والفرقُ عن الذراع (ج) `ctc_windows.py`: تلك تحتاج فهرسَ v2.1 مِرساةً، وأصحابُنا
مِرساتُهم هي المعطوبة. و`ctc_segmentation` يحاذي الساعاتِ الطوال بنافذةٍ منزلقة
بلا شبكة T×N كاملة.

⛔ **AI لا يولّد قرآناً:** النموذجُ يُعطي أزمنةً لنصٍّ نملكه، ولا يُشحن منه حرف.
⛔ **HIGH لا تُمنح إلا ببرهان صمت (D-025)** كالمسار القائم تماماً.
⛔ والحكمُ الحاسم للبوّابة الصوتيّة (openers + أربعة ملوح + عتبة 5%) لا لهذا الملف.

النموذج: `jonatasgrosman/wav2vec2-large-xlsr-53-arabic` (Apache-2.0).
⛔ `facebook/mms-*` مرفوض: CC-BY-NC-4.0 (D-703).
"""
from __future__ import annotations

import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "alignment"))

from common import (ffprobe_duration_ms, load_index, load_text, norm,  # noqa: E402
                    surah_slice, to_wav16k)
from validate import band, check_surah  # noqa: E402
from vad import read_wav, silences, snap_to_silence  # noqa: E402

ENGINE = "ctc-seg-1"
MODEL_ID = os.environ.get("CTC_MODEL", "jonatasgrosman/wav2vec2-large-xlsr-53-arabic")
BASMALA = "بسم الله الرحمن الرحيم"
SR = 16000
WIN_S = 30          # نافذةُ الاستخراج؛ مخرجاتُها تُلصق (الحقلُ الاستقباليّ ~25م.ث)

_M = {}


def _model():
    if not _M:
        import torch
        from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor
        torch.set_num_threads(int(os.environ.get("CTC_THREADS", os.cpu_count() or 1)))
        proc = Wav2Vec2Processor.from_pretrained(MODEL_ID)
        mdl = Wav2Vec2ForCTC.from_pretrained(MODEL_ID).eval()
        if os.environ.get("CTC_INT8", "1") == "1":
            mdl = torch.quantization.quantize_dynamic(mdl, {torch.nn.Linear}, dtype=torch.qint8)
        _M.update(proc=proc, mdl=mdl, torch=torch)
    return _M


def _emissions(x):
    m = _model()
    torch, proc, mdl = m["torch"], m["proc"], m["mdl"]
    out, step = [], SR * WIN_S
    with torch.inference_mode():
        for i in range(0, len(x), step):
            c = x[i:i + step]
            if len(c) < SR // 10:
                break
            iv = proc(c, sampling_rate=SR, return_tensors="pt").input_values
            out.append(torch.log_softmax(mdl(iv).logits[0], dim=-1).numpy())
    return np.concatenate(out)


def _segment(lpz, n_samples, texts):
    import ctc_segmentation as cs
    tok = _model()["proc"].tokenizer
    vocab = tok.get_vocab()
    char_list = [None] * len(vocab)
    for ch, i in vocab.items():
        char_list[i] = ch
    unk = tok.unk_token_id
    blank = tok.pad_token_id
    tokens = []
    for t in texts:
        ids = [i for i in tok(t).input_ids if i not in (unk, blank)]
        if not ids:
            raise RuntimeError(f"نصٌّ بلا رموز في المفردات: {t[:30]!r}")
        tokens.append(np.array(ids))
    cfg = cs.CtcSegmentationParameters(char_list=char_list)
    cfg.index_duration = n_samples / lpz.shape[0] / SR
    cfg.blank = blank
    gt, utt = cs.prepare_token_list(cfg, tokens)
    timings, char_probs, _ = cs.ctc_segmentation(cfg, lpz, gt)
    return cs.determine_utterance_segments(cfg, utt, char_probs, timings, texts)


def _conf(score):
    """درجةُ ctc_segmentation لوغاريتمٌ ≤0 (أدنى متوسّطٍ في نافذة). ⇒ [0،1].
    ‏−1 ⇒ 0.75 (حدّ HIGH) · −2.2 ⇒ 0.45 (حدّ MED)."""
    return round(max(0.0, min(1.0, 1.0 + 0.25 * float(score))), 3)


def run_surah(audio_path, surah_no, riwaya, log=print):
    index = load_index()
    a, b, s = surah_slice(index, surah_no)
    ref = [norm(t) for t in load_text(riwaya)[a:b]]
    wav = to_wav16k(audio_path)
    total_ms = ffprobe_duration_ms(audio_path)
    x = read_wav(wav).astype(np.float32)
    lead = [] if surah_no in (1, 9) else [BASMALA]
    segs = _segment(_emissions(x), len(x), lead + ref)[len(lead):]
    sil = silences(wav)
    entries = []
    for ai, (st, en, sc) in enumerate(segs):
        t, on_sil = snap_to_silence(int(st * 1000), sil, tolerance_ms=700)
        entries.append({"ayahIdx": ai, "startMs": int(t), "endMs": int(en * 1000),
                        "conf": _conf(sc), "snapped": bool(on_sil),
                        "matched": 0, "total": len(ref[ai].split())})
    # الحدُّ واحدٌ بين آيتين متجاورتين: نهايةُ الآية = بدايةُ التالية.
    for k in range(len(entries) - 1):
        entries[k]["endMs"] = entries[k + 1]["startMs"]
    if entries:
        entries[-1]["endMs"] = min(max(entries[-1]["endMs"], entries[-1]["startMs"] + 1), total_ms)
    for e in entries:
        if e["endMs"] <= e["startMs"]:
            e.update(startMs=None, endMs=None, conf=0.0)
        elif not e["snapped"]:
            e["conf"] = min(e["conf"], 0.74)   # ⛔ D-025: لا HIGH بلا صمت
    issues = check_surah(entries, [len(t.replace(" ", "")) for t in ref], total_ms)
    bands = {}
    for e in entries:
        k = band(e["conf"]) if e["startMs"] is not None else "MISSING"
        bands[k] = bands.get(k, 0) + 1
    log(f"سورة {surah_no}: {bands} · {len(issues)} مخالفة")
    return {"surah": surah_no, "riwaya": riwaya, "totalMs": total_ms,
            "entries": entries, "issues": issues, "bands": bands}


if __name__ == "__main__":
    import argparse
    import json
    ap = argparse.ArgumentParser()
    ap.add_argument("--audio", required=True)
    ap.add_argument("--surah", type=int, required=True)
    ap.add_argument("--riwaya", default="hafs")
    a = ap.parse_args()
    r = run_surah(a.audio, a.surah, a.riwaya)
    print(json.dumps([(e["ayahIdx"] + 1, e["startMs"], e["endMs"], e["conf"]) for e in r["entries"]]))
