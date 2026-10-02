#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""⚡🎯 **مسحُ معاملات الفكّ على نافذة الحلقة الحيّة** (‏«سمّع معي» · المستشار · 2026-10-02).

`speed_ab.py` أجاب سؤالاً واحداً (‏`audio_ctx` بهامش 1ث ⇒ ×11 لكن اتّفاقُ النافذة 79٪/68٪)، وهذا يرسم
**المنحنى** ليُعرف إن وُجدت نقطةٌ بلا خسارة: هوامشُ أكبر، وحدٌّ أدنى للإطارات، و`liveNoFallback`
(‏`-nf` = `temperature_inc 0`)، وعددُ الخيوط — كلُّها على **النافذة نفسِها** من كلّ بند.

**النافذة:** 3.6ث من **وسط** البند (‏لا من أوّله: أوّلُ الآية صمتٌ وبسملةٌ أحياناً، ووسطُها كلامٌ متّصل
كما يرى المحرّكُ في الحلقة). والذراعُ المرجع `ref` = السياقُ الكامل بالأعلام المشحونة
(‏greedy · best_of 5 · التراجعُ الحراريُّ الافتراضيّ · ‏et 2.4 · ‏-nt).

**المقاييس لكلّ ذراع:**
- الزمن: وسيطٌ · p95 · أقصى (‏ثوانٍ · بلا زمن التحميل).
- `agree`: اتّفاقُ كلمات النافذة مع `ref` (‏1 − تحرير/كلمات ref).
- `agree_clean`: للمضجَّج — اتّفاقُه مع فكّ **النافذة النظيفة نفسِها** (‏`--clean-src`): الحقيقةُ الأقرب.
- `oov`: نسبةُ كلمات الذراع التي **ليست في نصّ الآية** أصلاً (‏هلوسةٌ أو تحريف — ما يرفع الاتّهامَ الكاذب في المتابع).
- `words`: مجموعُ الكلمات نسبةً إلى `ref` (‏دون 1 = يفقد كلمات · فوق 1 = يزيد).
- `empty`: نوافذُ خرجت فارغة.

⛔ لا يُشحن شيءٌ من هنا بلا: `agree`/`agree_clean` لا ينخفضان انخفاضاً يُعتدّ به، و`oov` لا يرتفع.
"""
import argparse
import json
import math
import os
import statistics as st
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from speed_ab import norm_words, edits, run_cli, SR  # noqa: E402


def audio_ctx_for(dur_s, pad_s, min_frames=0):
    n = int(math.ceil((dur_s + pad_s) * 50))
    n = max(n, min_frames)
    return min(1500, ((n + 31) // 32) * 32)


def crop_mid(src, dst, seconds, at="mid"):
    import soundfile as sf
    a, sr = sf.read(src, dtype="float32")
    if sr != SR:
        raise SystemExit("⛔ معدّلُ العيّنة %d لا %d" % (sr, SR))
    n = int(seconds * SR)
    if seconds <= 0:                      # 0 = البندُ كاملاً (‏قياسُ الحكم النهائيّ لا النافذة)
        sf.write(dst, a, SR, subtype="PCM_16")
        return len(a) / SR, 0.0
    if at == "start" or len(a) <= n:
        s = 0
    else:
        s = max(0, len(a) // 2 - n // 2)
    seg = a[s: s + n]
    sf.write(dst, seg, SR, subtype="PCM_16")
    return len(seg) / SR, s / SR


def pct(vals, q):
    if not vals:
        return 0.0
    v = sorted(vals)
    k = min(len(v) - 1, int(math.ceil(q * len(v))) - 1)
    return v[max(0, k)]


def build_arms(a):
    """قائمةُ الأذرع: (الاسم، دالّةُ الأعلام بحسب مدّة النافذة)."""
    base_t = ["-t", str(a.threads)]
    arms = [("ref", lambda d: list(base_t))]
    for p in a.pads:
        arms.append(("ac_p%g" % p, (lambda p: lambda d: base_t + ["-ac", str(audio_ctx_for(d, p))])(p)))
    for m in a.mins:
        arms.append(("ac_p1_m%d" % m, (lambda m: lambda d: base_t + ["-ac", str(audio_ctx_for(d, 1.0, m))])(m)))
    if a.nofallback:
        arms.append(("nf", lambda d: base_t + ["-nf"]))
        for p in a.nf_pads:
            arms.append(("nf_ac_p%g" % p, (lambda p: lambda d: base_t + ["-nf", "-ac", str(audio_ctx_for(d, p))])(p)))
    for t in a.thread_arms:
        if t != a.threads:
            arms.append(("t%d" % t, (lambda t: lambda d: ["-t", str(t)])(t)))
    for name, flags in a.extra_arms:
        # 🎛️ رموزٌ في الأعلام: `{ac:P}` ⇒ `-ac` تناسبيّاً بهامش P ث · `env:K=V` ⇒ متغيّرُ بيئةٍ للعمليّة.
        def mk(f):
            def fn(d):
                out = []
                for tok in f:
                    if tok.startswith("{ac:") and tok.endswith("}"):
                        out += ["-ac", str(audio_ctx_for(d, float(tok[4:-1])))]
                    else:
                        out.append(tok)
                return base_t + out
            return fn
        arms.append((name, mk(flags)))
    return arms


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cli", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--lang", default="en")
    ap.add_argument("--src", required=True, help="مجلّدُ البنود (‏wav نظيف أو wavn مضجَّج)")
    ap.add_argument("--clean-src", default="", help="المجلّدُ النظيفُ المقابل (‏لمقياس agree_clean على المضجَّج)")
    ap.add_argument("--sample", default="sample.json")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--threads", type=int, default=2)
    ap.add_argument("--window", type=float, default=3.6, help="0 = البندُ كاملاً")
    ap.add_argument("--max-dur", type=float, default=0, help="يُقصي البنودَ الأطولَ من هذا (‏ثوانٍ) — مثل سقف الحكم النهائيّ 10ث")
    ap.add_argument("--at", default="mid", choices=["mid", "start"])
    ap.add_argument("--pads", type=float, nargs="*", default=[1.0, 2.0, 3.0, 5.0])
    ap.add_argument("--mins", type=int, nargs="*", default=[512, 768, 1024])
    ap.add_argument("--nofallback", action="store_true")
    ap.add_argument("--nf-pads", type=float, nargs="*", default=[])
    ap.add_argument("--thread-arms", type=int, nargs="*", default=[])
    ap.add_argument("--extra-arm", action="append", default=[], help="اسم=أعلامٌ (مثل et18=-et 1.8)")
    ap.add_argument("--md", required=True)
    ap.add_argument("--json", required=True)
    a = ap.parse_args()
    a.extra_arms = []
    for x in a.extra_arm:
        n, f = x.split("=", 1)
        a.extra_arms.append((n, f.split()))

    items = {it["id"]: it for it in json.load(open(a.sample, encoding="utf-8"))["items"]}
    wavs = sorted(f for f in os.listdir(a.src) if f.endswith(".wav") and f[:-4] in items)
    if a.max_dur > 0:
        import soundfile as _sf
        wavs = [f for f in wavs if _sf.info(os.path.join(a.src, f)).duration <= a.max_dur]
    if a.limit:
        wavs = wavs[: a.limit]
    if not wavs:
        raise SystemExit("⛔ لا بنود في %s" % a.src)
    tmp = os.path.join(os.path.dirname(a.json) or ".", "crops_" + os.path.basename(a.src.rstrip("/")))
    os.makedirs(tmp, exist_ok=True)
    arms = build_arms(a)
    names = [n for n, _ in arms]
    rows = []
    t_start = time.time()
    for k, f in enumerate(wavs):
        iid = f[:-4]
        it = items[iid]
        cw = os.path.join(tmp, f)
        cdur, at_s = crop_mid(os.path.join(a.src, f), cw, a.window, a.at)
        row = {"id": iid, "stratum": it.get("stratum"), "win_dur": cdur, "win_at": at_s, "refText": it["refText"]}
        if a.clean_src:
            cc = os.path.join(tmp, "clean_" + f)
            crop_mid(os.path.join(a.clean_src, f), cc, a.window, a.at)
            _, ctext = run_cli(a.cli, a.model, cc, a.threads, a.lang, [])
            row["clean"] = {"text": ctext}
        # 🔁 الأذرعُ تدور مع البند فلا يأخذ ذراعٌ حرارةَ المعالج وحدَه.
        order = arms[k % len(arms):] + arms[: k % len(arms)]
        for name, fl in order:
            flags = fl(cdur)
            # run_cli يضيف -t بنفسه؛ نُزيل تكرارَه بتمرير الخيوط من الأعلام.
            t = a.threads
            while "-t" in flags:            # آخرُ `-t` يغلب (‏كما يفعل مفسّرُ whisper-cli)
                i = flags.index("-t"); t = int(flags[i + 1]); flags = flags[:i] + flags[i + 2:]
            env = {k: v for k, v in (x[4:].split("=", 1) for x in flags if x.startswith("env:"))}
            flags = [x for x in flags if not x.startswith("env:")]
            sec, text = run_cli(a.cli, a.model, cw, t, a.lang, flags, env=env or None)
            row[name] = {"sec": sec, "text": text, "flags": " ".join(["-t", str(t)] + flags + ["%s=%s" % kv for kv in env.items()])}
        rows.append(row)
        if (k + 1) % 10 == 0 or k + 1 == len(wavs):
            print("%3d/%d %s (%.0fث مضت)" % (k + 1, len(wavs), iid, time.time() - t_start), flush=True)

    summary = {}
    lines = ["## 🎯 مسحُ الفكّ على نافذة %.1fث (%s) — %s · %d نافذةً · %d خيوط" % (
        a.window, "وسطُ البند" if a.at == "mid" else "أوّلُ البند", os.path.basename(a.src.rstrip("/")), len(rows), a.threads), "",
        "| الذراع | الأعلام | وسيطُ الزمن | p95 | أقصى | ×أسرع | agree مع ref | تطابقٌ تامّ | WER | " + ("agree مع النظيف | " if a.clean_src else "") + "oov | words/ref | فارغة |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|" + ("---:|" if a.clean_src else "") + "---:|---:|---:|"]
    ref_med = st.median(r["ref"]["sec"] for r in rows)
    for n in names:
        secs = [r[n]["sec"] for r in rows]
        agree_e = agree_n = 0
        ce = cn = 0
        oov = tot = 0
        nref = 0
        empty = 0
        wer_e = wer_n = same = 0
        for r in rows:
            h = norm_words(r[n]["text"])
            rw = norm_words(r["ref"]["text"])
            ay = norm_words(r["refText"])
            wer_e += edits(h, ay); wer_n += max(1, len(ay)); same += (h == rw)
            agree_e += edits(h, rw); agree_n += max(1, len(rw))
            if a.clean_src:
                cw_ = norm_words(r["clean"]["text"])
                ce += edits(h, cw_); cn += max(1, len(cw_))
            ayah = set(norm_words(r["refText"]))
            oov += sum(1 for w in h if w not in ayah); tot += len(h)
            nref += len(rw)
            empty += (len(h) == 0)
        s = {"flags": rows[0][n]["flags"], "med_s": st.median(secs), "p95_s": pct(secs, 0.95), "max_s": max(secs),
             "speedup": ref_med / st.median(secs) if st.median(secs) else None,
             "agree": 1 - agree_e / agree_n, "oov": oov / max(1, tot), "words_ratio": tot / max(1, nref),
             "empty": empty, "n": len(rows), "wer": wer_e / wer_n, "same_text": same}
        if a.clean_src:
            s["agree_clean"] = 1 - ce / cn
        summary[n] = s
        lines.append("| %s | `%s` | %.3fث | %.3fث | %.3fث | ×%.2f | %.1f%% | %d/%d | %.1f%% | " % (
            n, s["flags"], s["med_s"], s["p95_s"], s["max_s"], s["speedup"] or 0, 100 * s["agree"], s["same_text"], s["n"], 100 * s["wer"])
            + ("%.1f%% | " % (100 * s["agree_clean"]) if a.clean_src else "")
            + "%.1f%% | %.2f | %d |" % (100 * s["oov"], s["words_ratio"], s["empty"]))
    lines += ["", "- `ref` = السياقُ الكامل بالأعلام المشحونة (‏greedy · best_of 5 · تراجعٌ حراريٌّ افتراضيّ). "
              "`ac_pX` = ‏`-ac` بهامش X ث (‏50 إطاراً/ث، مقرَّباً إلى 32) · `ac_p1_mN` = هامش 1ث وحدٌّ أدنى N إطاراً · "
              "`nf` = ‏`-nf` (‏`temperature_inc 0` = `liveNoFallback`) · `tN` = N خيوط.",
              "- `oov` = كلماتٌ ليست في نصّ الآية (‏تحريفٌ أو هلوسة) من مجموع كلمات الذراع."]
    md = "\n".join(lines) + "\n"
    open(a.md, "w", encoding="utf-8").write(md)
    json.dump({"summary": summary, "rows": rows, "args": vars(a)}, open(a.json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(md)


if __name__ == "__main__":
    main()
