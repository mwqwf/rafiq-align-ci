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
سائقٌ فوق فهرسٍ دُقِّق قبله بلا حكمٍ جديد. ورفعُ التجميد **فعلٌ صريحٌ يملكه الوكيل** (‏D-183): سطرٌ
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
from concurrent.futures import ThreadPoolExecutor
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


_AYAH_COUNTS = [7, 286, 200, 176, 120, 165, 206, 75, 129, 109, 123, 111, 43,
                52, 99, 128, 111, 110, 98, 135, 112, 78, 118, 64, 77, 227, 93, 88,
                69, 60, 34, 30, 73, 54, 45, 83, 182, 88, 75, 85, 54, 53, 89, 59,
                37, 35, 38, 29, 18, 45, 60, 49, 62, 55, 78, 96, 29, 22, 24, 13,
                14, 11, 11, 18, 12, 12, 30, 52, 52, 44, 28, 28, 20, 56, 40, 31,
                50, 40, 46, 42, 29, 19, 36, 25, 22, 17, 19, 26, 30, 20, 15, 21,
                11, 8, 8, 19, 5, 8, 8, 11, 11, 8, 3, 9, 5, 4, 7, 3, 6, 3, 5, 4,
                5, 6]

def _op_mixes_engines(op: str) -> bool:
    """هل يخلط هذا التحويلُ مخرَجَ محرّكين في فهرسٍ واحد؟"""
    return op.startswith(("source_timing_splice", "mixed_engine",
                          "timing_splice"))

def s3():
    import boto3
    from botocore.config import Config
    # ⛔ **صبرٌ يناسب شبكةَ المالك** (‏قِيس 2026-09-09): `certify_catalog` سقط
    #    ثلاثَ مرّاتٍ متتاليةً بـ`ReadTimeout` وهو يسحب أحكامَ الصوت (‏~160ك.ب
    #    للحكم الواحد · مئاتُ الأحكام)، **وضاعت في كلّ مرّةٍ نصفُ ساعةٍ من
    #    السحب المنجَز** — لأنّ مهلةَ القراءة الافتراضية ستّون ثانية، وانقطاعُ
    #    التيّار في أثناء قراءة الجسم **لا تُعيده botocore أصلاً** (‏إعادةُ
    #    المحاولة للطلب لا للتدفّق). فالمهلةُ ثلاثُ دقائقَ والمحاولاتُ عشر.
    #    ⛔ ولا يُغيَّر هذا حكماً ولا عتبة — صبرٌ لا غير.
    c = json.loads(CREDS.read_text(encoding="utf-8"))
    cfg = Config(connect_timeout=30, read_timeout=180,
                 retries={"max_attempts": 10, "mode": "standard"},
                 max_pool_connections=10)
    return boto3.client("s3", endpoint_url=c["endpoint"],
                        aws_access_key_id=c["accessKeyId"],
                        aws_secret_access_key=c["secretAccessKey"],
                        region_name="auto", config=cfg), c["bucket"]


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
    # ⛔ **حارسُ شكلِ المفتاح (‏وقعت الحادثة 2026-09-03):** الحجزُ يُطابَق على
    #    **الهدف** `timings/<الرواية>/<المعرّف>.jz` مطابقةً حرفية. فمن كتب مفتاح
    #    **المصدر** (`timings-staging/…`) أو ألحق بصمةً (`…/<id>.<sha>.jz`) كتب
    #    حجزاً **لا يُطابق شيئاً أبداً** — ويبقى ساكتاً: لا خطأ، ولا حماية.
    #    وثمنُه أنّ مَن قرأ الملفّ حسِب الفهرس محجوزاً وهو سائبٌ إلى الإنتاج.
    #    ⇒ يُنبَّه ولا يُحذف: الحذفُ يُخفي ما كُتب، والتنبيهُ يُصلحه صاحبُه.
    bad = [k for k in out if not re.fullmatch(r"timings/[^/]+/[^/.]+\.jz", k)]
    if bad:
        print("⚠️ مفاتيحُ حجزٍ لا تُطابق شكلَ الهدف فلا تحجب شيئاً: "
              + " · ".join(bad), file=sys.stderr)
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


def _min_sample(ceiling, conf=0.95):
    """أصغرُ حجمِ عيّنةٍ يمكن أن ينزل حدُّها الأعلى تحت العتبة عند صفر أعطاب.

    ‏`1 − (1−ثقة)^(1/ن) < عتبة` — أي قاعدةُ الثلاثة الدقيقة مقلوبة. وعند
    عتبة 5% وثقة 95% تعطي **ن ≥ 59**. ورقمٌ مشتقٌّ لا مختار: من غيّر العتبة
    تحرّك الحدُّ معها بلا أن ينسى أحدٌ تحديثه.
    """
    import math
    n = math.log(1 - conf) / math.log(1 - ceiling)
    return int(math.ceil(n))


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
# ⛔ **مصادرُ CI الثلاثة — والاسمُ عقدٌ لا زينة.** كلُّها تشغّل **أداةَ 7e نفسها**
#    (`ci_run.py`) فمحرّكُها واحد، وإنما تختلف **بيئةُ التشغيل وملحُ البذرة**:
#      `ci`           → GitHub Actions        → `state/<المفتاح>.audio-ci.json`
#      `cloud-build`  → Cloud Build (D-095)   → `state/<المفتاح>.audio-cb.json`
#    (وملحا `ci` و`ci2` بيئتُهما واحدة وملحُهما مختلف — والملحُ هو ما يشهد.)
# ⛔ ولا يُضاف مصدرٌ رابع إلا بملفٍّ باسمه: **لا يكتب أحدٌ فوق ملفٍّ ليس له**
#    (وقد كلّفنا خلطُ الأسماء ليلةً كاملةً — انظر README البوابة).
# ⛔ والبيئةُ الجديدة **لا تزيد الدليل من نفسها**: `ci_pair_reps` يشترط اختلاف
#    الملح لا اختلاف البيئة — فحكمٌ من Cloud Build بملح `ci` لا يزاوج حكمَ
#    Actions بملح `ci`، ولو اختلفت الآلتان. **اختلافُ الملح يزيد الدليل،
#    واختلافُ المحرّك يُبطل المقارنة** (github-7e).
CI_SOURCES = {"ci", "cloud-build"}

# **أحكامٌ مقروءة سلفاً في الدورة** (أمر المشرف github-5a، 2026-09-03): الراصد يقرأ
# `state/` كاملاً مرةً في أول الدورة ويضعها هنا، فلا يعيد `main` قراءتها لكل
# ترقية (كانت 9 أزواج × 3 دقائق هدراً). ⛔ ولا تُخزَّن بين الدورتين: الراصد
# يمحوها في آخر الدورة، فلا يُبنى حكمٌ على قراءةٍ أقدم من دورة.
REPORTS_CACHE = None


def bucket_reports(cl, bucket):
    """أحكامُ الصوت المكتوبة على **الدلو** — فمصدر الحكم قد يكون خارج الجهاز.

    ⛔ **تُقرأ هنا لا في الراصد وحده:** كان الراصد يرى حكماً على الدلو فيعدّه
    مرشّحاً، ثمّ يستدعي `main` الذي لا يقرأ إلا `state/` المحلي فلا يجد شيئاً
    — مرشّحٌ أبديّ لا يُرقّى ولا يُرفض. ومسار الحكم يجب أن يكون **واحداً**.
    """
    # ⛔ **العطب المقيس (2026-09-04): `try` واحدٌ يلفّ القراءة كلَّها** — فخطأُ
    #    شبكةٍ في ملفٍّ واحدٍ يقطع الحلقة ويُرجع ما جُمع قبله **بلا أن يشتكي**.
    #    وعلى شبكةٍ ضعيفة صار الحكمُ يُبنى على **جزءٍ عشوائيّ**: قُرئ 76 حكماً
    #    وهي 241، **فسقط من التقييم قرّاءٌ يستحقّون الترقية** ولم يظهروا في
    #    قائمة الردّ أصلاً — **غيابٌ يُقرأ رفضاً وهو عمى**.
    #    ⇒ الخطأُ يُعزل في الملفّ الواحد، **ويُعلن العددُ والفشلُ معاً**، ويُعاد
    #    المحاولة. **وقراءةٌ ناقصةٌ لا تُسكَت عنها**: من قرأ بعضاً وحكم على الكلّ
    #    أخطأ في الاتجاه الذي لا يُرى.
    out, failed, seen = [], 0, 0
    for prefix in STATE_PREFIXES:
        try:
            pages = list(cl.get_paginator("list_objects_v2").paginate(
                Bucket=bucket, Prefix=prefix))
        except Exception as ex:                       # noqa: BLE001
            print(f"  ⛔ تعذّر سردُ {prefix}: {ex}")
            continue
        # ⛔ **القراءةُ التسلسليّة كانت عنقَ كلّ دورة**: ‏≈300 ملفٍّ × رحلةٍ
        #    شبكيّةٍ لكلٍّ ⇒ دقائقُ قبل أن تطبع البوابةُ حرفاً واحداً. والملفّات
        #    **مستقلّةٌ تماماً**، فتوازيها بلا خطر. (‏والعميلُ `boto3` آمنٌ
        #    للخيوط ما دام كلُّ خيطٍ يستدعي `get_object` وحده.)
        # ⛔ **العنقُ المقيس (2026-09-04): 1027 ملفَ حكمٍ = 65 م.ب تُنزَّل في
        #    كلّ دورة** — على شبكةٍ ضعيفة تتجاوز القراءةُ عشرَ دقائق، فتصير
        #    البوابةُ نفسُها أبطأَ من كلّ ما تحكم عليه. **والأحكامُ لا تتغيّر:**
        #    حكمٌ كُتب بمفتاحٍ وبصمةٍ لا يُعاد كتابته. ⇒ **ذاكرةٌ محليّةٌ
        #    بمفتاحٍ + `ETag`**: يُنزَّل الجديدُ وحدَه، ويُقرأ الباقي من القرص.
        objs = [(o["Key"], o.get("ETag", "").strip('"'))
                for page in pages for o in page.get("Contents", [])
                if o["Key"].endswith(".json")]
        seen += len(objs)
        cdir = Path(__file__).resolve().parent / "work" / "verdict_cache"
        cdir.mkdir(parents=True, exist_ok=True)

        def _cached(key, etag):
            f = cdir / (hashlib.sha256(f"{key}|{etag}".encode()).hexdigest() + ".json")
            if f.exists():
                try:
                    return json.loads(f.read_text(encoding="utf-8"))
                except Exception:                     # noqa: BLE001
                    pass
            return None

        def _store(key, etag, data):
            f = cdir / (hashlib.sha256(f"{key}|{etag}".encode()).hexdigest() + ".json")
            try:
                f.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            except Exception:                         # noqa: BLE001
                pass

        hits = 0
        keys = []
        for key, etag in objs:
            d = _cached(key, etag)
            if d is None:
                keys.append(key)
                continue
            hits += 1
            for rep in (d if isinstance(d, list) else [d]):
                if isinstance(rep, dict) and rep.get("key"):
                    out.append((key, rep))
        _ETAGS = dict(objs)

        def _one(key):
            for attempt in range(3):
                try:
                    return key, json.loads(cl.get_object(
                        Bucket=bucket, Key=key)["Body"].read())
                except Exception:                     # noqa: BLE001
                    if attempt == 2:
                        return key, None
                    time.sleep(1.5 * (attempt + 1))
            return key, None

        with ThreadPoolExecutor(max_workers=16) as pool:
            for key, data in pool.map(_one, keys):
                if data is None:
                    failed += 1
                    continue
                _store(key, _ETAGS.get(key, ""), data)
                for rep in (data if isinstance(data, list) else [data]):
                    if isinstance(rep, dict) and rep.get("key"):
                        out.append((key, rep))
        if hits:
            print(f"  ⚡ أحكامٌ من الذاكرة المحليّة: {hits} · نُزّل {len(keys)}")
    if failed:
        # ⛔ **الرقمُ عند وجود فشلٍ حدٌّ أدنى لا قياس** — ولا يُبنى عليه رفض.
        print(f"  ⚠️ أحكامُ الدلو: قُرئ {len(out)} من {seen} ملفاً · "
              f"**تعذّر {failed}** ⇒ التقييمُ ناقصٌ، والغيابُ ليس رفضاً.")
    return out


# ⛔ **بصمةُ أداةِ الفحص شرطٌ في حكمها** (‏D-175). الإيداعُ `9ffb957` أصلح
#    التبرئةَ الكاذبة، وما قبله لا يشهد. **ولا يُقاس بالزمن**: الساعةُ تكذب
#    (‏فروقُ مناطق، وآلاتٌ تُشغّل نسخةً قديمةً بعد الإصلاح)، **والبصمةُ لا تكذب**.
OPENERS_FIX_COMMIT = "9ffb957"
OPENERS_TRUSTED = set()                # يُملأ من `git log` عند أوّل سؤال


def openers_tool_ok(op):
    """أصدر هذا الحكمَ فاحصٌ **بعد** إصلاح التبرئة الكاذبة؟

    ⛔ **والتعذّرُ ليس حكماً في الاتجاهين**: إن تعذّر سؤالُ `git` (مستودعٌ
    ناقص، أو تشغيلٌ خارج الشجرة) **لا نُبرّئ الأداةَ المجهولة ولا ندين
    الصحيحة** — بل يُمنع الاعتدادُ بالحكم ويُعاد المسح، **فالمسحُ رخيصٌ
    والتبرئةُ الكاذبة غالية**.
    """
    if not isinstance(op, dict):
        return False
    c = str(op.get("commit") or "").strip()
    if not c:
        return False                   # حكمٌ بلا بصمةِ أداةٍ لا يشهد
    global OPENERS_TRUSTED             # noqa: PLW0603
    if not OPENERS_TRUSTED:
        import subprocess
        try:
            out = subprocess.run(
                ["git", "-C", str(Path(__file__).resolve().parents[2]), "log",
                 "--format=%h", f"{OPENERS_FIX_COMMIT}..HEAD"],
                capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=60)
            if out.returncode == 0:
                OPENERS_TRUSTED = {x.strip() for x in out.stdout.split() if x.strip()}
                OPENERS_TRUSTED.add(OPENERS_FIX_COMMIT)
        except Exception:              # noqa: BLE001
            OPENERS_TRUSTED = set()
    if not OPENERS_TRUSTED:
        # ⛔ **لا تُبرَّأ أداةٌ بلا سندٍ مقيس** — لكنّ السؤالَ قد يتعذّر لسببٍ
        #    بنيويٍّ لا شكَّ فيه: هذا الملفّ يُنسخ إلى مستودع الأسطول، و
        #    `9ffb957` من تاريخ `QuranRafiq` **لا وجودَ له هناك** ⇒ يُردّ كلُّ
        #    حكمِ مطالعَ صحيحٍ كذباً، **فيجمد النشرُ كلُّه في السحابة** (وقع
        #    2026-09-11: `sultani_douri` رُدّ بأداةٍ سليمة). ⇒ السندُ يُولَّد من
        #    تاريخ `QuranRafiq` نفسِه ويُودَع ملفّاً، فلا يُستبدل قياسٌ بظنّ.
        f = Path(__file__).with_name("openers_trusted.txt")
        if f.exists():
            OPENERS_TRUSTED = {x.strip() for x in
                               f.read_text(encoding="utf-8").split() if x.strip()}
    if not OPENERS_TRUSTED:
        return False                   # تعذّرَ السؤال ⇒ لا اعتداد، ويُعاد المسح
    return any(c.startswith(t) or t.startswith(c) for t in OPENERS_TRUSTED)


def openers_map(reports_iter):
    """أحدثُ فحص مطالع لكل بصمة — شرطٌ **سابقٌ** للعيّنة لا بديلٌ عنها.

    عيّنة 7e العنقودية على `s_alquraishi` **لم تسحب واحداً** من مطالعه الخمسة
    المعطوبة، وفحصُ المطالع أمسك الخمسة في دقائق. ⇒ صنفان من العطب لكلٍّ
    أداتُه: المطالعُ تكشف ما لا تراه العيّنة، والعيّنةُ تقيس ما لا يمسّه
    فحصُ المطالع.
    """
    best = {}
    for _name, rep in reports_iter:
        if str(rep.get("kind") or "").strip().lower() != "openers":
            continue
        sha = rep.get("sha256")
        if not sha:
            continue
        cur = best.get(sha)
        # ‏`openers_scan.py` يكتب زمنه في `at` لا `ts` — فيُقرأ الاثنان.
        if cur is None or _when(rep) > _when(cur):
            best[sha] = rep
    return best


def _when(rep):
    return float(rep.get("ts") or rep.get("at") or 0)


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
        if not is_ci(rep) or not has_audio_sample(rep):
            continue
        sha = rep.get("sha256")
        if not sha:
            continue
        cur = best.get(sha)
        if cur is None or (rep.get("ts") or 0) > (cur.get("ts") or 0):
            best[sha] = rep
    return best


def has_audio_sample(rep):
    """أحكمٌ صوتيٌّ حقيقيّ؟ — **بما في الملفّ نفسه لا بما يقوله عنه غيرُه**.

    ⛔ وجد github-7e على الدلو ملفّاً يُعلن `kind: "audio"` و`source: "ci"`
    وليس فيه عيّنة، بل حقلُ `verdict_file` يشير إلى ملفٍّ آخر — **وذاك الآخر
    حكمٌ بنيويّ بلا عيّنة**. فبوابةٌ تتبع المؤشِّر تحسبه شاهداً صوتياً ثانياً
    لا وجود له: «ثقةٌ مضاعفة بلا دليلٍ مضاعف». ⇒ **المؤشِّر يصف نفسه لا
    موصوفَه**، ولا يُحتسب حكماً إلا ما حمل عيّنته في جوفه.
    """
    if rep.get("verdict_file"):
        return False                       # مؤشِّرٌ لا حكم
    if str(rep.get("kind") or "").strip().lower() in ("structural", "openers"):
        # ⛔ **فحصُ المطالع ليس عيّنة** (‏إعلان github-7e): يمرّ على المطالع
        # كلِّها ولا يقيس الحدود الداخلية البتّة. فيصلح شاهداً على **رفضٍ**
        # وحده، ومن عدّه بديلاً عن العيّنة رقّى فهرساً لم تُقَس حدودُه.
        return False
    sample = rep.get("sample")
    if not isinstance(sample, dict) or not sample:
        return False
    rows = sample.get("rows")
    if isinstance(rows, list) and not rows:
        return False                       # عيّنةٌ فارغة ليست عيّنة
    return True


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
        if not has_audio_sample(rep) or rep.get("band") is not None:
            continue
        if is_ci(rep):
            continue        # شاهدٌ مُعاضِد لا ممثِّل — ‏`ci_map` موضعُه

        key = rep.get("key")
        cur = best.get(key)
        if cur is None or (rep.get("ts") or 0) > (cur[1].get("ts") or 0):
            best[key] = (name, rep)
    return list(best.values())


def corroboration(rep, ci):
    """وصفُ علاقة الحكمين — **متى يكون الاتفاق شهادتين ومتى يكون تكراراً**.

    تنبيه github-7e (‏2026-09-02، وقد أصلح شفرته عليه): بذرةُ العيّنة كانت
    تُشتقّ من هويّة القارئ وحدها، فيسحب هو وCI **الحدود المئتين نفسها**.
    واتفاقُهما حينئذٍ **إعادةُ قياسٍ لا شهادتان**: يكشف التقلّب والعطب العابر،
    ولا يكشف **خطأ المنهج** — إذ يخطئ المساران الخطأ نفسه على الحدود نفسها.
    وبرهانُ الليلة أنّ محرّكاً واحداً برّأ 211 مطلعاً بالغلط، وتكرارُ القياس
    ألفاً يعيد البراءة ألفاً. ⇒ الاتفاق لا يُحتسب إلا باختلاف `sample.seedSalt`،
    والحكمان بمحرّكين مختلفين (`engine`) **لا يُقارَنان** أصلاً.
    """
    a = ((rep.get("sample") or {}).get("seedSalt"), rep.get("engine"))
    b = ((ci.get("sample") or {}).get("seedSalt"), ci.get("engine"))
    bits = []
    if a[0] is not None and a[0] == b[0]:
        bits.append("‏بملحِ بذرةٍ واحد (تكرارُ قياسٍ لا شهادتان)")
    elif a[0] is None or b[0] is None:
        bits.append("‏بملحِ بذرةٍ غير معلوم")
    if a[1] and b[1] and a[1] != b[1]:
        bits.append(f"وبمحرّكين مختلفين ({a[1]} ≠ {b[1]}) — لا يُقارَنان")
    return (" — " + "، ".join(bits)) if bits else ""


def ci_all_map(reports_iter):
    """كل أحكام CI بعيّنتها **لكل بصمة ولكل ملح**: ‏{البصمة: {الملح: أحدثُ حكم}}.

    ‏`ci_map` يعطي أحدث حكمٍ للبصمة، وهذا يعطي أحدث حكمٍ **لكل ملحٍ** — فهو
    ما تُبنى عليه الشهادتان (‏D-090).
    """
    out = {}
    for _name, rep in reports_iter:
        if not is_ci(rep) or not has_audio_sample(rep) or rep.get("band") is not None:
            continue
        sha = rep.get("sha256")
        salt = (rep.get("sample") or {}).get("seedSalt")
        if not sha or not salt:
            continue                       # ملحٌ غير معلوم لا يشهد (القاعدة 3)
        cur = out.setdefault(sha, {}).get(salt)
        if cur is None or _when(rep) > _when(cur):
            out[sha][salt] = rep
    return out


CI_PAIR_SOURCE = "ci-pair"


def ci_pair_reps(reports_iter, human_keys=()):
    """حكمان من CI **متفقان على القبول** بملحي بذرةٍ مختلفين ومحرّكٍ واحد على
    البصمة نفسها ⇒ ممثِّلٌ مركَّب يمرّ بالبوابة كاملةً (‏D-090).

    القاعدة 3 في README تقول: «حكم 7e وحده أو حكمان متفقان، ولا يُحتسب الاتفاق
    شهادتين إلا باختلاف `seedSalt`». ومحرّك CI هو محرّك 7e نفسه (‏`ci_run.py`)،
    فحكمان من CI بملحين مختلفين **عيّنتان مستقلّتان بمنهجٍ واحد** — وهو عين ما
    تطلبه القاعدة. ⛔ **ولا يُركَّب شيء إن كان على البصمة حكمُ CI مخالف بأي
    ملح** (تعارضٌ يُوقف)، ولا لمفتاحٍ له حكمُ إنسانٍ بعيّنة (‏فذاك ممثِّله).

    والممثِّل المركَّب **يحمل الحكمين معه** (‏`corroborated`) ولا يدّعي أنه
    حكمُ إنسان: ‏`source = "ci-pair"`. ويُعاد كلُّ حكمٍ منهما مرشّحاً على حدة
    (بترتيب الأحدث) لأن حرّاس المجال (القاعدتان 6 و7) تقيس **عيّنةً بعينها**:
    عيّنةٌ بمجالٍ صفريّ تُردّ وحدها، وشقيقتُها بمجالٍ حقيقيّ تمرّ بدليلها.
    """
    out = []
    human = set(human_keys)
    for sha, by_salt in ci_all_map(reports_iter).items():
        reps = sorted(by_salt.values(), key=_when, reverse=True)
        if len(reps) < 2:
            continue
        key = reps[0].get("key")
        if key in human:
            continue
        bad = [r for r in reps if r.get("verdict") != ACCEPTED]
        if bad:
            continue                       # الخلاف يُوقف — يُقال في البوابة
        engines = {r.get("engine") for r in reps if r.get("engine")}
        if len(engines) > 1:
            continue                       # محرّكان لا يُقارَنان (القاعدة 3)
        salts = [(r.get("sample") or {}).get("seedSalt") for r in reps]
        runs = [r.get("runId") or (r.get("provenance") or {}).get("run_id") for r in reps]
        pooled = pooled_zero(reps)
        if pooled is not None:
            # **D-092**: زوجٌ كلاهما صفر عطب وكلٌّ ≥ الحد الأدنى المشتق ⇒ ممثِّلٌ واحد
            # بمجالٍ مشترك = قاعدة الثلاثة على المجموع — لا «0.0%» أبداً.
            out.append((f"ci-pair-pooled:{sha[:8]}", dict(
                reps[0], source=CI_PAIR_SOURCE, pooled=pooled,
                sample=dict(reps[0].get("sample") or {}, severe=[0, pooled["n"], [0.0, 0.0, pooled["hi"]]]),
                severeRate={"rate": 0.0, "lo": 0.0, "hi": pooled["hi"]},
                corroborated={"salts": salts, "runs": runs, "engine": next(iter(engines), None), "n": len(reps)})))
            continue
        for r in reps:
            rep = dict(r, source=CI_PAIR_SOURCE,
                       corroborated={"salts": salts, "runs": runs,
                                     "engine": next(iter(engines), None),
                                     "n": len(reps)})
            out.append((f"ci-pair:{sha[:8]}:{(r.get('sample') or {}).get('seedSalt')}", rep))
    return out


def pooled_zero(reps):
    """‏D-092 (إذن المشرف github-5a، 2026-09-03): زوجُ D-090 كلاهما **صفر عطب** وكلُّ
    عيّنةٍ ≥ الحدّ الأدنى المشتقّ (59 عند 5%) ⇒ مجالٌ مشترك بقاعدة الثلاثة على
    المجموع: الحدّ الأعلى = 3/(n1+n2). **والقاعدة 6 باقية لكل حكمٍ منفرد**: عيّنةٌ
    واحدة بمجالٍ صفري تُردّ؛ وعيّنتان مستقلّتان بملحين مجموعُهما 400 حدٍّ بلا عطب
    تقولان «≤ 0.75%» لا «0%». يُرجع {n, hi, parts} أو None."""
    n_min = _min_sample(SEVERE_CEILING)
    parts = []
    for r in reps:
        sv = (r.get("sample") or {}).get("severe")
        if not (isinstance(sv, list) and len(sv) >= 2 and isinstance(sv[1], int)):
            return None
        if sv[0] != 0 or sv[1] < n_min:
            return None
        parts.append(sv[1])
    if len(parts) < 2:
        return None
    n = sum(parts)
    return {"n": n, "hi": 3.0 / n, "parts": parts, "rule": "D-092"}


POOLED_SOURCE = "pooled"


def _cp_upper(m, n, conf=0.95):
    """الحدُّ الأعلى لكلوبر–بيرسون (‏أحاديُّ الجانب) لنسبةٍ ثنائية.

    ⛔ **ولمَ كلوبر–بيرسون لا ويلسون هنا:** التجميع يجمع عيّناتٍ صغيرةً بأعطابٍ
    قليلة، وويلسون تقريبٌ يضيق تحت هذه الحال فيعطي ثقةً ليست في الدليل. وكلوبر
    –بيرسون **محافظ**: يضمن التغطية ولا يدّعيها. ونحن نرقّي على **الحدّ
    الأعلى** (‏D-068) — فالمحافظُ هو الصحيح، والضيقُ الكاذب يُرقّي معيباً.

    ‏`p_hi` هو حلُّ ‏`P(X ≤ m | n, p) = 1 - conf`. يُحسب بالانصاف على دالة
    التوزيع التراكمي (‏بـ`lgamma` فلا ينهار على n كبير). وعند `m = 0` يعطي
    `1 - conf**(1/n)` ≈ `3/n` — **فقاعدة الثلاثة (‏D-092) حالةٌ خاصّةٌ منه لا
    قاعدةٌ أخرى**.
    """
    import math
    if n <= 0:
        return None
    if m >= n:
        return 1.0
    alpha = 1.0 - conf

    def cdf(p):
        if p <= 0.0:
            return 1.0
        if p >= 1.0:
            return 0.0
        tot = 0.0
        for k in range(m + 1):
            lc = (math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)
                  + k * math.log(p) + (n - k) * math.log1p(-p))
            tot += math.exp(lc)
        return tot

    lo, hi = 0.0, 1.0
    for _ in range(200):                    # انصافٌ ثابتُ العدد — لا حلقة مفتوحة
        mid = (lo + hi) / 2.0
        if cdf(mid) > alpha:
            lo = mid
        else:
            hi = mid
    return hi


def pooled_samples(reps):
    """‏**D-098** (إذن المشرف github-5a، 2026-09-03) — تعميمُ D-092 من «الصفر» إلى
    أيّ عددِ أعطاب: عيّناتٌ **مستقلّة** على البصمة نفسها بملوحٍ مختلفة ومحرّكٍ
    واحد تُجمَّع، فالعطبُ المجمَّع `Σm / Σn` وحدُّه الأعلى بكلوبر–بيرسون.

    ⛔ **وشرطُ الاستقلال هو الملح لا المصدر:** عيّنتان بملحٍ واحدٍ من آلتين
    تعيدان القياس نفسه وتضاعفان الثقة **بلا دليل** — «اختلافُ الملح يزيد
    الدليل، واختلافُ المحرّك يُبطل المقارنة» (github-7e). فالمفتاح `seedSalt`،
    والمحرّكُ يجب أن يكون واحداً.

    ⛔ **وكلُّ عيّنةٍ ≥ الحدّ الأدنى المشتقّ** (‏59 عند 5%): التجميعُ يزيد الدليل
    ولا يخلقه، ومن جمع عشرَ عيّناتٍ من عشرةٍ لم يبلغ ما تبلغه عيّنةٌ من مئة —
    لأنّ العيّنة الصغيرة لا تقع على العطب أصلاً (‏القاعدة 7 في README البوابة).

    ⛔ **ومرفوضٌ صريحٌ منفردٌ تقديرُه ≥ العتبة يمنع التجميع كلَّه**: التجميعُ
    يُوسّط، والوسطُ يبتلع رفضاً قائماً على دليله. **والخلافُ يُفصل ولا يُذوَّب.**

    يُرجع `{m, n, rate, hi, parts, salts, engine, rule}` أو `None`.
    """
    n_min = _min_sample(SEVERE_CEILING)
    by_seed, engines, dissent, dropped = {}, set(), [], []
    for r in reps:
        sv = (r.get("sample") or {}).get("severe")
        # ⛔ **هويّةُ العيّنة ملحُها، وللمحلّيّ ملحُه هو مصدرُه.** أداةُ 7e
        #    المحلية تُشغَّل بلا `--seed-salt` فيأتي الملحُ فارغاً، فتُردّ
        #    عيّنتُها بقاعدة «ملحٌ غير معلوم لا يشهد» — **وهي أقوى شهادةٍ
        #    عندنا**. وبذرتُها الافتراضية مختلفةٌ عن بذور CI الممْلوحة بالبناء،
        #    فاستقلالُها قائم. ⇒ يُسمّى ملحُها `local`، ويبقى الفارغُ من مصدرٍ
        #    غيرِ محلّيٍّ **مردوداً كما كان** (‏فهناك الملحُ هو ما يميّز).
        salt = (r.get("sample") or {}).get("seedSalt")
        if not salt and source_of(r) == "local":
            salt = "local"
        if not (isinstance(sv, list) and len(sv) >= 2
                and isinstance(sv[0], int) and isinstance(sv[1], int)):
            return None
        if not salt or sv[1] < n_min:
            return None                    # ملحٌ مجهول أو عيّنةٌ دون الحدّ
        est = sv[0] / sv[1] if sv[1] else None
        if r.get("verdict") != ACCEPTED and est is not None and est >= SEVERE_CEILING:
            dissent.append({"salt": salt, "m": sv[0], "n": sv[1], "rate": est,
                            "verdict": r.get("verdict")})
        if r.get("engine"):
            engines.add(r["engine"])
        # ⛔ **D-172 — الهويّةُ البذرةُ الفعلية لا اسمُ الملح.** التسميةُ `local`
        #    أعلاه **وسمٌ يُلصق وقتَ القراءة**، والعيّنةُ سُحبت ببذرة الملحِ
        #    الفارغ. فلو شُغّلت الأداةُ المحلية مرّةً بـ`--seed-salt local`
        #    — وهو أوّلُ ما يخطر لمن قرأ الاسم — لسحبت عيّنةً **مستقلّةً حقاً**
        #    (‏البذرة `sha256(riwaya/reciterId/salt)`، و`.../local` ≠ `.../""`)
        #    وحملت **الاسمَ نفسه**، فتتصادمان على مفتاحٍ واحدٍ فتُطرح إحداهما
        #    صامتة. **والأثرُ أخبثُ من فقدِ شاهد:** `n` ينقص فيتّسع الحدُّ
        #    الأعلى، **فينقلب مقبولٌ ممتنعاً بلا سطرِ تحذير**.
        #    ⇒ الفهرسةُ بـ`sample.seed`، والملحُ يبقى **وصفاً للقارئ**؛
        #    واتّحادُ البذرتين إعادةُ قياسٍ يُبقى أحدثُها (‏وهو الصواب).
        ident = (r.get("sample") or {}).get("seed") or f"salt:{salt}"
        cur = by_seed.get(ident)
        if cur is None or _when(r) > _when(cur):
            if cur is not None:
                # ⛔ لا يُطرح شاهدٌ صامتاً بحال: كلُّ طرحٍ يُطبع بسببه مع الحكم.
                dropped.append({"seed": ident, "salt": salt,
                                "reason": "بذرةٌ متّحدة — إعادةُ قياسٍ، يُبقى أحدثُها"})
            by_seed[ident] = r
        else:
            dropped.append({"seed": ident, "salt": salt,
                            "reason": "بذرةٌ متّحدة — إعادةُ قياسٍ، يُبقى أحدثُها"})
    if len(by_seed) < 2 or len(engines) > 1:
        return None
    parts = [((x.get("sample") or {}).get("severe")) for x in by_seed.values()]
    m = sum(int(x[0]) for x in parts)
    n = sum(int(x[1]) for x in parts)
    rate = (m / n) if n else None
    # ⛔ **D-109 — الخلافُ يُفصل ولا يُذوَّب، وفصلُه بدليلٍ رابعٍ لا بتليين القاعدة.**
    #    الأصلُ أنّ رفضاً صريحاً واحداً يمنع التجميع (‏D-098). ورُفع المنعُ في
    #    حالةٍ واحدةٍ **بشروطٍ أربعةٍ مجتمعة** (قرار المشرف github-5a):
    #      (١) **أربعةُ ملوحٍ فأكثر** — أي أنّ خلافاً واحداً يُقابله ثلاثةُ شهود؛
    #      (٢) **رافضٌ واحدٌ لا أكثر** — الرافضان اتفاقٌ لا شذوذ؛
    #      (٣) **تقديرُ الرافض دون ضِعف التقدير المجمَّع** — فالفرقُ الكبير
    #          **إشارةُ تكتّلٍ حقيقيّ** لا ضجيجَ عيّنة، والنسبةُ عمياءُ عن التكتّل
    #          (‏درسُ `shamrani`: 0.2% نقصاً ومنها سورةٌ كاملة)؛
    #      (٤) **وتناثرُ الأعطاب مشروطٌ قبل ذلك كلِّه** — يُفحص خارج الأداة:
    #          إن تكتّلت أعطابُ الرافض في سورةٍ أو سورتين فهو **عيبٌ موضعيٌّ
    #          حقيقيّ** يُحال إلى مسار الإصلاح، **ولا يُجمَّع أصلاً**.
    #    ⛔ والرافضُ **يُذكر في سطر التجميد شاهدَ خلاف** — فالسكوتُ عنه يجعل
    #       الترقية تُقرأ إجماعاً وهي ليست إجماعاً.
    # ⭐ **D-185 (المشرف github-op، 2026-09-04) — التناثرُ المقيسُ يفصل الخلاف،
    #    والقاعدةُ لا تُصبح لا-رتيبةً فتعاقبَ على كثرة الدليل.**
    #    قِيس الليلة: زيادةُ الملوح على مرشّحٍ حقيقيُّ عطبِه ≈3.6% **تزيد عددَ
    #    الرافضين** — لأن عيّنةَ 200 عند 3.6% تتجاوز 5% بالضجيج وحده مرّةً من
    #    ثلاث. فشرطُ «رافضٌ واحدٌ لا أكثر» يجعل **الدليلَ الأكثرَ أسوأ حالاً من
    #    الأقل**، وهذا انقلابٌ في المعنى لا تشدّدٌ فيه: `bader` (‏3.63% وحدّه
    #    الأعلى 4.76%) و`shaksh` (‏3.63% و4.92%) رُدّا بخمس بذورٍ بعد أن كانا
    #    يمرّان بأربع.
    #    ⛔ **والعتبةُ 5% لم تُمسّ ولا تُمسّ**: الحكمُ يبقى على الحدّ الأعلى
    #    لكلوبر–بيرسون للمجمَّع (‏D-068). الذي رُفع هنا **شرطُ العدد** وحده،
    #    وبديلُه **قياسُ الشرط الرابع من D-109 نفسه داخل الأداة** بدل تركه
    #    للفحص خارجها: التكتّلُ هو المانع، لا كثرةُ الرافضين.
    #    الشروط مجتمعةً: (١) خمسُ بذورٍ فأكثر · (٢) كلُّ رافضٍ دون ضِعف المجمَّع
    #    · (٣) **تناثرٌ مقيس**: أعطابُ العيّنات في ≥10 سور، ونصيبُ أكثرِ سورتين
    #    ≤40% منها — فالتكتّلُ (‏درسُ `shamrani`) يُردّ كما كان.
    def _scatter(rs):
        sev = {"EARLY_START", "LATE_START", "WRONG_AYAH"}
        surs = {}
        for r in rs:
            for row in ((r.get("sample") or {}).get("rows") or []):
                if row.get("verdict") in sev:
                    try:
                        sid = int(str(row.get("aid", "0:0")).split(":")[0])
                    except Exception:                     # noqa: BLE001
                        continue
                    surs[sid] = surs.get(sid, 0) + 1
        tot = sum(surs.values())
        if not tot or len(surs) < 10:
            return None
        top2 = sum(sorted(surs.values(), reverse=True)[:2]) / tot
        return {"surahs": len(surs), "top2Share": top2, "defects": tot}

    scatter = None
    if dissent:
        ok_one = (len(by_seed) >= 4 and len(dissent) == 1 and rate is not None
                  and dissent[0]["rate"] < 2 * rate)
        if not ok_one:
            scatter = _scatter(list(by_seed.values()))
            spread = (scatter is not None and scatter["top2Share"] <= 0.40)
            if not (len(by_seed) >= 5 and rate is not None and spread
                    and all(d["rate"] < 2 * rate for d in dissent)):
                return None
    hi = _cp_upper(m, n)
    if hi is None:
        return None
    out = {"m": m, "n": n, "rate": rate, "hi": hi,
           "parts": [[int(x[0]), int(x[1])] for x in parts],
           "salts": sorted({((x.get("sample") or {}).get("seedSalt")
                             or ("local" if source_of(x) == "local" else "?"))
                            for x in by_seed.values()}),
           "seeds": len(by_seed),
           "engine": next(iter(engines), None),
           "rule": ("D-185" if (dissent and scatter) else
                    ("D-109" if dissent else "D-098"))}
    if dissent:
        out["dissent"] = dissent
    if scatter:
        out["scatter"] = scatter
    if dropped:
        out["dropped"] = dropped
    return out


def sampling_skip_reason(key, reports, holds=(), frozen=()):
    """**هل تستحقُّ هذه البصمةُ عيّنةً صوتيةً جديدة؟** يُرجع سببَ التخطّي أو `None`.

    ⛔ **مصدرٌ واحدٌ للقاعدة** (‏قرار المشرف github-5a، 2026-09-03): كانت هذه
    الشروطُ مكتوبةً في `flood_loop` وغائبةً عن ماسح مسار Cloud Build، فكاد
    يُنفق خمسَ ساعاتِ حوسبةٍ على ستّةِ فهارسَ **مرفوضةٍ بنيوياً بشاهدين**.
    **والقاعدةُ الموجودةُ في أداةٍ والغائبةُ عن أختها ليست قاعدةً — هي عادةُ
    أداة.** ⇒ من أراد أن يُنفق عيّنةً فليسأل هنا.

    ⛔ **والمرفوضُ بنيوياً كالمحجوز تماماً:** `_verdict` يُرجع «خلل بنيوي»
    **قبل أن يُنظر في النسبة أصلاً**، فالبذرةُ لا تمسّ حكمَه البتّة — وعلّتُه
    محتوىً (سورةٌ غائبة · بسملةٌ مبتلعةٌ مؤكَّدة) لا تُصلحها عيّنةٌ أخرى.
    **والعيّنةُ عنقُنا، فلا تُنفَق على حكمٍ معلوم.**
    """
    riw = key.split("/")[1] if key.count("/") >= 2 else ""
    rid = key.split("/")[-1].split(".")[0]
    target = f"timings/{riw}/{rid}.jz"
    if key.startswith("timings-staging/tmp/"):
        return "مفتاحُ تجربة"
    if ".partial" in key:
        return "لقطةٌ جزئية — لا تُرقّى فلا تُقاس"
    if target in set(holds):
        return "محجوز"
    if target in set(frozen):
        return "الهدفُ مجمَّد"
    for rep in reports:
        v = str(rep.get("verdict") or "")
        if v.startswith("مرفوض") or rep.get("fatal"):
            return f"مرفوضٌ سلفاً: {v[:60] or 'خلل بنيوي'}"
    return None


def pooled_reps(reports_iter, accepted_keys=()):
    """ممثِّلو **التجميع** (‏D-098): لكلّ بصمةٍ عيّناتُها المستقلّة مجموعةً.

    ⛔ **ولا يُنشأ إلا لمفتاحٍ ليس له ممثِّلٌ مقبولٌ سلفاً**: التجميعُ بابٌ
    للحدّيّ الذي لم يبلغ وحدَه، لا طريقٌ ثانٍ لما مرّ. ومن جمّع ما هو مقبولٌ
    أصلاً أنفق حساباً وضاعف السطور بلا أثر.
    """
    acc = set(accepted_keys)
    by_sha = {}
    for _name, rep in reports_iter:
        if not has_audio_sample(rep) or rep.get("band") is not None:
            continue
        sha = rep.get("sha256")
        if not sha or rep.get("source") == CI_PAIR_SOURCE:
            continue                       # الممثِّلُ المركَّب ليس عيّنةً جديدة
        by_sha.setdefault(sha, []).append(rep)
    out = []
    for sha, reps in by_sha.items():
        base = max(reps, key=_when)
        if base.get("key") in acc:
            continue
        pooled = pooled_samples(reps)
        if pooled is None:
            continue
        rate, hi = pooled["rate"], pooled["hi"]
        # **الحكمُ على الحدّ الأعلى** (‏D-068): يُقبل إن كان الحدُّ دون العتبة،
        # ويُرفض إن بلغ **التقديرُ** العتبة، وما بينهما **حدّيٌّ لا يُرقّى**.
        if hi < SEVERE_CEILING:
            verdict = ACCEPTED
        elif rate is not None and rate >= SEVERE_CEILING:
            verdict = f"مرفوض (مجمَّع {rate:.1%} ≥ {SEVERE_CEILING:.0%})"
        else:
            verdict = (f"حدّي (مجمَّع {rate:.1%} والحدّ الأعلى {hi:.1%} "
                       f"> {SEVERE_CEILING:.0%})")
        rep = dict(base, source=POOLED_SOURCE, verdict=verdict, pooled=pooled,
                   sample=dict(base.get("sample") or {},
                               severe=[pooled["m"], pooled["n"], [rate, None, hi]]),
                   severeRate={"rate": rate, "lo": None, "hi": hi})
        out.append((f"pooled:{sha[:8]}:{'+'.join(pooled['salts'])}", rep))
    return out


def pooled_map_of(reports_iter):
    """‏{البصمة: ممثِّلُها المجمَّع} — يُمرَّر إلى `gate` ليفصل التعارضَ بالتجميع
    (‏D-111). **يُبنى من كلّ العيّنات لا من المقبولين وحدهم**، فالفاصلُ إنما
    ينفع حيث لم يُقبل بعد."""
    out = {}
    for _name, rep in pooled_reps(list(reports_iter)):
        sha = rep.get("sha256")
        if sha:
            out[sha] = rep
    return out


def sampled_candidates(reports_iter):
    """ممثِّلو الترقية: أحدثُ حكم إنسانٍ بعيّنة لكل مفتاح، ثم أزواجُ CI (‏D-090)
    للمفاتيح التي لا حكمَ إنسانٍ لها، ثم **المجمَّعون** (‏D-098) لما لم يُقبل بعد.
    **مسارٌ واحد** يقرؤه `main` والراصد."""
    everywhere = list(reports_iter)
    humans = latest_sampled(everywhere)
    pairs = ci_pair_reps(everywhere, {r.get("key") for _n, r in humans})
    ok = {r.get("key") for _n, r in (humans + pairs) if r.get("verdict") == ACCEPTED}
    return humans + pairs + pooled_reps(everywhere, ok)


BORDERLINE_CI_HI = 0.06


def ci_borderline_ok(rep, ci):
    """‏D-093 (قرار المشرف github-5a، 2026-09-03): حكمُ CI **حدّي** — تقديرٌ نقطي دون
    العتبة وحدُّه الأعلى ≤ 6% — **لا يناقض** حكمَ 7e مقبولاً بعيّنة كاملة على البصمة
    نفسها؛ يُرقّى بحكم 7e ويُذكر الحدّي في سطر التجميد. أما مرفوضٌ صريح (تقدير
    ≥ العتبة أو خلل بنيوي) فتناقضٌ يمنع. ⛔ ولا يسري على ممثِّل زوج CI (‏D-090/D-092)
    ولا على حكم CI ممثِّلاً — الإنسانُ وحده يغلب الحدّي.
    """
    if is_ci(rep) or rep.get("source") == CI_PAIR_SOURCE:
        return False
    if not str(ci.get("verdict") or "").startswith("حدّي"):
        return False
    if ci.get("fatal"):
        return False
    rate, _lo, hi = severe_ci(ci)
    if rate is None or hi is None or rate >= SEVERE_CEILING or hi > BORDERLINE_CI_HI:
        return False
    rep["ciBorderline"] = {"verdict": ci.get("verdict"), "rate": rate, "hi": hi,
                           "salt": (ci.get("sample") or {}).get("seedSalt"),
                           "runId": ci.get("runId"), "rule": "D-093"}
    return True


def _swallowed_surahs_from(rep):
    """سورُ «البسملة المبتلعة» المؤكَّدةُ في بلاغات حكمٍ صوتيّ — من `fatal` ومن
    صفوف العيّنة. ⛔ **قراءةُ نصٍّ لا استنتاجُ نيّة**: لا يُلتقط إلا ما صرّح
    بالابتلاع وبرقم السورة، فالبلاغُ الغامض لا يُبنى عليه منع."""
    out = set()
    for txt in (rep.get("fatal") or []):
        t = str(txt)
        if "مبتلع" not in t:
            continue
        m = re.search(r"(\d{1,3})\s*:\s*1", t)
        if m:
            n = int(m.group(1))
            if 1 <= n <= 114:
                out.add(n)
    for row in ((rep.get("sample") or {}).get("rows") or []):
        if "مبتلع" not in str(row.get("why") or ""):
            continue
        aid = str(row.get("aid") or "")
        if aid.endswith(":1") and aid.split(":")[0].isdigit():
            n = int(aid.split(":")[0])
            if 1 <= n <= 114:
                out.add(n)
    return out


def gate(rep, frozen, prefix, holds=None, override=None, ci_reports=None,
         openers_reports=None, pooled_map=None):
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
    # **فحصُ المطالع شرطٌ مستقلٌّ عن العيّنة** (اقتراح github-7e، وقد قِسنا
    # علّته الليلة): العيّنة العنقودية قد لا تقع على مطلعٍ واحد، فصنفُ
    # «البسملة المبتلعة» قد يمرّ سليماً في مئتي حدٍّ ويكون في خمسة مطالع.
    # فمتى حمل الحكمُ نتيجةَ الفحص الكامل، **يُشترط خلوُّها**؛ وغيابُ الحقل
    # لا يمنع اليوم (لا يُشترط ما لم يُنتج بعد) ويُقال في اللوحة.
    op = (openers_reports or {}).get(rep.get("sha256"))
    inline = rep.get("openers")
    if isinstance(inline, dict) and inline.get("defects"):
        bad = inline.get("defects")
        n_bad = len(bad) if isinstance(bad, list) else bad
        return target, (f"فحصُ المطالع الكامل وجد {n_bad} عطباً — "
                        "لا ترقية حتى يُصلَح المصدر")
    if op is not None:
        # ⛔ **حكمُ أداةٍ معطوبةٍ ليس حكماً** (‏D-175): كان الفاحصُ يبرّئ مطلعاً
        #    سمع فيه «بسم الله» لأنّ سماحةَ الحرف تجعل «بسم» تُطابق «طسم»
        #    (‏مطلعا 26 و28). ⇒ **كلُّ `clean` صدر قبل `9ffb957` لا يشهد
        #    بشيء**، وكلُّ فهرسٍ رُقّي اعتماداً عليه مرّ بشرطٍ لم يُستوفَ.
        #    ⛔ **والعطبُ في اتجاه التبرئة لا يُرى**: الحارسُ الذي يُخطئ بالمنع
        #    يشتكي منه صاحبُه فيُكشف، والذي يُخطئ بالتبرئة **يمرّ صامتاً
        #    ويُسجَّل شهادةَ سلامة**. ⇒ الشرطُ يُقرأ من بصمة الأداة لا من
        #    وجود الملف، فيصير الإصلاحُ **قاعدةً دائمةً لا دفعةً يدوية**.
        if not openers_tool_ok(op):
            return target, (
                "فحصُ المطالع صدر عن أداةٍ سابقةٍ لإصلاح التبرئة الكاذبة "
                f"(‏commit={str(op.get('commit'))[:12]} · D-175) — يُعاد المسح")
        # **صيغتان لملفّ المطالع** (‏github-7e يقترح `openers.defects`،
        # و`openers_scan.py` عند github-8e يكتب `swallowed`/`tail`/`suspect`)
        # — تُقرآن معاً ولا يُفترض شكلٌ واحد.
        blob = op.get("openers") if isinstance(op.get("openers"), dict) else {}
        hard = list(blob.get("defects") or []) + list(op.get("swallowed") or [])
        # ⛔ **`suspect` كشفٌ بلا تحقّق** — نصّ github-8e: قد يكون هلوسة نموذج
        # (والبسملة أكثرُ عبارةٍ في بيانات التدريب فهي هلوسته المفضّلة، وقد
        # أثبته بتفريغ 15 ثانية كاملة في `deban_qalun` س37). فلا يُبنى عليه
        # منعٌ ولا قبول، ويُعرض عدداً فقط.
        soft = len(op.get("suspect") or []) + len(op.get("tail") or [])
        # ⛔ **D-110 — `suspect` مع تأكيدٍ مستقلٍّ على السورة نفسها = مؤكَّدٌ يمنع.**
        #    `suspect` وحدَه يبقى بلا أثرٍ كما هو (‏قد يكون هلوسةَ نموذج، والبسملةُ
        #    أكثرُ عبارةٍ في بيانات التدريب فهي هلوسته المفضّلة). **لكنّه ليس
        #    ضجيجاً بالضرورة، بل شاهدٌ يُردّ لأنه وحده** — فمتى جاء شاهدٌ ثانٍ
        #    **مستقلٌّ** (‏بلاغُ بسملةٍ مبتلعةٍ في `fatal` حكمٍ صوتيّ) على **السورة
        #    نفسها**، اجتمع الشاهدان فصار العطبُ مؤكَّداً.
        #    وشاهدُه المقيس: `deban_qalun.7d70c3af` — المطالعُ `swallowed=[]` و
        #    `suspect=[37, 67]`، والعيّنةُ الصوتية أكّدت **67:1** بنصٍّ مسموع
        #    («اصْمِ اللَّهِ الرَّحْمَنِ الرَّحِيمِ تَب»). فالفهرسُ نجا من الترقية
        #    **بحكم الصوت لا بفحص المطالع** — حظٌّ حسنٌ لا تصميم.
        #    ⛔ وهو تشديدٌ لا تليين: لا يُرفع منعٌ قائم، وإنما يُضاف منعٌ لم يكن.
        susp = {int(x) for x in (op.get("suspect") or []) if str(x).isdigit()}
        if susp:
            confirmed = sorted(susp & _swallowed_surahs_from(rep))
            if confirmed:
                return target, (
                    f"بسملةٌ مبتلعةٌ **مؤكَّدةٌ بشاهدين مستقلَّين** في السور "
                    f"{confirmed} — فحصُ المطالع وسمها `suspect` وأكّدها حكمُ "
                    "الصوت (‏D-110)")
        if hard:
            first = hard[0]
            first = (first if isinstance(first, str)
                     else json.dumps(first, ensure_ascii=False))[:90]
            return target, f"فحصُ المطالع وجد بسملةً مبتلعةً متحقَّقة: {first}"
        # ⛔ **الجزئيّ يشهد على الرفض ولا يشهد بالسلامة** (تنبيه github-7e،
        # وقد وجد الثغرة في كاتبه هو): تشغيلةٌ على ستّة مطالع تُخرج ملفاً
        # بالوسم نفسه فتُقرأ شهادةَ سلامة وهي لم تنظر في 106 مطالع.
        # والشرطُ `scope == "full"` لا عددٌ بعينه: قد يخلو فهرسٌ من سورةٍ
        # فيقلّ عدّه وهو كاملُ الفحص.
        if str(op.get("scope") or "").lower() != "full":
            checked = op.get("checked") or (blob or {}).get("count")
            return target, (f"فحصُ المطالع **جزئيّ** (‏scope={op.get('scope')!r}"
                            + (f" · فُحص {checked}" if checked else "")
                            + ") — لا يشهد بسلامة، والشرطُ فحصٌ كامل")
        if op.get("verdict") and op["verdict"] != ACCEPTED:
            return target, f"فحصُ المطالع ردّه: {str(op['verdict'])[:60]}"
        if soft:
            # لا يمنع — لكن يُقال، فالسكوتُ عنه يجعل «مرّ» تُقرأ «لا شيء فيه».
            print(f"  ⚠️ {rep.get('key')}: فحصُ المطالع مرّ، وفيه {soft} "
                  "كشفاً بلا تحقّق (‏suspect/tail) — لا يمنع ولا يُبنى عليه")
    elif openers_reports is not None:
        return target, ("لا فحصَ مطالع على هذه البصمة — وهو شرطٌ سابقٌ "
                        "للعيّنة، والعيّنة لا تضمن الوقوع على مطلعٍ واحد")
    if rep.get("band") is not None:
        return target, f"عيّنة نطاق {rep['band']} — لا تحكم على الفهرس"
    if not rep.get("sha256"):
        return target, "حكمٌ بلا بصمة — أعِد التدقيق"
    if target in frozen:
        return target, ("الهدف مجمَّد — يُرفع بـ`--unfreeze <المفتاح> --reason <السبب>` "
                        "(‏D-183: أمرُ المالك 2026-09-04 — الوكيل يرفعه بنفسه، "
                        "والسببُ المكتوب والسطرُ المشطوب هما الحارس لا يدُ إنسان)")
    # **حكمان لا يتناقضان.** إن وُجد حكمُ CI على **البصمة نفسها** وخالف القبول
    # فالخلافُ يُوقف: اتّفاقُهما شرطُ الترقية حين يوجدان، ولا يُرجَّح أحدهما
    # على الآخر بلا قياسٍ يفصل.
    ci = (ci_reports or {}).get(rep.get("sha256"))
    # (وللممثِّل المركَّب من CI — ‏D-090 — يُشترط اتفاق **كل** أحكام CI على
    #  البصمة بأي ملح، ويُفحص ذلك في `ci_pair_reps` قبل التركيب.)
    # ⛔ **D-111 — التجميعُ فصلٌ، فيسبق إعلانَ التعارض.** «لا ترقية حتى يُفصل»
    #    تطلب **فاصلاً**، والتجميعُ (‏D-098) هو الفاصلُ بعينه: حكمٌ حدّيٌّ من
    #    مئتَي حدٍّ لا يناقض حكماً مقبولاً، **بل يُضاف إليه**. مقيسٌ على
    #    `nabil.c51a9c5b`: ‏7e مقبول 3/200 · ci حدّي 7/200 · ci2 حدّي 9/200
    #    ⇒ المجمَّع **19/600 = 3.17% بحدٍّ أعلى 4.9% ⇒ مقبول** — وكان يُردّ
    #    بـ«تعارض» لأنّ حدَّ ci2 الأعلى 7.2% تجاوز عتبة D-093 (6%).
    #    ⇒ **من ردَّ الدليلَ لأنّ جزءاً منه ضعيفٌ ردَّ الدليلَ كلَّه.**
    # ⛔ **وحدُّه:** لا يسري إن كان في المجموعة **رفضٌ صريح** — `pooled_samples`
    #    يردّه أصلاً (D-098/D-109)، فالخلافُ الحقيقيُّ يبقى موقوفاً.
    if (ci is not None and ci.get("verdict") != ACCEPTED
            and not ci_borderline_ok(rep, ci)
            and (pooled_map or {}).get(rep.get("sha256"), {}).get("verdict") == ACCEPTED):
        ci = None                       # فُصل الخلافُ بالتجميع — لا تعارضَ قائم
    if ci is not None and ci.get("verdict") != ACCEPTED and not ci_borderline_ok(rep, ci):
        return target, (f"تعارضُ حكمين على البصمة نفسها: CI يقول "
                        f"{ci.get('verdict')!r}{corroboration(rep, ci)} — "
                        "لا ترقية حتى يُفصل")
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
    # ⛔ **مجالٌ بعرض صفر ادّعاءُ يقينٍ تامّ من عيّنةٍ محدودة.** وجده github-7e
    # في أداته: المجال محسوبٌ على مستوى العنقود، فإذا انعدم التباين بين
    # العناقيد انهار إلى نقطة — فطُبع «[0.0–0.0]» من 158 حدّاً. **ونحن نرقّي
    # على الحدّ الأعلى**، فصفرٌ كاذبٌ يمرّ حيث يجب أن يمرّ رقمٌ حقيقيّ.
    # وحارسٌ هنا يمسك الصنف كلَّه مهما تغيّرت الأداة.
    if _lo is not None and hi == _lo:
        return target, (f"مجالٌ بعرض صفر [{hi * 100:.2f}–{hi * 100:.2f}] — "
                        "لا يقين تامّ من عيّنة؛ يُعاد حسابه")
    # ⛔ **وعيّنةٌ صغيرة لا تستطيع أن تقول «مقبول» ولو خرجت نظيفة تماماً.**
    # صفرُ أعطابٍ من 200 حدٍّ يعطي حدّاً أعلى 1.5%، ومن 50 يعطي **5.8%**.
    # والحدُّ الأدنى مشتقٌّ لا مختار: أصغرُ ن يجعل الحدّ الأعلى عند صفر أحداثٍ
    # دون العتبة هو ‏`1 − عتبة^(1/ن) < عتبة` (استنتاج github-7e).
    n_min = _min_sample(SEVERE_CEILING)
    n_obs = ((rep.get("sample") or {}).get("severe") or [None, None])[1]
    if isinstance(n_obs, int) and n_obs < n_min:
        return target, (f"عيّنةٌ من {n_obs} حدّاً لا تُغلق عتبة "
                        f"{SEVERE_CEILING * 100:.0f}% مهما نظفت — "
                        f"الحدّ الأدنى المشتقّ {n_min}")
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
    refs = [e.get("fileRef") for e in (idx.get("entries") or [])[:300]]
    refs = sorted({r for r in refs if isinstance(r, str) and r.startswith("http")})
    return catalog_gate_core(idx.get("riwaya"), idx.get("reciterId"), refs, cat)


def catalog_gate_core(riwaya, rid, refs, cat):
    """نواةُ حارس الهويّة — تعمل على **حقائقَ مستخرجة** لا على الفهرس كاملاً.

    ولماذا نواةٌ وغلاف؟ لأن الفرز يعيد الحكم كلَّما تغيّر الحاكم، وتنزيلُ
    أربعين فهرساً في كل مرّة يُبطئ الطابور ويثقل الشبكة. فالحقائق تُحفظ عند
    أوّل قراءة، والحكمُ يُعاد منها — **بالمنطق نفسه لا بنسخةٍ ثانية منه**.
    """
    people = cat.get(riwaya) or {}
    if not people:
        return None                            # رواية بلا كتالوج: لا يُحكم
    row = people.get(rid)
    if row is None:
        owner = next((k for k, v in people.items()
                      if refs and v.get("base")
                      and all(r.startswith(v["base"]) for r in refs)), None)
        return (f"معرّفٌ ليس في كتالوج {riwaya}: {rid!r}"
                + (f" — وصوتُه كلُّه لـ{owner!r}" if owner else ""))
    base = row.get("base")
    if base and refs:
        stray = [r for r in refs if not r.startswith(base)]
        if stray:
            return (f"مصدرُ الصوت لا يطابق قاعدة {rid} في الكتالوج: "
                    f"{stray[0][:80]}")
    return None


def facts_of(idx):
    """حقائقُ الفهرس التي يحكم عليها الحارس — تُستخرج مرّةً وتُخزَّن.

    **لماذا؟** الفرز يعيد الحكم كلّما تغيّرت البوابة، وتنزيلُ أربعين فهرساً
    وفكُّ ضغطها في كل مرّة كلّف الطابور **عشر دقائقَ عمياء** لكل تعديل. فما
    يُقرأ مرّةً لا يُعاد تنزيله ما دامت بصمة الكائن (`ETag`) لم تتغيّر —
    والحكمُ يُعاد **من المنطق نفسه** لا من نسخةٍ ثانية منه.
    """
    tr = idx.get("transform")
    return {
        "riwaya": idx.get("riwaya"), "reciterId": idx.get("reciterId"),
        "entries": len(idx.get("entries") or []),
        "refineVersion": idx.get("refineVersion"),
        "ayahCount": idx.get("ayahCount"),
        "missing": idx.get("missing") if isinstance(idx.get("missing"), dict) else None,
        "hasMissing": isinstance(idx.get("missing"), dict),
        "surahs": sorted({e["ayahId"].split(":")[0]
                          for e in (idx.get("entries") or [])}, key=int),
        "transformOp": tr if isinstance(tr, str) else str((tr or {}).get("op") or ""),
        "refs": sorted({e.get("fileRef") for e in (idx.get("entries") or [])[:300]
                        if isinstance(e.get("fileRef"), str)
                        and e["fileRef"].startswith("http")}),
        "lowCount": idx.get("lowCount"),
    }


def gate_facts(f, cat=None):
    """حكمُ الحارسين (البنية والهويّة) على **الحقائق** — وهو ما يستدعيه الفرز.

    ⛔ ولا يُكرَّر منطقٌ هنا: `index_gate` نفسه يعمل على فهرسٍ مُعادِ التركيب
    من الحقائق، فما يمرّ من أحدهما يمرّ من الآخر حرفاً.
    """
    fake = {"riwaya": f.get("riwaya"), "reciterId": f.get("reciterId"),
            "refineVersion": f.get("refineVersion"),
            "ayahCount": f.get("ayahCount"),
            "missing": f.get("missing") if f.get("hasMissing") else None,
            "transform": f.get("transformOp"),
            "entries": _fake_entries(f)}
    why = index_gate(fake)
    if why or cat is None:
        return why
    return catalog_gate_core(f.get("riwaya"), f.get("reciterId"),
                             f.get("refs") or [], cat)


def _fake_entries(f):
    """مداخلُ صوريّة تحمل **ما يحكم به الحارس فقط**: العدد وحضورُ السور.

    ولا تُستعمل في غير ذلك — فليس فيها أزمنةٌ ولا نطاقات، وأيّ حارسٍ يحتاجها
    يجب أن يعمل على الكائن لا على الحقائق.
    """
    sur = f.get("surahs") or []
    rows = [{"ayahId": f"{s}:1"} for s in sur]
    pad = max(0, int(f.get("entries") or 0) - len(rows))
    filler = sur[0] if sur else "1"
    return rows + [{"ayahId": f"{filler}:2"}] * pad


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
    # **سورةٌ غائبةٌ كلّياً ليست «غياباً قليلاً».** ‏`shamrani` ينقصه 13 مدخلاً
    # (0.2% دون العتبة) — **ومنها سورة 112 كاملةً**. والعتبةُ نسبةٌ، والنسبةُ
    # عمياءُ عن التكتّل: أربعُ آياتٍ متفرّقة عطبٌ صغير، وأربعٌ هي سورةٌ تامّة
    # عطبٌ يراه المستخدم لحظةَ يفتحها. (‏نبّه إليه github-7e، وأمسكه CI صوتياً.)
    # والمُسقَط عمداً بتحويلٍ مسجَّل **يُستثنى**: أثرُه مكتوبٌ في `transform`.
    present = {e["ayahId"].split(":")[0] for e in idx.get("entries", [])}
    # ‏**`transform` يأتي نصّاً أو قاموساً**: كتبه `drop_surah` قاموساً وكتبه
    # github-8e نصّاً — فتُقرأ الصيغتان ولا يُفترض شكلٌ واحد (وقع الافتراض
    # فأسقط الأداة عند أوّل ملفٍّ من صانعٍ آخر).
    tr = idx.get("transform")
    op_txt = tr if isinstance(tr, str) else str((tr or {}).get("op") or "")
    dropped = (set(re.findall(r"\d+", op_txt))
               if op_txt.startswith("drop_surah") else set())
    gone = sorted({str(n) for n in range(1, 115)} - present - dropped,
                  key=int)
    if gone and len(idx.get("entries", [])) > 4000:
        return ("سورٌ غائبةٌ كلّياً: " + "، ".join(gone[:5])
                + (f" (و{len(gone) - 5} غيرها)" if len(gone) > 5 else ""))
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
    # **الشهادتان من CI (‏D-090) تُختبران بحدودهما**: ملحان مختلفان ومحرّكٌ
    # واحد واتفاقٌ على القبول ⇒ ممثِّل؛ وملحٌ واحد أو محرّكان أو مخالفٌ ⇒ لا شيء.
    eng = "pywhispercpp/ggml-q8 (tiny-ar-quran)"
    c1 = dict(rep, source="ci", engine=eng, sample={"seed": 1, "seedSalt": "ci"}, ts=rep["ts"])
    c2 = dict(rep, source="ci", engine=eng, sample={"seed": 2, "seedSalt": "ci2"}, ts=rep["ts"] + 1)
    pair = ci_pair_reps([("a", c1), ("b", c2)])
    if len(pair) != 2 or any(r.get("source") != CI_PAIR_SOURCE for _n, r in pair):
        raise SystemExit("⛔ شهادتا CI بملحين مختلفين لم تُركَّبا ممثِّلاً")
    if ci_pair_reps([("a", c1), ("b", dict(c2, sample={"seed": 2, "seedSalt": "ci"}))]):
        raise SystemExit("⛔ ملحٌ واحد حُسب شهادتين — القاعدة 3 مكسورة")
    if ci_pair_reps([("a", c1), ("b", dict(c2, engine="other"))]):
        raise SystemExit("⛔ محرّكان مختلفان حُسبا شهادتين — القاعدة 3 مكسورة")
    if ci_pair_reps([("a", c1), ("b", dict(c2, verdict="مرفوض"))]):
        raise SystemExit("⛔ حكمان متعارضان رُكِّبا ممثِّلاً")
    if ci_pair_reps([("a", c1), ("b", dict(c2, sample={"seed": 2}))]):
        raise SystemExit("⛔ ملحٌ غير معلوم حُسب شهادة")

    # **المصدر الثالث `cloud-build` (‏D-095)**: يشغّل `ci_run.py` نفسه على آلات
    # Cloud Build بملح `cb`. يُختبر أمران: أنه **يشهد** كأي مصدر CI، وأنّ
    # **البيئة وحدها لا تزيد الدليل** — فحكمان بملحٍ واحدٍ من بيئتين لا يُزاوجان.
    b1 = dict(rep, source="cloud-build", engine=eng,
              sample={"seed": 3, "seedSalt": "cb"}, ts=rep["ts"] + 2)
    if len(ci_pair_reps([("a", c1), ("b", b1)])) != 2:
        raise SystemExit("⛔ حكمُ Cloud Build لم يُزاوج حكمَ Actions بملحٍ مختلف")
    if ci_pair_reps([("a", c1), ("b", dict(b1, sample={"seed": 3, "seedSalt": "ci"}))]):
        raise SystemExit("⛔ بيئتان بملحٍ واحد حُسبتا شهادتين — البيئةُ ليست ملحاً")
    if ci_pair_reps([("b", b1)]):
        raise SystemExit("⛔ حكمُ Cloud Build وحده رُكِّب ممثِّلاً — ولا ترقية بحكم CI منفرد")

    # **التجميع (‏D-098)** — تعميمُ D-092 من الصفر إلى أيّ عددِ أعطاب.
    # ⛔ **البذرةُ تُشتقّ من الملح كما في `run.py`** (`sha256(riwaya/id/salt)`)
    #    لا تُثبَّت على 1: تثبيتُها كان يُخفي عطبَ D-172 لأنّ كلّ العيّنات
    #    تتصادم فيبدو الجمعُ صحيحاً بالمصادفة. **والاختبارُ يحاكي المنتَج.**
    def _seed_of(salt):
        return int(hashlib.sha256(f"tmp/selftest/{salt}".encode()).hexdigest()[:8], 16)

    def _rp(salt, m, n, verdict=ACCEPTED, engine=eng, src="ci", seed=None):
        return dict(rep, source=src, engine=engine, verdict=verdict,
                    sample={"seed": _seed_of(salt) if seed is None else seed,
                            "seedSalt": salt, "severe": [m, n, [m / n, 0.0, 0.9]]},
                    ts=rep["ts"])
    #  (١) مثالُ twfeeq: 7e‏ 7/200 (3.5%) + cb‏ 8/400 (2.0%) ⇒ 15/600 = 2.5%
    pl = pooled_samples([_rp("local", 7, 200, src="local"), _rp("cb", 8, 400)])
    if pl is None or pl["n"] != 600 or pl["m"] != 15:
        raise SystemExit("⛔ التجميع لم يجمع عيّنتين مستقلّتين")
    if not (0.024 < pl["rate"] < 0.026 and pl["hi"] < SEVERE_CEILING):
        raise SystemExit(f"⛔ حدُّ التجميع خارج المتوقَّع: {pl}")
    #  (٢) ملحٌ واحدٌ من بيئتين لا يُجمَّع — الاستقلالُ بالملح لا بالآلة
    if pooled_samples([_rp("ci", 7, 200), _rp("ci", 8, 400)]) is not None:
        raise SystemExit("⛔ ملحٌ واحد جُمِّع — الاستقلالُ بالملح لا بالمصدر")
    #  (٣) محرّكان لا يُجمَّعان
    if pooled_samples([_rp("ci", 7, 200), _rp("cb", 8, 400, engine="other")]) is not None:
        raise SystemExit("⛔ محرّكان جُمِّعا")
    #  (٤) عيّنةٌ دون الحدّ الأدنى تُبطل التجميع (‏التجميعُ يزيد الدليل ولا يخلقه)
    if pooled_samples([_rp("ci", 0, 10), _rp("cb", 8, 400)]) is not None:
        raise SystemExit("⛔ عيّنةٌ دون الحدّ الأدنى دخلت التجميع")
    #  (٥) مرفوضٌ صريحٌ بتقديرٍ ≥ العتبة يمنع — الخلافُ يُفصل ولا يُذوَّب
    if pooled_samples([_rp("ci", 20, 200, verdict="مرفوض"), _rp("cb", 0, 400)]) is not None:
        raise SystemExit("⛔ رفضٌ صريحٌ ذُوِّب في متوسّطٍ مقبول")
    #  (٦) وقاعدةُ الثلاثة (‏D-092) حالةٌ خاصّةٌ من كلوبر–بيرسون لا قاعدةٌ أخرى
    z = pooled_samples([_rp("ci", 0, 200), _rp("cb", 0, 400)])
    if z is None or not (abs(z["hi"] - 3.0 / 600) < 0.0005):
        raise SystemExit(f"⛔ صفرُ الأعطاب لا يوافق قاعدة الثلاثة: {z}")
    #  (٧) **D-172 — الهويّةُ البذرةُ لا الاسم**: اسمان متّحدان ببذرتين
    #      مختلفتين شاهدان مستقلّان يُعدّان معاً؛ ولو فُهرس بالاسم لطُرح
    #      أحدُهما صامتاً فنقص `n` واتّسع الحدُّ **فانقلب مقبولٌ ممتنعاً**.
    same_name = pooled_samples([_rp("local", 7, 200, src="local", seed=11),
                                _rp("local", 8, 400, src="local", seed=22)])
    if same_name is None or same_name["n"] != 600 or same_name["m"] != 15:
        raise SystemExit(f"⛔ D-172: اسمٌ واحدٌ ببذرتين لم يُعدّ شاهدين: {same_name}")
    #      وبذرةٌ متّحدة إعادةُ قياسٍ يُبقى أحدثُها — **ويُطبع سببُ الطرح**
    dup = pooled_samples([_rp("ci", 7, 200), _rp("cb", 8, 400),
                          dict(_rp("cb", 9, 400), ts=rep["ts"] + 5)])
    if dup is None or dup["n"] != 600 or dup["m"] != 16 or not dup.get("dropped"):
        raise SystemExit(f"⛔ D-172: بذرةٌ متّحدة لم تُعامَل إعادةَ قياسٍ معلَنة: {dup}")
    print("  ✅ D-098: تجميعُ عيّناتٍ بملوحٍ مختلفة بكلوبر–بيرسون؛ والملحُ الواحد "
          "والمحرّكان والعيّنةُ الصغيرة والرفضُ الصريح تمنع؛ وصفرُ الأعطاب = 3/n؛ "
          "وD-172: الاسمُ الواحدُ ببذرتين شاهدان، والبذرةُ المتّحدةُ إعادةُ قياسٍ معلَنة")

    # **D-109** — رفعُ منعِ الرافض الواحد بشروطٍ أربعة.
    #  حالةُ `yousef` الحقيقية: cb 10/400 · ci 5/200 · ci2 **12/200 مرفوض** ·
    #  ورابعٌ cb2 10/400 ⇒ المجموع 37/1200 = 3.08%، وضِعفُه 6.17% > 6.00%.
    four = [_rp("cb", 10, 400), _rp("ci", 5, 200),
            _rp("ci2", 12, 200, verdict="مرفوض (عطبٌ جسيم 6.0% > 5%)"),
            _rp("cb2", 10, 400)]
    d100 = pooled_samples(four)
    if d100 is None or d100.get("rule") != "D-109" or not d100.get("dissent"):
        raise SystemExit(f"⛔ D-109: أربعةُ ملوحٍ برافضٍ واحدٍ دون الضِّعف لم تُجمَّع: {d100}")
    if d100["n"] != 1200 or d100["m"] != 37:
        raise SystemExit(f"⛔ D-109: المجموع خاطئ: {d100}")
    #  (١) ثلاثةُ ملوحٍ فقط ⇒ لا رفعَ للمنع (الشرط: أربعةٌ فأكثر)
    if pooled_samples(four[:3]) is not None:
        raise SystemExit("⛔ D-109: ثلاثةُ ملوحٍ رفعت المنع — الشرطُ أربعة")
    #  (٢) رافضان ⇒ اتفاقٌ لا شذوذ، فيمنعان
    two_bad = list(four)
    two_bad[3] = _rp("cb2", 24, 400, verdict="مرفوض (عطبٌ جسيم 6.0% > 5%)")
    if pooled_samples(two_bad) is not None:
        raise SystemExit("⛔ D-109: رافضان رُفع بهما المنع — الرافضان اتفاقٌ لا شذوذ")
    #  (٣) تقديرُ الرافض ≥ ضِعف المجمَّع ⇒ إشارةُ تكتّلٍ لا ضجيج، فيمنع
    far = list(four)
    far[2] = _rp("ci2", 40, 200, verdict="مرفوض (عطبٌ جسيم 20% > 5%)")
    if pooled_samples(far) is not None:
        raise SystemExit("⛔ D-109: رافضٌ عند ضِعف المجمَّع فأكثر لم يمنع")
    #  (٤) وبلا رافضٍ تبقى القاعدةُ D-098 لا D-109
    clean = [_rp("cb", 10, 400), _rp("ci", 5, 200), _rp("cb2", 10, 400), _rp("ci2", 5, 200)]
    if (pooled_samples(clean) or {}).get("rule") != "D-098":
        raise SystemExit("⛔ D-109: وُسم بلا خلافٍ — القاعدةُ تُسمّى بما وقع")
    print("  ✅ D-109: رافضٌ واحدٌ دون الضِّعف مع أربعة ملوحٍ يُجمَّع ويُذكر شاهدَ "
          "خلاف؛ وثلاثةُ ملوحٍ أو رافضان أو رافضٌ عند الضِّعف تمنع")

    # **D-175** — حكمُ فاحصٍ سابقٍ لإصلاح التبرئة الكاذبة **لا يشهد**.
    #  ⛔ ويُختبر بطرفيه: القديمُ يُردّ، **والجديدُ يمرّ** — فحارسٌ يمنع الصوابَ
    #     أسوأُ من غيابه، ولو مرّ الاختبارُ بالردّ وحده لَما كُشف ذلك.
    op_old = {"kind": "openers", "sha256": rep["sha256"], "scope": "full",
              "commit": "0000000", "swallowed": [], "suspect": []}
    _t, why = gate(dict(rep), {}, prefix, {}, None, None, {rep["sha256"]: op_old})
    if not (why and "أداةٍ سابقة" in why):
        raise SystemExit(f"⛔ D-175: حكمُ فاحصٍ قديمٍ لم يُردّ: {why}")
    op_new = dict(op_old, commit=OPENERS_FIX_COMMIT)
    _t, why = gate(dict(rep), {}, prefix, {}, None, None, {rep["sha256"]: op_new})
    if why and "أداةٍ سابقة" in why:
        raise SystemExit("⛔ D-175: حكمُ الفاحص المصحَّح رُدّ — حارسٌ يمنع الصواب")
    if not openers_tool_ok(op_new) or openers_tool_ok(dict(op_old, commit="")):
        raise SystemExit("⛔ D-175: بصمةُ الأداة لا تُقرأ كما يجب")
    print("  ✅ D-175: حكمُ فاحصٍ قبل إصلاح التبرئة الكاذبة لا يشهد؛ "
          "وحكمُ المصحَّح يمرّ؛ وبلا بصمةِ أداةٍ لا اعتداد")

    # **D-110** — `suspect` مع تأكيدٍ مستقلٍّ = مؤكَّدٌ يمنع؛ ووحدَه بلا أثر.
    #  ⛔ وأوّلُ ما يُختبر أنّ المستخرِج **يعمل أصلاً**: كُتب أوّلَ مرّة بمحرف
    #     تحكّمٍ خفيّ (‏U+0008) في نمطه، فكان **لا يطابق شيئاً أبداً** — قاعدةٌ
    #     تامّةُ المنطق لا تنفُذ ولا تشتكي. **فحارسٌ بلا اختبارٍ ليس حارساً.**
    conf = _swallowed_surahs_from(
        {"fatal": ["بسملة مبتلعة في 67:1 — مؤكَّدة بالصوت"], "sample": {"rows": []}})
    if conf != {67}:
        raise SystemExit(f"⛔ D-110: بلاغُ الابتلاع في fatal لم يُقرأ: {conf}")
    rows = _swallowed_surahs_from(
        {"fatal": [], "sample": {"rows": [{"aid": "37:1", "why": "بسملة مبتلعة"},
                                          {"aid": "9:1", "why": "بدء مبكر"}]}})
    if rows != {37}:
        raise SystemExit(f"⛔ D-110: صفوفُ العيّنة لم تُقرأ أو التُقط غيرُ المبتلع: {rows}")
    if _swallowed_surahs_from({"fatal": ["خلل ما"], "sample": {}}):
        raise SystemExit("⛔ D-110: بلاغٌ غامضٌ بلا رقمِ سورةٍ بُني عليه منع")
    print("  ✅ D-110: بلاغُ الابتلاع يُقرأ من `fatal` ومن صفوف العيّنة برقم "
          "السورة؛ والغامضُ لا يُبنى عليه منع")

    # **D-111 (تنفيذُ قرار المشرف D-171)** — التجميعُ فصلٌ فيسبق إعلانَ التعارض.
    #  حالةُ `nabil` الحقيقية: 7e مقبول 3/200 · ci حدّي 7/200 · ci2 حدّي 9/200.
    loc = dict(rep, source="local", engine=eng, verdict=ACCEPTED,
               sample={"seed": 1, "severe": [3, 200, [0.015, 0.0, 0.04]]}, ts=rep["ts"])
    c_a = _rp("ci", 7, 200, verdict="حدّي (التقدير 3.5% والحدّ الأعلى 7.0% > 5%)")
    c_b = _rp("ci2", 9, 200, verdict="حدّي (التقدير 4.5% والحدّ الأعلى 7.2% > 5%)")
    #  (١) الملحُ الفارغ من مصدرٍ **محلّيّ** يُسمّى `local` فيشهد — وهو أقوى شهادةٍ عندنا
    pl = pooled_samples([loc, c_a, c_b])
    if pl is None or pl["n"] != 600 or pl["m"] != 19 or "local" not in pl["salts"]:
        raise SystemExit(f"⛔ D-111: عيّنةُ 7e المحلية (بلا ملح) لم تدخل التجميع: {pl}")
    if not (pl["hi"] < SEVERE_CEILING):
        raise SystemExit(f"⛔ D-111: المجمَّع 19/600 كان يجب أن يُقبل: {pl}")
    #  (٢) والملحُ الفارغ من مصدرٍ **غيرِ محلّيّ** يبقى مردوداً
    if pooled_samples([dict(c_a, sample={"seed": 1, "severe": [7, 200]}), c_b]) is not None:
        raise SystemExit("⛔ D-111: ملحٌ فارغٌ من مصدرٍ غيرِ محلّيّ دخل التجميع")
    #  (٣) والفصلُ لا يقع مع رافضٍ صريح — الخلافُ الحقيقيُّ يبقى موقوفاً
    if pooled_samples([loc, _rp("ci", 20, 200, verdict="مرفوض (عطبٌ جسيم 10%)"), c_b]) is not None:
        raise SystemExit("⛔ D-111: رافضٌ صريحٌ ذُوِّب في الفصل")
    print("  ✅ D-111/D-171: عيّنةُ 7e المحلية تشهد بملح `local`؛ والمجمَّع 19/600 "
          "يفصل التعارض؛ والفارغُ من غير المحلّيّ والرافضُ الصريح يمنعان")
    if ci_pair_reps([("a", c1), ("b", c2)], human_keys={rep["key"]}):
        raise SystemExit("⛔ مفتاحٌ له حكمُ إنسان رُكِّب له زوجُ CI")
    if len(sampled_candidates([("a", c1), ("b", c2)])) != 2:
        raise SystemExit("⛔ sampled_candidates لا يُخرج زوج CI")
    if len(sampled_candidates([("h", rep), ("a", c1), ("b", c2)])) != 1:
        raise SystemExit("⛔ حكمُ الإنسان لم يغلب زوج CI على المفتاح نفسه")
    print("  ✅ شهادتا CI (‏D-090): ملحان مختلفان + محرّكٌ واحد + اتفاقٌ ⇒ ممثِّل؛ وما دونه لا")
    # **D-092**: زوجٌ كلاهما صفر عطب من 200 ⇒ ممثِّلٌ واحد مجمَّع بحدّ أعلى 3/400؛
    # ومن 30+30 (دون الحدّ الأدنى) لا تجميع؛ وواحدٌ بعطب لا تجميع.
    z1 = dict(c1, sample={"seed": 1, "seedSalt": "ci", "severe": [0, 200, [0.0, 0.0, 0.0]]})
    z2 = dict(c2, sample={"seed": 2, "seedSalt": "ci2", "severe": [0, 200, [0.0, 0.0, 0.0]]})
    pz = ci_pair_reps([("a", z1), ("b", z2)])
    if len(pz) != 1 or not pz[0][1].get("pooled") or abs(pz[0][1]["pooled"]["hi"] - 3 / 400) > 1e-12:
        raise SystemExit("⛔ D-092: زوجٌ صفريّ لم يُجمَّع بحدّ 3/400")
    _t, why = gate(pz[0][1], {}, prefix, {}, None)
    if why and ("عرض صفر" in why or "لا تُغلق" in why):
        raise SystemExit(f"⛔ D-092: الممثِّل المجمَّع رُدّ بحارس العيّنة: {why}")
    s1 = dict(z1, sample=dict(z1["sample"], severe=[0, 30, [0.0, 0.0, 0.0]]))
    s2 = dict(z2, sample=dict(z2["sample"], severe=[0, 30, [0.0, 0.0, 0.0]]))
    if any(r.get("pooled") for _n, r in ci_pair_reps([("a", s1), ("b", s2)])):
        raise SystemExit("⛔ D-092: عيّنتان دون الحدّ الأدنى جُمِّعتا")
    d2 = dict(z2, sample=dict(z2["sample"], severe=[1, 200, [0.005, 0.0, 0.0148]]))
    if any(r.get("pooled") for _n, r in ci_pair_reps([("a", z1), ("b", d2)])):
        raise SystemExit("⛔ D-092: زوجٌ فيه عطب جُمِّع")
    _t, why1 = gate(z1, {}, prefix, {}, None)
    if not (why1 and "عرض صفر" in why1):
        raise SystemExit("⛔ القاعدة 6 لم تعد تردّ الحكم المنفرد الصفري")
    # **D-093**: حدّي CI (تقدير < العتبة، حدّ أعلى ≤ 6%) لا يناقض 7e مقبولاً؛
    # وحدّي بحدّ أعلى 7% أو مرفوض صريح يناقض؛ ولا يسري على زوج CI.
    hb = dict(rep, source="ci", engine=eng, verdict="حدّي (التقدير 3.0% والحدّ الأعلى 5.2% > 5%)",
              sample={"seed": 9, "seedSalt": "ci2", "severe": [6, 199, [0.03, 0.01, 0.052]]})
    human = dict(rep)
    _t, why = gate(human, {}, prefix, {}, None, {rep["sha256"]: hb})
    if why and "تعارض" in why:
        raise SystemExit(f"⛔ D-093: حدّي CI عُدّ تناقضاً: {why}")
    if not human.get("ciBorderline"):
        raise SystemExit("⛔ D-093: لم يُسجَّل الحدّي في الحكم لسطر التجميد")
    hb7 = dict(hb, sample=dict(hb["sample"], severe=[8, 199, [0.04, 0.015, 0.07]]))
    _t, why = gate(dict(rep), {}, prefix, {}, None, {rep["sha256"]: hb7})
    if not (why and "تعارض" in why):
        raise SystemExit("⛔ D-093: حدّي بحدّ أعلى 7% مرّ")
    rj = dict(hb, verdict="مرفوض (عطبٌ جسيم 6.0% > 5%)", sample=dict(hb["sample"], severe=[12, 200, [0.06, 0.03, 0.09]]))
    _t, why = gate(dict(rep), {}, prefix, {}, None, {rep["sha256"]: rj})
    if not (why and "تعارض" in why):
        raise SystemExit("⛔ D-093: مرفوضٌ صريح مرّ")
    pr = dict(rep, source=CI_PAIR_SOURCE)
    _t, why = gate(pr, {}, prefix, {}, None, {rep["sha256"]: hb})
    if not (why and "تعارض" in why):
        raise SystemExit("⛔ D-093: سرى على زوج CI")
    print("  ✅ D-093: حدّي CI (≤6%) لا يناقض 7e مقبولاً؛ و7% أو مرفوضٌ صريح يناقض؛ ولا يسري على زوج CI")
    print("  ✅ D-092: زوجٌ صفريّ ≥59+59 ⇒ ممثِّلٌ مجمَّع بحدّ 3/(n1+n2)؛ ودون الحدّ أو مع عطبٍ لا؛ والقاعدة 6 باقية للمنفرد")
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
                  else (list(REPORTS_CACHE) if REPORTS_CACHE is not None
                        else list(reports()) + bucket_reports(cl, bucket)))
    ci_reports = ci_map(everywhere)
    openers_reports = None if a.self_test else openers_map(everywhere)
    # ⛔ **D-111 كانت نصفَ مطبَّقة**: بُنيت في الراصد وغابت هنا — والراصدُ
    #    يفحص ثمّ **يستدعي `main` هي التي تُرقّي**، فكان يقول «يمرّ» ثمّ يردُّه
    #    هذا المسار بالتعارض نفسِه، **فبقي `nabil` محبوساً دورتين بعد إصلاحه**.
    #    وهي عينُ قاعدة `sampling_skip_reason`: **قاعدةٌ في أداةٍ وغائبةٌ عن
    #    أختها ليست قاعدة — هي عادةُ أداة.** ⇒ الفاصلُ حيث يقع الحكم.
    pooled_map = None if a.self_test else pooled_map_of(everywhere)
    items = everywhere if a.self_test else sampled_candidates(everywhere)
    if a.only:
        items = [(n, r) for n, r in items if r.get("key") == a.only]

    ready, refused, done = [], [], []
    for name, rep in items:
        target, why = gate(rep, frozen, a.prefix, holds, a.override,
                           ci_reports, openers_reports, pooled_map)
        if why:
            refused.append((rep.get("key"), why))
            if why.startswith("حدّيّ") and a.yes:
                note_borderline(rep, target, why)
            continue
        ready.append((name, rep, target))

    print(f"أحكامٌ مقروءة: {len(items)} · مرشّحون: {len(ready)} · مرفوضون: {len(refused)}")
    # ⛔ **حدُّ الطباعة يصنع عمىً**: كانت تُطبع أربعون سبباً من مئاتٍ فيسقط
    #    سببُ المرشّحين الحقيقيين — من `timings-staging/` — تحت ركامِ أسبابِ
    #    فهارسِ الإنتاج المعادِ حكمُها، **فبقي ثلاثةٌ محبوسون ساعاتٍ بلا سببٍ
    #    ظاهر وأنا أقرأ «صفر مرشّحين» ولا أرى لماذا**. ⇒ المرشّحون أوّلاً،
    #    وبلا سقف؛ وما عداهم بسقفه.
    stage = [(k, w) for k, w in refused if str(k).startswith("timings-staging/")]
    other = [(k, w) for k, w in refused if not str(k).startswith("timings-staging/")]
    for key, why in stage:
        print(f"  ⛔ {key}: {why}")
    for key, why in other[:20]:
        print(f"  ⛔ {key}: {why}")
    if len(other) > 20:
        print(f"  … و{len(other) - 20} سبباً آخر لفهارسِ إنتاجٍ أُعيد حكمُها")

    promoted_targets = set()
    for _name, rep, target in ready:
        src = rep["key"]
        if target in promoted_targets:
            continue          # الهدف رُقّي في هذه الجولة (زوجُ CI يعطي مرشّحين — D-090)
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
        # ⛔ **حارسُ خلط المحرّكات** (‏كتبته جلسةٌ أخرى 2026-09-07): أنتجت
        #    الدورةُ الآليةُ `op=source_timing_splice:37` — دسّت سورةً من مصدر
        #    التوقيت في فهرسٍ من محرّكنا، والترويسةُ تقول `align-0.2` وحده
        #    **فتكذب على قارئها**. والقاعدة: **فهرسٌ واحد = محرّكٌ واحد وجيلٌ
        #    واحد**، ومن قبِل المختلط لا يعرف أيَّ حكمٍ يُنزل على أيّ موضع.
        #
        # ⛔⛔ **ونُقل إلى هنا 2026-09-07 (‏جنديّ الفهرسة): حكمُه كما هو ولم
        #    يُمسّ، وإنما موضعُه كان فوق سطر `idx = …` فيقرأ متغيّراً لم
        #    يُسنَد** — فانهار `promote.py` كلُّه بـ`UnboundLocalError` على
        #    **أوّل مرشّحٍ أيّاً كان** (‏مقيسٌ 23:2xZ)، أي أنّ البوابةَ توقّفت عن
        #    ترقية كلِّ أحد لا عن ردّ المخالف وحده. وهو **العطبُ نفسُه حرفاً**
        #    الذي وقع في حارس D-186 أمسِ ووُثّق في المرجع الجامع (‏الدرس
        #    الخامس عشر) — تكرّر لأنّ الدرسَ كان في مستندٍ لا في مكانِ الخطأ.
        #    ⇒ فليبقَ هذان الحارسان متجاورَين تحت سطر التحميل: **كلُّ حارسٍ
        #    يقرأ `idx` موضعُه بعده، بلا استثناء.**
        if _op_mixes_engines((idx.get("transform") or {}).get("op") or ""):
            print(f"  ⛔ {src}: تحويلٌ يخلط محرّكين في فهرسٍ واحد — "
                  "فهرسٌ واحد = محرّكٌ واحد وجيلٌ واحد")
            continue
        # ⛔ **حارسُ قاعدة D-186 في الأداة لا في الوصيّة** (‏2026-09-06):
        #    أنتجت الدورةُ الآليةُ بصمةً بـ`drop_surah:56,110` — وسورةُ 56
        #    (الواقعة) 96 آية، وتعديلُ D-186 ينصّ: «لا إسقاط لسورةٍ
        #    تزيد على 20 آية إلا بإذنٍ نصّيّ». فالقاعدةُ كانت في قرارٍ
        #    **ولا حارسَ يمنعها**، فخالفَتها أداةٌ تعمل بلا إنسان.
        #    **الوصيّةُ لا تحرس؛ الحارسُ يحرس.**
        # ⛔⛔ وموضعُه **بعد تحميل `idx`** لا قبله (‏عطبٌ مقيس 2026-09-06 22:4xZ):
        #    كُتب أوّلَ مرّةٍ فوق سطر التحميل، فكان يقرأ `idx` غيرَ المسنَد —
        #    فينهار `UnboundLocalError` على أوّل مرشّح، **أو أسوأُ منه**: يقرأ
        #    `idx` **المرشَّحِ السابق** في الدورات التالية فيحكم على فهرسٍ
        #    بتحويلِ غيره. وهو عمىً في اتجاهين: يمنع البريء ويُمرّر المخالف.
        _op = (idx.get("transform") or {}).get("op") or ""
        if _op.startswith("drop_surah:") and not a.allow_truncated:
            _big = [n for n in (int(x) for x in re.findall(r"\d+", _op))
                    if 1 <= n <= 114 and _AYAH_COUNTS[n - 1] > 20]
            if _big:
                _nm = "، ".join(f"س{n} ({_AYAH_COUNTS[n - 1]} آية)" for n in _big)
                print(f"  ⛔ {src}: إسقاطُ {_nm} يخالف تعديلَ D-186 — "
                      "لا إسقاط لما زاد على 20 آية إلا بإذنٍ نصّيّ")
                continue
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
        if rep.get("pooled"):
            pz = rep["pooled"]
            # ⛔ **السطرُ يصف ما وقع لا ما توقّعناه.** كان النصُّ ثابتاً «صفر عطب
            #    — D-092» فطُبع على ترقياتٍ مجمَّعةٍ **فيها أعطاب** (‏D-098):
            #    `m_harfoush` جُمّد بـ«صفر عطب» وأجزاؤه `[5,200]+[5,200]`.
            #    وسطرُ التجميد **سجلٌّ دائم**، فكذبُه يبقى بعد أن يُنسى سببُه.
            #    ⇒ القاعدةُ والملوحُ والأعطابُ تُقرأ من الحساب نفسه.
            salts = pz.get("salts")
            m = pz.get("m")
            # ⛔ **وشاهدُ الخلاف يُذكر** (‏D-109): ترقيةٌ فيها رافضٌ منفرد
            #    **ليست إجماعاً**، والسكوتُ عنه في سطرٍ دائمٍ يجعلها تُقرأ كذلك.
            ds = pz.get("dissent") or []
            rate = (f"حدّ أعلى {pz['hi'] * 100:.2f}% من {pz['n']} حدّ "
                    + (f"بملوح {'+'.join(salts)} " if salts else "بملحين ")
                    + f"({'+'.join(str(x) for x in pz['parts'])}، "
                    + (f"{m} عطباً" if m else "صفر عطب")
                    + f" — {pz.get('rule', 'D-092')})"
                    + ("".join(f" ⚠️ خلافٌ مذكور: ملح {d['salt']} رفض بـ"
                               f"{d['rate'] * 100:.1f}% من {d['n']}" for d in ds)))
        elif isinstance(severe, dict):
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
        if rep.get("ciBorderline"):
            cb = rep["ciBorderline"]
            note += (f" (‏7e مقبول؛ وCI/{cb.get('salt')} حدّي {cb['rate'] * 100:.1f}% "
                     f"بحدّ أعلى {cb['hi'] * 100:.1f}% — D-093)")
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
        promoted_targets.add(target)
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
