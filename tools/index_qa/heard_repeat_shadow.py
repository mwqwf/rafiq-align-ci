#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ظلُّ الباب الثالث (‏آيةٌ مكرّرةٌ مشهودة) في بوّابة السماع — **وضعُ التقرير**: لا state ولا دلوَ ولا كتابةً (‏2026-11-07).

يقرأ مخرَجَ `heard_repeat_shadow.yml` (‏لكلّ (مرشّح، سورة): خريطةُ العامّة وشاهدُ Whisper وإحصاءُ النوافذ للآيات المنحرفة ذواتِ التكرار المقيس)
ويطبع لكلّ سورةٍ: الحكمَ القديمَ (‏`surah_verdict` على الصفوف قبل الباب) والحكمَ بعده (‏`repeat_rescue` نفسُها التي تستدعيها `judge`)
و**كلَّ آيةٍ انقلبت نحو القبول بشاهدها** (‏التفريغ · الثقة · الفرق · نتيجة الإحصاء · الأداء الآخر المقيس)، ثمّ يفحص الشرط:
**لا انقلابَ نحو القبول إلا في آيةٍ مكرّرةٍ مشهودة** (‏كلُّ آيةٍ تغيّرت حالتُها هي منحرفةٌ في القديم وشهد لها الشاهدُ والإحصاءُ وفيها تكرارٌ مقيس،
ولا يتغيّر شيءٌ سواها)."""
from __future__ import annotations

import argparse
import copy
import gzip
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
    ap.add_argument("--shards", required=True, help="مجلّدُ مخرَجات المصفوفة: <flat src>/heard_sNNN.json · rw/ · rc/")
    ap.add_argument("--cands", required=True, help="مجلّدُ ملفّات المرشّحين المنزَّلة: <flat src>")
    ap.add_argument("--out", default="shadow_report.json")
    a = ap.parse_args()
    plan = json.load(open(a.plan, encoding="utf-8"))
    report, flips, violations = [], [], []
    for k, it in enumerate(plan):
        src, s, flat = it["src"], int(it["s"]), it["src"].replace("/", "_")
        idx = json.loads(gzip.decompress(open(os.path.join(a.cands, flat), "rb").read()))
        cs = H.by_surah(idx["entries"])[s]
        row = {"k": k, "src": src, "surah": s, "forced": bool(it.get("forced"))}
        pg = os.path.join(a.shards, flat, f"heard_s{s:03d}.json")
        pw = os.path.join(a.shards, flat, "rw", f"whisper_s{s:03d}.json")
        pc = os.path.join(a.shards, flat, "rc", f"census_s{s:03d}.json")
        if not os.path.exists(pg):
            row["error"] = "لا خريطةَ عامّةٍ في المخرَج (‏القياس أخفق)"
            report.append(row)
            print(f"■ {src} س{s}: ⚠️ {row['error']}")
            continue
        g = H.compact_map(json.load(open(pg, encoding="utf-8")))
        wit = json.load(open(pw, encoding="utf-8")) if os.path.exists(pw) else None
        cen = json.load(open(pc, encoding="utf-8")) if os.path.exists(pc) else None
        want = want_sha(idx, s)
        if g.get("sha256") != want:
            row["error"] = "الصوتُ المسموع غيرُ صوت المرشّح (‏audioSha256)"
            report.append(row)
            print(f"■ {src} س{s}: ⚠️ {row['error']} {str(g.get('sha256'))[:8]} ≠ {str(want)[:8]}")
            continue
        starts = {x: v[0] for x, v in cs.items()}
        old_rows = H.surah_rows(starts, g)
        old_why = H.surah_verdict(old_rows)
        new_rows = copy.deepcopy(old_rows)
        ev = H.repeat_rescue(s, new_rows, g, cs, want, idx.get("riwaya"), wit, cen)
        new_why = H.surah_verdict(new_rows)
        old_dev = [r["ayah"] for r in old_rows if r["status"] == "dev"]
        new_dev = [r["ayah"] for r in new_rows if r["status"] == "dev"]
        changed = [(o["ayah"], o["status"], n["status"]) for o, n in zip(old_rows, new_rows) if o["status"] != n["status"]]
        flipped = [x for x, _o, n in changed if n == H.REPEAT_STATUS]
        # الشرط: كلُّ تغيّرٍ = dev ⇒ witnessed_repeat لآيةٍ مرشَّحةٍ (‏تكرارٌ مقيس) نجح شاهدُها وإحصاؤها معاً
        bad = [c for c in changed if not (c[1] == "dev" and c[2] == H.REPEAT_STATUS and ev.get(c[0], {}).get("passed")
                                          and ev[c[0]]["otherPerformance"] and ev[c[0]]["witnessOk"] and ev[c[0]]["censusOk"])]
        row.update({"oldOk": old_why is None, "oldReason": old_why, "newOk": new_why is None, "newReason": new_why,
                    "oldDev": old_dev, "newDev": new_dev, "candidates": sorted(ev), "flipped": flipped, "violations": bad,
                    "evidence": {str(x): v for x, v in ev.items()},
                    "measured": sum(1 for r in old_rows if r["status"] != "unmeasured"), "n": len(cs)})
        flip_surah = row["newOk"] and not row["oldOk"]
        row["flipSurahToAccept"] = flip_surah
        report.append(row)
        for x in flipped:
            flips.append((src, s, x))
        for c in bad:
            violations.append((src, s, c))
        print(f"■ {src} س{s} ({'ضبط' if row['forced'] else 'مرشّح'}) · {len(cs)} آية · مقيس {row['measured']}")
        print(f"   منحرفةٌ في القديم {old_dev} · مرشَّحةٌ للباب (ذاتُ تكرارٍ مقيس) {sorted(ev)} · انقلبت {flipped} · بقيت منحرفةً {new_dev}")
        for x in sorted(ev):
            e = ev[x]
            print(f"   {'✅ انقلبت' if e['passed'] else '⛔ بقيت'} {s}:{x} · بدء منشور {e['startMs']} · مِرساة {e['anchorMs']} (انحراف {e['devMs']})")
            print(f"      أداءٌ آخر مقيس: {e['otherPerformance']}")
            print(f"      شاهد: {'حاسم' if e['witnessOk'] else 'غير حاسم'} · فرق {e['witness']['diffMs']}م.ث · نافذة {e['witness']['windowMs']}"
                  f" (سليمة {e['witness']['windowOk']}) · بدء الكلمة − بدء النافذة {e['witness']['wordMinusWindowMs']}م.ث"
                  f"{' ⛔ ملتصق' if e['witness']['stuckToWindow'] else ''} · {e['witness']['detail']}")
            print(f"      تفريغ: {e['witness']['heard']}")
            c = e["census"]
            print(f"      إحصاء: {c.get('verdict') or 'لا حكم'} {c.get('reason') or ''} · تشابه {c.get('simSelf')} · أقرب جارة {c.get('nearestOther')} "
                  f"({c.get('simNearestOther')}) · فجوة {c.get('gap')} · كلمات {c.get('words')} · {c.get('detail') or ''}")
        print(f"   القديم: {'✅' if row['oldOk'] else '⛔ ' + str(old_why)[:220]}")
        print(f"   بعد الباب: {'✅' if row['newOk'] else '⛔ ' + str(new_why)[:220]}")
        print(f"   {'⚠️ انقلبت السورةُ نحو القبول' if flip_surah else 'لا انقلابَ للسورة نحو القبول'}"
              f"{' · ⛔ تغيّرٌ خارج الشرط ' + str(bad) if bad else ''}")
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    print("\n══ الخلاصة ══")
    for r in report:
        if "error" in r:
            print(f"  {r['src']} س{r['surah']}: ⚠️ {r['error']}")
            continue
        print(f"  {r['src']} س{r['surah']}{' [ضبط]' if r['forced'] else ''}: قديم {'✅' if r['oldOk'] else '⛔'} → جديد "
              f"{'✅' if r['newOk'] else '⛔'} · انقلبت آياتٌ {r['flipped']}{'  ⚠️ سورةٌ نحو القبول' if r['flipSurahToAccept'] else ''}")
    print(f"آياتٌ انقلبت نحو القبول: {len(flips)} — {flips}")
    print(f"تغيّراتٌ خارج الشرط (‏يجب أن تكون 0): {len(violations)} — {violations}")
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
