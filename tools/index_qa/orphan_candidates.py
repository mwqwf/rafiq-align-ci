#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""يكشف **المرشَّحَ اليتيم**: فهرسٌ في `timings-staging/` نجا الفحصَ البنيويَّ
ثمّ نُسي بلا بوّابةٍ صوتيّة — فلا هو رُقّي ولا هو رُدّ.

    python tools/index_qa/orphan_candidates.py [--min-age-hours 6] [--only hafs/]

⛔ **العطبُ الذي وُلدت منه هذه الأداة، مقيسٌ لا مفترَض (2026-09-20):**
`timings-staging/hafs/a_binaoun.3987d0e4.jz` رُفع 2026-09-15 و**نجا الفحصَ
البنيويَّ فعلاً** (6170/6236 · 114/114 · صقلُ v2.1)، ثمّ بقي **خمسةَ أيّامٍ**
بلا مطالعَ ولا ملحٍ واحد — بينما المنشورُ عند المستخدم فهرسُ جيلٍ أوّلَ مكسورٌ
بـ**2246/6236 مدخلاً** و109 سورةً دون 70٪. ⇒ **3924 آيةً كانت جاهزةً ومحجوبة.**

**ولماذا وقع؟** الفحصُ البنيويُّ يُدفع في آخر الدورة، فتموت الجلسةُ قبل جوابه،
**ولا حارسَ في الأسطول يسأل «أيُّ ناجٍ بلا بوّابة؟»**. والحلقاتُ الأخرى تسأل
أسئلةً أخرى: `bucket_watch` يسأل «ما الجديد؟» فلا يرى ما قَدُم، و`promote`
يسأل «مَن يستحقّ الترقيةَ الآن؟» فلا يشتكي ممّن لم يُقَس أصلاً، و`restore_loop`
يسأل «أيُّ آيةٍ تُسترجَع؟» ولا يرى فهرساً كاملاً ينتظر. ⇒ **صمتٌ بين ثلاثِ
حلقاتٍ، كلٌّ منها سليمة.**

⚠️ قراءةٌ محضة: لا يكتب في الدلو بايتاً، ولا يمسّ حارساً ولا عتبة، ولا يُطلق
تشغيلة. مخرجُه **قائمةُ عملٍ** تُقرأ ثمّ تُدفع بوّاباتُها يدويّاً.
⛔ **ولا يقول «رقِّ»**: نجاةُ البنية ليست إذناً بالنشر — الإذنُ مطالعٌ وأربعةُ
ملوحٍ ثمّ `promote.py` بحُرّاسه. هذه الأداةُ تكشف المنسيَّ لا تُجيزه.
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                 # noqa: BLE001
        pass

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import promote                                                       # noqa: E402

STAGING = "timings-staging/"
# `timings-staging/<رواية>/<قارئ>.<بصمة>.jz` — والبصمةُ ثمانيُ خاناتٍ ستّ عشريّة.
KEY_RE = re.compile(r"^timings-staging/(?P<riwaya>[^/]+)/(?P<rid>.+)\.(?P<sha8>[0-9a-f]{8})\.jz$")


def list_staging(cl, bucket, only=None):
    out = []
    for page in cl.get_paginator("list_objects_v2").paginate(
            Bucket=bucket, Prefix=STAGING):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if not key.endswith(".jz"):
                continue
            if only and f"/{only}" not in f"/{key[len(STAGING):]}":
                continue
            out.append((key, obj["LastModified"], obj["Size"]))
    out.sort(key=lambda r: r[1])
    return out


def published_keys(cl, bucket):
    """المنشورُ فعلاً **وزمنُه** — فاليتيمُ الذي رُقّي بعدُ ليس يتيماً.

    ⛔ الزمنُ لازمٌ لا زينة: مرشَّحٌ رُفع ثمّ نُشر للقارئ فهرسٌ **أحدثُ منه**
    ليس منسيّاً بل **متجاوَزاً**، والشكوى منه ضجيجٌ يُغرق الحقيقيَّ.
    """
    out = {}
    for page in cl.get_paginator("list_objects_v2").paginate(
            Bucket=bucket, Prefix="timings/"):
        for obj in page.get("Contents", []):
            if obj["Key"].endswith(".jz"):
                out[obj["Key"]] = obj["LastModified"]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-age-hours", type=float, default=6.0,
                    help="لا يُشتكى من مرشّحٍ أحدثَ من هذا — بوّابتُه قد تكون تعمل الآن")
    ap.add_argument("--only", default=None, help="بادئةُ روايةٍ أو اسمِ قارئ")
    ap.add_argument("--all", action="store_true",
                    help="أظهر المتجاوَزَ أيضاً (بصمةً سبقتها أحدثُ، أو سبقها نشرٌ)")
    a = ap.parse_args()

    cl, bucket = promote.s3()
    now = dt.datetime.now(dt.timezone.utc)

    reports = list(promote.bucket_reports(cl, bucket))
    # ⛔ الحكمُ على البصمة لا على الاسم: فهرسان لقارئٍ واحدٍ ببصمتين حكمان.
    # ⛔⛔ **صنفٌ ثانٍ من النسيان، قِيس 2026-09-20:** `run.py` يُخرج حقلاً ثالثاً
    #    اسمُه `decision` — «موقوف — قرارُ منتَجٍ مطلوب» — لا هو عطبٌ ولا هو
    #    إجازة، بل بابٌ يُعرض على المالك عمداً (حذفُ سورةٍ **بإعلانٍ وسبب**).
    #    **ولا يقرؤه `promote.py` ولا `triage.py`** ⇒ لا جردَ في الأسطول كلِّه
    #    يُظهر الموقوفين، فيركد المرشَّحُ السليمُ بلا أن يسأل عنه أحد.
    #    الشاهد: `nufais.64811f36` — **ثلاثةَ عشرَ ملحاً مستقلّاً بلا عطبٍ واحد**
    #    وموقوفٌ منذ 2026-09-05. ⇒ يُجرَد هنا في بابٍ مستقلّ.
    # ⚖️ ولا يُقترح تجاوزُه: الحارسُ يقول «هذا ينتظر قرارَك» ولا يقرّر.
    struct_sha, audio_sha, openers_sha, pending_sha = set(), {}, set(), {}
    for _name, rep in reports:
        sha = rep.get("sha256")
        if not sha:
            continue
        kind = str(rep.get("kind") or "").strip().lower()
        if kind == "structural":
            struct_sha.add(sha)
        elif kind == "openers":
            openers_sha.add(sha)
        verd = str(rep.get("verdict") or "")
        if verd.startswith("موقوف"):
            pending_sha.setdefault(sha, verd)
        if promote.has_audio_sample(rep):
            # ⛔⛔ **عطبٌ في هذا الحارس التقطه تناقضُ أداتين (2026-09-20):**
            #    كنتُ أعدّ الشهاداتِ بـ`source` — وهو `ci` لكلّ الملوح — فتنهار
            #    المجموعةُ إلى **واحد**، فيصيح الحارسُ «1/4» على مرشَّحٍ له
            #    خمسةَ عشرَ حكماً. الشاهد: `en.81e7fa6c` قال عنه `promote`
            #    «أحكامٌ صوتيّةٌ موجودة (15: ci+ci3+…+en1..en4+k1..k4)»
            #    وقال حارسي «ملوحٌ بعيّنة: 1/4». ⇒ **حين تتناقض أداتان فالحَكَمُ
            #    قياسٌ ثالثٌ من بياناتٍ تملكها** — وكان العطبُ في حارسي أنا.
            # ✅ والعدُّ الصحيحُ **بالملح**، وهو نصُّ `pooled_samples`: «شرطُ
            #    الاستقلال هو الملح لا المصدر — عيّنتان بملحٍ واحدٍ من آلتين
            #    تعيدان القياسَ نفسَه وتضاعفان الثقةَ بلا دليل».
            # ⚖️ وبذرةُ العيّنة أدقُّ من اسم الملح عند وجودها (D-172): اسمان
            #    مختلفان ببذرةٍ واحدةٍ إعادةُ قياسٍ لا شاهدان.
            sample = rep.get("sample") or {}
            ident = (sample.get("seed") or sample.get("seedSalt")
                     or rep.get("salt") or _name)
            audio_sha.setdefault(sha, set()).add(str(ident))

    pub = published_keys(cl, bucket)

    # ⛔⛔ **درسٌ من أوّل تشغيلٍ لهذه الأداة (2026-09-20): صاحت 449 مرّة.**
    #    وحارسٌ يشتكي من كلّ شيءٍ لا يُعمل به، كما أنّ حارساً لا يجد شيئاً ليس
    #    حارساً — **كلاهما يُقرأ صمتاً**. والسببُ أنّ المسرحَ يحتفظ بكلّ بصمةٍ
    #    جُرّبت، فأغلبُ الـ449 **متجاوَزٌ لا منسيّ**:
    #    (أ) بصمةٌ أقدمُ لقارئٍ له في المسرح بصمةٌ **أحدث** ⇒ العملُ انتقل عنها؛
    #    (ب) أو فهرسُ القارئ المنشورُ **أحدثُ من المرشَّح** ⇒ رُقّي بعده بغيره.
    #    ⇒ يُبقى لكلّ قارئٍ **أحدثُ بصمةٍ** وحدَها، ويُطرح ما سبقه النشر.
    #    ⚖️ ولا يُخفى شيءٌ بلا بيان: `--all` يُظهر الكلَّ، والعددُ المطروح يُطبع.
    staging = list_staging(cl, bucket, a.only)
    newest = {}
    for key, mtime, _size in staging:
        m = KEY_RE.match(key)
        if m:
            k = (m["riwaya"], m["rid"])
            if k not in newest or mtime > newest[k][1]:
                newest[k] = (key, mtime)

    rows, pending_rows, superseded_newer, superseded_pub = [], [], 0, 0
    for key, mtime, size in staging:
        m = KEY_RE.match(key)
        if not m:
            continue
        if not a.all:
            if newest.get((m["riwaya"], m["rid"]), (key,))[0] != key:
                superseded_newer += 1
                continue
            pub_t = pub.get(f"timings/{m['riwaya']}/{m['rid']}.jz")
            if pub_t is not None and pub_t > mtime:
                superseded_pub += 1
                continue
        age_h = (now - mtime).total_seconds() / 3600.0
        if age_h < a.min_age_hours:
            continue
        pub_key = f"timings/{m['riwaya']}/{m['rid']}.jz"
        sha8 = m["sha8"]
        # الربطُ بالبصمةِ الثمانيّةِ في المفتاح: أحكامُ `state/` تحمل البصمةَ كاملةً.
        matched = [s for s in struct_sha | set(audio_sha) | openers_sha
                   if s.startswith(sha8)]
        sha = matched[0] if matched else None
        n_audio = len(audio_sha.get(sha, ())) if sha else 0
        has_struct = bool(sha and sha in struct_sha)
        has_open = bool(sha and sha in openers_sha)
        if sha and sha in pending_sha:
            # ⛔ موقوفٌ على قرار — لا يُعَدّ «بوّابةً ناقصة»: بوّابتُه تمّت وحكمُه
            #    ليس عطباً. فبابُه مستقلٌّ كي لا يُخلط النداءان.
            pending_rows.append((key, age_h, n_audio, pending_sha[sha]))
        elif has_struct and n_audio < 4:
            rows.append((key, age_h, has_open, n_audio, pub_key in pub, size))

    skipped = superseded_newer + superseded_pub
    if skipped:
        print(f"ℹ️ طُرح من الشكوى {skipped} مرشَّحاً **متجاوَزاً لا منسيّاً**: "
              f"{superseded_newer} سبقتها بصمةٌ أحدثُ للقارئ نفسِه · "
              f"{superseded_pub} سبقها نشرٌ أحدثُ منها. (‏`--all` يُظهرها.)")
    if pending_rows:
        pending_rows.sort(key=lambda r: -r[1])
        print(f"⚖️ **موقوفون على قرارِ منتَج — بوّابتُهم تامّةٌ ولا عطبَ فيهم:** "
              f"{len(pending_rows)}")
        print("   (‏هذا نداءٌ على المالك لا على الأداة — ولا يُتجاوز بيدِ وكيل.)")
        for key, age_h, n_audio, verd in pending_rows:
            print(f"  ⚖️ {key}")
            print(f"      عمرُه {age_h:.0f} ساعة · ملوحٌ بعيّنة: {n_audio}")
            print(f"      {verd}")
        print()

    if not rows:
        if pending_rows:
            print("✅ ولا مرشَّحَ يتيماً بمعنى البوّابة الناقصة.")
            return 1
        print("✅ لا مرشَّحَ يتيماً: كلُّ ناجٍ بنيويّاً له بوّابةٌ صوتيّةٌ تامّة أو يعمل الآن.")
        return 0

    rows.sort(key=lambda r: -r[1])
    print(f"⚠️ مرشَّحون نجوا بنيويّاً وبوّابتُهم ناقصة: {len(rows)}")
    print("   (الأقدمُ أوّلاً — والقِدمُ وحدَه ليس حكماً على المادّة)")
    for key, age_h, has_open, n_audio, is_pub, size in rows:
        flag = "🔴" if age_h >= 24 else "⚠️"
        state = "منشورٌ له فهرسٌ سابق" if is_pub else "⛔ لا فهرسَ منشوراً لهذا القارئ"
        print(f"  {flag} {key}")
        print(f"      عمرُه {age_h:.0f} ساعة · مطالع: {'نعم' if has_open else 'لا'}"
              f" · ملوحٌ بعيّنة: {n_audio}/4 · {state}")
    print()
    print("⇒ الخطوةُ التالية لكلٍّ: `openers.yml` ثمّ أربعةُ `audio_qa.yml` بملوحٍ متمايزة،")
    print("  ثمّ `promote.py --only <المفتاح>` — ⛔ ولا ترقيةَ بنجاةِ البنية وحدَها.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
