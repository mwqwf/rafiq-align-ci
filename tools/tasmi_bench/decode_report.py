#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""📊 **قراءةُ أثر `tasmi-decode`/`tasmi-decode2` بعد تنزيله** (‏المستشار · 2026-10-02).

    gh run download <run_id> -R mwqwf/rafiq-align-ci -D out && python tools/tasmi_bench/decode_report.py out

لكلّ ملفّ `live_*.json`/`r2*.json`: الجدولُ مع **الفرق المزدوج بالنافذة** [95٪ bootstrap] لاتّفاق كلّ ذراعٍ
مقابل `ref` (‏على المضجَّج: الاتّفاقُ مع النافذة النظيفة) — فالحكمُ لا يُقرأ من فرقِ متوسّطَين بل من مجاله.
"""
import json, glob, os, sys, statistics as st, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from speed_ab import norm_words, edits

D = sys.argv[1]

def boot(diffs, seed=7, n=2000):
    rng = random.Random(seed); ms = []
    for _ in range(n):
        pick = [diffs[rng.randrange(len(diffs))] for _ in range(len(diffs))]
        ms.append(sum(pick) / len(pick))
    ms.sort(); return ms[int(0.025 * n)], ms[int(0.975 * n) - 1]

for p in sorted(glob.glob(D + "/**/live_*.json", recursive=True) + glob.glob(D + "/**/r2*.json", recursive=True)):
    j = json.load(open(p, encoding="utf-8")); rows = j["rows"]; S = j["summary"]
    print("\n###", os.path.basename(p), "n=", len(rows))
    key = "agree_clean" if "agree_clean" in S["ref"] else "agree"
    print("| arm | flags | med | p95 | x | agree_ref | same | WER | agree_clean | oov | words | empty | Δ%s vs ref [95%%] |" % key)
    for n, s in S.items():
        diffs = []
        for r in rows:
            tgt = norm_words(r["clean"]["text"]) if key == "agree_clean" else norm_words(r["ref"]["text"])
            d = max(1, len(tgt))
            diffs.append((edits(norm_words(r["ref"]["text"]), tgt) - edits(norm_words(r[n]["text"]), tgt)) / d)
        lo, hi = boot(diffs)
        print("| %s | %s | %.3f | %.3f | x%.2f | %.1f | %s | %s | %s | %.1f | %.2f | %d | %+.1f [%+.1f..%+.1f] |" % (
            n, s["flags"], s["med_s"], s["p95_s"], s["speedup"] or 0, 100 * s["agree"],
            ("%d/%d" % (s["same_text"], s["n"])) if "same_text" in s else "-", ("%.1f" % (100 * s["wer"])) if "wer" in s else "-",
            ("%.1f" % (100 * s["agree_clean"])) if "agree_clean" in s else "-", 100 * s["oov"], s["words_ratio"], s["empty"],
            100 * sum(diffs) / len(diffs), 100 * lo, 100 * hi))
for p in sorted(glob.glob(D + "/**/noise_*.md", recursive=True) + glob.glob(D + "/**/cloud_vad.md", recursive=True) + glob.glob(D + "/**/r2*.md", recursive=True) + glob.glob(D + "/**/decode_verdict.md", recursive=True)):
    print("\n###", os.path.basename(p)); print(open(p, encoding="utf-8").read())
