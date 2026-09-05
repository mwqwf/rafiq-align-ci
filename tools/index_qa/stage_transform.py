#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""يرفع **منتَجَ تحويلٍ** مصنوعاً خارج مسار الأسطول إلى الاختبار — ببرهانٍ لا بثقة.

    python tools/index_qa/stage_transform.py --file tools/tasmi_bench/work/fix_hawashi.jz \
        --parent timings/hafs/hawashi.jz --parent-sha 57958521e6f2 \
        --op "basmala_fix" --reason "..." --yes

**لماذا أداةٌ ثانية؟** لأن `stage_upload.py` يشترط شجرة بناء أسطول
(`batch_<rid>/s*.json`) و**منتَجُ تحويلٍ لا يملكها بحال** — فوقف github-8e عند
حارسه ولم يلتفّ عليه، وهو الصواب. والحلُّ مسارٌ ثانٍ **بحُرّاسٍ تخصّه**، لا
ثقبٌ في الأول.

**ما يتحقّق منه قبل الرفع (‏قرار github-f4):**

1. **الأصلُ منشورٌ فعلاً** في `timings/`، وبصمتُه هي المذكورة — فلا يُبنى
   مشتقٌّ على فهرسٍ لا نعرف عينه.
2. **عددُ المداخل مطابقٌ للأصل حرفاً** — فالتحويلُ **يزيح حدوداً ولا يحذف
   آيات**؛ واختلافُ العدد يعني أنّ شيئاً آخر جرى.
3. **‏`entriesSha256` مختلفةٌ عن الأصل** — وإلا فالملفّ **لم يتغيّر** وادّعاءُ
   الإصلاح باطل. (‏عكسُ شرط `rename_reciter` تماماً: هناك تُشترط المطابقة
   لأن التسمية لا تمسّ المحتوى، وهنا يُشترط الاختلاف لأن القصّ يمسّه.)
4. **حارسا الهويّة والبنية** (`catalog_gate` و`index_gate`) على المنتَج نفسه.

ثمّ يُكتب أثرُ التحويل في الترويسة (`transform`) بالبصمتين، وتُرفع النسخة إلى
`timings-staging/{riwaya}/{reciter}.{بصمة}.jz` بميتاداتا تقول من صنعها وعمّن.
⛔ **ولا تُرقّى بذلك**: تدخل الطابور مشتقّاً كأيّ مرشّح — فحصُ مطالعَ وعيّنةٌ
كاملة على بصمتها هي، ثمّ حكمُ البوابة.
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
from rename_reciter import entries_sha                               # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True, help="ملفّ المنتَج المحلّي (.jz)")
    ap.add_argument("--parent", required=True, help="مفتاح الأصل المنشور")
    ap.add_argument("--parent-sha", required=True)
    ap.add_argument("--op", required=True, help="اسمُ التحويل، مثل basmala_fix")
    ap.add_argument("--reason", required=True)
    ap.add_argument("--by", default="github-8e", help="صانعُ التحويل")
    ap.add_argument("--yes", action="store_true")
    a = ap.parse_args()

    cl, bucket = promote.s3()
    blob = Path(a.file).read_bytes()
    sha = hashlib.sha256(blob).hexdigest()
    idx = json.loads(gzip.decompress(blob).decode("utf-8"))

    pbody = cl.get_object(Bucket=bucket, Key=a.parent)["Body"].read()
    psha = hashlib.sha256(pbody).hexdigest()
    if not psha.startswith(a.parent_sha.rstrip(".")):
        raise SystemExit(f"⛔ الأصل المنشور بصمتُه {psha[:16]} لا {a.parent_sha}")
    pidx = json.loads(gzip.decompress(pbody).decode("utf-8"))

    n_new, n_old = len(idx.get("entries") or []), len(pidx.get("entries") or [])
    if n_new != n_old:
        raise SystemExit(f"⛔ المداخل {n_new} ≠ الأصل {n_old} — التحويل يزيح "
                         "حدوداً ولا يحذف آيات")
    e_new, e_old = entries_sha(idx.get("entries") or []), entries_sha(
        pidx.get("entries") or [])
    if e_new == e_old:
        raise SystemExit("⛔ المداخل لم تتغيّر — لا إصلاح هنا")
    for check, name in ((promote.index_gate(idx), "البنية"),
                        (promote.catalog_gate(idx, promote.catalog(cl, bucket)),
                         "الهويّة")):
        if check:
            raise SystemExit(f"⛔ حارس {name}: {check}")

    moved = sum(1 for x, y in zip(idx["entries"], pidx["entries"])
                if x.get("startMs") != y.get("startMs")
                or x.get("endMs") != y.get("endMs"))
    out = dict(idx)
    # ‏**`transform` قد يصل نصّاً** (كتبه github-8e سلسلةً) — يُحفظ نصُّه في
    # `opAsGiven` ولا يُطمس، ويُبنى القاموس فوقه.
    prior = idx.get("transform")
    base = dict(prior) if isinstance(prior, dict) else (
        {"opAsGiven": prior} if prior else {})
    out["transform"] = dict(base, **{
        "op": a.op, "fromSha256": psha, "fromKey": a.parent,
        "entriesSha256": e_new, "parentEntriesSha256": e_old,
        "movedEntries": moved, "reason": a.reason, "by": a.by,
        "at": int(time.time() * 1000),
        "note": ("‏عددُ المداخل مطابقٌ للأصل والحدودُ وحدها أُزيحت؛ ولا يُرقّى "
                 "بحكم الأصل: يدخل الطابور بفحص مطالعَ وعيّنةٍ على بصمته."),
    })
    packed = gzip.compress(json.dumps(out, ensure_ascii=False,
                                      separators=(",", ":")).encode("utf-8"), 9)
    new = hashlib.sha256(packed).hexdigest()
    target = (f"timings-staging/{idx.get('riwaya')}/"
              f"{idx.get('reciterId')}.{new[:8]}.jz")
    print(f"الأصل {a.parent} ({psha[:12]}) · المنتَج {Path(a.file).name} "
          f"({sha[:12]})")
    print(f"المداخل {n_new} = {n_old} ✅ · بصمةُ المداخل {e_old[:10]} ⇒ "
          f"{e_new[:10]} (مختلفة ✅) · حدودٌ أُزيحت {moved}")
    print(f"إلى {target} ({len(packed)} بايت · بصمة {new[:12]})")
    if not a.yes:
        print("(عرضٌ فقط — أضف --yes للرفع)")
        return
    cl.put_object(Bucket=bucket, Key=target, Body=packed,
                  ContentType="application/gzip",
                  Metadata={"source": "transform-local", "transform": a.op,
                            "parent": psha[:8], "sha256-8": new[:8],
                            "by": a.by, "premeta": sha[:8]})
    head = cl.head_object(Bucket=bucket, Key=target)
    print(f"↑ رُفع · الدلو {head['ContentLength']} · المحلّي {len(packed)} → "
          f"{'✅' if head['ContentLength'] == len(packed) else '❌'}")


if __name__ == "__main__":
    main()
