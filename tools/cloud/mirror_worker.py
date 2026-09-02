"""عامل المرآة على خادم الحوسبة — يجلب من المصدر ويرفع إلى R2 من داخل مركز البيانات.

يُشغَّل على الخادم مباشرة (لا على جهاز المالك) ⇒ صفر بايت على خط المالك.
لا مهلة دالة تقيّده، فلا حاجة لتقطيع دفعات: يمشي على القائمة كاملة بتوازي ثابت.

⛔ الأسرار: تُقرأ من متغيرات البيئة فقط — لا تُودَع في المستودع ولا تُمرَّر في سطر
   الأوامر (ps يكشفه). المطلوب:
     R2_ENDPOINT · R2_BUCKET · R2_ACCESS_KEY_ID · R2_SECRET_ACCESS_KEY
⛔ D-012: نسخ بايتي حرفي — لا إعادة ترميز ولا أي معالجة.

الضمانات (منقولة كما هي من المرآة المحلية بعد أن أثبتت ٧ ساعات بصفر أخطاء):
  ١. تحقق Content-Length لكل ملف قبل الرفع (كشف البتر).
  ٢. رفض أي جسم أصغر من الحد الأدنى (كشف صفحات الخطأ المقنَّعة).
  ٣. أربع محاولات بتراجع زمني، وتسجيل صريح لكل سقوط.
  ٤. استئناف: سرد R2 أولاً وتخطي الموجود ⇒ القتل والاستئناف بلا خسارة ولا تكرار.
  ٥. تدقيق ختامي بالاسم لا بالعدّ، وبوابة: لا مانيفست لقارئ ناقص.
"""
import argparse, hashlib, json, os, subprocess, sys, threading, time
import boto3, requests
from concurrent.futures import ThreadPoolExecutor

ROOT_TOOLS = os.environ.get("RAFIQ_TOOLS", "/root/QuranRafiq/tools/alignment")

TOTAL_AYAHS = 6236
SURAH_AYAHS = [
    7, 286, 200, 176, 120, 165, 206, 75, 129, 109, 123, 111, 43, 52, 99, 128,
    111, 110, 98, 135, 112, 78, 118, 64, 77, 227, 93, 88, 69, 60, 34, 30, 73,
    54, 45, 83, 182, 88, 75, 85, 54, 53, 89, 59, 37, 35, 38, 29, 18, 45, 60,
    49, 62, 55, 78, 96, 29, 22, 24, 13, 14, 11, 11, 18, 12, 12, 30, 52, 52,
    44, 28, 28, 20, 56, 40, 31, 50, 40, 46, 42, 29, 19, 36, 25, 22, 17, 19,
    26, 30, 20, 15, 21, 11, 8, 8, 19, 5, 8, 8, 11, 11, 8, 3, 9, 5, 4, 7, 3,
    6, 3, 5, 4, 5, 6,
]
assert sum(SURAH_AYAHS) == TOTAL_AYAHS and len(SURAH_AYAHS) == 114


def env(k):
    v = os.environ.get(k)
    if not v:
        sys.exit(f"⛔ متغير البيئة {k} غير مضبوط")
    return v


BUCKET = env("R2_BUCKET")


def s3c():
    return boto3.client(
        "s3", endpoint_url=env("R2_ENDPOINT"),
        aws_access_key_id=env("R2_ACCESS_KEY_ID"),
        aws_secret_access_key=env("R2_SECRET_ACCESS_KEY"), region_name="auto")


s3 = s3c()
_t = threading.local()


def s3t():
    if not hasattr(_t, "c"):
        _t.c = s3c()
    return _t.c


def http():
    if not hasattr(_t, "h"):
        _t.h = requests.Session()
        _t.h.headers["User-Agent"] = "Mozilla/5.0 (QuranRafiq asset mirror)"
    return _t.h


LOCK = threading.Lock()
LOGPATH = os.environ.get("MIRROR_LOG", "mirror_worker.log")

# السجل عربي: لا نسمح لطرفية لا تتقن UTF-8 بإسقاط المهمة كلها عند أول سطر.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def log(m):
    line = time.strftime("%Y-%m-%d %H:%M:%S") + "  " + m
    print(line, flush=True)
    with LOCK:
        with open(LOGPATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")


def existing(prefix):
    out, tok = {}, None
    while True:
        kw = dict(Bucket=BUCKET, Prefix=prefix, MaxKeys=1000)
        if tok:
            kw["ContinuationToken"] = tok
        r = s3.list_objects_v2(**kw)
        for o in r.get("Contents", []):
            out[o["Key"]] = o["Size"]
        if not r.get("IsTruncated"):
            break
        tok = r["NextContinuationToken"]
    return out


def names_for(mode):
    if mode == "surah":
        return [f"{n:03d}" for n in range(114, 0, -1)]
    out = []
    for n in range(114, 0, -1):                     # الأصغر أولاً
        out += [f"{n:03d}{a:03d}" for a in range(1, SURAH_AYAHS[n - 1] + 1)]
    return out


stats = {"ok": 0, "fail": 0, "bytes": 0}
shas = {}

# ⛔ بوابة نظام العدّ (‏D-025) — إلزامية لا خيارية.
# مجلد مرقَّم بعدّ غير كوفي يشغّل الآية الخطأ صامتاً، وهو أخطر من أي عطل ظاهر:
# المستخدم يسمع آية ويقرأ غيرها فيحفظ خطأً وهو مطمئن. اكتُشف حياً في
# warsh_Abdul_Basit_128kbps (المزمل 18 لا 20، القارعة 10 لا 11 …).
GATE_PROBES = ["101011", "107007", "074056", "075040",
               "079046", "055078", "057029", "073020"]


def counting_gate(base):
    """يرجع KUFI أو NOT_KUFI أو UNKNOWN — بثمانية طلبات HEAD لا تنزّل بايتاً."""
    def one(p):
        for _ in range(3):
            try:
                r = http().head(base + p + ".mp3", timeout=30, allow_redirects=True)
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


# ⛔ حارس المدة (‏D-025 امتداداً) — إلزامي لوضع الآي قبل قبول أي قارئ.
# بوابة العدّ تسأل «كم آية في المجلد؟»، والبصمة تسأل «أنقلنا ما عند المصدر؟».
# ولا واحدة منهما تسأل **«أي آية في هذا الملف؟»** — وقد نجا بذلك ياسين/ورش:
# اجتاز البوابة 8/8 وبصمته سليمة، وثلاثة جيوب فيه منزاحة المحتوى.
# وهذا الحارس يسأل السؤال الثالث بلا تفريغ ولا نموذج: القارئ يقرأ بوتيرة شبه
# ثابتة، فمدة الملف ∝ عدد كلمات آيته. وأقوى شاهد في تلك القضية جاء منه:
# ملف 4:12 مدته 16.2ث وآيته 88 كلمة تحتاج ~116ث — فاستحال أن تكون فيه.
DUR_TOL = 0.55       # انحراف نسبي فوقه يُعدّ الملف مشتبهاً به
DUR_MARGIN = 0.20    # وأن يكون جارٌ أليقَ بهذا الفارق قبل الاتهام
DUR_MIN_WORDS = 4    # «الم» ونحوها لا تُحاكَم — مدتها لا تدلّ


def probe_durations(prefix, slots, idx_list, threads):
    """يقيس مدة ملفات بعينها من الدلو — ffprobe فقط، بلا تفريغ."""
    import tempfile
    out = {}

    def one(i):
        sn, an = slots[i]
        key = "{}{:03d}{:03d}.mp3".format(prefix, sn, an)
        fd, p = tempfile.mkstemp(suffix=".mp3")
        try:
            body = s3t().get_object(Bucket=BUCKET, Key=key)["Body"].read()
            with os.fdopen(fd, "wb") as f:
                f.write(body)
            r = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", p],
                capture_output=True, text=True, timeout=60)
            ms = int(float(r.stdout.strip()) * 1000)
            with LOCK:
                out[i] = ms
        except Exception:
            pass
        finally:
            try:
                os.remove(p)
            except Exception:
                pass

    with ThreadPoolExecutor(threads) as ex:
        list(ex.map(one, idx_list))
    return out


def duration_guard(prefix, riwaya, sample, threads):
    """يرجع (حكم, تفصيل). لا يحذف ولا يكتب — يقيس ويصف.

    الوتيرة تُبنى بوسيط النسبة لا بانحدار المربعات: المنزاح نفسه داخل العيّنة،
    والمربعات تنجذب إليه فتضيع الإشارة؛ أما الوسيط فلا يبالي بالشواذ.
    """
    sys.path.insert(0, ROOT_TOOLS)
    from common import load_index, load_text, norm      # noqa
    text = load_text(riwaya)
    index = load_index()
    slots = []
    for s in index["surahs"]:
        for i in range(s["ayahs"]):
            slots.append((s["n"], i + 1))
    words = [len(norm(t).split()) for t in text]

    elig = [i for i in range(len(slots)) if words[i] >= DUR_MIN_WORDS]
    step = max(1, len(elig) // sample)
    idx = elig[::step][:sample]
    log("حارس المدة: قياس {} ملفاً…".format(len(idx)))
    dur = probe_durations(prefix, slots, idx, threads)
    if len(dur) < 30:
        return "UNKNOWN", {"measured": len(dur),
                           "why": "قياسات أقل من أن يُبنى عليها"}
    ratios = sorted(ms / words[i] for i, ms in dur.items())
    rate = ratios[len(ratios) // 2]
    suspect = []
    for i, ms in dur.items():
        err = abs(ms - rate * words[i]) / max(ms, 1)
        if err <= DUR_TOL:
            continue
        best, bo = err, 0
        for off in (-3, -2, -1, 1, 2, 3):
            j = i + off
            if 0 <= j < len(words) and words[j] >= DUR_MIN_WORDS:
                e2 = abs(ms - rate * words[j]) / max(ms, 1)
                if e2 < best - DUR_MARGIN:
                    best, bo = e2, off
        if bo:
            sn, an = slots[i]
            tsn, tan = slots[i + bo]
            suspect.append({"ayah": "{}:{}".format(sn, an), "slot": i,
                            "fitsBetter": "{}:{}".format(tsn, tan),
                            "offset": bo, "durationMs": ms,
                            "words": words[i]})
    # ⛔ الفارق الحاسم ليس **عدد** المشتبهين بل **تكتّلهم**.
    # قِيس على قارئين معلومَين: ياسين (منزاح مثبت) 52 مشتبهاً، والدوسري
    # (سليم مثبت) 27 — والعدد وحده لا يفرّق بينهما. لكن مشتبهي ياسين تقع
    # على خانات متتالية (‏12:101 · 103 · 105 · 107 · 109) ومشتبهي الدوسري
    # متناثرون. فالتتابع بنيةٌ — أي انزياح حقيقي — والتناثر ضجيج قياس.
    slots_susp = sorted(x["slot"] for x in suspect)
    clustered = sum(1 for k, v in enumerate(slots_susp)
                    if (k and v - slots_susp[k - 1] <= 3)
                    or (k + 1 < len(slots_susp) and slots_susp[k + 1] - v <= 3))
    rateinfo = {"msPerWord": round(rate), "measured": len(dur),
                "suspect": len(suspect), "clustered": clustered,
                "tolerance": DUR_TOL,
                "margin": DUR_MARGIN, "samples": suspect[:40],
                "note": ("مدة الملف ∝ كلمات آيته. لا يفرّغ ولا يسمع — يقيس "
                         "الزمن فقط، فهو شاهد مستقل عن بوابة العدّ وعن البصمة "
                         "وعن أي تفريغ. «مشتبه» خبرٌ لا حكم: يحتاج شاهداً "
                         "ثانياً قبل أي إجراء.")}
    if not suspect:
        verdict = "CLEAN"
    elif clustered >= 4:
        verdict = "SUSPECT_POCKETS"      # تتابعٌ ⇒ انزياح بنيوي مرجَّح
    else:
        verdict = "SUSPECT_SCATTERED"    # تناثرٌ ⇒ ضجيج قياس مرجَّح
    return verdict, rateinfo


def fetch_one(name, base, prefix, have, min_bytes, want_sha):
    key = prefix + name + ".mp3"
    for attempt in range(4):
        try:
            r = http().get(base + name + ".mp3", timeout=(20, 600))
            if r.status_code != 200:
                if r.status_code in (403, 404):
                    with LOCK:
                        stats["fail"] += 1
                    log(f"MISS {r.status_code} {name}")
                    return
                raise IOError(f"HTTP {r.status_code}")
            data = r.content
            cl = r.headers.get("Content-Length")
            if cl is not None and int(cl) != len(data):
                raise IOError(f"size mismatch {cl} != {len(data)}")
            if len(data) < min_bytes:
                raise IOError(f"too small {len(data)}")
            if have.get(key) != len(data):
                s3t().put_object(Bucket=BUCKET, Key=key, Body=data,
                                 ContentType="audio/mpeg")
            with LOCK:
                stats["ok"] += 1
                stats["bytes"] += len(data)
                if want_sha:
                    shas[name] = (hashlib.sha256(data).hexdigest(), len(data))
            return
        except Exception as e:
            if attempt == 3:
                with LOCK:
                    stats["fail"] += 1
                log(f"FAIL {name}: {e}")
                return
            time.sleep(4 * (attempt + 1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--riwaya", required=True)
    ap.add_argument("--reciter", required=True)
    ap.add_argument("--base", required=True, help="مجلد المصدر (ينتهي بشرطة مائلة)")
    ap.add_argument("--mode", choices=("ayah", "surah"), default="ayah")
    ap.add_argument("--threads", type=int, default=10)
    ap.add_argument("--limit", type=int, default=0, help="سقف للاختبار")
    ap.add_argument("--no-manifest", action="store_true")
    ap.add_argument("--duration-sample", type=int, default=99999,
                    help="سقف ملفات حارس المدة — الافتراض الكل: المسح الكامل "
                         "للـ6236 كلّف 48ث مقياساً، والعيّنة تُعمي عن الجيوب "
                         "الصغيرة (16 آية في 6236 لا تصيبها عيّنة 300)")
    ap.add_argument("--skip-duration-guard", action="store_true",
                    help="⛔ لا تستعمله إلا بعذر معلن — الحارس هو ما يكشف "
                         "الانزياح الذي لا تراه البوابة ولا البصمة")
    a = ap.parse_args()

    prefix = f"audio/{a.riwaya}/{a.reciter}/"

    # ⛔ المحجر مقبرة لا مستودع عمل: ما دخله دخله لسبب، والكتابة فيه تُحييه.
    if "_quarantine" in prefix:
        sys.exit("⛔ الكتابة تحت مسار محجور ممنوعة — راجع سبب الحجر أولاً.")
    min_bytes = 10000 if a.mode == "surah" else 500
    expect = 114 if a.mode == "surah" else TOTAL_AYAHS
    want_sha = a.mode == "surah"        # السور: sha لكل ملف (مطابقة فهرس التوقيتات)

    # ⛔ البوابة قبل أي تنزيل — لا نمرئي مجلداً لا نعرف عدّه.
    gate_verdict, gate_res = ("SKIPPED_SURAH_MODE", [])
    if a.mode == "ayah":
        gate_verdict, gate_res = counting_gate(a.base)
        log(f"بوابة العدّ: {gate_verdict} — "
            + " ".join(f"{p}:{'200' if r else ('404' if r is False else '?')}"
                       for p, r in zip(GATE_PROBES, gate_res)))
        if gate_verdict != "KUFI":
            log("⛔ المجلد ليس بالعدّ الكوفي (أو تعذّر الحسم) — يُوقف قبل أي تنزيل.")
            log("   ربطه بمعرفات الآي الكوفية يشغّل الآية الخطأ صامتاً (D-025).")
            log("   الطريق: قياس العدّ الكامل بـprobe_ayah_counting.py ثم مسار "
                "يعلن ayahCounting مع طبقة تحويل — أو إسقاط القارئ.")
            if not os.environ.get("MIRROR_ALLOW_NON_KUFI"):
                sys.exit(2)
            log("⚠️ MIRROR_ALLOW_NON_KUFI مضبوط — يُكمَل بمسؤولية المشغّل، "
                "ولن يُدرج في مانيفست كوفي على أي حال.")

    have = existing(prefix)
    names = names_for(a.mode)
    todo = [n for n in names if prefix + n + ".mp3" not in have]
    if a.limit:
        todo = todo[:a.limit]
    log(f"=== {a.reciter} ({a.mode}) — موجود {len(have)}/{expect} · "
        f"للتنزيل {len(todo)} · خيوط {a.threads} ===")

    t0 = time.time()
    done = 0
    with ThreadPoolExecutor(a.threads) as ex:
        for _ in ex.map(
                lambda n: fetch_one(n, a.base, prefix, have, min_bytes, want_sha),
                todo):
            done += 1
            if done % 200 == 0:
                el = (time.time() - t0) / 60
                log(f"{done}/{len(todo)} — ok={stats['ok']} fail={stats['fail']} "
                    f"{stats['bytes']/1e6:.1f}MB · {done/max(el, 0.01):.0f} ملف/دقيقة")

    have = existing(prefix)
    missing = [n for n in names if prefix + n + ".mp3" not in have]
    tiny = [k for k, v in have.items() if v < min_bytes]
    ok = not missing and not tiny and len(have) == expect
    log(f"تدقيق: {len(have)}/{expect} — ناقص={len(missing)} مبتور={len(tiny)}"
        + ("" if ok else f" ⚠️ أول النواقص: {missing[:10]}"))
    log(f"انتهى في {(time.time()-t0)/60:.1f}د — ok={stats['ok']} fail={stats['fail']}")

    if a.no_manifest:
        return
    if not ok:
        log("⛔ غير مكتمل — لم يُدرج في المانيفست (قاعدة الفريق)")
        return

    mkey = f"audio/{a.riwaya}/manifest.json"
    merged = {}
    try:
        cur = json.loads(s3.get_object(Bucket=BUCKET, Key=mkey)["Body"].read())
        for e in cur.get("reciters", []):
            merged[e["id"]] = e
    except Exception:
        pass
    if a.mode == "ayah" and gate_verdict != "KUFI":
        log("⛔ لا إدراج في مانيفست كوفي لمجلد غير كوفي — انتهى بلا مانيفست.")
        return
    dur_verdict, dur_info = ("SKIPPED_SURAH_MODE", None)
    if a.mode == "ayah" and not a.skip_duration_guard:
        try:
            dur_verdict, dur_info = duration_guard(
                prefix, a.riwaya, a.duration_sample, a.threads)
            log("حارس المدة: {} — {} قياساً · {} مشتبهاً · {} م.ث/كلمة".format(
                dur_verdict, dur_info.get("measured"), dur_info.get("suspect"),
                dur_info.get("msPerWord")))
            for x in (dur_info.get("samples") or [])[:10]:
                log("   ⚠️ {} يليق بـ{} ({} م.ث · {} كلمة)".format(
                    x["ayah"], x["fitsBetter"], x["durationMs"], x["words"]))
        except Exception as e:
            dur_verdict, dur_info = "ERROR", {"why": str(e)}
            log("⚠️ حارس المدة تعذّر: {}".format(e))
    elif a.skip_duration_guard:
        dur_verdict = "SKIPPED_BY_OPERATOR"

    entry = {"id": a.reciter, "riwaya": a.riwaya, "source": a.base, "mode": a.mode,
             "files": len(have), "bytes": sum(have.values()), "complete": True,
             "ayahCounting": "kufi" if a.mode == "ayah" else None,
             "countingGate": gate_verdict,
             "durationGuard": dur_verdict}
    if dur_info:
        entry["durationGuardDetail"] = dur_info
    # ⛔ اشتباه كثير = لا قصاصات حتى يُبتّ بشاهد ثانٍ. ولا يُحذف شيء ولا
    # يُمنع المانيفست: المرآة تصف ولا تحكم، والحجب بقدر الشبهة لا أوسع منه.
    if dur_verdict == "SUSPECT_POCKETS":
        entry["usableForClips"] = False
        entry["usableForFullSurah"] = False
        log("⛔ اشتباه مدة كثير — usableForClips/FullSurah = false حتى شاهد ثانٍ.")
    if want_sha and len(shas) == expect:
        entry["perFile"] = [{"surah": int(n), "name": n + ".mp3",
                             "bytes": shas[n][1], "sha256": shas[n][0]}
                            for n in sorted(shas)]
    else:
        first = prefix + names[-1] + ".mp3"
        try:
            entry["sha256Sample"] = hashlib.sha256(
                s3.get_object(Bucket=BUCKET, Key=first)["Body"].read()).hexdigest()
        except Exception:
            pass
    merged[a.reciter] = entry
    s3.put_object(
        Bucket=BUCKET, Key=mkey, ContentType="application/json",
        Body=json.dumps({"version": 1, "updated": int(time.time()),
                         "reciters": [merged[k] for k in sorted(merged)]},
                        ensure_ascii=False, indent=1).encode("utf-8"))
    log(f"✅ {mkey} محدَّث — {len(have)} ملفاً / {sum(have.values())/1e6:.1f}MB")


if __name__ == "__main__":
    main()
