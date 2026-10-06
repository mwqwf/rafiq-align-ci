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
from spoken_letters import alignment_text  # noqa: E402

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
    # سقفُ النافذة الافتراضيّ (64000 إطار) أسقط سوراً طويلةً حتميّاً (يوسف عند bilal).
    # يُرفع إلى طول الصوت كلّه ما دام جدولُ الترصيد (نافذة × رموز × 4ب) دون ~4ج.ب.
    cfg.max_window_size = max(cfg.max_window_size,
                              min(lpz.shape[0], int(4e9 // (4 * max(len(gt), 1)))))
    timings, char_probs, _ = cs.ctc_segmentation(cfg, lpz, gt)
    return cs.determine_utterance_segments(cfg, utt, char_probs, timings, texts)


def _segment_overlapping_groups(lpz, n_samples, texts, leading_count, group_size, overlap,
                                prior_context_seconds=120.0):
    """Align bounded overlapping verse groups in a measured forward chain.

    The first group sees the full recording.  Each later group sees the suffix
    beginning before the previous group's measured overlap.  Repeated overlap
    verses are retained as agreement evidence.  No duration inferred from text
    length is used as an audio bound, and timings are never averaged.
    """
    if not isinstance(leading_count, int) or leading_count < 0 or leading_count > len(texts):
        raise ValueError("invalid leading utterance count")
    if not isinstance(group_size, int) or group_size < 2:
        raise ValueError("group_size must be an integer >= 2")
    if not isinstance(overlap, int) or overlap < 1 or overlap >= group_size:
        raise ValueError("overlap must be an integer in [1, group_size)")
    if not isinstance(prior_context_seconds, (int, float)) or prior_context_seconds <= 0:
        raise ValueError("prior_context_seconds must be positive")
    body = texts[leading_count:]
    if not body:
        return [], {"groupSize": group_size, "overlap": overlap, "groups": [],
                    "overlapAyahs": [], "maxStartDisagreementSeconds": 0.0,
                    "maxEndDisagreementSeconds": 0.0}

    claims = [[] for _ in body]
    groups = []
    start = 0
    previous = None
    frame_seconds = n_samples / lpz.shape[0] / SR
    while start < len(body):
        end = min(len(body), start + group_size)
        group_lead = texts[:leading_count] if start == 0 else []
        group_texts = group_lead + body[start:end]
        frame_start = 0
        if previous is not None:
            anchor_seconds = min(float(segment[0]) for segment in previous[-overlap:])
            frame_start = max(0, int((anchor_seconds - prior_context_seconds) / frame_seconds))
        group_lpz = lpz[frame_start:]
        group_samples = int(round(n_samples * len(group_lpz) / len(lpz)))
        relative = _segment(group_lpz, group_samples, group_texts)[len(group_lead):]
        time_offset = frame_start * frame_seconds
        measured = [(float(st) + time_offset, float(en) + time_offset, score)
                    for st, en, score in relative]
        if len(measured) != end - start:
            raise RuntimeError("group alignment returned an incomplete verse population")
        groups.append({"startAyahIdx": start, "endAyahIdxExclusive": end,
                       "verseCount": end - start,
                       "audioStartSeconds": round(time_offset, 6)})
        for offset, segment in enumerate(measured):
            claims[start + offset].append({"groupStartAyahIdx": start,
                                           "groupEndAyahIdxExclusive": end,
                                           "segment": segment})
        if end == len(body):
            break
        previous = measured
        start = end - overlap

    merged = []
    overlap_ayahs = []
    max_start_delta = 0.0
    max_end_delta = 0.0
    for ayah_idx, alternatives in enumerate(claims):
        if not alternatives:
            raise RuntimeError(f"verse {ayah_idx + 1} has no group alignment")
        # Prefer the claim with the most verse context on its thinner side.
        # This selects one measured boundary; it never averages two timings.
        chosen = max(alternatives, key=lambda item: min(
            ayah_idx - item["groupStartAyahIdx"],
            item["groupEndAyahIdxExclusive"] - 1 - ayah_idx,
        ))
        merged.append(chosen["segment"])
        if len(alternatives) > 1:
            starts = [float(item["segment"][0]) for item in alternatives]
            ends = [float(item["segment"][1]) for item in alternatives]
            start_delta = max(starts) - min(starts)
            end_delta = max(ends) - min(ends)
            max_start_delta = max(max_start_delta, start_delta)
            max_end_delta = max(max_end_delta, end_delta)
            overlap_ayahs.append({"ayahIdx": ayah_idx,
                                  "claims": len(alternatives),
                                  "startDisagreementSeconds": round(start_delta, 6),
                                  "endDisagreementSeconds": round(end_delta, 6)})
    return merged, {"groupSize": group_size, "overlap": overlap, "groups": groups,
                    "overlapAyahs": overlap_ayahs,
                    "maxStartDisagreementSeconds": round(max_start_delta, 6),
                    "maxEndDisagreementSeconds": round(max_end_delta, 6)}


def _conf(score):
    """درجةُ ctc_segmentation لوغاريتمٌ ≤0 (أدنى متوسّطٍ في نافذة). ⇒ [0،1].
    ‏−1 ⇒ 0.75 (حدّ HIGH) · −2.2 ⇒ 0.45 (حدّ MED)."""
    return round(max(0.0, min(1.0, 1.0 + 0.25 * float(score))), 3)


def run_surah(audio_path, surah_no, riwaya, log=print, spoken_openers=False, omit_basmala=False,
              quran_model=False, chunk_verses=None, chunk_overlap=4):
    if _M.get('alignmentModelId') and not quran_model:
        raise ValueError('Loaded Quran model requires its explicit engine flag')
    index = load_index()
    a, b, s = surah_slice(index, surah_no)
    canonical = load_text(riwaya)[a:b]
    model_evidence = None
    if quran_model:
        if spoken_openers:
            raise ValueError('Quran script and spelled-letter inputs are separate engines')
        import quran_ctc_model as Q
        model_evidence = Q.configure()
    ref = [Q.reference_text(t) if quran_model else
           alignment_text(surah_no, i + 1, t) if spoken_openers else norm(t)
           for i, t in enumerate(canonical)]
    wav = to_wav16k(audio_path)
    total_ms = ffprobe_duration_ms(audio_path)
    x = read_wav(wav).astype(np.float32)
    lead = [] if surah_no in (1, 9) or omit_basmala else [BASMALA]
    if quran_model and lead:
        lead = [Q.reference_text('بِسْمِ اللَّهِ الرَّحْمَٰنِ الرَّحِيمِ')]
    lpz = _emissions(x)
    chunk_evidence = None
    if chunk_verses is None:
        segs = _segment(lpz, len(x), lead + ref)[len(lead):]
    else:
        segs, chunk_evidence = _segment_overlapping_groups(
            lpz, len(x), lead + ref, len(lead), chunk_verses, chunk_overlap)
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
    issues = check_surah(entries, [len(norm(t).replace(" ", "")) for t in canonical], total_ms)
    bands = {}
    for e in entries:
        k = band(e["conf"]) if e["startMs"] is not None else "MISSING"
        bands[k] = bands.get(k, 0) + 1
    log(f"سورة {surah_no}: {bands} · {len(issues)} مخالفة")
    return {"surah": surah_no, "riwaya": riwaya, "totalMs": total_ms,
            "entries": entries, "issues": issues, "bands": bands,
            **({"chunkedAlignment": chunk_evidence} if chunk_evidence is not None else {}),
            **({'engine': 'ctc-quran-surah-1', 'alignmentModel': model_evidence} if quran_model else {}),
            **({"basmalaOmitted": True} if omit_basmala else {})}


if __name__ == "__main__":
    import argparse
    import json
    ap = argparse.ArgumentParser()
    ap.add_argument("--audio", required=True)
    ap.add_argument("--surah", type=int, required=True)
    ap.add_argument("--riwaya", default="hafs")
    ap.add_argument("--spoken-openers", action="store_true", help="تهجئة الحروف للمحاذاة فقط؛ تجربة صريحة لا تغيّر الوصفة الافتراضية")
    ap.add_argument("--quran-model", action="store_true")
    ap.add_argument("--omit-basmala", action="store_true", help="تسجيل مثبت صوتياً بلا بسملة؛ حذفها من مدخل المحاذاة فقط")
    a = ap.parse_args()
    r = run_surah(a.audio, a.surah, a.riwaya, spoken_openers=a.spoken_openers, omit_basmala=a.omit_basmala,
                  quran_model=a.quran_model)
    print(json.dumps([(e["ayahIdx"] + 1, e["startMs"], e["endMs"], e["conf"]) for e in r["entries"]]))
