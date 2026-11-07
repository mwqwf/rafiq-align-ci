#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""تشخيصٌ وحده (‏claude/diag-heard-quran-model): مقارنةُ خريطتَي سماعٍ لسورةٍ واحدة — النموذجُ العامّ مقابل نموذج التلاوة.

⛔ لا يمسّ `heard_gate.py` ولا عتباتِه؛ يستورد ثوابتَه (‏MIN_Q · TAIL_UNMEASURED · REPEAT_SIM) للقياس بها فقط.
    python tools/alignment_v3/diag_heard_compare.py out/heard_s022.json out_q/heard_s022.json [--focus 22:62]
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "index_qa"))
import heard_gate as G  # noqa: E402


def stats(d):
    hm = d["heardMap"]
    n = len(hm)
    q = {int(k): (v.get("anchorQuality") if v.get("anchorMs") else None) for k, v in hm.items()}
    meas = [k for k, v in q.items() if v is not None and v >= G.MIN_Q]
    strong = [k for k, v in q.items() if v is not None and v >= G.REPEAT_SIM]
    tail = 0
    for k in range(n, 0, -1):
        if k in meas:
            break
        tail += 1
    rep = {}
    excess = 0
    for k, v in hm.items():
        occ = [o for o in (v.get("occurrences") or []) if o[2] >= G.REPEAT_SIM]
        if len(occ) >= 2:
            rep[int(k)] = [[o[0], o[1], o[2]] for o in occ]
            excess += sum(o[1] - o[0] for o in occ[1:])
    nogm = [int(k) for k, v in hm.items() if not v.get("anchorMs")]
    nonheard = [int(k) for k, v in hm.items() if not v.get("heard")]
    verdict = ("المقيسُ %d/%d أقلُّ من النصف" % (len(meas), n)) if len(meas) * 2 < n else (
        "ذيلٌ غيرُ مقيس (%d)" % tail if tail >= G.TAIL_UNMEASURED else None)
    qs = [v for v in q.values() if v is not None]
    return {"n": n, "totalMs": d.get("totalMs"), "measured_q>=0.5": len(meas), "strong_q>=0.7": len(strong),
            "meanQ": round(sum(qs) / len(qs), 3) if qs else None, "noAnchor": len(nogm),
            "tailUnmeasured": tail, "notHeard": len(nonheard), "gateWouldReject": verdict,
            "repeatedAyat(>=2 occ sim>=0.7)": len(rep), "repeatExcessMs": excess, "repeats": rep,
            "anchors": {int(k): [v.get("anchorMs"), v.get("anchorQuality")] for k, v in hm.items()}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("base")
    ap.add_argument("quran")
    ap.add_argument("--focus", default="", help="آياتٌ مقروءةٌ مفصّلةً: 22:62,22:63")
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    B, Q = (json.load(open(p, encoding="utf-8")) for p in (a.base, a.quran))
    sb, sq = stats(B), stats(Q)
    agree = dis = 0
    far = []
    for k, (ab, qb) in sb["anchors"].items():
        aq, qq = sq["anchors"].get(k, [None, None])
        if ab and aq and qb is not None and qq is not None and qb >= G.MIN_Q and qq >= G.MIN_Q:
            if abs(ab[0] - aq[0]) <= G.TOL_MS:
                agree += 1
            else:
                dis += 1
                far.append([k, ab[0], aq[0]])
    qgain = [k for k, (aq, qq) in sq["anchors"].items()
             if qq is not None and qq >= G.MIN_Q and (sb["anchors"][k][1] is None or sb["anchors"][k][1] < G.MIN_Q)]
    qloss = [k for k, (ab, qb) in sb["anchors"].items()
             if qb is not None and qb >= G.MIN_Q and (sq["anchors"][k][1] is None or sq["anchors"][k][1] < G.MIN_Q)]
    focus = {}
    for f in [x for x in a.focus.split(",") if x.strip()]:
        s, k = f.split(":")
        k = int(k)
        focus[f] = {"base": sb["anchors"].get(k), "quran": sq["anchors"].get(k),
                    "baseOcc": B["heardMap"][str(k)].get("occurrences"), "quranOcc": Q["heardMap"][str(k)].get("occurrences")}
    res = {"surah": B.get("surah"), "base": {k: v for k, v in sb.items() if k != "anchors"},
           "quran": {k: v for k, v in sq.items() if k != "anchors"},
           "bothMeasured_agree<=1.5s": agree, "bothMeasured_disagree": dis, "disagreeSample": far[:20],
           "gainedByQuran": len(qgain), "lostByQuran": len(qloss), "focus": focus}
    txt = json.dumps(res, ensure_ascii=False, indent=1)
    print(txt)
    if a.out:
        open(a.out, "w", encoding="utf-8").write(txt)


if __name__ == "__main__":
    main()
