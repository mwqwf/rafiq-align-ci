#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""أين صوتُ الآية الغائبة؟ — قارئٌ محضٌ يقيس الفجوةَ بين جارتَيها في الفهرس المنشور.

⭐ **الفكرة (2026-09-29):** آيةٌ غائبةٌ بين آيتين محاذاتَين صوتُها محصورٌ بين نهاية
سابقتها وبداية لاحقتها — فإن كانت الفجوةُ بطول نصّها (بمعدّل القارئ نفسِه في
السورة نفسِها) فالآيةُ هناك، ويبقى **إثباتُ ذلك بالسمع** قبل أيّ كتابة. وإن كانت
الفجوةُ صفراً فصوتُها ابتلعته جارتُها، ولا يُسدّ من هذا الباب.

⚖️ لا يكتب بايتاً ولا يحكم: يطبع لكلّ غيابٍ (سورة · آيات · فجوة · متوقَّع · نسبة · صنف)
والحكمُ لأداةٍ تسمع النافذة وتقابلها بالنصّ.

    python tools/index_qa/gap_probe.py            # كلُّ الفهارس المنشورة ذات النقص
    python tools/index_qa/gap_probe.py hafs/nufais # قارئٌ بعينه
"""
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "alignment"))
from run import fetch_index, s3  # noqa: E402
from common import load_index, load_text, norm  # noqa: E402

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                  # noqa: BLE001
        pass

FILL_LO, FILL_HI = 0.6, 1.8      # الفجوةُ ÷ المتوقَّع: نطاقُ «الآيةُ هناك على الأرجح»
ABSORBED_MS = 400                # فجوةٌ دون هذا = الصوتُ في الجارة لا بينهما


def main() -> int:
    only = sys.argv[1:] or None
    qidx = load_index()
    start_of = {s["n"]: (s["start"], s["ayahs"]) for s in qidx["surahs"]}
    texts = {}
    cl, b = s3()
    keys = []
    for pg in cl.get_paginator("list_objects_v2").paginate(Bucket=b, Prefix="timings/"):
        for o in pg.get("Contents", []):
            k = o["Key"]
            if k.endswith(".jz") and k.count("/") == 2:
                keys.append(k)
    if only:
        keys = [k for k in keys if k[len("timings/"):-3] in only]
    tot = {"fill": 0, "absorbed": 0, "opener": 0, "tail": 0, "other": 0, "surah": 0}
    for key in sorted(keys):
        try:
            idx, sha = fetch_index(key)
        except Exception as ex:                        # noqa: BLE001
            print(f"⚠️ {key}: تعذّرت القراءة — {ex}")
            continue
        riw = idx.get("riwaya") or key.split("/")[1]
        if riw not in texts:
            texts[riw] = load_text(riw)
        text = texts[riw]
        have = {}
        for e in idx.get("entries") or []:
            s, a = (int(x) for x in str(e["ayahId"]).split(":"))
            if e.get("startMs") is not None and e.get("endMs") is not None:
                have[(s, a)] = (e["startMs"], e["endMs"])
        rows = []
        for s in range(1, 115):
            st0, n = start_of[s]
            present = [a for a in range(1, n + 1) if (s, a) in have]
            if not present:
                if any((s, a) for a in range(1, n + 1)):
                    rows.append((s, 1, n, None, None, None, "surah"))
                continue
            # معدّلُ القارئ في هذه السورة: م.ث لكلّ حرفٍ من الآيات الحاضرة
            rates = []
            for a in present:
                ch = len(norm(text[st0 + a - 1]).replace(" ", ""))
                d = have[(s, a)][1] - have[(s, a)][0]
                if ch and d > 0:
                    rates.append(d / ch)
            rate = statistics.median(rates) if rates else None
            a = 1
            while a <= n:
                if (s, a) in have:
                    a += 1
                    continue
                b0 = a
                while a <= n and (s, a) not in have:
                    a += 1
                b1 = a - 1
                chars = sum(len(norm(text[st0 + x - 1]).replace(" ", ""))
                            for x in range(b0, b1 + 1))
                exp = round(chars * rate) if rate else None
                prev = have.get((s, b0 - 1))
                nxt = have.get((s, b1 + 1))
                if prev is None:
                    kind, gap = "opener", None
                elif nxt is None:
                    kind, gap = "tail", None
                else:
                    gap = nxt[0] - prev[1]
                    r = gap / exp if exp else None
                    if gap < ABSORBED_MS:
                        kind = "absorbed"
                    elif r is not None and FILL_LO <= r <= FILL_HI:
                        kind = "fill"
                    else:
                        kind = "other"
                rows.append((s, b0, b1, gap, exp, prev[1] if prev else None, kind))
        if not rows:
            continue
        print(f"■ {key} · {sha[:8]} · مداخل {len(have)}")
        for s, b0, b1, gap, exp, pend, kind in rows:
            tot[kind] += (b1 - b0 + 1)
            rng = f"{b0}" if b0 == b1 else f"{b0}-{b1}"
            ratio = f"{gap / exp:.2f}" if gap is not None and exp else "—"
            print(f"   GAP\t{key}\t{s}\t{rng}\t{kind}\tgap={gap}\texp={exp}\tratio={ratio}\tfrom={pend}")
    print("\nالحصيلة بالآيات: " + " · ".join(f"{k}={v}" for k, v in tot.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
