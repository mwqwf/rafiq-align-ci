# -*- coding: utf-8 -*-
"""🔀 **البابُ الثاني: كم يردّ `RiwayaSlipDetector` من العمى الروائيّ؟** — بلا صوت.

⚠️ **لِمَ وُجد.** كلُّ رقمِ عمىً في اللوحة (‏D-281 · D-285 · D-286) قِيس على **بابِ القبول
وحدَه** (`RecitationScorer`)، وخلصت D-286 إلى أنّ «العمى الروائيَّ لا يُعالَج من باب القبول».
وبقي السؤالُ الذي يليه بلا جواب: **فمن أيِّ بابٍ يُعالَج؟** وفي المحرّك بابٌ ثانٍ موضوعٌ
لهذا بعينِه — `RiwayaSlipDetector` (‏D-248) — **لم يُقَس قطّ**. وأقصى ما قيل فيه سطرٌ في
`riwaya_surface.py --why` يعدّ مواضعَ الفرش ويسمّي نفسَه صراحةً **«سقفَ تغطيةٍ لا تغطية»**،
لأنّ كونَ الموضع فرشاً شرطٌ لازمٌ لا كافٍ. هذا الملفُّ يحوّل السقفَ إلى **عدٍّ حقيقيّ**: يسأل
الكاشفَ نفسَه — الكوتلن المشحون على JVM — عن كلِّ حالةٍ واحدةً واحدة.

**والعملةُ عملةُ D-286 نفسُها** فتُقارن الأرقامُ مباشرةً:

    الفائدة = زلّةٌ روائيةٌ حقيقيةٌ عمِيَ عنها بابُ القبول ⇒ يردّها البابُ الثاني
              (‏على المصحف كلِّه · الاتّجاهاتُ الستّة · 71,254 زوجاً)
    التكلفة = انزلاقٌ يُتَّهم به مَن تلا **صحيحاً بروايته** ⇒ أرضيّةُ اتّهامٍ كاذبٍ للباب الثاني
              (‏على المصحف كلِّه · ثلاثُ رواياتٍ · 232,288 موضعاً)

🔒 **وفرقٌ لا بدّ من تسميته:** الكاشفُ في التطبيق **لا يُسأل عن كلِّ كلمة**. جسرُ
`app/.../RiwayaSlips.kt` يصفّيه أوّلاً: `words.filter { verdict == SUBSTITUTED || UNCERTAIN }`.
فالكلمةُ التي حكم عليها بابُ القبول `CORRECT` — أي **العمياءُ بعينِها** — لا تصل الكاشفَ أصلاً.
لذلك يُعَدُّ هنا عدّان: **الكاشفُ مجرَّداً** (لو سُئل) و**الكاشفُ كما هو موصولٌ اليوم**؛
والفرقُ بينهما ثمنُ تلك المصفاة بعينِه.

    python tools/tasmi_bench/riwaya_second_layer.py --control   # 🧪 الضوابطُ أوّلاً
    python tools/tasmi_bench/riwaya_second_layer.py             # المصحف كلُّه

⚠️ يلزم مخرَجُ الطبقة الأولى `work/engine_riwaya_surface.tsv` (‏`riwaya_surface.py --arms b`).
⛔ لا يُمَسّ ملفُّ محرّكٍ على القرص، ولا يُغيَّر افتراضٌ مشحون: قياسٌ وتقريرٌ لا غير.
"""
import argparse
import collections
import gzip
import io
import itertools
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "tools", "alignment"))
import scorer  # noqa: E402
import parity_full as P  # noqa: E402
import riwaya_surface as RS  # noqa: E402  (‏مصدرٌ واحدٌ لبناء الحالات والصور)
from common import load_text  # noqa: E402

RIWAYAT = RS.RIWAYAT                 # الروايات المقيسة (لها نصٌّ كامل)
ALL_RIWAYAT = RS.ALL_RIWAYAT         # الروايات الستُّ التي يعرفها الكاشف
FARSH_DIR = RS.FARSH_DIR
WORK = RS.WORK
FS1, FS2 = "", ""        # فاصلا حقول الفروق — لا يقعان في نصٍّ عربيّ
FOREIGN = P.FOREIGN


def farsh_diffs():
    """‏آيةٌ (‏0-based) ⇒ {رواية: [(فهرسُ كلمة حفص، كلمةُ حفص، كلمةُ الرواية)]} — كما يقرؤها التطبيق."""
    per = collections.defaultdict(dict)
    for r in ALL_RIWAYAT:
        if r == "hafs":
            continue
        path = os.path.join(FARSH_DIR, "farsh_%s.jz" % r)
        d = json.loads(gzip.open(path, "rt", encoding="utf-8").read())
        for a, lst in d["diffs"].items():
            # ⛔ صفوفٌ فيها كلمةٌ خالية (‏3 لكلِّ رواية · 12 في المصحف كلِّه) تُسقَط: نوعُ
            # `FarshRepository.Diff` في `core/` يعلنها `String` غيرَ خالية أصلاً.
            rows = [(int(it[0]), it[1], it[2]) for it in lst
                    if it[1] is not None and it[2] is not None]
            if rows:
                per[int(a) - 1][r] = rows       # مفتاحُ الملفّ 1-based ⇒ فهرسُ `load_text` 0-based
    return per


def encode(rows_by_riwaya):
    return FS1.join(FS2.join((r, str(i), hw, ow))
                    for r, rows in rows_by_riwaya.items() for (i, hw, ow) in rows)


def run_detector(cases, out_tsv, cap=3):
    """يبني الكاشفَ (‏Kotlin) ويشغّله. `cases`: (name, refWord, heard, riwaya, diffsEncoded).

    `cap` (‏D-610): سقفُ «رخصة الكلمة القصيرة» في النسخة المبنيّة — **3 هو المشحون**
    والمسارُ حينها هو المسارُ القديمُ بحذافيره. وما عداه يبني من نسخةٍ مرقَّعةٍ في `work/`.
    ⛔ ولا يُمَسّ ملفُّ المحرك على القرص.
    """
    src = os.path.join(WORK, "cases_second_layer.tsv")
    os.makedirs(WORK, exist_ok=True)
    with io.open(src, "w", encoding="utf-8") as f:
        for row in cases:
            f.write("\t".join(row) + "\n")
    env = dict(os.environ, SHORT_CAP=str(cap))
    subprocess.run(["bash", os.path.join(HERE, "engine_judge", "build_and_run_slip.sh"),
                    src, out_tsv], check=True, env=env)
    got = {}
    for line in io.open(out_tsv, encoding="utf-8"):
        if not line.strip():
            continue
        f = line.rstrip("\n").split("\t")
        got[f[0]] = f[1]                        # "-" أو قائمةُ الرواياتِ التي تقرأ ما سُمع
    return got


def layer1():
    """أحكامُ الطبقة الأولى لذراع (ب) — تُقرأ من مخرَج `riwaya_surface.py --arms b`."""
    path = os.path.join(WORK, "engine_riwaya_surface.tsv")
    if not os.path.isfile(path):
        print("🚨 لا مخرَجَ للطبقة الأولى: شغّل `riwaya_surface.py --arms b` أوّلاً.")
        return None
    eng = {}
    for line in io.open(path, encoding="utf-8"):
        f = line.rstrip("\n").split("\t")
        if f and f[0].startswith("b|"):
            eng[f[0]] = (f[1], (f[2] if len(f) > 2 else "").split())
    return eng


def build_slips(limit=0, foreign=False, blind_diffs=False):
    """ذراعُ الزلّة: مرجعُ E وكلمةٌ واحدةٌ سُمعت بصورة S — أسماءٌ مطابقةٌ لأسماء `riwaya_surface`."""
    text = {r: RS.prepare(r, limit) for r in RIWAYAT}
    raw = {r: [a.split() for a in load_text(r)[:limit or None]] for r in RIWAYAT}
    diffs = farsh_diffs()
    cases = []
    for e, s in itertools.permutations(RIWAYAT, 2):
        for a in range(len(text[e])):
            _, ww, real_e = text[e][a]
            _, ws, real_s = text[s][a]
            if len(real_e) != len(real_s) or not real_e:
                continue
            enc = "" if blind_diffs else encode(diffs.get(a, {}))
            for ie, isx in zip(real_e, real_s):
                alt = FOREIGN if foreign else ws[isx]
                if alt == ww[ie]:
                    continue                    # لا زلّةَ: الروايتان تتّفقان
                cases.append(("b|%s|%s|%05d|%d" % (e, s, a, ie),
                              raw[e][a][ie], alt, e, enc))
    return cases


def build_floor(limit=0):
    """ذراعُ الأرضيّة: تلاوةٌ **صحيحةٌ تامّة** بروايتها — كلُّ اتّهامِ انزلاقٍ هنا كاذبٌ أرضيّ."""
    text = {r: RS.prepare(r, limit) for r in RIWAYAT}
    raw = {r: [a.split() for a in load_text(r)[:limit or None]] for r in RIWAYAT}
    diffs = farsh_diffs()
    cases = []
    for r in RIWAYAT:
        for a in range(len(text[r])):
            _, ww, real = text[r][a]
            enc = encode(diffs.get(a, {}))
            for i in real:
                cases.append(("f|%s|%s|%05d|%d" % (r, r, a, i),
                              raw[r][a][i], ww[i], r, enc))
    return cases


def pct(a, b):
    return 100.0 * a / b if b else 0.0


def measure(limit=0, examples=6):
    eng = layer1()
    if eng is None:
        return 1
    slips = build_slips(limit)
    print("حالاتُ الزلّة: %d" % len(slips))
    det = run_detector(slips, os.path.join(WORK, "slip_second_layer.tsv"))

    acc = collections.defaultdict(lambda: dict(n=0, l1=0, blind=0, l2=0, gated=0,
                                               l2_on_l1=0, m_only=0))
    found = []
    for name, ref, heard, riw, _enc in slips:
        got = eng.get(name)
        if got is None:
            continue
        verdicts, adds = got
        _arm, e, s, _a, i = name.split("|")
        i = int(i)
        v = verdicts[i] if i < len(verdicts) else "?"
        caught1 = (v != "C") or bool(adds)
        fired2 = det.get(name, "-") != "-"
        k = acc[(e, s)]
        k["n"] += 1
        k["l1"] += 1 if caught1 else 0
        if not caught1:
            k["blind"] += 1
            if fired2:
                k["l2"] += 1                    # يردّها الكاشفُ **لو سُئل**
                # مصفاةُ `RiwayaSlips.forAyah`: لا يُسأل إلا عن S/U ⇒ والحكمُ هنا C
                k["gated"] += 1
                if len(found) < 400:
                    found.append((name, ref, heard, det[name]))
        else:
            if fired2:
                k["l2_on_l1"] += 1
            if v == "M" and not fired2:
                k["m_only"] += 1

    tot = collections.Counter()
    print("\n=== ما يردّه البابُ الثاني من عمى بابِ القبول (‏على المصحف كلِّه) ===")
    for (e, s) in sorted(acc):
        k = acc[(e, s)]
        for key in ("n", "l1", "blind", "l2", "gated", "l2_on_l1"):
            tot[key] += k[key]
        print("  %-6s ⇜ %-6s  زلّات %6d · كشفُ الطبقة١ %5d · عمياء %5d"
              "  ⇒ يردّها الكاشفُ %4d (%5.1f٪ من العمياء)"
              % (e, s, k["n"], k["l1"], k["blind"], k["l2"], pct(k["l2"], k["blind"])))
    print("  %-15s زلّات %6d · كشفُ الطبقة١ %5d · عمياء %5d ⇒ يردّها الكاشفُ %4d (%.1f٪)"
          % ("المجموع", tot["n"], tot["l1"], tot["blind"], tot["l2"],
             pct(tot["l2"], tot["blind"])))
    print("  🔒 ومنها ما تحجبه مصفاةُ `RiwayaSlips.forAyah` اليوم (‏الحكمُ CORRECT ⇒ لا يُسأل): "
          "%d من %d" % (tot["gated"], tot["l2"]))
    print("  ↔️ وعلى ما كشفته الطبقةُ الأولى أصلاً يوافقها الكاشفُ في %d حالة (‏تسميةٌ لا كشف)."
          % tot["l2_on_l1"])

    floor = build_floor(limit)
    print("\nحالاتُ الأرضيّة (تلاوةٌ صحيحة): %d" % len(floor))
    fd = run_detector(floor, os.path.join(WORK, "slip_floor.tsv"))
    fa = collections.Counter()
    fa_ex = []
    for name, ref, heard, riw, _enc in floor:
        if fd.get(name, "-") != "-":
            fa[riw] += 1
            if len(fa_ex) < 10:
                fa_ex.append((name, ref, heard, fd[name]))
        fa[(riw, "n")] += 1
    print("\n=== أرضيّةُ الاتّهام الكاذب للباب الثاني (‏مَن تلا صحيحاً بروايته) ===")
    tn = tb = 0
    for r in RIWAYAT:
        n = fa[(r, "n")]
        tn += n
        tb += fa[r]
        print("  %-6s  مواضع %7d · اتُّهم بانزلاق %5d (%.3f٪)" % (r, n, fa[r], pct(fa[r], n)))
    print("  %-6s  مواضع %7d · اتُّهم بانزلاق %5d (%.3f٪)" % ("المجموع", tn, tb, pct(tb, tn)))

    print("\n=== أمثلةٌ · زلّةٌ عمياءُ يردّها الكاشف ===")
    for name, ref, heard, ids in found[:examples]:
        print("  %s · مرجع «%s» · سُمع «%s» ⇒ روايةُ %s" % (name, ref, heard, ids))
    if fa_ex:
        print("\n=== أمثلةٌ · اتّهامٌ كاذبٌ أرضيّ ===")
        for name, ref, heard, ids in fa_ex[:examples]:
            print("  %s · مرجع «%s» · سُمع «%s» ⇒ نُسب إلى %s" % (name, ref, heard, ids))
    return 0


def control(limit=600):
    """🧪 الضوابطُ (‏قاعدةُ D-279: حارسٌ لا يسقط على عطبٍ مزروعٍ لا يُصدَّق أخضرُه).

    ١ · **حيويّةُ العدّاد:** زلّةٌ حقيقيةٌ في مواضع الفرش ⇒ يجب أن يفتح الكاشفُ كثيراً.
    ٢ · **سالبٌ · بلا فرش:** الحالاتُ نفسُها وفروقُها مُفرَغة ⇒ يجب **0** (لا تخمينَ بلا فرش).
    ٣ · **سالبٌ · كلمةٌ غريبة:** «الحاسوب» مكانَ المسموع ⇒ يجب **0** أو ما يقاربه،
         فالغريبةُ خطأٌ لا انزلاق؛ وأيُّ فتحٍ هنا اتّهامٌ بلا سند.
    """
    a = build_slips(limit)
    b = build_slips(limit, blind_diffs=True)
    c = build_slips(limit, foreign=True)
    n1 = sum(1 for v in run_detector(a, os.path.join(WORK, "ctl_slip_a.tsv")).values() if v != "-")
    n2 = sum(1 for v in run_detector(b, os.path.join(WORK, "ctl_slip_b.tsv")).values() if v != "-")
    n3 = sum(1 for v in run_detector(c, os.path.join(WORK, "ctl_slip_c.tsv")).values() if v != "-")
    print("\n🧪 الضوابط (‏أوّلُ %d آية · %d حالة):" % (limit, len(a)))
    print("  ١ حيويّة  · زلّةٌ حقيقية      ⇒ فتح الكاشفُ %5d (%.1f٪)" % (n1, pct(n1, len(a))))
    print("  ٢ سالب    · بلا فروقِ فرش    ⇒ فتح %5d (يجب 0)" % n2)
    print("  ٣ سالب    · كلمةٌ غريبة      ⇒ فتح %5d (يجب 0)" % n3)
    ok = n1 >= 20 and n2 == 0 and n3 == 0
    print("  %s" % ("✅ العدّادُ حيٌّ ولا يفتح بلا سند" if ok
                    else "🚨 ضابطٌ سقط — لا يُوثق برقمٍ من هذا العدّاد"))
    return 0 if ok else 1


def cap_arm(cap=2, limit=0):
    """🔬 **ذراعُ سقف «رخصة الكلمة القصيرة» على الحاكم الذي تحيا فيه** (‏D-610).

    ⭐⭐ **ولِمَ هنا لا هناك:** `short_word_engine_arms` يقيس على `EngineJudge` الذي يترجم
    `RecitationScorer` وحدَه ⇒ الحكمُ من `score()` و`strictShort` صادقٌ افتراضاً
    (`criticalPairsUncertain = true`) ⇒ **شقُّ الرخصة لا يُبلَغ والذراعُ خرساء** (‏D-609:
    السقوفُ 2 و3 و9 بمخرَجٍ واحدٍ بايتاً بايت). وهنا يُترجَم `RiwayaSlipDetector` الذي ينادي
    `looseMatch` (‏`strictShort = false`) ⇒ **الرخصةُ حيّة**.

    ⛔ **والضابطُ قبلَ الرقم لا بعدَه:** سقفُ **9** يجب أن **يحرّك** أحكاماً؛ فإن لم يحرّك
    فالذراعُ ميتةٌ هنا أيضاً ⇒ **يُعلَن ولا يُنشر جدول**، ورمزُ الخروج **2** لا 0.
    """
    slips = build_slips(limit)
    print("حالاتُ الزلّة: %d (‏limit=%s)" % (len(slips), limit or "المصحف كلُّه"))

    base = run_detector(slips, os.path.join(WORK, "caparm_c3.tsv"), cap=3)
    live = run_detector(slips, os.path.join(WORK, "caparm_c9.tsv"), cap=9)
    moved9 = sum(1 for n in base if base.get(n) != live.get(n))
    print("%s ضابطُ الحيويّة: رخصةٌ موسَّعة (3⇐9) ⇒ اختلف %d حكماً (يجب > 0)"
          % ("✅" if moved9 > 0 else "🚨", moved9))
    if moved9 == 0:
        print("\n🚨🚨 **الذراعُ ميتةٌ على هذا الحاكم أيضاً — جرى ولم يَقِسْ شيئاً.**\n"
              "   ⛔ فلا جدولَ ولا رقم، والبابُ يبقى مفتوحاً حتّى يُوجد حاكمٌ تحيا فيه الرخصة.")
        return 2

    arm = run_detector(slips, os.path.join(WORK, "caparm_c%d.tsv" % cap), cap=cap)
    moved = sum(1 for n in base if base.get(n) != arm.get(n))

    # 🚨 والكلفةُ تُقاس **قبل** أن تُسمّى الفائدةُ مجّانيّة: أرضيّةُ الاتّهام الكاذب
    #    (‏تلاوةٌ صحيحةٌ تامّةٌ بروايتها — كلُّ اتّهامٍ هنا كاذبٌ أرضيّ).
    floor = build_floor(limit)
    f_b = run_detector(floor, os.path.join(WORK, "caparm_floor_c3.tsv"), cap=3)
    f_a = run_detector(floor, os.path.join(WORK, "caparm_floor_c%d.tsv" % cap), cap=cap)
    fb = sum(1 for v in f_b.values() if v != "-")
    fa = sum(1 for v in f_a.values() if v != "-")
    new_false = [n for n in f_b if f_b.get(n) == "-" and f_a.get(n, "-") != "-"]
    print("\n🚨 **أرضيّةُ الاتّهام الكاذب** (‏%d حالةَ تلاوةٍ صحيحة): %d ⇐ %d (‏%+d) · "
          "اتّهاماتٌ **جديدة** %d"
          % (len(floor), fb, fa, fa - fb, len(new_false)))
    fidx = {c[0]: c for c in floor}
    for n in new_false[:6]:
        _nm, ref, heard, riw, _e = fidx[n]
        print("    🚨 %-28s %-10s %s ⇜ %s" % (n, riw, ref, heard))
    opened_b = sum(1 for v in base.values() if v != "-")
    opened_a = sum(1 for v in arm.values() if v != "-")
    gain = [n for n in base if base.get(n) == "-" and arm.get(n, "-") != "-"]
    lost = [n for n in base if base.get(n) != "-" and arm.get(n, "-") == "-"]

    print("\n=== سقفُ %d (المشحون) ⇐⇒ سقفُ %d (الذراع) — على حالاتِ الزلّة عينِها ===" % (3, cap))
    print("  فتح الكاشفُ: %d ⇐ %d (‏فرقٌ %+d)" % (opened_b, opened_a, opened_a - opened_b))
    print("  ✅ زلّةٌ صارت **تُكشف** بالذراع: %d" % len(gain))
    print("  ⛔ زلّةٌ كانت تُكشف فـ**ضاعت**: %d" % len(lost))
    print("  (‏أحكامٌ تغيّرت جملةً: %d)" % moved)
    idx = {c[0]: c for c in slips}
    for label, names in (("✅ صارت تُكشف", gain), ("⛔ ضاعت", lost)):
        for n in names[:6]:
            _nm, ref, heard, riw, _e = idx[n]
            print("    %-28s %-10s %s ⇜ %s" % (n, riw, ref, heard))
        if names:
            print("    %s: %d" % (label, len(names)))
    print("\n⚠️ **وحدُّه:** هذه **الطبقةُ الثانية** (كشفُ الانزلاق الروائيّ) لا مسارُ حكم التسميع —"
          "\n   فحكمُ `score()` لا يتغيّر بالسقف أصلاً (‏D-609). ⛔ ولا قرارَ شحنٍ من هنا.")
    return 0


def farsh_index_audit(limit=0):
    """⭐⭐ **بأيِّ ترقيمٍ يعدُّ `hafsWordIdx` كلماتِ الآية؟** (‏D-505 · قِيس على المصحف كلِّه)

    الرقمُ يُمرَّر إلى الكاشف كما هو، **والكلمةُ التي يقصدها ليست الكلمةَ التي يجدها** إن
    اختلف الترقيم — فيُقابَل حرفُ الله بغير موضعه. والجوابُ مقيسٌ لا مظنون، على
    **220,672 صفَّ فرشٍ** في الروايات الخمس:

    | الترقيم | يطابق رسمَ حفصٍ في |
    |---|---:|
    | رموزُ الآية كما تنقسم بالفراغ (‏فيها علاماتُ الوقف `ۛ`) | **64.106٪** |
    | ⭐ **الكلماتُ الحقيقيّةُ وحدَها** (‏ما لا يفرغ بعد `norm`) | **100.000٪** (0 مخالف · 0 خارجَ المدى) |

    ⇒ `hafsWordIdx` **ترتيبُ الكلمة الحقيقيّة**، وعلاماتُ الوقف **لا تُعَدّ**. ومثالُه من
    البقرة 2: `ذَٰلِكَ ٱلْكِتَٰبُ لَا رَيْبَ ۛ فِيهِ ۛ هُدًۭى` — الرقمُ 5 **هُدًۭى** لا `فِيهِ`.
    ⛔ ومَن رقّم بالرموز أزاح ثلثَ المواضع وهو يظنّ نفسَه مصيباً.

    ومفتاحُ الآية في الملفّ **1-based** ويُطرح منه واحدٌ عند القراءة: وبإزاحةِ آيةٍ واحدةٍ
    تسقط المطابقةُ إلى **1.13٪** ⇒ الطرحُ صحيحٌ ومقيسٌ لا منقول.

    يردّ: (‏صفوفٌ · مطابقٌ بترقيم الكلمات الحقيقيّة · مطابقٌ بترقيم الرموز).
    """
    per = farsh_diffs()
    hafs = [a.split() for a in load_text("hafs")]
    cfg = P.config_for("hafs")
    rows = real_ok = tok_ok = 0
    for a, by_r in per.items():
        if limit and a >= limit:
            continue
        toks = hafs[a]
        real = [j for j, t in enumerate(toks) if scorer.norm(t, cfg)]
        for _r, lst in by_r.items():
            for (i, hw, _ow) in lst:
                rows += 1
                want = scorer.norm(hw, cfg)
                if i < len(real) and scorer.norm(toks[real[i]], cfg) == want:
                    real_ok += 1
                if i < len(toks) and scorer.norm(toks[i], cfg) == want:
                    tok_ok += 1
    return rows, real_ok, tok_ok


def _selftest_farsh(say):
    """فحوصُ الترقيم الثلاثةُ — تلزمها بياناتُ `tools/quraat/farsh/out` (ليست في المرآة العامّة)."""
    # ①⭐⭐ الترقيم: الكلماتُ الحقيقيّةُ تطابق تماماً، والرموزُ **لا** — فالمسطرةُ تميّز
    rows, real_ok, tok_ok = farsh_index_audit(limit=400)
    say(rows > 5000 and real_ok == rows and tok_ok < rows,
        "⭐⭐ `hafsWordIdx` ترتيبُ الكلمة الحقيقيّة: %d/%d مطابقاً · وبترقيم الرموز %d فقط"
        % (real_ok, rows, tok_ok))

    # ② ومفتاحُ الآية 1-based: الإزاحةُ بواحدٍ تُسقط المطابقةَ — فالطرحُ ليس زينة
    per = farsh_diffs()
    hafs = [a.split() for a in load_text("hafs")]
    cfg = P.config_for("hafs")
    shifted = tried = 0
    for a in sorted(per)[:400]:
        b = a + 1
        if b >= len(hafs):
            continue
        real = [j for j, t in enumerate(hafs[b]) if scorer.norm(t, cfg)]
        for _r, lst in per[a].items():
            for (i, hw, _ow) in lst:
                tried += 1
                if i < len(real) and scorer.norm(hafs[b][real[i]], cfg) == scorer.norm(hw, cfg):
                    shifted += 1
    say(tried > 1000 and shifted < tried * 0.10,
        "وبإزاحةِ الآية واحدةً تسقط المطابقةُ إلى %d من %d — فالمفتاحُ 1-based والطرحُ صحيح"
        % (shifted, tried))

    # ③ الصفوفُ الخاليةُ تُسقَط بعددٍ معلوم — وصفٌّ خالٍ يمرّ يكسر نوعَ `Diff` في المحرك
    dropped = 0
    for r in ALL_RIWAYAT:
        if r == "hafs":
            continue
        path = os.path.join(FARSH_DIR, "farsh_%s.jz" % r)
        d = json.loads(gzip.open(path, "rt", encoding="utf-8").read())
        dropped += sum(1 for lst in d["diffs"].values() for it in lst
                       if it[1] is None or it[2] is None)
    kept = sum(len(lst) for by_r in per.values() for lst in by_r.values())
    say(dropped == 12 and all(hw and ow for by_r in per.values() for lst in by_r.values()
                              for (_i, hw, ow) in lst),
        "الصفوفُ الخاليةُ مُسقَطةٌ: %d (والباقي %d صفّاً كلُّها ذاتُ كلمتَين)" % (dropped, kept))



def _selftest_cases(say):
    """فحوصُ بناء الحالات — تلزمها بياناتُ الفرش أيضاً (`build_slips` يقرؤها).""" 
    # ⑤⭐ مفتاحُ الالتحام: أسماءُ الحالات **هي هي** في الطبقتين — وإلّا قُرئ صمتُ العدّاد خُضرةً
    mine = {c[0] for c in build_slips(limit=25)}
    theirs = {c[0] for c in RS.build(limit=25, arms="b")}
    say(mine and mine == theirs,
        "⭐ أسماءُ الحالات مطابقةٌ لطبقة `riwaya_surface` (‏%d حالة · فرق %d)"
        % (len(mine), len(mine ^ theirs)))

    # ⑥ الضابطُ «بلا فرش» يُفرغ الفرشَ **كلَّه** ولا يمسّ شيئاً آخر
    a = build_slips(limit=25)
    b = build_slips(limit=25, blind_diffs=True)
    say(all(x[4] == "" for x in b) and any(x[4] for x in a)
        and [x[:4] for x in a] == [x[:4] for x in b],
        "🧪 ضابطُ «بلا فرش» يُفرغ الفرشَ وحدَه (‏غيرُ الفارغ في الأصل %d)"
        % sum(1 for x in a if x[4]))

    # ⑦ وضابطُ الكلمة الغريبة يزرعها في **المسموع** لا في المرجع
    c = build_slips(limit=25, foreign=True)
    names_a, names_c = {x[0] for x in a}, {x[0] for x in c}
    say(all(x[2] == FOREIGN for x in c) and all(x[1] != FOREIGN for x in c)
        and names_a < names_c,
        "🧪 وضابطُ الكلمة الغريبة يزرع «%s» في المسموع وحدَه" % FOREIGN)
    # ⚠️ ومجتمعُه **أوسعُ عمداً**: شرطُ «الروايتان تتّفقان» لا يُسقط شيئاً والغريبةُ تُزرع في
    # كلّ كلمةٍ حقيقيّة ⇒ فنسبتُه تُقرأ من مقامه هو لا من مقام الذراع (‏%d مقابل %d).
    say(len(names_c) > len(names_a),
        "ومقامُه أوسعُ عمداً: %d موضعاً مقابل %d — فلا تُقسَم أرقامُه على مقام الذراع"
        % (len(names_c), len(names_a)))

    # ⑧ ذراعُ الأرضيّة **تلاوةٌ صحيحةٌ فعلاً** — لا صورةُ روايةٍ أخرى بالخطإ
    floor = build_floor(limit=15)
    good = 0
    for name, ref, heard, riw, _enc in floor:
        forms = P.whisper_forms(ref, P.config_for(riw))
        good += 1 if heard == forms[-1] else 0
    say(floor and good == len(floor) and all(c[0].startswith("f|") for c in floor),
        "أرضيّةُ الاتّهام تلاوةٌ صحيحةٌ بروايتها: %d/%d" % (good, len(floor)))



def selftest():
    """🧪 **حارسُ الطبقة الثانية** (‏D-505) — والضابطُ الأصليُّ فيها ثقيلٌ (يبني الكاشفَ
    بالكوتلن ثلاثَ مرّات) فلا يُشعَل في كلّ دفعة، وهذا يفحص في ثانيةٍ ما لا يفحصه هو:

    ⭐⭐ **ترقيمُ كلمة الفرش** — أخطرُ سطرٍ هنا: رقمٌ يُقابَل بغير موضعه يقيس سورةً بأخرى.
    ⭐ **مفتاحُ الالتحام مع الطبقة الأولى** — لو اختلف حرفٌ في اسم الحالة لصار
      `eng.get(name)` فارغاً **فتُقرأ «صفرُ عمياء» بشارةً** وهي صمتُ عدّادٍ لا خُضرة.
    ⭐ **الضابطان السالبان يفعلان ما يدّعيان** — إفراغُ الفرش وزرعُ الكلمة الغريبة.
    """
    ok = True

    def say(good, line):
        nonlocal ok
        ok &= bool(good)
        print(("✅ " if good else "❌ ") + line)

    # ⛔ بياناتُ الفرش (`tools/quraat/farsh/out`) ليست في مرآة الحوسبة العامّة — ففحوصُ
    # الترقيم الثلاثةُ **تُعلَن غيرَ مفحوصةٍ هناك بالنصّ**، ولا تُعَدّ نجاحاً صامتاً.
    have_farsh = all(os.path.isfile(os.path.join(FARSH_DIR, "farsh_%s.jz" % r))
                     for r in ALL_RIWAYAT if r != "hafs")
    if have_farsh:
        _selftest_farsh(say)
        _selftest_cases(say)
    else:
        print("⚠️ **بياناتُ الفرش غائبةٌ في هذه النسخة** (‏%s) ⇒ **ثمانيةُ فحوصٍ لم تُجرَ هنا**\n"
              "   (ترقيمُ كلمة الفرش · مفتاحُ الآية · الصفوفُ الخالية · مفتاحُ الالتحام ·\n"
              "    الضابطان السالبان · ذراعُ الأرضيّة) — وموضعُها **مستودعُ الأصل**، وقد جرت\n"
              "   فيه. ⛔ وهذا إعلانٌ بالنصّ لا نجاحٌ صامت." % FARSH_DIR)
    # ④ الفاصلان **لا يقعان في نصٍّ عربيّ** — وإلّا انشقّ صفٌّ في منتصفه فصار رقماً كلمةً
    body = "".join(load_text("hafs")[:500]) + "".join(load_text("warsh")[:500])
    say(FS1 not in body and FS2 not in body and FS1 != FS2,
        "فاصلا الحقول %r و%r لا يقعان في المصحف" % (FS1, FS2))
    enc = encode({"warsh": [(3, "أ", "ب"), (7, "ج", "د")]})
    back = [tuple(x.split(FS2)) for x in enc.split(FS1)]
    say(back == [("warsh", "3", "أ", "ب"), ("warsh", "7", "ج", "د")],
        "والترميزُ يُفكّ كما رُكّب: %r" % (back,))

    # ⑨ عتباتُ الضابط لم تُليَّن (‏⛔ العلاجُ عيّنةٌ أكبر لا عتبةٌ أصغر)
    src = io.open(os.path.abspath(__file__), encoding="utf-8").read()
    say("ok = n1 >= 20 and n2 == 0 and n3 == 0" in src,
        "⛔ عتبةُ الضابط كما هي: حيويّةٌ ≥20 · والسالبان **صفرٌ** لا «قليل»")

    # ⑩ حارسُ مصدرٍ على الرقم الذي بُني عليه الحكم
    doc = farsh_index_audit.__doc__
    say(all(k in doc for k in ("100.000", "64.106", "220,672", "1.13")),
        "حارسُ مصدر: أرقامُ الترقيم الثلاثةُ في التوثيق")

    # ⑪⭐⭐ ذراعُ السقف (‏D-610): الضابطُ **قبل** الرقم · والكلفةُ مع الفائدة · والترقيعُ يفشل صراحةً
    say('env = dict(os.environ, SHORT_CAP=str(cap))' in src,
        "⭐ سقفُ الذراع يُمرَّر إلى سيرِ البناء (‏نسخةٌ مرقَّعةٌ في `work/` لا مساسَ بالمحرك)")
    say(src.index("ضابطُ الحيويّة") < src.index("سقفُ %d (المشحون)"),
        "⛔⛔ والضابطُ يُقرأ **قبل** الجدول في المتن نفسِه — لا بعدَه")
    say("if moved9 == 0:" in src and "return 2" in src,
        "⛔ وذراعٌ لا تتحرّك بسقف 9 ⇒ **رمزُ الخروج 2** (‏جرى ولم يَقِسْ) لا 0 — درسُ D-609")
    say("build_floor(limit)" in src and "أرضيّةُ الاتّهام الكاذب" in src
        and src.index("f_a = run_detector") < src.index("=== سقفُ %d (المشحون)"),
        "🚨⭐⭐ والكلفةُ (‏أرضيّةُ الاتّهام الكاذب) تُقاس **قبل** أن تُسمّى الفائدةُ مجّانيّة")

    sh = os.path.join(HERE, "engine_judge", "build_and_run_slip.sh")
    if os.path.isfile(sh):
        t = io.open(sh, encoding="utf-8").read()
        say('if t.count(old) != 1:' in t and "sys.exit(" in t,
            "⛔ وسيرُ البناء **يخرج بخطإٍ** إن لم تكن مرساةُ الترقيع فريدة")
        say('old, new = "n <= 3 && d <= 1"' in t,
            "والمرساةُ عينُ مرساة `build_and_run.sh` — مصدرٌ واحدٌ لا مرساتان تتباعدان")
        say('SHORT_CAP="${SHORT_CAP:-3}"' in t and 'if [ "$SHORT_CAP" != "3" ]' in t,
            "والافتراضُ **3 = المشحون** ⇒ المسارُ القديمُ بحذافيره حين لا تُطلب ذراع")
        say('"$SRC/RiwayaSlipDetector.kt"' in t,
            "⭐⭐ ويُترجَم `RiwayaSlipDetector` معه — **وهو علّةُ حياة الرخصة هنا** (`looseMatch`)")
    else:
        print("⚠️ **سيرُ بناء الكاشف غيرُ موجود** ⇒ أربعةُ فحوصٍ لم تُجرَ — ⛔ إعلانٌ لا صمت.")

    print("\n%s" % ("✅ حارسُ الطبقة الثانية: تمّ" if ok else "❌ حارسُ الطبقة الثانية: أخفق"))
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description="الطبقةُ الثانية: كاشفُ الانزلاق الروائيّ على المحرك")
    ap.add_argument("--limit", type=int, default=0, help="أوّل ن آية فقط (للتجربة)")
    ap.add_argument("--examples", type=int, default=6)
    ap.add_argument("--control", action="store_true", help="الضوابطُ وحدَها")
    ap.add_argument("--audit-index", action="store_true",
                    help="بأيِّ ترقيمٍ يعدُّ `hafsWordIdx` الكلمات؟ — جردٌ على المصحف بلا كاشف")
    ap.add_argument("--selftest", action="store_true", help="🧪 حارسُ الأداة (ثانيةٌ · بلا كاشف)")
    ap.add_argument("--cap-arm", type=int, metavar="N", default=0,
                    help="🔬 ذراعُ سقف رخصة القصيرة على هذا الحاكم (‏D-610) — الضابطُ قبل الرقم")
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    if args.audit_index:
        rows, real_ok, tok_ok = farsh_index_audit(args.limit)
        print("صفوفُ الفرش %d · بترقيم الكلمات الحقيقيّة %d (%.3f٪) · بترقيم الرموز %d (%.3f٪)"
              % (rows, real_ok, pct(real_ok, rows), tok_ok, pct(tok_ok, rows)))
        return 0
    os.makedirs(WORK, exist_ok=True)
    if args.control:
        return control(args.limit or 600)
    if args.cap_arm:
        return cap_arm(args.cap_arm, args.limit)
    return measure(args.limit, args.examples)


if __name__ == "__main__":
    sys.exit(main())
