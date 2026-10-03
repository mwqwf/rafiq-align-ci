#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""🎙️ **بصمةُ ضجيج الجلسة مقابل بصمة النافذة** (‏`NoiseGate.liveSessionProfile` · المستشار · 2026-10-02).

«سمّع معي» يكتم كلَّ نافذةٍ (‏3.6ث) ببصمةٍ مقدَّرةٍ **من النافذة نفسِها** (‏المشحون اليوم)، والمفتاحُ المطفأ
يعطيها بصمةً من آخر 30ث من الجلسة. يُقاس هنا بمرآة `denoise.py` (‏المتماثلة مع `NoiseGate` بـ
`NoiseGateParityTest`) على البنود **المضجَّجة** وتوأمِها النظيف:

| الذراع | ما يُسلَّم للنموذج |
|---|---|
| `nogate` | النافذةُ خاماً |
| `gate_win` | كتمٌ ببصمة النافذة (‏= المشحون) |
| `gate_sess` | كتمٌ ببصمةٍ من ≤30ث قبل نهاية النافذة (‏= المفتاح) |

والحقيقةُ الأقرب = فكُّ **النافذة النظيفة نفسِها** (‏`agree_clean`)، ومعها `oov` (‏كلماتٌ ليست في الآية)
و`words/clean` و`mask_open` (‏نسبةُ ما فتحه القناع — انخفاضُه خنقٌ للكلام).
"""
import argparse
import json
import os
import statistics as st
import sys

import numpy as np
import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from speed_ab import norm_words, edits, run_cli, SR  # noqa: E402
import denoise as dn  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cli", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--lang", default="en")
    ap.add_argument("--noisy-src", required=True)
    ap.add_argument("--clean-src", required=True)
    ap.add_argument("--sample", default="sample.json")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--threads", type=int, default=2)
    ap.add_argument("--window", type=float, default=3.6)
    ap.add_argument("--session", type=float, default=30.0)
    # 📈 عيّنةٌ أكبر من بنودٍ محدودة (‏2026-10-03): نوافذُ عدّةٌ في البند الواحد عند كسورٍ من طوله (‏0.5 = الوسط كما كان)،
    # والمجالُ حينئذٍ bootstrap **بعنقود البند** لا بالنافذة (‏نوافذُ البند الواحد غيرُ مستقلّة).
    ap.add_argument("--positions", type=float, nargs="+", default=[0.5])
    ap.add_argument("--max-windows", type=int, default=0, help="سقفُ النوافذ بعد التوسيع (‏0 = بلا سقف)")
    ap.add_argument("--md", required=True)
    ap.add_argument("--json", required=True)
    a = ap.parse_args()

    items = {it["id"]: it for it in json.load(open(a.sample, encoding="utf-8"))["items"]}
    wavs = sorted(f for f in os.listdir(a.noisy_src) if f.endswith(".wav") and f[:-4] in items
                  and os.path.exists(os.path.join(a.clean_src, f)))
    # 🎯 البنودُ التي يسبق نافذتَها كلامٌ كافٍ (‏≥ 8ث) — وإلا فبصمةُ الجلسة هي بصمةُ النافذة تقريباً.
    sel = []
    for f in wavs:
        if sf.info(os.path.join(a.noisy_src, f)).duration >= 8.0:
            sel.append(f)
    wavs = sel[: a.limit] if a.limit else sel
    if not wavs:
        raise SystemExit("⛔ لا بنود")
    # الترتيب: الموضعُ الأوّلُ لكلّ البنود ثمّ الثاني … فالسقفُ يأخذ أوسعَ تنوّعٍ من البنود قبل التكرار فيها.
    jobs = [(f, p) for p in a.positions for f in wavs]
    if a.max_windows:
        jobs = jobs[: a.max_windows]
    tmp = os.path.join(os.path.dirname(a.json) or ".", "crops_noise")
    os.makedirs(tmp, exist_ok=True)
    n = int(a.window * SR)
    arms = ["nogate", "gate_win", "gate_sess"]
    rows = []
    for k, (f, pos) in enumerate(jobs):
        iid = f[:-4]
        x, sr = sf.read(os.path.join(a.noisy_src, f), dtype="float32")
        c, _ = sf.read(os.path.join(a.clean_src, f), dtype="float32")
        s = min(max(0, int(len(x) * pos) - n // 2), max(0, len(x) - n)); e = s + n
        win = x[s:e]
        sess = x[max(0, e - int(a.session * SR)): e]
        prof = dn.estimate_profile(sess)
        y_win, rep_w = dn.denoise(win, report=True)
        y_sess, rep_s = dn.denoise(win, report=True, profile=prof)
        row = {"id": iid, "pos": pos, "win_at": s / SR, "ref": items[iid]["refText"],
               "mask_open": {"gate_win": rep_w.get("maskOpen"), "gate_sess": rep_s.get("maskOpen")}}
        tag = "%s_p%02d" % (iid, int(round(pos * 100)))
        f = tag + ".wav"
        cw = os.path.join(tmp, "clean_" + f); sf.write(cw, c[s:e], SR, subtype="PCM_16")
        _, row["clean"] = run_cli(a.cli, a.model, cw, a.threads, a.lang, [])
        for name, y in (("nogate", win), ("gate_win", y_win), ("gate_sess", y_sess)):
            p = os.path.join(tmp, name + "_" + f)
            sf.write(p, np.clip(y, -1, 1).astype(np.float32), SR, subtype="PCM_16")
            sec, text = run_cli(a.cli, a.model, p, a.threads, a.lang, [])
            row[name] = {"sec": sec, "text": text}
        rows.append(row)
        if (k + 1) % 10 == 0 or k + 1 == len(jobs):
            print("%3d/%d %s" % (k + 1, len(wavs), iid), flush=True)

    summary = {}
    lines = ["## 🎙️ بصمةُ الجلسة مقابل بصمة النافذة — %s · %d نافذةً (‏%.1fث من الوسط · جلسة ≤%.0fث)" % (
        os.path.basename(a.noisy_src.rstrip("/")), len(rows), a.window, a.session), "",
        "| الذراع | agree مع النظيف | oov | words/clean | فارغة | وسيطُ mask_open | وسيطُ الزمن |",
        "|---|---:|---:|---:|---:|---:|---:|"]
    for name in arms:
        ce = cn = oov = tot = ncl = empty = 0
        for r in rows:
            h = norm_words(r[name]["text"]); cw_ = norm_words(r["clean"])
            ce += edits(h, cw_); cn += max(1, len(cw_)); ncl += len(cw_)
            ayah = set(norm_words(r["ref"]))
            oov += sum(1 for w in h if w not in ayah); tot += len(h)
            empty += (len(h) == 0)
        mo = [r["mask_open"].get(name) for r in rows if r["mask_open"].get(name) is not None]
        s = {"agree_clean": 1 - ce / cn, "oov": oov / max(1, tot), "words_ratio": tot / max(1, ncl), "empty": empty,
             "mask_open": st.median(mo) if mo else None, "med_s": st.median(r[name]["sec"] for r in rows), "n": len(rows)}
        summary[name] = s
        lines.append("| %s | %.1f%% | %.1f%% | %.2f | %d | %s | %.3fث |" % (
            name, 100 * s["agree_clean"], 100 * s["oov"], s["words_ratio"], s["empty"],
            ("%.1f%%" % (100 * s["mask_open"])) if s["mask_open"] is not None else "—", s["med_s"]))
    # 🔁 فرقٌ مزدوجٌ بالنافذة (‏gate_sess − gate_win) على الاتّفاق مع النظيف — bootstrap.
    import random
    diffs = []
    clusters = {}
    for r in rows:
        cw_ = norm_words(r["clean"]); d = max(1, len(cw_))
        v = (edits(norm_words(r["gate_win"]["text"]), cw_) - edits(norm_words(r["gate_sess"]["text"]), cw_)) / d
        diffs.append(v); clusters.setdefault(r["id"], []).append(v)
    # bootstrap بعنقود البند (‏يساوي bootstrap النافذة حين تكون نافذةً واحدةً لكلّ بند).
    groups = list(clusters.values())
    rng = random.Random(7); ms = []
    for _ in range(2000):
        pick = [groups[rng.randrange(len(groups))] for _ in range(len(groups))]
        flat = [v for g in pick for v in g]
        ms.append(sum(flat) / len(flat))
    ms.sort(); lo, hi = ms[50], ms[1949]
    pos_lines = []
    for p in a.positions:
        dp = [diffs[i] for i, r in enumerate(rows) if r["pos"] == p]
        if dp and len(a.positions) > 1:
            pos_lines.append("  - الموضع %.2f: %+.2f نقطة على %d نافذةً." % (p, 100 * sum(dp) / len(dp), len(dp)))
    summary["sess_minus_win_agree"] = {"mean": sum(diffs) / len(diffs), "ci": (lo, hi)}
    lines += ["", "- فرقُ الاتّفاق المزدوج (‏`gate_sess` − `gate_win`): **%+.2f نقطة** [%+.2f .. %+.2f] (‏95٪ bootstrap بعنقود البند · %d نافذةً من %d بنداً)." % (
        100 * sum(diffs) / len(diffs), 100 * lo, 100 * hi, len(rows), len(groups))] + pos_lines
    md = "\n".join(lines) + "\n"
    open(a.md, "w", encoding="utf-8").write(md)
    json.dump({"summary": summary, "rows": rows}, open(a.json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(md)


if __name__ == "__main__":
    main()
