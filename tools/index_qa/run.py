#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""تدقيق فهارس التوقيتات التي يرفعها الأسطول — بأمر واحد.

    python tools/index_qa/run.py --all                # كل ما على R2
    python tools/index_qa/run.py qalun/husary_qalun   # فهرس بعينه
    python tools/index_qa/run.py --all --struct-only  # بنيوي فقط (بلا خادم)
    python tools/index_qa/run.py --watch 600 --new    # يدقّق كل جديد أولاً بأول

⛔ **حدود هذه الأداة — تُقرأ قبل أي حكم تطبعه** (وتُطبع مع كل تقرير):

1. **ليست أذناً.** كاتبها وكيل برمجي لا يسمع. الحكم مبنيّ على تفريغ
   `whisper-tiny-ar-quran q8` مقابَلاً بالنص المرجعي — بديلٌ موضوعي معلَن
   لا ادّعاء سماع. حكم الأذن يبقى للمالك.
2. **لا تفصل ما دون ~0.3ث.** «بريء» تعني «لا نشاز يلتقطه التفريغ» لا
   «مضبوط بالمللي»، وهي تقيس **وجود الأثر لا مقداره**.
3. **لا بلاغ إلا بشاهد نصّي، ولا شاهد إلا بتمريرين** (QA_BOUNDARIES §ج/§ز):
   نافذةٌ أمامية وحدها لا تفرّق «مضبوط» من «مبكر بثوانٍ» لأن whisper يتخطى
   الصمت الابتدائي بلا أثر. فكل اشتباه يمرّ بتمرير ثانٍ حاسم، وما لم يحسمه
   يُطبع «غير حاسم» ولا يُحتسب عطباً.
4. **المقارنة بالهيكل لا بالمواضع** (`SequenceMatcher`) لأن فروق الرسم
   تُزيح المواضع فتُنتج إنذاراً كاذباً (وقع فعلاً على 74:1).
5. **الفحص الحسابي يُرشِّح ولا يحكم** — فما يظهر تحت «مرشّح» ليس حكماً.
6. النسب من عيّنة عنقودية 8×6، ومجالها محسوب **على مستوى العنقود** — واسعٌ
   بطبعه، ولا يضيق إلا بأضعاف العيّنة.
"""
from __future__ import annotations
import argparse, difflib, gzip, hashlib, json, math, os, random, re, subprocess, sys, threading, time
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT    = Path(__file__).resolve().parents[2]
CREDS   = ROOT / "secure" / "r2_credentials.json"
ASSETS  = ROOT / "core" / "quran" / "src" / "main" / "assets" / "quran"
STATE   = Path(__file__).with_name("state")
SSH_KEY = Path.home() / ".ssh" / "rafiq_worker"
QA_HOST = "2.28.47.206"          # للقراءة والقصّ فقط — لا يُلمس فيه شيء آخر
REMOTE  = "/root/qa_worker.py"
WORKER  = Path(__file__).with_name("remote_worker.py")

# عدّ الآي الكوفي (6236) — الفهارس كلها كوفية بعقد المحرك
COUNTS = [7,286,200,176,120,165,206,75,129,109,123,111,43,52,99,128,111,110,98,135,112,78,118,64,77,
227,93,88,69,60,34,30,73,54,45,83,182,88,75,85,54,53,89,59,37,35,38,29,18,45,60,49,62,55,78,96,29,22,
24,13,14,11,11,18,12,12,30,52,52,44,28,28,20,56,40,31,50,40,46,42,29,19,36,25,22,17,19,26,30,20,15,21,
11,8,8,19,5,8,8,11,11,8,3,9,5,4,7,3,6,3,5,4,5,6]
assert sum(COUNTS) == 6236 and len(COUNTS) == 114
BASE = [0]
for _c in COUNTS:
    BASE.append(BASE[-1] + _c)

def flat(s, a):
    return BASE[s - 1] + a - 1

BASMALA = "بسم الله الرحمن الرحيم"

# ───────────────────────── تطبيع الرسم ─────────────────────────
_AR = re.compile(r"[^ء-ي ]")
_FOLD = (("أ", "ا"), ("إ", "ا"), ("آ", "ا"), ("ٱ", "ا"), ("ى", "ي"), ("ة", "ه"), ("ؤ", "و"), ("ئ", "ي"))
# ⛔ الحروف الصغيرة في رسم المصحف **تُنطق** ويكتبها التفريغ حروفاً كاملة، وهي
# خارج نطاق «ء-ي» فتُمحى بالتطبيع الساذج. فـ«اَ۬لْعَٰلَمِينَ» تصير `العلمين`
# بينما whisper يكتب «العالمين` — أربعة أحرف تطابق فقط، فيسقط عطبٌ حقيقي تحت
# أي عتبة. قِيس ذلك على 2:252 و2:157: كلاهما تسرّبٌ حقيقي أفلت قبل هذا السطر.
_SMALL = (("ٰ", "ا"), ("ۥ", "و"), ("ۦ", "ي"))
# والهمزة المفردة تُرسم في المصحف ولا يكتبها التفريغ («ءَاتَيْتَنِے» ← «آتيتني»)
# فتُسقط من الطرفين معاً كي لا تقطع كتلة التطابق (قِيس على 12:101).
_DROP = "ء"

def words(t: str):
    t = t or ""
    for a, b in _SMALL:
        t = t.replace(a, b)
    t = _AR.sub("", t)
    for a, b in _FOLD:
        t = t.replace(a, b)
    t = t.replace(_DROP, "")
    return [w for w in t.split() if w]

def skel(t: str) -> str:
    """هيكل حروفي متسامح مع فروق الرسم — بلا مسافات.

    ⛔ ضروري: «يَٰأَيُّهَا» هيكلها `يايها` و«يا أيها» المنطوقة `ياايها`،
    فالمقارنة الحرفية بالمواضع تُنتج إنذاراً كاذباً."""
    return "".join(words(t))

# ───────────────────────── R2 ─────────────────────────
def s3():
    import boto3
    c = json.loads(CREDS.read_text(encoding="utf-8"))
    return boto3.client("s3", endpoint_url=c["endpoint"], aws_access_key_id=c["accessKeyId"],
                        aws_secret_access_key=c["secretAccessKey"], region_name="auto"), c["bucket"]

def list_indexes():
    cl, b = s3()
    out = []
    for page in cl.get_paginator("list_objects_v2").paginate(Bucket=b, Prefix="timings/"):
        for o in page.get("Contents", []):
            if o["Key"].endswith(".jz"):
                out.append({"key": o["Key"], "size": o["Size"], "mtime": o["LastModified"].timestamp()})
    return sorted(out, key=lambda r: r["mtime"])

def fetch_index(key, want_sha=None):
    """يُرجع (الفهرس، بصمته). ⛔ البصمة تُسجَّل مع كل حكم لأن المفتاح **لا
    يعرّف المحتوى**: فهرسٌ يُستبدل تحت مفتاحه فيصير الحكم على نسخةٍ زائلة.
    وقع ذلك فعلاً: دقّقتُ `husary_warsh` فإذا هو النسخة الناقصة (110 سور)
    وقد استُبدلت بعدها بالكاملة — وحكمٌ بلا بصمةٍ لا يُعرف على أيّهما وقع."""
    cl, b = s3()
    raw = cl.get_object(Bucket=b, Key=key)["Body"].read()
    sha = hashlib.sha256(raw).hexdigest()
    if want_sha and sha != want_sha:
        raise RuntimeError(f"البصمة لا تطابق المطلوب: {sha[:16]}… ≠ {want_sha[:16]}…")
    return json.loads(gzip.decompress(raw).decode("utf-8")), sha

# ───────────────────────── الفحص البنيوي ─────────────────────────
def structural(idx, key, allow_unmarked=False, txt_ref=None):
    """كل بند يُرجع نصاً. القائمة الأولى مُوجِبة للحجب، والثانية مرشّحون لا أحكام."""
    fatal, warn, info = [], [], {}
    # ⛔ صنفٌ ثالث: ما **يمنع الترقية الآلية ولا يُسمّى عطباً**. الحذفُ المعلَن
    # بسببٍ موثّق قرارُ منتَجٍ يُعرض على المشرف؛ فمن جعله «خللاً بنيوياً» رفض
    # إصلاحاً، ومن أهمله رقّى نقصاً بلا أن يراه أحد.
    decision = []
    E = idx.get("entries", [])
    info["entries"] = len(E)

    # ١) الميتاداتا والعقد
    if idx.get("ayahCounting") != "KUFI":
        fatal.append(f"ayahCounting = {idx.get('ayahCounting')!r} لا KUFI — فهرسٌ بعدٍّ مخالف")
    if idx.get("ayahCount") != 6236:
        fatal.append(f"ayahCount = {idx.get('ayahCount')} لا 6236")
    parts = key.split("/")
    if len(parts) == 3:
        if idx.get("riwaya") != parts[1]:
            fatal.append(f"الرواية في الملف {idx.get('riwaya')!r} ≠ مسار الرفع {parts[1]!r}")
        # ⛔ لاحقة البصمة `<reciter>.<sha8>.jz` **اصطلاحُنا نحن** للرفع المرحلي
        # (كي لا يُكتب فهرسٌ فوق مفتاحٍ يقرؤه غيرنا أثناء بنائه). فحسمُها قبل
        # المقابلة واجب — وإلا أبلغت الأداة عن «معرّفٌ لا يطابق مساره» وهو
        # اصطلاحٌ سليم. أبلغتُ عنه فعلاً أنا وgithub-7d كلانا، وكان عطب أداةٍ
        # لا عطب فهرس.
        stem = re.sub(r"\.[0-9a-f]{8}$", "", parts[2][:-3])
        if idx.get("reciterId") != stem:
            fatal.append(f"معرّف القارئ {idx.get('reciterId')!r} ≠ مسار الرفع {stem!r}")
    info["engine"] = idx.get("engineVersion")
    info["exactEnds"] = idx.get("exactEnds")
    # ⛔ أثر الجيل: `engineVersion` وحده لا يفرّق الجيلين (كلاهما `align-0.2`)،
    # ولا حقل صقلٍ في المداخل. فحُكم «هذا جيلٌ ثانٍ» كان يُؤخذ **بقول صاحبه**
    # لا ببرهانٍ في الملف — ووقع فعلاً أن قيس فهرسٌ بوصفه جيلاً ثانياً وهو
    # جيلٌ أول + 17 حدّاً مصقولاً من 728 مستهدفاً. فالفهرس الذي لا يحمل أثره
    # **لا يُصنَّف**، وقياسه لا يُنسب إلى جيل.
    info["refineVersion"] = idx.get("refineVersion")
    info["refinedCount"] = idx.get("refinedCount")
    if idx.get("refineVersion") is None or idx.get("refinedCount") is None:
        (warn if allow_unmarked else fatal).append(
            "لا أثر صقلٍ في الترويسة (`refineVersion`/`refinedCount`) — "
            "الفهرس غير قابلٍ للتصنيف، ولا يُنسب قياسه إلى جيل")

    # ٢) بصمات الصوت — غيابها أو تكرارها = تنزيل فاشل أو ملفٌ واحد لسورتين
    sha = idx.get("audioSha256") or []
    info["sha"] = len(sha)
    if len(sha) != 114:
        fatal.append(f"بصمات الصوت {len(sha)}/114 — سورٌ بلا برهان تنزيل")
    empty = sum(1 for s in sha if not s)
    if empty:
        fatal.append(f"بصمات فارغة: {empty}")
    dup = len([x for x in sha if x]) - len(set(x for x in sha if x))
    if dup:
        fatal.append(f"بصمات مكرّرة: {dup} — الملف نفسه لسورتين فأكثر (تنزيلٌ مغشوش)")

    # ٣) التغطية
    per = {}
    for e in E:
        per.setdefault(int(e["ayahId"].split(":")[0]), []).append(e)
    info["surahs"] = len(per)
    miss_s = [s for s in range(1, 115) if s not in per]
    if miss_s:
        # ⛔ الإسقاطُ المعلَن يُسمّى ولا يُعفى. فالمستخدم الذي يطلب آيةً من
        # سورةٍ مُسقَطة لا يجد شيئاً سواءٌ أُسقطت عمداً أم سهواً — والنيّة
        # تُغيّر **اسم** العيب لا **وجوده**. ولو أعفينا المعلَن لصار الإعلان
        # باباً لإسقاط ما شئنا: «حُذف بقصد» ليست حجّةً على المستهلك.
        tr = idx.get("transform") or {}
        # الصيغة المستعملة: {"op": "drop_surah:24", …}
        dropped = []
        op = tr.get("op") or ""
        dropped += [int(x) for x in re.findall(r"drop_surah:(\d+)", str(op))]
        d2 = tr.get("dropSurah") or tr.get("drop_surah")
        dropped += [d2] if isinstance(d2, int) else list(d2 or [])
        declared = [x for x in miss_s if x in dropped]
        rest = [x for x in miss_s if x not in dropped]
        if declared:
            # ⛔ **تصحيحٌ 2026-09-02 بعد حكمٍ خاطئ أصدرتُه:** كنتُ أجعل الإسقاط
            # المعلَن **قاتلاً**، بحجّة أن المستخدم لا يجد الآية سواءٌ أُسقطت
            # عمداً أم سهواً. والحجّة ناقصة: في `akri_qalun.afaacc25` أُسقطت
            # سورة 24 لأن **صوتها مبتورٌ مؤكَّد** (نسبة المدة 0.39)، فالبديل
            # ليس «سورةً كاملة» بل **توقيتاً يقع على صوتٍ ناقص**. والصوتُ
            # المبتور لا يُنتج غياباً بل **إزاحة** — والمستخدم يسمع موضعاً
            # غير الذي يقرأ، وذاك أضرّ من ألّا يجدها: الغيابُ يُرى ويُشتكى
            # منه، والإزاحةُ تُصدَّق ويُحفَظ عليها الخطأ.
            # ⇒ الحذفُ المعلَن **قرارُ منتَجٍ لا حكمُ جودة**: يُعرض بارزاً
            # ويمنع الترقية الآلية، ولا يُسمّى عطباً ولا يُحسب في نسبة الفقد.
            decision.append(f"سورٌ محذوفةٌ **بإعلانٍ وسبب**: {declared} "
                            f"(السبب: {tr.get('reason') or 'غير مذكور'}) — "
                            f"قرارُ منتَجٍ يُعرض على المشرف، لا حكمُ جودة")
        if rest:
            fatal.append(f"سور غائبة كلياً: {len(rest)} → {rest[:10]}")
    info["decision"] = decision
    miss = 6236 - len(E)
    info["missing"] = miss
    # ⛔ **العتبة تُحاسب الناقص غير المبرَّر وحده.** جمعُ الحذف المعلَن مع
    # العطب في رقمٍ واحد ازدواجُ عدٍّ: بلغ `akri.afaacc25` **127 = 2.0%** فرُفض،
    # وفصلُهما يعطي **70 = 1.12%** — دون الحدّ. ومن حاسب على المجموع جعل
    # البوابة تُفضّل شحن توقيتٍ على صوتٍ ناقصٍ على قبول إسقاطه (وقعت هذه
    # بعينها في بوابة github-bd فأصلحها للسبب نفسه، من طريقٍ مستقلّ).
    excused = 0
    _mh = idx.get("missing") or {}
    if isinstance(_mh.get("byReason"), dict):
        excused = int(_mh["byReason"].get("source_truncated") or 0)
    info["missingExcused"], info["missingUnexcused"] = excused, miss - excused
    # العتبة 2% سياسةٌ قرّرها المشرف وحارس الأسطول عليها — ووحّدتُها معه قصداً
    # كي لا يقول حارسان رقمين. (وكانت عندي 350 مدخلاً ≈ 5.6%، وهي أرخى.)
    if miss > 0:
        unex = miss - excused
        tag = (f"مداخل ناقصة: {miss} من 6236 ({miss/6236:.1%})"
               + (f" — منها {excused} بعذرٍ معلَن (بترٌ مصدري) "
                  f"⇒ **غير المبرَّر {unex} ({unex/6236:.1%})**" if excused else "")
               + " — الحدّ 2% على غير المبرَّر")
        (fatal if unex > 0.02 * 6236 else warn).append(tag)

    # ٣-ب) ⛔ **انحياز الغياب إلى القصر** — صنفُ عطبٍ لا تكشفه العيّنة بطبعها:
    #      العيّنة تسحب حدوداً **موجودة** فتحكم عليها، والآية الغائبة لا تدخل
    #      السحب أصلاً فلا تظهر في المقام ولا في العطب. وأثرها على المستخدم
    #      أشدّ: الحدّ المزاح يُسمعه بدايةً متأخرة، والغائب يُسقط الآية من
    #      التظليل والتشغيل رأساً. (رصده github-8e على m_sayed_warsh: نصف
    #      المفقود ≤4 كلمات، ومنه ﴿يسٓ﴾ كلمةً واحدة.)
    #      والانحياز — لا مجرّد الغياب — هو الشاهد على الابتلاع: محاذاةٌ
    #      سليمةٌ تُسقط عشوائياً، والابتلاع يُسقط القصار.
    have = {e["ayahId"] for e in E}
    miss_ids = [f"{s_}:{a_}" for s_ in range(1, 115) for a_ in range(1, COUNTS[s_-1] + 1)
                if f"{s_}:{a_}" not in have]
    if miss_ids and txt_ref:
        lens = sorted(len(txt_ref[flat(*map(int, i.split(":")))].split()) for i in miss_ids)
        med_miss = lens[len(lens) // 2]
        all_len = sorted(len(t.split()) for t in txt_ref)
        med_all = all_len[len(all_len) // 2]
        short = sum(1 for l in lens if l <= 4) / len(lens)
        info["missMedianWords"] = med_miss
        info["missShortShare"] = round(short, 3)
        # ⛔ **حدٌّ أدنى قبل تطبيق اختبار الانحياز** (‏≥50 مدخلاً أو ≥1%):
        # اختبار الشكل بلا حدٍّ أدنى **يفقد معناه على الأعداد الصغيرة**،
        # ويعاقب أنظف الفهارس بالضبط — فكلما اقترب الفهرس من الكمال صار ما
        # بقي من مفقوده قصاراً بطبعه (فواتحُ وآياتٌ من كلمةٍ إلى ثلاث)، فيصير
        # النجاحُ سبباً للرفض. وقع ذلك فعلاً على `husary_warsh.5de0a957`:
        # ‏18 مفقوداً (0.3%) كلها فواتحُ وقصار، فرفضه الحارس وهو أنظف ما قِسنا
        # (‏0.5% عطباً و**صفرٌ في 185 حدّ HIGH**).
        # وأُقرّ التعديل **بعد** صدور حكم ذلك الفهرس لا قبله، كي لا يُقال إن
        # الحارس فُصِّل على الحالة التي بُني لها.
        enough = len(miss_ids) >= 50 or len(miss_ids) >= 0.01 * 6236
        if enough and med_miss * 2 < med_all:
            fatal.append(f"الغياب منحازٌ إلى القصار (ابتلاع): وسيط طول المفقودة {med_miss} كلمة "
                         f"مقابل {med_all} في المصحف · و{short:.0%} منها ≤4 كلمات")
        else:
            warn.append(f"آيات بلا مدخل: {len(miss_ids)} · وسيط طولها {med_miss} كلمة "
                        f"(المصحف {med_all}) — غيابٌ غير منحاز")

    # ٣-ج) وسمُ الاكتمال في الترويسة (يكتبه كاتب الترويسة) — **يُقابَل بحسابنا
    #      لا يُصدَّق**: نحن نحسب الغياب من النصّ المرجعي بأنفسنا، فوجود الوسم
    #      فرصةٌ لكشف ترويسةٍ تكذب لا سبباً للاستغناء عن الحساب. وحارسٌ يقرأ
    #      رقماً كتبه المُنتَجُ عن نفسه ليس حارساً.
    tag = idx.get("missing")
    if isinstance(tag, dict) and txt_ref:
        info["missingTag"] = tag.get("count")
        if tag.get("count") is not None and tag["count"] != len(miss_ids):
            fatal.append(f"وسم الاكتمال يخالف الحساب: الترويسة {tag['count']} والمحسوب {len(miss_ids)}")
        if tag.get("count") is not None and tag["count"] + len(E) != 6236:
            fatal.append(f"وسم الاكتمال لا يتّسق: {len(E)} + {tag['count']} ≠ 6236")

    # ٤) الرتابة وعدم التداخل داخل كل سورة
    neg = mono = long_ = 0
    ex_neg = ex_mono = ex_long = ""
    for s, lst in per.items():
        lst = sorted(lst, key=lambda e: int(e["ayahId"].split(":")[1]))
        prev_end = None
        for e in lst:
            st, en = e.get("startMs"), e.get("endMs")
            if st is None or en is None or en <= st:
                neg += 1
                ex_neg = ex_neg or f"{e['ayahId']} مدة غير صالحة {st}→{en}"
                continue
            if en - st > 120_000:
                long_ += 1
                ex_long = ex_long or f"{e['ayahId']} مدتها {(en-st)/1000:.0f}ث"
            if prev_end is not None and st < prev_end - 50:
                mono += 1
                ex_mono = ex_mono or f"{e['ayahId']} يبدأ قبل نهاية سابقته بـ{prev_end-st}م.ث"
            prev_end = en
    if neg:
        fatal.append(f"مداخل بمدة غير صالحة: {neg} · مثال: {ex_neg}")
    if mono:
        fatal.append(f"خرق الرتابة (تداخل): {mono} · مثال: {ex_mono}")
    if long_:
        warn.append(f"مداخل مدتها > 120ث: {long_} · مثال: {ex_long}")

    # ٥) مطالع السور ≥3ث — البسملة غير المعزولة تُزيح أصل زمن السورة كلها.
    #    (20:1 و23:2 في الجيل الأول: أخطر عطبٍ رأيناه.) والسورتان 1 و9
    #    مستثنيتان: البسملة في الفاتحة آية، وبراءة بلا بسملة.
    early = []
    for s, lst in per.items():
        if s in (1, 9):
            continue
        a1 = next((e for e in lst if e["ayahId"] == f"{s}:1"), None)
        if a1 and a1.get("startMs") is not None and a1["startMs"] < 3000:
            early.append((s, a1["startMs"]))
    info["earlyStarts"] = len(early)
    info["earlyList"] = early          # تُثبَت بالصوت في مرحلة العيّنة، لا بالعتبة وحدها
    if early:
        # ⛔ **مرشّح لا حكم — وهذا تصحيحٌ لخطأ وقعتُ فيه.** كانت العتبة تُصدر
        # حكماً بالحجب، ثم كذّبها مسبار الصوت 4/4: `tareq_qalun` مطلعه 88:1
        # عند **0م.ث** ومع ذلك تفريغه «هل أتاك» بلا بسملة — لأن الملف نفسه
        # لا بسملة فيه، لا لأن الفهرس ابتلعها. والمصادر تختلف في ذلك.
        # فالعتبة تُرشِّح، والمسبار وحده يحكم (§مسبار المطالع).
        warn.append("مطالع سور تبدأ دون 3ث — مرشّحون للمسبار الصوتي لا حكمٌ عليهم: "
                     + " · ".join(f"{s}:1={ms}م.ث" for s, ms in early[:10])
                     + (f" … و{len(early)-10} غيرها" if len(early) > 10 else ""))

    # ٦) فجوات زمنية كبيرة بين آيتين متتاليتين ⇒ مادة ضائعة
    gaps, ex_gap = 0, ""
    for s, lst in per.items():
        lst = sorted(lst, key=lambda e: int(e["ayahId"].split(":")[1]))
        for a, b in zip(lst, lst[1:]):
            if int(b["ayahId"].split(":")[1]) - int(a["ayahId"].split(":")[1]) != 1:
                continue
            if a.get("endMs") is None or b.get("startMs") is None:
                continue
            g = b["startMs"] - a["endMs"]
            if g > 15_000:
                gaps += 1
                ex_gap = ex_gap or f"{a['ayahId']}→{b['ayahId']} فجوة {g/1000:.0f}ث"
    if gaps:
        warn.append(f"فجوات > 15ث بين آيتين متتاليتين: {gaps} · مثال: {ex_gap}")

    bands = {}
    for e in E:
        bands[e.get("confBand", "?")] = bands.get(e.get("confBand", "?"), 0) + 1
    info["bands"] = bands
    return fatal, warn, info

# ───────────────────────── العيّنة العنقودية ─────────────────────────
LONG_SEG_MS = 10_000     # سقف موثوقية التفريغ الذي كشفه قياس github-8e لعلم -ac 512

def long_segment_ids(idx, limit_ms=LONG_SEG_MS):
    """مداخل تقع **داخل** مقطعٍ متصل أطول من 10ث — طبقةُ العطب المشتبهة.

    ⛔ لماذا هذه الطبقة بالذات: الوصفة الإنتاجية تفرّغ بـ`-ac 512`، وقياس
    ‏github-8e أثبت أنه **يهدم التفريغ بعد ~10ث** (‏10–20ث: 74.9% مقابل 100%
    بدونه). ووحدة التفريغ في المحرك مقطعٌ بين صمتين، ومقاطع النَّفَس الواحد
    أطول من 10ث بطبعها (‏67/67 على مريم). فالحدود المشتقّة من ذيل مقطعٍ طويل
    مشتقّةٌ من نصٍّ مبتور.

    والتقريب: المداخل المتلاصقة (`start[i] == end[i-1]`) مقطعٌ واحد — إذ لو
    وقع بينها صمتٌ لانفصلت. ونأخذ ما كان **داخل** الجرية لا أولَها، لأن
    أولها مسنودٌ إلى حافة الصمت وما بعده هو المخمَّن."""
    out = set()
    per = {}
    for e in idx.get("entries", []):
        per.setdefault(int(e["ayahId"].split(":")[0]), []).append(e)
    for s, lst in per.items():
        lst = sorted(lst, key=lambda e: int(e["ayahId"].split(":")[1]))
        run = [lst[0]]
        for a, b in zip(lst, lst[1:]):
            if b.get("startMs") == a.get("endMs"):
                run.append(b)
            else:
                if len(run) > 1 and run[-1]["endMs"] - run[0]["startMs"] > limit_ms:
                    out.update(x["ayahId"] for x in run[1:])
                run = [b]
        if len(run) > 1 and run[-1]["endMs"] - run[0]["startMs"] > limit_ms:
            out.update(x["ayahId"] for x in run[1:])
    return out

def sample_boundaries(idx, clusters=8, per_cluster=6, band=None, long_seg=False, refined=None):
    """عيّنة عمياء ذاتية الوزن: عناقيد (سور) بالتناسب مع الحجم (PPS) ثم
    حدود بالتساوي داخل كل عنقود. البذرة مشتقة من معرّف القارئ فالعيّنة
    **ثابتة قابلة لإعادة الإنتاج** وتُختار قبل سماع أي شيء (العمى محفوظ)."""
    # ⛔ **البذرةُ من هويّة القارئ وحدها ⇒ كلُّ من شغّل الأداة سحب الحدودَ
    # نفسها.** وذاك مقصودٌ للتكرار (‏العيّنةُ عمياء ومثبَّتةٌ قبل السماع)، لكنه
    # يجعل «حكمين متفقين» **إعادةَ قياسٍ لا تعاضدَ شهادتين**: يكشف التقلّب
    # والعطب العابر، ولا يكشف **خطأ المنهج** — إذ يخطئ المسارانِ الخطأَ نفسه
    # على الحدود نفسها. (وهو عينُ ما وقع الليلة: محرّكٌ واحد برّأ 211 مطلعاً
    # بالغلط، وتكرارُه ألفَ مرّةٍ يُعيد البراءة نفسها.)
    # ⇒ `QA_SEED_SALT` يجعل المسار الثاني يسحب عيّنةً **مستقلّة**، فيصير
    # اتفاقُهما شهادتين على الفهرس لا شهادةً واحدةً مكرّرة.
    _salt = os.environ.get("QA_SEED_SALT", "")
    seed = int(hashlib.sha256(f"{idx.get('riwaya')}/{idx.get('reciterId')}/{_salt}".encode()
                              ).hexdigest()[:12], 16)
    rng = random.Random(seed)
    keep = None
    if long_seg:
        keep = long_segment_ids(idx)
    per = {}
    for e in idx.get("entries", []):
        if keep is not None and e["ayahId"] not in keep:
            continue
        # عيّنةٌ مطبَّقة على نطاقٍ بعينه: المجتمع يصير مداخل ذلك النطاق وحدها،
        # والعنقدة والوزن يُحسبان عليه — فالرقم الناتج معدّل عطب **النطاق**
        # لا معدّل الفهرس. (طلب المشرف 2026-09-02 لتثبيت رقم MED.)
        if band and e.get("confBand") != band:
            continue
        # طبقة الصقل: المصقول وحده أو الأصلي وحده. ⚠️ والمقارنة بينهما
        # **رصديّةٌ لا تجريبية**: المصقول كان MED فاختير للصقل **لأنه أضعف
        # أصلاً**. فإن جاء أسوأ فقد يكون لضعفه السابق لا لأن الصقل أضرّه.
        # ⇒ تُقرأ النتيجة «هل HIGH المصقول يستحقّ وسمه؟» لا «هل الصقل نافع؟»
        # — والثانية لا تُجاب إلا بمقابلةٍ على الحدود نفسها قبل الصقل وبعده.
        if refined is not None and bool(e.get("refined")) != refined:
            continue
        per.setdefault(int(e["ayahId"].split(":")[0]), []).append(e)
    pool = [(s, lst) for s, lst in sorted(per.items()) if len(lst) >= per_cluster]
    if not pool:
        return seed, []
    sizes = [len(l) for _, l in pool]
    avail, chosen = list(range(len(pool))), []
    for _ in range(min(clusters, len(pool))):          # PPS بلا إرجاع
        r = rng.random() * sum(sizes[i] for i in avail)
        acc = 0.0
        for i in list(avail):
            acc += sizes[i]
            if acc >= r:
                chosen.append(i)
                avail.remove(i)
                break
    out = []
    for i in chosen:
        s, lst = pool[i]
        for e in rng.sample(lst, per_cluster):
            out.append((s, e))
    return seed, out

# ───────────────────────── التفريغ عن بُعد ─────────────────────────
def remote_run(jobs, host, threads=2):
    if not jobs:
        return {}, {}
    plan = json.dumps({"threads": threads, "jobs": jobs}, ensure_ascii=False)
    # nice كي لا نزاحم دفعات الفهرسة الجارية — القراءة والقصّ لا يعطّلان الإنتاج
    cmd = ["ssh", "-i", str(SSH_KEY), "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=25",
           f"root@{host}", f"nice -n 15 /root/QuranRafiq/.venv/bin/python {REMOTE}"]
    r = subprocess.run(cmd, input=plan, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=120 + 30 * len(jobs))
    line = next((l for l in reversed(r.stdout.splitlines()) if l.startswith("{")), None)
    if not line:
        raise RuntimeError(f"مخرج غير مفهوم من الخادم: {r.stdout[-200:]} | {r.stderr[-200:]}")
    d = json.loads(line)
    if not d.get("ok"):
        raise RuntimeError(d.get("error", "?"))
    return d["results"], d["errors"]

# ───────────────────────── مسارٌ محلي (بلا خادم) ─────────────────────────
LOCAL_MODEL = ROOT / "tools" / "tasmi_bench" / "work" / "ggml-q8.bin"
LOCAL_CACHE = Path(os.environ.get("TEMP", "/tmp")) / "rafiq_qa_local"
_LM = None

def _local_model():
    """⚠️ **النموذج والأوزان هي نفسها** التي على الخادم (`tiny-ar-quran q8`)،
    والمتغيّر رِباطُ الاستدعاء وحده. وقد اختُبرت المطابقة على ثلاث نوافذ لها
    تفريغٌ محفوظ من الخادم: اثنتان **حرفاً بحرف**، والثالثة بفرق **مسافةٍ
    واحدة** يمحوها `skel()` قبل الحكم (تُحقّق: الهيكلان متطابقان).
    ⇒ **مطابقةٌ وظيفية لا معايرةٌ جديدة** — فالأرقام تُقارن بما قبلها."""
    global _LM
    if _LM is None:
        from pywhispercpp.model import Model
        _LM = Model(str(LOCAL_MODEL), language="ar",
                    print_progress=False, print_realtime=False, print_timestamps=False)
    return _LM

# سياق المرآة — يضبطه `audit()` من ترويسة الفهرس.
MIRROR = {"riwaya": None, "reciter": None, "used": {}}
_MIRROR_DECIDED = {}

def _mirror_url(url):
    """مرآةُ الصوت على الدلو إن كانت **مطابقةً في الحجم** للمصدر.

    ⛔ الشرط ليس «موجودة» بل **«موجودةٌ ومطابقة»**: الفهرس حُوذي على صوت
    المصدر، فقياسُه على ملفٍ آخر — ولو باسمٍ واحد — قياسٌ لغير ما حُوذي.
    فإن اختلف الحجم أو تعذّر التحقق **رجعنا إلى المصدر ولم نخاطر**."""
    riwaya, reciter = MIRROR.get("riwaya"), MIRROR.get("reciter")
    if not (riwaya and reciter):
        return None
    m = re.search(r"(\d{3})\.mp3$", url)
    if not m:
        return None
    key = f"audio/{riwaya}/{reciter}/{m.group(1)}.mp3"
    try:
        cl, b = s3()
        size = cl.head_object(Bucket=b, Key=key)["ContentLength"]
    except Exception:
        return None
    try:
        import urllib.request
        rq = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(rq, timeout=30) as r:
            src = int(r.headers.get("Content-Length") or 0)
    except Exception:
        return None
    if src and size == src:
        return cl.generate_presigned_url("get_object", Params={"Bucket": b, "Key": key},
                                         ExpiresIn=3600), key, size
    return None

def _local_audio(url):
    LOCAL_CACHE.mkdir(parents=True, exist_ok=True)
    # ⛔ **قرار المرآة يُتّخذ مرّةً لكل ملف، لا لكل نافذة.** كان يُستدعى مع كل
    # قصّة (‏600 مرة للعيّنة الواحدة) وكلٌّ منها طلبا HEAD — فصار الفحصُ أبطأ
    # من التنزيل الذي جاء ليُسرّعه، وعلّق التشغيل بلا تقدّم. والأدهى أنه كان
    # يفحص حتى ما هو **مخبّأٌ أصلاً** فلا حاجة إلى مصدره البتة.
    p0 = LOCAL_CACHE / (hashlib.sha256(url.encode()).hexdigest()[:16] + ".mp3")
    if p0.exists() and p0.stat().st_size >= 10_000:
        return str(p0)                       # مخبّأ — لا مرآة ولا شبكة
    if url not in _MIRROR_DECIDED:
        _MIRROR_DECIDED[url] = _mirror_url(url)
    mir = _MIRROR_DECIDED[url]
    if mir:
        url, mkey, msize = mir
        MIRROR["used"][mkey] = msize
    p = LOCAL_CACHE / (hashlib.sha256(url.encode()).hexdigest()[:16] + ".mp3")
    if not p.exists() or p.stat().st_size < 10_000:
        # ⛔ **مهلةٌ صريحة وإعادةُ محاولة.** ‏`urlretrieve` بلا مهلةٍ افتراضية،
        # فاتصالٌ يتوقّف يعلّق العملية **إلى الأبد**: علّق قياس 400 حدّ 54
        # دقيقة عند نافذةٍ واحدة بلا تقدّمٍ ولا خطأ — والمخبأ لا ينمو والسجل
        # لا يتحرّك، فيبدو بطئاً وهو تعليق. وفي وظيفةٍ سحابية يبتلع المهلة
        # كلها (‏6 ساعات) بلا مخرَج.
        import urllib.request, shutil
        last = None
        for attempt in (1, 2, 3):
            try:
                with urllib.request.urlopen(url, timeout=90) as r, open(p, "wb") as f:
                    shutil.copyfileobj(r, f)
                if p.stat().st_size >= 10_000:
                    break
                last = RuntimeError(f"ملفٌ مبتور ({p.stat().st_size} بايت)")
            except Exception as ex:
                last = ex
                time.sleep(2 * attempt)
        else:
            raise RuntimeError(f"تعذّر تنزيل {url}: {last}")
    return str(p)

# ───────── جلبُ نافذةِ البايتات وحدها (بدل الملفّ الكامل) ─────────
# ⛔ **لماذا:** ملفّات بعض القرّاء ضخمة — البقرةُ عند `s_alquraishi` **373.9
# م.ب** (‏320 ك.ب/ث) — فتنزيلُ الملفّ كاملاً لقصّ خمس ثوانٍ يجرّ نهراً لشرب
# كوب. ومئتا حدٍّ تعني عشرات الجيجابايت، وقد وقف قياسٌ 13 دقيقة بلا ملفٍّ
# جديدٍ في المخبأ. والخوادم تُعلن `Accept-Ranges: bytes` فالمخرج متاح.
#
# ⛔ **وحدُّ الأمان الذي لا يُرفع:** إزاحةُ بايتٍ خاطئة تعني سماعَ موضعٍ غير
# الذي يُحكم عليه — وهو **أخطر أصناف العطب** لأنه لا يُخطئ بصخب بل يُبرّئ
# بصمت. ⇒ لا يُستعمل النطاق إلا على ملفٍّ **ثابت معدّل البتّ (CBR)** يُحسب
# فيه الزمن من الإزاحة **بالضبط** لا بالتقدير؛ وأيُّ شكٍّ (‏Xing/Info/VBRI أو
# ترويسةٌ لا تُقرأ) ⇒ **الرجوع إلى التنزيل الكامل**.
_BITRATES = (None, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, None)
_RATES = {0: 44100, 1: 48000, 2: 32000}
_CBR_INFO = {}
_NO_RANGE = os.environ.get('QA_NO_RANGE') == '1'   # مفتاحُ إطفاءٍ للمقارنة

def _mp3_cbr(url):
    """(بدايةُ الصوت, معدّل البتّ بت/ث) للملفّ الثابت، أو None لغيره."""
    if url in _CBR_INFO:
        return _CBR_INFO[url]
    out = None
    try:
        import urllib.request
        rq = urllib.request.Request(url, headers={"Range": "bytes=0-65535"})
        with urllib.request.urlopen(rq, timeout=45) as r:
            if r.status != 206:              # لا يدعم النطاقات ⇒ لا مجازفة
                _CBR_INFO[url] = None
                return None
            head = r.read(65536)
        off = 0
        if head[:3] == b"ID3":               # تخطّي وسم ID3v2 بحجمه المُرمَّز
            off = 10 + int.from_bytes(bytes(b & 0x7F for b in head[6:10]), "big")
        while off < len(head) - 4:           # أوّل تزامنٍ صالح
            if head[off] == 0xFF and (head[off + 1] & 0xE0) == 0xE0:
                h = head[off:off + 4]
                ver, layer = (h[1] >> 3) & 3, (h[1] >> 1) & 3
                bi, ri = (h[2] >> 4) & 0xF, (h[2] >> 2) & 3
                if ver == 3 and layer == 1 and _BITRATES[bi] and ri in _RATES:
                    frame = head[off:off + 900]
                    if b"Xing" in frame or b"Info" in frame or b"VBRI" in frame:
                        break                # VBR ⇒ الزمن لا يُشتقّ من الإزاحة
                    out = (off, _BITRATES[bi] * 1000)
                break
            off += 1
    except Exception:
        out = None
    _CBR_INFO[url] = out
    return out

def _range_pcm(url, start_ms, end_ms):
    """يُرجع (موجة أحادية 16ك.هز, معدّل) من نطاقِ بايتاتٍ، أو None للرجوع للكامل."""
    info = _mp3_cbr(url)
    if not info:
        return None
    audio0, bps = info
    byps = bps / 8.0
    pad = int(byps * 1.5)                    # هامشٌ سخيّ: إعادةُ التزامن تُهدر إطاراً
    b0 = max(audio0, audio0 + int(start_ms / 1000 * byps) - pad)
    b1 = audio0 + int(end_ms / 1000 * byps) + pad
    try:
        import io, urllib.request, numpy as np, soundfile as sf
        rq = urllib.request.Request(url, headers={"Range": f"bytes={b0}-{b1}"})
        with urllib.request.urlopen(rq, timeout=90) as r:
            if r.status != 206:
                return None
            buf = r.read()
        x, sr = sf.read(io.BytesIO(buf), dtype="float32", always_2d=True)
        if not len(x):
            return None
        x = x.mean(axis=1)
        # زمنُ أوّل بايتٍ جُلب — ومنه تُقتطع النافذة المطلوبة بالضبط.
        t0 = (b0 - audio0) / byps
        a = int(max(0.0, start_ms / 1000 - t0) * sr)
        b = int(max(0.0, end_ms / 1000 - t0) * sr)
        x = x[a:b]
        return (x, sr) if len(x) > sr * 0.2 else None
    except Exception:
        return None


_MIRROR_LOCK = threading.Lock()


def _prefetch(jobs, workers=4):
    """يُسخّن مخبأ الصوت للنوافذ القادمة **بالتوازي مع التفريغ**.

    ⛔ **آمنٌ على الحكم بالبناء لا بالوعد:** لا يُغيّر مُدخلاً ولا يمسّ قصّاً —
    غايتُه أن يكون الملفّ حاضراً حين يُطلب، والنتيجةُ واحدةٌ سواءٌ نُزّل قبل
    الطلب أم عنده. (اقترحه github-f4 على قياسٍ صحيح: المعالج عند **35%**
    والباقي انتظارُ شبكة.)

    ولا يُطبَّق على مسار النطاقات: ذاك يجلب بضعةَ كيلوبايت عند الحاجة فلا
    شيء يُسخَّن. وأخطاءُ التسخين **تُبتلع عمداً** — فالمسار الأصلي سيُعيد
    المحاولة بمهلته وإعاداته، ولا يصحّ أن يُسقط التسخينُ قياساً."""
    seen, order = set(), []
    for j in jobs:
        u = j["url"]
        if u not in seen:
            seen.add(u)
            order.append(u)
    def one(u):
        try:
            if _range_pcm is not None and not _NO_RANGE and _mp3_cbr(u):
                return                        # النطاقات تكفي — لا تنزيلَ كاملاً
        except Exception:
            pass
        try:
            with _MIRROR_LOCK:
                if u not in _MIRROR_DECIDED:
                    _MIRROR_DECIDED[u] = _mirror_url(u)
            _local_audio(u)
        except Exception:
            pass                              # التسخين لا يُسقط قياساً
    ts = []
    for i in range(max(1, workers)):
        th = threading.Thread(target=lambda i=i: [one(u) for u in order[i::workers]],
                              daemon=True)
        th.start()
        ts.append(th)
    return ts


def local_run(jobs, _host=None, _threads=None):
    """يقصّ بـ`soundfile` (يفكّ MP3 بلا ffmpeg) ويفرّغ بالنموذج المحلي."""
    import numpy as np, soundfile as sf
    m = _local_model()
    _prefetch(jobs)
    res, errs = {}, {}
    for j in jobs:
        try:
            got = None if _NO_RANGE else _range_pcm(j["url"], max(0, j["startMs"]), j["endMs"])
            if got is not None:
                x, r = got
            else:
                mp3 = _local_audio(j["url"])
                r = sf.info(mp3).samplerate
                a, b = int(max(0, j["startMs"]) / 1000 * r), int(j["endMs"] / 1000 * r)
                x, _ = sf.read(mp3, start=a, stop=b, dtype="float32", always_2d=True)
                x = x.mean(axis=1)
            n = int(len(x) * 16000 / r)
            y = np.interp(np.linspace(0, len(x) - 1, n), np.arange(len(x)), x).astype("float32")
            res[j["id"]] = {"text": " ".join(sg.text for sg in m.transcribe(y)).strip(), "ms": 0}
        except Exception as ex:
            errs[j["id"]] = f"{type(ex).__name__}: {ex}"[:200]
    return res, errs

def push_worker(host):
    subprocess.run(["scp", "-q", "-i", str(SSH_KEY), "-o", "StrictHostKeyChecking=no",
                    str(WORKER), f"root@{host}:{REMOTE}"], check=True, timeout=120)

# ───────────────────────── الحكم بتمريرين ─────────────────────────
FWD_MS, DEC_MS, LONG_MS = 5000, 4200, 8000
MIN_BLOCK = 4      # أصغر كتلة تطابق يُعتدّ بها (حرفاً)
MIN_TOTAL = 6      # مجموع الحروف المتطابقة اللازم لإثبات «هذا هو النص»
MIN_LEAK  = 6      # أقل تسرّبٍ يُعتدّ به: كلمةٌ قرآنية قصيرة («راجعون»، «العٰلمين»)
                   # — دونها ضجيج. والحارس أن التسرّب يمرّ بتمريرٍ ثانٍ أطول دائماً.
RASM_TOL  = 2      # إزاحة ≤ حرفين على المطلع = فرق رسم لا عطب

def _match_from(ref_sk, heard_sk, need=MIN_TOTAL):
    """أول موضعٍ في `ref_sk` يبدأ عنده التطابق — بمجموع الكتل لا بأطولها.

    ⛔ درسٌ مقيس: `find_longest_match` وحدها **تكسرها فروق الرسم**. «يَٰٓأَهْلَ»
    هيكلها `ياهل` و«يا أهل» المنطوقة `يااهل`، فألفٌ واحدة تقطع الكتلة نصفين
    فتسقط تحت أي عتبة معقولة ويُطبع «غير حاسم» على مطلعٍ سليمٍ تماماً. وقع
    ذلك على 4:171 و12:11 و2:46 في أول تشغيل — 22 من 48 حدّاً. فالعبرة
    بمجموع الكتل المتطابقة وبموضع أولاها."""
    if not ref_sk or not heard_sk:
        return None
    sm = difflib.SequenceMatcher(None, ref_sk, heard_sk, autojunk=False)
    # تفريغٌ قصيرٌ جداً (كلمة واحدة) يطابق النصّ بتمامه شاهدٌ كافٍ على موضعه —
    # فالعتبتان تُخفَّضان إلى طوله ولا يُسقَط بحجّة القِصَر.
    blocks = [b for b in sm.get_matching_blocks() if b.size >= min(MIN_BLOCK, len(heard_sk))]
    if not blocks:
        return None
    first = blocks[0]
    if sum(b.size for b in blocks) >= min(need, len(heard_sk)):
        return first
    # تطابقٌ على المطلع نفسه (الطرفان عند الصفر) شاهدٌ كافٍ ولو قصرت الكتلة:
    # النافذة تبدأ بالآية، وذاك كل ما نحتاجه لنفي العطب.
    if first.a <= RASM_TOL and first.b <= RASM_TOL and first.size >= 3:
        return first
    return None

def _whole_words(ws, nchars):
    """كم كلمةً كاملة من `ws` تقع داخل أول nchars حرفاً من هيكلها."""
    acc = n = 0
    for w in ws:
        acc += len(w)
        if acc <= nchars:
            n += 1
        else:
            break
    return n

def judge(ref_text, prev_text, fwd, dec, long_fwd):
    """يُرجع (الحكم، الصنف، الشاهد). الصنف: جسيم | طفيف | بريء | غير حاسم."""
    rw, ref_sk = words(ref_text), skel(ref_text)[:60]
    pw, prev_sk = words(prev_text), skel(prev_text)[-40:]
    if not skel(fwd or ""):
        return "غير حاسم", "غير حاسم", "تفريغ التمرير الأول فارغ (صمتٌ أو قصاصة قصيرة)"
    h = skel(fwd)

    # (أ) تسرّب مادةٍ سابقة في **أول** النافذة الأمامية ⇒ الحدّ مبكّر
    lead = h[:40]
    pm = difflib.SequenceMatcher(None, prev_sk, lead, autojunk=False).find_longest_match(
        0, len(prev_sk), 0, len(lead)) if prev_sk else None
    rm = _match_from(ref_sk, h)
    leak = pm.size if (pm and pm.size >= MIN_LEAK and pm.b <= 4
                       and (rm is None or pm.b + pm.size <= rm.b + 4)) else 0

    if leak:
        # التمرير الثاني للمبكّر: نافذةٌ أمامية أطول — الشظية العابرة تُبرَّأ فيها
        h2 = skel(long_fwd or "")
        pm2 = difflib.SequenceMatcher(None, prev_sk, h2[:48], autojunk=False).find_longest_match(
            0, len(prev_sk), 0, min(48, len(h2))) if h2 else None
        if not (pm2 and pm2.size >= MIN_LEAK and pm2.b <= 4):
            return "بريء", "بريء", f"اشتباه تسرّب لم يثبت في التمرير الثاني · سُمع: «{(fwd or '')[:40]}»"
        whole = _whole_words(pw[::-1], leak)
        kind = "جسيم" if whole >= 1 else "طفيف"
        label = "WRONG_AYAH" if whole >= 3 else "EARLY_START"
        return label, kind, (f"النافذة تبدأ بمادة الآية السابقة ({whole} كلمة كاملة · {leak} حرفاً هيكلياً): "
                             f"«{fwd[:50]}» · والآية تبدأ بـ«{' '.join(rw[:3])}»")

    # (ب) سقوط مطلع الآية ⇒ الحدّ متأخّر
    if rm is None:
        return "غير حاسم", "غير حاسم", f"لا يطابق التفريغ نصّ الآية ولا سابقتها · سُمع: «{fwd[:50]}»"
    if rm.a <= RASM_TOL:
        # ≤ حرفين إزاحةً على المطلع فرقُ رسمٍ لا عطب (ألف «يا أيها» الزائدة مثالاً)
        return "بريء", "بريء", f"المطلع مطابق: «{fwd[:45]}»"

    # التمرير الثاني الحاسم: نافذةٌ **تنتهي** عند الحدّ — ظهور كلمات الآية فيها = تأخّرٌ يقيناً
    d = skel(dec or "")
    dm = _match_from(ref_sk[:rm.a + 20], d)
    if not dm:
        return "بريء", "بريء", (f"اشتباه تأخّر لم تؤكّده النافذة الحاسمة (قبل الحدّ سُمع: "
                                f"«{(dec or 'صمت')[:35]}») — إنذارٌ أول كاذب")
    lost = _whole_words(rw, rm.a)
    kind = "جسيم" if lost >= 1 else "طفيف"
    what = f"«{' '.join(rw[:lost])}»" if lost else f"مطلع «{rw[0]}»"
    return "LATE_START", kind, (f"يسقط {what} ({lost} كلمة كاملة) · القصاصة تبدأ «{fwd[:38]}» "
                                f"· والنافذة الحاسمة قبل الحدّ فيها نصّ الآية: «{(dec or '')[:38]}»")

# ───────────────────────── مجال الثقة العنقودي ─────────────────────────
_T95 = {2: 12.71, 3: 4.303, 4: 3.182, 5: 2.776, 6: 2.571, 7: 2.447, 8: 2.365, 9: 2.306, 10: 2.262}

def cluster_ci(rates):
    """مجال 95% **على مستوى العنقود** — التصميم عنقودي، والمجال الثنائي
    الساذج يُظهر يقيناً أكبر من الحقيقة."""
    k = len(rates)
    if k < 2:
        return None
    m = sum(rates) / k
    var = sum((x - m) ** 2 for x in rates) / (k - 1)
    se = math.sqrt(var / k)
    t = _T95.get(k, 1.96)
    return m, max(0.0, m - t * se), min(1.0, m + t * se)

# ───────────────────────── التدقيق الكامل لفهرس ─────────────────────────
def _verdict(fatal, rate, ci_high, decision=()):
    """الحكم — على الحدّ الأعلى للمجال لا على التقدير وحده (D-068).

    و`decision` صنفٌ رابع لا يُرفض ولا يُقبل: **قرارُ منتَجٍ مطلوب**. لا يُرقّى
    آلياً لأن أحداً لم يقرّر بعد، ولا يُوصم عطباً لأن الأداة لا تملك القرار."""
    if fatal:
        return "مرفوض (خلل بنيوي)"
    if decision:
        return "موقوف — قرارُ منتَجٍ مطلوب: " + " · ".join(decision)[:120]
    if rate is None:
        return "بنيوياً سليم — بلا عيّنة صوتية"
    if rate > 0.05:
        return f"مرفوض (عطبٌ جسيم {rate:.1%} > 5%)"
    if ci_high is not None and ci_high > 0.05:
        return f"حدّي (التقدير {rate:.1%} والحدّ الأعلى {ci_high:.1%} > 5%)"
    return "مقبول"

def _finish(rep, rows, by_cluster, seed, nerr):
    def rate(pred):
        cl = [sum(1 for k in v if pred(k)) / len(v) for v in by_cluster.values() if v]
        n = sum(len(v) for v in by_cluster.values())
        hit = sum(1 for v in by_cluster.values() for k in v if pred(k))
        return hit, n, cluster_ci(cl)

    sev = rate(lambda k: k == "جسيم")
    any_ = rate(lambda k: k in ("جسيم", "طفيف"))
    rep["sample"] = {"seed": seed, "seedSalt": os.environ.get("QA_SEED_SALT", ""),
                     "clusters": sorted(by_cluster), "rows": rows,
                     "severe": sev, "any": any_, "errors": nerr}
    sev_rate = sev[0] / sev[1] if sev[1] else 0.0
    rep["severeRate"] = sev_rate
    # ⛔ الحكم على **الحدّ الأعلى للمجال** لا على التقدير النقطي (‏D-068):
    # تقديرٌ 4.5% بمجالٍ يبلغ 8.6% لا يُقال عنه «مقبول» — فالعتبة تُقرأ حيث
    # يمكن أن تكون الحقيقة لا حيث تقع أفضل تخمين. ووسمٌ ثالث «حدّي» يفصل
    # ما اجتاز النقطة ولم يجتز المجال، فلا يُخلط بالمقبول ولا بالمردود.
    lo, hi = (sev[2][1], sev[2][2]) if sev[2] else (None, None)
    rep["ciLow"], rep["ciHigh"] = lo, hi
    if MIRROR.get("used"):
        rep["audioSource"] = {"mirror": sorted(MIRROR["used"]), "note":
                              "مرآةُ الدلو استُعملت حيث طابق حجمُها المصدر؛ وما عداها من المصدر"}
    if rep["fatal"]:
        rep["verdict"] = "مرفوض (خلل بنيوي)"
    elif rep.get("decision"):
        rep["verdict"] = ("موقوف — قرارُ منتَجٍ مطلوب: "
                          + " · ".join(rep["decision"])[:120])
    elif sev_rate > 0.05:
        rep["verdict"] = f"مرفوض (عطبٌ جسيم {sev_rate:.1%} > 5%)"
    elif hi is not None and hi > 0.05:
        rep["verdict"] = f"حدّي (التقدير {sev_rate:.1%} والحدّ الأعلى {hi:.1%} > 5%)"
    else:
        rep["verdict"] = "مقبول"
    return rep

def rejudge(key, args):
    """إعادة الحكم من التفريغات المحفوظة — بلا خادمٍ ولا تفريغٍ جديد.

    وجودها ليس ترفاً: معايرة قاعدة الحكم تحتاج تكراراً، وإعادة تفريغ 144
    نافذة في كل تكرار تستهلك من الخادم ما هو للفهرسة لا لنا. والتفريغ
    محفوظٌ في `state/` مع كل حكم، فالشاهد ثابتٌ والحكم وحده يُعاد."""
    p = STATE / (key.replace("/", "_") + ".json")
    rep = json.loads(p.read_text(encoding="utf-8"))
    old = rep.get("sample")
    if not old:
        raise RuntimeError("لا عيّنة محفوظة لهذا الفهرس")
    txt = json.loads(gzip.decompress((ASSETS / f"text_{rep['riwaya']}.jz").read_bytes()).decode("utf-8"))
    rows, by_cluster = [], {}
    for x in old["rows"]:
        if "heard" not in x:
            rows.append(x)
            continue
        s, a = map(int, x["aid"].split(":"))
        prev = txt[flat(s, a - 1)] if a > 1 else (BASMALA if s not in (1, 9) else "")
        h = x["heard"]
        v, kind, why = judge(txt[flat(s, a)], prev, h.get("fwd"), h.get("dec"), h.get("long"))
        rows.append({**x, "verdict": v, "kind": kind, "why": why})
        by_cluster.setdefault(x["cluster"], []).append(kind)
    return _finish(rep, rows, by_cluster, old["seed"], old["errors"])

def _src_mtime(key):
    try:
        return next((r["mtime"] for r in list_indexes() if r["key"] == key), None)
    except Exception:
        return None

def audit(key, args):
    idx, sha = fetch_index(key, getattr(args, "expect_sha", None))
    rid, riwaya = idx.get("reciterId", "?"), idx.get("riwaya", "?")
    _tp = ASSETS / f"text_{idx.get('riwaya')}.jz"
    _txt = json.loads(gzip.decompress(_tp.read_bytes()).decode("utf-8")) if _tp.exists() else None
    fatal, warn, info = structural(idx, key, getattr(args, "allow_unmarked", False), _txt)
    rep = {"key": key, "reciterId": rid, "riwaya": riwaya, "info": info,
           "band": getattr(args, "band", None), "refined": getattr(args, "refined", None),
           "fatal": fatal, "warn": warn, "decision": info.get("decision") or [],
           # ⛔ **نسبُ الحكم — من غيره يصير حكمان متطابقان دليلاً كاذباً على
           # اتفاق وهما حكمٌ واحدٌ كُتب مرتين.** (طلبُ github-f4 عبر 3a، وهو
           # عينُ ما نبّهتُ عليه في `alijon`: النسبُ يُحمل في الكائن لا
           # يُستنبط.) و`engine` منها لأن محرّكين مختلفين **لا يُقارَن حكماهما**
           # — أثبتته ليلةُ اليوم: بُرِّئ مطلعٌ على الخادم وأُدين محلياً على
           # البصمة نفسها والملفّين متطابقين بايتاً.
           "kind": os.environ.get("QA_KIND", "audio"),
           "source": os.environ.get("QA_SOURCE", "local"),
           "runId": os.environ.get("QA_RUN_ID"),
           "engine": os.environ.get("QA_ENGINE", "pywhispercpp/ggml-q8 (tiny-ar-quran)"),
           "sample": None, "severeRate": None,
           "ts": time.time(), "srcMtime": _src_mtime(key), "sha256": sha}
    if args.struct_only:
        rep["kind"] = os.environ.get("QA_KIND", "struct")
        rep["verdict"] = ("مرفوض (خلل بنيوي)" if fatal else
                          ("موقوف — قرارُ منتَجٍ مطلوب: " + " · ".join(rep["decision"])[:120])
                          if rep.get("decision") else "بنيوياً سليم — بلا عيّنة صوتية")
        return rep

    tpath = ASSETS / f"text_{riwaya}.jz"
    if not tpath.exists():
        rep["verdict"] = f"تعذّرت العيّنة: لا نصّ مرجعي للرواية {riwaya!r}"
        return rep
    txt = json.loads(gzip.decompress(tpath.read_bytes()).decode("utf-8"))
    if len(txt) != 6236:
        rep["verdict"] = f"تعذّرت العيّنة: النص المرجعي {len(txt)} لا 6236"
        return rep

    if getattr(args, "local", False):
        MIRROR.update({"riwaya": idx.get("riwaya"), "reciter": idx.get("reciterId"), "used": {}})
    seed, sample = sample_boundaries(idx, args.clusters, args.per_cluster,
                                     getattr(args, "band", None), getattr(args, "long_seg", False),
                                     {"yes": True, "no": False}.get(getattr(args, "refined", None)))
    if not sample:
        rep["verdict"] = "تعذّرت العيّنة (لا سور كافية في الفهرس)"
        return rep

    jobs, meta = [], {}
    for s, e in sample:
        aid = e["ayahId"]
        a, st = int(aid.split(":")[1]), e["startMs"]
        prev = txt[flat(s, a - 1)] if a > 1 else (BASMALA if s not in (1, 9) else "")
        meta[aid] = {"s": s, "ref": txt[flat(s, a)], "prev": prev,
                     "band": e.get("confBand"), "startApprox": e.get("startApprox", False)}
        u = e["fileRef"]
        jobs += [{"id": f"F|{aid}", "url": u, "startMs": st, "endMs": st + FWD_MS},
                 {"id": f"D|{aid}", "url": u, "startMs": max(0, st - DEC_MS), "endMs": st},
                 {"id": f"L|{aid}", "url": u, "startMs": st, "endMs": st + LONG_MS}]

    # مسبار المطالع: العتبة (< 3ث) تُرشِّح والصوت يحكم. نقصّ من مطلع الآية
    # الأولى 6ث؛ فإن ظهرت البسملة **داخل** المدخل فهي مبتلعة يقيناً، وإلا
    # فالقارئ سريعُ البسملة لا أكثر — ولا يصحّ رفضٌ على عتبةٍ وحدها.
    E1 = {e["ayahId"]: e for e in idx["entries"]}
    openers = [s for s, _ in info.get("earlyList", [])][:12]
    for s in openers:
        e1 = E1.get(f"{s}:1")
        if e1:
            # نافذتان: ما **قبل** المدخل (أتمّت البسملة قبله؟) وما بعده.
            # ⛔ نافذةُ ما بعده وحدها **لا تفرّق** بين «البسملة كلها داخل
            # المدخل» و«ذيلٌ منها يتداخل بأجزاء الثانية» — وهما عطبان
            # مختلفان في الشدّة. وقع على `hawashi` 5:1: أدانه المسبار
            # «بسملةً مبتلعة» وإنما كان **~450م.ث من ذيلها** (شظيّة =
            # طفيف)، بينما `koshi_warsh` 73:1 بسملتُه كاملةً داخل المدخل
            # (= جسيم). ⇒ المسبار يقيس **المقدار** لا الوجود.
            jobs.append({"id": f"O|{s}", "url": e1["fileRef"],
                         "startMs": e1["startMs"], "endMs": e1["startMs"] + 6000})
            if e1["startMs"] > 300:
                jobs.append({"id": f"P|{s}", "url": e1["fileRef"],
                             "startMs": 0, "endMs": e1["startMs"]})

    res, errs = {}, {}
    for i in range(0, len(jobs), args.batch):
        runner = local_run if getattr(args, "local", False) else remote_run
        r, er = runner(jobs[i:i + args.batch], args.host, args.threads)
        res.update(r)
        errs.update(er)
        print(f"    …تفريغ {min(i + args.batch, len(jobs))}/{len(jobs)} نافذة", flush=True)

    rows, by_cluster = [], {}
    for aid, m in meta.items():
        g = lambda p: (res.get(f"{p}|{aid}") or {}).get("text", "")
        if not any(g(p) for p in "FDL") and f"F|{aid}" in errs:
            rows.append({"aid": aid, "cluster": m["s"], "verdict": "تعذّر", "kind": "غير حاسم",
                         "why": errs[f"F|{aid}"], "band": m["band"]})
            continue
        v, kind, why = judge(m["ref"], m["prev"], g("F"), g("D"), g("L"))
        rows.append({"aid": aid, "cluster": m["s"], "verdict": v, "kind": kind, "why": why,
                     "band": m["band"], "startApprox": m["startApprox"],
                     "heard": {"fwd": g("F"), "dec": g("D"), "long": g("L")}})
        by_cluster.setdefault(m["s"], []).append(kind)

    # حكم المطالع بالشاهد النصّي
    bas = skel(BASMALA)
    op_rows = []
    for s in openers:
        t = (res.get(f"O|{s}") or {}).get("text", "")
        pre = (res.get(f"P|{s}") or {}).get("text", "")
        hb = skel(t)[:len(bas) + 6]
        m = difflib.SequenceMatcher(None, bas, hb, autojunk=False).find_longest_match(
            0, len(bas), 0, len(hb)) if hb else None
        # كم من البسملة تمّ **قبل** المدخل؟ فما تمّ قبله ليس مبتلعاً.
        pb = difflib.SequenceMatcher(None, bas, skel(pre), autojunk=False)
        done_before = sum(b.size for b in pb.get_matching_blocks()) if pre else 0
        # «بسو» تفريغٌ شائع لـ«بسم» فالمقابلة بالهيكل لا بالحرف (درس QA_BOUNDARIES §و)
        inside = bool(m and m.size >= 8 and m.b <= 3)
        # مبتلعةٌ **جسيمة** فقط إذا لم يتمّ منها قبل المدخل إلا القليل.
        swallowed = inside and done_before < 0.4 * len(bas)
        frag = inside and not swallowed
        op_rows.append({"surah": s, "startMs": E1[f"{s}:1"]["startMs"], "heard": t,
                        "preHeard": pre, "basmalaBefore": done_before, "basmalaLen": len(bas),
                        "verdict": ("بسملة مبتلعة — مؤكَّدة بالصوت" if swallowed else
                                    f"شظيّة بسملة داخل المدخل (تمّ منها قبله {done_before}/{len(bas)} حرفاً) — طفيف"
                                    if frag else
                                    "بُرِّئ: لا بسملة داخل المدخل (بسملةٌ سريعة لا عطب)")})
    rep["openers"] = op_rows
    # المسبار وحده يرقّى المرشّح إلى حجب — لا العتبة
    for o in op_rows:
        if o["verdict"].startswith("بسملة"):
            rep["fatal"].append(f"بسملة مبتلعة في {o['surah']}:1 — مؤكَّدة بالصوت: «{o['heard'][:40]}»")
    return _finish(rep, rows, by_cluster, seed, len(errs))

# ───────────────────────── الطباعة ─────────────────────────
LIMITS = ("⚠️ حدود الحكم (تُقرأ معه لا بعده): ليست أذناً بشرية بل تفريغ whisper q8 مقابَلاً بالنص؛\n"
          "   لا تفصل ما دون ~0.3ث؛ تقيس وجود الأثر لا مقداره؛ ولا تُبلّغ إلا بشاهدٍ نصّي بعد تمريرين.\n"
          "   والنسب من عيّنة عنقودية 8×6 ومجالها واسعٌ بطبعه.")

def show(rep):
    i, s = rep["info"], rep["sample"]
    print(f"\n{'═' * 78}\n■ {rep['key']}  ({rep['reciterId']} · {rep['riwaya']})")
    print(f"  بنيوي: مداخل {i.get('entries')}/6236 · سور {i.get('surahs','?')}/114 · "
          f"بصمات {i.get('sha','?')}/114 · محرك {i.get('engine')} · exactEnds={i.get('exactEnds')} "
          f"· نطاقات {i.get('bands')}")
    for x in rep["fatal"]:
        print(f"  🔴 خلل بنيوي: {x}")
    for x in rep["warn"]:
        print(f"  ⚠️  مرشّح (لا حكم): {x}")
    for o in rep.get("openers") or []:
        mark = "🔴" if o["verdict"].startswith("بسملة") else "✅"
        print(f"  {mark} مطلع {o['surah']}:1 ({o['startMs']}م.ث) — {o['verdict']} · سُمع: «{o['heard'][:45]}»")
    if s:
        print(f"\n  عيّنة عمياء: بذرة {s['seed']} · عناقيد {s['clusters']} · "
              f"{s['any'][1]} حدّاً · تمريران لكل حدّ")
        print(f"  {'الآية':>8} {'النطاق':>5} {'الحكم':>12} {'الصنف':>10}  الشاهد")
        order = {"جسيم": 0, "طفيف": 1, "غير حاسم": 2, "بريء": 3}
        for r in sorted(s["rows"], key=lambda r: (order.get(r["kind"], 9), r["aid"])):
            mark = {"جسيم": "🔴", "طفيف": "🟡", "بريء": "✅"}.get(r["kind"], "⚪")
            print(f"  {mark}{r['aid']:>7} {str(r.get('band')):>5} {r['verdict']:>12} "
                  f"{r['kind']:>10}  {r['why'][:96]}")
        for nm, (hit, n, ci) in (("العطب الجسيم (إسقاط كلمة)", s["severe"]), ("أي أثرٍ في الحدّ", s["any"])):
            if not n:
                print(f"  📐 {nm}: —")
                continue
            c = f" · مجال 95% عنقودي: {ci[1]:.1%} – {ci[2]:.1%}" if ci else ""
            print(f"  📐 {nm}: {hit}/{n} = {hit/n:.1%}{c}")
        if s["errors"]:
            print(f"  ⚠️ نوافذ تعذّر تفريغها: {s['errors']}")
    print(f"\n  ⇒ الحكم: {rep['verdict']}\n{LIMITS}")

# ───────────────────────── main ─────────────────────────
def main():
    ap = argparse.ArgumentParser(description="تدقيق فهارس التوقيتات — بأمر واحد")
    ap.add_argument("keys", nargs="*", help="qalun/husary_qalun أو المفتاح الكامل timings/…jz")
    ap.add_argument("--all", action="store_true", help="كل فهارس R2")
    ap.add_argument("--new", action="store_true", help="ما لم يُدقَّق بعدُ فقط")
    ap.add_argument("--watch", type=int, metavar="ث", help="دورة دائمة: يدقّق كل جديدٍ أولاً بأول")
    ap.add_argument("--struct-only", action="store_true", help="بنيوي فقط (بلا خادم ولا صوت)")
    ap.add_argument("--rejudge", action="store_true",
                    help="إعادة الحكم من التفريغات المحفوظة (معايرة القاعدة بلا تفريغ جديد)")
    ap.add_argument("--clusters", type=int, default=8)
    ap.add_argument("--per-cluster", type=int, default=6)
    ap.add_argument("--refined", choices=["yes", "no"],
                    help="طبقة الصقل: المصقول وحده أو الأصلي وحده (رقمٌ للطبقة لا للفهرس)")
    ap.add_argument("--long-seg", action="store_true",
                    help="طبقة الحدود داخل مقاطع >10ث — حيث يهدم -ac 512 التفريغ")
    ap.add_argument("--band", choices=["HIGH", "MED"],
                    help="عيّنة مطبَّقة على نطاقٍ واحد — الرقم الناتج معدّل عطب ذلك النطاق")
    ap.add_argument("--batch", type=int, default=24, help="نوافذ لكل جولة SSH")
    ap.add_argument("--threads", type=int, default=2,
                    help="خيوط whisper — عمليةٌ واحدة لكل جهة (درس العدة §8)")
    ap.add_argument("--allow-unmarked", action="store_true",
                    help="اقبل فهرساً بلا أثر صقلٍ في الترويسة (للفهارس القديمة) — يبقى تحذيراً")
    ap.add_argument("--expect-sha", metavar="sha256",
                    help="ارفض التدقيق إن لم يطابق المحتوى هذه البصمة — المفتاح لا يعرّف المحتوى")
    ap.add_argument("--local", action="store_true",
                    help="التفريغ على هذا الجهاز بالنموذج نفسه (حين ينقطع الخادم)")
    ap.add_argument("--host", default=QA_HOST)
    ap.add_argument("--json", metavar="ملف", help="حفظ التقرير خاماً")
    a = ap.parse_args()

    STATE.mkdir(parents=True, exist_ok=True)
    if not (a.struct_only or a.rejudge or a.local):
        push_worker(a.host)

    def targets():
        if a.keys:
            # يقبل المفتاح كاملاً (بما فيه `timings-staging/…` للفهارس التي
            # تُدقَّق **قبل** نشرها) أو المختصر `riwaya/reciter`.
            out = []
            for k in a.keys:
                if "/" in k and k.split("/")[0].startswith("timings"):
                    out.append(k if k.endswith(".jz") else k + ".jz")
                else:
                    out.append("timings/" + k + ("" if k.endswith(".jz") else ".jz"))
            return out
        if a.rejudge:
            return sorted(p.name[:-5].replace("_", "/", 1).replace("_", "/", 1)
                          for p in STATE.glob("timings_*.json"))
        rs = list_indexes()
        if a.new or a.watch:
            # ⛔ «جديد» = مفتاحٌ لم يُدقَّق **أو فهرسٌ تغيّر تحت مفتاحه**.
            # الجيل الثاني يُرفع فوق المفاتيح نفسها، فمراقبةٌ تكتفي بالأسماء
            # الجديدة تُعلن «لا جديد» بينما كل الفهارس استُبدلت تحتها.
            fresh = []
            for r in rs:
                sp = STATE / (r["key"].replace("/", "_") + ".json")   # الممثِّلة وحدها تحكم «هل دُقّق؟»
                if not sp.exists():
                    fresh.append(r["key"])
                    continue
                try:
                    if json.loads(sp.read_text(encoding="utf-8")).get("srcMtime") != r["mtime"]:
                        fresh.append(r["key"])
                except Exception:
                    fresh.append(r["key"])
            return fresh
        return [r["key"] for r in rs]

    reports, seen_bad = [], []
    while True:
        for k in targets():
            print(f"\n▶ تدقيق {k} …", flush=True)
            try:
                rep = rejudge(k, a) if a.rejudge else audit(k, a)
            except Exception as ex:
                print(f"  ⛔ تعذّر التدقيق: {ex}")
                continue
            show(rep)
            reports.append(rep)
            if rep["verdict"].startswith("مرفوض"):
                seen_bad.append(rep["key"])
            # ⛔ لا يُمحى تقريرٌ فيه عيّنةٌ صوتية بتقريرٍ بنيويٍّ فقط: العيّنة
            # كلّفت خادماً ووقتاً، والبنيوي يُعاد في ثوانٍ. (وقع فعلاً: جولة
            # `--struct-only --all` محت عيّنات dokali وtareq وm_sayed.)
            suffix = (f".band-{a.band}" if getattr(a, "band", None) else "") +                      (f".refined-{a.refined}" if getattr(a, "refined", None) else "") +                      (".longseg" if getattr(a, "long_seg", False) else "")
            sp = STATE / (k.replace("/", "_") + suffix + ".json")
            if sp.exists() and rep.get("sample") is None:
                try:
                    old = json.loads(sp.read_text(encoding="utf-8"))
                    # ⛔ **الشاهد لا يُنقل إلا إلى بصمته.** كان الدمج يحفظ
                    # العيّنة والمطالع ويختمها بالبصمة **الجديدة**، فينشأ
                    # سجلٌّ يدّعي أن شاهداً من نسخةٍ يخصّ نسخةً أخرى. وقع
                    # فعلاً على `koshi_warsh`: سجّل «مطلع 85:1 عند 0م.ث»
                    # تحت بصمةٍ مداخلُها تقول 5185م.ث — فأدنتُ مطلعاً سليماً
                    # بشاهدٍ من نسخةٍ زائلة. ⇒ اختلاف البصمة يُسقط الشاهد.
                    if old.get("sha256") and old["sha256"] != rep.get("sha256"):
                        old = {}
                    if old.get("sample"):
                        # ⛔ ولا يكفي حفظ العيّنة: **الحكم يُعاد حسابه منها**.
                        # كان التقرير البنيوي يُبقي العيّنة ويكتب فوق الحكم
                        # «بنيوياً سليم — بلا عيّنة صوتية»، فيصير الملف يحمل
                        # عيّنةً بمعدّل 0.0% وحكماً يقول إنه بلا عيّنة —
                        # **وبوابة الترقية تشترط «مقبول» حرفاً فتحجبه بلا سبب**.
                        # وقع فعلاً على `huthaify_qalun` بعد أن قيس 0/200.
                        sr = old.get("severeRate")
                        rep = {**rep, "sample": old["sample"], "openers": old.get("openers"),
                               "severeRate": sr, "sampleFrom": old.get("ts"),
                               "ciLow": old.get("ciLow"), "ciHigh": old.get("ciHigh"),
                               "verdict": _verdict(rep["fatal"], sr, old.get("ciHigh"))
                                          if sr is not None else rep["verdict"]}
                except Exception:
                    pass
            sp.write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
        if not a.watch:
            break
        time.sleep(a.watch)

    if a.json:
        Path(a.json).write_text(json.dumps(reports, ensure_ascii=False, indent=1), encoding="utf-8")
    if seen_bad:
        print(f"\n🔴 مرفوض ويجب حجبه قبل المانيفست: {len(seen_bad)} — {', '.join(seen_bad)}")
    sys.exit(1 if seen_bad else 0)

if __name__ == "__main__":
    main()
