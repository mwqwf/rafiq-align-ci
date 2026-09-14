#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""🎯 **تدقيقُ أهدافِ التدريب ومقياسِها بالنصّ وحدَه** — بلا صوتٍ ولا نموذج (‏D-291 · 2026-09-11).

`label_audit.py` يسأل «هل يطابق نصُّ المقطع صوتَه؟» (يحتاج صوتاً ونموذجاً وشبكة). وقبلَه سؤالان
**لا يحتاجان شيئاً**، وجوابُهما يُحسب على المصحف كلِّه:

1. **لو تعلّم النموذجُ هدفَنا تعلّماً تامّاً — أيقبله حاكمُ التسميع؟** (‏`scorer` = مرآةُ
   `RecitationScorer` المشحون) — يقيسه الذراعُ `--judge`.
2. **ولو تعلّمه تامّاً — أيعطيه مقياسُنا صفراً؟** أي: هل `train.wer` تُحاسب المتعلّمَ المصيبَ؟
   — يقيسه الذراعُ الافتراضيّ (‏أرضيّةُ WER لكلِّ هدف).

وموضعُ الشكّ معروفٌ بعينِه: **D-274/D-275** قضت أنّ الألفَ الخنجرية **نطقٌ لا ألفٌ زائدة**
(`عَلَىٰ` تُقرأ «على» ويكتبها whisper «علي»)، وأُصلحت في `scorer.norm` وفي `RecitationScorer.kt`؛
ثم كشفت **D-278** أنّ `prep.target_text` تخالفها (13,839 كلمة · 5.96٪) فأُصلح **مسارُ v3 وحدَه**
(`train.target_from_ref`). وبقي بابان بعد D-278 وهما مقصودُ هذا الملفّ (‏D-291):
`prep.target_text` نفسُها (مسارُ `--target stored` وهو الافتراض)، و**`train.norm` مرجعُ المقياس**.

    python tools/finetune/target_audit.py            # أرضيّةُ WER لكلِّ هدف (‏~1 د.)
    python tools/finetune/target_audit.py --judge    # حكمُ الحاكم كلمةً كلمة (‏~2 د.)
    python tools/finetune/target_audit.py --judge --ayah   # بالمحاذاة الكاملة (‏~15 د.)
"""
import argparse, collections, os, re, sys, types

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "tasmi_bench"))
sys.path.insert(0, os.path.join(HERE, "..", "alignment"))
sys.path.insert(0, HERE)

import scorer                                    # noqa: E402  مرآةُ الحاكم المشحون
from common import load_text                     # noqa: E402  نصُّ الرواية (6236 آية)
import prep                                      # noqa: E402  مولّدُ الأهداف المشحون

RIWAYAT = ("hafs", "warsh", "qalun")

# هدفُ v2 كما كان قبل إصلاح D-291 (‏للمقارنة قبل/بعد — لا يُستعمل في تدريب)
_LEGACY = [("ٰ", "ا"), ("ٱ", "ا"), ("ۥ", "و"), ("ۦ", "ي"), ("ے", "ي"),
           ("ۡ", "ْ"), ("ٖ", "ٍ"), ("ٗ", "ً"), ("ٞ", "ٌ"), ("ٓ", "")]


def target_legacy(t):
    for a, b in _LEGACY:
        t = t.replace(a, b)
    return re.sub(r"\s+", " ", prep.DROP.sub("", t)).strip()


def load_train():
    """`train.py` بلا torch/transformers — المقصودُ دالّاتُ النصّ (`wer` · `norm` · `target_from_ref`)
    بشيفرتها الحقيقية لا بنسخةٍ منها: فالمقيسُ هو المقياسُ نفسُه."""
    def deco(*a, **k):
        def d(f):
            return f
        return d
    for m in ("numpy", "torch", "soundfile", "transformers", "torch.utils", "torch.utils.data"):
        sys.modules.setdefault(m, types.ModuleType(m))
    t = sys.modules["torch"]
    t.no_grad = deco; t.autocast = deco; t.float16 = None; t.device = lambda *a, **k: None
    sys.modules["torch.utils.data"].Dataset = object
    sys.modules["torch.utils.data"].DataLoader = object
    sys.modules["transformers"].WhisperForConditionalGeneration = object
    sys.modules["transformers"].WhisperProcessor = object
    import train
    return train


def config_for(riwaya):
    """مرآةُ `score.config_for` (الافتراضُ = المشحون: خنجريةٌ اختيارية + صلة)."""
    return scorer.Config(naql=(riwaya == "warsh"), sila=(riwaya in ("warsh", "qalun")))


def pct(a, b):
    return 100.0 * a / max(b, 1)


# ── ١) أرضيّةُ WER: ما يحاسب المقياسُ عليه متعلّماً تامّاً لكلِّ هدف ─────────────────────
def wer_floor(train, arms):
    print("\n=== أرضيّةُ `train.wer` لمتعلّمٍ تامٍّ (صفرٌ = المقياسُ لا يحاسب المصيب) ===")
    agg = {k: [0, 0] for k in arms}
    for riw in RIWAYAT:
        out = []
        for k, f in arms.items():
            e = n = 0
            for a in load_text(riw):
                de, dn = train.wer(a, f(a))
                e += de; n += dn
            agg[k][0] += e; agg[k][1] += n
            out.append(f"{k} {pct(e, n):5.2f}٪ ({e})")
        print(f"  {riw:6s} " + " · ".join(out))
    print("  " + "الكلُّ".ljust(6) + " " + " · ".join(f"{k} {pct(e, n):5.2f}٪ ({e}/{n})"
                                                     for k, (e, n) in agg.items()))
    return agg


# ── ٢) حكمُ الحاكم: أيقبل المشحونُ ما تعلّمه المتعلّمُ التامّ؟ ─────────────────────────
def judge_words(arms, examples):
    print("\n=== حكمُ الحاكم المشحون على هدفٍ تامّ (كلمةً كلمة) ===")
    agg = collections.Counter()
    for riw in RIWAYAT:
        cfg = config_for(riw)
        c = collections.Counter(); top = collections.Counter()
        for a in load_text(riw):
            src = a.split()
            # 🕳️ **D-316:** كان الشرطُ `len(f(a).split()) != len(src)` يُسقط **الآيةَ كلَّها**، وهو ما
            # أعمى الذراعَ عن 3,582 آيةً من 18,708 (‏حفصٌ وحدَه 2,719 = 43.6٪ من آياته) ⇒ لم يُقَس
            # إلا 165,398 كلمةً من 232,288 (‏71.2٪). والسببُ **ليس** غموضاً في المحاذاة: كلُّ فرقٍ
            # في العدّة يساويه بالضبط عددُ الرموز القائمة بذاتها التي يمحوها الهدفُ (علاماتُ الوقف
            # ۖۗۘۙۚ رمزاً مستقلّاً بين الكلمات) — قِيس على الروايات الثلاث فتطابق الفرقُ مع العدد
            # في **كلِّ** آيةٍ متخطّاة. فتُسقَط تلك الرموزُ من المصدر بدل أن تُسقَط الآية.
            for k, f in arms.items():
                per = [f(w) for w in src]
                keep = [(w, t) for w, t in zip(src, per) if t]
                # 🛡️ حارسٌ لا افتراض: الهدفُ المصنوعُ على الآية كاملةً يجب أن يطابق حرفاً بحرف
                # ما صُنع كلمةً كلمة؛ وإلّا فالمحاذاةُ مشكوكةٌ ⇒ تُخطّى الآيةُ **وتُعَدّ**.
                made = f(a).split()
                if [t for _, t in keep] != made:
                    c[f"{k}: آياتٌ متخطّاة (تعذّرت المحاذاة)"] += 1
                    continue
                c[f"{k}: كلمات"] += len(keep)
                for w, t in keep:
                    V = scorer._riwaya_forms(scorer.variants(w, cfg), cfg)
                    h = scorer.norm(t, cfg)
                    if scorer._matches(V, h, cfg):
                        continue
                    kind = "غيرُ متبيَّن" if scorer._near(V, h, cfg) else "إبدالٌ واثق"
                    c[f"{k}: يردّه ({kind})"] += 1
                    if k == "القديم":
                        top[(w, t, h, V[0])] += 1
        print(f"  {riw}: " + " · ".join(f"{k} {v}" for k, v in sorted(c.items())))
        agg.update(c)
        for (w, tgt, h, v0), n in top.most_common(examples):
            print(f"      {n:4d}× {w} ⇜ {tgt} ⇒ «{h}» والحاكمُ يطلب «{v0}»")
    print("  الكلُّ: " + " · ".join(f"{k} {v}" for k, v in sorted(agg.items())))
    return agg


def judge_ayat(arms):
    """بالمحاذاة الكاملة (`scorer.score`) ⇒ نسبةُ **المقاطع** المصابة (المقطع = آية في `prep.py`)."""
    print("\n=== حكمُ الحاكم بالمحاذاة الكاملة — مقاطعُ مصابة ===")
    for k, f in arms.items():
        tw = tr = tu = ta = tay = th = 0
        for riw in RIWAYAT:
            cfg = config_for(riw)
            for a in load_text(riw):
                ref = a.split()
                if not ref:
                    continue
                res = scorer.score(ref, f(a), cfg)
                vs = [w for w in res["words"] if w is not None]
                tay += 1; bad = 0
                for (_i, verdict, *_r) in vs:
                    tw += 1
                    if verdict in (scorer.MISSED, scorer.SUBSTITUTED):
                        tr += 1; bad = 1
                    elif verdict == scorer.UNCERTAIN:
                        tu += 1; bad = 1
                ta += len(res["additions"]); th += bad
        print(f"  {k}: إبدالٌ/فقدٌ واثق {tr} ({pct(tr, tw):.2f}٪) · غيرُ متبيَّن {tu} ({pct(tu, tw):.2f}٪)"
              f" · زائدة {ta} · مقاطعُ مصابة {th}/{tay} ({pct(th, tay):.1f}٪)")


# ── 🧪 حارسُ الحَكَم — **ومَن يحرس مَن يحكم؟** (‏D-490) ───────────────────────────────
def _with_corpus(ayat, fn, *a, **k):
    """يُشغّل الذراعَ على **مصحفٍ مصنوعٍ من آيتين** — بلا بياناتٍ ولا شبكةٍ ولا دقيقةِ انتظار.

    ⚠️ ويُعاد الأصلُ في `finally` مهما وقع: مناوبةٌ تستدعي `selftest` ثمّ تقيس حقيقةً
    يجب ألّا تقيس على مصحفٍ مزوَّر.
    """
    import contextlib, io
    global load_text, RIWAYAT
    old_lt, old_riw = load_text, RIWAYAT
    load_text = lambda _riw: list(ayat)      # noqa: E731
    RIWAYAT = ("hafs",)
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            return fn(*a, **k)
    finally:
        load_text, RIWAYAT = old_lt, old_riw


def selftest():
    """🧪 **حارسُ الحَكَم** — وهو الأداةُ التي صحّحت رقمَ D-486، فحارسُها يحرس الحَكَم نفسَه.

    ⛔⛔ **والبندُ الأوّلُ فيه هو درسُ D-486 منفَّذاً لا مكتوباً:** الحكمُ على الهدف
    **بدالّة القرار المشحونة** `scorer._matches` **لا بعضويّة** الهدف في صور الحاكم —
    والفرقُ بينهما **مقيسٌ على كلمتين حقيقيّتين** لا مفترَض.
    """
    ok = True

    def say(good, line):
        nonlocal ok
        ok &= bool(good)
        print(("✅ " if good else "❌ ") + line)

    # ① الهدفُ القديم: بدائلُ D-278 تُطبَّق وعلاماتُ الوقف تُمحى والفراغُ يُجمع
    say(target_legacy("عَلَىٰ") == "عَلَىا",
        f"الهدفُ القديم يُبدّل الخنجريّةَ ألفاً (‏وهو عينُ خطأ D-274): عَلَىٰ ⇜ {target_legacy('عَلَىٰ')}")
    say(target_legacy("ٱلْحَمْدُ  لِلَّهِ") == "الْحَمْدُ لِلَّهِ",
        "ويُبدّل ألفَ الوصل ويجمع الفراغَ المكرَّر")

    # ② إعدادُ الرواية = المشحون (نقلٌ لورشٍ وحدَه · صلةٌ لورشٍ وقالون)
    cf = {r: config_for(r) for r in ("hafs", "warsh", "qalun")}
    say(not cf["hafs"].naql and not cf["hafs"].sila and cf["warsh"].naql and cf["warsh"].sila
        and not cf["qalun"].naql and cf["qalun"].sila,
        "إعدادُ الرواية مرآةُ المشحون: النقلُ لورشٍ وحدَه والصلةُ لورشٍ وقالون")

    # ③ النسبةُ لا تقسم على صفر
    say(pct(0, 0) == 0.0 and pct(1, 0) == 100.0, "والنسبةُ لا تنفجر على مقامٍ صفرٍ")

    # ④ المقيسُ هو المقياسُ نفسُه: `train.py` الحقيقيُّ لا نسخةٌ منه
    train = load_train()
    say(os.path.basename(getattr(train, "__file__", "")) == "train.py"
        and all(callable(getattr(train, n, None)) for n in ("wer", "norm", "target_from_ref")),
        f"و`train.py` يُحمَّل بشيفرته الحقيقيّة بلا torch ({os.path.basename(train.__file__)})")

    # ⑤ أرضيّةُ WER: حسابٌ مُحسوبٌ باليد على مصحفٍ من ثلاث آيات
    corpus = ["الحمد لله رب العالمين", "مالك يوم الدين", "اهدنا الصراط المستقيم"]
    words = sum(len(a.split()) for a in corpus)          # 4 + 3 + 3 = 10
    agg = _with_corpus(corpus, wer_floor, train,
                       {"ذاتُه": lambda t: t,
                        "ناقصٌ كلمةً": lambda t: " ".join(t.split()[:-1])})
    say(agg["ذاتُه"] == [0, words],
        f"⭐ الضابطُ الموجَب: النصُّ هدفَ نفسِه ⇒ أرضيّةُ WER **صفرٌ** ({agg['ذاتُه']})")
    say(agg["ناقصٌ كلمةً"] == [len(corpus), words],
        f"والضابطُ السالب: حذفُ كلمةٍ من كلّ آيةٍ ⇒ {len(corpus)} أخطاءً بالضبط ({agg['ناقصٌ كلمةً']})")

    # ⑥⭐⭐ **ميزانُ الحاكم لا العضويّة** — على كلمتين من المصحف لا على افتراض
    #     `دَاوُۥدَ` ⇒ الهدفُ «داوود» والحاكمُ يكتبها «داود»: **ليست عضواً** في صوره
    #     **ويقبلها** تسامحُ التحريف الجزئيّ ⇒ ليست عطباً. وهذا بعينه ما أخطأتُ فيه في D-486.
    soft = ["دَاوُۥدَ ٱلنَّبِيِّۦنَ"]
    cfg = config_for("hafs")
    memberships = 0
    for w in soft[0].split():
        V = scorer._riwaya_forms(scorer.variants(w, cfg), cfg)
        h = scorer.norm(prep.target_text(w), cfg)
        if h not in V:
            memberships += 1
    c = _with_corpus(soft, judge_words, {"stored": prep.target_text}, 0)
    rejects = sum(v for k, v in c.items() if "يردّه" in k)
    say(memberships == 2 and rejects == 0,
        f"⭐⭐ بالعضويّة كانتا تُعَدّان عطبَين ({memberships})، **وبميزان الحاكم صفرٌ** ({rejects}) — درسُ D-486")
    say(c.get("stored: كلمات") == 2, f"والكلمتان قِيستا ولم تُتخطّيا ({c.get('stored: كلمات')})")

    # ⑦ والردُّ الحقيقيُّ يُعَدّ ولا يُبتلع: `وُۥرِىَ` (7:20) ⇒ «ووري» والحاكمُ يطلب «وري»
    c = _with_corpus(["وُۥرِىَ"], judge_words, {"stored": prep.target_text}, 0)
    say(sum(v for k, v in c.items() if "يردّه" in k) == 1,
        "والردُّ الحقيقيُّ يُعَدّ: وُۥرِىَ ⇒ «ووري» والحاكمُ يطلب «وري»")

    # ⑧ الآيةُ التي تعذّرت محاذاتُها **تُعَدّ** ولا تُطمس (حارسُ D-316)
    c = _with_corpus(["الحمد لله"], judge_words, {"مشوَّش": lambda t: t + " زائدة"}, 0)
    say(sum(v for k, v in c.items() if "متخطّاة" in k) == 1
        and not any("كلمات" in k and v for k, v in c.items()),
        "وآيةٌ لا تتّسق فيها المحاذاةُ **تُعَدّ متخطّاةً** ولا تُحسب كلماتُها")

    # ⑨ حارسُ المصدر: القرارُ بدالّة الحاكم لا بالعضويّة — ولو أُعيدت كتابةُ الذراع
    import inspect
    src = inspect.getsource(judge_words)
    say("scorer._matches(" in src and "h in V" not in src,
        "⛔ وحارسُ المصدر: القرارُ `scorer._matches` ولا عضويّةَ `h in V` في الذراع")

    # ⑩ ذراعُ المحاذاة الكاملة يدور بلا انفجارٍ على مصحفٍ صغير
    try:
        _with_corpus(corpus, judge_ayat, {"ذاتُه": lambda t: t})
        say(True, "وذراعُ المحاذاة الكاملة يدور على مصحفٍ صغيرٍ بلا عطب")
    except Exception as ex:                     # noqa: BLE001
        say(False, f"ذراعُ المحاذاة انفجر: {ex}")

    # ⑪ والمصحفُ الحقيقيُّ عاد كما كان بعد الحقن
    say(load_text.__module__ != __name__ and RIWAYAT == ("hafs", "warsh", "qalun"),
        "والحقنُ يُرفع بعده: `load_text` الحقيقيّةُ والرواياتُ الثلاثُ عادت")

    print("\n" + ("✅ الحَكَمُ محروسٌ — ويحكم بميزان المشحون لا بالعضويّة"
                  if ok else "❌ الحَكَمُ لا يفعل ما يدّعي"))
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true", help="حارسُ الحَكَم — بلا مصحفٍ ولا شبكة")
    ap.add_argument("--judge", action="store_true", help="ذراعُ الحاكم كلمةً كلمة")
    ap.add_argument("--ayah", action="store_true", help="ذراعُ الحاكم بالمحاذاة الكاملة (بطيء)")
    ap.add_argument("--examples", type=int, default=6)
    a = ap.parse_args()
    if a.selftest:
        return selftest()

    train = load_train()
    arms = {"v3(norm)": train.target_from_ref, "stored": prep.target_text, "القديم": target_legacy}

    # ✅ ضابطٌ موجَب: نصُّ المصحف نفسُه هدفاً ⇒ أرضيّةُ WER **صفرٌ** بعد إصلاح `train.norm`
    #    (وإلا فالمقياسُ يخالف مرجعَه). وضابطٌ سالب: هدفُ «القديم» يجب أن يعيد رقمَ D-278 (5.96٪).
    wer_floor(train, {"المصحفُ نفسُه (ضابطٌ موجَب)": lambda t: t, **arms})

    if a.judge:
        judge_words(arms, a.examples)
    if a.ayah:
        judge_ayat(arms)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
