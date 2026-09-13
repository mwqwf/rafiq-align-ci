# -*- coding: utf-8 -*-
"""⏱️ **زمنُ الفكّ بذراعَين على العتاد الذي تُشغَّل عليه** — بلا تطبيقٍ وبلا جهاز المالك.

⛔ **لماذا وُجدت** (‏D-334): محاكي العدّاء `x86_64` **لا يُظهر انهيارَ `greedy`** أصلاً (صفرُ بندٍ من
ستّين)، وعلى هاتف المالك `arm64` انهار في بندَين من عشرةٍ فبلغ RTF 1.63 — ونسبةُ بطءِ الهاتف عن
العدّاء تتراوح **×1.77 إلى ×9.26** في `greedy` و×1.32 إلى ×2.86 في `beam 5`. فالسؤالُ «هل يبوّب
الحرسُ أسوأَ الحالات؟» كان مفتوحاً بلا أداة، وإذنُ الهاتف استُنفد. وعدّاءُ `ubuntu-*-arm` يعطينا
**المعماريةَ نفسَها مجّاناً وبلا جهازه** — فإن ظهر الانهيارُ هناك صار السؤالُ مقيساً في كلّ شوط.

    python tools/tasmi_bench/cli_time.py --cli build/bin/whisper-cli --model work/ggml-q8.bin \\
        --src work/g4 --plan work/long_plan.json --threads 2 --md work/arm_time.md

⚠️ **الأمانةُ في الحدود:** هذا ليس أندرويد (‏bionic غيرُ glibc، والمعالجُ غيرُ معالجِه)، فلا يُنقل رقمُه
إلى جهاز المستخدم رقماً مطلقاً. الذي يُقاس هنا **سلوكٌ**: أيتفجّر `greedy` على `arm64` أم لا.
"""
import argparse
import json
import os
import re
import statistics as st
import subprocess
import sys
import time

import soundfile as sf

ARMS = {
    # المشحونُ اليوم: greedy بعتبةِ إنتروبيا 2.40 (افتراضُ المكتبة)
    "greedy": ["-bs", "1", "-et", "2.40"],
    # ‏`decodeGuard`: بحثُ حزمةٍ 5 وعتبةٌ أضيق 1.80 — مرآةُ `jni.c` حرفاً بحرف
    "guard": ["-bs", "5", "-et", "1.80"],
}
_NUM = re.compile(r"([0-9]+\.[0-9]+)")


def run_one(cli, model, wav, arm, threads, lang):
    """يعيد (ثوانيَ الاستدلال بلا التحميل، عددَ المقاطع، النصَّ) — أو يرفع إن سكتت الأداة."""
    cmd = [cli, "-m", model, "-t", str(threads), "-l", lang, "-ojf"] + ARMS[arm] + [wav]
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = (p.stdout or "") + (p.stderr or "")
    if "usage:" in out and "error:" in out:
        raise SystemExit(f"⛔ الأداةُ ردّت الاستعمالَ لا نتيجةً (رايةٌ غيرُ مدعومة): {out[:200]}")
    load = tot = None
    for ln in out.splitlines():
        if " load time" in ln:
            m = _NUM.search(ln); load = float(m.group(1)) if m else None
        elif " total time" in ln:
            m = _NUM.search(ln); tot = float(m.group(1)) if m else None
    if load is None or tot is None:
        raise SystemExit(f"⛔ لا زمنَ في مخرَج الأداة لـ{os.path.basename(wav)}/{arm} ⇒ لا يُحتسب صفراً:\n{out[-400:]}")
    segs = [ln for ln in out.splitlines() if ln.startswith("[")]
    text = " ".join(re.sub(r"^\[[^\]]*\]\s*", "", ln).strip() for ln in segs)
    return (tot - load) / 1000.0, len(segs), text


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cli", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--src", required=True, help="مجلدُ ملفّات wav")
    ap.add_argument("--plan", default="", help="‏json فيه items بمفاتيح id و durationSec (اختياريّ — وإلّا فمن الملفّ)")
    ap.add_argument("--threads", type=int, default=2, help="⚠️ سياسةُ التطبيق: عدُّ الأنوية التي تردّدها فوق الأدنى")
    ap.add_argument("--lang", default="en", help="‏D-308/D-313: المشحونُ يُخدم بـen صريحاً")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--md", default="")
    ap.add_argument("--json", default="")
    a = ap.parse_args()

    # ⏱️ **المدّةُ من الملفّ إن لم تكن في الخطّة** (2026-09-13): `sample.json` — وهي خطّةُ الآية
    # المفردة — **لا تحمل `durationSec` أصلاً** (‏202 بندٍ · صفرُ مدّة)، فكان الشوطُ يموت بـ«لا ملفَّ
    # له مدّة» وكأنّ المجموعةَ غائبة، والمجموعةُ حاضرةٌ والمدّةُ في الملفّ نفسِه. ⇒ الخطّةُ صارت
    # **تحسيناً لا شرطاً**: ما لم تُسمِّ مدّتَه تُقرأ من ترويسة الـwav.
    dur = {}
    if a.plan:
        plan = json.load(open(a.plan, encoding="utf-8"))
        items = plan["items"] if isinstance(plan, dict) else plan
        dur = {it["id"]: it.get("durationSec") for it in items if it.get("durationSec")}
    files = sorted(f for f in os.listdir(a.src) if f.endswith(".wav"))
    if a.limit:
        files = files[: a.limit]
    if not files:
        raise SystemExit(f"⛔ لا ملفَّ wav في {a.src} — لا يُقرأ الصفرُ نتيجةً")
    miss = 0
    for f in files:
        if not dur.get(f[:-4]):
            info = sf.info(os.path.join(a.src, f))
            dur[f[:-4]] = info.frames / float(info.samplerate)
            miss += 1
    if miss:
        print(f"⏱️ {miss} بنداً مدّتُها من الملفّ لا من الخطّة", flush=True)
    print(f"⏱️ {len(files)} بنداً · خيوط {a.threads} · لغة {a.lang}", flush=True)

    rows = {}
    for k, f in enumerate(files, 1):
        i = f[:-4]
        for arm in ("greedy", "guard"):   # متداخلتان لكلّ بندٍ كي تتقاسما حالةَ الحرارة
            s, n, txt = run_one(a.cli, a.model, os.path.join(a.src, f), arm, a.threads, a.lang)
            rows.setdefault(arm, {})[i] = {"sec": s, "rtf": s / dur[i], "segs": n, "text": txt}
        if k % 5 == 0 or k == len(files):
            print(f"   … {k}/{len(files)}", flush=True)

    def q(v, p):
        v = sorted(v); x = (len(v) - 1) * p; lo = int(x)
        return v[lo] if lo == x else v[lo] + (v[lo + 1] - v[lo]) * (x - lo)

    L = [f"### ⏱️ زمنُ الفكّ على `{os.uname().machine if hasattr(os, 'uname') else '?'}` · {len(files)} بنداً · {a.threads} خيطاً\n",
         "| المقياس | greedy | beam 5 + et 1.8 |", "|---|---:|---:|"]
    for lab, fn in (("RTF وسيطاً", lambda v: q(v, .5)), ("RTF p90", lambda v: q(v, .9)),
                    ("RTF أقصى", max), ("زمنٌ كلّيٌّ ÷ صوتٌ كلّيّ", None)):
        if fn is None:
            tb = sum(r["sec"] for r in rows["greedy"].values()) / sum(dur[i] for i in rows["greedy"])
            tg = sum(r["sec"] for r in rows["guard"].values()) / sum(dur[i] for i in rows["guard"])
            L.append(f"| {lab} | {tb:.3f} | {tg:.3f} |")
            continue
        L.append(f"| {lab} | {fn([r['rtf'] for r in rows['greedy'].values()]):.3f} | "
                 f"{fn([r['rtf'] for r in rows['guard'].values()]):.3f} |")
    for t in (1.0,):
        cb = sum(1 for r in rows["greedy"].values() if r["rtf"] > t)
        cg = sum(1 for r in rows["guard"].values() if r["rtf"] > t)
        L.append(f"| **بنودٌ يتجاوز فيها الزمنَ الحقيقيّ (‏RTF>{t:g})** | **{cb}/{len(files)}** | **{cg}/{len(files)}** |")
    rat = [rows["guard"][i]["sec"] / rows["greedy"][i]["sec"] for i in rows["greedy"]]
    L.append(f"\n**نسبةُ الحرس إلى greedy:** وسيطاً ×{st.median(rat):.2f} · المدى ×{min(rat):.2f}–×{max(rat):.2f} "
             f"· الحرسُ أسرعُ في {sum(1 for x in rat if x < 1)}/{len(rat)} بنداً")
    # 🔍 وأثرُ الانهيار يُسمّى: بنودٌ نسبتُها دون 1 هي التي انهار فيها greedy
    bad = sorted(((rows["greedy"][i]["rtf"], i) for i in rows["greedy"]), reverse=True)[:5]
    L.append("\n**أسوأُ خمسةٍ في greedy:** " + " · ".join(f"`{i}` RTF {r:.2f}" for r, i in bad))
    md = "\n".join(L)
    print("\n" + md)
    if a.md:
        open(a.md, "w", encoding="utf-8").write(md + "\n")
    if a.json:
        json.dump({"threads": a.threads, "lang": a.lang, "rows": rows},
                  open(a.json, "w", encoding="utf-8"), ensure_ascii=False)


if __name__ == "__main__":
    sys.exit(main())
