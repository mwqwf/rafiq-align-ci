#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""🎙️ **مقياسُ المحدِّد على تفريغاتِ متعلّمٍ حقيقيّ** — `owner_cases.tsv`.

⛔ **ولمَ لزم مقياسٌ ثانٍ**: `locator_parity.py` يقيس **اتّفاقَ** المحدّدَين لا صوابَهما،
   و`locator_bench.py` يقيس الصوابَ لكن **على مادّةٍ من صوتِ محترفٍ مُحاكاة**. وهذا يقيس
   الصوابَ على **ما يسقط عليه التطبيقُ فعلاً** — وهو ما عمينا عنه حتى 2026-09-15.

⛔ **ولا يُبنى عليه وحدَه حكمٌ**: ستُّ حالاتٍ عيّنةٌ صغيرة. غايتُه أن **يصرخ** إذا عاد
   عطبٌ كشفته إحداها — لا أن يُثبت نجاحاً.

    python tools/tasmi_bench/owner_bench.py            # الحالُ المشحون
    python tools/tasmi_bench/owner_bench.py --prec 0.5 # تجربةُ عتبةٍ أخرى قبل شحنها
"""
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import locator as L, scorer                                            # noqa: E402
import locator_parity as lp                                            # noqa: E402

COVER, PREC = 0.25, 0.61        # مرآةُ `QuranLocator.TENTATIVE_COVER/_MIN_PREC`


def rows(path):
    for line in open(path, encoding="utf-8"):
        line = line.rstrip("\n")
        if not line.strip() or line.startswith("#") or line.startswith("case\t"):
            continue
        c = line.split("\t")
        if len(c) >= 3:
            yield c[0], int(c[1]), c[2]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cover", type=float, default=COVER)
    ap.add_argument("--prec", type=float, default=PREC)
    a = ap.parse_args()
    ayat = lp.load_text("hafs")
    cfg = lp.config_for("hafs")
    loc = L.Locator([x.split() for x in ayat], cfg)
    here = os.path.dirname(os.path.abspath(__file__))
    ok = bad = silent = 0
    print(f"العتبات: cover≥{a.cover} · prec≥{a.prec}\n")
    print(f"{'الحالة':12s} {'المنتظر':>8s} {'الموضع':>8s} {'cover':>6s} {'prec':>6s}  الحكم")
    for name, truth, h in rows(os.path.join(here, "owner_cases.tsv")):
        hyp = [w for w in (scorer.norm(x, cfg) for x in L._WS.split(h)) if w]
        core = hyp[loc.strip_preamble(hyp):]
        best = None
        if len(core) >= 2:
            for f, v, _ in loc.candidates(core):
                r = loc._extend(f, h, 300, 2)
                if r is None:
                    continue
                hd = [x for x in r["anchored"] if x["window"] is not None]
                c = sum(x["correct"] for x in hd)
                n = sum(x["n"] for x in hd)
                cov, pr = c / max(1, len(core)), c / max(1, n)
                q = min(cov, 1.0) * (0.5 + 0.5 * pr) + v * 1e-3
                if best is None or q > best[0]:
                    best = (q, r["start"], cov, pr, c)
        asked = best is not None and best[2] >= a.cover and best[3] >= a.prec and best[4] >= 3
        if truth < 0:
            verdict = "✅ صمت (وهو المنتظر)" if not asked else "⛔ سأل وكان يجب أن يصمت"
            ok, bad = (ok + 1, bad) if not asked else (ok, bad + 1)
        elif asked and best[1] == truth:
            verdict = "✅ سأل بالموضع الصحيح"; ok += 1
        elif asked:
            verdict = f"⛔ سأل بموضعٍ خاطئ ({best[1]})"; bad += 1
        else:
            verdict = "⚠️ صمت وكان يعرف"; silent += 1
        p = f"{best[1]:>8d} {best[2]:>6.2f} {best[3]:>6.2f}" if best else f"{'—':>8s} {'—':>6s} {'—':>6s}"
        print(f"{name:12s} {truth:>8d} {p}  {verdict}")
    print(f"\n✅ {ok} · ⛔ خاطئ {bad} · ⚠️ صمتٌ عن معروف {silent}")
    # ⛔ الخاطئُ وحدَه يُخفق: الصمتُ نقصٌ يُرى ولا يُفسد حكماً.
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
