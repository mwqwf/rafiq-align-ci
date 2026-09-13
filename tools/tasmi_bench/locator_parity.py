# -*- coding: utf-8 -*-
"""🧭 تماثلُ **محدِّد الموضع**: المحرك (`QuranLocator.kt`) والمرآة (`locator.py`) — أوّلَ مرّة.

قياسُ التماثل في اللوحة (‏D-279 ثمّ D-297) يمسّ `RecitationScorer` **وحدَه**: 156,557 حالةً
وصفرُ انحراف. أمّا `QuranLocator` — ومعه `LongTasmiAnchor` و`LongTasmiMapper` — فلم يمرّ به
قياسُ تماثلٍ قطُّ، مع أنّ `locator.py` يقول عن نفسه في سطره الثالث: «كالحاكم: هذا الملف صورةُ
المحدّد لا تقريبٌ له». وكلُّ رقمٍ في `locator_bench.py` مبنيٌّ على ذلك الادّعاء.

فهذا يولّد **حالاتٍ حتميةً** (لا عشوائيةَ فيها ولا صوت) من نصّ المصحف نفسِه، ويُجريها على
المحدّدَين، ويطابق `(startFlat, endFlat, alternatives, و«لا موضع»)` حالةً بحالة:

    single   · الآيةُ كما هي                         ⇒ يُنتظر موضعُها
    whisper  · الآيةُ بالصورة التي يكتبها whisper      ⇒ بابُ الرُّخَص داخلَ المحاذاة
    basmala  · البسملةُ قبلها (كما يبدأ كثيرون)        ⇒ بابُ `stripPreamble`
    half     · النصفُ الأوّل (آيةٌ مقطوعة)             ⇒ بابُ «الذيل الجزئي»
    pair     · آيتان متتاليتان                        ⇒ بابُ الامتداد الأمامي
    noise    · كلامٌ غيرُ قرآنيّ                        ⇒ يُنتظر «لا موضع» من الاثنين

    python tools/tasmi_bench/locator_parity.py --stride 40      # عيّنةٌ حتميّة سريعة
    python tools/tasmi_bench/locator_parity.py --riwaya hafs    # الرواية كلُّها
    python tools/tasmi_bench/locator_parity.py --control        # 🧪 الضابطُ السالب أوّلاً

🗳️ **وطبقةُ التصويت تُقارَن وحدَها أيضاً** (‏أُضيف 2026-09-12 بعد D-298): مرشّحو
   `candidates` بعد `stripPreamble` في عمودَي المخرَج الخامس والسادس. لماذا: شكلُ `rare` يردّ «لا موضع» من
   المحدّدَين معاً ⇒ مقارنةُ `locate` وحدَها **لا تفحص** بابَ `RARE_WORD` البتّة (اتّفاقٌ على الرفض
   لا شهادةُ تماثل). وبالمقارنة قبلَ المحاذاة يُرى أثرُ الكلمة المفردة ولو رفضت المحاذاةُ الموضعَ بعدُ.
⚖️ **وبعدَ D-300 يُقارَن ترتيبُ المرشّحين كلُّه** لا القاطعون وحدَهم: كسرُ التعادل صار صريحاً في
   الطرفين (‏الأصغرُ فهرساً أوّلاً) فلم يبقَ في الترتيب أثرٌ لترتيب المرور على `dict`/`HashMap`.

⚠️ يقيس **اتّفاقَ** المحدّدَين لا **صوابَهما**: ما اتّفقا على خطئه لا يظهر هنا (‏وصوابُه يقيسه
   `locator_bench.py` على تفريغاتٍ حقيقية — وهي تحتاج صوتاً ونموذجاً).
🧪 **وابدأ بـ`--control`:** يزرع في المرآة **ثلاثةَ أعطابٍ معزولة**، بابًا لكلِّ طبقةٍ من طبقات
   المحدّد (‏إسقاطُ الاستعاذة والبسملة · ندرةُ الكلمة المفردة في التصويت · الذيلُ الجزئيُّ في
   المحاذاة)، ويتأكّد أنّ المقارنة تصرخ في كلٍّ منها. سقوطُ بابٍ واحدٍ يُسقط الضابطَ كلَّه.
"""
import argparse
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "tools", "alignment"))
import locator as L  # noqa: E402
import scorer  # noqa: E402
from common import load_text  # noqa: E402

# 🗺️ D-431: صارت ستّاً (‏من قائمة النظر في D-428) — و**تماثلُ المحدِّد لم يُقَس على شعبةَ
#    والدوريِّ والسوسيِّ قطّ**. ولا شيءَ فيه يتعلّق بمُدخَلٍ محصور: الحالاتُ تُولَّد من نصّ
#    المصحف وحدَه. ⚠️ **والأداةُ ثقيلةٌ**: الجريةُ الكاملةُ لروايةٍ تتجاوز حدَّ المناوبة،
#    فتُستعمل `--stride` وتُذكر الخطوةُ مع الرقم — عيّنةٌ حتميّةٌ لا عشوائيّة.
RIWAYAT = ("hafs", "warsh", "qalun", "shuba", "douri", "sousi")
TOP = 8            # `QuranLocator.TOP` — سقفُ المرشّحين؛ دونَه لا قطعَ فلا التباسَ في الحدّ
# قيمةُ `RARE_WORD` المشحونةُ كما هي عند الاستيراد — لا تُقرأ من الصنف وقتَ الاختيار لئلّا يغيّرها
# الضابطُ السالب فيصير انتقاءُ الحالات دائرياً (‏تُعطب المرآةُ فيُعطب المولّدُ معها فيسكتان).
RARE_WORD_REF = L.Locator.RARE_WORD
WORK = os.path.join(HERE, "work")
JUDGE = os.path.join(HERE, "engine_judge", "build_and_run_locator.sh")
BASMALA = "بسم الله الرحمن الرحيم"
# كلامٌ عربيٌّ غيرُ قرآنيّ — الحكمُ المنتظَر «لا موضع» في الاثنين (‏الإنذارُ الكاذب أسوأ من الصمت).
NOISE = (
    "صباح الخير كيف حالك اليوم يا صديقي",
    "أريد أن أذهب إلى السوق لأشتري الخبز والحليب",
    "هذا التطبيق يساعدني على الحفظ كل يوم",
    "اتصل بي غدا في الصباح الباكر من فضلك",
    "ذهب الولد إلى المدرسة ثم عاد إلى البيت",
)


def config_for(riwaya):
    """إعدادُ المرآة المطابقُ لملفّ الرواية في المحرك (‏D-248) — كما في `parity_full.py`."""
    return scorer.Config(naql=(riwaya == "warsh"), sila=(riwaya in ("warsh", "qalun")))


def whisper_form(word, cfg):
    """الصورةُ الحديثةُ التي يكتبها whisper لهذه الكلمة (‏آخرُ صورةٍ مرخَّصة) — حتميّة.

    كما في `parity_full.py`: لو وُلِّد المسموعُ بـ`norm` وحدَها لم يُفحَص بابُ `variants` البتّة
    (‏الخنجريّةُ الاختيارية · صلةُ ۦ/ۥ · النقلُ وصلةُ الميم) — وهو البابُ الذي وقع فيه عطبُ D-276.
    """
    forms = [f for f in scorer._riwaya_forms(scorer.variants(word, cfg), cfg) if f]
    return forms[-1] if forms else scorer.norm(word, cfg)


def rare_words(loc, ws, cfg, want=3):
    """أندرُ كلمات الآية بفهرس المفردات (‏≤`RARE_WORD` آيات) — **غيرَ متجاورة** فلا ثلاثيّةَ لها.

    بهذا وحدَه يُفحَص بابُ التصويت بالكلمة المفردة (‏البند 2 من `QuranLocator`)، وهو نصُّ أمر
    المالك 2026-09-06: «حتى لو لم أذكر إلا كلمات نادرة». وبدونه يبقى البابُ بلا حراسة: الآيةُ
    الكاملةُ فيها ثلاثيّاتٌ تكفي وحدَها فلا يظهر أثرُ الكلمة المفردة البتّة (‏قِيس: سكت الضابط).
    """
    picked, last = [], -9
    for i, w in enumerate(ws):
        if i - last < 2:                     # لا كلمتين متجاورتين ⇒ لا ثنائيّةَ ولا ثلاثيّة
            continue
        n = scorer.norm(w, cfg)
        if len(n) < 4:                       # المحدّك يتجاهل ما دون أربعةِ أحرفٍ في هذا الباب
            continue
        flats = loc.index1.get(n)
        if flats and len(flats) <= RARE_WORD_REF:
            picked.append(w)
            last = i
            if len(picked) >= want:
                break
    return picked


def build_cases(ayat, riwaya, stride, limit, loc=None):
    """الحالاتُ الحتميّة: ستّةُ أشكالٍ لكلِّ آيةٍ مختارة + حالاتُ الكلام غير القرآنيّ."""
    cfg = config_for(riwaya)
    picks = list(range(0, len(ayat), stride))
    if limit:
        picks = picks[:limit]
    cases = []
    for f in picks:
        ws = ayat[f].split()
        if len(ws) < 3:      # آيةٌ أقصرُ من ثلاثِ كلماتٍ لا ثلاثيّةَ لها ⇒ لا معنى لترشيحها
            continue
        text = " ".join(ws)
        cases.append((f"{riwaya}:{f}:single", text))
        cases.append((f"{riwaya}:{f}:whisper", " ".join(whisper_form(w, cfg) for w in ws)))
        cases.append((f"{riwaya}:{f}:basmala", BASMALA + " " + text))
        half = ws[:max(3, len(ws) // 2)]
        cases.append((f"{riwaya}:{f}:half", " ".join(half)))
        if f + 1 < len(ayat):
            cases.append((f"{riwaya}:{f}:pair", text + " " + " ".join(ayat[f + 1].split())))
        if loc is not None:
            rare = rare_words(loc, ws, cfg)
            if len(rare) >= 2:
                cases.append((f"{riwaya}:{f}:rare", " ".join(rare)))
    for i, s in enumerate(NOISE):
        cases.append((f"{riwaya}:noise{i}", s))
    return cases


def mirror_cands(loc, text):
    """مرشّحو التصويت **كلُّهم بترتيبهم** ومعهم عددُ المتساوين على الحدّ — بخطوات `locate` نفسِها قبلَ المحاذاة.

    أُضيف 2026-09-12: قياسُ D-298 وجد أنّ شكلَ `rare` يردّ «لا موضع» من المحدّدَين معاً ⇒ بابُ
    `RARE_WORD` لا تفحصه مقارنةُ `locate` البتّة (اتّفاقٌ على الرفض لا شهادةُ تماثل). فيُقارَن
    التصويتُ **وحدَه** هنا، فيُرى أثرُ الكلمة المفردة ولو رفضت المحاذاةُ الموضعَ بعدُ.

    ⚖️ **وصار يُقارَن الترتيبُ كلُّه بعدَ D-300** بعد أن صار كسرُ التعادل صريحاً في الطرفين
    (‏الأصغرُ فهرساً أوّلاً). قبلَها كان يُقارَن **القاطعُ** وحدَه — مَن صوتُه أعلى من آخرِ
    المرشّحين — لأنّ القطعَ عند `top=8` يقع داخلَ تساوٍ في 42–45 حالةً من 133، ومَن يدخل من
    المتساوين كان يقرّره ترتيبُ المرور على `dict` هنا و`HashMap` هناك. وذلك استثناءٌ **أُغلق**:
    الترتيبُ الآن منطقٌ لا تنفيذ، فيُقاس. و`tied` يبقى عدّاً للتشخيص (‏حجمُ التعادل) لا استثناءً.
    """
    scored = mirror_cands_scored(loc, text)
    if not scored:
        return [], 0
    tied = 0
    if len(scored) >= TOP:      # لا تعادلَ على الحدّ إن لم تُقطع القائمةُ أصلاً
        floor = scored[-1][1]
        tied = sum(1 for _, v in scored if v == floor)
    return [f for f, _ in scored], tied


def mirror_cands_scored(loc, text):
    """المرشّحون `(الآية، الصوت)` بترتيب التصويت — الترتيبُ للتشخيص لا للمقارنة."""
    hyp = [w for w in (scorer.norm(x, loc.cfg) for x in L._WS.split(text)) if w]
    core = hyp[loc.strip_preamble(hyp):]
    if len(core) < 2:
        return []
    return [(f, v) for f, v, _ in loc.candidates(core)]


def run_mirror(loc, cases):
    out = {}
    for name, text in cases:
        r = loc.locate(text)
        strict, tied = mirror_cands(loc, text)
        cands = (",".join(str(x) for x in strict), str(tied))
        out[name] = ("-", "-", "") + cands if r is None else (
            str(r["start"]), str(r["end"]),
            ",".join(str(x) for x in r.get("alternatives", []))) + cands
    return out


def run_engine(ayat, riwaya, cases, tag):
    os.makedirs(WORK, exist_ok=True)
    ayat_path = os.path.join(WORK, f"locpar_ayat_{riwaya}.txt")
    with open(ayat_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(" ".join(a.split()) for a in ayat) + "\n")
    cases_path = os.path.join(WORK, f"locpar_cases_{riwaya}_{tag}.tsv")
    with open(cases_path, "w", encoding="utf-8") as fh:
        for name, text in cases:
            fh.write(f"{name}\t{text}\t{riwaya}\n")
    out_path = os.path.join(WORK, f"locpar_out_{riwaya}_{tag}.tsv")
    subprocess.run([JUDGE, ayat_path, cases_path, out_path], check=True)
    out = {}
    with open(out_path, encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            p = line.rstrip("\n").split("\t")
            p += [""] * (6 - len(p))
            out[p[0]] = (p[1], p[2], p[3], p[4], p[5])
    return out


def compare(mirror, engine, cases, show=5):
    diffs = []
    for name, text in cases:
        m, e = mirror.get(name), engine.get(name)
        if m != e:
            diffs.append((name, m, e, text))
    if diffs:
        print(f"  🚨 انحرافٌ في {len(diffs)} من {len(cases)}:")
        for name, m, e, text in diffs[:show]:
            print(f"    {name}\n      المرآة={m}  المحرك={e}\n      «{text[:90]}»")
    return diffs


def rare_report(loc, cases, mirror, engine):
    """🔍 تشخيصُ شكل `rare` (‏D-298 ⏳): أين يقف «الكلماتُ النادرةُ وحدَها» — التصويتُ أم المحاذاة؟

    أمرُ المالك المقتبَس في ترويسة `QuranLocator` هو «حتى لو لم أذكر إلا كلمات نادرة». وقياسُ D-298
    وجد أنّ الجواب «لا موضع» من المحدّدَين معاً — لكنّه لم يفصل **أيَّ طبقةٍ** ردّت. فهذا يفصلها:
    إن كانت الآيةُ الصحيحةُ في مرشّحي التصويت ثمّ سقط `locate` فالتصويتُ **يعمل** والرافضُ هو
    شرطُ `anchor_one` (‏دقّةُ ٥٠٪ من كلمات الآية)، وهو ما يُقترَح للمالك لا ما يُغيَّر هنا.
    """
    rows = [(n, t) for n, t in cases if n.endswith(":rare")]
    if not rows:
        return None
    vote = top1 = located = 0
    strict_m = strict_e = 0
    for name, text in rows:
        flat = int(name.split(":")[1])
        ordered = [f for f, _ in mirror_cands_scored(loc, text)]
        if flat in ordered:
            vote += 1
            if ordered[0] == flat:
                top1 += 1
        # المرشّحون في الجانبين (‏بعدَ D-300: القائمةُ كلُّها بترتيبها، لا القاطعون وحدَهم)
        if str(flat) in (mirror.get(name, ("",) * 5)[3] or "").split(","):
            strict_m += 1
        if str(flat) in (engine.get(name, ("",) * 5)[3] or "").split(","):
            strict_e += 1
        if mirror.get(name, ("-",))[0] != "-":
            located += 1
    n = len(rows)
    print(f"  🔍 rare ({n} حالة): التصويتُ يضع الآيةَ الصحيحةَ في المرشّحين {vote}/{n} "
          f"(‏الأوّل {top1}/{n} · المرشّحون: المرآة {strict_m}/{n} · المحرك {strict_e}/{n}) "
          f"· لكنّ `locate` يردّ موضعاً {located}/{n}")
    return n, vote, top1, strict_m, strict_e, located


def measure(riwaya, stride, limit, tag="main", show=5):
    ayat = load_text(riwaya)
    cfg = config_for(riwaya)
    ayah_words = [a.split() for a in ayat]
    loc = L.Locator(ayah_words, cfg)
    # ⚠️ الفهرسُ يُبنى قبلَ الحالات: شكلُ `rare` يُنتقى بفهرس المفردات نفسِه (‏وبقيمةِ `RARE_WORD`
    # الأصليّة لا المعطوبة: الضابطُ يعطب المحدّدَ لا اختيارَ الحالات — وإلا صار القياسُ دائرياً).
    cases = build_cases(ayat, riwaya, stride, limit, loc)
    t0 = time.time()
    mirror = run_mirror(loc, cases)
    t1 = time.time()
    engine = run_engine(ayat, riwaya, cases, tag)
    t2 = time.time()
    diffs = compare(mirror, engine, cases, show)
    rare_report(loc, cases, mirror, engine)
    nul = sum(1 for v in mirror.values() if v[0] == "-")
    # 🎲 القطعُ عند `TOP` داخلَ تساوٍ: يُعَدُّ ولا يُقارَن — انظر `mirror_cands`.
    amb = sum(1 for v in mirror.values() if v[4] not in ("0", "1"))  # `tied` صفرٌ حين لا قطع
    print(f"  {riwaya}: {len(cases)} حالة · انحراف {len(diffs)} · «لا موضع» في المرآة {nul} "
          f"· قطعٌ داخلَ تساوٍ {amb} · المرآة {t1 - t0:.0f}ث · المحرك {t2 - t1:.0f}ث")
    return len(cases), diffs


# ───────────────────────── الضابطُ السالب ─────────────────────────
# ثلاثةُ أعطابٍ **معزولة**، بابًا لكلِّ طبقة. سقوطُ بابٍ واحدٍ يُسقط الضابطَ كلَّه (‏درسُ D-297:
# ضابطٌ من بابٍ واحدٍ يشهد لبابٍ ويسكت عن سائرها).

def _break_preamble():
    """البابُ الأوّل: `strip_preamble` لا يُسقط شيئاً ⇒ البسملةُ تخطف التصويت (شكلُ basmala)."""
    orig = L.Locator.strip_preamble
    L.Locator.strip_preamble = lambda self, hyp: 0
    return lambda: setattr(L.Locator, "strip_preamble", orig)


def _break_rare_word():
    """البابُ الثاني: بابُ الكلمة المفردة في التصويت يُغلق (‏`RARE_WORD` 4 ⇐ 0).

    ⚠️ وجُرِّب قبلَه `1` فسكت سكوتاً تامّاً (‏0/44): أكثرُ «النادر» يرد في **آيةٍ واحدة**، فسقفُ
    الواحدِ يُبقيه داخلَ الباب ولا يغيّر حكماً. فالعطبُ المزروعُ يجب أن **يُغلق البابَ** لا أن
    يضيّقه — وإلّا كان الأخضرُ أخضرَ فارغاً.
    """
    orig = L.Locator.RARE_WORD
    L.Locator.RARE_WORD = 0
    return lambda: setattr(L.Locator, "RARE_WORD", orig)


def _break_partial_tail():
    """البابُ الثالث: الذيلُ الجزئيُّ في `anchor_one` يُمنع ⇒ الآيةُ المقطوعة «لم تُسمع» (شكلُ half)."""
    orig = L.anchor_one

    def patched(ref, hyp, cursor, cfg, min_acc=0.5, slack=3, allow_partial=True):
        return orig(ref, hyp, cursor, cfg, min_acc, slack, allow_partial=False)

    L.anchor_one = patched
    return lambda: setattr(L, "anchor_one", orig)


CONTROL_DOORS = (
    ("إسقاطُ الاستعاذة والبسملة (stripPreamble)", _break_preamble, "hafs"),
    ("ندرةُ الكلمة المفردة في التصويت (RARE_WORD)", _break_rare_word, "warsh"),
    ("الذيلُ الجزئيُّ في المحاذاة (partial tail)", _break_partial_tail, "qalun"),
)


def control(stride, limit):
    print("🧪 الضابطُ السالب — ثلاثةُ أبوابٍ معزولة، كلُّها يجب أن تصرخ:")
    ok = True
    for i, (name, breaker, riwaya) in enumerate(CONTROL_DOORS):
        undo = breaker()
        try:
            n, diffs = measure(riwaya, stride, limit, tag=f"ctl{i}", show=2)
        finally:
            undo()
        verdict = "✅ صرخ" if diffs else "⛔ **سكت** — الضابطُ ساقط"
        print(f"  {verdict}: {name} [{riwaya}] ⇒ {len(diffs)}/{n}")
        ok = ok and bool(diffs)
    print("🧪 الضابطُ " + ("مرّ ✅ — المقارنةُ ترى الأبوابَ الثلاثة." if ok else "**سقط** ⛔"))
    return ok


def rare_probe(riwaya, stride, limit, thresholds=(0.5, 0.4, 0.3, 0.2, 0.1)):
    """📐 حجمُ الفجوة في «حتى لو لم أذكر إلا كلمات نادرة» — وثمنُ سدِّها، بالقياس لا بالرأي.

    قِيس (‏D-299): التصويتُ يضع الآيةَ الصحيحةَ **أوّلَ** المرشّحين في حالات `rare` كلِّها، ثمّ يسقط
    الموضعُ في `anchor_one`: شرطُ `min_acc=0.5` يُقاس على **كلمات الآية كلِّها**، وكلماتٌ نادرةٌ
    متفرّقةٌ من آيةٍ طويلة لا تبلغ نصفَها أبداً. فهذا يخفض العتبةَ في **المرآة وحدَها** ويقيس
    الوجهين معاً: كم من النادر يُعرف موضعُه صواباً، وكم من **الكلام غير القرآنيّ** يُحدَّد له موضعٌ
    زوراً (‏والإنذارُ الكاذب أسوأ من «لم نتبيّن» — البند 4 في ترويسة `QuranLocator`).

    ⛔ قياسٌ للاقتراح لا تغييرٌ في المحرك: العتبةُ المشحونة لا تُمَسّ من هنا.
    """
    ayat = load_text(riwaya)
    cfg = config_for(riwaya)
    loc = L.Locator([a.split() for a in ayat], cfg)
    cases = build_cases(ayat, riwaya, stride, limit, loc)
    rare = [(n, t) for n, t in cases if n.endswith(":rare")]
    noise = [(n, t) for n, t in cases if ":noise" in n]
    print(f"📐 مسبارُ النادر [{riwaya}]: {len(rare)} حالةَ «كلماتٍ نادرةٍ وحدَها» · "
          f"{len(noise)} حالةَ كلامٍ غير قرآنيّ")
    orig = L.anchor_one
    try:
        for th in thresholds:
            def patched(ref, hyp, cursor, cfg_, min_acc=th, slack=3, allow_partial=True, _o=orig, _t=th):
                return _o(ref, hyp, cursor, cfg_, _t, slack, allow_partial)
            L.anchor_one = patched
            hit = wrong = 0
            for name, text in rare:
                r = loc.locate(text)
                if r is None:
                    continue
                if r["start"] == int(name.split(":")[1]):
                    hit += 1
                else:
                    wrong += 1
            false_alarm = sum(1 for _, text in noise if loc.locate(text) is not None)
            print(f"  min_acc={th:.2f} ⇒ النادرُ يُعرف {hit}/{len(rare)} · "
                  f"موضعٌ خاطئ {wrong}/{len(rare)} · إنذارٌ كاذبٌ على كلامٍ غير قرآنيّ "
                  f"{false_alarm}/{len(noise)}")
    finally:
        L.anchor_one = orig


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--riwaya", choices=RIWAYAT)
    ap.add_argument("--stride", type=int, default=1, help="آيةٌ من كلِّ n (عيّنةٌ حتميّة)")
    ap.add_argument("--limit", type=int, default=0, help="أقصى عددِ آياتٍ بعد الأخذ بالخطوة")
    ap.add_argument("--control", action="store_true", help="الضابطُ السالب وحدَه")
    ap.add_argument("--rare-probe", action="store_true",
                    help="📐 قياسُ فجوة «الكلماتِ النادرةِ وحدَها» وثمنِ سدِّها (المرآةُ وحدَها)")
    args = ap.parse_args()

    if args.control:
        sys.exit(0 if control(args.stride, args.limit) else 1)
    if args.rare_probe:
        for r in ((args.riwaya,) if args.riwaya else RIWAYAT):
            rare_probe(r, args.stride, args.limit)
        return

    riwayat = (args.riwaya,) if args.riwaya else RIWAYAT
    total = bad = 0
    for r in riwayat:
        n, diffs = measure(r, args.stride, args.limit)
        total += n
        bad += len(diffs)
    print(f"\n⚖️ المجموع: {total} حالة · **{bad} انحراف**"
          + ("  ✅ المرآةُ هي المحدّد." if not bad else "  🚨 المرآةُ ليست المحدّد."))
    sys.exit(0 if not bad else 1)


if __name__ == "__main__":
    main()
