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
        arms = [x for x in ("A", "B", "C") if x in g["billed_s"]]
        hd = "| المقياس | " + " | ".join(f"{x} ({ {'A':'1.8ث','B':'3ث','C':'2.4ث'}[x]})" for x in arms) + " | " + " | ".join(f"{x}−A" for x in arms[1:]) + " |"
        L += [f"## المجموعة: {name} ({g['n']} بنداً)", "", hd, "|" + "---|" * (len(arms) * 2)]
        for lab, key, pct, dg in (("الكشف", "detect", True, 1), ("الاتّهام الكاذب", "false_accuse", True, 2), ("زمن الحكم بعد نهاية الكلمة (ث)", "latency_s", False, 2)):
            L.append(f"| {lab} | " + " | ".join(f(g[key][x], pct, dg) for x in arms) + " | " + " | ".join(f(g[key][x + "-A"], pct, dg) for x in arms[1:]) + " |")
        L.append("| الكلفة: ثوانٍ مرسلة | " + " | ".join(f"{g['billed_s'][x]:.0f}" for x in arms) + " | " + " | ".join(f"توفير {100*(g['savings'][x] or 0):.1f}٪" for x in arms[1:]) + " |")
        L.append("| النداءات | " + " | ".join(str(g["calls"][x]) for x in arms) + " | " + " | ".join("" for _ in arms[1:]) + " |")
        L += ["", "**الحكم:** " + d.get("verdict", ""), ""]
    L.append("العتبة: كشفٌ B−A حدُّه الأدنى ≥ −3 نقاط، واتّهامٌ كاذبٌ B−A حدُّه الأعلى ≤ +1 نقطة.")
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    open(a.out, "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
