# -*- coding: utf-8 -*-
"""🔬 **لماذا يعمى ورشٌ وقالون عن الانزلاق إلى حفص — ومَن يملك إصلاحَه** (‏D-281).

⚠️ **لِمَ وُجد:** قاست مناوبةُ D-280 السقفَ فوجدته منهاراً: **ورشٌ ⇜ حفص 0.3٪ · قالون ⇜ حفص
0.8٪**. وعلّقت السببَ على «قرارِ تصميمٍ في ملفّ الرواية: `naql` و`sila` والخنجريّةُ الاختيارية
تولّد صوراً تبتلع صورةَ حفصٍ نفسَها»، ثمّ أوصت الجلسةَ المحلّية بألّا تضيّق الملفّ لأنّ **ما
تشتريه** بالتضييق لا يظهر إلا على صوتٍ حقيقيّ. فبقي السؤالُ الذي يقرّر كلَّ شيءٍ بلا جواب:

    لو ضُيِّق الملفُّ إلى آخره — **كم يُسترَدّ من الكشف أصلاً؟** وكم يكلّف؟

وهذا يُقاس بلا صوتٍ وبلا شبكة، **على المحرك نفسِه** (‏`engine_judge/` ‏D-279)، لأنّ عَلَمَي
`naql` و`silaMeem` في `RiwayaProfile` موجودان في المحرك مضبوطَين على ثلاث تشكيلاتٍ جاهزة:

    hafs  · naql=✗ sila=✗   ⇐ استئصالُ العلمين معاً
    qalun · naql=✗ sila=✓   ⇐ استئصالُ النقل وحدَه
    warsh · naql=✓ sila=✓   ⇐ المشحون

فيُحكم نصُّ ورشٍ **بملفّ روايةٍ أخرى** فيصير الاستئصالُ قياساً على كودٍ مشحونٍ لم يُمَسّ حرفُه.

الذراعان (بناءُ الحالات من `riwaya_surface.py` نفسِه — مصدرٌ واحدٌ للقاعدة):

    ب · زلّةٌ روائيةٌ بكلمةٍ واحدة (‏E ⇜ حفص) ⇒ **ما يُسترَدّ** من الكشف
    أ · تلاوةٌ تامّةُ الصحّة بروايتها     ⇒ **ما يُدفَع** من الاتّهام الكاذب

⭐ وفوقهما **الإسناد**: لكلِّ زلّةٍ فاتت، أيُّ صورةٍ من صور الكلمة ابتلعت المسموع؟ الرسمُ
نفسُه (‏`norm` لا تفرّق بين الروايتين أصلاً) أم صورةٌ عامّةٌ (خنجريّة · ۦ/ۥ) أم صورةُ نقلٍ
أو صلة أم رخصةُ مطابقةٍ (الخُمس · القصيرةُ ≤3 · ‏D-277)؟ فما ابتلعه **الرسمُ نفسُه**
لا يستردّه تضييقُ ملفٍّ البتّة — وهذا هو الفرقُ بين «عطبٍ يُصلَح» و«سقفٍ يُلتَفّ عليه».

⚠️ **المسموعُ هنا صورةُ whisper الحتميّة** (`parity_full.whisper_forms`) لا تعرّفٌ حقيقيّ:
أرقامُ الذراع (أ) **حدٌّ أدنى** للكلفة، وأرقامُ (ب) مطلقةٌ صحيحة (نصٌّ إلى نصّ).

    python tools/tasmi_bench/riwaya_ablation.py --attribute-only   # الإسناد وحدَه (ثوانٍ)
    python tools/tasmi_bench/riwaya_ablation.py                    # الاستئصال + الإسناد
    python tools/tasmi_bench/riwaya_ablation.py --limit 600
"""
import argparse
import collections
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "tools", "alignment"))
import scorer  # noqa: E402
import parity_full as P  # noqa: E402
import riwaya_surface as R  # noqa: E402

WORK = R.WORK

# ملفَّاتُ الرواية في المحرك بعَلَمَيها — الاستئصالُ اختيارُ ملفٍّ لا تعديلُ كود.
SETTINGS = (("warsh", "naql=✓ sila=✓ (المشحون لورش)"),
            ("qalun", "naql=✗ sila=✓ (استئصالُ النقل)"),
            ("hafs",  "naql=✗ sila=✗ (استئصالُ العلمين)"))
SHIPPED = {"warsh": "warsh", "qalun": "qalun"}


def build_pairs(limit=0):
    """ذراعُ (ب) لزوجَي الاهتمام وحدَهما + ذراعُ (أ) لروايتَيهما."""
    text = {r: R.prepare(r, limit) for r in R.RIWAYAT}
    a_cases, b_cases = [], []
    for e in ("warsh", "qalun"):
        for a, (ayah, ww, real) in enumerate(text[e]):
            if real:
                a_cases.append(("a|%s|%s|%05d|0" % (e, e, a), ayah, " ".join(ww), e))
        s = "hafs"
        for a in range(len(text[e])):
            ayah, ww, real_e = text[e][a]
            _, ws, real_s = text[s][a]
            if len(real_e) != len(real_s) or not real_e:
                continue
            for ie, isx in zip(real_e, real_s):
                alt = ws[isx]
                if alt == ww[ie]:
                    continue
                hyp = ww[:ie] + [alt] + ww[ie + 1:]
                b_cases.append(("b|%s|%s|%05d|%d" % (e, s, a, ie), ayah, " ".join(hyp), e))
    return a_cases, b_cases


def judge(cases, setting, tag):
    """يحكم الحالاتِ بملفّ رواية `setting` — العمودُ الرابعُ وحدَه يتغيّر."""
    swapped = [(n, ref, hyp, setting) for (n, ref, hyp, _r) in cases]
    return R.run_engine(swapped, os.path.join(WORK, "engine_ablation_%s.tsv" % tag))


def measure(a_cases, b_cases, setting):
    """يعيد لكلِّ روايةٍ: (كُشف, زلّات) و(متّهَم, كلمات) تحت هذا الملفّ."""
    out = {}
    eng_b = judge(b_cases, setting, "b_" + setting)
    eng_a = judge(a_cases, setting, "a_" + setting)
    for e in ("warsh", "qalun"):
        det = n = 0
        for name, ref, hyp, _r in b_cases:
            if name.split("|")[1] != e:
                continue
            got = eng_b.get(name)
            if got is None:
                continue
            verdicts, adds = got
            i = int(name.split("|")[4])
            n += 1
            if (i < len(verdicts) and verdicts[i] != "C") or adds:
                det += 1
        acc = words = 0
        cfg = P.config_for(e)
        for name, ref, hyp, _r in a_cases:
            if name.split("|")[1] != e:
                continue
            got = eng_a.get(name)
            if got is None:
                continue
            verdicts, adds = got
            real = [j for j, t in enumerate(ref.split()) if scorer.norm(t, cfg)]
            words += len(real)
            acc += sum(1 for j in real if j < len(verdicts) and verdicts[j] != "C") + len(adds)
        out[e] = (det, n, acc, words)
    return out


# ═══════════ الإسناد: أيُّ صورةٍ ابتلعت المسموع؟ ═══════════
CATS = ("الرسمُ نفسُه (‏norm واحدة للروايتين)", "صورةٌ عامّة (خنجريّة · ۦ/ۥ)",
        "صورةُ النقل", "صورةُ الصلة", "رخصةُ الخُمس", "رخصةُ القصيرة (‏≤3 · D-277)",
        "المحاذاة/الدمج (لا صورةَ بعينها)")


_NAQL = scorer.Config(naql=True, sila=False)
_SILA = scorer.Config(naql=False, sila=True)


def attribute(ref_tok, heard, cfg):
    """أوّلُ صورةٍ من صور الكلمة تبتلع `heard` — بالترتيب: الرسمُ ⇐ عامّة ⇐ نقل ⇐ صلة ⇐ رخصة."""
    plain = scorer.variants(ref_tok, cfg)
    riw = scorer._riwaya_forms(plain, cfg)
    if plain and plain[0] == heard:
        return CATS[0]
    if heard in plain[1:]:
        return CATS[1]
    if heard in riw:
        if cfg.naql and heard in scorer._riwaya_forms(plain, _NAQL):
            return CATS[2]
        if cfg.sila and heard in scorer._riwaya_forms(plain, _SILA):
            return CATS[3]
        return CATS[2]
    for r in riw:
        n, d = max(len(r), len(heard)), scorer._edit(r, heard)
        if d * cfg.match_den <= cfg.match_num * n:
            return CATS[4]
        if n <= 3 and d <= 1:
            return CATS[5]
    return CATS[6]


def run_attribution(b_cases, eng, limit_examples=4):
    per = {e: collections.Counter() for e in ("warsh", "qalun")}
    ex = {}
    for name, ref, hyp, _r in b_cases:
        got = eng.get(name)
        if got is None:
            continue
        verdicts, adds = got
        _arm, e, _s, _a, i = name.split("|")
        i = int(i)
        if (i < len(verdicts) and verdicts[i] != "C") or adds:
            continue                      # كُشفت — ليست موضعَ إسناد
        cfg = P.config_for(e)
        toks = ref.split()
        heard = hyp.split()
        if i >= len(toks) or i >= len(heard):
            continue
        c = attribute(toks[i], heard[i], cfg)
        per[e][c] += 1
        ex.setdefault((e, c), []).append((toks[i], heard[i]))
    return per, ex


def pct(a, b):
    return 100.0 * a / b if b else 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="عددُ الآيات (0 = المصحف كلُّه)")
    ap.add_argument("--attribute-only", action="store_true")
    args = ap.parse_args()

    a_cases, b_cases = build_pairs(args.limit)
    print("حالات: ذراعُ (أ) %d · ذراعُ (ب) %d" % (len(a_cases), len(b_cases)))

    eng_shipped = judge(b_cases, "warsh", "b_attr_warsh")
    eng_q = judge([c for c in b_cases if c[0].split("|")[1] == "qalun"], "qalun", "b_attr_qalun")
    merged = dict(eng_shipped)
    merged.update(eng_q)                  # كلُّ روايةٍ بملفّها المشحون
    per, ex = run_attribution([c for c in b_cases], merged)
    print("\n=== إسنادُ الزلّات الفائتة (كلُّ روايةٍ بملفّها المشحون) ===")
    for e in ("warsh", "qalun"):
        tot = sum(per[e].values())
        print("  %s · فات %d" % (e, tot))
        for c, n in per[e].most_common():
            s = ex.get((e, c), [])[:2]
            print("     %-42s %6d (%5.1f٪)  %s" % (c, n, pct(n, tot),
                  " · ".join("%s⇜%s" % (a, b) for a, b in s)))

    if args.attribute_only:
        return
    print("\n=== الاستئصال على المحرك ===")
    rows = {}
    for setting, label in SETTINGS:
        rows[setting] = measure(a_cases, b_cases, setting)
        for e in ("warsh", "qalun"):
            det, n, acc, words = rows[setting][e]
            print("  %-6s · ملفّ %-6s %-28s كشف %6d/%6d (%5.2f٪) · اتّهامٌ كاذب %6d/%7d (%.3f٪)"
                  % (e, setting, label, det, n, pct(det, n), acc, words, pct(acc, words)))


if __name__ == "__main__":
    main()
