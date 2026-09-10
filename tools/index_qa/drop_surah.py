#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""يُسقط سورةً من فهرس توقيتات ويكتب نسخةً جديدة إلى الاختبار — بأثرٍ موثَّق.

    python tools/index_qa/drop_surah.py --key timings/qalun/akri_qalun.jz \\
        --sha 0cfa027e... --surah 24 --reason "بترٌ مصدري: نسبة المدة 0.39"

**لماذا يوجد هذا التحويل؟** لأنّ **توقيتاً تامَّ الظاهر على صوتٍ ناقص لا
يُشحن** (قرار المشرف github-f4): سورةُ الفرقان في `husary_douri` وسورة النور
في `akri_qalun` مفهرستان كاملتين على ملفّين ينقصهما ثلث الصوت وأكثر، فيسمع
الحافظ آيةً ويقرأ غيرها **بلا خطأ ظاهر**. والعلاج ليس إعادة فهرسة (ستُنتج
توقيتاً «ناجحاً» على البتر نفسه) بل **إسقاط السورة حتى يُصلح مصدرها**.

## ما يفعله بالضبط

1. يقرأ الفهرس من الدلو ويتحقّق أنّ بصمته **هي المطلوبة** — فلا يُحوَّل شيءٌ
   لا نعرف عينه.
2. يحذف **كل** مداخل السورة، ويسجّلها في `missing` بسبب **`source_truncated`**
   مع معرّفاتها وعددها — فالغياب **يُعلن بسببه** ولا يُبتلع في العدّ.
3. يكتب في الترويسة أثرَ التحويل: `transform` بالبصمة **الأصلية** والسورة
   والسبب والزمن — فمن يقرأ النسخة الجديدة يعرف **من أين جاءت ولماذا**.
4. يرفعها إلى `timings-staging/{riwaya}/{reciter}.{بصمةٌ جديدة}.jz` —
   **ولا يمسّ الأصل بحال**، فالاستبدال لا يقع إلا بترقيةٍ من البوابة بحكم.

⛔ **ولا يعيد حساب ما لم يُعد قياسه:** `refineStats` و`medTargeted` و`vad`
تبقى كما هي لأنها تصف **البناء** لا المجموعة المشحونة، ويقول ذلك `transform`
صراحةً. أمّا ما يتغيّر بالحذف حقاً (‏`entries` و`lowCount` و`missing`) فيُعاد
حسابه من المداخل الباقية.
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

AYAHS = 6236


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--key", required=True, help="مفتاح الفهرس على الدلو")
    ap.add_argument("--sha", required=True, help="بصمته المتوقَّعة (تحقّقٌ لا زينة)")
    ap.add_argument("--surah", required=True,
                    help="سورةٌ أو أكثر مفصولةً بفاصلة — تُسقط **معاً** في "
                         "تحويلٍ واحد لا في تحويلين متسلسلين، فالأثر يبقى "
                         "بصمةً واحدة عن الأصل لا سلسلةً يصعب تتبّعها")
    ap.add_argument("--reason", required=True,
                    help="السجلُّ الكامل — للمشرف والمراجعة، لا للمستخدم")
    # ⛔ **السببُ المعروضُ غيرُ السبب المسجَّل** (‏قياسُ جلسة الواجهة 2026-09-08):
    #    كتبتُ سجلّاً من ثلاثمئة حرفٍ فيه «−80.8 د.ب» و«server16» و«441 عنصراً»
    #    ثم عُرض على قارئٍ في شاشة 320dp، **فدفع الدعوةَ وزرَّها خارج الشاشة**
    #    فقرأ لوماً طويلاً بلا مخرجٍ يراه — وهو نقيضُ غرض البطاقة.
    #    ⇒ **حقلان لا واحد**: `reason` سجلٌّ كامل يبقى كما هو، و`reasonUser`
    #    جملةٌ واحدةٌ للقارئ العاديّ.
    ap.add_argument("--reason-user",
                    help="جملةٌ واحدةٌ تُعرض للمستخدم (‏دون 120 حرفاً)")
    # ⛔ **ورمزٌ يُترجَم** — والنصُّ وحدَه لا يكفي: مَن يقرأ بالسواحيلية كان
    #    يرى عنواناً بلغته وسبباً بالعربية. فالرمزُ يُخرّط في التطبيق إلى نصٍّ
    #    مترجَم، ويبقى `reasonUser` احتياطاً حين لا يعرف التطبيقُ الرمز.
    ap.add_argument("--reason-code",
                    choices=["NO_PUBLISHED_RECORDING", "SOURCE_TRUNCATED",
                             "SOURCE_CORRUPT", "OTHER"],
                    help="رمزٌ ثابتٌ يُترجمه التطبيق")
    ap.add_argument("--yes", action="store_true", help="ارفع (الافتراض عرضٌ فقط)")
    ap.add_argument("--declare-absent", action="store_true",
                    help="السورةُ غائبةٌ سلفاً — يُعلَن غيابُها بسببه بلا حذفِ شيء")
    # ⛔⛔ **نقصٌ جزئيّ داخل سورةٍ تعمل** (2026-09-09): `--declare-absent` لا
    #    يصلح له، وقد كاد يكلّفني **154 آيةً عاملة** حين أجريتُه جافّاً على
    #    `mukhtar_haj` [20,41] — فالرايةُ تعني «لا تحذف إن لم يكن ثمّة ما
    #    يُحذف»، فإن وُجدت مداخلُ حذفتها. والحالةُ الشائعة أنّ المصدر نشر
    #    السورةَ **ناقصةَ الذيل**: 102 من 135 في طه، و149 من 165 في الأنعام.
    #    ⇒ فبيانُ الغياب كان ثمنُه إسقاطَ ما يعمل، **وذلك ينقض المقصود**.
    # ✅ والحلّ: الآياتُ الغائبةُ **محسوبةٌ سلفاً** في `missing.ids` تحت
    #    `unknown` — فلا تحتاج قائمةً جديدة، إنما تحتاج أن يُسمّى سببُها.
    #    فهذا الوضعُ **يُصنّف ولا يحذف**: صفرُ مداخل تُمَسّ، والعقدُ لا يتغيّر.
    ap.add_argument("--declare-gap", action="store_true",
                    help="السورةُ تعمل وبعضُ آياتها غائبٌ — يُسمّى سببُ النقص "
                         "بلا حذفِ مدخلٍ واحد")
    a = ap.parse_args()
    if a.declare_gap and a.declare_absent:
        raise SystemExit("⛔ --declare-gap و--declare-absent وضعان متناقضان: "
                         "الأوّلُ لسورةٍ تعمل وينقصها بعضُ آياتها، والثاني "
                         "لسورةٍ لا مدخلَ لها. فاختر ما يصفه القياس.")

    # ⛔⛔ **حقلُ `reason` يُشحن ويُعرض للمستخدم** (‏وراء «التفاصيل» في التطبيق)
    #    — فلا يُكتب فيه شأنٌ داخليّ. كتبتُ فيه «إذن المالك النصّي» ونصَّ كلامه
    #    فظهر ذلك في تطبيقٍ يقرأه الناس (‏أمر المالك 2026-09-08: «هذا لا داعي له
    #    وليس موضع شيء كهذا»). **والسجلُّ الإداريّ موضعُه المستودع**
    #    (`docs/qa/DROPPED_SURAHS.md`) لا ترويسةُ فهرسٍ منشور.
    #    ⇒ يُردّ كلُّ نصٍّ يحمل أثرَ حوكمةٍ داخلية، ويُقال للكاتب أين يضعه.
    _BANNED = ("إذن المالك", "أمر المالك", "بإذنٍ نصّيّ", "بإذن نصي", "المشرف",
               "D-186", "D-220", "D-098", "D-183", "github-", "المالك")
    for _word in _BANNED:
        for _field, _name in ((a.reason, "--reason"),
                              (a.reason_user or "", "--reason-user")):
            if _word in _field:
                raise SystemExit(
                    f"⛔ {_name} يحمل «{_word}» — وهذا الحقلُ **يُعرض للمستخدم** "
                    f"في التطبيق. اكتب فيه ما يهمّ القارئَ (‏ما حدث ولماذا لا "
                    f"يجد الصوت)، وضع الإذنَ والقرارَ الإداريَّ في "
                    f"docs/qa/DROPPED_SURAHS.md.")

    cl, bucket = promote.s3()
    body = cl.get_object(Bucket=bucket, Key=a.key)["Body"].read()
    live = hashlib.sha256(body).hexdigest()
    if not live.startswith(a.sha.rstrip(".")):
        raise SystemExit(f"⛔ البصمة لا تطابق: الحيّة {live[:16]}… والمطلوبة {a.sha}")
    idx = json.loads(gzip.decompress(body).decode("utf-8"))

    surahs = [int(x) for x in str(a.surah).replace("،", ",").split(",") if x.strip()]
    prefixes = tuple(f"{n}:" for n in surahs)
    dropped = [e for e in idx["entries"] if e["ayahId"].startswith(prefixes)]
    # ⛔ **وضعُ التصنيف لا الحذف**: `--declare-gap` **لا يُسقط مدخلاً**، فقائمةُ
    #    المحذوف تبقى فارغةً عمداً ويمرّ الفهرسُ كما هو. وشرطُه أن تكون السورةُ
    #    **حاضرةً وناقصةً معاً** — فحاضرةٌ تامّةٌ لا نقصَ فيها يُعلَن، وغائبةٌ
    #    كلُّها بابُها `--declare-absent`. والخلطُ بينهما يعرض على المستخدم
    #    وصفاً لا يطابق ما يراه، وذاك أسوأُ من الصمت.
    if a.declare_gap:
        if not dropped:
            raise SystemExit(
                f"⛔ السور {surahs} لا مدخلَ لها أصلاً — وهذا بابُ "
                f"--declare-absent لا --declare-gap.")
        dropped = []
    elif not dropped and not a.declare_absent:
        raise SystemExit(f"⛔ لا مداخل للسور {surahs} في هذا الفهرس "
                         f"— وإن كان غيابُها هو المقصود فأعلنه بـ--declare-absent")
    if not dropped and not a.declare_gap:
        # ⛔ **إعلانُ غيابٍ قائم — لا حذفُ شيء** (2026-09-08، بإذن المالك النصّيّ):
        #    سورةٌ غائبةٌ أصلاً يردّها الحارسُ «سورٌ غائبةٌ كلياً» فيحجب القارئَ
        #    كلَّه أبداً. والحجبُ صحيحٌ ما دام الغيابُ **صامتاً**؛ فإن ثبت أنّ
        #    الصوتَ لا وجودَ له وأُذن نصّاً، فالصوابُ أن يُعلَن الغيابُ بسببه
        #    لا أن يُترك بلا بيان. **والإعلانُ لا يحذف بايتاً** — إنما يكتب في
        #    التحويل `drop_surah:<n>` وسببَه، فيتحوّل الغيابُ من «عطبٍ مجهول»
        #    إلى «قرارِ منتَجٍ يُعرض على المستخدم».
        print(f"ℹ️ السورُ {surahs} غائبةٌ سلفاً — يُكتب إعلانُ الغياب وسببُه، "
              f"ولا يُحذف مدخلٌ واحد.")
    # ⛔ **وفي وضع التصنيف يبقى كلُّ مدخل**: حسبتُ `kept` أوّلاً باستثناء السور
    #    المذكورة، فسقط 154 مدخلاً في وضعٍ لا يحذف شيئاً — **وكشفه حارسُ العقد**
    #    (‏6034 + 48 ≠ 6236) لا عينِي. فالحارسُ الذي يجمع الحاضرَ والغائبَ
    #    ويقابله بالمجموع هو الذي منع فهرساً مبتوراً من الرفع.
    kept = (list(idx["entries"]) if a.declare_gap
            else [e for e in idx["entries"] if not e["ayahId"].startswith(prefixes)])

    # **الفهرس القديم بلا وسم اكتمال:** يُبنى الوسم من المداخل نفسها، والغياب
    # الذي لا نعرف سببه يُسمّى **`unknown` ولا يُخترع له سبب** — فالتحويل يصف
    # ما فعل، ولا يدّعي علماً بما لم يقسه. (‏وقع فعلاً: `3siri` و`abkar` بُنيا
    # قبل الوسم، فكان العقد يختلّ: 2038 + 16 ≠ 6236.)
    miss = dict(idx.get("missing") or {})
    if not miss.get("byReason"):
        present = {e["ayahId"] for e in idx["entries"]}
        total = AYAH_TOTAL_OF(idx)
        every = []
        counts = SURAH_AYAHS_OF(idx)
        for sn, n in enumerate(counts, start=1):
            every += [f"{sn}:{i}" for i in range(1, n + 1)]
        absent = [x for x in every if x not in present]
        miss = {"count": len(absent), "byReason": {"unknown": len(absent)},
                "ids": absent,
                "note": "الفهرس بُني قبل وسم الاكتمال، فسببُ غيابه غير مقيس"}
        assert len(present) + len(absent) == total
    reasons = dict(miss.get("byReason") or {})
    reasons["source_truncated"] = reasons.get("source_truncated", 0) + len(dropped)
    # ✅ **التصنيف**: الآياتُ الغائبةُ من هذه السور محسوبةٌ سلفاً في `ids` تحت
    #    `unknown` — فيُنقل عددُها إلى `source_truncated` **ولا يُضاف مدخلٌ ولا
    #    يُحذف**، فالعقدُ (‏حاضر + غائب = المجموع) لا يتغيّر بحرف.
    gap_ids = []
    if a.declare_gap:
        _pfx = tuple(f"{n}:" for n in surahs)
        gap_ids = [i for i in (miss.get("ids") or []) if str(i).startswith(_pfx)]
        if not gap_ids:
            raise SystemExit(
                f"⛔ السور {surahs} حاضرةٌ **تامّةٌ** لا نقصَ فيها — فلا غيابَ "
                f"يُعلَن. (‏والإعلانُ على تامٍّ يعرض للمستخدم وصفاً لا يطابق "
                f"ما يراه.)")
        # ⛔ **ولا يُفترض اسمُ الدلو العامّ**: كتبتُ أوّلاً سحباً من `unknown`
        #    وحدَه، فلمّا نُشر `nasser_almajed` كان دلوُه `no-align` فنُقل
        #    **صفر** وبقي `source_truncated: 0` — إعلانٌ صحيحٌ ومحاسبةٌ كاذبة.
        #    (‏كشفه أنّي قرأتُ `byReason` من الفهرس المنشور بعد الرفع.)
        # ⇒ تُستنزف الدلاءُ العامّةُ كلُّها بالترتيب، وما لم يُوجد له دلوٌ عامّ
        #    يبقى عددُه في `transform.gapAyahs` — وهو مصدرُ الحقيقة للتطبيق.
        _need = len(gap_ids)
        for _generic in ("unknown", "no-align", "no_align", "unaligned"):
            if _need <= 0:
                break
            _have = reasons.get(_generic, 0)
            if not _have:
                continue
            _take = min(_need, _have)
            reasons[_generic] = _have - _take
            if not reasons[_generic]:
                reasons.pop(_generic)
            reasons["source_truncated"] = reasons.get("source_truncated", 0) + _take
            _need -= _take
        if _need:
            print(f"⚠️ {_need} آيةً لم يُوجد لها دلوٌ عامٌّ في byReason — "
                  f"عددُها الصحيح في transform.gapAyahs.")
        print(f"ℹ️ نقصٌ جزئيّ: {len(gap_ids)} آيةً غائبةً في السور {surahs} "
              f"سُمّي سببُها، و**صفرُ مداخل حُذفت**.")
    if reasons.get("unknown"):                        # المُسقَط كان محسوباً حاضراً
        pass
    ids = list(miss.get("ids") or []) + [e["ayahId"] for e in dropped]
    miss.update({"count": (miss.get("count") or 0) + len(dropped),
                 "byReason": reasons, "ids": sorted(ids, key=lambda s: (
                     int(s.split(":")[0]), int(s.split(":")[1])))})

    out = dict(idx)
    out["entries"] = kept
    out["missing"] = miss
    out["lowCount"] = sum(1 for e in kept if e.get("confBand") == "LOW")
    # **أثرُ التحويل في الترويسة نفسها** — لا في رسالةٍ ولا في سجلٍّ منفصل.
    out["transform"] = {
        "op": ("declare_gap:" if a.declare_gap else "drop_surah:")
              + ",".join(str(n) for n in surahs),
        "fromSha256": live,
        "fromKey": a.key,
        "droppedEntries": len(dropped),
        **({"gapAyahs": len(gap_ids)} if a.declare_gap else {}),
        "reason": a.reason,
        **({"reasonUser": a.reason_user} if a.reason_user else {}),
        **({"reasonCode": a.reason_code} if a.reason_code else {}),
        "at": int(time.time() * 1000),
        "note": ("‏`refineStats` و`medTargeted` و`vad` تصف **البناء الأصلي** ولم"
                 " تُعد حسابها؛ والمعاد حسابه: المداخل وعدّ LOW ووسم الاكتمال."),
    }
    if len(kept) + miss["count"] != AYAH_TOTAL_OF(idx):
        raise SystemExit(f"⛔ اختلال العقد: {len(kept)} + {miss['count']} "
                         f"≠ {AYAH_TOTAL_OF(idx)}")

    raw = json.dumps(out, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    blob = gzip.compress(raw, 9)
    new_sha = hashlib.sha256(blob).hexdigest()
    riwaya = idx.get("riwaya")
    reciter = idx.get("reciterId")
    target = f"timings-staging/{riwaya}/{reciter}.{new_sha[:8]}.jz"
    per = {n: sum(1 for e in dropped if e["ayahId"].startswith(f"{n}:"))
           for n in surahs}
    print(f"من {a.key} ({live[:12]}…) · أُسقطت السور {per}: "
          f"{len(dropped)} مدخلاً")
    print(f"المداخل {len(idx['entries'])} ⇐ {len(kept)} · الغياب "
          f"{(idx.get('missing') or {}).get('count')} ⇐ {miss['count']} · "
          f"LOW {idx.get('lowCount')} ⇐ {out['lowCount']}")
    print(f"إلى {target} ({len(blob)} بايت · بصمة {new_sha[:12]}…)")
    if not a.yes:
        print("(عرضٌ فقط — أضف --yes للرفع)")
        return
    cl.put_object(Bucket=bucket, Key=target, Body=blob,
                  ContentType="application/gzip")
    got = cl.head_object(Bucket=bucket, Key=target)["ContentLength"]
    print(f"↑ رُفع · الدلو {got} · المحلّي {len(blob)} → "
          f"{'✅' if got == len(blob) else '❌'}")


SURAH_AYAHS = [
    7, 286, 200, 176, 120, 165, 206, 75, 129, 109, 123, 111, 43, 52, 99, 128,
    111, 110, 98, 135, 112, 78, 118, 64, 77, 227, 93, 88, 69, 60, 34, 30, 73,
    54, 45, 83, 182, 88, 75, 85, 54, 53, 89, 59, 37, 35, 38, 29, 18, 45, 60,
    49, 62, 55, 78, 96, 29, 22, 24, 13, 14, 11, 11, 18, 12, 12, 30, 52, 52, 44,
    28, 28, 20, 56, 40, 31, 50, 40, 46, 42, 29, 19, 36, 25, 22, 17, 19, 26, 30,
    20, 15, 21, 11, 8, 8, 19, 5, 8, 8, 11, 11, 8, 3, 9, 5, 4, 7, 3, 6, 3, 5, 4,
    5, 6]


def SURAH_AYAHS_OF(idx):                              # noqa: N802
    """عدّ آي السور — كوفيّ، وهو عدّ كل فهارسنا (`ayahCounting`)."""
    if idx.get("ayahCounting") not in (None, "KUFI"):
        raise SystemExit("⛔ عدٌّ غير كوفيّ — لا يُحوَّل بلا جدول عدّه")
    return SURAH_AYAHS


def AYAH_TOTAL_OF(idx):                               # noqa: N802
    """عدد آي المصحف بعدّ هذا الفهرس — لا رقمٌ مفترض."""
    return idx.get("ayahCount") or AYAHS


if __name__ == "__main__":
    main()
