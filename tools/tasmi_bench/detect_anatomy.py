# -*- coding: utf-8 -*-
"""🔬 **تشريحُ الكشف صنفاً صنفاً — ولماذا «هبوطُ الكشف» كان عطبَ مسطرةٍ لا عطبَ نموذج** (‏D-351).

بدا أنّ النموذجَ الأكبرَ **أدقُّ نسخاً وأقلُّ كشفاً** — وهو تناقضٌ يستحقّ التفتيش لا التسليم.
والتشريحُ يردّ الهبوطَ كلَّه إلى صنفٍ واحد (`INSERT`)، وسببُه أنّ **المقياسَ يتجاهل الزوائد**:

- الكشفُ **الضيّق** = حكمُ `MISSED`/`SUBSTITUTED` داخل نطاق الحقن ‎±1 — أي أنّ الكلمةَ الدخيلةَ
  لا تُكتشف بذاتها بل **بما تُحدثه من ضررٍ جانبيٍّ في جاراتها**.
- والنموذجُ الأنظفُ نسخاً يُحدث ضرراً جانبيّاً **أقلّ** ⇒ **فيُعاقَب على نظافته**.
- والكشفُ **الموسَّع** يزيد شرطاً واحداً لا يزيد تساهلاً: **أن تظهر كلمةُ المانحِ بعينها زائدةً**
  في النسخ (‏`Score.additions`) — وهي حدثٌ لا يقع إلّا إذا سُمعت الدخيلةُ فعلاً.

⚠️ **وحدٌّ يُقال:** الزوائدُ في المحرك تُعدّ في **السطر العام** ولا تُنسب إلى كلمة
(‏`LongTasmiMapper`) ⇒ فالمتعلّمُ يُخبَر «زائدةٌ واحدة» ولا يُؤشَّر له موضعُها. فالكشفُ الموسَّعُ
**صادقٌ على أنّ الخطأ بلغ المستخدم**، لا على أنّه بلغه بالجودة نفسِها.

    python tools/tasmi_bench/detect_anatomy.py --dirs work/_bg/emu-0:B work/_br/emu-2:B2
"""
import argparse
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import scorer  # noqa: E402
import judge_cfg_probe as J  # noqa: E402
import restore_probe as R  # noqa: E402

OPS = ("OMIT", "SUBSTITUTE", "SWAP", "INSERT")


def boot(pairs, seed=7, n=4000):
    rng = random.Random(seed)
    d = []
    for _ in range(n):
        s = [pairs[rng.randrange(len(pairs))] for _ in range(len(pairs))]
        d.append((sum(y[1] for y in s) - sum(y[0] for y in s)) / len(s) * 100)
    d.sort()
    return d[int(0.025 * n)], d[int(0.975 * n)]


def donor_located(it, hyp, tol=1):
    """📍 أظهرت كلمةُ المانحِ زائدةً **وفي موضعها** (‏±[tol] كلمة)؟ — شرطٌ **يزيد ولا يتساهل**.

    ⛔ **لِمَ وُجد:** الكشفُ الموسَّع يسأل «أسُمعت الدخيلةُ؟» وهو صادقٌ على أنّ **الخطأ بلغ
    المستخدم**، ولا يقول إنّه بلغه **مؤشَّراً**. والمتعلّمُ الذي يُقال له «زائدةٌ واحدة» بلا موضعٍ
    لا يعرف أين زاد ⇒ وهذه الثغرةُ بعينها (‏`INSERT` 65٪ مقابل 90–97٪ · D-351) **ثغرةُ عرضٍ لا
    ثغرةُ نموذج**. فصار المحركُ يُوطِّن الزوائد (`Score.locatedAdditions`)، **وهذا الصفُّ يقيس
    أيُنتفع بالتوطين فعلاً**: أيقع موضعُ الزائدة حيث حُقنت أم في مكانٍ آخر؟
    """
    d = (it.get("donor") or {}).get("word", "")
    if not d:
        return 0
    c = J.cfg(it.get("riwaya"), True)
    dw = scorer.norm(d, c)
    if not dw:
        return 0
    w = int(it["wordIndex"])
    for text, at in scorer.score(it["refText"].split(), hyp["text"], c).get("located", []):
        if scorer.norm(text, c) == dw and abs(at - w) <= tol:
            return 1
    return 0


def donor_heard(it, hyp):
    """أظهرت كلمةُ المانحِ **بعينها** زائدةً؟ — شرطٌ يزيد ولا يتساهل."""
    d = (it.get("donor") or {}).get("word", "")
    if not d:
        return 0
    c = J.cfg(it.get("riwaya"), True)
    dw = scorer.norm(d, c)
    adds = scorer.score(it["refText"].split(), hyp["text"], c)["additions"]
    return 1 if dw and dw in [scorer.norm(w, c) for w in adds] else 0


def table(pl, ha, hb, pa, pb, wide):
    print("| صنفُ الحقن | ن | المشحون | المرشَّح | الفرق | مجال 95٪ |")
    print("|---|---:|---:|---:|---:|---:|")
    for op in OPS + (None,):
        sub = [x for x in pl if op is None or x["op"] == op]
        p = []
        for x in sub:
            k = x["id"]
            a, b = pa[k][2], pb[k][2]
            if wide:
                a = a or donor_heard(x, ha[k])
                b = b or donor_heard(x, hb[k])
            p.append((1 if a else 0, 1 if b else 0))
        A = sum(y[0] for y in p) / len(p) * 100
        B = sum(y[1] for y in p) / len(p) * 100
        lo, hi = boot(p)
        sig = " ⚠️" if hi < 0 else (" ✅" if lo > 0 else "")
        print(f"| {'`'+op+'`' if op else '**المضمومة**'} | {len(p)} | {A:.1f}٪ | **{B:.1f}٪** | "
              f"**{B-A:+.1f}**{sig} | [{lo:+.1f} .. {hi:+.1f}] |")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dirs", nargs="+", required=True)
    ap.add_argument("--arms", nargs=2, default=["shipped", "base-ar"])
    a = ap.parse_args()
    plan = {it["id"]: it for it in json.load(open(J.PLAN, encoding="utf-8"))["items"]}
    acc = R.load(a.dirs)
    ha, hb = R.arms_or_die(acc, a.arms)
    pl = [{**plan[k.split("/", 1)[1]], "id": k} for k in sorted(set(ha) & set(hb))
          if k.split("/", 1)[1] in plan]
    if len(pl) < 50:
        raise SystemExit(f"⛔ {len(pl)} بنداً فقط — لا يُقرأ الصفرُ نتيجةً")
    _, _, _, pa = J.judge(pl, ha, True)
    _, _, _, pb = J.judge(pl, hb, True)

    print(f"‏ن = **{len(pl)}** · `{a.arms[0]}` ⇒ `{a.arms[1]}`\n\n### ‏(١) الكشفُ **الضيّق** — حكمُ خطإٍ داخل ‎±1 وحدَه\n")
    table(pl, ha, hb, pa, pb, False)
    print("\n### ‏(٢) الكشفُ **الموسَّع** — أو أن تظهر كلمةُ المانحِ بعينها زائدةً\n")
    table(pl, ha, hb, pa, pb, True)

    ins = [x for x in pl if x["op"] == "INSERT"]
    p = [(donor_heard(x, ha[x["id"]]), donor_heard(x, hb[x["id"]])) for x in ins]
    A = sum(y[0] for y in p) / len(p) * 100
    B = sum(y[1] for y in p) / len(p) * 100
    lo, hi = boot(p)
    # 📍 **(٤) التوطين** — يُحسب قبل الطبع كي يُذكر مع (٣) في جملةٍ واحدة.
    pl_loc = [(donor_located(x, ha[x["id"]]), donor_located(x, hb[x["id"]])) for x in ins]
    LA = sum(y[0] for y in pl_loc) / len(pl_loc) * 100
    LB = sum(y[1] for y in pl_loc) / len(pl_loc) * 100
    l_lo, l_hi = boot(pl_loc)
    # ⛔ **والموضعُ الدقيقُ يُقاس أيضاً:** «±1» تساهلٌ مقبولٌ للعرض (الجارةُ تكفي للتأشير)،
    # لكنّ مئةً بالمئةٍ عند ±1 قد تكون **أثرَ التساهل** لا دقّةَ المحاذاة. ⇒ يُطبع الصفّان.
    pl_ex = [(donor_located(x, ha[x["id"]], 0), donor_located(x, hb[x["id"]], 0)) for x in ins]
    XA = sum(y[0] for y in pl_ex) / len(pl_ex) * 100
    XB = sum(y[1] for y in pl_ex) / len(pl_ex) * 100
    x_lo, x_hi = boot(pl_ex)
    print(f"\n### ‏(٣) والسببُ مباشرةً: **أيُّ ذراعٍ يسمع الدخيلةَ؟**\n\n"
          f"كلمةُ المانحِ تظهر زائدةً: `{a.arms[0]}` **{A:.1f}٪** ⇒ `{a.arms[1]}` **{B:.1f}٪** · "
          f"الفرق **{B-A:+.1f}** · [{lo:+.1f} .. {hi:+.1f}]"
          # ⛔ **والذراعُ تُسمّى باسمها لا بـ«المرشَّح»** (‏2026-09-13): منذ **ذراع المفتاح** قد
          # تكون الذراعُ الثانيةُ **النموذجَ المشحونَ نفسَه بمفتاحٍ آخر** لا مرشَّحاً ⇒ «المرشَّحُ
          # يسمعها أكثر» يُقرأ حكماً على نموذجٍ وهو حكمٌ على مفتاح. **والوسمُ الكاذبُ يُنسب رقماً
          # صحيحاً إلى غير صاحبه** (وهو عينُ ما بُني له جدولُ النسب في `gate-anatomy`).
          + (f"\n\n⇒ ✅ **`{a.arms[1]}` تسمعها أكثر** — فهبوطُ الكشفِ الضيّق **عقوبةٌ على قلّةِ الضررِ الجانبيّ**، لا عمىً عن الخطأ."
             if lo > 0 else "\n\n⇒ لا فرقَ يُعتدّ به في سماع الدخيلة."))

    # 📍 **(٤) التوطين: أتقع الزائدةُ حيث حُقنت؟** — الشرطُ هو شرطُ (٣) **وزيادةُ موضع**،
    # فنسبتُه **لا تزيد** على نسبة (٣) أبداً؛ ونسبةُ «المسموعِ الموطَّن» هي الرقمُ الذي يقول
    # هل يُنتفع بالتوطين أم تضع المحاذاةُ الزائدةَ في غير موضعها.
    print(f"\n### ‏📍 (٤) **وهل تقع الزائدةُ في موضعها؟** (‏±1 كلمة — شرطٌ يزيد ولا يتساهل)\n\n"
          f"| المقياس | `{a.arms[0]}` | `{a.arms[1]}` | الفرق | مجال 95٪ |\n|---|---:|---:|---:|---:|\n"
          f"| تُسمع الدخيلةُ (٣) | {A:.1f}٪ | **{B:.1f}٪** | **{B-A:+.1f}** | [{lo:+.1f} .. {hi:+.1f}] |\n"
          f"| **وتُسمع في موضعها (‏±1)** | {LA:.1f}٪ | **{LB:.1f}٪** | **{LB-LA:+.1f}** | [{l_lo:+.1f} .. {l_hi:+.1f}] |\n"
          f"| **وفي موضعها بالضبط (‏±0)** | {XA:.1f}٪ | **{XB:.1f}٪** | **{XB-XA:+.1f}** | [{x_lo:+.1f} .. {x_hi:+.1f}] |\n"
          f"| ⇒ **حصّةُ المُوطَّن من المسموع** | {(LA/A*100 if A else 0):.0f}٪ | **{(LB/B*100 if B else 0):.0f}٪** | — | — |")
    print("\n⚠️ **وحدُّ هذا الصفّ:** يقيس ما يستطيعه المحركُ **بعد** `locatedAdditions`، لا ما "
          "تعرضه الشاشةُ اليومَ — فالعرضُ قرارُ جلسةِ التطبيق. وما نقص من 100٪ فهو زائدةٌ "
          "**سُمعت ووُضعت في غير موضعها**: تلك لا يُغلقها عرضٌ بل محاذاةٌ (ولا تُغيَّر كلفتُها بلا شوط).")


if __name__ == "__main__":
    sys.exit(main())
