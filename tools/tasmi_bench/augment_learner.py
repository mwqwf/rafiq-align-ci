# -*- coding: utf-8 -*-
"""🧑‍🎓 **G2b — سلوكُ المتعلّم لا صوتُ القارئ** (إضافةٌ إلى M0-2 بعد قياسِ 2026-09-07).

## لماذا وُجد
أولُ قياسٍ على G2 أعطى نتيجةً مخالفةً للتوقّع: **الخفوتُ وحده يكلّف 0.89 نقطة فقط**
(‏‎−40 د.ب: 96.05٪ مقابل 96.94٪ نظيفاً). أي أن «الصوت الخافت» ليس وحده سببَ ضعف الأداء
الذي يشكوه المالك. وعيّنتُنا كلُّها **قرّاءٌ متقنون يقرؤون بلا توقّف**، بينما المستخدم الحقيقي:

- **يكرّر الكلمة** حين يشكّ فيها، ويعيد صدرَ الآية من أوّلها؛
- **يسكت طويلاً** في وسط الآية يستذكر؛
- **يبدأ بدايةً خاطئة** ثم يصحّح لنفسه؛
- **يستعيذ ويبسمل** قبل التلاوة، ويتنحنح؛
- **يقرأ بطيئاً متعثّراً** لا بإيقاع القارئ.

وكلُّ واحدةٍ من هذه **ليست خطأً في الحفظ**، فإن حكم عليها المحرك خطأً كان ظلماً — وهو
أخطرُ ما يفقد الطالبَ ثقتَه. وهذه العيّنة تقيس ذلك بحقيقةٍ أرضيةٍ معلومةٍ بالبناء
(النصُّ المرجعيُّ **لم يتغيّر**؛ والمطلوب أن تبقى الدقّةُ كما هي).

    python tools/tasmi_bench/augment_learner.py --selftest
    python tools/tasmi_bench/augment_learner.py

الشروط: `learner-repeat` · `learner-pause` · `learner-restart` · `learner-throat` ·
`learner-basmala` · `learner-combo`.
"""
import argparse
import hashlib
import json
import os
import sys

import numpy as np
import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "tools", "alignment"))

WORK = os.path.join(HERE, "work")
WAV = os.path.join(WORK, "wav")
G2 = os.path.join(WORK, "g2")
SR = 16_000
SEED = 1446

CONDITIONS = [
    "learner-repeat", "learner-pause", "learner-restart",
    "learner-throat", "learner-basmala", "learner-combo",
]


def rng_for(item_id, cond):
    h = hashlib.sha256(f"{SEED}:{item_id}:{cond}".encode()).digest()
    return np.random.default_rng(int.from_bytes(h[:8], "big"))


def word_bounds(x, frame=320, min_gap_frames=4):
    """حدودُ الكلمات تقديراً من الطاقة — لا من فهرس التوقيت.

    ⚠️ **تقديرٌ لا حقيقةٌ أرضية**: غرضُه أن يقع القصُّ عند فجوةٍ بين كلمتين لا وسطَ كلمة،
    وليس أن يُنسب فونيمٌ إلى موضع. والحقيقةُ الأرضيةُ لهذه العيّنة **النصُّ**، وهو لا يتغيّر.
    """
    n = len(x) // frame
    if n == 0:
        return [(0, len(x))]
    e = np.sqrt((x[: n * frame].reshape(n, frame).astype(np.float64) ** 2).mean(axis=1))
    thr = max(np.percentile(e, 90) * 0.12, 1e-5)
    voiced = e > thr
    out, start, gap = [], -1, 0
    for i in range(n):
        if voiced[i]:
            if start < 0:
                start = i
            gap = 0
        else:
            gap += 1
            if start >= 0 and gap >= min_gap_frames:
                out.append((start * frame, (i - gap + 1) * frame))
                start = -1
    if start >= 0:
        out.append((start * frame, len(x)))
    return [(a, b) for a, b in out if b - a >= frame * 5] or [(0, len(x))]


def silence(ms, rng, level=2e-4):
    """صمتٌ واقعيّ: أرضيةُ ضجيجٍ خفيفةٌ لا صفرٌ رقميّ (الصفرُ لا يقع في تسجيلٍ حقيقي)."""
    n = int(ms * SR / 1000)
    return (rng.standard_normal(n) * level).astype(np.float32)


def throat_clear(rng, ms=420):
    """تنحنحٌ صناعيّ: ضجيجٌ منخفضُ التردّد بغلافٍ صاعدٍ هابط."""
    n = int(ms * SR / 1000)
    noise = rng.standard_normal(n)
    k = 240
    kernel = np.ones(k) / k
    low = np.convolve(noise, kernel, mode="same")
    env = np.sin(np.linspace(0, np.pi, n)) ** 2
    y = low * env
    peak = np.abs(y).max()
    return (y / peak * 0.18).astype(np.float32) if peak > 0 else y.astype(np.float32)


def apply_repeat(x, rng):
    """يكرّر كلمةً من الوسط (المتعلّم يشكّ فيعيدها) — مع سكتةٍ قصيرة بينهما."""
    w = word_bounds(x)
    if len(w) < 2:
        return x
    i = int(rng.integers(max(1, len(w) // 4), max(2, len(w) - 1)))
    a, b = w[i]
    return np.concatenate([x[:b], silence(260, rng), x[a:b], x[b:]]).astype(np.float32)


def apply_pause(x, rng, ms=1800):
    """سكتةُ استذكارٍ طويلة في وسط الآية — الحدُّ الذي يقطع عنده المحرك مقطعاً."""
    w = word_bounds(x)
    cut = w[len(w) // 2][1] if len(w) > 1 else len(x) // 2
    return np.concatenate([x[:cut], silence(ms, rng), x[cut:]]).astype(np.float32)


def apply_restart(x, rng):
    """بدايةٌ خاطئة: يقرأ أوّلَ كلمتين ثم يسكت ثم يبدأ الآيةَ من أوّلها."""
    w = word_bounds(x)
    end = w[min(1, len(w) - 1)][1]
    return np.concatenate([x[:end], silence(500, rng), x]).astype(np.float32)


def apply_throat(x, rng):
    """تنحنحٌ قبل التلاوة وآخرُ في وسطها."""
    w = word_bounds(x)
    mid = w[len(w) // 2][0] if len(w) > 1 else len(x) // 2
    return np.concatenate([
        throat_clear(rng), silence(220, rng), x[:mid],
        throat_clear(rng, 300), x[mid:],
    ]).astype(np.float32)


def apply_basmala(x, rng, pool):
    """استعاذةٌ/بسملةٌ قبل الآية — كلامٌ **ليس من المدى المطلوب** (يجب ألّا يُحسب خطأً).

    تُؤخذ من بدايةِ تلاوةٍ أخرى في العيّنة (كلامٌ عربيٌّ حقيقيّ بصوتٍ حقيقي)، فهي أصدقُ
    من نغمةٍ صناعية.
    """
    if not pool:
        return x
    src = pool[int(rng.integers(0, len(pool)))]
    y, _ = sf.read(src, dtype="float32")
    take = y[: min(len(y), int(2.2 * SR))]
    if len(take) < SR // 2:
        return x
    lvl = max(np.abs(x).max(), 1e-6) / max(np.abs(take).max(), 1e-6)
    return np.concatenate([(take * lvl).astype(np.float32), silence(400, rng), x]).astype(np.float32)


def transform(x, cond, item_id, pool):
    rng = rng_for(item_id, cond)
    if cond == "learner-repeat":
        return apply_repeat(x, rng)
    if cond == "learner-pause":
        return apply_pause(x, rng)
    if cond == "learner-restart":
        return apply_restart(x, rng)
    if cond == "learner-throat":
        return apply_throat(x, rng)
    if cond == "learner-basmala":
        return apply_basmala(x, rng, pool)
    if cond == "learner-combo":
        y = apply_basmala(x, rng, pool)
        y = apply_restart(y, rng)
        y = apply_pause(y, rng, ms=1500)
        return y
    raise ValueError(cond)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", action="append", choices=CONDITIONS)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        return selftest()

    ids = sorted(f[:-4] for f in os.listdir(WAV) if f.endswith(".wav"))
    if args.limit:
        ids = ids[: args.limit]
    all_ids = sorted(i["id"] for i in json.load(
        open(os.path.join(HERE, "sample.json"), encoding="utf-8"))["items"])
    pool = [os.path.join(WAV, i + ".wav") for i in all_ids[:: max(1, len(all_ids) // 4)][:4]
            if os.path.exists(os.path.join(WAV, i + ".wav"))]

    for cond in (args.only or CONDITIONS):
        outdir = os.path.join(G2, cond)
        os.makedirs(outdir, exist_ok=True)
        n = 0
        grew = []
        for item in ids:
            dst = os.path.join(outdir, item + ".wav")
            if os.path.exists(dst) and not args.force:
                n += 1
                continue
            x, sr = sf.read(os.path.join(WAV, item + ".wav"), dtype="float32")
            if sr != SR or len(x) == 0:
                continue
            src_pool = [p for p in pool if os.path.basename(p)[:-4] != item] or pool
            y = transform(x, cond, item, src_pool)
            sf.write(dst, y, SR, subtype="PCM_16")
            grew.append(len(y) / max(len(x), 1))
            n += 1
        extra = f" · الطولُ ×{np.mean(grew):.2f}" if grew else ""
        print(f"✅ {cond}: {n} ملفاً{extra}", flush=True)
    return 0


def selftest():
    """كلُّ محوّلٍ يُفحص بأثرٍ يمكن قياسه: طولٌ زاد، وصمتٌ ظهر، وكلامٌ تكرّر."""
    rng = np.random.default_rng(SEED)
    t = np.arange(int(4.0 * SR)) / SR
    x = (0.3 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)
    for a, b in ((0.8, 1.0), (1.8, 2.05), (2.9, 3.1)):      # فجواتٌ بين «كلمات»
        x[int(a * SR):int(b * SR)] = 0
    ok = True
    w = word_bounds(x)
    good = len(w) == 4
    ok &= good
    print(f"{'✅' if good else '❌'} حدودُ الكلمات: {len(w)} (المتوقَّع 4)")

    for cond, min_growth in (("learner-repeat", 1.05), ("learner-pause", 1.3),
                             ("learner-restart", 1.15), ("learner-throat", 1.05)):
        y = transform(x, cond, "selftest", [])
        g = len(y) / len(x)
        good = g >= min_growth
        ok &= good
        print(f"{'✅' if good else '❌'} {cond}: الطولُ ×{g:.2f} (‏≥ {min_growth})")

    y = transform(x, "learner-pause", "selftest", [])
    e = np.sqrt((y[: (len(y) // 320) * 320].reshape(-1, 320) ** 2).mean(axis=1))
    longest = 0
    run = 0
    for v in e:
        run = run + 1 if v < 1e-3 else 0
        longest = max(longest, run)
    good = longest * 20 >= 1500
    ok &= good
    print(f"{'✅' if good else '❌'} learner-pause: أطولُ سكتة {longest*20} م.ث (‏≥ 1500)")

    print("\n" + ("✅ سلوكُ المتعلّم يُبنى كما يُوصف" if ok else "❌ عطبٌ في محوّلات المتعلّم"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
