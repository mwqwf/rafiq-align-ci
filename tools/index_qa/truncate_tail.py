#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ذيلُ سورةٍ **غيرُ متلوٍّ في ملفّها** يُحذف من فهرسٍ منشورٍ ويُعلَن غائباً — بلا محاذاةٍ جديدة.

    python tools/index_qa/truncate_tail.py --key timings/hafs/peshawa.jz --sha 82151d14 \\
        --surah 63 --keep 9 --absorb --reason "…قياس…" \\
        --reason-user "تسجيلُ هذه السورة ينقطع قبل آخر آيتين." --reason-code SOURCE_TRUNCATED

⭐ **سببُه (أمرُ المالك 2026-10-02):** «إن كان البترُ في أوّل السورة أو آخرها فلا بأس يُعلَن
ذلك». وبابُه القائمُ `ctc_splice.yml` بـ`truncated_tail` (‏`ctc_prefix_align.py`) يفترض أنّ
الملفّ ينقطع **في وسط** الآية N+1 فيمتصّ ما بعد N بالوعةً، ويردّ — بحقّ — ملفّاً لا صوتَ
فيه بعد N (‏حارسُه الثالث: «لا صوتَ بعد الآية N»). فالملفُّ الذي **ينتهي نظيفاً بعد الآية N**
(‏بيشاوا س63: الملفّ 182.07ث، و63:9 مسموعةٌ حتى 181.4ث، ولا يُسمع 63:10 ولا 63:11) لا بابَ
له هناك، والمنشورُ يضع الآيتين الغائبتين على صوت 63:9 — آياتٌ تُشغَّل بصوت غيرها.

**ما يفعله بالضبط** (‏ولا شيءَ غيره):
1. يقرأ الفهرسَ المنشور ويتحقّق من بصمته.
2. يحذف مداخلَ الآيات N+1..آخر السورة **وحدَها**، ويسجّلها في `missing` بسبب
   `source_truncated` — فالعقدُ (‏حاضر + غائب = المجموع) يبقى.
3. مع `--absorb` وحدَه: تمتدّ نهايةُ الآية N إلى نهاية آخر مدخلٍ محذوف — أي إلى حدٍّ
   **كان في الفهرس أصلاً** (‏لا يُخترع زمن)، وشرطُه أن تكون المداخلُ المحذوفة على ملفّ N
   نفسِه ومتّصلةً بعده. وهو قياسُ القائل: «ما بعد بدء N حتى نهاية المادّة صوتُ N».
   ⛔ **بدءُ كلّ آيةٍ منشورة لا يُمسّ بحرف.**
4. يكتب الترويسةَ التي يشترطها `promote.declared_truncated_tail` حرفاً:
   `transform.truncatedTail[س]` و`op = declare_gap:س` و`reasonCode = SOURCE_TRUNCATED`
   و`reasonUser`، ويرفع إلى `timings-staging/` — **ولا يمسّ المنشور**.

⛔ **حُرّاسُه** (‏وما لم يجتزها لا يُرفع شيء):
- مداخلُ السورة في الأصل **تامّةٌ** 1..آخرها (‏إن نقصت فليست حالتَه) و1 ≤ N < عددها.
- لا سورةَ غيرُها تتغيّر، ولا مدخلَ قبل N يتغيّر إلا نهايةُ N مع `--absorb`.
- `--reason-code` لا يقبل إلا `SOURCE_TRUNCATED`، و`--reason-user` إلزاميّ.
⚖️ **ولا يُعفي من شيء**: المرشّحُ يمرّ بعده بالبوّابات كلّها (‏بنية · مطالع · أربعة ملوح ·
heard_gate للسورة المعدّلة · تشخيص · full_audit) ثمّ `promote.py --allow-shrink` يسمّي الهدف.
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

_BANNED = ("إذن المالك", "أمر المالك", "المشرف", "المالك", "github-")


def _key(aid: str):
    s, a = str(aid).split(":")
    return int(s), int(a)


def surah_counts(idx):
    import drop_surah
    return drop_surah.SURAH_AYAHS_OF(idx)


def truncate_tail(idx: dict, surah: int, keep: int, *, absorb: bool, reason: str,
                  reason_user: str, reason_code: str, from_sha: str, from_key: str) -> dict:
    """يُعيد فهرساً جديداً ذيلُه N+1.. محذوفٌ ومعلَن، أو يرفع SystemExit بالسبب."""
    if reason_code != "SOURCE_TRUNCATED":
        raise SystemExit("⛔ --reason-code لهذا الباب SOURCE_TRUNCATED وحدَه")
    if not (reason_user or "").strip():
        raise SystemExit("⛔ --reason-user إلزاميّ: التطبيقُ لا يعرض سببَ النقص بدونه")
    for w in _BANNED:
        if w in reason or w in reason_user:
            raise SystemExit(f"⛔ السببُ يحمل «{w}» — والحقلُ يُعرض للمستخدم")
    counts = surah_counts(idx)
    if not 1 <= surah <= len(counts):
        raise SystemExit(f"⛔ سورةٌ خارج المصحف: {surah}")
    n = counts[surah - 1]
    if not 1 <= keep < n:
        raise SystemExit(f"⛔ --keep {keep} يجب أن يكون بين 1 و{n - 1} للسورة {surah}")
    ents = list(idx.get("entries") or [])
    mine = {_key(e["ayahId"])[1]: e for e in ents if _key(e["ayahId"])[0] == surah}
    if sorted(mine) != list(range(1, n + 1)):
        raise SystemExit(f"⛔ س{surah} في الأصل ليست تامّة ({len(mine)}/{n}) — ليست حالةَ هذه الأداة")
    tail = [mine[a] for a in range(keep + 1, n + 1)]
    last = mine[keep]
    new_last = dict(last)
    if absorb:
        ref = last.get("fileRef")
        if any(e.get("fileRef") != ref for e in tail):
            raise SystemExit("⛔ --absorb: المداخلُ المحذوفة على ملفٍّ غيرِ ملفّ الآية N")
        prev = last.get("endMs")
        for e in tail:
            if e.get("startMs") is None or prev is None or int(e["startMs"]) < int(prev) - 50:
                raise SystemExit("⛔ --absorb: المداخلُ المحذوفة ليست متّصلةً صاعدةً بعد N")
            prev = e.get("endMs")
        end = max(int(e["endMs"]) for e in tail)
        if end <= int(last["endMs"]):
            raise SystemExit("⛔ --absorb لا يمدّ شيئاً")
        new_last["endMs"] = end
    gone = {e["ayahId"] for e in tail}
    kept = [new_last if e is last else e for e in ents if e["ayahId"] not in gone]

    total = idx.get("ayahCount") or sum(counts)
    miss = dict(idx.get("missing") or {})
    ids = list(miss.get("ids") or [])
    if set(ids) & gone:
        raise SystemExit("⛔ وسمُ الاكتمال يعدّ آياتٍ حاضرةً غائبة — الأصلُ غيرُ متّسق")
    if len(ents) + int(miss.get("count") or 0) != total:
        raise SystemExit("⛔ الأصلُ نفسُه لا يحقّق العقد — لا يُبنى عليه")
    reasons = dict(miss.get("byReason") or {})
    reasons["source_truncated"] = int(reasons.get("source_truncated", 0)) + len(gone)
    miss.update({"count": int(miss.get("count") or 0) + len(gone), "byReason": reasons,
                 "ids": sorted(ids + sorted(gone), key=_key)})

    out = dict(idx)
    out["entries"] = kept
    out["missing"] = miss
    out["lowCount"] = sum(1 for e in kept if e.get("confBand") == "LOW")
    rec = {"published": keep, "absentFrom": keep + 1, "absentTo": n, "reason": "source_truncated",
           "tool": "truncate_tail", "absorbedIntoLast": bool(absorb),
           "lastEndMs": [int(last["endMs"]), int(new_last["endMs"])]}
    out["transform"] = {
        "truncatedTail": {str(surah): rec},
        "op": f"declare_gap:{surah}",
        "fromSha256": from_sha,
        "fromKey": from_key,
        "droppedEntries": len(gone),
        "gapAyahs": len(gone),
        "reason": reason,
        "reasonUser": reason_user,
        "reasonCode": reason_code,
        "at": int(time.time() * 1000),
        "note": "ذيلٌ غيرُ متلوٍّ في الملفّ حُذف وأُعلن؛ بدءُ كلّ آيةٍ منشورةٍ لم يتغيّر.",
    }
    if len(kept) + miss["count"] != total:
        raise SystemExit(f"⛔ اختلال العقد: {len(kept)} + {miss['count']} ≠ {total}")
    changed = [e["ayahId"] for e, o in zip(kept, [x for x in ents if x["ayahId"] not in gone])
               if e != o]
    if changed not in ([], [f"{surah}:{keep}"]) or (changed and not absorb):
        raise SystemExit(f"⛔ تغيّر ما لا يجوز: {changed[:5]}")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--key", required=True)
    ap.add_argument("--sha", required=True, help="بادئةُ بصمة المنشور (تحقّق)")
    ap.add_argument("--surah", type=int, required=True)
    ap.add_argument("--keep", type=int, required=True, help="N: آخرُ آيةٍ متلوّةٍ في الملفّ")
    ap.add_argument("--absorb", action="store_true",
                    help="تمتدّ نهايةُ N إلى نهاية آخر مدخلٍ محذوف (حدٌّ قائمٌ في الفهرس)")
    ap.add_argument("--reason", required=True)
    ap.add_argument("--reason-user", required=True)
    ap.add_argument("--reason-code", required=True)
    ap.add_argument("--yes", action="store_true", help="ارفع إلى الاختبار (الافتراض عرض)")
    a = ap.parse_args()
    import promote
    cl, bucket = promote.s3()
    body = cl.get_object(Bucket=bucket, Key=a.key)["Body"].read()
    live = hashlib.sha256(body).hexdigest()
    if not live.startswith(a.sha):
        raise SystemExit(f"⛔ البصمة لا تطابق: الحيّة {live[:16]} والمطلوبة {a.sha}")
    idx = json.loads(gzip.decompress(body).decode("utf-8"))
    out = truncate_tail(idx, a.surah, a.keep, absorb=a.absorb, reason=a.reason,
                        reason_user=a.reason_user, reason_code=a.reason_code,
                        from_sha=live, from_key=a.key)
    ok, why = promote.declared_truncated_tail(out, a.surah)
    if not ok:
        raise SystemExit(f"⛔ الناتجُ لا يجتاز declared_truncated_tail: {why}")
    blob = gzip.compress(json.dumps(out, ensure_ascii=False, separators=(",", ":")).encode("utf-8"), 9)
    new_sha = hashlib.sha256(blob).hexdigest()
    target = f"timings-staging/{idx.get('riwaya')}/{idx.get('reciterId')}.{new_sha[:8]}.jz"
    rec = out["transform"]["truncatedTail"][str(a.surah)]
    print(f"من {a.key} ({live[:12]}) · س{a.surah}: البادئة 1..{a.keep} · حُذف "
          f"{out['transform']['droppedEntries']} · نهاية {a.surah}:{a.keep} {rec['lastEndMs']}")
    print(f"المداخل {len(idx['entries'])} ⇐ {len(out['entries'])} · الغياب ⇐ {out['missing']['count']}")
    print(f"declared_truncated_tail: ✅ {why}")
    print(f"إلى {target} ({len(blob)} بايت · بصمة {new_sha[:12]})")
    if not a.yes:
        print("(عرضٌ فقط — أضف --yes للرفع)")
        return
    cl.put_object(Bucket=bucket, Key=target, Body=blob, ContentType="application/gzip")
    got = cl.head_object(Bucket=bucket, Key=target)["ContentLength"]
    print(f"↑ رُفع · الدلو {got} · المحلّي {len(blob)} → {'✅' if got == len(blob) else '❌'}")


if __name__ == "__main__":
    main()
