# -*- coding: utf-8 -*-
"""📜 الحكمُ بالتسجيل المسبق رقم 2 (`results/forced/PREREG_2.md`) — يقرأ سجلّاتِ `forced_auc.py --words` ويحكم حرفياً.

المعيار (لكلّ نموذجٍ على حدة): AUC ≥ 0.80 **وحدُّ المجال الأدنى ≥ 0.75** — إحصاء margin · صورة tash · موجَب OMIT/SUBSTITUTE بعينه ·
سالبٌ خارج النطاق · g3r المضجَّج · bootstrap عنقوديّ بالبند (2000). والثانويّ (‏لا يحكم): عتبةٌ مسجَّلةٌ مسبقاً لكلّ نموذج.

    python tools/tasmi_bench/forced_prereg2.py --words w.json --md o.md --json o.json
    python tools/tasmi_bench/forced_prereg2.py --selftest
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import detect_score as D  # noqa: E402
import forced_auc as F  # noqa: E402

AUC_BAR, LOWER_BAR = 0.80, 0.75
THRESH = {"tiny": 3.5097, "base": 3.3374}   # ⛔ مسجَّلةٌ مسبقاً في PREREG_2.md (‏المئين 95 للسالب في العيّنة الأولى)
OPS = ("OMIT", "SUBSTITUTE")


def judge(recs, n_boot=2000):
    sub = [r for r in recs if r["set"] == "g3rn" and r["op"] in OPS]
    s = F.summarize(sub, "tash", "margin", "exact", n_boot)
    ok = s["auc"] is not None and s["ci"] is not None and s["auc"] >= AUC_BAR and s["ci"][0] >= LOWER_BAR
    return sub, s, ok


def secondary(sub, thr):
    pos = [r["sc"]["tash"]["margin"] for r in sub if r["label"] == "pos"]
    neg = [r["sc"]["tash"]["margin"] for r in sub if r["label"] == "neg"]
    det = sum(1 for v in pos if v > thr)
    fa = sum(1 for v in neg if v > thr)
    return {"thr": thr, "detect": det, "n_pos": len(pos), "detect_ci": D.wilson(det, len(pos)),
            "false": fa, "n_neg": len(neg), "false_ci": D.wilson(fa, len(neg))}


def run(allrecs, n_boot=2000):
    md = ["# نتيجة التسجيل المسبق رقم 2 — margin/tash على OMIT وSUBSTITUTE بحقنٍ جديد (g3r مضجَّج)", "",
          "> المعيارُ حرفاً: **AUC ≥ 0.80 وحدُّ المجال الأدنى ≥ 0.75**، لكلّ نموذجٍ على حدة (‏`results/forced/PREREG_2.md`).", "",
          "| النموذج | AUC [95٪] | موجَب | سالب | الحكم |", "|---|---|---:|---:|---|"]
    res, sec = {}, []
    for m, recs in allrecs.items():
        sub, s, ok = judge(recs, n_boot)
        res[m] = {"summary": s, "pass": ok}
        md.append(f"| `{m}` | **{F.fmt(s)}** | {s['n_pos']} | {s['n_neg']} | " + ("**يُقبل**" if ok else "**لا يُقبل ⇒ يُغلق البند**") + " |")
        if m in THRESH:
            sec.append((m, secondary(sub, THRESH[m])))
        by = F.by_op(sub, "tash", "margin", 500)
        res[m]["ops"] = by
    md += ["", "### بحسب النوع (للاستئناس)", "", "| النموذج | النوع | AUC [95٪] | موجَب |", "|---|---|---|---:|"]
    for m in res:
        for op, s in res[m]["ops"].items():
            md.append(f"| `{m}` | {op} | {F.fmt(s)} | {s['n_pos']} |")
    md += ["", "### ثانويّ (لا يحكم): العتبةُ المسجَّلة مسبقاً", "",
           "| النموذج | العتبة | الكشف (موجَبٌ > العتبة) [Wilson 95٪] | الاتّهام الكاذب (سالبٌ > العتبة) [Wilson 95٪] |", "|---|---:|---|---|"]
    for m, e in sec:
        res[m]["secondary"] = e
        md.append(f"| `{m}` | {e['thr']} | {e['detect']}/{e['n_pos']} = {100*e['detect']/max(e['n_pos'],1):.1f}٪ [{e['detect_ci'][0]:.1f}, {e['detect_ci'][1]:.1f}] | "
                  f"{e['false']}/{e['n_neg']} = {100*e['false']/max(e['n_neg'],1):.1f}٪ [{e['false_ci'][0]:.1f}, {e['false_ci'][1]:.1f}] |")
    return "\n".join(md) + "\n", res


def selftest():
    recs = []
    for n in range(40):
        for k, lab, g, op in ((0, "neg", 0.1, "OMIT"), (1, "pos", 9.0, "OMIT"), (2, "neg", 0.2, "SUBSTITUTE")):
            recs.append({"set": "g3rn", "item": f"i{n}", "k": k, "op": op, "label": lab, "zone": lab == "pos",
                         "sc": {"tash": {"margin": g}}})
    md, res = run({"tiny": recs}, 100)
    assert res["tiny"]["pass"] and "يُقبل" in md and res["tiny"]["secondary"]["detect"] == 40, md
    flat = [dict(r, sc={"tash": {"margin": 1.0}}) for r in recs]
    assert not run({"tiny": flat}, 100)[1]["tiny"]["pass"]
    print("✅ forced_prereg2 selftest: نجح")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--words")
    ap.add_argument("--md", default="")
    ap.add_argument("--json", default="")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    md, res = run(json.load(open(a.words, encoding="utf-8")))
    print(md)
    if a.md:
        open(a.md, "w", encoding="utf-8").write(md)
    if a.json:
        json.dump(res, open(a.json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
