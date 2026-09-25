# -*- coding: utf-8 -*-
"""قياس **الكشف**: هل يُمسك المحرك الخطأ إذا وقع، وأين؟

لكل صنف حقن (OMIT · SUBSTITUTE · SWAP · INSERT) يقيس ثلاثة أرقام:

1. **نسبة الكشف** — أن يُحكم بخطأٍ داخل نطاق الحقن (الموضع ±1 كلمة).
2. **دقّة الموضع** — أن يقع الحكم على الكلمة المحقونة **بعينها** لا على جارها.
3. **الإنذار الكاذب على السليم من الآية نفسها** — نسبة الكلمات المحكوم عليها
   خطأً **خارج** نطاق الحقن، ومعها خطُّ الأساس من التلاوة السليمة نفسها
   (‏`--clean`) — فالفارق وحده هو ما أحدثه الحقن.

⚠️ يُقرأ مع حدّ العيّنة في `inject.py`: الخطأ المصنوع أنظف من البشري.

    python tools/tasmi_bench/detect_score.py
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import scorer  # noqa: E402

def cfg_for(riwaya):
    """ملفُّ الرواية كما في `score.config_for("proposed", …)` بالضبط — مرآةُ `RiwayaProfile`.

    ⛔ **صُحّح 2026-09-08:** كان هنا `naql = riwaya not in (None, "hafs")`، أي **نقلٌ لقالون
    أيضاً** — وقالونٌ **يصل ولا ينقل** (‏D-248). فكان الحاكمُ يحتمل في قالون ما لا يُحتمل فيه،
    فيخفض إنذارَه الكاذب خفضاً كاذباً. ولم يظهر العطبُ قطُّ لأن مجموعةَ الحقن كانت **حفصاً
    خالصاً** فلا يمرّ بهذا الفرع أصلاً — حتى بُنيت مجموعةُ ورشٍ وقالون.
    ⇒ **فرعٌ لا تمرّ به عيّنتُك لا يُحرسه اختبارُك.**
    """
    return scorer.Config(strip_yeh_barree=True, dagger_optional=True,
                         naql=riwaya == "warsh",
                         sila=riwaya in ("warsh", "qalun"), mark_sila=True)


# ⚖️ **مرآةُ إعداد المحرك (خطة الحَكَم 2026-09-25 §٣-أ):** `cfg_for` أعلاه يُرجع `Config` بلا `strict_short`
# وبلا `critical_long` فيأخذان افتراضَهما (`False` و`None`)، والمحركُ المشحونُ يفعّلهما
# (‏`RecitationScorer.criticalPairsUncertain` والفهرسُ `criticalPairsLong`). فالبوّابةُ على `cfg_for`
# وحدَه تحكم بغير ما يحكم به التطبيق في بابَين. و`cfg_for` يبقى كما هو حرفاً: أدواتٌ كثيرةٌ مقيسةٌ عليه.
ASSETS = os.path.join(os.path.dirname(os.path.dirname(HERE)), "core", "quran", "src", "main", "assets", "quran")
CRIT_MIN_LEN = 5
_CRIT = {}


def critical_long_from_text(riwaya, text=None):
    """فهرسُ الأزواج الحرجة الطويلة **مشتقّاً من النصّ الموثَّق في هذا المستودع** بقاعدة
    `make_critical_pairs_index.py` نفسِها: صورتان مطبَّعتان من مصحف الرواية مسافتُهما 1 وأطولُهما ≥5.

    ⛔ **لماذا لا يُقرأ ملفُّ المحرك:** `critical_pairs.tsv` في المستودع الخاصّ، والمرآةُ العامّةُ لا تراه
    على CI. والاشتقاقُ حسابٌ محضٌ من `text_<r>.jz` (‏لا تحريرَ يدويّ)، ويطابقه `--selftest` بملفّ المحرك
    زوجاً زوجاً حين يوجد (‏`CRITICAL_PAIRS_TSV` أو المستودعُ المجاور)."""
    if text is None and riwaya in _CRIT:
        return _CRIT[riwaya]
    if text is None:
        import zlib
        text = json.loads(zlib.decompress(open(os.path.join(ASSETS, f"text_{riwaya}.jz"), "rb").read(), 47))
    c = scorer.Config(strip_yeh_barree=True, dagger_optional=True)
    words = {w for ay in text for w in (scorer.norm(x, c) for x in ay.split()) if w}
    keys = {}
    for w in words:
        if len(w) < CRIT_MIN_LEN - 1:
            continue
        for k in [w] + [w[:i] + w[i + 1:] for i in range(len(w))]:
            keys.setdefault(k, set()).add(w)
    out = set()
    for group in keys.values():
        g = sorted(group)
        for i in range(len(g)):
            for j in range(i + 1, len(g)):
                a, b = g[i], g[j]
                if max(len(a), len(b)) >= CRIT_MIN_LEN and scorer._edit(a, b) == 1:
                    out.add((a, b))
    out = frozenset(out)
    if text is not None and riwaya is None:
        return out
    _CRIT[riwaya] = out
    return out


def engine_cfg_for(riwaya):
    """`cfg_for` + ما يفعّله المحرك المشحون: `strict_short=True` وفهرسُ `critical_long` للرواية."""
    c = cfg_for(riwaya)
    c.strict_short = True
    c.critical_long = critical_long_from_text(riwaya or "hafs")
    return c


def judge(items, hyps):
    """يعيد لكل بند: أحكام الكلمات + عدد الزوائد."""
    out = {}
    for it in items:
        h = hyps.get(it["id"])
        if not h or "error" in h or not h.get("text"):
            continue
        s = scorer.score(it["refText"].split(), h["text"], cfg_for(it.get("riwaya")))
        out[it["id"]] = s
    return out


def zone(it):
    """نطاق الحقن بتسامح ±1 كلمة."""
    lo = it["wordIndex"] - 1
    hi = it["wordIndex"] + (2 if it["op"] == "SWAP" else 1)
    return lo, hi


def wilson(k, n, z=1.96):
    """مجال ثقة 95% لنسبةٍ ثنائية (Wilson) — أصدق من التقريب الطبيعي عند
    النسب القريبة من 1 والعيّنات الصغيرة (40 لكل صنف)."""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / d
    return (max(0.0, c - h) * 100, min(1.0, c + h) * 100)


# ---- 🧪 اختبارٌ ذاتيٌّ (أُضيف 2026-09-14 · مناوبةُ :13) ----
# ⛔ **لِمَ:** ثلاثُ دوالَّ هنا **خالصةٌ** ويُبنى عليها كلُّ رقمِ كشفٍ واتّهامٍ في اللوحة:
# `cfg_for` (‏ملفُّ الرواية) و`zone` (‏ما يُعدّ كشفاً وما يُعدّ اتّهاماً باطلاً) و`wilson`
# (‏مجالُ النسبة). وخطأُ أيٍّ منها **يقلب معنى الرقم لا يُسقط الشوط**.
# ⭐ **وفي شرح `cfg_for` نفسِه درسٌ مكتوبٌ بلا حارس:** «فرعٌ لا تمرّ به عيّنتُك لا يُحرسه
# اختبارُك» — كان `naql` يُعطى لقالون خطأً فلم يظهر حتى بُنيت عيّنةُ ورشٍ وقالون. فهذا
# الاختبارُ يمرّ **بكلّ فرعٍ** لا بما تمرّ به العيّنةُ اليومَ. والقيمُ أدناه **مقيسةٌ** من
# الدوالّ نفسِها قبل كتابتها.


def selftest():
    bad = 0

    def ok(name, got, want):
        nonlocal bad
        good = got == want
        print(f"  {'✅' if good else '⛔'} {name}: {got} · المتوقَّع {want}")
        bad += 0 if good else 1

    # ① ملفُّ الرواية — D-248: **ورشٌ ينقل ويصل · وقالونُ يصل ولا ينقل** · وسواهما لا ولا.
    for riw, naql, sila in (("warsh", True, True), ("qalun", False, True), ("hafs", False, False),
                            ("shuba", False, False), ("douri", False, False), (None, False, False)):
        c = cfg_for(riw)
        ok(f"رواية {riw}: نقلٌ وصلة", (c.naql, c.sila), (naql, sila))

    # ② نطاقُ الحقن — ما دخله كشفٌ وما خرج عنه **اتّهامٌ باطل**، وتوسيعُه يقلب المعنى.
    ok("إبدالٌ في 5 ⇒ ±1", zone({"wordIndex": 5, "op": "SUBSTITUTE"}), (4, 6))
    ok("وتبديلُ موضعَين (SWAP) يمتدّ كلمةً أخرى", zone({"wordIndex": 5, "op": "SWAP"}), (4, 7))
    # ⚠️ وحدٌّ يُوصَف لا يُبرَّر: الحقنُ في أوّل كلمةٍ يُعطي حدّاً سالباً — ولا ضررَ لأنّ
    #    المقارنةَ بالمسافة لا بالفهرسة، **ويُثبَّت كي لا يُصلَح بلا داعٍ**.
    ok("والحقنُ في الكلمة الأولى ⇒ حدٌّ سالبٌ مقصود", zone({"wordIndex": 0, "op": "SUBSTITUTE"}), (-1, 1))

    # ③ مجالُ ويلسون — أصدقُ من الطبيعيّ عند الأطراف، وهذا **ما يُقاس عليه**.
    ok("صفرُ نجاحٍ من عشرةٍ ⇒ الحدُّ الأدنى صفر", tuple(round(x, 2) for x in wilson(0, 10)), (0.0, 27.75))
    ok("وخمسةٌ من عشرةٍ ⇒ متناظر", tuple(round(x, 2) for x in wilson(5, 10)), (23.66, 76.34))
    ok("والعشرُ من عشرٍ ⇒ سقفٌ 100 وأرضيّةٌ دونه", tuple(round(x, 2) for x in wilson(10, 10)), (72.25, 100.0))
    ok("ولا عيّنةَ ⇒ صفران بلا قسمةٍ على صفر", wilson(0, 0), (0.0, 0.0))
    ok("والأرضيّةُ ترتفع بارتفاع النجاح", wilson(39, 40)[0] > wilson(1, 40)[0], True)

    # ④ والبندُ بلا فرضيّةٍ (أو بنصٍّ فارغ · أو بخطأ) **لا يُحتسب** — ولا يُقرأ صفراً.
    it = {"id": "x", "refText": "الحمد لله رب العالمين", "riwaya": "hafs"}
    ok("لا فرضيّةَ ⇒ لا بند", len(judge([it], {})), 0)
    ok("ونصٌّ فارغٌ ⇒ لا بند", len(judge([it], {"x": {"text": ""}})), 0)
    ok("وفرضيّةٌ بخطإٍ ⇒ لا بند", len(judge([it], {"x": {"error": "boom", "text": "الحمد"}})), 0)
    ok("وفرضيّةٌ سليمةٌ ⇒ بندٌ واحد", len(judge([it], {"x": {"text": "الحمد لله رب العالمين"}})), 1)

    # ⑤ مرآةُ إعداد المحرك (§٣-أ): المفتاحان مفعَّلان، و`cfg_for` نفسُه لم يتغيّر.
    e, g = engine_cfg_for("warsh"), cfg_for("warsh")
    ok("مرآةُ المحرك: strict_short مفعَّلٌ وفهرسٌ غيرُ فارغ", (e.strict_short, bool(e.critical_long)), (True, True))
    ok("وcfg_for كما هو (بلا المفتاحين)", (g.strict_short, g.critical_long), (False, None))
    ok("والنقلُ والصلةُ تبقى بالرواية", (e.naql, e.sila), (g.naql, g.sila))
    # الاشتقاقُ على نصٍّ صغيرٍ مقيس: «يعلمون/تعلمون» و«لليسرى/للعسرى» زوجان بمسافة 1 (‏والألفُ المقصورةُ
    # تُطبَّع ياءً)؛ و«كذبوا/صدقوا» بعيدتان فلا زوج؛ والقصيرُ (‏<5) خارجٌ ولو كانت المسافةُ 1.
    toy = critical_long_from_text(None, ["يعلمون تعلمون لليسرى للعسرى كذبوا صدقوا لم لن"])
    ok("الاشتقاقُ على نصٍّ صغير", sorted(toy), [("تعلمون", "يعلمون"), ("للعسري", "لليسري")])
    # وفي المرآة: الأختُ القرآنيةُ لم تعد «صحيحة» مع المحرك وبقيت كذلك مع `cfg_for`.
    ref = ["يَعْلَمُونَ"]
    ok("الأختُ في الفهرس ⇒ غيرُ متبيَّنٍ بمرآة المحرك",
       scorer.score(ref, "تعلمون", engine_cfg_for("hafs"))["words"][0][1], scorer.UNCERTAIN)
    ok("وصحيحةٌ بـcfg_for (البابُ الذي أُغلق)", scorer.score(ref, "تعلمون", cfg_for("hafs"))["words"][0][1], scorer.CORRECT)
    ok("والقصيرُ بفارق حرفٍ ⇒ غيرُ متبيَّنٍ بمرآة المحرك",
       scorer.score(["لَمْ"], "لن", engine_cfg_for("hafs"))["words"][0][1], scorer.UNCERTAIN)
    # ومطابقةُ ملفّ المحرك زوجاً زوجاً حين يوجد (‏لا يوجد في المستودع العامّ على CI ⇒ يُطبع ولا يُحتسب).
    tsv = os.environ.get("CRITICAL_PAIRS_TSV") or os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(HERE))), "QuranRafiq", "engine", "recitation", "src",
        "main", "resources", "tasmi", "critical_pairs.tsv")
    if os.path.isfile(tsv):
        bits = {"hafs": 1, "warsh": 2, "qalun": 4, "shuba": 8, "douri": 16, "sousi": 32}
        eng = {r: set() for r in bits}
        for line in open(tsv, encoding="utf-8"):
            if line.strip() and not line.startswith("#"):
                a, b, m = line.rstrip("\n").split("\t")
                for r, bt in bits.items():
                    if int(m) & bt:
                        eng[r].add((a, b))
        for r in bits:
            ok(f"الفهرسُ المشتقّ = ملفُّ المحرك ({r})", critical_long_from_text(r) == eng[r], True)
    else:
        print(f"  ⚪ ملفُّ المحرك غيرُ موجودٍ هنا ({tsv}) ⇒ لم تُطابَق الأزواجُ بملفّه")

    print("✅ الأداةُ سليمةٌ على حالاتها" if not bad else f"⛔ الأداةُ نفسُها معطوبةٌ في {bad} حالة")
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", default=os.path.join(HERE, "inject_plan.json"))
    ap.add_argument("--inj", default=os.path.join(HERE, "work", "inj_hyps.json"))
    ap.add_argument("--clean", default=os.path.join(HERE, "work", "clean_hyps.json"))
    ap.add_argument("--require-clean-correct", action="store_true",
                    help="لا تحتسب إلا بنداً كانت كلمته المستهدفة صحيحةً قبل الجراحة "
                         "(تحقّقٌ بعديّ من موضع القطع حين تكون الحدود مشتقّة لا مقيسة)")
    ap.add_argument("--selftest", action="store_true", help="يختبر الدوالَّ الخالصةَ على قيمٍ مقيسة")
    args = ap.parse_args()
    if args.selftest:
        raise SystemExit(selftest())
    plan = json.load(open(args.plan, encoding="utf-8"))["items"]
    inj = judge(plan, json.load(open(args.inj, encoding="utf-8"))["hyps"])
    clean = judge(plan, json.load(open(args.clean, encoding="utf-8"))["hyps"]) \
        if os.path.exists(args.clean) else {}

    rows, skipped = {}, 0
    for it in plan:
        s = inj.get(it["id"])
        if s is None:
            continue
        c = clean.get(it["id"])
        if args.require_clean_correct:
            # شرطٌ سابق للحُكم: أن يكون التعرّف قد أصاب الكلمة **قبل** الجراحة —
            # وإلا فالبند يقيس عجز النموذج أو خطأ الحدّ لا الكشف.
            if c is None:
                skipped += 1
                continue
            tgt = [w for w in c["words"] if w[0] == it["wordIndex"]]
            if not tgt or tgt[0][1] != scorer.CORRECT:
                skipped += 1
                continue
        lo, hi = zone(it)
        bad = [w for w in s["words"] if w[1] != scorer.CORRECT]
        in_zone = [w for w in bad if lo <= w[0] <= hi]
        exact = [w for w in bad if w[0] == it["wordIndex"]
                 or (it["op"] == "SWAP" and w[0] == it["wordIndex"] + 1)]
        extra_add = len(s["additions"]) - (len(c["additions"]) if c else 0)
        hit = bool(in_zone) or (it["op"] == "INSERT" and extra_add > 0)
        exact_hit = bool(exact) or (it["op"] == "INSERT" and extra_add > 0)
        outside = [w for w in bad if not (lo <= w[0] <= hi)]
        outside_total = sum(1 for w in s["words"] if not (lo <= w[0] <= hi))
        base_bad = 0
        if c:
            base_bad = sum(1 for w in c["words"]
                           if w[1] != scorer.CORRECT and not (lo <= w[0] <= hi))
        r = rows.setdefault(it["op"], {"n": 0, "hit": 0, "exact": 0,
                                       "fa": 0, "faTotal": 0, "faBase": 0})
        r["n"] += 1; r["hit"] += hit; r["exact"] += exact_hit
        r["fa"] += len(outside); r["faTotal"] += outside_total; r["faBase"] += base_bad

    print(f"══ الكشف على الحقن ({sum(r['n'] for r in rows.values())} بنداً، "
          f"خط الأساس السليم: {'موجود' if clean else '⚠️ غائب'}"
          f"{f'، مستبعَد بشرط الصحة قبل الجراحة: {skipped}' if skipped else ''}) ══")
    print(f"{'الصنف':11s} {'ن':>4s} {'كشف':>8s} {'بالموضع':>9s} "
          f"{'إنذار كاذب (سليم الآية)':>26s}")
    for op in ("OMIT", "SUBSTITUTE", "SWAP", "INSERT"):
        r = rows.get(op)
        if not r:
            continue
        fa = r["fa"] / r["faTotal"] * 100 if r["faTotal"] else 0
        fb = r["faBase"] / r["faTotal"] * 100 if r["faTotal"] else 0
        lo, hi = wilson(r["hit"], r["n"])
        print(f"{op:11s} {r['n']:4d} {r['hit']/r['n']*100:7.1f}% [{lo:.1f}–{hi:.1f}] "
              f"{r['exact']/r['n']*100:8.1f}%   {fa:5.1f}% (سليماً {fb:.1f}%)")
    tot = {k: sum(r[k] for r in rows.values()) for k in ("n", "hit", "exact", "fa", "faTotal", "faBase")}
    lo, hi = wilson(tot["hit"], tot["n"])
    print(f"{'الإجمالي':11s} {tot['n']:4d} {tot['hit']/tot['n']*100:7.1f}% [{lo:.1f}–{hi:.1f}] "
          f"{tot['exact']/tot['n']*100:8.1f}%   "
          f"{tot['fa']/tot['faTotal']*100:5.1f}% (سليماً {tot['faBase']/tot['faTotal']*100:.1f}%)")


if __name__ == "__main__":
    main()
