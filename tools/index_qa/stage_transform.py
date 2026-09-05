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
import re
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


AYAH_COUNTS = [7, 286, 200, 176, 120, 165, 206, 75, 129, 109, 123, 111, 43, 52,
               99, 128, 111, 110, 98, 135, 112, 78, 118, 64, 77, 227, 93, 88, 69,
               60, 34, 30, 73, 54, 45, 83, 182, 88, 75, 85, 54, 53, 89, 59, 37, 35,
               38, 29, 18, 45, 60, 49, 62, 55, 78, 96, 29, 22, 24, 13, 14, 11, 11,
               18, 12, 12, 30, 52, 52, 44, 28, 28, 20, 56, 40, 31, 50, 40, 46, 42,
               29, 19, 36, 25, 22, 17, 19, 26, 30, 20, 15, 21, 11, 8, 8, 19, 5, 8,
               8, 11, 11, 8, 3, 9, 5, 4, 7, 3, 6, 3, 5, 4, 5, 6]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True, help="ملفّ المنتَج المحلّي (.jz)")
    ap.add_argument("--parent", required=True,
                    help="مفتاحُ الأصل: منشورٌ في timings/ أو مرشَّحٌ في "
                         "timings-staging/ لقارئه نفسِه")
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

    # ⛔ **الأصلُ من الاختبار مقبولٌ لقارئه نفسِه** (‏حكم المشرف 2026-09-05،
    #    كسرُ الحلقة المغلقة): كان الأصلُ يجب أن يكون منشوراً، فانحبس ثلاثةُ
    #    فهارسَ أُعيد بناؤها (99.7–99.97%) خلف منشورٍ تغطيتُه 45–86%: تمريرةُ
    #    البسملة لا تقصّ (‏امتناعٌ صواب)، و`realign_surah` على المنشور يُخرج
    #    مختلطَ الجيل فيُردّ، والبصمةُ الجيّدة لا تُرقّى لبسملةٍ واحدة. فكلُّ
    #    بابٍ مغلقٌ بحارسٍ محقّ. ⇒ يُفتح بابٌ **بالحُرّاس نفسِها كلِّها**، لا
    #    بتجاوزٍ ولا بنشرِ عيبٍ ولو ساعات (‏الموثوقيةُ فوق العدد، أمر المالك).
    if a.parent.startswith("timings-staging/"):
        # والحارسُ هنا: الرواية والمعرّف يُستخرجان من المفتاح ويُطابَقان
        # بترويسة المنتَج — فلا يُرقّع فهرسُ قارئٍ بمخرَجِ قارئٍ آخر.
        parts = a.parent.split("/")
        if len(parts) != 3:
            raise SystemExit(f"⛔ مفتاحُ اختبارٍ غيرُ سويّ: {a.parent}")
        p_riw, p_rid = parts[1], parts[2].split(".")[0]
        if idx.get("riwaya") != p_riw or idx.get("reciterId") != p_rid:
            raise SystemExit(f"⛔ المنتَج يصف {idx.get('riwaya')}/{idx.get('reciterId')} "
                             f"والأصلُ {p_riw}/{p_rid} — لا يُرقّع قارئٌ بمخرَجِ آخر")
    elif not a.parent.startswith("timings/"):
        raise SystemExit(f"⛔ الأصلُ ليس منشوراً ولا في الاختبار: {a.parent}")
    pbody = cl.get_object(Bucket=bucket, Key=a.parent)["Body"].read()
    psha = hashlib.sha256(pbody).hexdigest()
    if not psha.startswith(a.parent_sha.rstrip(".")):
        raise SystemExit(f"⛔ الأصل بصمتُه {psha[:16]} لا {a.parent_sha}")
    pidx = json.loads(gzip.decompress(pbody).decode("utf-8"))

    n_new, n_old = len(idx.get("entries") or []), len(pidx.get("entries") or [])
    # ⛔ **استثناءُ `realign_surah` وحدَه (‏قرار المشرف github-10، 2026-09-05):**
    #    القاعدةُ «التحويلُ يزيح حدوداً ولا يحذف آيات» بُنيت لتحويلاتٍ تُعدّل
    #    الحدود (‏`basmala_fix`)، و**إعادةُ محاذاة سورةٍ تُعيد مداخلَ غائبة** —
    #    فاختلافُ العدد فيها **هو المقصود** لا علامةُ خللٍ خفيّ.
    #    ⛔ ولا يُرفع الحارسُ بل **يُشدَّد**: بدل «تساوٍ» يُشترط أن يكون الفرقُ
    #    **مطابقاً حسابياً** لعدد آي السور المسمّاة في `--op`، وألّا يمسّ
    #    التحويلُ مدخلاً خارجها. فمن أعاد سورةً وحذف أخرى صامتاً يُردّ هنا.
    realigned = []
    _m = re.match(r"^realign_surah:([\d,\s]+)$", a.op.strip())
    if _m:
        realigned = sorted({int(x) for x in re.findall(r"\d+", _m.group(1))})
    if realigned:
        have_old = {e["ayahId"] for e in (pidx.get("entries") or [])}
        have_new = {e["ayahId"] for e in (idx.get("entries") or [])}
        outside_old = {i for i in have_old if int(i.split(":")[0]) not in realigned}
        outside_new = {i for i in have_new if int(i.split(":")[0]) not in realigned}
        if outside_old != outside_new:
            raise SystemExit("⛔ التحويل مسّ مداخلَ خارج السور المسمّاة — يُردّ")
        want = sum(AYAH_COUNTS[s - 1] for s in realigned)
        got = len({i for i in have_new if int(i.split(":")[0]) in realigned})
        if got != want:
            raise SystemExit(f"⛔ السورُ المُعادة {realigned}: مداخلُها {got} "
                             f"والرواية {want} — لا يُرفع ناقص")
        print(f"  ✔ إعادةُ محاذاة {realigned}: {n_old} ⇐ {n_new} مدخلاً "
              f"(‏+{n_new - n_old})، وما خارجها لم يُمسّ")
    elif n_new != n_old:
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
