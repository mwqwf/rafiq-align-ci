# -*- coding: utf-8 -*-
"""🧭🔁 هل طبقةُ **التصويت** في `QuranLocator` تتغيّر بتغيُّر الرواية؟ — يُجيب عنه بالقياس
لا بالظنّ، ويُغلق به البندُ الأخيرُ من قائمة D-428 (‏`make_locator_top_fixture` · D-436).

السؤالُ العمليّ: بصمةُ `locator_top_fixture.tsv` مبنيّةٌ على **حفصٍ وحدَه**، فوُسمت في تدقيق
السطح (D-428) بـ🚨 «نصٌّ ضيّق». وقبلَ أن تُوسَّع إلى ستٍّ يجب أن يُقاس: **هل التوسيعُ يشتري
حراسةً جديدة، أم ستَّ نسخٍ من البصمةِ نفسِها؟**

الطريقة (بلا صوتٍ ولا شبكة): تُحسب لكلِّ روايةٍ جدولةُ «رتبةِ الآية الصحيحة في `candidates`»
على المصحف كلِّه، ثمّ تُقارن الرواياتُ الخمسُ بحفصٍ في أربعةِ حقول: مجموعةُ المرشَّحات
(‏رتبة≠1) · الرتبةُ لكلِّ موضع · المرشَّحون الثلاثةُ الأوائل · صفةُ «متشابهةٌ تامّة».

⛔ والضابطُ السالبُ ليس زينة (‏D-279): `--control` يزرع عطباً في نصِّ روايةٍ واحدةٍ ثمّ يعيد
المقارنة؛ إن لم تصرخ فالمقارنةُ **لا ترى** ولا تصلح نتيجتُها الخضراءُ دليلاً.

  python tools/tasmi_bench/locator_riwaya_invariance.py [--control] [--limit N]

⚠️ الأرقامُ من المرآة البايثونية (`locator.py` · `scorer.py`) لا من المحرك — وللمقارنةِ النسبية.
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "tools", "alignment"))

import scorer  # noqa: E402
from common import load_text  # noqa: E402
from locator import Locator  # noqa: E402

# ⚠️ قائمةٌ محلّيّةٌ عن قصد: `riwaya_surface.RIWAYAT` ثلاثيّةٌ يرثها غيرُها (‏D-435) فلا تُوسَّع.
ALL_RIWAYAT = ("hafs", "warsh", "qalun", "shuba", "douri", "sousi")
BASE = "hafs"
FIELDS = ("المجموعة", "الرتبة", "المرشَّحون الثلاثة", "متشابهةٌ تامّة")


def rank_table(text, cfg, limit=0):
    """لكلِّ آية: رتبةُ نفسِها في مرشَّحي التصويت. يُعاد ما رتبتُه ≠ 1 فقط."""
    ayah_words = [a.split() for a in text]
    loc = Locator(ayah_words, cfg)
    n_all = len(ayah_words)

    # ⚠️ مفتاحُ «المتشابهاتِ التامّة» يُسقط الكلماتِ الفارغة (‏رموزُ الوقف ⇒ "") — وإلّا
    # فرّق فراغٌ زائدٌ بين آيتين متطابقتين نصّاً (‏D-438: 56 آيةً في الستِّ).
    def _key(ws):
        return " ".join(w for w in (scorer.norm(w2, cfg) for w2 in ws) if w)

    ident = {}
    for i, ws in enumerate(ayah_words):
        ident.setdefault(_key(ws), []).append(i)

    out = {}
    for f in range(n_all if not limit else min(limit, n_all)):
        core = [w for w in (scorer.norm(x, cfg) for x in text[f].split()) if w]
        core = core[loc.strip_preamble(core):]
        if len(core) < 2:
            continue
        order = [c[0] for c in loc.candidates(core)]
        r = order.index(f) + 1 if f in order else 0      # 0 = خارج الثمانية
        if r != 1:
            twin = len(ident[_key(ayah_words[f])]) > 1
            out[f] = (r, tuple(order[:3]), twin)
    return out


def compare(base, other):
    """يُعيد عدداً لكلِّ حقلٍ من حقول الاختلاف الأربعة."""
    ins = set(other) - set(base)
    out = set(base) - set(other)
    com = set(base) & set(other)
    return {
        "المجموعة": len(ins) + len(out),
        "الرتبة": sum(1 for f in com if base[f][0] != other[f][0]),
        "المرشَّحون الثلاثة": sum(1 for f in com if base[f][1] != other[f][1]),
        "متشابهةٌ تامّة": sum(1 for f in com if base[f][2] != other[f][2]),
    }


def plant_defect(text, every=300, head=4):
    """🧪 العطبُ المزروع — وشكلُه ليس اعتباطاً:

    ⛔ **المحاولةُ الأولى فشلت ويُحفظ سببُها**: زرعُ كلمةٍ غريبةٍ داخلَ آيةٍ لا يُرى البتّة،
    لأنّ `rank_table` تبني الفهرسَ من النصِّ نفسِه الذي تسأل به ⇒ الآيةُ المعطوبةُ تُطابق
    نفسَها فتبقى رتبتُها 1. فالعطبُ «ذاتيُّ الاتّساق» غيرُ مرئيٍّ بحكم البناء.

    ✅ **وما يُرى هو ما يُغيِّر العلاقةَ بين آيتين**: تُنسخ صدورُ آيةٍ (`head` كلمات) إلى آيةٍ
    أخرى ⇒ تشتركان في ثلاثيّاتٍ فتتزاحمان على الصدارة — وهي عينُ الآليّة التي تُنتج
    المرشَّحين. فإن لم تصرخ المقارنةُ لهذا فهي عمياءُ حقّاً."""
    t = list(text)
    hit = 0
    for f in range(0, len(t), every):
        donor = t[(f + 1777) % len(t)].split()
        ws = t[f].split()
        if len(ws) < head + 1 or len(donor) < head:
            continue
        t[f] = " ".join(donor[:head] + ws[head:])
        hit += 1
    return t, hit


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--control", action="store_true", help="🧪 الضابطُ السالب (‏D-279)")
    ap.add_argument("--limit", type=int, default=0, help="عددُ الآيات (0 = المصحفُ كلُّه)")
    args = ap.parse_args()

    cfg = scorer.DEFAULT
    base = rank_table(load_text(BASE), cfg, args.limit)
    print(f"# الأساس: {BASE} · مرشَّحاتٌ (رتبة≠1) {len(base)}")
    print(f"# {'رواية':10s}" + "".join(f"{h:>20s}" for h in FIELDS))

    total = {k: 0 for k in FIELDS}
    for riw in ALL_RIWAYAT:
        if riw == BASE:
            continue
        d = compare(base, rank_table(load_text(riw), cfg, args.limit))
        for k in FIELDS:
            total[k] += d[k]
        print(f"  {riw:10s}" + "".join(f"{d[k]:>20d}" for k in FIELDS))

    vote_fields = ("المجموعة", "الرتبة", "المرشَّحون الثلاثة")
    votes_same = all(total[k] == 0 for k in vote_fields)
    print(f"\n# 🧮 طبقةُ التصويت (‏المجموعة · الرتبة · المرشَّحون): "
          f"{'✅ لا تتغيّر بالرواية البتّة' if votes_same else '🚨 تتغيّر'}"
          f" — مجموعُ الفروق {sum(total[k] for k in vote_fields)}")
    print(f"# 🔀 وصفةُ «متشابهةٌ تامّة» تتغيّر: {total['متشابهةٌ تامّة']} موضعاً "
          f"(‏وهي خاصّةُ نصٍّ لا خاصّةُ مُوضِّع)")

    if args.control:
        planted, hit = plant_defect(load_text(BASE))
        d = compare(base, rank_table(planted, cfg, args.limit))
        screamed = sum(d[k] for k in vote_fields)
        print(f"\n# 🧪 الضابطُ السالب: عطبٌ مزروعٌ في {hit} آيةً من نصِّ {BASE}")
        print(f"#    " + " · ".join(f"{k}={d[k]}" for k in FIELDS))
        print(f"#    ⇒ {'✅ المقارنةُ تصرخ' if screamed else '🚨 المقارنةُ عمياء — لا يُعتدُّ بالأخضر أعلاه'}"
              f" (‏فروقُ التصويت {screamed})")
        if not screamed:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
