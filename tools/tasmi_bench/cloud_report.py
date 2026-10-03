#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""📊☁️ **قراءةُ أثر القياس السحابيّ** — طولُ النافذة (‏`cloud_window_ab.py`) وVAD (‏`cloud_vad_ab.py`) · المستشار · 2026-10-03.

    python tools/tasmi_bench/cloud_report.py --win out/cloud_win.json --vad out/cloud_vad.json --md out/cloud_report.md

المقاييس (‏لكلّ مجموعة × ذراع):
- **هلوسة** = نافذةٌ نصُّها غيرُ قرآنيّ: كلمةٌ من قائمة عبارات القنوات المعروفة (‏«اشتركوا في القناة» · «ترجمة نانسي قنقر»
  · «شكراً للمشاهدة» …) ليست في الآية، **أو** ≥2 كلمتان بلا كلمةٍ واحدةٍ من الآية.
- **WER المحلّي** = تحريرُ الفرضية على **أقرب مقطعٍ متّصلٍ من الآية** (‏محاذاةٌ شبهُ شاملة: بدايةُ الآية ونهايتُها مجّانيّتان)
  مقسوماً على طول ذلك المقطع — فالنافذةُ لا تُعاقَب على ما لم تسمعه. الفارغةُ تُعدّ وحدَها.
- **الاستدعاء** = الكلماتُ المطابِقة ÷ المتوقَّع في النافذة (‏`wordCount × النافذة ÷ مدّة البند`، بسقف `wordCount`).
- **agree مع النظيف** (‏المضجَّج فقط) = 1 − تحرير(نصّ المضجَّج، نصّ النافذة النظيفة نفسِها) ÷ طولِه.
والفرقُ المزدوجُ لكلّ ذراعٍ مقابل الأساس (‏`w3.6` / `novad`) على النوافذ نفسِها، بمجال 95٪ bootstrap (‏2000 · بذرة 7).
"""
import argparse
import json
import os
import random
import statistics as st
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from speed_ab import norm_words, edits  # noqa: E402

BLACK = {norm_words(w)[0] for w in ("اشتركوا", "القناة", "ترجمة", "نانسي", "قنقر", "للمشاهدة", "المشاهدة", "موسيقى",
                                    "المترجم", "تابعونا", "لايك", "الاشتراك", "اشترك", "قناتي")}


def semiglobal(h, r):
    """(التحرير، طول مقطع الآية، المطابَقات) لأفضل محاذاةٍ للفرضية h على مقطعٍ متّصلٍ من r."""
    m, n = len(h), len(r)
    if m == 0:
        return 0, 0, 0
    D = [[0] * (n + 1) for _ in range(m + 1)]
    B = [[0] * (n + 1) for _ in range(m + 1)]  # 0 قطري · 1 إدراج (فرضية) · 2 حذف (آية)
    for i in range(1, m + 1):
        D[i][0] = i; B[i][0] = 1
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            c = (D[i - 1][j - 1] + (h[i - 1] != r[j - 1]), 0)
            c = min(c, (D[i - 1][j] + 1, 1), (D[i][j - 1] + 1, 2))
            D[i][j], B[i][j] = c
    jend = min(range(n + 1), key=lambda j: (D[m][j], -j))
    best = D[m][jend]
    i, j, match = m, jend, 0
    while i > 0:
        b = B[i][j]
        if b == 0:
            match += (h[i - 1] == r[j - 1]); i -= 1; j -= 1
        elif b == 1:
            i -= 1
        else:
            j -= 1
    return best, jend - j, match


def classify(text, ref):
    h = norm_words(text); ay = set(norm_words(ref))
    blk = any(w in BLACK and w not in ay for w in h)
    nomatch = len(h) >= 2 and not any(w in ay for w in h)
    return h, (blk or nomatch), blk


def boot(diffs, n=2000, seed=7):
    if not diffs:
        return float("nan"), float("nan")
    rng = random.Random(seed); ms = []
    for _ in range(n):
        pick = [diffs[rng.randrange(len(diffs))] for _ in range(len(diffs))]
        ms.append(sum(pick) / len(pick))
    ms.sort(); return ms[int(0.025 * n)], ms[int(0.975 * n) - 1]


def per_window(row, arm, clean_text=None, expected=None):
    c = row[arm]
    if c["status"] != 200:
        return None
    h, hall, blk = classify(c["text"], row["ref"])
    e, span, match = semiglobal(h, norm_words(row["ref"]))
    out = {"sec": c["sec"], "hall": hall, "blk": blk, "empty": len(h) == 0, "edits": e, "span": span, "match": match,
           "words": len(h), "lwer": (e / span) if span else (1.0 if h else None)}
    if expected:
        out["recall"] = min(1.0, match / expected)
    if clean_text is not None:
        cw = norm_words(clean_text)
        out["agree_clean"] = 1 - edits(h, cw) / max(1, len(cw))
    return out


def analyze(rows, arms, base, label, expected_fn=None, clean_arm_fn=None):
    lines = []
    clean_by = {r["id"]: r for r in rows if r["set"] == "wav"}
    summary = {}
    for set_ in sorted({r["set"] for r in rows}):
        rs = [r for r in rows if r["set"] == set_]
        lines += ["", "### %s — `%s` · %d بنداً" % (label, set_, len(rs)), "",
                  "| الذراع | ن | وسيطُ الزمن | p95 | **هلوسة** | منها عبارةُ قناة | فارغة | WER المحلّي | الاستدعاء | agree مع النظيف | Δ WER المحلّي [95٪] | Δ الهلوسة [95٪] | Δ agree مع النظيف [95٪] |",
                  "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
        W = {}
        for arm in arms:
            W[arm] = {}
            for r in rs:
                ct = None
                if set_ != "wav" and r["id"] in clean_by:
                    ca = clean_arm_fn(arm) if clean_arm_fn else arm
                    cc = clean_by[r["id"]].get(ca)
                    ct = cc["text"] if cc and cc["status"] == 200 else None
                pw = per_window(r, arm, ct, expected_fn(r, arm) if expected_fn else None)
                if pw:
                    W[arm][r["id"]] = pw
        for arm in arms:
            ws = list(W[arm].values())
            if not ws:
                continue
            secs = sorted(w["sec"] for w in ws)
            sp = sum(w["span"] for w in ws); ed = sum(w["edits"] for w in ws if w["span"])
            rec = [w["recall"] for w in ws if "recall" in w]
            ag = [w["agree_clean"] for w in ws if "agree_clean" in w]
            ids = [i for i in W[arm] if i in W[base]]
            d_l = [(W[arm][i]["lwer"] or 0) - (W[base][i]["lwer"] or 0) for i in ids
                   if W[arm][i]["lwer"] is not None and W[base][i]["lwer"] is not None]
            d_h = [int(W[arm][i]["hall"]) - int(W[base][i]["hall"]) for i in ids]
            d_a = [W[arm][i]["agree_clean"] - W[base][i]["agree_clean"] for i in ids
                   if "agree_clean" in W[arm][i] and "agree_clean" in W[base][i]]

            def fmt(d):
                if not d or arm == base:
                    return "—"
                lo, hi = boot(d); return "%+.1f [%+.1f..%+.1f]" % (100 * sum(d) / len(d), 100 * lo, 100 * hi)
            s = {"n": len(ws), "med_s": st.median(secs), "p95_s": secs[min(len(secs) - 1, int(0.95 * len(secs)))],
                 "hall": sum(w["hall"] for w in ws), "blk": sum(w["blk"] for w in ws), "empty": sum(w["empty"] for w in ws),
                 "lwer": ed / sp if sp else None, "recall": sum(rec) / len(rec) if rec else None,
                 "agree_clean": sum(ag) / len(ag) if ag else None,
                 "d_lwer": (sum(d_l) / len(d_l), boot(d_l)) if d_l and arm != base else None,
                 "d_hall": (sum(d_h) / len(d_h), boot(d_h)) if d_h and arm != base else None,
                 "d_agree": (sum(d_a) / len(d_a), boot(d_a)) if d_a and arm != base else None}
            summary[set_ + "/" + arm] = s
            lines.append("| %s | %d | %.2fث | %.2fث | **%d** (%.1f%%) | %d | %d | %s | %s | %s | %s | %s | %s |" % (
                arm, s["n"], s["med_s"], s["p95_s"], s["hall"], 100 * s["hall"] / s["n"], s["blk"], s["empty"],
                "%.1f%%" % (100 * s["lwer"]) if s["lwer"] is not None else "—",
                "%.1f%%" % (100 * s["recall"]) if s["recall"] is not None else "—",
                "%.1f%%" % (100 * s["agree_clean"]) if s["agree_clean"] is not None else "—",
                fmt(d_l), fmt(d_h), fmt(d_a)))
    return lines, summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--win", default="")
    ap.add_argument("--vad", default="")
    ap.add_argument("--md", required=True)
    ap.add_argument("--json", default="")
    a = ap.parse_args()
    lines, out = ["## ☁️ القياسُ السحابيّ — طولُ النافذة وVAD (‏large-v3-turbo عبر `/v1/tasmi/stream`)"], {}
    if a.win and os.path.exists(a.win):
        j = json.load(open(a.win, encoding="utf-8"))
        arms = j["arms"]

        def exp(r, arm):
            wc = r.get("wordCount") or len(norm_words(r["ref"]))
            return max(1.0, min(wc, wc * r[arm]["win"] / max(0.1, r["dur"])))
        l, s = analyze(j["rows"], arms, arms[0], "طولُ النافذة (‏بلا VAD)", exp)
        lines += ["", "أُرسل %.1f دقيقة صوت." % (j["sent_ms"] / 60000)] + l; out["win"] = s
    if a.vad and os.path.exists(a.vad):
        j = json.load(open(a.vad, encoding="utf-8"))
        # المرجعُ النظيفُ لكلا الذراعين = نصُّ النافذة النظيفة بلا VAD (‏كما في حكم 2026-10-02).
        l, s = analyze(j["rows"], ["novad", "vad"], "novad", "VAD السحابيّ (‏نافذة 3.6ث)", None, lambda arm: "novad")
        lines += ["", "أُرسل %.1f دقيقة صوت." % (j["sent_ms"] / 60000)] + l; out["vad"] = s
    md = "\n".join(lines) + "\n"
    open(a.md, "w", encoding="utf-8").write(md)
    if a.json:
        json.dump(out, open(a.json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(md)


if __name__ == "__main__":
    main()
