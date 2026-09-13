# -*- coding: utf-8 -*-
"""🔤 **أيَّ لغةٍ يتوقّعها النموذجُ نفسُه؟** (‏D-298) — جوابٌ مقيسٌ لا مظنون.

السؤال: المحركُ يفكّ بـ`params.language = "en"` (‏jni.c) والتدريبُ يُلصق `<|ar|>` (‏train.py). فهل يبالي النموذج؟
القياس: يُعطى النموذجُ الصوتَ ورمزَ البداية وحدَه (`<|startoftranscript|>`) ثم يُنظَر توزيعُه على **رموز اللغات الـ99**.
هذا يكشف ما تعلّمه فعلاً، بلا حاجةٍ إلى بطاقة النموذج ولا إلى ثقةٍ في `generation_config`.

    python tools/finetune/lang_prefix_probe.py --model tools/finetune/work/shipped --n 12
    python tools/finetune/lang_prefix_probe.py --model tools/finetune/work/v2_best --n 12
"""
import argparse
import glob
import os
import sys

import numpy as np
import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
WAV = os.path.join(ROOT, "tools", "tasmi_bench", "work", "wav")
SR = 16000


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=os.path.join(HERE, "work", "shipped"))
    ap.add_argument("--wav", default=WAV)
    ap.add_argument("--n", type=int, default=12)
    ap.add_argument("--top", type=int, default=4)
    a = ap.parse_args()

    import torch
    from transformers import WhisperForConditionalGeneration, WhisperProcessor
    torch.set_num_threads(max(1, (os.cpu_count() or 4) // 2))
    proc = WhisperProcessor.from_pretrained(a.model)
    model = WhisperForConditionalGeneration.from_pretrained(a.model).eval()
    tok = proc.tokenizer

    # رموزُ اللغات: كلُّ رمزٍ مضافٍ على صورة <|xx|> بحرفين (‏99 لغة) — تُستخرج من المعجم لا من إعدادٍ قد يكون قديماً.
    lang_ids = {t: i for t, i in tok.get_added_vocab().items()
                if len(t) == 6 and t.startswith("<|") and t.endswith("|>") and t[2:4].isalpha()}
    sot = tok.convert_tokens_to_ids("<|startoftranscript|>")
    files = sorted(glob.glob(os.path.join(a.wav, "*.wav")))[: a.n]
    if not files:
        sys.exit(f"⛔ لا ملفّاتِ wav في {a.wav}")
    ids = torch.tensor([[sot]])
    tally, probs_sum = {}, {}
    for f in files:
        w, sr = sf.read(f, dtype="float32")
        if w.ndim > 1:
            w = w.mean(1)
        x = proc(w[: 30 * SR], sampling_rate=SR, return_tensors="pt").input_features
        with torch.no_grad():
            logits = model(input_features=x, decoder_input_ids=ids).logits[0, -1]
        p = torch.softmax(logits.float(), -1)
        lp = {t: float(p[i]) for t, i in lang_ids.items()}
        best = max(lp, key=lp.get)
        tally[best] = tally.get(best, 0) + 1
        for t, v in lp.items():
            probs_sum[t] = probs_sum.get(t, 0.0) + v
    n = len(files)
    print(f"النموذج: {a.model} · {n} مقطعاً · {len(lang_ids)} رمزَ لغة")
    print("الأكثرُ ترجيحاً بالتصويت:", {k: f"{v}/{n}" for k, v in sorted(tally.items(), key=lambda kv: -kv[1])})
    top = sorted(probs_sum.items(), key=lambda kv: -kv[1])[: a.top]
    print("متوسّطُ الاحتمال:", " · ".join(f"{t} {v/n*100:.1f}٪" for t, v in top))
    ar, en = probs_sum.get("<|ar|>", 0) / n, probs_sum.get("<|en|>", 0) / n
    print(f"⇒ ar {ar*100:.1f}٪ مقابل en {en*100:.2f}٪ — النسبة {ar/max(en,1e-12):,.0f}×")


if __name__ == "__main__":
    main()
