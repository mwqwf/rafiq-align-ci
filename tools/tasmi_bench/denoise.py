# -*- coding: utf-8 -*-
"""🔇 **كتمُ الضجيج — بوّابةٌ طيفية** (خارطة الطريق M1-2، قُدِّمت بعد قياس 2026-09-07).

## لماذا صار هذا أولويةً أولى
القياسُ على المحرك الحقيقي (‏142 آية، المحاكي) قال شيئاً لم نكن نتوقّعه:

| الشرط | التتبّع | آياتٌ نظيفةٌ تماماً |
|---|---|---|
| نظيف (‏G1) | **96.94٪** | 86.6٪ |
| خافتٌ ‎−40 د.ب | 96.05٪ (‏−0.89) | 83.1٪ |
| **مروحةٌ عند SNR 10** | **91.04٪ (‏−5.90)** | **61.3٪** |
| خافت+مروحة+هاتف | 91.04٪ | 61.3٪ |

أي أن **الخفوت وحده يكاد لا يضرّ** (النموذجُ يسوّي المستوى داخلياً)، و**الضجيجُ هو الذي
يهدم**، وأن «الظرف الصعب» لا يزيد شيئاً على الضجيج وحده — فالضجيجُ هو العنق، ومعالجتُه
هي الطريق إلى الأداء الواقعي لا تسويةُ الجهارة.

## الطريقة: بوّابةٌ طيفيةٌ بأرضيةٍ مقدَّرة (‏spectral gating)
1. STFT بنافذة 32 م.ث وقفزة 8 م.ث.
2. تقديرُ **طيف الضجيج** من أهدأ [noise_pct]٪ من الإطارات (لا من صمتٍ مفترضٍ في البداية:
   المستخدمُ قد يبدأ فوراً).
3. قناعٌ ناعم: `mag > noise * over` ⇒ يمرّ، وإلا يُخفَّض إلى [floor_db] (لا يُصفَّر:
   التصفيرُ يولّد «ضجيج موسيقيّ» أسوأ من الضجيج نفسه على النموذج).
4. تنعيمُ القناع زمنياً وترددياً (متوسطٌ متحرك) — الحوافُّ الحادّة تُسمع طقطقةً.
5. ISTFT بإعادة تركيبٍ بالتراكب.

⛔ **الخطرُ المعروف**: كتمُ الضجيج يشوّه الكلامَ النظيف. لذلك القياسُ **يشمل G1**، والقاعدة:
لا يُعتمد إن أنقص G1 أكثر من 0.2 نقطة. والوصفةُ تُختار بالرقم لا بالذوق (`--sweep`).

كلُّه numpy — بلا اعتمادية جديدة، وقابلٌ للنقل إلى Kotlin بـFFT بسيطة.
"""
import argparse
import os
import sys

import numpy as np
import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(HERE, "work")
SR = 16_000
N_FFT = 512          # 32 م.ث
HOP = 128            # 8 م.ث


def stft(x, n_fft=N_FFT, hop=HOP):
    win = np.hanning(n_fft + 1)[:-1].astype(np.float64)
    pad = n_fft // 2
    xp = np.pad(x.astype(np.float64), (pad, pad + n_fft), mode="reflect")
    n_frames = 1 + (len(xp) - n_fft) // hop
    idx = np.arange(n_fft)[None, :] + hop * np.arange(n_frames)[:, None]
    frames = xp[idx] * win
    return np.fft.rfft(frames, axis=1), win, pad


def istft(spec, win, pad, length, hop=HOP):
    frames = np.fft.irfft(spec, axis=1) * win
    n_fft = frames.shape[1]
    out = np.zeros(hop * (frames.shape[0] - 1) + n_fft)
    wsum = np.zeros_like(out)
    for i in range(frames.shape[0]):
        out[i * hop:i * hop + n_fft] += frames[i]
        wsum[i * hop:i * hop + n_fft] += win ** 2
    out /= np.maximum(wsum, 1e-8)
    return out[pad:pad + length].astype(np.float32)


def smooth2d(m, t=3, f=3):
    """تنعيمٌ بمتوسطٍ متحرك على الزمن والتردد (صندوقٌ بسيط — بلا scipy)."""
    if t > 1:
        k = np.ones(t) / t
        m = np.apply_along_axis(lambda v: np.convolve(v, k, mode="same"), 0, m)
    if f > 1:
        k = np.ones(f) / f
        m = np.apply_along_axis(lambda v: np.convolve(v, k, mode="same"), 1, m)
    return m


def denoise(x, noise_pct=15.0, over=1.6, floor_db=-14.0, smooth_t=3, smooth_f=3,
            report=False):
    """يكتم الضجيج الثابت في [x] ويعيد الصوت (‏و`report=True` معه قياسُ ما فُعل)."""
    if len(x) < N_FFT * 2:
        return (x, {}) if report else x
    spec, win, pad = stft(x)
    mag = np.abs(spec)
    pwr = mag ** 2
    energy = pwr.sum(axis=1)
    # أهدأُ الإطارات = تقديرُ الضجيج (لا نفترض صمتاً في البداية)
    k = max(3, int(len(energy) * noise_pct / 100))
    quiet = np.argsort(energy)[:k]
    noise_mag = np.median(mag[quiet], axis=0)
    thr = noise_mag * over
    floor = 10 ** (floor_db / 20.0)
    mask = np.where(mag > thr, 1.0, floor)
    mask = smooth2d(mask, smooth_t, smooth_f)
    y = istft(spec * mask, win, pad, len(x))
    if report:
        return y, {"frames": int(len(energy)), "noiseFrames": int(k),
                   "maskOpen": float((mask > 0.5).mean()),
                   "noiseDbfs": float(20 * np.log10(max(noise_mag.mean(), 1e-9)))}
    return y


# ───────────────────────── بناءُ مجموعةٍ منقّاة ─────────────────────────

def build(src_dir, dst_dir, limit=0, **kw):
    os.makedirs(dst_dir, exist_ok=True)
    ids = sorted(f for f in os.listdir(src_dir) if f.endswith(".wav"))
    if limit:
        ids = ids[:limit]
    n = 0
    for f in ids:
        dst = os.path.join(dst_dir, f)
        if os.path.exists(dst):
            n += 1
            continue
        x, sr = sf.read(os.path.join(src_dir, f), dtype="float32")
        if sr != SR or len(x) == 0:
            continue
        sf.write(dst, denoise(x, **kw), SR, subtype="PCM_16")
        n += 1
        if n % 40 == 0:
            print(f"  {n}/{len(ids)}", flush=True)
    print(f"✅ {os.path.basename(dst_dir)}: {n} ملفاً", flush=True)
    return n


def selftest():
    """يُقاس بأثرٍ مستقلٍّ عن التنفيذ: SNR يرتفع على المضجَّج، والنظيفُ لا يُشوَّه."""
    rng = np.random.default_rng(1446)
    t = np.arange(int(3.0 * SR)) / SR
    clean = (0.3 * np.sin(2 * np.pi * 300 * t) * (1 + 0.5 * np.sin(2 * np.pi * 3 * t))).astype(np.float32)
    clean[: SR // 2] = 0
    clean[-SR // 2:] = 0
    sys.path.insert(0, HERE)
    from augment import mix_at_snr, pink_noise, measure_snr

    ok = True
    noisy = mix_at_snr(clean, pink_noise(len(clean), rng), 10.0)
    before = measure_snr(clean, noisy)
    y, info = denoise(noisy, report=True)
    after = measure_snr(clean, y[: len(clean)])
    good = after > before + 3
    ok &= good
    print(f"{'✅' if good else '❌'} SNR: {before:.1f} ⇒ {after:.1f} د.ب (قناعٌ مفتوح {info['maskOpen']:.2f})")

    # النظيفُ لا يُشوَّه: الارتباطُ بالأصل يبقى عالياً
    yc = denoise(clean)
    m = np.abs(clean) > 1e-4
    corr = float(np.corrcoef(clean[m], yc[: len(clean)][m])[0, 1])
    good = corr > 0.95
    ok &= good
    print(f"{'✅' if good else '❌'} النظيف: ارتباطٌ بالأصل {corr:.4f} (‏> 0.95)")

    # الطولُ محفوظ (وإلا انزاحت المحاذاة الزمنية)
    good = len(denoise(noisy)) == len(noisy)
    ok &= good
    print(f"{'✅' if good else '❌'} الطولُ محفوظ")
    print("\n" + ("✅ كاتمُ الضجيج يفعل ما يدّعي" if ok else "❌ عطبٌ في الكاتم"))
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--src", help="مجلدُ المصدر (‏work/g2/<cond> أو work/wav)")
    ap.add_argument("--dst", help="مجلدُ المخرَج")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--over", type=float, default=1.6)
    ap.add_argument("--floor-db", type=float, default=-14.0)
    ap.add_argument("--noise-pct", type=float, default=15.0)
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    if not args.src or not args.dst:
        print("⛔ يلزم --src و--dst")
        return 1
    build(args.src, args.dst, args.limit, over=args.over,
          floor_db=args.floor_db, noise_pct=args.noise_pct)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
