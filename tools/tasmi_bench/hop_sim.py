# -*- coding: utf-8 -*-
"""⏩ **قياسُ عدم الدونيّة لقفزة المتابعة السحابيّة 3ث مقابل 1.8ث** (`RECITE_CLOUD_HOP3` · 2026-10-08).

محاكاةٌ بايثونيّةٌ **مستقلّة** لمنطق نوافذ «سمّع معي» السحابيّة — لا مصدرَ تطبيقٍ ولا سرَّ منقول:
  • الذراع A (المشحون): قفزة 1.8ث، نافذة `followSpan` (3.6ث/تداخل 2ث) مُمدَّدةً إلى 6ث (`cloudMinFrom`).
  • الذراع B (المرشَّح): قفزة 3ث، نافذة 6ث/تداخل 3ث (هندسةُ مسار الضغط).
  الدالتان `follow_span` و`cloud_min_from` مرآةٌ لـ`ReciteWithMeViewModel.followSpan/cloudMinFrom` (ثوانٍ بدل عيّنات).

ما يقيسه:
  ١) **الكلفة**: ثواني الصوت المرسلة (ما يعدّه الخادمُ على الحصّة) وعددُ النداءات — بلا صوت (`--cost-only`).
  ٢) **الدقّة (وكيلٌ لا المتابِعُ نفسُه)**: على بنود g3r (آيةٌ فيها حقنٌ OMIT/SUBSTITUTE/SWAP/INSERT) تُقطع الآيةُ بنوافذ
     كلّ ذراع وتُفرَّغ كلُّ نافذة، ثم تُحكم كلُّ كلمةٍ بمرآة الحاكم `scorer.score` بقاعدة «الشاهدين»: **تُتّهم الكلمةُ
     إن لم تصحّ في كلّ نافذةٍ تغطّيها**. المقياسان: **الكشف** (كلمةُ الهدف مُتّهمة) و**الاتّهام الكاذب** (كلمةٌ
     بعيدةٌ عن الهدف مُتّهمة)، بفرقٍ مزدوجٍ B−A وبوتستراب [95٪] على البنود، وزمنُ الحكم = نهايةُ أوّل نافذةٍ تغطّي
     الكلمةَ كلَّها − نهايةِ الكلمة. والعتبة: كشفٌ B−A ≥ −3 نقاط (الحدّ الأدنى للمجال) واتّهامٌ كاذبٌ B−A ≤ +1 نقطة (الحدّ الأعلى).
  ⚠️ **حدودُ الوكيل**: (أ) التفريغُ whisper.cpp المحلّيّ (tiny/base q8) لا large-v3-turbo في Workers AI — فيقيس
     **أثرَ الهندسة** لا مطلقَ الدقّة؛ (ب) توقيتُ الكلمات تناسبيٌّ بالحروف؛ (ج) المتابِعُ الحقيقيّ (Kotlin) أغنى من قاعدة
     الشاهدين. فالحكمُ النهائيّ بعدها على المحاكي (`emu-gate`).
  ⛔ **لا يلزمه سرٌّ**: التفريغُ محلّيّ. أمّا **نداءُ Workers AI الحقيقيّ** (ذراعٌ سحابيٌّ كامل) فيلزمه سرُّ الخادم في
     المستودع الخاصّ فلا يُجرى هنا.

    python tools/tasmi_bench/hop_sim.py --selftest
    python tools/tasmi_bench/hop_sim.py --cost-only
    python tools/tasmi_bench/hop_sim.py --set clean --cli bin/whisper-cli --model <ggml-q8.bin> --limit 80
    python tools/tasmi_bench/hop_sim.py --set noisy --cli bin/whisper-cli --model <ggml-q8.bin>
(الصوتُ يُبنى كما في `tasmi-gate.yml`: fetch_audio.py ثم inject_riwaya_local.py إلى work/g3r/{clean,noisy}.)
"""
import argparse
import hashlib
import json
import os
import random
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

SR = 16_000
MAX_WINDOW_S = 8.0
MIN_WINDOW_S = 6.0
SPEECH_TAIL_S = 0.4


def follow_span(total, last_end, last_speech_end, window=3.6, overlap=2.0):
    """مرآةُ `ReciteWithMeViewModel.followSpan`."""
    frm = max(0.0, min(total - window, last_end - overlap), total - MAX_WINDOW_S)
    to = min(total, last_speech_end + SPEECH_TAIL_S)
    if to - frm < 0.5:
        return None
    return frm, to


def cloud_min_from(frm, to, floor=0.0, min_s=MIN_WINDOW_S):
    """مرآةُ `cloudMinFrom`: تمديدٌ إلى الوراء حتى 6ث، أو None إن لم يتسع."""
    if to - frm >= min_s:
        return frm
    cand = to - min_s
    return cand if cand >= floor - 1e-9 else None


ARMS = {
    "A": dict(hop=1.8, window=3.6, overlap=2.0),   # المشحون (CLOUD_HOP_MS = 1800)
    "B": dict(hop=3.0, window=6.0, overlap=3.0),   # المرشَّح (SLOW_CLOUD_HOP_MS · SLOW_WINDOW_MS · SLOW_OVERLAP_MS)
    "C": dict(hop=2.4, window=6.0, overlap=3.6),   # نقطة الوسط (2.4ث · نافذة 6ث · تداخل = نافذة − قفزة كما في B)
}


def windows(arm, dur):
    """نوافذُ تلاوةٍ متّصلةٍ طولُها `dur`: قائمة (بدء، نهاية) المرسَلة فعلاً بالحلقة نفسها (نبضٌ كلَّ hop)."""
    g = ARMS[arm]
    out, total, last_end = [], 0.0, 0.0
    while total + g["hop"] <= dur + 1e-9:
        total += g["hop"]
        sp = follow_span(total, last_end, total, g["window"], g["overlap"])
        if sp is None:
            last_end = total
            continue
        last_end = total
        frm = cloud_min_from(sp[0], sp[1], floor=max(0.0, total - MAX_WINDOW_S))
        out.append((sp[0] if frm is None else frm, sp[1]))   # `?: audio` في الإنتاج
    if last_end < dur - 0.3:                                  # تمريرة الإنهاء
        sp = follow_span(dur, last_end, dur, g["window"], g["overlap"])
        if sp:
            frm = cloud_min_from(sp[0], sp[1], floor=max(0.0, dur - MAX_WINDOW_S))
            out.append((sp[0] if frm is None else frm, sp[1]))
    return out


def billed(arm, dur):
    w = windows(arm, dur)
    return sum(b - a for a, b in w), len(w)


def word_times(words, dur, skip=None):
    """(بدء، نهاية) لكلّ كلمة مرجعيّة، تناسبيّاً بالحروف؛ كلمةُ `skip` (المحذوفةُ من الصوت) بمدّةٍ ضئيلة عند موضعها (فتُحكم «غائبة» بجيرانها)."""
    weights = [0.05 if i == skip else max(1, len(w)) for i, w in enumerate(words)]   # المحذوفة: شقٌّ ضئيلٌ عند الموضع ليُحكم غيابُها
    tot = float(sum(weights)) or 1.0
    t, out = 0.0, []
    for wt in weights:
        out.append((t, t + dur * wt / tot)); t += dur * wt / tot
    return out


def judge(words, times, wins, hyps, scorer, margin=1):
    """لكلّ كلمةٍ (متّهمة؟، زمنُ الحكم). قاعدة الشاهدين: متّهمةٌ إن لم تصحّ في **كلّ** نافذةٍ تغطّيها كلَّها."""
    n = len(words)
    votes = [[] for _ in range(n)]
    first_cover = [None] * n
    for (a, b), hyp in zip(wins, hyps):
        idx = [i for i in range(n) if times[i][1] > times[i][0] and times[i][0] >= a - 0.05 and times[i][1] <= b + 0.05]
        if not idx:
            continue
        lo, hi = max(0, idx[0] - margin), min(n, idx[-1] + 1 + margin)
        res = scorer.score(words[lo:hi], hyp)["words"]
        for i in idx:
            votes[i].append(res[i - lo][1] == scorer.CORRECT)
            if first_cover[i] is None:
                first_cover[i] = b
    out = []
    for i in range(n):
        if not votes[i]:
            out.append((None, None))
        else:
            out.append((not all(votes[i]), first_cover[i] - times[i][1]))
    return out


def load_wav(path):
    import soundfile as sf
    x, sr = sf.read(path, dtype="float32")
    if x.ndim > 1:
        x = x.mean(axis=1)
    if sr != SR:
        from scipy.signal import resample_poly
        x = resample_poly(x, SR, sr).astype("float32")
    return x


class CliDecoder:
    """whisper-cli على مقطعٍ مقصوص؛ مخبّأٌ بمفتاح (ملف، بدء، نهاية) فلا يُعاد تفريغُ نافذةٍ مشتركة."""

    def __init__(self, cli, model, lang="ar", threads=4):
        self.cli, self.model, self.lang, self.threads = cli, model, lang, threads
        self.cache = {}
        h = subprocess.run([cli, "--help"], capture_output=True, text=True)
        self.flags = ["-nc"] if "-nc" in (h.stdout + h.stderr) else []   # كما في local_whisper (غيابُه في بعض الإصدارات)

    def __call__(self, wav_path, audio, a, b):
        key = hashlib.md5(f"{wav_path}|{a:.3f}|{b:.3f}".encode()).hexdigest()
        if key in self.cache:
            return self.cache[key]
        import numpy as np
        import soundfile as sf
        seg = audio[int(a * SR):int(b * SR)]
        with tempfile.TemporaryDirectory() as td:
            f = os.path.join(td, "w.wav")
            sf.write(f, seg.astype(np.float32), SR, subtype="PCM_16")
            r = subprocess.run([self.cli, "-m", self.model, "-f", f, "-l", self.lang, "-t", str(self.threads),
                                "-bo", "1", "-bs", "1", "-nt", "-np"] + self.flags,
                               capture_output=True, text=True, timeout=300)
            if r.returncode != 0:
                raise RuntimeError(f"whisper-cli rc={r.returncode}: {r.stderr[-200:]}")
            text = " ".join(r.stdout.split())
        self.cache[key] = text
        return text


def measure_item(it, wav_path, decoder, scorer):
    audio = load_wav(wav_path)
    dur = len(audio) / SR
    words = it["refText"].split()
    skip = it["wordIndex"] if it["op"] == "OMIT" else None
    times = word_times(words, dur, skip)
    res = {}
    for arm in ARMS:
        wins = [(a, min(b, dur)) for a, b in windows(arm, dur)]
        hyps = [decoder(wav_path, audio, a, b) for a, b in wins]
        s, c = billed(arm, dur)
        res[arm] = {"verdict": judge(words, times, wins, hyps, scorer), "billed": s, "calls": c}
    return {"id": it["id"], "op": it["op"], "target": it["wordIndex"], "n": len(words), "skip": skip, "dur": dur, "arms": res}


def aggregate(rows, seed=7, boot=2000):
    def per_item(r, arm):
        v, t = r["arms"][arm]["verdict"], r["target"]
        det = v[t][0] if 0 <= t < len(v) else None
        others = [x[0] for i, x in enumerate(v) if abs(i - t) > 1 and x[0] is not None and i != r["skip"]]
        lat = [x[1] for x in v if x[1] is not None]
        return det, (sum(others) / len(others) if others else None), (sum(lat) / len(lat) if lat else None)
    table = {a: [per_item(r, a) for r in rows] for a in ARMS}
    rng = random.Random(seed)

    def ci(xs):
        xs = [x for x in xs if x is not None]
        if not xs:
            return None
        ms = sorted(sum(rng.choice(xs) for _ in xs) / len(xs) for _ in range(boot))
        return sum(xs) / len(xs), ms[int(0.025 * boot)], ms[int(0.975 * boot)]

    out = {"n": len(rows)}
    others = [a for a in ARMS if a != "A"]
    for k, name in ((0, "detect"), (1, "false_accuse"), (2, "latency_s")):
        a = [None if t[k] is None else float(t[k]) for t in table["A"]]
        out[name] = {"A": ci(a)}
        for arm in others:
            b = [None if t[k] is None else float(t[k]) for t in table[arm]]
            d = [(y - x) if (x is not None and y is not None) else None for x, y in zip(a, b)]
            out[name][arm] = ci(b)
            out[name][arm + "-A"] = ci(d)
    out["billed_s"] = {a: sum(r["arms"][a]["billed"] for r in rows) for a in ARMS}
    out["calls"] = {a: sum(r["arms"][a]["calls"] for r in rows) for a in ARMS}
    out["saving"] = (1 - out["billed_s"]["B"] / out["billed_s"]["A"]) if out["billed_s"]["A"] else None
    out["savings"] = {a: (1 - out["billed_s"][a] / out["billed_s"]["A"]) if out["billed_s"]["A"] else None for a in others}
    return out


def verdict_text(agg, margin_det=0.03, margin_fa=0.01):
    parts = []
    for arm in [a for a in ARMS if a != "A"]:
        d, f = agg["detect"].get(arm + "-A"), agg["false_accuse"].get(arm + "-A")
        if not d or not f:
            parts.append(f"{arm}: لا بنود كافية")
            continue
        ok = d[1] >= -margin_det and f[2] <= margin_fa
        parts.append(f"{arm}: " + ("✅ عدمُ دونيّة" if ok else "⛔ لا يثبت عدمُ الدونيّة") +
                     f" (كشف {arm}−A {d[0]:+.3f} [{d[1]:+.3f}, {d[2]:+.3f}] · اتّهام كاذب {arm}−A {f[0]:+.4f} [{f[1]:+.4f}, {f[2]:+.4f}])")
    return " | ".join(parts)


def selftest():
    sa, ca = billed("A", 60.0); sb, cb = billed("B", 60.0)
    assert abs(sa / 60 - 3.33) < 0.1, sa / 60
    assert abs(sb / 60 - 2.0) < 0.1, sb / 60
    assert abs((1 - sb / sa) - 0.40) < 0.02, 1 - sb / sa
    assert 32 <= ca <= 34 and 19 <= cb <= 21, (ca, cb)
    for arm in ARMS:
        for a, b in windows(arm, 60.0)[3:]:
            assert b - a <= 6.0 + 1e-6, (arm, a, b)
    assert ARMS["B"]["overlap"] >= ARMS["B"]["hop"]
    sc, cc = billed("C", 60.0)
    assert sb < sc < sa and cb < cc < ca, (sa, sc, sb)           # C بين A وB كلفةً
    assert cloud_min_from(4.0, 8.0, floor=0.0) == 2.0
    assert cloud_min_from(0.0, 3.8, floor=0.0) is None
    t = word_times(["ab", "cde", "f"], 10.0)
    assert abs(t[-1][1] - 10.0) < 1e-9

    class FakeScorer:
        CORRECT = "CORRECT"
        @staticmethod
        def score(ref, hyp):
            return {"words": [(i, "CORRECT" if w in hyp.split() else "MISSED", None) for i, w in enumerate(ref)]}
    words = ["a", "b", "c", "d"]; times = word_times(words, 8.0)     # a[0,2] b[2,4] c[4,6] d[6,8]
    wins = [(0.0, 5.0), (3.0, 8.0)]
    v = judge(words, times, wins, ["a b", "c d"], FakeScorer)
    assert v[1][0] is False and v[2][0] is False                    # كلّ كلمةٍ مغطّاةٌ بنافذةٍ صحيحة
    v = judge(words, times, wins, ["a c", "c d"], FakeScorer)
    assert v[1][0] is True                                          # b غائبة من النافذة الأولى
    print("selftest: ok  (A: %.2f ث/ث، %d نداء/د · B: %.2f ث/ث، %d نداء/د · توفير %.1f٪)" % (sa / 60, ca, sb / 60, cb, 100 * (1 - sb / sa)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--cost-only", action="store_true")
    ap.add_argument("--set", default="clean", choices=["clean", "noisy"])
    ap.add_argument("--cli", default="bin/whisper-cli")
    ap.add_argument("--model", default=None)
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--lang", default="ar")
    ap.add_argument("--shard", default=None, help="k/N: يعالج البنودَ ذاتَ الفهرس ≡ k (mod N) — للتوازي على CI")
    ap.add_argument("--merge", nargs="+", default=None, help="ملفّاتُ rows لشظايا نفسِ المجموعة: تُدمج وتُجمَّع")
    ap.add_argument("--plan", default=os.path.join(HERE, "inject_plan_riwaya.json"))
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    if args.cost_only:
        print("طولُ التلاوة (ث) | A: ث مرسلة · نداء | B: ث مرسلة · نداء | توفير")
        for d in (10, 20, 30, 60, 120, 300):
            sa, ca = billed("A", float(d)); sb, cb = billed("B", float(d))
            print(f"{d:>5} | {sa:7.1f} · {ca:3d} | {sb:7.1f} · {cb:3d} | {100 * (1 - sb / sa):5.1f}٪")
        return
    if args.merge:
        rows = []
        for f in args.merge:
            rows += json.load(open(f, encoding="utf-8"))["rows"]
        agg = aggregate(rows)
        print(json.dumps(agg, ensure_ascii=False, indent=1)); print(verdict_text(agg))
        if args.out:
            json.dump({"agg": agg, "verdict": verdict_text(agg), "rows": rows}, open(args.out, "w", encoding="utf-8"), ensure_ascii=False)
        return
    import scorer
    if not args.model:
        raise SystemExit("⛔ --model مطلوب (ggml q8 محلّي؛ التفريغُ محلّيّ ولا سرَّ يلزم)")
    plan = json.load(open(args.plan, encoding="utf-8"))["items"]
    wdir = os.path.join(HERE, "work", "g3r", args.set)
    items = [(it, os.path.join(wdir, it["id"] + ".wav")) for it in plan]
    items = [(it, p) for it, p in items if os.path.exists(p)]
    if args.limit:
        random.Random(1).shuffle(items); items = items[:args.limit]
    if not items:
        raise SystemExit(f"⛔ لا صوتَ في {wdir} — ابنِ المجموعةَ أوّلاً (fetch_audio.py · inject_riwaya_local.py) كما في tasmi-gate.yml")
    if args.shard:
        k, n = (int(x) for x in args.shard.split("/"))
        items = [x for i, x in enumerate(items) if i % n == k]
    dec = CliDecoder(args.cli, args.model, lang=args.lang, threads=args.threads)
    rows = []
    for k, (it, p) in enumerate(items, 1):
        rows.append(measure_item(it, p, dec, scorer))
        if k % 10 == 0:
            print(f"… {k}/{len(items)}", flush=True)
    agg = aggregate(rows)
    print(json.dumps(agg, ensure_ascii=False, indent=1))
    print(verdict_text(agg))
    out = args.out or os.path.join(HERE, "work", f"hop_sim_{args.set}.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump({"agg": agg, "verdict": verdict_text(agg), "rows": rows}, open(out, "w", encoding="utf-8"), ensure_ascii=False)
    print("→", out)


if __name__ == "__main__":
    main()
