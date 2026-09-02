#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ترقية فهرس توقيتات من الاختبار إلى الإنتاج — بحكمٍ مكتوب لا بقرار لحظة.

    python tools/index_qa/promote.py                 # عرضٌ فقط (الافتراض)
    python tools/index_qa/promote.py --yes           # تنفيذ
    python tools/index_qa/promote.py --only timings/warsh/basit_warsh.jz --yes
    python tools/index_qa/promote.py --prefix tmp/ --self-test --yes   # تجربة

⛔ **ما لا تفعله هذه الأداة أبداً:** لا تحذف كائناً، ولا تُرقّي بلا حكمٍ مكتوب
في `state/`، ولا تكتب فوق مفتاحٍ مجمَّد، ولا «تُصلح» انحرافاً — الانحراف
يُبلَّغ حادثةً لأن الإصلاح يمحو الدليل.

**قائمةٌ بيضاء لا سوداء:** لا يُرقّى إلا ما طابق شروط القبول كلَّها؛ وأيّ حكمٍ
بصيغةٍ غير معروفة **يُرفض** ولا يُجتهد فيه.

**شروط القبول (عقد github-7e صاحب المجلد، 2026-09-02) — وكلٌّ منها من واقعة:**

1. `verdict == "مقبول"` **مطابقةً تامّة** لا بادئة.
2. `fatal == []` — حزامٌ وحمّالة.
3. `sample is not None` — **حكمٌ بلا عيّنة صوتية ليس حكماً**. و«بنيوياً سليم —
   بلا عيّنة صوتية» **لا يُرقّى قطعاً**: البنية لا تشهد للمحتوى (‏`m_sayed_warsh`
   تغطيته 94.7% وبنيته نظيفة وعطبه 10.4%؛ و`huthaify_qalun` أنظف فهرسٍ بنيوياً
   وعطبه 6.2%).
4. `band is None` — عيّنة نطاقٍ واحد (‏`*.band-MED`) معدّلُ عطبها معدّل **تلك
   الشريحة** لا الفهرس، فالترقية بها ترقيةٌ برقمٍ لا يخصّ الملفّ.
5. `sha256` موجودة في الحكم **وتطابق الكائن الحيّ الآن**. ⛔ وهذا أهمّ الشروط:
   **المفتاح لا يعرّف المحتوى** — دُقّق `husary_warsh` لحظة ظهور مفتاحه فكان
   نسخةً ناقصة (110 سور) استُبدلت بعدها بالكاملة، والحكم يُنسب إلى البصمة لا
   إلى الاسم. وحكمٌ بلا بصمة (تقريرٌ قديم) يُرفض ويُعاد تدقيقه.
6. `LastModified` للكائن ليس أحدث من زمن الحكم — بصمةٌ متطابقة مع زمنٍ أحدث
   تعني رفعاً مكرراً: بلاغٌ لا كارثة، والوقوف أسلم.
7. الهدف ليس في `frozen.txt`.
8. **الفهرس نفسه يحمل أثر صقله** (`refineVersion` بقيمة صريحة) — فغيابه يعني
   «لا نعلم أيّ جيلٍ هذا»، ولا يُرقّى مجهولُ الجيل.
9. **ووسمَ اكتماله** (`missing`) بنسبة غيابٍ دون العتبة (‏`GUARD_MAX_MISSING_FRAC`،
   الافتراض 2%) **وبلا انحياز إلى القصر** (`biasedShort`) — فالغياب المنحاز
   بصمةُ ابتلاعٍ في المحاذاة لا صمتٍ عارض. وغيابُ الوسم نفسه رفض: الحقل
   الغائب يُقرأ «لا نعلم»، ولا يُرقّى ما لم يُقَس اكتماله.

**والتجميد أثرٌ مقصود لا جانبيّ (قرار المشرف github-f4، 2026-09-02):** كل فهرس
يُرقّى بحكمٍ **يُضاف إلى `frozen.txt` في العملية نفسها** — إذ لا يجوز أن يكتب
سائقٌ فوق فهرسٍ دُقِّق قبله بلا حكمٍ جديد. ورفعُ التجميد **فعلٌ صريح**: سطرٌ
يُحذف بيد إنسان، وسطرٌ في `PROMOTIONS.md` بسببه.

**والمانيفست يُكتب كتابةً شرطية (‏`If-Match`) لا بقفلٍ محلي:** القفل يحمي من
كاتبين على هذا الجهاز، و`upload_timings.py` يعمل على **خمسة خوادم** لا ترى
قفلنا — فالسباق عبر الشبكة، والقفل يعطي **أماناً ظاهرياً وهو أخطر من انعدامه
لأنه يُسكت القلق** (تشخيص github-7e). فالكتابة هنا: اقرأ ومعك `ETag`، عدّل
صفّك وحده، اكتب بشرط `If-Match`؛ فإن ردّ الخادم 412 فقد سبقك غيرك ⇒ **أعِد
القراءة فترى صفّه** ولا تمحوه. وإن تعذّرت الكتابة الشرطية فلا تُستبدل بقفلٍ
أشدّ: يُبلَّغ ويُوقف، لأن كاتبين بلا شرطٍ ذرّي يتسابقان مهما احتطنا.
"""
from __future__ import annotations

import argparse
import datetime
import gzip
import re
import hashlib
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:                                 # noqa: BLE001
        pass

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
WORK = HERE / "work"
CREDS = ROOT / "secure" / "r2_credentials.json"
STATE = HERE / "state"
FROZEN = HERE / "frozen.txt"
LOG = ROOT / "docs" / "qa" / "PROMOTIONS.md"
PUBLIC = os.environ.get(
    "R2_PUBLIC", "https://pub-2c2e1dcd92e84a2898820dd38d3e09e6.r2.dev")
ACCEPTED = "مقبول"
TAB = chr(9)


def s3():
    import boto3
    c = json.loads(CREDS.read_text(encoding="utf-8"))
    return boto3.client("s3", endpoint_url=c["endpoint"],
                        aws_access_key_id=c["accessKeyId"],
                        aws_secret_access_key=c["secretAccessKey"],
                        region_name="auto"), c["bucket"]


FROZEN_KEY = os.environ.get("R2_FROZEN_KEY", "timings/frozen.txt")
HOLD = HERE / "hold.txt"
WITHDRAWN = HERE / "evidence_withdrawn.txt"
WITHDRAWN_MAP = None    # تُملأ مرّةً عند التشغيل (‏`withdrawn()` عند None)
DIAGNOSIS_KEY = "catalog/diagnosis/{riwaya}/{reciter}.json"
# أحكامُ البتر المصدري في مفردات فارز github-12 — تُقرأ ولا يُجتهد فيها.
# (‏`ALIGNMENT_FAILED` ليست منها: الفهرس يغطّي الملفّ والعلّة في المحاذاة.)
TRUNCATED_VERDICTS = {"AUDIO_SHORT"}



def withdrawn():
    """القرّاء الذين سقط شاهدُهم: المعرّف ← (لحظةُ السحب ثوانيَ، السبب).

    الملفّ `evidence_withdrawn.txt` يشرح الحادثة كاملة. والمهمّ هنا: الحاجز
    **زمنيّ لا أبديّ** — يقارن زمنَ الحكم بلحظة السحب، فأيّ حكمٍ جديد يمرّ
    بلا لمس الملفّ. (‏وحاجزٌ يحتاج من يرفعه يدوياً يُنسى مرفوعاً أو مسدلاً.)
    """
    out = {}
    if not WITHDRAWN.exists():
        return out
    for raw in WITHDRAWN.read_text(encoding="utf-8").splitlines():
        if raw.startswith("#") or not raw.strip():
            continue
        parts = [x for x in raw.split(TAB)] if TAB in raw else raw.split(None, 2)
        if len(parts) < 2:
            continue
        rid, when = parts[0].strip(), parts[1].strip()
        why = parts[2].strip() if len(parts) > 2 else "شاهدٌ مسحوب"
        try:
            ts = datetime.datetime.strptime(
                when, "%Y-%m-%dT%H:%M:%SZ").replace(
                    tzinfo=datetime.timezone.utc).timestamp()
        except ValueError:
            raise SystemExit(f"⛔ لحظة سحبٍ غير مقروءة في {WITHDRAWN.name}: {when!r}")
        out[rid] = (ts, why)
    return out

def held():
    """المحجوزون: المفتاح ← سببُ حجزه."""
    out = {}
    if not HOLD.exists():
        return out
    for raw in HOLD.read_text(encoding="utf-8").splitlines():
        if raw.startswith("#") or not raw.strip():
            continue
        parts = raw.split(TAB, 1) if TAB in raw else raw.split(None, 1)
        if len(parts) == 2:
            out[parts[0].strip()] = parts[1].strip()
    return out


def truncation(cl, bucket, riwaya, reciter, index_etag=None):
    """سورٌ موسومةٌ ببترٍ في المصدر — من تشخيص الكتالوج (github-12).

    يُرجع (قائمة السور، هل وُجد التشخيص أصلاً). ⛔ **والبترُ المصدري لا يكشفه
    شيءٌ ممّا نفحصه:** `husary_douri` سورةُ الفرقان فيه مفهرسةٌ **77/77 بلا
    سقوطٍ ولا LOW وببصمة صوتٍ مطابقة**، وملفُّها 62% من طوله — فهو **توقيتٌ
    تامّ الظاهر على صوتٍ غير موجود**. ولا يكشفه إلا قياس المدة.
    """
    key = DIAGNOSIS_KEY.format(riwaya=riwaya, reciter=reciter)
    try:
        data = json.loads(cl.get_object(Bucket=bucket, Key=key)["Body"].read())
    except Exception:                                 # noqa: BLE001
        return [], "missing"
    # **الهوية لا الترتيب الزمني** (‏`schema: 2` من github-12): التشخيص يصف
    # فهرساً بعينه فيحمل بصمته (`indexETag`). والطابع الزمني يقول **متى كُتب**
    # ولا يقول **عمّ كُتب** — فتشخيصٌ أُعيد توليده من فهرسٍ قديم يبدو أحدثَ من
    # الفهرس الجديد، فيُحكم به على ما لا يخصّه. وهي علّة «السجلّ يصف لحظته لا
    # لحظتك» في ثوبٍ رابع.
    tag = data.get("indexETag")
    if index_etag and tag and tag.strip("\"") != index_etag.strip("\""):
        return [], "stale"
    # ⛔ **يُقرأ الحكم ولا تُخترع عتبة.** كانت القاعدة هنا «نسبة المدة < 0.9»
    # فقاستُ على الأربعين فأمسكت **255 سورة** والمبتور فيها **ثلاث**: البقيّة
    # `ALIGNMENT_FAILED` بنسبٍ 0.85–0.89 و`indexSpanShare` ≈ 0.98 — أي أنّ
    # الفهرس يغطّي الملفّ والعلّة في المحاذاة لا في الصوت. فعتبتي كانت تحجب
    # عشرات الفهارس **بالسبب الخطأ**، وصاحبُ الفارز أعلم بمعنى أرقامه.
    bad = [row for row in (data.get("weakSurahs") or [])
           if str(row.get("verdict") or "").upper() in TRUNCATED_VERDICTS
           or "TRUNCAT" in str(row.get("verdict") or "").upper()]
    return bad, "match"


def parse_frozen(text):
    """نصّ القائمة ← {المفتاح: بصمته}."""
    out = {}
    for raw in (text or "").splitlines():
        row = raw.split("#")[0].strip()
        if not row:
            continue
        parts = row.split()
        if len(parts) >= 2:
            out[parts[0]] = parts[1]
    return out


def frozen_keys():
    """القائمة من **المرآة المحلية** — للقراءة السريعة وللأدوات التي لا تكتب."""
    return parse_frozen(FROZEN.read_text(encoding="utf-8") if FROZEN.exists() else "")


def load_frozen(cl, bucket):
    """(القاموس، النصّ، ETag) من **الدلو** — مصدرُ الحقيقة الوحيد (D-075).

    ⛔ **ولا يُقرأ من الشجرة المحلية عند التعذّر:** قائمةٌ في مستودعٍ يُنسخ
    يدوياً تحرس ما دام الكاتب على هذا الجهاز ولا تحرس شيئاً خارجه — وقد وقع:
    جُمّد `akri_qalun` الساعة 05:03، ثمّ رفعه الأسطول 05:21 لأن نسخته من
    القائمة آخر تعديلها 01:45. فالحارس عمل بأمانةٍ على قائمةٍ قديمة.
    ⇒ فمن تعذّر عليه قراءتها من الدلو **يقف ولا يُرقّي**: حارسٌ يقرأ نسخةً
    قديمة أسوأ من حارسٍ يعلن عجزه.
    """
    try:
        got = cl.get_object(Bucket=bucket, Key=FROZEN_KEY)
        text = got["Body"].read().decode("utf-8")
        return parse_frozen(text), text, got.get("ETag")
    except Exception as ex:                           # noqa: BLE001
        if "NoSuchKey" in str(ex) or "404" in str(ex):
            return {}, "", None                       # أول كتابة
        raise SystemExit(f"⛔ تعذّرت قراءة قائمة التجميد من الدلو: {ex}")


def put_frozen(cl, bucket, text, etag):
    """كتابةٌ شرطية للقائمة — من سبق فاز، ومن تأخّر أعاد القراءة."""
    kw = {"Bucket": bucket, "Key": FROZEN_KEY, "Body": text.encode("utf-8"),
          "ContentType": "text/plain; charset=utf-8"}
    if etag:
        kw["IfMatch"] = etag
    cl.put_object(**kw)
    FROZEN.write_text(text, encoding="utf-8")         # المرآة المحلية بعدها
    return len(text.encode("utf-8"))


def freeze(cl, bucket, target, sha, note):
    """يضيف المفتاح المرقّى إلى القائمة **على الدلو** ثمّ يحدّث المرآة."""
    line = TAB.join([target, sha, "# " + note])
    for _try in range(5):
        _keys, text, etag = load_frozen(cl, bucket)
        body = (text.rstrip(chr(10)) + chr(10) if text.strip() else "") + line + chr(10)
        try:
            put_frozen(cl, bucket, body, etag)
            return line
        except Exception as ex:                       # noqa: BLE001
            if "PreconditionFailed" in str(ex) or "412" in str(ex):
                time.sleep(0.4)
                continue
            raise
    raise SystemExit("⛔ تعذّر تحديث قائمة التجميد على الدلو")


def unfreeze(target, reason):
    """يرفع التجميد عن مفتاح — **بابٌ معلوم لا استثناء**.

    ⚠️ تنبيه github-12 وقد أخذتُ به: التجميد يمنع الكتابة فوق المُتقَن، **وهو
    نفسه يمنع تصحيحه** إن ظهر فيه عيبٌ بعد ساعة (وقع الليلة: سورٌ مبتورة عند
    المصدر بُنيت فهارسها عليها وحملت `MATCH`). فتجميدٌ بلا باب رفعٍ معلوم
    **يحرس الخطأ كما يحرس الصواب**.

    والباب هنا: سطرٌ يُشطب من `frozen.txt` (لا يُحذف — يبقى شاهداً مشطوباً)،
    وسطرٌ في `PROMOTIONS.md` **بسببه**. ولا يُرفع تجميدٌ بلا سبب مكتوب.
    """
    if not reason:
        raise SystemExit("⛔ لا يُرفع تجميدٌ بلا سبب مكتوب")
    cl, bucket = s3()
    _keys, text, etag = load_frozen(cl, bucket)
    lines = text.splitlines()
    hit = False
    for i, raw in enumerate(lines):
        if raw.split("#")[0].strip().split()[:1] == [target]:
            lines[i] = "# رُفع " + time.strftime("%Y-%m-%d %H:%M") + " · " + reason + chr(10) + "# " + raw
            hit = True
    if not hit:
        raise SystemExit(f"⛔ {target} ليس في قائمة التجميد")
    put_frozen(cl, bucket, chr(10).join(lines) + chr(10), etag)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(chr(10) + "**رفعُ تجميد** " + time.strftime("%Y-%m-%d %H:%M")
                + " · `" + target + "` — " + reason + chr(10))
    print(f"🔓 رُفع التجميد عن {target} — {reason}")


def reports():
    """كل الأحكام المكتوبة في `state/` — والملفّ قد يحمل حكماً أو قائمة أحكام."""
    for path in sorted(STATE.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as ex:                       # noqa: BLE001
            print(f"⚠️ تعذّرت قراءة {path.name}: {ex}")
            continue
        for rep in (data if isinstance(data, list) else [data]):
            if isinstance(rep, dict) and rep.get("key"):
                yield path.name, rep


def severe_ci(rep):
    """(المعدّل، الحدّ الأدنى، الحدّ الأعلى) من عيّنة الحكم — أو أعلى `None`.

    المجال **عنقودي** يحسبه `index_qa` ويخزّنه في `sample.severe`:
    ‏`[الإصابات، حجم العيّنة، [المعدّل، الأدنى، الأعلى]]`. ولا يُعاد حسابه هنا
    بمجالٍ ثنائيّ بسيط: ذاك **أضيق** من العنقودي فيُنتج قبولاً أوسع مما تحتمله
    البيانات — وهو عين ما تمنعه D-068.
    """
    sample = rep.get("sample") or {}
    severe = sample.get("severe")
    if isinstance(severe, list) and len(severe) == 3 and isinstance(severe[2], list):
        rate, lo, hi = (severe[2] + [None, None, None])[:3]
        return rate, lo, hi
    rate = rep.get("severeRate")
    rate = rate.get("rate") if isinstance(rate, dict) else rate
    return rate, None, None


STATE_PREFIXES = tuple(
    x for x in os.environ.get("R2_STATE_PREFIXES", "qa-state/,state/").split(",") if x)
# ⛔ **بالوسم الصريح وحده**: `source: "ci"` كما نصّ عليه المشرف. ولا يُوسَّع
# إلى «github-actions» وشبهها، فأحكام github-7e نفسها تُكتب بسكربتٍ اسمه
# `ci_run.py` — ولو صُنّفت CI لتوقّفت الترقية كلُّها بحجّة «حكمٌ منفرد».
# والأحكام الحالية كلُّها بلا حقل `source` (65 ملفّاً قِستُها) فتبقى أحكامَ إنسان.
CI_SOURCES = {"ci"}


def bucket_reports(cl, bucket):
    """أحكامُ الصوت المكتوبة على **الدلو** — فمصدر الحكم قد يكون خارج الجهاز.

    ⛔ **تُقرأ هنا لا في الراصد وحده:** كان الراصد يرى حكماً على الدلو فيعدّه
    مرشّحاً، ثمّ يستدعي `main` الذي لا يقرأ إلا `state/` المحلي فلا يجد شيئاً
    — مرشّحٌ أبديّ لا يُرقّى ولا يُرفض. ومسار الحكم يجب أن يكون **واحداً**.
    """
    out = []
    try:
        for prefix in STATE_PREFIXES:
            for page in cl.get_paginator("list_objects_v2").paginate(
                    Bucket=bucket, Prefix=prefix):
                for obj in page.get("Contents", []):
                    if not obj["Key"].endswith(".json"):
                        continue
                    data = json.loads(cl.get_object(
                        Bucket=bucket, Key=obj["Key"])["Body"].read())
                    for rep in (data if isinstance(data, list) else [data]):
                        if isinstance(rep, dict) and rep.get("key"):
                            out.append((obj["Key"], rep))
    except Exception as ex:                           # noqa: BLE001
        print("  تعذّرت قراءة أحكام الدلو: " + str(ex))
    return out


def source_of(rep):
    """مصدرُ الحكم كما يعلنه: `ci` لما تكتبه وظيفة CI، وغيرُه لحكم الإنسان."""
    return str(rep.get("source") or "").strip().lower()


def is_ci(rep):
    return source_of(rep) in CI_SOURCES


def ci_map(reports_iter):
    """أحدثُ حكم CI **لكل بصمة** — شاهدٌ مُعاضِد لا حكمٌ مستقلّ.

    قاعدة المشرف github-f4 (‏2026-09-02): تُرقّى الفهرسُ بحكمين متفقين
    (‏CI و7e ولو بعيّنةٍ أصغر) أو **بحكم 7e وحده**؛ ⛔ ولا ترقية بحكم CI وحده.
    وسببُها أنّ CI يشغّل منهج 7e بلا عينه — فيصلح تعزيزاً ولا يصلح شهادةً
    منفردة، خصوصاً بعد ليلةٍ سقط فيها محرّكٌ كامل عن كونه شاهداً.
    """
    best = {}
    for _name, rep in reports_iter:
        if not is_ci(rep) or rep.get("sample") is None:
            continue
        sha = rep.get("sha256")
        if not sha:
            continue
        cur = best.get(sha)
        if cur is None or (rep.get("ts") or 0) > (cur.get("ts") or 0):
            best[sha] = rep
    return best


def latest_sampled(reports_iter):
    """أحدثُ حكمٍ **يحمل عيّنة صوتية** لكل مفتاح — لا أحدثُ حكمٍ مطلقاً.

    ⛔ جولةٌ بنيوية (‏`--struct-only`) تكتب تقريراً بلا عيّنة، فيصير «الأحدث»
    حكماً لا يشهد للمحتوى: وقع فعلاً على `huthaify_qalun` فحُجب وحكمُه الصوتي
    مكتوبٌ قبله بدقائق. فالاختيار هنا على **العيّنة لا على الزمن وحده**، ثمّ
    على الزمن بين حاملات العيّنة. والبصمةُ تُقابَل بالكائن الحيّ في البوابة،
    فالحكم القديم على نسخةٍ زائلة يسقط هناك لا هنا.
    """
    best = {}
    for name, rep in reports_iter:
        if rep.get("sample") is None or rep.get("band") is not None:
            continue
        if is_ci(rep):
            continue        # شاهدٌ مُعاضِد لا ممثِّل — ‏`ci_map` موضعُه

        key = rep.get("key")
        cur = best.get(key)
        if cur is None or (rep.get("ts") or 0) > (cur[1].get("ts") or 0):
            best[key] = (name, rep)
    return list(best.values())


def gate(rep, frozen, prefix, holds=None, override=None, ci_reports=None):
    """(الهدف، سبب الرفض) — والرفض نصٌّ يُطبع، فالصمت ليس قبولاً."""
    target = f"{prefix}timings/{rep.get('riwaya')}/{rep.get('reciterId')}.jz"
    hold = (holds or {}).get(target)
    if hold:
        return target, f"محجوز: {hold}"
    verdict = rep.get("verdict")
    if verdict != ACCEPTED and not override:
        return target, f"الحكم {verdict!r} لا {ACCEPTED!r}"
    if rep.get("fatal"):
        return target, f"خلل بنيوي: {len(rep['fatal'])}"
    if rep.get("sample") is None:
        return target, "حكمٌ بلا عيّنة صوتية"
    if rep.get("band") is not None:
        return target, f"عيّنة نطاق {rep['band']} — لا تحكم على الفهرس"
    if not rep.get("sha256"):
        return target, "حكمٌ بلا بصمة — أعِد التدقيق"
    if target in frozen:
        return target, "الهدف مجمَّد — رفعُ التجميد فعلٌ صريح بيد إنسان"
    # **حكمان لا يتناقضان.** إن وُجد حكمُ CI على **البصمة نفسها** وخالف القبول
    # فالخلافُ يُوقف: اتّفاقُهما شرطُ الترقية حين يوجدان، ولا يُرجَّح أحدهما
    # على الآخر بلا قياسٍ يفصل.
    ci = (ci_reports or {}).get(rep.get("sha256"))
    if ci is not None and ci.get("verdict") != ACCEPTED:
        return target, (f"تعارضُ حكمين على البصمة نفسها: CI يقول "
                        f"{ci.get('verdict')!r} — لا ترقية حتى يُفصل")
    # **شاهدٌ مسحوب:** حكمٌ صِيغ على براءةٍ سُحبت لا يشهد لشيء. ويُقاس بالزمن
    # لا بالاسم وحده: فمتى وصل حكمٌ بعد لحظة السحب زال الحاجز من نفسه.
    # ⛔ وموضعُه **قبل التجاوز** عمداً: `--override` رأيٌ في العتبة، وهذا
    # طعنٌ في هويّة الدليل — كمطابقة البصمة، لا يُتجاوَز.
    wd = (WITHDRAWN_MAP if WITHDRAWN_MAP is not None else withdrawn()).get(
        rep.get("reciterId"))
    if wd and (rep.get("ts") or 0) < wd[0]:
        when = datetime.datetime.utcfromtimestamp(wd[0]).strftime("%H:%M")
        return target, (f"شاهدٌ مسحوب ({when}Z): {wd[1]} — "
                        f"لا ترقية حتى يصل حكمٌ بعد السحب")
    # **D-068: القبول من الحدّ الأعلى للمجال لا من التقدير.** التقدير النقطي
    # يقول ما رأته العيّنة، والحدّ الأعلى يقول **ما تحتمله**؛ وفهرسٌ قِيس 4.5%
    # ومجاله يبلغ 6.7% قد يكون فوق العتبة حقيقةً. فما بلغ حدُّه الأعلى 5%
    # فأكثر **حدّيّ**: لا يُرقّى ولا يُجمَّد، ويبقى في الإنتاج بحُراس HIGH
    # ويُسجَّل حدّياً كي لا يُقرأ يوماً مقبولاً.
    _rate, _lo, hi = severe_ci(rep)
    if override:
        # **التجاوز يمرّ بالسبب لا بتعديل الحكم** (اقتراح github-7e، وأوافقه):
        # لو كُتب «مقبول» في ملف الحالة لأنّ القرار أُذن به **لصار الملفّ
        # يكذب** — يقول إنّ الفهرس اجتاز عتبةً لم يجتزها، ويقرؤه بعد شهرٍ من
        # لا يعلم بالقرار فيبني عليه. فالحكم يبقى صادقاً، والقرار ظاهراً،
        # وسببه مكتوباً — والثلاثة معاً.
        return target, None
    if hi is None:
        return target, "بلا مجال ثقة في الحكم — D-068 لا تُطبَّق على تقديرٍ نقطي"
    if hi >= SEVERE_CEILING:
        return target, (f"حدّيّ (D-068): الحدّ الأعلى {hi * 100:.1f}% ≥ "
                        f"{SEVERE_CEILING * 100:.0f}%")
    return target, None


MAX_MISSING_FRAC = float(os.environ.get("GUARD_MAX_MISSING_FRAC", "0.02"))
SEVERE_CEILING = float(os.environ.get("GUARD_SEVERE_CEILING", "0.05"))


CATALOG_KEY = "catalog/reciters.json"
_CATALOG = None


def catalog(cl, bucket):
    """‏{الرواية: {معرّف القارئ: صفّه}} من كتالوج الإنتاج — يُقرأ مرّةً."""
    global _CATALOG                                               # noqa: PLW0603
    if _CATALOG is None:
        try:
            data = json.loads(cl.get_object(Bucket=bucket,
                                            Key=CATALOG_KEY)["Body"].read())
            _CATALOG = {r["id"]: {x["id"]: x for x in r.get("reciters", [])}
                        for r in data.get("riwayat", [])}
        except Exception:                                         # noqa: BLE001
            _CATALOG = {}                     # لا كتالوج ⇒ لا حكم، لا اختراع
    return _CATALOG


def catalog_gate(idx, cat):
    """سببُ رفضٍ من الكتالوج، أو None. **الهويّة تُفحص كما تُفحص الأرقام.**

    وقع فعلاً (‏2026-09-02): وصل `timings-staging/hafs/en.81e7fa6c.jz` تامّاً
    6236/6236 — و`en` **ليس قارئاً**: مداخلُه كلُّها تشير إلى
    `server16.mp3quran.net/shaheen/…` أي صوتِ أحمد خليل شاهين. فلو رُقّي لنُشر
    فهرسٌ باسمٍ لا يعرفه التطبيق، وبقي القارئ الحقيقيّ بلا فهرس. ولا يكشفه
    شيءٌ ممّا نفحص: بنيتُه سليمة وتغطيتُه تامّة وحكمُه الصوتي سيكون ممتازاً
    — **لأن الصوت صحيحٌ والاسم خطأ**.
    """
    people = cat.get(idx.get("riwaya")) or {}
    if not people:
        return None                            # رواية بلا كتالوج: لا يُحكم
    rid = idx.get("reciterId")
    refs = [e.get("fileRef") for e in (idx.get("entries") or [])[:300]]
    refs = sorted({r for r in refs if isinstance(r, str) and r.startswith("http")})
    row = people.get(rid)
    if row is None:
        owner = next((k for k, v in people.items()
                      if refs and v.get("base")
                      and all(r.startswith(v["base"]) for r in refs)), None)
        return (f"معرّفٌ ليس في كتالوج {idx.get('riwaya')}: {rid!r}"
                + (f" — وصوتُه كلُّه لـ{owner!r}" if owner else ""))
    base = row.get("base")
    if base and refs:
        stray = [r for r in refs if not r.startswith(base)]
        if stray:
            return (f"مصدرُ الصوت لا يطابق قاعدة {rid} في الكتالوج: "
                    f"{stray[0][:80]}")
    return None


def index_gate(idx):
    """سبب رفض الفهرس نفسه، أو None. **الغياب رفضٌ لا تساهل.**"""
    if not idx.get("refineVersion"):
        return "الفهرس بلا أثر صقلٍ في ترويسته — مجهول الجيل فلا يُرقّى"
    miss = idx.get("missing")
    if not isinstance(miss, dict):
        return "الفهرس بلا وسم اكتمال — لا يُرقّى ما لم يُقَس اكتماله"
    total = idx.get("ayahCount") or 6236
    count = miss.get("count")
    if count is None:
        return "وسم الاكتمال بلا عدد"
    if count + len(idx.get("entries", [])) != total:
        return f"وسم الاكتمال لا يتّسق: {len(idx.get('entries', []))} + {count} ≠ {total}"
    # **الغيابُ المعلَّل لا يُحسب على عتبة الفقد.** العتبة تحرس من **ضياعٍ لا
    # نعرف سببه**؛ أمّا سورةٌ أُسقطت عمداً لأن مصدرها مبتور (‏`source_truncated`)
    # فهي **قرارٌ مسجَّل** لا فقدٌ مجهول — وحسابُها على العتبة يعاقب الإصلاح:
    # `akri_qalun` بعد إسقاط سورة 24 صار غيابه 2.0% فردّته العتبة، أي أنّ
    # البوابة كانت تفضّل شحن توقيتٍ على صوتٍ ناقص على قبول إسقاطه.
    excused = int((miss.get("byReason") or {}).get("source_truncated", 0))
    unexplained = count - excused
    if unexplained / total > MAX_MISSING_FRAC:
        return (f"غيابٌ غير معلَّل {unexplained}/{total} "
                f"({unexplained / total * 100:.1f}%) > العتبة "
                f"{MAX_MISSING_FRAC * 100:.1f}%"
                + (f" (ومعه {excused} مُسقطةٌ ببترٍ مصدري مسجَّل)" if excused else ""))
    if miss.get("biasedShort"):
        return (f"انحياز الغياب إلى القصر (وسيط {miss.get('medianLen')} مقابل "
                f"{miss.get('medianLenAll')}) — بصمةُ ابتلاعٍ في المحاذاة")
    return None


def object_sha(cl, bucket, key):
    body = cl.get_object(Bucket=bucket, Key=key)["Body"].read()
    return hashlib.sha256(body).hexdigest(), len(body), body


def public_size(key):
    req = urllib.request.Request(f"{PUBLIC}/{key}", method="HEAD",
                                 headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return int(r.headers.get("Content-Length") or -1)
    except Exception as ex:                           # noqa: BLE001
        return f"خطأ: {ex}"


def write_manifest(cl, bucket, prefix, row, tries=5):
    """كتابةٌ شرطية بـ`If-Match`: من سبق فاز، ومن تأخّر أعاد القراءة فرأى صفّه."""
    key = f"{prefix}timings/manifest.json"
    for attempt in range(1, tries + 1):
        etag = None
        try:
            got = cl.get_object(Bucket=bucket, Key=key)
            cur = json.loads(got["Body"].read())
            etag = got.get("ETag")
        except Exception:                             # noqa: BLE001
            cur = {"version": 1, "indexes": []}
        cur["indexes"] = [x for x in cur.get("indexes", [])
                          if not (x.get("riwaya") == row["riwaya"]
                                  and x.get("reciterId") == row["reciterId"])]
        cur["indexes"].append(row)
        cur["updated"] = row["updatedTs"]
        body = json.dumps(cur, ensure_ascii=False).encode("utf-8")
        kw = {"Bucket": bucket, "Key": key, "Body": body,
              "ContentType": "application/json"}
        if etag:
            kw["IfMatch"] = etag
        try:
            cl.put_object(**kw)
            return key, len(body), len(cur["indexes"]), attempt, bool(etag)
        except Exception as ex:                       # noqa: BLE001
            text = str(ex)
            if "PreconditionFailed" in text or "412" in text:
                print(f"  ↻ سبقنا كاتبٌ آخر ({attempt}/{tries}) — أعيد القراءة")
                time.sleep(0.5 * attempt)
                continue
            if "NotImplemented" in text or "IfMatch" in text:
                raise SystemExit(
                    "⛔ الكتابة الشرطية غير مدعومة هنا — لا تُستبدل بقفلٍ أشدّ. "
                    "اجعل المانيفست بكاتبٍ واحد وأبلغ الفريق.")
            raise
    raise SystemExit("⛔ تعذّرت الكتابة الشرطية بعد محاولات — بلاغٌ لا التفاف")


def note_borderline(rep, target, why):
    """يسجّل الحكم **الحدّيّ** مرّةً واحدة لكل (مفتاح، بصمة) في `PROMOTIONS.md`.

    الحدّيّ ليس مرفوضاً ولا مقبولاً: **يبقى في الإنتاج بحُراس HIGH ولا يُرقّى
    ولا يُجمَّد** (‏D-068). وتسجيلُه واجبٌ لأنه بلا سجلٍّ يُقرأ بعد شهرٍ
    «مقبولاً لم يُرقَّ بعد» — والفرق بينهما هو الفرق بين انتظارٍ وقرار.
    """
    ledger = WORK / "borderline.json"
    WORK.mkdir(parents=True, exist_ok=True)
    try:
        seen = json.loads(ledger.read_text(encoding="utf-8"))
    except Exception:                                 # noqa: BLE001
        seen = {}
    if seen.get(target) == rep.get("sha256"):
        return
    rate, lo, hi = severe_ci(rep)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(chr(10) + "**حكمٌ حدّيّ (D-068)** " + time.strftime("%Y-%m-%d %H:%M")
                + " · `" + target + "` · بصمة `" + str(rep.get("sha256"))[:16]
                + "…` — " + why + f" (التقدير {(rate or 0) * 100:.1f}% ·"
                f" المجال [{(lo or 0) * 100:.1f}–{(hi or 0) * 100:.1f}])."
                + " **لا ترقية ولا تجميد**؛ يبقى في الإنتاج بحُراس HIGH."
                + chr(10))
    seen[target] = rep.get("sha256")
    ledger.write_text(json.dumps(seen, ensure_ascii=False, indent=1),
                      encoding="utf-8")
    print(f"  📝 سُجِّل حدّياً: {target}")


def log_promotion(rows):
    """الترقية بلا رقمها ادّعاء — فيُسجَّل المصدر والبصمة والحكم ومعدّل العطب."""
    LOG.parent.mkdir(parents=True, exist_ok=True)
    if not LOG.exists():
        LOG.write_text(
            "# سجل الترقيات — من الاختبار إلى الإنتاج\n\n"
            "> لا سطر هنا بلا حكمٍ مكتوب في `tools/index_qa/state/`، ولا حكمَ\n"
            "> بلا بصمة. والبصمة بصمةُ **البايتات المضغوطة** كما هي على الدلو.\n"
            "> وكل مفتاحٍ هنا **مجمَّد** بعد ترقيته؛ ورفعُ التجميد سطرٌ يُحذف من\n"
            "> `frozen.txt` وسطرٌ يُكتب هنا بسببه.\n\n"
            "| وقت الترقية | المصدر | الهدف | البصمة | الحكم | معدّل العطب | وقت الحكم |\n"
            "|---|---|---|---|---|---|---|\n", encoding="utf-8")
    with LOG.open("a", encoding="utf-8") as f:
        for r in rows:
            f.write(f"| {r['when']} | `{r['src']}` | `{r['dst']}` | `{r['sha'][:16]}…` | "
                    f"{r['verdict']} | {r['severe']} | {r['judged']} |\n")


def self_test(cl, bucket, prefix):
    """تجربةٌ كاملة على بادئة `tmp/`: كائنٌ وهمي وثلاثة أحكام — موجبٌ وسالبان.

    **الحارس يُختبر بما يجب أن يردّه** لا بما يجب أن يمرّره وحده.
    ⛔ ولا تُحذف كائنات التجربة بعدها (قاعدة «لا حذف») — تبقى تحت `tmp/` شاهدةً.
    """
    payload = gzip.compress(json.dumps(
        {"schema": 1, "riwaya": "tmp", "reciterId": "selftest",
         "refineVersion": "none", "entries": []}, ensure_ascii=False).encode())
    src = f"{prefix}timings-staging/tmp/selftest.jz"
    cl.put_object(Bucket=bucket, Key=src, Body=payload,
                  ContentType="application/gzip")
    sha = hashlib.sha256(payload).hexdigest()
    rep = {"key": src, "riwaya": "tmp", "reciterId": "selftest",
           "verdict": ACCEPTED, "fatal": [], "band": None,
           "sample": {"seed": 0},
           "severeRate": {"rate": 0.0, "lo": 0.0, "hi": 0.0},
           "sha256": sha, "ts": time.time() + 60,
           "info": {"entries": 0, "refineVersion": "none"}}
    # **الشاهد المسحوب يُختبر بحالتيه**: حكمٌ قبل السحب يُردّ، ومثلُه بعده يمرّ
    # — فالحاجز الذي لا يُرفع تلقائياً يجمّد الأسطول، والذي لا يقع لا يحرس.
    global WITHDRAWN_MAP                                          # noqa: PLW0603
    WITHDRAWN_MAP = dict(withdrawn())
    cut = time.time() + 3600
    WITHDRAWN_MAP["selftest_wd"] = (cut, "تجربةُ سحبٍ")
    wd_old = dict(rep, reciterId="selftest_wd", ts=cut - 60)
    wd_new = dict(rep, reciterId="selftest_wd", ts=cut + 60)
    print(f"— تجربة: رُفع كائنٌ وهمي {src} ({len(payload)} بايت) + حالتان "
          "سالبتان (بصمةٌ مخالفة · عيّنة نطاق) + الشاهدُ المسحوب وبديلُه")
    # (‏الحالة الموجبة تُختبر بأن **سبب الردّ لم يعد السحب** — لا بأنها تُرقّى:
    #  هذا الرِّيب مبنيٌّ بلا مجال ثقة عنقودي فتردّه D-068، وذاك حارسٌ آخر.)
    for name, r, want in (("سحبٌ قديم", wd_old, True), ("بديلٌ بعد السحب", wd_new, False)):
        _t, why = gate(r, {}, prefix, {}, None)
        ok = (why is not None and "مسحوب" in why) is want
        print(f"  {'✅' if ok else '❌'} {name}: {why or 'يمرّ'}")
        if not ok:
            raise SystemExit("⛔ فشل اختبار الشاهد المسحوب — لا ترقية بحارسٍ مكسور")
    # **حكمُ CI وحده لا يُرقّي، والمخالفُ منه يوقف** — قاعدة المشرف تُختبر لا تُوصف.
    ci_rep = dict(rep, source="ci")
    if [x for x in latest_sampled([("ci", ci_rep)])]:
        raise SystemExit("⛔ حكمُ CI صار ممثِّلاً — القاعدة مكسورة")
    _t, why = gate(rep, {}, prefix, {}, None,
                   {rep["sha256"]: dict(rep, source="ci", verdict="مرفوض")})
    print(f"  {'✅' if why and 'تعارض' in why else '❌'} تعارضُ CI: {why}")
    if not (why and "تعارض" in why):
        raise SystemExit("⛔ تعارضُ CI لم يوقف الترقية")
    print("  ✅ حكمُ CI منفرداً لا يصير ممثِّلاً")
    WITHDRAWN_MAP = None
    return [("self-test", rep),
            ("self-test-bad-sha", dict(rep, sha256="0" * 64)),
            ("self-test-bad-band", dict(rep, band="MED"))]


def main():
    ap = argparse.ArgumentParser(description="ترقية الفهارس المقبولة")
    ap.add_argument("--yes", action="store_true", help="نفّذ (الافتراض عرضٌ فقط)")
    ap.add_argument("--prefix", default="", help="بادئة للتجربة، مثل tmp/")
    ap.add_argument("--self-test", action="store_true",
                    help="اختبار المسار كاملاً على كائنٍ وهمي")
    ap.add_argument("--only", help="مفتاح مصدرٍ بعينه")
    ap.add_argument("--sync-frozen", action="store_true",
                    help="ادفع المرآة المحلية إلى قائمة الدلو (دمجٌ لا استبدال)")
    ap.add_argument("--unfreeze", metavar="KEY", help="رفع تجميدٍ بسببٍ مكتوب")
    ap.add_argument("--reason", help="سبب رفع التجميد — إلزامي معه")
    ap.add_argument("--allow-truncated", metavar="سبب",
                    help="ترقيةُ فهرسٍ فيه سورةٌ مبتورةُ المصدر — يجب أن يذكر "
                         "السببُ أرقامَ السور، ويُسجَّل في السجل")
    ap.add_argument("--override", metavar="سبب",
                    help="ترقيةٌ بتجاوزٍ صريح رغم أن الحكم ليس «مقبول» — "
                         "يُكتب السبب في السجل، ولا يُعدَّل وسمُ الحكم")
    a = ap.parse_args()

    if a.unfreeze:
        unfreeze(a.unfreeze, a.reason)
        return

    cl, bucket = s3()
    frozen, frozen_text, _etag = load_frozen(cl, bucket)
    holds = held()
    if a.sync_frozen:
        local = FROZEN.read_text(encoding="utf-8") if FROZEN.exists() else ""
        merged = dict(frozen)
        body = frozen_text.rstrip(chr(10))
        added = 0
        for raw in local.splitlines():
            row = raw.split("#")[0].strip().split()
            if len(row) >= 2 and merged.get(row[0]) != row[1]:
                body = (body + chr(10) if body else "") + raw
                merged[row[0]] = row[1]
                added += 1
        size = put_frozen(cl, bucket, body + chr(10), _etag)
        print(f"↑ {FROZEN_KEY} ({size} بايت · {len(merged)} مفتاحاً · أُضيف {added}) "
              f"· تحقّق عام {public_size(FROZEN_KEY)}")
        return
    everywhere = (self_test(cl, bucket, a.prefix) if a.self_test
                  else list(reports()) + bucket_reports(cl, bucket))
    ci_reports = ci_map(everywhere)
    items = everywhere if a.self_test else latest_sampled(everywhere)
    if a.only:
        items = [(n, r) for n, r in items if r.get("key") == a.only]

    ready, refused, done = [], [], []
    for name, rep in items:
        target, why = gate(rep, frozen, a.prefix, holds, a.override,
                           ci_reports)
        if why:
            refused.append((rep.get("key"), why))
            if why.startswith("حدّيّ") and a.yes:
                note_borderline(rep, target, why)
            continue
        ready.append((name, rep, target))

    print(f"أحكامٌ مقروءة: {len(items)} · مرشّحون: {len(ready)} · مرفوضون: {len(refused)}")
    for key, why in refused[:40]:
        print(f"  ⛔ {key}: {why}")

    for _name, rep, target in ready:
        src = rep["key"]
        try:
            live_sha, size, body = object_sha(cl, bucket, src)
        except Exception as ex:                       # noqa: BLE001
            print(f"  ⛔ {src}: تعذّر قراءة الكائن — {ex}")
            continue
        if live_sha != rep["sha256"]:
            print(f"  🔴 {src}: الفهرس تغيّر بعد الحكم "
                  f"({live_sha[:12]}… ≠ {rep['sha256'][:12]}…) — أعِد التدقيق، ولا يُصلَح")
            continue
        head = cl.head_object(Bucket=bucket, Key=src)
        if head["LastModified"].timestamp() > float(rep.get("ts") or 0):
            print(f"  🔴 {src}: الكائن أحدث من حكمه — رفعٌ مكرّر، وقوفٌ لا ترقية")
            continue
        stem = Path(src).name[:-3]                    # فحصٌ ثالث مجاني: لاحقة الاسم
        if "." in stem:
            tag = stem.rsplit(".", 1)[-1]
            if len(tag) == 8 and not live_sha.startswith(tag):
                print(f"  ⚠️ {src}: لاحقة الاسم {tag} لا تطابق البصمة {live_sha[:8]} "
                      "(الاسم يُكتب والبصمة تُحسب — البصمة هي الحكم)")
        if target in frozen and frozen[target] != live_sha:
            print(f"  🔴 {target}: مجمَّد ببصمةٍ أخرى — حادثةٌ تُبلَّغ ولا تُكتب")
            continue
        # **بترُ المصدر يُفحص قبل النسخ** — من تشخيص الكتالوج لا من الفهرس،
        # فالفهرس لا يعرف أن صوته ناقص.
        # **التشخيص يوصف به الصوت لا بايتات الفهرس.** فبصمتُه تُقابل بالفهرس
        # **المنشور** لذلك القارئ لا بالمرشّح: تابعُ github-12 لا يكتب تشخيصاً
        # إلا بعد نشر، فمقابلتُه بمفتاح الاختبار تجعل كل مرشّحٍ «قديم التشخيص»
        # أبداً — قفلٌ يمنع كل ترقية بحجّة انتظارٍ لا ينتهي.
        published = f"timings/{rep['riwaya']}/{rep['reciterId']}.jz"
        try:
            pub_etag = cl.head_object(Bucket=bucket, Key=published).get("ETag")
        except Exception:                             # noqa: BLE001
            pub_etag = None
        cut, diag_state = truncation(cl, bucket, rep["riwaya"], rep["reciterId"],
                                     pub_etag)
        # وسورةٌ أُسقطت من المرشّح لا تُحسب عليه: التشخيص يصف الفهرس المنشور
        # وفيه السورة، والمرشّح خالٍ منها — وهذا هو الإصلاح لا العيب.
        idx_peek = json.loads(gzip.decompress(body).decode("utf-8"))
        gone = {e["ayahId"].split(":")[0] for e in idx_peek.get("entries", [])}
        cut = [r for r in cut if str(r.get("surah")) in gone]
        if cut:
            names = "، ".join(str(r.get("surah")) for r in cut[:5])
            # **إن كان لها علاجٌ مسجَّل فقُله** — لئلا يُعاد عملٌ تمّ. ووسمُ
            # github-12 يميّز بحقٍّ: الإسقاط أزال **إشارة الفهرس** إلى العيب
            # ولم يُزل العيب (`audioStillDefective`)، فالصوت باقٍ معيباً وأيّ
            # بناءٍ جديد عليه يلتقطه من جديد.
            ready = [r.get("remediation", {}).get("stagingKey") for r in cut
                     if isinstance(r.get("remediation"), dict)]
            ready = [x for x in ready if x]
            if ready:
                print("     ↳ نسخةٌ معالَجةٌ بالإسقاط موجودة: " + "، ".join(ready)
                      + " — والصوت نفسه ما زال معيباً")
            # **استثناءُ البتر يُسمّي سورَه ولا يُمنح جملةً.** وهو منفصلٌ عن
            # `--override`: ذاك رأيٌ في **عتبة الحكم**، وهذا قبولٌ بأن يُشحن
            # توقيتٌ على **صوتٍ ناقص** — والخلط بينهما يجعل تجاوزاً واحداً
            # يفتح بابين. ولذلك يُشترط أن يذكر السببُ كل سورةٍ بعينها.
            wanted = {str(r.get("surah")) for r in cut}
            given = set(re.findall(r"\d+", a.allow_truncated or ""))
            if not (a.allow_truncated and wanted <= given):
                print(f"  🔴 {src}: سورٌ مبتورةٌ في المصدر ({names}) — "
                      "لا ترقية إلا باستثناءٍ يسمّيها في --allow-truncated")
                continue
            detail = "، ".join(
                f"{r.get('surah')} (نسبة المدة {r.get('durationRatio')})"
                for r in cut)
            LOG.parent.mkdir(parents=True, exist_ok=True)
            with LOG.open("a", encoding="utf-8") as f:
                f.write(chr(10) + "**استثناءُ بترٍ مصدريّ** "
                        + time.strftime("%Y-%m-%d %H:%M") + " · `" + target
                        + "`" + chr(10) + "- **السور المبتورة:** " + detail
                        + chr(10) + "- **السبب:** " + a.allow_truncated + chr(10)
                        + "- ⚠️ التوقيت في هذه السور يقع على **صوتٍ ناقص**؛"
                        " والمستهلك يراها كسائر السور ما لم يُستثنَ عنده."
                        + chr(10))
            print(f"  ⚠️ {src}: قُبل بترُ ({names}) باستثناءٍ مسجَّل")
        if diag_state == "stale":
            # **يُحجَز ولا يُسقَط:** التابع يعيد كتابة التشخيص عند كل نشر،
            # فبصمةٌ مخالفة تعني «التشخيص في الطريق» لا «مفقود» — والقيد يُرفع
            # من تلقائه عند أول تطابق (github-12).
            print(f"  ⏳ {src}: تشخيص الكتالوج يصف فهرساً آخر (بصمةٌ مخالفة) — "
                  "يُنتظر ولا يُرقّى")
            continue
        if diag_state == "missing":
            print(f"  ⚠️ {src}: لا تشخيص كتالوج لهذا القارئ — "
                  "البترُ المصدري غير مفحوص (يُرقّى بحكمه الصوتي وحده)")
        idx = json.loads(gzip.decompress(body).decode("utf-8"))
        # شرطا الفهرس نفسه (لا الحكم): أثرُ الصقل ووسمُ الاكتمال.
        bad = index_gate(idx) or catalog_gate(idx, catalog(cl, bucket))
        if bad:
            print(f"  ⛔ {src}: {bad}")
            continue
        row = {"riwaya": rep["riwaya"], "reciterId": rep["reciterId"],
               "entries": len(idx.get("entries", [])),
               "refineVersion": idx.get("refineVersion"),
               "sha256": live_sha, "updatedTs": int(time.time() * 1000)}
        # `severeRate` يأتي رقماً في بعض التقارير وقاموساً بمجاله في غيرها —
        # فيُقرأ الشكلان، ولا يُفترض شكلٌ واحد (وقع الافتراض فأسقط أول ترقية).
        severe = rep.get("severeRate")
        if isinstance(severe, dict):
            rate = (f"{severe.get('rate', 0) * 100:.1f}% "
                    f"[{severe.get('lo', 0) * 100:.1f}–{severe.get('hi', 0) * 100:.1f}]")
        elif isinstance(severe, (int, float)):
            rate = f"{severe * 100:.1f}%"
        else:
            rate = "—"
        if not a.yes:
            print(f"  ✅ جاهز: {src} → {target} · مداخل {row['entries']} · "
                  f"عطب {rate} · بصمة {live_sha[:12]}… (عرضٌ فقط، أضف --yes)")
            continue
        # الفهرس قد يكون دُقِّق **في مكانه** (مفتاحه هو مفتاح الإنتاج) — فلا
        # نسخ حينئذٍ، ويبقى للترقية معناها: المانيفست والتجميد والسجل.
        if src != target:
            cl.copy_object(Bucket=bucket, Key=target,
                           CopySource={"Bucket": bucket, "Key": src},
                           ContentType="application/gzip",
                           MetadataDirective="REPLACE")
        else:
            print(f"  ↔ {src}: دُقِّق في مكانه — لا نسخ، والترقية تسجيلٌ وتجميد")
        got = cl.head_object(Bucket=bucket, Key=target)["ContentLength"]
        pub = public_size(target)
        ok = got == size and pub == size
        print(f"  ↑ {target} · الدلو {got} · العام {pub} · المصدر {size} "
              f"→ {'✅' if ok else '❌'}")
        if not ok:
            print("  ⛔ لم يتحقّق الحجم — لا يُكتب المانيفست ولا يُجمَّد")
            continue
        mkey, mlen, count, tries, cond = write_manifest(cl, bucket, a.prefix, row)
        mpub = public_size(mkey)
        print(f"  ↑ {mkey} ({mlen} بايت · {count} فهرساً · محاولات {tries} · "
              f"شرطية {'نعم' if cond else 'أول كتابة'}) · العام {mpub} "
              f"→ {'✅' if mpub == mlen else '❌'}")
        note = ("ترقية بتجاوزٍ صريح" if a.override else "ترقية بحكمٍ")
        line = freeze(cl, bucket, target, live_sha,
                      f"{note} · عطب {rate} · مداخل {row['entries']}")
        print(f"  🧊 جُمّد: {line}")
        if a.override:
            LOG.parent.mkdir(parents=True, exist_ok=True)
            with LOG.open("a", encoding="utf-8") as f:
                f.write(chr(10) + "**ترقيةٌ بتجاوزٍ صريح** "
                        + time.strftime("%Y-%m-%d %H:%M") + " · `" + target
                        + "` · بصمة `" + live_sha[:16] + "…`" + chr(10)
                        + "- **حكم الفهرس كما هو ولم يُعدَّل:** "
                        + str(rep.get("verdict")) + chr(10)
                        + "- **السبب:** " + a.override + chr(10))
        done.append({"when": time.strftime("%Y-%m-%d %H:%M")
                     + (" (تجربة)" if a.self_test else ""),
                     "src": src, "dst": target, "sha": live_sha,
                     "verdict": rep["verdict"], "severe": rate,
                     "judged": time.strftime("%Y-%m-%d %H:%M",
                                             time.localtime(rep.get("ts") or 0))})
    if done:
        log_promotion(done)
        print(f"سُجّلت {len(done)} ترقية في {LOG.relative_to(ROOT)}")
    elif a.yes:
        print("لا ترقية — ولا شيء كُتب.")


if __name__ == "__main__":
    main()
