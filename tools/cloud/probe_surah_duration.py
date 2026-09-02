# -*- coding: utf-8 -*-
"""هل ملف السورة يحوي السورة التي يحملها اسمها؟ — بالمدة وحدها.

نفس صنف الخطر الذي كُشف في `warsh/yassin`، لكن في **وضع السور**: هناك سأل
أحدٌ «أي آية في هذا الملف؟» فوجد الجواب مخالفاً؛ وهنا لم يسأل أحدٌ بعدُ
**«أي سورة في هذا الملف؟»**. والحُرّاس القائمة لا تُجيب عنه:
  · `sha256` يثبت أننا نسخنا ما عند المصدر — لا أن المصدر سمّى صحيحاً.
  · بوابة العدّ **لا تعمل أصلاً** في وضع السور (`SKIPPED_SURAH_MODE`).
  · و114/114 دليل اكتمال لا صحة تسمية (‏D-046).

والمدة هنا **أقوى دليلاً منها في وضع الآي**: طول السور يتباين من ثلاث آيات
إلى 286، فالخلط بين سورتين ينكشف بفارق زمني فادح لا يحتمل التأويل. ولا
يحتاج تفريغاً ولا نموذجاً — `ffprobe` فقط.

⛔ لا يكتب في التخزين شيئاً ولا يحذف. قراءة وقياس ومقارنة.

    python3 probe_surah_duration.py --all
    python3 probe_surah_duration.py --riwaya qalun --reciter husary_qalun
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor

import boto3

sys.path.insert(0, os.environ.get("RAFIQ_TOOLS",
                                  "/root/QuranRafiq/tools/alignment"))
from common import load_index, load_text, norm  # noqa

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
B = os.environ["R2_BUCKET"]
LOCK = threading.Lock()
_t = threading.local()

TOL = 0.40      # انحراف نسبي فوقه تُعدّ السورة مشتبهاً بها
MARGIN = 0.15   # وأن تكون سورةٌ أخرى أليقَ بهذا الفارق
MIN_WORDS = 30  # أقصر من ذلك لا يُحاكَم: الثابت يغلب على المتغيّر فيه


def s3():
    if not hasattr(_t, "c"):
        _t.c = boto3.client(
            "s3", endpoint_url=os.environ["R2_ENDPOINT"],
            aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
            aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
            region_name="auto")
    return _t.c


def duration_ms_of(key):
    fd, p = tempfile.mkstemp(suffix=".mp3")
    try:
        body = s3().get_object(Bucket=B, Key=key)["Body"].read()
        with os.fdopen(fd, "wb") as f:
            f.write(body)
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", p],
            capture_output=True, text=True, timeout=120)
        return int(float(r.stdout.strip()) * 1000)
    except Exception:
        return None
    finally:
        try:
            os.remove(p)
        except Exception:
            pass


def surah_words(riwaya):
    text = load_text(riwaya)
    index = load_index()
    out = {}
    for s in index["surahs"]:
        n, start, cnt = s["n"], s["start"], s["ayahs"]
        out[n] = sum(len(norm(text[start + i]).split()) for i in range(cnt))
    return out


def check(riwaya, rid, threads):
    words = surah_words(riwaya)
    pref = "audio/{}/{}/".format(riwaya, rid)
    keys = [(n, pref + "{:03d}.mp3".format(n)) for n in range(1, 115)]
    dur = {}

    def one(item):
        n, k = item
        ms = duration_ms_of(k)
        if ms:
            with LOCK:
                dur[n] = ms

    with ThreadPoolExecutor(threads) as ex:
        list(ex.map(one, keys))
    if len(dur) < 60:
        return {"reciter": rid, "riwaya": riwaya, "verdict": "UNKNOWN",
                "measured": len(dur)}

    # ⛔ نموذج بثابتٍ لا بنسبةٍ صرفة: لكل ملف زمنٌ ثابت لا علاقة له بطول
    # السورة (استعاذة وبسملة وصمت طرفَي التسجيل). وهو يبتلع السور القصار:
    # ثابتٌ من عشرين ثانية على سورة الكوثر خطأٌ ساحق وعلى البقرة لا يُذكر.
    # فبلا هذا الثابت تظهر كل السور القصار «مشتبهاً بها» فيغرق الصادق في
    # الكاذب — وقد وقع فعلاً: 106 و107 و108 اتُّهمت في أول تشغيل.
    # والمعاملان بالوسيط لا بالمربعات، تكراراً ثلاثاً: المنزاح داخل العيّنة.
    def med(v):
        v = sorted(v)
        return v[len(v) // 2] if v else 0.0
    # ⛔ الوتيرة من **السور الكبيرة وحدها**، والثابت يُشتقّ منها بعد ذلك.
    # وسيطُ الكل يكذب لأن أكثر السور الـ114 قصيرة، والزمن الثابت (استعاذة
    # وبسملة وصمت الطرفين) **يسحق القصيرة ويُهمل في الطويلة**. قِيس على
    # `husary_douri`: وتيرة السور ≥800 كلمة 1607 م.ث/كلمة، و<200 كلمة
    # 2759 — ووسيط الكل 2003 يقع بينهما، فينفخ المقام ويُنزل نسبة كل سورة
    # كبيرة نحو الربع. (كشفه rafiq-tafsir، وحجّته حجّتي في حدّ الثلاثين
    # كلمة: أخرجتُ القصيرة من المحاكمة ولم أُخرجها من **المقام**.)
    BIG = 300
    big = [ms / words[n] for n, ms in dur.items() if words[n] >= BIG]
    if len(big) < 8:                       # لا كبيرة تكفي ⇒ ارجع للكل
        big = [ms / words[n] for n, ms in dur.items() if words[n] > 0]
    rate = med(big)
    c = med([ms - rate * words[n] for n, ms in dur.items()])
    if c < 0:                              # الثابت لا يكون سالباً
        c = 0.0
    pred = lambda w: c + rate * w                              # noqa: E731
    suspect = []
    for n, ms in dur.items():
        if words[n] < MIN_WORDS:
            continue
        err = abs(ms - pred(words[n])) / max(ms, pred(words[n]), 1)
        if err <= TOL:
            continue
        best, bn = err, None
        for m in range(1, 115):
            if m == n or words[m] < MIN_WORDS:
                continue
            e2 = abs(ms - pred(words[m])) / max(ms, pred(words[m]), 1)
            if e2 < best - MARGIN:
                best, bn = e2, m
        if bn:
            suspect.append({"surah": n, "fitsBetter": bn, "durationMs": ms,
                            "words": words[n], "wordsOfFit": words[bn],
                            "expectedMs": round(pred(words[n]))})
    # المدد الخام تُعاد مع الحكم: من يريد فرزاً آخر (كفرز السور الضعيفة)
    # يبني عليها بلا إعادة تنزيل 114 ملفاً — والتنزيل مرتين ثمنٌ بلا مقابل.
    return {"reciter": rid, "riwaya": riwaya, "measured": len(dur),
            "msPerWord": round(rate), "overheadMs": round(c),
            "verdict": "CLEAN" if not suspect else "SUSPECT",
            "suspect": suspect, "durations": dur, "words": words}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--riwaya")
    ap.add_argument("--reciter")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--threads", type=int, default=12)
    ap.add_argument("--out", default="/root/probe_surah_durations.json")
    a = ap.parse_args()

    targets = []
    if a.all:
        for r in ("qalun", "warsh", "hafs", "shuba", "douri", "sousi"):
            try:
                m = json.loads(s3().get_object(
                    Bucket=B, Key="audio/{}/manifest.json".format(r)
                )["Body"].read())
            except Exception:
                continue
            for e in m.get("reciters", []):
                if e.get("mode") == "surah" and e.get("complete"):
                    targets.append((r, e["id"]))
    else:
        targets = [(a.riwaya, a.reciter)]

    print("=== فحص {} قارئاً (وضع السور) ===".format(len(targets)), flush=True)
    out = []
    for riwaya, rid in targets:
        res = check(riwaya, rid, a.threads)
        out.append(res)
        mark = "✅" if res.get("verdict") == "CLEAN" else "⛔"
        print("{} {}/{} — {} · {} مشتبهة".format(
            mark, riwaya, rid, res.get("verdict"),
            len(res.get("suspect") or [])), flush=True)
        for x in (res.get("suspect") or [])[:8]:
            print("     سورة {} تليق بـ{} ({:.0f}ث فعلية · {:.0f}ث متوقعة)".format(
                x["surah"], x["fitsBetter"], x["durationMs"] / 1000,
                x["expectedMs"] / 1000), flush=True)

    bad = [r for r in out if r.get("verdict") == "SUSPECT"]
    print("\n=== الحصيلة: {} سليم · {} مشتبه · {} مجهول ===".format(
        sum(1 for r in out if r.get("verdict") == "CLEAN"), len(bad),
        sum(1 for r in out if r.get("verdict") == "UNKNOWN")))
    json.dump(out, open(a.out, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("التفصيل: " + a.out)


if __name__ == "__main__":
    main()
