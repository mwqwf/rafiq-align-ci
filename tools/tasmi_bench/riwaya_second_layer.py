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


def run_detector(cases, out_tsv):
    """يبني الكاشفَ (‏Kotlin) ويشغّله. `cases`: (name, refWord, heard, riwaya, diffsEncoded)."""
    src = os.path.join(WORK, "cases_second_layer.tsv")
    os.makedirs(WORK, exist_ok=True)
    with io.open(src, "w", encoding="utf-8") as f:
        for row in cases:
            f.write("\t".join(row) + "\n")
    subprocess.run(["bash", os.path.join(HERE, "engine_judge", "build_and_run_slip.sh"),
                    src, out_tsv], check=True)
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


def main():
    ap = argparse.ArgumentParser(description="الطبقةُ الثانية: كاشفُ الانزلاق الروائيّ على المحرك")
    ap.add_argument("--limit", type=int, default=0, help="أوّل ن آية فقط (للتجربة)")
    ap.add_argument("--examples", type=int, default=6)
    ap.add_argument("--control", action="store_true", help="الضوابطُ وحدَها")
    args = ap.parse_args()
    os.makedirs(WORK, exist_ok=True)
    if args.control:
        return control(args.limit or 600)
    return measure(args.limit, args.examples)


if __name__ == "__main__":
    sys.exit(main())
