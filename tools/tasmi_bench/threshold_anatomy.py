# -*- coding: utf-8 -*-
"""🎚️ **تشريحُ العتبة** — أين تعضّ أثقلُ رخصةٍ في بابِ القبول، وهل لها قطعةٌ أرخص؟

خلّف دفترُ D-286 مرشَّحاً لم يكن على الطاولة: **العتبةُ نفسُها**. تضييقُ «تحريفٌ ≤ خُمسُ
الطول» إلى السدس يكشف **6,249** زلّةً روائيةً ويكلّف **7** إنذاراتٍ كاذبةً في 3,823 كلمةً
من نصٍّ حقيقيّ — أي 130 ضعفَ أثرِ الذراع المعلَّق. وقال الدفترُ صراحةً إنّه **لا يُشحن
بهذا وحدَه**، لأنّ عمودَ التكلفة قِيس على قرّاءِ مرجعٍ لا على متعلّم.

وهذا الملفُّ يسأل ما قبلَ ذلك: **العتبةُ ليست مقبضاً متّصلاً بل درجاتٌ منفصلة.** فالشرطُ
`d * den <= n` معناه أنّ الذراعَ لا يلمس إلا شريطاً بعينِه من الأزواج:

    الخُمس ⇒ السدس  لا يمسّ إلا ما كان  n/d ∈ [5, 6)   — أي **(d=1, n=5)** و(d=2, n=10..11)…

فإن كان شريطُ «كلمةٌ من خمسة أحرفٍ بحرفٍ واحدٍ مخالف» هو الذي يحمل الفائدةَ كلَّها فذلك
**أكثرُ أشكال خطأ التعرّف شيوعاً** ⇒ التكلفةُ على متعلّمٍ حقيقيٍّ أكبرُ بكثيرٍ ممّا في
الدفتر. وإن كانت الفائدةُ في الكلمات الطويلة (‏d≥2) فثمّة **قطعةٌ أرخص لم تُقترح قطّ**:
سقفٌ مطلقٌ `d ≤ 1` يُبقي تسامحَ الحرف الواحدِ في القصيرة ويمنعه في الطويلة.

## العملة — هي عملةُ D-286 نفسُها (فتُقارَن الأرقامُ مباشرةً)
    الفائدة · كم زلّةً روائيةً عمياءَ يكشفها الذراع (من 49,146 على المصحف كلِّه)
    التكلفة أ · كم موضعَ تلاوةٍ صحيحةٍ ينقلب اتّهاماً (‏232,288 موضعاً · مولَّدة)
    التكلفة ب · كم إنذاراً كاذباً على **نصِّ تعرّفٍ حقيقيّ** (‏الحزمتان المودَعتان)

⚠️ المصدرُ المرآةُ البايثونية، وهي في بابِ القبول مصدَّقةٌ على المحرك (‏D-279/D-285)؛
والتوليدُ بالإعدادِ **المشحون** والفحصُ بالذراع ⇒ لا دائريّة. والمقياسُ **زوجيّ** ⇒ أرقامُ
الكشف سقفٌ لا حصيلة (‏قاعدةُ D-286).

    python threshold_anatomy.py --control   # 🧪 الضوابطُ أوّلاً
    python threshold_anatomy.py             # المصحفُ كلُّه (~6 د.)
    python threshold_anatomy.py --examples 6
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "tools", "alignment"))

import scorer  # noqa: E402
import license_ledger as L  # noqa: E402  (مصدرٌ واحدٌ للمجتمعين وللإعداد المشحون)

INF = 10 ** 6

# الأذرع: (المفتاح، الاسم، den، سقفٌ مطلق)
ARMS = (
    ("den4", "الرُّبع (توسيعٌ — ضابطُ حيويّة)", 4, None),
    ("den5", "المشحون: الخُمس", 5, None),
    ("den6", "السدس (مرشَّحُ D-286)", 6, None),
    ("den7", "السبع", 7, None),
    ("den8", "الثمن", 8, None),
    ("cap2", "الخُمس + سقفٌ مطلق ≤2 حرفين", 5, 2),
    ("cap1", "الخُمس + سقفٌ مطلق ≤1 حرف", 5, 1),
    ("d6c1", "السدس + سقفٌ مطلق ≤1", 6, 1),
    ("cap0", "لا تحريفَ البتّة (تبقى رخصةُ القصيرة)", INF, None),
)


def dn_list(raw, hyp, cfg):
    """لكلِّ صورةٍ مقبولةٍ للكلمة المرجعية: (التحريفُ d، الطولُ n) — يُحسب مرّةً ويُعاد استعمالُه.

    None ⇒ ليس موضعَ حكم (رمزُ وقفٍ أو ما يُطبَّع فراغاً) كما في `license_ledger.accepts`.
    """
    forms = tuple(f for f in scorer._riwaya_forms(scorer.variants(raw, cfg), cfg) if f)
    if not forms:
        return None
    return [(scorer._edit(f, hyp), max(len(f), len(hyp))) for f in forms]


def accepts_dn(dns, den, abs_cap=None, short_cap=3):
    """مرآةُ `scorer._matches` من (d, n) وحدَها — الإعدادُ المشحون فيما عدا العتبة."""
    for d, n in dns:
        if d * den <= n and (abs_cap is None or d <= abs_cap):
            return True
        if n <= short_cap and d <= 1:
            return True
    return False


def cap_den(dns):
    """أوسعُ مقامٍ يقبل هذا الزوجَ بقاعدة النسبة: `max(n/d)` (‏∞ إن طابق تماماً).

    ⇒ ذراعُ المقام `den` يقبل الزوجَ بقاعدة النسبة إن كان `den <= cap_den`. فهذا العددُ
    هو **الدرجةُ** التي يقف عندها الزوج، وبه يُشرَّح المجتمعان تشريحاً تامّاً.
    """
    best = 0.0
    for d, n in dns:
        if d == 0:
            return float("inf")
        best = max(best, n / d)
    return best


def band(dns):
    """اسمُ الشريط الذي يقف عنده الزوج: الدرجةُ الصحيحةُ من `cap_den`."""
    c = cap_den(dns)
    if c == float("inf"):
        return "∞ (مطابقةٌ تامّة)"
    if c < 4:
        return "< 4 (مردودٌ بالمشحون)"
    return "%d ≤ n/d < %d" % (int(c), int(c) + 1)


def min_d(dns):
    return min(d for d, _ in dns)


def hist(rows, key, title, total_label):
    order = {}
    for r in rows:
        order[key(r)] = order.get(key(r), 0) + 1
    print(title)
    tot = max(len(rows), 1)
    for k in sorted(order, key=lambda x: (x[0] != "∞", x)):
        print("   %-24s %8d  (%5.1f٪ من %s)" % (k, order[k], 100.0 * order[k] / tot, total_label))
    print()


def real_text(arms, examples=0):
    """التكلفةُ (ب): إنذارٌ كاذبٌ على نصِّ تعرّفٍ **حقيقيّ** (الحزمتان المودَعتان)."""
    import short_word_benefit as B  # noqa: E402

    rows = B.load_fixture() + B.load_long()

    def judge(**kw):
        out = {}
        for r in rows:
            base = dict(naql=(r["riwaya"] == "warsh"), sila=(r["riwaya"] in ("warsh", "qalun")))
            base.update(kw)
            cfg = scorer.Config(**base)
            words = r["ref"].split()
            res = scorer.score(words, r["hyp"], cfg)
            for i, (w, v) in enumerate(zip(words, res["words"])):
                out[(r["name"], i)] = (w, v[1], v[2])
        return out

    base = judge()
    total, bad = B.validate(B.load_fixture(), base)
    print("🧪 ضابطُ التصديق · الحزمةُ المصدَّقةُ على المحرك: %d/%d حكماً مطابقاً %s"
          % (total - bad, total, "✅" if bad == 0 else "🚨"))
    n_correct = sum(1 for v in base.values() if v[1] == scorer.CORRECT)
    print("🎙️ نصٌّ حقيقيّ: %d كلمةً مرجعية (%d منها CORRECT بالمشحون)\n" % (len(base), n_correct))

    # 📏 إحصاءُ التعرّض: كم كلمةً صحيحةً في النصِّ الحقيقيّ **تتّكئ** على تسامح العتبة أصلاً
    # (‏تحريفُها ≥ 1) وفي أيِّ شريط؟ هذا هو الطرفُ الذي لا يبلغه المجتمعُ المولَّد بحال.
    census, leaning = {}, 0
    for (nm, i), (w, v, heard) in base.items():
        if v != scorer.CORRECT or not heard:
            continue
        riw = next((r["riwaya"] for r in rows if r["name"] == nm), "hafs")
        cfg = scorer.Config(naql=(riw == "warsh"), sila=(riw in ("warsh", "qalun")))
        dns = dn_list(w, heard, cfg)
        if not dns:
            continue
        d = min_d(dns)
        if d:
            leaning += 1
        k = band(dns)
        census[k] = census.get(k, 0) + 1
    print("📏 إحصاءُ التعرّض على النصِّ الحقيقيّ — الشريطُ الذي تقف عنده كلُّ كلمةٍ حُكم عليها CORRECT:")
    for k in sorted(census, key=lambda x: (x[0] != "∞", x)):
        print("   %-24s %6d" % (k, census[k]))
    print("   ⇒ **%d** كلمةً من الصحيحة تتّكئ على تسامح العتبة (تحريفُها ≥ 1 حرف).\n" % leaning)

    out = {}
    for key, name, den, cap in arms:
        arm_j = judge(match_den=den, abs_cap=cap)
        lost, ex = 0, []
        for k, (w, v, heard) in base.items():
            if v == scorer.CORRECT and arm_j[k][1] in (scorer.MISSED, scorer.SUBSTITUTED):
                lost += 1
                if len(ex) < examples:
                    ex.append("%s ⇜ «%s»" % (w, heard))
        out[key] = lost
        print("%-40s %6d إنذاراً كاذباً%s" % (name, lost, ("   " + " · ".join(ex)) if ex else ""))
    print("\n   ⚠️ الحزمتان صغيرتان (%d كلمة) ⇒ الرقمُ **حدٌّ أدنى** لا حصر.\n" % len(base))
    return out


def measure(limit=0, examples=0, with_real=True):
    text = L.prepare(limit)
    ship = {r: L.shipped(r) for r in L.RIWAYAT}

    A = []      # تلاوةٌ صحيحة: (رواية، خام، مسموع، dns)
    for r, raw, hyp in L.population_a(text):
        dns = dn_list(raw, hyp, ship[r])
        if dns is not None:
            A.append((r, raw, hyp, dns))
    Ball, Bblind = 0, []
    for e, s, raw, hyp in L.population_b(text):
        dns = dn_list(raw, hyp, ship[e])
        if dns is None:
            continue
        Ball += 1
        if accepts_dn(dns, 5):
            Bblind.append((e, s, raw, hyp, dns))

    floor = [x for x in A if not accepts_dn(x[3], 5)]
    print("👥 المجتمعان (المصحفُ كلُّه):")
    print("   أ · تلاوةٌ صحيحة: %d موضعٍ ⇒ أرضيّةُ الاتّهام الكاذب بالمشحون: **%d**"
          % (len(A), len(floor)))
    print("   ب · زلّةٌ روائية: %d زوجٍ ⇒ يبتلعها المشحون (عمىً): **%d** (%.2f٪)\n"
          % (Ball, len(Bblind), 100.0 * len(Bblind) / max(Ball, 1)))

    # ١) التشريح: أين يقف كلُّ مجتمعٍ من درجات العتبة
    hist(Bblind, lambda x: band(x[4]),
         "🔬 تشريحُ العمى — الدرجةُ التي تُبقي الزلّةَ مقبولة (‏ذراعُ المقام den يكشفها إن den > الدرجة):",
         "العمى")
    hist(Bblind, lambda x: "d = %d" % min_d(x[4]),
         "🔬 وبعدد التحريفات (‏أقلُّ صورةٍ) — يقرأه ذراعُ السقف المطلق:", "العمى")
    hist(A, lambda x: band(x[3]),
         "🛡️ تشريحُ الحماية — درجةُ كلِّ موضعِ تلاوةٍ صحيحة (ما دون ∞ هو ما تحميه العتبة فعلاً):",
         "المواضع")

    # ٢) جدولُ الأذرع
    real = real_text(ARMS, examples) if with_real else {}
    print("⚖️ الأذرع — بعملة D-286 نفسِها:")
    print("%-40s %10s %12s %10s %10s" % ("الذراع", "زلّةٌ تُكشف", "اتّهامٌ كاذب أ", "كاذبٌ ب", "السعر ب"))
    base_rows = []
    for key, name, den, cap in ARMS:
        gain = sum(1 for x in Bblind if not accepts_dn(x[4], den, cap))
        cost_a = sum(1 for x in A if accepts_dn(x[3], 5) and not accepts_dn(x[3], den, cap))
        cost_b = real.get(key)
        price = ("%.0f" % (gain / cost_b)) if cost_b else ("∞" if gain else "—")
        print("%-40s %10d %12d %10s %10s"
              % (name, gain, cost_a, "—" if cost_b is None else cost_b, price))
        base_rows.append((key, name, gain, cost_a, cost_b))
    print("\n   «السعر ب» = كم زلّةً يكشف الذراعُ لكلِّ إنذارٍ كاذبٍ يُحدثه في النصِّ الحقيقيّ (الأعلى أربح).")
    print("   ⚠️ عمودُ «أ» مولَّدٌ (مسموعُه صورةُ whisper الحتميّة) ⇒ فيه فروقُ الرسم ولا شيءَ من")
    print("      ضجيج التعرّف؛ وعمودُ «ب» هو الوحيدُ الذي فيه خطأُ تعرّفٍ حقيقيّ، وهو صغير.\n")

    if examples:
        print("🔎 أمثلةٌ من الشريط الذي يفصل الخُمسَ عن السدس (d=1 · n=5):")
        shown = 0
        for e, s, raw, hyp, dns in Bblind:
            if accepts_dn(dns, 5) and not accepts_dn(dns, 6) and min_d(dns) == 1:
                print("   زلّةٌ تُكشف: %s⇜%s  %s ⇜ «%s»" % (e, s, raw, hyp))
                shown += 1
                if shown >= examples:
                    break
        shown = 0
        for r, raw, hyp, dns in A:
            if accepts_dn(dns, 5) and not accepts_dn(dns, 6):
                print("   اتّهامٌ يُحدَث: %s  %s ⇜ «%s»" % (r, raw, hyp))
                shown += 1
                if shown >= examples:
                    break
        print()
    return base_rows


def selftest():
    """🧪 **حارسُ حسابِ العتبة — بلا مصحفٍ ولا محرّك** (‏D-502).

    ⛔⛔ **ولماذا:** على أرقام هذا الملفّ يُقترح **تضييقُ عتبةِ قبولٍ مشحونة**. وحسابُه كلُّه
    في أربع دوالَّ صغيرة (`accepts_dn` · `cap_den` · `band` · `min_d`) — **وخطأٌ في واحدةٍ
    يُعطي جدولاً كاملاً سليمَ الشكل خاطئَ الحكم**. و`--control` هنا ثقيلٌ (يُهيّئ المصحفَ)
    فلا يُشعَل في كلّ دفعة ⇒ **فالحسابُ يُثبَّت في ثوانٍ**.
    """
    ok = True

    def say(good, line):
        nonlocal ok
        ok &= bool(good)
        print(("✅ " if good else "❌ ") + line)

    # ①⭐ قاعدةُ النسبة `d*den <= n` — وهي **الشريطُ الذي يمسّه الذراعُ بعينه**
    say(accepts_dn([(1, 5)], 5) and not accepts_dn([(1, 5)], 6),
        "⭐ (d=1, n=5): يقبله **الخُمس** ويردّه **السدس** — وهو الشريطُ الذي يمسّه مرشَّحُ D-286 وحدَه")
    say(accepts_dn([(2, 10)], 5) and not accepts_dn([(2, 10)], 6),
        "و(d=2, n=10) مثلُه — فالدرجةُ واحدةٌ والطولُ مضاعف")
    say(accepts_dn([(1, 6)], 6) and accepts_dn([(1, 6)], 5),
        "و(d=1, n=6) يقبله الاثنان — فليس في الشريط")

    # ② السقفُ المطلق يعمل **فوق** النسبة لا بدلَها
    say(accepts_dn([(2, 20)], 5) and not accepts_dn([(2, 20)], 5, 1),
        "والسقفُ المطلق ≤1 يردّ (d=2, n=20) وقاعدةُ النسبة تقبله — فهو **قطعةٌ أخرى** لا تضييقُ نسبة")

    # ③⭐⭐ رخصةُ الكلمة القصيرة **تبقى ولو مُنع التحريفُ البتّة** — وهي دعوى صفّ `cap0`
    say(accepts_dn([(1, 3)], 5) and accepts_dn([(1, 3)], INF),
        "⭐⭐ (d=1, n=3): تقبلها **رخصةُ القصيرة** ولو صار المقامُ ∞ — وهو نصُّ صفِّ `cap0`")
    say(not accepts_dn([(2, 3)], INF) and not accepts_dn([(2, 3)], 5),
        "وحرفان في كلمةٍ من ثلاثة **لا تقبلهما الرخصةُ** (‏شرطُها `d ≤ 1`)")
    say(accepts_dn([(0, 9)], INF), "والمطابقةُ التامّةُ تُقبل في كلّ ذراع")

    # ④⭐ رتابةٌ: مقامٌ أضيقُ لا يقبل ما ردّه الأوسع — والعتبةُ **درجاتٌ** لا مقبض
    grid = [[(d, n)] for d in range(0, 4) for n in (3, 4, 5, 7, 10, 16, 20)]
    bad = [(dns, a, b) for dns in grid for a, b in ((4, 5), (5, 6), (6, 7), (7, 8))
           if accepts_dn(dns, b) and not accepts_dn(dns, a)]
    say(not bad, f"⭐ ورتابةٌ تامّةٌ على {len(grid)} زوجاً: ما قبله الأضيقُ يقبله الأوسعُ دائماً — والمخالفُ {bad[:2]}")

    # ⑤ `cap_den` و`band`: الدرجةُ التي يقف عندها الزوج
    say(cap_den([(0, 7)]) == float("inf") and cap_den([(1, 5)]) == 5.0
        and cap_den([(3, 5), (1, 5)]) == 5.0,
        "والدرجةُ `cap_den`: ∞ للمطابق · 5 لـ(1,5) · **وأوسعُ صورةٍ تغلب** حين تتعدّد الصور")
    say(band([(0, 7)]).startswith("∞") and band([(1, 5)]) == "5 ≤ n/d < 6"
        and band([(2, 5)]).startswith("< 4"),
        f"واسمُ الشريط: {band([(1, 5)])} · {band([(2, 5)])}")
    say(min_d([(3, 9), (1, 9)]) == 1, "و`min_d` أقلُّ تحريفٍ بين الصور")

    # ⑥ جدولُ الأذرع: المشحونُ الخُمس · و`den4` **أوسعُ** فهو ضابطُ حيويّة · و`cap0` مقامُه ∞
    keys = [a[0] for a in ARMS]
    d = {a[0]: (a[2], a[3]) for a in ARMS}
    say(len(keys) == len(set(keys)) and d["den5"] == (5, None),
        f"وأذرعٌ {len(keys)} بمفاتيحَ فريدةٍ، والمشحونُ `den5` مقامُه 5 بلا سقف")
    say(d["den4"][0] < d["den5"][0],
        "و`den4` **أوسعُ** من المشحون — فهو ضابطُ حيويّةٍ لا مرشَّحُ شحن")
    say(d["cap0"][0] == INF, "و`cap0` مقامُه ∞ — «لا تحريفَ البتّة» وتبقى رخصةُ القصيرة")

    print("\n" + ("✅ حسابُ العتبة يفعل ما يدّعي — والرخصةُ القصيرةُ تبقى حيث قيل إنّها تبقى"
                  if ok else "❌ حسابُ العتبة لا يفعل ما يدّعي"))
    return 0 if ok else 1


def control(limit=400):
    """🧪 الضوابط (قاعدةُ D-279): موجَبٌ · سالبٌ · حيويّة — قبل أيِّ رقم."""
    text = L.prepare(limit)
    ship = {r: L.shipped(r) for r in L.RIWAYAT}
    A = []
    for r, raw, hyp in L.population_a(text):
        dns = dn_list(raw, hyp, ship[r])
        if dns is not None:
            A.append((r, raw, hyp, dns))

    # سالب ١: مرآةُ (d,n) تطابق `scorer._matches` نفسَها حالةً بحالة في كلِّ ذراع
    bad = 0
    for r, raw, hyp, dns in A:
        forms = tuple(f for f in scorer._riwaya_forms(scorer.variants(raw, ship[r]), ship[r]) if f)
        for _, _, den, cap in ARMS:
            cfg = scorer.Config(naql=(r == "warsh"), sila=(r in ("warsh", "qalun")),
                                match_den=den, abs_cap=cap)
            if scorer._matches(forms, hyp, cfg) != accepts_dn(dns, den, cap):
                bad += 1
    print("🧪 سالب ١ · مرآةُ (d,n) مقابل `_matches` نفسِها: %d اختلافاً من %d حالة %s"
          % (bad, len(A) * len(ARMS), "✅" if bad == 0 else "🚨"))

    # سالب ٢: ذراعُ المشحون (den=5) لا يحرّك شيئاً
    moved = sum(1 for x in A if accepts_dn(x[3], 5) != accepts_dn(x[3], 5, None))
    print("🧪 سالب ٢ · ذراعُ المشحون يطابق نفسَه: %d حركة %s" % (moved, "✅" if moved == 0 else "🚨"))

    # سالب ٣: كلمةٌ غريبةٌ مكانَ المسموع ⇒ لا ذراعَ يقبلها (العدّادُ لا يقبل بلا سند)
    odd = sum(1 for r, raw, _, _ in A
              if accepts_dn(dn_list(raw, "الحاسوب", ship[r]) or [(9, 9)], 4))
    print("🧪 سالب ٣ · كلمةٌ غريبة («الحاسوب») في %d موضعاً بأوسعِ ذراع: %d قبولاً %s"
          % (len(A), odd, "✅" if odd == 0 else "🚨"))

    # 🔑 ملحوظةٌ بنيويّة (لا عطب): مجتمعُ (أ) مسموعُه صورةُ whisper الحتميّة للكلمةِ نفسِها
    # ⇒ تحريفُه صفرٌ في الغالب، فأذرعُ العتبة لا تحرّكه البتّة. وهو **ما قاله دفترُ D-286**:
    # رخصتا التسامح مع خطأ التعرّف تعطيان صفراً بالبناء في هذا المجتمع. فالحيويّةُ تُقاس
    # حيث للعتبةِ أثرٌ أصلاً: مجتمعُ الزلّة (ب).
    zero_a = sum(1 for x in A if min_d(x[3]) == 0)
    print("🧪 بنيويّ · مجتمعُ (أ) تحريفُه صفرٌ في %d من %d موضعاً (%.1f٪) ⇒ عمودُ «أ» صفرٌ "
          "بالبناء لا حكماً" % (zero_a, len(A), 100.0 * zero_a / max(len(A), 1)))
    Bb = []
    for e, s, raw, hyp in L.population_b(text):
        dns = dn_list(raw, hyp, ship[e])
        if dns is not None:
            Bb.append(dns)
    for name, den, cap in (("الربع", 4, None), ("السدس", 6, None), ("سقف ≤1", 5, 1)):
        mv = sum(1 for dns in Bb if accepts_dn(dns, 5) != accepts_dn(dns, den, cap))
        print("🧪 حيويّة · %-7s يحرّك %d من %d زوجِ زلّة %s"
              % (name, mv, len(Bb), "✅" if mv else "🚨"))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--selftest", action="store_true",
                    help="حارسُ حساب العتبة — بلا مصحفٍ ولا محرّك (ثوانٍ)")
    ap.add_argument("--control", action="store_true", help="الضوابطُ وحدَها")
    ap.add_argument("--limit", type=int, default=0, help="عددُ الآياتِ لكلِّ رواية (0 = المصحفُ كلُّه)")
    ap.add_argument("--examples", type=int, default=0)
    ap.add_argument("--no-real", action="store_true", help="بلا نصِّ التعرّف الحقيقيّ")
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(selftest())
    if a.control:
        control(a.limit or 400)
    else:
        measure(a.limit, a.examples, not a.no_real)
