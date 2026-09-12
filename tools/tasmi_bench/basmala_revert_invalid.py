#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ترشيحٌ حسابيّ لمشتقّات «إصلاح البسملة»: إعادةُ كلّ مدخلٍ صارت مدّتُه غير صالحة إلى قيم أصله.

**العلّة المقيسة (‏D-097):** أداةُ إصلاح البسملة كانت تُزيح `startMs` إلى الأمام
ولا تنظر إلى `endMs`. فحيث كانت الآيةُ الأولى قصيرةً أصلاً تجاوزت الإزاحةُ
النهايةَ، فوُلد مدخلٌ **مدّتُه سالبة أو صفر** (`endMs <= startMs`) — وهو **fatal**
يُسقط الفهرس كلَّه لا المدخلَ وحده.

**لماذا ترشيحٌ حسابيّ لا إعادةُ قياس؟** لأن `endMs` **مقيسةٌ من الصوت** — شهادةُ
محاذاةٍ وقعت. ودفعُها إلى الأمام لتستوعب بدايةً مُزاحة **اختلاقُ قياسٍ لم يقع**:
رقمٌ لا يقابله شيء في الملفّ الصوتي، يُلبَس ثوبَ الشهادة. والصوابُ الوحيد بلا
سماعٍ جديد هو **التراجع**: نُعيد المدخلَ المعطوب إلى **قيم أصله بالضبط** —
بدايةً ونهايةً — فيعود إلى حالٍ كانت مقيسةً قبل الإزاحة، ويبقى مطلعُه **بلا
إصلاحٍ مُعلَن** (وهذا أصدق من إصلاحٍ مخترَع). فالأداةُ **تُحاذي ولا تخترع**،
ولا تفتح صوتاً ولا whisper: الإزاحاتُ كلُّها محسوبةٌ سلفاً وموجودةٌ في المشتقّ
نفسه، فلا حاجة لإعادة القياس بحال.

**والقاعدةُ الوقائية للمستقبل (‏`MIN_REMAIN_MS`):** لا يُقصّ مطلعٌ إذا لم تبقَ
بعده 500م.ث على الأقل من مدّة المدخل؛ وما لم يُقصّ **يبقى بلا إصلاحٍ مُعلَناً**.
تُطبَّق هنا **كشفاً**: كلُّ مدخلٍ مُزاحٍ بقيت مدّتُه دون هذا الحدّ يُعلَن في
الجدول ولو لم يكن معطوباً، ولا يُمَسّ (‏الترشيح للمعطوب وحده).

⛔ لا تكتب فوق شيء في الدلو: المخرَج **ملفٌّ محلّي** يُرفع بـ`stage_transform.py`.

    python tools/tasmi_bench/basmala_revert_invalid.py \
        --parent timings-staging/hafs/kyat.c5ce5771.jz \
        --child  timings-staging/hafs/kyat.60d0a521.jz \
        --out    tools/tasmi_bench/work/kyat_revert.jz
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                          # noqa: BLE001
        pass

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT / "tools" / "index_qa"))
import promote                                                 # noqa: E402

MIN_REMAIN_MS = 500        # لا يُقصّ مطلعٌ إن لم تبقَ بعده هذه المدّة


def fetch(cl, bucket: str, key: str):
    """يقرأ كائن `.jz` من الدلو ⇒ (‏بصمةُ البايتات، الفهرس)."""
    blob = cl.get_object(Bucket=bucket, Key=key)["Body"].read()
    idx = json.loads(gzip.decompress(blob).decode("utf-8"))
    return hashlib.sha256(blob).hexdigest(), idx


def dur(e) -> int:
    return int(e.get("endMs", 0)) - int(e.get("startMs", 0))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--parent", required=True, help="مفتاح الأصل في الدلو")
    ap.add_argument("--child", required=True, help="مفتاح المشتقّ في الدلو")
    ap.add_argument("--out", required=True, help="ملفّ المخرَج المحلّي (.jz)")
    a = ap.parse_args()

    cl, bucket = promote.s3()
    psha, pidx = fetch(cl, bucket, a.parent)
    csha, cidx = fetch(cl, bucket, a.child)
    pe, ce = pidx.get("entries") or [], cidx.get("entries") or []

    if len(pe) != len(ce):
        raise SystemExit(f"⛔ عددُ المداخل مختلف: الأصل {len(pe)} · المشتقّ "
                         f"{len(ce)} — هذا ليس مشتقّ إزاحةٍ فتوقّف")
    for p, c in zip(pe, ce):
        if p.get("ayahId") != c.get("ayahId"):
            raise SystemExit(f"⛔ ترتيب المداخل مختلف عند {p.get('ayahId')} ≠ "
                             f"{c.get('ayahId')}")

    out = json.loads(json.dumps(cidx))       # نسخةٌ عميقة لا تمسّ المقروء
    oe = out["entries"]
    rows, reverted, thin = [], [], []
    for i, (p, c) in enumerate(zip(pe, ce)):
        moved = (p.get("startMs") != c.get("startMs")
                 or p.get("endMs") != c.get("endMs"))
        broken = dur(c) <= 0
        if broken:
            oe[i]["startMs"], oe[i]["endMs"] = p["startMs"], p["endMs"]
            # ⛔ **والعلامةُ تُرفع مع القيم** — وإلا بقي المدخلُ يدّعي قصّاً لم
            #    يقع. وقع ذلك فعلاً ووصل **الإنتاج**: `kyat` 55:1 و103:1 في
            #    `timings/` تحملان `basmalaTrimmed: true` و`startMs = 0`
            #    والبسملةُ كاملةٌ مسموعة. **علامةٌ كاذبةٌ لا يمسكها حارس**: لا
            #    المدّةُ تشكو ولا التغطيةُ ولا فحصُ المطالع، ومن قرأ الفهرسَ
            #    حسِب المطلعَ مُصلَحاً. ⇒ **الوسمُ يتبع الأثر؛ فإن رُدّ الأثرُ
            #    رُفع الوسم.**
            for _f in ("basmalaTrimmed", "basmalaDeltaMs", "basmalaRung"):
                oe[i].pop(_f, None)
            reverted.append(c["ayahId"])
            act = "أُعيد إلى الأصل (‏ورُفعت علامةُ القصّ)"
        elif moved and dur(c) < MIN_REMAIN_MS:
            thin.append(c["ayahId"])
            act = f"مُزاحٌ ومدّتُه {dur(c)}م.ث < {MIN_REMAIN_MS} (كشفٌ فقط)"
        elif moved:
            act = "مُزاحٌ سليم — لا مساس"
        else:
            continue
        rows.append((c["ayahId"], p.get("startMs"), p.get("endMs"),
                     c.get("startMs"), c.get("endMs"), act))

    w = max([len(r[0]) for r in rows] + [5])
    print(f"الأصل {a.parent} ({psha[:12]}) · المشتقّ {a.child} ({csha[:12]})")
    print(f"المداخل {len(ce)} = {len(pe)} ✅")
    print(f"{'الآية'.ljust(w)}  {'الأصل':>17}  {'المشتقّ':>17}  ما فُعل")
    for aid, ps, pen, cs, cen, act in rows:
        print(f"{aid.ljust(w)}  {ps:>7}→{pen:<9}  {cs:>7}→{cen:<9}  {act}")

    left = [e["ayahId"] for e in oe if dur(e) <= 0]
    if left:
        raise SystemExit(f"⛔ بقي بعد الترشيح {len(left)} مدخلاً معطوباً: "
                         f"{left[:20]} — لا تُخرج ملفاً")
    if not reverted:
        raise SystemExit("⛔ لا مدخلَ معطوباً في هذا المشتقّ — لا شيء يُرشَّح")

    packed = gzip.compress(json.dumps(out, ensure_ascii=False,
                                      separators=(",", ":")).encode("utf-8"), 9)
    dst = Path(a.out)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(packed)
    print(f"\nأُعيد {len(reverted)} مدخلاً: {', '.join(reverted)}")
    if thin:
        print(f"⚠️ مُزاحٌ رقيقٌ (<{MIN_REMAIN_MS}م.ث) بلا مساس: {', '.join(thin)}")
    print(f"صفرُ مدخلٍ بمدّةٍ غير صالحة ✅ · إلى {dst} ({len(packed)} بايت · "
          f"بصمة {hashlib.sha256(packed).hexdigest()[:12]})")


if __name__ == "__main__":
    main()
