# -*- coding: utf-8 -*-
"""🎚️ **بناء G2 — عيّنة الظروف الواقعية** (خارطة الطريق M0-2).

المشكلة التي يحلّها: كل أرقامنا حتى اليوم (‏G1: تتبّع 97.46٪) مقيسةٌ على **تلاواتٍ نظيفة
لقرّاء متقنين**، والمالك يقول إن الأداء الفعلي ضعيف — خاصةً على الصوت الخافت. فهذا السكربت
يحوّل عيّنة G1 نفسها (`work/wav/*.wav`) إلى **ثلاثة عشر شرطاً واقعياً** بحقيقةٍ أرضية
معلومة بالبناء (النصّ لم يتغيّر، الصوت وحده هو الذي تغيّر)، فيصير عندنا رقمٌ صادق لكل ظرف
ونعرف **أين ينهار المحرك أولاً**.

    python tools/tasmi_bench/augment.py                 # كل الشروط
    python tools/tasmi_bench/augment.py --only gain-30  # شرطٌ واحد
    python tools/tasmi_bench/augment.py --selftest      # فحص المحوّلات وحدها

⚠️ **قاعدتان في القياس:**
1. **الكسب والـSNR يُقاسان على الكلام لا على الملف كلّه.** ملفُّ آيةٍ فيه صمتٌ في طرفيه،
   فلو حُسب الجذر التربيعي على الملف كلّه لخرج SNR أقلَّ من الحقيقي بعدة ديسيبلات. نحسب
   على الإطارات النشطة (فوق عتبةٍ نسبية إلى الذروة).
2. **البذرة ثابتة (1446) ومشتقّةٌ من معرّف البند**، فإعادة البناء تعطي الملفات نفسها بايتاً
   ببايت — وإلا لم تكن مقارنةُ إصدارين على «العيّنة نفسها» صحيحة.

الشروط ومعناها الواقعي:
| الشرط | ما يحاكيه |
|---|---|
| `gain-20/-30/-40` | مستخدم بعيد عن الهاتف أو يهمس (‏−40 ≈ ٪1 من المستوى) |
| `noise-fan-20/-10/-5` | مروحة/مكيّف/طريق — ضجيجٌ ورديٌّ ثابت |
| `noise-babble-10` | ثرثرةُ من حولك (خُلطت من تلاواتٍ أخرى في العيّنة) |
| `speed-0.8/1.25/1.5` | حدرٌ سريع أو ترتيلٌ بطيء (بلا تغيير الطبقة — `atempo`) |
| `phone` | ميكروفون رخيص: نطاق الهاتف 300–3400 هز + تكميم 8 بت |
| `clip` | القارئ قريبٌ جداً فيقصّ الميكروفون قمم الموجة |
| `reverb` | غرفةٌ فارغة/مسجد — صدىً صناعيّ |
| `combo-hard` | الحالة الصعبة الواقعية: خافت + مروحة + ميكروفون رخيص |
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys

import numpy as np
import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "tools", "alignment"))

WORK = os.path.join(HERE, "work")
WAV = os.path.join(WORK, "wav")
G2 = os.path.join(WORK, "g2")
SR = 16_000
SEED = 1446

CONDITIONS = [
    "gain-20", "gain-30", "gain-40",
    "noise-fan-20", "noise-fan-10", "noise-fan-5",
    "noise-babble-10",
    "speed-0.8", "speed-1.25", "speed-1.5",
    "phone", "clip", "reverb", "combo-hard",
]


# ───────────────────────── قياس ─────────────────────────

def speech_mask(x, frame=320, rel_db=35.0):
    """إطاراتُ الكلام: ما فوق (ذروةُ إطارٍ) − [rel_db]. (‏frame=20م.ث)

    ليست VAD مدرَّبة — هذه دالّة **قياس** لا معالجة: غرضها ألّا يُحسب الصمت في
    الجذر التربيعي فيكذب الكسب والـSNR.
    """
    n = len(x) // frame
    if n == 0:
        return np.ones(len(x), dtype=bool)
    f = x[: n * frame].reshape(n, frame)
    e = np.sqrt((f.astype(np.float64) ** 2).mean(axis=1) + 1e-12)
    thr = e.max() * (10 ** (-rel_db / 20))
    m = np.repeat(e >= thr, frame)
    if len(m) < len(x):
        m = np.concatenate([m, np.zeros(len(x) - len(m), dtype=bool)])
    return m if m.any() else np.ones(len(x), dtype=bool)


def speech_rms(x):
    """الجذر التربيعي على الكلام وحده."""
    m = speech_mask(x)
    return float(np.sqrt((x[m].astype(np.float64) ** 2).mean() + 1e-20))


def measure_snr(clean, noisy):
    """SNR المقيس بين نظيفٍ ومضجَّج بالطول نفسه (على إطارات كلام النظيف)."""
    m = speech_mask(clean)
    noise = noisy[: len(clean)] - clean
    ps = float((clean[m].astype(np.float64) ** 2).mean() + 1e-20)
    pn = float((noise[m].astype(np.float64) ** 2).mean() + 1e-20)
    return 10 * np.log10(ps / pn)


# ───────────────────────── مولّدات الضجيج ─────────────────────────

def pink_noise(n, rng):
    """ضجيجٌ ورديّ (‏1/f) — أقربُ طيفياً إلى المروحة والمكيّف من الأبيض."""
    white = rng.standard_normal(n)
    spec = np.fft.rfft(white)
    freqs = np.fft.rfftfreq(n, 1.0 / SR)
    scale = np.ones_like(freqs)
    scale[1:] = 1.0 / np.sqrt(freqs[1:])
    spec *= scale
    out = np.fft.irfft(spec, n)
    peak = np.abs(out).max()
    return (out / peak).astype(np.float32) if peak > 0 else out.astype(np.float32)


def babble_noise(n, rng, pool):
    """ثرثرة: أربعُ تلاواتٍ أخرى مخلوطة بإزاحاتٍ عشوائية (‏غير مفهومة مجتمعةً)."""
    acc = np.zeros(n, dtype=np.float64)
    for path in pool:
        y, _ = sf.read(path, dtype="float32")
        if len(y) == 0:
            continue
        reps = int(np.ceil((n + len(y)) / len(y)))
        y = np.tile(y, reps)
        off = int(rng.integers(0, max(1, len(y) - n)))
        acc += y[off:off + n]
    peak = np.abs(acc).max()
    return (acc / peak).astype(np.float32) if peak > 0 else acc.astype(np.float32)


def mix_at_snr(clean, noise, snr_db):
    """يخلط [noise] مع [clean] عند [snr_db] مقيساً على كلام النظيف."""
    m = speech_mask(clean)
    ps = float((clean[m].astype(np.float64) ** 2).mean() + 1e-20)
    pn = float((noise[m].astype(np.float64) ** 2).mean() + 1e-20)
    gain = np.sqrt(ps / (pn * (10 ** (snr_db / 10))))
    return (clean + noise * gain).astype(np.float32)


# ───────────────────────── محوّلات ─────────────────────────

def apply_gain(x, db):
    return (x * (10 ** (db / 20.0))).astype(np.float32)


def apply_clip(x, boost_db=12.0, ceiling=0.99):
    return np.clip(x * (10 ** (boost_db / 20.0)), -ceiling, ceiling).astype(np.float32)


def biquad(x, b, a):
    """ترشيحٌ ثنائيُّ القطب مباشر (‏Direct Form I) — بلا scipy."""
    y = np.zeros_like(x, dtype=np.float64)
    x1 = x2 = y1 = y2 = 0.0
    for i in range(len(x)):
        xn = float(x[i])
        yn = b[0] * xn + b[1] * x1 + b[2] * x2 - a[1] * y1 - a[2] * y2
        y[i] = yn
        x2, x1 = x1, xn
        y2, y1 = y1, yn
    return y


def _hp_coeffs(fc, q=0.707):
    import math
    w = 2 * math.pi * fc / SR
    al = math.sin(w) / (2 * q)
    c = math.cos(w)
    b = [(1 + c) / 2, -(1 + c), (1 + c) / 2]
    a = [1 + al, -2 * c, 1 - al]
    return [v / a[0] for v in b], [1.0, a[1] / a[0], a[2] / a[0]]


def _lp_coeffs(fc, q=0.707):
    import math
    w = 2 * math.pi * fc / SR
    al = math.sin(w) / (2 * q)
    c = math.cos(w)
    b = [(1 - c) / 2, 1 - c, (1 - c) / 2]
    a = [1 + al, -2 * c, 1 - al]
    return [v / a[0] for v in b], [1.0, a[1] / a[0], a[2] / a[0]]


def apply_phone(x):
    """نطاق الهاتف 300–3400 هز + تكميم 8 بت — ميكروفونٌ رخيص أو مكالمة."""
    y = biquad(x, *_hp_coeffs(300.0))
    y = biquad(y, *_lp_coeffs(3400.0))
    peak = np.abs(y).max()
    if peak > 0:
        y = y / peak * max(0.2, min(0.9, float(np.abs(x).max())))
    q = np.round(y * 127.0) / 127.0     # 8 بت
    return q.astype(np.float32)


def apply_reverb(x, rng, rt60=0.4, direct=0.75):
    """صدى غرفةٍ صناعيّ: استجابةٌ نبضية أُسّية التلاشي + انعكاساتٌ مبكرة."""
    n = int(rt60 * SR)
    ir = rng.standard_normal(n) * np.exp(-np.arange(n) / (rt60 * SR / 6.9))
    ir[0] = 1.0
    for d_ms, g in ((17, 0.5), (31, 0.35), (53, 0.25)):
        i = int(d_ms * SR / 1000)
        if i < n:
            ir[i] += g
    ir = (ir / np.abs(ir).max()).astype(np.float32)
    wet = np.convolve(x, ir)[: len(x)]
    peak = np.abs(wet).max()
    if peak > 0:
        wet = wet / peak * np.abs(x).max()
    return (direct * x + (1 - direct) * wet).astype(np.float32)


def apply_speed(x, rate, ffmpeg):
    """تغييرُ السرعة **بلا تغيير الطبقة** (‏atempo) — حدرٌ سريع أو ترتيلٌ بطيء.

    ⛔ لا إعادةَ عيّنةٍ بسيطة: تغييرُ الطبقة يجعل الشرط «صوتاً آخر» لا «سرعةً أخرى»،
    فيختلط سببُ الانهيار على القارئ.
    """
    import tempfile
    fd_in, p_in = tempfile.mkstemp(suffix=".wav")
    fd_out, p_out = tempfile.mkstemp(suffix=".wav")
    os.close(fd_in)
    os.close(fd_out)
    try:
        sf.write(p_in, x, SR, subtype="PCM_16")
        chain = []
        r = float(rate)
        while r > 2.0:
            chain.append("atempo=2.0")
            r /= 2.0
        while r < 0.5:
            chain.append("atempo=0.5")
            r /= 0.5
        chain.append(f"atempo={r:.6f}")
        subprocess.run(
            [ffmpeg, "-y", "-v", "error", "-i", p_in, "-filter:a", ",".join(chain),
             "-ar", str(SR), "-ac", "1", p_out],
            check=True,
        )
        y, _ = sf.read(p_out, dtype="float32")
        return y
    finally:
        for p in (p_in, p_out):
            try:
                os.remove(p)
            except OSError:
                pass


# ───────────────────────── التطبيق ─────────────────────────

def rng_for(item_id, cond):
    """بذرةٌ مشتقّة من (البند، الشرط) — إعادةُ البناء تعطي الملفّ نفسه."""
    h = hashlib.sha256(f"{SEED}:{item_id}:{cond}".encode()).digest()
    return np.random.default_rng(int.from_bytes(h[:8], "big"))


def transform(x, cond, item_id, pool, ffmpeg):
    rng = rng_for(item_id, cond)
    if cond.startswith("gain"):
        return apply_gain(x, float(cond.split("-", 1)[1]) * -1)
    if cond.startswith("noise-fan-"):
        snr = float(cond.rsplit("-", 1)[1])
        return mix_at_snr(x, pink_noise(len(x), rng), snr)
    if cond.startswith("noise-babble-"):
        snr = float(cond.rsplit("-", 1)[1])
        return mix_at_snr(x, babble_noise(len(x), rng, pool), snr)
    if cond.startswith("speed-"):
        return apply_speed(x, float(cond.split("-", 1)[1]), ffmpeg)
    if cond == "phone":
        return apply_phone(x)
    if cond == "clip":
        return apply_clip(x)
    if cond == "reverb":
        return apply_reverb(x, rng)
    if cond == "combo-hard":
        y = apply_gain(x, -30.0)
        y = mix_at_snr(y, pink_noise(len(y), rng), 10.0)
        return apply_phone(y)
    raise ValueError(f"شرطٌ غير معروف: {cond}")


def one_file(src, dst_dir, conds, ffmpeg):
    """🎯 **ملفٌّ واحد ⇒ كلُّ الشروط** — لمن أراد تجربةَ متانة حكمِه على صوتٍ ساءَ عمداً
    (طلبُ جلسة الفهرسة `github-17`، 2026-09-08: «كم يصمد ترتيبُ حكمي لو ساء الصوت؟»).

        python tools/tasmi_bench/augment.py --file path/to/ayah.wav --out-dir /tmp/deg
        python tools/tasmi_bench/augment.py --file a.wav --out-dir /tmp/deg --only noise-fan-5

    المدخلُ wav ‏16ك.هز أحاديّ (كأيّ مخرَج `ffmpeg -ar 16000 -ac 1`). والمخرَجُ ملفٌّ لكل شرطٍ باسمه،
    والبذرةُ مشتقّةٌ من اسم الملف فالإعادةُ تعطي البايتات نفسَها.
    """
    os.makedirs(dst_dir, exist_ok=True)
    x, sr = sf.read(src, dtype="float32")
    if sr != SR:
        print(f"⚠️ المعدّل {sr} لا {SR} — حوّله أولاً: ffmpeg -i {src} -ar 16000 -ac 1 out.wav")
        return 1
    stem = os.path.splitext(os.path.basename(src))[0]
    for cond in conds:
        y = transform(x, cond, stem, [src], ffmpeg)
        out = os.path.join(dst_dir, f"{stem}__{cond}.wav")
        sf.write(out, y, SR, subtype="PCM_16")
        extra = ""
        if cond.startswith("noise"):
            extra = f" · SNR المقيس {measure_snr(x, y):.1f} د.ب"
        elif cond.startswith("gain"):
            extra = f" · الكسبُ المقيس {20*np.log10(speech_rms(y)/max(speech_rms(x),1e-12)):+.1f} د.ب"
        print(f"✅ {cond:18s} ⇒ {out}{extra}")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", help="ملفٌّ واحد (wav 16ك.هز أحاديّ) بدل العيّنة كلِّها")
    ap.add_argument("--out-dir", help="مجلدُ المخرَج مع --file")
    ap.add_argument("--only", action="append", choices=CONDITIONS)
    ap.add_argument("--limit", type=int, default=0, help="عددُ البنود (للتجربة)")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    # ⏱️ **الشرطُ نفسُه على صوتٍ أطول** (‏2026-09-12 · D-333): كسبُ `decodeGuard` أكبرُه في الضجيج
    # (‏+1.45) وصفرٌ على الطويل **النظيف** ⇒ السؤالُ الفاصلُ «طويلٌ ومضجَّج»، ولا بانيَ له. فصار
    # المصدرُ والمقصدُ وسيطَين: `--src-dir work/g4 --dest-dir work/g4n --only noise-fan-5`.
    # ⛔ وبركةُ الثرثرة تبقى من `sample.json`/`wav` بلا تغيير — وإلا تغيّر الشرطُ بين تشغيلَين.
    ap.add_argument("--src-dir", help="مجلدُ المصدر (افتراضُه work/wav)")
    ap.add_argument("--dest-dir", help="مجلدُ المقصد (افتراضُه work/g2/<الشرط>؛ ومعه لا يُنشأ مجلدُ شرطٍ فرعيّ)")
    args = ap.parse_args()

    from common import FFMPEG  # noqa: E402

    if args.selftest:
        return selftest(FFMPEG)

    if args.file:
        return one_file(args.file, args.out_dir or os.path.join(WORK, "one"),
                        args.only or CONDITIONS, FFMPEG)

    src = args.src_dir or WAV
    ids = sorted(f[:-4] for f in os.listdir(src) if f.endswith(".wav"))
    if args.limit:
        ids = ids[: args.limit]
    if not ids:
        print(f"⛔ لا ملفات في {src} — شغّل fetch_audio.py أولاً")
        return 1
    conds = args.only or CONDITIONS
    # ⚠️ **بركةُ الثرثرة تُشتقّ من `sample.json` لا مما وصل من الصوت بعد**: لو اشتُقّت من
    # الموجود على القرص لتغيّر خليطُ الضجيج بين تشغيلٍ وآخر (‏112 ملفاً اليوم و202 غداً)
    # فاختلفت ملفاتُ الشرط نفسه — ومقارنةُ إصدارين «على العيّنة نفسها» تصير دعوى.
    all_ids = sorted(i["id"] for i in json.load(open(os.path.join(HERE, "sample.json"), encoding="utf-8"))["items"])
    want = all_ids[:: max(1, len(all_ids) // 4)][:4]
    pool = [os.path.join(WAV, i + ".wav") for i in want if os.path.exists(os.path.join(WAV, i + ".wav"))]
    if len(pool) < 2:
        pool = [os.path.join(WAV, i + ".wav") for i in ids[:4]]
        print(f"⚠️ بركةُ الثرثرة الأصلية ناقصة ({len(want)} مطلوب) — استُعمل بديلٌ: {[os.path.basename(p) for p in pool]}")
    manifest_pool = [os.path.basename(p)[:-4] for p in pool]

    manifest = {"seed": SEED, "sourceCount": len(ids), "babblePool": manifest_pool,
                "conditions": {}, "items": {}}
    mpath = os.path.join(G2, "manifest.json")
    if os.path.exists(mpath) and not args.force:
        manifest = json.load(open(mpath, encoding="utf-8"))
        manifest.setdefault("items", {})
        manifest.setdefault("conditions", {})
        manifest["babblePool"] = manifest_pool
        manifest["sourceCount"] = len(ids)

    for cond in conds:
        outdir = args.dest_dir or os.path.join(G2, cond)
        os.makedirs(outdir, exist_ok=True)
        done = 0
        snrs, gains = [], []
        for i, item in enumerate(ids, 1):
            dst = os.path.join(outdir, item + ".wav")
            if os.path.exists(dst) and not args.force:
                done += 1
                continue
            x, sr = sf.read(os.path.join(src, item + ".wav"), dtype="float32")
            if sr != SR or len(x) == 0:
                continue
            src_pool = [p for p in pool if os.path.basename(p)[:-4] != item] or pool
            y = transform(x, cond, item, src_pool, FFMPEG)
            sf.write(dst, y, SR, subtype="PCM_16")
            done += 1
            if len(snrs) < 12 and cond.startswith("noise"):
                snrs.append(measure_snr(x, y))
            if len(gains) < 12 and cond.startswith("gain"):
                gains.append(20 * np.log10(speech_rms(y) / max(speech_rms(x), 1e-12)))
            manifest["items"].setdefault(item, {})[cond] = True
            if i % 40 == 0:
                print(f"  {cond}: {i}/{len(ids)}", flush=True)
        info = {"files": done}
        if snrs:
            info["measuredSnrDb"] = round(float(np.mean(snrs)), 2)
        if gains:
            info["measuredGainDb"] = round(float(np.mean(gains)), 2)
        manifest["conditions"][cond] = info
        print(f"✅ {cond}: {done} ملفاً {info}", flush=True)

    os.makedirs(G2, exist_ok=True)
    json.dump(manifest, open(mpath, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\nالبيان: {mpath}")
    return 0


def selftest(ffmpeg):
    """⚖️ حارسُ المحوّلات: أن يكون ما ادّعيناه هو ما وقع فعلاً.

    كلُّ محوّلٍ يُفحص بمقياسٍ مستقلٍّ عن تنفيذه (‏الكسب بجذرٍ تربيعي، والـSNR بطاقة
    الفرق) — لأن شرطاً يدّعي «−30 د.ب» وهو −22 يجعل كلَّ عمودٍ في اللوحة كذبةً مهذّبة.
    """
    rng = np.random.default_rng(SEED)
    t = np.arange(int(3.0 * SR)) / SR
    # كلامٌ صناعيّ: نغمةٌ متذبذبة داخل نافذةٍ فيها صمتٌ في الطرفين
    x = (0.3 * np.sin(2 * np.pi * 220 * t) * (1 + 0.5 * np.sin(2 * np.pi * 3 * t))).astype(np.float32)
    x[: SR // 2] = 0
    x[-SR // 2:] = 0
    ok = True

    for db in (20, 30, 40):
        y = apply_gain(x, -db)
        got = 20 * np.log10(speech_rms(y) / speech_rms(x))
        good = abs(got + db) < 0.5
        ok &= good
        print(f"{'✅' if good else '❌'} gain-{db}: المقيس {got:+.2f} د.ب")

    for snr in (20, 10, 5):
        y = mix_at_snr(x, pink_noise(len(x), rng), snr)
        got = measure_snr(x, y)
        good = abs(got - snr) < 1.5
        ok &= good
        print(f"{'✅' if good else '❌'} noise-fan-{snr}: المقيس {got:.2f} د.ب")

    for rate in (0.8, 1.25, 1.5):
        y = apply_speed(x, rate, ffmpeg)
        ratio = len(x) / len(y)
        good = abs(ratio - rate) / rate < 0.05
        ok &= good
        print(f"{'✅' if good else '❌'} speed-{rate}: نسبةُ الطول {ratio:.3f}")

    # ⚠️ مرشّحُ النطاق يُفحص بمصدرٍ **عريض الطيف** لا بنغمةٍ واحدة: أول فحصٍ استعمل نغمة 220هز
    # (‏كلُّها تحت نطاق المرشّح) فرسب المحوّلُ الصحيح — والعطبُ كان في المقياس لا فيه.
    wide = rng.standard_normal(int(2.0 * SR)).astype(np.float32) * 0.2
    yb = apply_phone(wide)

    def band(sig, f0, f1):
        spec = np.abs(np.fft.rfft(sig))
        n = len(sig)
        return float(spec[int(f0 * n / SR): int(f1 * n / SR)].mean() + 1e-12)

    lo_att = 20 * np.log10(band(yb, 20, 200) / band(wide, 20, 200))
    hi_att = 20 * np.log10(band(yb, 5000, 7500) / band(wide, 5000, 7500))
    mid_att = 20 * np.log10(band(yb, 800, 2000) / band(wide, 800, 2000))
    good = (mid_att - lo_att) > 12 and (mid_att - hi_att) > 12
    ok &= good
    print(f"{'✅' if good else '❌'} phone: الوسط {mid_att:+.1f} · دون 200هز {lo_att:+.1f} · فوق 5ك {hi_att:+.1f} د.ب")

    y = apply_clip(x)
    good = np.abs(y).max() <= 0.995 and (np.abs(y) >= 0.98).mean() > 0.01
    ok &= good
    print(f"{'✅' if good else '❌'} clip: الذروة {np.abs(y).max():.3f}")

    y = apply_reverb(x, rng)
    tail_before = np.abs(x[-SR // 2:]).mean()
    tail_after = np.abs(y[-SR // 2:]).mean()
    good = tail_after > tail_before
    ok &= good
    print(f"{'✅' if good else '❌'} reverb: ذيلٌ {tail_before:.5f} ⇒ {tail_after:.5f}")

    print("\n" + ("✅ كل المحوّلات مطابقةٌ لادّعائها" if ok else "❌ محوّلٌ لا يفعل ما يدّعي"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
