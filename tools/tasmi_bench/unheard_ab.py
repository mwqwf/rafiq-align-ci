# -*- coding: utf-8 -*-
"""🤫 **«لم أتبيّن» بدل «أخطأت» — ذراعان من مسطرتَين على فرضيّاتٍ واحدة** (‏D-445).

⛔ **لِمَ وُجدت — بسببٍ مقيسٍ لا مقترَح:** أرضيّةُ الضجيج **359 اتّهاماً**، و**267 منها
(74.4٪)** مسموعُها **ليس صورةَ أيّ كلمةٍ في المصحف** (`تسفسوا` · `رفهثا` · `سسنسا`) ⇒ فقولُ
«أخطأتَ» عليها **إخبارٌ بما لا يعلمه المحرك**. والصنفُ الصحيحُ `UNCERTAIN` (D-231): يُعرَض،
ولا يُحسب زلّةً — **وهو مشحونٌ اليومَ**، فليست قاعدةً تحتاج نصّاً جديداً في `app/` بل
**شرطاً جديداً لصنفٍ قائم**.

⭐ **ويُقاس بلا شوطِ محاكٍ** (‏كـ`tie_rule_ab`): القاعدةُ في **المسطرة** لا في التفريغ،
والفرضيّاتُ محفوظةٌ ⇒ تُقرأ مرّةً ويُحكم بها مرّتَين (مطفأةً ومُشعلة).

⛔⛔ **والثمنُ هو المقصودُ من القياس لا الكسب:** `UNCERTAIN` **لا تُعَدّ كشفاً** في جدول
البوّابة (`CONF` فيه `MISSED` و`SUBSTITUTED` وحدَهما) ⇒ فكلُّ ما تكسبه هذه القاعدةُ من
**الاتّهام الكاذب** قد تدفعه من **الكشف**. والجدولُ يُظهر الاثنين معاً بمجالَيهما.

⚠️ **وحدُّها الذي لا يُقاس هنا:** الحقنُ **صوتٌ صحيحٌ لكلمةٍ أخرى**، أمّا **لحنُ طالبٍ
حقيقيٍّ** فقد يُفرَّغ لا-كلمةً **فيُكتَم عنه** — ولا مادّةَ عندنا تقيسه (‏تسجيلاتُ لاحنين).

    python tools/tasmi_bench/unheard_ab.py --selftest
    python tools/tasmi_bench/unheard_ab.py --dirs work: --arm shipped-P
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import scorer  # noqa: E402
import detect_score as D  # noqa: E402
import restore_probe as R  # noqa: E402
import judge_cfg_probe as J  # noqa: E402
import v2_gate as G  # noqa: E402


def lexicons(riwayat=("hafs", "warsh", "qalun")):
    """معجمُ **صورِ** كلّ كلمةٍ في نصّ كلّ رواية — الحكمُ «أهو كلمةٌ أصلاً؟» يُبنى عليه.

    ⛔ **و`_mods()` أوّلاً — بسببٍ مقيسٍ لا احتياطاً** (‏الشوط `34847289900`): `common` ليست
    في `tasmi_bench` بل في `tools/alignment/`، و`error_triage._mods()` هي التي تضعها في
    المسار. فاستيرادُها بلا ذلك يرمي `ModuleNotFoundError: No module named 'common'`
    **في العدّاء وحدَه** (‏وفي الصندوق إن شُغّلت من مجلد الأداة) — وهو ما وقع.
    """
    import error_triage as T
    T._mods()                       # يضع `tools/alignment` في المسار (‏وفيه `common`)
    from common import load_text
    from error_triage import lexicon_of
    out = {}
    for riw in riwayat:
        try:
            out[riw] = lexicon_of(riw, D.cfg_for(riw), scorer, load_text)
        except Exception as e:                      # نصٌّ غائبٌ ⇒ «لم يُبنَ» لا «فارغ»
            print(f"⚠️ لم يُبنَ معجمُ `{riw}` ({e}) — ولا تُقاس القاعدةُ عليه", file=sys.stderr)
    return out


def judge_with(plan, hyps, lex):
    """حكمُ الذراع بمسطرةٍ معجمُها [lex] (‏`None` = المشحون) — **ويُعيد `cfg_for` دائماً**.

    ⛔ **ولِمَ الحرصُ:** `detect_score.cfg_for` **دالّةٌ عامّةٌ** يناديها كلُّ حكمٍ في هذه
    العمليّة. وتسرُّبُها **لا يرمي خطأً ولا يُسقط شوطاً**: يجعل كلَّ ما يليها يُحكم بمسطرةٍ
    غيرِ المشحونة ⇒ **يُقرأ فرقُ ذراعَين وهو فرقُ مسطرتَين** (درسُ `tie_rule_ab`).
    """
    old = D.cfg_for
    try:
        if lex is not None:
            def patched(riwaya, _old=old):
                c = _old(riwaya)
                c.unheard_lexicon = lex.get(riwaya)
                return c
            D.cfg_for = patched
        return G.judge_arm(plan, hyps)
    finally:
        D.cfg_for = old


# ---- 🧪 اختبارٌ ذاتيٌّ — ولا يُقرأ رقمٌ من أداةٍ لم تُختبر ----
_REF = "الحمد لله رب العالمين الرحمن الرحيم"
_PLAN = [{"id": "t1", "refText": _REF, "wordIndex": 2, "op": "SUBSTITUTE", "riwaya": "hafs"}]
# فرضيّةٌ سُمعت فيها كلمةٌ **ليست من كلام العرب** مكانَ `رب` — وهي الحالةُ التي وُجدت لها.
_HYPS = {"t1": {"text": "الحمد لله سسنسا العالمين الرحمن الرحيم"}}
_LEX = {"hafs": {scorer.norm(w, D.cfg_for("hafs")) for w in _REF.split()}}


def selftest():
    bad = 0

    def ok(name, got, want):
        nonlocal bad
        good = got == want
        print(f"  {'✅' if good else '⛔'} {name}: {got} · المتوقَّع {want}")
        bad += 0 if good else 1

    cfg = D.cfg_for("hafs")
    ok("المشحونُ اليومَ: لا معجمَ في المسطرة", getattr(cfg, "unheard_lexicon", "؟"), None)

    ref = _REF.split()
    sA = scorer.score(ref, _HYPS["t1"]["text"], D.cfg_for("hafs"))
    c2 = D.cfg_for("hafs")
    c2.unheard_lexicon = _LEX["hafs"]
    sB = scorer.score(ref, _HYPS["t1"]["text"], c2)
    ok("المشحونةُ تتّهم: `رب` ⇒ إبدالٌ مؤكَّد", sA["words"][2][1], scorer.SUBSTITUTED)
    ok("والمرشَّحةُ تقول «لم أتبيّن»", sB["words"][2][1], scorer.UNCERTAIN)
    ok("⇒ فالذراعان ليستا نسختَين", [w[1] for w in sA["words"]] != [w[1] for w in sB["words"]], True)

    # ⛔ ضابطٌ سالبٌ ①: مسموعٌ **كلمةٌ قرآنيّةٌ** يبقى اتّهاماً — وإلّا صارت القاعدةُ تسكيتاً عامّاً
    s3 = scorer.score(ref, "الحمد لله الرحيم العالمين الرحمن الرحيم", c2)
    ok("كلمةٌ من المصحف مكانَ غيرها تبقى إبدالاً", s3["words"][2][1], scorer.SUBSTITUTED)
    # ⛔ ضابطٌ سالبٌ ②: `MISSED` لا تُلمَس — لا مسموعَ لها فلا يُقال «لم أتبيّن» عن صمت.
    #    (‏وذيلٌ لم يُسمع: كلمتان من ستٍّ ⇒ **دون** عتبة الانهيار 0.60 فلا يكبحه حارسُها.)
    s4 = scorer.score(ref, "الحمد لله رب العالمين", c2)
    ok("الفواتُ يبقى فواتاً", [w[1] for w in s4["words"]][-2:], [scorer.MISSED, scorer.MISSED])
    # ⛔ ضابطٌ سالبٌ ③: بلا معجمٍ **صفرُ تغييرٍ بالهويّة** (‏لا نسخةٌ جديدةٌ من القائمة)
    w_off = scorer._unheard_guard(sA["words"], D.cfg_for("hafs"))
    ok("بلا معجمٍ تُعاد القائمةُ بالهويّة", w_off is sA["words"], True)

    # ⛔⛔ **وضابطُ المسار — الذي كان ناقصاً فسقط الشوطُ الأوّل** (`34847289900`):
    #     الاختبارُ كان يبني المعجمَ **بيده** فلا يمرّ بـ`lexicons()` البتّة، فمرّ أخضرَ
    #     والأداةُ تسقط في العدّاء بـ`ModuleNotFoundError`. ⭐ **اختبارٌ لا يمرّ بالطريق
    #     الذي يمرّ به الشوطُ لا يحرسه** — فصار يُنادى الطريقُ نفسُه.
    lx = lexicons(("hafs",))
    ok("والمعجمُ يُبنى بالطريق الذي يسلكه الشوط", bool(lx.get("hafs")), True)

    # ② وحكمُ الذراع يتبدّل تبعاً — والكشفُ هو الثمنُ المحتمَل
    dA, faA, nA, _ = judge_with(_PLAN, _HYPS, None)
    dB, faB, nB, _ = judge_with(_PLAN, _HYPS, _LEX)
    ok("بالمشحونة: كشفٌ في موضع الحقن", (dA, nA), (1.0, 1))
    ok("وبالمرشَّحة: لا كشفَ (‏صار «لم أتبيّن»)", (dB, nB), (0.0, 1))
    ok("⇒ والثمنُ ظاهرٌ في الجدول لا مخفيٌّ", dB < dA, True)

    # ③ ⛔⛔ والأهمّ: `cfg_for` تعود دائماً — في السويّ وفي الاستثناء
    ok("تعود بعد نداءٍ سويّ", getattr(D.cfg_for("hafs"), "unheard_lexicon", "؟"), None)
    kept = G.judge_arm
    try:
        G.judge_arm = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("انفجارٌ متعمَّد"))
        try:
            judge_with(_PLAN, _HYPS, _LEX)
            ok("⛔ الاستثناءُ لم يُرمَ أصلاً", False, True)
        except RuntimeError as e:
            ok("واستثناءٌ في وسط الحكم يمرّ ولا يُبتلع", str(e), "انفجارٌ متعمَّد")
        ok("⭐ و`cfg_for` تعود **حتى مع الاستثناء**",
           getattr(D.cfg_for("hafs"), "unheard_lexicon", "؟"), None)
    finally:
        G.judge_arm = kept

    print("✅ الأداةُ سليمةٌ على حالاتها" if not bad else f"⛔ الأداةُ نفسُها معطوبةٌ في {bad} حالة")
    return 1 if bad else 0


def main():
    if "--selftest" in sys.argv:      # ⭐ قبل الوسائط المطلوبة: الاختبارُ لا يحتاج دلواً
        raise SystemExit(selftest())
    ap = argparse.ArgumentParser()
    ap.add_argument("--dirs", nargs="+", required=True)
    ap.add_argument("--arm", required=True, help="ذراعٌ واحدة — فالمقارنةُ بين مسطرتَين لا نموذجَين")
    a = ap.parse_args()

    plan_all = {it["id"]: it for it in json.load(open(J.PLAN, encoding="utf-8"))["items"]}
    acc = R.load(a.dirs)
    (h,) = R.arms_or_die(acc, [a.arm])
    plan = [{**plan_all[k.split("/", 1)[1]], "id": k} for k in sorted(h) if k.split("/", 1)[1] in plan_all]
    # ⛔ ولا يُقرأ الصفرُ نتيجةً: تُسمّى العيّنةُ قبل أيّ رقم.
    if len(plan) < 50:
        raise SystemExit(f"⛔ {len(plan)} بنداً فقط في {a.arm} — لا يُحكم بعيّنةٍ كهذه")
    lex = lexicons()
    if not lex:
        raise SystemExit("⛔ لم يُبنَ معجمٌ واحد ⇒ **القاعدةُ لم تُقَس** (ولا يُقرأ هذا «لا أثر»)")

    dA, faA, n, perA = judge_with(plan, h, None)
    dB, faB, _, perB = judge_with(plan, h, lex)

    print(f"# 🤫 «لم أتبيّن» بدل «أخطأت» — الذراعُ `{a.arm}` · ن = **{len(plan)}**\n")
    print("**مسطرتان على الفرضيّات عينِها**: المشحونة ⇐ «ما ليس كلمةً من المصحف لا يُتَّهم به».\n")
    pairs = [(perA[i][0], perA[i][1], perB[i][0], perB[i][1]) for i in perA if i in perB]
    lo, hi, p = G._boot_diff(pairs)
    det_pairs = [(perA[i][2], 1, perB[i][2], 1) for i in perA if i in perB]
    d_lo, d_hi, d_p = G._boot_diff(det_pairs)
    print("| المقياس | المشحونة | **المرشَّحة** | الفرق [95٪] | احتمالُ السوء |")
    print("|---|---:|---:|---|---:|")
    print(f"| اتّهامٌ كاذب | {faA*100:.2f}٪ | **{faB*100:.2f}٪** | {(faB-faA)*100:+.2f} "
          f"[{lo*100:+.2f} .. {hi*100:+.2f}] | {p*100:.0f}٪ |")
    print(f"| كشفٌ ضيّق | {dA*100:.1f}٪ | **{dB*100:.1f}٪** | {(dB-dA)*100:+.1f} "
          f"[{d_lo*100:+.1f} .. {d_hi*100:+.1f}] | {d_p*100:.0f}٪ |")
    print("\n⛔ **ويُقرأ الصفّان معاً لا أحدُهما:** `UNCERTAIN` لا تُعَدّ كشفاً، فكلُّ نقطةٍ "
          "تُكسب في الاتّهام قد تُدفع من الكشف. ⚠️ **ولا يقيس هذا لحنَ طالبٍ حقيقيٍّ** "
          "(الحقنُ صوتٌ صحيحٌ لكلمةٍ أخرى) — وذلك حدُّ القاعدة لا حدُّ الأداة.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
