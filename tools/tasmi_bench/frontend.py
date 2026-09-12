# -*- coding: utf-8 -*-
"""🔊 **الواجهة الصوتية الأمامية — النسخة الثانية** (خارطة الطريق M0-5).

هذه **مرآةُ التصميم قبل تنفيذه في Kotlin**: يُقاس هنا على G1+G2 أولاً، فإن ثبت أثره
نُقل إلى `AudioLevel.kt` مع اختبار وحدةٍ يثبت تطابق المخرجين. (القاعدة: لا يُكتب في المحرك
تغييرٌ لا رقم له.)

## عيوبُ النسخة الأولى — مقيسةٌ لا موصوفة
`AudioLevel.normalize` الحالية تسوّي **بالذروة**: `g = 0.9 / peak` بحدٍّ 30×، وتترك الملف كما
هو إن كانت الذروة ≥ 0.5. وفيها ثلاثة أعطاب بنيوية:

1. **الذروةُ لا تصف الجهارة.** نقرةٌ واحدة (طقّةُ ميكروفون · صوتُ باب) ترفع الذروة إلى 0.6
   فيُترك تسجيلٌ كلامُه عند 0.01 بلا كسبٍ إطلاقاً — وهذا بعينه بلاغُ المالك: «الصوت خافت
   ومع ذلك حُكم عليه». المقياس الصحيح جهارةُ **الكلام** لا أعلى عيّنة في الملف.
2. **حدُّ الكسب 30× يعجز عن الخافت جداً.** تسجيلٌ عند ‎−40 د.ب (ذروة ≈ 0.01) يحتاج 90× ليبلغ
   القياسي؛ الحدُّ يوقفه عند 30× فيبقى خافتاً ثلاثة أضعافٍ دون الهدف.
3. **القصُّ الصلب** (`coerceIn(-1, 1)`) يشوّه القمم حين يكبر الكسب، والتشويهُ هلوسةٌ للنموذج.

## النسخة الثانية
- **تسويةُ جهارة**: جذرٌ تربيعي على **إطارات الكلام وحدها** (بوابةٌ نسبية) إلى هدف ‎−20 د.ب.
- **سقفُ كسبٍ يقوده أرضيةُ الضجيج لا رقمٌ ثابت**: نرفع ما دام الضجيج بعد الرفع تحت سقفٍ
  معلوم، فلا نضخّم غرفةً صامتة إلى هسيس.
- **محدِّدُ ذروةٍ ناعم** (‏tanh فوق العتبة) بدل القصّ الصلب: يحفظ شكل الموجة عند القمم.
- **عتبةُ سكوتٍ من أرضية الضجيج المقيسة** لا من مئينٍ ثابت.
"""
import numpy as np

SR = 16_000
FRAME = 320                      # 20 م.ث
TARGET_DBFS = -20.0              # جهارةُ الكلام المستهدَفة
MAX_NOISE_DBFS = -38.0           # سقفُ أرضية الضجيج بعد الكسب
MAX_GAIN_DB = 45.0               # حدٌّ أعلى مطلق (‏≈178×)
MIN_DR_DB = 10.0                 # أقلُّ مدىً ديناميّ تُصدَّق عنده أرضيةُ الضجيج
LIMIT = 0.95                     # عتبةُ المحدِّد الناعم


def frame_rms(x, frame=FRAME):
    n = len(x) // frame
    if n == 0:
        return np.array([al_rms(x)])
    return np.sqrt((x[: n * frame].reshape(n, frame).astype(np.float64) ** 2).mean(axis=1))


def al_rms(x):
    return float(np.sqrt((x.astype(np.float64) ** 2).mean() + 1e-20)) if len(x) else 0.0


def speech_level(x, rel_db=25.0):
    """جهارةُ الكلام: الجذرُ التربيعي على الإطارات التي فوق (المئين 95) − [rel_db].

    ⚠️ لا يُستعمل المتوسطُ الكلي: صمتُ طرفَي الآية يخفضه فيُبالَغ في الكسب.
    ولا تُستعمل الذروةُ: نقرةٌ واحدة تُفسدها (العطب ١ أعلاه).
    """
    e = frame_rms(x)
    if len(e) == 0:
        return 0.0
    top = float(np.percentile(e, 95))
    thr = top * (10 ** (-rel_db / 20))
    sel = e[e >= thr]
    if len(sel) == 0:
        return top
    # ⚠️ **الوسيطُ لا المتوسط التربيعي**: نقرةٌ واحدة عالية (طقّةُ ميكروفون) إطارُها يبلغ
    # عشرين ضعفَ إطار الكلام، والمتوسطُ التربيعي يربّع الشواذ فيرفع «جهارة الكلام» ست
    # ديسيبلات ⇒ كسبٌ أقلَّ بستّ فيبقى التسجيل خافتاً. (قِيس: ‎−47 بالمتوسط مقابل ‎−53 حقيقةً.)
    return float(np.median(sel))


def noise_floor(x, pct=10.0):
    """أرضيةُ الضجيج: المئين [pct] من طاقة الإطارات (أهدأ ما في التسجيل)."""
    e = frame_rms(x)
    return float(np.percentile(e, pct)) if len(e) else 0.0


def soft_limit(x, ceiling=LIMIT):
    """محدِّدُ ذروةٍ ناعم: ما تحت العتبة يمرّ كما هو، وما فوقها ينضغط بـtanh.

    ⛔ لا قصَّ صلب: القصُّ يولّد توافقياتٍ حادّة يقرؤها النموذج كصوتٍ آخر.
    """
    a = np.abs(x)
    over = a > ceiling
    if not over.any():
        return x.astype(np.float32)
    y = x.copy().astype(np.float64)
    excess = (a[over] - ceiling) / max(1e-6, 1.0 - ceiling)
    y[over] = np.sign(x[over]) * (ceiling + (1.0 - ceiling) * np.tanh(excess))
    return np.clip(y, -1.0, 1.0).astype(np.float32)


def normalize_v2(x, target_dbfs=TARGET_DBFS, max_noise_dbfs=MAX_NOISE_DBFS,
                 max_gain_db=MAX_GAIN_DB, report=False):
    """تسويةُ الجهارة الجديدة. يعيد الصوت (‏و`report=True` معه قاموسُ القياس)."""
    if len(x) == 0:
        return (x, {}) if report else x
    sp = speech_level(x)
    nf = noise_floor(x)
    info = {"speechDbfs": _db(sp), "noiseDbfs": _db(nf), "snrDb": _db(sp) - _db(nf)}
    if sp <= 1e-6:
        info["gainDb"] = 0.0
        info["reason"] = "صمتٌ تام"
        return (x, info) if report else x

    want_db = target_dbfs - _db(sp)                       # ما يحتاجه الكلام
    # ⛔ لا نرفع الضجيج فوق سقفه: تسجيلٌ لا كلامَ فيه أصلاً، إن ضُخّم 45 د.ب، صار هسيسُه
    # صوتاً يهلوس عليه النموذج كلماتٍ لم تُقَل. لكنّ هذا القيد **لا يُطبَّق إلا حيث تُقاس
    # أرضيةُ ضجيجٍ حقيقية**:
    #
    # ⚠️ عطبٌ قِيس (2026-09-07): تلاوةٌ متّصلةٌ بلا سكتة (آيةٌ قصيرة) كلُّ إطاراتها كلام،
    # فالمئينُ العاشر = مستوى الكلام نفسه ⇒ «مدىً ديناميّ صفر» ⇒ ظنّ المقدّرُ الكلامَ ضجيجاً
    # فخنق الكسب 27 د.ب (‏−49 ⇒ ‎−38 بدل ‎−20). فالقيدُ مشروطٌ بأن نكون قد **رأينا صمتاً**
    # فعلاً: مدىً ديناميّ ≥ [MIN_DR_DB]. وإلا فالأرضيةُ مجهولةٌ ولا يُقيَّد بها.
    dr_db = _db(sp) - _db(nf)
    if nf > 1e-9 and dr_db >= MIN_DR_DB:
        room_db = max_noise_dbfs - _db(nf)
    else:
        room_db = max_gain_db
    info["dynamicRangeDb"] = round(dr_db, 2)
    gain_db = min(want_db, room_db, max_gain_db)
    gain_db = max(gain_db, 0.0)                            # لا نخفض: الخفضُ لا يفيد النموذج
    if gain_db <= 0.01:                                    # تسجيلٌ سليم: يُترك كما هو بلا مساس
        info.update({"gainDb": 0.0, "wantDb": round(want_db, 2),
                     "roomDb": round(room_db, 2), "afterSpeechDbfs": _db(sp)})
        return (x, info) if report else x
    y = soft_limit(x * (10 ** (gain_db / 20.0)))
    info.update({"gainDb": round(gain_db, 2), "wantDb": round(want_db, 2),
                 "roomDb": round(room_db, 2), "afterSpeechDbfs": _db(speech_level(y))})
    return (y, info) if report else y


def speech_floor_v2(x, margin_db=6.0):
    """عتبةُ السكوت من **أرضية الضجيج المقيسة** + هامش، محصورةً دون نصف مستوى الكلام.

    النسخةُ الأولى كانت «عُشر المئين 85» محصورةً في [0.004, 0.02]: رقمان مطلقان لا يعرفان
    غرفةَ المستخدم — ففي غرفةٍ مضجّة تُعدّ أنفاسُ المروحة كلاماً، وفي تسجيلٍ خافت يُعدّ
    الكلامُ سكوتاً.
    """
    nf = noise_floor(x)
    sp = speech_level(x)
    floor = nf * (10 ** (margin_db / 20.0))
    return float(min(max(floor, 1e-4), max(sp * 0.5, 1e-4)))


def _db(v):
    return round(20 * np.log10(max(float(v), 1e-9)), 2)


# ───────────────────────── فحصٌ ذاتي ─────────────────────────

def _selftest():
    rng = np.random.default_rng(1446)
    t = np.arange(int(3.0 * SR)) / SR
    speech = (0.3 * np.sin(2 * np.pi * 220 * t) * (1 + 0.5 * np.sin(2 * np.pi * 3 * t))).astype(np.float32)
    speech[: SR // 2] = 0
    speech[-SR // 2:] = 0
    ok = True

    def case(name, x, want_min_db=None, want_max_db=None):
        nonlocal ok
        y, info = normalize_v2(x, report=True)
        after = info.get("afterSpeechDbfs", -99)
        good = True
        if want_min_db is not None:
            good &= after >= want_min_db
        if want_max_db is not None:
            good &= after <= want_max_db
        ok &= good
        print(f"{'✅' if good else '❌'} {name}: كلامٌ {info['speechDbfs']:+.1f} ⇒ {after:+.1f} د.ب "
              f"(كسب {info['gainDb']:+.1f} · ضجيج {info['noiseDbfs']:+.1f})")

    # ١) خافتٌ جداً في غرفةٍ هادئة ⇒ يُرفع إلى الهدف
    case("خافت −40 د.ب (هادئ)", (speech * 0.01).astype(np.float32), want_min_db=-24)
    # ٢) الحالةُ التي أسقطت النسخة الأولى: كلامٌ خافت + نقرةٌ عالية
    quiet_click = (speech * 0.01).astype(np.float32).copy()
    quiet_click[SR] = 0.7
    case("خافت + نقرةٌ عالية", quiet_click, want_min_db=-26)
    # ٣) قياسيٌّ أصلاً (أعلى من الهدف) ⇒ **لا يُخفَض ولا يُرفع**: الخفضُ لا يفيد النموذج،
    #    ولا يجوز أن يمسّ التسجيلَ السليم تغييرٌ لا حاجة له.
    y3, i3 = normalize_v2(speech, report=True)
    good3 = i3["gainDb"] == 0.0 and np.array_equal(y3, speech)
    ok &= good3
    print(f"{'✅' if good3 else '❌'} قياسي: كلامٌ {i3['speechDbfs']:+.1f} د.ب ⇒ كسب {i3['gainDb']:+.1f} (بلا مساس)")
    # ٤) خافتٌ في غرفةٍ مضجّة ⇒ الكسبُ يقيّده الضجيج (لا يُضخَّم الهسيس)
    noisy = (speech * 0.02 + rng.standard_normal(len(speech)).astype(np.float32) * 0.004)
    y, info = normalize_v2(noisy, report=True)
    good = info["gainDb"] <= info["roomDb"] + 0.01 and info["afterSpeechDbfs"] < -10
    ok &= good
    print(f"{'✅' if good else '❌'} خافت + ضجيج: كسب {info['gainDb']:+.1f} ≤ متّسع الضجيج {info['roomDb']:+.1f}")

    # ٥ب) تلاوةٌ متّصلة بلا سكتة: لا يُخنق كسبُها بأرضيةِ ضجيجٍ لا وجود لها (عطب 2026-09-07)
    cont = (0.005 * np.sin(2 * np.pi * 220 * np.arange(2 * SR) / SR)).astype(np.float32)
    yc, ic = normalize_v2(cont, report=True)
    goodc = ic["afterSpeechDbfs"] >= -23
    ok &= goodc
    print(f"{'✅' if goodc else '❌'} متّصلٌ بلا سكتة: {ic['speechDbfs']:+.1f} ⇒ {ic['afterSpeechDbfs']:+.1f} د.ب "
          f"(مدىً ديناميّ {ic['dynamicRangeDb']:+.1f})")

    # ٥) المحدِّد الناعم: لا تجاوز، ولا قصَّ صلب
    loud = (speech * 6).astype(np.float32)
    y = soft_limit(loud)
    flat = float((np.abs(y) >= 0.9499).mean())
    good = np.abs(y).max() <= 1.0 and flat < 0.5
    ok &= good
    print(f"{'✅' if good else '❌'} محدِّد ناعم: ذروة {np.abs(y).max():.3f} · نسبةُ الالتصاق بالسقف {flat:.3f}")

    # ٦) مقارنةٌ مباشرة بالنسخة الأولى على الحالة العطبة
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from local_whisper import al_normalize
    v1 = al_normalize(quiet_click)
    v1_after = _db(speech_level(v1))
    v2_after = _db(speech_level(normalize_v2(quiet_click)))
    good = v2_after - v1_after > 15
    ok &= good
    print(f"{'✅' if good else '❌'} v1 مقابل v2 على «خافت + نقرة»: {v1_after:+.1f} ⇒ {v2_after:+.1f} د.ب")

    print("\n" + ("✅ الواجهة الأمامية v2 تفعل ما تدّعيه" if ok else "❌ عطبٌ في v2"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(_selftest())
