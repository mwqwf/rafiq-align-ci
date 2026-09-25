#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""🎚️ ثقةُ الرموز من التفريغ الحرّ (`RafiqConf`) — **قياسٌ فقط، لا يُشحن ولا يكتب على R2**.

السؤال (أمر المالك 2026-09-25 · محور conf): `jni.c:getTokens` يعيد `p` لكلّ رمز، و`LibWhisper.TimedWord.p`
يحمل متوسّطَها لكلّ كلمة، ثمّ **لا مستهلكَ لها في المحرك** (CLOUD_ENGINE.md: «لم تُقَس قطّ»). فهل:
  (أ) **التنزيل**: اتّهامُ SUBSTITUTED الذي ثقةُ كلمته المسموعة منخفضةٌ يُنزَّل إلى UNCERTAIN دون فقد كشف؟
  (ب) **الرفع**: UNCERTAIN (فرقُ حرفٍ واحد) بثقةٍ عالية يُرفع إلى SUBSTITUTED دون رفع الاتّهام؟
  (ج) **فيتو مشروط**: في `X+Y:veto` لا يَنقض «صحيحُ» Y اتّهامَ X إلا إن كانت ثقةُ Y في الكلمة ≥ τ؟

**المسجَّلُ سلفاً قبل رؤية أيّ نتيجة:**
- الإحصاءة الأولى `mean` = متوسّطُ p لرموز الكلمة (**هي `TimedWord.p` نفسُها** — صفرُ حسابٍ جديد في التطبيق)،
  والثانية `min` = أدنى p (استكشافيّة).
- الشبكة τ ∈ {0.05 … 0.95} بخطوة 0.05، والمنحنى كلُّه يُطبع (لا يُختار رقمٌ ويُخفى الباقي).
- **الاختيارُ بتحقّقٍ متقاطعٍ بالتسجيل (5 طيّات · crc32 كما `forced_judge`)**: على طيّات التدريب
  (أ) أكبرُ خفضٍ للاتّهام **بلا فقد كشفٍ** · (ب)/(ج) أكبرُ كسبِ كشفٍ **بلا زيادة اتّهام**؛ ثمّ يُقاس على الطيّة المحجوزة.
- **النقلُ إلى g3r**: τ المختارةُ على المتعلّمين كلِّهم تُطبَّق كما هي على g3r (نظيف/مضجَّج) — مادّةٌ مستقلّةٌ
  فيها خطأٌ مصنوعٌ معلومُ الموضع (240 بنداً)، فيُقاس فيها ثمنُ الكشف بعيّنةٍ أكبر من 51 كلمة.
- المسطرة: `learner_gate.py` نفسُه (apply_ruler · counts · paired · Boot) · وg3r بقاعدة `v2_gate.judge_arm`
  (±1 حول الحقن · كبحُ الانهيار 0.60).

    python conf_probe.py run --set learners --model tiny --model-path m.bin --cli whisper-cli --audio work/learner_audio --out raw.json
    python conf_probe.py run --set g3r:noisy --model base_q5_1 --model-path m.bin --cli whisper-cli --out raw.json
    python conf_probe.py analyze --raw work/raw/*.json --out results/conf_probe.json --md results/conf_probe.md
    python conf_probe.py selftest
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import subprocess
import sys
import tempfile
import time
import zlib

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import scorer  # noqa: E402
from detect_score import cfg_for  # noqa: E402

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass

SR = 16000
EOT = 50257                       # أوّلُ رمزٍ خاصّ في معجم whisper المتعدّد — كما يتخطّاه `jni.c:getTokens` (td.id >= eot)
GRID = [round(0.05 * k, 2) for k in range(1, 20)]
FOLDS = 5
COLLAPSE = 0.60
ACCUSE = {scorer.MISSED, scorer.SUBSTITUTED}
# لغةُ الفكّ الحرّ = لغةُ الخدمة (WhisperDecode.SERVING) كما في forced_judge.MODELS
LANG = {"tiny": "en", "base_q5_1": "ar"}
WS = b" \t\n\r"


# ───────────────────────────── ١) التفريغ مع الرموز ─────────────────────────────
def parse_ojf(path: str) -> list:
    """ملفُّ `-ojf` ⇐ [(bytes, p)] لرموز النصّ وحدها. النصُّ قد يحمل نصفَ حرفٍ (بايتات UTF-8 ناقصة)
    فيُقرأ بـsurrogateescape ويُعاد بايتاتٍ كما هي."""
    raw = open(path, "rb").read().decode("utf-8", "surrogateescape")
    d = json.loads(raw, strict=False)
    toks = []
    for seg in d.get("transcription", []):
        for t in seg.get("tokens", []):
            if int(t.get("id", 0)) >= EOT:
                continue
            toks.append((t.get("text", "").encode("utf-8", "surrogateescape"), float(t.get("p", 0.0))))
    return toks


def words_with_conf(parts: list) -> list:
    """أجزاءُ رموز ⇐ كلماتٌ مفصولةٌ بالمسافات، ولكلّ كلمة رموزُها التي تغطّي بايتاتها.
    مرآةُ `LibWhisper.wordsFromTokenLines`: البايتاتُ تُلصق قبل الفكّ، والمتوسّطُ على رموز الكلمة."""
    buf, owner = bytearray(), []
    for pi, toks in enumerate(parts):
        if pi:
            buf += b" "
            owner.append(None)
        for ti, (b, _p) in enumerate(toks):
            buf += b
            owner += [(pi, ti)] * len(b)
    out, i, n = [], 0, len(buf)
    while i < n:
        if buf[i] in WS:
            i += 1
            continue
        j = i
        while j < n and buf[j] not in WS:
            j += 1
        tk = sorted({owner[k] for k in range(i, j) if owner[k] is not None})
        ps = [parts[a][b][1] for a, b in tk]
        out.append({"t": bytes(buf[i:j]).decode("utf-8", "replace"),
                    "mean": float(np.mean(ps)) if ps else None, "min": float(min(ps)) if ps else None, "n": len(ps)})
        i = j
    return out


def run(a) -> int:
    import soundfile as sf
    import local_whisper as lw
    lang = LANG[a.model]
    if a.set == "learners":
        # مرآةُ `forced_judge.run`: Transcriber الافتراضيّ (بلا بوّابة · النافذةُ كاملة)
        man = json.load(open(os.path.join(a.audio, "manifest.json"), encoding="utf-8"))["items"]
        import forced_judge as fj
        items = [(r["key"], os.path.join(a.audio, man[r["key"]])) for r in fj.load_gold(a.gold) if r["key"] in man]
        tr = lw.Transcriber(a.model_path, backend="cli", cli=a.cli, lang=lang, threads=a.threads)
        reader = fj.read_audio
    else:
        # مرآةُ `tasmi-shrink`/`v2_gate`: `local_whisper --gate --group-cap 10`
        src, _tag = lw.resolve_set(a.set)
        items = [(f[:-4], os.path.join(src, f)) for f in sorted(os.listdir(src)) if f.endswith(".wav")]
        tr = lw.Transcriber(a.model_path, backend="cli", cli=a.cli, lang=lang, threads=a.threads,
                            gate=True, group_cap=int(10 * SR))

        def reader(p):
            x, sr = sf.read(p, dtype="float32")
            assert sr == SR, sr
            return x
    if a.limit:
        items = items[:a.limit]
    # 🪝 نلتقط كلَّ نداءٍ لـwhisper-cli ونضيف `-ojf -of` وحدهما (لا يغيّران الفكّ؛ و`token_timestamps`
    #    الذي يفعّله -ojf مفعَّلٌ في المحرك أصلاً · jni.c `params.token_timestamps = true`).
    calls = []
    real_run = subprocess.run
    tmpd = tempfile.mkdtemp()

    def hooked(cmd, *args, **kw):
        if isinstance(cmd, list) and cmd and cmd[0] == a.cli and "-f" in cmd:
            of = os.path.join(tmpd, f"c{len(calls)}")
            r = real_run(cmd + ["-ojf", "-of", of], *args, **kw)
            try:
                calls.append(parse_ojf(of + ".json"))
                os.remove(of + ".json")
            except Exception as e:  # noqa: BLE001
                calls.append({"error": f"{type(e).__name__}: {e}"[:200]})
            return r
        return real_run(cmd, *args, **kw)

    subprocess.run = hooked
    out, t0 = {}, time.time()
    try:
        for n, (key, path) in enumerate(items, 1):
            calls.clear()
            try:
                h = tr.transcribe(reader(path))
                text = " ".join((h[0] if isinstance(h, tuple) else h).split())
                errs = [c["error"] for c in calls if isinstance(c, dict)]
                parts = [c for c in calls if not isinstance(c, dict)]
                ws = words_with_conf(parts) if not errs else []
                out[key] = {"text": text, "words": ws, "calls": len(calls), "parse_errors": errs,
                            "parity": [w["t"] for w in ws] == text.split()}
            except Exception as e:  # noqa: BLE001
                out[key] = {"error": f"{type(e).__name__}: {e}"[:200]}
            if n % 25 == 0:
                print(f"  {n}/{len(items)} · {time.time() - t0:.0f}ث", flush=True)
    finally:
        subprocess.run = real_run
    par = sum(1 for v in out.values() if v.get("parity"))
    json.dump({"set": a.set, "model": a.model, "lang": lang, "items": out, "seconds": round(time.time() - t0),
               "parity": [par, len(out)]}, open(a.out, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"✅ {a.model} {a.set}: {len(out)} بنداً · تماثلُ الكلمات بين الرموز والنصّ {par}/{len(out)} · {time.time() - t0:.0f}ث")
    return 0


# ───────────────────────────── ٢) الحكم مع موضع الكلمة المسموعة ─────────────────────────────
def score_idx(ref_words, hyp_words, cfg):
    """أحكامُ `scorer.score` نفسُها + فهرسُ الكلمة المسموعة (في `hyp_words` الأصليّة) لكلّ كلمةٍ مرجعيّة.
    البرمجةُ الديناميّة منسوخةٌ حرفاً من `scorer.score` مع حمل الفهرس الأصليّ؛ والأحكامُ تُؤخذ من
    `scorer.score` الحقيقيّ (بحُرّاسه)، ويُتحقَّق أنّ المسموعَ المنسوبَ هو المسموعُ عنده."""
    real = scorer.score(ref_words, " ".join(hyp_words), cfg)
    ref = [scorer._riwaya_forms(scorer.variants(w, cfg), cfg) for w in ref_words]
    hyp, orig = [], []
    for k, x in enumerate(hyp_words):
        v = scorer.norm(x, cfg)
        if v:
            hyp.append(v)
            orig.append(k)
    INF = scorer.INF
    R, H = len(ref), len(hyp)
    dp = [[INF] * (H + 1) for _ in range(R + 1)]
    back = [[None] * (H + 1) for _ in range(R + 1)]
    dp[0][0] = 0
    for i in range(R + 1):
        for j in range(H + 1):
            d = dp[i][j]
            if d == INF:
                continue

            def relax(ni, nj, cost, op, i=i, j=j, d=d, sub=False):
                if ni > R or nj > H or cost >= INF:
                    return
                c = cost * scorer._SC + (scorer._SUB_TIE if (sub and scorer.PREFER_INSERT_ON_TIE) else 0) \
                    if scorer.PREFER_INSERT_ON_TIE else cost
                if d + c < dp[ni][nj]:
                    dp[ni][nj] = d + c
                    back[ni][nj] = (i, j, op)

            if i < R and j < H:
                _c = 0 if scorer._matches(ref[i], hyp[j], cfg) else (1 if scorer._uncertain(ref[i], hyp[j], cfg) else 2)
                relax(i + 1, j + 1, _c, 0, sub=(_c == 2))
            if i < R:
                relax(i + 1, j, 3, 1)
            if j < H:
                cheap = getattr(cfg, "learner_tolerant", False) and (
                    any(scorer._matches(ref[k], hyp[j], cfg) for k in range(max(0, i - 2), i))
                    or any(scorer._matches(ref[k], hyp[j], cfg) for k in range(i, min(R, i + 3)))
                    or (i == 0 and j < 6))
                relax(i, j + 1, 1 if cheap else 3, 2)
            if i < R and j + 1 < H:
                relax(i + 1, j + 2, 1 if scorer._matches(ref[i], hyp[j] + hyp[j + 1], cfg) else INF, 3)
            if i + 1 < R and j < H:
                joined = tuple(x + y for x in ref[i] for y in ref[i + 1])
                relax(i + 2, j + 1, 1 if scorer._matches(joined, hyp[j], cfg) else INF, 4)
    idx = [None] * R
    i, j = R, H
    while i > 0 or j > 0:
        b = back[i][j]
        if b is None:
            break
        pi, pj, op = b
        if op == 0:
            idx[pi] = [orig[pj]]
        elif op == 3:
            idx[pi] = [orig[pj], orig[pj + 1]]
        elif op == 4:
            idx[pi] = idx[pi + 1] = [orig[pj]]
        i, j = pi, pj
    st = [w[1] for w in real["words"]]
    heard = [w[2] for w in real["words"]]
    ok = all(hd is None or ix is None or hd == " ".join(scorer.norm(hyp_words[k], cfg) for k in ix)
             for hd, ix in zip(heard, idx))
    return st, idx, ok


def word_conf(item, ix, stat):
    """ثقةُ الكلمة المسموعة (أدنى الكلمتين عند الدمج) أو None إن لا مسموع/لا تماثل."""
    if not ix or not item.get("parity"):
        return None
    vals = [item["words"][k][stat] for k in ix if item["words"][k][stat] is not None]
    return min(vals) if vals else None


# ───────────────────────────── ٣) السياسات ─────────────────────────────
def apply_policy(st, conf, pol, tau):
    """st: أحكامُ الشاهد · conf: ثقةُ كلّ كلمة ⇐ أحكامٌ جديدة."""
    out = list(st)
    for k, (s, c) in enumerate(zip(st, conf)):
        if c is None:
            continue
        if pol == "demote" and s == scorer.SUBSTITUTED and c < tau:
            out[k] = scorer.UNCERTAIN
        elif pol == "promote" and s == scorer.UNCERTAIN and c >= tau:
            out[k] = scorer.SUBSTITUTED
    return out


def veto_acc(st_x, st_y, conf_y, tau):
    """`X+Y:veto` (قاعدةُ learner_gate) و«صحيحُ» Y لا يَنقض إلا بثقةٍ ≥ τ (τ=None ⇒ القاعدةُ المشحونة)."""
    return [a in ACCUSE and not (b == scorer.CORRECT and (tau is None or (c is not None and c >= tau)))
            for a, b, c in zip(st_x, st_y, conf_y)]


# ───────────────────────────── ٤) التحليل ─────────────────────────────
def _fold(rec):
    return zlib.crc32(rec.encode()) % FOLDS


def _auc(pos, neg):
    """P(ثقةُ الاتّهام الصادق > ثقةُ الكاذب) — 0.5 = لا فصل."""
    if not pos or not neg:
        return None
    s = 0.0
    for x in pos:
        s += sum(1.0 if x > y else 0.5 if x == y else 0.0 for y in neg)
    return round(s / (len(pos) * len(neg)), 4)


def _q(v, qs=(0.1, 0.25, 0.5, 0.75, 0.9)):
    v = sorted(v)
    return {str(q): round(v[min(int(q * len(v)), len(v) - 1)], 3) for q in qs} if v else {}


def learners(raws, gold, boot_n):
    import learner_gate as lg
    _meta, rows0 = lg.load_gold(gold)
    lg.check_text(rows0)
    models = sorted(raws)
    rows, why = lg.apply_ruler(rows0, {"turbo"})
    rows = [r for r in rows if all(r["key"] in raws[m] and "error" not in raws[m][r["key"]] for m in models)]
    boot = lg.Boot(rows, boot_n)
    per = {}
    diag = {}
    for m in models:
        st, cf = {"mean": [], "min": []}, {"mean": [], "min": []}
        sts = []
        bad_map = 0
        same_as_gold = 0
        for r in rows:
            it = raws[m][r["key"]]
            s, ix, ok = score_idx(r["ref_text"].split(), it["text"].split(), cfg_for(r["riwaya"]))
            bad_map += not ok
            gname = {"tiny": "tiny", "base_q5_1": "base"}[m]
            same_as_gold += " ".join(it["text"].split()) == " ".join(r["hyp"][gname].split())
            sts.append(s)
            for stat in ("mean", "min"):
                cf[stat].append([word_conf(it, x, stat) if ok else None for x in ix])
        per[m] = {"st": sts, "conf": cf}
        par = sum(1 for r in rows if raws[m][r["key"]].get("parity"))
        diag[m] = {"rows": len(rows), "token_word_parity": par, "map_mismatch": bad_map, "text_equal_to_gold_hyp": same_as_gold}
    st_turbo = [[w[1] for w in scorer.score(r["ref_text"].split(), r["hyp"]["turbo"], cfg_for(r["riwaya"]))["words"]]
                for r in rows]

    def acc_of(st):
        return [[s in ACCUSE for s in row] for row in st]

    res = {"ruler": {"kept_rows": len(rows), "recordings": boot.n_recordings, "dropped": why}, "diag": diag, "models": {}}
    for m in models:
        st = per[m]["st"]
        R = {"baseline": lg.summarize(rows, acc_of(st), boot)}
        # فصلُ الثقة: الاتّهامُ الصادق (موسومٌ خطأً) مقابل الكاذب (كلمةٌ في تسجيلٍ سليم)
        sep = {}
        for stat in ("mean", "min"):
            tp, fp, unc_t, unc_f, corr_clean, corr_marked = [], [], [], [], [], []
            for r, srow, crow in zip(rows, st, per[m]["conf"][stat]):
                for j, (s, c) in enumerate(zip(srow, crow)):
                    if c is None:
                        continue
                    marked = r["kind"] == "موجب" and r["labels"][j] == "1"
                    clean = r["kind"] == "سالب"
                    if s == scorer.SUBSTITUTED:
                        (tp if marked else fp if clean else []).append(c)
                    elif s == scorer.UNCERTAIN:
                        (unc_t if marked else unc_f if clean else []).append(c)
                    elif s == scorer.CORRECT:
                        (corr_marked if marked else corr_clean if clean else []).append(c)
            sep[stat] = {"SUBSTITUTED": {"true": len(tp), "false": len(fp), "auc_true_gt_false": _auc(tp, fp),
                                         "q_true": _q(tp), "q_false": _q(fp)},
                         "UNCERTAIN": {"true": len(unc_t), "false": len(unc_f), "auc_true_gt_false": _auc(unc_t, unc_f)},
                         "CORRECT": {"marked(missed errors)": len(corr_marked), "clean": len(corr_clean),
                                     "auc_clean_gt_marked": _auc(corr_clean, corr_marked),
                                     "q_marked": _q(corr_marked), "q_clean": _q(corr_clean)}}
        R["separation"] = sep
        # منحنياتُ السياسات
        curves = {}
        for stat in ("mean", "min"):
            for pol in ("demote", "promote"):
                cur = []
                for tau in GRID:
                    ns = [apply_policy(s, c, pol, tau) for s, c in zip(st, per[m]["conf"][stat])]
                    fa, cl, de, mk = lg.counts(rows, acc_of(ns))
                    cur.append([tau, fa, de])
                curves[f"{pol}:{stat}"] = {"clean": cl, "marked": mk, "points": cur}
        R["curves"] = curves
        # تحقّقٌ متقاطعٌ بالتسجيل
        cv = {}
        for stat in ("mean", "min"):
            for pol in ("demote", "promote"):
                chosen, new_st = {}, [None] * len(rows)
                for f in range(FOLDS):
                    tr_ix = [i for i, r in enumerate(rows) if _fold(r["rec"]) != f]
                    te_ix = [i for i, r in enumerate(rows) if _fold(r["rec"]) == f]
                    b_fa, _c, b_de, _m = lg.counts(rows, acc_of(st), tr_ix)
                    best = None
                    for tau in GRID:
                        ns = {i: apply_policy(st[i], per[m]["conf"][stat][i], pol, tau) for i in tr_ix}
                        full = [ns.get(i, st[i]) for i in range(len(rows))]
                        fa, _c2, de, _m2 = lg.counts(rows, acc_of(full), tr_ix)
                        if pol == "demote":
                            key = (b_fa - fa) if de >= b_de else None
                        else:
                            key = (de - b_de) if fa <= b_fa else None
                        if key is not None and key > 0 and (best is None or key > best[0]):
                            best = (key, tau)
                    tau = best[1] if best else None
                    chosen[f] = tau
                    for i in te_ix:
                        new_st[i] = apply_policy(st[i], per[m]["conf"][stat][i], pol, tau) if tau is not None else st[i]
                p = lg.paired(rows, acc_of(st), acc_of(new_st), boot)
                s2 = lg.summarize(rows, acc_of(new_st), boot)
                cv[f"{pol}:{stat}"] = {"tau_by_fold": chosen, "fa_pct": s2["fa_pct"], "fa": s2["fa"], "det": s2["det"],
                                       "det_pct": s2["det_pct"], "paired_vs_baseline": p}
        R["cv"] = cv
        per[m]["acc"] = acc_of(st)
        res["models"][m] = R
    # الفيتو المشروط بالثقة (ج): أذرعُ المنتَج — turbo+base (D-825) · base+tiny (D-826) · tiny+base
    veto = {}
    pairs = [("turbo", st_turbo, "base_q5_1"), ("base_q5_1", None, "tiny"), ("tiny", None, "base_q5_1")]
    for x, stx, y in pairs:
        if y not in per or (stx is None and x not in per):
            continue
        stx = stx if stx is not None else per[x]["st"]
        sty = per[y]["st"]
        for stat in ("mean", "min"):
            cy = per[y]["conf"][stat]
            base_acc = [veto_acc(a, b, c, None) for a, b, c in zip(stx, sty, cy)]
            pts = []
            for tau in GRID:
                acc = [veto_acc(a, b, c, tau) for a, b, c in zip(stx, sty, cy)]
                fa, _cl, de, _mk = lg.counts(rows, acc)
                pts.append([tau, fa, de])
            # CV: أكبرُ كسبِ كشفٍ بلا زيادة اتّهامٍ على التدريب
            new_acc = [None] * len(rows)
            chosen = {}
            for f in range(FOLDS):
                tr_ix = [i for i, r in enumerate(rows) if _fold(r["rec"]) != f]
                te_ix = [i for i, r in enumerate(rows) if _fold(r["rec"]) == f]
                b = lg.counts(rows, base_acc, tr_ix)
                best = None
                for tau in GRID:
                    acc = [veto_acc(a, bb, c, tau) for a, bb, c in zip(stx, sty, cy)]
                    q = lg.counts(rows, acc, tr_ix)
                    if q[0] <= b[0] and q[2] - b[2] > 0 and (best is None or q[2] - b[2] > best[0]):
                        best = (q[2] - b[2], tau)
                chosen[f] = best and best[1]
                for i in te_ix:
                    new_acc[i] = veto_acc(stx[i], sty[i], cy[i], chosen[f]) if chosen[f] is not None else base_acc[i]
            fa0, _c0, de0, _m0 = lg.counts(rows, base_acc)
            vals = [t for t in chosen.values() if t is not None]
            veto[f"{x}+{y}:veto|{stat}"] = {"shipped_rule": [fa0, de0], "points": pts, "cv_tau_by_fold": chosen,
                                            "transfer_tau": max(set(vals), key=lambda t: (vals.count(t), -t)) if vals else None,
                                            "cv_paired_vs_shipped_rule": lg.paired(rows, base_acc, new_acc, boot)}
    res["veto_conf"] = veto
    res["clean_words"], res["marked_words"] = lg.counts(rows, [[False] * r["n_ref"] for r in rows])[1], \
        lg.counts(rows, [[False] * r["n_ref"] for r in rows])[3]
    return res


def g3r(raws_by_set, taus):
    """قاعدةُ `v2_gate.judge_arm`: الكشفُ = اتّهامٌ في ±1 حول الحقن · الكاذبُ خارجَه · كبحُ الانهيار 0.60."""
    plan = {it["id"]: it for it in json.load(open(os.path.join(HERE, "inject_plan_riwaya.json"), encoding="utf-8"))["items"]}
    scored, bad = {}, {}
    for (sname, m), raw in sorted(raws_by_set.items()):
        d = scored.setdefault(sname, {}).setdefault(m, {})
        bad[(sname, m)] = 0
        for iid, it in raw.items():
            if iid not in plan or "error" in it or not it.get("text"):
                continue
            p = plan[iid]
            s, ix, ok = score_idx(p["refText"].split(), it["text"].split(), cfg_for(p.get("riwaya")))
            bad[(sname, m)] += not ok
            d[iid] = (s, {stat: [word_conf(it, x, stat) if ok else None for x in ix] for stat in ("mean", "min")})

    def judge(ids, accfun):
        det = n = fa = tot = 0
        for iid in ids:
            p = plan[iid]
            v = accfun(iid)
            n += 1
            if sum(v) / max(len(v), 1) > COLLAPSE:
                continue
            det += any(v[k] for k in range(len(v)) if abs(k - p["wordIndex"]) <= 1)
            o = [v[k] for k in range(len(v)) if abs(k - p["wordIndex"]) > 1]
            fa += sum(o)
            tot += len(o)
        return {"n": n, "det": det, "fa": fa, "outside_words": tot,
                "det_pct": round(100 * det / max(n, 1), 1), "fa_pct": round(100 * fa / max(tot, 1), 2)}

    out = {}
    for sname, bym in scored.items():
        for m, d in bym.items():
            ids = sorted(d)
            R = {"map_mismatch": bad[(sname, m)], "baseline": judge(ids, lambda i: [w in ACCUSE for w in d[i][0]]),
                 "curves": {}, "transfer": {}, "separation": {}}
            for stat in ("mean", "min"):
                tp, fp = [], []
                for iid in ids:
                    s, conf = d[iid]
                    for k, (v, c) in enumerate(zip(s, conf[stat])):
                        if v == scorer.SUBSTITUTED and c is not None:
                            (tp if abs(k - plan[iid]["wordIndex"]) <= 1 else fp).append(c)
                R["separation"][stat] = {"true": len(tp), "false": len(fp), "auc_true_gt_false": _auc(tp, fp),
                                         "q_true": _q(tp), "q_false": _q(fp)}
                for pol in ("demote", "promote"):
                    def f(t, pol=pol, stat=stat):
                        return judge(ids, lambda i: [w in ACCUSE for w in apply_policy(d[i][0], d[i][1][stat], pol, t)])
                    R["curves"][f"{pol}:{stat}"] = [[t, f(t)["fa"], f(t)["det"]] for t in GRID]
                    t = taus.get((m, f"{pol}:{stat}"))
                    if t is not None:
                        R["transfer"][f"{pol}:{stat}@{t}"] = f(t)
            out[f"{sname}|{m}"] = R
        # الفيتو المشروط على g3r (بالنموذجين معاً)
        if "tiny" in bym and "base_q5_1" in bym:
            ids = sorted(set(bym["tiny"]) & set(bym["base_q5_1"]))
            for x, y in (("base_q5_1", "tiny"), ("tiny", "base_q5_1")):
                X, Y = bym[x], bym[y]
                for stat in ("mean", "min"):
                    def f(t, stat=stat, X=X, Y=Y):
                        return judge(ids, lambda i: veto_acc(X[i][0], Y[i][0], Y[i][1][stat], t))
                    R = {"shipped_rule": f(None), "curve": [[t, f(t)["fa"], f(t)["det"]] for t in GRID]}
                    t = taus.get((f"{x}+{y}:veto", stat))
                    if t is not None:
                        R["transfer"] = {str(t): f(t)}
                    out[f"{sname}|{x}+{y}:veto|{stat}"] = R
    return out


def full_tau(res_models, lg_rows=None):
    """τ للنقل إلى g3r = الأكثرُ تكراراً بين طيّات CV (المسجَّلُ سلفاً: لا اختيارَ على g3r)."""
    taus = {}
    for m, R in res_models.items():
        for k, v in R["cv"].items():
            vals = [t for t in v["tau_by_fold"].values() if t is not None]
            if vals:
                taus[(m, k)] = max(set(vals), key=lambda t: (vals.count(t), -t))
    return taus


def analyze(a) -> int:
    raws = {}
    for p in a.raw:
        d = json.load(open(p, encoding="utf-8"))
        raws[(d["set"], d["model"])] = d["items"]
    lr = {m: v for (s, m), v in raws.items() if s == "learners"}
    res = {"grid": GRID, "folds": FOLDS}
    if lr:
        res["learners"] = learners(lr, a.gold, a.boot)
        taus = full_tau(res["learners"]["models"])
        for k, v in res["learners"]["veto_conf"].items():
            arm, stat = k.split("|")
            if v.get("transfer_tau") is not None:
                taus[(arm, stat)] = v["transfer_tau"]
    else:
        taus = {}
    gr = {k: v for k, v in raws.items() if k[0].startswith("g3r")}
    if gr:
        res["g3r"] = g3r(gr, taus)
    res["transfer_taus"] = {f"{m}|{k}": t for (m, k), t in taus.items()}
    json.dump(res, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    md = render(res)
    open(a.md, "w", encoding="utf-8").write(md)
    print(md)
    return 0


def render(res) -> str:
    L = ["### 🎚️ ثقةُ الرموز من التفريغ الحرّ (RafiqConf) — قياسٌ لا شحن", ""]
    if "learners" in res:
        lr = res["learners"]
        L.append(f"**المتعلّمون** (مسطرة learner_gate): {lr['ruler']['kept_rows']} صفّاً · {lr['ruler']['recordings']} تسجيلاً · "
                 f"{lr['clean_words']} كلمةً سليمة · {lr['marked_words']} خطأً موسوماً")
        L.append(f"- تشخيص: {json.dumps(lr['diag'], ensure_ascii=False)}")
        for m, R in lr["models"].items():
            b = R["baseline"]
            L += ["", f"#### {m} · أساس: اتّهام {b['fa']}/{b['clean_words']} = {b['fa_pct']}٪ · كشف {b['det']}/{b['marked_words']} = {b['det_pct']}٪"]
            for stat, s in R["separation"].items():
                L.append(f"- فصلٌ `{stat}`: SUBSTITUTED صادق {s['SUBSTITUTED']['true']} / كاذب {s['SUBSTITUTED']['false']} · "
                         f"AUC(صادق>كاذب) {s['SUBSTITUTED']['auc_true_gt_false']} · مئينات صادق {s['SUBSTITUTED']['q_true']} · كاذب {s['SUBSTITUTED']['q_false']}")
                L.append(f"  - UNCERTAIN صادق {s['UNCERTAIN']['true']} / كاذب {s['UNCERTAIN']['false']} · AUC {s['UNCERTAIN']['auc_true_gt_false']} · "
                         f"CORRECT على خطأٍ موسوم {s['CORRECT']['marked(missed errors)']} مقابل سليم {s['CORRECT']['clean']} · AUC(سليم>موسوم) {s['CORRECT']['auc_clean_gt_marked']}")
            L += ["", "| السياسة | τ لكلّ طيّة | اتّهام (CV) | كشف (CV) | Δاتّهام [95٪] | McNemar | Δكشف | عدم دونيّة |", "|---|---|---|---|---|---|---|---|"]
            for k, v in R["cv"].items():
                p = v["paired_vs_baseline"]
                L.append(f"| {k} | {list(v['tau_by_fold'].values())} | {v['fa']} = {v['fa_pct']}٪ | {v['det']} = {v['det_pct']}٪ | "
                         f"{p['fa_delta_pts']:+} {p['fa_delta_cluster95']} | {p['fa_mcnemar']['a_only']}↔{p['fa_mcnemar']['b_only']} | "
                         f"{p['det_delta_words']:+} | {'✅' if p['non_inferior'] else '❌'} |")
            for k, c in R["curves"].items():
                L.append(f"- منحنى {k} (τ:اتّهام/كشف): " + " ".join(f"{t}:{fa}/{de}" for t, fa, de in c["points"]))
        L += ["", "#### الفيتو المشروط بالثقة (صحيحُ الشاهد الثاني لا ينقض إلا بثقة ≥ τ)"]
        for k, v in lr["veto_conf"].items():
            p = v["cv_paired_vs_shipped_rule"]
            L.append(f"- {k}: القاعدةُ الحاليّة اتّهام/كشف {v['shipped_rule']} · CV τ {list(v['cv_tau_by_fold'].values())} ⇒ "
                     f"Δاتّهام {p['fa_delta_pts']:+} {p['fa_delta_cluster95']} · Δكشف {p['det_delta_words']:+} · McNemar كشف "
                     f"{p['det_mcnemar']['a_only']}↔{p['det_mcnemar']['b_only']} · منحنى " + " ".join(f"{t}:{fa}/{de}" for t, fa, de in v["points"]))
    if "g3r" in res:
        L += ["", "#### g3r (حقنٌ معلومُ الموضع · قاعدة v2_gate) — τ منقولةٌ من المتعلّمين بلا اختيارٍ هنا"]
        for k, R in res["g3r"].items():
            if "baseline" not in R:
                j = R["shipped_rule"]
                L.append(f"- **{k}** (فيتو): القاعدةُ الحاليّة كشف {j['det']}/{j['n']} · اتّهام {j['fa']}/{j['outside_words']} = {j['fa_pct']}٪"
                         + "".join(f" · نقلٌ τ={t}: كشف {v['det']} ({v['det']-j['det']:+}) · اتّهام {v['fa']} ({v['fa']-j['fa']:+})"
                                   for t, v in R.get("transfer", {}).items())
                         + " · منحنى " + " ".join(f"{t}:{fa}/{de}" for t, fa, de in R["curve"]))
                continue
            b = R["baseline"]
            L.append(f"- **{k}**: أساس كشف {b['det']}/{b['n']} = {b['det_pct']}٪ · اتّهام {b['fa']}/{b['outside_words']} = {b['fa_pct']}٪ · "
                     f"خللُ ربط {R['map_mismatch']}")
            for stat, s in R["separation"].items():
                L.append(f"  - فصلٌ `{stat}`: صادق {s['true']} / كاذب {s['false']} · AUC {s['auc_true_gt_false']} · صادق {s['q_true']} · كاذب {s['q_false']}")
            for t, j in R["transfer"].items():
                L.append(f"  - نقلٌ {t}: كشف {j['det']} ({j['det']-b['det']:+}) · اتّهام {j['fa']} ({j['fa']-b['fa']:+}) = {j['fa_pct']}٪")
            for kk, c in R["curves"].items():
                L.append(f"  - منحنى {kk}: " + " ".join(f"{t}:{fa}/{de}" for t, fa, de in c))
    return "\n".join(L) + "\n"


# ───────────────────────────── ٥) اختبارٌ ذاتيّ ─────────────────────────────
def selftest(_a) -> int:
    # الكلمةُ تُبنى من بايتات رموزٍ قد تكون أنصافَ حروف، والمتوسّطُ على رموزها
    ha = "ال".encode()
    parts = [[(b" " + ha[:3], 0.9), (ha[3:] + "حمد".encode(), 0.5), (b" " + "لله".encode(), 0.2)], [("رب".encode(), 0.8)]]
    w = words_with_conf(parts)
    assert [x["t"] for x in w] == ["الحمد", "لله", "رب"], w
    assert abs(w[0]["mean"] - 0.7) < 1e-9 and w[0]["min"] == 0.5 and w[2]["mean"] == 0.8, w
    # الأحكامُ مطابقةٌ لـscorer.score والفهرسُ يشير إلى المسموع
    cfg = cfg_for("hafs")
    ref = "بِسْمِ ٱللَّهِ ٱلرَّحْمَٰنِ ٱلرَّحِيمِ".split()
    for hyp in ["بسم الله الرحمن الرحيم", "بسم الله الرحمن الرحين", "بسم الرحيم", "اه بسم الله الرحمن كتب الرحيم"]:
        st, ix, ok = score_idx(ref, hyp.split(), cfg)
        assert ok and st == [x[1] for x in scorer.score(ref, hyp, cfg)["words"]], (hyp, st, ix)
    st, ix, ok = score_idx(ref, "اه بسم الله الرحمن الرحيم".split(), cfg)
    assert ix == [[1], [2], [3], [4]], ix
    # السياسات
    S, U, C = scorer.SUBSTITUTED, scorer.UNCERTAIN, scorer.CORRECT
    assert apply_policy([S, S, U, C], [0.2, 0.8, 0.9, 0.1], "demote", 0.5) == [U, S, U, C]
    assert apply_policy([S, S, U, U], [0.2, 0.8, 0.9, None], "promote", 0.5) == [S, S, S, U]
    assert veto_acc([S, S, S], [C, C, S], [0.9, 0.3, 0.9], None) == [False, False, True]
    assert veto_acc([S, S, S], [C, C, S], [0.9, 0.3, 0.9], 0.5) == [False, True, True]
    # ملفُّ -ojf بنصف حرف ورموزٍ خاصّة
    tmp = tempfile.mktemp(suffix=".json")
    body = ('{"transcription":[{"text":"x","tokens":[{"text":"[_BEG_]","id":50364,"p":0.99},'
            '{"text":" \xd8","id":100,"p":0.4},{"text":"\xa7\xd9\x84","id":101,"p":0.6},{"text":"<|endoftext|>","id":50257,"p":1.0}]}]}')
    open(tmp, "wb").write(body.encode("latin-1"))
    t = parse_ojf(tmp)
    assert [x[1] for x in t] == [0.4, 0.6] and b"".join(x[0] for x in t) == " ال".encode(), t
    assert words_with_conf([t])[0]["t"] == "ال"
    os.remove(tmp)
    print("selftest ✅")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--set", required=True)
    r.add_argument("--model", required=True, choices=sorted(LANG))
    r.add_argument("--model-path", required=True)
    r.add_argument("--cli", required=True)
    r.add_argument("--audio", default="")
    r.add_argument("--gold", default=os.path.join(HERE, "learner_gold_v1.jsonl"))
    r.add_argument("--threads", type=int, default=4)
    r.add_argument("--limit", type=int, default=0)
    r.add_argument("--out", required=True)
    z = sub.add_parser("analyze")
    z.add_argument("--raw", nargs="+", required=True)
    z.add_argument("--gold", default=os.path.join(HERE, "learner_gold_v1.jsonl"))
    z.add_argument("--boot", type=int, default=2000)
    z.add_argument("--out", required=True)
    z.add_argument("--md", required=True)
    sub.add_parser("selftest")
    a = ap.parse_args()
    if a.cmd == "run":
        a.cli = os.path.abspath(a.cli)
        return run(a)
    if a.cmd == "analyze":
        a.raw = [p for g in a.raw for p in (glob.glob(g) or [g])]
        return analyze(a)
    return selftest(a)


if __name__ == "__main__":
    sys.exit(main())
