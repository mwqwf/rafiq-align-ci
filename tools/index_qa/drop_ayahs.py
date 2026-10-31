#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""يحجب **آياتٍ غائبةً في وسط سورةٍ حاضرة** من فهرسٍ منشورٍ ويعلنها بسببها — بدل إسقاط السورة كلّها.

    python tools/index_qa/drop_ayahs.py --key timings/hafs/x.jz --sha 82151d14 \\
        --ayahs "79:15,79:17,79:18" --evidence ev.json --reason "…قياس…" \\
        --reason-user "تسجيلُ هذه السورة ينقصه بعضُ آياتها." --reason-code SOURCE_TRUNCATED --yes

⭐ **سببُه (أمرُ المالك 2026-10-31 · cmsg_01SnWBBbg8UvScqE3YMKdPHaAmmNARSqWMUt85wRaf6dSw):**
«إن كنتم ترون طريقة أفضل من الإسقاط فطبّقوه وصحّحوا القاعدة». كانت قاعدةُ 2026-10-02: البترُ في
أوّل السورة أو آخرها يُعلَن، وفي الوسط تُلغى السورةُ بأكملها. والجديد: تُحذف مداخلُ الآيات
الغائبة **وحدَها** (‏النصُّ الصوتيُّ لا يُحرَّف: آيةٌ بلا صوتٍ لها لا مدخلَ لها) وتُعلن بسببها.

**ما يفعله بالضبط** (‏ولا شيءَ غيره):
1. يتحقّق من بصمة المنشور، ويشترط أن تكون السورةُ في الأصل **تامّةَ المداخل**.
2. يحذف مداخلَ الآيات المسمّاة وحدَها. ⛔ **`startMs`/`endMs` لكلّ مدخلٍ باقٍ لا يُمسّ** (‏لا تُمَدّ الجارة).
3. يضيف المعرّفات إلى `missing.ids` معدودةً تحت `source_truncated`.
4. يكتب `transform.truncatedGaps[س] = {absent, reason, evidence}` و`op` يحمل `declare_gap:س` مع
   `reasonCode = SOURCE_TRUNCATED` و`reasonUser`، ويحمل إعلاناتِ الذيل الموروثة (‏`carried_declared_tails`).
5. يرفع إلى `timings-staging/{riwaya}/{id}.{sha8}.jz` — **ولا يمسّ المنشور**.

⛔ **حُرّاسُه** (‏وما لم يجتزها لا يُرفع شيء):
- لا أولى السورة ولا آخرتها (‏تلك بابُ الصدر/الذيل: `truncate_tail.py`).
- لا يُحجب أكثر من **ربع** آيات السورة، وإلا فالإسقاطُ الكامل (‏`drop_surah.py`).
- لكلّ آيةٍ دليلٌ في ملفّ `--evidence`: `{"79:15": {"method": "ctc_window|whisper", "detail": "نصّ قياس"}}`.
- `--reason-code` لا يقبل إلا `SOURCE_TRUNCATED` و`--reason-user` إلزاميٌّ بلا كلماتٍ إداريّة.
- الناتجُ يجتاز `promote.declared_truncated_gaps` قبل الرفع.
⚖️ **ولا يُعفي من شيء**: المرشّحُ يمرّ بعده ببوّابات الترقية كلّها.
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

_BANNED = ("إذن المالك", "أمر المالك", "بإذنٍ نصّيّ", "بإذن نصي", "المشرف", "المالك", "github-")
METHODS = ("ctc_window", "whisper")


def _key(aid: str):
    s, a = str(aid).split(":")
    return int(s), int(a)


def parse_ayahs(spec: str):
    """«79:15,79:17» ⇒ {79: [15, 17]} — ويُردّ المكرّر وما خرج عن المصحف."""
    import drop_surah
    counts = drop_surah.SURAH_AYAHS
    out: dict[int, list[int]] = {}
    seen = set()
    for item in [x for x in str(spec or "").replace("،", ",").replace(" ", ",").split(",") if x]:
        try:
            s, a = _key(item)
        except ValueError:
            raise SystemExit(f"⛔ --ayahs بصيغة سورة:آية مثل 79:15 لا {item!r}")
        if not 1 <= s <= len(counts) or not 1 <= a <= counts[s - 1]:
            raise SystemExit(f"⛔ آيةٌ خارج المصحف: {item}")
        if (s, a) in seen:
            raise SystemExit(f"⛔ آيةٌ مكرّرة: {item}")
        seen.add((s, a))
        out.setdefault(s, []).append(a)
    if not out:
        raise SystemExit("⛔ --ayahs فارغ")
    return {s: sorted(v) for s, v in out.items()}


def drop_ayahs(idx: dict, ayahs: dict, evidence: dict, *, reason: str, reason_user: str,
               reason_code: str, from_sha: str, from_key: str) -> dict:
    """يُعيد فهرساً جديداً حُجبت منه الآياتُ المسمّاة ومعلَنةً، أو يرفع SystemExit بالسبب."""
    import drop_surah
    if reason_code != "SOURCE_TRUNCATED":
        raise SystemExit("⛔ --reason-code لهذا الباب SOURCE_TRUNCATED وحدَه")
    if not (reason_user or "").strip():
        raise SystemExit("⛔ --reason-user إلزاميّ: التطبيقُ لا يعرض سببَ النقص بدونه")
    for w in _BANNED:
        if w in reason or w in reason_user:
            raise SystemExit(f"⛔ السببُ يحمل «{w}» — والحقلُ يُعرض للمستخدم")
    counts = drop_surah.SURAH_AYAHS_OF(idx)
    tr0 = idx.get("transform") if isinstance(idx.get("transform"), dict) else {}
    ents = list(idx.get("entries") or [])
    recs, gone = {}, set()
    for s, absent in sorted(ayahs.items()):
        n = counts[s - 1]
        if min(absent) < 2 or max(absent) > n - 1:
            raise SystemExit(f"⛔ س{s}: لا يُحجب أولُ السورة ولا آخرُها (‏2..{n - 1}) — ذاك بابُ truncate_tail")
        if len(absent) * 4 > n:
            raise SystemExit(f"⛔ س{s}: المحجوب {len(absent)} يتجاوز ربع آيات السورة ({n}) — الإسقاطُ الكامل")
        mine = sorted(_key(e["ayahId"])[1] for e in ents if _key(e["ayahId"])[0] == s)
        if mine != list(range(1, n + 1)):
            raise SystemExit(f"⛔ س{s} في الأصل ليست تامّة ({len(mine)}/{n}) — ليست حالةَ هذه الأداة")
        if (tr0.get("truncatedTail") or {}).get(str(s)) or (tr0.get("truncatedGaps") or {}).get(str(s)):
            raise SystemExit(f"⛔ س{s}: الأصلُ يعلن عليها ذيلاً أو حجباً — ابدأ من فهرسها قبل الإعلان")
        ev = {}
        for a in absent:
            rec = (evidence or {}).get(f"{s}:{a}")
            if (not isinstance(rec, dict) or rec.get("method") not in METHODS
                    or not str(rec.get("detail") or "").strip()):
                raise SystemExit(f"⛔ لا دليلَ قياسٍ للآية {s}:{a} (‏method من {METHODS} + detail)")
            ev[f"{s}:{a}"] = {"method": rec["method"], "detail": str(rec["detail"])}
        recs[str(s)] = {"absent": list(absent), "reason": "source_truncated", "evidence": ev}
        gone |= {f"{s}:{a}" for a in absent}

    kept = [e for e in ents if e["ayahId"] not in gone]
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
    touched = sorted(ayahs)
    tails, keep_decl = drop_surah.carried_declared_tails(idx, kept, set(touched), reason_code, reason_user)
    # إعلاناتُ حجبٍ وسطيٍّ موروثةٌ لسورٍ أخرى: تُحمل كما هي بشرط أن تبقى مداخلُها مطابقة.
    old_gaps = {k: v for k, v in (tr0.get("truncatedGaps") or {}).items()
                if int(k) not in touched and isinstance(v, dict)}
    for k, v in old_gaps.items():
        have = sorted(_key(e["ayahId"])[1] for e in kept if _key(e["ayahId"])[0] == int(k))
        want = [a for a in range(1, counts[int(k) - 1] + 1) if a not in set(v.get("absent") or [])]
        if have != want:
            raise SystemExit(f"⛔ س{k}: إعلانُ الحجب الموروث لا يطابق مداخلَها — لا يُحمل كذب")
    carried_gaps = sorted({int(k) for k in old_gaps})
    op = "declare_gap:" + ",".join(str(s) for s in touched)
    extra = sorted(set(keep_decl) | set(carried_gaps))
    if extra:
        op += "|declare_gap:" + ",".join(str(s) for s in extra)
    out["transform"] = {
        **({"truncatedTail": tails} if tails else {}),
        "truncatedGaps": {**old_gaps, **recs},
        "op": op,
        "fromSha256": from_sha,
        "fromKey": from_key,
        "droppedEntries": len(gone),
        "gapAyahs": len(gone),
        "reason": reason,
        "reasonUser": reason_user,
        "reasonCode": reason_code,
        "at": int(time.time() * 1000),
        "note": "آياتٌ غائبةٌ في وسط السورة حُجبت وأُعلنت بدليلٍ لكلٍّ؛ حدودُ كلّ مدخلٍ باقٍ لم تُمسّ.",
    }
    if len(kept) + miss["count"] != total:
        raise SystemExit(f"⛔ اختلال العقد: {len(kept)} + {miss['count']} ≠ {total}")
    orig = {e["ayahId"]: e for e in ents}
    if any(e != orig[e["ayahId"]] for e in kept):
        raise SystemExit("⛔ تغيّر مدخلٌ باقٍ (startMs/endMs أو غيرهما) — لا يجوز")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--key", required=True)
    ap.add_argument("--sha", required=True, help="بادئةُ بصمة المنشور (تحقّق)")
    ap.add_argument("--ayahs", required=True, help="«79:15,79:17,79:18»")
    ap.add_argument("--evidence", required=True, help="ملفّ JSON: دليلُ كلّ آية")
    ap.add_argument("--reason", required=True)
    ap.add_argument("--reason-user", required=True)
    ap.add_argument("--reason-code", required=True)
    ap.add_argument("--yes", action="store_true", help="ارفع إلى الاختبار (الافتراض عرض)")
    a = ap.parse_args()
    ayahs = parse_ayahs(a.ayahs)
    evidence = json.loads(Path(a.evidence).read_text(encoding="utf-8"))
    import promote
    cl, bucket = promote.s3()
    body = cl.get_object(Bucket=bucket, Key=a.key)["Body"].read()
    live = hashlib.sha256(body).hexdigest()
    if not live.startswith(a.sha):
        raise SystemExit(f"⛔ البصمة لا تطابق: الحيّة {live[:16]} والمطلوبة {a.sha}")
    idx = json.loads(gzip.decompress(body).decode("utf-8"))
    out = drop_ayahs(idx, ayahs, evidence, reason=a.reason, reason_user=a.reason_user,
                     reason_code=a.reason_code, from_sha=live, from_key=a.key)
    for s in ayahs:
        ok, why = promote.declared_truncated_gaps(out, s)
        if not ok:
            raise SystemExit(f"⛔ الناتجُ لا يجتاز declared_truncated_gaps (س{s}): {why}")
        print(f"declared_truncated_gaps س{s}: ✅ {why}")
    blob = gzip.compress(json.dumps(out, ensure_ascii=False, separators=(",", ":")).encode("utf-8"), 9)
    new_sha = hashlib.sha256(blob).hexdigest()
    target = f"timings-staging/{idx.get('riwaya')}/{idx.get('reciterId')}.{new_sha[:8]}.jz"
    print(f"من {a.key} ({live[:12]}) · حُجبت {out['transform']['droppedEntries']} آيةً")
    print(f"المداخل {len(idx['entries'])} ⇐ {len(out['entries'])} · الغياب ⇐ {out['missing']['count']}")
    print(f"إلى {target} ({len(blob)} بايت · بصمة {new_sha[:12]})")
    if not a.yes:
        print("(عرضٌ فقط — أضف --yes للرفع)")
        return
    cl.put_object(Bucket=bucket, Key=target, Body=blob, ContentType="application/gzip")
    got = cl.head_object(Bucket=bucket, Key=target)["ContentLength"]
    print(f"↑ رُفع · الدلو {got} · المحلّي {len(blob)} → {'✅' if got == len(blob) else '❌'}")


if __name__ == "__main__":
    main()
