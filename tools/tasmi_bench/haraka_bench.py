# -*- coding: utf-8 -*-
"""قياسُ الإنذار الكاذب لحكم الحركات (D-249) على عيّنة G1 — تلاواتٌ صحيحة، فكلُّ خلافِ حركةٍ إنذارٌ كاذب.

    python tools/tasmi_bench/haraka_bench.py [--hyps work/hyps_ar_win.json]

مرآةُ `HarakaChecker.kt`: الشدّةُ تُهمل، ورموزُ المغاربة تُردّ إلى حركاتها (ٖ كسرتان · ٗ فتحتان · ٞ ضمّتان).
النتيجة 2026-09-07 (المشحون tiny، 1859 كلمة مطابقة): الوسط 0.75٪ · الآخِر 1.94٪ · الكل 2.69٪.
"""
import argparse, json, os, sys
from collections import Counter
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import scorer, score as S  # noqa: E402

VOWEL = {"َ": "a", "ُ": "u", "ِ": "i", "ْ": "0", "ً": "an", "ٌ": "un", "ٍ": "in"}

def letters(w):
    w = w.replace("ٰ", "ا").replace("ٱ", "ا").replace("ۡ", "ْ").replace("ٖ", "ٍ").replace("ٗ", "ً").replace("ٞ", "ٌ")
    out = []
    for ch in w:
        if "ء" <= ch <= "ي" or ch == "ے": out.append([ch, set()])
        elif ch in VOWEL and out: out[-1][1].add(VOWEL[ch])
    return out

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--hyps", default=os.path.join(HERE, "work", "hyps_ar_win.json")); a = ap.parse_args()
    items = S.load_sample()["items"]; hyps = json.load(open(a.hyps, encoding="utf-8"))["hyps"]
    res = Counter(); comp = 0; ex = []
    for it in items:
        h = hyps.get(it["id"])
        if not h or "error" in h: continue
        cfg = S.config_for("proposed", it["riwaya"])
        ref = it["refText"].split(); s = scorer.score(ref, h["text"], cfg); hypw = h["text"].split()
        for (idx, verdict, heard) in s["words"]:
            if verdict != "CORRECT" or heard is None or " " in heard: continue
            raw = next((x for x in hypw if scorer.norm(x, cfg) == heard), None)
            if raw is None: continue
            r = letters(ref[idx]); q = letters(raw)
            if len(r) != len(q) or any(x[0] != y[0] for x, y in zip(r, q)): continue
            comp += 1
            diffs = [(i, x[1], y[1]) for i, (x, y) in enumerate(zip(r, q)) if x[1] and y[1] and x[1] != y[1]]
            if not diffs: res["ok"] += 1; continue
            last = diffs[-1][0] == len(r) - 1
            kind = "last-only" if (last and len(diffs) == 1) else "inner"
            res[(it["riwaya"], kind)] += 1
            if len(ex) < 10: ex.append((it["riwaya"], ref[idx], raw))
    bad = sum(v for k, v in res.items() if k != "ok")
    inner = sum(v for k, v in res.items() if k != "ok" and k[1] == "inner")
    print(f"كلمات مطابقة {comp} · إنذار كاذب: الكل {bad/comp*100:.2f}% · الوسط {inner/comp*100:.2f}% · الآخِر {(bad-inner)/comp*100:.2f}%")
    print(dict(res))
    for e in ex: print(" ", e)

if __name__ == "__main__":
    main()
