#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""انتقاءُ سور الدفعة السماعيّة (‏`heard_batch.yml` · fixT · 2026-10-03): أيُّ سورةٍ أُعيد بناؤها
بخريطة السماع (‏`ctc_heard_map`) تؤخذ في المرشّح، وأيُّها تُترك ولماذا.

تؤخذ السورةُ **بثلاثة شروطٍ مجتمعة** (‏ولا يُمسّ ما سواها بايتاً):
1. **المنشورُ معطوبٌ مقيساً:** بوّابةُ السماع (‏`heard_gate.surah_verdict`) على مداخل الأب
   تجد آيةً تنحرف عن موضعها المسموع > 1.5ث — فلا تُعاد سورةٌ سليمةٌ بلا قياس.
2. **المبنيُّ سليمٌ بالبوّابة نفسِها:** كلُّ آيةٍ لها حدود، ولا انحرافَ، والمقيسُ ≥ النصف،
   ولا ذيلَ غيرَ مقيس.
3. **الصوتُ هو صوتُ الأب:** بصمةُ الملفّ الذي سُمع = `audioSha256` للسورة في الأب، والرابطُ
   رابطُ مداخلها نفسُه.

وما لم يُؤخذ يُنقل إلى `<dir>/rejected/` فلا يراه الدمج، ويُكتب سببُه في التقرير.

    python tools/index_qa/heard_batch_select.py --parent parent.jz --dir work/batch_x \
        --surahs 3,14,35 --report heard_batch_report.json
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import heard_gate as H  # noqa: E402


def decide(s: int, parent: dict, res: dict | None) -> dict:
    """حكمُ سورةٍ واحدة: {"surah", "take": bool, "why": str, ...}."""
    out = {"surah": s, "take": False}
    if res is None:
        out["why"] = "لم تُبنَ (لا مخرَجَ للمحاذاة — انظر السجلّ)"
        return out
    cs = H.by_surah(parent.get("entries"))
    pub = cs.get(s)
    if not pub:
        out["why"] = "لا مداخلَ لها في الأب — ليست من شأن هذه الدفعة"
        return out
    present = sorted(cs)
    shas = parent.get("audioSha256")
    if isinstance(shas, list) and len(shas) == len(present):
        want = shas[present.index(s)]
        if want and res.get("sha256") != want:
            out["why"] = f"صوتُ المصدر تبدّل ({str(res.get('sha256'))[:8]} ≠ {str(want)[:8]}) — يُترك للتحقيق"
            return out
    refs = {v[2] for v in pub.values()}
    if res.get("fileRef") not in refs:
        out["why"] = f"سُمع {res.get('fileRef')} والأبُ يشير إلى {sorted(refs)}"
        return out
    cmap = H.compact_map(res)
    pub_rows = H.surah_rows({a: v[0] for a, v in pub.items()}, cmap)
    pub_why = H.surah_verdict(pub_rows)
    out["published"] = pub_why or "سليم"
    out["publishedDev"] = [r["ayah"] for r in pub_rows if r["status"] == "dev"]
    if not pub_why:
        out["why"] = "المنشورُ يطابق المسموع — لم يُمسّ"
        return out
    if not out["publishedDev"]:
        out["why"] = f"المنشورُ غيرُ حاسمٍ لا منحرف ({pub_why}) — لا يُعاد بلا انحرافٍ مقيس"
        return out
    ents = res.get("entries") or []
    unresolved = [e["ayahIdx"] + 1 for e in ents if e.get("startMs") is None or e.get("endMs") is None]
    if unresolved or not ents:
        unheard = [int(k) for k, v in (res.get("heardMap") or {}).items() if not v.get("heard")]
        out["why"] = (f"المبنيُّ فيه آياتٌ بلا حدود {unresolved[:20]}"
                      + (f" · بلا مِرساةٍ مسموعة {sorted(unheard)[:20]}" if unheard else "")
                      + " — يُترك (مرشّحٌ لقاعدة المالك إن ثبت غيابُ الصوت)")
        out["unheard"] = sorted(unheard)
        return out
    new_rows = H.surah_rows({e["ayahIdx"] + 1: e["startMs"] for e in ents}, cmap)
    new_why = H.surah_verdict(new_rows)
    if new_why:
        out["why"] = f"المبنيُّ يُردّ ببوّابة السماع: {new_why}"
        return out
    out["take"] = True
    devs = [abs(r["devMs"]) for r in pub_rows if r["status"] == "dev"]
    out["why"] = (f"أُصلحت: {len(out['publishedDev'])} آيةً كانت منحرفة (أقصاها {max(devs) / 1000:.1f}ث)"
                  f" والمبنيُّ يطابق المسموع")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--parent", required=True)
    ap.add_argument("--dir", required=True)
    ap.add_argument("--surahs", required=True)
    ap.add_argument("--report", required=True)
    a = ap.parse_args()
    parent = json.loads(gzip.decompress(open(a.parent, "rb").read()).decode("utf-8"))
    rej = os.path.join(a.dir, "rejected")
    os.makedirs(rej, exist_ok=True)
    rows = []
    for s in [int(x) for x in a.surahs.split(",") if x.strip()]:
        p = os.path.join(a.dir, f"s{s:03d}.json")
        res = json.load(open(p, encoding="utf-8")) if os.path.exists(p) else None
        d = decide(s, parent, res)
        rows.append(d)
        if res is not None and not d["take"]:
            shutil.move(p, os.path.join(rej, os.path.basename(p)))
        print(f"{'✅' if d['take'] else '—'} س{s}: {d['why']}")
    taken = [d["surah"] for d in rows if d["take"]]
    json.dump({"parent": a.parent, "taken": taken, "rows": rows}, open(a.report, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"المأخوذ {len(taken)}/{len(rows)}: {taken}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
