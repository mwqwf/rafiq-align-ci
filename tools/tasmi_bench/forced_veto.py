# -*- coding: utf-8 -*-
"""🛡️ الفيتو: هل تُخفّض إشارةُ margin القسريّ الاتّهامَ الكاذب للحاكم الحاليّ بلا خسارة كشف؟ — التسجيل المسبق 3 (`results/forced/PREREG_3.md`).

يقرأ سجلّاتِ `forced_auc.py --words` (‏فيها التفريغُ الحرّ `free_text` لكل بند و`margin` لكل كلمةٍ مرجعيّة بصورة tash)،
ويحاذي بـ`scorer.score` نفسِه (‏كما `detect_score`)، ويقارن ذراعَين على البنود نفسها:
- الأساس: الاتّهاماتُ (MISSED/SUBSTITUTED) كما هي. ‏- الفيتو: متّهمةٌ margin لها < τ تصير «غير متبيَّنة».
τ = المئين الثاني لـmargin بين المتّهمات داخل النطاق في **الخطة الأولى وحدها** (‏تحفظ ≥ 98٪ من الاتّهامات الصحيحة بالكلمة).
الحكم على **العيّنة الجديدة** حرفاً: Δكاذب ≤ −2 نقطة (‏حدّه الأعلى < 0) **و** Δكشف ≥ −1 نقطة (‏حدّه الأدنى ≥ −2) لكل نموذج.

    python tools/tasmi_bench/forced_veto.py --first w1.json --new w3.json --md o.md --json o.json
    python tools/tasmi_bench/forced_veto.py --selftest
"""
import argparse
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import detect_score as D  # noqa: E402
import scorer  # noqa: E402
import token_conf_auc as T  # noqa: E402

CONF = {scorer.MISSED, scorer.SUBSTITUTED}
COLLAPSE = 0.60
TAU_Q = 0.02
FA_BAR, FA_CI = -2.0, 0.0       # Δكاذب ≤ −2 وحدُّه الأعلى < 0
DET_BAR, DET_CI = -1.0, -2.0    # Δكشف ≥ −1 وحدُّه الأدنى ≥ −2
INF = float("inf")


def item_stats(plan_items, recs):
    """لكل بندٍ يُحسب: هوامشُ المتّهمات داخل النطاق وخارجه وعددُ الكلمات خارجه. يعيد (قائمة، عدد المستبعَد)."""
    meta = {r["item"]: r for r in recs if r["label"] == "meta" and r["set"] == "g3rn"}
    marg = {}
    for r in recs:
        if r["label"] != "meta" and r["set"] == "g3rn" and "tash" in r["sc"]:
            marg[(r["item"], r["k"])] = r["sc"]["tash"]["margin"]
    out, skipped = [], 0
    for it in plan_items:
        m = meta.get(it["id"])
        if not m:
            continue
        if not m["free_text"].strip():
            skipped += 1
            continue
        ref = it["refText"].split()
        s = scorer.score(ref, m["free_text"], D.cfg_for(it.get("riwaya")))
        ws = s["words"]
        if sum(1 for w in ws if w[1] in CONF) / max(len(ws), 1) > COLLAPSE:
            skipped += 1
            continue
        lo, hi = D.zone(it)
        zin, zout, n_out = [], [], 0
        for k, (idx, state, heard) in enumerate(ws):
            inz = lo <= k <= hi
            if not inz:
                n_out += 1
            if state in CONF:
                mg = marg.get((it["id"], k))
                (zin if inz else zout).append(INF if mg is None else mg)   # بلا margin ⇒ لا فيتو
        out.append({"id": it["id"], "op": it["op"], "zin": zin, "zout": zout, "n_out": n_out})
    return out, skipped


def rates(stats, tau):
    """(كشف الأساس، كشف الفيتو، كاذب الأساس، كاذب الفيتو) بالمئة."""
    n = len(stats)
    if not n:
        return None
    nout = sum(s["n_out"] for s in stats)
    db = sum(1 for s in stats if s["zin"])
    dv = sum(1 for s in stats if any(m >= tau for m in s["zin"]))
    fb = sum(len(s["zout"]) for s in stats)
    fv = sum(sum(1 for m in s["zout"] if m >= tau) for s in stats)
    return (100 * db / n, 100 * dv / n, 100 * fb / max(nout, 1), 100 * fv / max(nout, 1))


def boot(stats, tau, n_boot=2000, seed=11):
    rnd = random.Random(seed)
    ddet, dfa = [], []
    for _ in range(n_boot):
        samp = [stats[rnd.randrange(len(stats))] for _ in stats]
        r = rates(samp, tau)
        ddet.append(r[1] - r[0])
        dfa.append(r[3] - r[2])
    ddet.sort()
    dfa.sort()
    lo = int(0.025 * n_boot)
    hi = int(0.975 * n_boot) - 1
    return (ddet[lo], ddet[hi]), (dfa[lo], dfa[hi])


def tau_of(stats):
    z = [m for s in stats for m in s["zin"] if m != INF]
    return T.percentile(z, TAU_Q)


def analyze(stats, tau, n_boot):
    r = rates(stats, tau)
    cdet, cfa = boot(stats, tau, n_boot)
    return {"n": len(stats), "det_base": r[0], "det_veto": r[1], "fa_base": r[2], "fa_veto": r[3],
            "d_det": r[1] - r[0], "d_det_ci": cdet, "d_fa": r[3] - r[2], "d_fa_ci": cfa}


def passes(a):
    return a["d_fa"] <= FA_BAR and a["d_fa_ci"][1] < FA_CI and a["d_det"] >= DET_BAR and a["d_det_ci"][0] >= DET_CI


def row(label, a):
    return (f"| {label} | {a['n']} | {a['det_base']:.1f} → {a['det_veto']:.1f} | **{a['d_det']:+.2f}** [{a['d_det_ci'][0]:+.2f}, {a['d_det_ci'][1]:+.2f}] | "
            f"{a['fa_base']:.2f} → {a['fa_veto']:.2f} | **{a['d_fa']:+.2f}** [{a['d_fa_ci'][0]:+.2f}, {a['d_fa_ci'][1]:+.2f}] |")


HEAD = ["| العيّنة | بنود | الكشف % (أساس → فيتو) | Δكشف نقطة [95٪] | الاتّهام الكاذب % (أساس → فيتو) | Δكاذب نقطة [95٪] |", "|---|---:|---|---|---|---|"]


def run(first_plan, new_plan, first_recs, new_recs, n_boot=2000):
    md = ["# فيتو margin القسريّ على اتّهامات الحاكم الحاليّ — g3r مضجَّج", "",
          "> التسجيل المسبق 3 (`results/forced/PREREG_3.md`). الحاكم `scorer.score` على التفريغ الحرّ (whisper_full بالراياتِ المشحونة) للنموذج نفسه؛ ‏الفيتو: متّهمةٌ margin < τ ⇒ غير متبيَّنة.", ""]
    res = {}
    for m in first_recs:
        fs, fsk = item_stats(first_plan, first_recs[m])
        ns, nsk = item_stats(new_plan, new_recs[m])
        tau = tau_of(fs)
        a_new = analyze(ns, tau, n_boot)
        a_first = analyze(fs, tau, n_boot)
        ok = passes(a_new)
        res[m] = {"tau": tau, "new": a_new, "first": a_first, "pass": ok, "skipped": {"first": fsk, "new": nsk}, "ops": {}}
        md += [f"## النموذج `{m}` — τ = {tau:.4f} (‏المئين 2 للمتّهمات داخل النطاق في الخطة الأولى؛ استُبعد {fsk} و{nsk} بنداً بحارس الانهيار/تفريغٍ فارغ)", ""] + HEAD
        md.append(row("**الجديدة (الحكم)**", a_new))
        md.append(row("الأولى (اختيار τ)", a_first))
        for op in ("OMIT", "SUBSTITUTE", "SWAP", "INSERT"):
            sub = [s for s in ns if s["op"] == op]
            if sub:
                a = analyze(sub, tau, max(n_boot // 4, 200))
                res[m]["ops"][op] = a
                md.append(row(f"الجديدة · {op}", a))
        md += ["", "**الحكم الحرفيّ:** " + (
            f"Δكاذب = {a_new['d_fa']:+.2f} (‏حدّه الأعلى {a_new['d_fa_ci'][1]:+.2f}) و Δكشف = {a_new['d_det']:+.2f} (‏حدّه الأدنى {a_new['d_det_ci'][0]:+.2f}) ⇒ " +
            ("**يُقبل الفيتو**" if ok else "**لا يُقبل ⇒ يُغلق البند**")), ""]
        # الزمن (ثانويّ)
        mt = [r for r in new_recs[m] if r["label"] == "meta" and r["free_ms"] >= 0]
        if mt:
            f = sum(r["forced_ms"] for r in mt) / len(mt)
            fr = sum(r["free_ms"] for r in mt) / len(mt)
            e = sum(r["enc_ms"] for r in mt) / len(mt)
            res[m]["timing"] = {"forced_ms": f, "free_ms": fr, "enc_ms": e}
            md += [f"الزمن الإضافيّ (ثانويّ): الفكّ القسريّ بصورة tash ‏{f:.0f} م.ث لكل بند مقابل الحرّ الكامل ‏{fr:.0f} م.ث (‏منه ترميز {e:.0f}) ⇒ ‏+{100*f/fr:.1f}٪ فوق الحرّ، والترميز مشتركٌ.", ""]
    return "\n".join(md) + "\n", res


def selftest():
    # بندان: اتّهامٌ صحيحٌ بهامش مرتفع داخل النطاق، واتّهامٌ كاذبٌ بهامش منخفض خارجه
    mk = lambda zin, zout: {"id": "x", "op": "OMIT", "zin": zin, "zout": zout, "n_out": 10}
    stats = [mk([5.0], [1.0, 1.0]) for _ in range(50)] + [mk([], [6.0]) for _ in range(50)]
    r = rates(stats, 3.0)
    assert r[0] == 50 and r[1] == 50 and abs(r[2] - 0.0 - 100 * 150 / 1000) < 1e-9 and abs(r[3] - 100 * 50 / 1000) < 1e-9, r
    a = analyze(stats, 3.0, 200)
    assert a["d_det"] == 0 and a["d_fa"] < -9 and passes(a), a
    a2 = analyze([mk([2.0], [1.0]) for _ in range(40)], 3.0, 200)    # الفيتو يقتل الكشف الصحيح
    assert a2["d_det"] == -100 and not passes(a2)
    assert tau_of([mk([1.0, 2.0, 3.0, INF], [])]) is not None
    print("✅ forced_veto selftest: نجح")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--first")
    ap.add_argument("--new")
    ap.add_argument("--first-plan", default="inject_plan_riwaya.json")
    ap.add_argument("--new-plan", default="inject_plan_forced3.json")
    ap.add_argument("--boot", type=int, default=2000)
    ap.add_argument("--md", default="")
    ap.add_argument("--json", default="")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    fr = json.load(open(a.first, encoding="utf-8"))
    nr = json.load(open(a.new, encoding="utf-8"))
    md, res = run(T.load_plan(a.first_plan), T.load_plan(a.new_plan), fr, nr, a.boot)
    print(md)
    if a.md:
        open(a.md, "w", encoding="utf-8").write(md)
    if a.json:
        json.dump(res, open(a.json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
