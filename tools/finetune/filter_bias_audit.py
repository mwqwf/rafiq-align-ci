#!/usr/bin/env python3
"""⚖️ **هل تُصفّي عتبةُ `--min-match` ضجيجاً أم مِسطرةً؟** — يُقاس على المصحف كلِّه بلا صوتٍ ولا نموذج.

الخلفيّة: `finetune-filter.yml` يسقط من مجموعة v4 كلَّ مقطعٍ تطابقُه (`label_audit.match`) دون
`--min-match 0.85`. و`label_audit.match` يقارن **بتساوٍ صارم** مع صورةٍ واحدةٍ للكلمة، بينما
الحاكمُ المشحون يقبل صوراً أخرى (‏`scorer.variants` + `_riwaya_forms`: خنجريّةٌ اختيارية · صلةُ
ۦ/ۥ · النقل وصلةُ الميم في ورشٍ وقالون) أُضيفت **لأنّ whisper يكتبها**. فإن كتب القارئُ التامُّ
صورةً يقبلها الحاكمُ ويردُّها المدقِّق، هبط `match` بلا خطأ تلاوةٍ واحد.

والصورُ المقبولةُ ليست موزّعةً بالتساوي على الروايات (D-276: حفص 11.25٪ · قالون 20.40٪ ·
ورش 31.33٪ من الكلمات) ⇒ **العتبةُ الواحدة تُسقط ورشاً وقالون أكثرَ لسببٍ ليس ضجيجاً**، فتعيد
المجموعةَ نحوَ حفص — نقيضُ غرضِ v4 (‏بوّابةُ الاتّهام تُقاس في ورشٍ وقالون).

يقيس هذا الملفُّ الحدَّ الأعلى لذلك: القارئُ التامّ، والآيةُ نائبةٌ عن المقطع (مقاطعُ التدريب
مقصوصةٌ بالآية من فهارس التوقيت). ويفصل **صنفَ الخنجريّة** لأنّه وحدَه الصنفُ الذي يُعلم أنّ
whisper يكتب صورتَه غيرَ الصارمة (‏`ذَٰلِكَ` ⇜ «ذلك» لا «ذالك» — D-276)، فرقمُه **المتوقَّع** لا
الأعلى فحسب؛ وما عداه (‏الصلةُ والنقل) whisper يكتب فيه الصورةَ الصارمة غالباً فيُحسب حدّاً أعلى.

    python tools/finetune/filter_bias_audit.py [--min-match 0.85]
"""
import argparse, collections, os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tasmi_bench"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "alignment"))
import scorer                      # noqa: E402  مرآةُ الحاكم (يحرسها اختبارُ التماثل)
from common import load_text       # noqa: E402

RIWAYAT = ("hafs", "qalun", "warsh")


def cfg_for(riwaya):
    """إعدادُ المرآة بالرواية — حرفاً بحرفٍ كما في `make_parity_fixture.py` (وهو المقيسُ على المحرك)."""
    return scorer.Config(strip_yeh_barree=True, dagger_optional=True,
                         naql=riwaya == "warsh", sila=riwaya in ("warsh", "qalun"), mark_sila=True)


def word_classes(word, cfg):
    """أصنافُ الصور المقبولة لهذه الكلمة زيادةً على الصورة الصارمة (‏قد تجتمع)."""
    strict = scorer.norm(word, cfg)
    base = scorer.variants(word, cfg)
    full = scorer._riwaya_forms(base, cfg)
    cls = set()
    if any(f != strict for f in base):
        # الخنجريّةُ الاختيارية تُنتج الصورةَ الثانية؛ والصلةُ المرسومة تُنتج ما ينتهي بـي/و
        if "ٰ" in word and any(f != strict and not f.startswith(strict) for f in base):
            cls.add("dagger")
        if ("ۦ" in word or "ۥ" in word) and any(f != strict and f.startswith(strict) for f in base):
            cls.add("sila_mark")
    if any(f not in base for f in full):
        cls.add("riwaya")
    return cls


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-match", type=float, default=0.85)
    a = ap.parse_args()
    thr = a.min_match
    print(f"العتبة: {thr}  ·  الآيةُ نائبةٌ عن المقطع  ·  القارئُ التامّ (لا خطأ تلاوةٍ واحد)\n")
    rows = []
    for rw in RIWAYAT:
        cfg = cfg_for(rw)
        nw = amb = dag = 0
        cnt = collections.Counter()
        ay_tot = ay_any = ay_drop_all = ay_drop_dag = 0
        worst = []
        for ayah in load_text(rw):
            ws = ayah.split()
            if not ws:
                continue
            n = len(ws)
            d_all = d_dag = 0
            for w in ws:
                cls = word_classes(w, cfg)
                if cls:
                    d_all += 1
                    cnt.update(cls)
                    if "dagger" in cls:
                        d_dag += 1
            nw += n; amb += d_all; dag += d_dag
            ay_tot += 1
            ay_any += d_all > 0
            m_all, m_dag = 1 - d_all / n, 1 - d_dag / n
            ay_drop_all += m_all < thr
            ay_drop_dag += m_dag < thr
            if m_all < thr:
                worst.append((m_all, n, d_all, " ".join(ws)[:70]))
        rows.append((rw, nw, amb, dag, ay_tot, ay_any, ay_drop_all, ay_drop_dag, cnt, sorted(worst)[:3]))

    print(f"{'الرواية':8} {'كلمات':>7} {'ذاتُ صورٍ':>9} {'٪':>6} {'خنجريّة':>8} {'٪':>6}")
    for rw, nw, amb, dag, *_ in rows:
        print(f"{rw:8} {nw:7d} {amb:9d} {100*amb/nw:5.2f}٪ {dag:8d} {100*dag/nw:5.2f}٪")
    print(f"\nالآياتُ التي تسقط عند عتبة {thr} بسببِ المِسطرة وحدَها (لا ضجيج):")
    print(f"{'الرواية':8} {'آيات':>6} {'فيها ≥1':>9} {'٪':>6} {'تسقط (كلُّ الصور)':>18} {'٪':>6} {'تسقط (خنجريّة)':>16} {'٪':>6}")
    for rw, nw, amb, dag, ay_tot, ay_any, dall, ddag, cnt, _ in rows:
        print(f"{rw:8} {ay_tot:6d} {ay_any:9d} {100*ay_any/ay_tot:5.1f}٪ {dall:18d} {100*dall/ay_tot:5.2f}٪ "
              f"{ddag:16d} {100*ddag/ay_tot:5.2f}٪")
    print("\nتفصيلُ الأصناف (عددُ الكلمات في كلِّ صنف):")
    for rw, *_, cnt, worst in rows:
        print(f"  {rw:8} " + " · ".join(f"{k}={v}" for k, v in cnt.most_common()))
    print("\nأمثلةٌ من أسوأ الآيات (تطابقُها المتوقَّعُ للقارئ التامّ):")
    for rw, *_, worst in rows:
        for m, n, d, t in worst:
            print(f"  {rw:6} match={m:.2f} ({n-d}/{n})  {t}")


if __name__ == "__main__":
    main()
