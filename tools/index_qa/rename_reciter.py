#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""يُعيد تسمية قارئ فهرسٍ **بلا مساس بمحتواه** — حين يكون الصوت صحيحاً والاسم خطأ.

    python tools/index_qa/rename_reciter.py --key timings-staging/hafs/en.81e7fa6c.jz \
        --sha 81e7fa6c --to shaheen --reason "..." --yes

**الحادثة:** وصل `en.81e7fa6c` تامّاً 6236/6236 ومداخلُه كلُّها تشير إلى
`server16.mp3quran.net/shaheen/…`؛ و`en` ليس في كتالوج حفص. فالمحتوى فهرسُ
أحمد خليل شاهين، والاسمُ وحده خطأ (قرار المشرف github-f4: لا يُعاد حسابه).

**ما يفعله بالضبط:** يتحقّق من بصمة الأصل، ويبدّل `reciterId` **وحده**، ويثبت
أنّ المداخل لم تتغيّر بايتاً (‏`entriesSha256` قبل وبعد)، ويُمرّر النتيجة على
`catalog_gate` — فلا يُنشأ اسمٌ ثانٍ خطأ مكان الأول — ثمّ يرفع إلى الاختبار
بميتاداتا تقول **من أين جاء وبأيّ تحويل**.

⛔ **ولا يمسّ الأصل ولا يحذفه**: يبقى `en.81e7fa6c` شاهداً على الحادثة.
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
import promote                                                       # noqa: E402


def entries_sha(entries):
    """بصمةُ المداخل وحدها — البرهانُ على أنّ التسمية لم تمسّ المحتوى."""
    raw = json.dumps(entries, ensure_ascii=False, sort_keys=True,
                     separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--key", required=True)
    ap.add_argument("--sha", required=True, help="بصمةُ الأصل المتوقَّعة")
    ap.add_argument("--to", required=True, help="المعرّف الصحيح من الكتالوج")
    ap.add_argument("--reason", required=True)
    ap.add_argument("--yes", action="store_true")
    a = ap.parse_args()

    cl, bucket = promote.s3()
    got = cl.get_object(Bucket=bucket, Key=a.key)
    body = got["Body"].read()
    live = hashlib.sha256(body).hexdigest()
    if not live.startswith(a.sha.rstrip(".")):
        raise SystemExit(f"⛔ البصمة لا تطابق: الحيّة {live[:16]} والمطلوبة {a.sha}")
    idx = json.loads(gzip.decompress(body).decode("utf-8"))
    was = idx.get("reciterId")
    before = entries_sha(idx.get("entries") or [])

    out = dict(idx)
    out["reciterId"] = a.to
    after = entries_sha(out.get("entries") or [])
    if before != after:
        raise SystemExit("⛔ المداخل تغيّرت — وهذا ليس تسميةً")
    # **الحارس يُطبَّق على المنتَج لا على النيّة**: لو كان الاسم الجديد خطأً
    # آخر لَما مرّ من هنا.
    why = promote.catalog_gate(out, promote.catalog(cl, bucket))
    if why:
        raise SystemExit(f"⛔ الاسم الجديد لا يمرّ حارس الهويّة: {why}")
    out["transform"] = {
        "op": f"rename:{was}->{a.to}",
        "fromSha256": live,
        "fromKey": a.key,
        "entriesSha256": after,
        "reason": a.reason,
        "at": int(time.time() * 1000),
        "note": ("‏المداخل والصوت لم يتغيّرا بايتاً (‏`entriesSha256` واحدة قبل "
                 "وبعد)، فالحكمُ الصوتي على الأصل يصف هذه النسخة نفسها — "
                 "**ويبقى شرطُ نسبته إلى البصمة قائماً**: يُكتب حكمٌ على "
                 "البصمة الجديدة يستشهد بعيّنة الأصل، ولا تُورَّث البصمةُ ضمناً."),
    }
    blob = gzip.compress(json.dumps(out, ensure_ascii=False,
                                    separators=(",", ":")).encode("utf-8"), 9)
    new = hashlib.sha256(blob).hexdigest()
    target = f"timings-staging/{idx.get('riwaya')}/{a.to}.{new[:8]}.jz"
    meta = {k: v for k, v in (got.get("Metadata") or {}).items()
            if k in ("job", "execution", "region", "project", "startedat")}
    meta = {("parent" + k if k in ("job", "execution") else k): v
            for k, v in meta.items()}
    meta.update({"source": "rename-local", "transform": f"rename:{was}->{a.to}",
                 "parent": live[:8], "sha256-8": new[:8],
                 "surahs": str(len({e["ayahId"].split(":")[0]
                                    for e in out.get("entries") or []}))})
    print(f"من {a.key} ({live[:12]}) · {was} ⇒ {a.to}")
    print(f"المداخل {len(out.get('entries') or [])} · بصمةُ المداخل {after[:12]} "
          "(لم تتغيّر)")
    print(f"إلى {target} ({len(blob)} بايت · بصمة {new[:12]})")
    if not a.yes:
        print("(عرضٌ فقط — أضف --yes للرفع)")
        return
    cl.put_object(Bucket=bucket, Key=target, Body=blob,
                  ContentType="application/gzip", Metadata=meta)
    head = cl.head_object(Bucket=bucket, Key=target)
    print(f"↑ رُفع · الدلو {head['ContentLength']} · المحلّي {len(blob)} → "
          f"{'✅' if head['ContentLength'] == len(blob) else '❌'}")
    print("  ميتاداتا: " + json.dumps(head.get("Metadata"), ensure_ascii=False))


if __name__ == "__main__":
    main()
