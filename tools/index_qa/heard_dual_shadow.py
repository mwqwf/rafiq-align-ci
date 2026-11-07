#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ظلُّ الباب المزدوج في بوّابة السماع — **وضعُ التقرير**: لا state ولا دلوَ ولا كتابةً في شيء (‏2026-11-07).

يقرأ مخرَجَ `heard_dual_shadow.yml` (‏لكلّ (مرشّح، سورة): خريطتا G وR وشاهدُ Whisper) ويطبع لكلّ سورةٍ:
المقيسَ بـG وR · المتنازَعَ وحكمَ الشاهد فيه · عيّنةَ الاستقلال ونتيجتها · **الحكمَ القديم** (‏G وحدَها) و**الحكمَ المزدوج**
(‏`heard_gate.dual_surah` نفسُها التي تستدعيها `judge` — لا نسخة) · وهل **انقلب الحكمُ نحو القبول**.
قرّاءُ الضبط (‏`forced`) ليسوا في القائمة فتُفرض عليهم القائمةُ هنا في التقرير وحدَه ليُرى ما كان سيحدث."""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import heard_gate as H  # noqa: E402


def want_sha(idx: dict, s: int):
    shas, present = idx.get("audioSha256"), sorted(H.by_surah(idx["entries"]))
    if isinstance(shas, list) and len(shas) == 114:
        return shas[s - 1]
    if isinstance(shas, list) and len(shas) == len(present):
        return dict(zip(present, shas)).get(s)
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--plan", required=True)
    ap.add_argument("--shards", required=True, help="مجلّدُ مخرَجات المصفوفة: <flat src>/heard_sNNN.json · q/ · w/")
    ap.add_argument("--cands", required=True, help="مجلّدُ ملفّات المرشّحين المنزَّلة: <flat src>")
    ap.add_argument("--out", default="shadow_report.json")
    a = ap.parse_args()
    plan = json.load(open(a.plan, encoding="utf-8"))
    report, flips = [], []
    for k, it in enumerate(plan):
        src, s, flat = it["src"], int(it["s"]), it["src"].replace("/", "_")
        import gzip
        idx = json.loads(gzip.decompress(open(os.path.join(a.cands, flat), "rb").read()))
        cs = H.by_surah(idx["entries"])[s]
        row = {"k": k, "src": src, "surah": s, "forced": bool(it.get("forced")), "listed": s in H.dual_surahs(idx)}
        pg = os.path.join(a.shards, flat, f"heard_s{s:03d}.json")
        pr = os.path.join(a.shards, flat, "q", f"heard_s{s:03d}.json")
        pw = os.path.join(a.shards, flat, "w", f"whisper_s{s:03d}.json")
        if not (os.path.exists(pg) and os.path.exists(pr)):
            row["error"] = "لا خريطتان في المخرَج (‏القياس أخفق)"
            report.append(row)
            print(f"■ {src} س{s}: ⚠️ {row['error']}")
            continue
        g = H.compact_map(json.load(open(pg, encoding="utf-8")))
        r = H.compact_map(json.load(open(pr, encoding="utf-8")))
        wit = json.load(open(pw, encoding="utf-8")) if os.path.exists(pw) else None
        want = want_sha(idx, s)
        row["sha"] = {"cand": it["sha"][:8], "audio": str(want)[:8], "G": str(g.get("sha256"))[:8], "R": str(r.get("sha256"))[:8]}
        if g.get("sha256") != want:
            row["error"] = "الصوتُ المسموع غيرُ صوت المرشّح (‏audioSha256)"
            report.append(row)
            print(f"■ {src} س{s}: ⚠️ {row['error']} {row['sha']}")
            continue
        starts = {x: v[0] for x, v in cs.items()}
        old_rows = H.surah_rows(starts, g)
        old_why = H.surah_verdict(old_rows)
        why, dv = H.dual_surah(s, cs, g, r, wit, want, it["sha"], idx.get("riwaya"))
        ev = dv["evidence"]
        rows = {x["ayah"]: x for x in dv["rows"]}
        row.update({
            "old": {"ok": old_why is None, "reason": old_why,
                    "measured": sum(1 for x in old_rows if x["status"] != "unmeasured"),
                    "dev": [x["ayah"] for x in old_rows if x["status"] == "dev"]},
            "dual": {"ok": why is None, "reason": why, "evidence": ev},
            "contestedDetail": {str(x): (rows[x].get("witness") or "لم يحسمه الشاهد") for x in ev.get("contested", []) if x in rows},
            "witnessInfo": ev.get("witness"),
            "devAyahsDual": [x["ayah"] for x in dv["rows"] if x["status"] == "dev"],
        })
        flip = row["dual"]["ok"] and not row["old"]["ok"]
        row["flipToAccept"] = flip
        if flip:
            flips.append((src, s, row["forced"]))
        report.append(row)
        print(f"■ {src} س{s} ({'ضبط مفروض' if row['forced'] else 'القائمة' if row['listed'] else 'خارج القائمة'}) · {len(cs)} آية")
        print(f"   G مقيس {row['old']['measured']}/{len(cs)} · R مقيس {ev.get('rMeasured')}/{len(cs)} · مغطّى {ev.get('covered')}/{len(cs)}")
        print(f"   متنازَع {ev.get('contested')} · حُسم بالشاهد {ev.get('contestedResolved')} · غيرُ محسوم {[x for x in ev.get('contested', []) if x not in ev.get('contestedResolved', [])]}")
        print(f"   تفصيلُ الشاهد في المتنازَع/المستكمَل/العيّنة: {json.dumps(ev.get('witness'), ensure_ascii=False)[:700]}")
        print(f"   عيّنةُ الاستقلال {ev.get('sample')} · حسمها الشاهد {ev.get('sampleOk')}")
        print(f"   القديم (G وحدها): {'✅' if row['old']['ok'] else '⛔ ' + str(old_why)[:200]}")
        print(f"   المزدوج: {'✅' if row['dual']['ok'] else '⛔ ' + str(why)[:300]}")
        print(f"   {'⚠️ انقلب نحو القبول' if flip else 'لا انقلابَ نحو القبول'}")
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    ctrl = [x for x in report if x.get("forced") and "dual" in x]
    print("\n══ قرّاءُ الضبط ══")
    for x in ctrl:
        print(f"  {x['src']} س{x['surah']}: قديم {'✅' if x['old']['ok'] else '⛔'} → مزدوج {'✅' if x['dual']['ok'] else '⛔'}"
              f"{'  ⚠️ انقلاب نحو القبول' if x['flipToAccept'] else ''}")
    print(f"انقلاباتٌ نحو القبول: {len(flips)} — {flips}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
