# -*- coding: utf-8 -*-
"""مقارنة فهرسَي توقيتات لقارئٍ واحد: قبل الوصفة المصححة وبعدها.

المخرج ثلاثة أرقام يطلبها القرار (‏github-f4):
  1. نسبة HIGH ونصيب MED في كل نسخة.
  2. **عدد الحدود التي تغيّرت أكثر من 300م.ث** — وهو الرقم الذي يقول كم من
     الفهرس كان **معطوباً فعلاً** لا كم كان **معرّضاً** (فالتعرّض 98.7% لهذا
     القارئ، والعطب الفعلي ما تكشفه هذه المقارنة وحدها).
  3. توزيع التغيّر حسب طول المقطع المقدَّر (‏≤10ث · 10–20ث · >20ث) — فإن
     تركّز التغيّر فوق العشر ثوانٍ فتلك بصمة `-ac 512` لا ضجيج إعادة تشغيل.

    python tools/tasmi_bench/compare_index.py --before A.jz --after B.jz
"""
import argparse
import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "tools", "alignment"))
sys.path.insert(0, HERE)
from ac_exposure import segments, wilson  # noqa: E402
from common import read_jz  # noqa: E402


def bands(ti):
    c = collections.Counter(e.get("confBand") or "?" for e in ti["entries"])
    t = sum(c.values()) or 1
    return c, t


def seg_bucket_of_entry(ti):
    """لكل ayahId: طبقة طول المقطع المقدَّر الذي وُلد فيه حدُّه."""
    out = {}
    by_file = {}
    for e in ti["entries"]:
        by_file.setdefault(e["fileRef"], []).append(e)
    for _, es in by_file.items():
        es.sort(key=lambda e: e["startMs"])
        cur = []
        for e in es:
            if cur and not e.get("startApprox"):
                _tag(cur, out)
                cur = []
            cur.append(e)
        if cur:
            _tag(cur, out)
    return out


def _tag(group, out):
    ms = group[-1]["endMs"] - group[0]["startMs"]
    b = "≤10ث" if ms <= 10_000 else ("10–20ث" if ms <= 20_000 else ">20ث")
    for e in group:
        out[e["ayahId"]] = b


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--before", required=True)
    ap.add_argument("--after")
    ap.add_argument("--threshold", type=int, default=300)
    ap.add_argument("--after-json", nargs="*", default=[],
                    help="مخرجات pipeline لسور بعينها (بدل فهرس كامل بعدي)")
    ap.add_argument("--surahs", nargs="*", type=int, default=[])
    args = ap.parse_args()
    a = read_jz(args.before)
    if args.after_json:
        # نسخة «بعد» جزئية: مخرجات pipeline لسور مختارة تُحوَّل إلى شكل الفهرس
        ents = []
        for f in args.after_json:
            d = json.load(open(f, encoding="utf-8"))
            sn = d["surah"]
            for k, v in d["starts"].items():
                ay = k if ":" in str(k) else f"{sn}:{int(k)+1}"
                ents.append({"ayahId": ay, "startMs": v, "endMs": v,
                             "fileRef": f"s{sn}", "confBand": None})
        b = {"entries": ents}
        surahs = {d["surah"] for d in
                  (json.load(open(f, encoding="utf-8")) for f in args.after_json)}
        a = {"entries": [e for e in a["entries"]
                         if int(e["ayahId"].split(":")[0]) in surahs]}
    else:
        b = read_jz(args.after)
    ca, ta = bands(a)
    cb, tb = bands(b)
    print(f"قبل: {ta} مدخلاً · " + " · ".join(f"{k} {v} ({v/ta*100:.1f}%)" for k, v in sorted(ca.items())))
    print(f"بعد: {tb} مدخلاً · " + " · ".join(f"{k} {v} ({v/tb*100:.1f}%)" for k, v in sorted(cb.items())))

    A = {e["ayahId"]: e for e in a["entries"]}
    B = {e["ayahId"]: e for e in b["entries"]}
    common = sorted(set(A) & set(B))
    buckets = seg_bucket_of_entry(a)
    changed = collections.Counter()
    total = collections.Counter()
    deltas = []
    for k in common:
        d = abs(B[k]["startMs"] - A[k]["startMs"])
        deltas.append(d)
        bkt = buckets.get(k, "?")
        total[bkt] += 1
        if d > args.threshold:
            changed[bkt] += 1
    n = len(common)
    ch = sum(changed.values())
    lo, hi = wilson(ch, n)
    print(f"\nمشترك: {n} حدّاً · **تغيّر >{args.threshold}م.ث: {ch} = "
          f"{ch/n*100:.1f}% [{lo:.1f}–{hi:.1f}]**")
    deltas.sort()
    print(f"  الإزاحة: وسيط {deltas[n//2]}م.ث · p90 {deltas[int(0.9*n)-1]}م.ث · "
          f"أقصى {deltas[-1]}م.ث")
    print("  حسب طول المقطع (نسبة المتغيّر داخل كل طبقة):")
    for bkt in ("≤10ث", "10–20ث", ">20ث", "?"):
        if total.get(bkt):
            print(f"   {bkt:7s} {changed[bkt]}/{total[bkt]} = "
                  f"{changed[bkt]/total[bkt]*100:5.1f}%")
    moved = sum(1 for k in common
                if (A[k].get("confBand"), B[k].get("confBand")) == ("MED", "HIGH"))
    down = sum(1 for k in common
               if (A[k].get("confBand"), B[k].get("confBand")) == ("HIGH", "MED"))
    print(f"  ترقية MED⇒HIGH: {moved} · تنزيل HIGH⇒MED: {down}")
    only_a = len(set(A) - set(B)); only_b = len(set(B) - set(A))
    if only_a or only_b:
        print(f"  ⚠️ مدخلات في نسخةٍ دون الأخرى: قبل {only_a} · بعد {only_b}")


if __name__ == "__main__":
    main()
