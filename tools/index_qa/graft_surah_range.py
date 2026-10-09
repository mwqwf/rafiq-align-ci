#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""طعمُ مدى آياتٍ من مرشّحٍ مُنتَجٍ بحُرّاسه فوق منشورٍ — مرشّحٌ جديدٌ إلى `timings-staging/` وحده (pK · 2026-10-09).

    python tools/index_qa/graft_surah_range.py --base timings/hafs/kurdi.jz --base-sha 73c7ded5 \\
        --donor timings-staging/hafs/kurdi.e5e972c6.jz --donor-sha e5e972c6 --surah 42 --from 25 \\
        --reason "…" --yes

**لماذا:** وضعُ السماع (`ctc_splice heard`) يعيد بناءَ السورة كلِّها فيصلح الذيلَ المعطوب لكنّه يُفسد آياتٍ سليمةً
في أوّلها (‏س42: 1–4 و22–24 في الكردي). والمنشورُ سليمٌ في ما قبل المدى. فالمطلوب مرشّحٌ **يأخذ من المنشور ما كان سليماً
ومن المرشّح المُنتَج بحُرّاسه ما أصلحه** — دون أن يُنشئ زمناً: كلُّ بدءٍ في المرشّح الناتج هو بدءٌ من أحد الفهرسين الأصليّين.

**حُرّاسُه (تُرفع بالسبب ولا تُخفَّف):**
1. بصمتا الأصل والمتبرَّع تطابقان المطلوبتين، والمتبرَّعُ مشتقٌّ من الأصل نفسِه (`transform.fromSha256` = بصمة الأصل).
2. الفهرسان للقارئ والرواية نفسِها، وبقيّةُ السور (خارج `--surah`) **متطابقةٌ بايتاً** بين الأصل والمتبرَّع.
3. الناتجُ: آياتُ السورة < `--from` من الأصل، و≥ `--from` من المتبرَّع، **ونهايةُ الآية الأخيرة من الأصل تُمدّ إلى بدء أوّل آيةٍ متبرَّعة**
   (متّصلةً كما كانت) — ولا شيءَ غيرُ ذلك يتغيّر.
4. الحدودُ صاعدةٌ بلا تداخل، ومدّةُ كلّ آيةٍ > 0.
5. `engineBySurah[س]` و`transform` للمتبرَّع تبقى كما هي (فيلزم الإحصاءُ الشامل وحكمُ السماع كأنّه المتبرَّع نفسُه)،
   ويُضاف `transform.graft` بالأسباب. لا يمسّ حارساً ولا عتبة.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sys
import time
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                 # noqa: BLE001
        pass

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


def _sa(aid):
    s, a = str(aid).split(":")
    return int(s), int(a)


def graft(base, donor, base_sha, surah, first):
    """يُرجع (فهرساً جديداً، تقريراً) أو يرفع SystemExit بالسبب. دالةٌ نقيّةٌ للاختبار."""
    if (base.get("riwaya"), base.get("reciterId")) != (donor.get("riwaya"), donor.get("reciterId")):
        raise SystemExit("⛔ الفهرسان لقارئين أو روايتين مختلفتين")
    tr = donor.get("transform") if isinstance(donor.get("transform"), dict) else {}
    if tr.get("fromSha256") != base_sha:
        raise SystemExit(f"⛔ المتبرَّع غيرُ مشتقٍّ من الأصل (fromSha256={str(tr.get('fromSha256'))[:12]})")
    be, de = list(base.get("entries") or []), list(donor.get("entries") or [])
    if len(be) != len(de):
        raise SystemExit("⛔ عددُ المداخل يختلف بين الأصل والمتبرَّع")
    bm = {e["ayahId"]: e for e in be}
    out_entries, taken, kept = [], [], []
    for e in de:
        s, a = _sa(e["ayahId"])
        b = bm.get(e["ayahId"])
        if b is None:
            raise SystemExit(f"⛔ {e['ayahId']} ليست في الأصل")
        if s != surah:
            if e != b:
                raise SystemExit(f"⛔ {e['ayahId']}: تغيّرت في المتبرَّع وهي خارج السورة {surah}")
            out_entries.append(b)
        elif a >= first:
            out_entries.append(e)
            taken.append(a)
        else:
            out_entries.append(dict(b))
            kept.append(a)
    if not taken or not kept:
        raise SystemExit("⛔ المدى فارغٌ أو يشمل السورةَ كلَّها")
    mine = {_sa(e["ayahId"])[1]: e for e in out_entries if _sa(e["ayahId"])[0] == surah}
    last_kept = max(kept)
    if min(taken) != last_kept + 1:
        raise SystemExit("⛔ المدى غيرُ متّصل")
    # نهايةُ آخرِ آيةٍ من الأصل تُمدّ/تُقصّ إلى بدء أوّل آيةٍ متبرَّعة (متّصلةً)، لا غير.
    bl = bm[f"{surah}:{last_kept}"]
    if bl.get("endMs") is not None and int(bl["endMs"]) == int(bm[f"{surah}:{last_kept + 1}"]["startMs"]):
        mine[last_kept]["endMs"] = mine[min(taken)]["startMs"]
    prev = -1
    for a in sorted(mine):
        st, en = int(mine[a]["startMs"]), int(mine[a]["endMs"])
        if not (0 <= st < en) or st < prev:
            raise SystemExit(f"⛔ {surah}:{a}: حدودٌ غيرُ صاعدة ({st}→{en}، والسابقة تنتهي {prev})")
        prev = en
    out = dict(donor)
    out["entries"] = out_entries
    out["lowCount"] = sum(1 for e in out_entries if e.get("confBand") == "LOW")
    rep = {"surah": surah, "fromAyah": first, "keptFromBase": len(kept), "takenFromDonor": len(taken)}
    return out, rep


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--base", required=True)
    ap.add_argument("--base-sha", required=True)
    ap.add_argument("--donor", required=True)
    ap.add_argument("--donor-sha", required=True)
    ap.add_argument("--surah", type=int, required=True)
    ap.add_argument("--from", dest="first", type=int, required=True)
    ap.add_argument("--reason", required=True)
    ap.add_argument("--yes", action="store_true")
    a = ap.parse_args()
    import promote
    cl, bucket = promote.s3()

    def load(key, sha):
        body = cl.get_object(Bucket=bucket, Key=key)["Body"].read()
        full = hashlib.sha256(body).hexdigest()
        if not full.startswith(sha):
            raise SystemExit(f"⛔ البصمة لا تطابق {key}: الحيّة {full[:16]} والمطلوبة {sha}")
        return json.loads(gzip.decompress(body).decode("utf-8")), full

    base, bfull = load(a.base, a.base_sha)
    donor, _ = load(a.donor, a.donor_sha)
    out, rep = graft(base, donor, bfull, a.surah, a.first)
    t = dict(out.get("transform") or {})
    t["graft"] = {**rep, "baseKey": a.base, "baseSha256": bfull, "donorKey": a.donor,
                  "reason": a.reason, "at": int(time.time() * 1000), "by": "graft_surah_range"}
    out["transform"] = t
    blob = gzip.compress(json.dumps(out, ensure_ascii=False, separators=(",", ":")).encode("utf-8"), 9)
    new_sha = hashlib.sha256(blob).hexdigest()
    target = f"timings-staging/{out.get('riwaya')}/{out.get('reciterId')}.{new_sha[:8]}.jz"
    print(f"س{a.surah}: آياتٌ < {a.first} من الأصل ({rep['keptFromBase']}) و≥ {a.first} من المتبرَّع ({rep['takenFromDonor']})")
    print(f"إلى {target} ({len(blob)} بايت · بصمة {new_sha[:12]})")
    if not a.yes:
        print("(عرضٌ فقط — أضف --yes للرفع)")
        return
    cl.put_object(Bucket=bucket, Key=target, Body=blob, ContentType="application/gzip")
    got = cl.head_object(Bucket=bucket, Key=target)["ContentLength"]
    print(f"↑ رُفع · الدلو {got} · المحلّي {len(blob)} → {'✅' if got == len(blob) else '❌'}")


if __name__ == "__main__":
    main()
