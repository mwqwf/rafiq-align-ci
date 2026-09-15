# -*- coding: utf-8 -*-
"""🔪🎙️ **G4i — التلاوةُ الطويلة وفيها لحنٌ مصنوعٌ معلومُ الموضع** (‏D-537).

⛔⛔ **لِمَ وُجدت — بسببٍ مقيسٍ في هذه الدورة لا بتقدير:** الطريقُ الثالثُ (تقطيعٌ + بابُ
اتّهامٍ أضيق) قِيس **كسبُه** على `g4n` فتضاعف بالتقطيع (‏8.5 ⇒ 18.0 نقطة)، **وثمنُه** — أن
يُكتَم لحنٌ حقيقيٌّ يُفرَّغ لا-كلمةً — **لا يُقاس على مادّةٍ صحيحةٍ بحال**. ومادّةُ الحقن
القائمةُ (`g3r`) **آيةٌ مفردة**، وقِيس أنّ `chunk10` **لا يقطّع 163 من 240 بنداً فيها
(68٪)** ⇒ فالذراعان تصيران على أكثرِها **نسخةً واحدةً**، و«ذراعان متطابقتان سؤالٌ لا
جواب» (D-385). ⇒ فالثمنُ يحتاج **مادّةً طويلةً محقونة**: ستَّ آياتٍ (‏نحوَ 21ث ⇒ ثلاثةُ
مقاطع) بلحنٍ واحدٍ معلومِ الموضع، **وبضجيج `g4n` نفسِه** فيُقارَن الكسبُ بالثمن على
مادّةٍ واحدةِ الشرط.

⭐ **والعمليّةُ `SUBSTITUTE` بعينها لا غيرُها** — وذلك **شرطٌ في السؤال لا تفضيل**: بابُ
D-445 **لا يمسّ `MISSED` بالبناء** (لا مسموعَ لها فلا يُقال «لم أتبيّن» عن صمت) ⇒ فمجموعةُ
`OMIT` تُخرج **صفرَ ثمنٍ بالبناء** لا بالقياس، وهي نتيجةٌ لا تُساءل عنها القاعدة.

**البناءُ نفسُه بناءُ `g4`** (`build_long.py`): آياتٌ متتاليةٌ من ملفِّ السورة بحدودها
المقيسة، وسكتاتٌ واقعيّةٌ بينها، **والبذرةُ نفسُها** ⇒ فالمجموعاتُ مقارَنةٌ لا مستقلّة.
والجراحةُ: كلمةٌ في الآية الوسطى تُستبدل **بصوت كلمةٍ أخرى** من سورةٍ أخرى بمستوًى مُعايَر —
كما يفعل `inject_riwaya_local` حرفاً.

    python tools/tasmi_bench/build_long_inject.py --selftest
    python tools/tasmi_bench/build_long_inject.py --count 20
"""
import argparse
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "tools", "alignment"))
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

WORK = os.path.join(HERE, "work")
OUT = os.path.join(WORK, "g4i")
PLAN = os.path.join(WORK, "long_inject_plan.json")
SR = 16_000
SEED = 1446                       # ⛔ بذرةُ `build_long` نفسُها — فالمجموعاتُ تُقارَن بـ`g4`
AYAHS = 6
GAPS_MS = (350, 700, 1200, 1800)  # ⛔ ومثلُها حرفاً: لا صمتٌ مثاليّ
MIN_WORD_MS = 320                 # ⛔ كلمةٌ أقصرُ من ذلك جراحتُها لا تُسمع فلا تُقاس
TARGET_AYAH = 2                   # الآيةُ الوسطى (‏صفريّاً) — لا الأولى ولا الأخيرة


def pick_target(words):
    """🎯 كلمةٌ في الآية الوسطى مدّتُها كافيةٌ — **ولا الأولى ولا الأخيرة**.

    ⛔ **ولِمَ لا الأولى ولا الأخيرة:** حاكمُ الكشف يقبل الاتّهامَ في **جيرة** الموضع
    (`|w - wordIndex| <= 1`)، فطرفُ الآية جارُه في الآية الأخرى ⇒ يلتبس موضعُ اللحن
    بحدود الآيات. والوسطُ يجعل الجارَين في الآية نفسِها.
    ترجع فهرسَ الكلمة في الآية أو `None` إن لم تصلح واحدةٌ.
    """
    best = None
    for k in range(1, max(1, len(words) - 1)):
        a, b = words[k]
        if b - a >= MIN_WORD_MS and (best is None or (b - a) > (words[best][1] - words[best][0])):
            best = k
    return best


def splice(base, a_ms, b_ms, donor, sr=SR):
    """🔪 الجراحةُ بإحداثيّات **المقطع** لا الملفّ — ومعها معايرةُ المستوى.

    ⛔ **والمعايرةُ ليست تجميلاً:** كلمةٌ مانحةٌ أعلى أو أخفضُ بكثيرٍ تصنع **إنذاراً سببُه
    الجهارةُ لا النطق** (وهو عطبٌ قِيس في عدّة الحقن من قبل، ولذلك عُيِّرت هناك أيضاً).
    """
    import numpy as np
    ia = max(0, min(int(a_ms * sr / 1000), len(base)))
    ib = max(ia, min(int(b_ms * sr / 1000), len(base)))
    if donor is None or not len(donor):
        return None
    lvl = max(float(np.abs(base).max()), 1e-6) / max(float(np.abs(donor).max()), 1e-6)
    return np.concatenate([base[:ia], (donor * lvl).astype("float32"), base[ib:]]).astype("float32")


def assemble_ref(ayah_words, ti, tw):
    """📍 **نصُّ المرجع للمجموعة وموضعُ اللحن فيه** — دالّةٌ واحدةٌ تُنادى وتُختبر.

    ⛔⛔ **وهي الموضعُ الذي يكذب صامتاً:** لو حُسب الموضعُ بفهرس الكلمة في **آيتها** بدل
    المجموعة، لأشار الدفترُ إلى كلمةٍ سليمةٍ في الآية الأولى ⇒ **فحاكمُ الكشف يقيس جيرةَ
    موضعٍ لا لحنَ فيه**، فيخرج «صفرُ كشفٍ» في الذراعَين **بلا أن يصرخ شيء** — ويُقرأ ذلك
    «القاعدةُ تكتم كلَّ شيء» وهو خطأُ حسابٍ لا حكمُ قاعدة.
    ترجع (‏قائمةَ كلمات المرجع · موضعَ الكلمة المحقونة فيها).
    """
    ref, widx = [], None
    for i, words in enumerate(ayah_words):
        if i == ti:
            widx = len(ref) + tw
        ref += list(words)
    return ref, widx


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=20, help="تسجيلاتٌ لكلّ رواية")
    ap.add_argument("--ayahs", type=int, default=AYAHS)
    a = ap.parse_args()

    import numpy as np
    import soundfile as sf
    from common import FFMPEG, load_index, load_text
    import inject_riwaya as IR
    import inject_riwaya_local as L
    from build_long import AUDIO

    index = load_index()
    start = {s["n"]: s["start"] for s in index["surahs"]}
    rng = random.Random(SEED)
    os.makedirs(OUT, exist_ok=True)
    items, cache = [], {}

    for riwaya in ("warsh", "qalun"):
        d = IR.load_timings(riwaya, WORK)
        text = load_text(riwaya)
        span, wmap = {}, {}
        for e in d["entries"]:
            if not e["evidence"].get("fullEvidence"):
                continue
            s, ay = map(int, e["ayahId"].split(":"))
            if s < 78:
                continue
            ws = [(w["startMs"], w["endMs"]) for w in e["words"]]
            span[(s, ay)] = (min(w[0] for w in ws), max(w[1] for w in ws))
            wmap[(s, ay)] = ws

        runs = [[(s, ay + k) for k in range(a.ayahs)] for (s, ay) in sorted(span)]
        runs = [r for r in runs if all(x in span for x in r)]
        rng.shuffle(runs)
        # 🎁 **والمانحُ من مجموعةٍ أخرى** فلا يكون صوتَ كلمةٍ في البند نفسِه (‏وإلّا صار
        #    «تكراراً» لا «إبدالاً»، وهما صنفان مختلفان عند الحاكم).
        donors = [r for r in runs]
        made = 0
        for gi, seq in enumerate(runs):
            if made >= a.count:
                break
            s0 = seq[0][0]
            if (riwaya, s0) not in cache:
                p = L.surah_wav(riwaya, s0, AUDIO[riwaya] + f"{s0:03d}.mp3", FFMPEG)
                cache[(riwaya, s0)] = sf.read(p, dtype="float32")[0] if p else None
            full = cache[(riwaya, s0)]
            if full is None:
                continue
            ti = min(TARGET_AYAH, len(seq) - 2)
            tw = pick_target(wmap[seq[ti]])
            if tw is None:
                continue
            # 🎁 مانحٌ: كلمةٌ طويلةٌ من مجموعةٍ أخرى في **سورةٍ أخرى** إن أمكن
            dsel = None
            for dseq in donors[gi + 1:] + donors[:gi]:
                if dseq[0][0] == s0:
                    continue
                dw = pick_target(wmap[dseq[0]])
                if dw is None:
                    continue
                if (riwaya, dseq[0][0]) not in cache:
                    p = L.surah_wav(riwaya, dseq[0][0], AUDIO[riwaya] + f"{dseq[0][0]:03d}.mp3", FFMPEG)
                    cache[(riwaya, dseq[0][0])] = sf.read(p, dtype="float32")[0] if p else None
                if cache[(riwaya, dseq[0][0])] is None:
                    continue
                w0, w1 = wmap[dseq[0]][dw]
                dsel = (L.sl(cache[(riwaya, dseq[0][0])], w0, w1),
                        text[start[dseq[0][0]] + dseq[0][1] - 1].split()[dw])
                break
            if dsel is None or not len(dsel[0]):
                continue

            parts, got = [], 0
            ayah_words = [text[start[s] + ay - 1].split() for (s, ay) in seq]
            ref, widx = assemble_ref(ayah_words, ti, tw)
            for i, (s, ay) in enumerate(seq):
                a0, b0 = span[(s, ay)]
                piece = L.sl(full, a0, b0)
                if i == ti:
                    w0, w1 = wmap[(s, ay)][tw]
                    cut = splice(piece, w0 - a0, w1 - a0, dsel[0])
                    piece = cut          # `None` ⇒ يسقط البندُ أدناه
                if piece is None:
                    break
                parts.append(piece)
                got += 1
                if i < len(seq) - 1:
                    parts.append(np.zeros(int(rng.choice(GAPS_MS) * SR / 1000), dtype="float32"))
            # ⛔⛔ **والمقطوعاتُ تُعَدّ لا تُقدَّر:** `len(parts)` يشمل السكتاتَ (‏أحدَ عشرَ
            #    لستّ آيات) ⇒ فمقايستُه بعدد الآيات **تقبل بنداً ناقصَ آيةٍ** ونصُّ مرجعِه
            #    كاملٌ — أي **كلماتٌ في الدفتر لا صوتَ لها**، وهو اتّهامٌ كاذبٌ نصنعه بأيدينا.
            if widx is None or got != len(seq):
                continue
            y = np.concatenate(parts).astype("float32")
            iid = f"inj6_{riwaya}_{s0:03d}_{seq[0][1]:03d}x{len(seq)}"
            sf.write(os.path.join(OUT, iid + ".wav"), y, SR, subtype="PCM_16")
            items.append({"id": iid, "op": "SUBSTITUTE", "riwaya": riwaya, "surah": s0,
                          "ayah": seq[ti][1], "firstAyah": seq[0][1], "ayahs": len(seq),
                          "wordIndex": widx, "refText": " ".join(ref), "wordCount": len(ref),
                          "targetWord": text[start[seq[ti][0]] + seq[ti][1] - 1].split()[tw],
                          "donorWord": dsel[1], "durationSec": round(len(y) / SR, 1)})
            made += 1
            if made % 5 == 0:
                print(f"    … {riwaya} {made}/{a.count}", flush=True)

    # ⛔ ولا يُكتب دفترٌ فارغٌ: صفرُ بنودٍ **سقوطٌ** لا «مجموعةٌ صغيرة».
    if len(items) < 8:
        raise SystemExit(f"⛔ {len(items)} بنداً فقط — لا تُقاس قاعدةٌ على هذا")
    json.dump({"set": "g4i", "op": "SUBSTITUTE", "ayahs": a.ayahs, "items": items},
              open(PLAN, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    ds = [it["durationSec"] for it in items]
    print(f"✅ {len(items)} بنداً ⇒ {OUT}\n   المدّة: وسيط {sorted(ds)[len(ds) // 2]:.1f}ث "
          f"· أقصر {min(ds):.1f} · أطول {max(ds):.1f}\n   الدفتر: {PLAN}")


def _selftest():
    """🧪 **بلا شبكةٍ ولا بيانات** — الجراحةُ واختيارُ الهدف وحسابُ الموضع.

    ⛔ وهذه الثلاثةُ هي كلُّ ما يمكن أن يكذب صامتاً: قطعٌ في غير موضعه · هدفٌ في طرف
    الآية فيلتبس بجارته · وموضعٌ يُكتب في الدفتر لا يطابق موضعَ الصوت.
    """
    import numpy as np
    fails = []

    def ok(c, m):
        if not c:
            fails.append(m)

    base = np.concatenate([np.full(SR, 0.5, dtype="float32"),      # ثانيةٌ قبل
                           np.full(SR // 2, 0.9, dtype="float32"),  # نصفٌ = الكلمةُ الهدف
                           np.full(SR, 0.4, dtype="float32")])      # ثانيةٌ بعد
    donor = np.full(SR // 4, 0.2, dtype="float32")                  # ربعُ ثانيةٍ أخفضُ
    out = splice(base, 1000, 1500, donor)
    ok(out is not None, "🔪 الجراحةُ تُرجع صوتاً")
    ok(abs(len(out) - (len(base) - SR // 2 + SR // 4)) <= 1,
       f"🔪 الطولُ = الأصلُ − الهدفُ + المانح — جاء {len(out)}")
    ok(abs(float(out[:SR].max()) - 0.5) < 1e-6, "🔪 وما قبلَ القطع لم يُمَسّ")
    ok(abs(float(out[-SR:].max()) - 0.4) < 1e-6, "🔪 وما بعدَه لم يُمَسّ")
    # ⛔ **والمعايرةُ تُرفع لا تُترك**: مانحٌ أخفضُ يجب أن يصير في مستوى المقطع
    mid = out[SR:SR + SR // 4]
    ok(abs(float(mid.max()) - 0.9) < 0.05, f"🔪 مستوى المانح مُعايَرٌ — جاء {float(mid.max()):.3f}")
    ok(splice(base, 1000, 1500, np.array([], dtype="float32")) is None,
       "⛔ ومانحٌ فارغٌ يُرجع `None` لا صوتاً منقوصاً")

    # 🎯 اختيارُ الهدف: لا الأولى ولا الأخيرة، والأطولُ يُقدَّم
    ws = [(0, 500), (500, 1000), (1000, 1900), (1900, 2100), (2100, 2600)]
    ok(pick_target(ws) == 2, f"🎯 الأطولُ في الوسط (الفهرس 2) — جاء {pick_target(ws)}")
    ok(pick_target([(0, 100), (100, 150), (150, 200)]) is None,
       "🎯 وكلماتٌ كلُّها قصيرةٌ ⇒ لا هدفَ (لا هدفٌ ضعيف)")
    ok(pick_target([(0, 900), (900, 2000)]) is None or pick_target([(0, 900), (900, 2000)]) == 1,
       "🎯 ولا يُختار الفهرسُ صفرٌ البتّة")
    ok(pick_target([(0, 5000)]) is None, "🎯 وآيةٌ بكلمةٍ واحدةٍ لا هدفَ فيها")

    # 📍 **والموضعُ يُطابَق بالكلمة نفسِها لا بحسابٍ يُراجَع بالعين**
    ayat = [["ا1", "ا2"], ["ب1", "ب2", "ب3"], ["ج1", "ج2", "ج3"], ["د1"]]
    ref, widx = assemble_ref(ayat, 2, 1)
    ok(ref[widx] == "ج2", f"📍 المرجعُ عند الموضع هو الكلمةُ المحقونةُ عينُها — جاء {ref[widx]}")
    ok(len(ref) == 9 and widx == 6, f"📍 وطولُ المرجع 9 والموضعُ 6 — جاء {len(ref)}/{widx}")
    # ⛔ والنقيضُ: لو حُسب بفهرس الآية (1) لأشار إلى «ا2» — كلمةٌ سليمةٌ في آيةٍ أخرى
    ok(ref[1] == "ا2", "📍 ونقيضُه مسمًّى: الفهرسُ داخلَ الآية يشير إلى كلمةٍ سليمة")
    ok(assemble_ref(ayat, 0, 0)[1] == 0, "📍 وأوّلُ آيةٍ أوّلُ كلمةٍ ⇒ الموضعُ صفر")
    print("🧪 ضوابطُ `build_long_inject`: %d إخفاقاً" % len(fails))
    for m in fails:
        print("  ⛔", m)
    return 1 if fails else 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(_selftest())
    main()
