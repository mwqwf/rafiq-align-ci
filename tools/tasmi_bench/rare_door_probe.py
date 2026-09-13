# -*- coding: utf-8 -*-
"""📐 **بابُ النادر** — مقترَحٌ يُقاس بوجهَيه: ما يُكسَب وما يُدفَع ثمناً.

خلفيّتُه بالقياس لا بالرأي (‏D-299 ثمّ D-300): في شكل `rare` — «لم أذكر إلا كلماتٍ نادرةً من
الآية» وهو نصُّ أمر المالك 2026-09-06 — يضع التصويتُ الآيةَ الصحيحةَ **أوّلَ** المرشّحين
13/13 في الروايات الثلاث، والمحركُ يوافق المرآةَ على الترتيب كلِّه، ثمّ يردّ `locate`
«لا موضع» **13/13**. فالرافضُ `anchor_one` بعينِه: `acc = correct/n` يُقاس على **كلمات الآية
كلِّها**، وكلماتٌ نادرةٌ متفرّقةٌ من آيةٍ طويلة لا تبلغ `min_acc=0.5` أبداً.

و**خفضُ العتبة عامّاً رُدَّ بالقياس** في D-299 (‏عند 0.10: النادرُ يُعرف 5/6 والإنذارُ الكاذب
يقفز 0/5 ⇒ 2/5). فختمت: «يحتاج باباً خاصّاً بالنادر لا خفضاً عامّاً ⏳». وهذا الملفُّ يقيس ذلك
البابَ المقترَح، وعيّنةُ الإنذار الكاذب فيه ليست خمسَ جملٍ مكتوبةً باليد بل مولّدةٌ حتميّاً
بحجمٍ يُعتدُّ به.

## البابُ المقترَح (‏في `anchor_one` وحدَه، ولا يمسّ `min_acc` المشحونة)
تُقبل النافذةُ رغمَ `acc < min_acc` بشروطٍ **مجتمعة**:
  1. لا زوائد (`additions == 0`) ولا `SUBSTITUTED` ⇒ ما قاله المستخدم كلُّه من هذه الآية.
  2. المصيبُ ≥ 2 كلمات.
  3. **≥ `MIN_RARE` من المصيب كلماتٌ نادرةٌ بمعيار التصويت نفسِه** (`len(index1[w]) ≤ RARE_WORD`
     و`len(w) ≥ 4`) ⇒ شهادةُ الندرة هي التي تفتح الباب، لا مجرّدُ قلّةِ ما قيل.
الشرطُ الثالث هو الفرقُ كلُّه عن خفض العتبة: خفضُ العتبة يقبل **أيَّ** كلمتين شائعتين تصادفتا،
والبابُ لا يقبل إلا ما تشهد له الندرةُ نفسُها.

## العيّنات (‏حتميّةٌ كلُّها — لا عشوائيةَ ولا صوت)
- **موجَبة** `rare`: كلماتُ الآية النادرةُ غيرُ المتجاورة ⇒ يُنتظر موضعُها هي.
  ⚠️ وبصدق: هذه الحالاتُ **مبنيّةٌ** على «≥2 كلمةً نادرةً من آيةٍ واحدة»، وهو عينُ شرط الباب
  الثالث ⇒ **جانبُ الكسب فيه دَورٌ جزئيٌّ بالبناء** ولا يُقرأ وحدَه. المعلومةُ الحقيقيّةُ في
  جانب الثمن أدناه، وفي أنّ المحاذاةَ قد ترفض الموضعَ حتّى بعد فتح الباب.
- **سالبةٌ (أ)** `noise`: كلامٌ عربيٌّ غيرُ قرآنيّ من `locator_parity.NOISE` ⇒ يُنتظر «لا موضع».
- **سالبةٌ (ب)** `mixed` ⇒ **الخصمُ المباشر لهذا الباب**: كلمةٌ نادرةٌ واحدةٌ من كلِّ آيةٍ من
  آياتٍ متباعدة، تُخلط في نصٍّ واحد. لا موضعَ واحدٌ يجمعها، فإن ادّعى المحدّدُ لها موضعاً فهو
  إنذارٌ كاذبٌ صنعه البابُ نفسُه. وهذه — لا `noise` — هي التي تقول أيبقى الباب مأموناً أم لا.

⛔ **قياسٌ للاقتراح لا تغييرٌ في المحرك:** كلُّ ما هنا في **المرآة** (`locator.py`) بالترقيع وقتَ
التشغيل، ولا يُمَسّ ملفٌّ من ملفّات المحرك ولا افتراضٌ مشحون. الأرقامُ للمقارنة النسبيّة، والقرارُ
للمالك على عتادٍ وصوتٍ حقيقيّين.

    python tools/tasmi_bench/rare_door_probe.py --stride 250
    python tools/tasmi_bench/rare_door_probe.py --riwaya hafs --stride 120
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "tools", "alignment"))
import locator as L  # noqa: E402
import scorer  # noqa: E402
from common import load_text  # noqa: E402
from locator_parity import NOISE, RARE_WORD_REF, config_for, rare_words  # noqa: E402

RIWAYAT = ("hafs", "warsh", "qalun")
MIN_RARE = 2        # كم كلمةً نادرةً تُطلب لفتح الباب
MIXED_K = 3         # كم آيةً متباعدةً تُخلط في الحالة السالبة (ب)
FAR = 50            # أدنى تباعدٍ بين الآيات المخلوطة ⇒ لا مدًى واحدٌ يجمعها بحقّ

# كلامٌ عربيٌّ غيرُ قرآنيٍّ زائدٌ على خمسِ `locator_parity.NOISE` — وأكثرُه **دينيُّ النبرة عمداً**
# (‏دعاءٌ وذكرٌ وحديثٌ ومطلعُ خطبة) لا سوقيّ، لأنّ الإنذارَ الكاذبَ الخطِر يقع هنا لا في «صباح
# الخير»: هذا ما يقوله المستخدمُ فعلاً قبلَ التسميع وبعدَه.
# 🚨 **ودرسٌ قِيس هنا لا يُنسى:** أوّلُ صياغةٍ لهذه القائمة ظنّت نفسَها نظيفةً فأعطت «إنذارَين
# كاذبَين» في الذراع المشحونة — وكانا **صواباً**: «مِن شَرِّ مَا خَلَقَ» آيةُ الفلق 113:2 بنصِّها،
# و«رَبَّنَا تَقَبَّلْ مِنَّا إِنَّكَ أَنتَ السَّمِيعُ الْعَلِيمُ» شطرُ البقرة 2:127. فالدعاءُ
# المأثور قرآنٌ كثيراً. ولذلك لا يُوثَق بعينٍ بشريّة: `clean_noise` أدناه تُسقط آليّاً كلَّ جملةٍ
# فيها ثلاثيّةٌ قرآنيّة، وتطبع ما أسقطت. عيّنةُ الثمن الملوّثةُ تصنع فزعاً كاذباً كما تصنع طمأنينةً كاذبة.
NOISE_EXTRA = (
    "اللهم صل على سيدنا محمد وعلى آله وصحبه وسلم تسليما كثيرا",
    "سبحان الله وبحمده سبحان الله العظيم استغفر الله",
    "الحمد لله رب العالمين والصلاة والسلام على أشرف المرسلين",
    "اللهم اغفر لي ذنبي ووسع لي في داري وبارك لي في رزقي",
    "قال رسول الله صلى الله عليه وسلم إنما الأعمال بالنيات",
    "أعوذ بكلمات الله التامات من شر ما خلق",
    "اللهم إني أسألك العفو والعافية في الدنيا والآخرة",
    "لا حول ولا قوة إلا بالله العلي العظيم",
    "بسم الله توكلت على الله ولا حول ولا قوة إلا بالله",
    "ربنا تقبل منا إنك أنت السميع العليم وتب علينا",
    "سأبدأ الآن بحفظ الصفحة الجديدة إن شاء الله تعالى",
    "يا شيخ أريد أن أراجع معك الحزب الذي حفظته أمس",
    "الدرس القادم يوم الثلاثاء بعد صلاة العصر في المسجد",
    "هل يمكنك أن تعيد التسجيل من فضلك فالصوت لم يكن واضحا",
    "أنهيت اليوم مراجعة الجزء الثامن والعشرين ولله الحمد",
)


def check_mirror_copy():
    """🛡️ حارسُ النسخ: حلقةُ البحث في `rare_door_anchor` منسوخةٌ عن `locator.anchor_one`؛ فإن
    تغيّر الأصلُ ولم يُنقَل التغييرُ هنا صار القياسُ يقيس شيئاً غيرَ المرآة — وهو كذبٌ صامت.
    فيُقارَن المصدران سطراً سطراً في كلِّ تشغيل (‏التعليقاتُ وحدَها تُستثنى)."""
    def grab(path, head, tail, dedent):
        s = open(path, encoding="utf-8").read()
        i = s.index(head)
        body = s[i:s.index(tail, i)].rstrip().splitlines()
        out = []
        for ln in body:
            ln = ln[dedent:] if ln.startswith(" " * dedent) else ln
            if ln.strip().startswith("#"):
                continue
            out.append(ln)
        return out
    src = os.path.join(os.path.dirname(os.path.abspath(L.__file__)), "locator.py")
    a = grab(src, "    n = len(ref)\n", "    prefix_ok", 4)
    b = grab(os.path.abspath(__file__), "        n = len(ref)\n", "        prefix_ok", 8)
    ok = a == b
    print(("🛡️ حارسُ النسخ ✅ حلقةُ البحث مطابقةٌ لـ`locator.anchor_one` "
           f"({len(a)} سطراً)") if ok else
          "🚨 حارسُ النسخ **سقط**: حلقةُ البحث لم تعد مطابقةً لـ`locator.anchor_one` ⇒ الأرقامُ أدناه لا يُعتدُّ بها.")
    return ok


def clean_noise(loc, cfg, sentences):
    """🧹 تنقيةُ عيّنة «الكلام غير القرآنيّ»: تُسقط كلَّ جملةٍ فيها **ثلاثيّةٌ من المصحف** بفهرس
    `index3` نفسِه الذي يصوّت به المحدّد. جملةٌ فيها آيةٌ ليست سالبةً: إصابةُ المحدّد فيها صوابٌ
    يُحسب عليه خطأً — فيُفزَع من بابٍ بريء أو يُطمأنّ إلى بابٍ مذنب."""
    kept, dropped = [], []
    for s in sentences:
        hyp = [w for w in (scorer.norm(x, cfg) for x in L._WS.split(s)) if w]
        hit = next((" ".join(hyp[i:i + 3]) for i in range(len(hyp) - 2)
                    if loc.index3.get(" ".join(hyp[i:i + 3]))), None)
        (dropped if hit else kept).append((s, hit))
    for s, hit in dropped:
        print(f"  🧹 أُسقطت من العيّنة السالبة (فيها قرآن): «{s}» ⇒ «{hit}»")
    return [s for s, _ in kept]


def is_rare(word, loc, cfg):
    """معيارُ الندرة **نفسُه** الذي يصوّت به `Locator.candidates` — لا معيارٌ ثانٍ."""
    n = scorer.norm(word, cfg)
    if len(n) < 4:
        return False
    flats = loc.index1.get(n)
    return bool(flats) and len(flats) <= RARE_WORD_REF


def rare_door_anchor(loc, cfg_rare, min_rare=MIN_RARE):
    """`anchor_one` + بابُ النادر. 🪞 حلقةُ البحث منسوخةٌ عن `locator.anchor_one` كما هي لأنّ
    الأصلَ لا يُفصح عن نافذته حين يرفض؛ فما قبلَ سطر `acc < min_acc` مطابقٌ له حرفاً بحرف،
    والزيادةُ كلُّها في `door` أدناه. (‏أيُّ تعديلٍ في الأصل يُنقل إلى هنا — وإلا صار القياسُ كذباً.)"""
    orig = L.anchor_one

    def patched(ref, hyp, cursor, cfg, min_acc=0.5, slack=3, allow_partial=True):
        n = len(ref)
        if n == 0 or cursor >= len(hyp):
            return {"n": n, "correct": 0, "window": None}, cursor
        best = None
        max_start = min(len(hyp) - 1, cursor + n + slack * 2)
        for start in range(cursor, max_start + 1):
            lo = max(1, min(n - slack, len(hyp) - start))
            for ln in range(lo, min(len(hyp) - start, n + slack) + 1):
                end = start + ln
                sc = scorer.score(ref, " ".join(hyp[start:end]), cfg)
                acc = sc["correct"] / n
                adds = len(sc["additions"])
                better = (best is None or acc > best[0] or
                          (acc == best[0] and (adds < best[3] or (adds == best[3] and start < best[1][0]))))
                if better:
                    best = (acc, (start, end - 1), sc, adds)
        if best is None:
            return {"n": n, "correct": 0, "window": None}, cursor
        acc, win, sc, adds = best
        prefix_ok = all(w[1] == "CORRECT" for w in sc["words"][:sc["correct"]])
        partial_tail = (allow_partial and win[1] == len(hyp) - 1 and adds == 0 and prefix_ok
                        and sc["correct"] >= 3 and sc["correct"] == win[1] - win[0] + 1)
        # 🚪 البابُ المقترَح — وهو كلُّ الزيادة على الأصل:
        hit = [w for w in sc["words"] if w[1] == scorer.CORRECT]
        subs = any(w[1] == scorer.SUBSTITUTED for w in sc["words"])
        rare_hits = sum(1 for w in hit if is_rare(ref[w[0]], loc, cfg_rare))
        door = (adds == 0 and not subs and len(hit) >= 2 and rare_hits >= min_rare)
        if acc < min_acc and not partial_tail and not door:
            return {"n": n, "correct": 0, "window": None}, cursor
        kept = n - sum(1 for w in sc["words"] if w[1] in (scorer.MISSED, scorer.SUBSTITUTED))
        return {"n": n, "correct": kept, "window": win}, win[1] + 1

    L.anchor_one = patched
    return lambda: setattr(L, "anchor_one", orig)


def threshold_arm(th):
    """ذراعُ خفضِ العتبة عامّاً — ما رُدَّ في D-299، يُعاد هنا على عيّنةٍ أوسعَ للمقارنة."""
    orig = L.anchor_one

    def patched(ref, hyp, cursor, cfg, min_acc=0.5, slack=3, allow_partial=True, _o=orig, _t=th):
        return _o(ref, hyp, cursor, cfg, _t, slack, allow_partial)

    L.anchor_one = patched
    return lambda: setattr(L, "anchor_one", orig)


def build_sets(ayat, riwaya, stride, limit, loc, cfg):
    """الموجَبةُ والسالبتان — حتميّةٌ كلُّها، مبنيّةٌ من نصّ المصحف نفسِه."""
    picks = [f for f in range(0, len(ayat), stride) if len(ayat[f].split()) >= 3]
    if limit:
        picks = picks[:limit]
    pos, pool = [], []
    for f in picks:
        rare = rare_words(loc, ayat[f].split(), cfg)
        if len(rare) >= 2:
            pos.append((f, " ".join(rare)))
        if rare:
            pool.append((f, rare[0]))
    # سالبةٌ (ب): كلمةٌ نادرةٌ من كلِّ آيةٍ من `MIXED_K` آياتٍ متباعدةً — لا موضعَ يجمعها.
    # تُبنى بالدوران على البِركة كلِّها (لا بشريحةٍ منها) ⇒ حالةٌ لكلِّ آيةٍ في البِركة تقريباً،
    # فعيّنةُ الثمن تكبر بكِبَر العيّنة بدل أن تبقى حفنةً لا يُستدلّ بها.
    mixed = []
    if len(pool) >= MIXED_K * 2:
        step = max(1, len(pool) // MIXED_K)
        for i in range(len(pool)):
            flats = [pool[(i + k * step) % len(pool)] for k in range(MIXED_K)]
            fs = [p[0] for p in flats]
            if len(set(fs)) < MIXED_K:
                continue
            if min(abs(a - b) for a in fs for b in fs if a != b) < FAR:
                continue    # آياتٌ متجاورةٌ قد يجمعها مدًى واحدٌ بحقّ ⇒ ليست سالبةً نظيفة
            mixed.append((tuple(fs), " ".join(p[1] for p in flats)))
    noise = [(None, s) for s in clean_noise(loc, cfg, list(NOISE) + list(NOISE_EXTRA))]
    return pos, noise, mixed


def run_arm(loc, pos, noise, mixed):
    hit = wrong = none = 0
    for f, text in pos:
        r = loc.locate(text)
        if r is None:
            none += 1
        elif r["start"] == f:
            hit += 1
        else:
            wrong += 1
    fa_noise = sum(1 for _, t in noise if loc.locate(t) is not None)
    fa_mixed = sum(1 for _, t in mixed if loc.locate(t) is not None)
    return hit, wrong, none, fa_noise, fa_mixed


def probe(riwaya, stride, limit):
    ayat = load_text(riwaya)
    cfg = config_for(riwaya)
    loc = L.Locator([a.split() for a in ayat], cfg)
    pos, noise, mixed = build_sets(ayat, riwaya, stride, limit, loc, cfg)
    print(f"\n📐 بابُ النادر [{riwaya}] · موجَبة {len(pos)} · كلامٌ غيرُ قرآنيّ {len(noise)} · "
          f"نادرٌ مخلوطٌ من {MIXED_K} آياتٍ متباعدة {len(mixed)}")
    if not pos:
        print("  ⚠️ لا حالاتٍ موجَبةً في هذه العيّنة — وسّع الخطوة.")
        return
    arms = [("المشحون (min_acc=0.50)", None),
            ("خفضٌ عامّ 0.30", lambda: threshold_arm(0.30)),
            ("خفضٌ عامّ 0.10", lambda: threshold_arm(0.10)),
            (f"🚪 بابُ النادر (≥{MIN_RARE} نادرة)", lambda: rare_door_anchor(loc, cfg))]
    print(f"  {'الذراع':<26} {'يُعرف':>8} {'موضعٌ خطأ':>10} {'لا موضع':>9} "
          f"{'إنذارٌ/غيرُ قرآنيّ':>18} {'إنذارٌ/مخلوط':>14}")
    for name, make in arms:
        undo = make() if make else (lambda: None)
        try:
            hit, wrong, none, fa_n, fa_m = run_arm(loc, pos, noise, mixed)
        finally:
            undo()
        print(f"  {name:<26} {f'{hit}/{len(pos)}':>8} {f'{wrong}/{len(pos)}':>10} "
              f"{f'{none}/{len(pos)}':>9} {f'{fa_n}/{len(noise)}':>18} "
              f"{f'{fa_m}/{len(mixed)}':>14}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--riwaya", choices=RIWAYAT)
    ap.add_argument("--stride", type=int, default=250, help="آيةٌ من كلِّ n (عيّنةٌ حتميّة)")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    ok = check_mirror_copy()
    for r in ((args.riwaya,) if args.riwaya else RIWAYAT):
        probe(r, args.stride, args.limit)
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
