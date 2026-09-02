# -*- coding: utf-8 -*-
"""فرزُ السور الضعيفة: أعيبُ صوتٍ أم سقوطُ محاذاة؟ — بفارزين لا بواحد.

⛔ القاعدة (‏معتمدة من github-f4، وصياغتها مشتركة مع rafiq-tafsir):
   **نصيب السقوط يقول «هنا خلل» ولا يفرّق بين بترِ صوتٍ وسقوطِ محاذاة —
   وقياس المدة يفصل بينهما.**
     · سقوطٌ عالٍ + مدةٌ قصيرة  ⇒ **الصوت مبتور**  ⇒ يُوسم ولا يُعاد
       (إعادته إنفاقُ ساعةِ whisper على ملفٍ ناقص، والنتيجة كالأولى).
     · سقوطٌ عالٍ + مدةٌ سليمة  ⇒ **المحاذاة سقطت** ⇒ يُعاد ولا يُوسم
       (ووسمُه مصدرياً يُعفيه من الإعادة بغير حق فيبقى ناقصاً للأبد).
   ولا يغني أحدهما عن الآخر: كلاهما يُنتج فهرساً ناقصاً، وعلاجاهما متضادّان.

**نصيب السقوط يُحسب من الفهرس المشحون** لا من سجلّ: الفهرس يُسقط LOW عند
البناء (‏D-025)، فما نقص عن عدد آي السورة فهو ساقط — سواءٌ أسقطته الثقة أم
فشل التفريغ. وهو مقياسٌ متاح لكل قارئ بلا وصولٍ إلى مسار الفهرسة.

⛔ لا يكتب في التخزين شيئاً ولا يحذف — يقرأ ويقيس ويرتّب قائمة عمل.

    python3 classify_weak_surahs.py [--drop 0.5] [--threads 12]
"""
import argparse
import collections
import gzip
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

DUR_SHORT = 0.70   # دون هذا من المتوقع ⇒ الصوت مُتَّهم
DUR_OK = 0.85      # فوق هذا ⇒ الصوت بريء والتهمة على المحاذاة
DUR_LONG = 1.30    # فوق هذا ⇒ الملف **أطول** من سورته — عيبٌ لا محاذاة


def s3():
    if not hasattr(_t, "c"):
        _t.c = boto3.client(
            "s3", endpoint_url=os.environ["R2_ENDPOINT"],
            aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
            aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
            region_name="auto")
    return _t.c


def duration_ms(key):
    fd, p = tempfile.mkstemp(suffix=".mp3")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(s3().get_object(Bucket=B, Key=key)["Body"].read())
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--drop", type=float, default=0.5,
                    help="نصيب السقوط الذي فوقه تُفحص السورة")
    ap.add_argument("--threads", type=int, default=12)
    ap.add_argument("--out", default="/root/weak_surahs.json")
    a = ap.parse_args()

    index = load_index()
    ayahs = {s["n"]: s["ayahs"] for s in index["surahs"]}
    keys = [k for k in _list("timings/") if k.endswith(".jz")]
    print("=== فرز السور الضعيفة في {} فهرساً ===".format(len(keys)),
          flush=True)

    out = []
    for key in sorted(keys):
        riwaya, rid = key.split("/")[1], key.split("/")[2][:-3]
        try:
            idx = json.loads(gzip.decompress(
                s3().get_object(Bucket=B, Key=key)["Body"].read()))
        except Exception as e:
            print("  ⚠️ {} تعذّرت قراءته: {}".format(key, str(e)[:50]))
            continue
        if idx.get("sourceKind") != "SURAH_FILES":
            continue
        per = collections.Counter(int(e["ayahId"].split(":")[0])
                                  for e in idx.get("entries", []))
        words = _words(riwaya)
        # ⛔ تُقاس السور كلها لا الضعيفة وحدها: ملفٌ مبتور قد يُشحن له فهرسٌ
        # شبه تامّ (‏akri س24: 57 من 64 وصوتها 39% من طولها) — وهي أخطر
        # الحالات لأن التوقيت يبدو كاملاً على صوتٍ غير موجود، وعتبةُ السقوط
        # وحدها كانت تُعميها.
        weak = [(n, per.get(n, 0), ayahs[n]) for n in range(1, 115)]
        pref = "audio/{}/{}/".format(riwaya, rid)
        durs = {}

        def one(n):
            ms = duration_ms(pref + "{:03d}.mp3".format(n))
            if ms:
                with LOCK:
                    durs[n] = ms

        # ⛔ الوتيرة بوسيط النسبة على السور كلها لا من «السليمة» وحدها:
        # قارئٌ منخفض التغطية في كل سوره **لا سليمَ له**، فكانت الأداة تعجز
        # عن الوتيرة **فتتخطّاه صامتة** — أي أن أسوأ القراء، وهم أولاها
        # بالفحص، يسقطون منها. (‏`3siri` سقط هكذا وفيه التوبة عند خُمسها.)
        with ThreadPoolExecutor(a.threads) as ex:
            list(ex.map(one, [w[0] for w in weak]))
        rates = sorted(durs[n] / words[n] for n in durs if words[n] >= 30)
        if len(rates) < 20:
            print("  ⚠️ {}/{} — قياسات أقل من أن تُبنى عليها وتيرة".format(
                riwaya, rid))
            continue
        rate = rates[len(rates) // 2]
        for n, got, tot in weak:
            ms = durs.get(n)
            drop = 1 - got / tot
            ratio = round(ms / (rate * words[n]), 2) if (ms and words[n] >= 30) else None
            if ratio is not None and ratio < DUR_SHORT:
                verdict = "AUDIO_SHORT"
            elif ratio is not None and ratio > DUR_LONG:
                verdict = "AUDIO_LONG"
            elif drop < a.drop:
                continue
            elif ratio is None:
                verdict = "UNJUDGED"
            elif ratio >= DUR_OK:
                verdict = "ALIGNMENT_FAILED"
            else:
                verdict = "UNCLEAR"
            out.append({"riwaya": riwaya, "reciter": rid, "surah": n,
                        "shipped": got, "ayahs": tot,
                        "dropShare": round(drop, 2),
                        "durationRatio": ratio, "verdict": verdict})

    counts = collections.Counter(x["verdict"] for x in out)
    print("\n=== الحصيلة: {} سورة ضعيفة · {} ===".format(len(out), dict(counts)))
    for v, title in (("AUDIO_SHORT", "⛔ الصوت مبتور — يُوسم ولا يُعاد"),
                     ("AUDIO_LONG", "⛔ الصوت أطول من سورته — يُوسم ولا يُعاد"),
                     ("ALIGNMENT_FAILED", "🔁 المحاذاة سقطت — يُعاد ولا يُوسم"),
                     ("UNCLEAR", "· غير حاسم"),
                     ("UNJUDGED", "· لا يُحاكَم (سورة قصيرة)")):
        rows = [x for x in out if x["verdict"] == v]
        if not rows:
            continue
        print("\n{} ({})".format(title, len(rows)))
        for x in sorted(rows, key=lambda r: -r["dropShare"])[:15]:
            print("   {}/{} س{} — شُحن {}/{} · نسبة المدة {}".format(
                x["riwaya"], x["reciter"], x["surah"], x["shipped"],
                x["ayahs"], x["durationRatio"]))
    json.dump(out, open(a.out, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("\nالتفصيل: " + a.out)


_wcache = {}


def _words(riwaya):
    if riwaya not in _wcache:
        text, index = load_text(riwaya), load_index()
        _wcache[riwaya] = {
            s["n"]: sum(len(norm(text[s["start"] + i]).split())
                        for i in range(s["ayahs"]))
            for s in index["surahs"]}
    return _wcache[riwaya]


def _list(prefix):
    out, tok = [], None
    while True:
        kw = dict(Bucket=B, Prefix=prefix, MaxKeys=1000)
        if tok:
            kw["ContinuationToken"] = tok
        r = s3().list_objects_v2(**kw)
        out += [o["Key"] for o in r.get("Contents", [])]
        if not r.get("IsTruncated"):
            break
        tok = r["NextContinuationToken"]
    return out


if __name__ == "__main__":
    main()
