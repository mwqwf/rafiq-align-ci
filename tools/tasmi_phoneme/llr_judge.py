#!/usr/bin/env python3
"""⚖️🐦 **شاهدُ LLR بفرضيّتين بالهدهد — القياسُ على مسطرة المتعلّمين** ([[D-756]] · بند ج-1 من تقرير 2026-10-13).

النظيرُ البايثونيُّ لـ`engine/recitation/.../hudhud/WordLlr.kt` (‏الآلةُ نفسُها: `ctc_align.align` ودرجةُ أفضل مسار).
السؤال: الحاكمُ (`whisper`) اتّهم كلمةً (MISSED/SUBSTITUTED) — فهل يؤيّده الصوت؟ لكلّ كلمةٍ متَّهَمة على نافذة سياقها
(‏الجارةُ قبلها والجارةُ بعدها من محاذاة الآية كلِّها):

    H1: جارة | المتوقَّعة | جارة            H2: جارة | المسموعة (أو لا شيء للفائتة) | جارة
    LLR = log P(أفضل مسار H1) − log P(أفضل مسار H2)       LLR ≥ +m ⇒ تُطلق إلى «غير متبيَّن»

⛔ **لا تُضبط m على ما يُقاس** (‏كما في `gop_judge.py`): تُمسح قيمُ m وتُطبع لكلٍّ منها **نسبةُ الاتّهام الكاذب الباقية** على الكلمات
السليمة التي اتّهمها whisper (‏`human_error == False`) **ونسبةُ الكشف الباقية** على كلمات الخطأ (‏`human_error == True`) — بمجال
ويلسون. والقرارُ معيارُه المكتوب في `FeatureFlags.TASMI_HUDHUD_LLR`: اتّهامٌ كاذبٌ −2 نقطة فأكثر بلا نقصٍ في الكشف يفصله المجال.

⛔ **G2P من النصّ الموثَّق وحده**: المتوقَّع من `g2p_labels` (‏الآيةُ بفهرسها المسطّح)؛ والمسموعُ (‏كلمةُ `hyp` المشكولة) يُحوَّل عبر
**معجم المصحف** المشتقّ من `g2p_labels` + `text_<riwaya>.jz` (‏كلمةٌ مشكولة ⇒ رموزُها كما وردت في المصحف) — وما ليس في المعجم لا
يُقاس (‏فلا نحوّل نصّاً غيرَ موثَّق).

    python tools/tasmi_phoneme/llr_judge.py --onnx <hudhud.onnx> --vocab vocab.json --labels g2p_labels.jsonl \
        --index core/quran/src/main/assets/quran/index.jz --text core/quran/src/main/assets/quran/text_hafs.jz \
        --judge docs/qa/tasmi_2026-09-20/learner_judge.json --wav-dir work/tasmi/learner_wav --out work/llr.json

الصوتُ (‏`learner_fetch.py`) ليس في المستودع؛ فإن غاب محلّيّاً يُقاس في المستودع العامّ `rafiq-align-ci` (‏انظر `--help` وREADME).
"""
from __future__ import annotations

import argparse
import gzip
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from ctc_align import align, _validate                 # noqa: E402  — المسطرةُ نفسُها
from ctc_train import surah_starts                     # noqa: E402
from gop_judge import load_audio, wilson               # noqa: E402

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:                                  # noqa: BLE001
        pass

ACCUSE = {"MISSED", "SUBSTITUTED"}
DEFAULT_MARGINS = (0.0, 1.0, 2.0, 3.0, 4.0, 6.0, 8.0)
DIACRITICS = set("ًٌٍَُِّْٰ")


def path_score(log_probs, target, blank=0, lo=0, hi=None):
    """درجةُ أفضل مسار CTC لـ`target` على الإطارات `[lo, hi)` — نسخةُ `WordLlr.pathScore` (‏هدفٌ فارغ ⇒ مجموعُ الفراغ)."""
    x = np.asarray(log_probs, dtype=np.float64)
    hi = x.shape[0] if hi is None else hi
    x = x[lo:hi]
    if x.shape[0] == 0:
        return None
    target = list(target)
    if not target:
        return float(x[:, blank].sum())
    if any(t == blank or not 0 <= t < x.shape[1] for t in target):
        return None
    minimum = len(target) + sum(a == b for a, b in zip(target, target[1:]))
    if x.shape[0] < minimum:
        return None
    states = [blank]
    for t in target:
        states.extend([t, blank])
    prev = np.full(len(states), -math.inf)
    prev[:2] = x[0, states[:2]]
    for f in range(1, x.shape[0]):
        cur = np.full(len(states), -math.inf)
        for s, tok in enumerate(states):
            best = prev[s]
            if s > 0 and prev[s - 1] > best:
                best = prev[s - 1]
            if s > 1 and tok != blank and tok != states[s - 2] and prev[s - 2] > best:
                best = prev[s - 2]
            cur[s] = best + x[f, tok]
        prev = cur
    end = max(prev[-1], prev[-2]) if len(states) >= 2 else prev[-1]
    return None if not math.isfinite(end) else float(end)


def join(words, delim):
    out = []
    for w in words:
        if not w:
            continue
        if out:
            out.append(delim)
        out.extend(w)
    return out


def judge(llr, margin):
    if llr is None or (isinstance(llr, float) and math.isnan(llr)):
        return "NO_EVIDENCE"
    return "CLEAR" if llr >= margin else "KEEP"


def refine(log_probs, words, accused, delim, blank=0, context=1):
    """`WordLlr.refine`: لكلّ كلمةٍ في `accused` (‏فهرس ⇒ رموزُ المسموع أو None) يعيد (lo, hi, h1, h2, llr) أو None إن استحالت المحاذاة."""
    owner, target = [], []
    for w, toks in enumerate(words):
        if not toks:
            continue
        if target:
            target.append(delim); owner.append(-1)
        target.extend(toks); owner.extend([w] * len(toks))
    try:
        spans, _ = align(log_probs, target, blank=blank)
    except ValueError:
        return {w: None for w in accused}
    lo_f = [10 ** 9] * len(words); hi_f = [-1] * len(words)
    for sp in spans:
        w = owner[sp.token_index]
        if w < 0:
            continue
        lo_f[w] = min(lo_f[w], sp.start_frame); hi_f[w] = max(hi_f[w], sp.end_frame)
    out = {}
    frames = np.asarray(log_probs).shape[0]
    for w, heard in accused.items():
        before = [i for i in range(w - 1, -1, -1) if words[i]][:context][::-1]
        after = [i for i in range(w + 1, len(words)) if words[i]][:context]
        lo = lo_f[before[0]] if before else 0
        hi = hi_f[after[-1]] if after else frames
        if hi <= lo:
            out[w] = None
            continue
        ctx_b = [words[i] for i in before]; ctx_a = [words[i] for i in after]
        h1 = path_score(log_probs, join(ctx_b + [words[w]] + ctx_a, delim), blank, lo, hi)
        h2 = path_score(log_probs, join(ctx_b + [heard or []] + ctx_a, delim), blank, lo, hi)
        out[w] = (lo, hi, h1, h2, None if h1 is None or h2 is None else h1 - h2)
    return out


def load_text(path):
    data = gzip.decompress(open(path, "rb").read()).decode("utf-8")
    try:
        j = json.loads(data)
        if isinstance(j, list):
            return [str(a) for a in j]
        if isinstance(j, dict):
            for k in ("ayahs", "text", "verses"):
                if k in j:
                    return [str(a) if isinstance(a, str) else str(a.get("text", "")) for a in j[k]]
    except json.JSONDecodeError:
        pass
    return data.split("\n")


def lexicon(g2p, texts, riwaya):
    """معجمُ المصحف: كلمةٌ مشكولة ⇒ رموزُها الأكثرُ شيوعاً عبر مواضعها (‏السياقُ يغيّر الطرفين؛ نأخذ الأغلب)."""
    from collections import Counter, defaultdict
    acc = defaultdict(Counter)
    for (r, flat), words in g2p.items():
        if r != riwaya or flat >= len(texts):
            continue
        toks = [t for t in texts[flat].split() if t]
        if len(toks) != len(words):
            continue
        for t, ph in zip(toks, words):
            acc[t][tuple(ph)] += 1
    return {t: list(c.most_common(1)[0][0]) for t, c in acc.items()}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--onnx", required=True)
    ap.add_argument("--vocab", required=True, help="vocab.json للهدهد (الفراغ `--blank`، الفاصل `|`)")
    ap.add_argument("--blank", type=int, default=0)
    ap.add_argument("--labels", required=True)
    ap.add_argument("--index", required=True)
    ap.add_argument("--text", help="text_<riwaya>.jz لبناء معجم المسموع (‏بدونه لا تُقاس المُبدَلة)")
    ap.add_argument("--judge", required=True)
    ap.add_argument("--wav-dir", required=True)
    ap.add_argument("--riwaya", default="hafs")
    ap.add_argument("--margins", default=",".join(str(m) for m in DEFAULT_MARGINS))
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    import onnxruntime as ort
    sess = ort.InferenceSession(a.onnx, providers=["CPUExecutionProvider"])
    vocab = json.load(open(a.vocab, encoding="utf-8"))
    delim = vocab["|"]
    starts = surah_starts(a.index)
    g2p = {}
    for line in open(a.labels, encoding="utf-8"):
        d = json.loads(line)
        g2p[(d["r"], d["flat"])] = d["words"]
    lex = lexicon(g2p, load_text(a.text), a.riwaya) if a.text else {}
    man = json.load(open(os.path.join(a.wav_dir, "manifest.json"), encoding="utf-8"))
    wav_of = {(it["recording_id"], it["ref"]): os.path.join(a.wav_dir, it["wav"]) for it in man["items"]}
    judge_rows = json.load(open(a.judge, encoding="utf-8"))["rows"]

    rows, skipped = [], {}
    for r in judge_rows:
        path = wav_of.get((r["rec"], r["ref"]))
        s, ay = (int(x) for x in r["ref"].split(":"))
        words = g2p.get((r.get("riwaya") or "hafs", starts[s - 1] + ay - 1))
        why = None
        if path is None or not os.path.isfile(path):
            why = "no audio"
        elif not words or len(words) != r["n_ref"]:
            why = "word count"
        ids = []
        if not why:
            for w in words:
                if any(ph not in vocab for ph in w):
                    why = "phoneme not in vocab"; break
                ids.append([vocab[ph] for ph in w])
        if why:
            skipped[why] = skipped.get(why, 0) + 1
            continue
        accused = {}
        hyp = [t for t in r.get("hyp", "").split() if t]
        for wi, w in enumerate(r["words"]):
            if w["status"] == "MISSED":
                accused[wi] = None
            elif w["status"] == "SUBSTITUTED":
                # المسموعُ: كلمةُ `hyp` المقابلة إن وُجدت مشكولةً في معجم المصحف — وإلا لا تُقاس
                cand = [t for t in hyp if t in lex and set(t) & DIACRITICS]
                heard = r.get("heard", {}).get(str(wi)) if isinstance(r.get("heard"), dict) else None
                tok = heard if heard in lex else (cand[wi] if wi < len(cand) else None)
                if tok is not None and all(ph in vocab for ph in lex[tok]):
                    accused[wi] = [vocab[ph] for ph in lex[tok]]
        if not accused:
            continue
        wav = load_audio(path)
        logits = sess.run(None, {sess.get_inputs()[0].name: wav[None, :]})[0][0].astype(np.float64)
        m = logits.max(-1, keepdims=True)
        lp = logits - (m + np.log(np.exp(logits - m).sum(-1, keepdims=True)))
        try:
            _validate(lp, a.blank)
        except ValueError as e:
            skipped[f"lp: {e}"] = skipped.get(f"lp: {e}", 0) + 1
            continue
        ev = refine(lp, ids, accused, delim, a.blank)
        for wi, e in ev.items():
            rows.append({"rec": r["rec"], "ref": r["ref"], "kind": r.get("kind"), "w": wi, "status": r["words"][wi]["status"],
                         "human_error": r["words"][wi].get("human_error"), "llr": None if e is None else e[4],
                         "window": None if e is None else [e[0], e[1]]})
        print(f"{r['ref']:>8} {r.get('kind')}: " + " ".join(f"{wi}:{'∅' if e is None or e[4] is None else f'{e[4]:+.1f}'}" for wi, e in ev.items()), flush=True)

    clean = [x for x in rows if x["human_error"] is False]      # اتّهاماتٌ كاذبة
    errs = [x for x in rows if x["human_error"] is True]        # اتّهاماتٌ صائبة
    res = {"rows": len(rows), "skipped": skipped, "falseAccusations": len(clean), "trueAccusations": len(errs), "margins": {}}
    print(f"\n⚖️ متَّهَماتٌ مقيسة {len(rows)} · كاذبةٌ {len(clean)} · صائبةٌ {len(errs)} · مُسقَط {skipped}")
    for m in (float(v) for v in a.margins.split(",") if v.strip()):
        fa_cleared = sum(1 for x in clean if judge(x["llr"], m) == "CLEAR")
        det_lost = sum(1 for x in errs if judge(x["llr"], m) == "CLEAR")
        fl, fh = wilson(fa_cleared, len(clean)); dl, dh = wilson(det_lost, len(errs))
        res["margins"][str(m)] = {"falseAccuseClearedPct": None if not clean else round(100 * fa_cleared / len(clean), 1),
                                  "falseAccuseClearedWilson95": [round(fl, 1), round(fh, 1)],
                                  "detectLostPct": None if not errs else round(100 * det_lost / len(errs), 1),
                                  "detectLostWilson95": [round(dl, 1), round(dh, 1)]}
        print(f"  m={m:>4}: يُطلق من الكاذبة {fa_cleared}/{len(clean)} [{fl:.1f}..{fh:.1f}]٪ · ويُضيّع من الصائبة {det_lost}/{len(errs)} [{dl:.1f}..{dh:.1f}]٪")
    res["rowsDetail"] = rows
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    json.dump(res, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("⇒", a.out)
    print("⛔ لا يُعلن m إلا بفارقٍ يفصله مجالُ ويلسون؛ وعيّنةُ الخطأ صغيرة (D-735)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
