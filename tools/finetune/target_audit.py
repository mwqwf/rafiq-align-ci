#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""🎯 **تدقيقُ أهدافِ التدريب ومقياسِها بالنصّ وحدَه** — بلا صوتٍ ولا نموذج (‏D-291 · 2026-09-11).

`label_audit.py` يسأل «هل يطابق نصُّ المقطع صوتَه؟» (يحتاج صوتاً ونموذجاً وشبكة). وقبلَه سؤالان
**لا يحتاجان شيئاً**، وجوابُهما يُحسب على المصحف كلِّه:

1. **لو تعلّم النموذجُ هدفَنا تعلّماً تامّاً — أيقبله حاكمُ التسميع؟** (‏`scorer` = مرآةُ
   `RecitationScorer` المشحون) — يقيسه الذراعُ `--judge`.
2. **ولو تعلّمه تامّاً — أيعطيه مقياسُنا صفراً؟** أي: هل `train.wer` تُحاسب المتعلّمَ المصيبَ؟
   — يقيسه الذراعُ الافتراضيّ (‏أرضيّةُ WER لكلِّ هدف).

وموضعُ الشكّ معروفٌ بعينِه: **D-274/D-275** قضت أنّ الألفَ الخنجرية **نطقٌ لا ألفٌ زائدة**
(`عَلَىٰ` تُقرأ «على» ويكتبها whisper «علي»)، وأُصلحت في `scorer.norm` وفي `RecitationScorer.kt`؛
ثم كشفت **D-278** أنّ `prep.target_text` تخالفها (13,839 كلمة · 5.96٪) فأُصلح **مسارُ v3 وحدَه**
(`train.target_from_ref`). وبقي بابان بعد D-278 وهما مقصودُ هذا الملفّ (‏D-291):
`prep.target_text` نفسُها (مسارُ `--target stored` وهو الافتراض)، و**`train.norm` مرجعُ المقياس**.

    python tools/finetune/target_audit.py            # أرضيّةُ WER لكلِّ هدف (‏~1 د.)
    python tools/finetune/target_audit.py --judge    # حكمُ الحاكم كلمةً كلمة (‏~2 د.)
    python tools/finetune/target_audit.py --judge --ayah   # بالمحاذاة الكاملة (‏~15 د.)
"""
import argparse, collections, os, re, sys, types

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "tasmi_bench"))
sys.path.insert(0, os.path.join(HERE, "..", "alignment"))
sys.path.insert(0, HERE)

import scorer                                    # noqa: E402  مرآةُ الحاكم المشحون
from common import load_text                     # noqa: E402  نصُّ الرواية (6236 آية)
import prep                                      # noqa: E402  مولّدُ الأهداف المشحون

RIWAYAT = ("hafs", "warsh", "qalun")

# هدفُ v2 كما كان قبل إصلاح D-291 (‏للمقارنة قبل/بعد — لا يُستعمل في تدريب)
_LEGACY = [("ٰ", "ا"), ("ٱ", "ا"), ("ۥ", "و"), ("ۦ", "ي"), ("ے", "ي"),
           ("ۡ", "ْ"), ("ٖ", "ٍ"), ("ٗ", "ً"), ("ٞ", "ٌ"), ("ٓ", "")]


def target_legacy(t):
    for a, b in _LEGACY:
        t = t.replace(a, b)
    return re.sub(r"\s+", " ", prep.DROP.sub("", t)).strip()


def load_train():
    """`train.py` بلا torch/transformers — المقصودُ دالّاتُ النصّ (`wer` · `norm` · `target_from_ref`)
    بشيفرتها الحقيقية لا بنسخةٍ منها: فالمقيسُ هو المقياسُ نفسُه."""
    def deco(*a, **k):
        def d(f):
            return f
        return d
    for m in ("numpy", "torch", "soundfile", "transformers", "torch.utils", "torch.utils.data"):
        sys.modules.setdefault(m, types.ModuleType(m))
    t = sys.modules["torch"]
    t.no_grad = deco; t.autocast = deco; t.float16 = None; t.device = lambda *a, **k: None
    sys.modules["torch.utils.data"].Dataset = object
    sys.modules["torch.utils.data"].DataLoader = object
    sys.modules["transformers"].WhisperForConditionalGeneration = object
    sys.modules["transformers"].WhisperProcessor = object
    import train
    return train


def config_for(riwaya):
    """مرآةُ `score.config_for` (الافتراضُ = المشحون: خنجريةٌ اختيارية + صلة)."""
    return scorer.Config(naql=(riwaya == "warsh"), sila=(riwaya in ("warsh", "qalun")))


def pct(a, b):
    return 100.0 * a / max(b, 1)


# ── ١) أرضيّةُ WER: ما يحاسب المقياسُ عليه متعلّماً تامّاً لكلِّ هدف ─────────────────────
def wer_floor(train, arms):
    print("\n=== أرضيّةُ `train.wer` لمتعلّمٍ تامٍّ (صفرٌ = المقياسُ لا يحاسب المصيب) ===")
    agg = {k: [0, 0] for k in arms}
    for riw in RIWAYAT:
        out = []
        for k, f in arms.items():
            e = n = 0
            for a in load_text(riw):
                de, dn = train.wer(a, f(a))
                e += de; n += dn
            agg[k][0] += e; agg[k][1] += n
            out.append(f"{k} {pct(e, n):5.2f}٪ ({e})")
        print(f"  {riw:6s} " + " · ".join(out))
    print("  " + "الكلُّ".ljust(6) + " " + " · ".join(f"{k} {pct(e, n):5.2f}٪ ({e}/{n})"
                                                     for k, (e, n) in agg.items()))
    return agg


# ── ٢) حكمُ الحاكم: أيقبل المشحونُ ما تعلّمه المتعلّمُ التامّ؟ ─────────────────────────
def judge_words(arms, examples):
    print("\n=== حكمُ الحاكم المشحون على هدفٍ تامّ (كلمةً كلمة) ===")
    agg = collections.Counter()
    for riw in RIWAYAT:
        cfg = config_for(riw)
        c = collections.Counter(); top = collections.Counter()
        for a in load_text(riw):
            src = a.split()
            made = {k: f(a).split() for k, f in arms.items()}
            if any(len(v) != len(src) for v in made.values()):
                c["آياتٌ متخطّاة (عددُ الكلمات يختلف بعد حذف علامات الوقف)"] += 1
                continue
            for i, w in enumerate(src):
                V = scorer._riwaya_forms(scorer.variants(w, cfg), cfg)
                c["كلمات"] += 1
                for k in arms:
                    h = scorer.norm(made[k][i], cfg)
                    if scorer._matches(V, h, cfg):
                        continue
                    kind = "غيرُ متبيَّن" if scorer._near(V, h, cfg) else "إبدالٌ واثق"
                    c[f"{k}: يردّه ({kind})"] += 1
                    if k == "القديم":
                        top[(w, made[k][i], h, V[0])] += 1
        print(f"  {riw}: " + " · ".join(f"{k} {v}" for k, v in sorted(c.items())))
        agg.update(c)
        for (w, tgt, h, v0), n in top.most_common(examples):
            print(f"      {n:4d}× {w} ⇜ {tgt} ⇒ «{h}» والحاكمُ يطلب «{v0}»")
    print("  الكلُّ: " + " · ".join(f"{k} {v}" for k, v in sorted(agg.items())))
    return agg


def judge_ayat(arms):
    """بالمحاذاة الكاملة (`scorer.score`) ⇒ نسبةُ **المقاطع** المصابة (المقطع = آية في `prep.py`)."""
    print("\n=== حكمُ الحاكم بالمحاذاة الكاملة — مقاطعُ مصابة ===")
    for k, f in arms.items():
        tw = tr = tu = ta = tay = th = 0
        for riw in RIWAYAT:
            cfg = config_for(riw)
            for a in load_text(riw):
                ref = a.split()
                if not ref:
                    continue
                res = scorer.score(ref, f(a), cfg)
                vs = [w for w in res["words"] if w is not None]
                tay += 1; bad = 0
                for (_i, verdict, *_r) in vs:
                    tw += 1
                    if verdict in (scorer.MISSED, scorer.SUBSTITUTED):
                        tr += 1; bad = 1
                    elif verdict == scorer.UNCERTAIN:
                        tu += 1; bad = 1
                ta += len(res["additions"]); th += bad
        print(f"  {k}: إبدالٌ/فقدٌ واثق {tr} ({pct(tr, tw):.2f}٪) · غيرُ متبيَّن {tu} ({pct(tu, tw):.2f}٪)"
              f" · زائدة {ta} · مقاطعُ مصابة {th}/{tay} ({pct(th, tay):.1f}٪)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--judge", action="store_true", help="ذراعُ الحاكم كلمةً كلمة")
    ap.add_argument("--ayah", action="store_true", help="ذراعُ الحاكم بالمحاذاة الكاملة (بطيء)")
    ap.add_argument("--examples", type=int, default=6)
    a = ap.parse_args()

    train = load_train()
    arms = {"v3(norm)": train.target_from_ref, "stored": prep.target_text, "القديم": target_legacy}

    # ✅ ضابطٌ موجَب: نصُّ المصحف نفسُه هدفاً ⇒ أرضيّةُ WER **صفرٌ** بعد إصلاح `train.norm`
    #    (وإلا فالمقياسُ يخالف مرجعَه). وضابطٌ سالب: هدفُ «القديم» يجب أن يعيد رقمَ D-278 (5.96٪).
    wer_floor(train, {"المصحفُ نفسُه (ضابطٌ موجَب)": lambda t: t, **arms})

    if a.judge:
        judge_words(arms, a.examples)
    if a.ayah:
        judge_ayat(arms)


if __name__ == "__main__":
    main()
