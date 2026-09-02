# -*- coding: utf-8 -*-
"""مسبار المحتوى: هل الملف يحوي الآية التي يحملها اسمه؟

⛔ لماذا لا يكفي ما عندنا: **الاسم يكذب، والبصمة لا تدري، والعدّ لا يرى.**
   - اسم الملف `004013.mp3` ادّعاء لا برهان.
   - `sha256` يثبت أننا نسخنا ما عند المصدر بايتاً ببايت — لا أن المصدر صادق.
   - بوابة العدّ الثمانية تسأل «كم آية في المجلد؟» لا «أي آية في هذا الملف؟»،
     فمجلدٌ كوفيُّ العدّ قد يكون منزاح المحتوى (وقع في ياسين/ورش: ‏004013
     صوته 4:15 لا 4:13).
   فالسؤال الوحيد الذي يحسمها: **أَسمِع الملف وطابِق نصّه.**

المنهج: يُفرَّغ الملف بـwhisper ثم يُطابَق نصّه بالآية المتوقعة **وبجيرانها**
(‏±3 خانة كوفية)، والحكم لأعلى تشابه.

والحكم **نسبيّ لا مطلق** عمداً: تفريغ النموذج الصغير ناقص دوماً، فمقارنته
بعتبة مطلقة تُنتج إنذارات كاذبة بالجملة — أما سؤال «أيُّ المرشحين أقرب؟»
فيحتمل ضجيج التفريغ ولا ينكسر به.

⛔ لا يكتب في التخزين شيئاً، ولا يحذف، ويقرأ الصوت من مرآتنا لا من المصدر.

    python3 probe_content.py --reciter yassin --riwaya warsh --sample 60
    python3 probe_content.py --reciter yassin --riwaya warsh --all
    python3 probe_content.py --reciter yassin --riwaya warsh --ayahs 4:13,4:15
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

sys.path.insert(0, "/root/QuranRafiq/tools/alignment")
from common import MODEL_Q8, WHISPER_CLI, FFMPEG, load_index, load_text, norm  # noqa

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
B = os.environ["R2_BUCKET"]
NEIGH = 3          # مدى الجيران المفحوصين حول المتوقع
# ⛔ حكم ثلاثي لا ثنائي: «لا أدري» جوابٌ مشروع، وإجباره على نعم/لا يكذب.
# بلاغٌ كاذب بالانزياح يمحو قارئاً سليماً، وتبرئةٌ كاذبة تُبقي قارئاً يعلّم
# الحافظ خطأً — وكلاهما أسوأ من الاعتراف بأن التفريغ لم يحسم.
MARGIN = 0.08      # فضل الجار على المتوقع كي يُعدّ انزياحاً
FLOOR = 0.12       # أدنى درجة يُعتدّ بها أصلاً — دونها التفريغ ضجيج
MIN_WORDS = 6      # آية أقصر لا تميّز نفسها عن جيرانها فتُستبعد من العيّنة
LOCK = threading.Lock()
_t = threading.local()


def s3():
    if not hasattr(_t, "c"):
        _t.c = boto3.client(
            "s3", endpoint_url=os.environ["R2_ENDPOINT"],
            aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
            aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
            region_name="auto")
    return _t.c


def collapse(words, win=8):
    """يطوي التكرار الدوري في تفريغ whisper.

    النموذج الصغير يعلق في حلقة فيعيد المقطع نفسه مراراً («لا تأخذه سنة» ×5).
    وهذا التكرار وحده يهبط بدرجة التطابق للآية **الصحيحة** إلى 0.24، فيصير
    الحكم ضجيجاً. الطيّ يستعيد النصّ المسموع مرة واحدة.
    """
    out = []
    for w in words:
        out.append(w)
        for k in range(2, win + 1):
            if len(out) >= 2 * k and out[-k:] == out[-2 * k:-k]:
                del out[-k:]
                break
    return out


def score_recall(heard_words, cand_words):
    """استرجاعٌ لا تشابهٌ متماثل: كم من كلمات الآية المرشَّحة حضرت بالترتيب؟

    ‏SequenceMatcher.ratio يقسم على مجموع الطولين، فيعاقب فرق الطول عقاباً
    يطمس الإشارة — والتفريغ أطولُ أو أقصرُ من الآية دائماً. أما «كم من الآية
    سُمع؟» فلا يبالي بطول ما زاد، وهو السؤال الحقيقي.
    """
    if not cand_words:
        return 0.0
    m = difflib.SequenceMatcher(None, heard_words, cand_words)
    return sum(b.size for b in m.get_matching_blocks()) / len(cand_words)


def transcribe_file(mp3_bytes):
    """يفرّغ الملف كاملاً — الآية قصيرة فلا حاجة لـVAD ولا تقطيع."""
    d = tempfile.mkdtemp(prefix="probe_")
    try:
        mp3, wav, base = d + "/a.mp3", d + "/a.wav", d + "/o"
        with open(mp3, "wb") as f:
            f.write(mp3_bytes)
        subprocess.run([FFMPEG, "-y", "-v", "error", "-i", mp3,
                        "-ar", "16000", "-ac", "1", wav],
                       check=True, timeout=120, stdin=subprocess.DEVNULL)
        subprocess.run([WHISPER_CLI, "-m", MODEL_Q8, "-f", wav, "-l", "ar",
                        "-oj", "-of", base, "--no-prints",
                        "-bo", "1", "-bs", "1", "-nf", "-ac", "512", "-t", "2"],
                       capture_output=True, check=True, timeout=300,
                       stdin=subprocess.DEVNULL)
        with open(base + ".json", encoding="utf-8", errors="replace") as f:
            data = json.load(f)
        return norm(" ".join(s["text"] for s in data.get("transcription", [])))
    finally:
        subprocess.run(["rm", "-rf", d], check=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reciter", required=True)
    ap.add_argument("--riwaya", required=True)
    ap.add_argument("--sample", type=int, default=60)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--ayahs", help="قائمة س:آ مفصولة بفواصل — للتحقق الموجَّه")
    ap.add_argument("--threads", type=int, default=6)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    text = load_text(a.riwaya)              # 6236 خانة كوفية
    index = load_index()
    slots = []
    for s in index["surahs"]:
        for i in range(s["ayahs"]):
            slots.append((s["n"], i + 1))
    assert len(slots) == len(text) == 6236, (len(slots), len(text))

    if a.ayahs:
        want = []
        for tok in a.ayahs.split(","):
            sn, an = (int(x) for x in tok.strip().split(":"))
            want.append(slots.index((sn, an)))
    elif a.all:
        want = list(range(6236))
    else:
        # عيّنة موزّعة على المصحف كله لا متجاورة: الانزياح قد يبدأ في موضع
        # ويصحّ في غيره، والعيّنة المتجاورة تراه كله أو تعميه كله.
        elig = [i for i in range(6236) if len(text[i].split()) >= MIN_WORDS]
        step = max(1, len(elig) // a.sample)
        want = elig[::step][:a.sample]

    print("=== مسبار المحتوى: {}/{} — {} آية · خيوط {} ===".format(
        a.riwaya, a.reciter, len(want), a.threads), flush=True)
    results, t0 = [], time.time()

    def one(i):
        sn, an = slots[i]
        key = "audio/{}/{}/{:03d}{:03d}.mp3".format(a.riwaya, a.reciter, sn, an)
        try:
            body = s3().get_object(Bucket=B, Key=key)["Body"].read()
        except Exception as e:
            with LOCK:
                results.append({"slot": i, "ayah": "{}:{}".format(sn, an),
                                "error": str(e)})
            return
        try:
            heard = transcribe_file(body)
        except Exception as e:
            with LOCK:
                results.append({"slot": i, "ayah": "{}:{}".format(sn, an),
                                "error": "تفريغ: {}".format(e)})
            return
        hw = collapse(heard.split())
        scores = {}
        for off in range(-NEIGH, NEIGH + 1):
            j = i + off
            if 0 <= j < 6236:
                scores[off] = score_recall(hw, norm(text[j]).split())
        best = max(scores, key=scores.get)
        exp = scores.get(0, 0.0)
        # ⛔ الآية الأقصر من أربع كلمات لا تُحاكَم أصلاً: «الم» و«طه» ونحوهما
        # لا يفرّغها النموذج بشيء، فدرجتها صفر مهما كان الصوت صحيحاً، وأي جار
        # أطول يسبقها فيبدو «انزياحاً» وليس به. رُصد حياً: 2:1 اتُّهم زوراً.
        if len(norm(text[i]).split()) < 4:
            verdict = "UNJUDGED_SHORT"
        elif scores[best] < FLOOR:
            verdict = "UNCLEAR"          # التفريغ نفسه لم ينتج إشارة
        elif best == 0:
            verdict = "OK"
        elif scores[best] - exp >= MARGIN:
            verdict = "SHIFTED"
        else:
            verdict = "UNCLEAR"          # جارٌ سبق بفارق لا يُبنى عليه
        row = {"slot": i, "ayah": "{}:{}".format(sn, an), "verdict": verdict,
               "bestOffset": best, "bestScore": round(scores[best], 3),
               "expectedScore": round(exp, 3), "heard": heard[:120]}
        if best != 0:
            bs, ba = slots[i + best]
            row["heardAyah"] = "{}:{}".format(bs, ba)
        with LOCK:
            results.append(row)
            n = len(results)
            if verdict == "SHIFTED":
                print("  ⛔ {}:{} ← يسمع {} ({:.2f} مقابل {:.2f})".format(
                    sn, an, row["heardAyah"], scores[best], exp), flush=True)
            if n % 20 == 0:
                el = (time.time() - t0) / 60
                print("  …{}/{} · {:.0f} آية/دقيقة".format(
                    n, len(want), n / max(el, 0.01)), flush=True)

    with ThreadPoolExecutor(a.threads) as ex:
        list(ex.map(one, want))

    results.sort(key=lambda r: r["slot"])
    errs = [r for r in results if "error" in r]
    shifted = [r for r in results if r.get("verdict") == "SHIFTED"]
    unclear = [r for r in results if r.get("verdict") == "UNCLEAR"]
    short = [r for r in results if r.get("verdict") == "UNJUDGED_SHORT"]
    ok = [r for r in results if r.get("verdict") == "OK"]
    print("\n=== الحصيلة: {} مطابقة · {} منزاحة · {} غير حاسم · {} خطأ · "
          "{:.1f}د ===".format(len(ok), len(shifted), len(unclear), len(errs),
                               (time.time() - t0) / 60))
    if unclear:
        print("   (غير الحاسم ليس تبرئة ولا إدانة — تفريغه لم ينتج إشارة "
              "تكفي؛ يُعاد بنموذج أكبر إن كثر.)")
    if shifted:
        offs = {}
        for r in shifted:
            offs[r["bestOffset"]] = offs.get(r["bestOffset"], 0) + 1
        print("⛔ انزياح مؤكَّد — توزيع الإزاحات: {}".format(offs))
        for r in shifted[:20]:
            print("   {} ← {} ({} مقابل {})".format(
                r["ayah"], r.get("heardAyah"), r["bestScore"],
                r["expectedScore"]))
    elif not unclear:
        print("✅ لا انزياح في المفحوص — كل آية سُمعت في موضعها.")
    else:
        print("✅ لا انزياح مؤكَّد؛ و{} غير حاسم يحتاج إعادة.".format(len(unclear)))
    out = a.out or "/root/probe_{}_{}.json".format(a.riwaya, a.reciter)
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"reciter": a.reciter, "riwaya": a.riwaya,
                   "checked": len(results), "matched": len(ok),
                   "shifted": len(shifted), "unclear": len(unclear),
                   "unjudgedShort": len(short),
                   "errors": len(errs), "margin": MARGIN, "floor": FLOOR,
                   "results": results}, f, ensure_ascii=False, indent=1)
    print("التفصيل: {}".format(out))
    sys.exit(2 if shifted else 0)


if __name__ == "__main__":
    main()
