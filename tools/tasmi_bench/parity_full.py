# -*- coding: utf-8 -*-
"""⚖️ تماثلُ المحرك والمرآة على **المصحف كلِّه** — لا على ٢١٢ حالةً من عيّنةٍ واحدة.

حزمةُ `parity_fixture.tsv` سندُها عيّنةُ G1 (‏202 حالةً حقيقية + ١٠ مصنوعة)، وكلُّها من
تعرّفٍ فعليّ على صوتٍ نظيف — فأكثرُها `CORRECT`، وأبوابٌ كاملةٌ في الحاكم (الدمجُ، الانقسامُ،
الزيادةُ الغريبة، حارسُ الانهيار، رخصةُ الكلمة القصيرة) قد لا يمرّ بها بندٌ واحد. فإذا افترق
المحركُ عن المرآة في بابٍ منها لم يقل أحدٌ شيئاً، وبقيت أرقامُ `REPORT.md` تصف محركاً غير المحرك.

فهذا يولّد **اضطراباتٍ حتميةً** (لا عشوائيةَ فيها ولا صوت) على كلِّ آيةٍ من كلِّ رواية، ويُجري
عليها الحاكمَين، ويطابق الحكمَ حرفاً بحرف:

    نظيف   · التلاوةُ تامّة                      ⇒ يُنتظر CORRECT في كلِّ كلمة
    حذف    · تُسقَط كلمةُ الوسط                   ⇒ MISSED
    زيادة  · تُقحَم كلمةٌ غريبة                    ⇒ ADDED + additions
    إبدال  · كلمةٌ قرآنيةٌ من آيةٍ أخرى             ⇒ SUBSTITUTED (وهنا تعمل رخصةُ القصيرة)
    تصحيف  · حرفٌ واحدٌ يتغيّر                     ⇒ UNCERTAIN غالباً (‏D-231/D-271)
    دمج    · كلمتان تلتصقان                       ⇒ مسارُ الدمج ١↔٢ في DP
    انقسام · كلمةٌ تنشطر نصفين                     ⇒ مسارُ الانقسام ٢↔١
    انهيار · كلُّ الكلمات تُبدَل                    ⇒ حارسُ الانهيار (‏≥٥ كلمات)

    python tools/tasmi_bench/parity_full.py                 # الروايات الثلاث
    python tools/tasmi_bench/parity_full.py --riwaya hafs --limit 500
    python tools/tasmi_bench/parity_full.py --control       # 🧪 الضابطُ السالب أوّلاً

⚠️ لا يقيس هذا **صحّةَ** الحكم بل **اتّفاقَ** الحاكمَين. فما اتّفقا على خطئه لا يظهر هنا.
🧪 **وابدأ بـ`--control` قبل تصديق أيِّ أخضر:** يزرع عطبَ D-276 في المرآة ويتأكّد أنّ المقارنة
   تصرخ. (سقطت فيه أوّلُ صيغةٍ من هذا الملفّ — انظر `control()`.)
"""
import argparse
import io
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "tools", "alignment"))
import scorer  # noqa: E402
from common import load_text  # noqa: E402

RIWAYAT = ("hafs", "warsh", "qalun")
CODE = {scorer.CORRECT: "C", scorer.MISSED: "M", scorer.SUBSTITUTED: "S",
        scorer.ADDED: "A", scorer.UNCERTAIN: "U"}
WORK = os.path.join(HERE, "work")
# كلمةٌ لا ترد في المصحف رسماً — للزيادة الغريبة (‏D-267 يفرّق الغريبَ من المعاد).
FOREIGN = "الحاسوب"


def config_for(riwaya):
    """إعدادُ المرآة المطابقُ لملفّ الرواية في المحرك (‏D-248)."""
    return scorer.Config(naql=(riwaya == "warsh"), sila=(riwaya in ("warsh", "qalun")))


# ⚠️ **إعدادان لا واحد** — وهذا شرطُ أن يكون للقياس معنى.
# `GEN_CFG_FN` يبني المسموعَ (ما يكتبه whisper)، و`MIRROR_CFG_FN` هو الإعدادُ **موضعُ الفحص**.
# لو بُني المسموعُ بالإعداد المفحوص نفسِه لصار القياسُ دائرياً: تُعطب المرآةُ فيُعطب المولّدُ معها
# فيتّفقان على الخطأ وتسكت المقارنة. (جُرّب: بعطب D-276 المزروع سكتت المقارنةُ سكوتاً تامّاً.)
GEN_CFG_FN = config_for
MIRROR_CFG_FN = config_for


def whisper_forms(word, cfg):
    """الصورُ التي قد يكتبها whisper لهذه الكلمة — لا صورةُ المصحف وحدَها.

    `norm` تعطي صورةَ الرسم (‏`ذَٰلِكَ` ⇒ «ذالك»)، و**whisper يكتب «ذلك»** بالإملاء الحديث.
    فالصورةُ الثانية هي التي تمرّ على بابِ `variants` (الخنجريّةُ الاختيارية · صلةُ ۦ/ۥ · النقلُ
    وصلةُ الميم) — وهو البابُ الذي وقع فيه عطبُ D-276 كلُّه. فإن وُلِّد المسموعُ بـ`norm` وحدَها
    لم يُفحَص هذا البابُ البتّة، وكان الأخضرُ أخضرَ فارغاً.
    """
    forms = [f for f in scorer._riwaya_forms(scorer.variants(word, cfg), cfg) if f]
    return forms or [scorer.norm(word, cfg)]


def _typo(word):
    """تصحيفُ حرفٍ واحدٍ في وسط الكلمة — حتميّ."""
    if not word:
        return word
    i = len(word) // 2
    c = "ت" if word[i] == "ب" else "ب"
    return word[:i] + c + word[i + 1:]


def make_cases(riwaya, limit=0):
    """يولّد حالاتِ الاضطراب لكلِّ آية. المرجعُ رسمُ المصحف، والمسموعُ مطبَّعٌ كما يكتب whisper."""
    cfg = GEN_CFG_FN(riwaya)
    ayat = load_text(riwaya)
    if limit:
        ayat = ayat[:limit]
    n_ayat = len(ayat)
    cases = []
    for a, ayah in enumerate(ayat):
        w = ayah.split()
        # ⚠️ علاماتُ الوقف (ۖ ۗ ۚ ۛ) رموزٌ مستقلّةٌ بين الكلمات في رسم المصحف، وتُطبَّع إلى
        # فراغ. **ولا تُحذف من المرجع هنا**: التطبيقُ يمرّر كلماتِ الآية كما تُعرض، فيجب أن
        # يُقاس ما يصنعه الحاكمان بها فعلاً (يبتلعها مسارُ الانقسام ٢↔١ فتُحسب CORRECT بلا
        # مسموعٍ يقابلها). وهي في ثلثَي آيات المصحف — فحذفُها يُخرج أكثرَ المصحف من القياس.
        nw = [scorer.norm(x, cfg) for x in w]
        # 🗣️ قاعدةُ الاضطراب: **الصورةُ الأبعدُ عن الرسم** من صور الكلمة المقبولة — أقربُ ما
        # يكون إلى ما يكتبه whisper فعلاً (‏«ذلك» لا «ذالك»، «عليهمو» لا «عليهم»، «ليكه» لا
        # «الايكه»). وعليها تقع كلُّ الاضطرابات، فيُفحَص بابُ `variants` لا بابُ `norm` وحدَه.
        ww = [whisper_forms(x, cfg)[-1] if n else "" for x, n in zip(w, nw)]
        # مواضعُ الكلمات الحقيقية (غيرِ الفارغة) — عليها يقع الاضطراب.
        real = [i for i, x in enumerate(nw) if x]
        if len(real) < 2:
            continue
        m = real[len(real) // 2]
        tag = "%s_%05d" % (riwaya, a)
        add = cases.append
        # صورةُ الرسم تامّةً، ثمّ صورةُ whisper تامّةً — كلتاهما يُنتظر فيهما CORRECT.
        add((tag + "_clean", ayah, " ".join(nw)))
        add((tag + "_whisper", ayah, " ".join(ww)))
        add((tag + "_drop", ayah, " ".join(ww[:m] + ww[m + 1:])))
        add((tag + "_add", ayah, " ".join(ww[:m] + [FOREIGN] + ww[m:])))
        # الإبدالُ بكلمةٍ قرآنيةٍ حقيقية من آيةٍ بعيدةٍ حتميّاً — لا كلمةٍ مخترعة.
        other = [scorer.norm(x, cfg) for x in ayat[(a + 1597) % n_ayat].split()]
        other = [x for x in other if x]
        alt = other[len(other) // 2] if other else FOREIGN
        if alt and alt != ww[m]:
            add((tag + "_sub", ayah, " ".join(ww[:m] + [alt] + ww[m + 1:])))
        add((tag + "_typo", ayah, " ".join(ww[:m] + [_typo(ww[m])] + ww[m + 1:])))
        if m + 1 < len(ww):
            add((tag + "_merge", ayah, " ".join(ww[:m] + [ww[m] + ww[m + 1]] + ww[m + 2:])))
        if len(ww[m]) >= 4:
            h = len(ww[m]) // 2
            add((tag + "_split", ayah, " ".join(ww[:m] + [ww[m][:h], ww[m][h:]] + ww[m + 1:])))
        if len(w) >= scorer.COLLAPSE_MIN_WORDS:
            add((tag + "_collapse", ayah, " ".join([FOREIGN] * len(nw))))
    return cases


def run_engine(cases, riwaya, out_tsv):
    """يبني حاكمَ المحرك (‏Kotlin) ويشغّله على الحالات — انظر engine_judge/."""
    src = os.path.join(WORK, "cases_%s.tsv" % riwaya)
    with io.open(src, "w", encoding="utf-8") as f:
        for name, ref, hyp in cases:
            f.write("\t".join((name, ref, hyp, riwaya)) + "\n")
    sh = os.path.join(HERE, "engine_judge", "build_and_run.sh")
    subprocess.run(["bash", sh, src, out_tsv], check=True)
    got = {}
    for line in io.open(out_tsv, encoding="utf-8"):
        if not line.strip():
            continue
        f = line.rstrip("\n").split("\t")
        got[f[0]] = (f[1], (f[2] if len(f) > 2 else "").split())
    return got


_MIRROR_CFG = None


def _mirror_init(riwaya):
    global _MIRROR_CFG
    _MIRROR_CFG = MIRROR_CFG_FN(riwaya)


def _mirror_one(case):
    name, ref, hyp = case
    s = scorer.score(ref.split(), hyp, _MIRROR_CFG)
    return name, "".join(CODE[w[1]] for w in s["words"]), list(s["additions"])


def run_mirror(cases, riwaya, jobs=0):
    """المرآةُ أبطأُ من المحرك بمراتب (‏DP بايثونيّ على كلِّ صورة) — فتُوزَّع على الأنوية."""
    jobs = jobs or (os.cpu_count() or 1)
    if jobs <= 1 or len(cases) < 500:
        _mirror_init(riwaya)
        return {n: (v, a) for n, v, a in (_mirror_one(c) for c in cases)}
    import multiprocessing as mp
    with mp.Pool(jobs, initializer=_mirror_init, initargs=(riwaya,)) as pool:
        return {n: (v, a) for n, v, a in pool.imap_unordered(_mirror_one, cases, chunksize=200)}


def compare(riwaya, limit=0, examples=5, jobs=0):
    cases = make_cases(riwaya, limit)
    eng = run_engine(cases, riwaya, os.path.join(WORK, "engine_%s.tsv" % riwaya))
    mir = run_mirror(cases, riwaya, jobs)
    kinds = {}
    bad = []
    for name, ref, hyp in cases:
        kind = name.rsplit("_", 1)[1]
        k = kinds.setdefault(kind, [0, 0])
        k[0] += 1
        e, m = eng.get(name), mir[name]
        if e is None or e[0] != m[0] or e[1] != m[1]:
            k[1] += 1
            bad.append((name, ref, hyp, m, e))
    return dict(riwaya=riwaya, n=len(cases), kinds=kinds, bad=bad, examples=examples)


def report(r):
    print("\n=== %s === حالات: %d · انحرافات: %d" % (r["riwaya"], r["n"], len(r["bad"])))
    for kind, (tot, nbad) in sorted(r["kinds"].items()):
        mark = "🚨" if nbad else "✅"
        print("  %s %-9s %6d حالة · %d انحراف" % (mark, kind, tot, nbad))
    for name, ref, hyp, m, e in r["bad"][:r["examples"]]:
        print("  ⚠️ %s\n     مرجع : %s\n     مسموع: %s\n     مرآة : %s %s\n     محرك : %s"
              % (name, ref, hyp, m[0], m[1], e))


def control(limit=300, jobs=1):
    """🧪 **ضابطٌ سالب** — يُعطَب إعدادُ المرآة عمداً بعطبِ D-276 (الخنجريّةُ غير اختيارية)
    ويُتأكَّد أنّ المقارنة **تصرخ**. حارسٌ لا يسقط على عطبٍ مزروع حارسٌ أخرس، وأخضرُه لا يساوي شيئاً.

    ⚠️ وهذا ليس تنظيراً: أوّلُ صيغةٍ من هذا الملفّ **سقطت في الضابط** — كانت تبني المسموعَ
    بـ`norm` فلا يمرّ ببابِ `variants` البتّة، فسكتت عن العطب المزروع سكوتاً تامّاً (0 انحراف
    من 2,276 حالة). ومن هنا وُلدت `whisper_forms` وفصلُ `GEN_CFG_FN` عن `MIRROR_CFG_FN`.
    """
    global MIRROR_CFG_FN
    sound = MIRROR_CFG_FN

    def broken(riwaya):
        cfg = sound(riwaya)
        return scorer.Config(naql=cfg.naql, sila=cfg.sila, dagger_optional=False)

    MIRROR_CFG_FN = broken
    try:
        r = compare("hafs", limit=limit, examples=2, jobs=jobs)
    finally:
        MIRROR_CFG_FN = sound
    report(r)
    ok = bool(r["bad"])
    print("\nالضابط: %s" % ("✅ صرخت المقارنة — الحارسُ حيّ"
                            if ok else "🚨 سكتت على عطبٍ مزروع — القياسُ أخرس، لا يُوثق بأخضره"))
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description="تماثلُ المحرك والمرآة على المصحف كلِّه")
    ap.add_argument("--riwaya", choices=RIWAYAT, help="رواية واحدة (الافتراض: الثلاث)")
    ap.add_argument("--limit", type=int, default=0, help="أوّل ن آية فقط (للتجربة)")
    ap.add_argument("--examples", type=int, default=5, help="كم انحرافاً يُطبع")
    ap.add_argument("--jobs", type=int, default=0, help="أنوية المرآة (الافتراض: كلُّها)")
    ap.add_argument("--control", action="store_true",
                    help="الضابطُ السالب: يعطب المرآة عمداً ويتأكّد أنّ المقارنة تصرخ")
    args = ap.parse_args()
    os.makedirs(WORK, exist_ok=True)
    if args.control:
        return control(args.limit or 300, args.jobs or 1)
    total = bad = 0
    for riwaya in ([args.riwaya] if args.riwaya else RIWAYAT):
        r = compare(riwaya, args.limit, args.examples, args.jobs)
        report(r)
        total += r["n"]
        bad += len(r["bad"])
    print("\nالمجموع: %d حالة · %d انحراف" % (total, bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
