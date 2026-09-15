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


ARMS = {
    # المشحونُ اليوم: greedy بعتبةِ إنتروبيا 2.40 (افتراضُ المكتبة)
    "greedy": ["-bs", "1", "-et", "2.40"],
    # ‏`decodeGuard`: بحثُ حزمةٍ 5 وعتبةٌ أضيق 1.80 — مرآةُ `jni.c` حرفاً بحرف
    "guard": ["-bs", "5", "-et", "1.80"],
    # 🔇 **ذراعُ D-513**: المشحونُ نفسُه + **رفعُ إسكاتِ النافذة** (`no_speech_thold`).
    #    المصدرُ المثبَّت (`whisper.cpp@c4ac001:7711`) يُسقط **النافذةَ كلَّها** (ثلاثين ثانية)
    #    حين `no_speech_prob > 0.6` **و**`avg_logprobs < -1.0` ⇒ آياتٌ متتاليةٌ تختفي دفعةً.
    #    و`1.01` احتمالٌ **لا يُبلَغ** ⇒ يُبطل الإسقاطَ وحدَه ولا يمسّ عتبةَ الثقة ولا الإنتروبيا.
    #    ⚠️ وهي **مرآةُ مفتاح `WhisperDecode.hearAll`** لا التطبيقُ نفسُه (‏حدُّ الأداة في رأسها).
    "hearall": ["-bs", "1", "-et", "2.40", "-nth", "1.01"],
}

# 🏷️ عنوانُ كلّ ذراعٍ في الجدول — والمجهولُ يُسمّى باسمه لا بفراغ.
ARM_LABEL = {
    "greedy": "greedy",
    "guard": "beam 5 + et 1.8",
    "hearall": "greedy + nth 1.01",
}
_NUM = re.compile(r"([0-9]+\.[0-9]+)")


def silence_stats(rows_arm):
    """🔇 **بنودٌ خرج تفريغُها فارغاً** — وهي بصمةُ إسقاطِ النافذة (‏D-513).

    ترجع (‏عددَ الفارغة · عددَ الكلمات كلِّها). ⛔ و«فارغٌ» يعني **لا كلمةَ واحدة** بعد
    التشذيب — لا «قليلٌ»: فالقليلُ حكمُ دقّةٍ لا حكمُ إسكات.
    """
    empty = sum(1 for r in rows_arm.values() if not (r.get("text") or "").strip())
    words = sum(len((r.get("text") or "").split()) for r in rows_arm.values())
    return empty, words


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
    # 🎛️ **والذراعان تُسمّيان** (‏أُضيف 2026-09-15 · D-515): الافتراضُ **هو المشحونُ سلفاً**
    #    (`greedy,guard`) فلا يتبدّل رقمٌ منشور، ومن أراد ذراعاً أخرى سمّاها في الطلب.
    ap.add_argument("--arms", default="greedy,guard",
                    help="ذراعان بالاسم من ARMS مفصولتان بفاصلة (الافتراض: greedy,guard)")
    ap.add_argument("--md", default="")
    ap.add_argument("--json", default="")
    a = ap.parse_args()

    # ⏱️ **المدّةُ من الملفّ إن لم تكن في الخطّة** (2026-09-13): `sample.json` — وهي خطّةُ الآية
    # المفردة — **لا تحمل `durationSec` أصلاً** (‏202 بندٍ · صفرُ مدّة)، فكان الشوطُ يموت بـ«لا ملفَّ
    # له مدّة» وكأنّ المجموعةَ غائبة، والمجموعةُ حاضرةٌ والمدّةُ في الملفّ نفسِه. ⇒ الخطّةُ صارت
    # **تحسيناً لا شرطاً**: ما لم تُسمِّ مدّتَه تُقرأ من ترويسة الـwav.
    arms = [x.strip() for x in a.arms.split(",") if x.strip()]
    if len(arms) != 2:
        raise SystemExit(f"⛔ ذراعان بالاسم لا {len(arms)}: {a.arms}")
    if arms[0] == arms[1]:
        raise SystemExit("⛔ ذراعان متطابقتان سؤالٌ لا جواب (D-385)")
    for x in arms:
        if x not in ARMS:
            raise SystemExit(f"⛔ ذراعٌ لا تُعرف: {x} — والمعروفُ {' · '.join(ARMS)}")
    A, B = arms

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
            # 📦 **وحملُ `soundfile` هنا لا في الرأس** (‏2026-09-15): كان استيراداً علويّاً
            #    ⇒ **`--selftest` نفسُه لا يعمل** إلا في بيئةٍ فيها عدّةُ الصوت، وضابطٌ لا
            #    يُشغَّل في الصندوق حارسٌ نصفُ حاضر. والقراءةُ لا تحدث إلا هنا أصلاً.
            import soundfile as sf
            info = sf.info(os.path.join(a.src, f))
            dur[f[:-4]] = info.frames / float(info.samplerate)
            miss += 1
    if miss:
        print(f"⏱️ {miss} بنداً مدّتُها من الملفّ لا من الخطّة", flush=True)
    print(f"⏱️ {len(files)} بنداً · خيوط {a.threads} · لغة {a.lang}", flush=True)

    rows = {}
    for k, f in enumerate(files, 1):
        i = f[:-4]
        for arm in (A, B):   # متداخلتان لكلّ بندٍ كي تتقاسما حالةَ الحرارة
            s, n, txt = run_one(a.cli, a.model, os.path.join(a.src, f), arm, a.threads, a.lang)
            rows.setdefault(arm, {})[i] = {"sec": s, "rtf": s / dur[i], "segs": n, "text": txt}
        if k % 5 == 0 or k == len(files):
            print(f"   … {k}/{len(files)}", flush=True)

    def q(v, p):
        v = sorted(v); x = (len(v) - 1) * p; lo = int(x)
        return v[lo] if lo == x else v[lo] + (v[lo + 1] - v[lo]) * (x - lo)

    L = [f"### ⏱️ زمنُ الفكّ على `{os.uname().machine if hasattr(os, 'uname') else '?'}` · {len(files)} بنداً · {a.threads} خيطاً\n",
         f"| المقياس | {ARM_LABEL.get(A, A)} | {ARM_LABEL.get(B, B)} |", "|---|---:|---:|"]
    for lab, fn in (("RTF وسيطاً", lambda v: q(v, .5)), ("RTF p90", lambda v: q(v, .9)),
                    ("RTF أقصى", max), ("زمنٌ كلّيٌّ ÷ صوتٌ كلّيّ", None)):
        if fn is None:
            tb = sum(r["sec"] for r in rows[A].values()) / sum(dur[i] for i in rows[A])
            tg = sum(r["sec"] for r in rows[B].values()) / sum(dur[i] for i in rows[B])
            L.append(f"| {lab} | {tb:.3f} | {tg:.3f} |")
            continue
        L.append(f"| {lab} | {fn([r['rtf'] for r in rows[A].values()]):.3f} | "
                 f"{fn([r['rtf'] for r in rows[B].values()]):.3f} |")
    for t in (1.0,):
        cb = sum(1 for r in rows[A].values() if r["rtf"] > t)
        cg = sum(1 for r in rows[B].values() if r["rtf"] > t)
        L.append(f"| **بنودٌ يتجاوز فيها الزمنَ الحقيقيّ (‏RTF>{t:g})** | **{cb}/{len(files)}** | **{cg}/{len(files)}** |")
    # 🔇 **وصفُّ الإسكات — وهو المقصودُ من ذراع `hearall`** (‏D-513): بندٌ خرج تفريغُه **فارغاً**
    #    هو «لم أسمع شيئاً» بعينها. ويُقرأ **مع عدد الكلمات**: فارغٌ يهبط وكلماتٌ تُزاد = سمعٌ
    #    عاد؛ وفارغٌ يهبط وكلماتٌ تنفجر = هَلوَسةٌ على صمت، **والثانيةُ ثمنٌ لا مكسب**.
    ea, wa = silence_stats(rows[A])
    eb, wb = silence_stats(rows[B])
    L.append(f"| 🔇 **بنودٌ تفريغُها فارغ** | **{ea}/{len(files)}** | **{eb}/{len(files)}** |")
    L.append(f"| 📝 كلماتٌ مسموعةٌ كلّيّاً | {wa} | {wb} |")
    rat = [rows[B][i]["sec"] / rows[A][i]["sec"] for i in rows[A]]
    L.append(f"\n**نسبةُ {ARM_LABEL.get(B, B)} إلى {ARM_LABEL.get(A, A)}:** وسيطاً ×{st.median(rat):.2f} · المدى ×{min(rat):.2f}–×{max(rat):.2f} "
             f"· الحرسُ أسرعُ في {sum(1 for x in rat if x < 1)}/{len(rat)} بنداً")
    # 🔍 وأثرُ الانهيار يُسمّى: بنودٌ نسبتُها دون 1 هي التي انهار فيها greedy
    bad = sorted(((rows[A][i]["rtf"], i) for i in rows[A]), reverse=True)[:5]
    L.append(f"\n**أسوأُ خمسةٍ في {ARM_LABEL.get(A, A)}:** " + " · ".join(f"`{i}` RTF {r:.2f}" for r, i in bad))
    # 🧠 **وذروةُ الذاكرة تُقاس مع الزمن لا بعده** (‏أُضيفت 2026-09-14 لثمن D-432): رفعُ عدد
    # الخيوط يشتري زمناً **بذاكرةٍ** (‏كلُّ خيطٍ في ggml مخزنُه)، فلا يُقرأ الكسبُ بلا ثمنِه.
    # ⛔ **وحدُّ ما يقيسه `ru_maxrss` لـ`RUSAGE_CHILDREN`:** ذروةُ **أكبرِ ابنٍ انتهى** — وكلُّ
    # ابنٍ هنا تفريغةٌ واحدة ⇒ فهو **ذروةُ تفريغةٍ واحدةٍ في هذه الذراع** لا مجموعَ البنود.
    # وعلى لينكس بالكيبيبايت (‏وهي بيئةُ الأشواط كلِّها). وغيابُ `resource` لا يُسقط القياسَ.
    peak_kb = None
    try:
        import resource
        peak_kb = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    except Exception:
        pass
    if peak_kb:
        L.append(f"\n**ذروةُ ذاكرةِ تفريغةٍ واحدةٍ (‏أكبرُ ابن):** {peak_kb / 1024.0:.1f} م.ب "
                 f"بـ{a.threads} خيطاً")
    md = "\n".join(L)
    print("\n" + md)
    if a.md:
        open(a.md, "w", encoding="utf-8").write(md + "\n")
    if a.json:
        json.dump({"threads": a.threads, "lang": a.lang, "arms": [A, B], "peak_rss_kb": peak_kb,
                   "silence": {A: silence_stats(rows[A]), B: silence_stats(rows[B])}, "rows": rows},
                  open(a.json, "w", encoding="utf-8"), ensure_ascii=False)


def _selftest():
    fails = []

    def ok(c, m):
        if not c:
            fails.append(m)

    # ① ذراعُ D-513 هي المشحونةُ + رفعُ الإسكات وحدَه
    ok(ARMS["hearall"][:4] == ARMS["greedy"], "‏hearall تبدأ بذراع المشحون حرفاً")
    ok(ARMS["hearall"][4:] == ["-nth", "1.01"], "‏hearall تضيف `-nth 1.01` ولا شيءَ غيرَه")
    ok("-bs" in ARMS["hearall"] and ARMS["hearall"][ARMS["hearall"].index("-bs") + 1] == "1",
       "‏hearall تبقى greedy لا حزمة")
    ok(all("-lpt" not in v and "--logprob-thold" not in v for v in ARMS.values()),
       "⛔ لا ذراعَ تمسّ عتبةَ الثقة")
    ok(float(ARMS["hearall"][-1]) > 1.0, "‏العتبةُ احتمالٌ لا يُبلَغ (> 1.0)")
    ok(set(ARM_LABEL) >= set(ARMS), "لكلّ ذراعٍ عنوانٌ في الجدول")

    # ② عدُّ الإسكات
    R = {"a": {"text": ""}, "b": {"text": "   "}, "c": {"text": "ولا الضالين"}}
    e, w = silence_stats(R)
    ok(e == 2, f"الفارغُ اثنان (والفراغُ بمسافاتٍ فارغٌ) — جاء {e}")
    ok(w == 2, f"الكلماتُ اثنتان — جاءت {w}")
    ok(silence_stats({}) == (0, 0), "لا بنودَ ⇒ صفران بلا انفجار")
    ok(silence_stats({"a": {}}) == (1, 0), "بندٌ بلا مفتاح `text` يُعَدّ فارغاً لا يُسقط الأداة")

    print("🧪 ضوابطُ `cli_time`: %d إخفاقاً" % len(fails))
    for m in fails:
        print("  ⛔", m)
    return 1 if fails else 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(_selftest())
    sys.exit(main())
