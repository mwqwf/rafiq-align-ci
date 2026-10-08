# -*- coding: utf-8 -*-
"""ملخّصٌ عربيٌّ لنتائج `hop_sim.py` (clean + noisy) يُكتب في ops/out/hop3/summary.md.

    python tools/tasmi_bench/hop_report.py clean.json noisy.json --out ops/out/hop3/summary.md
"""
import argparse
import json
import os


def f(ci, pct=False, d=3):
    if not ci:
        return "—"
    m, lo, hi = ci
    k = 100 if pct else 1
    u = "٪" if pct else ""
    return f"{m*k:.{d}f}{u} [{lo*k:.{d}f}, {hi*k:.{d}f}]"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--out", required=True)
    ap.add_argument("--meta", default="")
    a = ap.parse_args()
    L = ["# قفزة المتابعة السحابيّة 3ث (B) مقابل 1.8ث (A) — محاكاة على g3r", "",
         a.meta, "",
         "> وكيلٌ لا المتابِعُ الحقيقيّ: تفريغ whisper.cpp المحلّيّ (tiny q8 المشحون) بدل Workers AI، وتوقيتُ الكلمات تناسبيّ بالحروف، "
         "وحكمُ «الشاهدين». يقيس أثرَ الهندسة لا مطلقَ الدقّة؛ والحكمُ النهائيّ على المحاكي. الأرقام: متوسط [فاصل ثقة بوتستراب 95٪].", ""]
    for p in a.files:
        d = json.load(open(p, encoding="utf-8"))
        g, name = d["agg"], os.path.basename(p).replace(".json", "")
        L += [f"## المجموعة: {name} ({g['n']} بنداً)", "",
              "| المقياس | A (1.8ث) | B (3ث) | الفرق B−A |", "|---|---|---|---|",
              f"| الكشف | {f(g['detect']['A'], True, 1)} | {f(g['detect']['B'], True, 1)} | {f(g['detect']['B-A'], True, 1)} |",
              f"| الاتّهام الكاذب | {f(g['false_accuse']['A'], True, 2)} | {f(g['false_accuse']['B'], True, 2)} | {f(g['false_accuse']['B-A'], True, 2)} |",
              f"| زمن الحكم بعد نهاية الكلمة (ث) | {f(g['latency_s']['A'], False, 2)} | {f(g['latency_s']['B'], False, 2)} | {f(g['latency_s']['B-A'], False, 2)} |",
              f"| الكلفة: ثوانٍ مرسلة | {g['billed_s']['A']:.0f} | {g['billed_s']['B']:.0f} | توفير {100*(g['saving'] or 0):.1f}٪ |",
              f"| النداءات | {g['calls']['A']} | {g['calls']['B']} | |", "",
              "**الحكم:** " + d.get("verdict", ""), ""]
    L.append("العتبة: كشفٌ B−A حدُّه الأدنى ≥ −3 نقاط، واتّهامٌ كاذبٌ B−A حدُّه الأعلى ≤ +1 نقطة.")
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    open(a.out, "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
