# -*- coding: utf-8 -*-
"""حزم سور متوازنة **بمدة الصوت** لعمال التوليد الكلمي المتوازي.

التقسيم بالسورة لا بالآية (عاملان على سورة واحدة يتنافسان على ملف صوتها)، والوزن
مدة آيات HIGH في الفهرس لا عددها (كلفة whisper بالثواني لا بالآيات؛ مقيس 2026-09-01:
8 حزم × ~11,100ث أعطت ~20 دقيقة لكل حزمة على 4 خيوط).

python make_bins.py --index <idx.jz> --parts 8 [--exclude 78-114] [--out bins.json]
"""
import argparse
import json
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))), "alignment"))
from common import read_jz  # noqa: E402


def parse_range(spec):
    out = set()
    for part in (spec or "").split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-")
            out.update(range(int(a), int(b) + 1))
        else:
            out.add(int(part))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", required=True)
    ap.add_argument("--parts", type=int, default=8)
    ap.add_argument("--exclude", default="", help="سور تُستثنى (مثل 78-114 إن عولجت أولاً)")
    ap.add_argument("--only", default="", help="حصر الحزم في سور بعينها")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    ti = read_jz(args.index)
    excl, only = parse_range(args.exclude), parse_range(args.only)
    dur, cnt = {}, {}
    for e in ti["entries"]:
        if e.get("confBand") != "HIGH" or e.get("startMs") is None:
            continue
        sn = int(e["ayahId"].split(":")[0])
        if sn in excl or (only and sn not in only):
            continue
        dur[sn] = dur.get(sn, 0) + e["endMs"] - e["startMs"]
        cnt[sn] = cnt.get(sn, 0) + 1
    bins = [[0, []] for _ in range(args.parts)]
    for sn in sorted(dur, key=lambda s: -dur[s]):         # الأطول أولاً، إلى الأخفّ حملاً
        b = min(bins, key=lambda x: x[0])
        b[0] += dur[sn]
        b[1].append(sn)
    spec = {}
    for i, (d, ss) in enumerate(bins, 1):
        spec[str(i)] = ",".join(str(s) for s in sorted(ss))
        print("bin%d: %ds · %d آية · %s" % (i, d // 1000, sum(cnt[s] for s in ss), spec[str(i)]))
    print("HIGH المشمولة: %d آية في %d سورة · %d ثانية"
          % (sum(cnt.values()), len(cnt), sum(dur.values()) // 1000))
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(spec, f, indent=1)
        print("كُتب", args.out)


if __name__ == "__main__":
    main()
