# -*- coding: utf-8 -*-
"""🧷 **حارسُ الحقيقة الأرضيّة** — يفحص خطط الحقن (`inject_plan*.json`) قبل أن يُحكم بها.

⛔ **لِمَ وُجد (‏عطبٌ مقيسٌ لا احتمالٌ مفترَض · 2026-09-14):** أرقامُ الكشف كلُّها مبنيّةٌ على
دعوى واحدة: **«في هذا الموضع خطأٌ مصنوعٌ فعلاً»**. وقياسُ `inject_plan.json` أظهر أنّ الدعوى
تكذب في بنودٍ منها:

- **ثلاثةُ بنودِ `SWAP` مقطعُها المُبدَّلُ هو مقطعُها نفسُه** (‏`swapMs == cutMs`) ⇒ الصوتُ
  **لا يتغيّر بحرفٍ واحد**، والبندُ يُعَدّ مع ذلك خطأً يجب كشفُه. ⇒ **سقفُ الصنف 37/40 =
  92.5٪ بالبناء** — وهو بعينه أعلى رقمِ `SWAP` ظهر في اللوحة قطّ.
- **وسبعةُ بنودٍ هدفُها «كلمةٌ» لا صوتَ لها**: علامةُ وقفٍ (‏`ۖ ۗ ۚ`) يعدّها `refText.split()`
  كلمةً. وقِيس حكمُها في المسطرة: **صحيحةٌ في 44 من 44** تلاوةٍ مثاليّة ⇒ **لا تُتَّهم ولا
  تُكشَف**، فالحقنُ عليها حقيقةٌ أرضيّةٌ كاذبةُ الاسم.

⭐ **ولا يُصحَّح رقمٌ بحذف بندٍ يضرّه**: إسقاطُ هذه البنود **يرفع** الكشفَ — وهي الجهةُ التي
يُشتبه فيها. فالحارسُ **يقيس ويُعلن** ويمنع الجديدَ (‏`inject.py` صار يتخطّاها عند التوليد)،
والخططُ المودَعةُ تبقى بحالها كي تبقى الأرقامُ السالفةُ قابلةً للمقارنة.

    python tools/tasmi_bench/plan_guard.py tools/tasmi_bench/inject_plan*.json
    python tools/tasmi_bench/plan_guard.py --selftest
"""
import argparse
import glob as _glob
import json
import os
import re
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# حروفُ العربيّة الأصليّة — وما خلا منها فعلامةُ وقفٍ أو ضبطٍ لا صوتَ لها مستقلّاً.
LETTERS = re.compile(r"[ء-ي]")
# فجوةُ الـ`SWAP` المسموحة: `inject.py` يشترط ألّا يفصل بين المقطعَين أكثرُ من 400م.ث
# (‏وإلّا صار قطعاً لا تبديلاً)، والهامشُ يقضم 2×`padMs` من الفجوة المعلنة.
SWAP_MAX_GAP_MS = 400

# ⛔ **قاتلٌ** = الحقيقةُ الأرضيّةُ نفسُها كاذبةٌ ⇒ الرقمُ المبنيُّ عليها لا يُقرأ.
# ⚠️ **منبِّهٌ** = البندُ يصحّ صوتاً ويُخطئ اسماً ⇒ يُقرأ الرقمُ بحدٍّ مكتوب.
FATAL = {
    "wordcount_mismatch": "⛔ `wordCount` يخالف عدَّ `refText`",
    "index_not_internal": "⛔ `wordIndex` ليس كلمةً داخليّةً (لا أوّلَ ولا آخر)",
    "target_mismatch": "⛔ `targetWord` لا يطابق `refText[wordIndex]`",
    "cut_malformed": "⛔ `cutMs` غيرُ مرتّبٍ أو سالب",
    "swap_missing": "⛔ `SWAP` بلا `swapMs`",
    "swap_degenerate": "⛔ `SWAP` مقطعاه متطابقان أو متداخلان ⇒ **الصوتُ لا يتغيّر**",
    "donor_missing": "⛔ `SUBSTITUTE`/`INSERT` بلا `donor`",
    "donor_same_word": "⛔ الكلمةُ المانحةُ هي المستبدَلةُ نفسُها ⇒ لا خطأ",
    "donor_cut_malformed": "⛔ `donor.cutMs` غيرُ مرتّب",
    "dup_id": "⛔ معرّفٌ مكرَّرٌ (بندان بحكمٍ واحد)",
}
WARN = {
    "silent_target": "⚠️ الهدفُ علامةُ وقفٍ لا صوتَ لها — تُحكم صحيحةً دائماً",
    "silent_donor": "⚠️ المانحُ علامةُ وقفٍ لا صوتَ لها",
    "swap_gap_wide": f"⚠️ فجوةُ `SWAP` تتجاوز {SWAP_MAX_GAP_MS}م.ث ⇒ قطعٌ لا تبديل",
}


def has_sound(token):
    """أفي هذا المقطع حرفٌ عربيٌّ يُنطَق؟ — «الكلمةُ» بلا حرفٍ علامةُ وقف."""
    return bool(LETTERS.search(token))


def check_item(it, pad_ms=0):
    """يعيد قائمةَ رموزِ العطب في بندٍ واحد — فارغةٌ إن سلم."""
    bad = []
    ref = it.get("refText", "").split()
    wi = it.get("wordIndex")
    if not ref or not isinstance(wi, int):
        return ["wordcount_mismatch"]
    if it.get("wordCount") != len(ref):
        bad.append("wordcount_mismatch")
    if not (0 < wi < len(ref) - 1):
        bad.append("index_not_internal")
        return bad                       # ما بعده يقرأ `ref[wi]` فلا يُقرأ على فهرسٍ باطل
    op = it.get("op")
    want = ref[wi] + " ↔ " + ref[wi + 1] if op == "SWAP" and wi + 1 < len(ref) else ref[wi]
    if "targetWord" in it and it["targetWord"] != want:
        bad.append("target_mismatch")
    if not has_sound(ref[wi]):
        bad.append("silent_target")
    cut = it.get("cutMs")
    if not (isinstance(cut, list) and len(cut) == 2 and 0 <= cut[0] < cut[1]):
        bad.append("cut_malformed")
        cut = None
    if op == "SWAP":
        sw = it.get("swapMs")
        if not (isinstance(sw, list) and len(sw) == 2 and 0 <= sw[0] < sw[1]):
            bad.append("swap_missing")
        elif cut:
            # ⛔ تطابقُ المقطعَين ⇒ تبديلُ الشيء بنفسِه: مخرَجٌ مطابقٌ للأصل حرفاً.
            #    وتداخلُهما بأكثرَ من الهامشَين ⇒ المقطعُ الثاني يبدأ قبل انتهاء الأوّل.
            if sw == cut or sw[0] < cut[1] - 2 * pad_ms:
                bad.append("swap_degenerate")
            elif sw[0] - cut[1] > SWAP_MAX_GAP_MS:
                bad.append("swap_gap_wide")
    if op in ("SUBSTITUTE", "INSERT"):
        dn = it.get("donor")
        if not isinstance(dn, dict):
            bad.append("donor_missing")
        else:
            if dn.get("word") == ref[wi]:
                bad.append("donor_same_word")
            if not has_sound(dn.get("word", "")):
                bad.append("silent_donor")
            dc = dn.get("cutMs")
            if not (isinstance(dc, list) and len(dc) == 2 and 0 <= dc[0] < dc[1]):
                bad.append("donor_cut_malformed")
    return bad


def check_plan(plan):
    """يعيد (‏رمزُ العطب → قائمةُ المعرّفات) لخطّةٍ كاملةٍ — والمعرّفُ المكرَّرُ يُعَدّ مرّةً."""
    pad = plan.get("padMs", plan.get("pad", 0)) or 0
    found, seen = {}, set()
    for it in plan.get("items", []):
        i = it.get("id", "<بلا معرّف>")
        if i in seen:
            found.setdefault("dup_id", []).append(i)
        seen.add(i)
        for code in check_item(it, pad):
            found.setdefault(code, []).append(i)
    return found


def report(path, plan):
    """يطبع حصيلةَ خطّةٍ ويعيد عددَ أصنافِ العطب القاتل."""
    items = plan.get("items", [])
    found = check_plan(plan)
    fatal = [c for c in found if c in FATAL]
    print(f"\n## `{os.path.basename(path)}` — **{len(items)}** بنداً")
    if not found:
        print("✅ الحقيقةُ الأرضيّةُ سليمةٌ على كلّ شرطٍ يُفحص.")
        return 0
    print("\n| الحكم | العدد | من البنود |\n|---|---:|---|")
    for code, ids in sorted(found.items(), key=lambda kv: (kv[0] not in FATAL, kv[0])):
        label = FATAL.get(code) or WARN.get(code, code)
        pct = len(ids) / len(items) * 100 if items else 0
        print(f"| {label} | **{len(ids)}** ({pct:.1f}٪) | " + " · ".join(f"`{i}`" for i in ids[:4])
              + (" …" if len(ids) > 4 else "") + " |")
    if fatal:
        # ⭐ والسقفُ يُحسب لا يُقدَّر: بنودٌ لا يتغيّر صوتُها **لا تُكشَف أبداً**.
        dead = set(found.get("swap_degenerate", []))
        if dead:
            by_op = [it for it in items if it.get("op") == "SWAP"]
            print(f"\n⛔ **سقفُ `SWAP` بالبناء: {len(by_op) - len(dead)}/{len(by_op)} = "
                  f"{(len(by_op) - len(dead)) / len(by_op) * 100:.1f}٪** — فما فوقَه مستحيلٌ ولو أُصلح المحرك.")
    return len(fatal)


# ---- 🧪 اختبارٌ ذاتيٌّ (حالاتٌ مقيسةٌ من الدوالّ نفسِها قبل كتابتها) ----
_REF = "الحمد لله رب العالمين الرحمن الرحيم"


def _it(**kw):
    base = {"id": "t1", "op": "OMIT", "refText": _REF, "wordCount": 6, "wordIndex": 2,
            "targetWord": "رب", "cutMs": [1000, 2000]}
    base.update(kw)
    return base


def selftest():
    bad = 0

    def ok(name, got, want):
        nonlocal bad
        good = got == want
        print(f"  {'✅' if good else '⛔'} {name}: {got} · المتوقَّع {want}")
        bad += 0 if good else 1

    ok("بندٌ سليمٌ ⇒ لا عطب", check_item(_it()), [])
    ok("عدُّ الكلمات يكذب ⇒ يُمسَك", check_item(_it(wordCount=9)), ["wordcount_mismatch"])
    ok("وآخرُ كلمةٍ ليست موضعَ حقن", check_item(_it(wordIndex=5)), ["index_not_internal"])
    ok("وأوّلُها كذلك", check_item(_it(wordIndex=0)), ["index_not_internal"])
    ok("وهدفٌ يخالف فهرسَه", check_item(_it(targetWord="الرحيم")), ["target_mismatch"])
    ok("وقطعٌ مقلوب", check_item(_it(cutMs=[2000, 1000])), ["cut_malformed"])

    # ⛔ **الحالةُ التي أوجدت الحارس**: مقطعان متطابقان ⇒ الصوتُ لا يتغيّر.
    sw = _it(op="SWAP", targetWord="رب ↔ العالمين", swapMs=[1000, 2000])
    ok("تبديلُ المقطع بنفسِه ⇒ قاتل", check_item(sw), ["swap_degenerate"])
    ok("وتبديلٌ سليمٌ يمرّ", check_item(_it(op="SWAP", targetWord="رب ↔ العالمين",
                                            swapMs=[2100, 3000])), [])
    # والهامشُ يقضم من الفجوة: تداخلُ 60م.ث مع `padMs=30` **مسموحٌ بالبناء** لا عطب.
    ok("وتداخلُ الهامشَين وحدَه ليس عطباً",
       check_item(_it(op="SWAP", targetWord="رب ↔ العالمين", swapMs=[1940, 2500]), pad_ms=30), [])
    ok("وفجوةٌ واسعةٌ ⇒ منبِّهٌ لا قاتل",
       check_item(_it(op="SWAP", targetWord="رب ↔ العالمين", swapMs=[2500, 3000])), ["swap_gap_wide"])

    # ⚠️ **علامةُ الوقف «كلمةٌ» في العدّ وليست كلمةً في السمع** (‏مقيسٌ: صحيحةٌ 44 من 44).
    mark = "الحمد لله ۖ العالمين الرحمن الرحيم"
    ok("هدفٌ بلا صوتٍ ⇒ منبِّهٌ يُكتب",
       check_item(_it(refText=mark, targetWord="ۖ")), ["silent_target"])
    ok("والحرفُ العربيُّ صوتٌ", (has_sound("رب"), has_sound("ۖ"), has_sound("ۗ")), (True, False, False))

    sub = _it(op="SUBSTITUTE", donor={"word": "مالك", "cutMs": [10, 900]})
    ok("واستبدالٌ سليم", check_item(sub), [])
    ok("وبلا مانحٍ ⇒ لا خطأَ مصنوع", check_item(_it(op="SUBSTITUTE")), ["donor_missing"])
    ok("ومانحٌ هو المستبدَلةُ نفسُها",
       check_item(_it(op="INSERT", donor={"word": "رب", "cutMs": [10, 900]})), ["donor_same_word"])
    ok("ومانحٌ بلا صوت",
       check_item(_it(op="INSERT", donor={"word": "ۚ", "cutMs": [10, 900]})), ["silent_donor"])

    # 🧾 وعلى مستوى الخطّة: المعرّفُ المكرَّرُ يُمسَك، والجردُ يجمع الرموز.
    plan = {"padMs": 30, "items": [_it(), _it(), _it(id="t2", wordCount=9)]}
    got = check_plan(plan)
    ok("خطّةٌ فيها مكرَّرٌ ومعطوب", {k: len(v) for k, v in sorted(got.items())},
       {"dup_id": 1, "wordcount_mismatch": 1})

    print("✅ الحارسُ سليمٌ على حالاته" if not bad else f"⛔ الحارسُ نفسُه معطوبٌ في {bad} حالة")
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("plans", nargs="*", help="ملفّاتُ خططٍ (‏يُقبل النمطُ النجميّ)")
    ap.add_argument("--selftest", action="store_true", help="يختبر الحارسَ على حالاتٍ مقيسة")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    paths = [p for pat in a.plans for p in sorted(_glob.glob(pat))]
    if not paths:
        raise SystemExit("⛔ لا خطّةَ تُفحص — سمِّ ملفّاً أو نمطاً")
    print("# 🧷 حارسُ الحقيقة الأرضيّة")
    fatal = sum(report(p, json.load(open(p, encoding="utf-8"))) for p in paths)
    print(f"\n**الحصيلة:** {len(paths)} خطّةً · أصنافُ عطبٍ قاتلٍ: **{fatal}**")
    return 1 if fatal else 0


if __name__ == "__main__":
    sys.exit(main())
