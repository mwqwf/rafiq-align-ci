#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""أيُّ فهرسٍ **منشور** بلا شاهدِ مطالعٍ موثوقٍ على بصمته الحاليّة؟ — قارئٌ محض.

⛔ **سببُه مقيسٌ 2026-09-29:** فهرسُ `hafs/nufais` المنشور كان فيه بسملةٌ مبتلعةٌ
في 37:1 (بدء 1820م.ث)، ولم يكشفها إلا ملوحُ مرشّحٍ لاحق. وشرطُ المطالع في
`promote.py` لا يمنع إن غاب الشاهد («غيابُ الحقل لا يمنع») ⇒ فالمنشورُ قبل
هذا الشرط، أو بشاهدٍ من أداةٍ غير موثوقة، لم يُفحص مطلعُه قطّ.

يطبع لكلّ فهرسٍ في `timings/**.jz`: بصمته، وهل له شاهدُ مطالع **بالبصمة نفسها**
صادرٌ عن أداةٍ موثوقة (`promote.openers_tool_ok`)، وفواتلُه إن وُجدت. ثمّ سطراً
أخيراً `UNCOVERED=<مفاتيح بفاصلة>` يُمرَّر إلى `openers.yml` (‏`only`).

    python tools/index_qa/openers_coverage.py

⚖️ لا يكتب بايتاً ولا يحكم: الحكمُ لـ`openers.yml` ثمّ لـ`promote.py` كما هما.
"""
import gzip
import hashlib
import io
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run import s3  # noqa: E402
from promote import late_ctc_trusted, openers_tool_ok  # noqa: E402

LATE_MS = int(os.environ.get("OPENERS_LATE_MS", "4000"))

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                  # noqa: BLE001
        pass


def _list(cl, bucket, prefix):
    out = []
    for pg in cl.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=prefix):
        out += [o["Key"] for o in pg.get("Contents", [])]
    return out


def main() -> int:
    cl, bucket = s3()
    pub = [k for k in _list(cl, bucket, "timings/")
           if k.endswith(".jz") and k.count("/") == 2]
    if "--list-published" in sys.argv:
        print("PUBLISHED=" + ",".join(sorted(pub)))
        return 0
    ops = [k for k in _list(cl, bucket, "state/") if k.endswith(".openers.json")]
    print(f"فهارسُ منشورة: {len(pub)} · شواهدُ مطالع في state/: {len(ops)}")

    def _get(k):
        for _ in range(3):
            try:
                return k, cl.get_object(Bucket=bucket, Key=k)["Body"].read()
            except Exception:                          # noqa: BLE001
                continue
        return k, None

    with ThreadPoolExecutor(max_workers=16) as pool:
        op_raw = dict(pool.map(_get, ops))
        pub_raw = dict(pool.map(_get, pub))

    # أحدثُ شاهدٍ موثوقٍ لكلّ بصمة — بالمقياس نفسِه الذي يحكم به الحارس.
    by_sha = {}
    for k, raw in op_raw.items():
        if raw is None:
            continue
        try:
            rep = json.loads(raw.decode("utf-8"))
        except Exception:                              # noqa: BLE001
            continue
        for r in (rep if isinstance(rep, list) else [rep]):
            if not isinstance(r, dict) or not r.get("sha256"):
                continue
            if not openers_tool_ok(r):
                continue
            t = float(r.get("ts") or r.get("at") or 0)
            cur = by_sha.get(r["sha256"])
            if cur is None or t > cur[0]:
                by_sha[r["sha256"]] = (t, k, r)

    uncovered, flagged, unread, late = [], [], [], []
    for k in sorted(pub):
        raw = pub_raw.get(k)
        if raw is None:
            unread.append(k)
            continue
        sha = hashlib.sha256(raw).hexdigest()
        hit = by_sha.get(sha)
        if not hit:
            uncovered.append(k)
            continue
        # بالحقول التي يقرؤها الحارس نفسُه (‏`promote.gate`): المؤكَّدُ `swallowed`
        # و`openers.defects`؛ و`tail` و`suspect` تُعرض عدداً فقط كما يعرضها.
        r = hit[2]
        blob = r.get("openers") if isinstance(r.get("openers"), dict) else {}
        hard = (list(blob.get("defects") or []) + list(r.get("swallowed") or [])
                + list(r.get("lateConfirmed") or []))
        soft = sorted(set(r.get("tail") or []) | set(r.get("suspect") or []))
        if hard or soft:
            flagged.append((k, hard, soft))
        # ⛔ **«سليمٌ» عند درجةٍ متأخّرة ليس سلامة** (‏النفيس 37:1 · 2026-09-29): الدرجاتُ
        #    1–4ث لم تُفرَّغ فيها البسملةُ فخرجت فارغة، ثمّ سُمع أوّلُ الآية عند 6ث فحُكم
        #    «سليماً» — والمدخلُ يبدأ قبل الآية بثلاث ثوانٍ. يُسرد هنا مرشّحاً لا حكماً.
        for row in r.get("rows") or []:
            if row.get("verdict") == "clean" and (row.get("rung") or 0) >= LATE_MS:
                late.append((k, row.get("surah"), row.get("startMs"), row.get("rung"),
                             row.get("heard")))

    print(f"\n✅ مغطّاةٌ بشاهدٍ موثوقٍ على بصمتها: {len(pub) - len(uncovered) - len(unread)}")
    print(f"⛔ بشاهدٍ فيه مطلعٌ مبتلعٌ مؤكَّد: {sum(1 for f in flagged if f[1])}")
    for k, hard, soft in flagged:
        if hard:
            print(f"   {k}: مبتلعٌ {hard}" + (f" · مشكوك {soft}" if soft else ""))
    print(f"⚠️ بشاهدٍ فيه مشكوكٌ وحده (tail/suspect — لا يمنع): "
          f"{sum(1 for f in flagged if not f[1])}")
    for k, hard, soft in flagged:
        if not hard:
            print(f"   {k}: {soft}")
    print(f"⚠️ بلا شاهدٍ موثوقٍ على بصمتها الحاليّة: {len(uncovered)}")
    # ⛔ **شاهدٌ لم يسأل عن التأخّر لا يشهد ببراءة البسملة المبتلعة** (‏2026-09-30 · حارسُ promote نفسُه).
    no_late = [k for k in sorted(pub) if k not in uncovered and k not in unread
               and "late" not in by_sha[hashlib.sha256(pub_raw[k]).hexdigest()][2]]
    print(f"⚠️ بشاهدٍ سابقٍ لحارس التأخّر (‏لا حقلَ late — يُعاد مسحُه): {len(no_late)}")
    for k in no_late:
        print(f"   NOLATE\t{k}")
    # للإصلاح: بدءُ CTC لكلّ مطلعٍ مؤكَّد ⇒ تخطّي realign_surah = ctcStartMs − 300
    for k in sorted(pub):
        if k in uncovered or k in unread:
            continue
        r = by_sha[hashlib.sha256(pub_raw[k]).hexdigest()][2]
        for s in r.get("lateConfirmed") or []:
            d = (r.get("lateCtc") or {}).get(str(s)) or {}
            url = next((x.get("url") for x in r.get("rows") or [] if x.get("surah") == s), "")
            print(f"   FIX\t{k}\t{s}\tindex={d.get('indexStartMs')}\tctc={d.get('ctcStartMs')}"
                  f"\tconf={d.get('conf')}\t{url}")
    if unread:
        print(f"⚠️ تعذّرت قراءتُها (لا يُحكم عليها): {len(unread)} — {', '.join(unread)}")
    print(f"\n🔎 «سليمٌ» عند درجة ≥{LATE_MS}م.ث (مرشّحو بسملةٍ مبتلعةٍ فاتت الفاحص): {len(late)}")
    for k, s, st, rung, heard in late:
        print(f"   {k} · س{s} · بدء {st}م.ث · درجة {rung} · سُمع «{heard}»")
    # ‏`--rows <riwaya>/<id>`: بدءُ الآية الأولى لكلّ سورةٍ كما في شاهد المنشور — للمقابلة بسبر CTC.
    if "--rows" in sys.argv:
        want = f"timings/{sys.argv[sys.argv.index('--rows') + 1]}.jz"
        raw = pub_raw.get(want)
        hit = by_sha.get(hashlib.sha256(raw).hexdigest()) if raw else None
        for row in (hit[2].get("rows") if hit else []) or []:
            print(f"ROW\t{want}\t{row.get('surah')}\t{row.get('startMs')}\t"
                  f"{row.get('verdict')}\t{row.get('rung')}")
    # ⛔ **تبرئةُ متأخّرٍ بمسبارٍ غيرِ حتميّ لا تشهد** (‏fixV 2026-10-05 · `promote.late_ctc_trusted`):
    #    int8 وذيلُ 1.5ث أبرأا الحارثيّ 89 الصادقَ ⇒ يُعاد مسحُ كلِّ منشورٍ برّأ متأخّراً بهما.
    oldctc = []
    for k in sorted(pub):
        if k in uncovered or k in unread:
            continue
        r = by_sha[hashlib.sha256(pub_raw[k]).hexdigest()][2]
        acq = sorted(set(r.get("late") or []) - set(r.get("lateConfirmed") or []))
        if acq and not late_ctc_trusted(r):
            oldctc.append(k)
            print(f"   OLDCTC\t{k}\t{acq}\t{r.get('lateCtcPrecision') or 'int8 · tail 1500'}")
    print(f"⚠️ برّأ متأخّراً بمسبارٍ غيرِ حتميّ (‏يُعاد مسحُه): {len(oldctc)}")
    print("UNCOVERED=" + ",".join(uncovered))
    print("RESCAN=" + ",".join(sorted(set(uncovered) | set(no_late) | set(oldctc))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
