# -*- coding: utf-8 -*-
"""🔁 بصمةُ **المتشابهاتِ التامّة** (البند 5 في `QuranLocator`) — حارسُ عطبِ D-438.

**العطب:** رمزُ الوقف (`ۖ ۚ ۗ ۞`) كلمةٌ مستقلّةٌ في المصحف تُطبَّع إلى `""`. وكان يبقى في
مفتاح فهرس المتشابهات فيُخلّف **فراغاً زائداً**: `خالدين فيها␣␣لا` ≠ `خالدين فيها␣لا`
وهما آيتان **متطابقتان حرفاً بحرف**. ومسارُ التفريغ كان يُسقط الفوارغ أصلاً ⇒ عدمُ تناظرٍ
بين جانبَي المقارنة لا قاعدةٌ مقصودة. المقيسُ قبلَ الإصلاح: **56 آيةً في الرواياتِ الستِّ**
تختفي عن الفهرس فتخرج `alternatives` فارغةً وللآية شريكٌ حقيقيّ.

**ولمَ روايتان في البصمة؟ — والفرضيّةُ الأولى كُذِّبت بالتجربة فتُحفظ (‏D-439):**
الاختيارُ آليٌّ: **أقلُّ الحالات التي تُغطّي كلَّ صنفٍ (رمزُ وقفٍ · موضعُه) موجودٍ في الستِّ**
⇒ خرج `hafs×3 · warsh×1`، وهو **أصغرُ** من ستِّ حالاتٍ حفصيّةٍ كان عليها أوّلاً.

🚨 **لكنّ تعليلي لإدخال ورشٍ كان خطأً، وقد جُرِّب فسقط:** ظننتُ أنّ موضعَ **النهاية**
(‏لا يقع إلا في ورشٍ وقالون) يحرس ما لا يحرسه حفص، لأنّ الفارغَ في الوسط يُخلّف فراغاً
**مزدوجاً** وفي النهاية **ذيليّاً**. فزُرع إصلاحٌ جزئيٌّ يطوي المزدوجَ وحدَه ⇒ **سقطت حالةُ
حفصٍ ومرَّت حالةُ ورشٍ خضراء** — عكسَ المتوقَّع تماماً.

**والسببُ أنّ المِسطرةَ ليست موضعَ الفارغ بل تناظرُ التوأمَين:** ورشٌ فيه `۞` **في طرفَي
المجموعة كلِّها** فالفراغُ الذيليُّ يقع على جانبَي المقارنة معاً **فيُلغي أثرَه**؛ وحفصٌ فيه
آيةٌ تحمل `۞` وتوأمُها لا يحمله ⇒ **عدمُ تناظرٍ يفضح أيَّ إصلاحٍ ناقص**.

⇒ **ما ثبت:** الإصلاحان الجزئيّان المحتملان (‏طيُّ المزدوج · `trim`) **يفضحهما حفصٌ وحدَه**.
**وما لم يثبت:** أنّ لحالةِ ورشٍ قدرةَ كشفٍ تنفرد بها — تبقى **تغطيةَ صنفٍ لا حارساً مُثبَتاً**،
ولا يُدّعى لها غيرُ ذلك.

  python tools/tasmi_bench/make_locator_twin_fixture.py [--check]

⚠️ الأرقامُ من المرآة البايثونية (`locator.py`) — والبصمةُ تُلزم المحركَ بها حرفاً بحرف.
⛔ لا تُحرَّر يدوياً.
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
from common import load_text  # noqa: E402
from locator import Locator  # noqa: E402

OUT = os.path.join(ROOT, "engine", "recitation", "src", "test", "resources",
                   "locator_twin_fixture.tsv")

# ⚠️ قائمةٌ محلّيّةٌ عن قصد: `riwaya_surface.RIWAYAT` ثلاثيّةٌ يرثها غيرُها (‏D-435) فلا تُوسَّع.
ALL_RIWAYAT = ("hafs", "warsh", "qalun", "shuba", "douri", "sousi")
WINDOW = 1   # آيةٌ قبلَ كلِّ معنيّةٍ وبعدَها (سياقُ التوالي يدخل البصمة كما هو)


def key(words, cfg, drop_blank):
    g = (scorer.norm(w, cfg) for w in words)
    return " ".join(w for w in g if w) if drop_blank else " ".join(
        scorer.norm(w, cfg) for w in words)


def classes(words, cfg):
    """أصنافُ (رمزٌ فارغ · موضعُه) في الآية — وهي ما تُغطّيه البصمة."""
    n = len(words)
    out = set()
    for i, w in enumerate(words):
        if scorer.norm(w, cfg) == "" and w.strip():
            out.add((w, "بداية" if i == 0 else "نهاية" if i == n - 1 else "وسط"))
    return out


def victims(riwaya, cfg):
    """آياتٌ يجمعها المفتاحُ الصحيحُ (بإسقاط الفوارغ) ويُفرِّقها القديم ⇒ ضحايا D-438."""
    text = load_text(riwaya)
    fixed, raw = collections.defaultdict(list), collections.defaultdict(list)
    for i, a in enumerate(text):
        fixed[key(a.split(), cfg, True)].append(i)
        raw[key(a.split(), cfg, False)].append(i)
    out = []
    for i, a in enumerate(text):
        if len(fixed[key(a.split(), cfg, True)]) > 1 and len(raw[key(a.split(), cfg, False)]) == 1:
            out.append((i, fixed[key(a.split(), cfg, True)]))
    return text, out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="تحقّقٌ بلا كتابة")
    args = ap.parse_args()
    cfg = scorer.DEFAULT

    # ① كلُّ الضحايا في الستِّ، وأصنافُ كلِّ ضحيّة
    pool = {}
    want = set()
    for riw in ALL_RIWAYAT:
        text, vs = victims(riw, cfg)
        pool[riw] = (text, vs)
        for f, _ in vs:
            want |= classes(text[f].split(), cfg)
    print(f"# أصنافٌ (رمز · موضع) في الرواياتِ الستِّ: {len(want)} — {sorted(want)}")

    # ② اختيارٌ جشعٌ: أقلُّ الحالاتِ التي تُغطّي كلَّ صنف (حفصٌ أوّلاً لأنّه أغنى الرموز)
    chosen = collections.defaultdict(list)
    remaining = set(want)
    for riw in ALL_RIWAYAT:
        text, vs = pool[riw]
        for f, group in sorted(vs):
            gain = classes(text[f].split(), cfg) & remaining
            if gain:
                chosen[riw].append((f, group))
                remaining -= gain
        if not remaining:
            break
    if remaining:
        raise SystemExit(f"🚨 أصنافٌ بلا حارس: {sorted(remaining)}")
    print(f"# اختير: " + " · ".join(f"{r}×{len(v)}" for r, v in chosen.items()))

    # ③ التوليد: كتلةٌ لكلِّ روايةٍ مختارة
    blocks = []
    for riw, vs in chosen.items():
        text = pool[riw][0]
        keep = sorted({g + d for f, grp in vs for g in grp
                       for d in range(-WINDOW, WINDOW + 1) if 0 <= g + d < len(text)})
        remap = {f: i for i, f in enumerate(keep)}
        loc = Locator([text[f].split() for f in keep], cfg)
        rows = []
        for f, grp in vs:
            r = loc.locate(text[f])
            if r is None:
                raise SystemExit(f"🚨 {riw}/{f}: لا موضعَ لها في العيّنة المصغّرة")
            group = sorted({remap[g] for g in grp if g in remap})
            wanted = [g for g in group if g != r["start"]]
            if r["alternatives"] != wanted or not wanted:
                raise SystemExit(f"🚨 {riw}/{f}: البدائل {r['alternatives']} ≠ المنتظر {wanted}")
            # 👁️ شاهدُ العضّ: القاعدةُ القديمةُ تُفرِّق بين البدايةِ وبديلها
            inv = {v: k for k, v in remap.items()}
            for alt in wanted:
                if key(text[inv[r["start"]]].split(), cfg, False) == \
                        key(text[inv[alt]].split(), cfg, False):
                    raise SystemExit(f"🚨 {riw}/{f}: الحالةُ لا تعضُّ")
            cls = sorted(classes(text[f].split(), cfg))
            print(f"  ✅ {riw:6s} {f:5d}→{remap[f]:3d} · start={r['start']:3d} · "
                  f"بدائل={r['alternatives']} · أصناف={cls}")
            rows.append((text[f], remap[f], r["start"], wanted))
        blocks.append((riw, keep, text, rows))

    if args.check:
        return
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("# بصمةُ المتشابهاتِ التامّة (QuranLocator البند 5 · حارسُ D-438) — "
                 "تُولَّد بـ tools/tasmi_bench/make_locator_twin_fixture.py · ⛔ لا تُحرَّر يدوياً\n")
        fh.write("# كلُّ حالةٍ كانت تُرجع بدائلَ فارغةً قبلَ الإصلاح. والرواياتُ هنا ليست "
                 "تكثيراً: هي أقلُّ ما يُغطّي كلَّ صنفٍ (رمزُ وقفٍ · موضعُه) في الستِّ — "
                 "والنهايةُ لا تقع إلا في ورشٍ وقالون (D-439).\n")
        fh.write("# A\t<الرواية>\t<فهرسٌ في العيّنة>\t<فهرسُ المصحف>\t<نصُّ الآية>\n")
        fh.write("# C\t<الرواية>\t<التفريغ>\t<فهرسُ الآية>\t<البدايةُ المنتظرة>\t<البدائلُ بفاصلة>\n")
        for riw, keep, text, rows in blocks:
            for i, f in enumerate(keep):
                fh.write(f"A\t{riw}\t{i}\t{f}\t{text[f]}\n")
            for hyp, own, start, wanted in rows:
                fh.write(f"C\t{riw}\t{hyp}\t{own}\t{start}\t{','.join(str(x) for x in wanted)}\n")
    print(f"# كُتب {OUT} · كتلٌ {len(blocks)} · "
          f"حالاتٌ {sum(len(b[3]) for b in blocks)}")


if __name__ == "__main__":
    main()
