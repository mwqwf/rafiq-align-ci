# -*- coding: utf-8 -*-
"""تحقق ثانٍ **مستقل عن التفريغ**: مدة الصوت مقابل طول الآية.

المسبار الأول يسمع الكلام (‏whisper). وهذا لا يسمع شيئاً — يقيس **الزمن** فقط.
فإن اتفق الشاهدان وأحدهما لا يعرف ما يقوله الآخر، فالحكم مسنود بطريقين
مختلفَين لا بطريق واحد مكرَّر. وهذا هو المقصود بـ«شاهد مستقل».

المنهج: القارئ يقرأ بوتيرة ثابتة تقريباً، فمدة الملف ∝ عدد كلمات الآية.
نبني الوتيرة من ملفات **سليمة** لهذا القارئ (انحدار بلا حدّ حرّ)، ثم نسأل عن
كل ملف مشكوك: أمدّته أقرب إلى طول الآية التي يحملها اسمه، أم إلى طول الآية
التي زعم المسبار أنه يحويها؟

⛔ لا يكتب في التخزين شيئاً ولا يحذف — قراءة ومقارنة فقط.

    python3 verify_shift_duration.py --riwaya warsh --reciter yassin \
        --probe /root/probe_yassin_full.json --pockets '12:102-12:111,...'
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

sys.path.insert(0, "/root/QuranRafiq/tools/alignment")
from common import load_index, load_text, norm  # noqa

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
B = os.environ["R2_BUCKET"]
_t = threading.local()
LOCK = threading.Lock()


def s3():
    if not hasattr(_t, "c"):
        _t.c = boto3.client(
            "s3", endpoint_url=os.environ["R2_ENDPOINT"],
            aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
            aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
            region_name="auto")
    return _t.c


def duration_ms(body):
    fd, p = tempfile.mkstemp(suffix=".mp3")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(body)
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", p],
            capture_output=True, text=True, check=True, timeout=60).stdout
        return int(float(out.strip()) * 1000)
    finally:
        os.remove(p)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--riwaya", required=True)
    ap.add_argument("--reciter", required=True)
    ap.add_argument("--probe", required=True)
    ap.add_argument("--pockets", required=True)
    ap.add_argument("--model-sample", type=int, default=150)
    ap.add_argument("--threads", type=int, default=8)
    a = ap.parse_args()

    text = load_text(a.riwaya)
    index = load_index()
    slots = []
    for s in index["surahs"]:
        for i in range(s["ayahs"]):
            slots.append((s["n"], i + 1))
    pos = {"{}:{}".format(sn, an): i for i, (sn, an) in enumerate(slots)}
    words = [len(norm(t).split()) for t in text]
    pref = "audio/{}/{}/".format(a.riwaya, a.reciter)

    def fetch_ms(i):
        sn, an = slots[i]
        key = pref + "{:03d}{:03d}.mp3".format(sn, an)
        try:
            return i, duration_ms(s3().get_object(Bucket=B, Key=key)["Body"].read())
        except Exception:
            return i, None

    probe = json.load(open(a.probe, encoding="utf-8"))
    ranges = []
    for tok in a.pockets.split(","):
        lo, hi = tok.strip().split("-")
        ranges.append((pos[lo], pos[hi]))
    susp = [r for r in probe["results"] if r.get("verdict") == "SHIFTED"
            and any(lo <= r["slot"] <= hi for lo, hi in ranges)]
    susp.sort(key=lambda r: r["slot"])

    # وتيرة القارئ من ملفاته السليمة وحدها — ولا تُبنى من المشكوك فيه
    ok = [r["slot"] for r in probe["results"] if r.get("verdict") == "OK"
          and words[r["slot"]] >= 5]
    step = max(1, len(ok) // a.model_sample)
    model_idx = ok[::step][:a.model_sample]
    print("بناء الوتيرة من {} ملفاً سليماً…".format(len(model_idx)), flush=True)
    with ThreadPoolExecutor(a.threads) as ex:
        model = [x for x in ex.map(fetch_ms, model_idx) if x[1]]
    num = sum(words[i] * ms for i, ms in model)
    den = sum(words[i] ** 2 for i, ms in model)
    rate = num / den                       # م.ث لكل كلمة
    resid = [abs(ms - rate * words[i]) / max(ms, 1) for i, ms in model]
    resid.sort()
    p90 = resid[int(0.9 * (len(resid) - 1))]
    print("الوتيرة: {:.0f} م.ث/كلمة · خطأ نسبي وسيط {:.0%} · مئين90 {:.0%}".format(
        rate, resid[len(resid) // 2], p90))

    print("\n=== الحكم المستقل على {} ملفاً مشكوكاً ===".format(len(susp)))
    print("| الملف | كلمات اسمه | كلمات المزعوم | المدة | يوافق |")
    print("|---|---:|---:|---:|---|")
    agree = disagree = unclear = 0
    with ThreadPoolExecutor(a.threads) as ex:
        durs = dict(ex.map(fetch_ms, [r["slot"] for r in susp]))
    for r in susp:
        i, off = r["slot"], r["bestOffset"]
        ms = durs.get(i)
        if not ms:
            continue
        j = i + off
        en, cn = words[i], words[j]
        e_err = abs(ms - rate * en) / max(ms, 1)
        c_err = abs(ms - rate * cn) / max(ms, 1)
        if abs(en - cn) <= 1:
            v, tag = "unclear", "≈ الطولان متقاربان"
        elif c_err < e_err:
            v, tag = "agree", "✅ المزعوم"
        else:
            v, tag = "disagree", "✋ الاسم"
        agree += v == "agree"
        disagree += v == "disagree"
        unclear += v == "unclear"
        print("| {} ({}) | {} | {} ({}) | {:.1f}ث | {} |".format(
            r["ayah"], "الاسم", en, cn, r.get("heardAyah"), ms / 1000, tag))

    print("\n=== الحصيلة: {} يوافق المسبار · {} يخالفه · {} لا يحسم ===".format(
        agree, disagree, unclear))
    print("(«لا يحسم» حين يتقارب طولا الآيتين فالزمن لا يفرّق بينهما — "
          "وهو صمتٌ لا تأييد.)")


if __name__ == "__main__":
    main()
