#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""الذراع (ج): محاذاةٌ **قسريّة** (CTC forced alignment) بنوافذَ إلى نصّ الرواية.

    python tools/alignment_v3/ctc_windows.py --url https://h/022.mp3 --surah 22 \
        --riwaya hafs --anchor work/parent.jz --model <HF id> --json out/s22.json

## لماذا هذه الذراع (تشخيصُ المشرف github-10، 2026-09-05)

وصفتُنا القائمة **تفرّغ ثم تطابق** (‏whisper-tiny ⇐ Needleman-Wunsch)، فكلُّ
خطأِ تفريغٍ يتسرّب عطباً **متناثراً** — وهو بالضبط شكلُ عطب السبعة عشر
(‏21–58 سورةً لكلٍّ، ونصيبُ أكثر سورتين 10–30%). والمسألةُ عندنا محاذاةُ نصٍّ
**معلوم** إلى صوت، ولها أداتُها القياسية: المحاذاةُ القسرية.

⛔ **ولا يخالف دستور «AI لا يولّد قرآناً»:** النموذج لا يُنتج نصّاً يُشحن —
يُعطي **زمنَ كلِّ كلمةٍ من النصّ الذي نملكه**، والنصُّ مرجعُ الرواية نفسه.

## لماذا نوافذ ولماذا مِرساةٌ من v2.1

`forced_align` يبني شبكةَ ترصيدٍ **T × N**: سورةٌ من ساعةٍ ونصُّها 2500 كلمة
⇒ ‏≈2.2 مليار خلية، **تفجّر ذاكرة العدّاء** لا تُبطئه. فتُقطَّع السورة نوافذَ
من ≈10 آيات، تُؤخذ حدودُها الخشنة من فهرس v2.1 القائم.

⛔ **وليس فيه دَورٌ منطقيّ:** المِرساةُ تحدّد **أين نقرأ** لا **أين الحدّ**؛
والحدُّ النهائيُّ يخرج من CTC وحده. وهامشُ النافذة يبتلع خطأَ المِرساة.
وإن كانت إزاحةُ v2.1 أكبرَ من الهامش ظهر ذلك **بلاغاً** لا قبولاً صامتاً:
النافذةُ تُوسَّع مرّةً، فإن بقي الخللُ وُسمت السورةُ «إزاحةٌ كبيرة» ورُفعت
بالاسم — ومن تجاوزت نوافذُه الموسَّعة 20% فسورتُه مشبوهةٌ كلُّها.

## الحُرّاس

1. **حدودُ النوافذ تقع في صمت** (`vad.silences` ≥300م.ث ضمن ±3ث) لا في وسط كلمة.
2. **كلمةُ سياقٍ من كلّ طرف** تدخل المحاذاة وتُهمل حدودُها — تمتصّ أثر القطع.
3. **حدٌّ خارج نافذته أو ثقةٌ دون العتبة ⇒ توسيعٌ مرّةً (±8ث) ثم إبلاغ.**
4. **الشارة `HIGH` لا تُمنح إلا بحارس الصمت (D-025)** كما في المسار القائم —
   لا شارةَ بلا برهانِ صمت، والقاعدةُ واحدةٌ للمحرّكين.
5. **الوسم `align-0.3-ctc`** — ولا يمسّ هذا المسارُ وصفةَ v2.1 المنشورة بحال.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "tools", "alignment"))

from common import (fetch_retry, load_text, norm, surah_slice,  # noqa: E402
                    to_wav16k, load_index)
from vad import silences, snap_to_silence  # noqa: E402

SR = 16000
CTX_WORDS = 1          # كلمةُ سياقٍ من كل طرف — تُهمل حدودُها
WIN_AYAT = 10
MARGIN_MS = 3000
EXPAND_MS = 8000
MIN_SIL_MS = 300


def _ms(frame, ratio):
    return int(frame * ratio * 1000 / SR)


def load_model(model_id):
    """يُرجع (‏معالج، نموذج، معجم) — ويُثبت أن مفردات النموذج تغطي حروفنا."""
    import torch
    from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor
    proc = Wav2Vec2Processor.from_pretrained(model_id)
    mdl = Wav2Vec2ForCTC.from_pretrained(model_id).eval()
    torch.set_num_threads(int(os.environ.get("CTC_THREADS", "4")))
    vocab = proc.tokenizer.get_vocab()
    return proc, mdl, vocab


def coverage(vocab, words):
    """نسبةُ الحروف التي يعرفها المعجم — **يُفحص قبل التشغيل** (أمر المشرف)."""
    chars = {ch for w in words for ch in w}
    known = {c for c in chars if c in vocab or c.upper() in vocab}
    return len(known) / max(1, len(chars)), sorted(chars - known)


def emit(mdl, wav_t):
    import torch
    with torch.inference_mode():
        out = mdl(wav_t.unsqueeze(0)).logits
        return torch.log_softmax(out, dim=-1)


def align_window(mdl, proc, wav_t, words):
    """يُرجع [(كلمة، بدايةٌ م.ث، نهايةٌ م.ث، نتيجة)] أو None عند التعذّر."""
    import torch
    import torchaudio.functional as F
    tok = proc.tokenizer
    ids, spans = [], []
    for w in words:
        t = tok(w.replace(" ", "|")).input_ids if hasattr(tok, "__call__") else None
        t = [i for i in (t or []) if i is not None]
        if not t:
            return None
        spans.append((len(ids), len(ids) + len(t)))
        ids += t
    em = emit(mdl, wav_t)
    targets = torch.tensor([ids], dtype=torch.int32)
    try:
        path, scores = F.forced_align(em, targets, blank=0)
    except Exception:                                     # noqa: BLE001
        return None
    path, scores = path[0], scores[0].exp()
    ratio = wav_t.shape[0] / em.shape[1]
    out, k = [], 0
    tf = [(i, int(t)) for i, t in enumerate(path.tolist()) if t != 0]
    for wi, (a, b) in enumerate(spans):
        hits = [i for i, _ in tf[a:b]] if b <= len(tf) else []
        if not hits:
            k += 1
            out.append((words[wi], None, None, 0.0))
            continue
        st, en = _ms(hits[0], ratio), _ms(hits[-1] + 1, ratio)
        sc = float(scores[hits[0]:hits[-1] + 1].mean()) if hits else 0.0
        out.append((words[wi], st, en, sc))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--surah", type=int, required=True)
    ap.add_argument("--riwaya", default="hafs")
    ap.add_argument("--anchor", required=True, help="فهرس v2.1 مِرساةً خشنة (.jz)")
    ap.add_argument("--model", required=True)
    ap.add_argument("--json", required=True)
    ap.add_argument("--window-ayat", type=int, default=WIN_AYAT)
    args = ap.parse_args()

    import gzip
    import torch

    s = args.surah
    idx = load_index()
    lo, hi, meta = surah_slice(idx, s)
    text = load_text(args.riwaya)
    ayat = [norm(text[i]).split() for i in range(lo, hi)]
    n_ayat = len(ayat)

    work = os.path.join(ROOT, "tools", "alignment_v3", "work")
    os.makedirs(work, exist_ok=True)
    mp3 = os.path.join(work, f"s{s:03d}.mp3")
    if not os.path.exists(mp3):
        fetch_retry(args.url, mp3)
    wav = to_wav16k(mp3)
    sil = silences(wav, min_silence_ms=MIN_SIL_MS)

    with gzip.open(args.anchor, "rt", encoding="utf-8") as f:
        anchor = json.load(f)
    anc = {int(e["ayahId"].split(":")[1]): e for e in anchor.get("entries") or []
           if int(e["ayahId"].split(":")[0]) == s}
    if len(anc) < n_ayat // 2:
        sys.exit(f"⛔ س{s}: المِرساة ناقصة ({len(anc)}/{n_ayat}) — لا تصلح نافذةً")

    import torchaudio
    wave, sr = torchaudio.load(wav)
    wave = wave.mean(0)
    total_ms = int(wave.shape[0] * 1000 / sr)

    proc, mdl, vocab = load_model(args.model)
    cov, missing = coverage(vocab, [w for a in ayat for w in a])
    print(f"تغطيةُ المعجم: {cov:.1%}" + (f" · حروفٌ مجهولة: {missing}" if missing else ""))
    if cov < 0.98:
        sys.exit(f"⛔ معجمُ النموذج لا يغطّي نصّنا ({cov:.1%}) — يُجرَّب البديل")

    results, expanded, flagged = {}, 0, []
    wins = [(i, min(i + args.window_ayat, n_ayat))
            for i in range(0, n_ayat, args.window_ayat)]
    for wi, (a0, a1) in enumerate(wins):
        base_s = (anc.get(a0 + 1) or {}).get("startMs")
        base_e = (anc.get(a1) or {}).get("endMs")
        if base_s is None or base_e is None:
            flagged.append((a0 + 1, "مِرساةٌ ناقصة")); continue
        for attempt, margin in enumerate((MARGIN_MS, EXPAND_MS)):
            w_s = max(0, base_s - margin)
            w_e = min(total_ms, base_e + margin)
            w_s, _ = snap_to_silence(w_s, sil, tolerance_ms=margin)
            w_e, _ = snap_to_silence(w_e, sil, tolerance_ms=margin)
            words, owner = [], []
            if a0 > 0:
                words += ayat[a0 - 1][-CTX_WORDS:]; owner += [-1] * min(CTX_WORDS, len(ayat[a0 - 1]))
            for ai in range(a0, a1):
                words += ayat[ai]; owner += [ai] * len(ayat[ai])
            if a1 < n_ayat:
                words += ayat[a1][:CTX_WORDS]; owner += [-1] * min(CTX_WORDS, len(ayat[a1]))
            seg = wave[int(w_s * SR / 1000):int(w_e * SR / 1000)]
            res = align_window(mdl, proc, seg, words)
            if res is None:
                if attempt: flagged.append((a0 + 1, "تعذّرت المحاذاة"))
                continue
            starts = {}
            bad = False
            for (w, st, en, sc), own in zip(res, owner):
                if own < 0 or st is None:
                    continue
                t = w_s + st
                if not (w_s - 1 <= t <= w_e + 1):
                    bad = True
                starts.setdefault(own, (t, sc))
            if bad or len(starts) < (a1 - a0):
                if attempt == 0:
                    expanded += 1
                    continue
                flagged.append((a0 + 1, "حدٌّ خارج النافذة أو آيةٌ بلا بداية"))
                continue
            results.update(starts)
            break

    entries = []
    for ai in range(n_ayat):
        got = results.get(ai)
        if got is None:
            entries.append({"ayahIdx": ai, "startMs": None, "endMs": None,
                            "conf": 0.0, "snapped": False})
            continue
        t, sc = got
        # ⛔ حارسُ الصمت D-025 — لا شارةَ HIGH إلا ببرهانِ صمتٍ عند الحدّ.
        snapped_t, on_sil = snap_to_silence(int(t), sil, tolerance_ms=700)
        entries.append({"ayahIdx": ai, "startMs": int(snapped_t), "endMs": None,
                        "conf": round(float(sc), 3), "snapped": bool(on_sil)})
    for i in range(len(entries) - 1):
        if entries[i]["startMs"] is not None and entries[i + 1]["startMs"] is not None:
            entries[i]["endMs"] = entries[i + 1]["startMs"]
    if entries and entries[-1]["startMs"] is not None:
        entries[-1]["endMs"] = total_ms
    for e in entries:
        if e["startMs"] is not None and (e["endMs"] is None or e["endMs"] <= e["startMs"]):
            e["startMs"] = e["endMs"] = None
            e["conf"] = 0.0

    ratio_exp = expanded / max(1, len(wins))
    issues = []
    if ratio_exp > 0.20:
        issues.append(f"إزاحةٌ كبيرة: وُسّعت {expanded} من {len(wins)} نافذة ({ratio_exp:.0%})")
    for a, why in flagged:
        issues.append(f"آية {a}: {why}")
    bands = {}
    for e in entries:
        b = ("MISSING" if e["startMs"] is None else
             "HIGH" if (e["snapped"] and e["conf"] >= 0.8) else
             "MED" if e["conf"] >= 0.5 else "LOW")
        bands[b] = bands.get(b, 0) + 1
    out = {"surah": s, "riwaya": args.riwaya, "totalMs": total_ms,
           "engineVersion": "align-0.3-ctc", "model": args.model,
           "windows": len(wins), "expandedWindows": expanded,
           "entries": entries, "issues": issues, "bands": bands}
    os.makedirs(os.path.dirname(args.json) or ".", exist_ok=True)
    json.dump(out, open(args.json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"س{s}: نوافذ {len(wins)} · وُسّع {expanded} · النطاقات {bands}")
    for i in issues:
        print("  ⚠️", i)
    print(f"كُتب: {args.json}")


if __name__ == "__main__":
    main()
