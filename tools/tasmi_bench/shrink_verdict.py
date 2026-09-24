# -*- coding: utf-8 -*-
"""📦⚖️ **حكمُ التصغير — أصغرُ نموذجٍ لا يخسر قدرةً** (أمرُ المالك 2026-09-24: «أكمل تصغير نموذج التسميع
لكن بقدراتٍ أعلى لا أقلّ»).

المدخل: ملخّصاتُ `v2_gate.py` (‏`<arm>_gate_summary.json`) لكلّ مرشَّحٍ مكمَّمٍ من `whisper-base-ar-quran`
في مقارنتَين على **البنود عينِها**:
1. **مقابل المشحون** (`tiny` q8 · `-l en`، وهو ما يسمعه كلُّ مستخدمٍ اليوم) ⇒ يلزم **تفوّقٌ مفصولٌ** (فاصلُ ثقة 95٪
   لا يشمل الصفر) في محورٍ واحدٍ على الأقلّ، **ولا خسارةٌ مفصولةٌ في أيّ محور**.
2. **مقابل `base` q8** (الحزمةُ الأدقُّ القائمة، باللغة نفسِها) ⇒ **لا خسارةٌ مفصولةٌ في أيّ محور** — أي أنّ التكميمَ
   الأشدَّ لم يُنقص شيئاً يُقاس.

والمحاورُ: تتبّعُ الدقّة لكلّ مجموعة (‏G1 · الضجيجُ الشديد · سلوكُ المتعلّم) · الاتّهامُ الكاذب (‏g3r نظيفاً وضجيجاً) ·
والكشف (‏g3r). ⛔ **هبوطُ الكشف المفصولُ يُعدّ خسارةً هنا** وإن كانت مسطرتُه لا ترى `INSERT` (D-351): الأمرُ «لا
قدراتٍ أقلّ»، فالشكُّ يُحسب على المرشَّح لا له.

ويُختار **أصغرُ** مرشَّحٍ نجح في المقارنتَين، ويُطبع حجمُه وزمنُه وذروةُ ذاكرته من `timing.json` خبراً (الحكمُ للجودة).

    python tools/tasmi_bench/shrink_verdict.py --dir work/shrink --out work/shrink/verdict.json
    python tools/tasmi_bench/shrink_verdict.py --selftest
"""
import argparse
import glob
import json
import os
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass


def axes(rows):
    """(تفوّقٌ مفصول، خسارةٌ مفصولة، أسبابُهما) من صفوف ملخّص `v2_gate`."""
    better, worse = [], []
    for r in rows:
        s = r.get("set", "?")
        if "acc" in r:
            lo, hi = r["ci"]
            if lo > 0:
                better.append(f"{s} تتبّع +{r['diff'] * 100:.2f}")
            if hi < 0:
                worse.append(f"{s} تتبّع {r['diff'] * 100:+.2f}")
        if "fa" in r:
            lo, hi = r["ci"]
            if hi < 0:
                better.append(f"{s} اتّهام {r['fa_diff'] * 100:+.2f}")
            if lo > 0:
                worse.append(f"{s} اتّهام {r['fa_diff'] * 100:+.2f}")
            dlo, dhi = r["det_ci"]
            if dlo > 0:
                better.append(f"{s} كشف {r['det_diff'] * 100:+.1f}")
            if dhi < 0:
                worse.append(f"{s} كشف {r['det_diff'] * 100:+.1f}")
    return better, worse


def complete(rows):
    """الحكمُ على عيّنةٍ ناقصةٍ ممنوع: يلزم صفُّ دقّةٍ لكلّ مجموعة وصفّا g3r."""
    acc = {r["set"] for r in rows if "acc" in r}
    g3r = {r["set"] for r in rows if "fa" in r}
    return len(acc) >= 3 and len(g3r) >= 2


def judge(vs_shipped, vs_base):
    b1, w1 = axes(vs_shipped)
    _, w2 = axes(vs_base)
    ok_data = complete(vs_shipped) and complete(vs_base)
    return {"complete": ok_data, "vs_shipped": {"better": b1, "worse": w1}, "vs_base": {"worse": w2},
            "pass": bool(ok_data and b1 and not w1 and not w2)}


def main_dir(d, out):
    timing = {}
    tp = os.path.join(d, "timing.json")
    if os.path.exists(tp):
        timing = json.load(open(tp, encoding="utf-8"))
    res = {}
    for p in sorted(glob.glob(os.path.join(d, "vs_shipped_*.json"))):
        cand = os.path.basename(p)[len("vs_shipped_"):-5]
        pb = os.path.join(d, f"vs_base_{cand}.json")
        if not os.path.exists(pb):
            print(f"⛔ {cand}: لا مقارنةَ مقابل base ⇒ لا حكم")
            continue
        v = judge(json.load(open(p, encoding="utf-8")), json.load(open(pb, encoding="utf-8")))
        v["timing"] = timing.get(cand, {})
        res[cand] = v
        mb = v["timing"].get("mb", "?")
        print(f"{'✅' if v['pass'] else '⛔'} {cand} · {mb} م.ب · أفضلُ من المشحون: {v['vs_shipped']['better'] or '—'}"
              f" · خسارةٌ مقابل المشحون: {v['vs_shipped']['worse'] or '—'} · خسارةٌ مقابل base-q8: {v['vs_base']['worse'] or '—'}"
              f"{'' if v['complete'] else ' · ⚠️ عيّنةٌ ناقصة'}")
    passing = [c for c, v in res.items() if v["pass"]]
    pick = min(passing, key=lambda c: res[c]["timing"].get("mb", 1e9)) if passing else None
    doc = {"candidates": res, "pick": pick, "baseline_mb": timing.get("base-q8", {}).get("mb"),
           "shipped_mb": timing.get("tiny-q8", {}).get("mb")}
    json.dump(doc, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"⇒ المختار: {pick or 'لا أحد — لا مرشَّحَ يفي بالشرطين'} · {out}")
    return 0 if res else 1


def selftest():
    bad = 0

    def ok(name, got, want):
        nonlocal bad
        print(f"  {'✅' if got == want else '⛔'} {name}: {got} · المتوقَّع {want}")
        bad += got != want

    acc = lambda s, lo, hi: {"set": s, "acc": (0.8, 0.8), "diff": (lo + hi) / 2, "ci": (lo, hi)}  # noqa: E731
    g3 = lambda s, lo, hi, dlo=-0.01, dhi=0.01: {"set": s, "fa": (0.05, 0.05), "fa_diff": (lo + hi) / 2,  # noqa: E731
                                                 "ci": (lo, hi), "det_diff": 0.0, "det_ci": (dlo, dhi)}
    neutral = [acc("g1", -0.01, 0.01), acc("g2a", -0.01, 0.01), acc("g2b", -0.01, 0.01),
               g3("g3n", -0.01, 0.01), g3("g3c", -0.01, 0.01)]
    gain = [acc("g1", 0.01, 0.03)] + neutral[1:]
    ok("تفوّقٌ مفصولٌ على المشحون وتعادلٌ مع base ⇒ ينجح", judge(gain, neutral)["pass"], True)
    ok("تعادلٌ مع المشحون ⇒ لا ينجح (المطلوبُ أعلى لا مساوٍ)", judge(neutral, neutral)["pass"], False)
    fa_up = gain[:3] + [g3("g3n", 0.005, 0.02), neutral[4]]
    ok("اتّهامٌ كاذبٌ يرتفع مفصولاً ⇒ يسقط ولو ارتفعت الدقّة", judge(fa_up, neutral)["pass"], False)
    base_loss = [acc("g1", -0.03, -0.005)] + neutral[1:]
    ok("خسارةٌ مفصولةٌ مقابل base-q8 ⇒ يسقط", judge(gain, base_loss)["pass"], False)
    det_down = gain[:3] + [g3("g3n", -0.01, 0.01, -0.05, -0.01), neutral[4]]
    ok("كشفٌ يهبط مفصولاً ⇒ يُحسب خسارة", judge(det_down, neutral)["pass"], False)
    ok("عيّنةٌ ناقصة ⇒ لا حكم", judge(gain[:2], neutral)["pass"], False)
    ok("اتّهامٌ يهبط مفصولاً ⇒ تفوّق", bool(axes([g3("g3n", -0.02, -0.001)])[0]), True)
    print("✅ الحاكمُ سليمٌ على حالاته" if not bad else f"⛔ الحاكمُ معطوبٌ في {bad} حالة")
    return 1 if bad else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="work/shrink")
    ap.add_argument("--out", default="")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        sys.exit(selftest())
    sys.exit(main_dir(a.dir, a.out or os.path.join(a.dir, "verdict.json")))
