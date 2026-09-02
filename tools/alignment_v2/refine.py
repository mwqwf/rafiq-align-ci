# -*- coding: utf-8 -*-
"""صقل حدود MED بطوابع whisper الكلمية على **نافذة قصيرة حول الحد** (alignment_v2).

المشكلة: عدة آيات تُتلى بنَفَس واحد ⇒ مقطع VAD واحد يملك آيتين فأكثر، فتُقسم
حدودها بتوزيع خطي تقديري ⇒ `snapped=False` ⇒ عقوبة الثقة ⇒ MED.

**الدرس الذي فرض التصميم:** أول تنفيذ كان يعيد تفريغ المقطع كله ويشترط أن يكون
دون 10ث احتراماً لدرس ../alignment/README.md البند الأول. أسقطه القياس: على مريم
المُحكمة كانت 67 هدفاً من 67 داخل مقاطع أطول من 10ث (مقاطع النَّفَس الواحد طويلة
بطبعها) فكانت الحصيلة صفر صقل. الحل ليس تخطي المقطع الطويل بل عدم تفريغه أصلاً:
نفرّغ نافذة قصيرة مركزها الحد المقدَّر، ونحاذيها بمرجع محلي (ذيل الآية السابقة
ورأس اللاحقة) لا بالسورة كلها. فالنافذة قصيرة دائماً والدرس محفوظ.

حارس ثانٍ مقيس: الطوابع تتشبّع عند نهاية النافذة (كل الكلمات المتأخرة تأخذ زمن
النهاية) فنُسقط أي كلمة يقع طابعها في آخر SAT_MS منها.
"""
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "alignment"))
from align import nw_align  # noqa: E402
from common import FFMPEG, MODEL_Q8, WHISPER_CLI, norm  # noqa: E402
from vad import silences  # noqa: E402

from gt import W2  # noqa: E402

WINDOW_MS = 9_000        # طول نافذة التفريغ حول الحد — دون سقف الموثوقية (10ث)
PAD_MS = 250             # هامش يمنع قصّ أول/آخر كلمة
SAT_MS = 120             # منطقة تشبّع الطوابع عند نهاية النافذة
SNAP_WINDOW_MS = 400     # نافذة الالتقاط على صمت دقيق داخل الفجوة
CTX_WORDS = 10           # كم كلمة من ذيل السابقة ورأس اللاحقة تدخل المرجع المحلي
MIN_ANCHOR = 2           # أقل عدد كلمات متطابقة على كل جانب لقبول الصقل
SLIDE_MS = (0, -3000, 3000)  # انزلاق أعمى عند غياب المرساتين
MAX_EDGE_CHASES = 3          # مطاردة موجَّهة عند استقرار الحد على حافة النافذة
# ── حارس الترقية (D-025): HIGH وعدٌ للمستهلك لا وصف إحصائي ──────────────────
# مقيس على 150 حداً مصقولاً (مريم + طه):
#   · `token-mid` وقع مرة واحدة فقط وكان هو الفشل الأفدح (خطأ 1796م.ث، acc=0.2)
#     ⇒ **لا يُرقّى أبداً**: الحد الذي لم يُسنَد إلى صمت حقيقي تخمينٌ محسَّن لا برهان.
#   · الحد الوحيد الآخر خارج ±300م.ث (مريم 17، خطأ 320م.ث) كان acc=0.714 بينما
#     وسيط acc = 0.75 ⇒ عتبة `acc >= 0.75` تُخرجه ولا تُسرّب شيئاً (0/78).
# الكلفة: تُرقّى 78 من 150 فقط. وهي كلفة **تسمية لا توقيت** — الحدود الـ150 كلها
# تحتفظ بزمنها المصقول المحسَّن، والحارس يحكم شارة الثقة وحدها.
EDGE_MARGIN_MS = 400     # حدٌّ يستقر على حافة النافذة = فشل مقنَّع (انظر أدناه)
PROMOTE_MIN_ACC = 0.75
MED_CEIL = 0.74          # سقف ثقة من لم يجتز الحارس (يبقى MED)


def clip_words(wav, start_ms, end_ms, tag, cache_dir=None):
    """يعيد [{"w":كلمة مطبَّعة, "s":ms مطلق, "e":ms مطلق}] لنافذة قصيرة.

    ⚠️ **الطوابع من `t_dtw` حصراً** — لا من `offsets`. المقيس على نموذجنا q8:
    طوابع `offsets` ممطَّطة ~3× ثم تتشبّع عند نهاية النافذة (٧ كلمات في ٩ث:
    أول كلمة 0–5140م.ث والأربع الأخيرة كلها عند 8990). أما `t_dtw` فسليمة
    ورتيبة (0.24→8.96ث للكلمات السبع نفسها).

    وسبب فشلنا الأول مع `-dtw`: **الانتباه الخاطف يعطّله بصمت** —
    `dtw_token_timestamps is not supported with flash_attn - disabling` —
    وflash-attn مفعّل افتراضياً، فلا بد من `-nfa` صراحةً.
    """
    cache_dir = cache_dir or os.path.join(W2, "clips")
    os.makedirs(cache_dir, exist_ok=True)
    cache = os.path.join(cache_dir, tag + ".words.json")
    if os.path.exists(cache):
        with open(cache, encoding="utf-8") as f:
            return json.load(f)
    s = max(0, start_ms - PAD_MS)
    dur = (end_ms + PAD_MS) - s
    base = os.path.join(cache_dir, tag)
    clip = base + ".clip.wav"
    subprocess.run([FFMPEG, "-y", "-v", "error", "-i", wav, "-ss", f"{s/1000:.3f}",
                    "-t", f"{dur/1000:.3f}", "-ar", "16000", "-ac", "1", clip],
                   check=True, timeout=120, stdin=subprocess.DEVNULL)
    # ضغط ذاكرة الجهاز يجعل نافذة 9ث تستغرق دقائق أحياناً ⇒ مهلة سخية + إعادة
    # بتراجع أُسّي بدل إسقاط الدفعة كلها (نفس درس transcribe_v2).
    for attempt in range(4):
        r = subprocess.run([WHISPER_CLI, "-m", MODEL_Q8, "-f", clip, "-l", "ar", "-oj", "-ojf",
                            "-ml", "1", "-sow", "-nfa", "-dtw", "tiny", "-of", base,
                            "--no-prints"],
                           capture_output=True, text=True, timeout=1800,
                           stdin=subprocess.DEVNULL)
        if r.returncode == 0 and os.path.exists(base + ".json"):
            break
        time.sleep(20 * (attempt + 1))
    else:
        raise RuntimeError(f"whisper فشل على النافذة {tag}: {r.returncode}")
    with open(base + ".json", encoding="utf-8") as f:
        data = json.load(f)
    words = []
    for seg in data.get("transcription", []):
        w = norm(seg.get("text", ""))
        ts = [t["t_dtw"] for t in seg.get("tokens", []) if t.get("t_dtw", -1) >= 0]
        if not w or not ts:
            continue
        w0, w1 = min(ts) * 10, max(ts) * 10          # t_dtw بوحدات 10م.ث
        if w0 >= dur - SAT_MS:                       # حافة النافذة: لا يُعوَّل عليها
            continue
        words.append({"w": w, "s": s + w0, "e": s + max(w1, w0 + 40)})
    for p in (clip, base + ".json"):
        if os.path.exists(p):
            os.remove(p)
    with open(cache, "w", encoding="utf-8") as f:
        json.dump(words, f, ensure_ascii=False)
    return words


def _seg_of(segments, t):
    for i, sg in enumerate(segments):
        if sg["s"] <= t <= sg["e"]:
            return i
    return None


def _fine_snap(sil, lo, hi):
    """مركز أطول فترة صمت دقيقة تتقاطع مع [lo,hi]، وإلا None."""
    best, best_len = None, 0
    for s, e in sil:
        ov = min(e, hi) - max(s, lo)
        if ov > 0 and (e - s) > best_len:
            best, best_len = (max(s, lo) + min(e, hi)) // 2, e - s
    return best


def _window(t, seg, total_ms):
    """نافذة WINDOW_MS مركزها الحد المقدَّر، محصورة في المقطع ما أمكن."""
    half = WINDOW_MS // 2
    lo, hi = t - half, t + half
    if seg is not None:
        lo, hi = max(lo, seg["s"] - PAD_MS), min(hi, seg["e"] + PAD_MS)
    lo, hi = max(0, lo), min(total_ms, hi)
    if hi - lo > WINDOW_MS:            # مقطع أطول من النافذة: أبقِ المركز
        lo, hi = t - half, t + half
    return int(lo), int(hi)


def refine_surah(d, log=print):
    """يصقل حدود entries غير المسنودة بنافذة قصيرة حول كل حد مقدَّر."""
    segments, entries, ref = d["segments"], d["entries"], d["refAyahs"]
    wav, total_ms = d["wav"], d["totalMs"]
    fine_sil = silences(wav, min_silence_ms=60, rel_threshold=0.06)
    stats = {"targets": 0, "refined": 0, "no_anchor": 0, "no_words": 0,
             "slid": 0, "edge": 0, "no_silence": 0}
    for k in range(1, len(entries)):
        e = entries[k]
        e["confBefore"] = e["conf"]
        e["refined"] = False
        if e["startMs"] is None or e.get("snapped") or entries[k - 1]["startMs"] is None:
            continue
        stats["targets"] += 1
        t = e["startMs"]
        si = _seg_of(segments, t)
        seg = segments[si] if si is not None else None
        # مرجع محلي: ذيل الآية السابقة + رأس اللاحقة (لا السورة كلها)
        prev_w = norm(ref[k - 1]).split()[-CTX_WORDS:]
        cur_w = norm(ref[k]).split()[:CTX_WORDS]
        ref_words = prev_w + cur_w
        side = [0] * len(prev_w) + [1] * len(cur_w)
        found = None
        why = "skip:no-words"
        # بحث بمرحلتين: انزلاق أعمى عند غياب المرساتين، و**مطاردة موجَّهة** عند
        # استقرار الحد على حافة النافذة (الحافة تدل على جهة الحد الحقيقي، فلا
        # داعي للتخبط: ننقل النافذة نصف طولها نحوها). اكتُشفت الحاجة إليها على
        # تلاوة قالون الحقيقية حيث تخطئ الحدود المقدَّرة بأكثر من نصف نافذة.
        queue = list(SLIDE_MS)
        chases = 0
        seen_slides = set()
        while queue:
            slide = queue.pop(0)
            if slide in seen_slides:
                continue
            seen_slides.add(slide)
            lo, hi = _window(t + slide, seg, total_ms)
            hyp = clip_words(wav, lo, hi, f"s{d['surah']:03d}_b{k:04d}_{slide}")
            if len(hyp) < 2 * MIN_ANCHOR:
                continue
            why = "skip:no-anchor"
            pairs = nw_align([h["w"] for h in hyp], ref_words)
            last_prev = first_cur = None
            n_prev = n_cur = exact = 0
            for hi_i, rj in pairs:
                exact += hyp[hi_i]["w"] == ref_words[rj]
                if side[rj] == 0:
                    n_prev += 1
                    if last_prev is None or hi_i > last_prev:
                        last_prev = hi_i
                else:
                    n_cur += 1
                    if first_cur is None:
                        first_cur = hi_i
            if not (last_prev is not None and first_cur is not None and first_cur > last_prev
                    and n_prev >= MIN_ANCHOR and n_cur >= MIN_ANCHOR):
                continue
            a, b = hyp[last_prev]["e"], hyp[first_cur]["s"]
            if b < a:
                a, b = b, a
            snapped = _fine_snap(fine_sil, a - SNAP_WINDOW_MS, b + SNAP_WINDOW_MS)
            if snapped is None:
                # ⛔ حارس «لا صمت لا حد»: منتصف الفجوة بين المرساتين تخمين، لا برهان.
                # مقيس على أربع مجموعات (الحصري ×3 سور + المنشاوي): `token-snap`
                # ‏230/231 = 99.6% ضمن ±300م.ث · و`token-mid` **0/10 = صفر**.
                # وعلى المنشاوي وحده: snap ‏19/19 = 100% · mid ‏0/8. فالمنتصف ليس
                # «أضعف قليلاً» بل **خاطئ دائماً** — ورفضه يمحو كل حالات الكسر.
                why = "skip:no-silence"
                continue
            cand = snapped
            if not (lo + EDGE_MARGIN_MS <= cand <= hi - EDGE_MARGIN_MS):
                why = "skip:window-edge"
                if chases < MAX_EDGE_CHASES:
                    chases += 1
                    direction = -1 if cand < (lo + hi) // 2 else 1
                    queue.insert(0, slide + direction * (WINDOW_MS // 2))
                continue
            found = (hyp, last_prev, first_cur, exact, len(pairs), lo, hi, slide,
                     cand, snapped)
            break
        if found is None:
            key = {"skip:window-edge": "edge", "skip:no-anchor": "no_anchor",
                   "skip:no-silence": "no_silence"}.get(why, "no_words")
            stats[key] += 1
            e["refineSrc"] = why
            continue
        hyp, last_prev, first_cur, exact, npairs, lo, hi, slide, new_t, snapped = found
        if slide:
            stats["slid"] += 1
        new_t = int(new_t)
        acc = exact / max(npairs, 1)
        e["startMs"] = new_t
        entries[k - 1]["endMs"] = new_t
        e["refined"] = True
        e["refineSrc"] = "token-snap"          # لا يبقى غيره بعد حارس «لا صمت لا حد»
        e["refineAcc"] = round(acc, 3)
        e["refineShift"] = new_t - t
        e["refineGap"] = int(b - a)          # اتساع الفجوة بين المرساتين
        cov = e["matched"] / max(e["total"], 1)
        conf = min(1.0, (0.6 * cov + 0.4 * acc) * (1.0 if acc >= 0.5 else 0.8))
        promoted = acc >= PROMOTE_MIN_ACC
        if not promoted:
            conf = min(conf, MED_CEIL)       # الزمن يتحسّن، والشارة لا تُمنح بلا برهان
        e["conf"] = round(conf, 3)
        e["promoted"] = promoted
        e["snapped"] = True
        stats["refined"] += 1
    log(f"صقل: {stats}")
    d["refineStats"] = stats
    return d
