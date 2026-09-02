# -*- coding: utf-8 -*-
"""هل مطلعُ ملف السورة مطلعُ سورته؟ — ⛔ **مقياسٌ لم يُقبَل: لا يُبنى عليه قرار.**

════════════════════════════════════════════════════════════════════════
⛔⛔ نتيجة سالبة موثَّقة — لا تُشغّله على الأسطول ولا تُصدّق مخرجه ⛔⛔
اختُبر على `qalun/husary_qalun` وسلامتُه مبرهنة بثلاث طرق مستقلة، فأعطى:
    التشغيل الأول: **20 «سورة خاطئة»** كاذبة + 55 غير حاسم من 114.
    بعد طيّ التكرار وحذف البسملة: **8 كاذبة** + 64 غير حاسم.
وثمانية إنذارات كاذبة من 114 (‏7%) على قارئٍ سليم تجعله أضرّ من عدمه:
**الإنذار الكاذب يدرّب المشغّل على تجاهل الإنذار الصادق.**

والعلة ليست في التنفيذ بل في **ضعف الإشارة نفسها**: مطلعٌ من اثنتي عشرة
كلمة + نموذج صغير يعلق في حلقات + بسملة مشتركة بين السور + مطالع متشابهة
أصلاً (‏«الحمد لله» تفتتح 1 و6 و18 و34 و35). فالطريق إلى قبوله — إن أُريد —
نموذج أكبر أو مطلع أطول أو مطابقة بالصوت لا بالنص، لا ضبط عتبات.

**والثغرة تبقى مفتوحة معلَنة:** حارس المدة يفحص الطول لا المحتوى، فسورةٌ
سليمة الطول محتواها سورةٌ أخرى من طولها **لا يكشفها أحد عندنا اليوم**.
وإعلانها خيرٌ من سدّها بمقياسٍ يكذب.
════════════════════════════════════════════════════════════════════════

يسدّ — لو صحّ — ما لا يبلغه حارس المدة.

⛔ الثغرة التي يسدّها، وقد أعلنتُها على أداتي قبل أن يسألني أحد:
   حارس المدة يفحص **الطول** لا **المحتوى**. فسورةٌ سليمة الطول محتواها
   سورةٌ أخرى **من طولها** تعبره سالمة. والقرآن فيه سورٌ كثيرة متقاربة
   الطول، فالثغرة واسعة لا نظرية.

المنهج: يُفرَّغ **مطلع** الملف وحده (أربعون ثانية) ويُطابَق بمطالع السور
كلها، والحكم لأعلى استرجاع. والمطلع يكفي: من سمع أول آيتين عرف السورة،
ولا حاجة لتفريغ ساعةٍ كاملة لكل ملف — فكلفة المسح تصير محتملة على الأسطول.

⛔ ويُطرح من المقارنة **الاستعاذة والبسملة**: هما مشتركتان بين كل السور،
   فإبقاؤهما يرفع درجة كل مرشَّح بالتساوي ويطمس الفرق — وهو ضجيجٌ يُقاس
   على أنه إشارة.

⛔ لا يكتب في التخزين ولا يحذف.

    python3 probe_surah_head.py --riwaya qalun --reciter akri_qalun
    python3 probe_surah_head.py --all --threads 8
"""
import argparse
import difflib
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import boto3

sys.path.insert(0, os.environ.get("RAFIQ_TOOLS",
                                  "/root/QuranRafiq/tools/alignment"))
from common import MODEL_Q8, WHISPER_CLI, FFMPEG, load_index, load_text, norm  # noqa

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
B = os.environ["R2_BUCKET"]
LOCK = threading.Lock()
_t = threading.local()

HEAD_SEC = 60      # 40 لم تكف: بطيء القراءة يستغرقها في الاستعاذة والبسملة
OPEN_WORDS = 12    # كلمات المطلع التي تُطابَق
MARGIN = 0.15      # فضل سورة أخرى على سورته قبل الاتهام
FLOOR = 0.25       # دون هذا فالتفريغ لم ينتج إشارة
# الاستعاذة والبسملة: مشتركة بين السور فتُطرح من المقارنة
PREFIX = norm("أعوذ بالله من الشيطان الرجيم بسم الله الرحمن الرحيم").split()


def s3():
    if not hasattr(_t, "c"):
        _t.c = boto3.client(
            "s3", endpoint_url=os.environ["R2_ENDPOINT"],
            aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
            aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
            region_name="auto")
    return _t.c


def collapse(words, win=8):
    """طيّ تكرار whisper الدوري — الدرس نفسه من probe_content."""
    out = []
    for w in words:
        out.append(w)
        for k in range(2, win + 1):
            if len(out) >= 2 * k and out[-k:] == out[-2 * k:-k]:
                del out[-k:]
                break
    return out


BASMALA = set(norm("اعوذ بالله من الشيطان الرجيم بسم الله الرحمن الرحيم").split())


def strip_prefix(words):
    """يحذف الاستعاذة والبسملة من أول المسموع مهما تكرّرتا أو نقصتا."""
    out = list(words)
    changed = True
    while changed and out:
        changed = False
        for k in range(min(len(PREFIX), len(out)), 2, -1):
            if out[:k] == PREFIX[-k:] or out[:k] == PREFIX[:k]:
                out = out[k:]
                changed = True
                break
        while out and out[0] in ("الله", "بسم", "الرحمن", "الرحيم", "اعوذ",
                                 "بالله", "من", "الشيطان", "الرجيم"):
            out = out[1:]
            changed = True
    return out


def head_text(key):
    d = tempfile.mkdtemp(prefix="head_")
    try:
        mp3, wav, base = d + "/a.mp3", d + "/a.wav", d + "/o"
        body = s3().get_object(Bucket=B, Key=key,
                               Range="bytes=0-3000000")["Body"].read()
        with open(mp3, "wb") as f:
            f.write(body)
        subprocess.run([FFMPEG, "-y", "-v", "error", "-i", mp3, "-t",
                        str(HEAD_SEC), "-ar", "16000", "-ac", "1", wav],
                       check=True, timeout=120, stdin=subprocess.DEVNULL)
        subprocess.run([WHISPER_CLI, "-m", MODEL_Q8, "-f", wav, "-l", "ar",
                        "-oj", "-of", base, "--no-prints",
                        "-bo", "1", "-bs", "1", "-nf", "-ac", "512", "-t", "2"],
                       capture_output=True, check=True, timeout=300,
                       stdin=subprocess.DEVNULL)
        with open(base + ".json", encoding="utf-8", errors="replace") as f:
            data = json.load(f)
        return norm(" ".join(x["text"] for x in data.get("transcription", [])))
    finally:
        subprocess.run(["rm", "-rf", d], check=False)


def recall(heard, cand):
    if not cand:
        return 0.0
    m = difflib.SequenceMatcher(None, heard, cand)
    return sum(b.size for b in m.get_matching_blocks()) / len(cand)


def openings(riwaya):
    text, index = load_text(riwaya), load_index()
    out = {}
    for s in index["surahs"]:
        w = []
        for i in range(min(4, s["ayahs"])):
            w += norm(text[s["start"] + i]).split()
            if len(w) >= OPEN_WORDS:
                break
        w = [x for x in strip_prefix(w) if x not in BASMALA] or w
        out[s["n"]] = w[:OPEN_WORDS]
    return out


def check(riwaya, rid, threads, only=None):
    opens = openings(riwaya)
    pref = "audio/{}/{}/".format(riwaya, rid)
    todo = only or list(range(1, 115))
    rows = []

    def one(n):
        try:
            raw = collapse(head_text(pref + "{:03d}.mp3".format(n)).split())
            # ⛔ البسملة تتناثر في التفريغ لا تتصدره: الحلقة تمزجها بالكلام،
            # فحذفها من الأول وحده يُبقي شظاياها تُطابق كل السور بالتساوي.
            heard = [w for w in strip_prefix(raw) if w not in BASMALA]
        except Exception as e:
            with LOCK:
                rows.append({"surah": n, "error": str(e)[:80]})
            return
        sc = {m: recall(heard, opens[m]) for m in range(1, 115)}
        best = max(sc, key=sc.get)
        exp = sc[n]
        if sc[best] < FLOOR:
            v = "UNCLEAR"
        elif best == n or sc[best] - exp < MARGIN:
            v = "OK"
        else:
            v = "WRONG_SURAH"
        with LOCK:
            rows.append({"surah": n, "verdict": v, "best": best,
                         "bestScore": round(sc[best], 3),
                         "expectedScore": round(exp, 3),
                         "heard": " ".join(heard[:14])})
            if v == "WRONG_SURAH":
                print("   ⛔ ملف {:03d} مطلعه سورة {} ({:.2f} مقابل {:.2f})".format(
                    n, best, sc[best], exp), flush=True)

    with ThreadPoolExecutor(threads) as ex:
        list(ex.map(one, todo))
    rows.sort(key=lambda r: r["surah"])
    wrong = [r for r in rows if r.get("verdict") == "WRONG_SURAH"]
    unclear = [r for r in rows if r.get("verdict") == "UNCLEAR"]
    return {"riwaya": riwaya, "reciter": rid, "checked": len(rows),
            "wrong": len(wrong), "unclear": len(unclear),
            "verdict": "WRONG_SURAH" if wrong else "OK",
            "rows": [r for r in rows if r.get("verdict") != "OK"]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--riwaya")
    ap.add_argument("--reciter")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--threads", type=int, default=8)
    ap.add_argument("--out", default="/root/probe_surah_heads.json")
    a = ap.parse_args()

    targets = []
    if a.all:
        for r in ("qalun", "warsh", "shuba", "douri", "sousi", "hafs"):
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

    print("=== مطالع السور: {} قارئاً ===".format(len(targets)), flush=True)
    out, t0 = [], time.time()
    for riwaya, rid in targets:
        res = check(riwaya, rid, a.threads)
        out.append(res)
        print("{} {}/{} — {} خطأ · {} غير حاسم ({:.0f}د)".format(
            "⛔" if res["wrong"] else "✅", riwaya, rid, res["wrong"],
            res["unclear"], (time.time() - t0) / 60), flush=True)
        json.dump(out, open(a.out, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
    bad = [r for r in out if r["wrong"]]
    print("\n=== الحصيلة: {} سليم · {} فيه سورة خاطئة ===".format(
        len(out) - len(bad), len(bad)))
    print("التفصيل: " + a.out)


if __name__ == "__main__":
    main()
