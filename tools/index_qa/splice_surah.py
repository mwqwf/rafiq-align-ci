#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""يستبدل مداخلَ سورةٍ (أو سور) في فهرسٍ قائم بمخرَجِ إعادةِ محاذاةٍ لها وحدها.

    python tools/index_qa/splice_surah.py --index in.jz --surah 22 \
        --aligned work/s022.json --url "https://host/{s:03d}.mp3" --out new.jz

**لماذا يوجد؟** لأن إعادةَ محاذاةِ قارئٍ كاملٍ لأجل سورةٍ واحدةٍ إنفاقُ ساعةٍ
على منجَز — والعلّةُ في `deban/22` و`lhdan/103` وأخواتِهما **سورةٌ واحدةٌ مزاحة**
لا فهرسٌ فاسد. (‏قرار المشرف github-10، 2026-09-05: الحجُّ أوّلُ ما يُعاد.)

## الحُرّاس — وكلٌّ منها من واقعة

1. **الفهرسُ لا يُمسّ إلا في السورة المطلوبة** — تُقارَن المداخلُ خارجها
   حرفاً قبل الكتابة وبعدها، فإن تغيّر مدخلٌ واحدٌ خارجها **يُوقَف كلُّ شيء**.
   (‏لا يُصلَح انحرافٌ بصمت: الإصلاحُ يمحو الدليل.)
2. **لا يُكتب مخرَجٌ ناقص:** إن رجعت المحاذاةُ بآيةٍ بلا حدود (`startMs is None`)
   فالسورةُ **لم تُحَلّ**، ويُردّ العملُ كلُّه بدل أن يُنتج فهرساً أسوأ من الأصل
   في موضعٍ ويُظنّ أحسن.
3. **عددُ الآيات يُطابَق بعدّ الرواية** لا بعدد ما رجع — فمخرَجٌ فيه آيتان
   لسورةٍ من ثلاثٍ يُردّ.
4. **الحدودُ تُفحص صعوداً** (‏`start < end` و`start[i] >= end[i-1]`)، فمخرَجٌ
   متداخلُ الحدود يُظهر للحافظ آيةً على صوت أختها.
5. ⛔ **ولا يُرفع من هنا:** المخرَجُ ملفٌّ محلّيّ، ورفعُه بـ`stage_transform.py`
   بحُرّاسه هو — كاتبٌ واحدٌ إلى الدلو لا كاتبان.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:                                     # noqa: BLE001
        pass

# عدُّ آي حفص — يُستعمل للتحقّق من اكتمال السورة المُعادة وحدها.
COUNTS = [7, 286, 200, 176, 120, 165, 206, 75, 129, 109, 123, 111, 43, 52, 99,
          128, 111, 110, 98, 135, 112, 78, 118, 64, 77, 227, 93, 88, 69, 60,
          34, 30, 73, 54, 45, 83, 182, 88, 75, 85, 54, 53, 89, 59, 37, 35, 38,
          29, 18, 45, 60, 49, 62, 55, 78, 96, 29, 22, 24, 13, 14, 11, 11, 18,
          12, 12, 30, 52, 52, 44, 28, 28, 20, 56, 40, 31, 50, 40, 46, 42, 29,
          19, 36, 25, 22, 17, 19, 26, 30, 20, 15, 21, 11, 8, 8, 19, 5, 8, 8,
          11, 11, 8, 3, 9, 5, 4, 7, 3, 6, 3, 5, 4, 5, 6]


def load(p: Path) -> dict:
    with gzip.open(p, "rt", encoding="utf-8") as f:
        return json.load(f)


def dump(d: dict, p: Path) -> str:
    raw = json.dumps(d, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    # ⛔ `mtime` معاملُ `GzipFile` لا `gzip.open` — و`gzip.open` يرفعه TypeError.
    #    وتثبيتُه صفراً مقصود: بصمةُ الملفّ يجب أن تتبع المحتوى وحده، فترويسةٌ
    #    فيها زمنُ البناء تُغيّر sha256 لمخرَجٍ لم يتغيّر.
    with open(p, "wb") as fh:
        with gzip.GzipFile(fileobj=fh, mode="wb", compresslevel=9, mtime=0) as f:
            f.write(raw)
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", required=True)
    ap.add_argument("--surah", required=True, help="سورةٌ أو أكثر بفواصل")
    ap.add_argument("--aligned", required=True, nargs="+",
                    help="مخرَجُ pipeline.py لكل سورة، بترتيب --surah")
    ap.add_argument("--url", required=True, help="قالبُ الصوت، مثل https://h/{s:03d}.mp3")
    ap.add_argument("--out", required=True)
    ap.add_argument("--skip-unresolved", action="store_true",
                    help="سورةٌ لم تُحلّ كلُّ آياتها تُترك كما هي في الأصل "
                         "وتُسمّى في المخرَج، بدل ردّ الدفعة كلِّها")
    args = ap.parse_args()

    surahs = [int(x) for x in args.surah.replace(",", " ").split()]
    if len(surahs) != len(args.aligned):
        sys.exit("⛔ عددُ السور لا يطابق عددَ ملفّات المحاذاة")

    idx = load(Path(args.index))
    entries = idx.get("entries") or []
    before_out = [e for e in entries if int(e["ayahId"].split(":")[0]) not in surahs]

    new_rows, skipped, taken = [], [], []
    for s, af in zip(surahs, args.aligned):
        res = json.load(open(af, encoding="utf-8"))
        rows = res.get("entries") or []
        want = COUNTS[s - 1]
        # ⛔ **الردُّ بالسورة لا بالدفعة** (‏تصحيحُ 2026-09-05): كان خللٌ في
        #    آيةٍ واحدةٍ يردّ اثنتي عشرةَ سورةً سليمةً معها — عقوبةٌ على
        #    التجميع لا على العطب. فالسورةُ التي لم تُحَلّ **تُترك كما هي في
        #    الأصل وتُسمَّى**، والباقياتُ تمضي. والمبدأ محفوظ: لا يُكتب ناقصٌ
        #    في موضعٍ ولا يُمسّ ما لم يُحَلّ.
        bad = None
        if len(rows) != want:
            bad = f"رجعت {len(rows)} آية والرواية {want}"
        else:
            prev = -1
            for i, r in enumerate(rows):
                st, en = r.get("startMs"), r.get("endMs")
                if st is None or en is None:
                    bad = f"{i + 1} بلا حدود"; break
                if not (0 <= st < en) or st < prev:
                    bad = f"{i + 1} حدودٌ غيرُ صاعدة ({st}→{en})"; break
                prev = en
        if bad:
            if not args.skip_unresolved:
                sys.exit(f"⛔ س{s}:{bad} — السورةُ لم تُحَلّ، ولا يُكتب ناقص")
            skipped.append(f"س{s}: {bad}")
            continue
        taken.append(s)
        prev_end = -1
        for i, r in enumerate(rows):
            st, en = r.get("startMs"), r.get("endMs")
            prev_end = en
            conf = float(r.get("conf") or 0.0)
            band = "HIGH" if conf >= 0.8 else ("MED" if conf >= 0.5 else "LOW")
            row = {"ayahId": f"{s}:{i + 1}", "fileRef": args.url.format(s=s),
                   "startMs": int(st), "endMs": int(en),
                   "conf": round(conf, 3), "confBand": band}
            if r.get("snapped") is False:
                row["startApprox"] = True
            new_rows.append(row)

    if args.skip_unresolved:
        surahs = taken
        before_out = [e for e in entries
                      if int(e["ayahId"].split(":")[0]) not in surahs]
        if not surahs:
            sys.exit("⛔ لم تُحلّ سورةٌ واحدة — لا شيءَ يُستبدل")
    merged = before_out + new_rows
    merged.sort(key=lambda e: (int(e["ayahId"].split(":")[0]),
                               int(e["ayahId"].split(":")[1])))

    # ⛔ الحارس 1: ما خارج السور المطلوبة لم يُمسّ — يُقارَن حرفاً.
    after_out = [e for e in merged if int(e["ayahId"].split(":")[0]) not in surahs]
    if json.dumps(before_out, sort_keys=True) != json.dumps(after_out, sort_keys=True):
        sys.exit("⛔ تغيّر مدخلٌ خارج السور المطلوبة — يُوقَف ولا يُصلَح بصمت")

    out = dict(idx, entries=merged)
    miss = dict(out.get("missing") or {})
    ids = [e["ayahId"] for e in merged]
    have = set(ids)
    all_ids = [f"{s}:{a}" for s in range(1, 115) for a in range(1, COUNTS[s - 1] + 1)]
    gone = [i for i in all_ids if i not in have]
    miss["count"] = len(gone)
    miss["ids"] = gone[:400]
    # السورُ المُعادةُ تخرج من عذر البتر: عادت مداخلُها فلا غيابَ يُعتذر عنه.
    by = dict(miss.get("byReason") or {})
    if by.get("source_truncated"):
        back = sum(COUNTS[s - 1] for s in surahs)
        by["source_truncated"] = max(0, int(by["source_truncated"]) - back)
        if not by["source_truncated"]:
            by.pop("source_truncated")
    miss["byReason"] = by
    out["missing"] = miss

    sha = dump(out, Path(args.out))
    for w in skipped:
        print("  ⚠️ تُركت كما هي:", w)
    print(f"المداخل {len(entries)} ⇐ {len(merged)} · الغياب {(idx.get('missing') or {}).get('count')}"
          f" ⇐ {miss['count']} · سور {surahs}")
    print(f"✅ {args.out} · sha256 {sha[:16]}…")


if __name__ == "__main__":
    main()
