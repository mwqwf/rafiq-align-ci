# -*- coding: utf-8 -*-
"""🗣️ اختبارُ المقترَح المعلَّق في D-282 §4: **جدولُ التباسٍ صوتيٍّ ضيّق** بدلَ رخصةِ القصيرة.

ختم D-282 باقتراحٍ لم يُقَس: الثمانيةُ التي تنقذها رخصةُ الكلمة القصيرة «ربحاً خالصاً»
«كلُّها التباسُ حرفٍ واحدٍ متقاربِ المخرج (‏س⇄ت · ق⇄ه · ك⇄ج · ر⇄ل)» ⇒ فجدولُ التباسٍ
صوتيٍّ ضيّقٌ «يكسب الثمانيةَ ولا يفتح البابَ لـ`كما`⇄`ما`». **وهذا الملفُّ يقيس المقترَحَ
بدلَ أن يُصدِّقَه**، والميزانُ كاملٌ فيه: ما يكسب (على نصِّ تعرّفٍ حقيقيّ) وما يكلّف
(على المصحف كلِّه)، بالطريقتين المعتمدتين في D-282 وD-277 نفسِهما.

**الأذرع:**

    أ) المشحون                `short_cap=3`
    ب) رخصةٌ ≤2               `short_cap=2`
    ج) بلا رخصةٍ البتّة        `short_cap=0`
    د) جدولٌ **ضيّق**          `short_cap=0, phon="same"` — مخرجٌ واحد
    هـ) جدولٌ **موسَّع**        `short_cap=0, phon="adj"`  — مخرجٌ واحدٌ أو مجاور

والجدولُ (`scorer._MAKHARIJ`) مبنيٌّ على تقسيمِ المخارج المتعارَف **لا** على الحالات
المرادِ كسبُها — وإلا كان الجدولُ مفصَّلاً على مقاسِ عيّنته فلا يدلّ على شيء.

🔑 **مفتاحُ الأرقام** (‏كما في D-282): تلاواتُ الحزمتين صحيحةٌ (قرّاءُ مرجع) ⇒ كلُّ اتّهامٍ
مؤكَّدٍ فيهما **إنذارٌ كاذب**، وكلُّ كلمةٍ ينقذها ذراعٌ **إنذارٌ كاذبٌ مُنع**.
والتكلفةُ تُقاس بطريقة D-277: **كم موضعاً في المصحف يقبل كلمةً قرآنيةً أخرى؟**

الضوابط (‏قاعدةُ D-279):
  • **التصديق:** الذراعُ (أ) يعيد أحكامَ حزمة التماثل المصدَّقةِ على المحرك حرفاً بحرف.
  • **السالب:** `phon=None` يجب أن يعطي فرقَ **صفر** عن المشحون (وإلا فالمعلَمُ يسرّب)،
    وجدولٌ موسَّعٌ يجب أن يُحرّك عدّاداً (وإلا فالعدّادُ ميّت).

    python phonetic_license.py
    python phonetic_license.py --control --examples 30
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
import short_word_benefit as B  # noqa: E402

RIWAYAT = ("hafs", "warsh", "qalun")
CONFIRMED = B.CONFIRMED

# (المفتاح، العنوان، short_cap، phon)
ARMS = (
    ("a", "أ) المشحون", 3, None),
    ("b", "ب) رخصةٌ ≤2", 2, None),
    ("c", "ج) بلا رخصةٍ البتّة", 0, None),
    ("d", "د) جدولٌ ضيّق (مخرجٌ واحد)", 0, "same"),
    ("e", "هـ) جدولٌ موسَّع (مخرجٌ مجاور)", 0, "adj"),
)


def cfg_for(riwaya, short_cap=3, phon=None):
    """الإعدادُ المشحون لكلِّ رواية، بذراعِ الرخصة معلَماً."""
    return scorer.Config(naql=(riwaya == "warsh"), sila=(riwaya in ("warsh", "qalun")),
                         short_cap=short_cap, phon=phon)


def judge(rows, short_cap, phon, phon_cap=3):
    out = {}
    for r in rows:
        cfg = cfg_for(r["riwaya"], short_cap, phon)
        cfg.phon_cap = phon_cap
        words = r["ref"].split()
        res = scorer.score(words, r["hyp"], cfg)
        for i, (w, v) in enumerate(zip(words, res["words"])):
            out[(r["name"], i)] = (w, v[1], scorer.norm(w, cfg), v[2])
    return out


# ───────────────────────── التكلفة: طريقةُ D-277 على المصحف كلِّه ─────────────────────────

def exposure_all(riwaya, arms):
    """كم موضعاً مرجعيّاً يقبل **كلمةً قرآنيةً أخرى** تحت كلِّ ذراع؟ (طريقةُ D-277 حرفيّاً).

    الأذرعُ تُحسب في مرورٍ واحدٍ لأنّ صورَ الكلمة ومسافاتِها لا تتعلّق بالرخصة — الرخصةُ
    تقرأ المسافةَ ولا تصنعها؛ فيُحسب الجارُ مرّةً ويُسأل عنه خمسَ مرّات.
    """
    from common import load_text  # يُستورد هنا كي يبقى نصفُ الفائدة قابلاً للتشغيل بلا نصّ
    cfg0 = cfg_for(riwaya)
    ayat = load_text(riwaya)

    forms_of, vocab = {}, collections.Counter()
    for aya in ayat:
        for w in aya.split():
            if w not in forms_of:
                forms_of[w] = tuple(f for f in scorer._riwaya_forms(scorer.variants(w, cfg0), cfg0) if f)
            if forms_of[w]:
                vocab[forms_of[w][0]] += 1
    # المرشَّحون: كلُّ صورةٍ قد تقبل بديلاً — والرخصتان كلتاهما محصورتان بـ≤3.
    cand = [v for v in vocab if len(v) <= 3]

    # جيرانُ كلِّ صورةٍ على مسافةِ حرفٍ واحد، مع بيانِ أهو إبدالُ حرفٍ في الموضع نفسِه.
    pairs = collections.defaultdict(list)
    for i, r in enumerate(cand):
        for h in cand[i + 1:]:
            if abs(len(r) - len(h)) > 1 or scorer._edit(r, h) != 1:
                continue
            pairs[r].append(h)
            pairs[h].append(r)

    out = {}
    for key, _, cap, phon in arms:
        cfg = cfg_for(riwaya, cap, phon)
        accepts = {}
        for r, alts in pairs.items():
            keep = [h for h in alts
                    if (max(len(r), len(h)) <= cfg.short_cap) or scorer._phon_ok(r, h, cfg)]
            if keep:
                accepts[r] = sorted(keep, key=lambda h: -vocab[h])
        occ = exposed = hit_ayat = 0
        hot = collections.Counter()
        for aya in ayat:
            touched = False
            for w in aya.split():
                occ += 1
                fs = forms_of[w]
                alt = next((f for f in fs if accepts.get(f)), None)
                if alt:
                    exposed += 1
                    touched = True
                    hot[alt] += 1
            if touched:
                hit_ayat += 1
        out[key] = dict(occ=occ, exposed=exposed, ayat=len(ayat), hit_ayat=hit_ayat,
                        accepts=accepts, vocab=vocab, hot=hot)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--examples", type=int, default=25)
    ap.add_argument("--control", action="store_true")
    ap.add_argument("--skip-cost", action="store_true", help="نصفُ الفائدة وحدَه (أسرع)")
    args = ap.parse_args()

    rows = B.load_fixture() + B.load_long()
    by_riw = collections.Counter(r["riwaya"] for r in rows)
    print("## نصفُ الفائدة — على نصِّ تعرّفٍ حقيقيّ مودَع")
    print(f"الحزمة: {len(rows)} حالةً — " + " · ".join(f"{k} {v}" for k, v in sorted(by_riw.items())))

    base = judge(rows, 3, None)
    words_n = len(base)
    total, bad = B.validate(rows, base)
    print(f"✅ ضابطُ التصديق: {total - bad}/{total} حكماً مطابقاً لأحكامِ الحزمة "
          f"(المصدَّقةِ على المحرك) — انحرافٌ {bad}")
    if bad:
        print("🚨 انحرافٌ في الذراع المشحون ⇒ كلُّ ما تحته ساقط.")
        return 1

    conf0 = sum(1 for _, v, _, _ in base.values() if v in CONFIRMED)
    print(f"أرضيّةُ الإنذار الكاذب في المشحون: {conf0}/{words_n} "
          f"({100*conf0/max(words_n,1):.2f}٪)\n")
    vocab = B.mushaf_vocab()

    lost_by_arm = {}
    print(f"{'الذراع':34s} {'إنذاراتٌ كاذبةٌ جديدة':>22s} {'جملةً':>10s} {'الفرق':>9s}")
    for key, name, cap, phon in ARMS:
        arm = judge(rows, cap, phon)
        lost, _ = B.diff(base, arm)
        lost_by_arm[key] = lost
        conf = sum(1 for _, v, _, _ in arm.values() if v in CONFIRMED)
        newfa = "—" if key == "a" else f"{len(lost)} ({100*len(lost)/words_n:.2f}٪)"
        print(f"{name:34s} {newfa:>22s} {100*conf/words_n:>9.2f}٪ "
              f"{100*(conf-conf0)/words_n:>+8.2f}")

    # ما الذي يستردّه الجدولُ ممّا يخسره «بلا رخصة»؟
    lost_c = {k for k, *_ in [(l[0], ) for l in lost_by_arm["c"]]}
    for key in ("d", "e"):
        lost_k = {l[0] for l in lost_by_arm[key]}
        got = lost_c - lost_k
        title = dict((k, n) for k, n, _, _ in ARMS)[key]
        print(f"\n=== {title}: يستردّ {len(got)} من {len(lost_c)} كلمةً يخسرها «بلا رخصة» ===")
        by_key = {l[0]: l for l in lost_by_arm["c"]}
        for k in sorted(got, key=lambda k: str(k)):
            _, w, n, heard, _ = by_key[k]
            mark = "🚨 كلمةٌ قرآنيةٌ أخرى" if heard in vocab else "ربحٌ خالص"
            print(f"    {w}  («{n}») ⇐ سُمعت «{heard}»   [{mark}]")
        miss = lost_k & lost_c
        print(f"  وما يبقى مفقوداً: {len(miss)}")
        for k in sorted(miss, key=lambda k: str(k))[:args.examples]:
            _, w, n, heard, _ = by_key[k]
            print(f"    {w}  («{n}») ⇐ سُمعت «{heard}»")

    if args.control:
        print("\n=== الضابطُ السالب ===")
        same = judge(rows, 3, None)
        _, m = B.diff(base, same)
        print(f"  ذراعٌ مطابقٌ (‏cap=3, phon=None): فرقٌ {sum(m.values())} "
              f"(يجب 0){' ✅' if not m else ' 🚨'}")
        keep = judge(rows, 3, "adj")
        _, m2 = B.diff(base, keep)
        n2 = sum(m2.values())
        print(f"  🔎 المشحون + الجدولُ فوقَه: فرقٌ {n2} — و**صفرُه هو الصواب**: الجدولُ "
              f"إبدالُ حرفٍ في كلمةٍ ≤3 ⇒ مجموعةٌ جزئيّةٌ من الرخصة العمياء لا زيادةٌ عليها"
              f"{' ✅' if n2 == 0 else ' 🚨 (فالجدولُ يقبل ما ترفضه العمياء ⇒ راجعه)'}")
        # فالعدّادُ يُختبر حيث يمكن أن يتحرّك: توسيعُ سقفِ الجدول وحدَه فوق «بلا رخصة».
        none0 = judge(rows, 0, None)
        c0 = sum(1 for _, v, _, _ in none0.values() if v in CONFIRMED)
        prev = None
        for cap in (3, 5, 9):
            arm = judge(rows, 0, "adj", phon_cap=cap)
            c = sum(1 for _, v, _, _ in arm.values() if v in CONFIRMED)
            print(f"  جدولٌ موسَّعٌ بسقفِ ≤{cap} فوق «بلا رخصة»: اتّهامٌ {c} (كان {c0})"
                  f"{' ✅' if c < c0 and (prev is None or c <= prev) else ' 🚨'}")
            prev = c
        print("  (‏ثباتُه فوق ≤3 متوقَّع: عتبةُ الخُمس تقبل حرفاً في كلمةٍ من خمسةٍ فصاعداً "
              "⇒ فلا يبقى للجدول ما يكسبه هناك)")

    if args.skip_cost:
        return 0

    print("\n## نصفُ التكلفة — طريقةُ D-277 على المصحف كلِّه")
    print(f"{'الرواية':8s} " + " ".join(f"{n.split(')')[0]+')':>14s}" for _, n, _, _ in ARMS))
    hot_d = {}
    for riwaya in RIWAYAT:
        res = exposure_all(riwaya, ARMS)
        cells = []
        for key, _, _, _ in ARMS:
            r = res[key]
            cells.append(f"{100*r['exposed']/r['occ']:>13.2f}٪")
        print(f"{riwaya:8s} " + " ".join(cells))
        hot_d[riwaya] = res["e"]
    if args.examples:
        r = hot_d["hafs"]
        print("\nأكثرُ ما يتعرّض تحت الجدول الموسَّع (حفص) — الصورةُ ← ما يُقبل مكانَها:")
        for form, cnt in r["hot"].most_common(min(args.examples, 12)):
            alts = "، ".join(f"{h}(×{r['vocab'][h]})" for h in r["accepts"].get(form, [])[:6])
            print(f"    {form:4s} (×{cnt:5d}) ← {alts}")
    print("(‏النسبةُ = مواضعُ المصحف التي تقبل **كلمةً قرآنيةً أخرى** بسبب الرخصة)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
