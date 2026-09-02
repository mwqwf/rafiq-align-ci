"""تابع الفهرسة — يمرئي صوت القارئ تلقائياً متى اكتمل فهرسه ونجح تدقيقه.

⛔ المبدأ الحاكم: **المرآة تتبع الفهرسة ولا تسبقها.**
   من يُبنى له فهرس يُمرأى، ومن لا فهرس له فمرآته مئات الميغابايت بلا مستهلك.

الحلقة:
  ١. اسرد `timings/**/*.jz` على R2.
  ٢. لكل فهرس جديد: دقّقه (بنية + عدد الآي + مصفوفة audioSha256).
  ٣. جِد مصدر القارئ من `catalog/reciters.json` (يُرفع من الفهرس المحلي).
  ٤. امرئ ملفات سوره (‏114) بنسخ بايتي حرفي مع تحقق Content-Length.
  ٥. طابق sha لكل ملف مع `audioSha256` في الفهرس.
  ٦. أدرجه في `audio/{riwaya}/manifest.json` مع sha لكل ملف وحكم المطابقة.

⛔ بوابات لا تُتجاوز:
   - لا إدراج لقارئ ناقص (‏114/114 وناقص=0 ومبتور=0).
   - `usableForClips` لا تصير true إلا بمطابقة sha كاملة — فهرس مُوقَّت على تسجيل
     لا يصلح لتقطيع تسجيل آخر، وانزياح المللي يفسد الحدود.
   - ⚠️ وضع السور **لا تُفحص فيه بوابة العدّ** (لا ملفات آحاد): مرور 114/114
     **دليل اكتمال لا دليل صحة عدّ**. المرآة تشهد أن الملفات الـ114 حضرت
     كاملةً غير مبتورة، ولا تشهد أن ترقيم آيها كوفي — فالملف الواحد يحوي
     السورة كلها فلا موضع فيه للاختبار. صحة العدّ في هذا الوضع يثبتها
     **الفهرس** (‏`ayahCounting` فيه مبنيّ على نص الرواية الكوفي 6236 خانة)
     لا المرآة. ولذلك يُكتب في المانيفست صراحةً:
     `countingGate: "SKIPPED_SURAH_MODE"` كي لا يُقرأ الاكتمال شهادةَ عدّ.
   - ⛔ بوابة العدّ الثمانية (`counting_gate`) **إلزامية** لقراء آية-بآية —
     مجلد مرقَّم بغير الكوفي يشغّل الآية الخطأ صامتاً (D-025).
   - ⛔ `audio/_quarantine/` مقبرة لا مستودع عمل: **لا يُكتب فيها بحال**.
"""
import gzip, hashlib, json, os, sys, threading, time
import boto3, requests
from concurrent.futures import ThreadPoolExecutor

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


# ⛔ بوابة العدّ الثمانية (‏D-025) — ثماني آيات يفترق عندها الكوفي عن غيره:
# وجود الملف = المجلد كوفي، وغيابه = عدّ آخر. مصدرها الواحد mirror_worker.
GATE_PROBES = ["101011", "107007", "074056", "075040",
               "079046", "055078", "057029", "073020"]

COUNTING_NOTE = ("وضع السور: 114/114 دليل اكتمال لا دليل صحة عدّ — "
                 "الملف يحوي السورة كلها فلا موضع فيه لاختبار الترقيم، "
                 "وصحة العدّ يثبتها الفهرس (ayahCounting) لا المرآة. "
                 "أما قراء آية-بآية فبوابة العدّ الثمانية إلزامية عليهم "
                 "(countingGate=KUFI شرط الإدراج).")


def env(k):
    v = os.environ.get(k)
    if not v:
        sys.exit(f"⛔ متغير البيئة {k} غير مضبوط")
    return v


BUCKET = env("R2_BUCKET")
POLL = int(os.environ.get("FOLLOW_POLL_SECONDS", "300"))
THREADS = int(os.environ.get("FOLLOW_THREADS", "6"))
ONCE = bool(os.environ.get("FOLLOW_ONCE"))
FORCE_BACKFILL = bool(os.environ.get("FOLLOW_BACKFILL_FORCE"))
# ذاكرة ما مُرئي — على القرص لا في الرام: إعادة التشغيل بلا هذا تُعيد قراءة
# جيغابايتات من الدلو لإعادة حساب بصمات قارئ فُرغ منه، فيصير الاستئناف عقوبة.
SEEN_PATH = os.environ.get("FOLLOW_SEEN", "/root/follower_seen.json")
# سطر لكل قارئ مُرئي: الأرقام مقيسة عند حدوثها لا مستنتجة من طوابع السجل
RESULTS_PATH = os.environ.get("FOLLOW_RESULTS", "/root/follower_results.jsonl")


def record(row):
    try:
        with LOCK:
            with open(RESULTS_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + chr(10))
    except Exception as e:
        log(f"⚠️ تعذّر تسجيل النتيجة: {e}")


def load_seen():
    try:
        return {tuple(x) for x in json.load(open(SEEN_PATH, encoding="utf-8"))}
    except Exception:
        return set()


def save_seen(seen):
    try:
        tmp = SEEN_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(sorted(list(x) for x in seen), f)
        os.replace(tmp, SEEN_PATH)   # استبدال ذرّي: لا ملف نصفَ مكتوب عند القتل
    except Exception as e:
        log(f"⚠️ تعذّر حفظ ذاكرة المرآة: {e}")
LOGPATH = os.environ.get("MIRROR_LOG", "mirror_follower.log")


def s3c():
    return boto3.client("s3", endpoint_url=env("R2_ENDPOINT"),
                        aws_access_key_id=env("R2_ACCESS_KEY_ID"),
                        aws_secret_access_key=env("R2_SECRET_ACCESS_KEY"),
                        region_name="auto")


s3 = s3c()
_t = threading.local()
LOCK = threading.Lock()


def s3t():
    if not hasattr(_t, "c"):
        _t.c = s3c()
    return _t.c


def http():
    if not hasattr(_t, "h"):
        _t.h = requests.Session()
        _t.h.headers["User-Agent"] = "Mozilla/5.0 (QuranRafiq asset mirror)"
    return _t.h


def guard_key(key):
    """⛔ المحجر مقبرة لا مستودع عمل — ما دخله دخله لسبب، والكتابة فيه تُحييه."""
    if "_quarantine" in key:
        raise PermissionError(f"⛔ كتابة ممنوعة تحت مسار محجور: {key}")
    return key


def put(client, key, **kw):
    """المنفذ الوحيد للكتابة في الدلو — لا put_object خارجه."""
    return client.put_object(Bucket=BUCKET, Key=guard_key(key), **kw)


def log(m):
    line = time.strftime("%Y-%m-%d %H:%M:%S") + "  " + m
    print(line, flush=True)
    with LOCK:
        with open(LOGPATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")


def listing(prefix, etags=None):
    out, tok = {}, None
    while True:
        kw = dict(Bucket=BUCKET, Prefix=prefix, MaxKeys=1000)
        if tok:
            kw["ContinuationToken"] = tok
        r = s3.list_objects_v2(**kw)
        for o in r.get("Contents", []):
            out[o["Key"]] = o["Size"]
            if etags is not None:
                etags[o["Key"]] = o["ETag"]
        if not r.get("IsTruncated"):
            break
        tok = r["NextContinuationToken"]
    return out


def load_catalog():
    d = json.loads(s3.get_object(Bucket=BUCKET, Key="catalog/reciters.json")
                   ["Body"].read())
    out = {}
    for r in d["riwayat"]:
        for x in r["reciters"]:
            out[(r["id"], x["id"])] = x
    return out


def counting_gate(base):
    """بوابة العدّ الثمانية: KUFI / NOT_KUFI / UNKNOWN — ثمانية HEAD بلا بايت واحد.

    ثماني آيات يفترق عندها الكوفي عن سواه: حضور ملفها في مجلد آية-بآية
    يشهد أن ترقيمه كوفي، وغيابه يشهد أنه عدّ آخر. وربط عدّ غير كوفي
    بمعرفاتنا يُسمع الحافظ آيةً ويقرأ غيرها صامتاً (‏D-025).
    """
    def one(p_):
        for _ in range(3):
            try:
                r = http().head(base + p_ + ".mp3", timeout=30,
                                allow_redirects=True)
                if r.status_code in (200, 404):
                    return r.status_code == 200
            except Exception:
                pass
        return None
    with ThreadPoolExecutor(4) as ex:
        res = list(ex.map(one, GATE_PROBES))
    if any(r is None for r in res):
        return "UNKNOWN", res
    return ("KUFI" if all(res) else "NOT_KUFI"), res


def backfill_gates():
    """يختم مانيفستات الروايات بالحقول الثلاثة — ولا يحذف مدخلاً بحال.

    قراء آية-بآية أُدرجوا قبل سنّ البوابة تُقاس بوابتهم الآن فعلاً (لا افتراضاً)،
    ومن سقط منها يُوسم ويُمنع من القصاصات ويبقى مدخله شاهداً على القياس.
    """
    for key in sorted(listing("audio/")):
        if not key.endswith("/manifest.json"):
            continue
        riwaya = key.split("/")[1]
        cur = json.loads(s3.get_object(Bucket=BUCKET, Key=key)["Body"].read())
        changed = False
        for e in cur.get("reciters", []):
            if e.get("countingGate") and not FORCE_BACKFILL:
                continue
            # مدخلات قديمة بلا "mode": يُستنتج من عدد الملفات لا يُترك فارغاً،
            # فالفراغ جعل usableForClips تسقط ظلماً عن قارئ آية-بآية مكتمل.
            if not e.get("mode"):
                e["mode"] = "surah" if e.get("files") == 114 else "ayah"
            if e.get("mode") == "surah":
                e["ayahCounting"] = e.get("ayahCounting") or "kufi"
                e["countingGate"] = "SKIPPED_SURAH_MODE"
            else:
                v, res = counting_gate(e["source"])
                e["ayahCounting"] = "kufi" if v == "KUFI" else "NOT_KUFI_MEASURED"
                e["countingGate"] = v
                e["countingGateProbes"] = {
                    p: ("200" if r else ("404" if r is False else "?"))
                    for p, r in zip(GATE_PROBES, res)}
                if v != "KUFI":
                    e["usableForClips"] = False
                    e["usableForFullSurah"] = False
                log(f"[{riwaya}/{e['id']}] بوابة العدّ: {v}")
            # آية-بآية بعدّ كوفي: كل ملف آيةٌ بحدّها، فالقصاصة عين الملف
            if e.get("mode") == "ayah":
                e["usableForClips"] = e.get("countingGate") == "KUFI"
                e["usableForFullSurah"] = e["usableForClips"]
            e.setdefault("usableForClips", False)
            e["countingGateNote"] = COUNTING_NOTE
            changed = True
        if changed:
            cur["countingNote"] = COUNTING_NOTE
            cur["updated"] = int(time.time())
            put(s3, key, ContentType="application/json",
                Body=json.dumps(cur, ensure_ascii=False, indent=1).encode("utf-8"))
            log(f"✅ {key} — خُتمت حقول العدّ")


DIAG_PREFIX = "catalog/diagnosis/"
WEAK_DROP = 0.5      # سقوط أقل منه لا يُفحص
WEAK_SHORT = 0.70    # دون هذا من المتوقع ⇒ الصوت مُتَّهم
WEAK_OK = 0.85       # فوقه ⇒ الصوت بريء والتهمة على المحاذاة
WEAK_LONG = 1.30     # فوقه ⇒ الملف **أطول** من سورته — عيبٌ آخر لا محاذاة
WEAK_SPAN = 0.85     # امتداد الفهرس فوقه ⇒ الصوت كله من السورة، والبطء ترتيل
WEAK_GAP = 0.08      # فجوةٌ عن أقرب سورةٍ أعلى — بها يصير المنخفض **شاذاً**
WEAK_CERTAIN = 0.50  # ودون هذا فالبتر يقينيّ ولا يحتاج فجوة
# ⛔ نطاق «يُذكر ولا يُدان»: شذوذُ مدةٍ لم يبلغ حدّ الحكم يبقى **مسجَّلاً**.
# وسببه عيبٌ وقع: `husary_douri` س25 (‏نسبة 0.60 بلا سقوط) **اختفت من ملف
# التشخيص كلياً** بعد تشديد الحكم — وهي الحالة التي بدأ منها التحقيق وما
# زالت محجوزة عند البوابة. فحُكمٌ أُسقط لا يعني شاهداً يُمحى: من يقرأ
# الملف بعدنا يجب أن يجد الرقم الذي حُجزت عليه، لا فراغاً يوحي بالسلامة.
WEAK_NOTE_LO = 0.80
WEAK_NOTE_HI = 1.20


def _isolated(ratio, all_ratios):
    """أشاذٌّ هو أم ذيلُ تشتّتٍ طبيعي؟ — الانعزال هو الفارق.

    ما دون `WEAK_CERTAIN` يقينٌ بذاته (لا ترتيل يضاعف السرعة). وما فوقه
    لا يُعدّ بتراً إلا إذا انفصل عن أقرب سورةٍ أعلى منه بفجوةٍ بيّنة.
    """
    if ratio < WEAK_CERTAIN:
        return True
    higher = [x for x in all_ratios if x > ratio + 1e-9]
    return bool(higher) and (min(higher) - ratio) >= WEAK_GAP


def classify_weak(riwaya, rid, idx, guard):
    """فرز سور القارئ الضعيفة: صوتٌ مبتور أم محاذاة ساقطة؟

    ⛔ يُبنى على مدد الحارس نفسها — **لا تنزيل إضافي**: الحارس نزّل الـ114
    قبل قليل، وتنزيلها ثانيةً ثمنٌ بلا مقابل على مصدرٍ نحسن جواره.

    والقاعدة (معتمدة): نصيب السقوط يقول «هنا خلل» ولا يفرّق، والمدة تفصل —
    وعلاجا الحالتين **متضادّان**: المبتور يُوسم ولا يُعاد، والساقط يُعاد
    ولا يُوسم. فوسمُ الساقط يُعفيه من الإعادة بغير حق فيبقى ناقصاً أبداً.
    """
    if not guard or not guard.get("durations"):
        return None
    dur, words = guard["durations"], guard["words"]
    index = load_index_cached()
    ayahs = {s["n"]: s["ayahs"] for s in index["surahs"]}
    per = {}
    for e in idx.get("entries", []):
        n = int(e["ayahId"].split(":")[0])
        per[n] = per.get(n, 0) + 1
    # ⛔ الوتيرة من الحارس نفسه (وسيطُ النسبة على السور كلها بتكرار)، لا من
    # «السور السليمة» وحدها. والسبب عيبٌ وقع فعلاً: قارئٌ تغطيته منخفضة في
    # كل سوره **لا سليمَ له**، فكانت الأداة تعجز عن بناء الوتيرة **فتتخطّاه
    # كله صامتة** — أي أن أسوأ القراء، وهم أولى بالفحص، كانوا يسقطون منه.
    # (‏`3siri` سقط هكذا وفيه سورة التوبة عند خُمس طولها.)
    # ⛔ النموذج ذو معاملين: **مدة = ثابت + وتيرة × كلمات**. وكنتُ أستعمل
    # الوتيرة وحدها وأُهمل الثابت — أي **نصف نموذج**، فانحرف حسابي عن حساب
    # الحارس نفسه في الملف نفسه (‏husary_douri س25: قلتُ 0.62 وقال شريكي
    # 0.73 بالمنهج الصحيح). ونصفُ نموذجٍ أسوأ من نموذجٍ آخر: يوهم الاتساق.
    rate = guard.get("msPerWord")
    overhead = guard.get("overheadMs") or 0
    if not rate:
        return None
    # امتداد الفهرس في الملف: يفصل «صوتٌ زائد غريب» عن «ترتيلٍ بطيء».
    span = {}
    for e in idx.get("entries", []):
        n = int(e["ayahId"].split(":")[0])
        a, b = span.get(n, (10 ** 12, 0))
        span[n] = (min(a, e["startMs"]), max(b, e["endMs"]))
    # ⛔ الشذوذ يُعرَّف بالانعزال لا بالموضع: قارئٌ تشتّته واسع تقع سوره
    # الطبيعية تحت أي عتبةٍ ثابتة. قِيس على قارئين: `akri` مئينه العاشر 0.88
    # وسورة 24 عنده **0.39** والتالية 0.72 ⇒ فجوةٌ 0.33 وشذوذٌ بيّن؛ و
    # `hawashi` مئينه العاشر **0.72** وأدناه 0.60 متصلاً بلا فجوة ⇒ تسع سور
    # كانت تُتَّهم بالبتر وهي في ذيل تشتّته الطبيعي (ترتيلٌ أسرع لا بتر).
    all_ratios = sorted(
        dur[n] / (overhead + rate * words[n])
        for n in dur if words.get(n, 0) >= 30 and (overhead + rate * words[n]))
    rows = []
    for n in range(1, 115):
        drop = 1 - per.get(n, 0) / ayahs[n]
        ratio, span_share = None, None
        if n in dur and words.get(n, 0) >= 30:
            ratio = round(dur[n] / (overhead + rate * words[n]), 2)
            if n in span and dur[n]:
                span_share = round((span[n][1] - span[n][0]) / dur[n], 2)
        # ⛔ عيب الصوت يُفحص في **كل** سورة لا في الضعيفة وحدها: ملفٌ مبتور
        # قد يُشحن له فهرسٌ شبه تامّ (‏akri س24: 57 من 64 وصوتها 39%) —
        # وهي أخطر الحالات لأن التوقيت يبدو كاملاً على صوتٍ غير موجود.
        if ratio is not None and ratio < WEAK_SHORT and _isolated(ratio,
                                                                   all_ratios):
            v = "AUDIO_SHORT"
        elif (ratio is not None and ratio > WEAK_LONG
              and (span_share is None or span_share < WEAK_SPAN)):
            # ⛔ الزيادة لا تكفي وحدها: سورٌ تُرتَّل بطيئاً بطبعها (الرحمن
            # بترجيعها) فتبدو «أطول» وليس فيها صوتٌ غريب. فالفارز الثاني:
            # **أيمتدّ الفهرس على الملف كله؟** فإن امتدّ فالصوت كله من
            # السورة والبطء ترتيل، وإن قصر فثمّ صوتٌ لا يفسّره نصّها.
            v = "AUDIO_LONG"
        elif drop < WEAK_DROP and (ratio is None
                                   or WEAK_NOTE_LO <= ratio <= WEAK_NOTE_HI):
            continue                   # لا سقوط ولا شذوذ مدة ⇒ لا شيء يُقال
        elif ratio is None:
            v = "UNJUDGED_SHORT"
        elif ratio >= WEAK_OK:
            v = "ALIGNMENT_FAILED"
        else:
            v = "UNCLEAR"
        rows.append({"surah": n, "shipped": per.get(n, 0), "ayahs": ayahs[n],
                     "dropShare": round(drop, 2), "durationRatio": ratio,
                     "indexSpanShare": span_share, "verdict": v})
    return rows


_index_cache = {}


def load_index_cached():
    if "i" not in _index_cache:
        sys.path.insert(0, "/root/QuranRafiq/tools/alignment")
        from common import load_index
        _index_cache["i"] = load_index()
    return _index_cache["i"]


DIAG_NOTE = ("نصيب السقوط يكشف الخلل والمدة تفصل: مبتورٌ يُوسم ولا يُعاد، "
             "وساقطٌ يُعاد ولا يُوسم. و«أطول» لا تُعلن إلا بامتدادِ فهرسٍ "
             "ناقص — فالسور البطيئة ترتيلاً تبدو أطول بلا عيب. والسور دون "
             "30 كلمة لا يحكمها الزمن؛ فارز LOW أقرب إليها.")


DIAG_SCHEMA = 2      # صيغة ملف التشخيص — يُرفع عند أي تغيير في الحقول


def write_diagnosis(riwaya, rid, idx, guard, index_key=None):
    """يكتب تشخيص القارئ إلى catalog/diagnosis/ — **منفذٌ واحد** للآلي
    وللختم الرجعي معاً، كي لا تفترق صيغتان تدّعيان أنهما واحدة."""
    try:
        weak = classify_weak(riwaya, rid, idx, guard)
        if weak is None:
            return None
        cnt = {}
        for w in weak:
            cnt[w["verdict"]] = cnt.get(w["verdict"], 0) + 1
        # ⛔ الربط ببصمة الفهرس لا بالزمن وحده: الطابع الزمني يقول «متى
        # كُتب» ولا يقول «عمّ كُتب». وتشخيصٌ أُعيد توليده من فهرسٍ قديم يبدو
        # أحدثَ من الفهرس الجديد، فتُبنى بوابةٌ على حكمٍ لا يخصّ ما تحجزه.
        # فالمستهلك يقارن `indexETag` بالبصمة الحالية: اختلافها = تشخيصٌ
        # لا يصف هذا الفهرس، ويُهمَل مهما كان طابعه حديثاً.
        etag = None
        try:
            k = index_key or "timings/{}/{}.jz".format(riwaya, rid)
            etag = s3.head_object(Bucket=BUCKET, Key=k)["ETag"].strip('"')
        except Exception:
            pass
        put(s3, "{}{}/{}.json".format(DIAG_PREFIX, riwaya, rid),
            ContentType="application/json",
            Body=json.dumps({"schema": DIAG_SCHEMA,
                             "riwaya": riwaya, "reciter": rid,
                             "generatedAt": int(time.time()),
                             "indexETag": etag,
                             "indexGeneratedAt": idx.get("generatedAt"),
                             "indexEntries": len(idx.get("entries") or []),
                             "staleIf": ("indexETag يخالف بصمة "
                                         "timings/{riwaya}/{reciter}.jz "
                                         "الحالية ⇒ التشخيص لا يصف هذا "
                                         "الفهرس فيُهمَل"),
                             "refineVersion": idx.get("refineVersion",
                                                      "unknown"),
                             "msPerWord": guard.get("msPerWord"),
                             "overheadMs": guard.get("overheadMs"),
                             "counts": cnt, "weakSurahs": weak,
                             "note": DIAG_NOTE},
                            ensure_ascii=False, indent=1).encode("utf-8"))
        if cnt:
            log("   🔬 تشخيص: {} — {}{}/{}.json".format(
                cnt, DIAG_PREFIX, riwaya, rid))
        return cnt
    except Exception as e:
        log("   ⚠️ تشخيص السور الضعيفة تعذّر: {}".format(e))
        return None


def surah_duration_guard(riwaya, rid, threads):
    """حارس المدة لوضع السور — جزءٌ من قبول المرآة لا فحصٌ لاحق (أمر المشرف).

    يسأل ما لا يسأله غيره: **أي سورة في هذا الملف، وأتامّةٌ هي؟** فالبصمة
    تشهد أننا نسخنا ما عند المصدر لا أن المصدر تامّ، وبوابة العدّ معطَّلة
    هنا أصلاً. رُصد حياً: `3siri` سورة التوبة بخُمس طولها — وبصمتها MATCH.
    """
    try:
        sys.path.insert(0, "/root")
        import probe_surah_duration as psd
        return psd.check(riwaya, rid, threads)
    except Exception as e:
        log("   ⚠️ حارس مدة السور تعذّر: {}".format(e))
        return None


def audit_index(idx):
    """يرجع (سليم؟, سبب). التدقيق قبل أي تنزيل — لا نمرئي على فهرس معطوب."""
    if not isinstance(idx, dict):
        return False, "ليس كائناً"
    entries = idx.get("entries")
    if not isinstance(entries, list) or not entries:
        return False, "لا مدخلات"
    sha = idx.get("audioSha256")
    if not isinstance(sha, list) or len(sha) != 114:
        return False, f"audioSha256 ليست 114 (‏{len(sha) if isinstance(sha, list) else '—'})"
    bad = [e for e in entries[:50]
           if not isinstance(e.get("startMs"), int)
           or not isinstance(e.get("endMs"), int)
           or e["endMs"] <= e["startMs"]]
    if bad:
        return False, f"حدود زمنية معطوبة ({len(bad)})"
    return True, f"{len(entries)} مدخلة"


def mirror_surahs(base, prefix, want_sha):
    """ينزّل الـ114 وينسخها بايتياً. يرجع {رقم السورة: (sha, bytes)}."""
    have = listing(prefix)
    out = {}

    def one(n):
        name = f"{n:03d}"
        key = prefix + name + ".mp3"
        for attempt in range(4):
            try:
                r = http().get(base + name + ".mp3", timeout=(20, 900))
                if r.status_code != 200:
                    raise IOError(f"HTTP {r.status_code}")
                data = r.content
                cl = r.headers.get("Content-Length")
                if cl is not None and int(cl) != len(data):
                    raise IOError(f"size mismatch {cl} != {len(data)}")
                if len(data) < 10000:
                    raise IOError(f"too small {len(data)}")
                if have.get(key) != len(data):
                    put(s3t(), key, Body=data, ContentType="audio/mpeg")
                with LOCK:
                    out[n] = (hashlib.sha256(data).hexdigest(), len(data))
                return
            except Exception as e:
                if attempt == 3:
                    log(f"   FAIL {name}: {e}")
                    return
                time.sleep(4 * (attempt + 1))

    todo = [n for n in range(114, 0, -1)
            if prefix + f"{n:03d}.mp3" not in have]
    log(f"   موجود {len(have)}/114 · للتنزيل {len(todo)}")
    with ThreadPoolExecutor(THREADS) as ex:
        list(ex.map(one, todo))

    # ما كان موجوداً سلفاً: تُقرأ تجزئته من R2 لا من المصدر
    for n in range(1, 115):
        if n not in out:
            k = prefix + f"{n:03d}.mp3"
            try:
                b = s3.get_object(Bucket=BUCKET, Key=k)["Body"].read()
                out[n] = (hashlib.sha256(b).hexdigest(), len(b))
            except Exception:
                pass
    return out


def publish(riwaya, rid, base, shas, idx, t0=None, downloaded=0,
            index_key=None):
    prefix = f"audio/{riwaya}/{rid}/"
    have = listing(prefix)
    missing = [n for n in range(1, 115) if prefix + f"{n:03d}.mp3" not in have]
    tiny = [k for k, v in have.items() if v < 10000]
    complete = not missing and not tiny and len(have) == 114
    log(f"   تدقيق: {len(have)}/114 — ناقص={len(missing)} مبتور={len(tiny)}")
    if not complete:
        log("   ⛔ غير مكتمل — لا إدراج في المانيفست.")
        record({"reciter": rid, "riwaya": riwaya, "complete": False,
                "files": len(have), "missing": len(missing), "tiny": len(tiny),
                "shaMatch": None, "seconds": round(time.time() - t0) if t0 else None,
                "ts": int(time.time())})
        return False

    # ⛔ حارس المدة قبل النشر: لا يمنع الإدراج (الصوت نافع في بقية سوره)
    # لكن يسم السورة المعيبة ويمنع قصاصاتها — والحجب بقدر العيب.
    dmis = []
    g = surah_duration_guard(riwaya, rid, THREADS)
    if g and g.get("verdict") == "SUSPECT":
        for x in g.get("suspect", []):
            ratio = round(x["durationMs"] / max(x["expectedMs"], 1), 2)
            dmis.append({"surah": x["surah"],
                         "kind": ("SHORT_AT_SOURCE" if ratio < 1
                                  else "LONG_AT_SOURCE"),
                         "durationMs": x["durationMs"],
                         "expectedMs": x["expectedMs"], "ratio": ratio})
        log("   ⛔ عيب مدة في سور: {}".format(
            ", ".join(str(d["surah"]) for d in dmis)))

    ref = idx.get("audioSha256") or []
    bad = [n for n in range(1, 115) if n in shas and shas[n][0] != ref[n - 1]]
    verdict = "MATCH" if (len(shas) == 114 and not bad) else (
        f"MISMATCH {bad[:10]}" if bad else "INCOMPLETE_SHA")
    log(f"   مطابقة audioSha256: {verdict} ({114-len(bad)}/114)")
    # ⛔ البوابة **لكل سورة** لا للقارئ جملةً:
    # سورة واحدة مخالفة لا تُسقط 113 سورة تطابق تسجيلَنا بايتاً ببايت — فتلك
    # توقيتاتها مبنية على نفس البايتات التي نخدمها، وقصاصاتها سليمة يقيناً.
    # والمخالفة وحدها تُمنع، فالخسارة بقدر العيب لا أوسع منه.
    bad_dur = {d["surah"] for d in dmis}
    sha_ok = {n: (n in shas and n - 1 < len(ref) and shas[n][0] == ref[n - 1])
              for n in range(1, 115)}
    clips_ok = {n: (sha_ok[n] and n not in bad_dur) for n in range(1, 115)}
    # ⛔ سببُ المنع يُصرَّح به لا يُخلط: «مخالفة بصمة» تعني أن الفهرس وُقِّت
    # على بايتات أخرى — **والسورة كاملةً تُشغَّل سليمة**؛ و«عيب مدة» تعني أن
    # الملف نفسه معطوب فلا يصلح لشيء. ومن يقرأ منعاً واحداً بمعنيين يُسقط
    # سوراً صالحة للتشغيل ظناً أنها معطوبة (نبّه عليه rafiq-packages، وكنتُ
    # أنا أفتيتُ بخلافه فأخطأت).
    clips_reason = {}
    for n in range(1, 115):
        if n in bad_dur:
            clips_reason[str(n)] = "DURATION_MISMATCH"   # الملف معطوب
        elif not sha_ok[n]:
            clips_reason[str(n)] = "SHA_MISMATCH"        # التوقيت لا يطابقه

    mkey = f"audio/{riwaya}/manifest.json"
    merged = {}
    try:
        cur = json.loads(s3.get_object(Bucket=BUCKET, Key=mkey)["Body"].read())
        for e in cur.get("reciters", []):
            merged[e["id"]] = e
    except Exception:
        pass
    merged[rid] = {
        "id": rid, "riwaya": riwaya, "source": base, "mode": "surah",
        "files": len(have), "bytes": sum(have.values()), "complete": True,
        # نظام العدّ من الفهرس نفسه (نصّ الرواية الكوفي 6236 خانة) لا من المرآة
        "ayahCounting": (idx.get("ayahCounting") or "KUFI").lower(),
        # ⚠️ في وضع السور لا تُفحص البوابة: الاكتمال ليس شهادة عدّ
        "countingGate": "SKIPPED_SURAH_MODE",
        "countingGateNote": COUNTING_NOTE,
        # ⚠️ تغطية الفهرس تُكشف ولا تُحجب: قارئ ثلثا آيه بلا توقيت لا يُعرض
        # كأنه قارئ مكتمل. واصفةٌ لا مانعة — الصوت نافع بذاته للتشغيل بالسورة
        # كاملة مهما كانت التغطية، والعتبة قرار المستهلك لا المرآة.
        "indexEntries": len(idx.get("entries") or []),
        "indexCoverage": round(len(idx.get("entries") or [])
                               / (idx.get("ayahCount") or 6236), 3),
        "indexSurahs": len({e["ayahId"].split(":")[0]
                            for e in (idx.get("entries") or [])}),
        "durationMismatchAtSource": dmis,
        "clipsBlockedReason": clips_reason,
        # جيل المحرّك من ترويسة الفهرس — كي يميّز المستهلك والكتالوج الجيلين
        # بلا فتح الملف (طلب المشرف، والحقول من f5).
        # ⛔ والغياب ليس "none": الغياب يعني فهرساً سابقاً للحقل أصلاً فلا
        # نعلم عنه شيئاً، و"none" يعني أن الوصفة الجديدة جرت ولم تصقل شيئاً.
        # فخلطهما يجعل فهرساً قديماً يبدو مقيساً، وهو ادّعاءٌ لا نملكه.
        "refineVersion": idx.get("refineVersion", "unknown"),
        "refinedCount": idx.get("refinedCount"),
        "medTargeted": idx.get("medTargeted"),
        "engineVersion": idx.get("engineVersion"),
        "timingIndexShaMatch": verdict,
        # ⛔ فهرس مُوقَّت على تسجيل لا يصلح لتقطيع تسجيل آخر
        "usableForClips": verdict == "MATCH",
        "usableForFullSurah": True,
        # المستهلك يقرأ clipsOk للسورة المطلوبة: يخدم قصاصاتها إن true،
        # وإلا يهبط إلى السورة كاملة. الحرمان بقدر العيب لا أوسع منه.
        "clipsOkBySurah": [n for n in range(1, 115) if clips_ok[n]],
        "clipsBlockedBySurah": [n for n in range(1, 115) if not clips_ok[n]],
        "perFile": [{"surah": n, "name": f"{n:03d}.mp3",
                     "bytes": shas[n][1], "sha256": shas[n][0],
                     "clipsOk": clips_ok[n]}
                    for n in sorted(shas)],
    }
    put(s3, mkey, ContentType="application/json",
        Body=json.dumps({"version": 1, "updated": int(time.time()),
                         "countingNote": COUNTING_NOTE,
                         "reciters": [merged[k] for k in sorted(merged)]},
                        ensure_ascii=False, indent=1).encode("utf-8"))
    write_diagnosis(riwaya, rid, idx, g, index_key)

    secs = round(time.time() - t0) if t0 else None
    log(f"   ✅ {mkey} — {rid}: {sum(have.values())/1e6:.1f}MB · "
        f"clips={verdict == 'MATCH'} · زمن المرآة {secs}ث ({(secs or 0)/60:.1f}د)")
    record({"reciter": rid, "riwaya": riwaya, "complete": True,
            "files": len(have), "missing": 0, "tiny": 0,
            "bytes": sum(have.values()), "downloaded": downloaded,
            "shaMatch": verdict, "shaOk": 114 - len(bad),
            "sampleSha": shas.get(1, ("—",))[0],
            "seconds": secs, "ts": int(time.time())})
    return True


def orphan_check(catalog):
    """فهارس مرفوعة بلا مرآة — تدقيقٌ ذاتي كل دورة.

    الاكتمال الظاهر أخطر من النقص الظاهر: تابعٌ يعمل بلا شكوى وفهرسٌ لا
    مرآة له يبدو نجاحاً. فيُسأل السؤال صراحةً كل دورة بدل انتظار من يسأله.
    """
    idx = [(k.split("/")[1], k.split("/")[2][:-3])
           for k in listing("timings/") if k.endswith(".jz")]
    mirrored = set()
    for r in {x[0] for x in idx}:
        try:
            m = json.loads(s3.get_object(
                Bucket=BUCKET,
                Key="audio/{}/manifest.json".format(r))["Body"].read())
        except Exception:
            continue
        for e in m.get("reciters", []):
            mirrored.add((r, e["id"]))
    orphans = [x for x in idx if x not in mirrored]
    nocat = [x for x in idx if x not in catalog]
    if orphans:
        log("⚠️ فهارس مرفوعة بلا مرآة ({}): {}".format(
            len(orphans), ", ".join("/".join(x) for x in orphans[:10])))
    if nocat:
        log("⚠️ فهارس بلا مدخل في الكتالوج ({}): {}".format(
            len(nocat), ", ".join("/".join(x) for x in nocat[:10])))
    return len(orphans), len(nocat)


def sweep(catalog, seen):
    etags = {}
    for key in sorted(listing("timings/", etags)):
        # فهرسٌ أُعيد رفعه (إعادة فهرسة) بصمته تتغير ⇒ تُعاد مرآته ولا يُبتلع صمتاً
        stamp = (key, etags.get(key))
        if not key.endswith(".jz") or stamp in seen:
            continue
        parts = key.split("/")
        if len(parts) != 3:
            continue
        riwaya, fname = parts[1], parts[2][:-3]
        rid = fname
        try:
            idx = json.loads(gzip.decompress(
                s3.get_object(Bucket=BUCKET, Key=key)["Body"].read()).decode())
        except Exception as e:
            log(f"[{key}] ⛔ تعذّرت القراءة: {e}")
            continue
        rid = idx.get("reciterId") or rid
        good, why = audit_index(idx)
        log(f"[{riwaya}/{rid}] فهرس جديد — التدقيق: {'سليم' if good else 'معطوب'} ({why})")
        if not good:
            log("   ⛔ لا مرآة على فهرس معطوب.")
            seen.add(stamp)
            continue
        ent = catalog.get((riwaya, rid))
        if not ent:
            # ⛔ لا يُضاف إلى الذاكرة: غياب المدخل حالٌ **عارض** يزول بتحديث
            # الكتالوج، لا عيبٌ في الفهرس. ووسمه «منجزاً» يدفنه إلى الأبد —
            # فيبقى فهرسٌ مرفوع بلا مرآة ولا يشتكي أحد، وهو أخبث ما يقع
            # لأنه يبدو اكتمالاً. فيُعاد في كل دورة حتى يظهر مدخله.
            log("   ⚠️ لا مدخل لـ{}/{} في catalog/reciters.json — "
                "يُعاد في الدورة القادمة (لا يُدفَن).".format(riwaya, rid))
            continue
        if ent.get("mode") != "surah":
            # آية-بآية مرآتها mirror_worker ببوابة العدّ الثمانية الإلزامية —
            # ولا يمرئيها هذا التابع لئلا تُدرج بلا بوابة.
            log(f"   (وضع {ent.get('mode')} — مرآته mirror_worker ببوابة العدّ) تخطٍّ.")
            seen.add(stamp)
            continue
        log(f"   المصدر: {ent['base']}")
        t0 = time.time()
        before = len(listing(f"audio/{riwaya}/{rid}/"))
        shas = mirror_surahs(ent["base"], f"audio/{riwaya}/{rid}/", True)
        if publish(riwaya, rid, ent["base"], shas, idx, t0, 114 - before,
                   key):
            seen.add(stamp)


def main():
    log(f"=== تابع الفهرسة — دورة كل {POLL}ث · خيوط {THREADS} ===")
    catalog = load_catalog()
    log(f"الفهرس: {len(catalog)} قارئاً")
    try:
        backfill_gates()
    except Exception as e:
        log(f"⚠️ ختم حقول العدّ تعذّر: {e}")
    seen = load_seen()
    log(f"ذاكرة المرآة: {len(seen)} فهرساً ممرأى سلفاً")
    while True:
        try:
            n = len(seen)
            sweep(catalog, seen)
            orphan_check(catalog)
            if len(seen) != n:
                save_seen(seen)
        except Exception as e:
            log(f"⚠️ خطأ في الدورة: {e}")
        if ONCE:
            break
        time.sleep(POLL)


if __name__ == "__main__":
    main()
