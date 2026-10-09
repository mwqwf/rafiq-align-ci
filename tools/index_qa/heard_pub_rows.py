#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""جدولُ انحرافات بدء الآيات عن المسموع لفهرسٍ منشور — قارئٌ محض (fixD · 2026-10-09).

    python tools/index_qa/heard_pub_rows.py <timings/riw/id.jz> [سور بفواصل] [--all]

يقرأ الفهرسَ المنشور وخريطةَ السماع في `state-heard/` ويطبع لكلّ سورةٍ آياتِها
المنحرفة (status=dev) بالبدء المنشور والمسموع والجودة والانحراف، مع مطابقة بصمة
صوت الخريطة لبصمة الفهرس المعلنة (‏لكشف قياسٍ على ملفٍّ غير ملفّ المنشور).
لا يكتب شيئاً ولا يمسّ حارساً.
"""
from __future__ import annotations
import gzip, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import heard_gate as H  # noqa: E402
from run import s3  # noqa: E402


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    show_all = "--all" in sys.argv
    key = args[0]
    want = {int(x) for x in args[1].split(",")} if len(args) > 1 and args[1] else None
    cl, b = s3()
    idx = json.loads(gzip.decompress(cl.get_object(Bucket=b, Key=key)["Body"].read()))
    cs = H.by_surah(idx["entries"])
    shas = idx.get("audioSha256")
    present = sorted(cs)
    if isinstance(shas, list) and len(shas) == 114:
        sha_of = {s: shas[s - 1] for s in present}
    elif isinstance(shas, list) and len(shas) == len(present):
        sha_of = dict(zip(present, shas))
    else:
        sha_of = {}
    maps = {}
    for pre in (H.state_key(key),):
        try:
            rep = json.loads(cl.get_object(Bucket=b, Key=pre)["Body"].read())
        except Exception as ex:  # noqa: BLE001
            print("⛔ لا خريطة:", pre, ex); return 1
        for sk, m in (rep.get("maps") or {}).items():
            maps[int(sk)] = m
    print(f"■ {key} · سور حاضرة {len(present)} · خرائط {len(maps)}")
    for s in present:
        if want and s not in want:
            continue
        m = maps.get(s)
        if not m:
            print(f"س{s}: بلا خريطة"); continue
        same = (m.get("sha256") == sha_of.get(s))
        starts = {a: v[0] for a, v in cs[s].items()}
        ends = {a: v[1] for a, v in cs[s].items()}
        rows = H.surah_rows(starts, m)
        dev = [r for r in rows if r["status"] == "dev"]
        unm = [r["ayah"] for r in rows if r["status"] == "unmeasured"]
        if not dev and not show_all:
            continue
        n = len(cs[s])
        print(f"── س{s} · آيات {n} · بصمةُ الخريطة {'=' if same else '≠'} بصمةَ الفهرس · totalMs={m.get('totalMs')} · منحرفة {len(dev)} · غير مقيسة {len(unm)} · fileRef={next(iter(cs[s].values()))[2]}")
        for r in (rows if show_all else dev):
            e = ends.get(r["ayah"])
            print(f"   {s}:{r['ayah']}\tpub={r['startMs']}\theard={r['anchorMs']}\tq={r['q']}\tdev={r['devMs']}\tend={e}\t{r['status']}")
        if unm:
            print("   غير مقيسة:", ",".join(map(str, unm[:60])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
