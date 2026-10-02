#!/usr/bin/env python3
"""⚡ **مقارنةُ سرعة المحرّك المحلّيّ ودقّته على مادّة الحلقة الحيّة** (‏«سمّع معي» · 2026-10-02).

يُسأل هنا سؤالان، وكلاهما على `arm64` بلا جهاز المالك:

1. **أيُّ رايات بناءٍ لنواة `ggml-cpu`؟** التطبيقُ يشحن النواةَ مبنيّةً على `armv8-a` الأساسيّة
   (‏قِيس في البناء المحلّيّ: صفرُ تعليمة `sdot` وصفرُ `fmla .8h` في `libggml-cpu.so`، لأنّ
   رايةَ `-march` في `CMakeLists.txt` تُطبَّق على هدف `ggml` لا على `ggml-cpu`). فتُقارن ثلاثُ
   أدواتٍ مبنيّةٍ من المصدر نفسِه: `base` (‏armv8-a = المشحون) · `dp` (‏+dotprod) · `i8` (‏+dotprod+i8mm).
   ⇒ الزمنُ يُقاس، و**تطابقُ النصّ** مع `base` يُعدّ (‏الحسابُ الصحيحُ لا يغيّر الناتج إلا نادراً).
2. **`audio_ctx` تناسبيّاً مع طول المقطع** (‏`-ac`): نافذةُ 3.6ث تُرمَّز اليوم كأنها 30ث. يُقاس الزمنُ
   والدقّةُ معاً — على البنود القصيرة كاملةً (‏WER مقابل نصّ الآية) وعلى **قصّةِ 3.6ث** من كلّ بند
   (‏شكلُ نافذة الحلقة الحيّة: اتّفاقُ الكلمات مع ناتج السياق الكامل).

⛔ لا يُشحن `audio_ctx` إلا إن لم ترتفع WER ولم ينخفض الاتّفاق انخفاضاً يُعتدّ به — والجدولُ يقول ذلك صريحاً.
"""
import argparse
import json
import math
import os
import re
import statistics as st
import subprocess
import sys

SR = 16000
_NUM = re.compile(r"=\s*([0-9.]+)\s*ms")
_DIAC = re.compile(r"[ؐ-ًؚ-ٰٟۖ-ۭـ]")
_NON_AR = re.compile(r"[^ء-ي\s]")


def norm_words(t):
    """هيكلُ الرسم المجرّد تقريباً: بلا تشكيلٍ ولا علامات وقف، والألفاتُ ألفٌ واحدة."""
    t = _DIAC.sub("", t or "")
    for a, b in (("أ", "ا"), ("إ", "ا"), ("آ", "ا"), ("ٱ", "ا"), ("ى", "ي"), ("ة", "ه"), ("ؤ", "ء"), ("ئ", "ء")):
        t = t.replace(a, b)
    t = _NON_AR.sub(" ", t)
    return [w for w in t.split() if w]


def edits(a, b):
    """مسافةُ التحرير بالكلمات."""
    prev = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        cur = [i] + [0] * len(b)
        for j, y in enumerate(b, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (x != y))
        prev = cur
    return prev[-1]


def run_cli(cli, model, wav, threads, lang, extra, env=None):
    """[env]: متغيّراتُ بيئةٍ إضافيّةٌ للعمليّة (‏مثل `KMP_BLOCKTIME=0` لذراع قياس) — لا شيءَ افتراضاً."""
    cmd = [cli, "-m", model, "-t", str(threads), "-l", lang, "-bs", "1", "-et", "2.40", "-nt"] + extra + [wav]
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env=(dict(os.environ, **env) if env else None))
    out = (p.stdout or "") + "\n" + (p.stderr or "")
    load = tot = None
    for ln in out.splitlines():
        if " load time" in ln:
            m = _NUM.search(ln); load = float(m.group(1)) if m else None
        elif " total time" in ln:
            m = _NUM.search(ln); tot = float(m.group(1)) if m else None
    if load is None or tot is None:
        raise SystemExit("⛔ لا زمنَ في مخرَج الأداة لـ%s (%s):\n%s" % (os.path.basename(wav), " ".join(extra), out[-500:]))
    text = " ".join(ln.strip() for ln in (p.stdout or "").splitlines() if ln.strip() and not ln.startswith("whisper_"))
    return (tot - load) / 1000.0, text


def audio_ctx_for(dur_s, pad_s):
    """إطاراتُ المرمِّز لمقطعٍ مدّتُه [dur_s]: 50 إطاراً في الثانية + هامش، مقرَّباً إلى 32 وبسقف 1500."""
    n = int(math.ceil((dur_s + pad_s) * 50))
    return min(1500, ((n + 31) // 32) * 32)


def crop(src, dst, seconds):
    import soundfile as sf
    a, sr = sf.read(src, dtype="float32")
    if sr != SR:
        raise SystemExit("⛔ معدّلُ العيّنة %d لا %d" % (sr, SR))
    sf.write(dst, a[: int(seconds * SR)], SR, subtype="PCM_16")
    return min(len(a), int(seconds * SR)) / SR


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--clis", required=True, help="اسم=مسار مفصولةً بفاصلة؛ الأوّلُ هو المرجع (المشحون)")
    ap.add_argument("--model", required=True)
    ap.add_argument("--lang", default="en")
    ap.add_argument("--src", required=True)
    ap.add_argument("--sample", default="sample.json")
    ap.add_argument("--threads", type=int, default=2)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--pad", type=float, default=1.0, help="هامشُ audio_ctx بالثواني")
    ap.add_argument("--window", type=float, default=3.6, help="طولُ نافذة الحلقة الحيّة")
    ap.add_argument("--md", required=True)
    ap.add_argument("--json", required=True)
    a = ap.parse_args()

    clis = [tuple(x.split("=", 1)) for x in a.clis.split(",") if x]
    ref_name = clis[0][0]
    fast_name = clis[-1][0]
    items = {it["id"]: it for it in json.load(open(a.sample, encoding="utf-8"))["items"]}
    wavs = sorted(f for f in os.listdir(a.src) if f.endswith(".wav") and f[:-4] in items)
    if a.limit:
        wavs = wavs[: a.limit]
    if not wavs:
        raise SystemExit("⛔ لا بنود في %s" % a.src)
    tmp = os.path.join(os.path.dirname(a.json) or ".", "crops")
    os.makedirs(tmp, exist_ok=True)
    import soundfile as sf

    rows = []
    for k, f in enumerate(wavs):
        iid = f[:-4]
        it = items[iid]
        wav = os.path.join(a.src, f)
        dur = sf.info(wav).duration
        cw = os.path.join(tmp, f)
        cdur = crop(wav, cw, a.window)
        row = {"id": iid, "stratum": it.get("stratum"), "dur": dur, "ref": it["refText"]}
        # 🔁 الأذرعُ متداخلةٌ والترتيبُ يدور مع البند — فلا يأخذ ذراعٌ حرارةَ المعالج وحدَه.
        arms = [(n, c, []) for n, c in clis] + [("actx", dict(clis)[fast_name], ["-ac", str(audio_ctx_for(dur, a.pad))])]
        arms = arms[k % len(arms):] + arms[: k % len(arms)]
        for name, cli, extra in arms:
            sec, text = run_cli(cli, a.model, wav, a.threads, a.lang, extra)
            row[name] = {"sec": sec, "text": text}
            cextra = ["-ac", str(audio_ctx_for(cdur, a.pad))] if name == "actx" else []
            csec, ctext = run_cli(cli, a.model, cw, a.threads, a.lang, cextra)
            row[name + "@win"] = {"sec": csec, "text": ctext}
        rows.append(row)
        print("%3d/%d %s %.1fث" % (k + 1, len(wavs), iid, dur), flush=True)

    names = [n for n, _ in clis] + ["actx"]
    lines = ["## ⚡ سرعةُ المحرّك المحلّيّ — %s · %d بنداً · %d خيوط" % (os.path.basename(a.model), len(rows), a.threads), "",
             "| الذراع | وسيطُ الزمن (بند كامل) | وسيطُ الزمن (نافذة %.1fث) | ×أسرع من %s (نافذة) | WER كامل | تطابقُ النصّ مع %s (كامل) | اتّفاقُ كلمات النافذة مع %s |" % (a.window, ref_name, ref_name, ref_name),
             "|---|---|---|---|---|---|---|"]
    summary = {}
    base_win = st.median(r[ref_name + "@win"]["sec"] for r in rows)
    for n in names:
        full = st.median(r[n]["sec"] for r in rows)
        win = st.median(r[n + "@win"]["sec"] for r in rows)
        e = sum(edits(norm_words(r[n]["text"]), norm_words(r["ref"])) for r in rows)
        nref = sum(len(norm_words(r["ref"])) for r in rows)
        same = sum(norm_words(r[n]["text"]) == norm_words(r[ref_name]["text"]) for r in rows)
        agree_e = sum(edits(norm_words(r[n + "@win"]["text"]), norm_words(r[ref_name + "@win"]["text"])) for r in rows)
        agree_n = sum(max(1, len(norm_words(r[ref_name + "@win"]["text"]))) for r in rows)
        s = {"full_med_s": full, "win_med_s": win, "speedup_win": base_win / win if win else None,
             "wer": e / max(1, nref), "same_text": same, "items": len(rows), "win_agree": 1 - agree_e / agree_n}
        summary[n] = s
        lines.append("| %s | %.3fث | %.3fث | ×%.2f | %.2f%% | %d/%d | %.2f%% |" % (
            n, full, win, s["speedup_win"] or 0, 100 * s["wer"], same, len(rows), 100 * s["win_agree"]))
    lines += ["", "- `actx` = أسرعُ بناءٍ (%s) + `-ac` تناسبيّاً (‏مدّة + %.1fث، مقرَّباً إلى 32 إطاراً)." % (fast_name, a.pad)]
    md = "\n".join(lines) + "\n"
    open(a.md, "w", encoding="utf-8").write(md)
    json.dump({"summary": summary, "rows": rows}, open(a.json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(md)


if __name__ == "__main__":
    main()
