# -*- coding: utf-8 -*-
"""مسبار البسملة **محلياً** بنافذةٍ قصيرة — بعد أن ثبت أن الطويلة تبتلعها.

⛔ **الدرس الذي وُلد منه هذا الملف (‏2026-09-02):** تفريغ [0–20ث] دفعةً أعطى
«يا أيها الناس اتقوا ربكم» لسورةٍ **تبدأ بالبسملة يقيناً** — النموذج يُسقط
العبارة الافتتاحية القصيرة داخل نافذةٍ طويلة. والتفريغ نفسه على **أول 4ث**
يعطي «بسم الله الرحمن الرحيم». ⇒ **الكشف بنافذة ≤6ث، ولا قيمة لنفيٍ بنافذةٍ
أطول.**

يعمل بـ`pywhispercpp` على النموذج المحلي (‏`ggml-q8`) — بلا خادم.
والقصّ يحتاج نهاية البسملة: تُقدَّر بمسحٍ متدرّج (‏3 → 6ث بخطوة نصف ثانية)
فأول نافذةٍ يظهر فيها ما بعد البسملة تحدّ نهايتها؛ وهو أدقّ من طوابع نافذةٍ
طويلة لا يُعوَّل عليها.

    python tools/tasmi_bench/basmala_local.py --plan work/basmala_plan_full.json
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "tools", "alignment"))
from common import FFMPEG, norm  # noqa: E402

WORK = os.path.join(HERE, "work", "basmala")
BAS = norm("بسم الله الرحمن الرحيم").split()


def _edit(a, b):
    if a == b:
        return 0
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def _eq(a, b):
    """تسامحٌ مع خطأ تعرّفٍ في حرفٍ أو حرفين: «وحمن» ⇄ «الرحمن» (وقعت فعلاً في
    hawashi 5:1، ولولاها لسقط كشف الذيل)."""
    return a == b or (len(a) > 2 and len(b) > 2 and a[1:] == b[1:]) or         (min(len(a), len(b)) >= 4 and _edit(a, b) <= 2)


def _eq_first(a):
    """أول كلمةٍ من البسملة يخطئ فيها التعرّف كثيراً («يسم» «اسم» «واسم»
    «وبسم») ولا يمسكها تسامح الطول العام لأنها ثلاثة أحرف. والقيد الآمن:
    تنتهي بـ«سم» وطولها ≤5 — فلا تلتقط «الله» ولا «اسمه»."""
    return a.endswith("سم") and 3 <= len(a) <= 5


def basmala_tail(words, start_within=1):
    """⚠️ الحدّ قد يقع **داخل** البسملة فيبدأ المسموع بذيلها («الرحمن الرحيم»)
    — وهي أسوأ الحالات للمستخدم (تشغيلٌ يبدأ من نصف بسملة). تُكشف بمطابقة
    ذيلٍ من كلمتين فأكثر في أول المسموع. (وقعت فعلاً: hawashi 5:1.)"""
    for k in (3, 2):                      # الله الرحمن الرحيم / الرحمن الرحيم
        tail = BAS[-k:]
        for i in range(0, start_within + 1):
            seq = words[i:i + k]
            if len(seq) == k and all(_eq(a, b) for a, b in zip(seq, tail)):
                return i, k
    # وأضيق الحالات: لم يبقَ من البسملة إلا «الرحيم» — تُقبل **بقيدٍ زمني**
    # (الحدّ في أوائل ملف السورة) كي لا تُلتقط «الرحيم» في وسط السورة.
    for i in (0, 1):
        if i < len(words) and _eq(words[i], BAS[-1]):
            return i, 1
    return None


def fuzzy_seq(words, target=BAS, start_within=3):
    """تتابعٌ بترتيبه في أوائل الكلمات، بسماحة حرفٍ أول (بسم ⇄ يسم ⇄ إسم)."""
    for i in range(0, min(len(words), start_within + 1)):
        seq = words[i:i + len(target)]
        if len(seq) < len(target):
            return None
        # ⛔ يُستعمل `_eq` المتسامح نفسه الذي يستعمله كشف الذيل: بالمقارن
        # الصارم كانت «اقحيم» (تعرّفاً عن «الرحيم») تُسقط بسملةً تامّة إلى
        # «ذيل» — وقعت فعلاً في hawashi 21 و28.
        if all((_eq_first(a) if k == 0 else _eq(a, b))
               for k, (a, b) in enumerate(zip(seq, target))):
            return i
    return None


def cut(src, start_ms, dur_ms, dst):
    subprocess.run([FFMPEG, "-y", "-v", "error", "-ss", f"{start_ms/1000:.3f}",
                    "-i", src, "-t", f"{dur_ms/1000:.3f}", "-ar", "16000",
                    "-ac", "1", dst], check=True)
    return dst


def text_of(model, wav):
    return norm(" ".join(s.text for s in model.transcribe(wav)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", required=True)
    ap.add_argument("--model", default=os.path.join(HERE, "work", "ggml-q8.bin"))
    ap.add_argument("--out", default=os.path.join(HERE, "work", "basmala_local.json"))
    ap.add_argument("--threads", type=int, default=2)
    ap.add_argument("--limit", type=int)
    args = ap.parse_args()
    os.makedirs(WORK, exist_ok=True)
    from pywhispercpp.model import Model
    model = Model(args.model, n_threads=args.threads, language="ar",
                  print_progress=False, print_realtime=False)

    plan = json.load(open(args.plan, encoding="utf-8"))
    if args.limit:
        plan = plan[:args.limit]
    done = {}
    if os.path.exists(args.out):
        done = {f"{r['reciter']}:{r['surah']}": r
                for r in json.load(open(args.out, encoding="utf-8"))}
    out = list(done.values())
    for n, it in enumerate(plan, 1):
        key = f"{it['reciter']}:{it['surah']}"
        if key in done:
            continue
        mp3 = os.path.join(WORK, f"{it['reciter']}_{it['surah']:03d}.mp3")
        row = {"reciter": it["reciter"], "surah": it["surah"], "startMs": it["startMs"]}
        try:
            if not os.path.exists(mp3):
                # ⚡ لا نُنزّل السورة كاملة (‏10–25م.ب) لأجل ست ثوانٍ: نطلب
                # **أول 256ك.ب** بترويسة Range — تكفي ≥12ث عند 128ك.بت/ث،
                # وmp3 يُفكّ مبتوراً بلا ضرر. (خفّض زمن السورة من ~دقيقة إلى ثوانٍ.)
                import urllib.request
                req = urllib.request.Request(it["url"],
                                             headers={"Range": "bytes=0-262143"})
                with urllib.request.urlopen(req, timeout=60) as r, open(mp3, "wb") as f:
                    f.write(r.read())
            base = os.path.join(WORK, "clip.wav")
            t0 = time.time()
            heard6 = text_of(model, cut(mp3, it["startMs"], 6000, base)).split()
            row["heard6"] = " ".join(heard6[:8])
            i = fuzzy_seq(heard6)
            row["basmala"] = i is not None
            if i is None:
                t = basmala_tail(heard6)
                if t and (t[1] >= 2 or it["startMs"] <= 8000):
                    row["basmala"] = True
                    row["partial"] = f"ذيلٌ من {t[1]} كلمات — الحدّ داخل البسملة"
            if i is not None:
                # ⛔ لا تُطلب النهاية بتوسيع النافذة: كلما اتّسعت **ابتلعت
                # البسملة نفسها** (‏73:1 عند 8ث يعود بلا بسملة). فتُطلب
                # بالعكس: **أصغر نافذةٍ تظهر فيها البسملة تامّةً** — وهي حدّ
                # نهايتها (منهج 7e، وقياسه على 22:1 أعطى 2.5–3.0ث).
                end = None
                for d in range(1500, 5001, 250):
                    w = text_of(model, cut(mp3, it["startMs"], d, base)).split()
                    j = fuzzy_seq(w)
                    if j is not None and len(w) >= j + len(BAS):
                        end = d
                        break
                row["basmalaEndMsApprox"] = (it["startMs"] + end) if end else None
                row["endWindowMs"] = end
            row["ms"] = int((time.time() - t0) * 1000)
        except Exception as e:
            row["error"] = str(e)[:120]
        finally:
            if os.path.exists(mp3):
                os.remove(mp3)
        out.append(row)
        json.dump(out, open(args.out, "w", encoding="utf-8"), ensure_ascii=False)
        print(f"[{n}/{len(plan)}] {key} · بسملة={row.get('basmala')} "
              f"· {row.get('heard6','')[:40]}", flush=True)
    hits = [r for r in out if r.get("basmala")]
    print(f"\n✅ فُحص {len(out)} · **بسملة مؤكَّدة: {len(hits)}**")


if __name__ == "__main__":
    main()
