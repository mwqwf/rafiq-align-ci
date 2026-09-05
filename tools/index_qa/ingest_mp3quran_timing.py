#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""يبني فهرسَ توقيتاتٍ من **توقيتات mp3quran الرسمية** على ملفّات السور نفسها.

    python tools/index_qa/ingest_mp3quran_timing.py --reciter kurdi --riwaya hafs \
        --read 221 --url "https://server6.mp3quran.net/kurdi/{s:03d}.mp3" --out kurdi.jz

## لماذا (‏قرار المشرف github-10، 2026-09-05)

`api/v3/ayat_timing?surah=S&read=R` يعطي `start_time`/`end_time` بالمللي **لكل
آية على الملفّ الذي نخدمه نحن** — فهو فهرسٌ بلا محاذاةٍ أصلاً، و**قصٌّ بشريٌّ
موثوقٌ أعلى جودةً من أيّ محاذاةٍ آلية**. ويغطّي 73 من قرّاء `mode:surah` عندنا.

⚠️ **وليس معصوماً:** `read=1` سورة 036 ينتهي عند 487ث من ملفٍ طولُه 1241ث.
⇒ **مرشَّحُ فهرسٍ لا حقيقة**: يمرّ بالبوابة كاملةً كأيّ مرشَّح، وله فوق ذلك
حُرّاسٌ بنيويةٌ تخصّه هنا.

## الحُرّاس البنيوية (‏قبل الرفع، أمر المشرف)

1. **عدُّ الآي = عدُّ الرواية** لكل سورة، وإلا وُسمت السورة `timing_bad_count`.
2. **الرتابة**: `start < end` وكلُّ آيةٍ تبدأ عند نهاية سابقتها أو بعدها.
3. **نهايةُ آخر آية ضمن 2%** من مدّة الملفّ — والمدّةُ تُقرأ من فهرسنا القائم
   إن وُجد (‏أرخص وأدقّ من تنزيل الصوت)، فإن لم يوجد فمن ترويسة الملفّ.
   والفاشلةُ تُوسم `timing_truncated` **ولا تُصلَّح بالتخمين**.
4. ⛔ **والبسملةُ تُقرأ ولا تُخمَّن:** الصفُّ `ayah: 0` هو البسملة، فبدايةُ
   الآية الأولى نهايتُه — وهذا يحلّ «البسملة المبتلعة» من أصلها لا بالقصّ.
5. **السورةُ الفاشلة تخرج من الفهرس بسببٍ معلَن** في `missing.byReason`،
   ولا يُكتب لها توقيتٌ مخمَّن بحال.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:                                     # noqa: BLE001
        pass

API = "https://mp3quran.net/api/v3/ayat_timing?surah={s}&read={r}"
# عدُّ الآي بحفص — والروايات الأخرى تُعطى عدَّها في `--counts`.
COUNTS = [7, 286, 200, 176, 120, 165, 206, 75, 129, 109, 123, 111, 43, 52, 99,
          128, 111, 110, 98, 135, 112, 78, 118, 64, 77, 227, 93, 88, 69, 60,
          34, 30, 73, 54, 45, 83, 182, 88, 75, 85, 54, 53, 89, 59, 37, 35, 38,
          29, 18, 45, 60, 49, 62, 55, 78, 96, 29, 22, 24, 13, 14, 11, 11, 18,
          12, 12, 30, 52, 52, 44, 28, 28, 20, 56, 40, 31, 50, 40, 46, 42, 29,
          19, 36, 25, 22, 17, 19, 26, 30, 20, 15, 21, 11, 8, 8, 19, 5, 8, 8,
          11, 11, 8, 3, 9, 5, 4, 7, 3, 6, 3, 5, 4, 5, 6]
TOL = 0.02          # 2% تسامحٌ على مدّة الملفّ


def fetch(url, tries=4, timeout=40):
    last = None
    for i in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as r:
                return json.load(r)
        except Exception as e:                            # noqa: BLE001
            last = e
            time.sleep(2 ** i)
    raise RuntimeError(f"تعذّر الجلب بعد {tries}: {last}")


def durations_from_index(path):
    """{سورة: آخرُ نهايةٍ م.ث} من فهرسنا القائم — مرجعُ مدّةٍ بلا تنزيلِ صوت."""
    if not path or not os.path.exists(path):
        return {}
    with gzip.open(path, "rt", encoding="utf-8") as f:
        idx = json.load(f)
    out = {}
    for e in idx.get("entries") or []:
        s = int(e["ayahId"].split(":")[0])
        if e.get("endMs"):
            out[s] = max(out.get(s, 0), int(e["endMs"]))
    return out


def build_surah(rows, s, want, dur_ref):
    """يُرجع (مداخل، سببُ الرفض أو None)."""
    body = [r for r in rows if isinstance(r.get("ayah"), int) and r["ayah"] >= 1]
    if len(body) != want:
        return None, f"timing_bad_count:{len(body)}≠{want}"
    body.sort(key=lambda r: r["ayah"])
    prev_end = -1
    out = []
    for r in body:
        st, en = r.get("start_time"), r.get("end_time")
        if st is None or en is None or not (0 <= st < en) or st < prev_end - 1:
            return None, f"timing_not_monotonic:{r['ayah']}"
        prev_end = en
        out.append((r["ayah"], int(st), int(en)))
    ref = dur_ref.get(s)
    warn = None
    if ref:
        ratio = out[-1][2] / max(1, ref)
        # ⛔ **المرجعُ هنا «نهايةُ آخر آيةٍ عندنا» لا «مدّةُ الملفّ»**، والفرقُ
        #    بينهما ذيلُ الصمت — فحدُّ 2% يردّ سليماً كثيراً: قِيس على `kurdi`
        #    أنّ 20 سورةً تُردّ بفروقٍ 2–7% وكلُّها سليمة، بينما البترُ الحقيقيّ
        #    (‏`read=1` سورة 036) نسبتُه **39%**. فالحدُّ على **البتر** لا على
        #    الاختلاف: دون 90% أو فوق 110% ⇒ ردّ، وما بينهما تحذيرٌ يُطبع
        #    ويعبر إلى البوابة لتحكم عليه بالعيّنة الصوتية لا بالنسبة.
        # ⛔ **تصحيحٌ ثانٍ بقياس (‏س114 من kurdi):** ذيلُ الصمت نسبتُه من
        #    السورةِ القصيرةِ كبيرةٌ بطبعها — 4.4ث من 36ث = 12%. فحدُّ 90%
        #    يردّ سليماً أيضاً. والبترُ الحقيقيُّ 39%. ⇒ الردُّ دون **75%**،
        #    وما بين 75% و98% **تحذيرٌ يُكتب في الترويسة** (‏لا في السجل وحده،
        #    أمر المشرف github-10) فتراه البوابةُ وتفحصه بالعيّنة الصوتية.
        if ratio < 0.75 or ratio > 1.10:
            return None, f"timing_truncated:{out[-1][2]}ms≈{ratio:.0%}×{ref}ms"
        if abs(1 - ratio) > TOL:
            warn = {"surah": s, "lastEndMs": out[-1][2], "refEndMs": ref,
                    "ratio": round(ratio, 3),
                    "note": "نهايةٌ تخالف مرجعنا — تعبر، والعيّنةُ الصوتية تحكم"}
    return out, (None if warn is None else ("__warn__", warn))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reciter", required=True)
    ap.add_argument("--riwaya", default="hafs")
    ap.add_argument("--read", type=int, required=True)
    ap.add_argument("--url", required=True, help="قالبٌ فيه {s:03d}")
    ap.add_argument("--out", required=True)
    ap.add_argument("--duration-ref", help="فهرسُنا القائم (.jz) مرجعَ مدّة")
    ap.add_argument("--counts", help="ملفُّ عدِّ آيٍ بديل (JSON، 114 رقماً) لغير حفص")
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()

    counts = COUNTS
    if args.counts:
        counts = json.load(open(args.counts, encoding="utf-8"))
        if len(counts) != 114:
            sys.exit("⛔ ملفُّ العدّ يجب أن يحمل 114 رقماً")
    dur_ref = durations_from_index(args.duration_ref)

    def one(s):
        try:
            return s, fetch(API.format(s=s, r=args.read)), None
        except Exception as e:                            # noqa: BLE001
            return s, None, str(e)[:80]

    got = {}
    with ThreadPoolExecutor(args.workers) as ex:
        for s, rows, err in ex.map(one, range(1, 115)):
            got[s] = (rows, err)

    entries, dropped, byreason, warns = [], [], {}, []
    for s in range(1, 115):
        rows, err = got[s]
        if err or not isinstance(rows, list):
            dropped.append(s); byreason["timing_fetch_failed"] = byreason.get("timing_fetch_failed", 0) + counts[s - 1]
            continue
        built, why = build_surah(rows, s, counts[s - 1], dur_ref)
        if isinstance(why, tuple):
            warns.append(why[1]); why = None
        if built is None:
            dropped.append((s, why))
            key = why.split(":")[0]
            byreason[key] = byreason.get(key, 0) + counts[s - 1]
            continue
        url = args.url.format(s=s)
        for a, st, en in built:
            entries.append({"ayahId": f"{s}:{a}", "fileRef": url,
                            "startMs": st, "endMs": en,
                            "conf": 1.0, "confBand": "HIGH"})

    total = sum(counts)
    idx = {
        "schema": 1, "riwaya": args.riwaya, "reciterId": args.reciter,
        "sourceKind": "surah", "ayahCounting": "hafs",
        "ayahCount": total, "method": "mp3quran-ayat-timing",
        "engineVersion": "mp3quran-timing-v1", "refineVersion": "n/a-source",
        "timingSource": {"api": "mp3quran.net/api/v3/ayat_timing",
                         "readId": args.read,
                         "fetchedAt": int(time.time())},
        "timingWarnings": warns,
        "missing": {"count": total - len(entries),
                    "byReason": byreason,
                    "ids": []},
        "entries": entries,
    }
    raw = json.dumps(idx, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    with open(args.out, "wb") as fh:
        with gzip.GzipFile(fileobj=fh, mode="wb", compresslevel=9, mtime=0) as f:
            f.write(raw)
    sha = hashlib.sha256(open(args.out, "rb").read()).hexdigest()
    print(f"{args.reciter} (read={args.read}): مداخل {len(entries)}/{total} · "
          f"سورٌ مردودة {len(dropped)} · {byreason or '—'}")
    for d in dropped[:12]:
        print("  ⛔", d)
    for w in warns[:12]:
        print("  ⚠️", f"س{w['surah']}: {w['ratio']:.0%} من مرجعنا")
    if len(warns) > 12:
        print(f"  ⚠️ …و{len(warns) - 12} تحذيراً آخر")
    print(f"✅ {args.out} · sha256 {sha[:16]}…")


if __name__ == "__main__":
    main()
