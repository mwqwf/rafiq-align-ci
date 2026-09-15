#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""🧪 تدقيقُ المِسطرة **بالحكم لا بالشكل** — وعلى الرواياتِ الستِّ لا الثلاث (‏D-426)

## عطبان في الفحص القائم، لا في المِسطرة
تدقيقُ المِسطرة (‏`T=3` في `docs/ops/CLOUD_DUTY_PROMPT.md`) هو أنفعُ ما يُفعَل بلا عتاد — وبه
وُجد D-274 وD-275. لكنّ فيه اثنتين:

1. **يدور على ثلاثِ رواياتٍ من ستّ** (`for riw in ("hafs","warsh","qalun")`) ⇒ **شعبةُ
   والدوريُّ والسوسيُّ لم تدخل هذا الفحصَ قطّ**، وهي التي انفردت في D-401 بأسوأ الأرضيّات.
2. **و‍يُبلِّغ عن الشكل لا عن الأثر:** يطبع كلَّ صورةٍ فيها «اا» أو «يي» أو بقايا، ثمّ يُترك
   الحكمُ لعينِ القارئ. **والشكلُ المريبُ ليس عطباً حتّى يُتَّهم به قارئٌ صحيحُ التلاوة.**
   (‏مثالُه `يَٰٓأَيُّهَا ⇒ ياايها`: صورةٌ لا يكتبها أحد، **ومع ذلك حكمُها `CORRECT`** لأنّ
   مسارَ الدمج ١↔٢ يبتلع «يا»+«ايها».)

## ما يفعله هذا الملفّ
لكلِّ صورةٍ مريبةٍ يبني **مسموعاً هو الإملاءُ الحديثُ لها**، ويُجري الحاكمَ على الآية، ويطبع
**الحكمَ**. فما خرج `CORRECT` فليس عطباً مهما قبُحت صورتُه، وما خرج غيرَ ذلك **اتّهامٌ كاذبٌ
بعينه** يستحقّ `D-27x` بأدلّته.

🔑 **والإملاءُ الحديثُ يُشتقّ آليّاً لا يُكتب بيد** (‏وإلّا صار الفحصُ مفصَّلاً على مقاسه):
- `اا ⇒ ا` · `يي ⇒ ي` · `وو ⇒ و` — **فكُّ التكرار** الذي أنتجته المِسطرة.
- والبقايا (‏رموزٌ خارجَ الحروف) **تُحذف**.
⚠️ **وليس هذا دائريّاً:** المشتقُّ ليس صورةً من صور `variants` التي يقبلها الحاكمُ سلفاً، بل
سلسلةٌ مبنيّةٌ من مخرَج `norm` نفسِه بقاعدةٍ واحدةٍ لا تعرف الحاكم.

    python ruler_audit_verdict.py              # الستُّ · يطبع غيرَ الصحيح وحدَه
    python ruler_audit_verdict.py --all-rows   # يطبع كلَّ صنفٍ ولو خرج صحيحاً

⛔ لا يُشحن بهذا شيء: قياسٌ وتبليغ. وإن ظهر اتّهامٌ كاذبٌ فإصلاحُه في `scorer.py` **و**
`RecitationScorer.kt` معاً — وذاك قرارٌ يُتَّخذ بأدلّته لا في هذا الملفّ.
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
import detect_score  # noqa: E402
from common import load_text  # noqa: E402

RIWAYAT = ("hafs", "warsh", "qalun", "shuba", "douri", "sousi")
AUDITED = ("hafs", "warsh", "qalun")     # ما يدور عليه الفحصُ القائم

# 📏 أرضيّةُ الذراع المقابلة — قِيست 2026-09-15 ‏03:1xZ على **مواضعَ عاديّةٍ لا ريبةَ فيها**
#    (‏العيّنةُ نفسُها من الروايات الستِّ، ومتوسّطُ الطول 4.7 مقابل 4.9 في المريبة).
#    ⛔ وبدونها يُقرأ عددُ المغفور عطباً هائلاً وهو في أغلبه **حدُّ التطابق العامّ**.
BASELINE_RATE = 73.4
BASELINE_N = 2374


def suspicious(n):
    """أصنافُ الريبة — هي أصنافُ `T=3` نفسُها."""
    tags = []
    if "اا" in n:
        tags.append("ألفان")
    if "وو" in n:
        tags.append("واوان")
    if "يي" in n:
        tags.append("ياءان")
    if any(ord(c) > 0x06FF or 0x0610 <= ord(c) <= 0x061A for c in n):
        tags.append("بقايا")
    return tags


def modern(n):
    """الإملاءُ الحديثُ المشتقُّ آليّاً: يُفَكُّ التكرارُ وتُحذف البقايا."""
    out = "".join(c for c in n
                  if not (ord(c) > 0x06FF or 0x0610 <= ord(c) <= 0x061A))
    for d in ("اا", "وو", "يي"):
        while d in out:
            out = out.replace(d, d[0])
    return out


# 🔤 الرسمُ المجرَّد: حروفُ الكلمة بلا تشكيلٍ ولا علاماتٍ، مع توحيد صور الهمزة وحدَها
#    (‏أ إ آ ٱ ⇒ ا · ؤ ⇒ و · ئ ى ⇒ ي · ة ⇒ ه) — **وبلا تحويل الخنجريّة ألفاً**.
#    ⚠️ وتدخل فيها **الياءُ البريّةُ والصغائر** (‏ۓ ۦ ے ⇒ ي · ۥ ⇒ و): هي حروفُ رسمٍ لا
#    علاماتٍ، وإسقاطُها يُوهِم أنّ التكرارَ صنيعةُ مِسطرة. (‏سقط الفحصُ بها في موضعَين:
#    `وَهَيِّۓْ ⇒ وهيي` في ورشٍ وقالون، وهي ياءان في الرسم لا واحدة.)
_HAMZA = {"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ء": "", "ؤ": "و",
          "ئ": "ي", "ى": "ي", "ة": "ه",
          "ۓ": "ي", "ۦ": "ي", "ے": "ي", "ۥ": "و"}


def rasm(w):
    return "".join(_HAMZA.get(c, c) for c in w
                   if ("ء" <= c <= "ي") or c in _HAMZA)


def artifact_double(w, n):
    """أتكرارُ الحرف في `norm` **صنعتْه المِسطرةُ**، أم هو حرفان في الرسم؟

    ⛔ **وهذا هو الضابطُ الذي بدونه يكذب الفحص:** `سَيِّئَة ⇒ سييه` تكرارُها من `ئ ⇒ ي`
    (‏حرفان في الرسم) فهي **سليمةٌ**، و`وَوَصَّىٰ ⇒ ووصي` من واوَين. أمّا `أَٰ۟نَّكُم ⇒ اانكم`
    فالرسمُ فيه ألفٌ واحدة، والثانيةُ **من الخنجريّة** ⇒ صنيعةُ مِسطرةٍ تستحقّ الاختبار.
    (‏جُرّب بلا هذا الضابط فأعطى **216 إنذاراً كاذباً** كلُّها كلماتٌ صحيحةٌ في الرسم.)
    """
    r = rasm(w)
    for d in ("اا", "وو", "يي"):
        if d in n and d not in r:
            return True
    return False


_VOCAB = None


def vocab():
    """كلُّ صورةٍ مطبَّعةٍ **مثبتةٍ في الرسم** عبر الروايات الستِّ — ومعها صورُ `variants`.

    ⛔ **ولِمَ لزمت:** الذراعُ المقابلةُ تحتاج «كلمةً ليست هذه الكلمة»، والاختيارُ باليد يقع في
    فخٍّ وقعتُ فيه ساعةَ كتابةِ هذا: ظننتُ `خطيئتكم` زلّةً مكانَ `خَطَٰيَىٰكُمۡ` (الدوريّ)
    **وهي قراءةُ حفصٍ وورشٍ وقالونَ وشعبةَ للموضع نفسِه** (‏الأعراف ١٦١) ⇒ فغفرانُ الحاكم
    لها صوابٌ لا عطب. فالضدُّ لا يصلح إلّا إن كان **غيرَ مثبتٍ في أيِّ روايةٍ أصلاً**.
    """
    global _VOCAB
    if _VOCAB is None:
        _VOCAB = set()
        for riw in RIWAYAT:
            cfg = detect_score.cfg_for(riw)
            for a in load_text(riw):
                for w in a.split():
                    n = scorer.norm(w, cfg)
                    if n:
                        _VOCAB.add(n)
                        _VOCAB.update(scorer.variants(w, cfg))
    return _VOCAB


# حروفٌ تُبدَّل بها آخرُ الكلمة لصنع الضدّ — مخارجُها متباعدةٌ فلا تُشبه الأصلَ سمعاً.
_SWAP = "بتجدرسفقكلمنه"


def counter_word(m):
    """⚖️ **الذراعُ المقابلة:** كلمةٌ تُشبه `m` بحرفٍ واحدٍ **وليست كلمةً في المصحف قطّ**.

    فإن حكم الحاكمُ عليها `CORRECT` فالتسامحُ الذي أنجى الإملاءَ الحديثَ **يُنجي الزلّةَ
    أيضاً** — وذاك عطبٌ بالاتّجاه الآخر لا يلتقطه عدُّ الاتّهام الكاذب وحدَه.
    ⛔ وتُعاد `None` متى تعذّر ضدٌّ غيرُ مثبت: **فلا يُختبَر** ولا يُحسب نجاحاً ولا فشلاً.
    """
    if len(m) < 3:
        return None
    V = vocab()
    for c in _SWAP:
        if c == m[-1]:
            continue
        cand = m[:-1] + c
        if cand not in V:
            return cand
    return None


def scan(riwayat, all_rows=False):
    rows = collections.Counter()
    ex = {}
    ctrl = collections.Counter()
    cex = {}
    for riw in riwayat:
        cfg = detect_score.cfg_for(riw)
        for i, a in enumerate(load_text(riw)):
            ws = a.split()
            norms = [scorer.norm(w, cfg) for w in ws]
            for k, n in enumerate(norms):
                if not n or not suspicious(n):
                    continue
                m = modern(n)
                if m == n:
                    continue            # لا فرقَ ⇒ لا شيءَ يُختبَر
                # ⚖️ التكرارُ المشروعُ (‏حرفان في الرسم) لا يُختبَر: فكُّه يصنع كلمةً أخرى
                #    فيُتَّهم الحاكمُ بما ليس فيه. تُستثنى البقايا (‏لا تكرارَ فيها).
                if ("اا" in n or "وو" in n or "يي" in n) and not artifact_double(ws[k], n):
                    continue
                hyp = " ".join(m if kk == k else (x or "")
                               for kk, x in enumerate(norms))
                v = scorer.score(ws, hyp, cfg)["words"][k][1]
                rows[(riw, n, m, v)] += 1
                ex.setdefault((riw, n, m, v), (i + 1, ws[k]))
                # ⚖️ والذراعُ المقابلةُ في **الموضع نفسِه من الآية نفسِها** — لا في كلمةٍ
                #    معزولة: التسامحُ يُقاس حيث يعمل، وجارةُ الكلمة جزءٌ من المحاذاة.
                cw = counter_word(m)
                if cw is not None:
                    chyp = " ".join(cw if kk == k else (x or "")
                                    for kk, x in enumerate(norms))
                    cv = scorer.score(ws, chyp, cfg)["words"][k][1]
                    ctrl[(riw, n, cw, cv)] += 1
                    cex.setdefault((riw, n, cw, cv), (i + 1, ws[k]))
    return rows, ex, ctrl, cex


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--all-rows", action="store_true")
    ap.add_argument("--riwaya", action="append", choices=RIWAYAT)
    args = ap.parse_args()
    riwayat = tuple(args.riwaya) if args.riwaya else RIWAYAT

    rows, ex, ctrl, cex = scan(riwayat, args.all_rows)
    bad = {k: c for k, c in rows.items() if k[3] != scorer.CORRECT}
    tot = sum(rows.values())
    new_riw = [r for r in riwayat if r not in AUDITED]
    print(f"صورٌ مريبةٌ فُحصت بالحكم: **{tot:,}** موضعاً في {len(riwayat)} رواية "
          f"(‏منها {len(new_riw)} لم تدخل الفحصَ القائم قطّ: {' · '.join(new_riw) or '—'})")
    print(f"🚨 **اتّهامٌ كاذبٌ (‏حكمٌ غيرُ `CORRECT` على إملاءٍ حديثٍ صحيح): "
          f"{sum(bad.values()):,}** {'🚨' if bad else '✅'}")
    show = rows if args.all_rows else bad
    if show:
        print(f"\n{'الرواية':8s} {'صورةُ المِسطرة':16s} {'الإملاءُ الحديث':16s} "
              f"{'الحكم':12s} {'مواضع':>6s}  مثال")
        for (riw, n, m, v), c in sorted(show.items(), key=lambda x: -x[1]):
            a, w = ex[(riw, n, m, v)]
            mark = "✅" if v == scorer.CORRECT else "🚨"
            print(f"{mark} {riw:7s} {n:16s} {m:16s} {v:12s} {c:>6d}  آية {a}: {w}")

    # ⚖️ الذراعُ المقابلة — بلا هذا يخرج حاكمٌ يغفر كلَّ شيءٍ **أخضرَ** في هذا الفحص.
    missed = {k: c for k, c in ctrl.items() if k[3] == scorer.CORRECT}
    ctot, mtot = sum(ctrl.values()), sum(missed.values())
    rate = 100.0 * mtot / max(ctot, 1)
    print(f"\n⚖️ **الذراعُ المقابلة** (‏كلمةٌ تُشبه الإملاءَ بحرفٍ وليست في المصحف قطّ): "
          f"{ctot:,} موضعاً · غُفر **{mtot:,} = {rate:.1f}٪**")
    print(f"   📏 وأرضيّةُ المقارنة — **{BASELINE_RATE:.1f}٪** على مواضعَ عاديّةٍ لا ريبةَ فيها "
          f"(‏عيّنةُ {BASELINE_N:,} · بمتوسّط طولٍ مكافئ) ⇒ **الفرقُ {rate - BASELINE_RATE:+.1f} نقطة**.")
    print("   ⛔ **ولا يُقرأ هذا العددُ عطباً:** أغلبُه حدُّ التطابق العامُّ (`match_num/match_den`)"
          " وهو معلَمٌ مقصودٌ مقيسٌ في موضعه، لا صنيعةُ مِسطرة. **الفرقُ عن الأرضيّة وحدَه**"
          " هو ما تضيفه الصورُ المريبة — وهو ما يُتابَع إن كبُر.")
    if args.all_rows and missed:
        print(f"\n{'الرواية':8s} {'صورةُ المِسطرة':16s} {'الضدُّ المغفور':16s} {'مواضع':>6s}  مثال")
        for (riw, n, cw, v), c in sorted(missed.items(), key=lambda x: -x[1])[:20]:
            a, w = cex[(riw, n, cw, v)]
            print(f"   {riw:7s} {n:16s} {cw:16s} {c:>6d}  آية {a}: {w}")
    # ⛔ ورمزُ الخروجُ للاتّهام الكاذب وحدَه: الذراعُ المقابلةُ **مقياسٌ يُتابَع لا بوّابةٌ تُسقِط**،
    #    وإسقاطُها على معلَمٍ مشحونٍ مقصودٍ يجعل الأداةَ تصرخ كلَّ يومٍ بما ليس جديداً.
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
